"""Media facade (design section 8.2). The editor backend calls only this module.

It never edits storyboard.json: `import_candidate` and `add_upload` return the assets
entry and the backend merges it.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import assets as _assets
from . import clips as _clips
from . import http as _http
from .errors import ImageTooSmall, LicenceRejected, MediaError, NotFound  # noqa: F401
from .imageinfo import ImageDamaged, drawn_size, image_problem, image_size, readable_problem  # noqa: F401
from .licence import check_licence as _check_licence, check_text, flag_for_meta, flag_for_text, with_size_flag
from .sources.commons import CommonsSource, ext_for
from .sources.bookpage import BookPageSource
from .sources.met import MetSource
from .sources.pexels import PexelsSource
from .sources.pixabay import PixabaySource
from .sources.osm import OsmSource

__all__ = ["search", "import_candidate", "add_upload", "moment_search", "inspect_video_url",
           "import_clip", "check_licence", "LicenceRejected", "VideoDamaged", "MIN_SHORT_SIDE"]
# The licence gate and the size floor are ADVISORY: nothing is refused for them. `LicenceRejected` and `ImageTooSmall`
# stay importable (the sources and the clip module still use them), but this facade never raises them.


class VideoDamaged(ValueError):
    def __init__(self, msg: str, code: str = "video_unreadable"):
        super().__init__(msg)
        self.code = code

MIN_SHORT_SIDE = 1200
_SOURCES: dict = {}          # name -> source instance; tests may replace entries
_FACTORIES = {
    "commons": CommonsSource,
    "met": MetSource,
    "book": BookPageSource,
    "pexels": PexelsSource,
    "pixabay": PixabaySource,
    "osm": OsmSource,
}
_VIDEO_EXT = {".mp4", ".webm", ".ogv", ".mov", ".mkv", ".m4v"}


def stored_image_size(path: Path) -> tuple[int, int]:
    """THE rule of this module: an asset's `width` and `height` are the pixels of the file that was STORED (as the engine
    draws it and the page shows it), never what a source's metadata says about its original. Every place that writes an
    asset record (import of any source, upload, book image) calls this on the stored file. The source's own claim is kept
    apart as `original_width` / `original_height`."""
    w, h = drawn_size(Path(path))
    if not (w and h):
        raise ImageDamaged("the stored image has no readable size", "image_unreadable")
    return w, h


def get_source(name: str):
    if name not in _SOURCES:
        if name not in _FACTORIES:
            raise ValueError(f"unknown source {name!r}; use one of {sorted(_FACTORIES)}")
        _SOURCES[name] = _FACTORIES[name]()
    return _SOURCES[name]


def check_licence(meta: dict) -> tuple[bool, str, str]:
    return _check_licence(meta)


def _candidate(meta: dict, stored: tuple[int, int] | None = None) -> dict:
    """One search card. `stored`: the pixel size of the file an import would store, when that is not what the source says about
    its original (a Commons image of 3048 x 4000 is stored as a 1920 x 2520 rendition): the card and the "small" flag then
    say what the owner will get, and what the page shows after the import is the same."""
    ok, name, reason = _check_licence(meta)
    w, h = int(meta.get("width") or 0), int(meta.get("height") or 0)
    use_stored = bool(stored and stored[0] > 0 and stored[1] > 0)
    if use_stored:
        w, h = int(stored[0]), int(stored[1])
    is_vid = meta.get("kind") == "video" or str(meta.get("mime") or "").startswith("video/")
    return {
        "source": meta.get("source", ""), "source_id": meta.get("source_id", ""),
        "title": meta.get("title", ""), "thumb_url": meta.get("thumb_url", ""),
        "page_url": meta.get("page_url", ""), "width": w if use_stored else meta.get("width", 0),
        "height": h if use_stored else meta.get("height", 0), "mime": meta.get("mime", ""),
        "author": meta.get("author", ""), "licence": name or meta.get("licence", ""),
        "licence_ok": ok, "licence_reason": reason,
        "flag": flag_for_meta(meta) if is_vid else with_size_flag(flag_for_meta(meta), w, h, MIN_SHORT_SIDE),
    }


def search(query: str, source: str = "commons", kind: str = "image", limit: int = 24) -> list[dict]:
    if kind not in ("image", "video"):
        raise ValueError("kind must be 'image' or 'video'")
    src = get_source(source)
    sized = getattr(src, "stored_size", None)          # a source that stores a scaled rendition says what size that is
    return [_candidate(m, sized(m) if callable(sized) else None) for m in src.search(query, kind, limit)]


def import_candidate(project_dir: Path, source: str, source_id: str, *,
                     min_short_side: int | None = None, require_root: bool = False) -> dict:
    """Download one item into `<project>/media/` and return `{"asset_key", "asset"}`.

    Never refused for its licence or its size: `asset["credit"]["flag"]` is `rejected`, `unknown`, `small` or None
    (`min_short_side`, default 1200, is the limit for "small"). Importing the same item again returns the same
    key without downloading. `require_root`: the project folder must already exist
    and no folder above `media/` is ever created (FileNotFoundError when the project was deleted meanwhile)."""
    project_dir = Path(project_dir)
    if require_root:
        token = _http.NO_NEW_PARENTS.set(True)
        try:
            return _import(project_dir, source, source_id, min_short_side, True)
        finally:
            _http.NO_NEW_PARENTS.reset(token)
    return _import(project_dir, source, source_id, min_short_side, False)


def _import(project_dir: Path, source: str, source_id: str, min_short_side: int | None, require_root: bool) -> dict:
    src = get_source(source)
    check = getattr(src, "check_id", None)           # a source may refuse an id it can no longer serve, before the index answers for it
    if callable(check):
        check(source_id)
    ident = f"{source}:{source_id}"
    idx = _assets.load_index(project_dir)
    hit = idx["items"].get(ident)
    if hit and (project_dir / hit["asset"]["file"]).is_file():
        # a record written before the size rule (it carried the source's size): measure the stored file and keep the index right
        if _assets.reconcile_sizes({hit["key"]: hit["asset"]}, project_dir):
            _assets.register(project_dir, ident, hit["key"], hit["asset"], require_root)
        return {"asset_key": hit["key"], "asset": hit["asset"]}

    meta = src.fetch_meta(source_id)
    lic_flag = flag_for_meta(meta)
    kind = meta.get("kind", "image")
    key = _assets.make_key(meta.get("title") or source_id, ident, _assets.taken_keys(project_dir, idx))
    media = _assets.media_dir(project_dir, require_root)
    dest_ext = ".mp4" if kind == "video" else ext_for(meta)
    dest = media / f"{key}{dest_ext}"
    floor = MIN_SHORT_SIDE if min_short_side is None else min_short_side
    duration: float | None = None
    try:
        if kind == "video":
            raw_tmp = dest.with_name(f"{key}_raw{ext_for(meta)}")
            try:
                src.download(meta, raw_tmp, min_short_side=0)
                try:
                    _clips.normalize(raw_tmp, dest, strip_audio=True)
                except MediaError as exc:
                    if isinstance(exc, _clips.ToolMissing):
                        shutil.copyfile(raw_tmp, dest)
                    else:
                        raise VideoDamaged(f"video cannot be processed: {exc}", "video_unreadable") from None
                p2 = _probe_upload_video(dest)
                w, h, duration = p2["width"], p2["height"], p2["duration"]
            finally:
                raw_tmp.unlink(missing_ok=True)
        else:
            got = src.download(meta, dest, min_short_side=0)    # the size floor only sets a flag, it never refuses
            if isinstance(got, Path) and got != dest and got.is_file():
                dest = got                                       # a rendition in another format than its original has its own extension
            bad = image_problem(dest)
            if bad:
                raise ImageDamaged(bad[1], bad[0])
            w, h = stored_image_size(dest)          # the pixels of what was stored, not the source's claim about its original
    except BaseException:
        dest.unlink(missing_ok=True)            # nothing of a refused download stays in media/
        raise
    credit = dict(src.credit(meta))
    credit["flag"] = with_size_flag(lic_flag, w, h, floor) if kind == "image" else lic_flag
    asset = _assets.build_asset(
        f"media/{dest.name}", kind, meta.get("title", ""), meta.get("author", ""),
        _assets.year_of(meta.get("year") or meta.get("date") or ""), w, h, credit,
        duration=duration, original_size=(meta.get("width"), meta.get("height")))
    _assets.register(project_dir, ident, key, asset, require_root)
    return {"asset_key": key, "asset": asset}


def _probe_upload_video(path: Path) -> dict:
    try:
        info = _clips.probe_video(path)
    except MediaError as exc:
        if isinstance(exc, _clips.ToolMissing):
            raise
        raise VideoDamaged(f"video cannot be read: {exc}", "video_unreadable") from None
    if info["width"] <= 0 or info["height"] <= 0 or info["duration"] <= 0:
        raise VideoDamaged("video has no readable frames or zero duration", "video_unreadable")
    return info


def add_upload(project_dir: Path, file_path: Path, meta: dict, *, require_root: bool = False) -> dict:
    """Add a human-supplied file. `meta` may carry licence, source_url, author, title, artist, year, all optional: a
    missing licence is recorded as such (`credit.flag` "unknown"), never refused. The file itself must be a complete,
    readable image or video file."""
    project_dir, file_path = Path(project_dir), Path(file_path)
    if require_root and not project_dir.is_dir():
        raise FileNotFoundError(f"project folder {project_dir.name!r} does not exist")
    if not file_path.is_file():
        raise NotFound(f"no such file: {file_path}")
    ext = file_path.suffix.lower() or ".bin"
    kind = "video" if ext in _VIDEO_EXT else "image"
    duration: float | None = None
    if kind == "video":
        vinfo = _probe_upload_video(file_path)
        w, h, duration = vinfo["width"], vinfo["height"], vinfo["duration"]
    else:
        bad = image_problem(file_path)
        if bad:
            raise ImageDamaged(bad[1], bad[0])
    licence_text = str(meta.get("licence") or "").strip()
    ok, name, _reason = check_text(licence_text)
    lic_flag = flag_for_text(licence_text)
    # no title: the stem of the file's own name (`original_name`, when the caller has it), never a temp file's name
    original = Path(str(meta.get("original_name") or "")).stem
    title = (str(meta.get("title") or "").strip() or original or file_path.stem).strip()
    ident = f"upload:{file_path.name}:{file_path.stat().st_size}"
    idx = _assets.load_index(project_dir)
    key = _assets.make_key(title, ident, _assets.taken_keys(project_dir, idx))
    dest_ext = ".mp4" if kind == "video" else ext
    dest = _assets.media_dir(project_dir, require_root) / f"{key}{dest_ext}"
    try:
        if kind == "video":
            try:
                _clips.normalize(file_path, dest, strip_audio=True)
            except MediaError as exc:
                if isinstance(exc, _clips.ToolMissing):
                    shutil.copyfile(file_path, dest)
                else:
                    raise VideoDamaged(f"video cannot be processed: {exc}", "video_unreadable") from None
            p2 = _probe_upload_video(dest)
            w, h, duration = p2["width"], p2["height"], p2["duration"]
        else:
            shutil.copyfile(file_path, dest)
            w, h = stored_image_size(dest)
        credit = {"source": "upload", "source_url": str(meta.get("source_url") or "").strip(),
                  "author": str(meta.get("author") or "").strip() or "unknown",
                  "licence": name if ok else licence_text, "licence_url": meta.get("licence_url", ""),
                  "flag": with_size_flag(lic_flag, w, h, MIN_SHORT_SIDE) if kind == "image" else lic_flag}
        asset = _assets.build_asset(f"media/{dest.name}", kind, title, meta.get("artist", ""),
                                    str(meta.get("year", "")), w, h, credit, duration=duration)
        _assets.register(project_dir, ident, key, asset, require_root)
    except BaseException:
        dest.unlink(missing_ok=True)          # what this call wrote is removed when it fails
        raise
    return {"asset_key": key, "asset": asset}


def moment_search(desc: str, *, limit: int = 6, extra_queries: list[str] | tuple = (),
                  search=None, metadata=None) -> list[dict]:
    """Search YouTube via You.com + read yt-dlp metadata/moment signals without downloading video."""
    return _clips.moment_search(desc, limit=limit, extra_queries=extra_queries,
                                search=search, metadata=metadata)


def inspect_video_url(url: str, desc: str = "", *, metadata=None) -> dict:
    """Inspect a pasted YouTube URL via yt-dlp metadata/moments (free, no You.com search)."""
    return _clips.inspect_video_url(url, desc=desc, metadata=metadata)


def import_clip(project_dir: Path, url: str, start: float, end: float, *, info: dict | None = None,
                strict_licence: bool = False, require_root: bool = False, runner=None) -> dict:
    """Download [start, end] of a video into `<project>/media/` and return `{"asset_key", "asset"}`."""
    project_dir = Path(project_dir)
    if require_root:
        token = _http.NO_NEW_PARENTS.set(True)
        try:
            return _clips.import_clip(project_dir, url, start, end, info=info,
                                      strict_licence=strict_licence, require_root=True, runner=runner)
        finally:
            _http.NO_NEW_PARENTS.reset(token)
    return _clips.import_clip(project_dir, url, start, end, info=info,
                              strict_licence=strict_licence, require_root=False, runner=runner)
