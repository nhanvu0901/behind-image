"""Shared helpers: asset keys, the per-project source index, asset entries.

The media folder keeps `media/sources.json` (our own index, atomic writes) so that
importing the same source item twice returns the same key and file. Nothing here edits
storyboard.json; it is read (if present) only to avoid key clashes.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from pathlib import Path

from ._io import read_json, write_json_atomic
from .imageinfo import drawn_size
from .. import textfold
from bti.fsio import atomic_replace

INDEX_NAME = "sources.json"
_STOP = {"with", "from", "by", "for", "the", "of", "a", "an", "and", "de", "la", "le", "in", "on", "at", "file"}
MAX_KEY = 24


def slugify(title: str, fallback: str = "img") -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", textfold.fold(title)) if w not in _STOP]
    slug = "_".join(words[:3])[:MAX_KEY].strip("_")
    return slug or fallback


def media_dir(project_dir: Path, require_root: bool = False) -> Path:
    """`<project>/media`. `require_root`: the project folder must already exist (FileNotFoundError otherwise) and is never
    created here; the default (stand-alone use) makes the whole path."""
    d = Path(project_dir) / "media"
    if require_root and not Path(project_dir).is_dir():
        raise FileNotFoundError(f"project folder {Path(project_dir).name!r} does not exist")
    d.mkdir(parents=not require_root, exist_ok=True)
    return d


def load_index(project_dir: Path) -> dict:
    doc = read_json(Path(project_dir) / "media" / INDEX_NAME, {}) or {}
    if not isinstance(doc, dict):            # valid JSON of the wrong shape: set aside like a corrupt file, start a new index
        try:
            p = Path(project_dir) / "media" / INDEX_NAME
            atomic_replace(p, p.with_name(p.name + ".corrupt"))
        except OSError:
            pass
        doc = {}
    if not isinstance(doc.get("items"), dict):
        doc["items"] = {}
    doc["items"] = {k: v for k, v in doc["items"].items() if isinstance(v, dict)}
    return doc


def save_index(project_dir: Path, doc: dict, require_root: bool = False) -> None:
    write_json_atomic(media_dir(project_dir, require_root) / INDEX_NAME, doc, parents=not require_root)


def taken_keys(project_dir: Path, index: dict) -> set[str]:
    keys = {v.get("key") for v in index["items"].values()}
    for name in ("storyboard.json", "picks.json"):          # an asset key is shared by the picks and the storyboard
        doc = _peek(Path(project_dir) / name)
        if isinstance(doc.get("assets"), dict):
            keys |= set(doc["assets"])
    return {k for k in keys if k}


def _peek(path: Path) -> dict:
    """The JSON object of a project document, or {} when it is missing or unreadable. Read only: a damaged file is left
    where it is (it belongs to another stage, which reports it)."""
    import json
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def make_key(title: str, ident: str, taken: set[str]) -> str:
    """Short, unique, stable: the slug of the title, plus 4 hex of the id hash on a clash."""
    base = slugify(title)
    if base not in taken:
        return base
    suffix = hashlib.sha1(ident.encode()).hexdigest()[:4]
    key = f"{base[:MAX_KEY - 5]}_{suffix}"
    n = 2
    while key in taken:
        key = f"{base[:MAX_KEY - 7]}_{suffix}{n}"
        n += 1
    return key


def year_of(text: str) -> str:
    m = re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text or "")
    return m.group(1) if m else ""


def build_asset(file_rel: str, kind: str, title: str, artist: str, year: str,
                width: int, height: int, credit: dict, *, duration: float | None = None,
                original_size: tuple | None = None) -> dict:
    """One asset record. `width` and `height` MUST be the pixels of the stored file (measure it: `api.stored_image_size`);
    `original_size` is what the source says its original is (kept as `original_width` / `original_height`, only when
    positive), which can be larger than the stored file when a scaled rendition was downloaded."""
    out = {"file": file_rel, "kind": kind, "title": title, "artist": artist, "year": year,
           "width": int(width), "height": int(height), "credit": credit}
    if original_size and all(_pos(v) for v in original_size[:2]):
        out["original_width"], out["original_height"] = int(original_size[0]), int(original_size[1])
    if kind == "video" and duration is not None and duration > 0:
        out["duration"] = round(float(duration), 2)
    return out


# ---------------------------------------------------------------- the size of a stored picture
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _pos(v) -> bool:
    return _num(v) and v > 0


_SIZE_CACHE: dict = {}          # (path, mtime_ns, bytes) -> (w, h); a project page asks for every asset on every load
_SIZE_CACHE_MAX = 4096


def stored_size(path: Path) -> tuple[int, int]:
    """The pixels of the image file at `path` as the engine draws it and the page shows it (EXIF turn included), or (0, 0)
    when the file is missing or unreadable. Reads only the header; remembered per (path, mtime, size)."""
    try:
        st = Path(path).stat()
    except OSError:
        return 0, 0
    key = (str(path), st.st_mtime_ns, st.st_size)
    hit = _SIZE_CACHE.get(key)
    if hit is None:
        hit = drawn_size(Path(path))
        if len(_SIZE_CACHE) >= _SIZE_CACHE_MAX:
            _SIZE_CACHE.clear()
        _SIZE_CACHE[key] = hit
    return hit


def _inside(project_dir: Path, rel) -> Path | None:
    """`project_dir / rel` when `rel` is a plain relative path that stays inside the project, else None."""
    if not isinstance(rel, str) or not rel or Path(rel).anchor or ".." in Path(rel).parts:      # anchor: absolute, drive or rooted
        return None
    return Path(project_dir) / rel


def _scaled(v, k: float):
    out = v * k
    return int(round(out)) if isinstance(v, int) else round(out, 2)


def scale_regions(regions: dict | None, kx: float, ky: float) -> None:
    """Scale the regions of a picture IN PLACE when its size changes: x and rx by `kx` (new width / old width), y and ry by `ky`
    (new height / old height). The one rule shared by `reconcile_sizes` and by the draft compiler (`bti.draft.compile`)."""
    for r in (regions or {}).values():
        if not isinstance(r, dict):
            continue
        for name, k in (("x", kx), ("y", ky), ("rx", kx), ("ry", ky)):
            if _num(r.get(name)):
                r[name] = _scaled(r[name], k)


def reconcile_sizes(assets: dict, project_dir: Path) -> list[str]:
    """Make the declared `width` / `height` of every image asset in `assets` (a `picks.json` or `storyboard.json` `assets`
    object) equal the pixels of its stored file, IN PLACE, and return the keys that changed. No network, only file headers.

    The regions of a corrected asset were drawn in the declared space, so each is scaled by the same factors (x and rx by
    stored width / declared width, y and ry by stored height / declared height). The old declared size is kept as
    `original_width` / `original_height` when the record has none yet (it is what the source claimed). An asset whose file is
    missing or unreadable, a video, or one that already agrees is left alone, so the call is idempotent. When the declared
    size is missing (0) it is filled in and the regions are not touched (their space is unknown)."""
    changed: list[str] = []
    for key, a in (assets or {}).items():
        if not isinstance(a, dict) or a.get("kind") not in ("image", "mask"):
            continue
        f = _inside(project_dir, a.get("file"))
        if f is None:
            continue
        sw, sh = stored_size(f)
        if not (sw and sh):
            continue
        dw, dh = a.get("width"), a.get("height")
        if _pos(dw) and _pos(dh) and dw == sw and dh == sh:
            continue
        if _pos(dw) and _pos(dh):
            scale_regions(a.get("regions"), sw / dw, sh / dh)
            if "original_width" not in a and "original_height" not in a:
                a["original_width"], a["original_height"] = int(round(dw)), int(round(dh))
        a["width"], a["height"] = sw, sh
        changed.append(key)
    return changed


def register(project_dir: Path, ident: str, key: str, asset: dict, require_root: bool = False) -> None:
    idx = load_index(project_dir)
    idx["items"][ident] = {"key": key, "asset": asset}
    save_index(project_dir, idx, require_root)
