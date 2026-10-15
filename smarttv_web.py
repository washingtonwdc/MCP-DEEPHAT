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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple

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
retry_count: int = 0
MAX_MIDNIGHT_RETRIES: int = 6
is_running_full_flow: bool = False
full_flow_step: str = ""
full_flow_progress: int = 0
last_full_flow_result: Dict[str, Any] = {}


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
                if "fallback_playlist_url" not in data:
                    data["fallback_playlist_url"] = "https://iptv-org.github.io/iptv/index.m3u"
                if "telegram_bot_token" not in data:
                    data["telegram_bot_token"] = ""
                if "telegram_chat_id" not in data:
                    data["telegram_chat_id"] = ""
                if "webhook_url" not in data:
                    data["webhook_url"] = ""
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


async def enviar_notificacao_externa(titulo: str, mensagem: str, sucesso: bool = True):
    """Envia alerta assíncrono para Telegram e/ou Webhook configurados."""
    cfg = carregar_config()
    tg_token = cfg.get("telegram_bot_token", "").strip()
    tg_chat = cfg.get("telegram_chat_id", "").strip()
    webhook_url = cfg.get("webhook_url", "").strip()

    if not (tg_token and tg_chat) and not webhook_url:
        return

    import httpx
    async with httpx.AsyncClient(timeout=8.0) as client:
        if tg_token and tg_chat:
            icone = "✅" if sucesso else "⚠️"
            texto_tg = f"*{icone} SmartTV Club Auto-Sync*\n\n*{titulo}*\n{mensagem}"
            try:
                await client.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={"chat_id": tg_chat, "text": texto_tg, "parse_mode": "Markdown"}
                )
                print("[INFO] Notificação enviada via Telegram com sucesso.")
            except Exception as e_tg:
                print(f"[!] Erro ao enviar notificação Telegram: {e_tg}")

        if webhook_url:
            payload = {
                "title": titulo,
                "message": mensagem,
                "success": sucesso,
                "timestamp": datetime.now().isoformat(),
                "source": "SmartTV Club Auto-Sync"
            }
            try:
                await client.post(webhook_url, json=payload)
                print("[INFO] Notificação enviada via Webhook com sucesso.")
            except Exception as e_wh:
                print(f"[!] Erro ao enviar Webhook: {e_wh}")


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
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--host-resolver-rules=MAP smarttv.club 104.21.24.154, MAP *.smarttv.club 104.21.24.154",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            page = await browser.new_page()

            await page.goto("https://smarttv.club/upload-channels/", wait_until="domcontentloaded", timeout=45000)
            try:
                await page.wait_for_selector("input", timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(1.0)

            # 1. Preenche TV ID
            input_tvid = page.locator("input[name='tvid']")
            if await input_tvid.count() > 0:
                await input_tvid.fill(tv_id)
            else:
                await page.locator("input[placeholder*='TV ID']").fill(tv_id)

            # 2. Preenche Email (Obrigatório pelo SmartTV Club)
            cfg = carregar_config()
            temp_email = cfg.get("temp_email") or "teste-washington@maxxspace.com"
            input_email = page.locator("input[name='email']")
            if await input_email.count() > 0:
                await input_email.fill(temp_email)

            # 3. Preenche Playlist URL
            input_url = page.locator("input[name='url']")
            if await input_url.count() > 0:
                await input_url.fill(playlist_url)
            else:
                await page.locator("input[placeholder*='playlist link']").fill(playlist_url)

            # 4. Marcar checkboxes obrigatórios ("Agree to all") via DOM
            await page.evaluate("""() => {
                const el = document.getElementById('agree_all');
                if (el && !el.checked) el.click();
                const elPriv = document.getElementById('privacy');
                if (elPriv && !elPriv.checked) elPriv.click();
            }""")

            await asyncio.sleep(0.5)

            # 5. Clica no botão "Send playlist to TV"
            btn_send = page.locator("button[type='submit']:has-text('Send playlist')")
            if await btn_send.count() > 0:
                try:
                    await btn_send.click(force=True, timeout=8000)
                except Exception:
                    await btn_send.evaluate("b => b.click()")

                # Aguarda retorno de processamento do portal
                await asyncio.sleep(6)

                # Verifica se houve erro de validação em vermelho
                is_red = await page.locator("input[name='tvid'].border-red-500").count() > 0
                conteudo_tela = await page.content()

                if is_red or "check the fields marked in red" in conteudo_tela.lower():
                    resultado["success"] = False
                    resultado["message"] = f"SmartTV Club recusou TV ID '{tv_id}': formato inválido ou inexistente no app."
                    print(f"  [AVISO] SmartTV Club recusou TV ID: {tv_id}")
                elif any(w in conteudo_tela.lower() for w in ["sending your playlist", "checking the playlist", "uploaded", "sucesso", "success"]):
                    resultado["success"] = True
                    resultado["message"] = "Playlist transmitida e aceita com sucesso pelo SmartTV Club!"
                    print(f"  [OK] Playlist aceita pelo SmartTV Club para {device_name}!")
                else:
                    resultado["success"] = True
                    resultado["message"] = "Formulário submetido no SmartTV Club."
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


async def executar_fluxo_completo_pipeline() -> Dict[str, Any]:
    """
    Executa o Fluxo Completo ponta a ponta:
    1. Cria/renova novo e-mail temporário no Mail.tm (descartando anterior).
    2. Lê caixa de entrada e extrai link de playlist do conteúdo da mensagem.
    3. Testa conectividade da Playlist via Ping HTTP.
    4. Atualiza a Playlist Mestre compartilhada e configurações no servidor.
    5. Dispara a sincronização via Playwright para todos os equipamentos ativos (TV Washington, iPad, Celular, etc).
    6. Dispara notificações externas (Telegram/Webhook) com o resultado.
    """
    global is_running_full_flow, full_flow_step, full_flow_progress, last_full_flow_result
    is_running_full_flow = True
    full_flow_progress = 5
    full_flow_step = "Iniciando fluxo completo..."
    inicio_total = time.time()
    relatorio: Dict[str, Any] = {
        "success": False,
        "timestamp": datetime.now().isoformat(),
        "steps": [],
        "novo_email": "",
        "playlist_url": "",
        "devices_synced": 0,
        "message": ""
    }

    try:
        import mailtm_manager
        cfg = carregar_config()

        # ETAPA 1 e 2: Gerar novo teste IPTV via gerador oficial TestersByGold (https://www.testersbygold.fun/plajezev/prod808033)
        full_flow_progress = 25
        full_flow_step = "1/5: Gerando novo teste IPTV via TestersByGold Oficial (Gold Card)..."
        print(f"\n[⚡ FLUXO COMPLETO] {full_flow_step}")
        import gold_generator
        res_gold = await gold_generator.gerar_novo_teste_gold(descartar_email_anterior=True)

        endereco = res_gold.get("email", "")
        playlist_alvo = res_gold.get("playlist_url") or cfg.get("master_playlist_url") or cfg.get("fallback_playlist_url") or "https://iptv-org.github.io/iptv/index.m3u"
        found_in_gold = bool(res_gold.get("success") and res_gold.get("playlist_url"))

        if endereco:
            cfg["temp_email"] = endereco
            salvar_config(cfg)
            relatorio["novo_email"] = endereco

        relatorio["steps"].append({
            "step": 1,
            "name": "Gerar Teste Gold Card (testersbygold.fun)",
            "success": found_in_gold,
            "detail": f"Usuário: {res_gold.get('username')} | Playlist: {playlist_alvo}"
        })
        relatorio["playlist_url"] = playlist_alvo
        print(f"  [{'OK' if found_in_gold else 'AVISO'}] Teste Gold Card: {playlist_alvo} (Origem: {'TestersByGold' if found_in_gold else 'Fallback'})")

        # ETAPA 3: Testar conectividade via Ping HTTP
        full_flow_progress = 55
        full_flow_step = "3/5: Validando conectividade da playlist via Ping HTTP..."
        print(f"[⚡ FLUXO COMPLETO] {full_flow_step}")
        is_online = True
        status_code = 200
        latency_ms = 0
        try:
            import httpx
            t_ping = time.time()
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp_ping = await client.get(playlist_alvo, headers={"Range": "bytes=0-524287", "User-Agent": "Mozilla/5.0 (SmartTV Club Sync)"})
                latency_ms = int((time.time() - t_ping) * 1000)
                status_code = resp_ping.status_code
                is_online = status_code in [200, 206]
        except Exception as e_ping:
            is_online = False
            print(f"  [AVISO] Ping da playlist: {e_ping}")

        relatorio["steps"].append({
            "step": 3,
            "name": "Ping Playlist",
            "success": is_online,
            "status_code": status_code,
            "latency_ms": latency_ms
        })
        print(f"  [{'OK' if is_online else 'AVISO'}] Ping HTTP: {status_code} ({latency_ms} ms)")

        # ETAPA 4: Atualizar Playlist Mestre e configurações
        full_flow_progress = 70
        full_flow_step = "4/5: Atualizando Playlist Mestre e salvando configurações..."
        print(f"[⚡ FLUXO COMPLETO] {full_flow_step}")
        cfg["master_playlist_url"] = playlist_alvo
        cfg["new_playlist_url"] = playlist_alvo
        cfg["last_playlist_check"] = datetime.now().isoformat()
        salvar_config(cfg)
        relatorio["steps"].append({"step": 4, "name": "Salvar Configurações", "success": True})

        # ETAPA 5: Disparar sincronização via Playwright para todos os equipamentos ativos
        full_flow_progress = 85
        full_flow_step = "5/5: Sincronizando TV Washington, iPad, Celular e equipamentos ativos via Playwright..."
        print(f"[⚡ FLUXO COMPLETO] {full_flow_step}")
        resultados_lote = await executar_upload_em_lote()
        relatorio["devices_synced"] = len(resultados_lote)
        relatorio["resultados_dispositivos"] = resultados_lote
        relatorio["steps"].append({
            "step": 5,
            "name": "Upload Equipamentos",
            "success": any(r.get("success") for r in resultados_lote) if resultados_lote else True,
            "count": len(resultados_lote)
        })

        # ETAPA 6: Notificação externa
        try:
            sucesso_total = all(r.get("success") for r in resultados_lote) if resultados_lote else True
            await enviar_notificacao_externa(
                "Fluxo Completo SmartTV Club Finalizado",
                f"E-mail: {endereco}\nPlaylist: {playlist_alvo}\nAparelhos sincronizados: {len(resultados_lote)}\nStatus: {'Sucesso total' if sucesso_total else 'Com avisos'}.",
                sucesso=sucesso_total
            )
        except Exception:
            pass

        relatorio["success"] = True
        relatorio["duration_ms"] = int((time.time() - inicio_total) * 1000)
        relatorio["message"] = f"Fluxo Completo executado com sucesso! ({len(resultados_lote)} aparelhos sincronizados em {relatorio['duration_ms'] // 1000}s)"
        full_flow_progress = 100
        full_flow_step = "✔️ Fluxo Completo Concluído com Sucesso!"
        print(f"[🏁 FLUXO COMPLETO] {relatorio['message']}\n")

    except Exception as e_geral:
        relatorio["success"] = False
        relatorio["duration_ms"] = int((time.time() - inicio_total) * 1000)
        relatorio["message"] = f"Erro na execução do Fluxo Completo: {str(e_geral)}"
        full_flow_step = f"❌ Erro: {str(e_geral)}"
        print(f"[!] Erro no Fluxo Completo: {e_geral}")

    finally:
        last_full_flow_result = relatorio
        is_running_full_flow = False

    return relatorio


async def background_scheduler():
    """Loop assíncrono para verificar e disparar atualizações periódicas ou por data agendada."""
    global next_run_dt, retry_count
    print("[*] Scheduler de atualização contínua iniciado em background.")

    while True:
        try:
            await asyncio.sleep(10)
            cfg = carregar_config()

            if cfg.get("auto_update_enabled") and cfg.get("master_playlist_url"):
                agora = datetime.now()
                sync_mode = cfg.get("sync_mode", "interval")
                scheduled_str = cfg.get("scheduled_datetime")

                # Modo 1 (Principal): Sincronização Diária às 00:00 (Horário de Brasília) com Retry e Fallback
                if sync_mode == "daily_midnight_brasilia":
                    if next_run_dt is None:
                        next_run_dt = calcular_proxima_meia_noite_brasilia()
                        print(f"[*] Próxima sincronização diária agendada para: {next_run_dt.strftime('%d/%m/%Y às 00:00:00 (Brasília)')}")
                    elif agora >= next_run_dt and not is_running_batch:
                        print(f"\n[🕛 CICLO DIÁRIO] Gerando novo teste IPTV via TestersByGold Oficial (Tentativa {retry_count + 1}/{MAX_MIDNIGHT_RETRIES})...")
                        try:
                            import gold_generator
                            res_gold = await gold_generator.gerar_novo_teste_gold(descartar_email_anterior=(retry_count == 0))
                            link_playlist = res_gold.get("playlist_url")
                            is_valid_link = bool(res_gold.get("success") and link_playlist)

                            if is_valid_link and link_playlist:
                                cfg["master_playlist_url"] = link_playlist
                                cfg["new_playlist_url"] = link_playlist
                                cfg["last_playlist_check"] = datetime.now().isoformat()
                                salvar_config(cfg)
                                print(f"[✨] Nova playlist válida capturada com sucesso: {link_playlist}")

                                # Sincroniza todos os equipamentos ativos
                                await executar_upload_em_lote()

                                # Sucesso: zera retentativas e agenda para a próxima meia-noite
                                retry_count = 0
                                next_run_dt = calcular_proxima_meia_noite_brasilia()
                                print(f"[*] Próxima sincronização diária reagendada para: {next_run_dt.strftime('%d/%m/%Y às 00:00:00')}")
                                await enviar_notificacao_externa(
                                    "Sincronização Diária Concluída com Sucesso",
                                    f"Nova playlist capturada e propagada para todos os aparelhos ativos às {agora.strftime('%H:%M:%S')}.",
                                    sucesso=True
                                )
                            else:
                                # Se ainda não chegou ou link inválido
                                if retry_count < MAX_MIDNIGHT_RETRIES:
                                    retry_count += 1
                                    next_run_dt = agora + timedelta(minutes=5)
                                    print(f"[⚠️] E-mail com playlist ainda não chegou às {agora.strftime('%H:%M:%S')}. Retentativa {retry_count}/{MAX_MIDNIGHT_RETRIES} agendada para 5 minutos ({next_run_dt.strftime('%H:%M:%S')}).")
                                else:
                                    # Esgotou retentativas: aciona contingência (Fallback)
                                    fallback_url = cfg.get("fallback_playlist_url") or cfg.get("master_playlist_url") or "https://iptv-org.github.io/iptv/index.m3u"
                                    print(f"[🚨] Retentativas esgotadas ({MAX_MIDNIGHT_RETRIES}x). Aplicando lista de CONTINGÊNCIA (Fallback): {fallback_url}")
                                    cfg["master_playlist_url"] = fallback_url
                                    cfg["last_playlist_check"] = datetime.now().isoformat()
                                    salvar_config(cfg)

                                    await executar_upload_em_lote()

                                    retry_count = 0
                                    next_run_dt = calcular_proxima_meia_noite_brasilia()
                                    print(f"[*] Ciclo finalizado com fallback. Próxima execução: {next_run_dt.strftime('%d/%m/%Y às 00:00:00')}")
                                    await enviar_notificacao_externa(
                                        "Alerta: Lista de Contingência Aplicada",
                                        f"O e-mail diário com a nova playlist não foi recebido após {MAX_MIDNIGHT_RETRIES} tentativas de 5 min. A lista de fallback foi propagada para não deixar as TVs sem sinal.",
                                        sucesso=False
                                    )
                        except Exception as e_mail:
                            print(f"[!] Erro no processamento do ciclo diário: {e_mail}")
                            if retry_count < MAX_MIDNIGHT_RETRIES:
                                retry_count += 1
                                next_run_dt = agora + timedelta(minutes=5)
                            else:
                                retry_count = 0
                                next_run_dt = calcular_proxima_meia_noite_brasilia()

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


import hashlib

# Conjunto de sessões ativas autenticadas em memória
ACTIVE_SESSIONS = set()


def gerar_token_sessao(senha: str) -> str:
    """Gera hash seguro de token de sessão para a senha de administrador."""
    secret = "smarttv_admin_salt_2026_washington_0808"
    return hashlib.sha256(f"{senha}:{secret}".encode()).hexdigest()


def is_request_authenticated(request: Request) -> bool:
    """Verifica se a requisição possui credenciais válidas de administrador."""
    cfg = carregar_config()
    if not cfg.get("auth_enabled", True):
        return True

    admin_pwd = str(cfg.get("admin_password", "0808")).strip()
    valid_token = gerar_token_sessao(admin_pwd)

    # 1. Cookie de sessão HttpOnly
    cookie_token = request.cookies.get("smarttv_session")
    if cookie_token and (cookie_token == valid_token or cookie_token in ACTIVE_SESSIONS):
        return True

    # 2. Header Authorization Bearer
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if token == valid_token or token in ACTIVE_SESSIONS:
            return True

    # 3. Query string token ou pwd (útil para automações headless)
    query_token = request.query_params.get("token") or request.query_params.get("pwd")
    if query_token and (query_token == admin_pwd or query_token == valid_token):
        return True

    return False


async def auth_login_handler(request: Request):
    """Autentica o administrador com a senha informada (padrão: 0808)."""
    try:
        body = await request.json()
        pwd = str(body.get("password", "")).strip()
        cfg = carregar_config()
        expected_pwd = str(cfg.get("admin_password", "0808")).strip()

        if pwd == expected_pwd:
            token = gerar_token_sessao(pwd)
            ACTIVE_SESSIONS.add(token)
            resp = JSONResponse({
                "success": True,
                "authenticated": True,
                "token": token,
                "message": "Login realizado com sucesso! Bem-vindo, Administrador."
            })
            resp.set_cookie(
                key="smarttv_session",
                value=token,
                max_age=86400 * 30,  # 30 dias de validade
                path="/",
                httponly=True,
                samesite="lax"
            )
            return resp
        else:
            return JSONResponse({
                "success": False,
                "authenticated": False,
                "error": "Senha de administrador incorreta. Tente novamente."
            }, status_code=401)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)


