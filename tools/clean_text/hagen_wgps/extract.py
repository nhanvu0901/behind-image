"""Stage A: text-layer lines with geometry -> .scratch/clean_hagen/lines.json"""
import pymupdf,glob,json
ROOT='/Users/nhanvu/Documents/code/behind-the-image/'
d=pymupdf.open(glob.glob(ROOT+'books/*What Great Paintings Say*')[0])
out=[]
for i,p in enumerate(d):
    L=[]
    for bi,b in enumerate(p.get_text('dict')['blocks']):
        if b['type']!=0: continue
        for l in b['lines']:
            t=''.join(s['text'] for s in l['spans']).rstrip()
            if not t.strip(): continue
            sz=max(s['size'] for s in l['spans'])
            L.append(dict(t=t,b=[round(v,1) for v in l['bbox']],sz=round(sz,1),blk=bi,sp=[[x['text']]+[round(v,1) for v in x['bbox']]+[round(x['size'],1)] for x in l['spans']]))
    out.append(dict(page=i+1,w=p.rect.width,h=p.rect.height,lines=L))
json.dump(out,open(ROOT+'.scratch/clean_hagen/lines.json','w'))
print(len(out),sum(len(x['lines']) for x in out))
