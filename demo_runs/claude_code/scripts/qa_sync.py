"""Measure highlight onsets in the rendered final_demo.mp4 and compare with the aligned word start times.
usage: qa_sync.py final_demo.mp4 timing.json"""
import sys, json, subprocess, numpy as np
v,tj=sys.argv[1],sys.argv[2]
T=json.load(open(tj)); B=T["beats"]
W,H=480,270
raw=subprocess.run(["ffmpeg","-v","error","-i",v,"-vf",f"fps=30,scale={W}:{H}","-f","rawvideo","-pix_fmt","gray","-"],capture_output=True).stdout
n=len(raw)//(W*H); F=np.frombuffer(raw,np.uint8)[:n*W*H].reshape(n,H,W).astype(np.float32)
def wt(beat,pre):
    for x in B[beat]["words"]:
        if x["w"].lower().strip(".,'\"").startswith(pre): return x["s"]
def onset(sig,t_lo,t_hi,frac=.10,rising=True):
    """first time in [t_lo,t_hi] where the signal has covered `frac` of its excursion to the end of the window"""
    i0,i1=int(t_lo*30),int(t_hi*30); s=sig[i0:i1+1]; b=s[0]; e=s[-1] if rising else s[-1]
    d=(s-b)/(e-b+1e-9); k=np.argmax(d>frac); return (i0+k)/30
rows=[]
def lumratio(t,y0,y1,x0,x1,cy0,cy1,cx0,cx1):
    i=int(t*30); return F[i,y0:y1,x0:x1].mean()/(F[i,cy0:cy1,cx0:cx1].mean()+1e-6)
# 1 spotlight on mirror: corner vs centre luminance ratio falls; window word-0.3 .. word+1.2
w=wt("B3a","mirror"); sig=np.array([lumratio(i/30,0,40,0,80,100,170,180,300) for i in range(n)])
rows.append(("Spotlight on mirror (B3a)","mirror",w,onset(sig,w-.4,w+1.2),sig))
# 2 rings: bright grey pixels in area right of the mirror
w=wt("B3b","roundels"); sig=np.array([(F[i,100:180,260:420]>150).sum() for i in range(n)],np.float32)
rows.append(("Two circles (B3b)","roundels",w+.1,onset(sig,w-.2,w+1.0),sig))
# 3 hands spotlight
w=wt("B4d","holds"); sig=np.array([lumratio(i/30,0,40,0,80,90,180,160,320) for i in range(n)])
rows.append(("Spotlight on joined hands (B4d)","holds",w,onset(sig,w-.4,w+1.2),sig))
# 4 slide-in of Van der Paele panel: right-edge band brightness
w=wt("B4a","compare"); sig=np.array([F[i,60:200,430:476].mean() for i in range(n)])
rows.append(("Van der Paele slide-in (B4a)","Compare",w+.08,onset(sig,w-.2,w+1.2),sig))
# 5 year text 1433 : white pixels in left band
w=wt("B2d","1433"); sig=np.array([(F[i,90:140,50:140]>200).sum() for i in range(n)],np.float32)
rows.append(("'1433' caption (B2d)","1433",w,onset(sig,w-.3,w+.9),sig))
w=wt("B2d","finished"); sig=np.array([(F[i,90:140,340:430]>200).sum() for i in range(n)],np.float32)
rows.append(("'1434' caption (B2d)","finished",w,onset(sig,w-.3,w+.9),sig))
print("| highlight | word | word start (s) | visual onset measured in mp4 (s) | offset (s) | within +-0.25 |\n|---|---|---|---|---|---|")
ok=0
for name,word,w,o,_ in rows:
    off=o-w; good=abs(off)<=.25; ok+=good
    print(f"| {name} | {word} | {w:.2f} | {o:.2f} | {off:+.2f} | {'yes' if good else 'NO'} |")
print(f"\n{ok}/{len(rows)} within +-0.25 s")
