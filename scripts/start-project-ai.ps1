param([switch]$Quiet)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Runtime = Join-Path $ProjectRoot 'tools\ollama\ollama.exe'
$ModelPath = Join-Path $ProjectRoot 'models\ollama'
$PidPath = Join-Path $ProjectRoot 'run\ollama.pid'

if (-not (Test-Path $Runtime)) {
    if (-not $Quiet) { Write-Error 'Project-local Ollama runtime is not installed. Run scripts\setup-project-ai.ps1 first.' }
    exit 1
}

New-Item -ItemType Directory -Force -Path $ModelPath, (Split-Path -Parent $PidPath) | Out-Null
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
    exit 0
} catch {
}

$env:OLLAMA_MODELS = $ModelPath
$env:CUDA_VISIBLE_DEVICES = '0'
$env:OLLAMA_CONTEXT_LENGTH = '4096'
$process = Start-Process -FilePath $Runtime -ArgumentList 'serve' -WorkingDirectory $ProjectRoot -WindowStyle Hidden -PassThru
Set-Content -Path $PidPath -Value $process.Id -Encoding ascii

for ($attempt = 1; $attempt -le 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 | Out-Null
        if (-not $Quiet) { Write-Output 'Project-local Ollama service is ready on http://127.0.0.1:11434.' }
        exit 0
    } catch {
    }
}

Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
throw 'Ollama did not start. Review the Ollama service logs and try again.'
