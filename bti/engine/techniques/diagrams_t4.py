"""Diagram techniques DIA-01 .. DIA-06 (the convex-mirror diagram DIA-07 lives in `diagrams.py`).

Ported from build_reel.py dia01..dia06. Every image, mask, point, label and layer list comes from the storyboard (slots, params,
anchors); the renderers contain mechanisms only.

  DIA-01  GridRays        a lettered grid over a crop of the image, and a ray fan built up from one point beside it
  DIA-02  TwoViews        one image shown flat and, beside it, warped by a perspective quad (from_quad -> to_quad)
  DIA-03  CrossSection    layered bands (schematic from `layers`, or an image slot), gold V rays, an optional measuring arrow
  DIA-04  ExplodedFigure  a cut-out figure on black and circular crops that drift out from the centre
  DIA-05  ProcessSilhouette  a silhouette whose fill, outline and finally the picture / footage fade in stage by stage
  DIA-06  RoomModelUV     a room (image slot, or a wireframe schematic) with the painting marked, and a detail image crossfading to a UV image

Timing: all times in params are seconds from the shot start (`self.t0`). Frames are pure functions of t.
Canvas coordinates (1920x1080) are used for everything that has no image; source coordinates (region name or [x, y]) for image crops.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .. import helpers as H
from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import Layer, backdrop, blend, ease, ramp, text_layer
from . import _t4_common as C


# ----------------------------------------------------------------------------- shared drawing helpers
def _txt(ctx, f, text, cx, cy, size, env=1.0, kind="reg", tracking=5, color=(255, 255, 255), shadow=True):
    if env <= 0.001 or not text:
        return f
    L = ctx.layer(("t4txt", text, int(cx), int(cy), int(size), kind, tracking, tuple(color), shadow),
                  lambda: text_layer(text, int(cx), int(cy), int(size), kind, tracking, color=tuple(color), w=ctx.w, h=ctx.h, shadow=shadow))
    return L.apply(f, env)


def _label_style(ctx):
    return int(ctx.sv("diagram", "label_size_px", 28)), int(ctx.sv("diagram", "label_tracking", 5))


def _crop(ctx, key, focus, zoom, bw, bh):
    """float32 BGR crop (bh x bw) of asset `key` centred on `focus` (source px) at `zoom`."""
    cx, cy = C.focus_xy(ctx, focus, key)
    return ctx.image(key).view(cx, cy, float(zoom), bw, bh)[0].astype(np.float32)


def _box(p, name):
    x0, y0, x1, y1 = (int(v) for v in p[name])
    return x0, y0, x1, y1


def _xy(p, name):
    return int(p[name][0]), int(p[name][1])


def _line(f, a, b, col, th):
    cv2.line(f, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), col, th, cv2.LINE_AA)


class _T4Base(BaseRenderer):
    """Common default_params: focus point and zoom rescaled to the asset the editor is working on."""
    ZOOM_PARAMS: tuple = ()

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = C.base_defaults(spec)
        pt = C.ctx_point(context)
        if pt is not None and "focus" in d:
            d["focus"] = pt
        for k in cls.ZOOM_PARAMS:
            if k in d and d[k] is not None:
                d[k] = C.scaled_zoom(d[k], context, bundle)
        return d


# ============================================================================= DIA-01
@technique("DIA-01", "base")
class GridRays(_T4Base):
    """Grid with column letters over a crop of slot `image`, plus rays growing from one point (`ray_origin`) to a fan of end points.

    The rays start at `ray_start_s` and take `ray_draw_s` (inout_sine); nothing depends on t1."""
    ZOOM_PARAMS = ("zoom",)

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        u = t - self.t0
        f = np.zeros((Hh, W, 3), np.float32) + float(p["bg_level"])
        x0, y0, x1, y1 = _box(p, "grid_box")
        bw, bh = x1 - x0, y1 - y0
        key = self.slot_asset("image")
        f[y0:y1, x0:x1] = _crop(ctx, key, p["focus"], p["zoom"], bw, bh)
        cols, rows = max(int(p["grid_cols"]), 1), max(int(p["grid_rows"]), 1)
        gcol = (255, 255, 255)
        for k in range(cols + 1):
            x = x0 + int(round(k * bw / cols))
            _line(f, (x, y0), (x, y1), gcol, int(p["grid_line_px"]))
        for k in range(rows + 1):
            y = y0 + int(round(k * bh / rows))
            _line(f, (x0, y), (x1, y), gcol, int(p["grid_line_px"]))
        letters = p["column_labels"] or "".join(chr(65 + i) for i in range(cols))
        for k in range(cols):
            if k < len(letters):
                f = _txt(ctx, f, letters[k], x0 + int(round((k + .5) * bw / cols)), y0 - 20, int(p["letter_px"]), 1.0, tracking=0)
        # right: axes and the ray fan
        ox, oy = _xy(p, "axes_origin")
        ex, ey = _xy(p, "axes_end")
        wcol = (255, 255, 255)
        _line(f, (ox, oy), (ex, oy), wcol, 2)
        _line(f, (ox, oy), (ox, ey), wcol, 2)
        pr = ramp(u, float(p["ray_start_s"]), float(p["ray_draw_s"]), "inout_sine")
        rx, ry = _xy(p, "ray_origin")
        n = max(int(p["ray_count"]), 1)
        col = hex_to_bgr(p["ray_color"])
        for i in range(n):
            frac = i / (n - 1) if n > 1 else 0.5
            e = (int(p["ray_end_x"]), int(round(p["ray_end_top"] + (p["ray_end_bottom"] - p["ray_end_top"]) * frac)))
            q = (int(rx + (e[0] - rx) * pr), int(ry + (e[1] - ry) * pr))
            _line(f, (rx, ry), q, col, int(p["ray_width_px"]))
        return f


# ============================================================================= DIA-02
@technique("DIA-02", "base")
class TwoViews(_T4Base):
    """Slot `image` shown flat in `box_a`; in `box_b` the same crop warped. The warp runs from `from_quad` to `to_quad`
    (4 points TL, TR, BR, BL as fractions of the panel) between `warp_delay_s` and `warp_delay_s + warp_s` (inout_cubic).
    The second label fades in with the warp."""
    ZOOM_PARAMS = ("zoom",)

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.q0 = [tuple(float(v) for v in q) for q in (p["from_quad"] or [[0, 0], [1, 0], [1, 1], [0, 1]])]
        self.q1 = [tuple(float(v) for v in q) for q in p["to_quad"]]

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        u = t - self.t0
        ax0, ay0, ax1, ay1 = _box(p, "box_a")
        bx0, by0, bx1, by1 = _box(p, "box_b")
        aw, ah, bw, bh = ax1 - ax0, ay1 - ay0, bx1 - bx0, by1 - by0
        key = self.slot_asset("image")
        sig = C.asset_sig(ctx, key)
        a = ctx.cached(("t4dia02a", sig, repr(p["focus"]), float(p["zoom"]), aw, ah), lambda: _crop(ctx, key, p["focus"], p["zoom"], aw, ah))
        pr = ease("inout_cubic", (u - float(p["warp_delay_s"])) / float(p["warp_s"]))
        quad = C.lerp_quad(self.q0, self.q1, pr)
        dst = [(x * (bw - 1), y * (bh - 1)) for x, y in quad]
        bd = backdrop(bw, bh)
        b = C.warp_with_alpha(a if (aw, ah) == (bw, bh) else cv2.resize(a, (bw, bh), interpolation=cv2.INTER_AREA), dst, (bw, bh), bd)
        f = backdrop(W, Hh).copy()
        f[ay0:ay1, ax0:ax1] = a
        f[by0:by1, bx0:bx1] = b
        size, trk = _label_style(ctx)
        gap = int(p["label_gap_px"])
        f = _txt(ctx, f, p["label_a"], (ax0 + ax1) // 2, ay1 + gap, size, 1.0, tracking=trk)
        f = _txt(ctx, f, p["label_b"], (bx0 + bx1) // 2, by1 + gap, size, pr, tracking=trk)
        return f


# ============================================================================= DIA-03
def parse_layers(lines):
    """`lines` -> [(name, bgr, height)]. Each line is 'NAME | #rrggbb | height'; colour and height are optional."""
    out = []
    for ln in lines or []:
        name, col, h = C.parse_bar(ln, 3)
        try:
            bgr = hex_to_bgr(col) if col else (128, 128, 128)
        except Exception:
            bgr = (128, 128, 128)
        try:
            hh = float(h) if h else 80.0
        except ValueError:
            hh = 80.0
        out.append((name, bgr, max(hh, 1.0)))
    return out


@technique("DIA-03", "base")
class CrossSection(_T4Base):
    """Layered cross-section. Slot `cross_section` (optional): a real image fitted into `section_box`; the layer names from `layers`
    are then drawn over it at their band positions. Without the slot the bands are drawn as colour fills from `layers`.

    Bands fade in one after another (`band_stagger_s`), then `ray_count` gold rays come down, bounce at `ray_hit_y` and go back up
    in a V, each one `ray_stagger_s` after the previous. `measure_text` (non-empty) adds a double arrow along the layers
    `measure_first_layer`..`measure_last_layer` (1-based; 0 = last) with that text, drawn from `measure_start_s`."""

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        u = t - self.t0
        bg = float(p["bg_level"])
        f = np.zeros((Hh, W, 3), np.float32) + bg
        layers = parse_layers(p["layers"])
        x0, y0, x1, y1 = _box(p, "section_box")
        total = sum(h for _, _, h in layers) or 1.0
        scale = (y1 - y0) / total
        key = self.slot_asset("cross_section")
        size, trk = _label_style(ctx)
        ys, cum = [], 0.0
        for _, _, h in layers:
            ys.append((y0 + int(round(cum * scale)), y0 + int(round((cum + h) * scale))))
            cum += h
        if key:
            im = ctx.image(key)
            a = ramp(u, float(p["band_start_s"]), float(p["band_fade_s"]))
            if a > 0:
                bw, bh = x1 - x0, y1 - y0
                z = H.cover_zoom(im.w, im.h, bw, bh)
                pic = im.view(im.w / 2, im.h / 2, z, bw, bh)[0].astype(np.float32)
                f[y0:y1, x0:x1] = pic * a + bg * (1 - a)
        for i, ((name, c, _), (ya, yb)) in enumerate(zip(layers, ys)):
            a = ramp(u, float(p["band_start_s"]) + float(p["band_stagger_s"]) * i, float(p["band_fade_s"]))
            if not key:
                cv2.rectangle(f, (x0, ya), (x1, yb), tuple(float(v) * a + bg * (1 - a) for v in c), -1)
                dark = C.luminance(c) > 190
                f = _txt(ctx, f, name, (x0 + x1) // 2, (ya + yb) // 2 + 6, size, a, tracking=trk, color=(0, 0, 0) if dark else (255, 255, 255), shadow=False)
            else:
                if i:
                    f[ya:ya + 2, x0:x1] = f[ya:ya + 2, x0:x1] * (1 - .6 * a) + 255 * .6 * a
                f = _txt(ctx, f, name, (x0 + x1) // 2, (ya + yb) // 2 + 6, size, a, tracking=trk)
        # rays
        col = hex_to_bgr(p["ray_color"])
        top, hit = int(p["ray_top_y"]), int(p["ray_hit_y"])
        hw, th = int(p["ray_half_width_px"]), int(p["ray_width_px"])
        for i in range(int(p["ray_count"])):
            pr = ramp(u, float(p["ray_start_s"]) + float(p["ray_stagger_s"]) * i, float(p["ray_draw_s"]))
            rx = int(p["ray_x0"]) + i * int(p["ray_pitch_px"])
            k1 = min(pr * 2, 1)
            _line(f, (rx, top), (rx + hw * k1, top + (hit - top) * k1), col, th)
            if pr > .5:
                k2 = (pr - .5) * 2
                _line(f, (rx + hw, hit), (rx + hw + hw * k2, hit - (hit - top) * k2), col, th)
        # measuring arrow
        mt = p["measure_text"]
        if mt and layers:
            first = max(int(p["measure_first_layer"]), 1) - 1
            last = int(p["measure_last_layer"]) - 1 if int(p["measure_last_layer"]) > 0 else len(layers) - 1
            first, last = min(first, len(layers) - 1), min(max(last, first), len(layers) - 1)
            m = ramp(u, float(p["measure_start_s"]), float(p["measure_draw_s"]), "inout_sine")
            if m > 0:
                ya, yb = ys[first][0], ys[last][1]
                ax = x1 + int(p["measure_gap_px"])
                mid = (ya + yb) / 2
                yy0, yy1 = mid - (mid - ya) * m, mid + (yb - mid) * m
                white = (255, 255, 255)
                cv2.arrowedLine(f, (ax, int(mid)), (ax, int(yy0)), white, 3, cv2.LINE_AA, 0, min(.35, 14 / max(abs(mid - yy0), 1)))
                cv2.arrowedLine(f, (ax, int(mid)), (ax, int(yy1)), white, 3, cv2.LINE_AA, 0, min(.35, 14 / max(abs(yy1 - mid), 1)))
                f = _txt(ctx, f, mt, ax + int(p["measure_text_dx_px"]), int(mid), size, ramp(u, float(p["measure_start_s"]) + float(p["measure_draw_s"]) * .5, .4), tracking=trk)
        return f


# ============================================================================= DIA-04
@technique("DIA-04", "base")
class ExplodedFigure(_T4Base):
    """Cut-out `figure` (with optional `mask`, white = inside) centred on black, and circular crops (`pieces`) that start at the
    canvas centre and drift to their target positions between `drift_delay_s` and `drift_delay_s + drift_s` (inout_cubic), fading in.

    `pieces` lines: 'SOURCE | zoom | x,y' where SOURCE is a region name or 'x,y' in source px of the pieces image (slot `pieces`, else
    `figure`) and x,y is the piece's top-left corner on the canvas at the end of the drift."""
    ZOOM_PARAMS = ()

    def _static(self):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        fkey, mkey = self.slot_asset("figure"), self.slot_asset("mask")
        fsig = C.asset_sig(ctx, fkey)
        msig = C.asset_sig(ctx, mkey) if mkey else None

        def build():
            im = ctx.image(fkey)
            cx, cy = C.focus_xy(ctx, p["figure_focus"], fkey)
            z = float(p["figure_height_pct"]) / 100.0 * Hh / im.h
            f = np.zeros((Hh, W, 3), np.float32) + float(p["bg_level"])
            fg, alpha, _ = im.view(cx, cy, z, W, Hh)
            if mkey:
                m = H.mask_alpha(ctx, mkey, cx, cy, z, W, Hh, image_key=fkey)
            else:
                m = alpha
            return f * (1 - m) + fg.astype(np.float32) * m
        return ctx.cached(("t4dia04fig", fsig, msig, repr(p["figure_focus"]), float(p["figure_height_pct"]), float(p["bg_level"])), build)

    def _pieces(self):
        p = self.p
        out = []
        for ln in p["pieces"] or []:
            src, zoom, tgt = C.parse_bar(ln, 3)
            out.append((src, float(zoom or 0.5), C.parse_point(tgt or "0,0")))
        return out

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        u = t - self.t0
        pr = ease("inout_cubic", (u - float(p["drift_delay_s"])) / float(p["drift_s"]))
        f = self._static().copy()
        pkey = self.slot_asset("pieces") or self.slot_asset("figure")
        psig = C.asset_sig(ctx, pkey)
        tw = int(p["piece_px"])
        yy, xx = np.mgrid[0:tw, 0:tw].astype(np.float32)
        circ = (np.sqrt((xx - tw / 2) ** 2 + (yy - tw / 2) ** 2) < tw / 2 - 2).astype(np.float32)[:, :, None]
        for src, zoom, pos in self._pieces():
            def build(src=src, zoom=zoom):
                c = C.parse_point(src) if "," in src else src
                cx, cy = C.focus_xy(ctx, c, pkey)
                return ctx.image(pkey).view(cx, cy, zoom, tw, tw)[0].astype(np.float32)
            piece = ctx.cached(("t4dia04pc", psig, src, zoom, tw), build)
            x = int(W / 2 + (pos[0] - W / 2) * pr)
            y = int(Hh / 2 + (pos[1] - Hh / 2) * pr)
            fx0, fy0, fx1, fy1 = max(x, 0), max(y, 0), min(x + tw, W), min(y + tw, Hh)
            if fx1 <= fx0 or fy1 <= fy0:
                continue
            sl = (slice(fy0 - y, fy1 - y), slice(fx0 - x, fx1 - x))
            reg = f[fy0:fy1, fx0:fx1]
            k = circ[sl] * pr
            f[fy0:fy1, fx0:fx1] = reg * (1 - k) + piece[sl] * k
        return f


