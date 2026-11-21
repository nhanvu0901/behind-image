import re,json,glob,collections,sys
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import layout as Lo
D='/Users/nhanvu/Documents/code/behind-the-image/library/clean_text/hagen_wgps/'
txt={}; cnt=collections.Counter()
for n in range(12,492):
    t=open(D+'page_%04d.txt'%n).read(); txt[n]=t
    for w in re.findall(r"[A-Za-zÀ-ÿ]+(?:[’'-][A-Za-zÀ-ÿ]+)*",t): cnt[w]+=1
low=collections.Counter()
for w,c in cnt.items(): low[w.lower()]+=c
bad={}
for n,t in txt.items():
    for w in re.findall(r"(?<![A-Za-zÀ-ÿ])[a-zà-ÿ]+(?:[’'-][A-Za-zà-ÿ]+)*",t):
        for p in re.split(r"[’'-]",w):
            if len(p)<3: continue
            pl=p.lower()
            if pl in Lo.DICT or pl.rstrip('s') in Lo.DICT or pl in ('ve','ll','re') or any(pl.endswith(x) and pl[:-len(x)] in Lo.DICT for x in ('ed','ing','ly','er','es','ness','ment','d')): continue
            if low[pl]>=3 and (pl in Lo.DICT): continue
            bad.setdefault(pl,set()).add(n)
if __name__=='__main__':
    print(len(bad))
    print(' '.join('%s(%s)'%(w,','.join(map(str,sorted(p)[:2]))) for w,p in sorted(bad.items())))
