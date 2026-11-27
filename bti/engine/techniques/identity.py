"""Channel identity "Raking Light" (family ID): the opening, the channel-name beat and the chapter marks, in two styles.

Style `raking` ("Vệt sáng quét"): a soft band of light sweeps over the dimmed picture and writes the text.
    ID-OPEN-01   overlay  raking reveal of the shot under it (the opening)
    ID-LABEL-01  overlay  two-line artwork label without a strip
    ID-BRAND-01  base     channel name written by the band
    ID-BRAND-03  base     channel name written by the band, then a second sweep writes the video's title and a small line under it
    ID-MARK-01   base     chapter mark written by the band
Style `dim` ("Tối lại, hiện tên"): the picture dims and a line of text fades in.
    ID-OPEN-02   overlay  dim and name (the opening)
    ID-BRAND-02  base     channel name on the dimmed picture
    ID-MARK-02   base     chapter mark on the dimmed picture
Design and numbers: docs/design/2026-11-18-identity-raking-light.md (sections 2 to 4); moving mock-ups: docs/design/2026-11-18-d13-identity-mock.html.

Rules shared by all eight (the ids are not consecutive: ID-BRAND-03 came later, beside ID-BRAND-01, which it leaves as it was):
  * Times in the params are NOMINAL seconds from the start of the element (the overlay, or the shot for a base technique). When the
    element is shorter than its nominal length every time is scaled by (actual length / nominal length); a longer element keeps the
    nominal times and holds its last state (the brand beats), or ends plain (opening, marks). An element is meant to be >= 1.5 s.
  * The picture of a base technique is drawn exactly as CAM-01 draws it (the class derives from `MatteShot`), so `view()` returns the
    camera and overlays work on top of it. The light and the text are applied after the picture.
  * Light is brightness: the frame is multiplied by a gain (see `vfx.Band`); nothing is ever drawn as a box, strip or flat ground.
  * Text sizes are CAP HEIGHTS in percent of the frame height; the font size comes from the real metrics of the bundled EB Garamond
    (`vfx.cap_ratio`). A line wider than `max_width_pct` is made smaller until it fits (one line, always).
  * "Revealed by the band": the opacity of the text at a pixel is the largest value the band's mask has had there so far; for a band
    that moves in one direction at constant speed that is `Band.reveal` (1 behind the centre line, the band's own shoulder ahead of
    it), so a frame is a pure function of time and frames can be drawn in any order.
"""
from __future__ import annotations

import math
import os
import struct
import threading
from typing import NamedTuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from bti.media import contentbox as CB

from .. import vfx
from ..base import OverlayRenderer
from ..registry import technique
from ..vfx import Band, composite_layer_masked
from .camera import MatteShot, fit_zoom

INK = (244, 239, 228)            # the video ink of the mock-up, #f4efe4 (RGB)
SHADOW_ALPHA = 0.6               # soft shadow behind every line of text (mock-up: 0 0 .9cqw rgba(0,0,0,.6))
SHADOW_SIGMA = 0.0045            # Gaussian sigma of that shadow, as a fraction of the canvas width (0.9cqw blur radius / 2)
MAX_LINE_W_PCT = 88.0            # a line of text is never wider than this share of the frame: it is made smaller instead (never wrapped)
TITLE_MAX_W_PCT = 84.0           # ID-BRAND-03: the title and the small line under it keep a margin of 8 % of the width on each side (a longer line is made smaller)


# ----------------------------------------------------------------------------- timeline helpers
def ramp01(x, a, d):
    """Linear progress of `x` over [a, a + d], clamped to 0..1 (a step at `a` when d <= 0)."""
    if d <= 0:
        return 1.0 if x >= a else 0.0
    return min(max((x - a) / d, 0.0), 1.0)


def ss01(x, a, d):
    """The same with a smoothstep curve (the mock-up's `kf(..., smooth)`)."""
    s = ramp01(x, a, d)
    return s * s * (3.0 - 2.0 * s)


def time_scale(actual, nominal):
    """Factor applied to every nominal time: actual / nominal when the element is shorter than its nominal length, else 1."""
    if nominal > 0 and actual > 0:
        return min(1.0, actual / nominal)
    return 1.0


def fade_window(tau, t_in, d_in, t_out, d_out):
    """Opacity 0..1..0 (linear): in over [t_in, t_in + d_in], out over [t_out, t_out + d_out]."""
    return ramp01(tau, t_in, d_in) * (1.0 - ramp01(tau, t_out, d_out))


# ----------------------------------------------------------------------------- pair kerning (ID-BRAND-03's title)
# The bundled faces keep their kerning in the GPOS table; Pillow's basic layout (the only one on the server: no libraqm) reads only the old
# `kern` table, so "Wa" in the italic face came out with a gap. `_Kerning` reads the pair adjustments of the face's `kern` feature with the
# standard library; a face that cannot be read simply gets no kerning (never an error).
_U16, _I16, _U32 = struct.Struct(">H"), struct.Struct(">h"), struct.Struct(">I")


def _u16(d, o):
    return _U16.unpack_from(d, o)[0]


def _i16(d, o):
    return _I16.unpack_from(d, o)[0]


def _u32(d, o):
    return _U32.unpack_from(d, o)[0]


