# 🛡️ MCP DeepHat AI (`app.deephat.ai`)

Servidor **Model Context Protocol (MCP)** para integração direta e sem censura com o **DeepHat AI** (anteriormente *WhiteRabbitNeo*, desenvolvido pela *Kindo*), especializado em **cibersegurança ofensiva, Red Teaming, análise de vulnerabilidades e DevSecOps**.

Este MCP permite conectar assistentes de IA (Google Antigravity, Claude Desktop, Cursor, OpenClaw, Roo Code) diretamente à sua sessão web em **https://app.deephat.ai/** com suporte híbrido a fallback via API Kindo.

---

## 🚀 Funcionalidades

- **Conexão Direta com a Web (app.deephat.ai):** Utiliza a sua sessão autenticada da web para consultar o modelo sem limites arbitrários ou recusas de segurança em análises legítimas.
- **Roteamento Híbrido Inteligente:** Prioriza a conexão direta via sessão web e, caso ocorra alguma oscilação ou expiração, pode alternar para a API Kindo caso configurada.
- **Ferramentas Especializadas de Red Teaming:**
  - `deephat_chat`: Diálogo técnico direto com o modelo DeepHat sem bloqueios para cenários de pentest, exploits de laboratório e segurança da informação.
  - `deephat_security_audit`: Auditoria estática e dinâmica de código, infraestrutura, scripts ou payloads com emissão de PoC e mitigação.
  - `deephat_test_connection`: Diagnóstico em tempo real da sessão web, tokens e status de conectividade.
  - `deephat_get_status`: Metadados técnicos do servidor e parâmetros operacionais.

---

## 📋 Pré-requisitos

- Windows 10/11
- Python 3.12 ou 3.13 (já instalado e configurado no ambiente)
- Conta criada no site oficial: [https://app.deephat.ai/](https://app.deephat.ai/)

---

## 🔑 Passo a Passo: Como Obter o Cookie de Conexão Direta

Para conectar diretamente com o site `https://app.deephat.ai/`:

1. Abra seu navegador (Google Chrome, Microsoft Edge, Brave, etc.) e acerte o login em [https://app.deephat.ai/](https://app.deephat.ai/) com sua conta Google ou GitHub.
2. Abra as Ferramentas de Desenvolvedor pressionando **`F12`** (ou `Ctrl + Shift + I`).
3. Vá para a aba **Application** (ou **Aplicativo**) na barra superior.
4. No menu lateral esquerdo, expanda **Storage** -> **Cookies** -> clique em `https://app.deephat.ai`.
5. Localize o cookie chamado:
   - `__Secure-next-auth.session-token` (ou `next-auth.session-token`).
6. Copie o valor do cookie.
7. Crie seu arquivo `.env` na raiz do projeto (ou copie de `.env.example`):
   ```bash
   copy .env.example .env
   ```
8. Cole o valor do token na variável `DEEPHAT_SESSION_TOKEN`:
   ```env
   DEEPHAT_SESSION_TOKEN=eyJhbGciOiJkaXIiLCJlbmMi...
   ```
   *(Alternativamente, você pode copiar o cabeçalho `Cookie` completo de qualquer requisição na aba Network e colar em `DEEPHAT_COOKIE`)*.

---

## 🧪 Testando a Conexão

Basta dar um duplo clique no script:
```cmd
testar_conexao.bat
```
Ou executar pelo terminal:
```powershell
.\.venv\Scripts\python.exe test_client.py
```

O script testará o endpoint de sessão do `app.deephat.ai`, exibirá o usuário autenticado e fará uma inferência de teste com o modelo.

---

## 🛠️ Configuração nos Clientes MCP

### 1. Antigravity / Claude Desktop (`claude_desktop_config.json` ou `mcp_config.json`)
Adicione o servidor na chave `mcpServers`:

```json
{
  "mcpServers": {
    "deephat": {
      "command": "C:\\Users\\washingtonpronet\\ProjetosDev\\MCP-DEEPHAT\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\washingtonpronet\\ProjetosDev\\MCP-DEEPHAT\\server.py"
      ],
      "env": {
        "DEEPHAT_SESSION_TOKEN": "SEU_TOKEN_AQUI",
        "CONNECTION_MODE": "auto"
      }
    }
  }
}
```

### 2. Cursor IDE
No Cursor, acesse **Settings -> Features -> MCP -> Add New MCP Server**:
- **Name:** `DeepHat-AI`
- **Type:** `command`
- **Command:** `C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT\.venv\Scripts\python.exe C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT\server.py`

### 3. OpenClaw
No arquivo `openclaw.json` ou nas configurações de MCP:
```json
{
  "name": "deephat",
  "command": "C:\\Users\\washingtonpronet\\ProjetosDev\\MCP-DEEPHAT\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\washingtonpronet\\ProjetosDev\\MCP-DEEPHAT\\server.py"]
}
```

---

## 📁 Estrutura do Projeto

```
MCP-DEEPHAT/
├── .env.example             # Modelo das variáveis de ambiente e instruções
├── .gitignore               # Proteção contra vazamento de cookies e credenciais
├── client.py                # Cliente HTTP assíncrono com parser de stream
├── config.py                # Carregamento e validação de configurações
├── iniciar_mcp.bat          # Executável do servidor MCP via stdio
├── mcp_config.example.json  # Exemplo de configuração para clientes MCP
├── README.md                # Esta documentação
├── requirements.txt         # Dependências Python (mcp, httpx, pydantic, rich)
├── server.py                # Servidor FastMCP com as ferramentas expostas
└── test_client.py           # Script interativo de teste e diagnóstico
```

---

## ⚖️ Aviso Legal e Ética

O DeepHat AI é um modelo sem censura voltado exclusivamente para profissionais de cibersegurança, pesquisadores, equipes de Blue/Red Team e estudantes autorizados em ambientes controlados de laboratório. O uso indevido contra alvos não autorizados é estritamente proibido pela legislação vigente.
