"""Pixabay client (photos and videos) behind the media source interface.

API key read via `bti.script.env.get_key('PIXABAY_API_KEY')`.
No key is ever printed in logs, exceptions or API responses.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from .. import http
from ..errors import ImageTooSmall, NotFound
from ..imageinfo import image_size
from ..licence import check_licence
from bti.script import env

PIXABAY_BASE = "https://pixabay.com/api"
PIXABAY_VIDEO_BASE = "https://pixabay.com/api/videos"
PIXABAY_LICENCE = "Pixabay Content License"
PIXABAY_LICENCE_URL = "https://pixabay.com/service/license-summary/"
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024


def parse_image_hit(hit: dict) -> dict:
    hid = str(hit.get("id") or "")
    tags = (hit.get("tags") or "").strip()
    title = tags or f"Pixabay Image {hid}"
    author = (hit.get("user") or "").strip()
    w = int(hit.get("imageWidth") or 0)
    h = int(hit.get("imageHeight") or 0)
    sz = int(hit.get("imageSize") or 0)
    url = hit.get("largeImageURL") or hit.get("webformatURL") or ""
    thumb = hit.get("previewURL") or hit.get("webformatURL") or ""
    return {
        "source": "pixabay",
        "source_id": hid,
        "title": title,
        "page_url": hit.get("pageURL") or f"https://pixabay.com/photos/{hid}/",
        "url": url,
        "thumb_url": thumb,
        "width": w,
        "height": h,
        "size": sz,
        "mime": "image/jpeg",
        "kind": "image",
        "author": author,
        "artist": author,
        "licence": PIXABAY_LICENCE,
        "licence_url": PIXABAY_LICENCE_URL,
    }


def parse_video_hit(hit: dict) -> dict:
    hid = str(hit.get("id") or "")
    tags = (hit.get("tags") or "").strip()
    title = tags or f"Pixabay Video {hid}"
    author = (hit.get("user") or "").strip()
    dur = float(hit.get("duration") or 0)
    vids = hit.get("videos") or {}
    vfile = vids.get("large") or vids.get("medium") or vids.get("small") or vids.get("tiny") or {}
    w = int(vfile.get("width") or 0)
    h = int(vfile.get("height") or 0)
    sz = int(vfile.get("size") or 0)
    thumb = vfile.get("thumbnail") or f"https://i.vimeocdn.com/video/{hit.get('picture_id')}_640x360.jpg"
    return {
        "source": "pixabay",
        "source_id": hid,
        "title": title,
        "page_url": hit.get("pageURL") or f"https://pixabay.com/videos/{hid}/",
        "url": vfile.get("url") or "",
        "thumb_url": thumb,
        "width": w,
        "height": h,
        "duration": dur,
        "size": sz,
        "mime": "video/mp4",
        "kind": "video",
        "author": author,
        "artist": author,
        "licence": PIXABAY_LICENCE,
        "licence_url": PIXABAY_LICENCE_URL,
    }


class PixabaySource:
    name = "pixabay"

    def __init__(self, *, key: str | None = None, opener: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 base_url: str = PIXABAY_BASE, video_base_url: str = PIXABAY_VIDEO_BASE):
        self._key = key
        self._opener = opener
        self._sleep = sleep
        self.base_url = base_url
        self.video_base_url = video_base_url

    @property
    def key(self) -> str | None:
        if self._key is not None:
            return self._key or None
        return env.get_key("PIXABAY_API_KEY")

    def has_key(self) -> bool:
        return bool(self.key)

    def _get(self, url: str, params: dict) -> dict:
        k = self.key
        if not k:
            return {}
        p = {"key": k, **params}
        return http.get_json(url, p, opener=self._opener, sleep=self._sleep)

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        if not self.has_key():
            return []
        query = (query or "").strip()
        if not query:
            return []
        n = max(3, min(int(limit), 100))
        if kind == "image":
            data = self._get(f"{self.base_url}/", {"q": query, "image_type": "photo", "per_page": n})
            hits = data.get("hits") or []
            return [parse_image_hit(h) for h in hits if h.get("largeImageURL") or h.get("webformatURL")]
        elif kind == "video":
            data = self._get(f"{self.video_base_url}/", {"q": query, "per_page": n})
            hits = data.get("hits") or []
            return [parse_video_hit(h) for h in hits if (h.get("videos") or {}).get("large") or (h.get("videos") or {}).get("medium")]
        return []

    def fetch_meta(self, source_id: str) -> dict:
        if not self.has_key():
            raise NotFound("Pixabay key is not set")
        sid = str(source_id).strip()
        # Try photo first
        try:
            data = self._get(f"{self.base_url}/", {"id": sid})
            hits = data.get("hits") or []
            if hits:
                return parse_image_hit(hits[0])
        except http.MediaHTTPError as exc:
            if exc.status != 404:
                raise
        # Try video next
        try:
            vdata = self._get(f"{self.video_base_url}/", {"id": sid})
            vhits = vdata.get("hits") or []
            if vhits:
                return parse_video_hit(vhits[0])
        except http.MediaHTTPError as exc:
            if exc.status == 404:
                raise NotFound(f"Pixabay has no item {sid}") from exc
            raise
        raise NotFound(f"Pixabay has no item {sid}")

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        author = meta.get("author") or "Pixabay contributor"
        return {
            "source": "pixabay",
            "source_url": meta.get("page_url", ""),
            "author": author,
            "licence": PIXABAY_LICENCE,
            "licence_url": meta.get("licence_url") or PIXABAY_LICENCE_URL,
        }

    def download(self, meta: dict, dest: Path, *, min_short_side: int = 0,
                 max_bytes: int = MAX_IMAGE_BYTES) -> Path:
        url = (meta.get("url") or "").strip()
        if not url:
            raise NotFound(f"pixabay {meta.get('source_id')}: no download URL")
        is_video = meta.get("kind") == "video"
        mb = MAX_VIDEO_BYTES if is_video else max_bytes
        dest = http.download_file(url, dest, max_bytes=mb, opener=self._opener, sleep=self._sleep)
        if not is_video and min_short_side:
            w, h = image_size(dest)
            if w and h and min(w, h) < min_short_side:
                Path(dest).unlink(missing_ok=True)
                raise ImageTooSmall(f"pixabay {meta.get('source_id')}: {w}x{h} px, below {min_short_side}")
        return dest
