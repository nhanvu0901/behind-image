"""Build clean text for hagen_wgps. Usage: python3 build.py"""
import sys,re,json,collections,datetime,os
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import layout as Lo, accents as A
ROOT=Lo.ROOT; OUT=ROOT+'library/clean_text/hagen_wgps/'
SOFT=Lo.SOFT
P=Lo.P; N=len(P)
# ---------- vocab for hyphen decisions (middle-of-line tokens only)
MID=collections.Counter(); HY=collections.Counter()
for p in P[11:491]:
    for l in p['lines']:
        ts=l['t'].split()
        for t in ts[1:-1]:
            a=re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$","",t)
            if re.fullmatch(r"[A-Za-z]+-[A-Za-z]+(-[A-Za-z]+)*",a): HY[a.lower()]+=1
            elif re.fullmatch(r"[A-Za-z]+",a): MID[a.lower()]+=1
STATS=collections.Counter(); DEC=[]
def join_lines(ls):
    s=''
    for t in ls:
        t=t.rstrip()
        if not s: s=t; continue
        t=t.lstrip()
        if s.endswith(SOFT) or re.search(r'[A-Za-z]-$',s):
            soft=s.endswith(SOFT)
            base=s[:-1]
            m1=re.search(r"([A-Za-z]+)$",base); m2=re.match(r"([A-Za-z]+)",t)
            if m1 and m2:
                l,r=m1.group(1),m2.group(1)
                joined=(l+r).lower(); hyph=(l+'-'+r).lower()
                keep=False
                inj=(MID[joined]>0 or joined in Lo.DICT)
                if HY[hyph]>0 and HY[hyph]>=MID[joined]: keep=True
                elif soft:
                    PRE={'anti','self','mid','well','much','ill','half','non','semi','quasi','eye','jewel','wax','pig','drop'}
                    SUF={'like','shaped','oriented','encrusted','catching','loved','known','born','based','minded','free','proof','sized','looking','coloured','made','bound','ridden','laden','driven','fed','worn','written','held','effacing','deserving','dressed','snouted','writing'}
                    keep = (not inj) and (l.lower() in PRE or r.lower() in SUF)
                elif inj: keep=False
                else:
                    ok3=('sea','egg','ill','old','new','top','two','set','one','red','all','war','art','man','sun','sky','air','car','pop','wet','far','low','mid','non','ex')
                    lv=lambda w: (len(w)>=4 or w.lower() in ok3) and (w.lower() in Lo.DICT or MID[w.lower()]>0 or Lo.valid(w))
                    keep = lv(l) and lv(r) and not Lo.valid(l+r)
                if keep: s=base+'-'+t; STATS['hyphen_kept']+=1; DEC.append(('keep',soft,hyph))
                else:
                    s=base+t; STATS['soft_joined' if soft else 'hyph_joined']+=1
                    if not soft or MID[joined]==0 and joined not in Lo.DICT: DEC.append(('join',soft,joined))
            else:
                s=base+t if soft else s+t
                STATS['soft_joined']+=soft
        elif re.search(r'\d-$',s) and re.match(r'[a-z]',t): s+=t; STATS['digit_hyphen_joined']+=1
        else: s+=' '+t
    return s
Lo.join_lines=join_lines
Lo.LINEFIX=lambda n,t,b,W,H: A.collect(n,t,b,W,H,Lo.valid) or t

# ---------- pass 1: evidence for accents (entry + appendix pages)
RAW={}
def run_assemble(n):
    try: return Lo.assemble(n)
    except Exception as e:
        print('assemble fail',n,e); return [],{'printed':None,'junk':0,'flags':[]},[]
for n in range(12,492):
    RAW[n]=run_assemble(n)
A.build_map(Lo.valid)
for bad in ('gloire','vers','te-crayon','hauser','miere','hiitte','preceeded'): A.MAP.pop(bad,None)
Lo.LINEFIX=None

