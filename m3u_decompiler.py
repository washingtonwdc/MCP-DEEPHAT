#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U Playlist Decompiler, Parser & Hosting Generator
WashingtonProNet - SmartTV Club Multi-Device Ecosystem

Baixa, descompila, categoriza e gera arquivos de playlist M3U e metadados JSON
estruturados para hospedagem local e remota na VPS.
Separa rigorosamente:
  1. canais.m3u / ao_vivo.m3u: Canais de TV Linear / Ao Vivo
  2. filmes.m3u: Filmes sob Demanda (VOD)
  3. series.m3u: Séries e Novelas On Demand
  4. all.m3u: Catálogo completo unificado
"""

import os
import sys
import re
import json
import argparse
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx

DEFAULT_URL = "http://zymv.shop/get.php?username=goldlnr020&password=56508193&type=m3u_plus&output=mpegts"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "hosted_playlists"

# Mapeamentos exatos das categorias da playlist oficial do provedor
EXACT_SERIES_GROUPS = {
    "♦️ Novelas",
    "♦️ Legendadas",
    "♦️ Netflix",
    "♦️ Outras Produtoras",
    "♦️ Prime Video",
    "♦️ Globoplay",
    "♦️ HBO Max",
    "♦️ Disney+",
    "♦️ Doramas Legendados",
    "♦️ Paramount+",
    "♦️ Discovery+",
    "♦️ Crunchyroll",
    "♦️ Novelas Turcas",
    "♦️ Apple TV+",
    "♦️ Star+",
    "♦️ DirecTV",
    "♦️ Doramas",
    "♦️ Funimation Now",
    "♦️ SBT+",
    "♦️ Programas de TV",
    "♦️ Brasil Paralelo",
    "♦️ Univer",
    "♦️ Claro video",
    "♦️ PlutoTV",
    "♦️ Lionsgate",
    "♦️ AMC Plus"
}

EXACT_MOVIE_GROUPS = {
    "♦️ Legendados ✔️",
    "♦️ Adultos ❌❤️ [+18]",
    "♦️ Drama ✔️",
    "♦️ Comedia ✔️",
    "♦️ Ação ✔️",
    "♦️ Terror ☠",
    "♦️ UHD| 4K ⭐",
    "♦️ Animacao ✔️",
    "♦️ Nacionais ✔️",
    "♦️ Adultos ❌ [LEGENDADO]",
    "♦️ Documentário ✔️",
    "♦️ Suspense ✔️",
    "♦️ Romance ✔️",
    "♦️ Adultos ❌   [ONLYFANS]",
    "♦️ Ficcao Cientifica ✔️",
    "♦️ Fantasia ✔️",
    "♦️ Crime ✔️",
    "♦️Top  Lançamentos 2026  ⭐",
    "♦️ Adultos ❌ [TRANS]",
    "⭐ ReelsShorts",
    "♦️ Esportes ✔️",
    "♦️ Faroeste ✔️",
    "♦️ Adultos ❌ [Bella da Semana]",
    "♦️ Guerra ⚔",
    "♦️ Adultos ❌ [GAYS]",
    "♦️ Religiosos ✔️",
    "♦️ Familia ✔️",
    "♦️ Aventura ✔️",
    "♦️ Shows ✔️",
    "♦️ Especial Infantil ✔️",
    "♦️ Dublagem Nao Oficial ✔️",
    "♦️ Stand Up Comedy ✔️",
    "♦️ Cinema ⭐",
    "Filmes | Drama",
    "Filmes | Ficcao",
    "Documentarios"
}

EXACT_LIVE_GROUPS = {
    "♦️  FILMES E SÉRIES",
    "♦️  GLOBO | REGIONAIS",
    "♦️  GLOBO | CAPITAIS",
    "♦️ CANAIS 24H | DESENHOS ⭐",
    "♦️ CANAIS 24H | SERIES ⭐",
    "♦️ CANAIS | FHD H265 ⭐",
    "♦️  REDE RECORD",
    "♦️  ABERTOS",
    "♦️  VARIEDADES",
    "♦️ CANAIS 24H | LIVES & SHOWS ⭐",
    "♦️  NOTICIAS",
    "♦️  SBT",
    "♦️  RELIGIOSOS",
    "♦️  INFANTIL",
    "♦️  HBO",
    "♦️  DISCOVERY",
    "♦️  PREMIERE",
    "♦️ CANAIS 24H  | PREMIUM ⭐",
    "♦️  REDE BANDEIRANTES",
    "♦️  ESPN",
    "♦️  TELECINE",
    "♦️ CANAIS | UHD 4K ⭐",
    "♦️ EVENTOS EM DESTAQUE",
    "♦️  DOCUMENTÁRIOS",
    "♦️  ESPORTES",
    "♦️  SPORTV",
    "♦️ PPV | NFL",
    "♦️  CINE SKY",
    "♦️  PPV | ESPORTES ⛳",
    "♦️  PPV | NBA PASS",
    "♦️ PPV | PARAMOUNT+ ⚽️",
    "♦️  HISTORY",
    "♦️ PPV | DISNEY+ ⚽️",
    "♦️ A FAZENDA 2026 ⭐",
    "♦️  PPV | AMAZON PRIME ⚽️",
    "♦️ PPV | MAX ⚽",
    "♦️  PPV | DAZN ⚽️",
    "♦️ PPV | GOAT ⚽️",
    "♦️ PPV | APPLE TV⛳",
    "♦️ PPV | NSPORTS ⚽️",
    "♦️  PPV | ONE FOOTBAL ⚽️",
    "♦️  SPORTYNET ⚽️",
    "♦️ PPV | CAZÉTV ⚽️",
    "♦️ UFC PARAMOUNT+ ⭐",
    "♦️ ADULTOS +18 ❌♠️",
    "Update"
}


def sanitize_filename(name: str) -> str:
    """Converte um nome de categoria para um nome de arquivo seguro."""
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    name = re.sub(r'[^\w\s-]', '', name).strip().lower()
    name = re.sub(r'[-\s]+', '_', name)
    return name or "outros"


def classificar_tipo(grupo: str, nome: str, stream_url: str = "") -> str:
    """
    Classifica rigorosamente o item em:
      - 'canais': Canal de TV Linear / Ao Vivo
      - 'filmes': Filme sob Demanda (VOD)
      - 'series': Série de TV, Novela ou Dorama On Demand
    Garante separação estrita sem misturar séries com filmes ou canais ao vivo.
    """
    g_raw = (grupo or "").strip()
    g_upper = g_raw.upper()
    n_raw = (nome or "").strip()
    n_upper = n_raw.upper()
    u_lower = (stream_url or "").lower()

    # 1. Correspondência exata pelo conjunto oficial de grupos da Gold/M3U
    if g_raw in EXACT_SERIES_GROUPS:
        return "series"
    if g_raw in EXACT_MOVIE_GROUPS:
        return "filmes"
    if g_raw in EXACT_LIVE_GROUPS:
        return "canais"

    # 2. Heurística estrita de marcação de episódio (S01E01, T01E01, etc.)
    # Séries sempre contêm identificação de temporada/episódio no título
    if re.search(r'\bS\d{1,2}\s*E\d{1,3}\b', n_upper) or \
       re.search(r'\bT\d{1,2}\s*E\d{1,3}\b', n_upper) or \
       re.search(r'\bTEMPORADA\s*\d+\b', n_upper) or \
       re.search(r'\bEPIS[OÓ]DIO\s*\d+\b', n_upper) or \
       re.search(r'\bCAP[IÍ]TULO\s*\d+\b', n_upper):
        return "series"

    # 3. Análise da rota do stream
    if "/series/" in u_lower:
        return "series"
    if "/movie/" in u_lower:
        return "filmes"
    if "/live/" in u_lower:
        return "canais"

    # 4. Palavras-chave no nome do grupo
    if "✔️" in g_raw or any(k in g_upper for k in ["VOD", "CINEMA", "FILME", "FILMES", "LANÇAMENTO", "LANCAMENTO"]):
        return "filmes"

    if any(k in g_upper for k in ["SERIE", "SÉRIE", "SERIES", "NOVELA", "DORAMA"]):
        return "series"

    if any(k in g_upper for k in ["CANAL", "CANAIS", "24H", "AO VIVO", "LIVE", "ABERTO", "PPV", "ESPORTE", "GLOBO", "RECORD", "SBT"]):
        return "canais"

    # 5. Sufixos típicos de canais de TV linear (FHD, HD, SD, [ALT], H265) sem numeração de ano
    if re.search(r'\b(FHD|HD|SD|4K|H265)\b', n_upper) and not re.search(r'\b(19\d\d|20\d\d)\b', n_upper):
        return "canais"

    return "canais"


def parse_extinf(extinf_line: str) -> Dict[str, str]:
    """Extrai atributos de uma linha #EXTINF."""
    res = {
        "xui_id": "",
        "tvg_id": "",
        "tvg_name": "",
        "tvg_logo": "",
        "group_title": "Outros",
        "name": ""
    }

    xui = re.search(r'xui-id="([^"]*)"', extinf_line)
    if xui: res["xui_id"] = xui.group(1)

    tvid = re.search(r'tvg-id="([^"]*)"', extinf_line)
    if tvid: res["tvg_id"] = tvid.group(1)

    tvname = re.search(r'tvg-name="([^"]*)"', extinf_line)
    if tvname: res["tvg_name"] = tvname.group(1)

    tvlogo = re.search(r'tvg-logo="([^"]*)"', extinf_line)
    if tvlogo: res["tvg_logo"] = tvlogo.group(1)

    grp = re.search(r'group-title="([^"]*)"', extinf_line)
    if grp: res["group_title"] = grp.group(1).strip()

    name_match = re.search(r',([^,]+)$', extinf_line)
    if name_match:
        res["name"] = name_match.group(1).strip()
    else:
        res["name"] = res["tvg_name"] or "Canal Sem Nome"

    return res