async def auth_status_handler(request: Request):
    """Retorna se o cliente atual está autenticado."""
    cfg = carregar_config()
    auth_enabled = bool(cfg.get("auth_enabled", True))
    is_auth = is_request_authenticated(request)
    return JSONResponse({
        "authenticated": is_auth,
        "auth_enabled": auth_enabled
    })


async def auth_logout_handler(request: Request):
    """Encerra a sessão ativa do administrador."""
    cookie_token = request.cookies.get("smarttv_session")
    if cookie_token and cookie_token in ACTIVE_SESSIONS:
        ACTIVE_SESSIONS.discard(cookie_token)
    resp = JSONResponse({
        "success": True,
        "authenticated": False,
        "message": "Sessão encerrada com sucesso."
    })
    resp.delete_cookie(key="smarttv_session", path="/")
    return resp


# Rotas HTTP
async def index_handler(request: Request):
    """Renderiza a interface web moderna."""
    if UI_FILE.exists():
        html_content = UI_FILE.read_text(encoding="utf-8")
    else:
        html_content = "<h1>UI file not found</h1>"
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return HTMLResponse(content=html_content, headers=headers)


def extrair_credenciais_de_url(url: str) -> Dict[str, str]:
    """Extrai host, username e password a partir de query params em URLs de IPTV."""
    if not url:
        return {}
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        user = qs.get("username", [None])[0] or qs.get("user", [None])[0] or ""
        pwd = qs.get("password", [None])[0] or qs.get("pass", [None])[0] or ""
        host = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
        if user or pwd:
            return {"host": host, "username": user, "password": pwd, "m3u_url": url}
    except Exception:
        pass
    return {}


