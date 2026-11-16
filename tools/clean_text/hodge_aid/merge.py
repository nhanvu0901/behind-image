"""Merge PDF text layer + Apple Vision lines for hodge_aid into clean page text.
Usage: python3 -I merge.py [pages...]   (writes .scratch/clean_hodge/auto/page_NNNN.txt + auto.json)"""
import sys, re, json, glob, difflib, unicodedata, os, statistics
import pymupdf
ROOT='/Users/nhanvu/Documents/code/behind-the-image'
sys.path.insert(0,ROOT+'/tools/clean_text/hodge_aid')
from vload import load
DICT=set(w.strip().lower() for w in open('/usr/share/dict/words'))
DOC=pymupdf.open(glob.glob(ROOT+'/books/*Art in detail*')[0])
V=load()
import os as _os
V3=load('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hodge/vision3.jsonl') if _os.path.exists('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_hodge/vision3.jsonl') else {}
WORKS=json.load(open(ROOT+'/library/books/hodge_aid/works.json'))

def strip_acc(s): return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
def fold(s):
    s=strip_acc(s).lower()
    s=re.sub(r'[^a-z0-9]','',s)
    return s.translate(str.maketrans('il','11'))
def isword(t):
    t=re.sub(r"[^A-Za-z]",'',strip_acc(t)).lower()
    if not t: return True
    if t in DICT: return True
    for suf in ('s','es','ed','d','ing','ly','er','ers','ist','ists'):
        if t.endswith(suf) and t[:-len(suf)] in DICT: return True
    return False
def fixdig(s):
    s=re.sub(r'(?<![A-Za-z])[Il](?=\d{2,3}\b)','1',s)
    s=re.sub(r'(?<![A-Za-z])[Il](?=[0-9OoIl]{3}\b)','1',s)
    s=re.sub(r'(?<=\d)[Iil](?=\d|\b)','1',s)
    s=re.sub(r'(?<=\d)[Oo](?=\d)','0',s)
    return s

def tl_words(n):
    pg=DOC[n-1]; W,H=pg.rect.width,pg.rect.height
    out=[]
    for x0,y0,x1,y1,w,*_ in pg.get_text('words'):
        out.append(dict(t=w,cx=(x0+x1)/2/W,cy=(y0+y1)/2/H,x0=x0/W,x1=x1/W,y0=y0/H,y1=y1/H))
    return out

DIFFS=[]
LOOK=str.maketrans({'r':'1','i':'1','l':'1','I':'1','g':'9','s':'5','o':'0','O':'0','z':'2','y':'7','S':'5','B':'8'})
def vq(t):
    t=re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])","’",t)
    t=re.sub(r"^'","‘",t); t=re.sub(r"'$","’",t); t=re.sub(r"(?<=[\w.,;!?])'(?=\W|$)","’",t)
    t=re.sub(r"(?<=\s)'","‘",' '+t)[1:] if False else t
    t=t.replace("'","’")
    return t
def numrep(t):
    """repair digit look-alikes in a numeric/ordinal token; returns repaired token or None"""
    m=re.fullmatch(r"([\W]*)([A-Za-z0-9]{1,4}?)((?:st|nd|rd|th|s)?)([\W]*)",t)
    if not m: return None
    pre,core,suf,post=m.groups()
    if re.fullmatch(r"[A-Za-z0-9]{3,4}",core) and sum(c.isdigit() for c in core)>=1 or (suf in('st','nd','rd','th') and re.fullmatch(r"[A-Za-z0-9]{1,2}",core)):
        core2=core.translate(LOOK)
        if core2.isdigit(): return pre+core2+suf+post
    return None
def pick(x,y,z):
    """x=text layer, y=vision1, z=vision2 (or None). returns (token, doubt)"""
    if y in ("×","x") and x in ("x","×"): return "x",False
    cands=[('x',x),('y',y)]+([('z',z)] if z else [])
    nums=[t for _,t in cands if re.search(r'\d',t)]
    if nums:
        rx=numrep(x) or x; ry=numrep(y) or y; rz=(numrep(z) or z) if z else None
        if rx==ry or (rz and rx==rz): return rx,False
        if rz and ry==rz and numrep(y): return ry,False
        if fold(rx)==fold(ry) or (rz and fold(rx)==fold(rz)): return rx,False
        return x,True
    def sc(t,v):
        return v+(1.5 if isword(t) else 0)+(0.4 if t[:1].isupper() and not isword(t) else 0)
    votes={}
    for k,t in cands: votes.setdefault(fold(t),[]).append(t)
    best=None;bs=-1
    for k,ts in votes.items():
        s_=sc(ts[0],len(ts))
        if ts[0] is x or x in ts: s_+=0.2
        if s_>bs: bs=s_;best=ts
    tok=best[0]
    if x in best: tok=x
    sup=len(best)>=2 or isword(tok)
    return tok,not sup

