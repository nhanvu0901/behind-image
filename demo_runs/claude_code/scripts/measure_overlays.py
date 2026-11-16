"""Overlay timing measurements in the reference (30 fps dense decode, 1280x720 gray)."""
import subprocess, numpy as np, sys
V="/Users/nhanvu/Documents/code/behind-the-image/research_media/great-art-explained/T15Kv6dtYO0.mp4"
def dec(start,dur,fps=29.97):
    w,h=1280,720
    raw=subprocess.run(["ffmpeg","-v","error","-ss",str(start),"-t",str(dur),"-i",V,"-vf",f"fps={fps},format=gray","-f","rawvideo","-"],capture_output=True).stdout
    n=len(raw)//(w*h); return np.frombuffer(raw,np.uint8).reshape(n,h,w).astype(np.float32)
def p(title): print("\n##",title)
# 1. opening fade from black
f=dec(0,2.0); p("open: mean luminance, t(s) -> lum")
print(" ".join(f"{i/29.97:.2f}:{f[i].mean():.1f}" for i in range(0,len(f),3)))
# 2. label envelope (BLUE UNDERGARMENT): strip region y .79-.93; text region = bright pixels
f=dec(326.0,6.0); p("label strip: t -> (strip mean lum in x 0.80-1.0 [no text], max text lum, #white px)")
ys,ye=int(.80*720),int(.93*720)
for i in range(0,len(f),3):
    reg=f[i][ys:ye,:]; wh=(f[i][ys:ye,60:700]>200).sum()
    print(f"{326+i/29.97:.2f}: stripLum={f[i][ys:ye,900:1280].mean():.1f} aboveLum={f[i][int(.65*720):ys,900:1280].mean():.1f} whitePx={wh}")
# 3. chapter title card 'FASHIONS AND FABRICS' ~ 179-183
f=dec(178.0,6.0); p("chapter card: t -> mean lum, white px in text band")
for i in range(0,len(f),3):
    print(f"{178+i/29.97:.2f}: lum={f[i].mean():.1f} whitePx={(f[i][int(.65*720):int(.95*720)]>200).sum()}")
# 4. dimension annotation 173.5-176.5
f=dec(173.5,3.5); p("annotation: t -> white px (>235) in frame")
for i in range(0,len(f),3):
    print(f"{173.5+i/29.97:.2f}: whitePx={(f[i]>235).sum()}")
# 5. circles
f=dec(661.5,5.5); p("circles: t -> px with |diff vs frame0|>40 (ring pixels)")
for i in range(0,len(f),3):
    d=(abs(f[i]-f[0])>25).sum(); print(f"{661.5+i/29.97:.2f}: diffPx={d}")
