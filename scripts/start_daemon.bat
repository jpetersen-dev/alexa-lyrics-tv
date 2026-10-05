@echo off
title Alexa Lyrics TV - Daemon
cd /d "%~dp0\.."
echo =======================================================
echo        Alexa Lyrics TV - Daemon en Primer Plano
echo =======================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encontro el entorno virtual .venv.
    echo Asegurate de crearlo con: python -m venv .venv
    pause
    exit /b 1
)

echo Iniciando servidor FastAPI + WebSockets + Cast en http://0.0.0.0:8000 ...
echo Presiona Ctrl+C para detener el servicio.
echo.
.venv\Scripts\python.exe -m uvicorn src.server:app --host 0.0.0.0 --port 8000
pause
