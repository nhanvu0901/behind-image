import sys,os,subprocess,glob
import cv2,numpy as np
S=sys.argv[1]; ids=sys.argv[2:]
d=S+"_reelstills"; 
r=subprocess.run(["python3","build_reel.py","still",d]+ids,capture_output=True,text=True); print(r.stderr[-1500:])
fs=[]
for i in ids:
    i0=i.split(":")[0]; g=sorted(glob.glob(f"{d}/{i0}_*.png"))
    fs.append(g[-1] if g else None)
tiles=[]
for f in fs:
    im=cv2.imread(f) if f else np.zeros((1080,1920,3),np.uint8)
    tiles.append(cv2.resize(im,(640,360),interpolation=cv2.INTER_AREA))
cols=3; rows=(len(tiles)+cols-1)//cols
sh=np.zeros((rows*360,cols*640,3),np.uint8)
for k,t in enumerate(tiles): sh[(k//cols)*360:(k//cols+1)*360,(k%cols)*640:(k%cols+1)*640]=t
cv2.imwrite(S+".jpg",sh)
