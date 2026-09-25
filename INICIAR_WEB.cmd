@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not defined NFE_DATABASE_PASSWORD_FILE if exist "%~dp0secrets\db-password.txt" (
    set "NFE_DATABASE_PASSWORD_FILE=%~dp0secrets\db-password.txt"
)

if not defined NFE_ADMIN_PASSWORD_FILE if exist "%~dp0secrets\admin-password.txt" (
    set "NFE_ADMIN_PASSWORD_FILE=%~dp0secrets\admin-password.txt"
)

if not defined NFE_ADMIN_USER_FILE if exist "%~dp0secrets\admin-user.txt" (
    set "NFE_ADMIN_USER_FILE=%~dp0secrets\admin-user.txt"
)

if not defined NFE_ADMIN_USER if not defined NFE_ADMIN_USER_FILE set "NFE_ADMIN_USER=admin"
if not defined NFE_ADMIN_SESSION_MINUTES set "NFE_ADMIN_SESSION_MINUTES=30"

py -m nfe_consulta.web.app
