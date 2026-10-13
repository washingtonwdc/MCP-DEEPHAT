"""
Módulo de Configuração do MCP DeepHat AI.
Carrega variáveis de ambiente e define os parâmetros de conexão.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Config:
    # URL base da plataforma web oficial
    DEEPHAT_WEB_URL: str = os.getenv("DEEPHAT_WEB_URL", "https://app.deephat.ai")
    DEEPHAT_CHAT_ENDPOINT: str = os.getenv(
        "DEEPHAT_CHAT_ENDPOINT", "https://app.deephat.ai/api/chat"
    )

    # Autenticação via Sessão Web (Cookie completo extraído do DevTools / F12)
    # Exemplo: "__Secure-next-auth.session-token=eyJhbGciOi..." ou string de cookies completa
    DEEPHAT_COOKIE: str = os.getenv("DEEPHAT_COOKIE", "").strip()

    # Token de sessão individual (caso fornecido separadamente)
    DEEPHAT_SESSION_TOKEN: str = os.getenv("DEEPHAT_SESSION_TOKEN", "").strip()

    # User-Agent para emulação fiel do navegador
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    )

    # API Key opcional (Fallback para Kindo / DeepHat API direta)
    KINDO_API_KEY: str = os.getenv("KINDO_API_KEY", "").strip()
    KINDO_API_BASE: str = os.getenv("KINDO_API_BASE", "https://api.kindo.ai/v1").rstrip("/")
    DEEPHAT_MODEL: str = os.getenv("DEEPHAT_MODEL", "DeepHat/DeepHat-V1-7B")

    # Timeout de requisições em segundos
    TIMEOUT_SECONDS: float = float(os.getenv("TIMEOUT_SECONDS", "120.0"))

    # Modo de conexão preferencial ('web' ou 'api' ou 'auto')
    CONNECTION_MODE: str = os.getenv("CONNECTION_MODE", "auto").lower()

    @classmethod
    def get_cookie_header(cls) -> str:
        """Monta o header de Cookie priorizando DEEPHAT_COOKIE ou DEEPHAT_SESSION_TOKEN com suporte a Auth.js v5 e NextAuth."""
        if cls.DEEPHAT_COOKIE:
            return cls.DEEPHAT_COOKIE
        if cls.DEEPHAT_SESSION_TOKEN:
            token = cls.DEEPHAT_SESSION_TOKEN.strip()
            # Se já veio no formato 'chave=valor', retorna diretamente
            if "=" in token and ";" in token:
                return token
            # Inclui todas as variantes de cookies de sessão (Auth.js v5 e NextAuth)
            cookies = [
                f"__Secure-authjs.session-token={token}",
                f"authjs.session-token={token}",
                f"__Secure-next-auth.session-token={token}",
                f"next-auth.session-token={token}",
            ]
            return "; ".join(cookies)
        return ""

    @classmethod
    def is_web_auth_configured(cls) -> bool:
        return bool(cls.get_cookie_header())

    @classmethod
    def is_api_auth_configured(cls) -> bool:
        return bool(cls.KINDO_API_KEY)
