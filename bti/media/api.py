"""Media facade (design section 8.2). The editor backend calls only this module.

It never edits storyboard.json: `import_candidate` and `add_upload` return the assets
entry and the backend merges it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import assets as _assets
from .errors import ImageTooSmall, LicenceRejected, MediaError, NotFound  # noqa: F401
from .imageinfo import image_size, readable_problem
from .licence import check_licence as _check_licence, check_text
from .sources.commons import CommonsSource, ext_for
from .sources.met import MetSource

__all__ = ["search", "import_candidate", "add_upload", "check_licence", "LicenceRejected",
           "MIN_SHORT_SIDE"]

MIN_SHORT_SIDE = 1200
_SOURCES: dict = {}          # name -> source instance; tests may replace entries
_FACTORIES = {"commons": CommonsSource, "met": MetSource}
_VIDEO_EXT = {".mp4", ".webm", ".ogv", ".mov", ".mkv", ".m4v"}


def get_source(name: str):
    if name not in _SOURCES:
        if name not in _FACTORIES:
            raise ValueError(f"unknown source {name!r}; use one of {sorted(_FACTORIES)}")
        _SOURCES[name] = _FACTORIES[name]()
    return _SOURCES[name]


def check_licence(meta: dict) -> tuple[bool, str, str]:
    return _check_licence(meta)


def _candidate(meta: dict) -> dict:
    ok, name, reason = _check_licence(meta)
    return {
        "source": meta.get("source", ""), "source_id": meta.get("source_id", ""),
        "title": meta.get("title", ""), "thumb_url": meta.get("thumb_url", ""),
        "page_url": meta.get("page_url", ""), "width": meta.get("width", 0),
        "height": meta.get("height", 0), "mime": meta.get("mime", ""),
        "author": meta.get("author", ""), "licence": name or meta.get("licence", ""),
        "licence_ok": ok, "licence_reason": reason,
    }


def search(query: str, source: str = "commons", kind: str = "image", limit: int = 24) -> list[dict]:
    if kind not in ("image", "video"):
        raise ValueError("kind must be 'image' or 'video'")
    return [_candidate(m) for m in get_source(source).search(query, kind, limit)]


def import_candidate(project_dir: Path, source: str, source_id: str, *,
                     min_short_side: int | None = None) -> dict:
    """Download one item into `<project>/media/` and return `{"asset_key", "asset"}`.

    Raises LicenceRejected (before downloading) and ImageTooSmall. Importing the same
    item again returns the same key without downloading."""
    project_dir = Path(project_dir)
    src = get_source(source)
    ident = f"{source}:{source_id}"
    idx = _assets.load_index(project_dir)
    hit = idx["items"].get(ident)
    if hit and (project_dir / hit["asset"]["file"]).is_file():
        return {"asset_key": hit["key"], "asset": hit["asset"]}

    meta = src.fetch_meta(source_id)
    ok, name, reason = src.licence(meta)
    if not ok:
        raise LicenceRejected(reason, name)
    kind = meta.get("kind", "image")
    key = _assets.make_key(meta.get("title") or source_id, ident, _assets.taken_keys(project_dir, idx))
    media = _assets.media_dir(project_dir)
    dest = media / f"{key}{ext_for(meta)}"
    floor = MIN_SHORT_SIDE if min_short_side is None else min_short_side
    src.download(meta, dest, min_short_side=floor)
    w, h = (meta.get("width") or 0, meta.get("height") or 0)
    if kind == "image" and not (w and h):
        w, h = image_size(dest)
    asset = _assets.build_asset(
        f"media/{dest.name}", kind, meta.get("title", ""), meta.get("author", ""),
        _assets.year_of(meta.get("year") or meta.get("date") or ""), w, h, src.credit(meta))
    _assets.register(project_dir, ident, key, asset)
    return {"asset_key": key, "asset": asset}


def add_upload(project_dir: Path, file_path: Path, meta: dict) -> dict:
    """Add a human-supplied file. `meta` needs licence, source_url, author (or
    "unknown, PD"); optional title, artist, year. The licence gate applies."""
    project_dir, file_path = Path(project_dir), Path(file_path)
    missing = [k for k in ("licence", "source_url", "author") if not str(meta.get(k, "")).strip()]
    if missing:
        raise ValueError(f"upload metadata is missing: {', '.join(missing)}")
    ok, name, reason = check_text(meta["licence"])
    if not ok:
        raise LicenceRejected(reason, name)
    if not file_path.is_file():
        raise NotFound(f"no such file: {file_path}")
    if file_path.suffix.lower() not in _VIDEO_EXT:
        problem = readable_problem(file_path)
        if problem:
            raise ValueError(problem)
    title = (meta.get("title") or file_path.stem).strip()
    ident = f"upload:{file_path.name}:{file_path.stat().st_size}"
    idx = _assets.load_index(project_dir)
    key = _assets.make_key(title, ident, _assets.taken_keys(project_dir, idx))
    ext = file_path.suffix.lower() or ".bin"
    dest = _assets.media_dir(project_dir) / f"{key}{ext}"
    shutil.copyfile(file_path, dest)
    kind = "video" if ext in _VIDEO_EXT else "image"
    w, h = image_size(dest) if kind == "image" else (int(meta.get("width") or 0), int(meta.get("height") or 0))
    credit = {"source": "upload", "source_url": meta["source_url"], "author": meta["author"],
              "licence": name, "licence_url": meta.get("licence_url", "")}
    asset = _assets.build_asset(f"media/{dest.name}", kind, title, meta.get("artist", ""),
                                str(meta.get("year", "")), w, h, credit)
    _assets.register(project_dir, ident, key, asset)
    return {"asset_key": key, "asset": asset}
