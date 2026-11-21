import re,sys,collections,json
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import suspects as S, accents as A
sus=S.suspects()
res=[]
for w,pages in sorted(sus.items()):
    for n in sorted(pages):
        vt=[m.group(0) for v in A.V[n] for m in A.CORE.finditer(v['t'])]
        vl=[x.lower() for x in vt]
        if w in vl or any(w==x.lower().strip("-") for x in vt): continue
        # nearest vision token
        near=sorted(vl,key=lambda x:A.lev(x,w) if abs(len(x)-len(w))<=3 else 9)[:1]
        res.append((w,n,near[0] if near and A.lev(near[0],w)<=3 else None))
print(len(res))
print('; '.join('%s@%d->%s'%r for r in res))
json.dump(res,open('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hagen/disagree.json','w'))
