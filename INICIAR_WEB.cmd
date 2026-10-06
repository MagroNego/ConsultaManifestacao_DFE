@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not defined NFE_AUTO_SYNC_ENABLED set "NFE_AUTO_SYNC_ENABLED=1"
if not defined NFE_AUTO_SYNC_WEEKDAYS set "NFE_AUTO_SYNC_WEEKDAYS=0,1,2,3,4,5,6"
if not defined NFE_WEB_ENV set "NFE_WEB_ENV=production"
if not exist "%~dp0secrets" mkdir "%~dp0secrets"
if not defined NFE_WEB_CSRF_SECRET if not exist "%~dp0secrets\web-csrf-secret.txt" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$b=New-Object byte[] 48; $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($b); $rng.Dispose(); [System.IO.File]::WriteAllText('%~dp0secrets\web-csrf-secret.txt', [Convert]::ToBase64String($b))"
    if errorlevel 1 exit /b 1
)

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=py"
)

"%PYTHON_EXE%" -m nfe_consulta.web.app

