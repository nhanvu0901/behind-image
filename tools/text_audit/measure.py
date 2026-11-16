#!/usr/bin/env python3
"""Per-page text-layer metrics for the six books -> library/text_audit/<id>.json

Usage: python3 tools/text_audit/measure.py [book_id ...]
Vocabulary: /usr/share/dict/words (+ plural/-ed/-ing/possessive stripping)
 + per-book 'recurring' list: any lowercase-folded token seen >= REC times in the book
   (REC=4 for digital books, 6 for scans: OCR errors repeat less than real names, but
   a threshold that is too low whitelists repeated OCR garbage).
 Non-word rate = unknown tokens (alphabetic, len>=3) / alphabetic tokens (len>=3).
"""
import sys, re, json, glob, os, collections, statistics
import pymupdf

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOOKS = {
    'payne_gae': ('Great_Art_Explained', 'digital', 4),
    'hodge_aid': ('Art in detail', 'scan', 6),
    'hagen_wgps': ('What Great Paintings Say', 'scan', 6),
    'grovier_nws': ('A_New_Way_of_Seeing', 'digital', 4),
    'brookehitching_mad': ('Madmans_Gallery', 'digital', 4),
    'dasal_artcurious': ('ArtCurious', 'digital', 4),
}
TOK = re.compile(r"[^\W_]+(?:['’\-¬­][^\W_]+)*", re.U)
SOFT = ('¬', '­')


def load_dict():
    s = set()
    with open('/usr/share/dict/words', errors='ignore') as f:
        for l in f:
            s.add(l.strip().lower())
    return s


DICT = load_dict()


BRIT = [('our', 'or'), ('ours', 'ors'), ('oured', 'ored'), ('ise', 'ize'), ('ised', 'ized'), ('ising', 'izing'), ('isation', 'ization'),
        ('ises', 'izes'), ('yse', 'yze'), ('re', 'er'), ('res', 'ers'), ('lled', 'led'), ('lling', 'ling'), ('ogue', 'og'), ('ence', 'ense'),
        ('ae', 'e'), ('oe', 'e'), ('ful', 'ful'), ('ourite', 'orite'), ('ourful', 'orful'), ('oured', 'ored'), ('ourist', 'orist')]


def known_base(w, extra):
    w = w.lower()
    for c in SOFT:
        w = w.replace(c, '')
    if w in DICT or w in extra:
        return True
    for a, b in BRIT:
        if w.endswith(a) and (w[:-len(a)] + b) in DICT:
            return True
    # doubled consonant before -ed/-ing/-er (planned, cropping, committed)
    m = re.fullmatch(r'(.{2,})([^aeiou])\2(ed|ing|er|ers|est)', w)
    if m and (m.group(1) + m.group(2)) in DICT:
        return True
    if w.endswith('ied') or w.endswith('ies'):
        pass
    for suf, rep in (("'s", ''), ("’s", ''), ('s', ''), ('es', ''), ('ed', ''), ('d', ''), ('ing', ''), ('ing', 'e'),
                     ('ly', ''), ('ies', 'y'), ('ied', 'y'), ('er', ''), ('ers', ''), ('ness', ''), ('ment', ''),
                     ('ments', ''), ('al', ''), ('ally', ''), ('est', ''), ('ish', ''), ("s'", '')):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            b = w[:-len(suf)] + rep
            if b in DICT or b in extra:
                return True
    if "-" in w:
        return all(known_base(p, extra) for p in w.split('-') if p)
    return False


def odd_case(t):
    # e.g. "aRt", "pRANSCUCENT" (lower->upper inside word), but allow McX, iPad
    if len(t) < 3 or not t.isalpha():
        return False
    if re.search(r'[a-z][A-Z]', t) and not re.match(r'^(Mc|Mac|De|Di|Le|La|Van|Von)[A-Z]', t):
        return True
    return False


def garbled(t):
    out = []
    if re.search(r'[A-Za-z]', t) and re.search(r'\d', t):
        # letter+digit mix; allow ordinals / dates like 1st 15th 1920s 3D, 2nd
        if not re.fullmatch(r'(c\.|b\.|d\.|fl\.|mid-)?\d+([,.\-\u2013]\d+)*(st|nd|rd|th|s|D|d|cm|mm|m|in|ft|x|BC|AD|am|pm|bc|ad|kg|km)?(-\w+)*', t, re.I) \
                and not re.fullmatch(r'\d+(st|nd|rd|th)-?\w*', t, re.I):
            out.append('alnum')
    elif odd_case(t):
        out.append('case')
    return out


