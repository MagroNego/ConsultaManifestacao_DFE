@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Configurar senha do Admin
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Execute INSTALAR.cmd antes de configurar o Admin.
    pause
    exit /b 1
)
echo Este configurador cria ou redefine a senha da conta administrativa escolhida.
echo As demais contas e o banco fiscal permanecem preservados.
echo.
"%PYTHON_EXE%" -m nfe_consulta.web.configure_admin
if errorlevel 1 (
    echo.
    echo Falha ao configurar o Admin.
    pause
    exit /b 1
)
echo.
pause
