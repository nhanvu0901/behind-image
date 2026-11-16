import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
BID='grovier_nws'
doc=pymupdf.open(pdf(BID)); N=len(doc)
V=vocab_of(BID,doc)
FRONT={1,3,10}; CONTENTS={5,6,7,8}; NOTES=set(range(381,397)); CREDITS=set(range(397,406)); INDEX=set(range(406,422)); BACK={422,423,425}
CAPMAX=11.35
meta={}; stats=collections.Counter(); hylog=[]
struct={}
for n in range(1,N+1):
    L,w,h=lines(doc[n-1]); struct[n]=sorted([l for l in L if l['t'].strip()],key=lambda l:(l['y0'],l['x0']))
def ends_term(t): return bool(re.search(r"[.!?:;\"”’)\]]\s*$",t))
def build_paras(body):
    paras=[]; prev=None
    for l in body:
        if prev is not None and (l['size']!=prev['size'] or l['y0']-prev['y0']>=1.65*l['size'] or l['x0']-prev['x0']>40 and False):
            paras.append([l])
        elif prev is None: paras.append([l])
        else: paras[-1].append(l)
        prev=l
    return paras
def body_items(L,m):
    """returns list of (kind,text) and info"""
    out=[]
    heads=[l for l in L if l['bold'] and l['size']>=18]
    rest=[l for l in L if not (l['bold'] and l['size']>=18)]
    bodyl=[l for l in rest if l['size']>CAPMAX]
    small=[l for l in rest if l['size']<=CAPMAX]
    margin=min([l['x0'] for l in bodyl],default=77)
    seq=[]
    if heads:
        g=[[heads[0]]]
        for l in heads[1:]:
            if l['y0']-g[-1][-1]['y0']<=40: g[-1].append(l)
            else: g.append([l])
        for gg in g: seq.append((gg[0]['y0'],'h',join_lines([x['t'] for x in gg],V)))
    for ps in build_paras(bodyl):
        t=join_lines([x['t'] for x in ps],V,hylog)
        first=ps[0]
        kind='p'
        # centred short parenthetical line right after a title -> meta
        if heads and len(ps)==1 and t.startswith('(') and abs((first['x0']+first['x1'])/2-306)<40 and first['y0']>heads[-1]['y0'] and first['y0']-heads[-1]['y1']<60: kind='meta'
        seq.append((first['y0'],kind,t,ps))
    # small: split into groups; verse if indented and directly under a body paragraph
    groups=[]
    for l in small:
        if groups and l['y0']-groups[-1][-1]['y0']<1.6*l['size'] and abs(l['size']-groups[-1][-1]['size'])<0.6 and abs(l['x0']-groups[-1][-1]['x0'])<45: groups[-1].append(l)
        else: groups.append([l])
    bl_by_y=sorted(bodyl,key=lambda l:l['y0'])
    for g in groups:
        seq.append((g[0]['y0'],'cap',join_lines([x['t'] for x in g],V),g))
    seq.sort(key=lambda s:s[0])
    # verse: indented small group directly below a body paragraph (or another verse line)
    prevk=None; prev=None; res=[]
    for it in seq:
        if it[1]=='cap' and it[3][0]['x0']>=110 and it[3][0]['x0']>margin+35 and prevk in ('p','quote') and it[0]-prev[3][-1]['y1']<45:
            for l in it[3]: res.append((l['y0'],'quote',l['t'],[l]))
            prevk='quote'; prev=res[-1]
        else:
            res.append(it); prevk=it[1]; prev=it
    seq=res
    return seq,bodyl,small
