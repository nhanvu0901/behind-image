import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
BID='brookehitching_mad'
doc=pymupdf.open(pdf(BID)); N=len(doc)
V=vocab_of(BID,doc)
DICT={x.strip().lower() for x in open('/usr/share/dict/words',errors='ignore')}
SP=str.maketrans({' ':' ',' ':' ',' ':' ',' ':' ',' ':' '})
FRONT={3:'front',5:'front',7:'front',258:'back',259:'back'}
CONTENTS={8,9}; BIB={246,247}; INDEX=set(range(248,254)); CREDITS={256,257}
meta={}; stats=collections.Counter(); dclog=[]; hylog=[]
def clean(t): return t.translate(SP).strip()
def paragraphs(body, drop):
    """body: lines (dicts) in y order. returns list of [text lines], and flag first_is_cont"""
    if not body: return [],False
    xs=collections.Counter(round(l['x0']) for l in body)
    margin=min(x for x,c in xs.items() if c>=2) if any(c>=2 for c in xs.values()) else min(xs)
    paras=[]; prev=None; first_cont=False; start_indented=False
    for idx,l in enumerate(body):
        indent=l['x0']-margin>6
        newp=False
        if prev is None:
            newp=True
            if not indent and not drop: first_cont=True
        else:
            if prev['size']!=l['size'] and abs(prev['size']-l['size'])>0.4: newp=True
            elif indent:
                if drop and start_indented and l['y0']-prev['y0']<=18 and l['y0']<drop['y1']: newp=False
                else: newp=True
        if newp:
            paras.append([l]); start_indented=indent
        else: paras[-1].append(l)
        prev=l
    return paras,first_cont
struct={}
for n in range(1,N+1):
    p=doc[n-1]; L,w,h=lines(p)
    L=[l for l in L if l['t']]
    foot=[l for l in L if l['size']==7.0]
    pp=None
    for l in foot:
        m_=re.search(r'Page\s+(\d+)',l['t'])
        if m_: pp=m_.group(1)
    Lb=[l for l in L if l['size']!=7.0]
    struct[n]=dict(L=Lb,pp=pp,w=w)
def classify(l,ptype):
    s=l['size']
    if s>=35: return 'drop'
    if s in (24.0,24.7,18.0) and 'Granjon' in l['font']:
        if s==18.0 and l['ital']: return 'quote'
        return 'head'
    if s==8.5: return 'note'
    if s==9.0: return 'cap'
    return 'body'
