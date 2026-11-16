import sys; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
BID='payne_gae'
doc=pymupdf.open(pdf(BID)); N=len(doc)
V=vocab_of(BID,doc)
works=json.load(open(f'{ROOT}/library/books/{BID}/works.json'))
chap_start={w['pdf_pages'][0]:w for w in works}
NOTES=range(375,396); CREDITS=range(396,404); INDEX=range(405,416)
meta={}; stats=collections.Counter(); hylog=[]
def kind(l):
    s=l['size']; f=l['font']
    if 'OceanofPDF' in l['t']: return 'wm'
    if s>=24.9 and 'Ital' in f and 'Serif' in f: return 'pull'
    if 'Sans' in f and l['bold'] and s>=16: return 'head'+str(s)
    if s==11.2 and 'Sans' in f: return 'cap'
    if s==21.2 and 'Serif' in f: return 'stand'
    return 'body'
pages_out={}
def para_items(L,page_no):
    """L filtered lines in stream order -> list of items [(type,text)], pulls separately"""
    items=[]; cur=None; pulls=[]; lastk=None; firstbody_cont=False; seen_any=False
    i=0
    while i<len(L):
        l=L[i]; k=kind(l)
        if k=='wm': i+=1; continue
        if k=='pull':
            j=i
            while j<len(L) and kind(L[j])=='pull': j+=1
            pulls.append(' '.join(x['t'] for x in L[i:j])); i=j; continue
        if k.startswith('head'):
            j=i
            while j<len(L) and kind(L[j])==k and abs(L[j]['y0']-L[j-1]['y0'])<45 or j==i: j+=1
            txt=' '.join(x['t'] for x in L[i:j]); cur=None
            items.append(['h',txt,float(k[4:])]); i=j; lastk='h'; seen_any=True; continue
        if k=='cap':
            j=i
            while j<len(L) and kind(L[j])=='cap' and (j==i or abs(L[j]['y0']-L[j-1]['y0'])<20): j+=1
            items.append(['cap',' '.join(x['t'] for x in L[i:j])]); i=j; seen_any=True; continue
        # body-type line (15 serif, 21.2 stand, 11.2 serif)
        indent=l['x0']>=90
        newp = cur is None or indent
        if not seen_any and not indent and cur is None: firstbody_cont=True
        if newp:
            cur=['p',[l['t']]]; items.append(cur)
        else: cur[1].append(l['t'])
        seen_any=True; i+=1
    return items,pulls,firstbody_cont
cont_next={}
page_items={}
for n in range(1,N+1):
    p=doc[n-1]; L,w,h=lines(p)
    L=[l for l in L if 'OceanofPDF' not in l['t'] and l['t']]
    stats['sup']+=sum(l['nsup'] for l in L)
    page_items[n]=(L,)
# pass A: build per-page structure for body pages
struct={}
for n in range(1,N+1):
    L=page_items[n][0]
    if n in NOTES or n in CREDITS or n in INDEX or n<=11 or n>=404 or not L: continue
    struct[n]=para_items(L,n)
def pw(n):
    it=struct[n][0]; return norm_words(' '.join(' '.join(x[1]) for x in it if x[0]=='p'))
