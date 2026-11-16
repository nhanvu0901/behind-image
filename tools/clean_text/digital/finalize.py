import sys,datetime; sys.path.insert(0,'/Users/nhanvu/Documents/code/behind-the-image/tools/clean_text/digital')
from common import *
import check
RAW=f'{ROOT}/.scratch/clean_digital'
READ={'payne_gae':[15,17,23,27,41,36,47,59,71,83,96,108,121,134,144,155,168,179,193,205,218,226,240,252,265,277,288,303,314,327,341,353,364],'brookehitching_mad':[12,63,72,96,97,98,144,159,189,210,213,219,221],'dasal_artcurious':[16,21,34,70,71,87,127,128,202],'grovier_nws':[14,17,21,37,398]}
EXTRA_ISSUES={'payne_gae':{193:['chapter card prints 1907 for Les Demoiselles d\u2019Avignon; the page caption prints 1917 (a misprint in the book, both kept as printed)']}}
def sup_count(bid):
    doc=pymupdf.open(pdf(bid)); c=0
    for p in doc:
        for l in lines(p)[0]: c+=l['nsup']
    return c
def reorder_count(bid):
    """pages where the first body words of the text layer differ from the cleaned first body words (order changed)"""
    doc=pymupdf.open(pdf(bid)); n_=0; pages=[]
    for n in range(1,len(doc)+1):
        s=open(f'{OUT}/{bid}/page_{n:04d}.txt',encoding='utf-8').read()
        if s.startswith('[page-type] body') is False: continue
        body=[l for l in s.split('\n')[1:] if l.strip() and not l.startswith('[')]
        if not body: continue
        first=norm_words(body[0].lstrip('# '))[:4]
        lay=norm_words(doc[n-1].get_text())[:4]
        if first and lay and first!=lay: n_+=1; pages.append(n)
    return n_,pages
def grovier_sizes():
    doc=pymupdf.open(pdf('grovier_nws')); r={}
    for n in range(1,len(doc)+1):
        L=lines(doc[n-1])[0]
        if any(12.3<=l['size']<=13.0 and not l['bold'] for l in L): r[n]=True
    return r