for n in range(1,N+1):
    S=struct[n]; L=S['L']; m=dict(type='body',printed_page=S['pp'],method='script',read_by_model=False,confidence='high',issues=[],corrections=[])
    p=doc[n-1]; items=[]; cont=False
    if not L:
        m['type']='blank' if page_blank(p) else 'plate'
        write_page(BID,n,m['type'],[]); meta[f'{n:04d}']=m; continue
    if n in FRONT or n in CONTENTS:
        m['type']='contents' if n in CONTENTS else FRONT[n]
        L2=sorted(L,key=lambda l:(l['y0'],l['x0']))
        if n in CONTENTS:
            heads=[l for l in L2 if l['size']>=24]; rest=[l for l in L2 if l['size']<24]
            items=['# '+clean(' '.join(l['t'] for l in heads))] if heads else []
            items.append('\n'.join(clean(l['t']) for l in rest))
        else:
            # title page: order by y
            items=[clean(' '.join(l['t'] for l in L2))]
            if n==5: items=[clean(l['t']) for l in sorted(L,key=lambda l:(l['y0']))]
            if n==5: m['issues'].append('title page: stacked display lines, order by y is not the visual order (title page 5 displayed as picture text)')
            if n==5: m['confidence']='medium'
        write_page(BID,n,m['type'],items); meta[f'{n:04d}']=m; continue
    if n in BIB or n in INDEX:
        m['type']='notes' if n in BIB else 'index'
        L2=sorted(L,key=lambda l:(l['y0'],l['x0']))
        heads=[l for l in L2 if l['size']>=24]; rest=[l for l in L2 if l['size']<24]
        if heads: items.append('# '+clean(' '.join(l['t'] for l in heads)))
        if n in BIB:
            xs=min(l['x0'] for l in rest); cur=None
            for l in rest:
                if l['x0']-xs<5 or cur is None: cur=[clean(l['t'])]; items.append(cur)
                else: cur.append(clean(l['t']))
            items=[x if isinstance(x,str) else '[note] '+join_lines(x,V) for x in items]
            # entry continuing from previous page / onto next
            m['issues'].append('bibliography entry may continue across page boundary (first/last lines)') 
        else:
            xs=min(l['x0'] for l in rest)
            items.append('\n'.join(('    ' if l['x0']-xs>5 else '')+clean(l['t']) for l in rest))
        write_page(BID,n,m['type'],items); meta[f'{n:04d}']=m; continue
    if n in CREDITS:
        m['type']='credits'
        L2=sorted(L,key=lambda l:(l['y0'],l['x0']))
        # split: heading, 9.0 credits blocks, 10.0 ack text
        cur=None; out=[]
        for l in L2:
            if l['size']>=24: out.append(('h',[l])); cur=None
            elif l['size']==9.0:
                if cur is None or cur[0]!='c': cur=['c',[]]; out.append(cur)
                cur[1].append(l)
            else:
                if cur is None or cur[0]!='b': cur=['b',[]]; out.append(cur)
                cur[1].append(l)
        for kd,ls in out:
            if kd=='h': items.append('# '+clean(' '.join(x['t'] for x in ls)))
            elif kd=='c':
                t=join_lines([clean(x['t']) for x in ls],V)
                for part in re.split(r'(?<=;) (?=pp?\d)',t): items.append('[credit] '+part)
            else: items.append(join_lines([clean(x['t']) for x in ls],V))
        m['issues'].append('credit entries split at ";" before page references (machine split)')
        write_page(BID,n,'credits',items); meta[f'{n:04d}']=m; continue
    # ---------- body / plate pages
    cls=collections.defaultdict(list)
    for l in L: cls[classify(l,'body')].append(l)
    for k in cls: cls[k].sort(key=lambda l:(l['y0'],l['x0']))
    body=cls['body']; drop=cls['drop'][0] if cls['drop'] else None
    if len(cls['drop'])>1: m['issues'].append('more than one drop-cap-sized line'); m['confidence']='medium'
    heads=cls['head']
    if heads:
        # merge heading lines (stacked) into one heading
        grp=[heads[0]]
        for l in heads[1:]:
            if l['y0']-grp[-1]['y0']<=45: grp.append(l)
            else: items.append('# '+clean(' '.join(x['t'] for x in grp))); grp=[l]
        items.append('# '+clean(' '.join(x['t'] for x in grp)))
    for q in cls['quote']: pass
    if cls['quote']:
        ql=cls['quote']; items.append('[quote] '+clean(' '.join(x['t'] for x in ql)))
        # attribution: a 10.0 italic line shortly after the quote, before the drop cap
        at=[l for l in body if l['ital'] and l['y0']<ql[-1]['y1']+45 and l['size']==10.0]
        for l in at: items.append('[quote] '+clean(l['t'])); body=[b for b in body if b is not l]
    paras,fc=paragraphs(body,drop)
    if drop and paras:
        d=clean(drop['t']); first=paras[0][0]; ft=clean(first['t'])
        w1=re.match(r"[A-Za-zÀ-ɏ]+",ft); w1s=w1.group(0).lower() if w1 else ''
        letter=re.sub(r'[^A-Za-zÀ-ɏ]','',d)
        comb=(letter+w1s).lower()
        if letter.upper() in ('A','I') and len(w1s)>=2 and comb not in DICT and (w1s in DICT or V.c.get(w1s,0)>=1): txt=d+' '+ft
        else: txt=d+ft
        first=dict(first); first['t']=txt; paras[0][0]=first
        stats['dropcap']+=1; dclog.append((n,txt[:40]))
    elif drop and not paras:
        m['issues'].append('drop cap without following text'); m['confidence']='low'
    lg=[]
    for ps in paras:
        items.append(join_lines([clean(x['t']) for x in ps],V,lg))
    hylog.extend(lg)
    # footnotes
    nl=cls['note']
    if nl:
        cur=None
        for l in nl:
            t=clean(l['t']); mm=re.match(r'^(\d{1,2})\s+(.*)',t)
            if mm and (cur is None or True): cur=[mm.group(1),[mm.group(2)]]; items.append(cur)
            elif cur is None: cur=['',[t]]; items.append(cur)
            else: cur[1].append(t)
        for i,it in enumerate(items):
            if isinstance(it,list): items[i]='[note] '+(it[0]+'. ' if it[0] else '')+join_lines(it[1],V)
    # captions
    cl=cls['cap']
    if cl:
        grp=[cl[0]]; res=[]
        for l in cl[1:]:
            if l['y0']-grp[-1]['y0']>16 or abs(l['x0']-grp[-1]['x0'])>20: res.append(grp); grp=[l]
            else: grp.append(l)
        res.append(grp)
        for g in res: items.append('[caption] '+join_lines([clean(x['t']) for x in g],V))
    ptype='body'
    if not body and not paras and not heads:
        ptype='plate'
    m['type']=ptype
    # continuation
    nxt=struct.get(n+1)
    if nxt and (n+1) not in FRONT and (n+1) not in CONTENTS|BIB|INDEX|CREDITS:
        nb=[l for l in nxt['L'] if classify(l,'body')=='body']
        nd=[l for l in nxt['L'] if classify(l,'body')=='drop']
        nh=[l for l in nxt['L'] if classify(l,'body')=='head']
        if nb:
            nb.sort(key=lambda l:(l['y0'],l['x0'])); _,nfc=paragraphs(nb,nd[0] if nd else None)
            if nfc and paras: cont=True
    # first_cont on this page with no previous: nothing
    write_page(BID,n,ptype,items,cont); meta[f'{n:04d}']=m
json.dump(meta,open(f'{ROOT}/.scratch/clean_digital/brooke_meta_raw.json','w'))
print(stats); print(collections.Counter(x[0] for x in hylog)); print(dclog)
