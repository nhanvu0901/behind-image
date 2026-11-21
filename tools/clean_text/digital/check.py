import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
def words(t): return len(re.findall(r"\S+",t))
def run(bid):
    doc=pymupdf.open(pdf(bid)); N=len(doc); res=dict(missing=[],soft=[],long=[],outliers=[],pages=N,types=collections.Counter())
    for n in range(1,N+1):
        f=f'{OUT}/{bid}/page_{n:04d}.txt'
        if not os.path.exists(f): res['missing'].append(n); continue
        s=open(f,encoding='utf-8').read()
        lines_=s.split('\n'); 
        if not lines_[0].startswith('[page-type] '): res['missing'].append(f'badhdr{n}')
        else: res['types'][lines_[0].split()[1]]+=1
        if '¬' in s or '­' in s: res['soft'].append(n)
        for l in lines_:
            if len(l)>4000: res['long'].append((n,len(l)))
        body=re.sub(r'^\[page-type\].*\n','',s); body=re.sub(r'\[(caption|credit|note|quote|meta|continues)\]','',body); body=re.sub(r'^#+ ','',body,flags=re.M)
        cw=words(body)
        tw=words(doc[n-1].get_text())
        ratio=cw/tw if tw else None
        ptype=lines_[0].split()[1] if lines_[0].startswith('[page-type]') else ''
        if tw>=60 and (ratio<0.80 or ratio>1.08): res['outliers'].append((n,ptype,tw,cw,round(ratio,2)))
    return res
if __name__=='__main__':
    for bid in sys.argv[1:]:
        r=run(bid); print(bid,r['pages'],dict(r['types']),'missing',r['missing'],'soft',r['soft'],'long',r['long'][:5]); print(' outliers',len(r['outliers']),r['outliers'][:60])
