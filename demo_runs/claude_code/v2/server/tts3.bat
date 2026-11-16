@echo off
cd /d D:\bench\claude_code
set PYTHONDONTWRITEBYTECODE=1
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_tts3.txt 2>&1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B tts_v2.py 3 > D:\bench\claude_code\tts3.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\tts3.log
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_tts3.txt 2>&1
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\claude_code\tts3.log
