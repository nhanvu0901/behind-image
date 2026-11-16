"""Measure virtual-camera zoom/pan between consecutive frames of a reference clip with ECC (affine).
Usage: measure_motion.py <video> <start> <dur> <label> [fps]
Outputs per-interval cumulative scale and translation (px at 320x180) + fitted easing summary."""
import sys, subprocess, json, numpy as np, cv2
FF="ffmpeg"
def frames(video, start, dur, fps, w=320, h=180):
    cmd=[FF,"-v","error","-ss",str(start),"-t",str(dur),"-i",video,"-vf",f"fps={fps},scale={w}:{h},format=gray","-f","rawvideo","-"]
    raw=subprocess.run(cmd,capture_output=True).stdout
    n=len(raw)//(w*h)
    return [np.frombuffer(raw[i*w*h:(i+1)*w*h],np.uint8).reshape(h,w) for i in range(n)]
def ecc(a,b):
    # estimate warp M such that b(x) ~ a(M x)  (MOTION_AFFINE)
    W=np.eye(2,3,dtype=np.float32)
    crit=(cv2.TERM_CRITERIA_EPS|cv2.TERM_CRITERIA_COUNT,100,1e-5)
    af=cv2.GaussianBlur(a,(5,5),0).astype(np.float32); bf=cv2.GaussianBlur(b,(5,5),0).astype(np.float32)
    try:
        cc,W=cv2.findTransformECC(af,bf,W,cv2.MOTION_AFFINE,crit,None,5)
    except cv2.error:
        return None,0
    return W,cc
def run(video,start,dur,label,fps=10):
    fr=frames(video,start,dur,fps)
    h,w=fr[0].shape; cx,cy=w/2,h/2
    out=[]; S=1.0; TX=0.0; TY=0.0
    for i in range(1,len(fr)):
        W,cc=ecc(fr[i-1],fr[i])
        if W is None or cc<0.5: out.append((i/fps,None,None,None,cc)); continue
        # a(Wx)=b(x): content scale in b relative a = 1/s where s=W[0,0]  -> zoom_in factor = 1/s
        s=(abs(np.linalg.det(W[:,:2])))**0.5
        zin=s
        # content shift of image centre (in b coordinates): point c in b came from W c in a
        sc=W@np.array([cx,cy,1.0]); dx=cx-sc[0]; dy=cy-sc[1]   # content moved by (dx,dy) between frames? sign: a-point sc is at centre in b => content moved by (cx-sc)
        S*=zin; TX+=dx; TY+=dy
        out.append((i/fps,S,TX,TY,cc))
    return out
if __name__=="__main__":
    v,st,du,lab=sys.argv[1],float(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
    fps=float(sys.argv[5]) if len(sys.argv)>5 else 10
    r=run(v,st,du,lab,fps)
    print(f"# {lab}  start={st} dur={du}")
    print("t  cumMagnification  cumShiftX  cumShiftY (px@320x180, content motion)  ecc")
    for t,S,X,Y,cc in r[::max(1,int(fps//2))]:
        print(f"{t:5.1f} " + (f"{S:7.4f} {X:8.2f} {Y:8.2f}" if S else "   n/a") + f"  {cc:.2f}")
    good=[x for x in r if x[1]]
    if good:
        t=np.array([g[0] for g in good]); S=np.array([g[1] for g in good])
        print("TOTAL magnification change %.3fx (>1 = push-in/zoom-in, <1 = pull-back) over %.1fs; mean ln-rate %.4f /s"%(S[-1],t[-1],np.log(S[-1])/t[-1]))
        # easing: normalised progress in ln-zoom vs time
        p=np.log(S)/np.log(S[-1]) if abs(np.log(S[-1]))>1e-3 else None
        if p is not None:
            for q in (0.25,0.5,0.75):
                k=np.argmin(abs(t-q*t[-1])); print(f"  progress@{int(q*100)}%time = {p[k]:.2f}")
