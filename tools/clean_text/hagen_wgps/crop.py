"""Make a montage of line crops for the reader pass: crop.py out.png page:needle ..."""
import sys,json,re
from PIL import Image,ImageDraw
ROOT='/Users/nhanvu/Documents/code/behind-the-image/'
P=json.load(open(ROOT+'.scratch/clean_hagen/lines.json'))
def find(n,needle):
    best=None
    for l in P[n-1]['lines']:
        if needle.startswith('=') and l['t'].strip()==needle[1:]: return l
    for l in P[n-1]['lines']:
        if needle in l['t'] or needle in l['t'].replace('¬',''): best=l; break
    return best
def crop(n,needle,pad=2.6,w=None):
    l=find(n,needle)
    if l is None: return None
    im=Image.open(ROOT+'.scratch/clean_hagen/img/p%04d.png'%n); s=1600/P[n-1]['w']
    x0,y0,x1,y1=l['b']; h=y1-y0
    X0=max(0,int((x0-8)*s)); X1=min(im.width,int((x1+8)*s)); Y0=max(0,int((y0-h*pad)*s)); Y1=min(im.height,int((y1+h*pad)*s))
    return im.crop((X0,Y0,X1,Y1))
def montage(items,out,width=1100):
    tiles=[]
    for n,needle in items:
        c=crop(n,needle)
        if c is None:
            c=Image.new('RGB',(400,30),'white'); ImageDraw.Draw(c).text((5,5),'NOT FOUND',fill='red')
        if c.width>width: c=c.resize((width,int(c.height*width/c.width)))
        lab=Image.new('RGB',(width,22),'#ddd'); ImageDraw.Draw(lab).text((4,4),'p%d  [%s]'%(n,needle),fill='black')
        tiles.append(lab); tiles.append(c.convert('RGB'))
    H=sum(t.height+3 for t in tiles); M=Image.new('RGB',(width,H),'white'); y=0
    for t in tiles: M.paste(t,(0,y)); y+=t.height+3
    M.save(out)
if __name__=='__main__':
    out=sys.argv[1]; items=[]
    for a in sys.argv[2:]:
        n,needle=a.split(':',1); items.append((int(n),needle))
    montage(items,out)
