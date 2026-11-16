"""Private helpers shared by the T1 modules (layouts_grid, compare, transitions_extra).  Not a technique module (leading underscore).

Nothing here is specific to one painting: every number comes from a param of the calling technique.
"""
from __future__ import annotations

import cv2
import numpy as np

from .. import vfx
from ..helpers import cover_zoom, gray
from ..vfx import Cam, compose_matte
from .camera import camera_keys

TREATMENTS = ["none", "grey", "white", "sepia", "warm", "contrast"]


def cam_of(shot, ctx, name):
    """Cam for a camera param of the shot (keys in absolute seconds) or None when the param is absent/null."""
    k = camera_keys(shot, ctx, name)
    return Cam(k) if k else None


def hexbgr(c):
    c = c.lstrip("#")
    return (int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16))


def treat(img, name):
    """Colour treatment of a float32 BGR image (0..255)."""
    if name in (None, "none", "colour"):
        return img
    g = gray(img)
    if name == "grey":
        return g
    gg = g[:, :, 0]
    if name == "white":
        return np.clip(g + 60, 0, 255)
    if name == "sepia":
        return np.stack([gg * .55, gg * .75, gg * 1.0], -1)
    if name == "warm":
        return np.stack([gg * .62, gg * .78, gg * 1.0], -1)
    if name == "contrast":
        return np.clip((img - 110) * 1.8 + 110, 0, 255)
    raise ValueError("unknown treatment %r" % name)


def panel(ctx, key, cam, t, w, h, matte=False, pct=0.94):
    """float32 BGR (h, w, 3) view of asset `key` through camera `cam` (a Cam or None: cover-fit, or contain on the matte)."""
    img = ctx.image(key)
    if cam is not None:
        cx, cy, z = cam.at(t)
    else:
        cx, cy = img.w / 2, img.h / 2
        z = pct * min(w / img.w, h / img.h) if matte else cover_zoom(img.w, img.h, w, h)
    if matte:
        return compose_matte(img, cx, cy, z, w, h)
    return img.view(cx, cy, z, w, h)[0].astype(np.float32)


def aligned_cam(ctx, vals, key_from, key_to):
    """(cx, cy, z) of an aligned image: the same view of a picture stored at another resolution (scan vs print)."""
    if key_from == key_to:
        return vals
    wa, ha = ctx.asset_size(key_from)
    wb, hb = ctx.asset_size(key_to)
    cx, cy, z = vals
    return cx * wb / wa, cy * hb / ha, z * wa / wb


def aligned_view(ctx, key_from, key_to, cam, t, w, h):
    """View of `key_to` that shows what `cam` (given in the pixels of `key_from`) shows of `key_from`; cover-fit when cam is None."""
    if cam is None:
        return panel(ctx, key_to, None, t, w, h)
    cx, cy, z = aligned_cam(ctx, cam.at(t), key_from, key_to)
    return ctx.image(key_to).view(cx, cy, z, w, h)[0].astype(np.float32)


def caption(ctx, text, sub, cx, cy, size=30, tracking=2, subsize=26):
    return ctx.layer(("t1cap", text, sub or None, cx, cy, size, tracking, subsize),
                     lambda: vfx.text_layer(text, cx, cy, size, "reg", tracking, sub=sub or None, subsize=subsize, w=ctx.w, h=ctx.h))


def as_lines(v):
    """A `lines` param (list of str) or a newline separated string -> list of str."""
    if v is None:
        return []
    if isinstance(v, str):
        return [s for s in v.split("\n")]
    return [str(s) for s in v]


def floats(s, n=None, fill=0.0):
    out = [float(x) for x in str(s).replace(";", ",").split(",") if x.strip() != ""]
    if n is not None:
        out = (out + [out[-1] if out else fill] * n)[:n]
    return out


def key_at(rel, cx, cy, z, ease="linear"):
    return {"at": {"rel": rel}, "cx": round(float(cx), 2), "cy": round(float(cy), 2), "zoom": round(float(z), 5), "ease": ease}


def static_cam(cx, cy, z):
    return [key_at(0.0, cx, cy, z), key_at(1.0, cx, cy, z)]


def fit_cam(a, w, h, cover=True, pct=0.94):
    """Default camera for asset info `a` ({w, h}) in a w x h panel."""
    z = cover_zoom(a["w"], a["h"], w, h) if cover else pct * min(w / a["w"], h / a["h"])
    return static_cam(a["w"] / 2, a["h"] / 2, z)


def region_xy(a, context):
    """Focus point of a context: region name / [x, y] / centre of the asset."""
    f = context.get("focus") or context.get("region")
    if isinstance(f, str):
        r = (a.get("regions") or {}).get(f)
        if r:
            return float(r["x"]), float(r["y"])
    elif isinstance(f, (list, tuple)) and len(f) == 2:
        return float(f[0]), float(f[1])
    return a["w"] / 2.0, a["h"] / 2.0


def pdef(name, typ, default, mn=None, mx=None, unit=None, values=None, **kw):
    """Registry param dict (for building the patch file)."""
    d = {"name": name, "type": typ, "default": default, "min": mn, "max": mx, "unit": unit, "values": values, "measured": None}
    d.update(kw)
    return d
