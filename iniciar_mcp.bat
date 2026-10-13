@echo off
chcp 65001 > nul
echo ==============================================================================
echo  INICIANDO SERVIDOR MCP DEEPHAT AI (STDIO)
echo ==============================================================================
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Ambiente virtual .venv nao encontrado!
    echo Criando ambiente virtual e instalando dependencias...
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo [OK] Servidor MCP DeepHat iniciando...
".venv\Scripts\python.exe" server.py
