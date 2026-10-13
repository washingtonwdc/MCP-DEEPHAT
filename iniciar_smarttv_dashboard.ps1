<#
.SYNOPSIS
    Inicializa o Dashboard Web do SmartTV Club Auto-Sync.
.DESCRIPTION
    Inicia o servidor web na porta 5050 e abre a interface no navegador.
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonVenv = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonVenv)) {
    $PythonVenv = "python"
}

Write-Host "===========================================================" -ForegroundColor Magenta
Write-Host "🌟 Iniciando SmartTV Club Auto-Sync Dashboard" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Magenta

# Checar porta 5050
$PortOccupied = Get-NetTCPConnection -LocalPort 5050 -ErrorAction SilentlyContinue

if ($PortOccupied) {
    Write-Host "[*] O Dashboard já está em execução na porta 5050." -ForegroundColor Yellow
} else {
    Write-Host "[+] Iniciando servidor Web na porta 5050..." -ForegroundColor Green
    Start-Process -FilePath $PythonVenv -ArgumentList "`"$ScriptDir\smarttv_web.py`" --port 5050" -WindowStyle Hidden
    Start-Sleep -Seconds 2
}

Write-Host "[🚀] Abrindo interface no navegador: http://127.0.0.1:5050" -ForegroundColor Cyan
Start-Process "http://127.0.0.1:5050"
