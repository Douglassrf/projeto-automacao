@echo off
setlocal
echo Verificando pacote final seguro...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\verify_final_package.ps1"
if errorlevel 1 (
  echo Verificacao do pacote FALHOU.
  exit /b 1
)
echo Verificacao do pacote OK.
