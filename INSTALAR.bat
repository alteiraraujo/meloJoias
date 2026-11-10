@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set MELO_DEMO_MODE=0
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" scripts\setup.py
if errorlevel 1 goto :fail
echo.
echo Instalacao concluida. Abra INICIAR.bat para usar o sistema.
pause
exit /b 0
:fail
echo.
echo A instalacao nao foi concluida. Veja a mensagem acima e as instrucoes em README.md.
pause
exit /b 1
