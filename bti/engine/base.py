"""Interfaces and shared services for technique renderers (see bti/engine/README.md).

Four kinds of renderer, all constructed once per compiled Scene and called once per frame:

    BaseRenderer        (kind base / card)   render(t) -> float32 BGR frame (H x W x 3, 0..255)
    OverlayRenderer     (kind overlay)       apply(frame, t, view) -> frame      (drawn on top of the base)
    TransitionRenderer  (kind transition)    blend(f_out, f_in, p) -> frame      (p = 0..1 progress)

`Ctx` carries what a renderer needs: canvas size, style constants, assets, the image store and the layer cache.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

from . import registry as R
from . import vfx

CANVAS_W, CANVAS_H = 1920, 1080


# ----------------------------------------------------------------------------- caches
class _LRU:
    """Thread-safe LRU bounded by bytes (and a floor of `keep` entries that are never evicted)."""

    def __init__(self, max_bytes: int, keep: int = 1):
        self.max_bytes, self.keep = max_bytes, keep
        self._d: OrderedDict = OrderedDict()
        self._size: dict = {}
        self._total = 0
        self._lock = threading.RLock()

    def get(self, key, build, sizeof):
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return self._d[key]
        val = build()                        # built outside the lock: image decode is slow
        with self._lock:
            if key in self._d:
                return self._d[key]
            n = sizeof(val)
            self._d[key] = val
            self._size[key] = n
            self._total += n
            while self._total > self.max_bytes and len(self._d) > self.keep:
                k, _ = self._d.popitem(last=False)
                self._total -= self._size.pop(k)
            return val

    def clear(self):
        with self._lock:
            self._d.clear(); self._size.clear(); self._total = 0

    def stats(self):
        with self._lock:
            return {"entries": len(self._d), "mb": round(self._total / 1e6, 1)}


def _img_bytes(im) -> int:
    return sum(l.nbytes for l in im.levels)


def _layer_bytes(L) -> int:
    return L.rgb.nbytes + L.a.nbytes + 200


# Process-wide stores: safe to share between projects because keys carry the file path + mtime (images) or all inputs (layers).
IMAGES = _LRU(int(float(os.environ.get("BTI_IMAGE_CACHE_MB", "900")) * 1e6), keep=2)
LAYERS = _LRU(int(float(os.environ.get("BTI_LAYER_CACHE_MB", "240")) * 1e6), keep=8)
MISC = _LRU(int(float(os.environ.get("BTI_MISC_CACHE_MB", "200")) * 1e6), keep=4)   # blurred backgrounds, procedural bitmaps


def hex_to_bgr(c: str):
    c = c.lstrip("#")
    return (int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16))


class View:
    """Where the base shot is looking: source point (cx, cy) at the canvas centre, zoom = screen px per source px."""

    def __init__(self, cx, cy, zoom, img, asset_key=None):
        self.cx, self.cy, self.z, self.img, self.asset_key = cx, cy, zoom, img, asset_key

    def to_screen(self, px, py):
        return self.img.to_screen(px, py, self.cx, self.cy, self.z, CANVAS_W, CANVAS_H)


def tag_asset(exc: BaseException, key, ctx=None) -> BaseException:
    """Remember on `exc` which asset key it is about (read back by `scene.render_error`); the first key set stays.
    With `ctx` it also records the asset's kind, its file (path relative to the project) and whether that file is missing, so the
    message for the owner can name the file without showing the exception text or a server path."""
    if isinstance(key, str) and getattr(exc, "bti_asset", None) is None:
        try:
            exc.bti_asset = key
            a = ctx.assets.get(key) if ctx is not None and isinstance(ctx.assets, dict) else None
            if isinstance(a, dict) and isinstance(a.get("file"), str):
                exc.bti_kind, exc.bti_file = a.get("kind"), a["file"]
                exc.bti_missing = not os.path.exists(os.path.join(str(ctx.project_dir), a["file"]))
        except Exception:       # noqa: BLE001
            pass
    return exc


class Ctx:
    def __init__(self, project_dir: Path, sb: dict, timing, bundle: R.StyleBundle):
        self.project_dir = Path(project_dir)
        self.sb = sb
        self.timing = timing
        self.bundle = bundle
        self.style = bundle.style
        self.w, self.h = CANVAS_W, CANVAS_H          # engine always renders 1080p and resizes down
        self.assets = sb.get("assets") or {}
        vfx.configure_fonts(self.style)
        self._font_sig = vfx.font_signature()

    # -- style -----------------------------------------------------------------------------------------------
    def sv(self, section, key, default=None):
        return self.bundle.sv(section, key, default)

    # -- assets ----------------------------------------------------------------------------------------------
    def asset(self, key: str) -> dict:
        try:
            return self.assets[key]
        except KeyError:
            raise tag_asset(KeyError("asset %r is not defined" % key), key, self)

    def asset_path(self, key: str) -> str:
        return str(self.project_dir / self.asset(key)["file"])

    def image(self, key: str) -> "vfx.Img":
        """Lazy, LRU-cached source image with its pyramid."""
        path = self.asset_path(key)
        try:
            mt = os.stat(path).st_mtime_ns
            return IMAGES.get(("img", path, mt), lambda: vfx.Img(path, key), _img_bytes)
        except Exception as e:      # noqa: BLE001 - a missing or unreadable file: say which asset it is
            raise tag_asset(e, key, self)

    def raw_image_reduced(self, key: str, reduce: int = 4):
        """Decode-time downscaled BGR image (cv2.IMREAD_REDUCED_COLOR_n), for blurred backgrounds."""
        import cv2
        path = self.asset_path(key)
        flag = {2: cv2.IMREAD_REDUCED_COLOR_2, 4: cv2.IMREAD_REDUCED_COLOR_4, 8: cv2.IMREAD_REDUCED_COLOR_8}[reduce]
        return cv2.imread(path, flag)

    def asset_size(self, key: str):
        a = self.asset(key)
        if a.get("width") and a.get("height"):
            return int(a["width"]), int(a["height"])
        im = self.image(key)
        return im.w, im.h

    def point(self, pt, asset_key):
        """Region name or [x, y] -> source pixels on the asset."""
        if isinstance(pt, str):
            r = (self.asset(asset_key).get("regions") or {}).get(pt)
            if r is None:
                raise KeyError("region %r is not defined on asset %r" % (pt, asset_key))
            return float(r["x"]), float(r["y"])
        return float(pt[0]), float(pt[1])

    # -- caches ----------------------------------------------------------------------------------------------
    def layer(self, key, build):
        """Cached `vfx.Layer`. The key is extended with canvas size and font choice, so a size or font change never hits."""
        return LAYERS.get(("layer", self.w, self.h, self._font_sig) + tuple(key), build, _layer_bytes)

    def cached(self, key, build, sizeof=lambda a: getattr(a, "nbytes", 1000)):
        return MISC.get(("misc", self.w, self.h, self._font_sig) + tuple(key), build, sizeof)

    # -- time ------------------------------------------------------------------------------------------------
    def t(self, anchor, shot=None) -> float:
        """Seconds for a resolved anchor (uses `_t`; falls back to resolving)."""
        if "_t" in anchor:
            return anchor["_t"]
        return self.timing.resolve(anchor, shot["_t0"] if shot else None, shot["_t1"] if shot else None)


# ----------------------------------------------------------------------------- renderer interfaces
class Renderer:
    """Common parts. `technique_ids` is filled by @technique."""
    technique_ids: tuple = ()

    @classmethod
    def default_params(cls, tid: str, spec: dict, context: dict, bundle: R.StyleBundle) -> dict:
        """Starting params when a human picks the technique. Default: the registry defaults."""
        return {p["name"]: p["default"] for p in spec["params"]}


class BaseRenderer(Renderer):
    def __init__(self, tid, shot, ctx: Ctx):
        self.tid, self.shot, self.ctx = tid, shot, ctx
        self.spec = ctx.bundle.spec(tid)
        self.p = R.merged_params(self.spec, shot.get("params"))
        self.t0, self.t1 = shot["_t0"], shot["_t1"]
        self.slots = shot.get("slots") or {}

    def slot_asset(self, name="image"):
        s = self.slots.get(name)
        return s.get("asset") if isinstance(s, dict) else None

    def render(self, t):                     # -> float32 BGR
        raise NotImplementedError

    def view(self, t):                       # -> View | None (None: overlays that need a camera are skipped)
        return None


class OverlayRenderer(Renderer):
    def __init__(self, tid, ov, shot_r: BaseRenderer, ctx: Ctx):
        self.tid, self.ov, self.shot_r, self.ctx = tid, ov, shot_r, ctx
        self.spec = ctx.bundle.spec(tid)
        self.p = R.merged_params(self.spec, ov.get("params"))
        self.t0, self.t1 = ov["_t0"], ov["_t1"]

    def apply(self, f, t, view):
        raise NotImplementedError


class TransitionRenderer(Renderer):
    def __init__(self, tid, tr, ctx: Ctx):
        self.tid, self.tr, self.ctx = tid, tr, ctx
        self.spec = ctx.bundle.spec(tid)
        self.p = R.merged_params(self.spec, tr.get("params"))
        self.dur = float(tr.get("dur", 0.0) or 0.0)

    def blend(self, f_out, f_in, p):
        raise NotImplementedError
