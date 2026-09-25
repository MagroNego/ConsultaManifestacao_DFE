@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0secrets" mkdir "%~dp0secrets"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$p1=Read-Host 'Nova senha do administrador' -AsSecureString;" ^
  "$p2=Read-Host 'Repita a senha' -AsSecureString;" ^
  "$s1=[System.Net.NetworkCredential]::new('', $p1).Password;" ^
  "$s2=[System.Net.NetworkCredential]::new('', $p2).Password;" ^
  "if($s1 -ne $s2){ throw 'As senhas nao conferem.' };" ^
  "if($s1.Length -lt 12){ throw 'Use pelo menos 12 caracteres.' };" ^
  "[System.IO.File]::WriteAllText('%~dp0secrets\admin-password.txt',$s1,(New-Object System.Text.UTF8Encoding($false)));" ^
  "Write-Host 'Senha administrativa configurada.'"

if errorlevel 1 (
    echo Falha ao configurar a senha administrativa.
    exit /b 1
)

echo.
echo Usuario padrao: admin
echo Arquivo: secrets\admin-password.txt
echo.
pause
