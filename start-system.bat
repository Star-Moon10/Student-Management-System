@echo off
setlocal
cd /d "%~dp0"

if exist "run\server.pid" (
  powershell -NoProfile -Command "$serverProcessId = Get-Content 'run\server.pid'; $process = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $serverProcessId); if ($process -and $process.CommandLine -match 'uvicorn app.main:app') { exit 2 }; exit 0"
  if errorlevel 2 (
    echo The student management system is already running.
    start "" "http://127.0.0.1:8100"
    exit /b 0
  )
  del /q "run\server.pid" >nul 2>&1
)

powershell -NoProfile -Command "$connection = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $connection) { exit 0 }; $process = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $connection.OwningProcess); if ($process -and $process.CommandLine -match 'uvicorn app.main:app') { if (-not (Test-Path 'run')) { New-Item -ItemType Directory 'run' | Out-Null }; Set-Content -Path 'run\server.pid' -Value $connection.OwningProcess -Encoding ascii; exit 2 }; exit 3"
if errorlevel 3 (
  echo Port 8100 is in use by another application.
  pause
  exit /b 1
)
if errorlevel 2 (
  echo The student management system is already running.
  start "" "http://127.0.0.1:8100"
  exit /b 0
)

set "PROJECT_PYTHON=python"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import fastapi, uvicorn, sqlalchemy, openpyxl, docx" >nul 2>&1
  if not errorlevel 1 set "PROJECT_PYTHON=%CD%\.venv\Scripts\python.exe"
)

"%PROJECT_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.12 or add it to PATH.
  timeout /t 8 /nobreak >nul
  exit /b 1
)

"%PROJECT_PYTHON%" -c "import fastapi, uvicorn, sqlalchemy, openpyxl, docx" >nul 2>&1
if errorlevel 1 (
  echo Project dependencies are missing. Run setup.bat first.
  timeout /t 8 /nobreak >nul
  exit /b 1
)

if not exist "run" mkdir "run"
if exist "tools\ollama\ollama.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\start-project-ai.ps1" -Quiet
)
start "Student Management System Server" /D "%CD%" "%PROJECT_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8100 --log-config "app\uvicorn_logging.json"
powershell -NoProfile -Command "$connection = $null; 1..20 | ForEach-Object { $connection = Get-NetTCPConnection -LocalPort 8100 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if ($connection) { return }; Start-Sleep -Milliseconds 500 }; if ($connection) { Set-Content -Path 'run\server.pid' -Value $connection.OwningProcess -Encoding ascii; exit 0 }; exit 1"
if errorlevel 1 (
  echo The server did not start. Check the server window for errors.
  timeout /t 8 /nobreak >nul
  exit /b 1
)

if not "%SMS_NO_BROWSER%"=="1" start "" "http://127.0.0.1:8100"
echo Server started at http://127.0.0.1:8100
exit /b 0
