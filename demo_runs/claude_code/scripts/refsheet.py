import sys
from PIL import Image, ImageDraw
S='/private/tmp/claude-501/-Users-nhanvu-Documents-code-behind-the-image/d1d99b63-899d-4011-a440-2cba5b3bca9e/scratchpad'
t0,t1,step,name=float(sys.argv[1]),float(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
cols=int(sys.argv[5]) if len(sys.argv)>5 else 4; w=int(sys.argv[6]) if len(sys.argv)>6 else 400
ts=[];t=t0
while t<=t1+1e-6: ts.append(t); t+=step
h=int(w*9/16); rows=(len(ts)+cols-1)//cols
sh=Image.new('RGB',(cols*w,rows*h)); d=ImageDraw.Draw(sh)
for i,t in enumerate(ts):
    n=int(round(t*5))+1
    try: im=Image.open(f'{S}/f/a_{n:05d}.jpg').resize((w,h))
    except Exception: continue
    sh.paste(im,((i%cols)*w,(i//cols)*h)); d.text(((i%cols)*w+5,(i//cols)*h+5),f'{t:.1f}s',fill=(255,255,0))
sh.save(f'{S}/{name}.jpg')
