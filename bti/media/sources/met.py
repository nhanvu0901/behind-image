"""The Met Open Access adapter (REST JSON, stdlib only).

Adapted from comic-book-pipeline/art_pipeline/sources/met.py. The comic imports
(`stages.user_errors`, `..config`) are replaced by local constants and bti.media.errors.
Docs: https://metmuseum.github.io/
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from .. import http
from ..errors import ImageTooSmall, NotFound
from ..imageinfo import image_size
from ..licence import check_licence

MET_API_BASE = "https://collectionapi.metmuseum.org/public/collection/v1"
MAX_IMAGE_BYTES = 150 * 1024 * 1024


def parse_candidate(meta: dict) -> dict:
    """Met object JSON to our normalised meta (same keys as commons.parse_page)."""
    oid = meta.get("objectID")
    big = (meta.get("primaryImage") or "").strip()
    return {
        "source": "met",
        "source_id": str(oid),
        "title": meta.get("title") or "",
        "page_url": meta.get("objectURL") or "",
        "url": big,
        "thumb_url": (meta.get("primaryImageSmall") or "").strip() or big,
        "width": 0, "height": 0, "size": 0,   # the API does not report pixels
        "mime": "image/jpeg", "kind": "image",
        "author": meta.get("artistDisplayName") or "",
        "artist": meta.get("artistDisplayName") or "",
        "year": meta.get("objectDate") or "",
        "date": meta.get("objectDate") or "",
        "description": meta.get("medium") or "",
        "department": meta.get("department") or "",
        "credit_line": meta.get("creditLine") or "",
        "licence": "CC0" if meta.get("isPublicDomain") else "",
        "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/" if meta.get("isPublicDomain") else "",
        "isPublicDomain": bool(meta.get("isPublicDomain")),
    }


def validate_cc0(meta: dict) -> tuple[bool, str]:
    """Hard gate: public domain and a primary image (accepts raw or normalised meta)."""
    if not meta.get("isPublicDomain"):
        return False, f"objectID {meta.get('objectID') or meta.get('source_id')} is NOT public domain, refused"
    if not ((meta.get("primaryImage") or meta.get("url") or "").strip()):
        return False, f"objectID {meta.get('objectID') or meta.get('source_id')} has no primaryImage"
    return True, ""


class MetSource:
    name = "met"

    def __init__(self, *, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep,
                 base: str = MET_API_BASE):
        self._opener, self._sleep, self.base = opener, sleep, base

    def _get(self, path: str, params: dict | None = None) -> dict:
        return http.get_json(f"{self.base}{path}", params, opener=self._opener, sleep=self._sleep)

    def fetch_meta(self, source_id: str) -> dict:
        try:
            raw = self._get(f"/objects/{int(source_id)}")
        except http.MediaHTTPError as exc:
            if exc.status == 404:
                raise NotFound(f"Met has no object {source_id}") from exc
            raise
        return parse_candidate(raw)

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        if kind != "image":
            return []
        data = self._get("/search", {"hasImages": "true", "isPublicDomain": "true", "q": query})
        ids = list(data.get("objectIDs") or [])[: max(1, int(limit))]
        def one(i):
            try:
                return self.fetch_meta(str(i))
            except (http.MediaHTTPError, NotFound):
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            metas = list(pool.map(one, ids))
        return [m for m in metas if m and m["url"]]

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        _, name, _ = check_licence(meta)
        return {"source": "met", "source_url": meta.get("page_url", ""),
                "author": meta.get("author") or "unknown, PD",
                "licence": name or "CC0", "licence_url": meta.get("licence_url", "")}

    def download(self, meta: dict, dest: Path, *, min_short_side: int = 0,
                 max_bytes: int = MAX_IMAGE_BYTES) -> Path:
        url = (meta.get("url") or "").strip()
        if not url:
            raise NotFound(f"objectID {meta.get('source_id')}: no primaryImage")
        dest = http.download_file(url, dest, max_bytes=max_bytes, opener=self._opener, sleep=self._sleep)
        if min_short_side:
            w, h = image_size(dest)
            if w and h and min(w, h) < min_short_side:
                Path(dest).unlink(missing_ok=True)
                raise ImageTooSmall(f"met {meta.get('source_id')}: {w}x{h} px, below {min_short_side}")
        return dest

    fetch_image = download
