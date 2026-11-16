import json,sys
T=json.load(open('v2/timing2.json')); END=T['end']
card={c['text']:c['t0'] for c in T['cards']}
fr=lambda t: round(round(t*30)/30,4)
B1=fr(card['FASHIONS AND FABRICS']); B2=fr(card['THE MIRROR'])
PY=r'D:\code\comic-book-pipeline\.venv\Scripts\python.exe'
def mk(name,cmds):
    L=["@echo off",r"cd /d D:\bench\claude_code","set PYTHONDONTWRITEBYTECODE=1","set CV_THREADS=4","set OMP_NUM_THREADS=4",
       rf"git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_before_{name}.txt 2>&1"]
    for c in cmds:
        L+= [c+rf" >> D:\bench\claude_code\{name}.log 2>&1", rf"echo EXIT=%ERRORLEVEL% >> D:\bench\claude_code\{name}.log"]
    L+=[rf"git -C D:\code\comic-book-pipeline status --short > D:\bench\claude_code\git_after_{name}.txt 2>&1", r"rmdir /s /q D:\bench\_heavy.lock", rf"echo LOCK_RELEASED >> D:\bench\claude_code\{name}.log"]
    open(f'v2/server/{name}.bat','w',newline='\r\n').write("\n".join(L)+"\n")
mk('v2prev',[f'{PY} -B build_v2.py render timing2.json prev_p1.mp4 --size 640x360 --fps 10 --t0 0 --t1 {B1}'])
mk('v2r1',[f'{PY} -B build_v2.py render timing2.json part1.mp4 --t0 0 --t1 {B1}'])
mk('v2r2',[f'{PY} -B build_v2.py render timing2.json part2.mp4 --t0 {B1} --t1 {B2}'])
mk('v2r3',[f'{PY} -B build_v2.py render timing2.json part3.mp4 --t0 {B2} --t1 {END}'])
open('v2/server/parts.txt','w',newline='\r\n').write("file 'part1.mp4'\nfile 'part2.mp4'\nfile 'part3.mp4'\n")
mk('v2fin',[f'{PY} -B audio_job2.py','ffmpeg -y -v error -f concat -safe 0 -i parts.txt -c copy video_all.mp4',
  f'ffmpeg -y -v error -i video_all.mp4 -i mix2_final.wav -i subtitles.srt -map 0:v -map 1:a -map 2:s -c:v copy -c:a aac -b:a 192k -c:s mov_text -metadata:s:s:0 language=eng -movflags +faststart -t {END} final_demo.mp4'])
print("B1",B1,"B2",B2,"END",END,"frames",int(B1*30),int((B2-B1)*30),int((END-B2)*30))