# ============================================================================= DIA-05
@technique("DIA-05", "base")
class ProcessSilhouette(_T4Base):
    """A silhouette (slot `mask` on slot `image`) that changes state in `stages`. Lines: 'KIND | colour | start_s | fade_s' with KIND
    `fill` (silhouette in colour on bg_level), `outline` (its edge in colour) or `image` (the picture, `colour` ignored) or `footage`
    (slot `footage`, played from the stage start). The first stage is shown from the start (start and fade ignored); each later stage
    fades over the previous one from `start_s` over `fade_s` (shot seconds)."""
    ZOOM_PARAMS = ()

    def _stage_img(self, kind, colour, u0):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        ikey, mkey = self.slot_asset("image"), self.slot_asset("mask")
        cx, cy = C.focus_xy(ctx, p["focus"], ikey)
        iw, ih = ctx.asset_size(ikey)
        z = float(p["width_pct"]) / 100.0 * W / iw
        bg = float(p["bg_level"])
        col = np.array(hex_to_bgr(colour) if colour else (255, 255, 255), np.float32)
        sig = (C.asset_sig(ctx, ikey), C.asset_sig(ctx, mkey) if mkey else None, cx, cy, z, bg)

        def alpha():
            return ctx.cached(("t4dia05m",) + sig, lambda: H.mask_alpha(ctx, mkey, cx, cy, z, W, Hh, image_key=ikey))
        if kind == "fill":
            m = alpha()
            return ctx.cached(("t4dia05fill", colour) + sig, lambda: np.zeros((Hh, W, 3), np.float32) + bg * (1 - m) + col * m)
        if kind == "outline":
            def build():
                m = alpha()
                e = cv2.Canny((m[:, :, 0] * 255).astype(np.uint8), 50, 150)
                e = cv2.dilate(e, np.ones((3, 3), np.uint8)).astype(np.float32)[:, :, None] / 255
                return (np.zeros((Hh, W, 3), np.float32) + bg) * (1 - e) + col * e
            return ctx.cached(("t4dia05outl", colour) + sig, build)
        if kind == "footage":
            vkey = self.slot_asset("footage")
            if not vkey:
                return np.zeros((Hh, W, 3), np.float32) + bg
            fr = H.video_frame(ctx, vkey, max(u0, 0.0)).astype(np.float32)
            s = max(W / fr.shape[1], Hh / fr.shape[0])
            fr = cv2.resize(fr, (int(math.ceil(fr.shape[1] * s)), int(math.ceil(fr.shape[0] * s))), interpolation=cv2.INTER_AREA)
            y, x = (fr.shape[0] - Hh) // 2, (fr.shape[1] - W) // 2
            return fr[y:y + Hh, x:x + W]
        return ctx.image(ikey).view(cx, cy, z, W, Hh)[0].astype(np.float32)

    def render(self, t):
        p = self.p
        u = t - self.t0
        stages = [C.parse_bar(s, 4) for s in p["stages"] or []]
        if not stages:
            return np.zeros((self.ctx.h, self.ctx.w, 3), np.float32)
        kind, colour, _, _ = stages[0]
        f = self._stage_img(kind, colour, u)
        for kind, colour, start, fade in stages[1:]:
            s0 = float(start or 0)
            a = ramp(u, s0, float(fade or 1.0))
            if a > 0:
                f = blend(f, self._stage_img(kind, colour, u - s0), a)
        return f


