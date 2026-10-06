@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Consulta de Manifestacao - Rede local

if not exist "%~dp0INICIAR_WEB.cmd" (
    echo Coloque este BAT na mesma pasta de INICIAR_WEB.cmd.
    pause
    exit /b 1
)

set "NFE_WEB_HOST=0.0.0.0"
set "NFE_WEB_PORT=8080"

echo Neste computador: http://127.0.0.1:8080
echo Na rede: use o IP deste computador seguido de :8080
echo Deixe esta janela aberta enquanto usar o aplicativo.
echo Para encerrar, pressione Ctrl+C.
echo.

call "%~dp0INICIAR_WEB.cmd"
if errorlevel 1 (
    echo.
    echo O aplicativo encerrou com erro. Confira a mensagem acima.
    pause
    exit /b 1
)
