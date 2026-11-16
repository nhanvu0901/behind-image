"""Vertical-short techniques SHORT-01 .. SHORT-05: a 9:16 panel inside the 16:9 canvas (`helpers.vertical_panel`).

Ported from build_reel.py sh01..sh05. Differences from the benchmark, all deliberate:
  * the blurred ambient fill is built ONCE per shot from a time-independent source and cached (`vertical_panel` caches by key);
    the benchmark blurred a large image every frame (0.85-0.93 s per frame). A warm still now costs about 50-100 ms.
  * SHORT-02 warps with a constant border and an anti-aliased coverage mask instead of BORDER_REPLICATE (no vertical edge streaks).
  * SHORT-04 centres its label inside the box (the benchmark drew it 13 px too high, so its top overflowed the box).

The ambient fill is therefore the same for the whole shot; the panel content is animated as in the benchmark. Frames are pure functions of t.
"""
from __future__ import annotations

import math
import threading

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .. import helpers as H
from .. import vfx
from ..base import BaseRenderer, OverlayRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import Layer, blend, ease, ramp, text_layer
from . import _t4_common as C

_KM_LOCK = threading.Lock()


def _panel(ctx, p):
    return C.aspect_wh(p["frame_aspect"], ctx.h)


def _view(ctx, key, focus, zoom, w, h):
    cx, cy = C.focus_xy(ctx, focus, key)
    return ctx.image(key).view(cx, cy, float(zoom), w, h)[0].astype(np.float32)


class _ShortBase(BaseRenderer):
    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = C.base_defaults(spec)
        pt = C.ctx_point(context)
        if pt is not None and "focus" in d:
            d["focus"] = pt
        if "zoom" in d and d["zoom"] is not None:
            d["zoom"] = C.scaled_zoom(d["zoom"], context, bundle)
        return d

    def _sig_key(self, *names):
        return tuple(C.asset_sig(self.ctx, self.slot_asset(n)) for n in names)

    def _compose(self, content, amb_key, amb_build):
        """Panel over the cached ambient. `amb_build()` returns the (time independent) ambient source and is only called when the cache is cold."""
        ctx = self.ctx
        pw, ph = content.shape[1], content.shape[0]
        amb = ctx.cached(("t4amb",) + tuple(amb_key), amb_build)
        return H.vertical_panel(ctx, content, ("t4",) + tuple(amb_key), amb, pw=pw, ph=ph)


# ============================================================================= SHORT-01
@technique("SHORT-01", "base")
class ThreeStrips(_ShortBase):
    """Three stacked strips. Strip k shows source (k + step) mod 3, where step = floor(u / swap_every_s); in the last `fade_s` of each step
    it cross-fades to the next source. Source j is slot `strip_{j+1}` at `focus[j]` (region name or [x, y]; null = image centre).
    The visible source slowly zooms by `zoom_drift_per_s`. The ambient fill is blurred from the strips at the start of the shot."""
    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = C.base_defaults(spec)
        d["zoom"] = C.scaled_zoom(d["zoom"], context, bundle)
        return d

    def _strips(self, u, drift=True):
        ctx, p = self.ctx, self.p
        pw, ph = _panel(ctx, p)
        gap = int(p["strip_gap_px"])
        sh = (ph - 2 * gap) // 3
        focus = list(p["focus"] or [None, None, None]) + [None] * 3
        keys = [self.slot_asset("strip_%d" % (i + 1)) for i in range(3)]
        z = float(p["zoom"])
        T, fade = float(p["swap_every_s"]), min(float(p["fade_s"]), float(p["swap_every_s"]))
        step = int(u / T)
        a = ease(C.ease_name(p["ease"]), (u % T - (T - fade)) / fade) if fade > 0 else 0.0
        zz = z * (1 + float(p["zoom_drift_per_s"]) * u) if drift else z
        c = np.zeros((ph, pw, 3), np.float32)
        for i in range(3):
            j, n = (i + step) % 3, (i + step + 1) % 3
            v = _view(ctx, keys[j], focus[j], zz, pw, sh)
            if a > 0:
                v = blend(v, _view(ctx, keys[n], focus[n], z, pw, sh), a)
            c[i * (sh + gap):i * (sh + gap) + sh] = v
        return c

    def render(self, t):
        u = t - self.t0
        p = self.p
        c = self._strips(u)
        key = ("s01", self._sig_key("strip_1", "strip_2", "strip_3"), repr(p["focus"]), float(p["zoom"]), int(p["strip_gap_px"]), p["frame_aspect"])
        return self._compose(c, key, lambda: self._strips(0.0, drift=False))


