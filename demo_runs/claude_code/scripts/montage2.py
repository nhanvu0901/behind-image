import sys,subprocess,os,cv2,numpy as np
tp,out,t0,t1,step=sys.argv[1],sys.argv[2],float(sys.argv[3]),float(sys.argv[4]),float(sys.argv[5])
cols=int(sys.argv[6]) if len(sys.argv)>6 else 4
ts=list(np.arange(t0,t1,step)); sd=out+"_st"
r=subprocess.run(["python3","build_v2.py","still",tp,sd]+["%.2f"%t for t in ts],capture_output=True,text=True)
if r.returncode: print(r.stderr[-1500:]); sys.exit(1)
w,h=480,270; rows=(len(ts)+cols-1)//cols; sh=np.zeros((rows*h,cols*w,3),np.uint8)
for i,t in enumerate(ts):
    im=cv2.resize(cv2.imread(os.path.join(sd,"t%07.2f.png"%t)),(w,h),interpolation=cv2.INTER_AREA)
    cv2.putText(im,"%.1f"%t,(6,22),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,255,255),2); sh[(i//cols)*h:(i//cols+1)*h,(i%cols)*w:(i%cols+1)*w]=im
cv2.imwrite(out+".jpg",sh,[cv2.IMWRITE_JPEG_QUALITY,85]); print("ok",len(ts))