# ============================================================================= DIA-06
@technique("DIA-06", "base")
class RoomModelUV(_T4Base):
    """Left: slot `room` fitted into `room_box` (else a wireframe room schematic drawn at `room_center`), with the painting marked
    (`painting_box`, source px of the room image; in the schematic the painting is the filled rectangle). Right: slot `detail` (optional)
    cross-fading into slot `uv_detail` inside `uv_box` from `uv_start_s` over `uv_fade_s`. Labels fade in at their own times.
    Both images are shown as given: nothing is simulated."""

    def _room(self, f, u):
        ctx, p = self.ctx, self.p
        key = self.slot_asset("room")
        if key:
            x0, y0, x1, y1 = _box(p, "room_box")
            im = ctx.image(key)
            bw, bh = x1 - x0, y1 - y0
            z = H.contain_zoom(im.w, im.h, bw, bh, 1.0)
            pic = im.view(im.w / 2, im.h / 2, z, bw, bh)[0].astype(np.float32)
            f[y0:y1, x0:x1] = pic
            pb = p["painting_box"]
            if pb:
                col = hex_to_bgr(p["painting_color"])
                sx0, sy0 = x0 + bw / 2 + (pb[0] - im.w / 2) * z, y0 + bh / 2 + (pb[1] - im.h / 2) * z
                sx1, sy1 = x0 + bw / 2 + (pb[2] - im.w / 2) * z, y0 + bh / 2 + (pb[3] - im.h / 2) * z
                pa = ramp(u, float(p["painting_start_s"]), float(p["painting_fade_s"]))
                a_, b_ = (int(sx0), int(sy0)), (int(sx1), int(sy1))
                ov = f.copy()
                cv2.rectangle(ov, a_, b_, col, -1)
                ov = blend(f, ov, .45)
                cv2.rectangle(ov, a_, b_, col, 3, cv2.LINE_AA)
                f = blend(f, ov, pa)
            return f
        ox, oy = _xy(p, "room_center")
        s = float(p["room_scale"])
        line = (230, 230, 230)
        o = lambda dx, dy: np.array([ox + dx * s, oy + dy * s], np.float32)
        floor = np.array([o(0, 120), o(330, -40), o(0, -200), o(-330, -40)], np.float32)
        up = np.array([0, -330 * s], np.float32)
        wall = np.array([floor[2], floor[3], floor[3] + up, floor[2] + up], np.int32)
        wall2 = np.array([floor[2], floor[1], floor[1] + up, floor[2] + up], np.int32)
        cv2.polylines(f, [floor.astype(np.int32)], True, line, 3, cv2.LINE_AA)
        cv2.polylines(f, [wall, wall2], True, line, 3, cv2.LINE_AA)
        col = hex_to_bgr(p["painting_color"])
        cv2.rectangle(f, (int(ox - 70 * s), int(oy - 440 * s)), (int(ox + 20 * s), int(oy - 290 * s)), col, -1)
        return f

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        u = t - self.t0
        f = backdrop(W, Hh).copy()
        f = self._room(f, u)
        size, trk = int(p["label_px"]), _label_style(ctx)[1]
        rx, ry = _xy(p, "room_label_pos")
        f = _txt(ctx, f, p["room_label"], rx, ry, size, ramp(u, float(p["room_label_start_s"]), float(p["room_label_fade_s"])), tracking=trk)
        x0, y0, x1, y1 = _box(p, "uv_box")
        bw, bh = x1 - x0, y1 - y0
        ukey, dkey = self.slot_asset("uv_detail"), self.slot_asset("detail")

        def fit(key):
            im = ctx.image(key)
            return im.view(im.w / 2, im.h / 2, H.cover_zoom(im.w, im.h, bw, bh), bw, bh)[0].astype(np.float32)
        uv = ctx.cached(("t4dia06uv", C.asset_sig(ctx, ukey), bw, bh), lambda: fit(ukey))
        if dkey:
            det = ctx.cached(("t4dia06det", C.asset_sig(ctx, dkey), bw, bh), lambda: fit(dkey))
            pic = blend(det, uv, ramp(u, float(p["uv_start_s"]), float(p["uv_fade_s"])))
        else:
            a = ramp(u, float(p["uv_start_s"]), float(p["uv_fade_s"]))
            pic = blend(f[y0:y1, x0:x1], uv, a)
        f[y0:y1, x0:x1] = pic
        lx, ly = _xy(p, "uv_label_pos")
        f = _txt(ctx, f, p["uv_label"], lx, ly, size, ramp(u, float(p["uv_label_start_s"]), float(p["uv_label_fade_s"])), tracking=trk)
        return f