for n in range(1,N+1):
    p=doc[n-1]; L=page_items[n][0]; m=dict(type='body',printed_page=None,method='script',read_by_model=False,confidence='high',issues=[],corrections=[])
    cont=False; items=[]
    if not L:
        m['type']='plate' if not page_blank(p) else 'blank'
        if n<=5: m['type']='plate' if not page_blank(p) else 'blank'
        write_page(BID,n,m['type'],[]); meta[f'{n:04d}']=m; continue
    if n in NOTES:
        m['type']='notes'; cur=None; first=True
        for l in L:
            t=l['t']
            if l['size']>=21: items.append('# '+t); continue
            if l['bold'] and l['size']>=16: items.append('## '+t); cur=None; continue
            if re.fullmatch(r'\d{1,3}',t) and l['x0']<90 and not l['bold']:
                cur=[f'[note] {t}.']; items.append(cur); first=False; continue
            if cur is None:
                if first and l['x0']>=100: cur=['[note]']; items.append(cur); cont=False; first=False; m['issues'].append('first note continues from previous page'); 
                else: cur=['[note]']; items.append(cur)
            cur.append(t)
        # join with url awareness: join wrapped lines, hyphen before url fragments is kept
        res=[]
        for it in items:
            if isinstance(it,str): res.append(it); continue
            head=it[0]; s=''
            for t in it[1:]:
                if not s: s=t
                elif s.endswith('-') or s.endswith('/'): s+=t
                else: s+=' '+t
            res.append((head+' '+s).strip())
        items=res
        # last note may continue next page: next page first line indented non-number
        nl=page_items[n+1][0] if n+1<=N else []
        if n+1 in NOTES and nl and nl[0]['x0']>=100 and not re.fullmatch(r'\d{1,3}',nl[0]['t']): cont=True
        write_page(BID,n,'notes',items,cont); meta[f'{n:04d}']=m; continue
    if n in CREDITS:
        m['type']='credits'
        blocks=collections.OrderedDict()
        for l in L: blocks.setdefault(l['blk'],[]).append(l)
        for b,ls in blocks.items():
            if ls[0]['size']>=21: items.append('# '+' '.join(x['t'] for x in ls)); continue
            t=join_lines([x['t'] for x in ls],V)
            if len(ls)<=4: items+=['[credit] '+x['t'] for x in ls]; continue
            LST=r'((?:\d{1,3}[a-z]?(?:\u2013\d{1,3}[a-z]?)?, )*\d{1,3}[a-z]?(?:\u2013\d{1,3}[a-z]?)?) (?=[A-Z])'
            cuts=[mm.start() for mm in re.finditer(LST,t)]
            cuts=[0]+[c for c in cuts if c>0]
            parts=[t[cuts[i]:cuts[i+1]].strip() for i in range(len(cuts)-1)]+[t[cuts[-1]:].strip()]
            items+=['[credit] '+x for x in parts]
        m['issues'].append('credit entries split by a page-number pattern (machine split; words untouched)')
        # first line may be continuation of the previous credit entry
        write_page(BID,n,'credits',items); meta[f'{n:04d}']=m; continue
    if n in INDEX:
        m['type']='index'
        for l in L:
            if l['size']>=21: items.append('# '+l['t'])
            elif l['bold'] and 'Sans' in l['font'] and len(l['t'])<=2: items.append('## '+l['t'])
            elif l['t'].startswith(('All page numbers','Page references')): items.append(l['t'])
            else: items.append(('    ' if l['x0']>=90 else '')+l['t'])
        # index lines: single newline between entries
        txt=[]; buf=[]
        out=[]
        for it in items:
            if it.startswith(('#','All page','Page ref')):
                if buf: out.append('\n'.join(buf)); buf=[]
                out.append(it)
            else: buf.append(it)
        if buf: out.append('\n'.join(buf))
        write_page(BID,n,'index',out); meta[f'{n:04d}']=m; continue
    if n<=11 or n>=404:
        m['type']={6:'front',7:'front',8:'contents',9:'contents',10:'contents',11:'contents',404:'back',416:'back'}.get(n,'back')
        if n in (8,9,10,11):
            cur=None
            for l in L:
                if l['size']>=24: items.append('# '+l['t']); cur=None; continue
                if re.fullmatch(r'\d{1,2}',l['t']) and l['x0']<95 and l['bold']: cur=[l['t']]; items.append(cur); continue
                if l['bold'] and l['x0']<120 and cur and len(cur)==1: cur.append(l['t']); continue
                if cur is not None and (l['x0']>=112 or True) and (len(cur)>=1) and l['y0']-cur_y<30 if False else cur is not None and not (l['bold'] and l['x0']<=115 and l['t'].isupper() and len(cur)>1 and False): cur.append(l['t']); continue
                items.append(l['t']); cur=None
            items=[x if isinstance(x,str) else ' '.join(x) for x in items]
            # contents entries which hold only number+artist run into next entry? handled by numbers
        elif n==404:
            cur=None
            for l in L:
                if l['size']>=21: items.append('# '+l['t']); cur=None; continue
                if l['x0']>=90 or cur is None: cur=[l['t']]; items.append(cur)
                else: cur.append(l['t'])
            items=[x if isinstance(x,str) else join_lines(x,V) for x in items]
        else:
            items=[join_lines([l['t'] for l in L],V)]
        write_page(BID,n,m['type'],items); meta[f'{n:04d}']=m; continue
    # ---- body page
    its,pulls,fb=struct[n]
    # pull-quote removal
    hay=[]
    for k in range(n-7,n+8):
        if k in struct: hay+=pw(k)
    for pq in pulls:
        pwds=norm_words(pq)
        r=contains_fuzzy(pwds,hay,0.8)
        if r=='near': m['issues'].append('pull quote removed; it repeats a body sentence with 1-2 words changed')
        if r: stats['pull_removed']+=1; m.setdefault('pull_removed',0); m['pull_removed']+=1
        else:
            items.append('[quote] '+pq); stats['pull_kept']+=1; m['issues'].append('pull-like large italic text not found in body; kept as [quote]'); m['confidence']='medium'
    # note: unmatched pulls come first in items; reorder later
    kept_pull=list(items); items=[]
    cs=chap_start.get(n)
    for it in its:
        if it[0]=='h':
            tag='# ' if it[2]>=30 else '## '
            items.append(tag+it[1])
        elif it[0]=='cap': items.append('[caption] '+it[1])
        else:
            lg=[]; items.append(join_lines(it[1],V,lg)); hylog.extend(lg)
    items+=kept_pull
    if cs:
        hd=[f"# {cs['title']}",f"[meta] {cs['artist']}",f"[meta] {cs['year']}"]
        items=['\n'.join(hd)]+items
        m['issues'].append('chapter title/artist/year taken from the chapter-opening picture page and contents (image text, not text layer)')
    # continuation: next page starts with non-indented body line (no heading before)
    if (n+1) in struct:
        nits,_,nfb=struct[n+1]
        if nfb and its and its[-1][0]!='h': cont=True
        elif nfb: cont=True
    if its and its[-1][0]=='h': cont=False
    if n+1 in struct and not struct[n+1][2]: cont=False
    if n+1 not in struct: cont=False
    if its and not any(i[0]=='p' for i in its): cont=False if not (n+1 in struct and struct[n+1][2]) else cont
    write_page(BID,n,'body',items,cont); meta[f'{n:04d}']=m
json.dump(meta,open('/Users/nhanvu/Documents/code/behind-the-image/.scratch/clean_digital/payne_meta_raw.json','w'))
print(stats); 
import collections as C
print(C.Counter(x[0] for x in hylog))
print([x for x in hylog if x[0]=='keep'][:80])
