@echo off
cd /d "%~dp0src"
set PYTHONPATH=%CD%
echo Ligando motor seguro...
..\venv\Scripts\python.exe -B -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --lifespan off --log-level info
pause
