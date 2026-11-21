import re,json,glob,os,collections
ROOT='/Users/nhanvu/Documents/code/behind-the-image/'; D=ROOT+'library/clean_text/hagen_wgps/'
P=json.load(open(ROOT+'.scratch/clean_hagen/lines.json'))
meta=json.load(open(D+'meta.json'))
ok=True
files=sorted(glob.glob(D+'page_*.txt'))
print('files',len(files)); assert len(files)==504
txt={}
for f in files:
    n=int(f[-8:-4]); t=open(f,encoding='utf-8').read(); txt[n]=t
    if '¬' in t: print('SOFT HYPHEN left',n); ok=False
    if max(len(l) for l in t.split('\n'))>4000: print('long line',n)
    if not t.startswith('[page-type] '): print('bad first line',n)
out=[]
for n,t in txt.items():
    typ=t.split('\n')[0].split()[-1]
    if typ!='body': continue
    w=len(re.sub(r'\[[a-z-]+\]|^#+ ','',t,flags=re.M).split())
    lw=sum(len(l['t'].split()) for l in P[n-1]['lines'])
    out.append((n,w,lw,round(w/max(lw,1),2)))
bad=[o for o in out if o[3]<0.75 or o[3]>1.1]
print('word-count outliers (ratio out/layer)',len(bad),bad[:40])
# digits scan
c=collections.Counter()
for n,t in txt.items():
    for m in re.finditer(r"\S*\d\S*",t):
        tok=m.group(0)
        if re.fullmatch(r"[\(“\"]?\d{1,4}(st|nd|rd|th)?([,.;:)”\"]*)?",tok) or re.fullmatch(r"[\d,.\-–/()x]+(cm|m)?[,.;:)]*",tok): continue
        c[(n,tok)]+=1
print('odd digit tokens',len(c)); print(sorted(c)[:120])
yrs=[(n,m.group(0)) for n,t in txt.items() if t.split('\n')[0].endswith('body') for m in re.finditer(r"\b\d{4}\b",t) if not (1000<=int(m.group(0))<=2003)]
print('4-digit non-years',yrs[:60])
