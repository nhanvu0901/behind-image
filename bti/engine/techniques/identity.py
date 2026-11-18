"""Channel identity "Raking Light" (family ID): the opening, the channel-name beat and the chapter marks, in two styles.

Style `raking` ("Vệt sáng quét"): a soft band of light sweeps over the dimmed picture and writes the text.
    ID-OPEN-01   overlay  raking reveal of the shot under it (the opening)
    ID-LABEL-01  overlay  two-line artwork label without a strip
    ID-BRAND-01  base     channel name written by the band
    ID-MARK-01   base     chapter mark written by the band
Style `dim` ("Tối lại, hiện tên"): the picture dims and a line of text fades in.
    ID-OPEN-02   overlay  dim and name (the opening)
    ID-BRAND-02  base     channel name on the dimmed picture
    ID-MARK-02   base     chapter mark on the dimmed picture
Design and numbers: docs/design/2026-11-18-identity-raking-light.md (sections 2 to 4); moving mock-ups: docs/design/2026-11-18-d13-identity-mock.html.

Rules shared by all seven:
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

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .. import vfx
from ..base import OverlayRenderer
from ..registry import technique
from ..vfx import Band, composite_layer_masked
from .camera import MatteShot, fit_zoom

INK = (244, 239, 228)            # the video ink of the mock-up, #f4efe4 (RGB)
SHADOW_ALPHA = 0.6               # soft shadow behind every line of text (mock-up: 0 0 .9cqw rgba(0,0,0,.6))
SHADOW_SIGMA = 0.0045            # Gaussian sigma of that shadow, as a fraction of the canvas width (0.9cqw blur radius / 2)
MAX_LINE_W_PCT = 88.0            # a line of text is never wider than this share of the frame: it is made smaller instead (never wrapped)


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


# ----------------------------------------------------------------------------- text
def _build_ink(W, H, text, kind, cap_pct, tracking_pct, baseline_pct, centre_pct, x_pct, align, max_w_pct, shadow):
    """One line of text (ink and a soft shadow) as a canvas-positioned `vfx.Layer`."""
    ratio = vfx.cap_ratio(kind)
    size = max(6, int(round(cap_pct / 100.0 * H / ratio)))
    max_w = max_w_pct / 100.0 * W

    def measure(sz):
        ft = vfx.font(kind, sz)
        trk = tracking_pct / 100.0 * sz
        if trk > 0:                                  # tracked capitals: letter by letter (no trailing space after the last letter)
            adv = [ft.getlength(c) for c in text]
            return ft, trk, adv, sum(adv) + trk * (len(text) - 1)
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
              max_w_pct=MAX_LINE_W_PCT, shadow=True):
    """Cached one-line text layer, or None when there is nothing to draw. The cap height is `cap_pct` % of the frame height; the line
    is centred (or left aligned) at `x_pct` % of the width and sits with the middle of its capitals at `centre_pct` % of the height
    (or its baseline at `baseline_pct`). The cache key holds every input."""
    if not isinstance(text, str) or not text.strip():
        return None
    key = ("idtext", text, kind, float(cap_pct), float(tracking_pct), baseline_pct, centre_pct, float(x_pct), align, float(max_w_pct), bool(shadow))
    return ctx.layer(key, lambda: _build_ink(ctx.w, ctx.h, text, kind, float(cap_pct), float(tracking_pct), baseline_pct, centre_pct,
                                             float(x_pct), align, float(max_w_pct), bool(shadow)))


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
