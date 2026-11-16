"""Shared building blocks of the annotation / highlight / camera ports in `annotations_extra`, `highlights_extra` and
`camera_extra` (engineer T2).  The leading underscore keeps this module out of the automatic import of techniques.

    slot_key(obj, name)                       asset key stored under `slots.<name>` of a shot or an overlay
    Track                                     keyframed camera whose zoom may interpolate linearly (benchmark) or in log space
    mask_contours(ctx, mask_key, image_key)   outer contours of a `mask` asset, in the aligned image's source pixels (cached)
    dense_path(points, closed, step)          resample a user polyline so that "n points drawn" is proportional to length
    to_screen_arr(view, pts)                  vectorised View.to_screen
    draw_progress(canvas, paths, prog, thick) progressive anti-aliased polylines on a uint8 canvas
    blend_color(f, mask_u8, bgr, opacity)     alpha-blend a colour through a uint8 mask, restricted to its bounding box
    dim(f, factor, e)                         multiply the frame by 1 - (1 - factor) * e
    MapBackdrop                               the frame the map annotations draw on (base shot / map image / procedural map)
    soft_region(h, w, cx, cy, rx, ry, ...)    quarter-resolution soft ellipse / rounded rectangle mask
"""
from __future__ import annotations

import math
import os

import cv2
import numpy as np

from ..vfx import EASE, ease, text_layer


def slot_key(obj, name):
    s = (obj.get("slots") or {}).get(name) if isinstance(obj, dict) else None
    return s.get("asset") if isinstance(s, dict) else None


def numbered_slots(obj, prefix, n=6):
    """[(index, asset key)] of slots prefix_1 .. prefix_n that are present."""
    out = []
    for i in range(1, n + 1):
        k = slot_key(obj, "%s_%d" % (prefix, i))
        if k:
            out.append((i, k))
    return out


# ----------------------------------------------------------------------------- camera track
class Track:
    """Keyframed camera [(t, cx, cy, zoom, ease_to_next)].  `interp`: "linear" (the benchmark's layer motion) or "log"
    (the engine's `Cam`): how zoom is interpolated between two keys."""

    def __init__(self, keys, interp="log"):
        self.k = keys
        self.linear = interp == "linear"

    def at(self, t):
        k = self.k
        if t <= k[0][0]:
            return k[0][1:4]
        for a, b in zip(k[:-1], k[1:]):
            if t <= b[0]:
                p = ease(a[4], (t - a[0]) / (b[0] - a[0]))
                cx = a[1] + (b[1] - a[1]) * p
                cy = a[2] + (b[2] - a[2]) * p
                if self.linear:
                    z = a[3] + (b[3] - a[3]) * p
                else:
                    z = math.exp(math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * p)
                return cx, cy, z
        return k[-1][1:4]


def keys_from_param(shot, ctx, name):
    """[(t, cx, cy, zoom, ease)] from a camera param of the shot (anchors resolved), or None."""
    keys = (shot.get("params") or {}).get(name)
    if not keys:
        return None
    return [(ctx.t(k["at"], shot), float(k["cx"]), float(k["cy"]), float(k["zoom"]), k.get("ease", "linear")) for k in keys]


def fit_key(t0, iw, ih, canvas=(1920, 1080), cover=False, pct=0.955):
    """A static key that shows the whole image (contain, `pct` of the height) or covers the canvas."""
    W, H = canvas
    z = max(W / iw, H / ih) if cover else pct * H / ih
    return [(t0, iw / 2.0, ih / 2.0, z, "linear")]


def cam_key_json(rel, cx, cy, z, ease_name="linear"):
    return {"at": {"rel": rel}, "cx": round(float(cx), 2), "cy": round(float(cy), 2), "zoom": round(float(z), 6), "ease": ease_name}