# ---------- appendix (492-498) layout
def assemble_appendix(n):
    p=P[n-1]; L=[dict(l) for l in p['lines'] if not (re.fullmatch(r"\d{1,3}",l['t'].strip()) and l['b'][1]>740)]
    cols=Lo.clusters_x0(L,gap=60)
    def colof(l):
        for i,(a,b) in enumerate(cols):
            if a<=round(l['b'][0])<=b: return i
    for l in L: l['col']=colof(l)
    R={}
    for i in range(len(cols)):
        x1=sorted(l['b'][2] for l in L if l['col']==i)
        if x1: R[i]=x1[int(len(x1)*0.85)]
    items=[]; cur=None; prev=None
    for l in sorted(L,key=lambda l:(l['col'],l['b'][1])):
        newp = cur is None or prev['col']!=l['col'] or prev['b'][2]<R[prev['col']]-14 or re.match(r"^(\d{1,2}\s|Notes:|Lit\.:)",l['t']) or (l['b'][1]-prev['b'][3])>6
        if prev is not None and (prev['t'].endswith(SOFT)): newp=False
        if newp:
            if cur: items.append(cur)
            cur=dict(kind='para',lines=[l['t']])
        else: cur['lines'].append(l['t'])
        prev=l
    if cur: items.append(cur)
    for it in items:
        it['text']=join_lines(it['lines']); del it['lines']
        if re.match(r"^(\d{1,2}\s|Notes:|Lit\.:)",it['text']): it['kind']='note'
    return items,{'printed':None,'junk':0,'flags':[]}

# ================= finalize =================
TERM=re.compile(r'[.!?”"’)\]]\s*$')
OVR_PATH=os.path.join(os.path.dirname(os.path.abspath(__file__)),'overrides.json')
OVR=json.load(open(OVR_PATH)) if os.path.exists(OVR_PATH) else {}
FOOT=re.compile(r"(?<=[.,;:!?”’\")])(\d{1,2})(?=\s|$|[”’\"])|(?<=[a-z]{3})(\d{1,2})(?=\s|$)")
FIXLOG=collections.defaultdict(list)
def speckfix(n,t):
    def rep(m):
        tok=m.group(0)
        if (n,tok) in A.SPECKFIX: STATS['specks_vision']+=1; return A.SPECKFIX[(n,tok)]
        return tok
    return re.sub(r"\S+",rep,t)
def clean_para(n,t,kind):
    t=t.replace(SOFT+' ','').replace('\u00a0',' ')
    if kind!='h1': t=speckfix(n,t)
    FL={'Fler':'Her','Flenry':'Henry','Flolbein':'Holbein','Flis':'His','Flarold':'Harold','Fleers':'Heers','Flere':'Here','Fle':'He','Llorence':'Florence'}
    def swp(m):
        w=m.group(0)
        if w in FL: STATS['H_to_Fl_fixed']+=1; FIXLOG[n].append(('Fl->H',w,FL[w])); return FL[w]
        return w
    t=re.sub(r"\b[A-Za-z]{2,8}\b",swp,t)
    t=re.sub(r"\barid (?=(the|a|an|then|his|her|they|it|he|she|we|in|of|to)\b)","and ",t)
    t2=re.sub(r"\bFie (?=[a-z])","He ",t)
    if t2!=t: STATS['H_to_Fl_fixed']+=1; t=t2
    t=A.apply(n,t)
    t0=t
    if kind in ('para','h2','quote','h1'):
        t=re.sub(r"(?:(?<=[A-Za-z][.,;:!?])|(?<=[.,;:!?][”’\"])|(?<=[”’\"][.,;:!?])|(?<=[A-Za-z][”’\"])|(?<=[A-Za-z]\)))\d{1,2}(?=\s|$)","",t)
        t=re.sub(r"(?<=[a-z]{3})\d{1,2}(?=\s|$)","",t)
        if t!=t0: STATS['footnote_refs']+=1; FIXLOG[n].append(('footnote ref',t0,t))
    t1=t
    t=re.sub(r"\b[iIlL](\d{3})\b",lambda m:'1'+m.group(1) if 400<=int('1'+m.group(1))<=2003 else m.group(0),t)
    if t!=t1: STATS['years_fixed']+=1; FIXLOG[n].append(('year',t1,t))
    if kind in ('para','quote'):
        t=re.sub(r"(?<=[.,;:!?])'(?=\s|$)","",t)
        t=re.sub(r"(?<=[,;:])-(?=[A-Za-z])"," ",t)
        t=re.sub(r"(?<=[a-z])[’']'(?=[a-z])"," ",t)
    t=re.sub(r"\s+"," ",t).strip()
    return t
def typo(t):
    t=re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])","’",t)
    t=re.sub(r"(?<=[A-Za-z])'(?=\s|$|[.,;:!?])","’",t)
    t=re.sub(r'(^|[\s(\[—-])"',lambda m:m.group(1)+'“',t)
    t=t.replace('"','”')
    return t
