"""Images and pages of the books in the library, as a media source (no network: the PDFs are local).

A source id is `<book_id>/img/<xref>` (an image embedded in the PDF) or `<book_id>/page/<n>` (a whole page, 1-based).
The pixels come from `bti.library.extract`, imported only when something is rendered, so this module imports without
PyMuPDF. The renderer is injectable (tests pass a fake). What a book image is worth legally is not known here: its
licence is recorded as missing, which the advisory gate shows as the flag "unknown".
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable

from ..errors import NotFound

ID_RE = re.compile(r"([a-z0-9_]{1,40})/(img|page)/(\d{1,9})")
IMG_WIDTH = 2400          # an embedded image is rendered at its own size, never larger than this
PAGE_WIDTH = 1800         # a page is rendered this wide


def make_id(book_id: str, kind: str, ref: int) -> str:
    return f"{book_id}/{'img' if kind in ('img', 'image') else 'page'}/{int(ref)}"


def parse_id(source_id: str) -> tuple[str, str, int]:
    m = ID_RE.fullmatch(str(source_id or "").strip())
    if not m:
        raise NotFound(f"not a book image id: {str(source_id)[:60]!r}")
    return m.group(1), m.group(2), int(m.group(3))


def book_info(book_id: str) -> dict:
    from bti.library import config            # pure Python, no PyMuPDF
    b = config.BOOK_BY_ID.get(book_id)
    if b is None:
        raise NotFound(f"no such book: {book_id!r}")
    return b


def default_renderer(book_id: str, kind: str, ref: int, dest: Path) -> None:
    """Render with the library extractor (cached under library/cache) and copy the JPEG to `dest`."""
    from bti.library import extract
    try:
        out = extract.render_image(book_id, ref, IMG_WIDTH) if kind == "img" else extract.render_page(book_id, ref, PAGE_WIDTH)
    except (FileNotFoundError, IndexError) as e:
        raise NotFound(f"{book_id} {kind} {ref}: {e}") from e
    shutil.copyfile(out, dest)


class BookPageSource:
    name = "book"

    def __init__(self, *, renderer: Callable[[str, str, int, Path], None] | None = None):
        self._render = renderer or default_renderer

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        return []            # book images are listed per project (bti.picks), not searched

    def fetch_meta(self, source_id: str) -> dict:
        book_id, kind, ref = parse_id(source_id)
        info = book_info(book_id)
        what = f"p. {ref}" if kind == "page" else f"image {ref}"
        return {"source": "book", "source_id": make_id(book_id, kind, ref), "kind": "image", "mime": "image/jpeg",
                "title": f"{info['title']}, {what}", "author": info["author"], "page_url": "",
                "width": 0, "height": 0, "licence": "", "book_id": book_id, "ref": ref, "ref_kind": kind,
                "book_title": info["title"]}

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return False, "", "licence is missing (a picture taken from a book)"

    def credit(self, meta: dict) -> dict:
        what = f"p. {meta['ref']}" if meta.get("ref_kind") == "page" else f"image {meta.get('ref')}"
        return {"source": "book", "source_url": f"{meta.get('book_title', '')}, {what}",
                "author": meta.get("author") or "unknown", "licence": "", "licence_url": ""}

    def download(self, meta: dict, dest: Path, **kw) -> Path:
        dest = Path(dest)
        tmp = dest.with_name(dest.name + ".part")
        try:
            self._render(meta["book_id"], meta["ref_kind"], int(meta["ref"]), tmp)
            tmp.replace(dest)
        finally:
            tmp.unlink(missing_ok=True)
        return dest
