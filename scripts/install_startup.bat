@echo off
title Alexa Lyrics TV - Registrar en Inicio de Windows
echo =======================================================
echo     Alexa Lyrics TV - Iniciar con Windows (Silencioso)
echo =======================================================
echo.

set SCRIPT_DIR=%~dp0
set VBS_TARGET=%SCRIPT_DIR%start_hidden.vbs
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT_PATH=%STARTUP_DIR%\AlexaLyricsTV.lnk

if not exist "%VBS_TARGET%" (
    echo [ERROR] No se encontro el archivo %VBS_TARGET%
    pause
    exit /b 1
)

echo Creando acceso directo en:
echo %SHORTCUT_PATH%
echo.

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_TARGET%\"'; $s.WorkingDirectory = '%SCRIPT_DIR%..'; $s.Description = 'Alexa Lyrics TV Background Daemon'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [EXITO] Acceso directo registrado. Alexa Lyrics TV iniciara automaticamente en segundo plano con cada arranque de Windows.
) else (
    echo [ERROR] No se pudo crear el acceso directo en Inicio.
)
echo.
pause