def render(items,n):
    out=[]
    for it in items: it['text']=typo(it['text'])
    for it in items:
        k=it['kind']; tx=it['text']
        if not tx.strip(): continue
        if k=='h1': out.append('# '+tx)
        elif k=='h2': out.append('## '+tx)
        elif k=='meta': out.append('[meta] '+tx)
        elif k=='quote': out.append('[quote] '+tx)
        elif k=='note': out.append('[note] '+tx)
        elif k=='caption': out.append('[caption] '+tx)
        elif k=='credit': out.append('[credit] '+tx)
        else: out.append(tx)
    return out
STATIC=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'static_pages.json'))) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),'static_pages.json')) else {}

pages={}   # n -> dict(type, items, printed, issues, method, conf)
for n in range(1,N+1):
    pg=dict(type=None,items=[],printed=None,issues=[],conf='high',method='script',read=False,junk=0)
    key='%04d'%n
    if key in STATIC:
        st=STATIC[key]; pg.update(type=st['type'],items=[dict(kind=k,text=t) for k,t in st['items']],method=st.get('method','read'),read=st.get('read',True),conf=st.get('conf','high'),issues=st.get('issues',[]))
        pg['printed']=st.get('printed')
    elif 12<=n<=491:
        it,o,L=RAW[n]
        pg['printed']=o['printed']; pg['junk']=o['junk']
        words=sum(len(x['text'].split()) for x in it)
        if not it or (words<25 and not any(x['kind']=='h1' for x in it)):
            pg['type']='plate'; pg['items']=[]
            if words: pg['issues'].append('residual OCR junk from picture dropped (%d words)'%words)
        else:
            pg['type']='body'; pg['items']=it
    elif 492<=n<=498:
        it,o=assemble_appendix(n); pg.update(type='index',items=it,conf='medium')
        pg['issues'].append('appendix in small print, 3 columns; line structure approximate; accents restored only where Vision confirmed')
    else:
        pg['type']='blank'
    pages[n]=pg

# ---------- clean paragraphs, contents harmonisation
norm=lambda t: re.sub(r'[^a-z0-9]','',t.lower())
sk=lambda t: re.sub(r'[^a-z]','',t.lower()).translate({ord(c):None for c in 'iloszbr'})
for n,pg in pages.items():
    if pg['type'] in ('body','index'):
        for it in pg['items']:
            it['text']=clean_para(n,it['text'],it['kind'])
# ---------- cross-page soft hyphen at end of page
def last_para(pg):
    for it in reversed(pg['items']):
        if it['kind'] in ('para',): return it
    return None
def first_para(pg):
    for it in pg['items']:
        if it['kind'] in ('para',): return it
    return None
for n in range(12,492):
    pg=pages[n]; lp=last_para(pg)
    if pg['type']!='body' or not lp or not (lp['text'].endswith(SOFT) or re.search(r'[A-Za-z]-$',lp['text'])): continue
    # next body page
    m=n+1
    while m<=491 and pages[m]['type']=='plate': m+=1
    if m>491 or pages[m]['type']!='body': continue
    fp=first_para(pages[m])
    if not fp: continue
    txt=lp['text']; soft=txt.endswith(SOFT)
    tok=fp['text'].split(' ',1); first=tok[0]; rest=tok[1] if len(tok)>1 else ''
    merged=join_lines([txt,first]) if (soft or True) else txt
    lp['text']=merged; fp['text']=rest
    STATS['crosspage_joins']+=1
    pg['issues'].append('word broken across the page boundary was completed here (first word of next page moved)'); pages[m]['issues'].append('first word moved to previous page to complete a broken word')
    if not fp['text']: fp['text']=''
for n,pg in pages.items():
    pg['items']=[it for it in pg['items'] if it['text'].strip() or it['kind'] in ('h1',)]

# ---------- page-level checks / issues
for n in range(12,492):
    pg=pages[n]
    if pg['type']!='body': continue
    its=pg['items']
    for i,x in enumerate(its):
        if x['kind']=='para' and x['text'][:1].islower() and i>0 and its[i-1]['kind']=='h2':
            pg['issues'].append('paragraph after heading starts lowercase (drop cap lost): "%s"'%x['text'][:30]); pg['conf']='medium'
    if pg['junk']>=5 and sum(len(x['text'].split()) for x in its)>100: pg['issues'].append('%d picture-OCR junk lines dropped'%pg['junk'])
    for x in its:
        if x['kind']=='para' and "'" in x['text'] and re.search(r"[a-z]'[a-z]",x['text']): pg['issues'].append("straight apostrophe inside word (possible OCR speck): "+re.search(r"\w*[a-z]'[a-z]\w*",x['text']).group(0))

