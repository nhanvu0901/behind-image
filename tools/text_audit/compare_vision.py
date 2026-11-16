#!/usr/bin/env python3
"""Compare PDF text layer vs Apple Vision OCR for sampled pages. Writes .scratch/audit/notes/<book>_p<N>.txt
Vision lines are ordered column-aware (left column then right) when the page has two text columns.
Usage: compare_vision.py <book_id> <key> """
import sys, json, re, glob, difflib, os, pymupdf
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
bid, key = sys.argv[1], sys.argv[2]
sel = json.load(open(f'{ROOT}/.scratch/audit/scan_sample.json'))[bid]
pages = sum(sel.values(), [])
doc = pymupdf.open([x for x in glob.glob(f'{ROOT}/books/*.pdf') if key in x][0])
vis = {}
for l in open(f'{ROOT}/.scratch/audit/vision/{bid}.jsonl'):
    r = json.loads(l); n = int(re.search(r'_p(\d+)\.png', r['image']).group(1)); vis[n] = r
os.makedirs(f'{ROOT}/.scratch/audit/notes', exist_ok=True)

def vis_text(r):
    L = [x for x in r['lines'] if x['c'] > 0.3 or len(x['t']) > 12]
    # column-aware: split by x centre at 0.5 if many lines on both sides with width<0.5
    narrow = [x for x in L if x['w'] < 0.5]
    left = [x for x in narrow if x['x'] + x['w'] / 2 < 0.5]; right = [x for x in narrow if x['x'] + x['w'] / 2 >= 0.5]
    if len(left) > 8 and len(right) > 8:
        wide = [x for x in L if x['w'] >= 0.5]
        L = sorted(wide + left, key=lambda x: x['y']) + sorted(right, key=lambda x: x['y'])
    else:
        L = sorted(L, key=lambda x: x['y'])
    return '\n'.join(x['t'] for x in L)

def norm(t):
    t = t.replace('¬', '').replace('­', '')
    t = t.replace('’', "'").replace('‘', "'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", t.lower())
import collections
def fold(w):
    import unicodedata
    return unicodedata.normalize('NFKD', w).encode('ascii','ignore').decode()
for n in pages:
    tl = doc[n - 1].get_text()
    vt = vis_text(vis[n])
    a, b = norm(tl), norm(vt)
    ca, cb = collections.Counter(a), collections.Counter(b)
    only_layer = sorted((ca - cb).elements()); only_vis = sorted((cb - ca).elements())
    # bag-of-words diff: order independent (page layouts have 1-3 columns, so sequence diff is unreliable)
    with open(f'{ROOT}/.scratch/audit/notes/{bid}_p{n:04d}.txt', 'w') as f:
        f.write(f'== TEXT LAYER p{n} ==\n{tl}\n== VISION p{n} ({vis[n]["seconds"]:.2f}s) ==\n{vt}\n')
        f.write(f'== BAG DIFF ==\nONLY_IN_LAYER ({len(only_layer)}): {" ".join(only_layer)}\nONLY_IN_VISION ({len(only_vis)}): {" ".join(only_vis)}\n')
    print(n, len(a), len(b), 'only_layer', len(only_layer), 'only_vision', len(only_vis))
