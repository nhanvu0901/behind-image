"""Wikimedia Commons through the MediaWiki API (stdlib only)."""
from __future__ import annotations

import html
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote, urlparse

from .. import http
from ..errors import ImageTooSmall, NotFound
from ..imageinfo import image_size
from ..licence import check_licence

API_URL = "https://commons.wikimedia.org/w/api.php"
IIPROP = "url|size|mime|extmetadata"
MIN_SHORT_SIDE = 1200
MAX_IMAGE_BYTES = 60 * 1024 * 1024
MAX_VIDEO_BYTES = 400 * 1024 * 1024
MAX_ORIGINAL_PIXELS = 25_000_000
MAX_ORIGINAL_BYTES = 40 * 1024 * 1024
SCALED_LONGEST_SIDE = 6000
# The only widths Wikimedia serves for a scaled rendition ("thumbnail steps"). Read from MediaWiki's own documentation,
# "Common thumbnail sizes" (https://www.mediawiki.org/wiki/Common_thumbnail_sizes) and `$wgThumbnailSteps`
# (https://www.mediawiki.org/wiki/Manual:$wgThumbnailSteps): 20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840 px.
# Any other width is rounded up to a step by the API, and a request for a rendition of a non-standard width is throttled
# by Wikimedia (HTTP 429, "Use thumbnail steps"). So this app never asks for a width that is not in this list.
THUMB_STEPS = (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)
CARD_THUMB_WIDTH = 330          # the small picture of a search card (a step: it used to be 320, which is not)
_TAG = re.compile(r"<[^>]+>")
_VIDEO_MIMES = ("video/", "application/ogg")


def standard_width(limit: int) -> int | None:
    """The largest width of `THUMB_STEPS` that is at most `limit`, or None when `limit` is under the smallest step."""
    fit = [s for s in THUMB_STEPS if s <= limit]
    return max(fit) if fit else None


def rendition_width(w: int, h: int, longest: int = SCALED_LONGEST_SIDE, max_pixels: int = MAX_ORIGINAL_PIXELS) -> int | None:
    """The width to ask Commons for when a scaled rendition of a `w` x `h` original is wanted: the largest standard width that
    is smaller than the original and gives a rendition that is no longer "too big" by the app's own rule (a longest side of at
    most `longest` px, or at most `max_pixels` pixels: the same two limits that decide when a scaled rendition is wanted at
    all). None when no standard width fits (the caller then downloads the original). Without a known size: the largest
    standard width that is at most `longest`."""
    if not (w and h):
        return standard_width(longest)
    for step in sorted(THUMB_STEPS, reverse=True):
        if step >= w:
            continue
        rh = h * step / w
        if max(step, rh) <= longest or step * rh <= max_pixels:
            return step
    return None


def _text(v: Any) -> str:
    if isinstance(v, dict):
        v = v.get("value")
    return " ".join(html.unescape(_TAG.sub(" ", str(v or ""))).split())


def kind_of(mime: str) -> str:
    mime = (mime or "").lower()
    if mime.startswith(_VIDEO_MIMES):
        return "video"
    if mime.startswith("image/"):
        return "image"
    return "other"


def parse_page(page: dict) -> dict | None:
    """One MediaWiki `pages[]` entry (formatversion=2) to our normalised meta, or None."""
    infos = page.get("imageinfo") or []
    if page.get("missing") or not infos:
        return None
    ii = infos[0]
    ext = ii.get("extmetadata") or {}
    title = page.get("title", "")
    fname = title.split(":", 1)[-1]
    nice = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", fname).replace("_", " ")
    name = _text(ext.get("ObjectName")) or nice
    if len(name) > 140:
        name = nice
    mime = ii.get("mime", "")
    return {
        "source": "commons",
        "source_id": title,
        "title": name,
        "page_url": ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'))}",
        "url": ii.get("url", ""),
        "thumb_url": ii.get("thumburl") or ii.get("url", ""),
        "width": int(ii.get("width") or 0),
        "height": int(ii.get("height") or 0),
        "size": int(ii.get("size") or 0),
        "mime": mime,
        "kind": kind_of(mime),
        "author": _text(ext.get("Artist")) or _text(ext.get("Credit")),
        "date": _text(ext.get("DateTimeOriginal")) or _text(ext.get("DateTime")),
        "description": _text(ext.get("ImageDescription")),
        "licence": _text(ext.get("LicenseShortName")) or _text(ext.get("License")) or _text(ext.get("UsageTerms")),
        "licence_url": _text(ext.get("LicenseUrl")),
        "extmetadata": {k: _text(ext.get(k)) for k in ("LicenseShortName", "License", "UsageTerms")
                        if ext.get(k)},
        "_index": page.get("index", 0),
    }


def ext_for(meta: dict) -> str:
    suffix = Path(urlparse(meta.get("url", "")).path).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{2,5}", suffix):
        return suffix
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/tiff": ".tif", "video/webm": ".webm",
            "application/ogg": ".ogv", "video/ogg": ".ogv", "video/mp4": ".mp4"}.get(
                (meta.get("mime") or "").lower(), ".bin")


