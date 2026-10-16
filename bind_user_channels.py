# -*- coding: utf-8 -*-
"""
Script de Vinculação Direta de Categorias e Canais para Usuário Mestre IPTV
Mapeia automaticamente todos os canais do provedor local para o usuário 'washington'.
"""

import sqlite3
import requests
import sys

DB_PATH = "/opt/iptv-manager/data/db.sqlite"
TARGET_USERNAME = "washington"
TARGET_PASSWORD = "tv_washington_2026"
PUBLIC_BASE_URL = "http://163.176.216.39:5050"


def main():
    print("[INFO] Iniciando mapeamento e vinculacao total de canais para o usuario mestre...")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # 1. Localizar usuario
    user_row = cur.execute("SELECT id, username FROM users WHERE username = ?", (TARGET_USERNAME,)).fetchone()
    if not user_row:
        print(f"[ERRO] Usuario '{TARGET_USERNAME}' nao encontrado no banco de dados!")
        con.close()
        return False

    user_id = user_row[0]
    print(f"[INFO] Usuario '{TARGET_USERNAME}' localizado com ID {user_id}.")

    # 2. Localizar provedor
    provider_row = cur.execute("SELECT id, name FROM providers WHERE id = 1").fetchone()
    if not provider_row:
        print("[ERRO] Provedor 1 nao encontrado!")
        con.close()
        return False

    provider_id = provider_row[0]
    print(f"[INFO] Provedor 1 localizado: {provider_row[1]}")

    # 3. Obter todas as categorias existentes em category_mappings ou provider_channels
    mappings = cur.execute("""
        SELECT id, provider_category_id, provider_category_name, user_category_id, category_type
        FROM category_mappings
        WHERE provider_id = ? AND user_id = ?
    """, (provider_id, user_id)).fetchall()

    print(f"[INFO] Total de category_mappings registradas: {len(mappings)}")

    # Se mappings estiver vazio, vamos buscar direto de provider_channels
    if not mappings:
        print("[INFO] category_mappings vazia. Extraindo categorias de provider_channels...")
        cats_raw = cur.execute("""
            SELECT DISTINCT original_category_id
            FROM provider_channels
            WHERE provider_id = ?
        """, (provider_id,)).fetchall()
        print(f"[INFO] Categorias extraidas de provider_channels: {len(cats_raw)}")

    sort_order = 0
    total_canais_vinculados = 0
    total_categorias_criadas = 0

    # Iniciar transacao atomica
    cur.execute("BEGIN TRANSACTION")

    # Mapear cada categoria
    for m in mappings:
        mapping_id, prov_cat_id, prov_cat_name, user_cat_id, cat_type = m
        cat_type = cat_type or "live"
        cat_name = prov_cat_name or f"Categoria {prov_cat_id}"

        # Verificar se user_category ja existe
        uc_row = cur.execute("""
            SELECT id FROM user_categories
            WHERE user_id = ? AND name = ? AND type = ?
        """, (user_id, cat_name, cat_type)).fetchone()

        if uc_row:
            target_user_cat_id = uc_row[0]
        else:
            sort_order += 1
            cur.execute("""
                INSERT INTO user_categories (user_id, name, is_adult, sort_order, type)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, cat_name, 0, sort_order, cat_type))
            target_user_cat_id = cur.lastrowid
            total_categorias_criadas += 1

        # Atualizar mapping com a user_category_id
        cur.execute("""
            UPDATE category_mappings
            SET user_category_id = ?
            WHERE id = ?
        """, (target_user_cat_id, mapping_id))

        # Obter todos os canais desta categoria do provedor
        channels = cur.execute("""
            SELECT id, original_sort_order
            FROM provider_channels
            WHERE provider_id = ? AND original_category_id = ?
        """, (provider_id, prov_cat_id)).fetchall()

        # Inserir em user_channels se nao estiver presente
        for ch_idx, ch in enumerate(channels):
            ch_id = ch[0]
            existing_uch = cur.execute("""
                SELECT id FROM user_channels
                WHERE user_category_id = ? AND provider_channel_id = ?
            """, (target_user_cat_id, ch_id)).fetchone()

            if not existing_uch:
                cur.execute("""
                    INSERT INTO user_channels (
                        user_category_id, provider_channel_id, sort_order,
                        custom_name, is_hidden, assignment_origin,
                        granted_by_admin, authorization_revoked, mapping_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    target_user_cat_id, ch_id, ch_idx,
                    "", 0, "mapping",
                    1, 0, mapping_id
                ))
                total_canais_vinculados += 1

    con.commit()
    con.close()

    print(f"\n[SUCESSO DA VINCULACAO]")
    print(f"  - Novas Categorias Criadas: {total_categorias_criadas}")
    print(f"  - Novos Canais Vinculados: {total_canais_vinculados:,}")

    # Reiniciar servico do IPTV-Manager para limpar caches em memoria
    print("[INFO] Reiniciando iptv-manager.service na VPS para atualizar caches...")
    import subprocess
    subprocess.run(["systemctl", "restart", "iptv-manager.service"], check=False)
    time.sleep(3)

    # Validar clientes Xtream e M3U
    print("\n[VALIDACAO DE SAIDA XTREAM / M3U]")
    try:
        url_api = f"{PUBLIC_BASE_URL}/player_api.php?username={TARGET_USERNAME}&password={TARGET_PASSWORD}&action=get_live_categories"
        r_api = requests.get(url_api, timeout=10)
        if r_api.status_code == 200:
            cats = r_api.json()
            print(f"  [OK] player_api.php: {len(cats)} categorias ativas retornadas!")
        else:
            print(f"  [AVISO] player_api.php: HTTP {r_api.status_code}")
    except Exception as e:
        print(f"  [AVISO] player_api.php erro: {e}")

    try:
        url_m3u = f"{PUBLIC_BASE_URL}/get.php?username={TARGET_USERNAME}&password={TARGET_PASSWORD}&type=m3u_plus&output=ts"
        r_m3u = requests.get(url_m3u, headers={"Range": "bytes=0-8192"}, timeout=12)
        if r_m3u.status_code in [200, 206]:
            print(f"  [OK] get.php (M3U Plus): {len(r_m3u.content)} bytes lidos no chunk inicial!")
            linhas = [l for l in r_m3u.text.split('\n') if l.startswith("#EXTINF")][:5]
            print(f"  [OK] Primeiros {len(linhas)} canais gerados na playlist:")
            for l in linhas:
                print(f"    * {l[:90]}...")
        else:
            print(f"  [AVISO] get.php: HTTP {r_m3u.status_code}")
    except Exception as e:
        print(f"  [AVISO] get.php erro: {e}")

    print("\n[CONCLUIDO] Integracao total finalizada com sucesso!")
    return True


if __name__ == "__main__":
    main()
