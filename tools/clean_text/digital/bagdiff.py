import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
def toks(t): return collections.Counter(re.findall(r"[^\W_]+",t.lower().replace('­','')))
def run(bid,show=12):
    doc=pymupdf.open(pdf(bid)); rows=[]
    for n in range(1,len(doc)+1):
        s=open(f'{OUT}/{bid}/page_{n:04d}.txt',encoding='utf-8').read()
        body=re.sub(r'^\[page-type\].*\n','',s); body=re.sub(r'\[(caption|credit|note|quote|meta|continues)\]','',body)
        a=toks(doc[n-1].get_text()); b=toks(body)
        extra=b-a; miss=a-b
        rows.append((n,sum(extra.values()),sum(miss.values()),dict(list(extra.items())[:6]),dict(list(miss.items())[:8])))
    tot_e=sum(r[1] for r in rows); tot_m=sum(r[2] for r in rows)
    print(bid,'extra words in clean:',tot_e,'words only in layer:',tot_m)
    rows.sort(key=lambda r:-(r[1]))
    for r in rows[:show]: print('  EXTRA',r[0],r[1],r[3])
    rows.sort(key=lambda r:-(r[2]))
    for r in rows[:show]: print('  MISS ',r[0],r[2],r[4])
for b in sys.argv[1:]: run(b)