def merge_text(tl,v,v2=None):
    """word-level 3-way merge; returns (text, doubt)"""
    if not tl: return v,True
    if fold(tl)==fold(v) and (v2 is None or fold(v2)==fold(v)) and not re.search(r"[¢~@€|=<>¥£©®§_]",tl):
        pass
    a=tl.split(); b=v.split()
    c=v2.split() if v2 else None
    # map v1 index -> v2 token
    m12={}
    if c:
        sm2=difflib.SequenceMatcher(None,[fold(x) for x in b],[fold(x) for x in c],autojunk=False)
        for op,i1,i2,j1,j2 in sm2.get_opcodes():
            if op=='equal' or (op=='replace' and i2-i1==j2-j1):
                for k in range(i2-i1): m12[i1+k]=c[j1+k]
    sm=difflib.SequenceMatcher(None,[fold(x) for x in a],[fold(x) for x in b],autojunk=False)
    out=[]; doubt=False
    for op,i1,i2,j1,j2 in sm.get_opcodes():
        if op=='equal':
            for k,(x,y) in enumerate(zip(a[i1:i2],b[j1:j2])):
                if x!=y and re.search(r'[¢~@€|=<>¥£©®§_]',x) and not re.search(r'[¢~@€|=<>¥£©®§_]',y): out.append(vq(y))
                elif x!=y and re.search(r"[A-Za-z]'[A-Za-z]",y) and not re.search(r"[A-Za-z][’'‘][A-Za-z]",x): out.append(vq(y))
                elif x!=y and x[:1] in '‘“’”' and y[:1] not in "'\"‘“’”": out.append(x[1:])
                else:
                    z=m12.get(j1+k)
                    # digit tokens: repair look-alikes in text layer when engines agree
                    if re.search(r'\d',x) and numrep(x) and numrep(x)!=x and (fold(x)==fold(y) and False): out.append(x)
                    out.append(x) if True else None
            continue
        A=a[i1:i2]; B=b[j1:j2]
        DIFFS.append((' '.join(A),' '.join(B),' '.join(m12.get(j) or '' for j in range(j1,j2))))
        if len(A)==len(B):
            for k,(x,y) in enumerate(zip(A,B)):
                z=m12.get(j1+k)
                if strip_acc(x).lower()==strip_acc(y).lower() and x!=y and not re.search(r'\d',x):
                    out.append(vq(y) if y!=strip_acc(y) else x); continue
                t,d=pick(x,vq(y),vq(z) if z else None)
                out.append(t); doubt=doubt or d
        elif not B and all(len(re.sub(r'[^A-Za-z]','',t))<=2 and not isword(t) or not re.search(r'[A-Za-z0-9]',t) for t in A):
            continue
        else:
            def vr(T): return sum(isword(t) for t in T)/max(1,len(T))
            C=[A,B]+([[m12.get(j) or '' for j in range(j1,j2)]] if c else [])
            C=[T for T in C if all(T)]
            bt=max(C,key=lambda T:(vr(T),T is A))
            out+=[vq(t) for t in bt] if bt is not A else bt
            doubt=True
    return ' '.join(out),doubt

CAPS=re.compile(r"^[A-Z0-9ÀÁÂÃÄÅÇÈÉÊËÍÎÏÑÓÔÖÚÛÜ’'‘&,.:;\-–\"“”!?()/ ]+$")
def is_caps(t):
    t=re.sub(r'^\d{1,2}\s+','',t.strip())
    return bool(CAPS.match(t)) and sum(c.isalpha() for c in t)>=3

