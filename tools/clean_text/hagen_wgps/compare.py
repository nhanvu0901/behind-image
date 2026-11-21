import re,sys,collections,json
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import accents as A
D='/Users/nhanvu/Documents/code/behind-the-image/library/clean_text/hagen_wgps/'
tok=lambda s:[A.nrm(w) for w in re.findall(r"[A-Za-zÀ-ÿ]{3,}",s)]
def stats(n):
    t=open(D+'page_%04d.txt'%n).read()
    out=collections.Counter(tok(re.sub(r'^\[[a-z -]+\]','',t,flags=re.M)))
    # vision: drop hyphen-broken pieces by removing trailing '-' joins crudely
    vt=[]
    for v in A.V[n]:
        vt.append(v['t'])
    vtext='\n'.join(vt)
    vtext=re.sub(r'-\n','',vtext)
    vis=collections.Counter(tok(vtext))
    miss=sum((vis-out).values()); extra=sum((out-vis).values())
    return miss,extra,sum(vis.values()),sum(out.values())
if __name__=='__main__':
    rows=[]
    for n in range(12,492):
        t=open(D+'page_%04d.txt'%n).read()
        if t.startswith('[page-type] plate'): continue
        m,e,vn,on=stats(n); rows.append((n,m,e,vn,on))
    rows.sort(key=lambda r:-r[1])
    print('pages',len(rows))
    print('top missing-from-output:',[(r[0],r[1],r[3]) for r in rows[:50]])
    rows.sort(key=lambda r:-r[2]); print('top extra:',[(r[0],r[2],r[4]) for r in rows[:30]])
