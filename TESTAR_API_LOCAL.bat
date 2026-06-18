@echo off
setlocal
echo Testando API local...
curl http://127.0.0.1:8000/
echo.
echo Testando operador Meta em modo seguro...
curl http://127.0.0.1:8000/api/v1/campaign-operator/status
echo.
pause