def page_lines(n):
    vl=[dict(l) for l in V[n]]
    tw=tl_words(n); claim={}
    for k,l in enumerate(vl):
        l['y1']=l['y']+l['h']; l['x1']=l['x']+l['w']
        best=None;bi=0.45
        for u in V3.get(n,[]):
            ix=min(l['x1'],u['x']+u['w'])-max(l['x'],u['x']); iy=min(l['y1'],u['y']+u['h'])-max(l['y'],u['y'])
            if ix>0 and iy>0:
                iou=ix*iy/(l['w']*l['h']+u['w']*u['h']-ix*iy)
                if iou>bi: bi=iou;best=u
        l['t2']=best['t'] if best else None
    for i,w in enumerate(tw):
        best=None;bo=0
        for k,l in enumerate(vl):
            if l['x']-0.006<=w['cx']<=l['x1']+0.006:
                ov=min(w['y1'],l['y1'])-max(w['y0'],l['y'])
                ov/= (w['y1']-w['y0']+1e-9)
                if ov>0.5 and ov>bo: best=k;bo=ov
        if best is not None: claim.setdefault(best,[]).append(w)
    claimed=set(id(w) for ws in claim.values() for w in ws)
    for k,l in enumerate(vl):
        ws=sorted(claim.get(k,[]),key=lambda w:w['cx'])
        l['tl']=' '.join(w['t'] for w in ws)
    orphans=[w['t'] for w in tw if id(w) not in claimed]
    return vl,orphans

def clean_line(l):
    v=l['t']; tl=l['tl']
    l['caps']=is_caps(v)
    if l['caps']:
        if tl and fold(tl)==fold(v): l['txt']=v; l['doubt']=False
        else: l['txt']=v; l['doubt']=l['c']<0.5
    else:
        t,d=merge_text(tl,fixdig(v),fixdig(l['t2']) if l.get('t2') else None) if tl else (vq(fixdig(v)),True)
        l['txt']=t; l['doubt']=d
        if re.search(r'\d\s*[x×]\s*\d|\d\s*cm\b|\bcm\b|\bin\.\)',v):
            v1=vq(fixdig(v)); v2=vq(fixdig(l['t2'])) if l.get('t2') else None
            l['txt']=v1; l['doubt']=bool(v2) and fold(v1)!=fold(v2) or not v2
    return l

def fixq(s):
    if s.count('“')!=s.count('”'):
        s=s.replace('“','‘').replace('”','’')
    return s

def endash(s):
    s=re.sub(r'(?<=\d)-(?=\d)','–',s)
    return s

DROP_LABELS=re.compile(r'^(IN DETAIL|TECHNIQUE|IN DETAIL ?\d*)$')
YR=re.compile(r"^(c\. ?)?[0-9IlOo]{3,4}([-–][0-9]{2,4})?$")
TERM=re.compile(r"[.!?:'’”\"”)]$")

def find_title(L):
    """L: cleaned lines sorted by y (top 0.3). Returns (title_lines, artist_line, year_line) or None"""
    top=[l for l in L if l['y']<0.3 and l['c']>0.35]
    for i,l in enumerate(top[:7]):
        if i>=2 and YR.match(fixdig(l['t']).strip().replace('–','-')) is None and not re.match(r'^(c\. ?)?[0-9IlOo]{3,4}',l['t']): continue
        if i>=2 and len(l['t'])<24 and is_caps(top[i-1]['t']) and abs(top[i-1]['x']-top[i-2]['x'])<0.03 and top[i-2]['h']>=0.017 and is_caps(top[i-2]['t']):
            art=top[i-1]; tl=[]; k=i-2
            while k>=0 and is_caps(top[k]['t']) and top[k]['h']>=0.017 and abs(top[k]['x']-art['x'])<0.03:
                tl.insert(0,top[k]); k-=1
            return tl,art,l
    return None

