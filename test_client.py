"""
Script de teste e diagnóstico interativo do MCP DeepHat AI.
Valida autenticação de sessão web (app.deephat.ai), conexão Kindo e execução de prompts.
"""

import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import Config
from client import DeepHatClient

console = Console()


async def main():
    console.print(
        Panel.fit(
            "[bold cyan]DeepHat AI - Diagnostic & Test Suite[/bold cyan]\n"
            "[dim]Verificação de Sessão Web (app.deephat.ai) e API Kindo[/dim]",
            border_style="cyan",
        )
    )

    table = Table(title="Configuração Atual", show_header=True, header_style="bold magenta")
    table.add_column("Parâmetro", style="dim")
    table.add_column("Valor")
    table.add_column("Status")

    has_web = Config.is_web_auth_configured()
    has_api = Config.is_api_auth_configured()

    table.add_row(
        "Web Endpoint",
        Config.DEEPHAT_CHAT_ENDPOINT,
        "🟢 Configurado",
    )
    table.add_row(
        "Cookie / Sessão Web",
        f"Definido ({len(Config.get_cookie_header())} chars)" if has_web else "Não definido",
        "🟢 Presente" if has_web else "🟡 Vazio (.env)",
    )
    table.add_row(
        "Chave Kindo (API)",
        "Configurada" if has_api else "Não definida",
        "🟢 Presente" if has_api else "⚪ Opcional",
    )
    table.add_row(
        "Modo de Operação",
        Config.CONNECTION_MODE,
        "🟢 Ativo",
    )

    console.print(table)
    console.print()

    client = DeepHatClient()

    # 1. Testar sessão Web no app.deephat.ai
    console.print("[bold yellow]1. Testando endpoint de autenticação do app.deephat.ai...[/bold yellow]")
    try:
        session_info = await client.check_web_session()
        st = session_info.get("status")
        if st == "authenticated":
            user = session_info.get("user", {})
            console.print(
                f"[bold green]✔ Sessão Web Válida![/bold green] Usuário: [cyan]{user.get('email') or user.get('name')}[/cyan]"
            )
        elif st == "unauthenticated":
            console.print(
                "[yellow]⚠ Sessão Web não autenticada.[/yellow] O site retornou sessão vazia.\n"
                "[dim]Para conectar diretamente com o site, insira o cookie da sua conta em DEEPHAT_COOKIE no .env.[/dim]"
            )
        else:
            console.print(f"[red]✖ Resposta inesperada da sessão web: {session_info}[/red]")
    except Exception as e:
        console.print(f"[red]✖ Falha ao contatar endpoint de sessão: {e}[/red]")

    console.print()

    # 2. Testar Inferência (se houver credenciais)
    if not has_web and not has_api:
        console.print(
            Panel(
                "[bold yellow]Nenhuma credencial configurada no .env![/bold yellow]\n\n"
                "Para ativar o MCP:\n"
                "1. Copie o arquivo [bold].env.example[/bold] para [bold].env[/bold]\n"
                "2. Faça login em [cyan]https://app.deephat.ai/[/cyan]\n"
                "3. No DevTools (F12) -> Application -> Cookies -> copie o cookie para [bold]DEEPHAT_COOKIE[/bold]\n"
                "4. Execute novamente este teste: [bold].\\testar_conexao.bat[/bold]",
                border_style="yellow",
            )
        )
        return

    console.print("[bold yellow]2. Testando envio de mensagem para o DeepHat AI...[/bold yellow]")
    prompt_teste = "Qual a importância de um modelo uncensored para equipes de Red Teaming e segurança ofensiva? Responda em 3 tópicos curtos."
    
    try:
        res = await client.chat(prompt_teste)
        src = res.get("source")
        content = res.get("content", "")
        
        console.print(f"[bold green]✔ Resposta recebida com sucesso via {src}![/bold green]\n")
        console.print(Panel(content, title=f"Resposta do DeepHat ({src})", border_style="green"))
    except Exception as e:
        console.print(f"[bold red]✖ Falha no teste de inferência:[/bold red] {e}")


if __name__ == "__main__":
    asyncio.run(main())
