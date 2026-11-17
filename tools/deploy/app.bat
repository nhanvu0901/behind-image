@echo off
rem Runs the BTI editor/script/library app on 127.0.0.1:8560 on the Windows server. Started by start_app.ps1 (detached).
rem Never edit this file while the app runs (cmd re-reads a running .bat by byte offset).
cd /d D:\code\behind-the-image
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1
echo START %date% %time% >> logs\app.log
.venv\Scripts\python.exe -m bti.editor --host 127.0.0.1 --port 8560 >> logs\app.log 2>&1
echo EXIT=%ERRORLEVEL% %date% %time% >> logs\app.log
