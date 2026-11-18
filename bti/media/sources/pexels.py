"""Pexels client (photos and videos) behind the media source interface.

API key read via `bti.script.env.get_key('PEXELS_API_KEY')`.
No key is ever printed in logs, exceptions or API responses.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlencode, urlparse

from .. import http
from ..errors import ImageTooSmall, NotFound
from ..imageinfo import image_size
from ..licence import check_licence
from bti.script import env

PEXELS_BASE = "https://api.pexels.com/v1"
PEXELS_VIDEO_BASE = "https://api.pexels.com/videos"
PEXELS_LICENCE = "Pexels License"
PEXELS_LICENCE_URL = "https://www.pexels.com/license/"
MAX_IMAGE_BYTES = 100 * 1024 * 1024
MAX_VIDEO_BYTES = 300 * 1024 * 1024


def parse_photo(photo: dict) -> dict:
    pid = str(photo.get("id") or "")
    src = photo.get("src") or {}
    w = int(photo.get("width") or 0)
    h = int(photo.get("height") or 0)
    title = (photo.get("alt") or "").strip() or f"Pexels Photo {pid}"
    author = (photo.get("photographer") or "").strip()
    return {
        "source": "pexels",
        "source_id": pid,
        "title": title,
        "page_url": photo.get("url") or f"https://www.pexels.com/photo/{pid}/",
        "url": src.get("original") or src.get("large2x") or src.get("large") or "",
        "thumb_url": src.get("medium") or src.get("small") or src.get("tiny") or "",
        "width": w,
        "height": h,
        "size": 0,
        "mime": "image/jpeg",
        "kind": "image",
        "author": author,
        "artist": author,
        "licence": PEXELS_LICENCE,
        "licence_url": PEXELS_LICENCE_URL,
    }


_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}      # kept lower case inside a title


def title_from_page_url(page_url: str) -> str:
    """A video record has no title, but its page URL ends in a slug of words: `.../video/aerial-view-of-oslo-fjord-12345/`.
    Returns "Aerial View of Oslo Fjord", or "" when the URL has no words (`.../video/857251/`) or is not a URL."""
    try:
        u = urlparse(str(page_url or "").strip())
        parts = [p for p in unquote(u.path).split("/") if p]
    except ValueError:
        return ""
    if not u.netloc or "video" not in parts:                # only a video page URL: `<host>/[xx-xx/]video/<slug>/`
        return ""
    parts = parts[parts.index("video") + 1:]
    if not parts:
        return ""
    slug = re.sub(r"-\d+$", "", parts[-1].strip().lower())      # the trailing number is the id
    words = [w for w in slug.split("-") if w]
    if not words or not any(any(c.isalpha() for c in w) for w in words):
        return ""
    out = [w if (i and w in _SMALL_WORDS) else w[:1].upper() + w[1:] for i, w in enumerate(words)]
    return " ".join(out)[:100].strip()


def video_title(video: dict, author: str, vid: str) -> str:
    title = title_from_page_url(video.get("url") or "")
    if title:
        return title
    return f"Video của {author}" if author else f"Video Pexels {vid}"


def parse_video(video: dict) -> dict:
    vid = str(video.get("id") or "")
    files = video.get("video_files") or []
    # Pick highest resolution <= 1920 width, or first mp4
    best = None
    for f in files:
        if f.get("file_type") == "video/mp4" or "mp4" in str(f.get("link", "")):
            fw = int(f.get("width") or 0)
            if best is None:
                best = f
            elif fw <= 1920 and fw > int(best.get("width") or 0):
                best = f
    if not best and files:
        best = files[0]
    best = best or {}
    author = ((video.get("user") or {}).get("name") or "").strip()
    w = int(best.get("width") or video.get("width") or 0)
    h = int(best.get("height") or video.get("height") or 0)
    dur = float(video.get("duration") or 0)
    return {
        "source": "pexels",
        "source_id": vid,
        "title": video_title(video, author, vid),
        "page_url": video.get("url") or f"https://www.pexels.com/video/{vid}/",
        "url": best.get("link") or "",
        "thumb_url": video.get("image") or "",
        "width": w,
        "height": h,
        "duration": dur,
        "size": 0,
        "mime": best.get("file_type") or "video/mp4",
        "kind": "video",
        "author": author,
        "artist": author,
        "licence": PEXELS_LICENCE,
        "licence_url": PEXELS_LICENCE_URL,
    }


class PexelsSource:
    name = "pexels"

    def __init__(self, *, key: str | None = None, opener: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep,
                 base_url: str = PEXELS_BASE, video_base_url: str = PEXELS_VIDEO_BASE):
        self._key = key
        self._opener = opener
        self._sleep = sleep
        self.base_url = base_url
        self.video_base_url = video_base_url

    @property
    def key(self) -> str | None:
        if self._key is not None:
            return self._key or None
        return env.get_key("PEXELS_API_KEY")

    def has_key(self) -> bool:
        return bool(self.key)

    def _headers(self) -> dict[str, str]:
        k = self.key
        if not k:
            return {}
        return {"Authorization": k}

    def _get_json(self, url: str, params: dict | None = None) -> dict:
        if params:
            url = f"{url}?{urlencode(params)}"
        hdrs = {"Accept": "application/json", **self._headers()}
        with http.open_url(url, headers=hdrs, opener=self._opener, sleep=self._sleep) as r:
            body = r.read()
        try:
            return json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise http.MediaHTTPError(f"response was not JSON for {http._short(url)}") from exc

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        if not self.has_key():
            return []
        query = (query or "").strip()
        if not query:
            return []
        n = max(1, min(int(limit), 80))
        if kind == "image":
            url = f"{self.base_url}/search"
            data = self._get_json(url, {"query": query, "per_page": n, "page": 1})
            photos = data.get("photos") or []
            return [parse_photo(p) for p in photos if p.get("src")]
        elif kind == "video":
            url = f"{self.video_base_url}/search"
            data = self._get_json(url, {"query": query, "per_page": n, "page": 1})
            videos = data.get("videos") or []
            return [parse_video(v) for v in videos if v.get("video_files")]
        return []

    def fetch_meta(self, source_id: str) -> dict:
        if not self.has_key():
            raise NotFound("Pexels key is not set")
        sid = str(source_id).strip()
        # Try photo first
        try:
            data = self._get_json(f"{self.base_url}/photos/{sid}")
            if data and "src" in data:
                return parse_photo(data)
        except http.MediaHTTPError as exc:
            if exc.status != 404:
                raise
        # Try video next
        try:
            vdata = self._get_json(f"{self.video_base_url}/videos/{sid}")
            if vdata and "video_files" in vdata:
                return parse_video(vdata)
        except http.MediaHTTPError as exc:
            if exc.status == 404:
                raise NotFound(f"Pexels has no item {sid}") from exc
            raise
        raise NotFound(f"Pexels has no item {sid}")

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        author = meta.get("author") or "Pexels contributor"
        return {
            "source": "pexels",
            "source_url": meta.get("page_url", ""),
            "author": author,
            "licence": PEXELS_LICENCE,
            "licence_url": meta.get("licence_url") or PEXELS_LICENCE_URL,
        }

    def download(self, meta: dict, dest: Path, *, min_short_side: int = 0,
                 max_bytes: int = MAX_IMAGE_BYTES) -> Path:
        url = (meta.get("url") or "").strip()
        if not url:
            raise NotFound(f"pexels {meta.get('source_id')}: no download URL")
        is_video = meta.get("kind") == "video"
        mb = MAX_VIDEO_BYTES if is_video else max_bytes
        dest = http.download_file(url, dest, max_bytes=mb, opener=self._opener, sleep=self._sleep)
        if not is_video and min_short_side:
            w, h = image_size(dest)
            if w and h and min(w, h) < min_short_side:
                Path(dest).unlink(missing_ok=True)
                raise ImageTooSmall(f"pexels {meta.get('source_id')}: {w}x{h} px, below {min_short_side}")
        return dest
