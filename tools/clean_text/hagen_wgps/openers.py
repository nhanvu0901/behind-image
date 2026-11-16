import sys,re,json
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import layout as Lo
from PIL import Image,ImageDraw
ROOT=Lo.ROOT
SP='/private/tmp/claude-501/-Users-nhanvu-Documents-code-behind-the-image/d1d99b63-899d-4011-a440-2cba5b3bca9e/scratchpad/'
def region(n):
    L,o=Lo.classify_page(n)
    bigf=lambda l: l['sp'] and all(x[5]>=22 for x in l['sp'] if re.search('[A-Za-z]',x[0])) and re.search('[A-Za-z]{3}',l['t']) and l['d']>=0.14
    big=[l for l in L if bigf(l)]
    if not big: return None
    y0=min(l['b'][1] for l in big); y1=max(l['b'][3] for l in big)
    ab=[l for l in L if l['b'][3]<=y0+6 and l['b'][1]>y0-60 and l not in big and l['d']>=0.2]
    ls=big+ab
    return (min(l['b'][0] for l in ls),min(l['b'][1] for l in ls),max(l['b'][2] for l in ls),max(l['b'][3] for l in ls))
ops=[]
import pickle
for n in range(12,492):
    t=open(ROOT+'library/clean_text/hagen_wgps/page_%04d.txt'%n).read()
    if '\n# ' in t: ops.append(n)
print(len(ops))
tiles=[]; k=0
for n in ops:
    r=region(n)
    if not r: continue
    im=Image.open(ROOT+'.scratch/clean_hagen/img/p%04d.png'%n); s=1600/Lo.P[n-1]['w']
    c=im.crop((max(0,int((r[0]-6)*s)),max(0,int((r[1]-4)*s)),min(im.width,int((r[2]+6)*s)),min(im.height,int((r[3]+4)*s))))
    W=900
    if c.width!=W: c=c.resize((W,int(c.height*W/c.width)))
    lab=Image.new('RGB',(W,16),'#ccc'); ImageDraw.Draw(lab).text((3,2),'p%d'%n,fill='black')
    tiles+=[lab,c.convert('RGB')]
    k+=1
    if k%9==0 or n==ops[-1]:
        H=sum(t.height+2 for t in tiles); M=Image.new('RGB',(W,H),'white'); y=0
        for t in tiles: M.paste(t,(0,y)); y+=t.height+2
        M.save(SP+'open_%02d.png'%(k//9 if k%9==0 else k//9+1)); print('saved',k,M.size); tiles=[]