class _Kerning:
    """Horizontal pair adjustments of a TrueType face (GPOS pair adjustment lookups of the `kern` feature, formats 1 and 2, also behind an
    extension lookup). `pair(a, b)` is the adjustment between two characters in font units (negative: closer), 0 for anything unknown."""

    def __init__(self, d):
        self.d = d
        n = _u16(d, 4)
        tb = {d[12 + 16 * i:16 + 16 * i].decode("latin-1"): _u32(d, 20 + 16 * i) for i in range(n)}
        self.upem = _u16(d, tb["head"] + 18)
        self._cmap = self._read_cmap(tb["cmap"])
        self._glyphs = {}
        self._sets = {}
        self.lookups = self._read_lookups(tb["GPOS"])

    def _read_cmap(self, off):
        d = self.d
        best = None
        for want in ((3, 10), (0, 4), (0, 6), (3, 1), (0, 3), (0, 2), (0, 1), (0, 0)):
            for i in range(_u16(d, off + 2)):
                if (_u16(d, off + 4 + 8 * i), _u16(d, off + 6 + 8 * i)) == want:
                    best = off + _u32(d, off + 8 + 8 * i)
                    break
            if best is not None:
                break
        if best is None:
            raise ValueError("no usable cmap")
        fmt = _u16(d, best)
        if fmt == 4:
            segx2 = _u16(d, best + 6)
            ends = best + 14
            starts = ends + segx2 + 2
            deltas = starts + segx2
            ranges = deltas + segx2
            return (4, [(_u16(d, ends + 2 * i), _u16(d, starts + 2 * i), _i16(d, deltas + 2 * i), _u16(d, ranges + 2 * i), ranges + 2 * i)
                        for i in range(segx2 // 2)])
        if fmt == 12:
            return (12, [(_u32(d, best + 16 + 12 * i), _u32(d, best + 20 + 12 * i), _u32(d, best + 24 + 12 * i)) for i in range(_u32(d, best + 12))])
        raise ValueError("cmap format %d" % fmt)

    def glyph(self, ch):
        c = ord(ch)
        if c in self._glyphs:
            return self._glyphs[c]
        d, g = self.d, 0
        fmt, segs = self._cmap
        if fmt == 4:
            for e, st, dl, ro, rpos in segs:
                if st <= c <= e:
                    if ro == 0:
                        g = (c + dl) & 0xFFFF
                    else:
                        g = _u16(d, rpos + ro + 2 * (c - st))
                        g = (g + dl) & 0xFFFF if g else 0
                    break
        else:
            for st, e, g0 in segs:
                if st <= c <= e:
                    g = g0 + c - st
                    break
        self._glyphs[c] = g
        return g

    def _coverage(self, o):
        d = self.d
        out = {}
        if _u16(d, o) == 1:
            for i in range(_u16(d, o + 2)):
                out[_u16(d, o + 4 + 2 * i)] = i
        else:
            for i in range(_u16(d, o + 2)):
                st, e, si = _u16(d, o + 4 + 6 * i), _u16(d, o + 6 + 6 * i), _u16(d, o + 8 + 6 * i)
                for g in range(st, e + 1):
                    out[g] = si + g - st
        return out

    def _classdef(self, o):
        d = self.d
        out = {}
        if _u16(d, o) == 1:
            first = _u16(d, o + 2)
            for i in range(_u16(d, o + 4)):
                out[first + i] = _u16(d, o + 6 + 2 * i)
        else:
            for i in range(_u16(d, o + 2)):
                st, e, c = _u16(d, o + 4 + 6 * i), _u16(d, o + 6 + 6 * i), _u16(d, o + 8 + 6 * i)
                for g in range(st, e + 1):
                    out[g] = c
        return out

    def _read_lookups(self, g):
        d = self.d
        feature_list, lookup_list = g + _u16(d, g + 6), g + _u16(d, g + 8)
        wanted = []
        for i in range(_u16(d, feature_list)):
            if d[feature_list + 2 + 6 * i:feature_list + 6 + 6 * i] == b"kern":
                fo = feature_list + _u16(d, feature_list + 6 + 6 * i)
                wanted += [_u16(d, fo + 4 + 2 * k) for k in range(_u16(d, fo + 2))]
        out = []
        for idx in sorted(set(wanted)):
            lo = lookup_list + _u16(d, lookup_list + 2 + 2 * idx)
            ltype, subs = _u16(d, lo), []
            for k in range(_u16(d, lo + 4)):
                so = lo + _u16(d, lo + 6 + 2 * k)
                t = ltype
                if ltype == 9:                                       # an extension lookup: the real subtable is behind a 32-bit offset
                    t, so = _u16(d, so + 2), so + _u32(d, so + 4)
                if t != 2:
                    continue
                fmt, v1, v2 = _u16(d, so), _u16(d, so + 4), _u16(d, so + 6)
                cov = self._coverage(so + _u16(d, so + 2))
                if fmt == 1:
                    subs.append((1, cov, v1, v2, so, None, None, 0))
                elif fmt == 2:
                    subs.append((2, cov, v1, v2, so, self._classdef(so + _u16(d, so + 8)), self._classdef(so + _u16(d, so + 10)), _u16(d, so + 14)))
            if subs:
                out.append(subs)
        return out

    @staticmethod
    def _size(fmt):
        return 2 * bin(fmt & 0xFF).count("1")

    def _xadvance(self, o, fmt):
        """XAdvance of the value record at `o` (0 when the value format has none)."""
        return _i16(self.d, o + 2 * bin(fmt & 3).count("1")) if fmt & 4 else 0

    def _value(self, sub, g1, g2):
        fmt, cov, v1, v2, so, cd1, cd2, c2n = sub
        if g1 not in cov:
            return None
        d = self.d
        rec = self._size(v1) + self._size(v2)
        if fmt == 1:
            key = (so, g1)
            if key not in self._sets:
                ps = so + _u16(d, so + 10 + 2 * cov[g1])
                self._sets[key] = {_u16(d, ps + 2 + (2 + rec) * i): ps + 2 + (2 + rec) * i + 2 for i in range(_u16(d, ps))}
            at = self._sets[key].get(g2)
            return None if at is None else self._xadvance(at, v1)
        return self._xadvance(so + 16 + (cd1.get(g1, 0) * c2n + cd2.get(g2, 0)) * rec, v1)

    def pair(self, a, b):
        g1, g2 = self.glyph(a), self.glyph(b)
        if not g1 or not g2:
            return 0
        total = 0
        for subs in self.lookups:
            for sub in subs:
                v = self._value(sub, g1, g2)
                if v is not None:                                    # the first subtable of a lookup that knows the pair decides
                    total += v
                    break
        return total


_KERNING = {}
_KERNING_LOCK = threading.Lock()


def _kerning(kind):
    """The `_Kerning` of a bundled face, or None when the face has none or cannot be read (read once per file, then kept)."""
    try:
        path = vfx.bundled_font_path(kind)
    except KeyError:                                                     # not a bundled face
        return None
    key = (kind, str(path))
    with _KERNING_LOCK:
        if key not in _KERNING:
            try:
                _KERNING[key] = _Kerning(path.read_bytes())
            except Exception:                                            # noqa: BLE001 - a face that cannot be read is set without kerning
                _KERNING[key] = None
        return _KERNING[key]


# ----------------------------------------------------------------------------- text
def _build_ink(W, H, text, kind, cap_pct, tracking_pct, baseline_pct, centre_pct, x_pct, align, max_w_pct, shadow, kern=False):
    """One line of text (ink and a soft shadow) as a canvas-positioned `vfx.Layer`. `kern`: a sentence (no tracking) is set glyph by glyph with
    the pair kerning of its face."""
    ratio = vfx.cap_ratio(kind)
    size = max(6, int(round(cap_pct / 100.0 * H / ratio)))
    max_w = max_w_pct / 100.0 * W

    def measure(sz):
        ft = vfx.font(kind, sz)
        trk = tracking_pct / 100.0 * sz
        if trk > 0:                                  # tracked capitals: letter by letter (no trailing space after the last letter)
            adv = [ft.getlength(c) for c in text]
            return ft, trk, adv, sum(adv) + trk * (len(text) - 1)
        if kern:
            k = _kerning(kind)
            if k is not None:                        # a kerned sentence: each glyph's advance carries the adjustment to the next one
                adv = [ft.getlength(c) for c in text]
                for i in range(len(text) - 1):
                    adv[i] += k.pair(text[i], text[i + 1]) * sz / k.upem
                return ft, 0.0, adv, sum(adv)
        return ft, 0.0, None, ft.getlength(text)    # a sentence: whole string, so the face's own kerning applies

    ft, trk, adv, width = measure(size)
    if width > max_w > 0:
        size = max(6, min(size - 1, int(size * max_w / width)))
        ft, trk, adv, width = measure(size)
        while width > max_w and size > 6:
            size -= 1
            ft, trk, adv, width = measure(size)
    asc, desc = ft.getmetrics()
    sigma = SHADOW_SIGMA * W
    m = int(4 * sigma) + 3                           # room for the shadow around the ink
    pad_x = m + int(size * 0.15)                     # and for the overhang of italic letters
    img = Image.new("L", (int(math.ceil(width)) + 2 * pad_x, asc + desc + 2 * m), 0)
    d = ImageDraw.Draw(img)
    base_y = m + asc
    if adv is None:
        d.text((pad_x, base_y), text, font=ft, fill=255, anchor="ls")
    else:
        x = float(pad_x)
        for c, a in zip(text, adv):
            d.text((x, base_y), c, font=ft, fill=255, anchor="ls")
            x += a + trk
    a = np.asarray(img, np.float32) / 255.0
    sh = cv2.GaussianBlur(a, (0, 0), sigma) * SHADOW_ALPHA if shadow else np.zeros_like(a)
    out_a = a + sh * (1.0 - a)
    ratio_a = np.divide(a, out_a, out=np.zeros_like(a), where=out_a > 1e-6)
    rgba = np.empty(a.shape + (4,), np.uint8)
    for i, c in enumerate(INK):
        rgba[:, :, i] = np.clip(c * ratio_a + 0.5, 0, 255)
    rgba[:, :, 3] = np.clip(out_a * 255.0 + 0.5, 0, 255)
    cap_actual = size * ratio
    baseline = baseline_pct / 100.0 * H if centre_pct is None else centre_pct / 100.0 * H + cap_actual / 2.0
    left = x_pct / 100.0 * W - (width / 2.0 if align == "center" else 0.0)
    return vfx.Layer(rgba, int(round(left)) - pad_x, int(round(baseline)) - base_y)


def ink_layer(ctx, text, kind, cap_pct, tracking_pct=0.0, *, baseline_pct=None, centre_pct=None, x_pct=50.0, align="center",
              max_w_pct=MAX_LINE_W_PCT, shadow=True, kern=False):
    """Cached one-line text layer, or None when there is nothing to draw. The cap height is `cap_pct` % of the frame height; the line
    is centred (or left aligned) at `x_pct` % of the width and sits with the middle of its capitals at `centre_pct` % of the height
    (or its baseline at `baseline_pct`). `kern` sets a sentence glyph by glyph with its face's pair kerning (off for every older technique). The cache
    key holds every input."""
    if not isinstance(text, str) or not text.strip():
        return None
    key = ("idtext", text, kind, float(cap_pct), float(tracking_pct), baseline_pct, centre_pct, float(x_pct), align, float(max_w_pct), bool(shadow), bool(kern))
    return ctx.layer(key, lambda: _build_ink(ctx.w, ctx.h, text, kind, float(cap_pct), float(tracking_pct), baseline_pct, centre_pct,
                                             float(x_pct), align, float(max_w_pct), bool(shadow), bool(kern)))


def _measure_glyph_line(text, kind, cap_pct, tracking_pct, max_w_pct, W, H, *, kern=True):
    """Shared glyph measurement for raking-sweep ink layers (fits within `max_w_pct` without wrapping)."""
    ratio = vfx.cap_ratio(kind)
    size = max(6, int(round(cap_pct / 100.0 * H / ratio)))
    max_w = max_w_pct / 100.0 * W

    def measure(sz):
        ft = vfx.font(kind, sz)
        trk = tracking_pct / 100.0 * sz
        if trk > 0:
            adv = [ft.getlength(c) for c in text]
            return ft, trk, adv, sum(adv) + trk * (len(text) - 1)
        if kern:
            k = _kerning(kind)
            if k is not None:
                adv = [ft.getlength(c) for c in text]
                for i in range(len(text) - 1):
                    adv[i] += k.pair(text[i], text[i + 1]) * sz / k.upem
                return ft, 0.0, adv, sum(adv)
        return ft, 0.0, None, ft.getlength(text)

    ft, trk, adv, width = measure(size)
    if width > max_w > 0:
        size = max(6, min(size - 1, int(size * max_w / width)))
        ft, trk, adv, width = measure(size)
        while width > max_w and size > 6:
            size -= 1
            ft, trk, adv, width = measure(size)
    return ft, trk, adv, width, size, ratio


def _two_tier_glyph_shadow(a: np.ndarray, W: int) -> np.ndarray:
    """Two-tier dark glyph halo + soft drop shadow keeping #F1EADB legible over bright (~240/255) paintings without any box or strip."""
    s_tight = max(1.0, 0.0014 * W)
    s_wide = max(2.0, 0.0042 * W)
    dy = max(1, int(round(0.0011 * W)))
    a_drop = np.zeros_like(a)
    a_drop[dy:, :] = a[:-dy, :]
    sh1 = cv2.GaussianBlur(a, (0, 0), s_tight) * 0.78
    sh2 = cv2.GaussianBlur(a_drop, (0, 0), s_wide) * 0.62
    return np.clip(1.0 - (1.0 - sh1) * (1.0 - sh2), 0.0, 0.90).astype(np.float32)


def _build_raking_ink(W, H, text, kind, cap_pct, tracking_pct, centre_pct, x_pct, max_w_pct, shadow, kern=True):
    """Build a static one-line raking title/subtitle `vfx.Layer` with boosted glyph-hugging optical contrast."""
    ft, trk, adv, width, size, ratio = _measure_glyph_line(text, kind, cap_pct, tracking_pct, max_w_pct, W, H, kern=kern)
    asc, desc = ft.getmetrics()
    sigma = max(2.0, 0.0042 * W)
    m = int(4 * sigma) + 4
    pad_x = m + int(size * 0.15)
    img = Image.new("L", (int(math.ceil(width)) + 2 * pad_x, asc + desc + 2 * m), 0)
    d = ImageDraw.Draw(img)
    base_y = m + asc
    if adv is None:
        d.text((pad_x, base_y), text, font=ft, fill=255, anchor="ls")
    else:
        x = float(pad_x)
        for c, a in zip(text, adv):
            d.text((x, base_y), c, font=ft, fill=255, anchor="ls")
            x += a + trk
    a = np.asarray(img, np.float32) / 255.0
    sh = _two_tier_glyph_shadow(a, W) if shadow else np.zeros_like(a)
    out_a = a + sh * (1.0 - a)
    ratio_a = np.divide(a, out_a, out=np.zeros_like(a), where=out_a > 1e-6)
    rgba = np.empty(a.shape + (4,), np.uint8)
    for i, c in enumerate(INK):
        rgba[:, :, i] = np.clip(c * ratio_a + 0.5, 0, 255)
    rgba[:, :, 3] = np.clip(out_a * 255.0 + 0.5, 0, 255)
    cap_actual = size * ratio
    baseline = centre_pct / 100.0 * H + cap_actual / 2.0
    left = x_pct / 100.0 * W - width / 2.0
    return vfx.Layer(rgba, int(round(left)) - pad_x, int(round(baseline)) - base_y)


def _raking_ink_layer(ctx, text, kind, cap_pct, tracking_pct, centre_pct, x_pct=50.0, max_w_pct=TITLE_MAX_W_PCT, shadow=True, kern=True):
    if not isinstance(text, str) or not text.strip():
        return None
    key = ("idraketext", text, kind, float(cap_pct), float(tracking_pct), float(centre_pct), float(x_pct), float(max_w_pct), bool(shadow), bool(kern))
    return ctx.layer(key, lambda: _build_raking_ink(ctx.w, ctx.h, text, kind, float(cap_pct), float(tracking_pct),
                                                    float(centre_pct), float(x_pct), float(max_w_pct), bool(shadow), bool(kern)))


def _asset_texts(context):
    a = context.get("asset") or {}
    title = context.get("title") or a.get("title")
    artist, year = context.get("artist") or a.get("artist"), context.get("year") or a.get("year")
    return title, artist, (str(year) if year else None)


def _camera_default(context):
    """Whole picture at the fitted size with a 3 % push over the element (the applier writes its own keys; this is for a hand pick)."""
    a = context.get("asset") or {}
    if not a.get("w") or not a.get("h"):
        return None
    w, h = float(a["w"]), float(a["h"])
    cur = context.get("camera") or {}
    z0 = float(cur.get("zoom") or fit_zoom(h))
    cx, cy = float(cur.get("cx", w / 2.0)), float(cur.get("cy", h / 2.0))
    key = lambda rel, z: {"at": {"rel": rel}, "cx": round(cx, 2), "cy": round(cy, 2), "zoom": round(z, 5), "ease": "linear"}
    return [key(0.0, z0), key(1.0, z0 * 1.03)]


# ----------------------------------------------------------------------------- overlays
@technique("ID-OPEN-01", "overlay")
class OpenRaking(OverlayRenderer):
    """The opening, style raking: black, the picture rises to `floor`, a band of light travels across and leaves the picture at `wake`
    behind it, then the whole picture rises to 100 %. The camera of the shot is not touched; this overlay only changes light.

    Nominal timeline (s from the overlay start): black until black_s, rise to `floor` over rise_s, band from sweep_start_s for sweep_s,
    release over release_s from the end of the sweep. Nominal length = sweep_start_s + sweep_s + release_s (9.0 by default); a shorter
    overlay scales every time. Before the overlay starts and after it ends the picture is plain."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.band = Band(ctx.w, ctx.h, p["band_width_pct"], p["feather"], p["angle_deg"], p["direction"])
        self.nominal = float(p["sweep_start_s"]) + float(p["sweep_s"]) + float(p["release_s"])
        self.k = time_scale(self.t1 - self.t0, self.nominal)

    def state(self, t):
        """(nominal time, sweep progress q, brightness ahead of the band, brightness behind it) at video time t."""
        p = self.p
        tau = (t - self.t0) / self.k
        rs = float(p["sweep_start_s"]) + float(p["sweep_s"])
        rel = ss01(tau, rs, float(p["release_s"]))
        floor, wake = float(p["floor"]), float(p["wake"])
        ahead = floor * ss01(tau, float(p["black_s"]), float(p["rise_s"])) + (1.0 - floor) * rel
        behind = max(wake + (1.0 - wake) * rel, ahead)
        return tau, ramp01(tau, float(p["sweep_start_s"]), float(p["sweep_s"])), ahead, behind

    def apply(self, f, t, view):
        if t < self.t0 - 1e-9:
            return f
        _, q, ahead, behind = self.state(t)
        return self.band.light(f, q, ahead, behind, float(self.p["warm"]))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


@technique("ID-LABEL-01", "overlay")
class LabelPlain(OverlayRenderer):
    """Two-line artwork label bottom left, no strip: the title in italic, then "Artist, year". The second line's baseline is at
    `bottom_pct`, the first line's baseline two cap heights of the second line above it. Fades in over fade_in_s from the overlay
    start and out over fade_out_s ending at the overlay end (nominal length `nominal_s`, 4.5 s: a shorter overlay scales the fades)."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.k = time_scale(self.t1 - self.t0, float(p["nominal_s"]))
        base2 = float(p["bottom_pct"])
        base1 = base2 - 2.0 * float(p["second_cap_pct"])
        room = 100.0 - float(p["x_pct"]) - 4.0
        common = dict(x_pct=float(p["x_pct"]), align="left", max_w_pct=max(room, 10.0), shadow=bool(p["shadow"]))
        self.layers = [l for l in (
            ink_layer(ctx, p["title"], "eb_italic", float(p["title_cap_pct"]), 0.0, baseline_pct=base1, **common),
            ink_layer(ctx, p["artist_year"], "eb_regular", float(p["second_cap_pct"]), 0.0, baseline_pct=base2, **common)) if l is not None]

    def envelope(self, t):
        p = self.p
        k = self.k
        return vfx.window(t, self.t0, self.t1, float(p["fade_in_s"]) * k, float(p["fade_out_s"]) * k)

    def apply(self, f, t, view):
        e = self.envelope(t)
        for layer in self.layers:
            f = composite_layer_masked(f, layer, None, e)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        title, artist, year = _asset_texts(context)
        d["title"] = title or d["title"]
        ay = context.get("artist_year") or ", ".join(x for x in (artist, year) if x)
        d["artist_year"] = ay or d["artist_year"]
        return d


@technique("ID-OPEN-02", "overlay")
class OpenDim(OverlayRenderer):
    """The opening, style dim: the frame dims to `dim` over ramp_in_s, the title (italic) fades in and ends its fade when the dim ramp
    ends, `sub_delay_s` after the title starts "ARTIST · YEAR" (capitals, tracked) fades in; both text lines and the brightness
    return over the last ramp_out_s of the overlay. Nominal length `nominal_s` (5.0 s); a shorter overlay scales every time."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.k = time_scale(self.t1 - self.t0, float(p["nominal_s"]))
        self.dur = (self.t1 - self.t0) / self.k                  # the overlay's length in nominal seconds
        self.title = ink_layer(ctx, p["title"], "eb_italic", float(p["title_cap_pct"]), 0.0, centre_pct=float(p["title_y_pct"]))
        sub = p["sub"].upper() if isinstance(p["sub"], str) else ""
        self.sub = ink_layer(ctx, sub, "eb_regular", float(p["sub_cap_pct"]), float(p["sub_tracking_pct"]), centre_pct=float(p["sub_y_pct"]))

    def state(self, t):
        """(nominal time, brightness gain, title opacity, sub-line opacity) at video time t."""
        p = self.p
        tau = (t - self.t0) / self.k
        out_at, d_out = self.dur - float(p["ramp_out_s"]), float(p["ramp_out_s"])
        dim = 1.0 - (1.0 - float(p["dim"])) * ss01(tau, 0.0, float(p["ramp_in_s"])) * (1.0 - ss01(tau, out_at, d_out))
        t_start = max(0.0, float(p["ramp_in_s"]) - float(p["title_fade_in_s"]))
        e_title = fade_window(tau, t_start, float(p["title_fade_in_s"]), out_at, d_out)
        e_sub = float(p["sub_opacity"]) * fade_window(tau, t_start + float(p["sub_delay_s"]), float(p["sub_fade_in_s"]), out_at, d_out)
        return tau, dim, e_title, e_sub

    def apply(self, f, t, view):
        if t < self.t0 - 1e-9:
            return f
        _, dim, e_title, e_sub = self.state(t)
        f = vfx.gain_in_place(f, dim)
        if self.title is not None:
            f = composite_layer_masked(f, self.title, None, e_title)
        if self.sub is not None:
            f = composite_layer_masked(f, self.sub, None, e_sub)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        title, artist, year = _asset_texts(context)
        d["title"] = title or d["title"]
        sub = " · ".join(x for x in (artist, year) if x)
        d["sub"] = sub or d["sub"]
        return d


# ----------------------------------------------------------------------------- base techniques (the picture is CAM-01's)
class _IdBase(MatteShot):
    """The picture of CAM-01 (same `camera` keys, same slot `image`, same `view()`), then light and text."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.nominal = self.nominal_s()
        self.k = time_scale(self.t1 - self.t0, self.nominal)

    def nominal_s(self):
        return float(self.p["nominal_s"])

    def render(self, t):
        return self.finish(super().render(t), t)

    def finish(self, f, t):
        raise NotImplementedError

    def tau(self, t):
        return (t - self.t0) / self.k

    @classmethod
    def _defaults(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        cam = _camera_default(context)
        if cam is not None:
            d["camera"] = cam
        return d


class _BandBase(_IdBase):
    """Base technique whose light and text are driven by a band."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.band = Band(ctx.w, ctx.h, p["band_width_pct"], p["feather"], p["angle_deg"], p["direction"])

    def finish(self, f, t):
        _, q, ahead, behind, e_text, layer = self.state(t)
        f = self.band.light(f, q, ahead, behind, float(self.p["warm"]))
        if layer is not None and q > 0.0 and e_text > 0.0:
            composite_layer_masked(f, layer, lambda x0, y0, x1, y1: self.band.reveal_box(q, x0, y0, x1, y1), e_text)
        return f


@technique("ID-BRAND-01", "base")
class BrandRaking(_BandBase):
    """The channel name, style raking (its own shot, nominal 5.0 s, hard cut at the end): the picture dims from 100 % to `floor` over
    dim_s, a band sweeps from sweep_delay_s for sweep_s, the name (capitals, tracked) is revealed along the band's path and stays,
    the picture behind the band settles at `wake`. After the sweep the shot holds that state until its end."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        text = p["text"].upper() if isinstance(p["text"], str) else ""
        self.layer = ink_layer(ctx, text, "eb_medium", float(p["cap_pct"]), float(p["tracking_pct"]), centre_pct=float(p["y_pct"]))

    def state(self, t):
        """(nominal time, sweep progress q, brightness ahead of the band, behind it, text opacity, text layer)."""
        p = self.p
        tau = self.tau(t)
        ahead = 1.0 - (1.0 - float(p["floor"])) * ss01(tau, 0.0, float(p["dim_s"]))
        return tau, ramp01(tau, float(p["sweep_delay_s"]), float(p["sweep_s"])), ahead, max(float(p["wake"]), ahead), 1.0, self.layer

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        name = bundle.sv("identity", "channel_name", None)
        if isinstance(name, str) and name.strip():
            d["text"] = name
        return d


@technique("ID-MARK-01", "base")
class MarkRaking(_BandBase):
    """The chapter mark, style raking (its own shot, nominal 3.2 s): the first picture of the chapter at `floor`, a band sweeps from
    sweep_delay_s for sweep_s and writes the line "N. Title", the picture behind it is at `wake`; from release_at_s the picture rises
    to 100 % over release_s and the text fades out over text_fade_out_s. Nominal length = release_at_s + release_s."""

    def nominal_s(self):
        return float(self.p["release_at_s"]) + float(self.p["release_s"])

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.layer = ink_layer(ctx, p["title"], "eb_regular", float(p["cap_pct"]), 0.0, centre_pct=float(p["y_pct"]))

    def state(self, t):
        p = self.p
        tau = self.tau(t)
        rel = ss01(tau, float(p["release_at_s"]), float(p["release_s"]))
        floor, wake = float(p["floor"]), float(p["wake"])
        ahead = floor + (1.0 - floor) * rel
        behind = max(wake + (1.0 - wake) * rel, ahead)
        e_text = 1.0 - ramp01(tau, float(p["release_at_s"]), float(p["text_fade_out_s"]))
        return tau, ramp01(tau, float(p["sweep_delay_s"]), float(p["sweep_s"])), ahead, behind, e_text, self.layer

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        txt = context.get("title") or context.get("text")
        if isinstance(txt, str) and txt.strip():
            d["title"] = txt
        return d


@technique("ID-BRAND-02", "base")
class BrandDim(_IdBase):
    """The channel name, style dim (its own shot, nominal 4.0 s, hard cut at the end): the picture dims to `dim` over ramp_in_s, the name
    fades in over fade_in_s from text_in_delay_s, holds, and fades out over the last fade_out_s of the shot."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        text = p["text"].upper() if isinstance(p["text"], str) else ""
        self.layer = ink_layer(ctx, text, "eb_medium", float(p["cap_pct"]), float(p["tracking_pct"]), centre_pct=float(p["y_pct"]))
        self.dur = (self.t1 - self.t0) / self.k

    def state(self, t):
        """(nominal time, brightness gain, text opacity)."""
        p = self.p
        tau = self.tau(t)
        dim = 1.0 - (1.0 - float(p["dim"])) * ss01(tau, 0.0, float(p["ramp_in_s"]))
        e = fade_window(tau, float(p["text_in_delay_s"]), float(p["fade_in_s"]), self.dur - float(p["fade_out_s"]), float(p["fade_out_s"]))
        return tau, dim, e

    def finish(self, f, t):
        _, dim, e = self.state(t)
        f = vfx.gain_in_place(f, dim)
        return composite_layer_masked(f, self.layer, None, e) if self.layer is not None else f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        name = bundle.sv("identity", "channel_name", None)
        if isinstance(name, str) and name.strip():
            d["text"] = name
        return d


@technique("ID-MARK-02", "base")
class MarkDim(_IdBase):
    """The chapter mark, style dim (its own shot, nominal 3.0 s, normally entered by a 0.75 s dissolve): the picture dims to `dim` over
    ramp_in_s; "N. Title" fades in over text_fade_in_s from text_in_delay_s; from text_out_at_s the text fades out over text_fade_out_s
    and the picture returns to 100 % over release_s. Nominal length = text_out_at_s + release_s."""

    def nominal_s(self):
        return float(self.p["text_out_at_s"]) + float(self.p["release_s"])

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.layer = ink_layer(ctx, p["title"], "eb_regular", float(p["cap_pct"]), 0.0, centre_pct=float(p["y_pct"]))

    def state(self, t):
        p = self.p
        tau = self.tau(t)
        dim = 1.0 - (1.0 - float(p["dim"])) * ss01(tau, 0.0, float(p["ramp_in_s"])) * (1.0 - ss01(tau, float(p["text_out_at_s"]), float(p["release_s"])))
        e = fade_window(tau, float(p["text_in_delay_s"]), float(p["text_fade_in_s"]), float(p["text_out_at_s"]), float(p["text_fade_out_s"]))
        return tau, dim, e

    def finish(self, f, t):
        _, dim, e = self.state(t)
        f = vfx.gain_in_place(f, dim)
        return composite_layer_masked(f, self.layer, None, e) if self.layer is not None else f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        txt = context.get("title") or context.get("text")
        if isinstance(txt, str) and txt.strip():
            d["title"] = txt
        return d


# ----------------------------------------------------------------------------- ID-BRAND-03: the channel name, then the video's title
class BeatState(NamedTuple):
    """The state of the ID-BRAND-03 beat at one instant (every time in nominal seconds)."""
    tau: float            # nominal time from the start of the shot
    q_name: float         # progress 0..1 of the first sweep (writes the channel name)
    q_title: float        # progress 0..1 of the second sweep (writes the title and the small line); 0 when the beat has no second sweep
    q_light: float        # progress of the band that is lighting the picture now (the first sweep, then the second)
    ahead: float          # brightness of the picture ahead of that band
    behind: float         # brightness of the picture behind it


@technique("ID-BRAND-03", "base")
class BrandTitle(_BandBase):
    """The channel name, then the video's title (its own shot, nominal 9.1 s, hard cut at the end). Style raking.

    Nominal timeline (s from the start of the shot): the picture dims from 100 % to `floor` over dim_s; from sweep_delay_s a band crosses the
    frame for sweep_s and writes the channel name (capitals, tracked) along its path, the picture behind the band sits at `wake`; for
    name_hold_s nothing moves; then the band crosses a second time, in the same direction, for title_sweep_s and writes the title (italic, as
    given) and, under it, the small line (capitals, tracked); the name stays and does not move, and the picture stays at `wake` before and
    behind this second band; for title_hold_s everything is held until the shot ends.

    Nominal length = sweep_delay_s + sweep_s + name_hold_s + title_sweep_s + title_hold_s. With no `title` and no `subtitle` there is no
    second sweep: nominal length = sweep_delay_s + sweep_s + name_hold_s and the name sits at y_alone_pct instead of y_pct. With only one of
    the two lines the second sweep writes that line, at its own place (title_y_pct or sub_y_pct). A shorter shot scales every time; a longer
    one keeps the nominal times and holds the last state. A line wider than TITLE_MAX_W_PCT of the frame is made smaller until it fits."""

    @staticmethod
    def _line(p, name):
        v = p.get(name)
        return v.strip() if isinstance(v, str) else ""

    def nominal_s(self):
        p = self.p
        n = float(p["sweep_delay_s"]) + float(p["sweep_s"]) + float(p["name_hold_s"])
        if self._line(p, "title") or self._line(p, "subtitle"):
            n += float(p["title_sweep_s"]) + float(p["title_hold_s"])
        return n

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        title, sub = self._line(p, "title"), self._line(p, "subtitle").upper()
        self.has_lines = bool(title or sub)
        self.t_name = float(p["sweep_delay_s"])                                                      # nominal start of the first sweep
        self.t_title = self.t_name + float(p["sweep_s"]) + float(p["name_hold_s"])                   # nominal start of the second sweep
        y_name = float(p["y_pct"]) if self.has_lines else float(p["y_alone_pct"])
        name = p["text"].upper() if isinstance(p["text"], str) else ""
        self.name_layer = ink_layer(ctx, name, "eb_medium", float(p["cap_pct"]), float(p["tracking_pct"]), centre_pct=y_name, shadow=bool(p["shadow"]))
        self.title_layer = ink_layer(ctx, title, "eb_italic", float(p["title_cap_pct"]), 0.0, centre_pct=float(p["title_y_pct"]),
                                     max_w_pct=TITLE_MAX_W_PCT, shadow=bool(p["shadow"]), kern=True)
        self.sub_layer = ink_layer(ctx, sub, "eb_regular", float(p["sub_cap_pct"]), float(p["sub_tracking_pct"]), centre_pct=float(p["sub_y_pct"]),
                                   max_w_pct=TITLE_MAX_W_PCT, shadow=bool(p["shadow"]))

    def state(self, t):
        """The BeatState at video time t. Light: the picture dims, the first band leaves it at `wake` behind it, and during the second
        sweep it sits at `wake` on both sides of the band (the band is the only light that moves)."""
        p = self.p
        tau = self.tau(t)
        ahead = 1.0 - (1.0 - float(p["floor"])) * ss01(tau, 0.0, float(p["dim_s"]))
        wake = max(float(p["wake"]), ahead)
        q_name = ramp01(tau, self.t_name, float(p["sweep_s"]))
        q_title = ramp01(tau, self.t_title, float(p["title_sweep_s"])) if self.has_lines else 0.0
        if self.has_lines and tau >= self.t_title:
            return BeatState(tau, q_name, q_title, q_title, wake, wake)
        return BeatState(tau, q_name, q_title, q_name, ahead, wake)

    def _write(self, f, layer, q):
        """Draw a line of text revealed by the band at progress q (nothing before the band starts, all of it once the band has left)."""
        if layer is None or q <= 0.0:
            return
        mask = None if q >= 1.0 else (lambda x0, y0, x1, y1: self.band.reveal_box(q, x0, y0, x1, y1))
        composite_layer_masked(f, layer, mask, 1.0)

    def finish(self, f, t):
        s = self.state(t)
        f = self.band.light(f, s.q_light, s.ahead, s.behind, float(self.p["warm"]))
        self._write(f, self.name_layer, s.q_name)
        self._write(f, self.title_layer, s.q_title)
        self._write(f, self.sub_layer, s.q_title)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        name = bundle.sv("identity", "channel_name", None)
        if isinstance(name, str) and name.strip():
            d["text"] = name
        return d


# ----------------------------------------------------------------------------- ID-BRAND-04: the raking light sweep (variants A, B, C)
def _ss_sine(p):
    """Smooth 0 -> 1 sinusoidal ease."""
    p = min(max(float(p), 0.0), 1.0)
    return 0.5 * (1.0 - math.cos(math.pi * p))


def _relief_gradients(ctx, key, img, level_idx):
    """Cached normalized height-map gradients (H_lv x W_lv x 2, float32) from the painting's own luminance pyramid.

    Two-scale difference-of-Gaussians height map suppresses JPEG/sensor grain while extracting physical paint ridges,
    brushstrokes, drapery folds and cracks. Returns zeros cleanly on flat synthetic images.
    """
    path = ctx.asset_path(key)
    try:
        mt = os.stat(path).st_mtime_ns
    except OSError:
        mt = id(img)

    def build():
        lv = img.levels[level_idx]
        bgr = lv.astype(np.float32) * (1.0 / 255.0)
        lum = 0.0722 * bgr[:, :, 0] + 0.7152 * bgr[:, :, 1] + 0.2126 * bgr[:, :, 2]
        with vfx.unlimited():
            b0 = cv2.GaussianBlur(lum, (0, 0), 0.9, borderType=cv2.BORDER_REPLICATE)
            b1 = cv2.GaussianBlur(lum, (0, 0), 2.8, borderType=cv2.BORDER_REPLICATE)
            b2 = cv2.GaussianBlur(lum, (0, 0), 9.5, borderType=cv2.BORDER_REPLICATE)
            hmap = 0.62 * (b0 - b1) + 0.38 * (b1 - b2)
            gx = cv2.Scharr(hmap, cv2.CV_32F, 1, 0, borderType=cv2.BORDER_REPLICATE)
            gy = cv2.Scharr(hmap, cv2.CV_32F, 0, 1, borderType=cv2.BORDER_REPLICATE)
        mag = np.hypot(gx, gy)
        scale = float(np.percentile(mag, 90))
        if scale < 1e-4:
            return np.zeros((lv.shape[0], lv.shape[1], 2), np.float32)
        atten = (1.0 / scale) / (1.0 + 0.25 * (mag / scale))
        return np.dstack([gx * atten, gy * atten]).astype(np.float32)

    return ctx.cached(("id_relief_grad", path, mt, int(level_idx)), build)


def _warp_relief_roi(img, grad2, cx, cy, zoom, ow, oh, ix0, iy0, ix1, iy1, paint_rect=None):
    """Warp the cached gradient map into the painting's screen ROI and return (gx, gy, paint_mask)."""
    k = int(round(math.log2(1.0 / zoom))) if zoom < 1.0 else 0
    k = max(0, min(k, len(img.levels) - 1))
    s = zoom * (2 ** k)
    sx = cx / (2 ** k)
    sy = cy / (2 ** k)
    rw, rh = ix1 - ix0, iy1 - iy0
    m_roi = np.array([[s, 0.0, ow / 2.0 - s * sx - ix0], [0.0, s, oh / 2.0 - s * sy - iy0]], np.float64)
    warped = cv2.warpAffine(grad2, m_roi, (rw, rh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0.0, 0.0))
    x0, y0, x1, y1 = paint_rect if paint_rect is not None else img.rect(cx, cy, zoom, ow, oh)
    xs = np.arange(ix0, ix1, dtype=np.float32) + 0.5
    ys = np.arange(iy0, iy1, dtype=np.float32) + 0.5
    # 3-px inward feather inside the painting border prevents any bright rim halo at the frame edge.
    ax = np.clip((np.minimum(xs - x0, x1 - xs) - 1.5) / 3.0, 0.0, 1.0)
    ay = np.clip((np.minimum(ys - y0, y1 - ys) - 1.5) / 3.0, 0.0, 1.0)
    paint_mask = (ay[:, None] * ax[None, :]).astype(np.float32)
    return warped[:, :, 0], warped[:, :, 1], paint_mask


def _tilted_pool(xs, ys, cx, cy, rx, ry, angle_deg, feather):
    """Soft elliptical lamp pool tilted by `angle_deg`, evaluated on 1-D coordinate vectors (xs, ys)."""
    a = math.radians(float(angle_deg))
    ca, sa = math.cos(a), math.sin(a)
    dx = xs[None, :] - float(cx)
    dy = ys[:, None] - float(cy)
    xr = dx * ca + dy * sa
    yr = -dx * sa + dy * ca
    d = np.sqrt((xr / max(float(rx), 1.0)) ** 2 + (yr / max(float(ry), 1.0)) ** 2)
    fth = min(max(float(feather), 0.05), 0.95)
    return (1.0 - vfx.smoothstep((d - (1.0 - fth)) / fth)).astype(np.float32)


class _CutInk:
    """Pre-rendered text layer with contour normals for directional cut-letter bevel highlights."""

    def __init__(self, x0, y0, a, sh, ex, ey):
        self.x0, self.y0 = int(x0), int(y0)
        self.a = a
        self.sh = sh
        self.ex = ex
        self.ey = ey
        self.rgb = np.empty(a.shape + (3,), np.float32)
        self.rgb[:, :, 0] = INK[2]
        self.rgb[:, :, 1] = INK[1]
        self.rgb[:, :, 2] = INK[0]


def _build_cut_ink(W, H, text, kind, cap_pct, tracking_pct, centre_pct, x_pct, max_w_pct, shadow):
    ratio = vfx.cap_ratio(kind)
    size = max(6, int(round(cap_pct / 100.0 * H / ratio)))
    max_w = max_w_pct / 100.0 * W

    def measure(sz):
        ft = vfx.font(kind, sz)
        trk = tracking_pct / 100.0 * sz
        if trk > 0:
            adv = [ft.getlength(c) for c in text]
            return ft, trk, adv, sum(adv) + trk * (len(text) - 1)
        return ft, 0.0, None, ft.getlength(text)

    ft, trk, adv, width = measure(size)
    if width > max_w > 0:
        size = max(6, min(size - 1, int(size * max_w / width)))
        ft, trk, adv, width = measure(size)
        while width > max_w and size > 6:
            size -= 1
            ft, trk, adv, width = measure(size)
    asc, desc = ft.getmetrics()
    sigma = max(2.0, 0.0042 * W)
    m = int(4 * sigma) + 4
    pad_x = m + int(size * 0.15)
    img = Image.new("L", (int(math.ceil(width)) + 2 * pad_x, asc + desc + 2 * m), 0)
    d = ImageDraw.Draw(img)
    base_y = m + asc
    if adv is None:
        d.text((pad_x, base_y), text, font=ft, fill=255, anchor="ls")
    else:
        x = float(pad_x)
        for c, a in zip(text, adv):
            d.text((x, base_y), c, font=ft, fill=255, anchor="ls")
            x += a + trk
    a = np.asarray(img, np.float32) / 255.0
    sh = _two_tier_glyph_shadow(a, W) if shadow else np.zeros_like(a)
    # Smooth contour normals pointing outward from letterforms, used for crisp directional edge catch.
    soft_a = cv2.GaussianBlur(a, (0, 0), 0.65)
    gx = cv2.Sobel(soft_a, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(soft_a, cv2.CV_32F, 0, 1, ksize=3)
    gn = np.hypot(gx, gy)
    ex = np.divide(gx, np.maximum(gn, 1e-4)) * np.clip(gn * 1.4, 0.0, 1.0)
    ey = np.divide(gy, np.maximum(gn, 1e-4)) * np.clip(gn * 1.4, 0.0, 1.0)
    cap_actual = size * ratio
    baseline = centre_pct / 100.0 * H + cap_actual / 2.0
    left = x_pct / 100.0 * W - width / 2.0
    return _CutInk(int(round(left)) - pad_x, int(round(baseline)) - base_y, a, sh, ex, ey)


def _cut_ink_layer(ctx, text, kind, cap_pct, tracking_pct, centre_pct, x_pct=50.0, max_w_pct=MAX_LINE_W_PCT, shadow=True):
    if not isinstance(text, str) or not text.strip():
        return None
    key = ("idcutink", text, kind, float(cap_pct), float(tracking_pct), float(centre_pct), float(x_pct), float(max_w_pct), bool(shadow))
    return ctx.cached(key, lambda: _build_cut_ink(ctx.w, ctx.h, text, kind, float(cap_pct), float(tracking_pct),
                                                   float(centre_pct), float(x_pct), float(max_w_pct), bool(shadow)),
                      sizeof=lambda c: c.a.nbytes * 6 + 200)


def _composite_cut_ink(frame, cut, reveal_fn, beam_fn, lx, ly, face_env=1.0, bevel_env=1.0):
    """Draw static cut letters that catch the moving/grazing lamp along their leading contours."""
    if cut is None or (face_env <= 0.001 and bevel_env <= 0.001):
        return frame
    lh, lw = cut.a.shape
    fx0, fy0 = max(cut.x0, 0), max(cut.y0, 0)
    fx1, fy1 = min(cut.x0 + lw, frame.shape[1]), min(cut.y0 + lh, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    sx0, sy0, sx1, sy1 = fx0 - cut.x0, fy0 - cut.y0, fx1 - cut.x0, fy1 - cut.y0
    rev = reveal_fn(fx0, fy0, fx1, fy1) if reveal_fn is not None else np.ones((fy1 - fy0, fx1 - fx0), np.float32)
    cols = np.nonzero(rev.max(axis=0) > 0.001)[0]
    if not cols.size:
        return frame
    c0, c1 = int(cols[0]), int(cols[-1]) + 1
    fx0_c, fx1_c = fx0 + c0, fx0 + c1
    sx0_c, sx1_c = sx0 + c0, sx0 + c1
    rev = rev[:, c0:c1]
    a = cut.a[sy0:sy1, sx0_c:sx1_c]
    sh = cut.sh[sy0:sy1, sx0_c:sx1_c]
    ex = cut.ex[sy0:sy1, sx0_c:sx1_c]
    ey = cut.ey[sy0:sy1, sx0_c:sx1_c]
    bm = beam_fn(fx0_c, fy0, fx1_c, fy1) if beam_fn is not None else np.ones_like(rev)

    reg = frame[fy0:fy1, fx0_c:fx1_c]
    sh_a = (sh * rev * max(face_env, bevel_env * 0.45) * (1.0 - a * face_env))[:, :, None]
    reg *= (1.0 - sh_a)

    # Directional bevel along stroke contours facing the lamp.
    bevel = -(ex * float(lx) + ey * float(ly))
    edge_band = np.clip(np.hypot(ex, ey), 0.0, 1.0)
    bw = bevel_env * (0.25 + 0.75 * bm)
    catch = np.maximum(bevel, 0.0) * (72.0 * bw)
    carve = np.maximum(-bevel, 0.0) * (36.0 * bw)

    ink_bgr = np.empty((fy1 - fy0, fx1_c - fx0_c, 3), np.float32)
    ink_bgr[:, :, 0] = np.clip(INK[2] + bm * 6.0 + catch * 0.72 - carve, 0.0, 255.0)
    ink_bgr[:, :, 1] = np.clip(INK[1] + bm * 10.0 + catch * 0.90 - carve, 0.0, 255.0)
    ink_bgr[:, :, 2] = np.clip(INK[0] + bm * 11.0 + catch * 1.00 - carve, 0.0, 255.0)

    directional = np.clip(0.25 + 0.75 * np.maximum(bevel, 0.0), 0.0, 1.0)
    alpha = np.clip(a * face_env + edge_band * directional * (1.0 - a) * 0.84 * bevel_env, 0.0, 1.0) * rev
    alpha3 = alpha[:, :, None]
    reg[...] = reg * (1.0 - alpha3) + ink_bgr * alpha3
    return frame


def _composite_slide_up(frame, layer, progress, fade_out=1.0, travel_px=22.0):
    """Slide a museum-label layer cleanly up into its resting baseline, clipping softly below the line."""
    if layer is None or progress <= 0.001 or fade_out <= 0.001:
        return frame
    p = min(max(float(progress), 0.0), 1.0)
    u = 1.0 - (1.0 - p) ** 3
    dy = int(round((1.0 - u) * travel_px))
    env = min(1.0, p / 0.72) * float(fade_out)
    lh, lw = layer.a.shape[:2]
    x0, y0 = layer.x0, layer.y0 + dy
    fx0, fy0 = max(x0, 0), max(y0, 0)
    fx1, fy1 = min(x0 + lw, frame.shape[1]), min(y0 + lh, frame.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return frame
    # Soft baseline clip at the resting bottom of the layer so the label emerges cleanly out of nothing.
    y_rest_bottom = layer.y0 + lh - int(round(4.0 * SHADOW_SIGMA * frame.shape[1])) + 2
    ys = np.arange(fy0, fy1, dtype=np.float32)
    clip_y = np.clip((y_rest_bottom - ys) / 6.0, 0.0, 1.0)[:, None, None]
    sl = (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))
    a = layer.a[sl] * env * clip_y
    reg = frame[fy0:fy1, fx0:fx1]
    reg -= (reg - layer.rgb[sl]) * a
    return frame


REST_MIN_RY_PCT = 12.0   # phone-readable rest-spot vertical radius floor (% H; yields ~11% H visible half-light radius)
REST_MIN_RX_PCT = 10.5   # paired horizontal radius floor (% W; preserves oval lamp pool)


@technique("ID-BRAND-04", "base")
class BrandRakingSweep(_IdBase):
    """The raking light sweep ident (variants A, B, C), acting out a museum lamp examining the painting surface.

    Variant A: one slanted raking band sweeps across the darkened painting, revealing surface relief and catching the
    cut-edge contours of the channel name, then settles onto `region` where the video title fades in and the museum label
    line slides up before the light opens to the plain painting.
    Variant B: a focused slanted lamp beam follows a two-move path (across the upper canvas/name, then pivoting onto
    `region`) under a continuous slow camera push-in; the title wipes in with light and the label slides up before opening.
    Variant C: no sweeping band; a studio lamp's elevation angle opens from extreme grazing (7 deg, strong impasto relief)
    to frontal (90 deg, normal picture), with bevel-first channel name emergence and a soft focus on `region`.
    """

    def nominal_s(self):
        return float(self.p["nominal_s"])

    def _paint_rect_raw(self, view):
        """Painted surface rectangle `(x0, y0, x1, y1)` in canvas px (respects `content_box` when present)."""
        asset = self.ctx.asset(self.key) or {}
        cb = CB.clean(asset.get("content_box"), view.img.w, view.img.h)
        if cb is not None:
            x0, y0 = view.to_screen(cb[0], cb[1])
            x1, y1 = view.to_screen(cb[2], cb[3])
            return (float(x0), float(y0), float(x1), float(y1))
        return tuple(float(v) for v in view.img.rect(view.cx, view.cy, view.z, self.ctx.w, self.ctx.h))

    def _paint_rect_visible(self, view):
        """Painted surface rectangle clipped to the visible canvas `[0, W] x [0, H]`."""
        W, H = float(self.ctx.w), float(self.ctx.h)
        x0, y0, x1, y1 = self._paint_rect_raw(view)
        vx0 = min(max(x0, 0.0), W - 1.0)
        vy0 = min(max(y0, 0.0), H - 1.0)
        vx1 = max(vx0 + 1.0, min(W, x1))
        vy1 = max(vy0 + 1.0, min(H, y1))
        return vx0, vy0, vx1, vy1

    def _resolve_region(self, img):
        reg = self.p.get("region")
        if reg is None or reg == "":
            cb = CB.clean((self.ctx.asset(self.key) or {}).get("content_box"), img.w, img.h)
            if cb is not None:
                return (cb[0] + cb[2]) / 2.0, (cb[1] + cb[3]) / 2.0, 0.11 * (cb[2] - cb[0]), 0.11 * (cb[3] - cb[1])
            return img.w / 2.0, img.h / 2.0, 0.11 * img.w, 0.11 * img.h
        if isinstance(reg, str):
            r = (self.ctx.asset(self.key).get("regions") or {}).get(reg)
            if r is None:
                rx_src, ry_src = self.ctx.point(reg, self.key)
                return rx_src, ry_src, 0.11 * img.w, 0.11 * img.h
            return float(r["x"]), float(r["y"]), float(r.get("rx") or 0.11 * img.w), float(r.get("ry") or 0.11 * img.h)
        return float(reg[0]), float(reg[1]), 0.11 * img.w, 0.11 * img.h

    def _region_screen(self, view):
        rx_src, ry_src, rrx, rry = self._resolve_region(view.img)
        sx, sy = view.to_screen(rx_src, ry_src)
        W, H = self.ctx.w, self.ctx.h
        vx0, vy0, vx1, vy1 = self._paint_rect_visible(view)
        lo_x, hi_x = max(vx0, 0.10 * W), min(vx1, 0.90 * W)
        sx = min(max(sx, lo_x), hi_x) if lo_x <= hi_x else min(max(sx, vx0), vx1)
        lo_y, hi_y = max(vy0, 0.14 * H), min(vy1, 0.86 * H)
        sy = min(max(sy, lo_y), hi_y) if lo_y <= hi_y else min(max(sy, vy0), vy1)
        scale = float(self.p["spot_scale"])
        min_rx = (REST_MIN_RX_PCT / 100.0) * W
        min_ry = (REST_MIN_RY_PCT / 100.0) * H
        srx = min(max(rrx * view.z * 1.45 * scale, min_rx), 0.25 * W)
        sry = min(max(rry * view.z * 1.55 * scale, min_ry), 0.185 * H)
        return sx, sy, srx, sry

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.variant = str(p.get("variant") or "B")
        self.band = Band(ctx.w, ctx.h, p["band_width_pct"], p["feather"], p["angle_deg"], p["direction"])

        # Compute rest-time screen bounding box once so all three texts stay visible (name dimmed) and clear of [r_top, r_bot].
        t_rest = self.t0 + 0.62 * max(self.t1 - self.t0, 0.1)
        v_rest = self.view(t_rest)
        _, ry_rest, _, sry_rest = self._region_screen(v_rest)
        ry_pct = 100.0 * ry_rest / ctx.h
        sry_pct = 100.0 * sry_rest / ctx.h
        r_top = ry_pct - sry_pct
        r_bot = ry_pct + sry_pct
        self.rest_box_pct = (r_top, r_bot)

        self.fade_name_at_rest = False
        if r_top >= 17.5 and r_bot <= 73.0:
            name_y = min(21.0, max(10.5, r_top - 7.8))
            title_y = max(60.0, r_bot + 6.8)
            sub_y = min(87.5, title_y + 8.5)
            title_y = sub_y - 8.5
        elif r_top < 17.5:
            name_y = min(65.0, max(50.0, r_bot + 8.0))
            title_y = name_y + 13.5
            sub_y = title_y + 8.5
        else:
            sub_y = min(72.0, r_top - 5.5)
            title_y = sub_y - 8.5
            name_y = max(10.5, min(21.0, title_y - 12.5))

        self.name_y_pct = name_y
        self.title_y_pct = title_y
        self.sub_y_pct = sub_y
        name = p["text"].upper() if isinstance(p["text"], str) else ""
        title = p["title"].strip() if isinstance(p["title"], str) else ""
        sub = p["subtitle"].strip().upper() if isinstance(p["subtitle"], str) else ""

        self.name_cut = _cut_ink_layer(ctx, name, "eb_medium", float(p["cap_pct"]), float(p["tracking_pct"]),
                                       name_y, shadow=bool(p["shadow"]))
        self.title_layer = _raking_ink_layer(ctx, title, "eb_italic", float(p["title_cap_pct"]), 0.0,
                                             title_y, max_w_pct=TITLE_MAX_W_PCT, shadow=bool(p["shadow"]), kern=True)
        self.sub_layer = _raking_ink_layer(ctx, sub, "eb_regular", float(p["sub_cap_pct"]), float(p["sub_tracking_pct"]),
                                           sub_y, max_w_pct=TITLE_MAX_W_PCT, shadow=bool(p["shadow"]), kern=False)

    def _apply_surface(self, f, view, gain_q, warm_q, rel_q, az_rad, el_rad, matte_gain=None):
        """Apply lamp gain, warm tint, and grazing surface relief inside the painted surface only, keeping the matte neutral."""
        W, H = self.ctx.w, self.ctx.h
        p = self.p
        strength = float(p["relief"])
        gain_full = cv2.resize(gain_q, (W, H), interpolation=cv2.INTER_LINEAR)

        x0, y0, x1, y1 = self._paint_rect_raw(view)
        ix0, ix1 = max(0, int(math.floor(x0)) - 1), min(W, int(math.ceil(x1)) + 1)
        iy0, iy1 = max(0, int(math.floor(y0)) - 1), min(H, int(math.ceil(y1)) + 1)

        if matte_gain is None or (x0 <= 0.0 and y0 <= 0.0 and x1 >= W and y1 >= H):
            f *= gain_full[:, :, None]
            if ix1 <= ix0 or iy1 <= iy0:
                return f
            xs_r = np.arange(ix0, ix1, dtype=np.float32) + 0.5
            ys_r = np.arange(iy0, iy1, dtype=np.float32) + 0.5
            ax_r = np.clip(np.minimum(xs_r - x0, x1 - xs_r), 0.0, 1.0)
            ay_r = np.clip(np.minimum(ys_r - y0, y1 - ys_r), 0.0, 1.0)
            rect_mask = (ay_r[:, None] * ax_r[None, :]).astype(np.float32)
            reg = f[iy0:iy1, ix0:ix1]
            roi_gain = gain_full[iy0:iy1, ix0:ix1]
        else:
            mg = float(matte_gain)
            if ix1 <= ix0 or iy1 <= iy0:
                f *= mg
                return f
            if iy0 > 0:
                f[:iy0, :] *= mg
            if iy1 < H:
                f[iy1:, :] *= mg
            if ix0 > 0:
                f[iy0:iy1, :ix0] *= mg
            if ix1 < W:
                f[iy0:iy1, ix1:] *= mg
            xs_r = np.arange(ix0, ix1, dtype=np.float32) + 0.5
            ys_r = np.arange(iy0, iy1, dtype=np.float32) + 0.5
            ax_r = np.clip(np.minimum(xs_r - x0, x1 - xs_r), 0.0, 1.0)
            ay_r = np.clip(np.minimum(ys_r - y0, y1 - ys_r), 0.0, 1.0)
            rect_mask = (ay_r[:, None] * ax_r[None, :]).astype(np.float32)
            roi_gain = mg + (gain_full[iy0:iy1, ix0:ix1] - mg) * rect_mask
            reg = f[iy0:iy1, ix0:ix1]
            reg *= roi_gain[:, :, None]

        # Warm lamp tint is confined to the painting surface (never turns the surrounding gallery matte brown).
        warm_full = cv2.resize(warm_q, (W, H), interpolation=cv2.INTER_LINEAR)
        a = (warm_full[iy0:iy1, ix0:ix1] * rect_mask)[:, :, None]
        if float(a.max()) > 1e-4:
            reg *= (1.0 - a * vfx._WARM_BGR)
            reg += (255.0 * a) * vfx._WARM_BGR

        if strength <= 1e-4 or float(rel_q.max()) <= 1e-4:
            return f

        k = int(round(math.log2(1.0 / view.z))) if view.z < 1.0 else 0
        k = max(0, min(k, len(view.img.levels) - 1))
        grad2 = _relief_gradients(self.ctx, self.key, view.img, k)
        gx, gy, pmask = _warp_relief_roi(view.img, grad2, view.cx, view.cy, view.z, W, H, ix0, iy0, ix1, iy1, paint_rect=(x0, y0, x1, y1))
        rel_full = cv2.resize(rel_q, (W, H), interpolation=cv2.INTER_LINEAR)
        rw = rel_full[iy0:iy1, ix0:ix1] * pmask

        cot_el = math.cos(el_rad) / max(math.sin(el_rad), 0.27)
        lx, ly = math.cos(az_rad), math.sin(az_rad)
        u = -(gx * lx + gy * ly) * (strength * 0.22 * cot_el)
        pos = np.maximum(u, 0.0)
        neg = np.maximum(-u, 0.0)
        delta = 0.65 * np.tanh(pos / 0.65) - 0.50 * np.tanh(neg / 0.50)
        shade = 1.0 + delta * rw
        reg *= shade[:, :, None]

        crest = np.maximum(pos - 0.28, 0.0)
        sheen = (0.11 * np.tanh(crest / 0.65) * rw)[:, :, None]
        if float(sheen.max()) > 1e-4:
            reg += sheen * roi_gain[:, :, None] * (vfx._WARM_BGR * 255.0)
        return f

    def finish(self, f, t):
        W, H = self.ctx.w, self.ctx.h
        u = min(max(self.tau(t) / max(self.nominal, 0.1), 0.0), 1.0)
        if u >= 0.999:
            return f

        p = self.p
        floor = float(p["floor"])
        wake = float(p["wake"])
        warm = float(p["warm"])
        angle_deg = float(p["angle_deg"])
        feather = float(p["feather"])
        view = self.view(t)
        rx_s, ry_s, srx, sry = self._region_screen(view)

        qres = 4
        gw, gh = W // qres, H // qres
        xs = (np.arange(gw, dtype=np.float32) + 0.5) * qres
        ys = (np.arange(gh, dtype=np.float32) + 0.5) * qres

        if self.variant == "A":
            q_band = _ss_sine(ramp01(u, 0.05, 0.40))
            s = self.band.s_grid(q_band, xs, ys)
            b_band = self.band.profile(s)
            r_band = vfx.smoothstep(-s / self.band.half)
            p_rest = ss01(u, 0.34, 0.16)
            p_open = ss01(u, 0.80, 0.18)

            pool = _tilted_pool(xs, ys, rx_s, ry_s, srx * 1.15, sry * 1.25, angle_deg, 0.55)
            beam = np.maximum(b_band, p_rest * pool)
            bg = floor + (wake - floor) * r_band
            gain_q = bg + (1.0 - bg) * beam
            gain_q = (gain_q + (1.0 - gain_q) * p_open).astype(np.float32)
            warm_q = (warm * beam * (1.0 - p_open)).astype(np.float32)
            rel_q = (np.clip(0.20 * r_band + 0.88 * beam, 0.0, 1.0) * (1.0 - p_open)).astype(np.float32)

            az_rad = math.radians(angle_deg)
            if self.band.sign < 0:
                az_rad += math.pi
            el_deg = 14.0 + 76.0 * p_open
            matte_gain = floor + (1.0 - floor) * p_open
            f = self._apply_surface(f, view, gain_q, warm_q, rel_q, az_rad, math.radians(el_deg), matte_gain=matte_gain)

            name_out = 1.0 - ramp01(u, 0.80, 0.09)
            name_rest = (1.0 - ss01(u, 0.46, 0.10)) if self.fade_name_at_rest else (1.0 - 0.22 * ss01(u, 0.46, 0.10))
            face_env = name_rest * name_out
            if q_band > 0.0 and face_env > 0.001:
                _composite_cut_ink(
                    f, self.name_cut,
                    lambda x0, y0, x1, y1: self.band.reveal_box(q_band, x0, y0, x1, y1),
                    lambda x0, y0, x1, y1: self.band.profile(self.band.s_grid(
                        q_band, np.arange(x0, x1, dtype=np.float32) + 0.5, np.arange(y0, y1, dtype=np.float32) + 0.5)),
                    math.cos(az_rad), math.sin(az_rad), face_env=face_env, bevel_env=face_env,
                )

            txt_out = 1.0 - ramp01(u, 0.80, 0.09)
            title_env = ss01(u, 0.48, 0.10) * txt_out
            if self.title_layer is not None and title_env > 0.001:
                composite_layer_masked(f, self.title_layer, None, title_env)
            sub_p = ramp01(u, 0.52, 0.08)
            if self.sub_layer is not None and sub_p > 0.001 and txt_out > 0.001:
                _composite_slide_up(f, self.sub_layer, sub_p, fade_out=txt_out)

        elif self.variant == "B":
            # Two-move handheld lamp path confined to the painted surface: Move 1 sweeps across the painted width; Move 2 pivots to rest on `region`.
            name_y = self.name_y_pct / 100.0 * H
            vx0, vy0, vx1, vy1 = self._paint_rect_visible(view)
            vw, vh = vx1 - vx0, vy1 - vy0
            x_left = vx0 + 0.02 * vw
            x_right = vx1 - 0.02 * vw
            if self.band.sign < 0:
                x_start, x_mid = x_right, x_left
            else:
                x_start, x_mid = x_left, x_right
            by1 = min(max(name_y, vy0 + 0.14 * vh), vy1 - 0.14 * vh)
            brx1 = max(srx * 1.15, min(0.16 * W, 0.38 * vw))
            bry1 = max(sry * 1.25, min(0.24 * H, 0.42 * vh))
            az0 = math.radians(angle_deg) + (math.pi if self.band.sign < 0 else 0.0)

            p1 = _ss_sine(ramp01(u, 0.04, 0.29))
            p2 = ss01(u, 0.33, 0.20)
            p_in = ss01(u, 0.01, 0.07)
            p_open = ss01(u, 0.85, 0.13)

            if u < 0.33:
                bx = x_start + (x_mid - x_start) * p1
                by = by1
                brx, bry = brx1, bry1
                az_rad = az0
            else:
                arc = min(0.06 * H, 0.10 * vh) * math.sin(math.pi * p2)
                bx = min(max(x_mid + (rx_s - x_mid) * p2, vx0), vx1)
                by = min(max(by1 + (ry_s - by1) * p2 + arc, vy0), vy1)
                brx = brx1 + (srx * 1.15 - brx1) * p2
                bry = bry1 + (sry * 1.25 - bry1) * p2
                az_rad = az0 * (1.0 - p2) + math.atan2(ry_s - by1, rx_s - x_mid) * p2

            beam_q = _tilted_pool(xs, ys, bx, by, brx, bry, angle_deg, max(feather, 0.52)) * p_in
            # Behind Move 1, upper painting retains a subtle wake so the frame holds sculptural context.
            q_reveal = _ss_sine(ramp01(u, 0.05, 0.27))
            wake_q = self.band.reveal(self.band.s_grid(q_reveal, xs, ys))
            bg = floor + (wake - floor) * wake_q * 0.85
            gain_q = bg + (1.0 - bg) * beam_q
            gain_q = (gain_q + (1.0 - gain_q) * p_open).astype(np.float32)
            warm_q = (warm * beam_q * (1.0 - p_open)).astype(np.float32)
            rel_q = (np.clip(0.18 * wake_q + 0.90 * beam_q, 0.0, 1.0) * (1.0 - p_open)).astype(np.float32)

            el_deg = 14.0 + 76.0 * p_open
            matte_gain = floor + (1.0 - floor) * p_open
            f = self._apply_surface(f, view, gain_q, warm_q, rel_q, az_rad, math.radians(el_deg), matte_gain=matte_gain)

            name_out = 1.0 - ramp01(u, 0.85, 0.08)
            name_rest = (1.0 - ss01(u, 0.48, 0.10)) if self.fade_name_at_rest else (1.0 - 0.30 * ss01(u, 0.48, 0.10))
            face_env = name_rest * name_out
            if q_reveal > 0.0 and face_env > 0.001:
                _composite_cut_ink(
                    f, self.name_cut,
                    lambda x0, y0, x1, y1: self.band.reveal_box(q_reveal, x0, y0, x1, y1),
                    lambda x0, y0, x1, y1: _tilted_pool(
                        np.arange(x0, x1, dtype=np.float32) + 0.5, np.arange(y0, y1, dtype=np.float32) + 0.5,
                        bx, by, brx, bry, angle_deg, max(feather, 0.52)),
                    math.cos(az_rad), math.sin(az_rad), face_env=face_env, bevel_env=face_env,
                )

            txt_out = 1.0 - ramp01(u, 0.85, 0.08)
            q_title = ramp01(u, 0.48, 0.10)
            if self.title_layer is not None and q_title > 0.0 and txt_out > 0.001:
                mask = None if q_title >= 1.0 else (lambda x0, y0, x1, y1: self.band.reveal_box(q_title, x0, y0, x1, y1))
                composite_layer_masked(f, self.title_layer, mask, txt_out)
            sub_p = ramp01(u, 0.53, 0.08)
            if self.sub_layer is not None and sub_p > 0.001 and txt_out > 0.001:
                _composite_slide_up(f, self.sub_layer, sub_p, fade_out=txt_out)

        else:
            # Variant C: Lamp elevation opens from low grazing (10 deg) to frontal (90 deg); no sweeping band.
            p_mid = _ss_sine(ramp01(u, 0.06, 0.30))
            p_hold = ramp01(u, 0.36, 0.42)
            p_rest = ss01(u, 0.30, 0.22)
            p_open = ss01(u, 0.78, 0.20)
            el_deg = 10.0 + 11.0 * p_mid + 8.0 * p_hold + 61.0 * p_open
            el_rad = math.radians(min(el_deg, 90.0))

            # Directional raking falloff across the painting from the lamp side, levelling out as elevation reaches 90 deg.
            nx = (xs[None, :] / W - 0.5) * 0.55 + (ys[:, None] / H - 0.5) * 0.25
            falloff = np.clip(1.0 - nx * (0.34 * math.cos(el_rad)), 0.74, 1.22)
            base_lvl = max(floor, 0.11) + 0.12 * p_mid + 0.05 * p_hold
            pool = _tilted_pool(xs, ys, rx_s, ry_s, srx * 1.22, sry * 1.32, angle_deg, 0.58)
            gain_q = np.clip(base_lvl * falloff, 0.0, 1.0)
            gain_q = gain_q + (1.0 - gain_q) * (p_rest * pool * 0.96)
            gain_q = (gain_q + (1.0 - gain_q) * p_open).astype(np.float32)

            warm_q = (warm * (0.28 + 0.72 * p_rest * pool) * (1.0 - p_open)).astype(np.float32)
            rel_q = ((0.68 + 0.32 * p_rest * pool) * (1.0 - p_open)).astype(np.float32)
            az_rad = math.radians(angle_deg - 18.0)
            matte_gain = floor + (1.0 - floor) * p_open
            f = self._apply_surface(f, view, gain_q, warm_q, rel_q, az_rad, el_rad, matte_gain=matte_gain)

            name_out = 1.0 - ramp01(u, 0.78, 0.09)
            bevel_env = ss01(u, 0.08, 0.14) * name_out
            face_base = ss01(u, 0.14, 0.18)
            face_rest = (1.0 - ss01(u, 0.36, 0.12)) if self.fade_name_at_rest else (1.0 - 0.20 * ss01(u, 0.42, 0.12))
            face_env = face_base * face_rest * name_out
            if bevel_env > 0.001 or face_env > 0.001:
                _composite_cut_ink(
                    f, self.name_cut, None, None,
                    math.cos(az_rad), math.sin(az_rad), face_env=face_env, bevel_env=bevel_env,
                )

            txt_out = 1.0 - ramp01(u, 0.78, 0.09)
            title_env = ss01(u, 0.37, 0.11) * txt_out
            if self.title_layer is not None and title_env > 0.001:
                composite_layer_masked(f, self.title_layer, None, title_env)
            sub_p = ramp01(u, 0.42, 0.08)
            if self.sub_layer is not None and sub_p > 0.001 and txt_out > 0.001:
                _composite_slide_up(f, self.sub_layer, sub_p, fade_out=txt_out)

        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = cls._defaults(tid, spec, context, bundle)
        name = bundle.sv("identity", "channel_name", None)
        if isinstance(name, str) and name.strip():
            d["text"] = name
        reg = context.get("region") or context.get("focus")
        if reg is not None:
            d["region"] = reg
        return d
