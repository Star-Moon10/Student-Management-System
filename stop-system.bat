@echo off
setlocal
cd /d "%~dp0"

if not exist "run\server.pid" (
  echo No managed server process was found.
  pause
  exit /b 0
)

set /p PID=<"run\server.pid"
set SMS_PID=%PID%
powershell -NoProfile -Command "$process = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $env:SMS_PID); if (-not $process -or $process.CommandLine -notmatch 'uvicorn app.main:app') { exit 2 }"
if errorlevel 2 (
  echo The saved process is no longer the student management server.
  del /q "run\server.pid" >nul 2>&1
  pause
  exit /b 0
)

taskkill /PID %PID% /T /F >nul 2>&1
del /q "run\server.pid" >nul 2>&1
if exist "run\ollama.pid" powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\stop-project-ai.ps1"
echo Student management system server stopped.
timeout /t 2 /nobreak >nul
exit /b 0
