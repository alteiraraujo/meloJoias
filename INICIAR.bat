@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set MELO_DEMO_MODE=0
if not exist ".venv\Scripts\python.exe" (
  echo Execute INSTALAR.bat primeiro para preparar o sistema.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\start.py
if errorlevel 1 pause
