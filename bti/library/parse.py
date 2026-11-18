"""Deterministic per-book catalogue parsers. Each returns a list of raw work dicts:
{n, title, artist, year, headline?, pdf_pages:[a,b], artist_death?, artist_alive?}.
Rules per book are documented in docs/design/2026-11-16-library-design.md."""
from __future__ import annotations

import re
import unicodedata

import pymupdf

ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
       "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
       "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
       "twentieth": 20, "twenty-first": 21}
OCR_FIX = {"Land the Village": "I and the Village", "Diirer": "Dürer", "Griinewald": "Grünewald",
           "Leonardo da Vinei": "Leonardo da Vinci", "Jan Eyck": "Jan van Eyck", "Battle of Issues": "Battle of Issus",
           "Riigen": "Rügen", "Alamedea": "Alameda", "theTurkish Sutan": "the Turkish Sultan"}


def fix_ocr(s: str) -> str:
    for a, b in OCR_FIX.items():
        s = s.replace(a, b)
    return s


def clean(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\x00", "").replace("\xad", "").replace("\xa0", " ")
    s = re.sub(r"¬\s*", "", s)
    s = re.sub(r"[\ud800-\udfff]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def fix_digits(tok: str) -> str:
    """OCR: x913 / i486 / l9l4 -> digits (only inside 4-char tokens that are mostly digits)."""
    def f(m):
        t = m.group(0)
        if sum(c.isdigit() for c in t) >= 2:
            return t.translate(str.maketrans("xXiIlO", "111100"))
        return t
    return re.sub(r"\b[xXiIlO\d]{4}\b", f, tok)


def year_num(year: str | None) -> int | None:
    if not year:
        return None
    y = fix_digits(year)
    low = y.lower()
    if "bc" in low:
        m = re.search(r"(\d[\d,]*)", y)
        return -int(m.group(1).replace(",", "")) if m else None
    m = re.search(r"\b(\d{4})\b", y)
    if m:
        return int(m.group(1))
    m = re.search(r"([a-z]+(?:-first)?)\s*(?:-|–)?\s*(?:[a-z-]+\s+)?centur", low)
    if m and m.group(1) in ORD:
        return (ORD[m.group(1)] - 1) * 100 + 50
    m = re.search(r"\b(\d{3})\b", y)
    return int(m.group(1)) if m else None


YEAR_TAIL = re.compile(r"[,\s]\s*((?:c\.\s*|ca\.\s*|after\s+|before\s+|between\s+)?[\dxXilO]{4}"
                       r"(?:\s*(?:[/–-]|and)\s*[\dxXilO]{1,4})?)\s*$")


def split_year_tail(s: str) -> tuple[str, str | None]:
    m = YEAR_TAIL.search(s)
    if not m:
        return s.strip(" ,"), None
    return s[:m.start()].strip(" ,"), fix_digits(m.group(1)).strip()


def parse_death(dates: str):
    """-> (birth, death, alive) from '(1909-92)' / '(c. 1431-1516)' / '(b.1945)'."""
    d = fix_digits(dates)
    if re.search(r"\bb\.\s*\d{4}", d):
        return int(re.search(r"\d{4}", d).group(0)), None, True
    m = re.search(r"(\d{4})\s*[-–—]\s*(?:c\.\s*)?(\d[\d ]{1,4})", d)
    if not m:
        return None, None, False
    b, e = int(m.group(1)), m.group(2).replace(" ", "")
    if len(e) == 3:
        return b, None, False
    if len(e) == 2:
        dd = int(e)
        cent = b // 100 * 100
        death = cent + dd if cent + dd >= b else cent + 100 + dd
    else:
        death = int(e)
    return b, death, False


# ------------------------------------------------------------------ digital books with a PDF TOC
def _toc(doc):
    return [(lvl, clean(t), p) for lvl, t, p in doc.get_toc()]


def parse_payne(doc) -> list[dict]:
    toc = _toc(doc)
    ents = [(t, p) for _, t, p in toc if re.match(r"^\d+ ", t)]
    notes = next(p for _, t, p in toc if t == "Notes")
    out = []
    for i, (t, p) in enumerate(ents):
        end = (ents[i + 1][1] if i + 1 < len(ents) else notes) - 1
        m = re.match(r"^(\d+) (.*)$", t)
        body = m.group(2)
        body, year = split_year_tail(body)
        artist, _, title = body.partition(": ")
        out.append(dict(n=int(m.group(1)), title=title.strip(), artist=artist.strip(), year=year, pdf_pages=[p, end]))
    return out


def parse_grovier(doc) -> list[dict]:
    toc = _toc(doc)
    ents = [(t, p) for _, t, p in toc if re.match(r"^\d\d\s+\S", t) and "Masterpieces" not in t[:16]]
    after = next(p for _, t, p in toc if t.startswith("Sources and Further"))
    out = []
    for i, (t, p) in enumerate(ents):
        end = (ents[i + 1][1] if i + 1 < len(ents) else after) - 1
        m = re.match(r"^(\d\d)\s+(.*)$", t)
        body = m.group(2)
        artist, title = None, body
        if ", " in body and not body.startswith("The "):
            a, _, rest = body.partition(", ")
            artist, title = a.strip(), rest.strip()
        title, year = split_year_tail(title) if re.search(r",\s*\d{4}$", title) else (title, None)
        out.append(dict(n=int(m.group(1)), title=title, artist=artist, year=year, pdf_pages=[p, end]))
    return out


# entries whose title carries the artist without a "(year), Artist" tail (explicit, by entry number)
MADMAN_EXC = {21: {"artist": "Giuseppe Arcimboldo"}, 36: {"artist": "Giovanni Battista Piranesi"},
              37: {"artist": "Franz Xaver Messerschmidt"}, 39: {"artist": "Robert Barker"},
              51: {"artist": "Georgiana Houghton"}, 54: {"artist": "Arthur Stace"},
              58: {"artist": "Pierre Brassau"}, 60: {"artist": "Marina Abramović", "title": "Marina Abramović and Performance Art"}}


def parse_madman(doc) -> list[dict]:
    toc = _toc(doc)
    i0 = next(i for i, (_, t, _) in enumerate(toc) if t == "Introduction")
    i1 = next(i for i, (_, t, _) in enumerate(toc) if t == "Select Bibliography")
    ents = toc[i0 + 1:i1]
    out = []
    for i, (_, t, p) in enumerate(ents):
        end = (ents[i + 1][2] if i + 1 < len(ents) else toc[i1][2]) - 1
        title, artist, year, extra = t, None, None, None
        m = re.match(r"^(.*?)\s*\(([^()]*\d[^()]*|[^()]*centur[^()]*)\)(.*)$", t)
        if m:
            title, year, tail = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            if tail.startswith(","):
                a = tail[1:].strip()
                a = re.split(r"\s+and\s+", a)[0]
                artist = a.strip() or None
                extra = tail[1:].strip()[len(a):].strip() or None
            elif tail:
                extra = tail.strip(") ")
            if artist and artist.startswith("after "):
                artist = artist[6:]
            pm = re.match(r"^([A-Z][\w.]*(?:\s+(?:[a-z]+\s+)?[A-Z][\w.]*)+)’s\s+(.+)$", title)
            if pm and not artist and not pm.group(1).startswith(("Mr ", "Mrs ", "Dr ", "St ")):
                artist, title = pm.group(1), pm.group(2)
        title = title.replace("´", "")
        w = dict(n=i + 1, title=title, artist=artist, year=year, pdf_pages=[p, end],
                 **({"headline": extra} if extra else {}))
        w.update(MADMAN_EXC.get(i + 1, {}))
        out.append(w)
    return out


ARTCURIOUS_FIX = {}


def parse_artcurious(doc) -> list[dict]:
    toc = _toc(doc)
    chs = [(i, t, p) for i, (lvl, t, p) in enumerate(toc) if re.match(r"^Chapter \d+$", t)]
    ack = next(p for _, t, p in toc if t == "Acknowledgments")
    parts = {}
    cur = None
    for lvl, t, p in toc:
        if t.startswith("Part "):
            cur = t
        elif re.match(r"^Chapter \d+$", t):
            parts[t] = cur
    out = []
    for k, (_, t, p) in enumerate(chs):
        end = (chs[k + 1][2] if k + 1 < len(chs) else ack) - 1
        spans = []
        for b in doc[p - 1].get_text("dict")["blocks"]:
            if b["type"]:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if abs(s["size"] - 25.0) < 1.5 and s["text"].strip():
                        spans.append(s["text"])
        title = clean(" ".join(spans)) or t
        n = int(t.split()[1])
        out.append(dict(n=n, title=title, artist=None, year=None, pdf_pages=[p, end], headline=parts.get(t)))
    return out


# ------------------------------------------------------------------ scans
def _flip_name(a: str) -> str:
    parts = [x.strip() for x in a.split(", ")]
    if len(parts) == 2:
        return f"{parts[1]} {parts[0]}"
    if len(parts) == 3:
        return f"{parts[1]} {parts[0]} {parts[2]}"
    return a


def parse_hodge(doc) -> list[dict]:
    raw = "\n".join(doc[p - 1].get_text() for p in (428, 429))
    stop = raw.find("Abstract Expressionism")
    if stop > 0:
        raw = raw[:stop]
    lines = []
    for ln in raw.split("\n"):
        s = ln.strip()
        if not s or re.fullmatch(r"\d{3}", s) or s in ("Index of artworks", "INDEX", "Index", "|", ")"):
            continue
        if re.fullmatch(r"[A-Za-z]{1,3}", s):
            continue
        lines.append(s)
    text = clean(" ".join(lines))
    # an entry ends at "(year) 388-91"; OCR sometimes loses the dash ("(year) 75"), then the page is None
    pat = re.compile(r"\)\s+(\d{1,3})(?:\s*[-–—]\s*(\d{1,3}))?\b(?=\s+[A-ZÀ-Ý]|\s*$)")
    out, pos = [], 0
    for m in pat.finditer(text):
        chunk = text[pos:m.start() + 1]
        pos = m.end()
        if m.group(2) is None:
            p1, end = None, None
        else:
            p1, p2 = int(m.group(1)), m.group(2)
            end = int(str(p1)[:max(0, len(str(p1)) - len(p2))] + p2) if len(p2) < len(str(p1)) else int(p2)
            if end - p1 != 3:
                end = p1 + 3
        i = chunk.find("(")
        j = chunk.find(")", i)
        artist = clean(chunk[:i]) if i > 0 else None
        dates = chunk[i:j + 1] if i >= 0 else ""
        rest = chunk[j + 1:].strip()
        title, year = rest, None
        ym = re.search(r"\(([^()]*)\)\s*$", rest)
        if ym:
            title, year = rest[:ym.start()].strip(), fix_digits(clean(ym.group(1)))
        b, d, alive = parse_death(dates)
        title = title.lstrip("‘’'“\" ").strip()
        year = re.sub(r"\s*[-–—]\s*", "-", year) if year else year
        out.append(dict(title=fix_ocr(title), artist=_flip_name(fix_ocr(artist or "")) or None, year=year,
                        pdf_pages=[p1 + 4, end + 4] if p1 else None, artist_death=d, artist_alive=alive,
                        artist_birth=b, artist_dates=dates.strip("()")))
    # entries whose page OCR was unreadable take the one free 4-page slot between their neighbours
    known = sorted(w["pdf_pages"][0] for w in out if w["pdf_pages"])
    gaps = [a + 4 for a, b in zip(known, known[1:]) if b - a == 8]
    for w in [w for w in out if not w["pdf_pages"]]:
        if gaps:
            a = gaps.pop(0)
            w["pdf_pages"] = [a, a + 3]
            w["pages_inferred"] = True
    out.sort(key=lambda w: w["pdf_pages"][0])
    for i, w in enumerate(out, 1):
        w["n"] = i
    return out


def parse_hagen(doc) -> list[dict]:
    """Contents (PDF pages 9-11) is two columns whose headline and detail lines interleave by a few points, so
    per page and column: headline lines (size >= 9.2) are grouped by vertical gap, detail lines (smaller) are
    grouped by the `Artist: Title` colon, and the k-th headline pairs with the k-th detail."""
    heads_all, dets_all, ties = [], [], set()
    for pno in (9, 10, 11):
        lines = []
        for b in doc[pno - 1].get_text("dict")["blocks"]:
            if b["type"]:
                continue
            for l in b["lines"]:
                t = clean("".join(s["text"] for s in l["spans"]))
                if t:
                    lines.append((l["bbox"][0], l["bbox"][1], l["spans"][0]["size"], t))
        for col in (0, 1):
            cl = sorted((x for x in lines if (x[0] >= 200 if col else x[0] < 200)), key=lambda x: x[1])
            heads, dets, last_y = [], [], None
            for x, y, size, t in cl:
                if re.fullmatch(r"\d{1,3}", t) or len(t) <= 2 or t == "Contents":
                    continue
                t = re.sub(r"^\d{3}\s+(?=\D)", "", t)
                t = re.sub(r"(?<=[A-Za-z!?,\"”)])\s+\d{2,3}$", "", t)
                t = re.sub(r"\b(\d{3}) (\d)$", r"\1\2", t)
                if t.startswith("Appendix"):
                    continue
                if size >= 9.2:
                    if heads and last_y is not None and 8 <= y - last_y <= 18:
                        heads[-1].append(t)
                    else:
                        if heads and last_y is not None and y - last_y < 8:
                            ties.add(len(heads_all) + len(heads))  # two headlines within a few points
                        heads.append([t])
                    last_y = y
                else:
                    if ": " in t or not dets:
                        dets.append([t])
                    else:
                        dets[-1].append(t)
            if len(heads) != len(dets):
                raise RuntimeError(f"hagen contents page {pno} col {col}: {len(heads)} headlines vs {len(dets)} details")
            heads_all += heads
            dets_all += dets
    # two headlines printed on (almost) the same line are in arbitrary order: keep the order whose words
    # occur best on the first pages of the two entries
    def words(t):
        return set(re.findall(r"[a-z]{4,}", t.lower()))
    for k in sorted(ties):
        if k < 1 or k >= len(heads_all):
            continue
        def score(h, i):
            pg = " ".join(doc[q - 1].get_text() for q in (12 + 6 * i, 13 + 6 * i))
            return len(words(" ".join(h)) & words(pg[:600]))
        keep = score(heads_all[k - 1], k - 1) + score(heads_all[k], k)
        swap = score(heads_all[k], k - 1) + score(heads_all[k - 1], k)
        if swap > keep:
            heads_all[k - 1], heads_all[k] = heads_all[k], heads_all[k - 1]
    out = []
    for i, (h, d) in enumerate(zip(heads_all, dets_all)):
        head, det = clean(" ".join(h)), clean(" ".join(d))
        artist, title = None, det
        if ": " in det:
            artist, _, title = det.partition(": ")
        title, year = split_year_tail(title)
        title, artist = fix_ocr(title), fix_ocr(artist) if artist else artist
        if artist and artist.lower().startswith("artist unknown"):
            artist = None
        a = 12 + 6 * i
        out.append(dict(n=i + 1, title=title, artist=artist, year=year, headline=head, pdf_pages=[a, a + 5]))
    return out


PARSERS = {"payne_gae": parse_payne, "hodge_aid": parse_hodge, "hagen_wgps": parse_hagen,
           "grovier_nws": parse_grovier, "brookehitching_mad": parse_madman, "dasal_artcurious": parse_artcurious}
