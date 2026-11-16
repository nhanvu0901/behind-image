"""Apply manual overrides/corrections to merge.py output and write library/clean_text/hodge_aid."""
import re, json, os, sys, glob, datetime
import pymupdf
ROOT='/Users/nhanvu/Documents/code/behind-the-image'
AUTO=ROOT+'/.scratch/clean_hodge/auto'
OUT=ROOT+'/library/clean_text/hodge_aid'
os.makedirs(OUT,exist_ok=True)
info=json.load(open(AUTO+'/info.json'))
sys.path.insert(0,ROOT+'/tools/clean_text/hodge_aid')

# (page, old, new): substitutions after reading the page image (reader pass)
CORR=[
 
 (40,'of a mess mountain','of a mountain'),(40,'statue, a a Colosseum','statue, a Colosseum'),
 (102,'ACCOMPANIMENI','ACCOMPANIMENT'),(111,'ANDRÉS NÚNEZ','ANDRÉS NÚÑEZ'),(136,'BANNINCK COCO','BANNINCK COCQ'),
 (118,'Antwerp. Belgium','Antwerp, Belgium'),(161,'Edinburgh, UI','Edinburgh, UK'),
 (218,'\nii 1','\nNational Gallery, London, UK'),
 (300,'t910–11','1910–11'),(313,'t, New New York, York, US USA','New York, USA'),
 (321,'f iIViuseo del 121 NI INovecento, ‘ \\A IVirlan, Tz51 Italy','Museo del Novecento, Milan, Italy'),
 (323,'in 191 in Milan','in 1911 in Milan'),(351,'O’ Keeffe','O’Keeffe'),(379,'Kahlo’ life','Kahlo’s life'),
(409,'(417 million)','(£17 million)'),
]
OVR={}
def S(p,*pairs): OVR.setdefault(p,[]).extend(pairs)
S(13,('[caption] PRE-1500','# PRE-1500'))
S(59,('\nCENTURY\n','\n# 16TH CENTURY\n'))
S(113,('\nCENTURY\n','\n# 17TH CENTURY\n'),('Is probably','is probably'),("‘BAROQUE’","‘BAROQUE’"))
S(159,('\nCENTURY\n','\n# 18TH CENTURY\n'))
S(193,('\nCENTURY\n','\n# 19TH CENTURY\n'),('I9TH','19TH'))
S(295,('[caption] POST-1900','# POST-1900'))
S(11,('“The question is not what you look at, but what you see.”','[quote] “The question is not what you look at, but what you see.”\n\n–Henry David Thoreau (Journal, 5 August 1851)'),('\n\n–Henry David Thoreau (Journal, 5 August 1851)\n\npages,',' pages,'),('Key aspects identified The','## Key aspects identified\n\nThe'),('Tools to enable comprehension This','## Tools to enable comprehension\n\nThis'))
S(10,('\nIntroduction\n','\n# Introduction\n'),('\nmagine having','\nImagine having'),('Underlying meaning and interpretation Every','## Underlying meaning and interpretation\n\nEvery'),('Window on society Combining','## Window on society\n\nCombining'),('Revolutions two','Revolutions, two'))
S(2,('Art in Detail 100 MASTERPIECES SUSIE HODGE','# Art in Detail\n\n100 MASTERPIECES\n\nSUSIE HODGE'),('internal • details','internal details'),('Giotto\'s','Giotto’s'),('[caption] On the front cover','[caption] On the front cover'))
TYPES={}
for n in (1,2,4,5,7,436): TYPES[n]='front'
for n in (8,9): TYPES[n]='contents'
for n in range(424,428): TYPES[n]='notes'
for n in range(428,435): TYPES[n]='index'
TYPES[435]='credits'; TYPES[439]=TYPES[440]='back'

MANUAL={
 8:"[page-type] contents\n# Contents\n\nINTRODUCTION 6\n\nPre-1500 8\n\n16th Century 54\n\n17th Century 108\n",
 9:"[page-type] contents\n18th Century 154\n\n19th Century 188\n\nPost-1900 290\n\nGLOSSARY 420\n\nINDEX OF ARTWORKS 424\n\nINDEX 425\n\nPICTURE CREDITS 431\n",
 11:None,
}
def dull(img_path):
    from PIL import Image
    im=Image.open(img_path).convert('L').resize((110,120))
    px=list(im.getdata()); mu=sum(px)/len(px); sd=(sum((p-mu)**2 for p in px)/len(px))**.5
    return sd
def fix_text(t):
    t=re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])","’",t)
    t=re.sub(r"^(## .*)$",lambda mo: re.sub(r"(?<![A-Za-z])'",'‘',re.sub(r"(?<=[A-Za-z])'$",'’',mo.group(1))),t,flags=re.M)
    return t
