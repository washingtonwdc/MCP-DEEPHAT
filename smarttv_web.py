"""
SmartTV Club Auto-Sync Web Server (Multi-Equipamento).
Gerencia múltiplos equipamentos (TV IDs), compartilha a mesma Playlist IPTV
e executa atualizações automáticas e manuais periódicas via Playwright.
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
from typing import Dict, Any, List, Optional

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
is_running_batch = False
current_running_device_id: Optional[int] = None
next_run_dt: Optional[datetime] = None


def carregar_config() -> Dict[str, Any]:
    """Carrega as configurações salvas em disco."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Garante chaves padrões
                if "devices" not in data:
                    data["devices"] = []
                if "master_playlist_url" not in data:
                    data["master_playlist_url"] = data.get("playlist_url", "")
                return data
        except Exception as e:
            print(f"[!] Erro ao carregar {CONFIG_FILE}: {e}")

    # Config padrão com 10 equipamentos iniciais
    return {
        "master_playlist_url": "",
        "interval_minutes": 60,
        "auto_update_enabled": False,
        "devices": [
            {"id": i, "name": f"Equipamento {i:02d}", "tv_id": "", "enabled": True, "last_sync": None, "status": "idle"}
            for i in range(1, 11)
        ],
        "last_run": None,
        "history": [],
    }


