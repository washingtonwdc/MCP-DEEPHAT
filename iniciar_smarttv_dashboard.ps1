<#
.SYNOPSIS
    Inicializa o Dashboard Web do SmartTV Club Auto-Sync.
.DESCRIPTION
    Inicia o servidor web na porta 5050 e abre a interface no navegador.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonVenv = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonVenv)) {
    $PythonVenv = "python"
}

Write-Host "===========================================================" -ForegroundColor Magenta
Write-Host "[INFO] Iniciando SmartTV Club Auto-Sync Dashboard" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Magenta

# Checar porta 5050
$PortOccupied = Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue

if ($PortOccupied) {
    Write-Host "[INFO] O Dashboard ja esta em execucao na porta 5050." -ForegroundColor Yellow
} else {
    Write-Host "[INFO] Iniciando servidor Web desacoplado permanente na porta 5050..." -ForegroundColor Green
    $code = @"
import subprocess, sys
log_path = r'$ScriptDir\smarttv_dashboard.log'
log_file = open(log_path, 'a', encoding='utf-8')
subprocess.Popen(
    [sys.executable, 'smarttv_web.py', '--port', '5050'],
    cwd=r'$ScriptDir',
    stdout=log_file,
    stderr=log_file,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)
"@
    & $PythonVenv -c $code
    Start-Sleep -Seconds 3
}

# Validar resposta
try {
    $res = Invoke-WebRequest -Uri "http://127.0.0.1:5050/" -UseBasicParsing -TimeoutSec 5
    if ($res.StatusCode -eq 200) {
        Write-Host "[OK] Servidor ativo e respondendo na porta 5050!" -ForegroundColor Green
    }
} catch {
    Write-Host "[AVISO] Aguardando servidor finalizar inicializacao..." -ForegroundColor Yellow
}

Write-Host "[OK] Abrindo interface no navegador: http://127.0.0.1:5050" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5050"
