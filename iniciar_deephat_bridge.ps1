<#
.SYNOPSIS
    Garante que a Bridge Local OpenAI do DeepHat AI esteja rodando na porta 3095 de forma desacoplada permanente.
#>
param(
    [switch]$ForceRestart
)

$Port = 3095
$PythonExe = "C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT\.venv\Scripts\python.exe"

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

# Inicia desacoplado via Python Popen (DETACHED_PROCESS)
$code = @"
import subprocess, sys
subprocess.Popen(
    [sys.executable, 'openai_api.py'],
    cwd=r'C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT',
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)
"@

& $PythonExe -c $code
Start-Sleep -Seconds 2

try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3
    if ($res.data) {
        Write-Output "[SUCESSO] Bridge DeepHat AI ativa em http://127.0.0.1:$Port/v1"
        exit 0
    }
} catch {
    Write-Output "[AVISO] Bridge iniciando em background..."
}