def baixar_playlist(url: str, destino_arquivo: Path) -> bool:
    """Baixa a playlist M3U completa via HTTP streaming com progresso."""
    print(f"[INFO] Conectando a {url}...")
    destino_arquivo.parent.mkdir(parents=True, exist_ok=True)
    
    with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
        if response.status_code != 200:
            print(f"[ERRO] Resposta HTTP {response.status_code} ao baixar playlist.")
            return False
        
        total = int(response.headers.get("content-length", 0))
        baixado = 0
        with open(destino_arquivo, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1024 * 64):
                f.write(chunk)
                baixado += len(chunk)
                if total > 0 and baixado % (1024 * 1024 * 10) == 0:
                    mb = baixado / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    pct = (baixado / total) * 100
                    print(f"  [DOWNLOAD] {mb:.1f} MB / {tot_mb:.1f} MB ({pct:.1f}%)")
                    
        tam_final_mb = baixado / (1024 * 1024)
        print(f"[SUCESSO] Playlist baixada com sucesso: {tam_final_mb:.2f} MB em {destino_arquivo}")
        return True


def decompilar_m3u(arquivo_origem: Path, pasta_saida: Path) -> Dict[str, Any]:
    """
    Decompila o arquivo M3U linha a linha, gerando sub-playlists e metadados.
    Garante separação estrita: canais.m3u/ao_vivo.m3u, filmes.m3u, series.m3u e all.m3u.
    """
    print(f"[INFO] Iniciando descompilação de {arquivo_origem}...")
    pasta_saida.mkdir(parents=True, exist_ok=True)
    pasta_grupos = pasta_saida / "grupos"
    pasta_grupos.mkdir(parents=True, exist_ok=True)

    # Handlers para os arquivos de saída principais (com escrita atômica segura via .tmp)
    path_all = pasta_saida / "all.m3u"
    path_canais = pasta_saida / "canais.m3u"
    path_ao_vivo = pasta_saida / "ao_vivo.m3u"
    path_filmes = pasta_saida / "filmes.m3u"
    path_series = pasta_saida / "series.m3u"

    tmp_all = pasta_saida / "all.m3u.tmp"
    tmp_canais = pasta_saida / "canais.m3u.tmp"
    tmp_ao_vivo = pasta_saida / "ao_vivo.m3u.tmp"
    tmp_filmes = pasta_saida / "filmes.m3u.tmp"
    tmp_series = pasta_saida / "series.m3u.tmp"

    f_all = open(tmp_all, "w", encoding="utf-8")
    f_canais = open(tmp_canais, "w", encoding="utf-8")
    f_ao_vivo = open(tmp_ao_vivo, "w", encoding="utf-8")
    f_filmes = open(tmp_filmes, "w", encoding="utf-8")
    f_series = open(tmp_series, "w", encoding="utf-8")

    # Cabeçalho padrão M3U Plus
    header = "#EXTM3U\n#EXT-X-SESSION-DATA:DATA-ID=\"com.xui.1_5_5r2\"\n"
    f_all.write(header)
    f_canais.write(header)
    f_ao_vivo.write(header)
    f_filmes.write(header)
    f_series.write(header)

    group_handles: Dict[str, Any] = {}
    grupos_stats = Counter()
    tipo_stats = Counter()
    amostra_canais: List[Dict[str, Any]] = []

    total_itens = 0
    current_extinf = None

    with open(arquivo_origem, "r", encoding="utf-8", errors="ignore") as f_in:
        for line in f_in:
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.startswith("#EXTINF:"):
                current_extinf = line_str
            elif current_extinf and (line_str.startswith("http://") or line_str.startswith("https://")):
                stream_url = line_str
                meta = parse_extinf(current_extinf)
                tipo = classificar_tipo(meta["group_title"], meta["name"], stream_url)

                total_itens += 1
                tipo_stats[tipo] += 1
                grupos_stats[meta["group_title"]] += 1

                bloco = f"{current_extinf}\n{stream_url}\n"

                # 1. Grava no all.m3u
                f_all.write(bloco)

                # 2. Grava no arquivo do tipo correspondente
                if tipo == "canais":
                    f_canais.write(bloco)
                    f_ao_vivo.write(bloco)
                elif tipo == "filmes":
                    f_filmes.write(bloco)
                elif tipo == "series":
                    f_series.write(bloco)

                # 3. Grava no arquivo de grupo específico (apenas canais ao vivo)
                if tipo == "canais":
                    safe_grp = sanitize_filename(meta["group_title"])
                    if safe_grp not in group_handles:
                        grp_path = pasta_grupos / f"{safe_grp}.m3u"
                        gh = open(grp_path, "w", encoding="utf-8")
                        gh.write(f"#EXTM3U\n#EXTINF:0,Grupo: {meta['group_title']}\n")
                        group_handles[safe_grp] = gh
                    group_handles[safe_grp].write(bloco)

                # Amostra para conferência
                if len(amostra_canais) < 60:
                    amostra_canais.append({
                        "name": meta["name"],
                        "group": meta["group_title"],
                        "tipo": tipo,
                        "logo": meta["tvg_logo"],
                        "stream_url": stream_url
                    })

                current_extinf = None

    # Fecha todos os arquivos
    f_all.close()
    f_canais.close()
    f_ao_vivo.close()
    f_filmes.close()
    f_series.close()
    for gh in group_handles.values():
        gh.close()

    # Aplica substituição atômica dos arquivos
    os.replace(tmp_all, path_all)
    os.replace(tmp_canais, path_canais)
    os.replace(tmp_ao_vivo, path_ao_vivo)
    os.replace(tmp_filmes, path_filmes)
    os.replace(tmp_series, path_series)

    # Prepara JSON de Metadados e Estatísticas
    resumo = {
        "status": "success",
        "total_streams": total_itens,
        "totais_por_tipo": {
            "canais_ao_vivo": tipo_stats["canais"],
            "filmes_vod": tipo_stats["filmes"],
            "series": tipo_stats["series"]
        },
        "arquivos_gerados": {
            "all": "all.m3u",
            "canais": "canais.m3u",
            "ao_vivo": "ao_vivo.m3u",
            "filmes": "filmes.m3u",
            "series": "series.m3u"
        },
        "top_grupos": [
            {"group": grp, "count": count, "file": f"grupos/{sanitize_filename(grp)}.m3u"}
            for grp, count in grupos_stats.most_common(40)
        ],
        "amostra": amostra_canais[:20]
    }

    path_meta = pasta_saida / "metadata.json"
    with open(path_meta, "w", encoding="utf-8") as fm:
        json.dump(resumo, fm, indent=2, ensure_ascii=False)

    print(f"[CONCLUÍDO] Descompilação finalizada com sucesso!")
    print(f" - Total de streams: {total_itens}")
    print(f" - Canais de TV ao Vivo: {tipo_stats['canais']}")
    print(f" - Filmes (VOD):         {tipo_stats['filmes']}")
    print(f" - Séries:               {tipo_stats['series']}")
    print(f" - Total de categorias:  {len(grupos_stats)}")
    print(f" - Metadados salvos em:  {path_meta}")
    return resumo


def main():
    parser = argparse.ArgumentParser(description="Descompilador e Hospedador de Listas IPTV M3U")
    parser.add_argument("--url", default=DEFAULT_URL, help="URL M3U da playlist a baixar")
    parser.add_argument("--file", help="Caminho para arquivo M3U local existente")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Diretório para salvar as playlists geradas")
    parser.add_argument("--no-download", action="store_true", help="Pular download se o arquivo já existir")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    m3u_file = Path(args.file) if args.file else out_dir / "raw_download.m3u"

    if not args.file:
        if not args.no_download or not m3u_file.exists():
            sucesso = baixar_playlist(args.url, m3u_file)
            if not sucesso:
                print("[ERRO] Falha ao obter a lista IPTV.")
                sys.exit(1)
        else:
            print(f"[INFO] Usando arquivo em cache: {m3u_file}")

    resumo = decompilar_m3u(m3u_file, out_dir)
    print("\n[OK] Processo 100% finalizado!")


if __name__ == "__main__":
    main()
