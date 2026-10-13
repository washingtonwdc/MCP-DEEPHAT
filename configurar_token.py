"""
Script interativo para configuração e validação imediata do cookie/token DeepHat AI.
"""

import asyncio
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from client import DeepHatClient
from config import Config

console = Console()
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


async def main():
    console.print(
        Panel.fit(
            "[bold cyan]🛡️ Configuração de Autenticação - DeepHat AI[/bold cyan]\n"
            "[dim]Conexão direta com https://app.deephat.ai/[/dim]",
            border_style="cyan",
        )
    )

    console.print(
        "[bold white]Como obter o cookie de sessão:[/bold white]\n"
        "1. No navegador, acerte seu login em [link=https://app.deephat.ai/]https://app.deephat.ai/[/link]\n"
        "2. Pressione [bold]F12[/bold] -> [bold]Application[/bold] (ou Aplicativo) -> [bold]Cookies[/bold] -> [bold]https://app.deephat.ai[/bold]\n"
        "3. Copie o valor de [bold]__Secure-next-auth.session-token[/bold] (ou o cabeçalho Cookie completo da aba Network)\n"
    )

    token_ou_cookie = Prompt.ask(
        "[bold green]Cole o valor do cookie ou token de sessão aqui[/bold green]"
    ).strip()

    if not token_ou_cookie:
        console.print("[red]Nenhum valor inserido. Operação cancelada.[/red]")
        return

    # Testa se é o cookie completo ou apenas o token
    is_full_cookie = "=" in token_ou_cookie and ";" in token_ou_cookie

    # Atualiza temporariamente em memória para testar
    if is_full_cookie:
        Config.DEEPHAT_COOKIE = token_ou_cookie
        Config.DEEPHAT_SESSION_TOKEN = ""
    else:
        Config.DEEPHAT_COOKIE = ""
        Config.DEEPHAT_SESSION_TOKEN = token_ou_cookie

    console.print("\n[yellow]⏳ Testando token com a API de sessão do DeepHat...[/yellow]")
    client = DeepHatClient()
    client.cookie_header = Config.get_cookie_header()

    session_info = await client.check_web_session()
    status = session_info.get("status")

    if status == "authenticated":
        user = session_info.get("user", {})
        user_name = user.get("email") or user.get("name") or "Autenticado"
        console.print(f"[bold green]✔ Sucesso! Usuário autenticado: [cyan]{user_name}[/cyan][/bold green]\n")

        # Salvar no .env
        env_lines = []
        if ENV_PATH.exists():
            env_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

        new_lines = []
        token_written = False
        cookie_written = False

        for line in env_lines:
            if line.startswith("DEEPHAT_SESSION_TOKEN="):
                new_lines.append(f"DEEPHAT_SESSION_TOKEN={token_ou_cookie if not is_full_cookie else ''}")
                token_written = True
            elif line.startswith("DEEPHAT_COOKIE="):
                new_lines.append(f"DEEPHAT_COOKIE={token_ou_cookie if is_full_cookie else ''}")
                cookie_written = True
            else:
                new_lines.append(line)

        if not token_written:
            new_lines.append(f"DEEPHAT_SESSION_TOKEN={token_ou_cookie if not is_full_cookie else ''}")
        if not cookie_written:
            new_lines.append(f"DEEPHAT_COOKIE={token_ou_cookie if is_full_cookie else ''}")
        if not any(l.startswith("CONNECTION_MODE=") for l in new_lines):
            new_lines.append("CONNECTION_MODE=auto")

        ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        console.print(f"[bold green]✔ Arquivo [cyan]{ENV_PATH.name}[/cyan] salvo com sucesso![/bold green]")

        # Testar prompt com o modelo
        console.print("\n[yellow]⏳ Executando pergunta de teste para o DeepHat AI...[/yellow]")
        try:
            res = await client.chat("Olá DeepHat! Confirme que você está conectado respondendo com uma saudação breve.")
            console.print(f"\n[bold green]✔ Resposta do DeepHat:[/bold green]\n{res.get('content')}")
        except Exception as e:
            console.print(f"[red]Erro na inferência: {e}[/red]")

    else:
        console.print(
            f"[bold red]✖ Não foi possível validar a sessão (Status: {status}).[/bold red]\n"
            f"Detalhes: {session_info.get('message') or session_info.get('raw')}\n\n"
            "[yellow]Dica:[/yellow] Certifique-se de que fez login recente na página https://app.deephat.ai/ antes de copiar o cookie."
        )


if __name__ == "__main__":
    asyncio.run(main())
