"""Frame rendering with an on-disk cache, JPEG encoding, thumbs."""
from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from bti.engine.errors import DataError
from bti.script.store import ProjectGone, make_parent

from bti.engine import limits

from .common import ApiError, finite_number
from bti.fsio import atomic_replace

# The engine's limits file has no time range; this one is the editor's own (a day), named here so it is not a loose number.
T_MAX_SECONDS = 86400
from .engine_adapter import ENGINE_LOCK

JPEG_QUALITY = 85
MAX_CACHED = 1500


def to_jpeg(frame: np.ndarray, quality: int = JPEG_QUALITY) -> bytes:
    arr = np.asarray(frame)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        arr = arr[:, :, :3][:, :, ::-1]  # BGR to RGB
    img = Image.fromarray(np.ascontiguousarray(arr.astype(np.uint8)))
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=quality)
    return b.getvalue()


def clean_t(t, name: str = "t") -> float:
    """A time in seconds: a finite number from 0 to 86400 (a string, a boolean, NaN, infinity or a whole number too large for a
    float is a 422, never a 500)."""
    try:
        return float(finite_number(t, name, 0, T_MAX_SECONDS))
    except ApiError as e:
        if name != "t":
            raise ApiError(422, f"t0 and t1 must be numbers from 0 to {T_MAX_SECONDS}", code="invalid_field", fields=[{"path": "t0", "problem": "must be a number from 0 up"}, {"path": "t1", "problem": "must be a number from 0 up"}])
        raise ApiError(422, "t must be a number" if "number" in e.detail and "between" not in e.detail
                       and "from" not in e.detail and "finite" not in e.detail else "t out of range", code="invalid_field", field="t")


def clean_width(width, default: int = 960) -> int:
    try:
        return int(finite_number(width, "width", limits.FRAME_WIDTH_MIN, limits.FRAME_WIDTH_MAX, integer=True, default=default))
    except ApiError as e:
        raise ApiError(422, "width must be an integer" if "an integer" in e.detail and "from" not in e.detail
                       else f"width must be between {limits.FRAME_WIDTH_MIN} and {limits.FRAME_WIDTH_MAX}", code="invalid_field", field="width")


def render_jpeg(project, t: float, width: int, draft: dict | None = None) -> bytes:
    """Serialised engine call. A draft is swapped in and always reverted."""
    with ENGINE_LOCK:
        try:
            if draft is not None:
                project.use_draft(draft)
            frame = project.frame_at(t, width)
        except ApiError:
            raise
        except Exception as e:  # noqa: BLE001
            if isinstance(e, DataError):
                raise
            logging.getLogger("bti.editor").warning("render failed", exc_info=e)
            raise ApiError(500, f"render failed ({type(e).__name__})", render_failed=True, code="render_failed")
        finally:
            if draft is not None:
                try:
                    project.use_draft(None)
                except Exception:
                    pass
    return to_jpeg(frame)


def cached_jpeg(project, cache_dir: Path, rev: str, t: float, width: int, tag: str = "f") -> bytes:
    """`rev` is the RENDER key (storyboard + timing + style + media), not the storyboard revision alone."""
    try:
        make_parent(cache_dir / "x", 2)       # <project>/cache/frames: never re-creates a deleted project folder
    except ProjectGone:
        raise ApiError(404, "project not found", code="project_not_found")
    p = cache_dir / f"{tag}_{rev[:16]}_{int(round(t * 1000))}_{width}.jpg"
    try:
        return p.read_bytes()
    except OSError:
        pass
    data = render_jpeg(project, t, width)
    tmp = p.with_suffix(f".{id(data)}.tmp")
    try:
        tmp.write_bytes(data)
        atomic_replace(tmp, p)
    except OSError:
        tmp.unlink(missing_ok=True)
    prune(cache_dir)
    return data


def prune(cache_dir: Path, keep: int = MAX_CACHED) -> None:
    try:
        files = [f for f in cache_dir.iterdir() if f.suffix == ".jpg"]
        if len(files) <= keep:
            return
        files.sort(key=lambda f: f.stat().st_mtime)
        for f in files[: len(files) - keep]:
            f.unlink(missing_ok=True)
    except OSError:
        pass
