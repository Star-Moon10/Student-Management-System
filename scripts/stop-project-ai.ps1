$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidPath = Join-Path $ProjectRoot 'run\ollama.pid'

if (-not (Test-Path $PidPath)) {
    exit 0
}

$pidValue = [int](Get-Content -LiteralPath $PidPath)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $pidValue" -ErrorAction SilentlyContinue
if ($process -and $process.CommandLine -match 'ollama.*serve') {
    & taskkill.exe /PID $pidValue /T /F | Out-Null
}
$runtimePath = [regex]::Escape((Join-Path $ProjectRoot 'tools\ollama'))
Get-CimInstance Win32_Process -Filter "Name = 'llama-server.exe'" | Where-Object { $_.CommandLine -match $runtimePath } | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $PidPath -Force -ErrorAction SilentlyContinue
