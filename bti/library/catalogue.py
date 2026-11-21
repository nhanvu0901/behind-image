"""Catalogue builder and loaders: library/books/<id>/{book.json,works.json}, library/artworks.json.

Everything is deterministic (no LLM, no network). Human corrections live in library/overrides/<book>.json and are
never written by the build."""
from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

import pymupdf

from . import config, extract, parse, restored
from .. import textfold
from bti.fsio import atomic_replace

PARTICLES = {"van", "von", "de", "da", "di", "del", "della", "le", "la", "the", "elder", "younger", "of", "der",
             "den", "af", "el", "jr", "sir", "mr"}
ARTICLES = {"the", "a", "an", "la", "le", "les", "il", "el", "l", "un", "une"}
RIGHTS_NOTE = "Ước lượng tự động, chỉ để tham khảo; cần người kiểm tra."
YEAR_PD = 71  # years after the artist's death
FIELDS_OVERRIDABLE = {"title", "artist", "attribution", "year", "year_raw", "headline", "pdf_pages", "artwork_key",
                      "rights", "notes", "artist_death", "artist_alive"}
# Source trust, most trusted first. Every field of a work records where its value came from (field_src), and the
# artwork takes each field from the most trusted source that has one:
#   library/overrides  >  clean text of a digital book  >  clean text of a scanned (OCR) book  >  PDF outline
#   >  anything from a low-trust (machine-translated) book.
SRC_RANK = {"override": 0, "clean_digital": 1, "clean_scan": 2, "outline": 3, "low_trust": 4}
# Keys that projects already use (the server's projects point at them): a rebuild must never move them.
PINNED_KEYS = ("eyck-the-arnolfini-portrait", "munch-the-scream")
# A low-trust book gives only these fields from its clean text (its names and titles are machine-translated).
CLEAN_FIELDS = {"grovier_nws": ("year",)}


# ------------------------------------------------------------------ json io
def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    atomic_replace(tmp, path)


class LibraryDataError(ValueError):
    """A library file (catalogue, dossier, overrides) is there but is not UTF-8 JSON. The message names the file; the editor
    answers 409 with `data_error: "library"`."""
    what = "library"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise LibraryDataError("%s is corrupt: it is not UTF-8 text" % path.name)
    except (ValueError, RecursionError):
        raise LibraryDataError("%s is corrupt: it is not valid JSON" % path.name)
    except IsADirectoryError:
        raise LibraryDataError("%s is corrupt: it is a folder, not a file" % path.name)
    except PermissionError:
        raise LibraryDataError("%s is corrupt: the server may not read it (permission denied)" % path.name)


# ------------------------------------------------------------------ normalising and matching
def norm(s: str | None) -> str:
    return textfold.norm(s)       # one folding for the query and the indexed text (đ to d, accents of any script)


def title_norm(t: str | None) -> str:
    toks = norm(t).split()
    while toks and toks[0] in ARTICLES:
        toks = toks[1:]
    return " ".join(toks)


def artist_tokens(a: str | None) -> list[str]:
    return [t for t in norm(a).split() if t not in PARTICLES]


def artists_match(a: str | None, b: str | None) -> bool:
    ta, tb = artist_tokens(a), artist_tokens(b)
    if not ta or not tb:
        return False
    return ta[-1] in tb or tb[-1] in ta


def titles_match(a: str | None, b: str | None) -> bool:
    x, y = title_norm(a), title_norm(b)
    if not x or not y:
        return False
    if x == y:
        return True
    if difflib.SequenceMatcher(None, x, y).ratio() >= 0.88:
        return True
    s, l = sorted((x, y), key=len)
    return len(s.split()) >= 3 and len(s) >= 14 and (l + " ").startswith(s + " ")


def works_match(a: dict, b: dict) -> bool:
    """Conservative: same artist and similar title; with an unknown artist only an identical title counts."""
    ya, yb = a.get("year_num"), b.get("year_num")
    if ya is not None and yb is not None and abs(ya - yb) > 25:
        return False
    if a.get("artist") and b.get("artist"):
        return artists_match(a["artist"], b["artist"]) and titles_match(a["title"], b["title"])
    return title_norm(a["title"]) == title_norm(b["title"]) and len(title_norm(a["title"]).split()) >= 2


def slug(s: str, words: int = 6) -> str:
    return "-".join(norm(s).split()[:words]) or "x"


SMALL_WORDS = {"a", "an", "the", "of", "and", "in", "on", "at", "to", "with", "after", "du", "de", "la", "le"}
_APOS = ("’", "'")


def _cap(p: str) -> str:
    """Upper-case the first letter, lower-case the rest ("“the" -> "“The")."""
    for i, ch in enumerate(p):
        if ch.isalpha():
            return p[:i] + ch.upper() + p[i + 1:].lower()
    return p


