#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M3U Playlist Decompiler, Parser & Hosting Generator
WashingtonProNet - SmartTV Club Multi-Device Ecosystem

Baixa, descompila, categoriza e gera arquivos de playlist M3U e metadados JSON
estruturados para hospedagem local e remota na VPS.
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


def sanitize_filename(name: str) -> str:
    """Converte um nome de categoria para um nome de arquivo seguro."""
    # Remove acentos
    name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
    # Remove caracteres especiais
    name = re.sub(r'[^\w\s-]', '', name).strip().lower()
    name = re.sub(r'[-\s]+', '_', name)
    return name or "outros"


def classificar_tipo(grupo: str, nome: str) -> str:
    """Classifica se o item é Canal ao Vivo, Filme (VOD) ou Série."""
    g_upper = grupo.upper()
    n_upper = nome.upper()
    
    # Séries
    if any(k in g_upper for k in ["SERIE", "SÉRIE", "SERIES", "TEMPORADA", "EPISODIO", "EPISÓDIO"]):
        return "series"
    if re.search(r'\bS\d{2}E\d{2}\b', n_upper) or re.search(r'\bT\d{1,2}\s*E\d{1,2}\b', n_upper):
        return "series"

    # Filmes / VOD
    if any(k in g_upper for k in ["FILME", "FILMES", "VOD", "CINEMA", "4K FILMES", "LANCAMENTOS", "LANÇAMENTOS"]):
        return "filmes"

    # Canais ao vivo
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

    # O nome do canal fica após a última vírgula da linha #EXTINF
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
    """
    print(f"[INFO] Iniciando descompilação de {arquivo_origem}...")
    pasta_saida.mkdir(parents=True, exist_ok=True)
    pasta_grupos = pasta_saida / "grupos"
    pasta_grupos.mkdir(parents=True, exist_ok=True)

    # Handlers para os arquivos de saída principais
    path_all = pasta_saida / "all.m3u"
    path_canais = pasta_saida / "canais.m3u"
    path_filmes = pasta_saida / "filmes.m3u"
    path_series = pasta_saida / "series.m3u"

    f_all = open(path_all, "w", encoding="utf-8")
    f_canais = open(path_canais, "w", encoding="utf-8")
    f_filmes = open(path_filmes, "w", encoding="utf-8")
    f_series = open(path_series, "w", encoding="utf-8")

    # Cabeçalho padrão M3U Plus
    header = "#EXTM3U\n#EXT-X-SESSION-DATA:DATA-ID=\"com.xui.1_5_5r2\"\n"
    f_all.write(header)
    f_canais.write(header)
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
                tipo = classificar_tipo(meta["group_title"], meta["name"])

                # Atualiza contadores
                total_itens += 1
                tipo_stats[tipo] += 1
                grupos_stats[meta["group_title"]] += 1

                # Bloco M3U formatado
                bloco = f"{current_extinf}\n{stream_url}\n"

                # 1. Grava no all.m3u
                f_all.write(bloco)

                # 2. Grava no arquivo do tipo correspondente
                if tipo == "canais":
                    f_canais.write(bloco)
                elif tipo == "filmes":
                    f_filmes.write(bloco)
                elif tipo == "series":
                    f_series.write(bloco)

                # 3. Grava no arquivo de grupo específico (se for canal ao vivo)
                if tipo == "canais":
                    safe_grp = sanitize_filename(meta["group_title"])
                    if safe_grp not in group_handles:
                        grp_path = pasta_grupos / f"{safe_grp}.m3u"
                        gh = open(grp_path, "w", encoding="utf-8")
                        gh.write(f"#EXTM3U\n#EXTINF:0,Grupo: {meta['group_title']}\n")
                        group_handles[safe_grp] = gh
                    group_handles[safe_grp].write(bloco)

                # Coleta amostra inicial para exibição na UI
                if len(amostra_canais) < 50:
                    amostra_canais.append({
                        "name": meta["name"],
                        "group": meta["group_title"],
                        "tipo": tipo,
                        "logo": meta["tvg_logo"],
                        "stream_url": stream_url
                    })

                current_extinf = None

    # Fecha todos os handles
    f_all.close()
    f_canais.close()
    f_filmes.close()
    f_series.close()
    for gh in group_handles.values():
        gh.close()

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
            "filmes": "filmes.m3u",
            "series": "series.m3u"
        },
        "top_grupos": [
            {"group": grp, "count": count, "file": f"grupos/{sanitize_filename(grp)}.m3u"}
            for grp, count in grupos_stats.most_common(40)
        ],
        "amostra": amostra_canais[:20]
    }

    # Salva metadata.json
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
