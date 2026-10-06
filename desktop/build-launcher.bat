@echo off
setlocal
cd /d "%~dp.."
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
py -3 -m PyInstaller --noconfirm --clean --windowed --onefile --name StudentRecordsControlCenter desktop\launcher.py
if errorlevel 1 (
  echo Launcher build failed.
  pause
  exit /b 1
)
echo Built dist\StudentRecordsControlCenter.exe
pause
