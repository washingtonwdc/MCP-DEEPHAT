"""
Cliente HTTP assíncrono para conexão com o DeepHat AI (app.deephat.ai e API Kindo).
Gerencia autenticação de sessão web, parsing de fluxos Vercel AI SDK / SSE e fallback.
"""

import json
import uuid
import re
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from config import Config


class DeepHatClient:
    def __init__(self):
        self.cookie_header = Config.get_cookie_header()
        self.kindo_key = Config.KINDO_API_KEY
        self.web_endpoint = Config.DEEPHAT_CHAT_ENDPOINT
        self.kindo_endpoint = f"{Config.KINDO_API_BASE}/chat/completions"
        self.timeout = Config.TIMEOUT_SECONDS

    def _get_web_headers(self) -> Dict[str, str]:
        """Headers HTTP emulando o navegador oficial no app.deephat.ai."""
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://app.deephat.ai",
            "Referer": "https://app.deephat.ai/",
            "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="133", "Google Chrome";v="133"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": Config.USER_AGENT,
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        return headers

    def _parse_vercel_ai_stream(self, chunk_text: str) -> str:
        """
        Interpreta chunks no protocolo Vercel AI SDK Data Stream.
        Formato típico:
          0:"Texto incremental"
          d:{"finishReason":"stop",...}
        """
        extracted = []
        for line in chunk_text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Prefixo 0: representa texto do modelo
            if line.startswith("0:"):
                raw_json = line[2:]
                try:
                    text_part = json.loads(raw_json)
                    if isinstance(text_part, str):
                        extracted.append(text_part)
                except Exception:
                    # Se falhar o parse JSON puro, remove aspas periféricas
                    cleaned = raw_json.strip('"').replace('\\"', '"').replace('\\n', '\n')
                    extracted.append(cleaned)

            # Suporte a SSE padrão (data: ...)
            elif line.startswith("data:"):
                data_content = line[5:].strip()
                if data_content == "[DONE]":
                    continue
                try:
                    parsed = json.loads(data_content)
                    if isinstance(parsed, dict):
                        # Padrão OpenAI / Delta
                        delta = parsed.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if delta:
                            extracted.append(delta)
                        elif "text" in parsed:
                            extracted.append(parsed["text"])
                except Exception:
                    extracted.append(data_content)

        return "".join(extracted)

    async def check_web_session(self) -> Dict[str, Any]:
        """Verifica o estado da sessão de autenticação no app.deephat.ai."""
        session_url = f"{Config.DEEPHAT_WEB_URL}/api/auth/session"
        headers = self._get_web_headers()

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                resp = await client.get(session_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    is_logged = bool(data and data.get("user"))
                    return {
                        "status": "authenticated" if is_logged else "unauthenticated",
                        "status_code": resp.status_code,
                        "user": data.get("user") if is_logged else None,
                        "raw": data,
                    }
                return {
                    "status": "error",
                    "status_code": resp.status_code,
                    "message": resp.text[:200],
                }
            except Exception as e:
                return {
                    "status": "exception",
                    "error": str(e),
                }

    async def chat_web(
        self,
        messages: List[Dict[str, str]],
        conversation_id: Optional[str] = None,
    ) -> str:
        """Envia mensagem diretamente para https://app.deephat.ai/api/chat via sessão web."""
        if not self.cookie_header:
            raise ValueError(
                "Nenhum cookie de sessão web configurado. Adicione DEEPHAT_COOKIE ou "
                "DEEPHAT_SESSION_TOKEN no arquivo .env."
            )

        chat_id = conversation_id or str(uuid.uuid4())
        payload = {
            "messages": messages,
            "id": chat_id,
            "previewToken": None,
        }

        headers = self._get_web_headers()

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.post(
                    self.web_endpoint,
                    json=payload,
                    headers=headers,
                )
            except httpx.RequestError as e:
                raise ConnectionError(f"Falha de rede ao conectar com {self.web_endpoint}: {e}")

            if response.status_code == 401:
                raise PermissionError(
                    "Erro 401 Unauthorized no app.deephat.ai: O cookie de sessão expirou ou é inválido. "
                    "Faça login novamente no navegador e copie o cookie atualizado para o .env."
                )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Erro retornado por {self.web_endpoint} (HTTP {response.status_code}): {response.text[:500]}"
                )

            content_type = response.headers.get("content-type", "")
            raw_body = response.text

            # Se a resposta vier no formato de stream Vercel AI SDK
            if "text/plain" in content_type or "text/event-stream" in content_type or "0:\"" in raw_body:
                parsed_text = self._parse_vercel_ai_stream(raw_body)
                if parsed_text:
                    return parsed_text
                return raw_body.strip()

            # Caso venha como JSON direto
            try:
                json_data = response.json()
                if isinstance(json_data, dict):
                    if "text" in json_data:
                        return json_data["text"]
                    if "content" in json_data:
                        return json_data["content"]
                    if "message" in json_data:
                        return json_data["message"]
                return json.dumps(json_data, ensure_ascii=False)
            except Exception:
                return raw_body.strip()

    async def chat_kindo(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
    ) -> str:
        """Envia mensagem via API oficial Kindo / DeepHat (OpenAI-compatible)."""
        if not self.kindo_key:
            raise ValueError(
                "Nenhuma chave KINDO_API_KEY configurada no .env para uso via API direta."
            )

        headers = {
            "Authorization": f"Bearer {self.kindo_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or Config.DEEPHAT_MODEL,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(self.kindo_endpoint, json=payload, headers=headers)
            except httpx.RequestError as e:
                raise ConnectionError(f"Erro ao conectar na API Kindo ({self.kindo_endpoint}): {e}")

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Erro retornado pela API Kindo (HTTP {resp.status_code}): {resp.text[:500]}"
                )

            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return json.dumps(data, ensure_ascii=False)

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Roteador inteligente:
        Executa a inferência priorizando a conexão Web direta (app.deephat.ai),
        com fallback automático para a API Kindo caso configurada.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        mode = Config.CONNECTION_MODE

        # 1. Modo explícito de API
        if mode == "api":
            response_text = await self.chat_kindo(messages)
            return {
                "source": "kindo_api",
                "model": Config.DEEPHAT_MODEL,
                "content": response_text,
            }

        # 2. Modo Web ou Auto (prioriza web direta)
        if Config.is_web_auth_configured():
            try:
                response_text = await self.chat_web(messages, conversation_id=conversation_id)
                return {
                    "source": "web_session_app_deephat",
                    "endpoint": self.web_endpoint,
                    "content": response_text,
                }
            except Exception as e:
                # Se falhar e houver chave Kindo configurada, realiza fallback
                if Config.is_api_auth_configured() and mode != "web":
                    response_text = await self.chat_kindo(messages)
                    return {
                        "source": "kindo_api_fallback",
                        "fallback_reason": str(e),
                        "model": Config.DEEPHAT_MODEL,
                        "content": response_text,
                    }
                raise e

        # 3. Caso não haja cookie web mas haja KINDO_API_KEY
        if Config.is_api_auth_configured():
            response_text = await self.chat_kindo(messages)
            return {
                "source": "kindo_api",
                "model": Config.DEEPHAT_MODEL,
                "content": response_text,
            }

        raise ValueError(
            "Nenhuma credencial configurada. Configure DEEPHAT_COOKIE / DEEPHAT_SESSION_TOKEN "
            "(para conexão direta com app.deephat.ai) ou KINDO_API_KEY no arquivo .env."
        )
