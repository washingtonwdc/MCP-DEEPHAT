<#
.SYNOPSIS
    Garante que a Bridge Local OpenAI do DeepHat AI esteja rodando na porta 3095 de forma desacoplada permanente.
#>
param(
    [switch]$ForceRestart
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::InputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$Port = 3095
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }

if ($conn -and $ForceRestart) {
    $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
    $conn = $null
}

if ($conn) {
    Write-Output "[OK] Bridge DeepHat AI ja esta ativa na porta $Port."
    exit 0
}

# Inicia desacoplado via Python Popen com redirecionamento de logs
$code = @"
import subprocess, sys
log_path = r'$ScriptDir\deephat_bridge.log'
log_file = open(log_path, 'a', encoding='utf-8')
subprocess.Popen(
    [sys.executable, 'openai_api.py'],
    cwd=r'$ScriptDir',
    stdout=log_file,
    stderr=log_file,
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)
"@

& $PythonExe -c $code
Start-Sleep -Seconds 3

try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 5
    if ($res.data) {
        Write-Output "[SUCESSO] Bridge DeepHat AI ativa em http://127.0.0.1:$Port/v1"
        exit 0
    }
} catch {
    Write-Output "[AVISO] Bridge iniciando em background..."
}
