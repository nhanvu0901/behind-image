"""contact_sheet.jpg (every 3 s, timestamp burned in) and reference_compare.jpg (my frame vs reference moment)."""
import sys, subprocess, os, glob, json, cv2, numpy as np
HERE=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V=sys.argv[1]; REF="/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained/T15Kv6dtYO0.mp4"
tmp="/private/tmp/claude-501/-Users-nhanvu-Documents-code-behind-the-image/d1d99b63-899d-4011-a440-2cba5b3bca9e/scratchpad/qa"
os.makedirs(tmp,exist_ok=True)
def frame(path,t,w=640,h=360):
    out=f"{tmp}/f.png"; subprocess.run(["ffmpeg","-y","-v","error","-ss",str(t),"-i",path,"-frames:v","1","-vf",f"scale={w}:{h}",out]); return cv2.imread(out)
dur=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",V],capture_output=True,text=True).stdout)
ts=list(np.arange(0,dur,3.0)); cols=4; w,h=480,270
rows=(len(ts)+cols-1)//cols; sh=np.zeros((rows*h,cols*w,3),np.uint8)
for i,t in enumerate(ts):
    f=frame(V,t,w,h); cv2.putText(f,"%05.1fs"%t,(8,26),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,255,255),2,cv2.LINE_AA)
    sh[(i//cols)*h:(i//cols+1)*h,(i%cols)*w:(i%cols+1)*w]=f
cv2.imwrite(os.path.join(HERE,"contact_sheet.jpg"),sh,[cv2.IMWRITE_JPEG_QUALITY,88])
T=json.load(open(os.path.join(HERE,"timing.json"))); b=T["beats"]
pairs=[("opening couple detail",0.8,22.0),("full painting on matte (end of pull-back)",9.0,31.0),("detail label strip",b["B2a"]["start"]+3.2,329.5),
       ("pan down dress",b["B2b"]["start"]+2.0,340.0),("title card vs chapter card",T["title"][0]+1.5,180.0),("circles",b["B3b"]["start"]+1.8,664.0),
       ("mirror spotlight/push",b["B3a"]["start"]+3.0,596.0),("hands detail",b["B4d"]["start"]+2.0,872.0),("closing pull-out",b["B5b"]["start"]+3.0,906.0),
       ("matte painting + side text",b["B2d"]["start"]+5.0,926.0)]
W2,H2=800,450
sh=np.zeros((len(pairs)*(H2+30),2*W2,3),np.uint8)
for i,(name,tm,tr) in enumerate(pairs):
    a=frame(V,tm,W2,H2); r=frame(REF,tr,W2,H2)
    for im,txt in ((a,"MINE %.1fs"%tm),(r,"REFERENCE %.1fs"%tr)): cv2.putText(im,txt,(10,30),cv2.FONT_HERSHEY_SIMPLEX,.9,(0,255,255),2,cv2.LINE_AA)
    y=i*(H2+30); sh[y+30:y+30+H2,:W2]=a; sh[y+30:y+30+H2,W2:]=r
    cv2.putText(sh,name,(10,y+22),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2,cv2.LINE_AA)
cv2.imwrite(os.path.join(HERE,"reference_compare.jpg"),sh,[cv2.IMWRITE_JPEG_QUALITY,86])
print("sheets done")
