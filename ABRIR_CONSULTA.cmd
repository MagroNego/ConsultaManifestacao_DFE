@echo off
setlocal
cd /d "%~dp0"
py -m nfe_consulta.cli --gui
if errorlevel 1 (
  echo A interface nao abriu. Consulte MANUAL_DE_INSTALACAO.md ou use ABRIR_CONSULTA_TEXTO.cmd.
  pause
)
