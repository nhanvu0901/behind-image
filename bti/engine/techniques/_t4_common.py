"""Small shared pieces for the diagram and shorts modules (`diagrams_t4`, `shorts`). Not a renderer module (leading underscore).

Nothing here knows any content: it parses params (point lists, `a|b|c` lines, aspect strings), builds cache signatures for
assets and turns a registry spec plus an editor context into default params.
"""
from __future__ import annotations

import os

import cv2
import numpy as np

from .. import vfx

# Benchmark painting width (px). Registry defaults for image-space numbers (zoom) were measured on an image of this width;
# `default_params` rescales them to the width of the asset the editor is working on.
REFERENCE_IMAGE_W = 4386.0


def asset_sig(ctx, key):
    """(path, mtime) of an asset file: part of every cache key that depends on its pixels."""
    path = ctx.asset_path(key)
    try:
        mt = os.stat(path).st_mtime_ns
    except OSError:
        mt = 0
    return (path, mt)


def focus_xy(ctx, pt, key):
    """A point param (region name, [x, y] or None = image centre) in source pixels of asset `key`."""
    if pt is None:
        w, h = ctx.asset_size(key)
        return w / 2.0, h / 2.0
    return ctx.point(pt, key)


def parse_point(v):
    """[x, y] or 'x,y' -> (float, float)."""
    if isinstance(v, str):
        v = [float(s) for s in v.split(",")]
    return float(v[0]), float(v[1])


def parse_bar(line, n=3):
    """'a|b|c' -> n stripped parts (missing ones are '')."""
    parts = [s.strip() for s in str(line).split("|")]
    return (parts + [""] * n)[:n] if len(parts) < n else parts


def aspect_wh(text, ph=1080):
    """'9:16' -> panel (pw, ph) with ph fixed to the canvas height."""
    try:
        a, b = str(text).replace("/", ":").split(":")
        return max(2, int(ph * float(a) / float(b) + 0.5)), ph
    except Exception:
        return int(ph * 9 / 16 + 0.5), ph


def luminance(bgr):
    return 0.114 * bgr[0] + 0.587 * bgr[1] + 0.299 * bgr[2]


def ease_name(name, default="inout_sine"):
    return name if name in vfx.EASE else default


def lerp_quad(q0, q1, p):
    return [(a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p) for a, b in zip(q0, q1)]


def warp_with_alpha(src, quad_px, size, fill_bgr):
    """Perspective-warp float32 `src` (h x w x 3) so its corners land on `quad_px` (TL, TR, BR, BL) inside a (w, h) canvas;
    everything outside the quad is the constant `fill_bgr` (no border replication, so no edge streaks)."""
    h, w = src.shape[:2]
    s = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    M = cv2.getPerspectiveTransform(s, np.float32(quad_px))
    ow, oh = size
    out = cv2.warpPerspective(src, M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    m = cv2.warpPerspective(np.ones((h, w), np.float32), M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)[:, :, None]
    m = np.clip(m, 0, 1)
    # `out` was interpolated against black at the edge: divide it back out so the border does not darken
    out = out / np.maximum(m, 1e-3)
    fill = np.asarray(fill_bgr, np.float32) if np.ndim(fill_bgr) else np.float32(fill_bgr)
    return out * m + fill * (1 - m)


# ----------------------------------------------------------------------------- default params
def ctx_point(context):
    """Region name or [x, y] the editor wants to focus on, as stored in a point param (None when unknown)."""
    r = context.get("region") if context.get("region") is not None else context.get("focus")
    a = context.get("asset") or {}
    if isinstance(r, str):
        reg = (a.get("regions") or {}).get(r)
        if reg is not None or not a:
            return r if reg is not None else None
        return None
    if isinstance(r, (list, tuple)) and len(r) == 2:
        return [float(r[0]), float(r[1])]
    return None


def scaled_zoom(default, context, bundle=None):
    a = context.get("asset") or {}
    w = a.get("w")
    ref = REFERENCE_IMAGE_W
    if bundle is not None:
        ref = float(bundle.sv("matte", "benchmark_painting_width_px", REFERENCE_IMAGE_W) or REFERENCE_IMAGE_W)
    if w:
        return float(default) * ref / float(w)
    return float(default)


def base_defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}
