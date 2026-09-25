@echo off
setlocal
cd /d "%~dp0"
py -m nfe_consulta.web.app
