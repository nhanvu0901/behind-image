"""Shared text-layout helpers of the TEXT / CARDS / STATIC / FOOTAGE ports (modules text_extra, cards_extra, static_extra, footage).

Everything here follows the engine's rules: no per-frame state, layers are built once through `ctx.layer`.
`block_layer` with one row is pixel-identical to `vfx.text_layer` (same shadow, same tracking, same bbox crop); it adds wrapping,
several rows (a quote and its attribution), colours, an extra font face (`serif` = Georgia regular) and never fails on empty or off-canvas text.
"""
from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .. import vfx
from ..vfx import Layer

FONT_KINDS = ("reg", "bold", "sans_bold", "serif_it", "serif")
_SERIF = [r"C:\Windows\Fonts\georgia.ttf", r"C:\Windows\Fonts\times.ttf", "/System/Library/Fonts/Supplemental/Georgia.ttf",
          "/System/Library/Fonts/Supplemental/Times New Roman.ttf"]
_CACHE: dict = {}


def font(kind, size):
    """vfx fonts plus `serif` (upright Georgia, falling back to the italic face)."""
    size = max(1, int(size))
    if kind != "serif":
        return vfx.font(kind if kind in vfx._FONTS else "reg", size)
    key = ("serif", size)
    if key not in _CACHE:
        ft = None
        for p in _SERIF:
            if os.path.exists(p):
                try:
                    ft = ImageFont.truetype(p, size)
                    break
                except Exception:
                    continue
        _CACHE[key] = ft or vfx.font("serif_it", size)
    return _CACHE[key]


def serif_signature():
    return next((os.path.basename(p) for p in _SERIF if os.path.exists(p)), "none")


def hex_rgb(c, default=(255, 255, 255)):
    try:
        c = c.lstrip("#")
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except Exception:
        return default


def _tracked(draw, xy, text, ft, fill, tracking=0, centre=True):
    x, y = xy
    widths = [draw.textlength(c, font=ft) for c in text]
    total = sum(widths) + tracking * max(len(text) - 1, 0)
    if centre:
        x -= total / 2
    for c, w in zip(text, widths):
        draw.text((x, y), c, font=ft, fill=fill)
        x += w + tracking


def text_width(text, kind, size, tracking=0):
    ft = font(kind, size)
    d = ImageDraw.Draw(Image.new("L", (10, 10)))
    return sum(d.textlength(c, font=ft) for c in text) + tracking * max(len(text) - 1, 0)


def wrap(text, kind, size, tracking, max_w):
    """Greedy word wrap of `text` (explicit newlines kept) so that no line is wider than max_w; a single longer word keeps its own line."""
    out = []
    for para in str(text or "").split("\n"):
        words = para.split()
        if not words:
            out.append("")
            continue
        cur = words[0]
        for w in words[1:]:
            if text_width(cur + " " + w, kind, size, tracking) <= max_w:
                cur += " " + w
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    while out and out[-1] == "":
        out.pop()
    return out


def fit_size(text, kind, size, tracking, max_w, min_size=24, step=2):
    """Largest size <= `size` at which the single line `text` fits max_w (the chapter card behaviour)."""
    while size > min_size and text_width(text, kind, size, tracking) > max_w:
        size -= step
    return size


def block_layer(w, h, rows, cx, cy, shadow=True, line_gap=1.25, attr_gap_px=18):
    """Centred rows of text as a bbox-cropped `Layer`. rows = [{"text", "size", "kind", "tracking", "color": (r, g, b), "attr": bool}].
    Rows with attr=False are the body (stepped by size * line_gap); an attr row sits `attr_gap_px` under the body.
    The block is centred on cy; one body row is placed exactly like `vfx.text_layer` (top = cy - size // 2)."""
    rows = [r for r in rows if r.get("text") is not None]
    if not rows or not any(str(r["text"]).strip() for r in rows):
        return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)
    ys, y = [], 0
    prev = None
    for r in rows:
        if prev is None:
            y = 0
        elif r.get("attr"):
            y = ys[-1] + int(prev["size"]) + int(attr_gap_px)
        else:
            y = ys[-1] + int(int(r["size"]) * line_gap)
        ys.append(y)
        prev = r
    total = ys[-1] + int(rows[-1]["size"])
    top = int(cy) - total // 2
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def draw(d, colour=None):
        for r, yy in zip(rows, ys):
            col = colour or (tuple(r.get("color", (255, 255, 255))) + (255,))
            _tracked(d, (int(cx), top + yy), str(r["text"]), font(r.get("kind", "reg"), r["size"]), col, int(r.get("tracking", 0)))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw(ImageDraw.Draw(sh), (0, 0, 0, 170))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(9)))
    draw(ImageDraw.Draw(im))
    arr = np.array(im)
    yy, xx = np.where(arr[:, :, 3] > 0)
    if yy.size == 0:
        return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)
    y0, y1, x0, x1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
    return Layer(arr[y0:y1, x0:x1], int(x0), int(y0))


def style_default(bundle, section, key, default):
    try:
        return bundle.sv(section, key, default)
    except Exception:
        return default


def asset_dict(context):
    a = (context or {}).get("asset")
    return a if isinstance(a, dict) else {}


def param(name, typ, default, mn=None, mx=None, unit=None, values=None):
    return {"name": name, "type": typ, "default": default, "min": mn, "max": mx, "unit": unit, "values": values, "measured": None}
