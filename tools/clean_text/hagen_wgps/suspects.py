import re,sys,collections
sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/hagen_wgps')
import english as EN
D='/Users/nhanvu/Documents/code/behind-the-image/library/clean_text/hagen_wgps/'
txt={}; cnt=collections.Counter()
for n in range(12,492):
    t=open(D+'page_%04d.txt'%n).read(); txt[n]=t
    for w in re.findall(r"[A-Za-zÀ-ÿ]+(?:[’'-][A-Za-zÀ-ÿ]+)*",t): cnt[w.lower()]+=1
def suspects():
    out=collections.defaultdict(set)
    for n,t in txt.items():
        if t.startswith('[page-type] plate'): continue
        for m in re.finditer(r"(?<![A-Za-zÀ-ÿ])([a-z]+(?:[’'-][A-Za-z]+)*)",t):
            w=m.group(1)
            for p in re.split(r"[’'-]",w):
                if len(p)<3 or EN.valid_en(p) or cnt[p]>=3: continue
                out[p].add(n)
    return out
if __name__=='__main__':
    s=suspects(); print(len(s))
    print(' '.join('%s(%s)'%(w,','.join(map(str,sorted(p)[:2]))) for w,p in sorted(s.items())))
