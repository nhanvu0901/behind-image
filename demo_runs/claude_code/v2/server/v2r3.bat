@echo off
cd /d D:\bench\claude_code
set PYTHONDONTWRITEBYTECODE=1
set CV_THREADS=4
set OMP_NUM_THREADS=4
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_v2r3.txt 2>&1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B build_v2.py render timing2.json part3.mp4 --t0 554.7667 --t1 820.8333 >> D:\bench\claude_code\v2r3.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\v2r3.log
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_v2r3.txt 2>&1
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\claude_code\v2r3.log
