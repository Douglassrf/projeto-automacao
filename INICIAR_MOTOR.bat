@echo off
cd /d "%~dp0src"
set PYTHONPATH=%CD%
..\venv\Scripts\python.exe -B -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level debug --lifespan off
pause