def title_case_words(s: str) -> str:
    """Re-case a title that is ALL UPPER or all lower case; a title in any other case is returned exactly as written.
    Small words (a, an, the, of, and, in, on, at, to, with, after, du, de, la, le) stay lower case except as the first
    word (and the first word after a dash or a colon), and a letter after an apostrophe inside a word is never capitalised ("Artist’s", not "Artist’S")."""
    if not s or not (s.isupper() or s.islower()):
        return s
    out = []
    words = s.split()
    for i, w in enumerate(words):
        prev = words[i - 1] if i else ""
        # a subtitle starts like a title: after a dash, after "word:" and after a plate number ("Mode: 1, The ...")
        first = i == 0 or prev in ("-", "–", "—") or prev.endswith(":") or (prev.endswith(",") and prev[:-1].isdigit())
        parts = re.split(r"([-/’'])", w)          # odd indices are the separators
        cased = []
        for j, p in enumerate(parts):
            if j % 2 == 1 or not p:
                cased.append(p)
                continue
            low = p.lower()
            if j >= 2 and parts[j - 1] in _APOS and any(c.isalpha() for c in parts[j - 2]):
                cased.append(low)
            elif (not first or j > 0) and re.sub(r"\W", "", low) in SMALL_WORDS:
                cased.append(low)
            else:
                cased.append(_cap(p))
        out.append("".join(cased))
    return " ".join(out)


# ------------------------------------------------------------------ canonical artist names
def artists_path() -> Path:
    return config.LIB_DIR / "overrides" / "artists.json"


_ARTISTS_CACHE: dict = {}


def _artist_tables() -> tuple[dict[str, str], dict[str, str]]:
    """-> ({norm(spelling): canonical name}, {canonical name: key word}); both empty when the file is missing or damaged."""
    f = artists_path()
    try:
        st = f.stat()
        stamp = (str(f), st.st_mtime_ns, st.st_size)
    except OSError:
        return {}, {}
    if _ARTISTS_CACHE.get("stamp") != stamp:
        index: dict[str, str] = {}
        keys: dict[str, str] = {}
        try:
            d = read_json(f)
        except ValueError:
            d = {}
        for can, ent in (d.items() if isinstance(d, dict) else []):
            if isinstance(ent, dict):
                variants, kn = ent.get("variants"), ent.get("key_name")
            else:
                variants, kn = ent, None
            if not isinstance(can, str) or not isinstance(variants or [], list):
                continue
            if isinstance(kn, str) and norm(kn):
                keys[can] = norm(kn).replace(" ", "-")
            for v in [can] + [x for x in (variants or []) if isinstance(x, str)]:
                index.setdefault(norm(v), can)
        _ARTISTS_CACHE.update(stamp=stamp, index=index, keys=keys)
    return _ARTISTS_CACHE["index"], _ARTISTS_CACHE["keys"]


def load_artist_names() -> dict[str, str]:
    """library/overrides/artists.json is {canonical name: [variant spellings]}, or {canonical name: {"variants": [...],
    "key_name": "word"}} where key_name is the word artwork keys start with when the last word of the name is a poor key
    ("Rembrandt van Rijn" -> rembrandt-...). -> {norm(spelling): canonical name}, so that case, accents, hyphens and
    apostrophes never matter. Missing or damaged file: no canonical names."""
    return _artist_tables()[0]


def artist_key_word(artist: str | None) -> str:
    """The word an artwork key starts with: the artist's `key_name` from artists.json, else the last word of the name
    (not counting particles such as "van"), else "unknown"."""
    kn = _artist_tables()[1].get(artist or "")
    if kn:
        return kn
    tk = artist_tokens(artist)
    return tk[-1] if tk else "unknown"


NAME_PARTICLES = {"van", "von", "der", "den", "de", "da", "di", "del", "della", "du", "des", "dos", "la", "le", "af", "y"}


def name_case(s: str) -> str:
    """A person's name in capitals (or all lower case) -> usual case: particles (van, de, da, di, la, af ...) stay lower
    case except first, "O’Keeffe" and "Mc" keep a capital. Names that are written in mixed case are never passed here."""
    out = []
    for i, w in enumerate(s.split()):
        parts = re.split(r"([-’'])", w)
        cased = []
        for j, p in enumerate(parts):
            if j % 2 == 1 or not p:
                cased.append(p)
            elif i > 0 and j == 0 and p.lower() in NAME_PARTICLES:
                cased.append(p.lower())
            else:
                c = _cap(p)
                cased.append(re.sub(r"^(Mc)([a-z])", lambda m: m.group(1) + m.group(2).upper(), c))
        out.append("".join(cased))
    return " ".join(out)


def split_attribution(raw: str | None) -> tuple[str | None, str | None]:
    """"After Cornelis van Dalem" -> ("Cornelis van Dalem", "after"); "Zhang Zeduan (Attrib.)" -> ("Zhang Zeduan",
    "attributed"); a plain name -> (name, None)."""
    if not raw or not isinstance(raw, str) or not raw.strip():
        return None, None
    name = raw.strip()
    m = re.match(r"^after\s+(.+)$", name, flags=re.I)
    if m:
        return m.group(1).strip(), "after"
    m = re.match(r"^(.+?)\s*\((?:attrib\.?|attributed)\)$", name, flags=re.I)
    if m:
        return m.group(1).strip(), "attributed"
    return name, None


