import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
BID='dasal_artcurious'
doc=pymupdf.open(pdf(BID)); N=len(doc)
V=vocab_of(BID,doc)
DICT={x.strip().lower() for x in open('/usr/share/dict/words',errors='ignore')}
LIG={'ﬁ':'fi','ﬂ':'fl','ﬃ':'ffi','ﬄ':'ffl','ﬀ':'ff','ﬅ':'st','ﬆ':'st'}
TR=str.maketrans({'‒':'–',' ':' ',' ':' ',' ':' ',' ':' ',' ':' ',**{k:v for k,v in LIG.items() if len(v)==1}})
def clean(t):
    for k,v in LIG.items(): t=t.replace(k,v)
    return t.translate(TR).strip()
def join_para(ls,log=None):
    out=''
    for t in ls:
        t=clean(t)
        if not t: continue
        if not out: out=t; continue
        if out.endswith('—') or t.startswith('—'): out+=t; continue
        # URL continuation
        last=out.split(' ')[-1]
        if re.match(r'(https?://|www\.)',last) and re.search(r'[-_/=&?#.:%]$',last) and not last.endswith('. '):
            if not re.search(r'\.(html?|pdf|php|aspx?)\.?$',last): out+=t; continue
        out=join_lines([out,t],V,log) if (out[-1] in '-‐' and out[-2:-1].isalpha() and t[:1].isalpha()) else out+' '+t
    return re.sub(r'\s+',' ',out)
CONTENTS={7,8}; NOTES=set(range(237,250)); CREDITS={250}; INDEX=set(range(251,267)); FRONT={2:'front',3:'front',5:'front',6:'front'}
chap=[(w['pdf_pages'][0],w['title']) for w in json.load(open(f'{ROOT}/library/books/{BID}/works.json'))]
meta={}; stats=collections.Counter(); dclog=[]; hylog=[]
struct={}
for n in range(1,N+1):
    L,w,h=lines(doc[n-1]); struct[n]=[l for l in L if l['t'].strip()]
def kind(l):
    s=l['size']; f=l['font']
    if s>=50: return 'drop'
    if s==11.2 and 'Sans' in f and re.match(r'(CHAPTER \d+|INTRODUCTION|EPILOGUE|CONCLUSION)\b',l['t']): return 'label'
    if s==25.0 and 'Type3' in f: return 'title'
    if s==21.2 and 'Type3' in f: return 'sub'
    if s==16.9: return 'h2'
    if s==11.2 and 'Type3' in f: return 'attr'
    if s==11.2 and 'Sans' in f: return 'sans'
    if s==11.2 and 'Serif' in f:
        if l['x0']>=150 and abs((l['x0']+l['x1'])/2-306)<20 and (l['x1']-l['x0'])>60: return 'cap'
        return 'side'
    return 'main'
def paras(ls,drop=None):
    """ls sorted by y; split by indent relative to min margin; returns list of list-of-lines, first_cont"""
    if not ls: return [],False
    xs=collections.Counter(round(l['x0']) for l in ls)
    cand=[x for x,c in xs.items() if c>=2]; margin=min(cand) if cand else min(xs)
    out=[]; first_cont=False; prev=None; start_ind=False
    for l in ls:
        ind=l['x0']-margin>5
        if l['t'].strip().replace(' ','')=='***': out.append([l]); prev=None; start_ind=False; out.append(None); continue
        if prev is None:
            if not ind and out==[] and not drop: first_cont=True
            if out and out[-1] is None: out.pop()
            out.append([l]); start_ind=ind
        elif ind and not (drop and start_ind and l['y0']<drop['y1'] and l['y0']-prev['y0']<=20):
            out.append([l]); start_ind=ind
        else: out[-1].append(l)
        prev=l
    return [o for o in out if o],first_cont
