"""On-demand extraction from the book PDFs: text of a page range, embedded images, page renders (cached)."""
from __future__ import annotations

import io
import re
import threading
from pathlib import Path

import pymupdf

from . import config
from bti.fsio import atomic_replace

_LOCK = threading.RLock()
_DOCS: dict[str, "pymupdf.Document"] = {}
MIN_IMG = 150  # px on the short side; smaller embedded images are decoration


def doc(book_id: str):
    with _LOCK:
        d = _DOCS.get(book_id)
        if d is None:
            f = config.book_pdf(book_id)
            if f is None:
                raise FileNotFoundError(f"PDF of {book_id} is missing")
            d = _DOCS[book_id] = pymupdf.open(f)
        return d


def repair(text: str) -> str:
    """Soft hyphens: `Hast¬\\nings` -> `Hastings`; stray soft hyphens are dropped."""
    text = re.sub(r"[¬\xad]\s*\n\s*", "", text)
    return text.replace("¬", "").replace("\xad", "").replace("\x00", "")


def page_text(book_id: str, pdf_page: int) -> tuple[str, str]:
    """(text, source) of one 1-based PDF page; source is 'clean' (library/clean_text) or 'layer'."""
    f = config.LIB_DIR / "clean_text" / book_id / f"page_{pdf_page:04d}.txt"
    if f.is_file():
        return f.read_text(encoding="utf-8"), "clean"
    with _LOCK:
        d = doc(book_id)
        if not 1 <= pdf_page <= len(d):
            raise IndexError(pdf_page)
        return d[pdf_page - 1].get_text(), "layer"


def work_text(work: dict) -> dict:
    """Body text of one entry (clean pages when present, text layer otherwise); see clean.entry."""
    from . import clean
    e = clean.entry(work)
    return {"work_id": work["id"], "ocr": e["ocr"], "text_source": e["text_source"], "pdf_pages": work["pdf_pages"],
            "pages": e["pages"], "text": e["body"], "words": e["words"], "outline": e["outline"]}


def headings(book_id: str, a: int, b: int, limit: int = 10) -> list[str]:
    """Large-type lines of a digital book's page range (empty for scans)."""
    out: list[str] = []
    with _LOCK:
        d = doc(book_id)
        sizes, lines = [], []
        for p in range(a, min(b, len(d)) + 1):
            for blk in d[p - 1].get_text("dict")["blocks"]:
                if blk["type"]:
                    continue
                for ln in blk["lines"]:
                    t = " ".join(s["text"] for s in ln["spans"]).strip()
                    if not t:
                        continue
                    sz = max(s["size"] for s in ln["spans"])
                    sizes += [sz] * len(t)
                    lines.append((sz, t))
    if not sizes:
        return out
    sizes.sort()
    body = sizes[len(sizes) // 2]
    for sz, t in lines:
        t = re.sub(r"\s+", " ", t.replace("\xa0", " "))
        if sz >= body * 1.3 and 3 <= len(t) <= 90 and not t.isdigit() and t not in out:
            out.append(t)
        if len(out) >= limit:
            break
    return out


def images(book_id: str, a: int, b: int) -> list[dict]:
    """Embedded images (>= MIN_IMG px) in the page range, de-duplicated by xref. Digital books only."""
    if config.BOOK_BY_ID[book_id]["pdf_type"] != "digital":
        return []
    out, seen = [], set()
    with _LOCK:
        d = doc(book_id)
        for p in range(a, min(b, len(d)) + 1):
            for im in d[p - 1].get_images(full=True):
                xref, w, h = im[0], im[2], im[3]
                if xref in seen or min(w, h) < MIN_IMG:
                    continue
                seen.add(xref)
                out.append({"xref": xref, "page": p, "width": w, "height": h})
    return out


def _cache(book_id: str) -> Path:
    d = config.LIB_DIR / "cache" / book_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def clamp_w(w: int) -> int:
    return max(64, min(int(w), 2400))


def render_page(book_id: str, pdf_page: int, width: int = 800) -> Path:
    """JPEG render of one PDF page at `width` px, cached under library/cache/<book>/pages/."""
    width = clamp_w(width)
    out = _cache(book_id) / "pages" / f"{pdf_page:04d}_{width}.jpg"
    if out.is_file():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        d = doc(book_id)
        if not 1 <= pdf_page <= len(d):
            raise IndexError(pdf_page)
        page = d[pdf_page - 1]
        z = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        data = pix.tobytes("jpeg", jpg_quality=80)
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(data)
    atomic_replace(tmp, out)
    return out


def render_image(book_id: str, xref: int, width: int = 600) -> Path:
    """An embedded image resized to `width` px (JPEG), cached."""
    from PIL import Image
    width = clamp_w(width)
    out = _cache(book_id) / "img" / f"{xref}_{width}.jpg"
    if out.is_file():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        d = doc(book_id)
        pix = pymupdf.Pixmap(d, xref)
        if pix.colorspace is None or pix.colorspace.n not in (1, 3) or pix.alpha:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        data = pix.tobytes("png")
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        if im.width > width:
            im = im.resize((width, max(1, round(im.height * width / im.width))))
        tmp = out.with_suffix(".tmp")
        im.save(tmp, format="JPEG", quality=82)
        atomic_replace(tmp, out)
    return out
