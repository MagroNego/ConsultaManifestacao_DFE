@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Execucao unica em 30/09/2026, 09:00 no horario de Brasilia.
rem As variaveis valem somente para esta janela do aplicativo.
set "NFE_AUTO_SYNC_ONCE_DATE=2026-09-30"
set "NFE_AUTO_SYNC_HOUR=9"
set "NFE_AUTO_SYNC_MINUTE=0"
set "NFE_AUTO_SYNC_MAX_LOTES=50"

echo Teste unico da sincronizacao: 30/09/2026 as 09:00 (Brasilia).
echo Mantenha esta janela aberta. Encerre outra instancia antes de iniciar.
echo.
call "%~dp0INICIAR_WEB.cmd"
if errorlevel 1 (
    echo.
    echo O servidor nao iniciou corretamente; o teste nao foi agendado.
    pause
    exit /b 1
)