# ---------- overrides (reader pass)
def apply_overrides():
    for key,o in OVR.items():
        n=int(key); pg=pages[n]
        if 'full' in o:
            pg['items']=[dict(kind=k,text=t) for k,t in o['full']]
            if 'type' in o: pg['type']=o['type']
        for rep in o.get('replace',[]):
            done=False
            for it in pg['items']:
                if rep['from'] in it['text']:
                    it['text']=it['text'].replace(rep['from'],rep['to'],1); done=True; break
            if not done: print('OVERRIDE MISS',n,rep['from'][:40])
            else: pg.setdefault('corr',[]).append(dict(**{'from':rep['from'],'to':rep['to'],'reason':rep.get('reason','read page image')}))
        for dm in o.get('delete_match',[]):
            for i,it in enumerate(pg['items']):
                if it['kind']==dm['kind'] and it['text']==dm['text']:
                    pg['items'].pop(i); pg.setdefault('corr',[]).append({'from':dm['text'],'to':'','reason':dm.get('reason','picture-OCR junk heading removed')}); break
            else: print('DELETE MISS',n,dm['text'][:40])
        if 'replace_head' in o:
            rh=o['replace_head']; pg['items'][:rh['count']]=[dict(kind=k,text=t) for k,t in rh['items']]
            pg.setdefault('corr',[]).append({'from':'(first %d items)'%rh['count'],'to':'rewritten from page image','reason':rh.get('reason','read page image')})
        for ins in o.get('insert',[]):   # {"after_kind":..,"index":i,"kind":..,"text":..}
            pg['items'].insert(ins['index'],dict(kind=ins['kind'],text=ins['text']))
        for dl in o.get('delete_items',[]):
            pg['items'].pop(dl)
        if o.get('read'): pg['read']=True; pg['method']='read'
        if 'conf' in o: pg['conf']=o['conf']
        if 'issues' in o: pg['issues']+=o['issues']
        if o.get('clear_issues'): pg['issues']=[i for i in pg['issues'] if not any(i.startswith(c) for c in o['clear_issues'])]
apply_overrides()

# ---------- write
os.makedirs(OUT,exist_ok=True)
nxt_first_lower={}
for n in range(1,N+1):
    pg=pages[n]; lines=['[page-type] '+pg['type']]
    body=render(pg['items'],n)
    if pg['type']=='body' and body:
        lp=last_para(pg)
        cont=False
        if lp and pg['items'][-1] is lp and not TERM.search(lp['text']): cont=True
        if lp and pg['items'][-1] is lp and TERM.search(lp['text']):
            m=n+1
            while m<=491 and pages[m]['type']=='plate': m+=1
            if m<=491 and pages[m]['type']=='body':
                fp=first_para(pages[m])
                if fp and fp['text'][:1].islower() and pages[m]['items'][0] is fp: cont=True
        pg['cont']=cont
    for b in body:
        lines.append(''); lines.append(b)
    if pg.get('cont'): lines.append(''); lines.append('[continues]')
    pg['text']='\n'.join(lines)+'\n'
    open(OUT+'page_%04d.txt'%n,'w',encoding='utf-8').write(pg['text'])
# printed page numbers
for n,pg in pages.items():
    if pg['printed'] is None and 12<=n<=491: pg['printed']=str(n-4); pg['issues'].append('printed page number inferred (pdf page minus 4)') if False else None
meta=dict(book_id='hagen_wgps',generated=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),format=1,pages={},summary={})
for n,pg in pages.items():
    meth='read' if pg['read'] else ('script+vision' if any(x[0]==n for x in A.LOG) else pg['method'])
    meta['pages']['%04d'%n]=dict(type=pg['type'],printed_page=pg['printed'],method=meth,read_by_model=pg['read'],confidence=pg['conf'],issues=pg['issues'],corrections=pg.get('corr',[]))
json.dump(meta,open(OUT+'meta.json','w'),ensure_ascii=False,indent=1)
print(collections.Counter(p['type'] for p in pages.values()))
print(dict(STATS)); print('accent applications',len(A.LOG),'unique maps',len(A.MAP))
