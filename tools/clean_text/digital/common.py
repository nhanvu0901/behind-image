import pymupdf, glob, os, re, json, collections, difflib
ROOT='/Users/nhanvu/Documents/code/behind-the-image'
KEYS={'payne_gae':'Great_Art_Explained','brookehitching_mad':'Madmans_Gallery','dasal_artcurious':'ArtCurious','grovier_nws':'A_New_Way_of_Seeing'}
OUT=f'{ROOT}/library/clean_text'
def pdf(bid):
    return glob.glob(f"{ROOT}/books/*{KEYS[bid]}*.pdf")[0]
def is_sup(s):
    return bool(s['flags']&1) and re.fullmatch(r'\s*[\d,–\-]+\s*',s['text']) is not None
def lines(page, strip_sup=True):
    """line dicts: t (text, superscript digit spans removed if strip_sup), x0,y0,x1,y1,size,font,bold,blk,nsup"""
    d=page.get_text('dict'); out=[]
    for bi,b in enumerate(d['blocks']):
        if b['type']!=0: continue
        for l in b['lines']:
            sp=[s for s in l['spans'] if s['text'].strip()]
            if not sp: continue
            nsup=0; parts=[]
            for s in l['spans']:
                if strip_sup and is_sup(s): nsup+=1; continue
                parts.append(s['text'])
            t=''.join(parts).strip()
            ns=[s for s in sp if not is_sup(s)] or sp
            main=max(ns,key=lambda s:len(s['text'].strip()))
            out.append(dict(t=t,x0=l['bbox'][0],y0=l['bbox'][1],x1=l['bbox'][2],y1=l['bbox'][3],size=round(main['size'],1),font=main['font'],
                bold=bool(main['flags']&16) or 'Bold' in main['font'],ital=bool(main['flags']&2) or 'Ital' in main['font'],blk=bi,nsup=nsup,
                spans=[(s['text'],round(s['size'],1),s['font'],s['flags'],round(s['bbox'][0],1),round(s['bbox'][1],1)) for s in sp]))
    return out,d['width'],d['height']
def render(bid,pno,path,w=1600):
    doc=pymupdf.open(pdf(bid)); p=doc[pno-1]; z=w/p.rect.width
    p.get_pixmap(matrix=pymupdf.Matrix(z,z)).save(path)
def page_blank(page):
    pm=page.get_pixmap(matrix=pymupdf.Matrix(0.2,0.2),colorspace=pymupdf.csGRAY)
    s=pm.samples
    return (max(s)-min(s))<12
def norm_words(t):
    return re.findall(r"[a-z0-9]+",t.lower().replace('’',"'").replace("'",''))
class Vocab:
    def __init__(self): self.c=collections.Counter(); self.hy=collections.Counter()
    def feed(self,text):
        for w in re.findall(r"[A-Za-zÀ-ɏ]+(?:-[A-Za-zÀ-ɏ]+)*",text):
            self.c[w.lower()]+=1
            if '-' in w: self.hy[w.lower()]+=1
def join_lines(ls, vocab, log=None):
    out=''
    for t in ls:
        t=t.strip().replace('­','')
        if not t: continue
        if not out: out=t; continue
        if out[-1] in '-‐' and len(out)>1 and out[-2].isalpha() and t[0].isalpha():
            m=re.search(r'([A-Za-zÀ-ɏ]+)-$',out); a=m.group(1).lower() if m else ''
            b=re.match(r'[A-Za-zÀ-ɏ]+',t); b=b.group(0).lower() if b else ''
            joined=a+b; hy=a+'-'+b
            if t[0].isupper(): out+=t
            elif vocab.hy.get(hy,0)>0 and vocab.c.get(joined,0)<=vocab.hy.get(hy,0):
                out+=t
                if log is not None: log.append(('keep',hy))
            elif vocab.c.get(joined,0)>0:
                out=out[:-1]+t
                if log is not None: log.append(('join',joined))
            else:
                out+=t
                if log is not None: log.append(('keep',hy))
        else: out+=' '+t
    return re.sub(r'\s+',' ',out)
def contains_fuzzy(pull, hay_words, thr=0.8):
    """returns 'exact' (longest contiguous match >= thr), 'near' (aligned window ratio >= thr) or ''"""
    if not pull: return ''
    sm=difflib.SequenceMatcher(None,hay_words,pull,autojunk=False)
    m=sm.find_longest_match(0,len(hay_words),0,len(pull))
    if m.size/len(pull)>=thr: return 'exact'
    if m.size>=4:
        a=max(0,m.a-m.b-3); win=hay_words[a:a+len(pull)+8]
        sm2=difflib.SequenceMatcher(None,win,pull,autojunk=False)
        tot=sum(b.size for b in sm2.get_matching_blocks())
        if tot/len(pull)>=thr: return 'near'
    return ''
def write_page(bid,n,ptype,items,cont=False):
    d=f'{OUT}/{bid}'; os.makedirs(d,exist_ok=True)
    txt=f'[page-type] {ptype}\n'
    if items: txt+='\n'+'\n\n'.join(items)+'\n'
    if cont: txt+='\n[continues]\n'
    open(f'{d}/page_{n:04d}.txt','w',encoding='utf-8').write(txt)
def vocab_of(bid,doc):
    v=Vocab()
    for p in doc:
        for l in lines(p)[0]: v.feed(l['t'])
    return v
