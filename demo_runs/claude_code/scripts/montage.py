import sys,json,subprocess,os,glob
import cv2,numpy as np
tp=sys.argv[1]; out=sys.argv[2]; times=[float(x) for x in sys.argv[3:]]
d=json.load(open(tp)); 
sd=out+"_stills"
subprocess.run(["python3","build_final.py","still",tp,sd]+[str(t) for t in times],check=True)
tiles=[]
for t in times:
    im=cv2.imread(os.path.join(sd,"t%07.2f.png"%t)); im=cv2.resize(im,(640,360),interpolation=cv2.INTER_AREA)
    cv2.putText(im,"%.2f"%t,(8,24),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,255,255),2); tiles.append(im)
cols=3; rows=(len(tiles)+cols-1)//cols
sh=np.zeros((rows*360,cols*640,3),np.uint8)
for i,t in enumerate(tiles): sh[(i//cols)*360:(i//cols+1)*360,(i%cols)*640:(i%cols+1)*640]=t
cv2.imwrite(out+".jpg",sh)
