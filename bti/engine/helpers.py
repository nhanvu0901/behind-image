"""Shared building blocks for technique ports (lifted from demo_runs/claude_code/build_reel.py).

Use these instead of writing your own; they follow the engine's caching rules (README "Caching rules").
All functions take the `Ctx` (self.ctx in a renderer) and work on float32 BGR frames of canvas size.

    paste(f, p, x, y)                       copy panel p into f at (x, y) (reel: paste)
    gray(f)                                 greyscale as 3-channel float32 (reel: gray)
    cover_zoom(iw, ih, pw, ph)              zoom at which an iw x ih image covers a pw x ph panel
    contain_zoom(iw, ih, pw, ph, pct)       zoom at which it fits inside, pct of the panel (default 0.94)
    tile_rects(n, cols, area, gutter, caption_h)   panel rectangles for a grid
    render_tiles(ctx, f, tiles, cols, area, gutter, caption_px)   draw a grid of panels with captions (reel: two_panels, LAY-02/03)
    mask_alpha(ctx, mask_key, cx, cy, zoom, ow, oh)   screen-space alpha (H x W x 1, 0..1) of a `mask` asset for a camera
    video_frame(ctx, key, t)                BGR uint8 frame of a `video` asset at source time t (small cache)
    vertical_panel(ctx, content, ambient_key, ambient_src, pw, ph)   9:16 content in 16:9 with blurred fill (reel: vpanel)
    text_block(ctx, lines, cx, cy, size, ...)   multi-line tracked text -> cached Layer (apply with envelope)
"""
from __future__ import annotations

import threading
from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import vfx
from .base import tag_asset
from .vfx import Img, Layer, backdrop, compose_matte


# ----------------------------------------------------------------------------- small pixel helpers
def paste(f, p, x, y):
    h, w = p.shape[:2]
    f[y:y + h, x:x + w] = p
    return f