def year_ocr(t):
    # i486 / l486 / I486 / x913 / 1o86 style: letter standing for a digit in a 4-char year-like token
    return bool(re.fullmatch(r'[ilIoOxsS]\d{3}', t) or re.fullmatch(r'\d[ilIoO]\d{2}', t) or re.fullmatch(r'\d{2}[ilIoO]\d', t))


STRAY = re.compile(r'[¤¦§¬¶°•■□�¾¼½«»|~^{}\\<>]')


def line_text(l):
    return ''.join(s['text'] for s in l['spans'])


def page_lines(page):
    d = page.get_text('dict')
    blocks = []
    for b in d['blocks']:
        if b['type'] != 0:
            continue
        lines = []
        for l in b['lines']:
            t = line_text(l).strip()
            if t:
                sz = max((s['size'] for s in l['spans']), default=0)
                lines.append({'t': t, 'bbox': l['bbox'], 'size': sz,
                              'bold': any(s['flags'] & 16 for s in l['spans'])})
        if lines:
            blocks.append({'bbox': b['bbox'], 'lines': lines})
    return blocks, d['width'], d['height']


def reading_order_flag(blocks, W):
    """Column-aware check. Detect 2 columns by x-centre clustering of body lines; then
    check that the extracted block sequence does not jump right->left->right->left.
    Returns (ncols, problem_bool, detail)."""
    xs = []
    for b in blocks:
        for l in b['lines']:
            x0, y0, x1, y1 = l['bbox']
            if len(l['t']) > 25 and (x1 - x0) < W * 0.55:
                xs.append((x0 + x1) / 2)
    if len(xs) < 12:
        return 1, False, ''
    left = [x for x in xs if x < W / 2]
    right = [x for x in xs if x >= W / 2]
    if len(left) < 5 or len(right) < 5:
        return 1, False, ''
    # sequence of column labels over body blocks (text blocks whose width < 0.55 W)
    seq = []
    for b in blocks:
        x0, y0, x1, y1 = b['bbox']
        if (x1 - x0) < W * 0.55 and sum(len(l['t']) for l in b['lines']) > 60:
            seq.append(0 if (x0 + x1) / 2 < W / 2 else 1)
    # count alternations; ideal = a single L->R switch (0..0 1..1) per column group
    alt = sum(1 for a, c in zip(seq, seq[1:]) if a != c)
    # right->left switches are the legit "next column"; L->R jumps beyond one are suspicious
    lr = sum(1 for a, c in zip(seq, seq[1:]) if a == 0 and c == 1)
    rl = sum(1 for a, c in zip(seq, seq[1:]) if a == 1 and c == 0)
    bad = lr > 1 or (rl >= 1 and lr >= 1 and alt > 2)
    return 2, bad, f'seq_alternations={alt}'


def classify_nonbody(blocks, W, H, page_no, rep_counts):
    """running header/footer/page number/caption/credit candidates by geometry & repetition."""
    res = {'page_number': 0, 'running_head': 0, 'caption_like': 0, 'credit_like': 0}
    for b in blocks:
        for l in b['lines']:
            t = l['t']
            y0, y1 = l['bbox'][1], l['bbox'][3]
            top = y1 < H * 0.07
            bot = y0 > H * 0.92
            if (top or bot) and re.fullmatch(r'\d{1,4}|[ivxlc]{1,6}', t, re.I):
                res['page_number'] += 1
            elif (top or bot) and len(t.split()) <= 10:
                res['running_head'] += 1
            elif rep_counts.get(re.sub(r'\d+', '#', t.lower()), 0) >= 8 and len(t) < 80:
                res['running_head'] += 1
            if re.match(r'^(Fig\.?|Figure|Plate|Detail|Left|Right|Above|Opposite)\b', t) or (l['size'] < 8.0 and len(t) < 160 and not top and not bot and l['size'] > 0):
                res['caption_like'] += 1
            if re.search(r'(©|\bcopyright\b|Photo:|Courtesy|Photograph|Bridgeman|Scala|akg-images|Getty|Wikimedia|Art Resource)', t, re.I):
                res['credit_like'] += 1
    return res


