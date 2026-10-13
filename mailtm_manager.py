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


def extrair_links_confirmacao(token: str) -> List[Dict[str, Any]]:
    """
    Lê todas as mensagens da caixa e extrai links com foco em confirmação/ativação.
    """
    mensagens = listar_mensagens(token)
    if not mensagens:
        print("[-] Nenhuma mensagem na caixa de entrada.")
        return []

    resultados = []
    padrao_url = re.compile(r"https?://[^\s\"'<>]+")

    for msg in mensagens:
        msg_id = msg.get("id")
        remetente = msg.get("from", {}).get("address", "")
        assunto = msg.get("subject", "")

        detalhe = obter_detalhes_mensagem(token, msg_id)
        texto_corpo = detalhe.get("text") or ""
        html_corpo = detalhe.get("html") or ""

        # Encontra todas as URLs em texto e html
        urls_encontradas = set(padrao_url.findall(texto_corpo + " " + html_corpo))
        # Filtra URLs irrelevantes (schemas, imagens, unsubscribes básicos se quiser)
        urls_limpas = [u for u in urls_encontradas if not u.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg"))]

        # Prioriza links que contenham palavras-chave de ativação
        links_ativacao = [u for u in urls_limpas if any(k in u.lower() for k in ["confirm", "activat", "verif", "token", "auth", "valida", "clique"])]

        item = {
            "id": msg_id,
            "remetente": remetente,
            "assunto": assunto,
            "data_recebimento": msg.get("createdAt"),
            "links_ativacao": links_ativacao,
            "todos_links": urls_limpas,
            "texto": texto_corpo[:400] + ("..." if len(texto_corpo) > 400 else ""),
        }
        resultados.append(item)

        print("-" * 50)
        print(f"📩 De:      {remetente}")
        print(f"📌 Assunto: {assunto}")
        if links_ativacao:
            print("🔗 Links de Confirmação/Ativação Detectados:")
            for lk in links_ativacao:
                print(f"   -> {lk}")
        elif urls_limpas:
            print("🔗 Links Encontrados no e-mail:")
            for lk in urls_limpas[:3]:
                print(f"   -> {lk}")
        else:
            print("[-] Nenhum link encontrado no corpo desta mensagem.")

    return resultados


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