def salvar_config(cfg: Dict[str, Any]):
    """Salva as configurações de forma atômica."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def calcular_proxima_meia_noite_brasilia() -> datetime:
    """Calcula o próximo dia às 00:00:00 (Horário Oficial de Brasília)."""
    agora = datetime.now()
    amanha = agora.date() + timedelta(days=1)
    return datetime(amanha.year, amanha.month, amanha.day, 0, 0, 0)


def agendar_proxima_execucao(minutos: int):
    """Calcula o próximo horário de execução."""
    global next_run_dt
    next_run_dt = datetime.now() + timedelta(minutes=minutos)
    print(f"[*] Próxima atualização automática agendada para: {next_run_dt.strftime('%H:%M:%S')}")


async def executar_upload_individual(device: Dict[str, Any], playlist_url: str) -> Dict[str, Any]:
    """
    Executa a automação de envio da playlist para um equipamento individual no SmartTV Club.
    """
    tv_id = device.get("tv_id", "").strip()
    device_name = device.get("name", f"Equipamento #{device.get('id')}")

    resultado = {
        "device_id": device.get("id"),
        "device_name": device_name,
        "tv_id": tv_id,
        "playlist_url": playlist_url,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "message": "",
        "duration_ms": 0,
    }

    if not tv_id:
        resultado["message"] = "TV ID vazio. Preencha o código do equipamento."
        return resultado

    if not playlist_url:
        resultado["message"] = "Playlist URL mestre não configurada."
        return resultado

    inicio = time.time()
    print(f"[🚀] Enviando playlist para {device_name} (TV ID: {tv_id})...")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        resultado["message"] = "Playwright não instalado no ambiente."
        return resultado

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto("https://smarttv.club/upload-channels/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1.5)

            # Localiza campo TV ID
            tv_input = None
            for sel in ["input[placeholder*='TV ID']", "input[placeholder*='code']", "input[type='text']"]:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    tv_input = loc
                    break

            if tv_input:
                await tv_input.fill(tv_id)
            else:
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

            # Marcar checkboxes ("Agree to all")
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

            agree_label = page.locator("text='Agree to all'").first
            if await agree_label.count() > 0 and await agree_label.is_visible():
                try:
                    await agree_label.click()
                except Exception:
                    pass

            await asyncio.sleep(0.5)

            # Clica no botão "Send playlist to TV"
            btn_send = None
            for b_sel in ["button:has-text('Send playlist to TV')", "button:has-text('Send playlist')", "button[type='submit']"]:
                b = page.locator(b_sel).first
                if await b.count() > 0 and await b.is_visible():
                    btn_send = b
                    break

            if btn_send:
                await btn_send.click()
                await asyncio.sleep(3)

                conteudo_tela = await page.content()
                if any(w in conteudo_tela.lower() for w in ["success", "uploaded", "sucesso", "sent", "channel"]):
                    resultado["success"] = True
                    resultado["message"] = "Playlist enviada com sucesso!"
                else:
                    resultado["success"] = True
                    resultado["message"] = "Formulário submetido com sucesso."
            else:
                resultado["success"] = False
                resultado["message"] = "Botão 'Send playlist to TV' não localizado."

            await browser.close()

    except Exception as e:
        resultado["success"] = False
        resultado["message"] = f"Erro no envio: {str(e)}"
        print(f"[!] Erro ao enviar para {device_name}: {e}")

    finally:
        resultado["duration_ms"] = int((time.time() - inicio) * 1000)

    return resultado


async def executar_upload_em_lote() -> List[Dict[str, Any]]:
    """
    Executa o upload da Playlist Mestre para TODOS os equipamentos ativos.
    """
    global is_running_batch, current_running_device_id
    if is_running_batch:
        return []

    is_running_batch = True
    cfg = carregar_config()
    playlist_mestre = cfg.get("master_playlist_url", "").strip()
    dispositivos = cfg.get("devices", [])
    resultados = []

    if not playlist_mestre:
        print("[!] Não é possível sincronizar: Nenhuma Playlist Mestre configurada.")
        is_running_batch = False
        return []

    dispositivos_ativos = [d for d in dispositivos if d.get("enabled", True) and d.get("tv_id", "").strip()]
    print(f"\n[🚀] Iniciando sincronização em lote para {len(dispositivos_ativos)} equipamentos ativos...")

    for dev in dispositivos_ativos:
        current_running_device_id = dev["id"]
        # Atualiza status visual em tempo de execução
        dev["status"] = "syncing"
        salvar_config(cfg)

        res = await executar_upload_individual(dev, playlist_mestre)
        resultados.append(res)

        # Atualiza status do dispositivo
        dev["status"] = "success" if res["success"] else "error"
        dev["last_sync"] = res["timestamp"]
        salvar_config(cfg)

        # Intervalo de segurança entre cada envio (evita rate limit no site)
        await asyncio.sleep(2)

    current_running_device_id = None
    is_running_batch = False

    # Registra no histórico geral
    if "history" not in cfg:
        cfg["history"] = []
    cfg["history"].extend(resultados)
    if len(cfg["history"]) > 60:
        cfg["history"] = cfg["history"][-60:]
    cfg["last_run"] = resultados[-1] if resultados else None
    salvar_config(cfg)

    print(f"[✅] Sincronização em lote finalizada com sucesso!")
    return resultados


async def background_scheduler():
    """Loop assíncrono para verificar e disparar atualizações periódicas ou por data agendada."""
    global next_run_dt
    print("[*] Scheduler de atualização contínua iniciado em background.")

    while True:
        try:
            await asyncio.sleep(10)
            cfg = carregar_config()

            if cfg.get("auto_update_enabled") and cfg.get("master_playlist_url"):
                agora = datetime.now()
                sync_mode = cfg.get("sync_mode", "interval")
                scheduled_str = cfg.get("scheduled_datetime")

                # Modo 1 (Principal): Sincronização Diária às 00:00 (Horário de Brasília)
                if sync_mode == "daily_midnight_brasilia":
                    if next_run_dt is None:
                        next_run_dt = calcular_proxima_meia_noite_brasilia()
                        print(f"[*] Próxima sincronização diária agendada para: {next_run_dt.strftime('%d/%m/%Y às 00:00:00 (Brasília)')}")
                    elif agora >= next_run_dt and not is_running_batch:
                        print(f"\n[🕛 00:00 BRASÍLIA] Horário diário atingido! Iniciando ciclo de renovação e sincronização...")
                        try:
                            import mailtm_manager
                            novo_email, _, token = mailtm_manager.criar_email()
                            cfg["temp_email"] = novo_email
                            print(f"[📬] Novo e-mail diário criado para receber a playlist: {novo_email}")
                            
                            # Verifica mensagens para extrair o link da nova playlist
                            msgs = mailtm_manager.extrair_links_confirmacao(token)
                            link_playlist = None
                            for m in msgs:
                                for l in m.get("todos_links", []):
                                    if any(p in l.lower() for p in [".m3u", ".m3u8", "get.php", "type=m3u", "playlist"]):
                                        link_playlist = l
                                        break
                                if link_playlist:
                                    break
                            
                            if link_playlist:
                                cfg["master_playlist_url"] = link_playlist
                                cfg["new_playlist_url"] = link_playlist
                                print(f"[✨] Link da nova playlist extraído do e-mail: {link_playlist}")
                            cfg["last_playlist_check"] = datetime.now().isoformat()
                            salvar_config(cfg)
                        except Exception as e_mail:
                            print(f"[!] Erro ao processar e-mail diário: {e_mail}")

                        # Sincroniza todos os equipamentos ativos (Celular e iPad de Washington inclusos)
                        await executar_upload_em_lote()
                        # Reagenda para a próxima meia-noite
                        next_run_dt = calcular_proxima_meia_noite_brasilia()
                        print(f"[*] Próxima sincronização diária reagendada para: {next_run_dt.strftime('%d/%m/%Y às 00:00:00')}")

                # Modo 2: Data e Hora específica agendada
                elif sync_mode == "datetime" and scheduled_str:
                    try:
                        scheduled_dt = datetime.fromisoformat(scheduled_str)
                        if agora >= scheduled_dt and not is_running_batch:
                            print(f"\n[📅] Data/Hora Agendada atingida ({scheduled_str})! Disparando sincronização...")
                            await executar_upload_em_lote()
                            # Desativa após execução única de data marcada
                            cfg["auto_update_enabled"] = False
                            cfg["scheduled_datetime"] = ""
                            salvar_config(cfg)
                            next_run_dt = None
                    except Exception as err:
                        print(f"[!] Erro ao processar data agendada: {err}")

                # Modo 3: Intervalo recorrente em minutos (fallback opcional)
                elif sync_mode == "interval":
                    if next_run_dt is None:
                        agendar_proxima_execucao(cfg.get("interval_minutes", 60))
                    elif agora >= next_run_dt and not is_running_batch:
                        print(f"\n[⏰] Horário atingido! Disparando atualização automática para todos os equipamentos...")
                        await executar_upload_em_lote()
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
    """Retorna configuração global, equipamentos e status."""
    cfg = carregar_config()
    cfg["is_syncing"] = is_running_batch
    cfg["current_device_id"] = current_running_device_id
    cfg["status"] = "running" if is_running_batch else ("online" if cfg.get("auto_update_enabled") else "paused")
    
    # Próxima execução
    if cfg.get("auto_update_enabled"):
        if cfg.get("sync_mode") == "datetime" and cfg.get("scheduled_datetime"):
            cfg["next_run"] = cfg["scheduled_datetime"]
        elif next_run_dt:
            cfg["next_run"] = next_run_dt.isoformat()
        else:
            cfg["next_run"] = None
    else:
        cfg["next_run"] = None

    return JSONResponse(cfg)


async def post_config_handler(request: Request):
    """Salva configurações globais e/ou lista de equipamentos."""
    global next_run_dt
    try:
        body = await request.json()
        cfg = carregar_config()

        intervalo_antigo = cfg.get("interval_minutes", 60)
        auto_antigo = cfg.get("auto_update_enabled", False)

        if "master_playlist_url" in body:
            cfg["master_playlist_url"] = str(body["master_playlist_url"]).strip()
        if "interval_minutes" in body:
            cfg["interval_minutes"] = max(1, int(body["interval_minutes"]))
        if "auto_update_enabled" in body:
            cfg["auto_update_enabled"] = bool(body["auto_update_enabled"])
        if "sync_mode" in body:
            cfg["sync_mode"] = str(body["sync_mode"])
        if "scheduled_datetime" in body:
            cfg["scheduled_datetime"] = str(body["scheduled_datetime"]).strip()
        if "temp_email" in body:
            cfg["temp_email"] = str(body["temp_email"]).strip()
        if "devices" in body and isinstance(body["devices"], list):
            cfg["devices"] = body["devices"]

        salvar_config(cfg)

        if cfg["auto_update_enabled"]:
            if cfg.get("sync_mode") == "daily_midnight_brasilia":
                next_run_dt = calcular_proxima_meia_noite_brasilia()
            elif cfg.get("sync_mode") == "datetime" and cfg.get("scheduled_datetime"):
                try:
                    next_run_dt = datetime.fromisoformat(cfg["scheduled_datetime"])
                except Exception:
                    next_run_dt = None
            elif not auto_antigo or cfg["interval_minutes"] != intervalo_antigo:
                agendar_proxima_execucao(cfg["interval_minutes"])
        else:
            next_run_dt = None

        return JSONResponse({"success": True, "message": "Configurações salvas com sucesso!"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def check_playlist_from_email_handler(request: Request):
    """Verifica e-mails recebidos na conta ativa e extrai automaticamente o link da nova playlist IPTV."""
    try:
        import mailtm_manager
        cfg = carregar_config()
        email_ativo = cfg.get("temp_email", "")
        dados = mailtm_manager.carregar_dados()
        contas = dados.get("contas", [])

        conta = next((c for c in contas if c.get("email") == email_ativo), None)
        if not conta:
            for k, v in dados.items():
                if isinstance(v, dict) and v.get("email") == email_ativo:
                    conta = v
                    break

        if not conta or not conta.get("token"):
            return JSONResponse({"success": False, "error": f"Conta '{email_ativo}' sem token ou não encontrada."}, status_code=404)

        msgs = mailtm_manager.extrair_links_confirmacao(conta["token"])
        playlist_link = None

        for m in msgs:
            for l in m.get("todos_links", []):
                if any(p in l.lower() for p in [".m3u", ".m3u8", "get.php", "type=m3u", "playlist"]):
                    playlist_link = l
                    break
            if playlist_link:
                break

        cfg["last_playlist_check"] = datetime.now().isoformat()

        if playlist_link:
            cfg["master_playlist_url"] = playlist_link
            cfg["new_playlist_url"] = playlist_link
            salvar_config(cfg)
            return JSONResponse({
                "success": True,
                "found": True,
                "playlist_url": playlist_link,
                "message": "Nova playlist identificada e configurada com sucesso para todos os aparelhos!",
                "total_messages": len(msgs)
            })
        else:
            salvar_config(cfg)
            return JSONResponse({
                "success": True,
                "found": False,
                "playlist_url": cfg.get("master_playlist_url", ""),
                "message": "Nenhuma nova playlist identificada nas mensagens recentes ainda.",
                "total_messages": len(msgs)
            })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def renew_daily_email_handler(request: Request):
    """Gera um novo e-mail no Mail.tm especificamente para o ciclo diário."""
    try:
        import mailtm_manager
        endereco, senha, token = mailtm_manager.criar_email()
        cfg = carregar_config()
        cfg["temp_email"] = endereco
        salvar_config(cfg)
        return JSONResponse({
            "success": True,
            "email": endereco,
            "password": senha,
            "message": f"Novo e-mail diário ({endereco}) criado com sucesso para receber a playlist!"
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def create_mailtm_account_handler(request: Request):
    """Cria uma nova conta temporária no Mail.tm sob demanda."""
    try:
        import mailtm_manager
        endereco, senha, token = mailtm_manager.criar_email()
        cfg = carregar_config()
        cfg["temp_email"] = endereco
        salvar_config(cfg)
        return JSONResponse({
            "success": True,
            "email": endereco,
            "password": senha,
            "message": "Conta Mail.tm criada com sucesso!"
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def list_mailtm_accounts_handler(request: Request):
    """Retorna todas as contas criadas salvas em emails.json."""
    try:
        import mailtm_manager
        dados = mailtm_manager.carregar_dados()
        contas = dados.get("contas", [])
        cfg = carregar_config()
        email_ativo = cfg.get("temp_email", "")

        resultado = []
        for c in contas:
            resultado.append({
                "email": c.get("email"),
                "senha": c.get("senha"),
                "data": c.get("data"),
                "criado_em": c.get("criado_em"),
                "is_active": c.get("email") == email_ativo,
                "has_token": bool(c.get("token"))
            })

        resultado.sort(key=lambda x: str(x.get("criado_em", "")), reverse=True)
        return JSONResponse({"success": True, "accounts": resultado, "active_email": email_ativo})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def get_mailtm_messages_handler(request: Request):
    """Busca as mensagens recebidas de uma conta Mail.tm específica."""
    try:
        import mailtm_manager
        target_email = request.query_params.get("email", "").strip()
        dados = mailtm_manager.carregar_dados()
        contas = dados.get("contas", [])

        if not target_email:
            cfg = carregar_config()
            target_email = cfg.get("temp_email", "")

        conta = next((c for c in contas if c.get("email") == target_email), None)
        if not conta:
            for k, v in dados.items():
                if isinstance(v, dict) and v.get("email") == target_email:
                    conta = v
                    break

        if not conta or not conta.get("token"):
            return JSONResponse({"success": False, "error": f"Conta '{target_email}' não encontrada ou sem token de acesso."}, status_code=404)

        token = conta["token"]
        msgs = mailtm_manager.extrair_links_confirmacao(token)
        return JSONResponse({"success": True, "email": target_email, "messages": msgs, "total": len(msgs)})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def select_mailtm_account_handler(request: Request):
    """Define uma das contas existentes como a conta temporária ativa."""
    try:
        body = await request.json()
        email = body.get("email", "").strip()
        if not email:
            return JSONResponse({"success": False, "error": "E-mail não fornecido."}, status_code=400)

        cfg = carregar_config()
        cfg["temp_email"] = email
        salvar_config(cfg)
        return JSONResponse({"success": True, "active_email": email})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)



async def add_device_handler(request: Request):
    """Adiciona um novo equipamento dinamicamente à lista."""
    try:
        body = await request.json()
        cfg = carregar_config()
        devices = cfg.get("devices", [])

        # Próximo ID sequencial
        novo_id = max([d.get("id", 0) for d in devices], default=0) + 1
        nome = body.get("name", f"Equipamento {novo_id:02d}").strip()
        tv_id = body.get("tv_id", "").strip()

        novo_device = {
            "id": novo_id,
            "name": nome or f"Equipamento {novo_id:02d}",
            "tv_id": tv_id,
            "enabled": True,
            "last_sync": None,
            "status": "idle",
        }
        devices.append(novo_device)
        cfg["devices"] = devices
        salvar_config(cfg)

        return JSONResponse({"success": True, "device": novo_device})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def delete_device_handler(request: Request):
    """Remove um equipamento pelo ID."""
    try:
        body = await request.json()
        dev_id = int(body.get("id"))
        cfg = carregar_config()
        cfg["devices"] = [d for d in cfg.get("devices", []) if d.get("id") != dev_id]
        salvar_config(cfg)
        return JSONResponse({"success": True, "message": "Equipamento removido."})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def trigger_all_handler(request: Request):
    """Dispara a sincronização de todos os equipamentos ativos com a mesma lista IPTV."""
    cfg = carregar_config()
    playlist = cfg.get("master_playlist_url", "").strip()

    if not playlist:
        return JSONResponse({"success": False, "message": "Defina a Playlist IPTV Mestre antes de sincronizar."}, status_code=400)

    # Executa a tarefa em background para não travar a requisição HTTP
    asyncio.create_task(executar_upload_em_lote())
    return JSONResponse({"success": True, "message": "Sincronização em lote iniciada para todos os equipamentos!"})


async def trigger_single_device_handler(request: Request):
    """Dispara o envio da playlist para um equipamento específico."""
    try:
        body = await request.json()
        dev_id = int(body.get("id"))
        cfg = carregar_config()
        playlist = cfg.get("master_playlist_url", "").strip()

        if not playlist:
            return JSONResponse({"success": False, "message": "Playlist IPTV Mestre não configurada."}, status_code=400)

        dispositivo = next((d for d in cfg.get("devices", []) if d.get("id") == dev_id), None)
        if not dispositivo:
            return JSONResponse({"success": False, "message": "Equipamento não encontrado."}, status_code=404)

        res = await executar_upload_individual(dispositivo, playlist)
        # Atualiza status individual
        dispositivo["status"] = "success" if res["success"] else "error"
        dispositivo["last_sync"] = res["timestamp"]
        salvar_config(cfg)

        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Gerenciador do ciclo de vida da aplicação."""
    global next_run_dt
    cfg = carregar_config()
    if cfg.get("auto_update_enabled"):
        if cfg.get("sync_mode") == "daily_midnight_brasilia":
            next_run_dt = calcular_proxima_meia_noite_brasilia()
            print(f"[*] Próxima sincronização diária agendada para: {next_run_dt.strftime('%d/%m/%Y às 00:00:00 (Brasília)')}")
        elif cfg.get("sync_mode") == "datetime" and cfg.get("scheduled_datetime"):
            try:
                next_run_dt = datetime.fromisoformat(cfg["scheduled_datetime"])
            except Exception:
                next_run_dt = None
        else:
            agendar_proxima_execucao(cfg.get("interval_minutes", 60))
    scheduler_task = asyncio.create_task(background_scheduler())
    yield
    scheduler_task.cancel()