for n in range(1,N+1):
    L=struct[n]; m=dict(type='body',printed_page=None,method='script',read_by_model=False,confidence='high',issues=[],corrections=[])
    p=doc[n-1]; items=[]; cont=False
    if not L:
        m['type']='blank' if page_blank(p) else 'plate'; write_page(BID,n,m['type'],[]); meta[f'{n:04d}']=m; continue
    if n in FRONT:
        m['type']='front'; items=[join_lines([l['t'] for l in L],V)] if False else ['\n'.join(l['t'] for l in L)]
        write_page(BID,n,'front',items); meta[f'{n:04d}']=m; continue
    if n in CONTENTS:
        m['type']='contents'; heads=[l for l in L if l['bold']]
        for l in L:
            if l['bold']: items.append('# '+l['t'])
        rest=[l for l in L if not l['bold']]
        blocks=collections.OrderedDict()
        for l in rest: blocks.setdefault(l['blk'],[]).append(l)
        lines_=[join_lines([x['t'] for x in ls],V) for ls in blocks.values()]
        items.append('\n'.join(lines_))
        write_page(BID,n,'contents',items); meta[f'{n:04d}']=m; continue
    if n in NOTES:
        m['type']='notes'; blocks=collections.OrderedDict()
        for l in L: blocks.setdefault(l['blk'],[]).append(l)
        for b,ls in blocks.items():
            if ls[0]['bold'] and ls[0]['size']>=23: items.append('# '+join_lines([x['t'] for x in ls],V))
            elif ls[0]['bold']: items.append('## '+join_lines([x['t'] for x in ls],V))
            else: items.append('[note] '+join_lines([x['t'] for x in ls],V))
        write_page(BID,n,'notes',items); meta[f'{n:04d}']=m; continue
    if n in CREDITS:
        m['type']='credits'; blocks=collections.OrderedDict()
        for l in L: blocks.setdefault(l['blk'],[]).append(l)
        for b,ls in blocks.items():
            t=join_lines([x['t'] for x in ls],V)
            if ls[0]['bold']: items.append('# '+t if ls[0]['size']>=23 else '## '+t); continue
            LST=r'((?:\d{1,3}[a-z]?(?:[-–]\d{1,3}[a-z]?)?,? )+)(?=[A-Z©])'
            cuts=[0]+[mm.start() for mm in re.finditer(LST,t) if mm.start()>0]
            parts=[t[cuts[i]:cuts[i+1]].strip() for i in range(len(cuts)-1)]+[t[cuts[-1]:].strip()]
            items+=['[credit] '+x for x in parts]
        m['issues'].append('credit lists were run together in the text layer; split at page-number lists (machine split, words untouched)')
        write_page(BID,n,'credits',items); meta[f'{n:04d}']=m; continue
    if n in INDEX:
        m['type']='index'; blocks=collections.OrderedDict()
        for l in L: blocks.setdefault(l['blk'],[]).append(l)
        buf=[]
        for b,ls in blocks.items():
            t=join_lines([x['t'] for x in ls],V)
            if ls[0]['bold']:
                if buf: items.append('\n'.join(buf)); buf=[]
                items.append('# '+t if ls[0]['size']>=23 else '## '+t)
            else: buf.append(t)
        if buf: items.append('\n'.join(buf))
        write_page(BID,n,'index',items); meta[f'{n:04d}']=m; continue
    seq,bodyl,small=body_items(L,m)
    ptype='body' if bodyl else 'plate'
    if n in BACK: ptype='back'
    m['type']=ptype
    sz=sorted(set(l['size'] for l in L))
    if any(11.35<s<12.05 for s in sz): m['issues'].append('has text in size 11.4-12.0 treated as body prose (read p37 to confirm the rule)'); m['confidence']='medium'
    for s in seq:
        k=s[1]; t=s[2]
        if k=='h': items.append('# '+t)
        elif k=='meta': items.append('[meta] '+t)
        elif k=='p': items.append(t)
        elif k=='quote': items.append('[quote] '+t)
        elif k=='cap': items.append('[caption] '+t)
    # merge consecutive verse quotes without blank line
    merged=[]
    for it in items:
        if it.startswith('[quote] ') and merged and merged[-1].startswith('[quote] '): merged[-1]+='\n'+it
        else: merged.append(it)
    items=merged
    # continuation
    last_body=[s for s in seq if s[1]=='p']
    if last_body and n+1 in struct and (n+1) not in NOTES|CREDITS|INDEX|CONTENTS|FRONT and n+1 not in BACK and struct[n+1]:
        lastp=last_body[-1]
        # last element on page should be that paragraph (ignoring captions below)
        nl=struct[n+1]; firstb=[l for l in nl if l['size']>CAPMAX and not (l['bold'] and l['size']>=18)]
        nheads=[l for l in nl if l['bold'] and l['size']>=18]
        if firstb and not nheads and lastp[0]>=max(s[0] for s in seq if s[1] in ('p','h'))-0.1:
            if not ends_term(lastp[2]) or firstb[0]['t'][:1].islower(): cont=True
    write_page(BID,n,ptype,items,cont); meta[f'{n:04d}']=m
json.dump(meta,open(f'{ROOT}/.scratch/clean_digital/grovier_meta_raw.json','w'))
print(stats,collections.Counter(x[0] for x in hylog))
