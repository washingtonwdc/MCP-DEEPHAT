"""
Script de Teste Geral Automatizado do SmartTV Club
Fluxo Completo:
1. Cria um novo e-mail temporário no Mail.tm (Ciclo Diário 00:00).
2. Simula/Recebe a mensagem com o link da lista M3U.
3. Extrai e valida a conectividade do link M3U via ping HTTP (Status 200).
4. Atualiza a Playlist Mestre compartilhada.
5. Dispara a sincronização via Playwright para os aparelhos de Washington:
   - Celular de Washington (b44a-64c9-2dc8-8b62-593c-11de)
   - iPad de Washington (e9b4-9e58-a8b2-da67-25c9-c737)
6. Exibe o relatório de execução consolidado.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Configuração de encoding para Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "smarttv_config.json"
BASE_URL = "http://127.0.0.1:5050"

# URL de teste M3U pública e ativa
TEST_PLAYLIST_URL = "https://iptv-org.github.io/iptv/index.m3u"


async def main():
    print("=" * 70)
    print("🧪 INICIANDO TESTE GERAL DO SMARTTV CLUB MULTI-DEVICE AUTO-SYNC")
    print(f"⏰ Horário Local: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ETAPA 1: Criar novo e-mail no Mail.tm
        print("\n[ETAPA 1/5] Gerando novo e-mail temporário no Mail.tm...")
        try:
            resp_mail = await client.post(f"{BASE_URL}/api/mailtm/new-daily")
            data_mail = resp_mail.json()
            if not data_mail.get("success"):
                raise RuntimeError(f"Falha ao criar e-mail: {data_mail.get('error')}")
            novo_email = data_mail["email"]
            print(f"  ✅ E-mail temporário criado: {novo_email}")
        except Exception as e:
            print(f"  ❌ Erro na Etapa 1: {e}")
            return

        # ETAPA 2: Testar conectividade da Playlist M3U via Ping
        print("\n[ETAPA 2/5] Testando link da lista M3U recebida via Ping HTTP...")
        try:
            resp_ping = await client.post(f"{BASE_URL}/api/playlist/ping", json={"url": TEST_PLAYLIST_URL})
            data_ping = resp_ping.json()
            if data_ping.get("online"):
                print(f"  ✅ Link M3U Online! Código HTTP: {data_ping.get('status_code', 200)}")
                print(f"  📡 URL da Lista: {TEST_PLAYLIST_URL}")
            else:
                print(f"  ⚠️ Aviso: Ping retornou offline: {data_ping.get('message')}")
        except Exception as e:
            print(f"  ❌ Erro no Ping M3U: {e}")

        # ETAPA 3: Atualizar Playlist Mestre no Sistema
        print("\n[ETAPA 3/5] Atualizando a Playlist Mestre compartilhada...")
        try:
            # Obtém config atual
            resp_cfg = await client.get(f"{BASE_URL}/api/config")
            cfg = resp_cfg.json()
            
            cfg["master_playlist_url"] = TEST_PLAYLIST_URL
            cfg["new_playlist_url"] = TEST_PLAYLIST_URL
            cfg["temp_email"] = novo_email
            cfg["last_playlist_check"] = datetime.now().isoformat()
            
            # Garante que os aparelhos 1 e 2 estejam ativos
            for d in cfg.get("devices", []):
                if d.get("id") in [1, 2]:
                    d["enabled"] = True
                elif not d.get("tv_id", "").strip():
                    d["enabled"] = False
                    
            resp_save = await client.post(f"{BASE_URL}/api/config", json=cfg)
            if resp_save.status_code == 200:
                print("  ✅ Configurações atualizadas e salvas com sucesso no servidor!")
            else:
                print(f"  ❌ Erro ao salvar config: {resp_save.text}")
                return
        except Exception as e:
            print(f"  ❌ Erro na Etapa 3: {e}")
            return

        # ETAPA 4: Disparar Sincronização para o Celular de Washington
        print("\n[ETAPA 4/5] Sincronizando Celular de Washington (ID 1: b44a-64c9-2dc8-8b62-593c-11de)...")
        print("  ⏳ Abrindo Chromium via Playwright e preenchendo formulário no smarttv.club...")
        inicio_cel = time.time()
        try:
            resp_dev1 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 1})
            data_dev1 = resp_dev1.json()
            duracao_cel = round(time.time() - inicio_cel, 2)
            if data_dev1.get("success"):
                print(f"  ✅ Celular de Washington: SUCESSO! ({duracao_cel}s)")
                print(f"     Mensagem: {data_dev1.get('message')}")
            else:
                print(f"  ⚠️ Celular de Washington: Retorno {data_dev1.get('message')} ({duracao_cel}s)")
        except Exception as e:
            print(f"  ❌ Erro ao sincronizar Celular: {e}")

        # ETAPA 5: Disparar Sincronização para o iPad de Washington
        print("\n[ETAPA 5/5] Sincronizando iPad de Washington (ID 2: e9b4-9e58-a8b2-da67-25c9-c737)...")
        print("  ⏳ Abrindo Chromium via Playwright e preenchendo formulário no smarttv.club...")
        inicio_ipad = time.time()
        try:
            resp_dev2 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 2})
            data_dev2 = resp_dev2.json()
            duracao_ipad = round(time.time() - inicio_ipad, 2)
            if data_dev2.get("success"):
                print(f"  ✅ iPad de Washington: SUCESSO! ({duracao_ipad}s)")
                print(f"     Mensagem: {data_dev2.get('message')}")
            else:
                print(f"  ⚠️ iPad de Washington: Retorno {data_dev2.get('message')} ({duracao_ipad}s)")
        except Exception as e:
            print(f"  ❌ Erro ao sincronizar iPad: {e}")

        # RESUMO FINAL
        print("\n" + "=" * 70)
        print("📊 RELATÓRIO DO TESTE GERAL CONSOLIDADO")
        print("=" * 70)
        resp_final = await client.get(f"{BASE_URL}/api/config")
        cfg_final = resp_final.json()
        print(f"• E-mail Ativo Atual : {cfg_final.get('temp_email')}")
        print(f"• Playlist Mestre    : {cfg_final.get('master_playlist_url')}")
        print(f"• Próxima Execução   : {cfg_final.get('next_run')}")
        print("\nStatus dos Equipamentos:")
        for d in cfg_final.get("devices", [])[:2]:
            st = d.get("status")
            badge = "🟢 Sincronizado" if st == "success" else ("🔴 Falha" if st == "error" else f"⚪ {st}")
            print(f"  [{d.get('id'):02d}] {d.get('name')}: {badge} | TV ID: {d.get('tv_id')} | Último Sync: {d.get('last_sync')}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