def build_page(n,mode='entry'):
    vl,orph=page_lines(n)
    info=dict(issues=[],doubts=0)
    DIFFS.clear()
    lines=[clean_line(l) for l in vl]
    foot=[];body=[]
    ft=find_title(sorted([l for l in lines if l['y']<0.955],key=lambda l:(l['y'],l['x']))) if mode=='entry' else None
    tused=set()
    if ft: tused=set(id(l) for l in ft[0])|{id(ft[1]),id(ft[2])}
    for l in lines:
        if id(l) in tused: body.append(l); continue
        t=l['t'].strip()
        if l['y']>0.955 or (l['y']<0.012 and l['h']<0.012): foot.append(l); continue
        if DROP_LABELS.match(t): continue
        if l['c']<0.5 and not l['tl'] : continue
        alpha=sum(c.isalpha() for c in t)
        if not l['caps'] and alpha<3: continue
        if l['c']<0.4 and alpha<8: continue
        body.append(l)
    body.sort(key=lambda l:(l['y'],l['x']))
    out=[]
    # printed page number
    pn=None
    for l in foot:
        if l['x']<0.07 or l['x1']>0.93:
            s=fixdig(l['t']).replace(' ','')
            m=re.fullmatch(r'\d{1,3}',s)
            if m: pn=m.group(0)
    info['printed_page_seen']=pn
    # title
    meta_lines=[]
    if ft:
        tl,art,yr=ft
        title=' '.join(l['t'].strip() for l in tl)
        info['entry']=dict(title=title,artist=art['t'].strip(),year=endash(fixdig(yr['t'].strip())))
        out.append('# '+title); out.append('[meta] '+art['t'].strip()); out.append('[meta] '+endash(fixdig(yr['t'].strip())))
        used=set(id(l) for l in tl)|{id(art),id(yr)}
        body=[l for l in body if id(l) not in used and not (l['y']<yr['y'] and l['x']<yr['x1']+0.3 and False)]
    if not body and not ft and mode=='entry':
        return 'plate',['[page-type] plate'],info,orph
    # columns: anchors from non-caps lines
    txt=[l for l in body if not l['caps']]
    xs=sorted(l['x'] for l in txt)
    anchors=[]
    for x in xs:
        if anchors and x-anchors[-1][-1]<0.035 and x-anchors[-1][0]<0.06: anchors[-1].append(x)
        else: anchors.append([x])
    anchors=[min(a) for a in anchors if len(a)>=2] or [0.0]
    def col(l):
        c=0
        for i,a in enumerate(anchors):
            if a<=l['x']+0.012: c=i
        return c
    for l in body: l['col']=col(l)
    # merge multi-line headings
    items=[]
    b2=sorted(body,key=lambda l:(l['col'],l['y']))
    i=0
    while i<len(b2):
        l=b2[i]
        if mode=='entry' and l['caps'] and l['h']<0.03:
            parts=[l]
            while i+1<len(b2) and b2[i+1]['caps'] and b2[i+1]['col']==l['col'] and abs(b2[i+1]['x']-l['x'])<0.03 and b2[i+1]['y']-parts[-1]['y']<0.032 and not TERM.search(parts[-1]['t'].strip()):
                parts.append(b2[i+1]); i+=1
            h=' '.join(re.sub(r'^\d{1,2}\s+','',p['txt'].strip()) for p in parts)
            items.append(dict(kind='H',col=l['col'],y=l['y'],x=l['x'],text=h,lines=parts,doubt=any(p['doubt'] for p in parts)))
        else:
            items.append(dict(kind='T',col=l['col'],y=l['y'],x=l['x'],line=l,lines=[l]))
        i+=1
    # blocks
    dys=[]
    prev=None
    for it in items:
        if it['kind']=='T' and prev and prev['kind']=='T' and prev['col']==it['col']:
            d=it['y']-prev['y']
            if 0<d<0.04: dys.append(d)
        prev=it
    pitch=statistics.median(dys) if dys else 0.02
    blocks=[];cur=None;prev=None
    for it in items:
        if it['kind']=='H':
            blocks.append(dict(head=it,lines=[],col=it['col'],y=it['y'],x=it['x'])); cur=blocks[-1]; prev=it; continue
        new=False
        if cur is None or cur['col']!=it['col']: new=True
        elif prev['kind']=='T' and it['y']-prev['y']>1.5*pitch: new=True
        elif prev['kind']=='H' and False: new=True
        if new:
            cur=dict(head=None,lines=[],col=it['col'],y=it['y'],x=it['x']); blocks.append(cur)
        cur['lines'].append(it['line']); prev=it
    # tag captions
    for b in blocks:
        b['caption']=False
        if b['head'] is None and b['lines']:
            t=' '.join(l['txt'] for l in b['lines'])
            if len(b['lines'])<=4 and not TERM.search(t.strip()) and re.search(r'\b(1[0-9]{3}|20[0-2][0-9])\b',t) :
                b['caption']=True
            elif len(b['lines'])<=4 and re.search(r'\d+ x \d+ cm',t): b['caption']=True
    headed=[b for b in blocks if b['head']]
    if headed:
        lead=[b for b in blocks if not b['head'] and b['y']<0.1]
        rest=[b for b in blocks if not b['head'] and b['y']>=0.1]
        order=sorted(lead,key=lambda b:(b['col'],b['y']))+sorted(headed,key=lambda b:(b['col'],b['y']))+sorted(rest,key=lambda b:(b['col'],b['y']))
    else:
        order=sorted(blocks,key=lambda b:(b['col'],b['y']))
    # emit
    def paras(lines):
        P=[];cur=[];base=min(l['x'] for l in lines)
        for l in lines:
            if cur and l['x']>base+0.012: P.append(cur);cur=[]
            cur.append(l['txt'])
        if cur:P.append(cur)
        res=[]
        for p in P:
            s=''
            for k,t in enumerate(p):
                t=t.strip()
                if not s: s=t; continue
                if s.endswith('-') :
                    pre=re.search(r'([A-Za-z]+)-$',s)
                    nxt=re.match(r'[A-Za-z]+',t)
                    if re.search(r'\d-$',s) and re.match(r'\d',t): s=s[:-1]+'–'+t
                    elif pre and nxt and (pre.group(1)+nxt.group(0)).lower() in DICT and not (pre.group(1).lower() in DICT and nxt.group(0).lower() in DICT and False): s=s[:-1]+t
                    else: s=s+t
                else: s=s+' '+t
            res.append(fixq(endash(s)))
        return res
    if mode=='index':
        for b in sorted(blocks,key=lambda b:(b['col'],b['y'])):
            for l in b['lines']: out.append(endash(l['txt'].strip()))
        order=[]
    if mode=='glossary':
        order=sorted(blocks,key=lambda b:(b['col'],b['y']))
        for b in order:
            ls_=b['lines']; t0=ls_[0]['txt'].strip()
            if len(ls_)>=2 and len(t0)<48 and not TERM.search(t0) and t0[:1].isupper() and ls_[1]['txt'].strip()[:1].isupper():
                out.append(''); out.append('## '+t0); rest=ls_[1:]
            else: rest=ls_
            for p in paras(rest): out.append(''); out.append(p)
        order=[]
    for b in order:
        if b['head']:
            out.append(''); out.append('## '+b['head']['text'])
            if b['head']['doubt']: info['doubts']+=1
        if b['lines']:
            P=paras(b['lines'])
            for p in P:
                out.append('')
                out.append(('[caption] ' if b['caption'] else '')+p)
    for b in blocks:
        for l in b['lines']:
            if l['doubt']: info['doubts']+=1
    res=[x for x in out]
    # collapse
    txt='\n'.join(res)
    txt=re.sub(r'\n{3,}','\n\n',txt).strip('\n')
    lastp=[x for x in txt.split('\n') if x.strip() and not x.startswith(('#','[meta]'))]
    typ='body'
    ls=['[page-type] '+typ]+txt.split('\n')
    if lastp and not TERM.search(lastp[-1].strip()) and not lastp[-1].startswith('[caption]'):
        ls.append('[continues]')
    info['orphans']=orph; info['diffs']=list(DIFFS)
    return typ,ls,info,orph

MODES={n:'text' for n in list(range(1,14))+[59,113,159,193,295,435,436,439,440]}
MODES.update({n:'glossary' for n in range(424,428)}); MODES.update({n:'index' for n in range(428,435)})
if __name__=='__main__':
    pages=[int(a) for a in sys.argv[1:]] or range(1,441)
    os.makedirs(ROOT+'/.scratch/clean_hodge/auto',exist_ok=True)
    allinfo={}
    for n in pages:
        typ,ls,info,orph=build_page(n,MODES.get(n,'entry'))
        open(f'{ROOT}/.scratch/clean_hodge/auto/page_{n:04d}.txt','w').write('\n'.join(ls)+'\n')
        info['type']=typ; allinfo[n]=info
        if len(pages)<=6: print('\n'.join(ls)); print(info)
    json.dump(allinfo,open(ROOT+'/.scratch/clean_hodge/auto/info.json','w'),indent=0,default=str)