# ----------------------------------------------------------------------------- paths
def mask_contours(ctx, mask_key, image_key=None, max_n=2, min_pts=12, thresh=128):
    """Outer contours of a `mask` asset (white = inside) as float32 (N, 2) arrays in source pixels of the aligned image.
    The longest `max_n` are kept (they are what a rough GrabCut mask gives; a good mask has one per object).  Each axis is scaled
    by image size / mask size, the same convention `helpers.mask_alpha` uses, so an outline sits exactly on the displayed silhouette."""
    path = ctx.asset_path(mask_key)
    ik = image_key or ctx.asset(mask_key).get("aligned_to")
    mt = os.stat(path).st_mtime_ns

    def build():
        m = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if m is None:
            raise FileNotFoundError(path)
        cs, _ = cv2.findContours((m > thresh).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cs = sorted([c for c in cs if len(c) >= min_pts], key=lambda c: -len(c))[:max_n]
        iw, ih = ctx.asset_size(ik) if ik else (m.shape[1], m.shape[0])
        sx, sy = iw / m.shape[1], ih / m.shape[0]
        return [c[:, 0, :].astype(np.float32) * np.float32([sx, sy]) for c in cs]
    return ctx.cached(("t2contours", path, mt, ik, max_n, min_pts, thresh), build, lambda cs: sum(c.nbytes for c in cs) + 64)


def dense_path(pts, closed=False, step=3.0):
    """Resample a polyline (list of [x, y]) to points about `step` source px apart, so that progress by point count is progress by length."""
    a = np.asarray(pts, np.float64)
    if closed:
        a = np.vstack([a, a[:1]])
    seg = np.hypot(*(a[1:] - a[:-1]).T)
    total = float(seg.sum())
    if total <= 0:
        return a.astype(np.float32)
    n = max(int(total / step), 2)
    cum = np.concatenate([[0], np.cumsum(seg)])
    u = np.linspace(0, total, n)
    return np.stack([np.interp(u, cum, a[:, 0]), np.interp(u, cum, a[:, 1])], 1).astype(np.float32)


def to_screen_arr(view, pts):
    W, H = 1920, 1080
    return np.stack([W / 2 + (pts[:, 0] - view.cx) * view.z, H / 2 + (pts[:, 1] - view.cy) * view.z], 1)


def draw_progress(canvas, paths, prog, thick, closed=True):
    """Draw the first `prog` fraction of each screen-space path (float (N, 2)) as an anti-aliased polyline.
    A closed path is closed once it is complete.  Points are truncated to ints, as the benchmark does."""
    for sc in paths:
        n = int(len(sc) * prog)
        if n > 2:
            cv2.polylines(canvas, [sc[:n].astype(np.int32)], bool(closed and n >= len(sc)), 255, int(thick), cv2.LINE_AA)
    return canvas


def blend_color(f, m, bgr, opacity=1.0):
    """f = f * (1 - a) + colour * a, with a = mask / 255 * opacity, on the mask's bounding box only."""
    if opacity <= 0:
        return f
    x, y, w, h = cv2.boundingRect(m)
    if w == 0 or h == 0:
        return f
    a = m[y:y + h, x:x + w].astype(np.float32)[:, :, None] * (opacity / 255.0)
    reg = f[y:y + h, x:x + w]
    f[y:y + h, x:x + w] = reg * (1 - a) + np.array(bgr, np.float32) * a
    return f


def dim(f, factor, e=1.0):
    g = 1 - (1 - float(factor)) * float(e)
    return f * g if g < 0.9999 else f


def out_env(t, t1, fade_s):
    """1 until t1 - fade_s, then fades to 0 at t1 (nothing is drawn at or after t1)."""
    if t >= t1:
        return 0.0
    if fade_s <= 0:
        return 1.0
    return 1.0 - ease("linear", (t - (t1 - fade_s)) / fade_s)


def hex_bgr(c):
    c = c.lstrip("#")
    return (int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16))


# ----------------------------------------------------------------------------- soft regions (X-HI-01)
def soft_region(h, w, cx, cy, rx, ry, shape="ellipse", feather=0.55, q=4):
    """0 inside .. 1 outside float mask (h x w x 1), computed at 1/q resolution and resized.  `ellipse` follows the benchmark spotlight
    (distance 1 - feather/2 .. 1 + feather/2 is the transition); `rect` uses the Chebyshev distance, so the bright region is a rounded-edge box."""
    yy, xx = np.mgrid[0:h // q, 0:w // q].astype(np.float32)
    dx = np.abs(xx * q - cx) / max(rx, 1.0)
    dy = np.abs(yy * q - cy) / max(ry, 1.0)
    d = np.sqrt(dx * dx + dy * dy) if shape == "ellipse" else np.maximum(dx, dy)
    m = np.clip((d - (1 - feather * .5)) / max(feather, 1e-3), 0, 1)
    m = m * m * (3 - 2 * m)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR)[:, :, None]


# ----------------------------------------------------------------------------- map backdrop
BACKGROUNDS = ["auto", "base", "image", "procedural"]


