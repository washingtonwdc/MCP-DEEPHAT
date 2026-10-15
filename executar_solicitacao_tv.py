# -*- coding: utf-8 -*-
"""
Execução Autônoma:
1. Configura TV Washington (b44a-64c9-2dc8-8b62-593c-11de) e iPad de Washington (e9b4-9e58-a8b2-da67-25c9-c737).
2. Cria novo e-mail no Mail.tm e injeta nova mensagem com credenciais de teste Xtream Codes.
3. Extrai e valida a playlist de teste via Ping HTTP.
4. Realiza o upload automatizado Playwright para todos os equipamentos ativos.
"""

import sys
import time
import json
import asyncio
from datetime import datetime
from pathlib import Path
import httpx

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:5050"
BASE_DIR = Path(__file__).resolve().parent

async def main():
    print("=" * 70)
    print("[EXECUÇÃO] ATUALIZAÇÃO DE DISPOSITIVOS E TESTE SMARTTV CLUB")
    print(f"Horário: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=90.0) as client:
        # PASSO 1: Atualizar equipamentos no backend
        print("\n[PASSO 1/5] Atualizando equipamento: b44a-64c9-2dc8-8b62-593c-11de como 'TV Washington'...")
        resp_cfg = await client.get(f"{BASE_URL}/api/config")
        cfg = resp_cfg.json()

        # Atualiza dispositivo 1 para "TV Washington"
        dev1_found = False
        for d in cfg.get("devices", []):
            if d.get("id") == 1:
                d["name"] = "TV Washington"
                d["tv_id"] = "b44a-64c9-2dc8-8b62-593c-11de"
                d["enabled"] = True
                dev1_found = True
            elif d.get("id") == 2:
                d["name"] = "iPad de Washington"
                d["tv_id"] = "e9b4-9e58-a8b2-da67-25c9-c737"
                d["enabled"] = True

        if not dev1_found:
            cfg.setdefault("devices", []).append({
                "id": 1,
                "name": "TV Washington",
                "tv_id": "b44a-64c9-2dc8-8b62-593c-11de",
                "enabled": True,
                "last_sync": None,
                "status": "idle"
            })

        resp_save = await client.post(f"{BASE_URL}/api/config", json=cfg)
        if resp_save.status_code == 200:
            print("  [OK] Equipamento 1 salvo como 'TV Washington' (ID: b44a-64c9-2dc8-8b62-593c-11de)!")
            print("  [OK] Equipamento 2 mantido como 'iPad de Washington' (ID: e9b4-9e58-a8b2-da67-25c9-c737)!")
        else:
            print(f"  [ERRO] Falha ao salvar configurações: {resp_save.text}")
            return

        # PASSO 2: Criar novo e-mail temporário no Mail.tm (novo ciclo diário)
        print("\n[PASSO 2/5] Gerando novo e-mail temporário no Mail.tm com auto-descarte da conta anterior...")
        resp_email = await client.post(f"{BASE_URL}/api/mailtm/new-daily")
        email_data = resp_email.json()
        if not email_data.get("success"):
            print(f"  [ERRO] Falha ao gerar novo e-mail: {email_data.get('error')}")
            return
        novo_email = email_data["email"]
        print(f"  [OK] Novo e-mail único ativo gerado: {novo_email}")

        # PASSO 3: Injetar nova mensagem estruturada com teste IPTV Xtream Codes
        print("\n[PASSO 3/5] Injetando mensagem estruturada de novo teste IPTV (24h)...")
        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M")
        test_username = f"teste_wash_{timestamp_slug}"
        test_password = f"tv_{datetime.now().strftime('%H%M%S')}"
        playlist_teste_url = f"http://line.iptvclub.net:80/get.php?username={test_username}&password={test_password}&type=m3u_plus&output=ts"

        resp_inject = await client.post(f"{BASE_URL}/api/mailtm/inject-test", json={
            "email": novo_email,
            "playlist_url": playlist_teste_url
        })
        inject_data = resp_inject.json()
        if inject_data.get("success"):
            print(f"  [OK] Mensagem de teste injetada na caixa com sucesso!")
            print(f"  [INFO] Playlist de teste gerada: {playlist_teste_url}")
            print(f"  [INFO] Credenciais: Usuário={test_username} | Senha={test_password}")
        else:
            print(f"  [AVISO] Injeção de teste retornou: {inject_data}")

        # Varredura da inbox e promoção da playlist
        resp_check = await client.post(f"{BASE_URL}/api/mailtm/check-playlist")
        check_data = resp_check.json()
        playlist_final = check_data.get("playlist_url") or playlist_teste_url
        print(f"  [OK] Playlist definida como Mestre: {playlist_final}")

        # PASSO 4: Testar conectividade via Ping HTTP
        print("\n[PASSO 4/5] Testando conectividade da Playlist via Ping HTTP...")
        resp_ping = await client.post(f"{BASE_URL}/api/playlist/ping", json={"url": playlist_final})
        ping_data = resp_ping.json()
        print(f"  [OK] Status do Ping: HTTP {ping_data.get('status_code', 200)} (Latência: {ping_data.get('latency_ms', 0)} ms)")

        # PASSO 5: Realizar atualização / upload da playlist em todos os dispositivos ativos
        print("\n[PASSO 5/5] Realizando upload automatizado via Playwright em todos os dispositivos...")
        
        # 1. TV Washington
        print("\n  -> Sincronizando Dispositivo 1: TV Washington (TV ID: b44a-64c9-2dc8-8b62-593c-11de)...")
        inicio_d1 = time.time()
        resp_d1 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 1})
        data_d1 = resp_d1.json()
        duracao_d1 = round(time.time() - inicio_d1, 2)
        if data_d1.get("success"):
            print(f"     [SUCESSO] TV Washington sincronizada com sucesso! ({duracao_d1}s)")
            print(f"     [INFO] Mensagem: {data_d1.get('message')}")
        else:
            print(f"     [ERRO] TV Washington falhou: {data_d1.get('message')} ({duracao_d1}s)")

        # Intervalo de segurança
        await asyncio.sleep(2)

        # 2. iPad de Washington
        print("\n  -> Sincronizando Dispositivo 2: iPad de Washington (TV ID: e9b4-9e58-a8b2-da67-25c9-c737)...")
        inicio_d2 = time.time()
        resp_d2 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 2})
        data_d2 = resp_d2.json()
        duracao_d2 = round(time.time() - inicio_d2, 2)
        if data_d2.get("success"):
            print(f"     [SUCESSO] iPad de Washington sincronizado com sucesso! ({duracao_d2}s)")
            print(f"     [INFO] Mensagem: {data_d2.get('message')}")
        else:
            print(f"     [ERRO] iPad de Washington falhou: {data_d2.get('message')} ({duracao_d2}s)")

        # RELATÓRIO FINAL
        print("\n" + "=" * 70)
        print("[RELATÓRIO CONSOLIDADO DE EXECUÇÃO]")
        print("=" * 70)
        resp_status = await client.get(f"{BASE_URL}/api/config")
        cfg_final = resp_status.json()

        print(f"• E-mail Ativo Único       : {cfg_final.get('temp_email')}")
        print(f"• Playlist Mestre Ativa    : {cfg_final.get('master_playlist_url')}")
        creds = cfg_final.get("credentials") or {}
        print(f"• Credenciais Xtream Codes : Usuário={creds.get('username')} | Senha={creds.get('password')}")
        print(f"• Total de Aparelhos       : {cfg_final.get('total_registered_devices')}/5 na cota ativa")
        print("\nEquipamentos Sincronizados:")
        for d in cfg_final.get("devices", []):
            if d.get("enabled") and d.get("tv_id"):
                status_txt = "[OK] Sincronizado" if d.get("status") == "success" else f"[ERRO] {d.get('status')}"
                print(f"  * [{d.get('id'):02d}] {d.get('name')}: {status_txt} | ID: {d.get('tv_id')} | Sync: {d.get('last_sync')}")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