class CommonsSource:
    name = "commons"

    def __init__(self, *, opener: Callable | None = None, sleep: Callable[[float], None] = time.sleep,
                 api_url: str = API_URL, min_short_side: int = MIN_SHORT_SIDE):
        self._opener, self._sleep, self.api_url = opener, sleep, api_url
        self.min_short_side = min_short_side

    def _api(self, params: dict) -> dict:
        p = {"action": "query", "format": "json", "formatversion": "2", **params}
        return http.get_json(self.api_url, p, opener=self._opener, sleep=self._sleep)

    def search(self, query: str, kind: str = "image", limit: int = 24) -> list[dict]:
        ftype = "video" if kind == "video" else "bitmap"
        data = self._api({
            "generator": "search", "gsrsearch": f"{query} filetype:{ftype}", "gsrnamespace": "6",
            "gsrlimit": str(max(1, min(int(limit), 50))), "prop": "imageinfo", "iiprop": IIPROP,
            "iiurlwidth": str(CARD_THUMB_WIDTH),
        })
        out = []
        for page in sorted((data.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0)):
            meta = parse_page(page)
            if meta and meta["kind"] == ("video" if kind == "video" else "image"):
                out.append(meta)
        return out[:limit]

    def fetch_meta(self, source_id: str) -> dict:
        title = unquote(source_id.strip())
        if not title.lower().startswith("file:"):
            title = "File:" + title
        data = self._api({"titles": title.replace("_", " "), "prop": "imageinfo",
                          "iiprop": IIPROP, "iiurlwidth": str(CARD_THUMB_WIDTH)})
        for page in (data.get("query") or {}).get("pages") or []:
            meta = parse_page(page)
            if meta:
                return meta
        raise NotFound(f"Commons has no file {title!r}")

    def licence(self, meta: dict) -> tuple[bool, str, str]:
        return check_licence(meta)

    def credit(self, meta: dict) -> dict:
        return credit(meta)

    def download(self, meta: dict, dest: Path, *, min_short_side: int | None = None,
                 max_bytes: int | None = None) -> Path:
        """Download the file. Images shorter than `min_short_side` (default 1200 px)
        are refused with ImageTooSmall before any bytes are fetched.
        Large images (> 25 megapixels with a side over 6000 px, or > 40 MB) request a scaled rendition: the largest of
        Wikimedia's standard widths (`THUMB_STEPS`) that is smaller than the original and keeps the longest side within 6000 px.
        The size of the stored file can therefore differ from `meta["width"]` x `meta["height"]` (the original's): whoever
        records the asset measures the file (`api.stored_image_size`).
        Files over 60 MB (or max_bytes) after all that are refused with FileTooLarge."""
        dest = Path(dest)
        kind = meta.get("kind") or kind_of(meta.get("mime", ""))
        floor = self.min_short_side if min_short_side is None else min_short_side
        w, h = int(meta.get("width") or 0), int(meta.get("height") or 0)
        size = int(meta.get("size") or 0)
        if kind == "image" and w and h and min(w, h) < floor:
            raise ImageTooSmall(f"{meta.get('source_id')}: {w}x{h} px, short side below {floor}")
        if not meta.get("url"):
            raise NotFound(f"{meta.get('source_id')}: no download url")
        cap = max_bytes or (MAX_VIDEO_BYTES if kind == "video" else MAX_IMAGE_BYTES)
        download_url = meta["url"]
        scaled = False

        if kind == "image" and ((max(w, h) > SCALED_LONGEST_SIDE and w * h > MAX_ORIGINAL_PIXELS) or (size > MAX_ORIGINAL_BYTES)):
            target_w = rendition_width(w, h, SCALED_LONGEST_SIDE)
            if target_w:
                title = unquote(str(meta.get("source_id") or "").strip())
                if not title.lower().startswith("file:"):
                    title = "File:" + title
                data = self._api({
                    "titles": title.replace("_", " "),
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime",
                    "iiurlwidth": str(target_w),
                })
                for page in (data.get("query") or {}).get("pages") or []:
                    infos = page.get("imageinfo") or []
                    thumb = infos[0].get("thumburl") if infos else None
                    if thumb and thumb != meta["url"]:          # the same address as the original is no rendition
                        download_url = thumb
                        scaled = True
                        break

        if not scaled and meta.get("size") and int(meta["size"]) > cap:
            raise http.FileTooLarge(f"{meta.get('source_id')}: {meta['size']} bytes exceeds cap {cap}")
        http.download_file(download_url, dest, max_bytes=cap, opener=self._opener, sleep=self._sleep)
        if kind == "image" and not (w and h):
            aw, ah = image_size(dest)
            if aw and ah and min(aw, ah) < floor:
                dest.unlink(missing_ok=True)
                raise ImageTooSmall(f"{meta.get('source_id')}: {aw}x{ah} px, short side below {floor}")
        return dest


def credit(meta: dict) -> dict:
    """The `credit` object of a storyboard asset."""
    _, name, _ = check_licence(meta)
    return {"source": "commons", "source_url": meta.get("page_url", ""),
            "author": meta.get("author") or "unknown",
            "licence": name or meta.get("licence", ""), "licence_url": meta.get("licence_url", "")}
