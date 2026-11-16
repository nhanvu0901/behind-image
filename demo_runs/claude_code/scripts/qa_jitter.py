"""Frame-to-frame motion smoothness: per-pair ECC affine (translation + scale), residual vs a smooth (Savitzky-Golay) fit.
usage: qa_jitter.py <video> <t0> <dur> <label> [fps]"""
import sys, subprocess, numpy as np, cv2
from scipy.signal import savgol_filter
v,t0,du,label=sys.argv[1],float(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
fps=float(sys.argv[5]) if len(sys.argv)>5 else 30.0
w,h=640,360
raw=subprocess.run(["ffmpeg","-v","error","-ss",str(t0),"-t",str(du),"-i",v,"-vf",f"fps={fps},scale={w}:{h},format=gray","-f","rawvideo","-"],capture_output=True).stdout
n=len(raw)//(w*h); fr=[np.frombuffer(raw[i*w*h:(i+1)*w*h],np.uint8).reshape(h,w) for i in range(n)]
sc=[];dx=[];dy=[]
crit=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,80,1e-6)
for a,b in zip(fr[:-1],fr[1:]):
    W=np.eye(2,3,dtype=np.float32)
    try: cc,W=cv2.findTransformECC(cv2.GaussianBlur(a,(5,5),0).astype(np.float32),cv2.GaussianBlur(b,(5,5),0).astype(np.float32),W,cv2.MOTION_AFFINE,crit,None,5)
    except cv2.error: continue
    s=abs(np.linalg.det(W[:,:2]))**.5; sc.append(np.log(s)); dx.append(W[0,2]); dy.append(W[1,2])
def resid(x):
    x=np.array(x); 
    if len(x)<11: return float('nan')
    sm=savgol_filter(x,9,3); return float(np.std(x-sm))
rs,rx,ry=resid(sc),resid(dx),resid(dy)
# convert to 1080p-equivalents: translation px at 640 -> *3 ; scale residual -> px at frame edge (half-width 960 px)
print(f"{label}: frames={n} pairs={len(sc)}  trans-resid x={rx*3:.3f}px y={ry*3:.3f}px (1080p-equiv)  scale-resid={rs*960:.3f}px at frame edge  mean|dx|={np.mean(np.abs(dx))*3:.2f}px/f mean|dy|={np.mean(np.abs(dy))*3:.2f}px/f mean ln-scale/f={np.mean(sc):+.5f}")
