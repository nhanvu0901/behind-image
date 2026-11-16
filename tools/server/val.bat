@echo off
cd /d D:\bench\bti
set PYTHONDONTWRITEBYTECODE=1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine validate projects\arnolfini
echo EXIT=%ERRORLEVEL%
