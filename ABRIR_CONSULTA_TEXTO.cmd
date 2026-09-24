@echo off
setlocal
cd /d "%~dp0"
py -m nfe_consulta.assistente
if errorlevel 1 echo Verifique o erro acima ou consulte MANUAL_DE_USO.md.
echo.
pause
