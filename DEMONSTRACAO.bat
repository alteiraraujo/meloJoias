@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set DB_ENGINE=sqlite
set MELO_DEMO_MODE=1
set MELO_PORT=8792
if not exist ".venv\Scripts\python.exe" (
  echo Execute INSTALAR.bat primeiro para preparar o sistema.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\setup.py --demo --no-input
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" scripts\start.py
if errorlevel 1 goto :fail
exit /b 0
:fail
pause
exit /b 1
