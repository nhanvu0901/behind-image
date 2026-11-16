"""Stage C: layout analysis of text-layer lines -> per-page item lists.
Items: dict(kind, text, ...) kinds: h1 meta h2 para note junk
"""
import json,re,collections,statistics
import numpy as np
from PIL import Image
ROOT='/Users/nhanvu/Documents/code/behind-the-image/'
P=json.load(open(ROOT+'.scratch/clean_hagen/lines.json'))
WORKS=json.load(open(ROOT+'library/books/hagen_wgps/works.json'))
OPEN={w['pdf_pages'][0]:w for w in WORKS}
DICT=set(x.strip().lower() for x in open('/usr/share/dict/words'))
SOFT='¬'
SHORT=set('a i an as at be by do go he if in is it me my no of on or so to up us we am ox oh ah'.split())

def tok_alpha(t): return re.sub(r"[^A-Za-z]","",t)
# vocabulary from the book (joined across soft hyphens, lines only)
def build_vocab():
    c=collections.Counter()
    for p in P:
        if p['page']<12 or p['page']>491: continue
        for l in p['lines']:
            for t in l['t'].replace(SOFT,'').split():
                a=tok_alpha(t).lower()
                if len(a)>1: c[a]+=1
    return c
VOC=build_vocab()
def valid(t):
    a=tok_alpha(t).lower()
    if not a: return True
    return a in DICT or VOC[a]>=4 or a+'s' in DICT or a.rstrip('s') in DICT or (a.endswith('ed') and a[:-2] in DICT) or (a.endswith('ing') and a[:-3] in DICT)

_img={}
def page_img(n):
    if n not in _img:
        _img.clear(); _img[n]=np.array(Image.open(ROOT+'.scratch/clean_hagen/img/p%04d.png'%n).convert('L')).astype(float)
    return _img[n]
def ink(n,l):
    im=page_img(n); s=1600/P[n-1]['w']
    x0,y0,x1,y1=[int(v*s) for v in l['b']]
    a=im[max(y0,0):y1,max(x0,0):x1]
    if a.size==0: return 0.,0.
    bg=np.percentile(a,85); m=a<bg-70
    return float(m.mean()), float(m.sum()/(len(l['t'])+1)/s/s)

def propername(x):
    a=re.sub(r"[^A-Za-z]","",x)
    return len(a)>=4 and a[0].isupper() and a[1:].islower() and re.search('[aeiouy]',a.lower()) is not None
def runlen(n,l):
    im=page_img(n); sc=1600/P[n-1]['w']
    x0,y0,x1,y1=[int(v*sc) for v in l['b']]
    a=im[max(y0,0):y1,max(x0,0):x1]
    if a.size==0: return 0.
    bg=np.percentile(a,85); m=(a<bg-70).astype(np.int8)
    starts=((m[:,1:]==1)&(m[:,:-1]==0)).sum()+m[:,0].sum()
    return float(m.sum()/max(starts,1))
def is_junk(l):
    t=l['t'].replace(SOFT,'-').strip()
    if l['sp'] and all(x[5]>=20 for x in l['sp'] if re.search('[A-Za-z]',x[0])) and re.search('[A-Za-z]{3}',t):
        ws=t.split()
        if sum(ch.isalpha() or ch in " '’-!?,.:\"“”" for ch in t)/len(t)>=0.95 and all((len(tok_alpha(w))>=2 or w.lower() in ('a','i','—','-')) and re.fullmatch(r"[\"“(]?[A-Za-z][a-z'’-]*[,.:!?\"”)-]*|[A-Z0-9'’-]+[,.:!?]*|[-—–]",w) for w in ws): return False
    toks=[x for x in t.split() if re.search(r'[A-Za-z]',x)]
    if len(re.sub(r'[^A-Za-z0-9]','',t))<=2 and not re.search(r'[A-Za-z]{2}',t): return True
    sym=sum(1 for ch in t if not (ch.isalnum() or ch in " .,;:'’‘“”\"!?()-–—/&"))
    if sym/max(len(t),1)>0.12: return True
    if len(toks)>=3:
        v=sum(((valid(x) or propername(x)) and (len(tok_alpha(x))>2 or tok_alpha(x).lower() in SHORT)) for x in toks)/len(toks)
        if v<0.6: return True
    elif len(toks)<=2:
        for x in toks:
            a=tok_alpha(x)
            if valid(x) or x[:1].isupper(): continue
            if len(a)>=4 and re.search('[aeiouy]',a.lower()) and sum(ch.isalpha() for ch in x)/len(x)>=0.7: continue
            return True
    return False

def union(sp):
    return [min(x[1] for x in sp),min(x[2] for x in sp),max(x[3] for x in sp),max(x[4] for x in sp)]
