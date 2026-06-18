@echo off
setlocal
cd /d "%~dp0"
set "PY=C:\Users\USU??RIO\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not exist "%PY%" set "PY=C:\Users\USU??RIO\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
echo Validando homologacao final segura...
"%PY%" -m pytest src/app/tests/test_final_safe_e2e.py -p no:cacheprovider --basetemp .pytest_tmp
if errorlevel 1 (
  echo.
  echo Falha na validacao final.
  exit /b 1
)
echo.
echo Validacao final OK.
exit /b 0
