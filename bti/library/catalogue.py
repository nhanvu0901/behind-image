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

from . import config, extract, parse
from .. import textfold

PARTICLES = {"van", "von", "de", "da", "di", "del", "della", "le", "la", "the", "elder", "younger", "of", "der",
             "den", "af", "el", "jr", "sir", "mr"}
ARTICLES = {"the", "a", "an", "la", "le", "les", "il", "el", "l", "un", "une"}
RIGHTS_NOTE = "Ước lượng tự động, chỉ để tham khảo; cần người kiểm tra."
YEAR_PD = 71  # years after the artist's death
FIELDS_OVERRIDABLE = {"title", "artist", "year", "headline", "pdf_pages", "artwork_key", "rights", "notes",
                      "artist_death", "artist_alive"}


# ------------------------------------------------------------------ json io
def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class LibraryDataError(ValueError):
    """A library file (catalogue, dossier, overrides) is there but is not UTF-8 JSON. The message names the file; the editor
    answers 409 with `data_error: "library"`."""
    what = "library"


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as e:
        raise LibraryDataError("%s is corrupt: %s" % (path.name, str(e)[:100]))


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
    work id and field. Only known fields; `rights` is merged key by key."""
    out = []
    for w in works:
        o = overrides.get(w["id"]) or overrides.get(str(w["n"])) or {}
        w = dict(w)
        for k, v in o.items():
            if k not in FIELDS_OVERRIDABLE:
                continue
            if k == "rights" and isinstance(v, dict):
                w["rights"] = {**(w.get("rights") or {}), **v}
            else:
                w[k] = v
        if "year" in o:
            w["year_num"] = parse.year_num(w.get("year"))
        out.append(w)
    return out


# ------------------------------------------------------------------ loaders
def books_overrides_path() -> Path:
    return config.LIB_DIR / "overrides" / "books.json"


DEFAULT_TRUST = {b["id"]: {"trust": "normal", "trust_note": ""} for b in config.BOOKS}
DEFAULT_TRUST["grovier_nws"] = {"trust": "low", "trust_note": config.TRUST_NOTE_LOW}


def book_trust(book_id: str) -> dict:
    """{trust: normal|low, trust_note} from library/overrides/books.json (human-editable), else the default."""
    out = dict(DEFAULT_TRUST.get(book_id, {"trust": "normal", "trust_note": ""}))
    f = books_overrides_path()
    if f.is_file():
        try:
            tbl = read_json(f)
            o = (tbl.get(book_id) if isinstance(tbl, dict) else None) or {}
        except ValueError:
            o = {}
        if not isinstance(o, dict):
            o = {}
        if o.get("trust") in ("normal", "low"):
            out["trust"] = o["trust"]
        if isinstance(o.get("trust_note"), str):
            out["trust_note"] = o["trust_note"]
    return out


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
    return apply_overrides(read_json(f), load_overrides(book_id))


def load_work(book_id: str, n: int) -> dict | None:
    for w in load_works(book_id):
        if w["n"] == n:
            return w
    return None


def load_artworks() -> dict:
    f = config.LIB_DIR / "artworks.json"
    d = read_json(f) if f.is_file() else {}
    if not isinstance(d, dict):
        raise LibraryDataError("artworks.json is corrupt: the top level must be an object")
    return d


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
            w = {"id": f"{bid}/{r['n']:03d}", "n": r["n"], "title": r["title"], "artist": r.get("artist"),
                 "year": r.get("year")}
            if r.get("headline"):
                w["headline"] = r["headline"]
            w["pdf_pages"] = r["pdf_pages"]
            for k in ("artist_death", "artist_alive", "artist_dates", "pages_inferred"):
                if r.get(k) is not None:
                    w[k] = r[k]
            w["year_num"] = parse.year_num(w["year"])
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


def regroup(log=print) -> dict:
    """Recompute artwork groups, keys and rights from works.json (no PDF access), honouring
    library/overrides/artworks.json: `merge` = lists of work ids forced into one artwork, `split` = work ids that
    stay alone (never auto-merged). Writes works.json and artworks.json."""
    order = [b["id"] for b in config.BOOKS]
    all_works = {bid: load_works(bid) for bid in order}
    ovr = load_artwork_overrides()
    splits = set(ovr["split"])
    for ws in all_works.values():
        for w in ws:
            w["year_num"] = parse.year_num(w.get("year")) if w.get("year") else None
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

    known = [w for w in all_works.get("hodge_aid", []) if w.get("artist_death") or w.get("artist_alive")]
    keys_used: dict[str, int] = {}
    artworks: dict[str, dict] = {}
    for members in groups.values():
        ws = [w for _, w in members]
        rep = next((w for w in ws if w.get("artist")), ws[0])
        year = next((w["year"] for w in ws if w.get("year")), None)
        ynum = next((w["year_num"] for w in ws if w.get("year_num") is not None), None)
        themed = config.BOOK_BY_ID[members[0][0]]["unit"] == "themed_chapter"
        if themed:
            base = f"theme-{members[0][0]}-{members[0][1]['n']:02d}"
        else:
            tk = artist_tokens(rep.get("artist"))
            base = f"{tk[-1] if tk else 'unknown'}-{slug(rep['title'], 5)}"
        keys_used[base] = keys_used.get(base, 0) + 1
        key = base if keys_used[base] == 1 else f"{base}-{keys_used[base]}"
        artworks[key] = {"title": rep["title"], "artist": rep.get("artist"), "year": year,
                         "works": [w["id"] for w in ws]}
        for w in ws:
            w["artwork_key"] = key
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
    write_json(config.LIB_DIR / "artworks.json", rebuilt)
    multi = {k: a for k, a in rebuilt.items() if len({x.split("/")[0] for x in a["works"]}) >= 2}
    return {"artworks": len(rebuilt), "multi_book": {k: a["works"] for k, a in multi.items()}}


def _public(w: dict) -> dict:
    """Stored shape: the spec fields first, helper fields after."""
    keys = ["id", "n", "title", "artist", "year", "headline", "pdf_pages", "words", "n_images", "headings",
            "artwork_key", "rights"]
    out = {k: w[k] for k in keys if k in w}
    for k, v in w.items():
        if k not in out:
            out[k] = v
    return out
