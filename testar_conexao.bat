@echo off
chcp 65001 > nul
echo ==============================================================================
echo  DIAGNOSTICO E TESTE DE CONEXAO - MCP DEEPHAT AI
echo ==============================================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    echo Criando ambiente virtual...
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" test_client.py
pause