def gray(f):
    g = cv2.cvtColor(np.clip(f, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return np.stack([g, g, g], -1)


def cover_zoom(iw, ih, pw, ph):
    return max(pw / iw, ph / ih)


def contain_zoom(iw, ih, pw, ph, pct=0.94):
    return pct * min(pw / iw, ph / ih)


# ----------------------------------------------------------------------------- tiles / grid
def tile_rects(n, cols, area, gutter=20, caption_h=0):
    """Rectangles (x, y, w, h) of n panels in a grid of `cols` columns inside area=(x, y, w, h); caption_h is reserved under each panel."""
    ax, ay, aw, ah = area
    rows = -(-n // cols)
    pw = (aw - gutter * (cols - 1)) // cols
    ph = (ah - gutter * (rows - 1) - caption_h * rows) // rows
    return [(ax + (i % cols) * (pw + gutter), ay + (i // cols) * (ph + gutter + caption_h), pw, ph) for i in range(n)]


def render_tiles(ctx, f, tiles, cols, area=(50, 36, 1820, 920), gutter=20, caption_px=30, sub_px=26):
    """Draw panels onto f. Each tile is a dict:
        {"asset": key, "view": (cx, cy, zoom) | None (None = cover-fit, centred), "matte": bool (painting on the backdrop),
         "caption": str | None, "sub": str | None}
    Returns (f, rects). Captions are centred under their panel (cached layers)."""
    has_cap = any(t.get("caption") for t in tiles)
    rects = tile_rects(len(tiles), cols, area, gutter, int(caption_px * 1.9) if has_cap else 0)
    for t, (x, y, w, h) in zip(tiles, rects):
        img = ctx.image(t["asset"])
        cx, cy, z = t["view"] if t.get("view") else (img.w / 2, img.h / 2, cover_zoom(img.w, img.h, w, h))
        if t.get("matte"):
            p = compose_matte(img, cx, cy, z, w, h)
        else:
            p = img.view(cx, cy, z, w, h)[0].astype(np.float32)
        paste(f, p, x, y)
        if t.get("caption"):
            cap, sub = t["caption"], t.get("sub") or None
            L = ctx.layer(("tilecap", cap, sub, x + w // 2, y + h + int(caption_px * 1.7), caption_px, sub_px),
                          lambda: vfx.text_layer(cap, x + w // 2, y + h + int(caption_px * 1.7), caption_px, "reg", 2, sub=sub, subsize=sub_px, w=ctx.w, h=ctx.h))
            L.apply(f)
    return f, rects


# ----------------------------------------------------------------------------- masks
def _mask_img(ctx, mask_key):
    import os
    path = ctx.asset_path(mask_key)

    def build():
        m = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if m is None:
            raise FileNotFoundError(path)
        return Img(cv2.cvtColor(m, cv2.COLOR_GRAY2BGR), mask_key)
    try:
        return ctx.cached(("mask", path, os.stat(path).st_mtime_ns), build, lambda im: sum(l.nbytes for l in im.levels))
    except Exception as e:      # noqa: BLE001
        raise tag_asset(e, mask_key, ctx)


def mask_alpha(ctx, mask_key, cx, cy, zoom, ow=None, oh=None, image_key=None):
    """Alpha (oh x ow x 1, float32 0..1) of a `mask` asset seen through a camera given in the ALIGNED IMAGE's source pixels.
    The mask may have a different resolution than its image (`image_key`: the aligned image asset; default the asset's
    `aligned_to` field). Outside the mask image the alpha is 0."""
    ow, oh = ow or ctx.w, oh or ctx.h
    mi = _mask_img(ctx, mask_key)
    ik = image_key or ctx.asset(mask_key).get("aligned_to")
    iw, ih = ctx.asset_size(ik) if ik else (mi.w, mi.h)
    sx, sy = mi.w / iw, mi.h / ih
    out, a, _ = mi.view(cx * sx, cy * sy, zoom / sx, ow, oh)
    return (out[:, :, :1].astype(np.float32) / 255.0) * a


# ----------------------------------------------------------------------------- video
class _Video:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise FileNotFoundError(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.n = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        self.pos = 0                      # index of the next frame cap.read() returns
        self.recent: OrderedDict = OrderedDict()

    def frame(self, idx):
        idx = max(0, min(idx, self.n - 1))
        if idx in self.recent:
            self.recent.move_to_end(idx)
            return self.recent[idx]
        if idx != self.pos:
            if 0 <= idx - self.pos <= 5:          # short forward gap: read through it, cheaper than a seek
                while self.pos < idx:
                    self.cap.read(); self.pos += 1
            else:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx); self.pos = idx
        ok, fr = self.cap.read()
        self.pos = idx + 1
        if not ok:
            fr = next(reversed(self.recent.values())) if self.recent else np.zeros((2, 2, 3), np.uint8)
        self.recent[idx] = fr
        while len(self.recent) > 8:
            self.recent.popitem(last=False)
        return fr


_VIDEOS: OrderedDict = OrderedDict()
_VLOCK = threading.RLock()


def video_frame(ctx, key, t, loop=False):
    """BGR uint8 frame of video asset `key` at source time t seconds (clamped to the clip, or looped). At most 3 files stay open."""
    path = ctx.asset_path(key)
    with _VLOCK:
        v = _VIDEOS.get(path)
        if v is None:
            try:
                v = _VIDEOS[path] = _Video(path)
            except Exception as e:      # noqa: BLE001
                raise tag_asset(e, key, ctx)
            while len(_VIDEOS) > 3:
                _, old = _VIDEOS.popitem(last=False)
                old.cap.release()
        else:
            _VIDEOS.move_to_end(path)
        idx = int(round(t * v.fps))
        if loop:
            idx %= v.n
        return v.frame(idx).copy()


def close_videos():
    with _VLOCK:
        for v in _VIDEOS.values():
            v.cap.release()
        _VIDEOS.clear()


# ----------------------------------------------------------------------------- vertical panel
def vertical_panel(ctx, content, ambient_key, ambient_src=None, pw=None, ph=1080, sigma=None, dark=None):
    """9:16 `content` (ph x pw x 3 float32) centred in the 16:9 canvas over a blurred, darkened ambient fill with a soft shadow.
    The expensive blur and shadow are computed ONCE per (ambient_key, size) from `ambient_src` (default: `content`) and cached;
    per frame only a copy and a paste remain (the reel recomputed the blur every frame: ~0.9 s)."""
    W, H = ctx.w, ctx.h
    pw = int(pw if pw is not None else ctx.sv("shorts", "panel_w_px", 608))          # defaults live in style.json "shorts"
    sigma = sigma if sigma is not None else ctx.sv("shorts", "ambient_blur_sigma", 38)
    dark = dark if dark is not None else ctx.sv("shorts", "ambient_darken", 0.42)
    x0 = (W - pw) // 2

    def build():
        src = ambient_src if ambient_src is not None else content
        bg = cv2.GaussianBlur(cv2.resize(np.asarray(src, np.float32), (W, int(W * ph / pw)), interpolation=cv2.INTER_AREA), (0, 0), sigma)
        y0 = (bg.shape[0] - H) // 2
        f = bg[y0:y0 + H] * dark
        sh = np.zeros((H, W), np.float32)
        sh[10:H, x0 - 6:x0 + pw + 6] = 1
        sh = cv2.GaussianBlur(sh, (0, 0), 18)[:, :, None]
        return (f * (1 - .5 * sh)).astype(np.float32)
    bg = ctx.cached(("vpanel", ambient_key, pw, ph, sigma, dark), build)
    f = bg.copy()
    f[:, x0:x0 + pw] = content
    return f


# ----------------------------------------------------------------------------- text block
def text_block(ctx, lines, cx, cy, size=60, kind="reg", tracking=0, color=(255, 255, 255), line_gap=1.25, align="center", shadow=True, upper=False):
    """Multi-line text centred (or left-aligned at cx) around cy, as a cached `Layer`. `kind`: reg, bold, sans_bold, serif_it.
    Use `layer.apply(f, env, dx, dy)`; the envelope is `vfx.window(t, t0, t1, fade_in, fade_out)` (or `fade_env` below)."""
    lines = [l.upper() if upper else l for l in ([lines] if isinstance(lines, str) else list(lines))]
    key = ("tblock", tuple(lines), cx, cy, size, kind, tracking, tuple(color), line_gap, align, shadow)

    def build():
        W, H = ctx.w, ctx.h
        ft = vfx.font(kind, size)
        step = int(size * line_gap)
        top = cy - (step * (len(lines) - 1)) // 2 - size // 2
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        def draw(d, fill):
            for i, ln in enumerate(lines):
                vfx._tracked(d, (cx, top + i * step), ln, ft, fill, tracking, "ma" if align == "center" else "la")
        if shadow:
            sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            draw(ImageDraw.Draw(sh), (0, 0, 0, 170))
            im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
        draw(ImageDraw.Draw(im), tuple(color) + (255,))
        arr = np.array(im)
        ys, xs = np.where(arr[:, :, 3] > 0)
        if ys.size == 0:
            return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)
        return Layer(arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1], int(xs.min()), int(ys.min()))
    return ctx.layer(key, build)


def fade_env(t, t0, t1, fade_in=0.1, fade_out=0.15):
    return vfx.window(t, t0, t1, fade_in, fade_out)
