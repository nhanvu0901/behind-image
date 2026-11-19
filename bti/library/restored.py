"""Restored text of a machine-translated book: the third trust level, `restored` (no model, no network).

A book that exists only as a machine-translated print (Grovier) is restored chapter by chapter by tools/clean_text/restore and
then read by an independent reviewer. Their files live in library/restored/<book_id>/:

    page_NNNN.txt              restored pages, in the clean-text page format; a passage that could not be restored is wrapped in
                               [[? ... ?]]
    report.json                {"works": {"<n>": {"pages": ["page_0017", ...], "ok": true, ...}}}  which pages belong to which work
    review.json                {"work_verdicts": [{"work": n, "verdict": usable | usable_after_fixes | not_usable, "fix_ids": [...]}]}
    review_fixes.json          [{"id": "F001", "work": 4, ...}]  the replacements the review asks for
    review_fixes.applied.json  {"applied": ["F001", ...]}  the fixes that were applied to the pages

check() decides per WORK whether its restored text may be used; catalogue.work_trust() turns that into a trust level. Every doubt
(a missing or damaged file, a missing record, a page range that moved) means "no": the work keeps the level of its book.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import config

LEVELS = ("normal", "restored", "low")
VERDICTS_OK = ("usable", "usable_after_fixes")
MARK = "[…]"                                   # what the model sees where the restorer marked a passage as unclear
_UNCLEAR = re.compile(r"\[\[\?.*?\?\]\]", re.S)
_CACHE: dict[Path, tuple[tuple[int, int], object]] = {}


def folder(book_id: str) -> Path:
    return config.LIB_DIR / "restored" / book_id


def page_file(book_id: str, pdf_page: int) -> Path:
    return folder(book_id) / f"page_{pdf_page:04d}.txt"


def forget() -> None:
    """Drop what was read from the review files (a test or a tool that rewrites them)."""
    _CACHE.clear()


def _json(path: Path):
    """The parsed file, None when it is missing or damaged. Cached by size and time of change: a dossier build asks for every work."""
    try:
        st = path.stat()
    except OSError:
        return None
    sig = (st.st_mtime_ns, st.st_size)
    hit = _CACHE.get(path)
    if hit is not None and hit[0] == sig:
        return hit[1]
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        obj = None
    _CACHE[path] = (sig, obj)
    return obj


def _work_no(v) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    return int(v) if isinstance(v, str) and v.strip().isdigit() else None


def review(book_id: str) -> dict | None:
    """What the review of a book says: {"verdicts": {n: [record]}, "fixes": {n: {id}}, "applied": {id}, "report": {n: record} | None}.
    None when the book has no restoration folder or no readable review (a book without one is never `restored`)."""
    d = folder(book_id)
    if not d.is_dir():
        return None
    rv = _json(d / "review.json")
    if not isinstance(rv, dict) or not isinstance(rv.get("work_verdicts"), list):
        return None
    verdicts: dict[int, list[dict]] = {}
    for r in rv["work_verdicts"]:
        n = _work_no(r.get("work")) if isinstance(r, dict) else None
        if n is not None:
            verdicts.setdefault(n, []).append(r)
    fixes: dict[int, set[str]] = {}
    lst = _json(d / "review_fixes.json")
    for f in lst if isinstance(lst, list) else []:
        n = _work_no(f.get("work")) if isinstance(f, dict) else None
        if n is not None and isinstance(f.get("id"), str):
            fixes.setdefault(n, set()).add(f["id"])
    ap = _json(d / "review_fixes.applied.json")
    applied_list = ap.get("applied") if isinstance(ap, dict) else ap
    applied = {x for x in applied_list if isinstance(x, str)} if isinstance(applied_list, list) else set()
    rep = _json(d / "report.json")
    report = None
    if isinstance(rep, dict) and isinstance(rep.get("works"), dict):
        report = {str(k): v for k, v in rep["works"].items() if isinstance(v, dict)}
    return {"verdicts": verdicts, "fixes": fixes, "applied": applied, "report": report}


def _pages(work: dict) -> list[int]:
    """The PDF pages of the work; [] when the range is missing, malformed or empty (a work without pages has no restored text)."""
    try:
        a, b = work["pdf_pages"]
        return list(range(int(a), int(b) + 1))
    except (KeyError, TypeError, ValueError):
        return []


def has_pages(work: dict) -> bool:
    """The work has pages, and every one of them has a restored file."""
    bid = work["id"].split("/")[0]
    pages = _pages(work)
    return bool(pages) and all(page_file(bid, p).is_file() for p in pages)


def check(work: dict) -> tuple[bool, str]:
    """May the restored text of this work be used? (yes/no, the reason in English). Yes only when all of this holds: the book has a
    restoration folder with a readable review; the review has a verdict for the work and it is `usable` or `usable_after_fixes`;
    every fix the review lists for the work (its fix_ids and the entries of review_fixes.json) is recorded as applied, and a
    `usable_after_fixes` verdict lists at least one; every page of the work has a restored file; and, when report.json is there, it
    lists the work as done with the same pages the catalogue gives (a catalogue rebuild that moved the page range stops it)."""
    bid, n = work["id"].split("/")
    n = int(n)
    rv = review(bid)
    if rv is None:
        return False, "no restoration folder with a readable review"
    recs = rv["verdicts"].get(n)
    if not recs:
        return False, "the review has no verdict for this work"
    for r in recs:
        if r.get("verdict") not in VERDICTS_OK:
            return False, f"verdict {r.get('verdict')}"
    need = set(rv["fixes"].get(n, ()))
    for r in recs:
        ids = r.get("fix_ids")
        need |= {x for x in ids if isinstance(x, str)} if isinstance(ids, list) else set()
    if any(r["verdict"] == "usable_after_fixes" for r in recs) and not need:
        return False, "verdict usable_after_fixes lists no fix, so nothing can be shown as applied"
    if not need <= rv["applied"]:
        return False, "fixes not recorded as applied: " + ", ".join(sorted(need - rv["applied"]))
    if not _pages(work):
        return False, "the work has no page range"
    missing = [p for p in _pages(work) if not page_file(bid, p).is_file()]
    if missing:
        return False, f"restored page {missing[0]:04d} is missing"
    if rv["report"] is not None:
        rec = rv["report"].get(str(n))
        if rec is None:
            return False, "report.json does not list this work"
        if rec.get("ok") is False:
            return False, "report.json says the restoration of this work failed"
        if isinstance(rec.get("pages"), list) and rec["pages"] != [f"page_{p:04d}" for p in _pages(work)]:
            return False, "the pages of report.json are not the pages of the catalogue"
    return True, "reviewed and fixes applied"


def page_text(book_id: str, pdf_page: int) -> str:
    return page_file(book_id, pdf_page).read_text(encoding="utf-8-sig")        # a byte-order mark would hide the first [page-type] tag


def mark_unclear(text: str) -> str:
    """Every [[? ... ?]] passage becomes the mark […]. A marker that is not closed (or not opened) makes its whole line one mark:
    what the restorer was unsure about is never given to the model, whatever the file looks like."""
    out = _UNCLEAR.sub(MARK, text)
    if "[[?" in out or "?]]" in out:
        out = "\n".join(MARK if ("[[?" in ln or "?]]" in ln) else ln for ln in out.split("\n"))
    return out


def count_words(text: str) -> int:
    """Words that remain: the marks do not count, and a piece of punctuation left beside a mark is not a word."""
    return sum(1 for t in text.replace(MARK, " ").split() if any(c.isalnum() for c in t))
