"""Stage D: restore accents / confusions from Apple Vision, line by line."""
import json,re,unicodedata
ROOT='/Users/nhanvu/Documents/code/behind-the-image/'
V={}
for line in open(ROOT+'.scratch/clean_hagen/vision.jsonl'):
    d=json.loads(line); n=int(d['image'].split('/p')[-1][:4]); V[n]=d['lines']
CORE=re.compile(r"[A-Za-zÀ-ɏ]+(?:[’'-][A-Za-zÀ-ɏ]+)*")
def nrm(s):
    s=s.replace('ß','ss').replace('Æ','AE').replace('æ','ae').replace('Œ','OE').replace('œ','oe')
    s=unicodedata.normalize('NFKD',s)
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()
def nonascii(s): return any(ord(c)>127 for c in s)
def lev(a,b):
    if abs(len(a)-len(b))>2: return 9
    prev=list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1): cur.append(min(prev[j]+1,cur[-1]+1,prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]
def variants(t):
    t=t.lower(); out={t}
    for x in list(out): out.add(x.replace('fi','ss')); out.add(x.replace('ii','u')); out.add(x.replace('ii','o'))
    for x in list(out): out.add(x.replace('fi','ss').replace('ii','u'))
    for x in list(out): out.add(x.replace('1','l')); 
    return out
LOG=[]  # (page, from, to, kind)
OKCH=set("àáâãäçèéêëìíîïñòóôõöùúûüýÿßœ"+"ÀÁÂÃÄÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝ")
import collections
CAND=collections.defaultdict(collections.Counter)   # t -> Counter(v)
SEEN=collections.Counter()                            # t occurrences where Vision confirms ascii form t
WORDFIX=collections.defaultdict(collections.Counter)
def vision_tokens(n,b,W,H):
    x0,y0,x1,y1=b; hh=y1-y0
    toks=[]
    for v in V.get(n,[]):
        vx0,vy0=v['x']*W,v['y']*H; vx1,vy1=vx0+v['w']*W,vy0+v['h']*H
        oy=min(y1,vy1)-max(y0,vy0)
        if oy>=0.5*min(hh,vy1-vy0) and min(x1,vx1)-max(x0,vx0)>10:
            toks+= [(m.group(0),vx0) for m in CORE.finditer(v['t'])]
    return toks
SPECK=re.compile(r"[\^*°~|\\<>]|(?<=[a-z])'(?=[a-z])")
SPECKFIX={}   # (page, token) -> replacement
def collect_specks(n,text,b,W,H,validf):
    vt=vision_tokens(n,b,W,H)
    vwords=[m.group(0) for v in A_lines(n,b,W,H) for m in re.finditer(r"\S+",v)]
    for m in re.finditer(r"\S+",text):
        tok=m.group(0)
        if not SPECK.search(tok): continue
        core=tok.replace('¬','')
        alnum=re.sub(r"[^A-Za-z\u00c0-\u024f]","",core).lower()
        cand=None
        # try vision whole-word match
        for w in vwords:
            wl=re.sub(r"[^A-Za-z\u00c0-\u024f]","",w).lower()
            if wl and nrm(wl)==nrm(alnum) and len(wl)>=3: cand=w; break
        if cand is None:
            for w in vwords:
                wl=re.sub(r"[^A-Za-z\u00c0-\u024f]","",w).lower()
                if wl and len(wl)>=3 and lev(nrm(wl),nrm(alnum))<=1 and validf(wl): cand=w; break
        if cand is not None:
            # keep trailing punctuation of the text token
            lead=re.match(r"^[^A-Za-z\u00c0-\u024f]*",core).group(0); trail=re.search(r"[^A-Za-z\u00c0-\u024f]*$",core).group(0)
            wcore=re.sub(r"^[^A-Za-z\u00c0-\u024f]+|[^A-Za-z\u00c0-\u024f]+$","",cand)
            SPECKFIX[(n,tok)]=lead+wcore+trail+('¬' if tok.endswith('¬') else '')
def A_lines(n,b,W,H):
    x0,y0,x1,y1=b; hh=y1-y0; out=[]
    for v in V.get(n,[]):
        vx0,vy0=v['x']*W,v['y']*H; vx1,vy1=vx0+v['w']*W,vy0+v['h']*H
        oy=min(y1,vy1)-max(y0,vy0)
        if oy>=0.5*min(hh,vy1-vy0) and min(x1,vx1)-max(x0,vx0)>10: out.append(v['t'])
    return out
SWAPFIX={}
VOCF=None
def collect_swaps(n,text,b,W,H,validf):
    global VOCF
    if VOCF is None:
        import layout as _L
        VOCF=_L.VOC
    vl=A_lines(n,b,W,H)
    vt=[m.group(0) for q in vl for m in CORE.finditer(q)]
    vset=set(vt)
    import difflib
    a=re.sub(r'[^a-z]','',nrm(text.replace('¬',''))); bb=re.sub(r'[^a-z]','',nrm(' '.join(vl)))
    if len(a)<15 or len(bb)<15: return
    if difflib.SequenceMatcher(None,a,bb).ratio()<0.9 or abs(len(vt)-len(text.split()))>2: return
    for m in re.finditer(r"[A-Za-z]{3,}",text):
        t=m.group(0)
        if t in vset: continue
        ft=VOCF[t.lower()]
        if ft>3: continue
        best=None
        for v in vt:
            if v==t or len(v)<3 or nonascii(v): continue
            if v[:1].isupper()!=t[:1].isupper(): continue
            d=lev(v.lower(),t.lower())
            if d<=2 and VOCF[v.lower()]>=30*max(ft,1) and (best is None or VOCF[v.lower()]>VOCF[best.lower()]): best=v
        if best: SWAPFIX[(n,t)]=best
def okaccent(v): return all((ord(c)<=127 or c in OKCH) for c in v)
def collect(n,text,b,W,H,validf):
    """collect-mode: record candidate conversions; return text unchanged"""
    collect_specks(n,text,b,W,H,validf)
    collect_swaps(n,text,b,W,H,validf)
    vt=vision_tokens(n,b,W,H)
    if not vt: return text
    vcores=[t for t,_ in vt]
    for m in CORE.finditer(text):
        t=m.group(0)
        if len(t)<3 or (nonascii(t) and not re.search('[ﬁﬂ]',t)): continue
        if t in vcores: SEEN[t]+=1; continue
        tn=nrm(t); vs=variants(tn); cands=[]
        for v in vcores:
            if not nonascii(v) or not okaccent(v): continue
            vn=nrm(v)
            if vn in vs: cands.append((0,v))
            elif len(vn)>=5 and not validf(t) and lev(vn,tn)<=2: cands.append((lev(vn,tn),v))
        if cands:
            cands.sort(key=lambda x:x[0]); v=cands[0][1]
            if t[:1].isupper() and not v[:1].isupper(): v=v[:1].upper()+v[1:]
            CAND[t][v]+=1
        elif len(t)>=4 and not validf(t):
            best=None
            vtext=' '.join(vcores).lower()
            for i in range(1,len(t)-1):
                a,b=t[:i].lower(),t[i:].lower()
                if (a in ('a','i','of','to','in','on','at','by','or','as','is','it','no','so','he','we','my','be','do','up','us','an') or (len(a)>=3 and validf(a))) and len(b)>=2 and validf(b) and (a+' '+b) in vtext:
                    best=(0,t[:i]+' '+t[i:]); break
            if best is None:
              for v in vcores:
                if v!=t and not nonascii(v) and len(v)>=4 and (v[:1].islower() or (t[:1].isupper() and v.lower() in DICTW)) and validf(v):
                    d=lev(v.lower(),t.lower())
                    if d<=1 or (d==2 and v[0].lower()==t[0].lower()):
                        if best is None or d<best[0]: best=(d,v)
            if best: WORDFIX[t][best[1]]+=1
DICTW=set(x.strip().lower() for x in open('/usr/share/dict/words'))
MAP={}
def VOCF_get(t):
    import layout as _L
    return _L.VOC[t.lower()]
def build_map(validf):
    for t,c in CAND.items():
        v,cnt=c.most_common(1)[0]
        if len(c)>1 and c.most_common(2)[1][1]==cnt: continue
        if validf(t) and not ((cnt>=2 or VOCF_get(t)<=2) and SEEN[t]==0): continue
        if SEEN[t]>cnt: continue
        MAP[t]=v
    for t,c in WORDFIX.items():
        v,cnt=c.most_common(1)[0]
        if SEEN[t]==0: MAP[t]=v
def apply(n,text):
    def rep(m):
        t=m.group(0)
        v=MAP.get(t)
        if v is not None:
            LOG.append((n,t,v,'map')); return v
        return t
    return CORE.sub(rep,text)
