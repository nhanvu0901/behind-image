@echo off
cd /d D:\bench\claude_code
set PYTHONDONTWRITEBYTECODE=1
set CV_THREADS=4
set OMP_NUM_THREADS=4
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_job_final.txt 2>&1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B audio_job.py >> D:\bench\claude_code\job_final.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\job_final.log
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B build_final.py render timing.json video_silent.mp4 >> D:\bench\claude_code\job_final.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\job_final.log
ffmpeg -y -v error -i video_silent.mp4 -i mix_final.wav -filter_script:v vf.txt -map 0:v -map 1:a -c:v libx264 -preset medium -crf 17 -pix_fmt yuv420p -r 30 -c:a aac -b:a 192k -movflags +faststart -t 81.05 final_demo.mp4 >> D:\bench\claude_code\job_final.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\job_final.log
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_job_final.txt 2>&1
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\claude_code\job_final.log