def canonical_artist(raw: str | None) -> tuple[str | None, str | None]:
    """An artist as written in a source -> (the one spelling used in the whole catalogue, attribution or None).
    The spelling comes from library/overrides/artists.json; a name that is not in it is kept as written (re-cased
    only when it is all upper case)."""
    name, attr = split_attribution(raw)
    if not name:
        return None, None
    can = load_artist_names().get(norm(name))
    if can:
        return can, attr
    return (name_case(name) if name.isupper() or name.islower() else name), attr


# ------------------------------------------------------------------ the title, artist and year in the clean text
def _clean_header(bid: str, w: dict) -> tuple[str | None, list[str]] | None:
    """(# heading, [meta] lines) of the first page of the work that has them (a plate may come first), or None."""
    a, b = w["pdf_pages"]
    for p in ((a, a + 1) if a < b else (a,)):
        cf = config.LIB_DIR / "clean_text" / bid / f"page_{p:04d}.txt"
        if not cf.is_file():
            continue
        try:
            lines = [ln.strip() for ln in cf.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except (OSError, UnicodeDecodeError):
            continue
        h1, metas = None, []
        for ln in lines:
            if re.match(r"^#\s+", ln) and h1 is None:
                h1 = re.sub(r"^#\s+", "", ln).strip()
            elif re.match(r"^\[meta\]", ln, re.I):
                metas.append(re.sub(r"^\[meta\]\s*", "", ln, flags=re.I).strip())
        if h1 or metas:
            return h1, metas
    return None


def extract_clean_meta(bid: str, w: dict) -> dict[str, str]:
    """What the cleaned text of a work's first page says, as written: {title, artist, year, headline}, only the keys
    it has. Nothing is re-cased or reformatted here (`pick_fields` does that, once, for every source)."""
    head = _clean_header(bid, w)
    if head is None:
        return {}
    h1, metas = head
    res: dict[str, str] = {}
    if bid in ("payne_gae", "hodge_aid"):
        if h1:
            res["title"] = h1
        for m in metas:
            if re.match(r"^CHAPTER\s+\d+$", m, re.I):
                continue
            key = "year" if re.search(r"\d", m) else "artist"
            res.setdefault(key, m)
    elif bid == "hagen_wgps":
        if metas and ":" in metas[0]:
            art_part, _, rest = metas[0].partition(": ")
            t_part, y_part = parse.split_year_tail(rest)
            art_part, t_part = parse.fix_ocr(art_part.strip()), parse.fix_ocr(t_part.strip())
            if art_part and not art_part.lower().startswith("artist unknown"):
                res["artist"] = art_part
            if t_part:
                res["title"] = t_part
            if y_part:
                res["year"] = y_part
        if h1:
            res["headline"] = h1
    elif bid == "grovier_nws":
        if metas:
            ym = re.search(r"^\((.*)\)$", metas[0])
            res["year"] = (ym.group(1) if ym else metas[0]).strip()
    elif bid == "brookehitching_mad":
        m = re.match(r"^(.*?)\s*\(([^()]*\d[^()]*|[^()]*centur[^()]*)\)(.*)$", h1 or "")
        if m:
            t_str, y_str, tail = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            a_str = None
            if tail.startswith(","):
                a_str = re.split(r"\s+and\s+", tail[1:].strip(), flags=re.I)[0].strip() or None
            pm = re.match(r"^([A-Z][\w.]*(?:\s+(?:[a-z]+\s+)?[A-Z][\w.]*)+)’s\s+(.+)$", t_str, re.I)
            if pm and not a_str and not pm.group(1).lower().startswith(("mr ", "mrs ", "dr ", "st ")):
                a_str, t_str = pm.group(1), pm.group(2)
            res["title"] = t_str
            if a_str:
                res["artist"] = a_str
            if y_str:
                res["year"] = y_str
    elif bid == "dasal_artcurious":
        if h1:
            res["title"] = h1
    return {k: v for k, v in res.items() if v}


def pick_fields(bid: str, outline: dict, clean: dict) -> tuple[dict, dict]:
    """The title, artist, attribution and year of one work: each field from the clean text if it has one, else from the
    PDF outline. Everything is normalised here and nowhere else: title_case_words for the title, canonical_artist for the
    artist (an "after" goes to `attribution`), parse_year / print_year for the year (text that is not a year goes to
    `year_raw`, never to `year`). -> (fields, field_src) where field_src[field] is "clean" or "outline"."""
    use = CLEAN_FIELDS.get(bid)
    if use is not None:
        clean = {k: v for k, v in clean.items() if k in use}
    scan = config.BOOK_BY_ID[bid]["pdf_type"] == "scan"
    fields: dict = {}
    src: dict = {}

    def same_but_case(a: str, b: str | None) -> bool:
        """`a` is written in capitals (or all lower case) and `b` is the same text in better case."""
        return bool(b) and (a.isupper() or a.islower()) and a.casefold() == b.casefold()

    for name, d in (("clean", clean), ("outline", outline)):
        t = (d.get("title") or "").strip()
        if t and "title" not in fields:
            t = re.sub(r"(?<=[^\W\d_])-\s+(?=[^\W\d_])", "-", t)      # "Master- Stroke": a line break in the print
            t = parse.fix_ocr(t) if scan and name == "clean" else t
            o = (outline.get("title") or "").strip()
            fields["title"] = o if name == "clean" and same_but_case(t, o) else title_case_words(t)
            src["title"] = name
        a = (d.get("artist") or "").strip()
        if a and "artist" not in fields:
            o = split_attribution(outline.get("artist"))[0]
            a_name, a_attr = split_attribution(a)
            if name == "clean" and same_but_case(a_name or a, o):
                a = o                                           # same name, the outline's case is better
            fields["artist"], attr = canonical_artist(a)
            attr = attr or a_attr or d.get("attribution")
            if attr:
                fields["attribution"] = attr
            src["artist"] = name
    raw = None
    for name, d in (("clean", clean), ("outline", outline)):
        year, yraw = parse.normalise_year(d.get("year"))
        if year:
            fields["year"], src["year"], raw = year, name, None
            break
        if yraw and raw is None:
            raw = (name, yraw)
    else:
        if raw:
            fields["year"], fields["year_raw"], src["year"] = None, raw[1], raw[0]
    fields.setdefault("year", None)
    return fields, src


# ------------------------------------------------------------------ rights estimate
def estimate_rights(w: dict, today_year: int | None = None) -> dict:
    """Only a hint for the human. pd_likely: artist died >= 71 years ago, or work before 1900.
    copyright_likely: artist died < 71 years ago, is alive, or work after 1955 with unknown death year."""
    now = today_year or dt.date.today().year
    death, alive, yn = w.get("artist_death"), w.get("artist_alive"), w.get("year_num")
    if alive:
        return {"status": "copyright_likely", "basis": "nghệ sĩ còn sống"}
    if death:
        ago = now - death
        if ago >= YEAR_PD:
            return {"status": "pd_likely", "basis": f"nghệ sĩ mất năm {death} ({ago} năm trước)"}
        return {"status": "copyright_likely", "basis": f"nghệ sĩ mất năm {death} (mới {ago} năm)"}
    if yn is not None and yn < 1900:
        return {"status": "pd_likely", "basis": f"tác phẩm làm trước 1900 (năm {yn}), chưa rõ năm mất"}
    if yn is not None and yn > 1955:
        return {"status": "copyright_likely", "basis": f"tác phẩm làm sau 1955 (năm {yn}), chưa rõ năm mất"}
    return {"status": "unknown", "basis": "thiếu năm mất và năm sáng tác"}


# ------------------------------------------------------------------ overrides
def overrides_path(book_id: str) -> Path:
    return config.LIB_DIR / "overrides" / f"{book_id}.json"


def load_overrides(book_id: str) -> dict:
    f = overrides_path(book_id)
    if not f.is_file():
        return {}
    try:
        d = read_json(f)
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def apply_overrides(works: list[dict], overrides: dict) -> list[dict]:
    """Merge overrides (`{work_id: {field: value}}`, a bare number key like "7" also works) over the works, by
    work id and field. Only known fields; `rights` is merged key by key. An overridden field is marked
    field_src[field] = "override" (the most trusted source); a year is parsed and printed like any other, an artist
    gets its canonical spelling."""
    out = []
    for w in works:
        o = overrides.get(w["id"]) or overrides.get(str(w["n"])) or {}
        w = dict(w)
        for k, v in o.items():
            if k not in FIELDS_OVERRIDABLE:
                continue
            if k == "rights" and isinstance(v, dict):
                w["rights"] = {**(w.get("rights") or {}), **v}
                continue
            if k == "year":
                w["year"], yraw = parse.normalise_year(v)
                if yraw:
                    w["year_raw"] = yraw
                else:
                    w.pop("year_raw", None)
            elif k == "artist" and isinstance(v, str):
                w["artist"], attr = canonical_artist(v)
                if attr:
                    w["attribution"] = attr
            else:
                w[k] = v
            w["field_src"] = {**(w.get("field_src") or {}), ("year" if k == "year_raw" else k): "override"}
        if "year" in o or "year_raw" in o:
            w["year_num"] = parse.year_num(w.get("year") or w.get("year_raw"))
        out.append(w)
    return out


# ------------------------------------------------------------------ loaders
def books_overrides_path() -> Path:
    return config.LIB_DIR / "overrides" / "books.json"


DEFAULT_TRUST = {b["id"]: {"trust": "normal", "trust_note": ""} for b in config.BOOKS}
DEFAULT_TRUST["grovier_nws"] = {"trust": "low", "trust_note": config.TRUST_NOTE_LOW}
TRUST_LEVELS = restored.LEVELS            # normal, restored, low
# Where a value of the catalogue (title, artist, year of an artwork) comes from a book that is machine-translated at its root,
# whether or not its text was restored: restored text does not make the names of the catalogue more trusted.
MACHINE_TEXT = ("low", "restored")


def _books_entry(book_id: str) -> dict:
    """What library/overrides/books.json says about one book ({} when nothing, or when the file is damaged)."""
    f = books_overrides_path()
    if not f.is_file():
        return {}
    try:
        tbl = read_json(f)
        o = (tbl.get(book_id) if isinstance(tbl, dict) else None) or {}
    except ValueError:
        o = {}
    return o if isinstance(o, dict) else {}


def book_trust(book_id: str) -> dict:
    """{trust: normal|restored|low, trust_note} of a BOOK, from library/overrides/books.json (human-editable), else the default.
    This is the level of the book as a whole. The level of one work is work_trust()."""
    out = dict(DEFAULT_TRUST.get(book_id, {"trust": "normal", "trust_note": ""}))
    o = _books_entry(book_id)
    if o.get("trust") in TRUST_LEVELS:
        out["trust"] = o["trust"]
        if o["trust"] == "restored":
            out["trust_note"] = config.TRUST_NOTE_RESTORED
    if isinstance(o.get("trust_note"), str):
        out["trust_note"] = o["trust_note"]
    return out


def book_forced(book_id: str) -> bool:
    """Does books.json FORCE the level of the book, so that every one of its works gets that level and no review is asked?
    Yes when the entry has `"force": true`, or when it names a level other than the built-in one of the book (`low` for
    grovier_nws, `normal` for the others). An entry that only repeats the built-in level is not a decision: build() writes
    one for every book, so it must not switch the restoration off."""
    o = _books_entry(book_id)
    level = o.get("trust")
    if level not in TRUST_LEVELS:
        return False
    return o.get("force") is True or level != DEFAULT_TRUST.get(book_id, {"trust": "normal"})["trust"]


def work_trust_why(work: dict) -> tuple[dict, str]:
    """({trust: normal|restored|low, trust_note}, why) of ONE work (`work` has `id` and `pdf_pages`).
    - books.json forces a level for the book (book_forced): every work gets it. `restored` forced needs the restored page files
      of the work, without them the work is `low`; it does not ask for the review, the owner vouches for it.
    - the book is `low` (as built in, or repeated in books.json): the work is `restored` when restored.check() says yes, else `low`.
    - otherwise (`normal`, not forced) the work keeps the level of its book."""
    bid = work["id"].split("/")[0]
    book = book_trust(bid)
    if book_forced(bid):
        if book["trust"] == "restored" and not restored.has_pages(work):
            return {"trust": "low", "trust_note": config.TRUST_NOTE_LOW}, "forced restored, but the work has no restored pages"
        return book, "forced by books.json"
    if book["trust"] == "low":
        ok, why = restored.check(work)
        if ok:
            return {"trust": "restored", "trust_note": config.TRUST_NOTE_RESTORED}, why
        return book, why
    return book, "the level of the book"


def work_trust(work: dict) -> dict:
    """{trust: normal|restored|low, trust_note} of one work; see work_trust_why."""
    return work_trust_why(work)[0]


def book_json(book_id: str) -> dict:
    return read_json(config.book_dir(book_id) / "book.json")


def load_books() -> list[dict]:
    out = []
    for b in config.BOOKS:
        f = config.book_dir(b["id"]) / "book.json"
        if f.is_file():
            out.append({**read_json(f), **book_trust(b["id"])})
    return out


def load_works(book_id: str) -> list[dict]:
    f = config.book_dir(book_id) / "works.json"
    if not f.is_file():
        return []
    # A works.json written before `_public` always wrote `artist` has no such key for a work whose book names no artist: read it as null.
    return [w if "artist" in w else {**w, "artist": None} for w in apply_overrides(read_json(f), load_overrides(book_id))]


def load_work(book_id: str, n: int) -> dict | None:
    for w in load_works(book_id):
        if w["n"] == n:
            return w
    return None


class ArtworksDict(dict):
    """The artworks by key. Iteration, `in`, `len` and `keys()` see only the current keys; `d[key]` and `d.get(key)` also
    accept an OLD key (an alias, see aliases.json) and answer with the current artwork, so that a link made before a key
    changed still opens."""

    def __init__(self, data: dict, aliases: dict[str, str] | None = None):
        super().__init__(data)
        self.aliases: dict[str, str] = {}
        for k, v in data.items():
            for a in (v.get("aliases") or []) if isinstance(v, dict) else []:
                if isinstance(a, str) and a not in data:
                    self.aliases[a] = k
        for a, k in (aliases or {}).items():
            if isinstance(a, str) and isinstance(k, str) and a not in data and k in data:
                self.aliases[a] = k

    def resolve(self, key):
        """The current key of `key` (itself when it is current), or None when there is no such artwork."""
        if dict.__contains__(self, key):
            return key
        return self.aliases.get(key) if isinstance(key, str) else None

    def __getitem__(self, key):
        k = self.resolve(key)
        if k is None:
            raise KeyError(key)
        return dict.__getitem__(self, k)

    def get(self, key, default=None):
        k = self.resolve(key)
        return default if k is None else dict.__getitem__(self, k)


def aliases_path() -> Path:
    return config.LIB_DIR / "overrides" / "aliases.json"


def load_aliases() -> dict[str, str]:
    """library/overrides/aliases.json: {old artwork key: current artwork key}. Kept by regroup (it adds every key that
    a rebuild changed or merged away); a person may add lines too."""
    f = aliases_path()
    if not f.is_file():
        return {}
    try:
        d = read_json(f)
    except ValueError:
        return {}
    return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(d, dict) else {}


def load_artworks() -> ArtworksDict:
    f = config.LIB_DIR / "artworks.json"
    d = read_json(f) if f.is_file() else {}
    if not isinstance(d, dict):
        raise LibraryDataError("artworks.json is corrupt: the top level must be an object")
    return ArtworksDict(d, load_aliases())


def resolve_key(key: str) -> str | None:
    """The current artwork key for a current or an old key; None when unknown."""
    return load_artworks().resolve(key)


def get_artwork(key: str) -> dict | None:
    """The artwork for a current or an old key (see ArtworksDict)."""
    return load_artworks().get(key)


# ------------------------------------------------------------------ build
def _stats(book_id: str, w: dict) -> dict:
    a, b = w["pdf_pages"]
    wt = extract.work_text(w)
    w["words"] = len(wt["text"].split())
    w["n_images"] = len(extract.images(book_id, a, b))
    w["headings"] = extract.headings(book_id, a, b) if config.BOOK_BY_ID[book_id]["pdf_type"] == "digital" else []
    return w


def build(only: list[str] | None = None, log=print) -> dict:
    """Parse every available book and write the catalogue. Returns a summary."""
    LIB = config.LIB_DIR
    (LIB / "overrides").mkdir(parents=True, exist_ok=True)
    all_works: dict[str, list[dict]] = {}
    summary: dict = {"books": {}, "unparsed": []}
    if not books_overrides_path().exists():  # explicit values so a human can change them; never rewritten
        write_json(books_overrides_path(), DEFAULT_TRUST)
    if not artwork_overrides_path().exists():
        artwork_overrides_path().write_text('{"merge": [], "split": []}\n', encoding="utf-8")
    for b in config.BOOKS:
        bid = b["id"]
        ovr_f = overrides_path(bid)
        if not ovr_f.exists():
            ovr_f.write_text("{}\n", encoding="utf-8")  # created empty, never rewritten by the build
        if only and bid not in only:
            if (config.book_dir(bid) / "works.json").is_file():
                all_works[bid] = read_json(config.book_dir(bid) / "works.json")
            continue
        pdf = config.book_pdf(bid)
        if pdf is None:
            log(f"[skip] {bid}: PDF missing")
            continue
        d = extract.doc(bid)
        raw = parse.PARSERS[bid](d)
        works = []
        for r in raw:
            w = {"id": f"{bid}/{r['n']:03d}", "n": r["n"], "pdf_pages": r["pdf_pages"]}
            outline = {k: r.get(k) for k in ("title", "artist", "year", "attribution")}
            clean = extract_clean_meta(bid, w)
            fields, src = pick_fields(bid, outline, clean)
            exc = parse.MADMAN_EXC.get(r["n"], {}) if bid == "brookehitching_mad" else {}
            for k, v in exc.items():          # hand-made corrections of the outline in parse.py: as good as an override
                fields[k], src[k] = (canonical_artist(v)[0] if k == "artist" else v), "override"
            w.update(fields)
            headline = clean.get("headline") or r.get("headline")
            if headline:
                w["headline"] = headline
            for k in ("artist_death", "artist_alive", "artist_dates", "pages_inferred"):
                if r.get(k) is not None:
                    w[k] = r[k]
            w["field_src"] = src
            w["year_num"] = parse.year_num(w.get("year") or w.get("year_raw"))
            works.append(w)
        works = apply_overrides(works, load_overrides(bid))
        for w in works:
            _stats(bid, w)
        all_works[bid] = works
        notes = {
            "payne_gae": "Chương = mục TOC `N Artist: Title year`, chạy đến trang trước mục kế tiếp; chương cuối đến trước 'Notes'.",
            "hodge_aid": "Bản scan có lớp OCR, không có TOC. Danh sách lấy từ 'Index of artworks' (PDF 428-429); trang sách = trang PDF - 4; mỗi mục 4 trang, có chỗ trống (trang giới thiệu) nên không đều.",
            "hagen_wgps": "Bản scan 2 cột, không TOC. 80 tranh x 6 trang từ PDF 12 (sách tr.8). Mục lục (PDF 9-11) được ghép theo cột/toạ độ.",
            "grovier_nws": "TOC 57 mục `NN  Artist, Title`; một số mục không có tác giả (công trình, tác phẩm vô danh). Không có năm trong TOC.",
            "brookehitching_mad": "TOC ~60 mục, định dạng tiêu đề hỗn hợp, năm trong ngoặc; nhiều mục là nhóm tác phẩm.",
            "dasal_artcurious": "12 chương theo chủ đề (3 phần), không phải từng tác phẩm; tên chương lấy từ trang đầu chương.",
        }[bid]
        book = {"id": bid, "title": b["title"], "author": b["author"], "file": pdf.name, "pages": len(d),
                "pdf_type": b["pdf_type"], "unit": b["unit"], "n_works": len(works), "notes": notes,
                **book_trust(bid)}
        write_json(config.book_dir(bid) / "book.json", book)
        summary["books"][bid] = len(works)

    for bid in config.BOOK_BY_ID:
        if bid in all_works:
            write_json(config.book_dir(bid) / "works.json", [_public(w) for w in apply_overrides(all_works[bid], load_overrides(bid))])
    reg = regroup()
    summary.update(reg)
    for bid in config.BOOK_BY_ID:
        for w in load_works(bid):
            miss = [k for k in ("title", "artist", "year") if not w.get(k)]
            if miss:
                summary["unparsed"].append({"id": w["id"], "missing": miss, "title": w.get("title")})
    write_json(config.LIB_DIR / "unparsed.json", summary["unparsed"])
    return summary


# ------------------------------------------------------------------ artwork overrides (forced merges / splits)
def artwork_overrides_path() -> Path:
    return config.LIB_DIR / "overrides" / "artworks.json"


def load_artwork_overrides() -> dict:
    f = artwork_overrides_path()
    d = {}
    if f.is_file():
        try:
            d = read_json(f)
        except ValueError:
            d = {}
    if not isinstance(d, dict):
        d = {}
    return {"merge": [list(g) for g in d.get("merge", []) if isinstance(g, list)],
            "split": [x for x in d.get("split", []) if isinstance(x, str)]}


def save_artwork_overrides(d: dict) -> None:
    write_json(artwork_overrides_path(), {"merge": d.get("merge", []), "split": d.get("split", [])})


def source_rank(bid: str, src: str | None, trust: dict[str, str] | None = None) -> int:
    """How far a value is trusted (lower = more): see SRC_RANK. `src` is a field_src value: override, clean or outline."""
    if src == "override":
        return SRC_RANK["override"]
    if (trust or {}).get(bid, book_trust(bid)["trust"]) in MACHINE_TEXT:
        return SRC_RANK["low_trust"]
    if src == "clean":
        return SRC_RANK["clean_scan"] if config.BOOK_BY_ID[bid]["pdf_type"] == "scan" else SRC_RANK["clean_digital"]
    return SRC_RANK["outline"]


def _project_pins(groups: dict[str, list[tuple[str, dict]]]) -> dict[str, str]:
    """group leader -> the artwork_key a project in projects/ already uses for (most of) its works."""
    pins: dict[str, str] = {}
    pdir = Path(getattr(config, "PROJECTS_DIR", None) or "projects")
    if not pdir.is_dir():
        return pins
    for pj in sorted(pdir.glob("*/project.json")):
        try:
            pdata = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pk = pdata.get("artwork_key") if isinstance(pdata, dict) else None
        pwids = {s.get("work_id") for s in (pdata.get("sources") or []) if isinstance(s, dict) and s.get("work_id")} \
            if isinstance(pdata, dict) else set()
        if not (isinstance(pk, str) and pk and pwids):
            continue
        best, best_n = None, 0
        for leader, members in groups.items():
            n = len({w["id"] for _, w in members} & pwids)
            if n > best_n:
                best, best_n = leader, n
        if best is not None:
            pins[best] = pk
    return pins


def update_aliases(previous: dict, artworks: dict, log=print) -> dict[str, str]:
    """Record every artwork key that this regroup changed or merged away as an alias of the artwork that took over its
    works (the most shared works). Aliases from earlier rebuilds follow their artwork when its key changes again; an alias
    that is also a current key is dropped (the current key wins). Writes library/overrides/aliases.json when it changes."""
    old = load_aliases()
    moved: dict[str, str] = {}
    for key, art in previous.items():
        if key in artworks or not isinstance(art, dict):
            continue
        ids = set(art.get("works") or [])
        best, best_n = None, 0
        for k, a in artworks.items():
            n = len(ids & set(a["works"]))
            if n > best_n:
                best, best_n = k, n
        if best:
            moved[key] = best
    out: dict[str, str] = {}
    for a, k in list(old.items()) + list(moved.items()):
        seen = set()
        while k in moved and k not in seen:       # the target itself moved on
            seen.add(k)
            k = moved[k]
        if a != k and a not in artworks and k in artworks:
            out[a] = k
    out = dict(sorted(out.items()))
    if out != old and (out or aliases_path().is_file()):
        write_json(aliases_path(), out)
    return out


def regroup(log=print) -> dict:
    """Recompute artwork groups, keys and rights from works.json (no PDF access), honouring
    library/overrides/artworks.json: `merge` = lists of work ids forced into one artwork, `split` = work ids that
    stay alone (never auto-merged). Writes works.json and artworks.json.
    Each field of an artwork (title, artist, attribution, year) comes from the most trusted of its works (source_rank of
    the work's field_src, then book order); keys that change are kept as aliases (update_aliases)."""
    order = [b["id"] for b in config.BOOKS]
    all_works = {bid: load_works(bid) for bid in order}
    trust = {bid: book_trust(bid)["trust"] for bid in order}
    ovr = load_artwork_overrides()
    splits = set(ovr["split"])
    for ws in all_works.values():
        for w in ws:
            w["year_num"] = parse.year_num(w.get("year") or w.get("year_raw"))
            w.pop("year_from_group", None)
    flat = [(bid, w) for bid in order for w in all_works[bid]]
    parent = {w["id"]: w["id"] for _, w in flat}
    group_books = {w["id"]: {bid} for bid, w in flat}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y, strict=True):
        rx, ry = find(x), find(y)
        if rx == ry or (strict and group_books[rx] & group_books[ry]):
            return
        parent[ry] = rx
        group_books[rx] |= group_books[ry]

    matchable = [(bid, w) for bid, w in flat if config.BOOK_BY_ID[bid]["unit"] != "themed_chapter"
                 and w["id"] not in splits]
    for i, (ba, wa) in enumerate(matchable):
        for bb, wb in matchable[i + 1:]:
            if ba != bb and works_match(wa, wb):
                union(wa["id"], wb["id"])
    for g in ovr["merge"]:
        ids = [x for x in g if x in parent]
        for x in ids[1:]:
            union(ids[0], x, strict=False)
    groups: dict[str, list[tuple[str, dict]]] = {}
    for bid, w in flat:
        groups.setdefault(find(w["id"]), []).append((bid, w))

    pins = _project_pins(groups)
    known = [w for w in all_works.get("hodge_aid", []) if w.get("artist_death") or w.get("artist_alive")]
    keys_used: dict[str, int] = {}
    artworks: dict[str, dict] = {}
    for leader, members in groups.items():
        ws = [w for _, w in members]

        def best(field, usable=lambda v: bool(v)):
            """The work whose `field` is the most trusted among the works that have it."""
            cands = [(source_rank(bid, (w.get("field_src") or {}).get(field if field != "year_raw" else "year",
                                                                     "outline"), trust),
                      order.index(bid), w["n"], w) for bid, w in members if usable(w.get(field))]
            return min(cands, key=lambda c: c[:3])[3] if cands else None

        tw, aw, yw = best("title"), best("artist"), best("year")
        yrw = None if yw else best("year_raw")
        title = tw["title"] if tw else ws[0]["title"]
        artist, attribution = canonical_artist(aw["artist"]) if aw else (None, None)
        attribution = attribution or (aw.get("attribution") if aw else None)
        if artist and not attribution:
            attribution = next((w["attribution"] for w in ws if w.get("attribution") and canonical_artist(w.get("artist"))[0] == artist), None)
        year = yw["year"] if yw else None
        ynum = next((w["year_num"] for w in ws if w.get("year_num") is not None), None)
        themed = config.BOOK_BY_ID[members[0][0]]["unit"] == "themed_chapter"
        if themed:
            base = f"theme-{members[0][0]}-{members[0][1]['n']:02d}"
        else:
            base = f"{artist_key_word(artist)}-{slug(title, 5)}"
        keys_used[base] = keys_used.get(base, 0) + 1
        key = base if keys_used[base] == 1 else f"{base}-{keys_used[base]}"
        final_key = pins.get(leader) or key
        art_entry = {"title": title, "artist": artist, "year": year}
        if attribution:
            art_entry["attribution"] = attribution
        if yrw:
            art_entry["year_raw"] = yrw["year_raw"]
        art_entry["works"] = [w["id"] for w in ws]
        artworks[final_key] = art_entry
        for w in ws:
            w["artwork_key"] = final_key
            if w.get("year_num") is None and ynum is not None:
                w["year_num"] = ynum
                w["year_from_group"] = True
            if not w.get("artist_death") and not w.get("artist_alive") and w.get("artist"):
                hit = next((k for k in known if artists_match(w["artist"], k["artist"])), None)
                if hit:
                    w["artist_death"], w["artist_alive"] = hit.get("artist_death"), hit.get("artist_alive", False)
            w["rights"] = estimate_rights(w)
            if themed:
                w["rights"] = {"status": "unknown", "basis": "chương theo chủ đề, không phải một tác phẩm"}
            w["rights"]["estimate"] = True
    for bid in order:
        if all_works[bid]:
            write_json(config.book_dir(bid) / "works.json",
                       [_public(w) for w in apply_overrides(all_works[bid], load_overrides(bid))])
    rebuilt: dict[str, dict] = {}
    for bid in order:
        for w in load_works(bid):  # a per-work `artwork_key` override moves the work between groups
            k = w["artwork_key"]
            rebuilt.setdefault(k, {**artworks.get(k, {"title": w["title"], "artist": w.get("artist"),
                                                       "year": w.get("year")}), "works": []})["works"].append(w["id"])
    af = config.LIB_DIR / "artworks.json"
    try:
        previous = read_json(af) if af.is_file() else {}
    except ValueError:
        previous = {}
    aliases = update_aliases(previous if isinstance(previous, dict) else {}, rebuilt, log)
    for old_key, k in aliases.items():
        rebuilt[k].setdefault("aliases", []).append(old_key)
    write_json(af, rebuilt)
    multi = {k: a for k, a in rebuilt.items() if len({x.split("/")[0] for x in a["works"]}) >= 2}
    gone = [k for k in PINNED_KEYS if k in previous and k not in rebuilt]
    return {"artworks": len(rebuilt), "multi_book": {k: a["works"] for k, a in multi.items()},
            "aliases": len(aliases), "pinned_missing": gone}


def _public(w: dict) -> dict:
    """Stored shape: the spec fields first, helper fields after. `artist` is always there (null when the book names none), like `year`:
    the shape of docs/design/2026-11-16-library-design.md lists it, and a work without the key made the shape test fail on the built library."""
    keys = ["id", "n", "title", "artist", "attribution", "year", "year_raw", "headline", "pdf_pages", "words",
            "n_images", "headings", "artwork_key", "rights"]
    w = w if "artist" in w else {**w, "artist": None}
    out = {k: w[k] for k in keys if k in w}
    for k, v in w.items():
        if k not in out:
            out[k] = v
    return out
