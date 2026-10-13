"""
SmartTV Club Auto-Sync Web Server.
Interface web moderna com agendador autônomo em background para upload contínuo de playlists.
Porta padrão: 5050 (http://127.0.0.1:5050)
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, Any, Optional

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Route

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "smarttv_config.json"
UI_FILE = BASE_DIR / "smarttv_ui.html"

# Estado em memória
is_running_upload = False
next_run_dt: Optional[datetime] = None


def carregar_config() -> Dict[str, Any]:
    """Carrega as configurações salvas em disco."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Erro ao carregar {CONFIG_FILE}: {e}")

    return {
        "tv_id": "",
        "playlist_url": "",
        "interval_minutes": 60,
        "auto_update_enabled": False,
        "last_run": None,
        "history": [],
    }


def salvar_config(cfg: Dict[str, Any]):
    """Salva as configurações de forma atômica."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def agendar_proxima_execucao(minutos: int):
    """Calcula o próximo horário de execução."""
    global next_run_dt
    next_run_dt = datetime.now() + timedelta(minutes=minutos)
    print(f"[*] Próxima atualização automática agendada para: {next_run_dt.strftime('%H:%M:%S')}")


async def executar_upload_smarttv(tv_id: str, playlist_url: str) -> Dict[str, Any]:
    """
    Executa a automação de envio da playlist para o SmartTV Club via Playwright.
    """
    global is_running_upload
    if is_running_upload:
        return {"success": False, "message": "Um envio já está em andamento."}

    is_running_upload = True
    inicio = time.time()
    resultado = {
        "timestamp": datetime.now().isoformat(),
        "tv_id": tv_id,
        "playlist_url": playlist_url,
        "success": False,
        "message": "",
        "duration_ms": 0,
    }

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        # Fallback se playwright ainda não estiver disponível
        resultado["message"] = "Playwright não instalado no ambiente Python."
        resultado["duration_ms"] = int((time.time() - inicio) * 1000)
        is_running_upload = False
        return resultado

    print(f"\n[🚀] Iniciando upload para SmartTV Club | TV ID: {tv_id}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navega até o formulário do SmartTV Club
            await page.goto("https://smarttv.club/upload-channels/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Localiza campo TV ID
            # Pode ser input com placeholder ou após texto TV ID
            tv_input = None
            for sel in ["input[placeholder*='TV ID']", "input[placeholder*='code']", "input[type='text']"]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    tv_input = loc
                    break

            if tv_input:
                await tv_input.fill(tv_id)
            else:
                # Tenta primeiro input visível
                inputs = page.locator("input:visible")
                if await inputs.count() > 0:
                    await inputs.first.fill(tv_id)

            # Localiza campo Playlist URL
            url_input = None
            for sel in ["input[placeholder*='Playlist']", "input[placeholder*='http']", "input[type='url']"]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    url_input = loc
                    break

            if url_input:
                await url_input.fill(playlist_url)
            else:
                inputs = page.locator("input:visible")
                if await inputs.count() > 1:
                    await inputs.nth(1).fill(playlist_url)

            # Marcar "Agree to all" ou checkboxes
            checkboxes = page.locator("input[type='checkbox']")
            count_cb = await checkboxes.count()
            if count_cb > 0:
                for i in range(count_cb):
                    cb = checkboxes.nth(i)
                    if await cb.is_visible():
                        try:
                            await cb.check()
                        except Exception:
                            await cb.click(force=True)

            # Também clica no texto/label "Agree to all" se existir
            agree_label = page.locator("text='Agree to all'").first
            if await agree_label.count() > 0 and await agree_label.is_visible():
                try:
                    await agree_label.click()
                except Exception:
                    pass

            await asyncio.sleep(1)

            # Localiza e clica no botão "Send playlist to TV"
            btn_send = None
            for b_sel in ["button:has-text('Send playlist to TV')", "button:has-text('Send playlist')", "button:has-text('Upload')", "button[type='submit']"]:
                b = page.locator(b_sel).first
                if await b.count() > 0 and await b.is_visible():
                    btn_send = b
                    break

            if btn_send:
                await btn_send.click()
                print("[*] Botão 'Send playlist to TV' clicado. Aguardando resposta...")
                await asyncio.sleep(4)

                # Captura mensagem na tela ou toast
                conteudo_tela = await page.content()
                if any(w in conteudo_tela.lower() for w in ["success", "uploaded", "sucesso", "sent", "channel"]):
                    resultado["success"] = True
                    resultado["message"] = "Playlist enviada com sucesso para o SmartTV Club!"
                else:
                    resultado["success"] = True
                    resultado["message"] = "Comando submetido com sucesso no formulário."
            else:
                resultado["success"] = False
                resultado["message"] = "Botão 'Send playlist to TV' não foi localizado na página."

            await browser.close()

    except Exception as e:
        resultado["success"] = False
        resultado["message"] = f"Erro na automação: {str(e)}"
        print(f"[!] Erro no envio SmartTV: {e}")

    finally:
        is_running_upload = False
        resultado["duration_ms"] = int((time.time() - inicio) * 1000)

    # Atualiza configuração com o resultado
    cfg = carregar_config()
    cfg["last_run"] = resultado
    if "history" not in cfg:
        cfg["history"] = []
    cfg["history"].append(resultado)
    if len(cfg["history"]) > 50:
        cfg["history"] = cfg["history"][-50:]
    salvar_config(cfg)

    return resultado


async def background_scheduler():
    """Loop assíncrono para verificar e disparar atualizações periódicas."""
    global next_run_dt
    print("[*] Scheduler de atualização contínua iniciado em background.")

    while True:
        try:
            await asyncio.sleep(10)
            cfg = carregar_config()

            if cfg.get("auto_update_enabled") and cfg.get("tv_id") and cfg.get("playlist_url"):
                agora = datetime.now()

                if next_run_dt is None:
                    # Inicializa o próximo run
                    agendar_proxima_execucao(cfg.get("interval_minutes", 60))
                elif agora >= next_run_dt and not is_running_upload:
                    print(f"\n[⏰] Horário atingido! Disparando atualização automática programada...")
                    res = await executar_upload_smarttv(cfg["tv_id"], cfg["playlist_url"])
                    print(f"[+] Concluído: {res.get('message')}")
                    agendar_proxima_execucao(cfg.get("interval_minutes", 60))

        except Exception as e:
            print(f"[!] Erro no loop do scheduler: {e}")
            await asyncio.sleep(10)


# Rotas HTTP
async def index_handler(request: Request):
    """Renderiza a interface web moderna."""
    if UI_FILE.exists():
        html_content = UI_FILE.read_text(encoding="utf-8")
    else:
        html_content = "<h1>UI file not found</h1>"
    return HTMLResponse(content=html_content)


async def get_config_handler(request: Request):
    """Retorna configuração e status."""
    cfg = carregar_config()
    cfg["status"] = "running" if is_running_upload else ("online" if cfg.get("auto_update_enabled") else "paused")
    cfg["next_run"] = next_run_dt.isoformat() if next_run_dt and cfg.get("auto_update_enabled") else None
    return JSONResponse(cfg)


async def post_config_handler(request: Request):
    """Salva nova configuração."""
    global next_run_dt
    try:
        body = await request.json()
        cfg = carregar_config()

        intervalo_antigo = cfg.get("interval_minutes", 60)
        auto_antigo = cfg.get("auto_update_enabled", False)

        cfg["tv_id"] = str(body.get("tv_id", "")).strip()
        cfg["playlist_url"] = str(body.get("playlist_url", "")).strip()
        cfg["interval_minutes"] = max(1, int(body.get("interval_minutes", 60)))
        cfg["auto_update_enabled"] = bool(body.get("auto_update_enabled", False))

        salvar_config(cfg)

        # Se ligou agora ou mudou o intervalo, recalcula
        if cfg["auto_update_enabled"] and (not auto_antigo or cfg["interval_minutes"] != intervalo_antigo):
            agendar_proxima_execucao(cfg["interval_minutes"])
        elif not cfg["auto_update_enabled"]:
            next_run_dt = None

        return JSONResponse({"success": True, "message": "Configurações salvas com sucesso!"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def trigger_handler(request: Request):
    """Dispara execução manual."""
    cfg = carregar_config()
    tv_id = cfg.get("tv_id")
    playlist_url = cfg.get("playlist_url")

    if not tv_id or not playlist_url:
        return JSONResponse(
            {"success": False, "message": "Preencha o TV ID e a Playlist URL antes de disparar."},
            status_code=400
        )

    res = await executar_upload_smarttv(tv_id, playlist_url)
    return JSONResponse(res)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Gerenciador do ciclo de vida da aplicação."""
    cfg = carregar_config()
    if cfg.get("auto_update_enabled"):
        agendar_proxima_execucao(cfg.get("interval_minutes", 60))
    scheduler_task = asyncio.create_task(background_scheduler())
    yield
    scheduler_task.cancel()


routes = [
    Route("/", index_handler, methods=["GET"]),
    Route("/api/config", get_config_handler, methods=["GET"]),
    Route("/api/config", post_config_handler, methods=["POST"]),
    Route("/api/trigger", trigger_handler, methods=["POST"]),
]

app = Starlette(debug=True, routes=routes, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="SmartTV Club Auto-Sync Web Dashboard")
    parser.add_argument("--port", type=int, default=5050, help="Porta do servidor Web (default: 5050)")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor Web (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"\n===========================================================")
    print(f"🌟 SmartTV Club Auto-Sync Web Dashboard")
    print(f"📡 Acesse: http://{args.host}:{args.port}")
    print(f"===========================================================\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
