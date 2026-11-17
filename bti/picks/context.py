"""What step 4 reads from the rest of the project: the approved narration, the dossier, the books, the beat's search words."""
from __future__ import annotations

import re
from pathlib import Path

from bti.script import store as sstore

DETAIL_RE = re.compile(r"D(\d{1,3})")
PAGE_CAP = 40          # pages listed per source (a source is a short page range of a book)


def project_json(pdir: Path) -> dict:
    return sstore.read_object(Path(pdir) / "project.json", "project") or {}


def dossier(pdir: Path) -> dict:
    """The project's dossier ({} when it has none). A damaged one is DocumentCorrupt, like everywhere else."""
    proj = project_json(pdir)
    for cand in (proj.get("dossier"), "source/dossier.json"):
        if isinstance(cand, str) and cand and ".." not in cand.split("/") and not cand.startswith("/"):
            d = sstore.read_object(Path(pdir) / cand, "project")
            if d is not None:
                return d
    return {}


def identity(pdir: Path) -> dict:
    ident = dossier(pdir).get("identity") or {}
    proj = project_json(pdir)
    return {"title": str(ident.get("title") or proj.get("title") or ""), "artist": str(ident.get("artist") or proj.get("artist") or ""),
            "year": str(ident.get("year") or proj.get("year") or "")}


def details(pdir: Path) -> list[dict]:
    """The details of the dossier, named D1, D2... in order (the names the script's `show` words use)."""
    return [{"id": f"D{i + 1}", "label": str(t).strip().title()} for i, t in enumerate(dossier(pdir).get("details") or [])
            if isinstance(t, str) and t.strip()]


def narration_view(pdir: Path) -> dict:
    """The narration as the page needs it, and whether its approval stands:
    `{approved, reason, rev, chapters: [{id, title, role, beats: [{id, text, show, facts}]}], facts: {id: claim}}`."""
    n = sstore.load_narration(pdir)
    o = sstore.load_outline(pdir)
    if n is None:
        return {"present": False, "approved": False, "reason": None, "rev": None, "chapters": [], "facts": {}, "beat_ids": []}
    na = sstore.narration_approval(n, o)
    chapters = [{"id": c.id, "title": c.title, "role": c.role,
                 "beats": [{"id": b.id, "text": b.text, "show": list(b.show), "facts": list(b.facts)} for b in c.beats]}
                for c in n.chapters]
    return {"present": True, "approved": na["approved"], "reason": na["reason"], "rev": n.rev(), "chapters": chapters,
            "facts": {f.id: f.claim for f in o.facts} if o is not None else {},
            "beat_ids": [b["id"] for c in chapters for b in c["beats"]]}


def default_query(show: list[str], det: list[dict], ident: dict) -> str:
    """First search for a beat: its `show` words (a `D5` becomes the dossier's name for that detail); the painting's title
    and artist when the beat has none."""
    names = {d["id"]: d["label"] for d in det}
    words = []
    for w in show or []:
        w = str(w).strip()
        if not w:
            continue
        words.append(names.get(w, "") if DETAIL_RE.fullmatch(w) else w)
    words = [w for w in words if w]
    if not words:
        words = [ident.get("title", ""), ident.get("artist", "")]
    return " ".join(w for w in words if w)[:200].strip()


# ---------------------------------------------------------------- book images
def _work_n(work_id: str) -> int:
    try:
        return int(str(work_id).split("/")[1])
    except (IndexError, ValueError):
        return 0


def book_images(pdir: Path) -> dict:
    """The pictures of the books this project was made from: `{images: [...], pages: [...]}`.
    An image is one embedded in the PDF (from the dossier: work, xref, page, size); a page is any page of the source's range
    (capped). Each has `book_id`, `kind` (`img` | `page`), `ref` (xref | page number), `page`, `source_id` (the media source id),
    `thumb_url`, `label`. Nothing is rendered here."""
    from bti.library import config as libcfg           # pure Python
    from bti.media.sources import bookpage
    proj = project_json(pdir)
    dos = dossier(pdir)
    images, pages, seen = [], [], set()
    for s in proj.get("sources") or dos.get("sources") or []:
        if not isinstance(s, dict):
            continue
        book_id, wid = str(s.get("book_id") or ""), str(s.get("work_id") or "")
        if book_id not in libcfg.BOOK_BY_ID:
            continue
        n = _work_n(wid)
        short = libcfg.BOOK_BY_ID[book_id]["title"]
        pp = s.get("pdf_pages") or []
        a, b = (int(pp[0]), int(pp[1])) if len(pp) == 2 and all(isinstance(x, int) for x in pp) else (0, -1)
        for im in dos.get("images") or []:
            if not isinstance(im, dict) or im.get("work_id") != wid or not isinstance(im.get("xref"), int):
                continue
            sid = bookpage.make_id(book_id, "img", im["xref"])
            if sid in seen:
                continue
            seen.add(sid)
            images.append({"book_id": book_id, "kind": "img", "ref": im["xref"], "page": im.get("page"), "source_id": sid,
                           "width": int(im.get("width") or 0), "height": int(im.get("height") or 0),
                           "thumb_url": f"/api/library/works/{book_id}/{n}/image/{im['xref']}.jpg?w=420",
                           "label": f"{short}, ảnh trang {im.get('page')}"})
        for p in range(a, min(b, a + PAGE_CAP - 1) + 1):
            sid = bookpage.make_id(book_id, "page", p)
            pages.append({"book_id": book_id, "kind": "page", "ref": p, "page": p, "source_id": sid, "width": 0, "height": 0,
                          "thumb_url": f"/api/library/works/{book_id}/{n}/page/{p}.jpg?w=420", "label": f"{short}, trang {p}"})
    return {"images": images, "pages": pages}


def book_source_allowed(pdir: Path, source_id: str) -> bool:
    """Only pictures of the books this project was made from can be imported through the book route."""
    li = book_images(pdir)
    return any(x["source_id"] == source_id for x in li["images"] + li["pages"])
