<#
.SYNOPSIS
    Inicia a Bridge Local OpenAI do DeepHat AI em segundo plano na porta 3095.
#>
param(
    [switch]$ForceRestart
)

$Port = 3095
$PythonExe = "C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT\.venv\Scripts\python.exe"
$ScriptPy  = "C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT\openai_api.py"

$conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' }
if ($conn -and -not $ForceRestart) {
    Write-Output "[OK] Bridge DeepHat AI ja esta rodando na porta $Port."
    exit 0
}

if ($conn -and $ForceRestart) {
    $conn | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
}

Start-Process -FilePath $PythonExe -ArgumentList $ScriptPy -WorkingDirectory "C:\Users\washingtonpronet\ProjetosDev\MCP-DEEPHAT" -WindowStyle Hidden
Start-Sleep -Seconds 2

try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/v1/models" -TimeoutSec 3
    if ($res.data) {
        Write-Output "[SUCESSO] Bridge DeepHat AI iniciada com sucesso em http://127.0.0.1:$Port/v1"
        exit 0
    }
} catch {
    Write-Output "[AVISO] Iniciando bridge... Aguardando conclusao."
}
