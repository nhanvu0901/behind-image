"""Contents pages from Vision (geometry-sorted) + hand-read static pages -> static_pages.json"""
import json,re,sys,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import accents as A
V=A.V
MAPC=str.maketrans({'I':'1','l':'1','O':'0','S':'5','B':'8','o':'0','s':'5','r':'1','$':'5','§':'5'})
def fixyear(t):
    t=re.sub(r'\bC\. (?=[\dIlOSBosr$§])','c. ',t)
    t=re.sub(r'\b([Il1])([SsIlO5$§]) (\d\d)\b',lambda m:'1'+m.group(2).translate(MAPC)+m.group(3),t)
    t=re.sub(r'\b(1\d{2}) ([Ilr1])\b',lambda m:m.group(1)+'1',t)
    def f(m):
        tok=m.group(0); d=tok.translate(MAPC)
        return d if re.fullmatch(r"1\d{3}",d) and re.fullmatch(r"[Il1][0-9IlOSBosr$§]{3}",tok) else tok
    return re.sub(r"(?<![A-Za-z0-9])[IlOSBosr0-9$§]{4}(?![A-Za-z0-9])",f,t)
def contents(n):
    items=[]
    for col in (0,1):
        L=[v for v in V[n] if (0 if v['x']+v['w']/2<0.47 else 1)==col]
        L.sort(key=lambda v:(v['y'],v['x']))
        nums=[v for v in L if re.fullmatch(r"\d{1,3}",v['t'].strip())]
        used=set(); head={}
        for nv in nums:
            c=[v for v in L if v is not nv and v not in nums and abs(v['y']-nv['y'])<0.014 and v['x']>nv['x']]
            if c:
                h=min(c,key=lambda v:abs(v['y']-nv['y'])); head[id(h)]=nv['t'].strip(); used.add(id(nv))
        # inline numbers ("458 An inflammatory ...")
        for v in L:
            m=re.match(r"^(\d{1,3}) (\S.+)",v['t'])
            if m and id(v) not in head and (int(m.group(1))-8)%6==0 and 8<=int(m.group(1))<=488:
                head[id(v)]=m.group(1); v['t']=m.group(2)
        blocks=[]; cur=None
        for v in L:
            t=v['t'].strip()
            if id(v) in used: continue
            if t=='Contents': items.append(('h1',t)); continue
            if id(v) in head: cur=[head[id(v)],[t]]; blocks.append(cur)
            elif cur is not None: cur[1].append(t)
        for num,ls in blocks:
            k=next((i for i,x in enumerate(ls) if ':' in x and i>0),None)
            if k is None: hl,ml=ls,[]
            else: hl,ml=ls[:k],ls[k:]
            items.append(('para',num+' '+' '.join(hl)))
            if ml: items.append(('meta',fixyear(' '.join(ml))))
    return items
if __name__=='__main__':
    S={}
    for n in (9,10,11):
        S['%04d'%n]=dict(type='contents',items=contents(n),method='script+vision',read=False,conf='medium',issues=['contents rebuilt from Apple Vision rows; page numbers/years checked against works.json'])
    json.dump(S,open(os.path.dirname(os.path.abspath(__file__))+'/static_pages.json','w'),ensure_ascii=False,indent=1)
    for n in (9,10,11):
        print('==',n)
        for k,t in S['%04d'%n]['items'][:14]: print(k,'|',t)