def measure_book(bid):
    key, kind, REC = BOOKS[bid]
    path = [p for p in glob.glob(os.path.join(ROOT, 'books', '*.pdf')) if key in p][0]
    doc = pymupdf.open(path)
    pages = []
    # pass 1: collect raw text and tokens
    raw = []
    for pg in doc:
        blocks, W, H = page_lines(pg)
        imgs = pg.get_images(full=True)
        raw.append((blocks, W, H, len(imgs), pg.get_text()))
    cnt = collections.Counter()
    linecnt = collections.Counter()
    for blocks, W, H, ni, txt in raw:
        for t in TOK.findall(txt):
            cnt[t.lower()] += 1
        for b in blocks:
            for l in b['lines']:
                linecnt[re.sub(r'\d+', '#', l['t'].lower())] += 1
    extra = {w for w, c in cnt.items() if c >= REC and w.isalpha() and len(w) >= 3}
    # body font size (mode) for heading detection
    sizes = collections.Counter()
    for blocks, *_ in raw:
        for b in blocks:
            for l in b['lines']:
                sizes[round(l['size'])] += len(l['t'])
    body_size = sizes.most_common(1)[0][0] if sizes else 10
    for i, (blocks, W, H, ni, txt) in enumerate(raw):
        words = txt.split()
        toks = TOK.findall(txt)
        alpha = [t for t in toks if t.isalpha() and len(t) >= 3]
        unk_all = [t for t in alpha if not known_base(t, extra)]
        # capitalised unknowns are treated as proper nouns (not errors); lowercase / ALLCAPS-with-lowercase-mix unknowns are errors
        unk = [t for t in unk_all if not (t[0].isupper() and (t[1:].islower()))]
        proper = len(unk_all) - len(unk)
        fn = len(re.findall(r'[a-z\u2019\u201d][.,;:!?\u2019\u201d]\d{1,3}\b|[a-z]{3,}\d{1,2}\b', txt))
        # strict: what you would see without the book-recurring list
        unk_strict = [t for t in alpha if not known_base(t, set())]  # no recurring list, includes names
        gar = []
        yr = 0
        for t in re.findall(r'\S+', txt):
            t2 = t.strip('.,;:!?()[]"\'“”‘’')
            if not t2:
                continue
            g = garbled(t2)
            if g:
                gar.append(t2)
            if year_ocr(t2):
                yr += 1
        stray = len(STRAY.findall(txt))
        soft = sum(txt.count(c) for c in SOFT)
        # line-break hyphenation: line ends with hyphen & next line starts lowercase
        lb = 0
        for b in blocks:
            ls = b['lines']
            for a, c in zip(ls, ls[1:]):
                if re.search(r'[A-Za-z][-¬­]$', a['t']) and c['t'][:1].islower():
                    lb += 1
        # headings: short all-caps line with non-words, or big font lines
        heads = []
        for b in blocks:
            for l in b['lines']:
                t = l['t']
                letters = [c for c in t if c.isalpha()]
                if 3 <= len(letters) and len(t) <= 70 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
                    hw = [w for w in TOK.findall(t) if w.isalpha() and len(w) >= 3]
                    bad = [w for w in hw if not known_base(w, extra)]
                    heads.append({'text': t, 'nonwords': bad, 'suspect': bool(bad) or bool(garbled(t.replace(' ', '')))})
        # junk lines: short lines (<=4 tokens) containing no recognisable word and not a number / roman numeral -> typical of OCR run over picture texture
        junk = 0
        for b in blocks:
            for l in b['lines']:
                tk = TOK.findall(l['t'])
                if len(tk) <= 4 and not re.fullmatch(r'[\dIVXLivxl.,\- ]+', l['t']) and not any(
                        (t.isalpha() and len(t) >= 3 and known_base(t, extra)) or t.isdigit() for t in tk):
                    junk += 1
        ncols, order_bad, odetail = reading_order_flag(blocks, W)
        nb = classify_nonbody(blocks, W, H, i + 1, linecnt)
        # pull-quote duplicates: line >=6 words that appears (>=80% of its words) inside another block
        dup = 0
        btxt = [' '.join(l['t'] for l in b['lines']) for b in blocks]
        for bi, b in enumerate(blocks):
            for l in b['lines']:
                ws = l['t'].lower().split()
                if len(ws) >= 6:
                    frag = ' '.join(ws)
                    for bj, o in enumerate(btxt):
                        if bj != bi and frag in o.lower():
                            dup += 1
                            break
        notext = len(txt.strip()) == 0
        img_only = notext and ni > 0
        # text-bearing check for scans: an OCR layer exists but is tiny relative to an image page
        sparse = (not notext) and ni > 0 and len(words) < 15
        rec = {
            'page': i + 1, 'words': len(words), 'alpha_tokens': len(alpha),
            'nonword_tokens': len(unk), 'nonword_rate': round(len(unk) / len(alpha), 4) if alpha else 0.0,
            'nonword_rate_strict': round(len(unk_strict) / len(alpha), 4) if alpha else 0.0,
            'nonword_examples': unk[:8], 'proper_noun_candidates': proper, 'footnote_markers': fn,
            'garbled_tokens': len(gar), 'garbled_examples': gar[:8], 'year_ocr': yr, 'stray_symbols': stray,
            'soft_hyphens': soft, 'linebreak_hyphens': lb,
            'headings': heads, 'garbled_headings': sum(1 for h in heads if h['suspect']),
            'columns': ncols, 'reading_order_flag': order_bad, 'order_detail': odetail,
            'nonbody': nb, 'pullquote_dups': dup, 'junk_lines': junk,
            'images': ni, 'no_text_layer': notext, 'image_only': img_only, 'sparse_text_on_image_page': sparse,
        }
        # composite suspicion score (used to pick worst pages & to prioritise review)
        rec['suspicion'] = round(rec['nonword_rate'] * 100 + 3 * rec['garbled_tokens'] / max(1, len(words)) * 100
                                 + 5 * rec['garbled_headings'] + 2 * rec['year_ocr'] + 1.5 * rec['junk_lines'] + (3 if order_bad else 0), 3) if len(words) >= 40 else 0
        pages.append(rec)
    n = len(pages)
    tw = sum(p['words'] for p in pages)
    body = [p for p in pages if p['words'] >= 40]
    summ = {
        'book_id': bid, 'kind': kind, 'pages': n, 'words': tw, 'body_size_pt': body_size,
        'recurring_vocab_size': len(extra), 'recurring_threshold': REC,
        'pages_no_text': sum(p['no_text_layer'] for p in pages),
        'pages_image_only': sum(p['image_only'] for p in pages),
        'pages_sparse_text_on_image': sum(p['sparse_text_on_image_page'] for p in pages),
        'pages_lt40_words': n - len(body),
        'nonword_rate_overall': round(sum(p['nonword_tokens'] for p in pages) / max(1, sum(p['alpha_tokens'] for p in pages)), 4),
        'nonword_rate_strict_overall': round(sum(p['nonword_rate_strict'] * p['alpha_tokens'] for p in pages) / max(1, sum(p['alpha_tokens'] for p in pages)), 4),
        'nonword_rate_page_median': round(statistics.median([p['nonword_rate'] for p in body]), 4) if body else 0,
        'junk_lines_total': sum(p['junk_lines'] for p in pages),
        'pages_with_junk_ge5': sum(p['junk_lines'] >= 5 for p in pages),
        'garbled_tokens_total': sum(p['garbled_tokens'] for p in pages),
        'year_ocr_total': sum(p['year_ocr'] for p in pages),
        'soft_hyphens_total': sum(p['soft_hyphens'] for p in pages),
        'linebreak_hyphens_total': sum(p['linebreak_hyphens'] for p in pages),
        'garbled_headings_total': sum(p['garbled_headings'] for p in pages),
        'headings_total': sum(len(p['headings']) for p in pages),
        'pages_two_column': sum(p['columns'] == 2 for p in pages),
        'pages_reading_order_flag': sum(p['reading_order_flag'] for p in pages),
        'pages_with_pullquote_dups': sum(p['pullquote_dups'] > 0 for p in pages),
        'running_head_lines': sum(p['nonbody']['running_head'] for p in pages),
        'page_number_lines': sum(p['nonbody']['page_number'] for p in pages),
        'caption_like_lines': sum(p['nonbody']['caption_like'] for p in pages),
        'credit_like_lines': sum(p['nonbody']['credit_like'] for p in pages),
        'pages_nonword_rate_gt_3pct': sum(p['nonword_rate'] > 0.03 for p in body),
        'pages_nonword_rate_gt_6pct': sum(p['nonword_rate'] > 0.06 for p in body),
    }
    out = {'schema': 'text_audit/v1: {book: summary, pages:[per-page metrics]}; see docs/design/research/R4_book_text_audit.md',
           'summary': summ, 'pages': pages}
    with open(os.path.join(ROOT, 'library/text_audit', bid + '.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    return summ


if __name__ == '__main__':
    ids = sys.argv[1:] or list(BOOKS)
    for b in ids:
        s = measure_book(b)
        print(json.dumps(s))
