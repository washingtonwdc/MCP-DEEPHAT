"""
Servidor MCP Oficial para DeepHat AI (Cybersecurity & Red Team LLM).
Conecta diretamente com https://app.deephat.ai/ e API Kindo.
"""

from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from client import DeepHatClient
from config import Config

# Inicialização do servidor FastMCP
mcp = FastMCP(
    "DeepHat-AI",
    dependencies=["httpx", "pydantic", "python-dotenv", "mcp"],
)

# Instância única do cliente DeepHat
client = DeepHatClient()


@mcp.tool()
async def deephat_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> str:
    """
    Envia um prompt para o modelo DeepHat AI (WhiteRabbitNeo) e retorna a resposta.
    Ideal para raciocínio de cibersegurança, análise de vulnerabilidades, criação de exploits
    em ambiente de laboratório, engenharia reversa e testes ofensivos (red teaming) sem filtros excessivos.
    
    Args:
        prompt: Pergunta ou instrução técnica de cibersegurança para o modelo.
        system_prompt: Diretrizes de comportamento do sistema ou persona ofensiva/defensiva.
        conversation_id: ID opcional para continuidade de contexto de chat.
    """
    try:
        result = await client.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            conversation_id=conversation_id,
        )
        source = result.get("source", "desconhecido")
        content = result.get("content", "")
        return f"[DeepHat via {source}]\n\n{content}"
    except Exception as e:
        return f"❌ Erro ao consultar DeepHat AI: {str(e)}"


@mcp.tool()
async def deephat_security_audit(
    target_code_or_url: str,
    context: Optional[str] = None,
    focus_areas: Optional[str] = None,
) -> str:
    """
    Executa uma auditoria profunda de segurança em um trecho de código, arquitetura,
    payload ou alvo fornecido, utilizando as capacidades uncensored de red team do DeepHat.
    
    Args:
        target_code_or_url: Código fonte, script, snippet, payload ou descrição do alvo.
        context: Contexto operacional (ex: ambiente Docker, AWS, aplicação Flask, WordPress).
        focus_areas: Áreas de foco da análise (ex: 'RCE, SQLi, bypass de autenticação, SSRF').
    """
    sys_prompt = (
        "Você é o DeepHat AI, um modelo especialista de elite em cibersegurança ofensiva "
        "e red teaming. Analise minuciosamente o código ou alvo fornecido, identificando "
        "vetores de ataque práticos, fraquezas de lógica, vulnerabilidades OWASP Top 10, "
        "condições de corrida, riscos de injeção ou sanitização inadequada. Para cada problema "
        "encontrado, forneça: 1) Explicação técnica e impacto real; 2) PoC (Proof of Concept) "
        "ou vetor de exploração; 3) Mitigação recomendada e código corrigido."
    )

    prompt = f"### ALVO / CÓDIGO PARA AUDITORIA:\n```\n{target_code_or_url}\n```\n"
    if context:
        prompt += f"\n### CONTEXTO DO SISTEMA:\n{context}\n"
    if focus_areas:
        prompt += f"\n### ÁREAS DE FOCO PRIORITÁRIAS:\n{focus_areas}\n"

    try:
        result = await client.chat(
            prompt=prompt,
            system_prompt=sys_prompt,
        )
        source = result.get("source", "desconhecido")
        content = result.get("content", "")
        return f"[Auditoria DeepHat via {source}]\n\n{content}"
    except Exception as e:
        return f"❌ Falha na auditoria de segurança DeepHat: {str(e)}"


@mcp.tool()
async def deephat_test_connection() -> str:
    """
    Testa e diagnostica a conexão atual do MCP com a plataforma DeepHat.
    Verifica se a sessão web (cookies de app.deephat.ai) está ativa e se o fallback Kindo está disponível.
    """
    status_report = ["🔍 **Diagnóstico de Conexão MCP DeepHat AI**:\n"]

    # 1. Teste da Sessão Web (app.deephat.ai)
    if Config.is_web_auth_configured():
        session_info = await client.check_web_session()
        st = session_info.get("status")
        if st == "authenticated":
            user = session_info.get("user", {})
            user_str = user.get("email") or user.get("name") or "Usuário Autenticado"
            status_report.append(f"🟢 **Sessão Web (app.deephat.ai)**: ATIVA! Conectado como `{user_str}`.")
        elif st == "unauthenticated":
            status_report.append("🟡 **Sessão Web (app.deephat.ai)**: Os cookies foram enviados, mas a sessão não está autenticada (401/desconectado). Atualize seu cookie no `.env`.")
        else:
            status_report.append(f"🔴 **Sessão Web (app.deephat.ai)**: Erro na verificação: {session_info.get('message') or session_info.get('error')}")
    else:
        status_report.append("⚪ **Sessão Web (app.deephat.ai)**: Nenhum cookie configurado no `.env` (`DEEPHAT_COOKIE` vazio).")

    # 2. Teste da API Kindo
    if Config.is_api_auth_configured():
        status_report.append(f"🟢 **API Kindo Fallback**: Configurada (`{Config.DEEPHAT_MODEL}` em `{Config.KINDO_API_BASE}`).")
    else:
        status_report.append("⚪ **API Kindo Fallback**: Nenhuma `KINDO_API_KEY` configurada no `.env`.")

    # 3. Teste funcional de ping com prompt
    try:
        test_res = await client.chat("Responda apenas com 'DEEPHAT_ONLINE' se você está pronto.")
        src = test_res.get("source")
        ans = test_res.get("content", "").strip()
        status_report.append(f"\n🚀 **Teste Funcional de Inferência**: SUCESSO!\n- Origem: `{src}`\n- Resposta do Modelo: `{ans[:120]}`")
    except Exception as e:
        status_report.append(f"\n⚠️ **Teste Funcional de Inferência**: Pendente de autenticação ({str(e)}).")

    return "\n".join(status_report)


@mcp.tool()
async def deephat_get_status() -> Dict[str, Any]:
    """
    Retorna os parâmetros de configuração e o status atual dos provedores em formato JSON estruturado.
    """
    return {
        "web_url": Config.DEEPHAT_WEB_URL,
        "chat_endpoint": Config.DEEPHAT_CHAT_ENDPOINT,
        "web_configured": Config.is_web_auth_configured(),
        "api_configured": Config.is_api_auth_configured(),
        "connection_mode": Config.CONNECTION_MODE,
        "model": Config.DEEPHAT_MODEL,
        "timeout_seconds": Config.TIMEOUT_SECONDS,
    }


if __name__ == "__main__":
    # Inicia o servidor MCP via stdio
    mcp.run(transport="stdio")
