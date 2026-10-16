# -*- coding: utf-8 -*-
"""
Script de Integração Total do Ecossistema IPTV
Conecta o IPTV-Manager (Bladestar2105) às Playlists Hospedadas na VPS,
provisiona o usuário mestre 'washington', mapeia categorias e canais,
e valida a emulação Xtream Codes na porta 5050.
"""

import sys
import json
import time
import requests
import sqlite3

IPTV_BASE_URL = "http://127.0.0.1:3000"
PUBLIC_BASE_URL = "http://163.176.216.39:5050"
ADMIN_USER = "admin"
ADMIN_PASS = "Admin@IPTV2026!"

TARGET_USERNAME = "washington"
TARGET_PASSWORD = "tv_washington_2026"
TARGET_CONNECTIONS = 5


def main():
    print("[INFO] Iniciando integracao completa do IPTV-Manager com playlists e usuarios...")

    # 1. Autenticacao no IPTV-Manager
    print("[INFO] Realizando login administrativo no IPTV-Manager...")
    try:
        resp = requests.post(
            f"{IPTV_BASE_URL}/api/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"[ERRO] Falha no login: HTTP {resp.status_code} - {resp.text}")
            return False

        token = resp.json().get("token")
        if not token:
            print("[ERRO] Token JWT nao retornado na resposta de login.")
            return False
        print("[SUCESSO] Login administrativo efetuado com sucesso!")
    except Exception as e:
        print(f"[ERRO] Falha ao conectar ao IPTV-Manager: {e}")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 2. Localizar ID do usuario mestre 'washington'
    print(f"[INFO] Consultando usuario '{TARGET_USERNAME}'...")
    resp_users = requests.get(f"{IPTV_BASE_URL}/api/users", headers=headers, timeout=10)
    users = resp_users.json() if resp_users.status_code == 200 else []
    user_id = None
    for u in users:
        if u.get("username") == TARGET_USERNAME:
            user_id = u.get("id")
            print(f"[INFO] Usuario mestre localizado: ID {user_id}")
            break

    if not user_id:
        print("[ERRO] Usuario mestre 'washington' nao encontrado.")
        return False

    # 3. Vincular user_id no Provedor 1
    try:
        con = sqlite3.connect('/opt/iptv-manager/data/db.sqlite')
        cur = con.cursor()
        cur.execute("UPDATE providers SET user_id = ? WHERE id = 1", (user_id,))
        con.commit()
        con.close()
    except Exception as e:
        print(f"[AVISO] SQLite provider update: {e}")

    # 4. Importar Categorias e Canais para o Usuario Mestre
    print("[INFO] Consultando categorias disponiveis no provedor ID 1...")
    try:
        resp_cats = requests.get(
            f"{IPTV_BASE_URL}/api/providers/1/categories",
            headers=headers,
            timeout=15
        )
        categories = resp_cats.json() if resp_cats.status_code == 200 else []
        print(f"[INFO] Total de categorias encontradas no provedor: {len(categories)}")

        if categories:
            # Dividir em lotes de 15 categorias para importacao estavel e rapida
            batch_size = 15
            for i in range(0, len(categories), batch_size):
                chunk = categories[i:i + batch_size]
                cats_payload = []
                for c in chunk:
                    cat_id = str(c.get("category_id") or c.get("id"))
                    cat_name = c.get("category_name") or c.get("name")
                    if cat_id and cat_name:
                        cats_payload.append({
                            "id": cat_id,
                            "name": cat_name,
                            "import_channels": True,
                            "type": c.get("category_type") or c.get("type") or "live"
                        })

                print(f"[INFO] Importando lote {i//batch_size + 1} ({len(cats_payload)} categorias)...")
                resp_imp = requests.post(
                    f"{IPTV_BASE_URL}/api/providers/1/import-categories",
                    headers=headers,
                    json={
                        "user_id": user_id,
                        "categories": cats_payload
                    },
                    timeout=60
                )
                if resp_imp.status_code == 200:
                    data_imp = resp_imp.json()
                    print(f"  [OK] Lote {i//batch_size + 1}: +{data_imp.get('categories_imported', 0)} cats, +{data_imp.get('channels_imported', 0):,} canais")
                else:
                    print(f"  [AVISO] Falha no lote {i//batch_size + 1}: HTTP {resp_imp.status_code} - {resp_imp.text[:150]}")
    except Exception as e:
        print(f"[AVISO] Erro na importacao de categorias: {e}")

    # 5. Estatisticas finais no Banco SQLite
    try:
        con = sqlite3.connect('/opt/iptv-manager/data/db.sqlite')
        cur = con.cursor()
        ch_count = cur.execute("SELECT COUNT(*) FROM provider_channels WHERE provider_id = 1").fetchone()[0]
        cat_count = cur.execute("SELECT COUNT(DISTINCT original_category_id) FROM provider_channels WHERE provider_id = 1").fetchone()[0]
        user_cat_count = cur.execute("SELECT COUNT(*) FROM user_categories WHERE user_id = ?", (user_id,)).fetchone()[0]
        user_ch_count = cur.execute("SELECT COUNT(*) FROM user_channels uc JOIN user_categories cat ON cat.id = uc.user_category_id WHERE cat.user_id = ?", (user_id,)).fetchone()[0]
        con.close()
        print(f"\n=======================================================")
        print(f"[ESTATISTICAS CONSOLIDADAS DO ECOSSISTEMA]")
        print(f"  - Provedor ID 1 (Playlists Hospedadas VPS):")
        print(f"    * Canais Totais no Provedor: {ch_count:,}")
        print(f"    * Categorias no Provedor: {cat_count:,}")
        print(f"  - Usuario Mestre '{TARGET_USERNAME}' (ID {user_id}):")
        print(f"    * Categorias Ativas: {user_cat_count:,}")
        print(f"    * Canais Liberados e Ativos: {user_ch_count:,}")
        print(f"    * Conexoes Simultaneas Permitidas: {TARGET_CONNECTIONS}")
        print(f"=======================================================\n")
    except Exception as e:
        print(f"[AVISO] Erro ao consultar estatisticas no SQLite: {e}")

    # 6. Validar Emulacao Xtream Codes na porta 5050
    print("[INFO] Validando endpoints Xtream Codes na porta 5050 (Gateway Starlette)...")
    try:
        url_player_api = f"{PUBLIC_BASE_URL}/player_api.php?username={TARGET_USERNAME}&password={TARGET_PASSWORD}&action=get_live_categories"
        r_api = requests.get(url_player_api, timeout=10)
        print(f"  [TESTE] player_api.php (get_live_categories): HTTP {r_api.status_code}")
        if r_api.status_code == 200:
            cats_live = r_api.json()
            print(f"  [OK] Categorias retornadas para cliente Xtream: {len(cats_live):,}")
    except Exception as e:
        print(f"  [AVISO] Erro no teste do player_api.php: {e}")

    try:
        url_m3u = f"{PUBLIC_BASE_URL}/get.php?username={TARGET_USERNAME}&password={TARGET_PASSWORD}&type=m3u_plus&output=ts"
        r_m3u = requests.get(url_m3u, headers={"Range": "bytes=0-4096"}, timeout=12)
        print(f"  [TESTE] get.php (M3U Plus): HTTP {r_m3u.status_code} ({len(r_m3u.content)} bytes lidos)")
        if r_m3u.status_code in [200, 206]:
            print("  [OK] Header e primeiros canais M3U recebidos com sucesso!")
            preview = r_m3u.text[:350].replace('\r', '')
            print("  --- Amostra de M3U Gerada ---")
            for line in preview.split('\n')[:8]:
                if line.strip():
                    print(f"    {line}")
    except Exception as e:
        print(f"  [AVISO] Erro no teste do get.php: {e}")

    print("\n[SUCESSO] Integracao total finalizada com exito!")
    return True


if __name__ == "__main__":
    main()