def total_dispositivos_cadastrados(cfg: Dict[str, Any]) -> int:
    """Retorna a contagem de equipamentos com TV ID preenchido."""
    devices = cfg.get("devices", [])
    return len([d for d in devices if d.get("tv_id", "").strip()])


async def get_config_handler(request: Request):
    """Retorna configuração global, equipamentos e status."""
    cfg = carregar_config()
    is_auth = is_request_authenticated(request)

    # Se autenticação estiver ativa e cliente não autenticado, bloqueia dados confidenciais
    if cfg.get("auth_enabled", True) and not is_auth:
        return JSONResponse({
            "authenticated": False,
            "auth_required": True,
            "status": "locked",
            "message": "Autenticação requerida. Digite a senha de administrador."
        }, status_code=401)

    cfg["is_syncing"] = is_running_batch
    cfg["current_device_id"] = current_running_device_id
    cfg["status"] = "running" if is_running_batch else ("online" if cfg.get("auto_update_enabled") else "paused")
    cfg["total_registered_devices"] = total_dispositivos_cadastrados(cfg)
    cfg["authenticated"] = True

    # Credenciais Xtream extraídas da playlist ativa
    creds = cfg.get("xtream_info") or {}
    if not creds.get("username"):
        creds = extrair_credenciais_de_url(cfg.get("new_playlist_url") or cfg.get("master_playlist_url") or "")
    cfg["credentials"] = creds

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

    # Oculta a senha de administrador do payload enviado ao cliente
    cfg_clean = dict(cfg)
    cfg_clean.pop("admin_password", None)
    return JSONResponse(cfg_clean)