# ============================================================================= SHORT-02
@technique("SHORT-02", "base")
class ChangingView(_ShortBase):
    """Slot `image` (crop at `focus`, `zoom`) filling the panel, perspective-warped from the identity to `to_quad` (TL, TR, BR, BL as
    fractions of the panel) between `warp_delay_s` and `warp_delay_s + warp_s` (inout_cubic). Pixels outside the warped quad are
    `fill_color` (constant border; the benchmark replicated edge pixels and streaked)."""
    def _content(self):
        ctx, p = self.ctx, self.p
        pw, ph = _panel(ctx, p)
        key = self.slot_asset("image")
        return ctx.cached(("t4s02view", C.asset_sig(ctx, key), repr(p["focus"]), float(p["zoom"]), pw, ph), lambda: _view(ctx, key, p["focus"], p["zoom"], pw, ph))

    def render(self, t):
        ctx, p = self.ctx, self.p
        u = t - self.t0
        pw, ph = _panel(ctx, p)
        a = self._content()
        pr = ease("inout_cubic", (u - float(p["warp_delay_s"])) / float(p["warp_s"]))
        ident = [(0, 0), (1, 0), (1, 1), (0, 1)]
        q = C.lerp_quad(ident, [tuple(float(v) for v in x) for x in p["to_quad"]], pr)
        dst = [(x * (pw - 1), y * (ph - 1)) for x, y in q]
        b = C.warp_with_alpha(a, dst, (pw, ph), hex_to_bgr(p["fill_color"])) if pr > 0 else a
        key = ("s02", C.asset_sig(ctx, self.slot_asset("image")), repr(p["focus"]), float(p["zoom"]), pw, ph)
        return self._compose(b, key, lambda: a)