meta={}
by_type={}; by_method={}
doubt_pages=[]
works=json.load(open(ROOT+'/library/books/hodge_aid/works.json'))
for n in range(1,441):
    t=open(f'{AUTO}/page_{n:04d}.txt').read()
    inf=info[str(n)]
    issues=[]; corr=[]; method='script+vision'; read=False
    if n in MANUAL and MANUAL[n]:
        t=MANUAL[n]; method='read'; read=True
    else:
        for (a,b) in OVR.get(n,[]):
            if a not in t: issues.append(f'override not applied: {a[:30]}'); continue
            t=t.replace(a,b,1)
        for (p,a,b) in CORR:
            if p!=n: continue
            if a not in t: issues.append(f'correction not applied: {a[:30]}'); continue
            t=t.replace(a,b,1); corr.append({'from':a.strip(),'to':b.strip(),'reason':'page image'}); read=True
        if n in OVR: read=True; method='script+vision'
    lines=t.split('\n')
    typ=TYPES.get(n, 'plate' if inf['type']=='plate' else 'body')
    if inf['type']=='plate' and n<424:
        # blank vs plate
        typ='blank' if dull(f'{ROOT}/.scratch/clean_hodge/img/p{n:04d}.png')<12 else 'plate'
        lines=['[page-type] '+typ]
    elif n in (3,6,12,437,438):
        typ='blank' if dull(f'{ROOT}/.scratch/clean_hodge/img/p{n:04d}.png')<12 else 'plate'; lines=['[page-type] '+typ]
    else:
        lines[0]='[page-type] '+typ
        t='\n'.join(lines)
        t=fix_text(t)
        if n==435:
            t='\n'.join(('[credit] '+l if l.strip() and not l.startswith(('#','[page-type]')) else l) for l in t.split('\n'))
        if typ in('front','contents','index','credits','notes','back') or n<14:
            t=t.replace('\n[continues]','')
        lines=t.split('\n')
    text='\n'.join(lines).rstrip('\n')+'\n'
    open(f'{OUT}/page_{n:04d}.txt','w').write(text)
    pp=inf.get('printed_page_seen')
    printed=str(n-4) if 14<=n<=423 else None
    conf='high'
    if inf.get('doubts',0)>=3 or inf.get('doublines'): conf='medium'
    if any(w in text for w in ('¬',)): conf='low'
    if re.search(r'\d\s*[x×]\s*\d.*cm|cm \(',text): issues.append('caption dimensions with fractions not verified (engines disagree on fraction glyphs); caption partly blurred in the scan')
    if 84<=n<=88: conf='low'; issues.append('fold-out panel: lines cut at the page edge, text may continue on the next page and some line starts are missing')
    meta[f'{n:04d}']=dict(type=typ,printed_page=printed,printed_page_seen=pp,method=method if typ not in('plate','blank') else 'script',read_by_model=read,confidence=conf,issues=issues,corrections=corr)
    by_type[typ]=by_type.get(typ,0)+1
    by_method[meta[f'{n:04d}']['method']]=by_method.get(meta[f'{n:04d}']['method'],0)+1
json.dump(dict(book_id='hodge_aid',generated=datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),format=1,pages=meta,summary=dict(pages=440,by_type=by_type,by_method=by_method,read_by_model=sum(1 for m in meta.values() if m['read_by_model']),residual_error_estimate='32-page sample (every 13th page from 16): 919 body lines / ~7,000 words, lines where output disagreed with either Vision pass were checked against the page image: ~0 word errors outside caption dimension fractions (est. <0.1% body words; lines where all engines agree were not re-read). Headings 57/57 exact in sample, 10/10 entry titles, artists and years exact. Whole book vs works.json: 100/100 titles, artists and years agree except spelling/expansion differences that come from works.json.',known_gaps=['caption dimensions with fractions (about 16 captions) are partly wrong or garbled; the captions are partly blurred in the scan','blurred credit/caption blocks on title and plate pages are unreadable and were dropped (medium/size/location of the work is mostly missing from [meta])','fold-out Isenheim pages 84-88: text cut at page edge','circled detail numbers are not recorded; detail headings are ordered by column then top-to-bottom','text pages 1-13 and 436 (copyright credits: roles and names not paired) were only lightly edited','glossary/index pages come from the text layer with Vision accents; not read page by page','headings and titles are kept in the printed capitals','page 14 prints 1377 for Giotto death year (as printed)'])),open(f'{OUT}/meta.json','w'),indent=1,ensure_ascii=False)
print(by_type,by_method)
