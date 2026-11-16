"""Rough cut-out masks for the couple and the dog (stand-in assets for the reel). Polygon seeds in 658x900 thumbnail coords -> GrabCut refine at 1/4 scale."""
import cv2, numpy as np
im=cv2.imread('assets/commons/arnolfini_commons.jpg',cv2.IMREAD_REDUCED_COLOR_4)   # 1096x1500
h,w=im.shape[:2]; k=w/658.0
def P(pts): return (np.array(pts,np.float32)*k).astype(np.int32)
# thumbnail polygons (probable foreground, generous), figures
giov=P([(120,150),(135,100),(190,92),(250,105),(262,170),(252,235),(300,285),(345,365),(335,385),(300,360),(320,640),(330,690),(250,700),(120,700),(60,690),(45,670),(75,490),(92,330),(95,255),(125,230)])
cost=P([(455,185),(470,160),(520,150),(575,185),(585,300),(560,330),(590,420),(640,560),(652,720),(640,870),(440,880),(355,830),(358,720),(400,700),(440,610),(410,430),(400,380),(380,368),(430,345),(440,300),(455,250)])
dog=P([(250,745),(300,745),(340,775),(375,790),(375,860),(330,885),(265,880),(245,830)])
def gc(poly, name):
    m=np.full((h,w),cv2.GC_BGD,np.uint8)
    pf=np.zeros((h,w),np.uint8); cv2.fillPoly(pf,[poly],255)
    prob=cv2.dilate(pf,np.ones((25,25),np.uint8)); sure=cv2.erode(pf,np.ones((41,41),np.uint8))
    m[prob>0]=cv2.GC_PR_BGD; m[pf>0]=cv2.GC_PR_FGD; m[sure>0]=cv2.GC_FGD
    bg=np.zeros((1,65));fg=np.zeros((1,65))
    cv2.grabCut(im,m,None,bg,fg,5,cv2.GC_INIT_WITH_MASK)
    out=((m==cv2.GC_FGD)|(m==cv2.GC_PR_FGD)).astype(np.uint8)*255
    out=cv2.morphologyEx(out,cv2.MORPH_OPEN,np.ones((5,5),np.uint8)); out=cv2.morphologyEx(out,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8))
    out=cv2.GaussianBlur(out,(0,0),1.5)
    cv2.imwrite(f'assets/masks/{name}.png',out); return out
mg=gc(giov,'giovanni'); mc=gc(cost,'costanza'); md=gc(dog,'dog')
couple=np.maximum(mg,mc); cv2.imwrite('assets/masks/couple.png',couple)
vis=im.copy(); vis[couple<128]=(vis[couple<128]*0.15).astype(np.uint8); vis[md>128]=(0.5*vis[md>128]+0.5*np.array([0,0,255])).astype(np.uint8)
cv2.imwrite('/private/tmp/claude-501/-Users-nhanvu-Documents-code-behind-the-image/d1d99b63-899d-4011-a440-2cba5b3bca9e/scratchpad/mask_vis.jpg',cv2.resize(vis,(658,900)))
