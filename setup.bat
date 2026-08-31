@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"

echo.
echo ==========================================
echo   Student Management System - First Setup
echo ==========================================
echo.

set "BOOTSTRAP_PYTHON="
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 set "BOOTSTRAP_PYTHON=py -3.12"

if not defined BOOTSTRAP_PYTHON (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3.12 or later was not found.
    echo Install Python from https://www.python.org/downloads/ and run this file again.
    pause
    exit /b 1
  )
  set "BOOTSTRAP_PYTHON=python"
)

%BOOTSTRAP_PYTHON% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 or later is required.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the project virtual environment...
  %BOOTSTRAP_PYTHON% -m venv .venv
  if errorlevel 1 goto :setup_failed
)

set "PROJECT_PYTHON=%CD%\.venv\Scripts\python.exe"
echo Installing project dependencies...
"%PROJECT_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :setup_failed
"%PROJECT_PYTHON%" -m pip install -e .
if errorlevel 1 goto :setup_failed

if not exist ".env" (
  for /f "usebackq delims=" %%S in (`"%PROJECT_PYTHON%" -c "import secrets; print(secrets.token_urlsafe(48))"`) do set "JWT_SECRET_VALUE=%%S"
  echo Creating the local configuration file...
  (
    echo APP_NAME=Student Management System
    echo ENVIRONMENT=development
    echo DATABASE_URL=sqlite:///./data/student_management.db
    echo JWT_SECRET=%JWT_SECRET_VALUE%
    echo COOKIE_SECURE=false
    echo STORAGE_PATH=storage
    echo EXPORT_PATH=exports
    echo OLLAMA_BASE_URL=http://127.0.0.1:11434
    echo OLLAMA_MODEL=student-qwen-cuda:latest
    echo AI_ENABLED=true
  ) > ".env"
) else (
  echo Keeping the existing .env configuration.
)

if not exist "data" mkdir "data"
if not exist "storage" mkdir "storage"
if not exist "exports" mkdir "exports"
if not exist "run" mkdir "run"

echo Initializing the database...
"%PROJECT_PYTHON%" -c "from app.db import init_db; init_db()"
if errorlevel 1 goto :setup_failed

set "AI_READY=0"
if exist "models\ollama\manifests\registry.ollama.ai\library\student-qwen\latest" set "AI_READY=1"
if exist "models\imports\Qwen2.5-7B-Instruct-Q5_K_M.gguf" set "AI_READY=1"
if "%AI_READY%"=="1" (
  echo Configuring the project-local AI runtime...
  powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\setup-project-ai.ps1"
  if errorlevel 1 (
    echo AI setup did not finish. The system can still run without AI.
    echo Copy the model files into models\ollama or the GGUF file into models\imports, then run:
    echo powershell -ExecutionPolicy Bypass -File scripts\setup-project-ai.ps1
  )
) else (
  echo AI model files were not found. The system will start with AI in degraded mode.
  echo Copy the project models\ollama folder or place the GGUF file in models\imports, then run:
  echo powershell -ExecutionPolicy Bypass -File scripts\setup-project-ai.ps1
)

echo.
echo Setup completed.
echo For normal use, run start-system.bat. Do not run setup.bat again unless repairing or migrating the installation.
pause
exit /b 0

:setup_failed
echo.
echo Setup failed. Review the messages above, correct the issue, and run setup.bat again.
pause
exit /b 1
