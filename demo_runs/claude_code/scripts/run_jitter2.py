import json,subprocess,sys,os
H=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); V=sys.argv[1]
shots=json.load(open(f"{H}/v2/shots_final.json"))
def f(sub,n=0): return [s for s in shots if sub in s['effect']][n]
R="/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained"
w=[("mine: opening pull-back",f("opening pull-back")['t0']+3,8),("mine: matte to fill-width + push to dress",f("matte to fill-width")['t0']+1,7),("mine: long pan down the dress",f("long pan down the dress")['t0']+1,min(8,f("long pan down the dress")['t1']-f("long pan down the dress")['t0']-1.5)),
   ("mine: mirror push",f("mirror push")['t0']+1,8),("mine: closing pull-out",f("closing")['t0']+3,12)]
for name,t0,d in w:
    o=subprocess.run(["python3",f"{H}/scripts/qa_jitter.py",V,"%.2f"%t0,"%.2f"%d,name],capture_output=True,text=True).stdout.strip(); print(o)
for name,p,t0,d in (("REF excerpt pan-up",f"{R}/effect-excerpts/lAjVuUB9AkI-930-pan-up.mp4",0.5,8.5),("REF excerpt push-in",f"{R}/effect-excerpts/crCPVoPsTtk-815-push-in.mp4",0.3,5.5),("REF episode mirror push",f"{R}/T15Kv6dtYO0.mp4",590,8)):
    print(subprocess.run(["python3",f"{H}/scripts/qa_jitter.py",p,str(t0),str(d),name],capture_output=True,text=True).stdout.strip())