def procedural_map(ctx, seed=5):
    """The grey stand-in map of the benchmark (same drawing as the STATIC-06 background), cached."""
    W, H = ctx.w, ctx.h

    def build():
        f = np.zeros((H, W, 3), np.float32) + (150, 150, 150)
        r = np.random.RandomState(seed)
        for _ in range(22):
            c = (int(r.randint(0, W)), int(r.randint(0, H)))
            cv2.ellipse(f, c, (int(r.randint(160, 420)), int(r.randint(80, 220))), int(r.randint(0, 180)), 0, 360, (172, 170, 168), -1, cv2.LINE_AA)
        f = cv2.GaussianBlur(f, (0, 0), 4)
        for gx in range(0, W, 160):
            cv2.line(f, (gx, 0), (gx, H), (140, 140, 140), 1)
        for gy in range(0, H, 160):
            cv2.line(f, (0, gy), (W, gy), (140, 140, 140), 1)
        return f
    return ctx.cached(("t2procmap", seed), build)


class MapBackdrop:
    """What a map annotation draws on.  mode:
         base         the parent shot's frame; positions are source pixels of the shot's image (through its camera)
         image        the `map` slot image fitted to cover the canvas (centred), painted over the frame; positions are pixels of that image
         procedural   the grey stand-in map (named fallback when no real map is available); positions are canvas pixels
         auto         image when a `map` slot is present, else procedural
    `frame(f, view)` returns (f, to_screen, asset_key); to_screen(point_or_region) -> (x, y) on the canvas, or None when there is no view."""

    def __init__(self, ctx, ov, mode, seed=5):
        self.ctx = ctx
        self.map_key = slot_key(ov, "map")
        if mode == "auto":
            mode = "image" if self.map_key else "procedural"
        if mode == "image" and not self.map_key:
            raise ValueError("background 'image' needs a `map` slot")
        self.mode, self.seed = mode, int(seed)

    def frame(self, f, view):
        ctx = self.ctx
        W, H = ctx.w, ctx.h
        if self.mode == "base":
            if view is None:
                return f, None, None
            return f, (lambda pt: view.to_screen(*ctx.point(pt, view.asset_key))), view.asset_key
        if self.mode == "procedural":
            return procedural_map(ctx, self.seed).copy(), (lambda pt: ctx.point(pt, None)), None
        key = self.map_key
        img = ctx.image(key)
        z = max(W / img.w, H / img.h)
        path = ctx.asset_path(key)
        bg = ctx.cached(("t2mapimg", path, os.stat(path).st_mtime_ns, W, H), lambda: img.view(img.w / 2, img.h / 2, z, W, H)[0])
        return bg.astype(np.float32), (lambda pt: (W / 2 + (ctx.point(pt, key)[0] - img.w / 2) * z, H / 2 + (ctx.point(pt, key)[1] - img.h / 2) * z)), key


def text_at(ctx, text, size, tracking, kind="reg"):
    """A text layer built once at the canvas centre (README rule 6): apply with integer offsets (x - W//2, y - H//2)."""
    W, H = ctx.w, ctx.h
    return ctx.layer(("t2text", text, size, tracking, kind), lambda: text_layer(text, W // 2, H // 2, size, kind, tracking, w=W, h=H))


def stamp_circle(f, cx, cy, r, bgr, alpha=1.0, thick=-1):
    """Anti-aliased circle (filled when thick < 0) blended into f on its bounding box."""
    if alpha <= 0 or r <= 0:
        return f
    H, W = f.shape[:2]
    pad = int(r + max(thick, 0) + 3)
    x0, y0 = int(cx) - pad, int(cy) - pad
    x1, y1 = x0 + 2 * pad + 1, y0 + 2 * pad + 1
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if fx1 <= fx0 or fy1 <= fy0:
        return f
    S = 4
    m = np.zeros(((y1 - y0) * S, (x1 - x0) * S), np.uint8)
    cv2.circle(m, (int(round((cx - x0) * S)), int(round((cy - y0) * S))), int(round(r * S)), 255, int(round(thick * S)) if thick > 0 else -1, cv2.LINE_8)
    a = cv2.resize(m, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA).astype(np.float32)[:, :, None] * (alpha / 255.0)
    a = a[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    reg = f[fy0:fy1, fx0:fx1]
    f[fy0:fy1, fx0:fx1] = reg * (1 - a) + np.array(bgr, np.float32) * a
    return f


EASES = sorted(EASE)