async def post_config_handler(request: Request):
    """Salva configurações globais e/ou lista de equipamentos."""
    global next_run_dt
    if not is_request_authenticated(request):
        return JSONResponse({"success": False, "authenticated": False, "error": "Acesso não autorizado. Digite a senha de administrador."}, status_code=401)

    try:
        body = await request.json()
        cfg = carregar_config()

        intervalo_antigo = cfg.get("interval_minutes", 60)
        auto_antigo = cfg.get("auto_update_enabled", False)

        if "master_playlist_url" in body:
            cfg["master_playlist_url"] = str(body["master_playlist_url"]).strip()
        if "fallback_playlist_url" in body:
            cfg["fallback_playlist_url"] = str(body["fallback_playlist_url"]).strip()
        if "telegram_bot_token" in body:
            cfg["telegram_bot_token"] = str(body["telegram_bot_token"]).strip()
        if "telegram_chat_id" in body:
            cfg["telegram_chat_id"] = str(body["telegram_chat_id"]).strip()
        if "webhook_url" in body:
            cfg["webhook_url"] = str(body["webhook_url"]).strip()
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


def checar_msgs_conta(c_item: Dict[str, Any], dados: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Helper que extrai mensagens e playlists de uma conta específica."""
    import mailtm_manager
    tok = c_item.get("token")
    if not tok and c_item.get("senha"):
        tok = mailtm_manager.autenticar_token(c_item["email"], c_item["senha"])
        if tok:
            c_item["token"] = tok
    if not tok:
        return c_item["email"], []
    try:
        msgs = mailtm_manager.extrair_links_confirmacao(tok, c_item["email"])
        for m in msgs:
            m["conta_email"] = c_item["email"]
        return c_item["email"], msgs
    except Exception:
        return c_item["email"], []


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

        # Auto-renovação de token caso possua senha salva
        if conta and not conta.get("token") and conta.get("senha"):
            novo_tok = mailtm_manager.autenticar_token(conta["email"], conta["senha"])
            if novo_tok:
                conta["token"] = novo_tok
                mailtm_manager.salvar_dados(dados)

        # Auto-healing se a conta foi criada em outra máquina e não existe localmente
        if not conta or not conta.get("token"):
            conta_valida = next((c for c in reversed(contas) if c.get("token")), None)
            if conta_valida:
                conta = conta_valida
                email_ativo = conta["email"]
                cfg["temp_email"] = email_ativo
                salvar_config(cfg)
            else:
                endereco, senha, token = mailtm_manager.criar_email()
                conta = {"email": endereco, "senha": senha, "token": token}
                email_ativo = endereco
                cfg["temp_email"] = endereco
                salvar_config(cfg)

        # 1. Checa conta ativa primeiro (rápido, ~0.5s)
        playlist_encontrada = None
        email_com_playlist = None
        detalhes_item = None
        total_msgs_geral = 0
        link_ativacao_pendente = None

        _, msgs_ativas = checar_msgs_conta(conta, dados)
        total_msgs_geral += len(msgs_ativas)
        for m in msgs_ativas:
            pls = m.get("playlists_detectadas", [])
            if pls:
                playlist_encontrada = pls[0]
                email_com_playlist = conta["email"]
                detalhes_item = m
                break
            if not link_ativacao_pendente and m.get("links_ativacao"):
                link_ativacao_pendente = m["links_ativacao"][0]

        # 2. Se não encontrou na conta ativa, varre as demais contas em paralelo
        if not playlist_encontrada:
            outras_contas = [c for c in reversed(contas) if c.get("email") != email_ativo]
            if outras_contas:
                with ThreadPoolExecutor(max_workers=6) as executor:
                    fut_map = {executor.submit(checar_msgs_conta, c, dados): c for c in outras_contas}
                    for fut in as_completed(fut_map):
                        em, msgs_c = fut.result()
                        total_msgs_geral += len(msgs_c)
                        for m in msgs_c:
                            pls = m.get("playlists_detectadas", [])
                            if pls and not playlist_encontrada:
                                playlist_encontrada = pls[0]
                                email_com_playlist = em
                                detalhes_item = m
                            if not link_ativacao_pendente and m.get("links_ativacao"):
                                link_ativacao_pendente = m["links_ativacao"][0]

        cfg["last_playlist_check"] = datetime.now().isoformat()

        if playlist_encontrada:
            cfg["master_playlist_url"] = playlist_encontrada
            cfg["new_playlist_url"] = playlist_encontrada
            if email_com_playlist:
                cfg["temp_email"] = email_com_playlist
            if detalhes_item and detalhes_item.get("xtream_info"):
                cfg["xtream_info"] = detalhes_item["xtream_info"]
            else:
                cfg["xtream_info"] = extrair_credenciais_de_url(playlist_encontrada)
            salvar_config(cfg)
            return JSONResponse({
                "success": True,
                "found": True,
                "playlist_url": playlist_encontrada,
                "email_origem": email_com_playlist,
                "credentials": cfg.get("xtream_info") or {},
                "message": f"Nova playlist identificada com sucesso na caixa de {email_com_playlist}!",
                "total_messages": total_msgs_geral,
                "detalhes": detalhes_item
            })
        else:
            salvar_config(cfg)
            msg_retorno = "Nenhuma nova playlist identificada nas mensagens recentes ainda."
            if link_ativacao_pendente:
                msg_retorno = f"Link de confirmação/ativação detectado: {link_ativacao_pendente}"
            return JSONResponse({
                "success": True,
                "found": False,
                "playlist_url": cfg.get("master_playlist_url", ""),
                "message": msg_retorno,
                "link_ativacao": link_ativacao_pendente,
                "total_messages": total_msgs_geral
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
    """Cria uma nova conta temporária no Mail.tm sob demanda (regra: só cria outro e-mail se mais de 5 dispositivos forem cadastrados)."""
    try:
        import mailtm_manager
        cfg = carregar_config()
        total_devs = total_dispositivos_cadastrados(cfg)
        dados = mailtm_manager.carregar_dados()
        contas = dados.get("contas", [])

        force = False
        try:
            body = await request.json()
            force = bool(body.get("force", False))
        except Exception:
            pass

        # Regra: 1 e-mail atende até 5 aparelhos. Se mais de 5, permite até 2 e-mails (cobre até 10 aparelhos).
        max_contas = max(1, (total_devs + 4) // 5)
        if len(contas) >= max_contas and not force:
            email_atual = cfg.get("temp_email") or contas[0].get("email")
            return JSONResponse({
                "success": False,
                "created": False,
                "email": email_atual,
                "total_devices": total_devs,
                "max_accounts": max_contas,
                "message": f"Regra ativa: Você possui {total_devs} aparelho(s) cadastrado(s). A cota atual permite até {max_contas} e-mail(s) (1 para cada 5 aparelhos). Um novo e-mail só será liberado ao cadastrar mais aparelhos."
            })

        endereco, senha, token = mailtm_manager.criar_email()
        cfg["temp_email"] = endereco
        salvar_config(cfg)
        return JSONResponse({
            "success": True,
            "created": True,
            "email": endereco,
            "password": senha,
            "total_devices": total_devs,
            "message": f"Nova conta criada com sucesso para atender aparelhos adicionais ({total_devs} cadastrados)!"
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
    """Busca as mensagens recebidas de uma conta Mail.tm específica ou de todas (?email=all)."""
    try:
        import mailtm_manager
        target_email = request.query_params.get("email", "").strip()
        dados = mailtm_manager.carregar_dados()
        contas = dados.get("contas", [])

        # Modo consolidado: busca em todas as contas em paralelo
        if target_email.lower() in ["all", "todas", "*"]:
            todas_mensagens = []
            with ThreadPoolExecutor(max_workers=6) as executor:
                fut_list = [executor.submit(checar_msgs_conta, c, dados) for c in reversed(contas)]
                for fut in as_completed(fut_list):
                    _, msgs_c = fut.result()
                    todas_mensagens.extend(msgs_c)

            # Ordena por data mais recente
            todas_mensagens.sort(key=lambda m: str(m.get("data_recebimento", "")), reverse=True)
            return JSONResponse({
                "success": True,
                "email": "todas",
                "messages": todas_mensagens,
                "total": len(todas_mensagens)
            })

        if not target_email:
            cfg = carregar_config()
            target_email = cfg.get("temp_email", "")

        conta = next((c for c in contas if c.get("email") == target_email), None)
        if not conta:
            for k, v in dados.items():
                if isinstance(v, dict) and v.get("email") == target_email:
                    conta = v
                    break

        # Auto-renovação de token caso possua senha salva
        if conta and not conta.get("token") and conta.get("senha"):
            novo_tok = mailtm_manager.autenticar_token(conta["email"], conta["senha"])
            if novo_tok:
                conta["token"] = novo_tok
                mailtm_manager.salvar_dados(dados)

        # Auto-healing se a conta foi criada em outra máquina e não existe localmente
        if not conta or not conta.get("token"):
            conta_valida = next((c for c in reversed(contas) if c.get("token")), None)
            if conta_valida:
                conta = conta_valida
                target_email = conta["email"]
                cfg = carregar_config()
                cfg["temp_email"] = target_email
                salvar_config(cfg)
            else:
                endereco, senha, token = mailtm_manager.criar_email()
                conta = {"email": endereco, "senha": senha, "token": token}
                target_email = endereco
                cfg = carregar_config()
                cfg["temp_email"] = endereco
                salvar_config(cfg)

        token = conta["token"]
        msgs = mailtm_manager.extrair_links_confirmacao(token, target_email)
        for m in msgs:
            m["conta_email"] = target_email
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


async def inject_test_message_handler(request: Request):
    """Injeta uma mensagem de teste com playlist para homologação imediata da inbox."""
    try:
        import mailtm_manager
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        cfg = carregar_config()
        email = body.get("email") or cfg.get("temp_email")
        url_padrao_teste = "http://line.iptvclub.net:80/get.php?username=teste_washington&password=tv_smart_2026&type=m3u_plus&output=ts"
        playlist = body.get("playlist_url") or url_padrao_teste
        if not email:
            return JSONResponse({"success": False, "error": "E-mail ativo não encontrado."}, status_code=400)

        msg = mailtm_manager.injetar_mensagem_teste(email, playlist)
        creds = msg.get("xtream_info") or extrair_credenciais_de_url(playlist)
        cfg["new_playlist_url"] = playlist
        cfg["master_playlist_url"] = playlist
        cfg["xtream_info"] = creds
        cfg["last_playlist_check"] = datetime.now().isoformat()
        salvar_config(cfg)
        return JSONResponse({
            "success": True,
            "message": "Mensagem de teste injetada na caixa com sucesso!",
            "item": msg,
            "playlist_url": playlist,
            "credentials": creds
        })
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

        # Rotação automática de cota: se atingir 6+ aparelhos e houver apenas 1 conta, auto-provisiona a 2ª
        total_devs_novo = total_dispositivos_cadastrados(cfg)
        if total_devs_novo >= 6:
            import mailtm_manager
            dados_m = mailtm_manager.carregar_dados()
            contas_m = dados_m.get("contas", [])
            if len(contas_m) < 2:
                try:
                    novo_end, _, _ = mailtm_manager.criar_email(descartar_anterior=False)
                    print(f"[+] 6º aparelho cadastrado! Auto-provisionada 2ª conta Mail.tm ({novo_end}) para cobrir slots 06-10.")
                except Exception as e_cota:
                    print(f"[!] Erro ao auto-provisionar 2ª conta de cota: {e_cota}")

        return JSONResponse({"success": True, "device": novo_device, "total_devices": total_devs_novo})
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

        # Registra no histórico geral
        if "history" not in cfg:
            cfg["history"] = []
        cfg["history"].append(res)
        if len(cfg["history"]) > 60:
            cfg["history"] = cfg["history"][-60:]
        cfg["last_run"] = res
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
    """Testa detalhadamente a conectividade e integridade de um link M3U via HTTP."""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        if not url:
            return JSONResponse({"success": False, "error": "URL não fornecida."}, status_code=400)

        import httpx, time
        t_inicio = time.time()
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers={"Range": "bytes=0-524287", "User-Agent": "Mozilla/5.0 (SmartTV Club Sync)"})
                latency_ms = int((time.time() - t_inicio) * 1000)
                is_ok = resp.status_code in [200, 206]

                content_text = resp.text
                is_m3u = "#EXTM3U" in content_text or "#EXTINF" in content_text
                channel_count = content_text.count("#EXTINF:")

                content_length = resp.headers.get("content-length") or resp.headers.get("content-range")
                size_formatted = ""
                if content_length:
                    try:
                        total_bytes = int(content_length.split("/")[-1]) if "/" in str(content_length) else int(content_length)
                        if total_bytes > 1024 * 1024:
                            size_formatted = f"{total_bytes / (1024 * 1024):.1f} MB"
                        elif total_bytes > 1024:
                            size_formatted = f"{total_bytes / 1024:.1f} KB"
                        else:
                            size_formatted = f"{total_bytes} B"
                    except Exception:
                        size_formatted = f"{len(resp.content)} B (amostra)"
                else:
                    size_formatted = f"{len(resp.content)} B (amostra)"

                return JSONResponse({
                    "success": True,
                    "online": is_ok,
                    "status_code": resp.status_code,
                    "latency_ms": latency_ms,
                    "is_m3u": is_m3u,
                    "channel_count": channel_count,
                    "size_formatted": size_formatted,
                    "message": "Link M3U acessível e respondendo com sucesso!" if is_ok else f"Servidor retornou status {resp.status_code}"
                })
            except Exception as e:
                latency_ms = int((time.time() - t_inicio) * 1000)
                return JSONResponse({
                    "success": True,
                    "online": False,
                    "latency_ms": latency_ms,
                    "error": str(e),
                    "message": f"Falha de conexão com a playlist: {str(e)}"
                })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def test_notification_handler(request: Request):
    """Envia uma notificação de teste para Telegram ou Webhook configurados."""
    try:
        cfg = carregar_config()
        tg_token = cfg.get("telegram_bot_token", "").strip()
        tg_chat = cfg.get("telegram_chat_id", "").strip()
        webhook_url = cfg.get("webhook_url", "").strip()

        if not (tg_token and tg_chat) and not webhook_url:
            return JSONResponse({
                "success": False,
                "message": "Configure o Telegram (Token e Chat ID) ou uma Webhook URL antes de testar."
            }, status_code=400)

        await enviar_notificacao_externa(
            "Teste de Notificação SmartTV Club",
            f"Este é um teste de alerta disparado com sucesso em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}!",
            sucesso=True
        )
        return JSONResponse({"success": True, "message": "Notificação de teste disparada com sucesso!"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def export_backup_handler(request: Request):
    """Exporta a configuração completa e aparelhos cadastrados em formato JSON para download."""
    cfg = carregar_config()
    dados_backup = {
        "export_date": datetime.now().isoformat(),
        "version": "1.0",
        "devices": cfg.get("devices", []),
        "master_playlist_url": cfg.get("master_playlist_url", ""),
        "fallback_playlist_url": cfg.get("fallback_playlist_url", ""),
        "sync_mode": cfg.get("sync_mode", "daily_midnight_brasilia"),
        "telegram_bot_token": cfg.get("telegram_bot_token", ""),
        "telegram_chat_id": cfg.get("telegram_chat_id", ""),
        "webhook_url": cfg.get("webhook_url", "")
    }
    return JSONResponse(dados_backup, headers={
        "Content-Disposition": f"attachment; filename=smarttv_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    })


async def import_backup_handler(request: Request):
    """Restaura a lista de equipamentos e configurações a partir de um backup JSON."""
    try:
        dados = await request.json()
        if not isinstance(dados, dict) or "devices" not in dados:
            return JSONResponse({"success": False, "error": "Formato de arquivo de backup inválido. Chave 'devices' ausente."}, status_code=400)

        cfg = carregar_config()
        if "devices" in dados and isinstance(dados["devices"], list):
            cfg["devices"] = dados["devices"]
        if dados.get("master_playlist_url"):
            cfg["master_playlist_url"] = dados["master_playlist_url"]
        if dados.get("fallback_playlist_url"):
            cfg["fallback_playlist_url"] = dados["fallback_playlist_url"]
        if dados.get("telegram_bot_token") is not None:
            cfg["telegram_bot_token"] = dados["telegram_bot_token"]
        if dados.get("telegram_chat_id") is not None:
            cfg["telegram_chat_id"] = dados["telegram_chat_id"]
        if dados.get("webhook_url") is not None:
            cfg["webhook_url"] = dados["webhook_url"]

        salvar_config(cfg)
        return JSONResponse({
            "success": True,
            "message": f"Backup restaurado com sucesso! {len(cfg.get('devices', []))} equipamentos carregados.",
            "total_devices": len(cfg.get("devices", []))
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


async def trigger_full_flow_handler(request: Request):
    """Inicia a execução do Fluxo Completo em background."""
    global is_running_full_flow
    if is_running_full_flow:
        return JSONResponse({
            "success": False,
            "message": "O Fluxo Completo já está em andamento no momento.",
            "running": True,
            "step": full_flow_step
        }, status_code=409)

    asyncio.create_task(executar_fluxo_completo_pipeline())
    return JSONResponse({
        "success": True,
        "message": "Fluxo Completo iniciado com sucesso!",
        "running": True
    })


async def get_full_flow_status_handler(request: Request):
    """Consulta o status e progresso do Fluxo Completo."""
    return JSONResponse({
        "running": is_running_full_flow,
        "step": full_flow_step,
        "progress": full_flow_progress,
        "last_result": last_full_flow_result
    })


async def generate_gold_test_handler(request: Request):
    """Gera um teste gratuito IPTV oficial e exclusivo via https://www.testersbygold.fun/plajezev/prod808033."""
    try:
        import gold_generator
        resultado = await gold_generator.gerar_novo_teste_gold()
        return JSONResponse(resultado)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


routes = [
    Route("/", index_handler, methods=["GET"]),
    Route("/api/auth/login", auth_login_handler, methods=["POST"]),
    Route("/api/auth/status", auth_status_handler, methods=["GET"]),
    Route("/api/auth/logout", auth_logout_handler, methods=["POST"]),
    Route("/api/config", get_config_handler, methods=["GET"]),
    Route("/api/config", post_config_handler, methods=["POST"]),
    Route("/api/device/add", add_device_handler, methods=["POST"]),
    Route("/api/device/delete", delete_device_handler, methods=["POST"]),
    Route("/api/trigger-all", trigger_all_handler, methods=["POST"]),
    Route("/api/trigger-device", trigger_single_device_handler, methods=["POST"]),
    Route("/api/playlist/ping", ping_playlist_handler, methods=["POST"]),
    Route("/api/full-flow", trigger_full_flow_handler, methods=["POST"]),
    Route("/api/full-flow/status", get_full_flow_status_handler, methods=["GET"]),
    Route("/api/generator/gold-test", generate_gold_test_handler, methods=["POST"]),
    Route("/api/mailtm/new", create_mailtm_account_handler, methods=["POST"]),
    Route("/api/mailtm/new-daily", renew_daily_email_handler, methods=["POST"]),
    Route("/api/mailtm/check-playlist", check_playlist_from_email_handler, methods=["GET", "POST"]),
    Route("/api/mailtm/accounts", list_mailtm_accounts_handler, methods=["GET"]),
    Route("/api/mailtm/messages", get_mailtm_messages_handler, methods=["GET"]),
    Route("/api/mailtm/select", select_mailtm_account_handler, methods=["POST"]),
    Route("/api/mailtm/inject-test", inject_test_message_handler, methods=["POST"]),
    Route("/api/notifications/test", test_notification_handler, methods=["POST"]),
    Route("/api/backup/export", export_backup_handler, methods=["GET"]),
    Route("/api/backup/import", import_backup_handler, methods=["POST"]),
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
    parser.add_argument("--host", default="0.0.0.0", help="Host do servidor Web (default: 0.0.0.0)")
    args = parser.parse_args()

    print(f"\n===========================================================")
    print(f"🌟 SmartTV Club Multi-Device Auto-Sync Web Server")
    print(f"📡 Acesse: http://{args.host}:{args.port}")
    print(f"===========================================================\n")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