def main():
    GS=grovier_sizes()
    now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out={}
    for bid,rawn in (('payne_gae','payne'),('brookehitching_mad','brooke'),('dasal_artcurious','dasal'),('grovier_nws','grovier')):
        raw=json.load(open(f'{RAW}/{rawn}_meta_raw.json'))
        corr={}
        if bid=='grovier_nws': corr=json.load(open(f'{RAW}/grovier_corrections.json'))
        pages={}
        for k,m in raw.items():
            n=int(k)
            f=f'{OUT}/{bid}/page_{n:04d}.txt'
            t=open(f,encoding='utf-8').read().split('\n')[0].split()[1]
            m['type']=t
            if n in READ[bid]: m['read_by_model']=True; m['method']='script+vision'
            if corr.get(str(n)):
                agg=collections.Counter((c['from'],c['to'],c['reason']) for c in corr[str(n)])
                m['corrections']=[{'from':a,'to':b,'reason':r+(f' (x{c})' if c>1 else '')} for (a,b,r),c in agg.items()]
            if bid=='grovier_nws' and GS.get(n) and t in ('body','plate'):
                if m['confidence']=='high': m['confidence']='medium'
                m['issues'].append('paragraph(s) in size 12.3-13.0 treated as body (could be commentary on a picture); unverified')
            if bid=='grovier_nws' and t=='body':
                txt=open(f'{OUT}/{bid}/page_{n:04d}.txt',encoding='utf-8').read()
                sz=[l['size'] for l in lines(pymupdf.open(pdf(bid))[n-1])[0]] if False else []
                if '[quote]' in txt:
                    m['confidence']='medium'; m['issues'].append('indented small lines taken as verse/quotation by layout rule (unverified)')
            for it in EXTRA_ISSUES.get(bid,{}).get(n,[]): m['issues'].append(it)
            m['issues']=list(dict.fromkeys(m['issues']))
            pages[k]=m
        chk=check.run(bid)
        ro,rop=reorder_count(bid)
        by_type=dict(collections.Counter(m['type'] for m in pages.values()))
        by_method=dict(collections.Counter(m['method'] for m in pages.values()))
        conf=dict(collections.Counter(m['confidence'] for m in pages.values()))
        out[bid]=dict(by_type=by_type,sup=sup_count(bid),reorder=ro,outliers=chk['outliers'],conf=conf,
                      ncorr=sum(len(v) for v in corr.values()), nfrom=len({(c['from']) for v in corr.values() for c in v}),
                      pages_changed=len(corr))
        known={
         'payne_gae':['Chapter number, artist, title and year on the 30 chapter-opening pages were read from the picture card (capitals as printed); the text layer has no such text. The Picasso card prints 1907, the caption on the same page prints 1917.','Credits (396-403) are split into entries by a page-number pattern; the first/last entry of a page may be cut.','Index kept one line per entry; sub-entries marked by 4 spaces.','Printed page numbers do not exist in this reflowed edition (printed_page null).','About 9 pull quotes repeat the body with more than 2 words changed (paraphrase); they were removed too, as they add nothing.','Only 5 full pages plus the 30 opening cards were read by eye; pull-quote removal and paragraph joins elsewhere rest on scripts and word conservation.'],
         'brookehitching_mad':['Margin captions are placed after the body of their page, not next to the paragraph they sit beside. 12 pages have two or three caption columns (21, 60, 96, 97, 156, 158, 159, 199, 210, 213, 219, 221): each caption is separated by column; a caption that runs on into the next column is joined. Pages 21, 60, 156, 158, 199 were not read by eye.','Block quotations (italic indented lines, 14 blocks) are tagged [quote]; the rule is layout-based.','Title page p5 stacked display lines are in y-order, not in design order.','Index kept line-per-line with an indent marker; bibliography entries split at the left margin; credits split at ";" before page references.'],
         'dasal_artcurious':['Sidebars (grey boxes) are wrapped in [sidebar-start] <title> / [sidebar-end]. 35 boxes start with a heading; a box split by a page break has an empty [sidebar-start] on the next page. Detection is by layout (11.2 pt box text, 21.2 pt box title); 9 pages were read by eye.','A box whose title sits at the page foot and whose text is on the next page is left open across the page break.','Italics lost (as in the source text layer).','Index kept line-per-line; e-book A-Z navigation line removed.','"[meta] CHAPTER n" holds the chapter number; # holds the chapter title. Epigraph attributions share the [quote] tag.'],
         'grovier_nws':['Body-vs-caption is decided by font size (<=11.3 caption, larger = body). Verified only on the 5 pages read; sizes 12.3-13.0 paragraphs are treated as body and may be picture commentary (59 pages marked medium).','Verse/poem lines are detected by indent under a body paragraph; the four inscription lines on p163 are plain paragraphs.','Name corrections cover artist/work names, a few chapter-subject names and 40 certain misses found by the verifier; about 700 other capitalised non-words in the body and 540 in Sources/Index/Credits are left as printed. A name search in this text is NOT reliable. This book is low-trust for facts.','"Issenheim", "Abramovic" and "Gustave" are correct spelling variants and are left alone; "Maman" is printed "Mom" and left alone.'],
        }[bid]
        resid={
         'payne_gae':'Prose faithful (word conservation: only 94 pull quotes removed, title words added). 33 pages read (5 full, 30 opening cards, 2 overlap): 0 structure errors found after the heading fix. Not read: the other ~380 pages rest on scripts.',
         'brookehitching_mad':'13 pages read, all of them chosen from pages the fixes touched (12 caption pages, plus the reordered pages read in run 1): 0 errors left; before the fix 6-12 caption pages were scrambled. Pages 21, 60, 156, 158, 199 changed but were not read. Estimate: under 1% of body pages with a structure error; not measured on a random sample.',
         'dasal_artcurious':'9 pages read: 0 errors. Sidebar detection by layout is correct on 9 of 9 pages read; the other ~40 sidebar pages are unverified. Estimate: a few sidebars may be mis-bounded; prose and drop caps verified.',
         'grovier_nws':'5 pages read. Structure fine where read, unverified elsewhere. Proper names: 576 replacements, hundreds of mangled names left. Low-trust book.',
        }[bid]
        meta={'book_id':bid,'generated':now,'format':1,'pages':pages,
              'summary':{'pages':chk['pages'],'by_type':by_type,'by_method':by_method,'read_by_model':sum(1 for m in pages.values() if m['read_by_model']),
                         'residual_error_estimate':resid,'known_gaps':known,
                         'word_count_outliers':[list(o) for o in chk['outliers']],
                         **({'name_corrections':{'replacements':out[bid]['ncorr'],'distinct_mangled_forms':out[bid]['nfrom'],'pages_changed':out[bid]['pages_changed']}} if bid=='grovier_nws' else {})}}
        json.dump(meta,open(f'{OUT}/{bid}/meta.json','w'),ensure_ascii=False,indent=1)
    print(json.dumps(out,default=str,indent=1)[:3500])
main()
