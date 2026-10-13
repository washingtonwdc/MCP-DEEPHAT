"""
Script de Teste de Validação e Deduplicação de Cadastros (QA & DevSecOps).
Testa como o endpoint lida com normalização de e-mails (aliases, pontos, case-folding)
e telefones (máscaras, DDI/DDD, formatações) para auditar regras de duplicidade.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# Garante suporte adequado a UTF-8 em terminais Windows/CP1252
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx


def carregar_emails_arquivo(caminho_arquivo: str) -> List[str]:
    """Carrega uma lista de e-mails a partir de um arquivo de texto (.txt ou .csv)."""
    p = Path(caminho_arquivo)
    if not p.exists():
        print(f"[!] Arquivo não encontrado: {caminho_arquivo}")
        return []

    emails = []
    with open(p, "r", encoding="utf-8") as f:
        for linha in f:
            e = linha.strip()
            if e and "@" in e and not e.startswith("#"):
                emails.append(e)
    return emails


def gerar_variacoes_email(email_base: str, emails_custom: List[str] = None) -> List[Dict[str, str]]:
    """Gera variações técnicas comuns de e-mail ou utiliza lista personalizada."""
    if emails_custom and len(emails_custom) > 0:
        return [
            {
                "tipo": "custom_dot_trick" if "." in e.split("@")[0] else "custom_lista",
                "email": e,
                "descricao": f"E-mail customizado #{idx+1}"
            }
            for idx, e in enumerate(emails_custom)
        ]

    if "@" not in email_base:
        return [{"tipo": "original", "email": email_base, "descricao": "E-mail inválido/bruto"}]

    usuario, dominio = email_base.split("@", 1)
    variacoes = [
        {"tipo": "original", "email": email_base, "descricao": "E-mail original de base"},
        {"tipo": "alias_plus", "email": f"{usuario}+teste@{dominio}", "descricao": "Alias com sufixo +tag"},
        {"tipo": "alias_plus_numero", "email": f"{usuario}+123@{dominio}", "descricao": "Alias com sufixo +numérico"},
        {"tipo": "maiusculas", "email": f"{usuario.upper()}@{dominio}", "descricao": "Local-part todo em maiúsculas"},
        {"tipo": "capitalizado", "email": f"{usuario.capitalize()}@{dominio}", "descricao": "Primeira letra maiúscula"},
    ]

    # Variação com ponto intercalado no local-part (ex: u.suario@domain)
    if len(usuario) > 2 and "." not in usuario:
        ponto_email = f"{usuario[:2]}.{usuario[2:]}@{dominio}"
        variacoes.append({"tipo": "ponto_inserido", "email": ponto_email, "descricao": "Ponto adicionado no meio do local-part"})

    return variacoes


def gerar_variacoes_telefone(telefone_base: str) -> List[Dict[str, str]]:
    """Gera variações de formatação de telefone para testar higienização."""
    # Extrai apenas dígitos
    digitos = "".join(c for c in telefone_base if c.isdigit())
    
    variacoes = [
        {"tipo": "apenas_digitos", "telefone": digitos, "descricao": "Apenas números sem máscara"},
    ]

    # Formatação padrão brasileira se tiver 10 ou 11 dígitos
    if len(digitos) == 11:
        ddd, d9, rest = digitos[:2], digitos[2], digitos[3:]
        variacoes.extend([
            {"tipo": "mascara_padrao", "telefone": f"({ddd}) {d9}{rest[:4]}-{rest[4:]}", "descricao": "Formato (XX) 9XXXX-XXXX"},
            {"tipo": "com_espacos", "telefone": f"{ddd} {d9} {rest[:4]} {rest[4:]}", "descricao": "Separado por espaços"},
            {"tipo": "com_tracos", "telefone": f"{ddd}-{d9}{rest[:4]}-{rest[4:]}", "descricao": "Separado por traços"},
            {"tipo": "formato_e164", "telefone": f"+55{digitos}", "descricao": "Padrão internacional E.164 (+55...)"},
        ])
    elif len(digitos) == 10:
        ddd, prefixo, sufixo = digitos[:2], digitos[2:6], digitos[6:]
        variacoes.extend([
            {"tipo": "mascara_fixo", "telefone": f"({ddd}) {prefixo}-{sufixo}", "descricao": "Formato fixo (XX) XXXX-XXXX"},
            {"tipo": "formato_e164", "telefone": f"+55{digitos}", "descricao": "Padrão internacional E.164 (+55...)"},
        ])

    return variacoes


def executar_testes(
    url_endpoint: str,
    email_base: str,
    telefone_base: str,
    nome_base: str = "Teste QA",
    delay_segundos: float = 1.0,
    dry_run: bool = False,
    headers_custom: Dict[str, str] = None,
    emails_custom: List[str] = None,
    single_phone: bool = False,
    max_emails: int = 0,
) -> List[Dict[str, Any]]:
    """Executa a bateria de testes de submissão e mapeia status de duplicidade."""
    resultados = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QA-Audit/1.0",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }
    if headers_custom:
        headers.update(headers_custom)

    if emails_custom and max_emails > 0:
        emails_custom = emails_custom[:max_emails]

    variacoes_email = gerar_variacoes_email(email_base, emails_custom=emails_custom)

    if single_phone:
        variacoes_tel = [{"tipo": "telefone_unico", "telefone": telefone_base, "descricao": "Telefone fixo/único"}]
    else:
        variacoes_tel = gerar_variacoes_telefone(telefone_base)

    print(f"\n[*] Iniciando Bateria de Testes de Normalizacao & Deduplicacao")
    print(f"Target Endpoint: {url_endpoint}")
    print(f"Total Variacoes de E-mail: {len(variacoes_email)} | Telefone: {len(variacoes_tel)} (Total requisições: {len(variacoes_email) * len(variacoes_tel)})")
    print(f"Modo: {'[DRY RUN - Apenas Simulacao]' if dry_run else '[LIVE - Requisicoes Ativas]'}\n")

    idx = 1
    with httpx.Client(timeout=15.0, follow_redirects=True) as http:
        for var_email in variacoes_email:
            for var_tel in variacoes_tel:
                payload = {
                    "name": nome_base,
                    "email": var_email["email"],
                    "phone": var_tel["telefone"],
                    "terms": True,
                    "privacy": True,
                }

                registro = {
                    "indice": idx,
                    "timestamp": datetime.now().isoformat(),
                    "email_tipo": var_email["tipo"],
                    "email_enviado": var_email["email"],
                    "tel_tipo": var_tel["tipo"],
                    "tel_enviado": var_tel["telefone"],
                    "status_code": None,
                    "tempo_ms": 0,
                    "resposta_resumo": "",
                    "deduplicado": False,
                }

                print(f"[{idx:02d}] Testando: {var_email['email']} | {var_tel['telefone']} ... ", end="", flush=True)

                if dry_run:
                    print("SIMULADO (dry-run)")
                    registro["status_code"] = 200
                    registro["resposta_resumo"] = "Simulação sem envio de rede"
                else:
                    inicio = time.time()
                    try:
                        resp = http.post(url_endpoint, json=payload, headers=headers)
                        duracao = int((time.time() - inicio) * 1000)
                        registro["status_code"] = resp.status_code
                        registro["tempo_ms"] = duracao
                        registro["resposta_resumo"] = resp.text[:150].strip().replace("\n", " ")

                        # Se retornar 409 Conflict ou mensagem de duplicidade
                        if resp.status_code == 409 or "duplicate" in resp.text.lower() or "já cadastrado" in resp.text.lower():
                            registro["deduplicado"] = True
                            print(f"HTTP {resp.status_code} [DEDUPLICADO/BLOQUEADO] ({duracao}ms)")
                        elif resp.status_code in [200, 201]:
                            print(f"HTTP {resp.status_code} [CRIADO/ACEITO] ({duracao}ms)")
                        else:
                            print(f"HTTP {resp.status_code} ({duracao}ms)")

                    except Exception as e:
                        registro["resposta_resumo"] = f"Erro de conexão: {str(e)}"
                        print(f"FALHA ({e})")

                    if delay_segundos > 0:
                        time.sleep(delay_segundos)

                resultados.append(registro)
                idx += 1

    return resultados


def salvar_relatorios(resultados: List[Dict[str, Any]], prefixo_arquivo: str = "relatorio_deduplicacao"):
    """Salva os resultados em CSV e JSON estruturados."""
    data_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"{prefixo_arquivo}_{data_str}.csv"
    json_file = f"{prefixo_arquivo}_{data_str}.json"

    # Salva CSV
    if resultados:
        campos = list(resultados[0].keys())
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(resultados)

    # Salva JSON
    with open(json_file, mode="w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

    print(f"\n[+] Relatorios gerados:")
    print(f"  - CSV:  {csv_file}")
    print(f"  - JSON: {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Automação de Testes de Normalização e Deduplicação de Cadastros")
    parser.add_argument("--url", default="https://httpbin.org/post", help="URL do endpoint POST de submissão do formulário (default: https://httpbin.org/post)")
    parser.add_argument("--email", default="qa.tester@gmail.com", help="E-mail base de teste (default: qa.tester@gmail.com)")
    parser.add_argument("--emails-file", default="emails_alvo.txt" if Path("emails_alvo.txt").exists() else None, help="Arquivo de texto com lista de e-mails customizados (ex: emails_alvo.txt)")
    parser.add_argument("--phone", default="11987654321", help="Telefone base de teste (default: 11987654321)")
    parser.add_argument("--name", default="Teste QA DevSecOps", help="Nome do usuário no payload")
    parser.add_argument("--delay", type=float, default=1.0, help="Intervalo em segundos entre envios (default: 1.0s)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas exibe os payloads gerados sem fazer requisições")
    parser.add_argument("--all-phones", action="store_true", help="Se ativado, testa todas as 5 variações de telefone para cada e-mail (matriz completa)")
    parser.add_argument("--max-emails", type=int, default=0, help="Limita o número máximo de e-mails testados (0 = sem limite)")

    parser.add_argument("--use-mailtm", action="store_true", help="Gera uma caixa temporária no Mail.tm e aguarda o link de confirmação após o envio")

    args = parser.parse_args()

    emails_custom = None
    mailtm_token = None

    if args.use_mailtm:
        try:
            import mailtm_manager
            email_tm, _, token_tm = mailtm_manager.obter_ou_criar_email_do_dia()
            emails_custom = [email_tm]
            mailtm_token = token_tm
            print(f"[+] Modo Mail.tm Ativo: usando caixa descartável {email_tm}")
        except Exception as e:
            print(f"[!] Falha ao inicializar Mail.tm: {e}")

    elif args.emails_file and Path(args.emails_file).exists():
        emails_custom = carregar_emails_arquivo(args.emails_file)
        print(f"[+] Carregados {len(emails_custom)} e-mails do arquivo: {args.emails_file}")

    # Por padrão, se estiver usando lista customizada de e-mails, usamos 1 telefone fixo para não explodir em 5x requisições
    single_phone = not args.all_phones if emails_custom else False

    resultados = executar_testes(
        url_endpoint=args.url,
        email_base=args.email,
        telefone_base=args.phone,
        nome_base=args.name,
        delay_segundos=args.delay,
        dry_run=args.dry_run,
        emails_custom=emails_custom,
        single_phone=single_phone,
        max_emails=args.max_emails,
    )

    salvar_relatorios(resultados)

    # Se usou Mail.tm e não foi dry-run, aguarda a chegada do e-mail de ativação
    if args.use_mailtm and not args.dry_run and mailtm_token:
        print("\n[📩] Aguardando e-mail de confirmação no Mail.tm...")
        import mailtm_manager
        mailtm_manager.monitorar_caixa(mailtm_token, timeout_segundos=60)


if __name__ == "__main__":
    main()
