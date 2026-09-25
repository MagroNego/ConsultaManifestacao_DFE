@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not defined NFE_ADMIN_SESSION_MINUTES set "NFE_ADMIN_SESSION_MINUTES=30"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=py"
)

"%PYTHON_EXE%" -m nfe_consulta.web.app
