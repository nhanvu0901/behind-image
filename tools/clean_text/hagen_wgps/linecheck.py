import re,sys,json,difflib,collections
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import layout as Lo, accents as A
def vis_lines(n,b,W,H):
    x0,y0,x1,y1=b; hh=y1-y0; out=[]
    for v in A.V.get(n,[]):
        vx0,vy0=v['x']*W,v['y']*H; vx1,vy1=vx0+v['w']*W,vy0+v['h']*H
        oy=min(y1,vy1)-max(y0,vy0)
        if oy>=0.5*min(hh,vy1-vy0) and min(x1,vx1)-max(x0,vx0)>10: out.append((vx0,v['t']))
    return [t for _,t in sorted(out)]
nz=lambda s: re.sub(r'[^a-z]','',A.nrm(s))
def check(n):
    p=Lo.P[n-1]; W,H=p['w'],p['h']; res=[]
    for l in p['lines']:
        t=l['t'].replace(Lo.SOFT,'')
        if len(re.sub(r'[^A-Za-z]','',t))<8: continue
        vl=' '.join(vis_lines(n,l['b'],W,H))
        a,b=nz(t),nz(vl)
        if len(b)<5: 
            res.append((n,'novision',t,'')); continue
        r=difflib.SequenceMatcher(None,a,b).ratio()
        # vision line may be wider (merged columns) -> use best substring ratio
        if len(b)>len(a)*1.3:
            m=difflib.SequenceMatcher(None,a,b).find_longest_match(0,len(a),0,len(b))
            r=max(r,m.size/max(len(a),1))
        res.append((n,round(r,2),t,vl))
    return res
if __name__=='__main__':
    bad=[]
    for n in range(12,492):
        for r in check(n):
            if r[1]=='novision' or r[1]<0.75: bad.append(r)
    print(len(bad))
    c=collections.Counter(r[0] for r in bad)
    print(sorted(c.items(),key=lambda kv:-kv[1])[:60])
    json.dump(bad,open('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hagen/linebad.json','w'),ensure_ascii=False)