# ============================================================================= SHORT-03
@technique("SHORT-03", "base")
class LargeType(_ShortBase):
    """Slot `background` (crop at `focus`, `zoom`, dimmed by `dim`) with large bold type centred on the canvas. `lines` are shown one per
    `seconds_per_line`; each fades in over `fade_in_s` and out over the last `fade_out_s`. After the last line's slot it stays visible.
    Text wider than `max_width_pct` of the panel is scaled down to fit."""
    def _content(self):
        ctx, p = self.ctx, self.p
        pw, ph = _panel(ctx, p)
        key = self.slot_asset("background")
        return ctx.cached(("t4s03bg", C.asset_sig(ctx, key), repr(p["focus"]), float(p["zoom"]), float(p["dim"]), pw, ph),
                          lambda: _view(ctx, key, p["focus"], p["zoom"], pw, ph) * float(p["dim"]))

    def _layer(self, text, pw):
        ctx, p = self.ctx, self.p
        size, trk, kind = int(p["size_px"]), int(p["tracking"]), "bold"
        col = hex_to_bgr(p["text_color"])
        ft = vfx.font(kind, size)
        w = sum(ft.getlength(ch) for ch in text) + trk * max(len(text) - 1, 0)
        lim = pw * float(p["max_width_pct"]) / 100.0
        if w > lim > 0:
            size = max(int(size * lim / w), 8)
        return ctx.layer(("t4s03txt", text, size, trk, col), lambda: text_layer(text, ctx.w // 2, ctx.h // 2, size, kind, trk, color=col, w=ctx.w, h=ctx.h))

    def render(self, t):
        ctx, p = self.ctx, self.p
        u = t - self.t0
        pw, ph = _panel(ctx, p)
        c = self._content()
        key = ("s03", C.asset_sig(ctx, self.slot_asset("background")), repr(p["focus"]), float(p["zoom"]), float(p["dim"]), pw, ph)
        f = self._compose(c, key, lambda: c)
        lines = [s for s in (p["lines"] or []) if s]
        if not lines:
            return f
        S = float(p["seconds_per_line"])
        i = min(int(u // S), len(lines) - 1)
        ph_ = u % S if u < S * len(lines) else S * .5
        fi, fo = float(p["fade_in_s"]), float(p["fade_out_s"])
        a = min(1.0, ph_ / fi) if fi > 0 else 1.0
        if u < S * len(lines):
            a *= 1 - ease("linear", (ph_ - (S - fo)) / fo) if fo > 0 else 1.0
        return self._layer(lines[i], pw).apply(f, a)


# ============================================================================= SHORT-04
@technique("SHORT-04", "overlay")
class YellowLabelBox(OverlayRenderer):
    """Small label on a coloured box near the bottom of the vertical panel (draw it on a SHORT-* shot with the same `frame_aspect`).
    The box (`box_margin_px` from the panel sides, `box_bottom_px` above the bottom, `box_height_px` tall) is visible from the
    overlay start; the text fades in at `text_delay_s` over `pop_s` and is centred in the box (shrunk if it would not fit)."""
    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        pw, ph = C.aspect_wh(p["frame_aspect"], ctx.h)
        x0 = (ctx.w - pw) // 2
        self.box = (x0 + int(p["box_margin_px"]), ph - int(p["box_bottom_px"]) - int(p["box_height_px"]), x0 + pw - int(p["box_margin_px"]), ph - int(p["box_bottom_px"]))
        self.layer = self._build_layer(ctx, p)

    def _build_layer(self, ctx, p):
        text = p["text"]
        if not text:
            return None
        bx0, by0, bx1, by1 = self.box
        size, trk = int(p["size_px"]), int(p["tracking"])
        col = tuple(int(v) for v in hex_to_bgr(p["text_color"]))
        maxw = (bx1 - bx0) - 2 * int(p["box_pad_px"])

        def build():
            sz = size
            while True:
                ft = vfx.font("reg", sz)
                w = sum(ft.getlength(ch) for ch in text) + trk * max(len(text) - 1, 0)
                if w <= maxw or sz <= 8:
                    break
                sz -= 1
            im = Image.new("RGBA", (ctx.w, ctx.h), (0, 0, 0, 0))
            vfx._tracked(ImageDraw.Draw(im), (ctx.w // 2, 0), text, ft, (col[2], col[1], col[0], 255), trk, "ma")
            arr = np.array(im)
            ys, xs = np.where(arr[:, :, 3] > 0)
            if ys.size == 0:
                return Layer(np.zeros((1, 1, 4), np.uint8), 0, 0)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2          # ink centred in the box
            return Layer(arr[y0:y1, x0:x1], cx - (x1 - x0) // 2, cy - (y1 - y0) // 2)
        return ctx.layer(("t4s04txt", text, size, trk, col, self.box, maxw), build)

    def apply(self, f, t, view):
        p = self.p
        u = t - self.t0
        bx0, by0, bx1, by1 = self.box
        cv2.rectangle(f, (bx0, by0), (bx1, by1), hex_to_bgr(p["box_color"]), -1)
        if self.layer is not None:
            self.layer.apply(f, ramp(u, float(p["text_delay_s"]), float(p["pop_s"])))
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = C.base_defaults(spec)
        d["text"] = context.get("text") or context.get("title") or d["text"]
        return d


# ============================================================================= SHORT-05
@technique("SHORT-05", "base")
class ColourWheel(_ShortBase):
    """A wheel of `sectors` colours taken from slot `palette` (k-means on a `sample_px` square thumbnail, seeded: `seed`), drawn sector by sector
    (`sector_stagger_s` apart, each growing over `sector_grow_s`, clockwise from the top) with a hole in the middle, on a dark panel.
    `sector_order` cluster keeps the clustering order, hue sorts around the wheel, lightness sorts dark to light."""
    def _colours(self):
        ctx, p = self.ctx, self.p
        key = self.slot_asset("palette")
        n, sp, seed, order = int(p["sectors"]), int(p["sample_px"]), int(p["seed"]), p["sector_order"]

        def build():
            im = ctx.image(key)
            lv = im.levels[0]
            for l in im.levels:                           # smallest pyramid level that is still at least 400 px on its short side
                if min(l.shape[:2]) >= 400:
                    lv = l
            px = cv2.resize(lv, (sp, sp), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
            with _KM_LOCK:
                cv2.setRNGSeed(seed)
                km = cv2.kmeans(px, n, None, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 20, .5), 3, cv2.KMEANS_PP_CENTERS)[2]
            if order == "hue":
                hsv = cv2.cvtColor(km.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV)[0]
                km = km[np.argsort(hsv[:, 0], kind="stable")]
            elif order == "lightness":
                km = km[np.argsort(km.mean(1), kind="stable")]
            return km
        return ctx.cached(("t4s05col", C.asset_sig(ctx, key), n, sp, seed, order), build)

    def _wheel(self, u, full=False):
        ctx, p = self.ctx, self.p
        pw, ph = _panel(ctx, p)
        c = np.zeros((ph, pw, 3), np.float32) + float(p["bg_level"])
        km = self._colours()
        n = len(km)
        cc = (pw // 2, ph // 2)
        r = int(p["radius_px"])
        step = 360.0 / n
        for i in range(n):
            a = 1.0 if full else ramp(u, float(p["sector_start_s"]) + float(p["sector_stagger_s"]) * i, float(p["sector_grow_s"]))
            if a > 0:
                cv2.ellipse(c, cc, (r, r), 0, step * i - 90, step * i - 90 + step * a, tuple(float(v) for v in km[i]), -1, cv2.LINE_AA)
        cv2.circle(c, cc, int(p["hole_px"]), (float(p["bg_level"]),) * 3, -1)
        return c

    def render(self, t):
        ctx, p = self.ctx, self.p
        u = t - self.t0
        pw, ph = _panel(ctx, p)
        key = ("s05", C.asset_sig(ctx, self.slot_asset("palette")), int(p["sectors"]), int(p["sample_px"]), int(p["seed"]), p["sector_order"],
               int(p["radius_px"]), int(p["hole_px"]), float(p["bg_level"]), pw, ph)
        return self._compose(self._wheel(u), key, lambda: self._wheel(0.0, full=True))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return C.base_defaults(spec)
