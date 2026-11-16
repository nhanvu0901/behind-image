@echo off
cd /d D:\bench\bti
set PYTHONDONTWRITEBYTECODE=1
set CV_THREADS=4
set OMP_NUM_THREADS=4
if not exist out mkdir out
echo START %date% %time% > D:\bench\bti\p1.log
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine render projects\arnolfini --t0 0 --t1 273.6 --quality final --threads 4 -o out\part1.mp4 >> D:\bench\bti\p1.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\bti\p1.log
echo END %date% %time% >> D:\bench\bti\p1.log
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\bti\p1.log