async def ping_playlist_handler(request: Request):
    """Testa rapidamente a conectividade de um link M3U via HTTP."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        if not url:
            return JSONResponse({"success": False, "error": "URL não fornecida."}, status_code=400)

        import httpx
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            try:
                resp = await client.head(url)
                if resp.status_code >= 400:
                    resp = await client.get(url, headers={"Range": "bytes=0-100"})
                is_ok = resp.status_code < 400
                return JSONResponse({
                    "success": True,
                    "online": is_ok,
                    "status_code": resp.status_code,
                    "message": "Link M3U acessível e respondendo com sucesso!" if is_ok else f"Servidor retornou status {resp.status_code}"
                })
            except Exception as e:
                return JSONResponse({
                    "success": True,
                    "online": False,
                    "error": str(e),
                    "message": "Falha de conexão com o servidor da playlist."
                })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


routes = [
    Route("/", index_handler, methods=["GET"]),
    Route("/api/config", get_config_handler, methods=["GET"]),
    Route("/api/config", post_config_handler, methods=["POST"]),
    Route("/api/device/add", add_device_handler, methods=["POST"]),
    Route("/api/device/delete", delete_device_handler, methods=["POST"]),
    Route("/api/trigger-all", trigger_all_handler, methods=["POST"]),
    Route("/api/trigger-device", trigger_single_device_handler, methods=["POST"]),
    Route("/api/playlist/ping", ping_playlist_handler, methods=["POST"]),
    Route("/api/mailtm/new", create_mailtm_account_handler, methods=["POST"]),
    Route("/api/mailtm/new-daily", renew_daily_email_handler, methods=["POST"]),
    Route("/api/mailtm/check-playlist", check_playlist_from_email_handler, methods=["GET", "POST"]),
    Route("/api/mailtm/accounts", list_mailtm_accounts_handler, methods=["GET"]),
    Route("/api/mailtm/messages", get_mailtm_messages_handler, methods=["GET"]),
    Route("/api/mailtm/select", select_mailtm_account_handler, methods=["POST"]),
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
    parser = argparse.ArgumentParser(description="SmartTV Club Multi-Device Auto-Sync")
    parser.add_argument("--port", type=int, default=5050, help="Porta do servidor Web (default: 5050)")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor Web (default: 127.0.0.1)")
    args = parser.parse_args()

    print(f"\n===========================================================")
    print(f"🌟 SmartTV Club Multi-Device Auto-Sync Web Server")
    print(f"📡 Acesse: http://{args.host}:{args.port}")
    print(f"===========================================================\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