for n in range(1,N+1):
    L=struct[n]; m=dict(type='body',printed_page=None,method='script',read_by_model=False,confidence='high',issues=[],corrections=[])
    p=doc[n-1]; items=[]; cont=False
    if not L:
        m['type']='blank' if page_blank(p) else 'plate'; write_page(BID,n,m['type'],[]); meta[f'{n:04d}']=m; continue
    L=sorted(L,key=lambda l:(l['y0'],l['x0']))
    if n in FRONT or n in CONTENTS:
        m['type']='contents' if n in CONTENTS else 'front'
        blk=collections.OrderedDict()
        for l in L: blk.setdefault(l['blk'],[]).append(l)
        for b,ls in blk.items():
            t=join_para([x['t'] for x in ls])
            if ls[0]['size']>=25 or (n in CONTENTS and ls[0]['size']==16.9): items.append('## '+t if ls[0]['size']==16.9 else '# '+t)
            elif n in CONTENTS: items.append(t)
            else: items.append(t)
        if n in CONTENTS: m['issues'].append('contents wrapped entries re-joined; page 8 may continue the list from page 7')
        write_page(BID,n,m['type'],['\n'.join(items)] if n in CONTENTS else items); meta[f'{n:04d}']=m; continue
    if n in NOTES:
        m['type']='notes'; xs=min(l['x0'] for l in L if kind(l)=='side'); cur=None; first=True
        for l in L:
            k=kind(l)
            if k=='title': items.append('# '+clean(l['t'])); cur=None
            elif k=='h2':
                if items and isinstance(items[-1],str) and items[-1].startswith('## ') and abs(l['y0']-prev_y)<30: items[-1]+=' '+clean(l['t'])
                else: items.append('## '+clean(l['t']))
                cur=None; prev_y=l['y0']
            elif l['size']==15.0 and 'Sans' in l['font']: items.append('## '+clean(l['t'])); cur=None
            else:
                if l['x0']-xs>4 and cur is None and first: m['issues'].append('first note continues from the previous page')
                if l['x0']-xs<=4 or cur is None: cur=[l['t']]; items.append(cur)
                else: cur.append(l['t'])
                first=False
        items=[x if isinstance(x,str) else '[note] '+join_para(x) for x in items]
        ncont=False
        if n+1 in NOTES:
            nl=sorted(struct[n+1],key=lambda l:(l['y0'],l['x0'])); ns=[l for l in nl if kind(l)=='side']
            if ns and nl[0] is ns[0] and ns[0]['x0']-min(l['x0'] for l in ns)>4: ncont=True
        write_page(BID,n,'notes',items,ncont); meta[f'{n:04d}']=m; continue
    if n in CREDITS:
        m['type']='credits'; cur=None
        for l in L:
            k=kind(l)
            if k=='title': items.append('# '+clean(l['t'])); cur=None
            elif re.match(r'^\d+ ',l['t']) and l['x0']<80 or cur is None: cur=[l['t']]; items.append(cur)
            else: cur.append(l['t'])
        items=[x if isinstance(x,str) else '[credit] '+join_para(x) for x in items]
        write_page(BID,n,'credits',items); meta[f'{n:04d}']=m; continue
    if n in INDEX:
        m['type']='index'; xs=min(l['x0'] for l in L if kind(l)=='side'); buf=[]
        for l in L:
            if re.fullmatch(r'(?:[A-Z] ){10,}[A-Z]',l['t'].strip()): m['issues'].append('removed e-book A-Z navigation line'); continue
            if kind(l)=='title': 
                if buf: items.append('\n'.join(buf)); buf=[]
                items.append('# '+clean(l['t']))
            else: buf.append(('    ' if l['x0']-xs>4 else '')+clean(l['t']))
        if buf: items.append('\n'.join(buf))
        write_page(BID,n,'index',items); meta[f'{n:04d}']=m; continue
    if n==267:
        write_page(BID,n,'back',[join_para([l['t'] for l in L])]); m['type']='back'; meta[f'{n:04d}']=m; continue
    # ---- body pages
    K=collections.defaultdict(list)
    for l in L: K[kind(l)].append(l)
    drop=K['drop'][0] if K['drop'] else None
    label=K['label'][0] if K['label'] else None
    opener=label is not None
    # headings
    def merge(ls,gap=45):
        g=[]; 
        for l in ls:
            if g and l['y0']-g[-1][-1]['y0']<=gap: g[-1].append(l)
            else: g.append([l])
        return g
    first_y=L[0]['y0']
    seq=[]  # (y, kind, payload)
    for g in merge(K['title']): seq.append((g[0]['y0'],'title',' '.join(clean(x['t']) for x in g)))
    for g in merge(K['sub']): seq.append((g[0]['y0'],'sub',' '.join(clean(x['t']) for x in g)))
    if label: seq.append((label['y0'],'label',clean(label['t'])))
    # epigraphs (opener only): side lines with y < drop.y0 (or before first main line) and x>=100
    first_main=min([l['y0'] for l in K['main']],default=9999)
    epi=[l for l in K['side']+K['attr'] if opener and l['y0']<min(first_main,drop['y1'] if drop else 9999)]
    for l in epi:
        pass
    side=[l for l in K['side'] if l not in epi]
    # epigraph groups: consecutive side lines, closed by attr
    cur=None
    for l in sorted(epi,key=lambda l:l['y0']):
        k=kind(l)
        if k=='side':
            if cur is None or cur[0]!='q': cur=['q',[]]; seq.append((l['y0'],'epi',cur))
            cur[1].append(l)
        else:
            if seq and seq[-1][1]=='epiattr' and l['y0']-seq[-1][0]<20: seq[-1]=(seq[-1][0],'epiattr',seq[-1][2]+' '+clean(l['t']))
            else: seq.append((l['y0'],'epiattr',clean(l['t'])))
            cur=None
    # captions
    for g in merge(K['cap'],gap=18): seq.append((g[0]['y0'],'cap',join_para([x['t'] for x in g])))
    # paragraphs: main and side
    mp,mfc=paras(K['main'],drop)
    sp,sfc=paras(side,None)
    if drop and mp:
        d=clean(drop['t']); first=mp[0][0]; ft=clean(first['t']); w1=re.match(r"[A-Za-zÀ-ɏ]+",ft); w1s=w1.group(0).lower() if w1 else ''
        letter=re.sub(r'[^A-Za-zÀ-ɏ]','',d); comb=(letter+w1s).lower()
        if letter.upper() in ('A','I') and len(w1s)>=2 and comb not in DICT and (w1s in DICT or V.c.get(w1s,0)>=1): txt=d+' '+ft
        else: txt=d+ft
        f2=dict(first); f2['t']=txt; mp[0][0]=f2; stats['dropcap']+=1; dclog.append((n,txt[:30]))
    elif drop: m['issues'].append('drop cap without text'); m['confidence']='low'
    for ps in mp: seq.append((ps[0]['y0'],'p',join_para([x['t'] for x in ps],hylog)))
    for ps in sp: seq.append((ps[0]['y0'],'sp',join_para([x['t'] for x in ps],hylog)))
    seq.sort(key=lambda s:s[0])
    # build items
    title=None; i=0
    # opener: heading first (title / sub) then meta
    out=[]; pend_label=None
    for y,k,pl in seq:
        if k=='label': pend_label=pl; continue
        if k=='title': out.append('# '+pl+(('\n[meta] '+pend_label) if pend_label else '')); pend_label=None; continue
        if k=='sub':
            if opener and not any(o.startswith('# ') for o in out): out.append('# '+pl+(('\n[meta] '+pend_label) if pend_label else '')); pend_label=None
            else: out.append('## '+pl)
            continue
        if k=='epi': out.append('[quote] '+join_para([x['t'] for x in pl[1]])); continue
        if k=='epiattr': out.append('[quote] '+pl); continue
        if k=='cap': out.append('[caption] '+pl); continue
        if k in ('p','sp'): out.append(pl.replace('* * *','* * *') if pl.replace(' ','')!='***' else '* * *')
    if pend_label: out.insert(0,'# '+pend_label)
    items=out
    if opener: m['issues'].append('chapter opener: drop cap rejoined, CHAPTER label put in [meta]')
    # continuation to next page: last paragraph class must equal first class of next page and next first line not indented
    lastp=[(y,k) for y,k,pl in seq if k in ('p','sp')]
    if lastp and n+1 in struct and (n+1) not in NOTES|CONTENTS|CREDITS|INDEX and struct[n+1]:
        lastk=max(lastp)[1]; lasty=max(lastp)[0]
        later=[k for y,k,pl in seq if y>lasty and k in ('title','sub','epi')]
        nl=sorted(struct[n+1],key=lambda l:(l['y0'],l['x0'])); nk=[(kind(l),l) for l in nl]
        fk,fl=nk[0]
        if fk in ('main','side') and (fk=='main')==(lastk=='p') and 'drop' not in [k for k,_ in nk] and not later:
            xs=collections.Counter(round(l['x0']) for k,l in nk if k==fk); cand=[x for x,c in xs.items() if c>=2]; margin=min(cand) if cand else min(xs)
            if fl['x0']-margin<=5: cont=True
    write_page(BID,n,'body',items,cont); meta[f'{n:04d}']=m
json.dump(meta,open(f'{ROOT}/.scratch/clean_digital/dasal_meta_raw.json','w'))
print(stats); print(collections.Counter(x[0] for x in hylog)); print(dclog)
