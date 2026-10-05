@echo off
title Alexa Lyrics TV - Detener Daemon
echo =======================================================
echo        Alexa Lyrics TV - Detener Servicio
echo =======================================================
echo.
echo Buscando proceso activo en el puerto 8000...

set FOUND=0
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    set FOUND=1
    echo Finalizando proceso con PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

if "%FOUND%"=="1" (
    echo.
    echo [OK] El servicio Alexa Lyrics TV ha sido detenido correctamente.
) else (
    echo.
    echo [INFO] No habia ningun proceso escuchando en el puerto 8000.
)

timeout /t 3 >nul
