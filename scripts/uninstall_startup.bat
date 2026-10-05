@echo off
title Alexa Lyrics TV - Desinstalar de Inicio de Windows
echo =======================================================
echo    Alexa Lyrics TV - Remover de Inicio de Windows
echo =======================================================
echo.

set SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AlexaLyricsTV.lnk

if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo [EXITO] El acceso directo ha sido eliminado de la carpeta de inicio.
) else (
    echo [INFO] No habia ningun acceso directo instalado en la carpeta de inicio.
)
echo.
pause
