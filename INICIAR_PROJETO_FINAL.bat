@echo off
setlocal
cd /d "%~dp0"
set "PY=C:\Users\USU??RIO\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=C:\Users\USU??RIO\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
echo Iniciando Projeto Automacao em modo seguro...
echo URL: http://127.0.0.1:8000/docs
cd src
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
