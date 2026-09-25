@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "BASE_DIR=%~dp0"
cd /d "%BASE_DIR%"

if not exist "%BASE_DIR%logs" mkdir "%BASE_DIR%logs"

set "LOG_FILE=%BASE_DIR%logs\atualizacao_agendada.log"

if not defined NFE_DATABASE_PATH set "NFE_DATABASE_PATH=%BASE_DIR%dados\nfe_manifestacoes_seguro.db"
if not defined NFE_DATABASE_PASSWORD_FILE set "NFE_DATABASE_PASSWORD_FILE=%BASE_DIR%secrets\db-password.txt"
if not defined NFE_CERT_STORE set "NFE_CERT_STORE=LocalMachine"
if not defined NFE_SEFAZ_COOLDOWN_MINUTES set "NFE_SEFAZ_COOLDOWN_MINUTES=120"

echo ======================================================== >> "%LOG_FILE%"
echo [%date% %time%] Inicio da atualizacao agendada. >> "%LOG_FILE%"

if not exist "%NFE_DATABASE_PATH%" (
    echo [%date% %time%] ERRO: banco nao encontrado: %NFE_DATABASE_PATH% >> "%LOG_FILE%"
    exit /b 2
)

if not exist "%NFE_DATABASE_PASSWORD_FILE%" (
    echo [%date% %time%] ERRO: arquivo de senha nao encontrado: %NFE_DATABASE_PASSWORD_FILE% >> "%LOG_FILE%"
    exit /b 3
)

if not defined NFE_CERT_THUMBPRINT if not defined NFE_CERT_PATH if not exist "%BASE_DIR%secrets\cert-path.txt" (
    echo [%date% %time%] ERRO: certificado nao configurado. >> "%LOG_FILE%"
    echo [%date% %time%] Configure o PFX/P12 na area Atualizar ou defina NFE_CERT_THUMBPRINT. >> "%LOG_FILE%"
    exit /b 4
)

set "PYTHON_EXE=%BASE_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [%date% %time%] ERRO: Python nao encontrado. Crie .venv ou instale o Python Launcher. >> "%LOG_FILE%"
        exit /b 5
    )
    set "PYTHON_EXE=py"
)

echo [%date% %time%] Banco: %NFE_DATABASE_PATH% >> "%LOG_FILE%"
if exist "%BASE_DIR%secrets\cert-path.txt" (
    echo [%date% %time%] Certificado: arquivo PFX/P12 configurado pela area admin >> "%LOG_FILE%"
) else (
    echo [%date% %time%] Certificado: %NFE_CERT_STORE% / Windows Store >> "%LOG_FILE%"
)

"%PYTHON_EXE%" -m nfe_consulta.cli atualizar --banco "%NFE_DATABASE_PATH%" --max-lotes 50 >> "%LOG_FILE%" 2>&1
set "RESULTADO=%ERRORLEVEL%"

if "%RESULTADO%"=="0" (
    echo [%date% %time%] Atualizacao concluida com sucesso. >> "%LOG_FILE%"
) else (
    echo [%date% %time%] Atualizacao finalizada com erro. Codigo: %RESULTADO% >> "%LOG_FILE%"
)

echo. >> "%LOG_FILE%"
exit /b %RESULTADO%
