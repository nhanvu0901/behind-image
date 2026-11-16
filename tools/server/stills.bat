@echo off
cd /d D:\bench\bti
set PYTHONDONTWRITEBYTECODE=1
if not exist stills mkdir stills
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 5 --width 960 -o stills\w_5.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 17 --width 960 -o stills\w_17.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 32 --width 960 -o stills\w_32.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 43 --width 960 -o stills\w_43.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 75.5 --width 960 -o stills\w_75.5.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 78.5 --width 960 -o stills\w_78.5.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 90 --width 960 -o stills\w_90.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 110 --width 960 -o stills\w_110.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 177 --width 960 -o stills\w_177.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 196 --width 960 -o stills\w_196.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 258.5 --width 960 -o stills\w_258.5.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 310 --width 960 -o stills\w_310.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 510 --width 960 -o stills\w_510.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 580 --width 960 -o stills\w_580.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 805 --width 960 -o stills\w_805.png
D:\code\comic-book-pipeline\.venv\Scripts\python.exe -B -m bti.engine still projects\arnolfini 818 --width 960 -o stills\w_818.png
echo EXIT=%ERRORLEVEL%
