import sys
# usage: mkjob.py name t0 t1 outfile [extra]
name,t0,t1,out=sys.argv[1:5]
L=["@echo off","cd /d D:\\bench\\bti","set PYTHONDONTWRITEBYTECODE=1","set CV_THREADS=4","set OMP_NUM_THREADS=4",
"if not exist out mkdir out",
f"echo START %date% %time% > D:\\bench\\bti\\{name}.log",
f"D:\\code\\comic-book-pipeline\\.venv\\Scripts\\python.exe -B -m bti.engine render projects\\arnolfini --t0 {t0} --t1 {t1} --quality final --threads 4 -o out\\{out} >> D:\\bench\\bti\\{name}.log 2>&1",
f"echo EXIT=%ERRORLEVEL% >> D:\\bench\\bti\\{name}.log",
f"echo END %date% %time% >> D:\\bench\\bti\\{name}.log",
"rmdir /s /q D:\\bench\\_heavy.lock",
f"echo LOCK_RELEASED >> D:\\bench\\bti\\{name}.log"]
open(name+".bat","w",newline="").write("\r\n".join(L)+"\r\n")
