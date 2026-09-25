@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "%~dp0secrets" mkdir "%~dp0secrets"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$usuario=Read-Host 'Usuario administrador [admin]';" ^
  "if([string]::IsNullOrWhiteSpace($usuario)){ $usuario='admin' };" ^
  "$usuario=$usuario.Trim();" ^
  "if($usuario.Length -gt 64 -or $usuario -match '[\r\n\t]'){ throw 'Usuario administrador invalido.' };" ^
  "$p1=Read-Host 'Nova senha do administrador' -AsSecureString;" ^
  "$p2=Read-Host 'Repita a senha' -AsSecureString;" ^
  "$s1=[System.Net.NetworkCredential]::new('', $p1).Password;" ^
  "$s2=[System.Net.NetworkCredential]::new('', $p2).Password;" ^
  "if($s1 -ne $s2){ throw 'As senhas nao conferem.' };" ^
  "if($s1.Length -lt 12){ throw 'Use pelo menos 12 caracteres.' };" ^
  "$utf8=New-Object System.Text.UTF8Encoding($false);" ^
  "[System.IO.File]::WriteAllText('%~dp0secrets\admin-user.txt',$usuario,$utf8);" ^
  "[System.IO.File]::WriteAllText('%~dp0secrets\admin-password.txt',$s1,$utf8);" ^
  "Write-Host '';" ^
  "Write-Host ('Login administrativo configurado: ' + $usuario) -ForegroundColor Green"

if errorlevel 1 (
    echo.
    echo Falha ao configurar o login administrativo.
    exit /b 1
)

echo.
echo Arquivos criados:
echo   secrets\admin-user.txt
echo   secrets\admin-password.txt
echo.
echo Reinicie a aplicacao para aplicar a alteracao.
echo.
pause