def split_line(n,l):
    sp=l['sp']
    smallpresent=any(x[5]<12 and re.search('[A-Za-z]{2}',x[0]) for x in sp)
    iscap=lambda x: smallpresent and x[5]>=25 and len(x[0].strip())==1 and x[0].strip().isalpha()
    caps=[i for i,x in enumerate(sp) if iscap(x)]
    hv=lambda x: x[5]>=11.8 and len(re.sub(r'[^A-Za-z]','',x[0]))>=2 and not iscap(x)
    # heading run: leading spans (before cap or first body span) that are large
    i=0
    while i<len(sp) and (hv(sp[i]) or (not sp[i][0].strip() and i+1<len(sp) and hv(sp[i+1]))): i+=1
    if caps and i==0:
        body=[x for k,x in enumerate(sp) if k not in caps and x[0].strip()]
        if body:
            l=dict(l); b=l['b']; l['b']=[b[0],min(x[2] for x in body),b[2],max(x[4] for x in body)]
    if i==0 or i==len(sp): return [l]
    rest=sp[i:]
    # only split when something body-like (cap or small text) follows
    rest=[x for x in rest]
    if not any(x[0].strip() for x in rest): return [l]
    if not any(iscap(x) or x[5]<11 for x in rest): return [l]
    hd=dict(l); hd['sp']=sp[:i]; hd['t']=''.join(x[0] for x in sp[:i]).strip(); hd['b']=union([x for x in sp[:i] if x[0].strip()])
    hd['d'],hd['pc']=ink(n,hd)
    if not (hd['d']>=0.2 and hd['pc']>=13): return [l]
    hd['forcehead']=True
    bd=dict(l); bd['sp']=rest; bd['t']=''.join(x[0] for x in rest).rstrip(); bd['b']=union([x for x in rest if x[0].strip()])
    if caps:
        body=[x for x in rest if x[0].strip() and not iscap(x)]
        if body: bd['b']=[bd['b'][0],min(x[2] for x in body),bd['b'][2],max(x[4] for x in body)]
    return [hd,bd]

def classify_page(n):
    """return dict(type, items, printed_page, flags)"""
    p=P[n-1]; L=[dict(l) for l in p['lines']]
    W=p['w']; H=p['h']
    out=dict(items=[],printed=None,flags=[],junk=0)
    # printed page number
    foot=[l for l in L if re.fullmatch(r"\d{1,3}",l['t'].strip()) and l['b'][1]>H*0.94 and (l['b'][0]<80 or l['b'][2]>W-80)]
    if foot:
        out['printed']=foot[0]['t'].strip(); L=[l for l in L if l not in foot]
    keep=[]
    for l in L:
        if is_junk(l): out['junk']+=1
        else: keep.append(l)
    L=keep
    L2=[]
    for l in L:
        L2+=split_line(n,l)
    L=L2
    for l in L:
        if 'd' not in l: l['d'],l['pc']=ink(n,l)
        l['rl']=runlen(n,l)
        l['hascap']=any(x[5]>=25 and len(x[0].strip())==1 and x[0].strip().isalpha() for x in l['sp']) and any(x[5]<12 and re.search('[A-Za-z]{2}',x[0]) for x in l['sp'])
    return L,out

def clusters_x0(L,gap=60):
    xs=sorted(set(round(l['b'][0]) for l in L))
    cl=[[xs[0]]]
    for x in xs[1:]:
        if x-cl[-1][-1]>gap: cl.append([x])
        else: cl[-1].append(x)
    return [(c[0],c[-1]) for c in cl]

