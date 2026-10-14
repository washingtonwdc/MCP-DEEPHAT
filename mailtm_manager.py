"""
Gerenciador de E-mails Temporários via Mail.tm API.
Cria caixas postais sob demanda, autentica via JWT, lista mensagens
e extrai links de confirmação e ativação automaticamente.
Documentação: https://docs.mail.tm/
"""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import secrets
import sys
import time
from typing import Dict, Any, List, Optional, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_EMAILS = BASE_DIR / "emails.json"
API_URL = "https://api.mail.tm"


def carregar_dados() -> Dict[str, Any]:
    """Carrega dados salvos em emails.json."""
    if ARQUIVO_EMAILS.exists():
        try:
            return json.loads(ARQUIVO_EMAILS.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def salvar_dados(dados: Dict[str, Any]):
    """Salva dados em emails.json."""
    ARQUIVO_EMAILS.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def obter_dominios_disponiveis() -> List[str]:
    """Consulta domínios públicos ativos na API do Mail.tm."""
    try:
        resp = requests.get(f"{API_URL}/domains", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        membros = data.get("hydra:member", [])
        return [m["domain"] for m in membros if m.get("isActive", True)]
    except Exception as e:
        print(f"[!] Erro ao obter domínios do Mail.tm: {e}")
        return []


def autenticar_token(endereco: str, senha: str) -> Optional[str]:
    """Obtém ou renova um token JWT para um e-mail e senha existentes."""
    try:
        resp = requests.post(
            f"{API_URL}/token",
            json={"address": endereco, "password": senha},
            timeout=10.0,
        )
        if resp.status_code == 200:
            return resp.json().get("token")
    except Exception as e:
        print(f"[!] Erro ao autenticar token para {endereco}: {e}")
    return None


def criar_email(usuario_custom: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Cria uma nova caixa de e-mail temporária no Mail.tm.
    Retorna (endereco, senha, token).
    """
    dominios = obter_dominios_disponiveis()
    if not dominios:
        raise RuntimeError("Nenhum domínio disponível no Mail.tm no momento.")

    dominio = dominios[0]

    # Gera usuário legível baseado na data e sufixo aleatório
    if usuario_custom:
        usuario = usuario_custom.strip().lower()
    else:
        hoje = date.today().strftime("%Y-%m-%d")
        sufixo = secrets.token_hex(3)
        usuario = f"teste-{hoje}-{sufixo}"

    endereco = f"{usuario}@{dominio}"
    senha = secrets.token_urlsafe(16)

    # 1. Cria a conta
    resp_account = requests.post(
        f"{API_URL}/accounts",
        json={"address": endereco, "password": senha},
        timeout=10.0,
    )
    if resp_account.status_code not in [200, 201]:
        raise RuntimeError(f"Falha ao criar conta ({resp_account.status_code}): {resp_account.text}")

    # 2. Obtém token JWT
    resp_token = requests.post(
        f"{API_URL}/token",
        json={"address": endereco, "password": senha},
        timeout=10.0,
    )
    if resp_token.status_code != 200:
        raise RuntimeError(f"Falha ao autenticar token ({resp_token.status_code}): {resp_token.text}")

    token = resp_token.json().get("token")

    # 3. Salva no arquivo local
    dados = carregar_dados()
    chave_data = str(date.today())
    if "contas" not in dados:
        dados["contas"] = []

    registro = {
        "data": chave_data,
        "criado_em": datetime.now().isoformat(),
        "email": endereco,
        "senha": senha,
        "token": token,
    }

    # Salva na lista e como conta do dia
    dados[chave_data] = registro
    dados["contas"].append(registro)
    salvar_dados(dados)

    print(f"[+] E-mail temporário criado com sucesso: {endereco}")
    return endereco, senha, token


def obter_ou_criar_email_do_dia() -> Tuple[str, str, str]:
    """Recupera o e-mail criado hoje ou cria um novo caso ainda não exista."""
    hoje = str(date.today())
    dados = carregar_dados()

    if hoje in dados and "email" in dados[hoje] and "token" in dados[hoje]:
        reg = dados[hoje]
        print(f"[*] Reutilizando e-mail de hoje: {reg['email']}")
        return reg["email"], reg["senha"], reg["token"]

    return criar_email()


def listar_mensagens(token: str) -> List[Dict[str, Any]]:
    """Consulta todas as mensagens recebidas na caixa postal."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{API_URL}/messages", headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("hydra:member", [])
    except Exception as e:
        print(f"[!] Erro ao listar mensagens: {e}")
        return []


def obter_detalhes_mensagem(token: str, msg_id: str) -> Dict[str, Any]:
    """Obtém o conteúdo completo (texto e HTML) de uma mensagem específica."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{API_URL}/messages/{msg_id}", headers=headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[!] Erro ao buscar mensagem {msg_id}: {e}")
        return {}


def analisar_mensagem_para_playlist(detalhe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analisa os detalhes de um e-mail para extrair URLs de playlist M3U/M3U8,
    credenciais Xtream Codes (Host + User + Pass), links de ativação e anexos.
    """
    texto_corpo = detalhe.get("text") or ""
    html_corpo = detalhe.get("html") or ""
    corpo_combinado = f"{texto_corpo}\n{html_corpo}"

    padrao_url = re.compile(r"https?://[^\s\"'<>]+")
    urls_encontradas = set(padrao_url.findall(corpo_combinado))
    urls_limpas = [u for u in urls_encontradas if not u.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"))]

    playlists_detectadas = []

    # 1. Busca URLs com extensões ou rotas clássicas de M3U / IPTV
    for u in urls_limpas:
        u_lower = u.lower()
        if any(p in u_lower for p in [".m3u8", ".m3u", "get.php", "type=m3u", "output=ts", "output=m3u8", "/live/", "/playlist", "channels.m3u"]):
            playlists_detectadas.append(u)

    # 2. Busca credenciais Xtream Codes no texto do e-mail (Host, User, Senha)
    host_match = re.search(r"(?:servidor|server|host|url|dns)[:=\s]+(https?://[^\s/:]+(?::\d+)?)", corpo_combinado, re.I)
    user_match = re.search(r"(?:usu[aá]rio|user|username|login)[:=\s]+([a-zA-Z0-9_\-\.]+)", corpo_combinado, re.I)
    pass_match = re.search(r"(?:senha|pass|password)[:=\s]+([a-zA-Z0-9_\-\.]+)", corpo_combinado, re.I)

    xtream_info = None
    if host_match and user_match and pass_match:
        host = host_match.group(1).rstrip("/")
        user = user_match.group(1).strip()
        pwd = pass_match.group(1).strip()
        m3u_sintetizado = f"{host}/get.php?username={user}&password={pwd}&type=m3u_plus&output=ts"
        playlists_detectadas.append(m3u_sintetizado)
        xtream_info = {"host": host, "username": user, "password": pwd, "m3u_url": m3u_sintetizado}

    # 3. Anexos M3U
    anexos = detalhe.get("attachments") or []
    for att in anexos:
        fn = att.get("filename", "").lower()
        if fn.endswith((".m3u", ".m3u8")):
            download_url = f"https://api.mail.tm{att.get('downloadUrl')}"
            playlists_detectadas.append(download_url)

    # 4. Links de ativação / confirmação
    links_ativacao = [u for u in urls_limpas if any(k in u.lower() for k in ["confirm", "activat", "verif", "token", "auth", "valida", "clique", "ativar"])]

    return {
        "playlists_detectadas": list(dict.fromkeys(playlists_detectadas)),
        "xtream_info": xtream_info,
        "links_ativacao": links_ativacao,
        "todos_links": urls_limpas,
        "texto": texto_corpo[:400] + ("..." if len(texto_corpo) > 400 else "")
    }


def extrair_links_confirmacao(token: str) -> List[Dict[str, Any]]:
    """
    Lê todas as mensagens da caixa e extrai links com foco em confirmação, ativação e playlists IPTV.
    """
    mensagens = listar_mensagens(token)
    if not mensagens:
        return []

    resultados = []

    for msg in mensagens:
        msg_id = msg.get("id")
        remetente = msg.get("from", {}).get("address", "")
        assunto = msg.get("subject", "")

        detalhe = obter_detalhes_mensagem(token, msg_id)
        analise = analisar_mensagem_para_playlist(detalhe)

        item = {
            "id": msg_id,
            "remetente": remetente,
            "assunto": assunto,
            "data_recebimento": msg.get("createdAt"),
            "playlists_detectadas": analise["playlists_detectadas"],
            "xtream_info": analise["xtream_info"],
            "links_ativacao": analise["links_ativacao"],
            "todos_links": analise["todos_links"],
            "texto": analise["texto"],
        }
        resultados.append(item)

        print("-" * 50)
        print(f"[INFO] De:      {remetente}")
        print(f"[INFO] Assunto: {assunto}")
        if analise["playlists_detectadas"]:
            print("[INFO] Playlist IPTV Detectada:")
            for pl in analise["playlists_detectadas"]:
                print(f"   -> {pl}")
        if analise["links_ativacao"]:
            print("[INFO] Links de Confirmacao/Ativacao Detectados:")
            for lk in analise["links_ativacao"]:
                print(f"   -> {lk}")

    return resultados


def buscar_playlist_em_todas_as_contas() -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Varre todas as contas registradas em emails.json em busca de e-mails contendo playlists IPTV.
    Retorna (email_encontrado, playlist_url, detalhes_item).
    """
    dados = carregar_dados()
    contas = dados.get("contas", [])
    for conta in reversed(contas):
        token = conta.get("token")
        if not token and conta.get("senha"):
            token = autenticar_token(conta["email"], conta["senha"])
            if token:
                conta["token"] = token
                salvar_dados(dados)
        if not token:
            continue

        msgs = extrair_links_confirmacao(token)
        for m in msgs:
            pls = m.get("playlists_detectadas", [])
            if pls:
                return conta["email"], pls[0], m

    return None, None, None


def monitorar_caixa(token: str, timeout_segundos: int = 120, intervalo_segundos: int = 5) -> Optional[Dict[str, Any]]:
    """
    Monitora a caixa em tempo real aguardando a chegada de novos e-mails.
    Útil após submeter formulários de cadastro.
    """
    print(f"\n[*] ⏱️ Monitorando caixa de entrada (Timeout: {timeout_segundos}s)...")
    inicio = time.time()
    mensagens_iniciais = len(listar_mensagens(token))

    while (time.time() - inicio) < timeout_segundos:
        tempo_restante = int(timeout_segundos - (time.time() - inicio))
        print(f"\rAguardando e-mail... ({tempo_restante}s restantes)", end="", flush=True)

        msgs = listar_mensagens(token)
        if len(msgs) > mensagens_iniciais:
            print(f"\n[🎉] Novo e-mail recebido! Total: {len(msgs)}")
            nova_msg = msgs[0]
            detalhes = obter_detalhes_mensagem(token, nova_msg["id"])
            links = extrair_links_confirmacao(token)
            return {"mensagem": detalhes, "links": links}

        time.sleep(intervalo_segundos)

    print("\n[-] Timeout atingido sem novos e-mails.")
    return None


def main():
    parser = argparse.ArgumentParser(description="Mail.tm - Gerenciador de E-mails Temporários e Links de Ativação")
    parser.add_argument("--criar", action="store_true", help="Força a criação de um novo e-mail temporário")
    parser.add_argument("--ler", action="store_true", help="Lê mensagens da conta de hoje")
    parser.add_argument("--links", action="store_true", help="Lê mensagens e extrai todos os links de confirmação")
    parser.add_argument("--watch", action="store_true", help="Monitora a caixa em tempo real aguardando novos e-mails")
    parser.add_argument("--timeout", type=int, default=120, help="Tempo limite em segundos para o modo --watch (default: 120s)")

    args = parser.parse_args()

    # Se nenhum argumento for passado, usa fluxo diário padrão
    if not (args.criar or args.ler or args.links or args.watch):
        endereco, senha, token = obter_ou_criar_email_do_dia()
        print(f"\nCaixa de E-mail: {endereco}")
        extrair_links_confirmacao(token)
        return

    if args.criar:
        endereco, senha, token = criar_email()
        print(f"\n[+] Conta Criada:")
        print(f"  E-mail: {endereco}")
        print(f"  Senha:  {senha}")
        return

    # Para ler ou monitorar, precisa do token da conta
    endereco, senha, token = obter_ou_criar_email_do_dia()

    if args.watch:
        monitorar_caixa(token, timeout_segundos=args.timeout)
    elif args.links or args.ler:
        extrair_links_confirmacao(token)


if __name__ == "__main__":
    main()
