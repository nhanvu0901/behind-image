@echo off
cd /d D:\bench\claude_code
set PYTHONDONTWRITEBYTECODE=1
set CV_THREADS=4
set OMP_NUM_THREADS=4
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_v2fin.txt 2>&1
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B audio_job2.py >> D:\bench\claude_code\v2fin.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\v2fin.log
ffmpeg -y -v error -f concat -safe 0 -i parts.txt -c copy video_all.mp4 >> D:\bench\claude_code\v2fin.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\v2fin.log
ffmpeg -y -v error -i video_all.mp4 -i mix2_final.wav -i subtitles.srt -map 0:v -map 1:a -map 2:s -c:v copy -c:a aac -b:a 192k -c:s mov_text -metadata:s:s:0 language=eng -movflags +faststart -t 820.8333 final_demo.mp4 >> D:\bench\claude_code\v2fin.log 2>&1
echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\v2fin.log
git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_v2fin.txt 2>&1
rmdir /s /q D:\bench\_heavy.lock
echo LOCK_RELEASED >> D:\bench\claude_code\v2fin.log
