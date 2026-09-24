@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher nao encontrado. Instale Python 3.11+ pela TI e consulte MANUAL_DE_INSTALACAO.md.
  pause
  exit /b 1
)
py -m pip install -e .
if errorlevel 1 (
  echo Instalacao falhou. Consulte MANUAL_DE_INSTALACAO.md e a equipe de TI.
  pause
  exit /b 1
)
py -m nfe_consulta.cli --version
echo Instalacao concluida. Use ABRIR_CONSULTA.cmd para consultar.
pause
