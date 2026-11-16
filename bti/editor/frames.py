"""Frame rendering with an on-disk cache, JPEG encoding, thumbs."""
from __future__ import annotations

import io
import math
from pathlib import Path

import numpy as np
from PIL import Image

from bti.engine.errors import DataError

from .common import ApiError
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


def clean_t(t, duration: float | None = None) -> float:
    try:
        t = float(t)
    except (TypeError, ValueError):
        raise ApiError(422, "t must be a number")
    if not math.isfinite(t) or t < 0 or t > 86400:
        raise ApiError(422, "t out of range")
    return t


def clean_width(width, default: int = 960) -> int:
    try:
        w = int(width if width is not None else default)
    except (TypeError, ValueError):
        raise ApiError(422, "width must be an integer")
    if not 64 <= w <= 1920:
        raise ApiError(422, "width must be between 64 and 1920")
    return w


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
            raise ApiError(500, f"render failed: {type(e).__name__}: {e}"[:300], render_failed=True)
        finally:
            if draft is not None:
                try:
                    project.use_draft(None)
                except Exception:
                    pass
    return to_jpeg(frame)


def cached_jpeg(project, cache_dir: Path, rev: str, t: float, width: int, tag: str = "f") -> bytes:
    """`rev` is the RENDER key (storyboard + timing + style + media), not the storyboard revision alone."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = cache_dir / f"{tag}_{rev[:16]}_{int(round(t * 1000))}_{width}.jpg"
    try:
        return p.read_bytes()
    except OSError:
        pass
    data = render_jpeg(project, t, width)
    tmp = p.with_suffix(f".{id(data)}.tmp")
    try:
        tmp.write_bytes(data)
        tmp.replace(p)
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