def assemble(n):
    L,out=classify_page(n)
    p=P[n-1]; W=p['w']
    items=[]
    if not L: return items,out,L
    head=[]
    # --- opening header
    bigf=lambda l: l['sp'] and all(x[5]>=22 for x in l['sp'] if re.search('[A-Za-z]',x[0])) and re.search('[A-Za-z]',l['t']) and re.search('[A-Za-z]{3}',l['t']) and l['d']>=0.14
    if any(bigf(l) for l in L):
        big=[l for l in L if bigf(l)]
        if big:
            big.sort(key=lambda l:l['b'][1])
            hb=big[0]['b'][1]; hl=[l for l in big if l['b'][1]-big[-1]['b'][1]<=0 or True]
            # consecutive big lines
            grp=[big[0]]
            for l in big[1:]:
                if l['b'][1]-grp[-1]['b'][3]<8: grp.append(l)
            above=[l for l in L if l['b'][3]<=grp[0]['b'][1]+6 and l['b'][1]>grp[0]['b'][1]-60 and l not in grp and l['d']>=0.2 and l['pc']>=11 and all(11<=x[5]<=21 for x in l['sp'] if re.search('[A-Za-z]',x[0]))]
            above.sort(key=lambda l:l['b'][1])
            axis=None
            if above:
                axis=(above[-1]['b'][0]+above[-1]['b'][2])/2
            items.append(dict(kind='h1',text=' '.join(l['t'] for l in grp)))
            if above:
                items.insert(0,dict(kind='meta',text=' '.join(l['t'] for l in above)))
                items[0],items[1]=items[1],items[0]
            used=set(map(id,grp+above)); head=grp+above
            # intro: centred lines below the headline
            if axis is not None:
                y=grp[-1]['b'][3]; intro=[]
                for l in sorted(L,key=lambda l:l['b'][1]):
                    if id(l) in used or l['b'][1]<y-2: continue
                    c=(l['b'][0]+l['b'][2])/2
                    if abs(c-axis)<14 and (l['b'][2]-l['b'][0])<380 and (not intro or l['b'][1]-max(x['b'][3] for x in intro)<40):
                        intro.append(l)
                if intro and max(l['b'][2]-l['b'][0] for l in intro)<225: intro=[]
                if intro:
                    items.append(dict(kind='para',text=join_lines([l['t'] for l in intro])))
                    head+=intro
            L=[l for l in L if id(l) not in set(map(id,head))]
    if not L: return items,out,L
    # --- column order
    cols=clusters_x0(L)
    drop=set()
    for (a,b) in cols:
        cl=[l for l in L if a<=round(l['b'][0])<=b]
        if len(cl)<=2 and all(len(l['t'].split())<=3 for l in cl) and not any(l['d']>=0.215 for l in cl):
            drop|=set(map(id,cl))
    if drop:
        out['junk']+=len(drop); L=[l for l in L if id(l) not in drop]
        if not L: return items,out,L
        cols=clusters_x0(L)
    def colof(l):
        x=round(l['b'][0])
        for i,(a,b) in enumerate(cols):
            if a<=x<=b: return i
    for l in L: l['col']=colof(l)
    ordered=sorted(L,key=lambda l:(l['col'],l['b'][1]))
    # per column stats
    cs={}
    for i in range(len(cols)):
        cl=[l for l in ordered if l['col']==i]
        if not cl: continue
        x0s=sorted(l['b'][0] for l in cl); x1s=sorted(l['b'][2] for l in cl)
        cs[i]=dict(base=x0s[len(x0s)//5],R=x1s[int(len(x1s)*0.8)])
    # headings (sans bold): high density and ink per char
    for l in ordered:
        l['head']= l.get('forcehead',False) or (l['rl']>=5.0 and l['d']>=0.15 and not l['hascap'] and len(l['t'])<=70)
    # build paragraphs
    cur=None; prev=None; pend=[]
    def flush():
        nonlocal cur
        if cur: items.append(cur); cur=None
    def emit_pend():
        nonlocal pend
        for h in pend: items.append(h)
        pend=[]
    TERM=re.compile(r'[.!?”"’)]\d*$')
    for l in ordered:
        c=cs[l['col']]
        l['t']=l['t'].strip()
        if not l['t']: continue
        if l['head']:
            if pend and prev is not None and prev['head'] and l['b'][1]-prev['b'][3]<14 and l['col']==prev['col']:
                pend[-1]['lines'].append(l['t'])
            elif cur and cur['kind']=='h2' and prev is not None and prev['head'] and l['b'][1]-prev['b'][3]<14 and l['col']==prev['col']:
                cur['lines'].append(l['t'])
            else:
                lastp=cur
                if lastp is None and items and items[-1]['kind']=='para': lastp=items[-1]
                incomplete = lastp is not None and lastp['kind']=='para' and not TERM.search(lastp['lines'][-1].strip() if 'lines' in lastp else lastp['text'].strip())
                if incomplete:
                    pend.append(dict(kind='h2',lines=[l['t']]))
                else:
                    flush(); cur=dict(kind='h2',lines=[l['t']])
            prev=l; continue
        indent=l['b'][0]-c['base']
        if pend:
            lastp=cur if cur is not None else (items[-1] if items and items[-1]['kind']=='para' else None)
            cont = l['t'][:1].islower() and indent<6 and lastp is not None
            if cont:
                if cur is None: cur=items.pop(); cur.setdefault('lines',[cur.pop('text')] if 'text' in cur else [])
                cur['lines'].append(l['t']); prev=l; continue
            else:
                flush(); emit_pend()
        newp=False
        if cur is None or cur['kind']!='para': newp=True
        else:
            prevshort = prev['b'][2] < c['R']-8 if prev['col']==l['col'] else False
            endp = bool(TERM.search(prev['t'].strip()))
            if 6<=indent<=22 and (prevshort or endp or prev['col']!=l['col']): newp=True
            if prevshort and endp and prev['col']==l['col'] and l['b'][1]-prev['b'][3]>2 and indent>=4: newp=True
        if newp:
            if cur is not None and cur['kind']=='para' and pend: emit_pend()
            flush(); cur=dict(kind='para',lines=[l['t']],first_indent=indent)
        else: cur['lines'].append(l['t'])
        prev=l
    flush(); emit_pend()
    for it in items:
        if 'lines' in it:
            it['text']=join_lines(it['lines']); del it['lines']
    return items,out,L

def join_lines(ls):
    s=''
    for t in ls:
        t=t.rstrip()
        if not s: s=t; continue
        if s.endswith(SOFT): s=s[:-1]+t.lstrip()
        elif s.endswith('-') and re.search(r'[A-Za-z]-$',s) and t[:1].islower() and False: s+=t
        else: s+=' '+t.lstrip()
    return s
