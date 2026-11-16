@echo off
cd /d D:\bench\claude_code
set PYTHONDONTWRITEBYTECODE=1
set CV_THREADS=4
set OMP_NUM_THREADS=4
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_v2prev.txt 2>&1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B build_v2.py render timing2.json prev_p1.mp4 --size 640x360 --fps 10 --t0 0 --t1 296.3333 >> D:\bench\claude_code\v2prev.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\v2prev.log
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_v2prev.txt 2>&1
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\claude_code\v2prev.log
