"""Make a contact sheet of line crops. Usage: sheet.py out.png page:x:y:w:h:label ..."""
import sys
from PIL import Image, ImageDraw
IMG='/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hodge/img/p%04d.png'
def make(items,out,width=1300,pad=0.006):
    rows=[]
    for it in items:
        p,x,y,w,h,label=it
        im=Image.open(IMG%p); W,H=im.size
        box=(max(0,int((x-pad)*W)),max(0,int((y-pad*0.8)*H)),min(W,int((x+w+pad)*W)),min(H,int((y+h+pad*0.8)*H)))
        c=im.crop(box)
        s=min(1.6,(width-90)/c.width)
        c=c.resize((max(1,int(c.width*s)),max(1,int(c.height*s))))
        rows.append((label,c))
    Hh=sum(c.height+26 for _,c in rows)
    sh=Image.new('RGB',(width,Hh),'white'); d=ImageDraw.Draw(sh); y=0
    for label,c in rows:
        d.text((4,y+2),label,fill=(200,0,0)); sh.paste(c,(8,y+14)); y+=c.height+26
    sh.save(out)
if __name__=='__main__':
    out=sys.argv[1]; items=[]
    for a in sys.argv[2:]:
        p,x,y,w,h,l=a.split(':',5); items.append((int(p),float(x),float(y),float(w),float(h),l))
    make(items,out)
