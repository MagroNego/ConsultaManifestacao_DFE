@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo Consulta de Manifestacao - Web
echo ============================================
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python Launcher nao encontrado.
  echo Instale Python 3.11 ou superior e execute este arquivo novamente.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  py -m venv .venv
  if errorlevel 1 goto :erro
)

echo Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :erro

echo Instalando aplicacao...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :erro

if not exist "dados" mkdir "dados"
if not exist "secrets" mkdir "secrets"
if not exist "logs" mkdir "logs"

echo.
".venv\Scripts\python.exe" -c "import nfe_consulta; import nfe_consulta.web.app; print('Versao:', nfe_consulta.__version__)"
if errorlevel 1 goto :erro

echo.
echo Instalacao concluida.
echo.
echo Proximos passos:
echo   1. Coloque o banco em dados\nfe_manifestacoes_seguro.db
echo   2. Coloque a senha do banco em secrets\db-password.txt
echo   3. Execute INICIAR_WEB.cmd
echo.
pause
exit /b 0

:erro
echo.
echo ERRO: a instalacao nao foi concluida.
pause
exit /b 1
