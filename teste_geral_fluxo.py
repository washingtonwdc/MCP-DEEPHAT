"""
Script de Teste Geral Automatizado do SmartTV Club
Fluxo Completo:
1. Cria um novo e-mail temporário no Mail.tm (Ciclo Diário 00:00 com auto-descarte da conta anterior).
2. Inspeciona a caixa de entrada e extrai link de playlist do conteúdo da mensagem (/api/mailtm/check-playlist).
3. Valida a conectividade da Playlist via Ping HTTP (Status 200).
4. Atualiza a Playlist Mestre compartilhada e configurações no servidor.
5. Dispara a sincronização via Playwright para o Celular de Washington (ID 1).
6. Dispara a sincronização via Playwright para o iPad de Washington (ID 2).
7. Exibe o relatório de execução consolidado e cota de aparelhos.
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

# URL de teste M3U pública e ativa como fallback
FALLBACK_PLAYLIST_URL = "https://iptv-org.github.io/iptv/index.m3u"


async def main():
    print("=" * 70)
    print("[INÍCIO] INICIANDO FLUXO COMPLETO DO SMARTTV CLUB MULTI-DEVICE")
    print(f"Horário Local: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # ETAPA 1: Criar novo e-mail no Mail.tm (descartando anterior)
        print("\n[ETAPA 1/6] [CONTA] Gerando novo e-mail temporário no Mail.tm (Ciclo Diário)...")
        try:
            resp_mail = await client.post(f"{BASE_URL}/api/mailtm/new-daily")
            data_mail = resp_mail.json()
            if not data_mail.get("success"):
                raise RuntimeError(f"Falha ao criar e-mail: {data_mail.get('error')}")
            novo_email = data_mail["email"]
            print(f"  [OK] Novo e-mail criado e sincronizado: {novo_email}")
            print(f"  [INFO] Mensagem do servidor: {data_mail.get('message')}")
        except Exception as e:
            print(f"  [ERRO] Falha na Etapa 1: {e}")
            return

        # ETAPA 2: Ler caixa de entrada e extrair link da mensagem
        print("\n[ETAPA 2/6] [INBOX] Inspecionando caixa de entrada e extraindo links da mensagem...")
        playlist_alvo = FALLBACK_PLAYLIST_URL
        try:
            resp_check = await client.post(f"{BASE_URL}/api/mailtm/check-playlist")
            data_check = resp_check.json()
            total_msgs = data_check.get("total_messages", 0)
            print(f"  [INFO] Total de mensagens na caixa: {total_msgs}")
            
            if data_check.get("found") and data_check.get("playlist_url"):
                playlist_alvo = data_check["playlist_url"]
                print(f"  [SUCESSO] Playlist extraída do conteúdo do e-mail: {playlist_alvo}")
                if data_check.get("link_ativacao"):
                    print(f"  [INFO] Link de ativação detectado: {data_check.get('link_ativacao')}")
            else:
                print(f"  [INFO] Nenhuma playlist recebida por e-mail ainda. Utilizando lista pública homologada.")
                print(f"  [INFO] URL adotada para o fluxo: {playlist_alvo}")
        except Exception as e:
            print(f"  [AVISO] Falha ao verificar inbox: {e}. Prosseguindo com fallback.")

        # ETAPA 3: Testar conectividade da Playlist via Ping HTTP
        print("\n[ETAPA 3/6] [PING] Testando conectividade do link da playlist via Ping HTTP...")
        try:
            resp_ping = await client.post(f"{BASE_URL}/api/playlist/ping", json={"url": playlist_alvo})
            data_ping = resp_ping.json()
            if data_ping.get("online"):
                print(f"  [OK] Link da Playlist ONLINE! Código HTTP: {data_ping.get('status_code', 200)}")
            else:
                print(f"  [AVISO] Ping retornou status: {data_ping.get('message')}")
        except Exception as e:
            print(f"  [ERRO] Erro no Ping da playlist: {e}")

        # ETAPA 4: Atualizar Playlist Mestre e Configurações no Sistema
        print("\n[ETAPA 4/6] [CONFIG] Atualizando a Playlist Mestre e dispositivos ativos...")
        try:
            resp_cfg = await client.get(f"{BASE_URL}/api/config")
            cfg = resp_cfg.json()
            
            cfg["master_playlist_url"] = playlist_alvo
            cfg["new_playlist_url"] = playlist_alvo
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
                print("  [OK] Configurações salvas e Playlist Mestre definida com sucesso!")
            else:
                print(f"  [ERRO] Erro ao salvar config: {resp_save.text}")
                return
        except Exception as e:
            print(f"  [ERRO] Erro na Etapa 4: {e}")
            return

        # ETAPA 5: Disparar Sincronização para o Celular de Washington
        print("\n[ETAPA 5/6] [PLAYWRIGHT] Sincronizando Celular de Washington (ID 1: b44a-64c9-2dc8-8b62-593c-11de)...")
        print("  [INFO] Preenchendo formulário no smarttv.club via Playwright Chromium...")
        inicio_cel = time.time()
        try:
            resp_dev1 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 1})
            data_dev1 = resp_dev1.json()
            duracao_cel = round(time.time() - inicio_cel, 2)
            if data_dev1.get("success"):
                print(f"  [SUCESSO] Celular de Washington sincronizado com sucesso! ({duracao_cel}s)")
                print(f"  [INFO] Resposta: {data_dev1.get('message')}")
            else:
                print(f"  [AVISO] Retorno Celular: {data_dev1.get('message')} ({duracao_cel}s)")
        except Exception as e:
            print(f"  [ERRO] Erro ao sincronizar Celular: {e}")

        # ETAPA 6: Disparar Sincronização para o iPad de Washington
        print("\n[ETAPA 6/6] [PLAYWRIGHT] Sincronizando iPad de Washington (ID 2: e9b4-9e58-a8b2-da67-25c9-c737)...")
        print("  [INFO] Preenchendo formulário no smarttv.club via Playwright Chromium...")
        inicio_ipad = time.time()
        try:
            resp_dev2 = await client.post(f"{BASE_URL}/api/trigger-device", json={"id": 2})
            data_dev2 = resp_dev2.json()
            duracao_ipad = round(time.time() - inicio_ipad, 2)
            if data_dev2.get("success"):
                print(f"  [SUCESSO] iPad de Washington sincronizado com sucesso! ({duracao_ipad}s)")
                print(f"  [INFO] Resposta: {data_dev2.get('message')}")
            else:
                print(f"  [AVISO] Retorno iPad: {data_dev2.get('message')} ({duracao_ipad}s)")
        except Exception as e:
            print(f"  [ERRO] Erro ao sincronizar iPad: {e}")

        # RESUMO CONSOLIDADO
        print("\n" + "=" * 70)
        print("[RELATÓRIO] CONSOLIDADO DO FLUXO COMPLETO")
        print("=" * 70)
        resp_final = await client.get(f"{BASE_URL}/api/config")
        cfg_final = resp_final.json()
        print(f"• E-mail Ativo Único : {cfg_final.get('temp_email')}")
        print(f"• Playlist Mestre    : {cfg_final.get('master_playlist_url')}")
        print(f"• Cota de Aparelhos  : {cfg_final.get('total_registered_devices', 2)}/5 cadastrados (1 e-mail cobre até 5)")
        print(f"• Próxima Execução   : {cfg_final.get('next_run')}")
        print("\nStatus dos Equipamentos:")
        for d in cfg_final.get("devices", [])[:2]:
            st = d.get("status")
            badge = "[OK] Sincronizado" if st == "success" else (f"[ERRO] {st}" if st == "error" else f"[INFO] {st}")
            print(f"  [{d.get('id'):02d}] {d.get('name')}: {badge} | TV ID: {d.get('tv_id')} | Último Sync: {d.get('last_sync')}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
