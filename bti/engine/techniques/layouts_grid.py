"""Layout family T1: LAY-02 .. LAY-08 (grids, columns, inset, held subject, strips, overlay grid, mirrored motif).

Ported from demo_runs/claude_code/build_reel.py lay02..lay08.  Every shot time `tt` below is seconds since the shot start (`self.t0`);
"d" is the shot length.  Pictures arrive through slots, text and geometry through params, cameras through `camera*` params
(keys in the source pixels of the slot's image, anchors `rel` so a retimed shot keeps its motion).

The registry entries (params, slots) for these ids are generated from `SPECS` (see tools in .scratch/t1/make_patch.py) and live in
style/gae/patches/t1_layouts_compare.json.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .. import helpers as H
from ..base import BaseRenderer, View
from ..registry import technique
from ..vfx import Cam, backdrop, blend, ease, ramp
from ._t1common import (aligned_view, as_lines, cam_of, fit_cam, hexbgr, panel, pdef, region_xy, static_cam, treat, TREATMENTS)
from .camera import _key


def _defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}


def _asset(context, k="asset"):
    return context.get(k) or {}


# ============================================================================================ LAY-02
@technique("LAY-02", "base")
class FourGrid(BaseRenderer):
    """Four tiles in a 2 x 2 grid; each fades in `stagger_s` after the previous one; thin lines then draw between the tile centres.

    Slots tile_1..tile_4; per-tile cameras camera_1..camera_4 (None = cover-fit).  Timing: tile i appears at i * stagger_s
    (fade_s long), the connectors start at connector_delay_s and take connector_draw_s (inout_sine)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.keys = [self.slot_asset("tile_%d" % i) for i in range(1, 5)]
        self.cams = [cam_of(shot, ctx, "camera_%d" % i) for i in range(1, 5)]
        p = self.p
        tw, th = int(p["tile_w_px"]), int(p["tile_h_px"])
        mx, my, gx, gy = int(p["margin_x_px"]), int(p["margin_y_px"]), int(p["gap_x_px"]), int(p["gap_y_px"])
        self.tw, self.th = tw, th
        self.pos = [(mx, my), (mx + tw + gx, my), (mx, my + th + gy), (mx + tw + gx, my + th + gy)]
        self.bg = hexbgr(p["background"])

    def render(self, t):
        W, Hh, p = self.ctx.w, self.ctx.h, self.p
        tt = t - self.t0
        f = np.zeros((Hh, W, 3), np.float32) + np.array(self.bg, np.float32)
        tw, th = self.tw, self.th
        for i, ((x, y), k, cam) in enumerate(zip(self.pos, self.keys, self.cams)):
            a = ramp(tt, float(p["stagger_s"]) * i, float(p["fade_s"]))
            if a <= 0 or k is None:
                continue
            tile = panel(self.ctx, k, cam, t, tw, th)
            f[y:y + th, x:x + tw] = f[y:y + th, x:x + tw] * (1 - a) + tile * a
        if p["connectors"]:
            pr = ramp(tt, float(p["connector_delay_s"]), float(p["connector_draw_s"]), "inout_sine")
            if pr > 0:
                c = [(x + tw // 2, y + th // 2) for x, y in self.pos]
                mode = p["connector_mode"]
                pairs = []
                if mode in ("frame", "all"):
                    pairs += [(0, 1), (0, 2), (1, 3), (2, 3)]
                if mode in ("cross", "all"):
                    pairs += [(0, 3), (1, 2)]
                col = hexbgr(p["connector_color"])
                for a_, b_ in pairs:
                    A, B = c[a_], c[b_]
                    q = (int(A[0] + (B[0] - A[0]) * pr), int(A[1] + (B[1] - A[1]) * pr))
                    cv2.line(f, A, q, col, int(p["connector_px"]), cv2.LINE_AA)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            for i in range(1, 5):
                d["camera_%d" % i] = fit_cam(a, d["tile_w_px"], d["tile_h_px"])
        return d


# ============================================================================================ LAY-03
def _stretch_tile(ctx, key, cw, ch, treatment):
    """Image squeezed to cw x ch from the smallest pyramid level that is large enough (the reel's behaviour), then treated.  Cached."""
    def build():
        im = ctx.image(key)
        lv = im.levels[0]
        for l in reversed(im.levels):
            if l.shape[1] >= cw and l.shape[0] >= ch:
                lv = l
                break
        out = treat(lv.astype(np.float32), treatment)
        return cv2.resize(out, (cw, ch), interpolation=cv2.INTER_AREA)
    return ctx.cached(("t1stretch", ctx.asset_path(key), cw, ch, treatment), build)


def _fit_tile(ctx, key, cw, ch, treatment, fit):
    if fit == "stretch":
        return _stretch_tile(ctx, key, cw, ch, treatment)
    def build():
        img = ctx.image(key)
        z = max(cw / img.w, ch / img.h) if fit == "cover" else min(cw / img.w, ch / img.h)
        out = img.view(img.w / 2, img.h / 2, z, cw, ch)[0].astype(np.float32)
        return treat(out, treatment)
    return ctx.cached(("t1fit", ctx.asset_path(key), cw, ch, treatment, fit), build)


@technique("LAY-03", "base")
class Columns(BaseRenderer):
    """N tall columns side by side (default 5), each a slot image with an optional colour treatment (grey, warm tint, contrast ...).

    Column i fades in at i * stagger_s over fade_s.  fit: cover (crop), contain, or stretch (the reel squeezed its stand-in)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.n = int(self.p["columns"])
        self.keys = [self.slot_asset("tile_%d" % i) for i in range(1, self.n + 1)]

    def render(self, t):
        W, Hh, p = self.ctx.w, self.ctx.h, self.p
        tt = t - self.t0
        f = np.zeros((Hh, W, 3), np.float32) + np.array(hexbgr(p["background"]), np.float32)
        cw, ch, gap, y0 = int(p["col_w_px"]), int(p["col_h_px"]), int(p["gap_px"]), int(p["y_px"])
        x0 = (W - self.n * cw - (self.n - 1) * gap) // 2
        for i, k in enumerate(self.keys):
            if k is None:
                continue
            a = ramp(tt, float(p["stagger_s"]) * i, float(p["fade_s"]))
            if a <= 0:
                continue
            c = _fit_tile(self.ctx, k, cw, ch, p["treatment_%d" % (i + 1)], p["fit"])
            x = x0 + i * (cw + gap)
            f[y0:y0 + ch, x:x + cw] = f[y0:y0 + ch, x:x + cw] * (1 - a) + c * a
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _defaults(spec)


# ============================================================================================ LAY-04
@technique("LAY-04", "base")
class InsetWindow(BaseRenderer):
    """A crop of the painting on the matte with a small framed window (image crop or footage) in a corner.

    Slots: image (main, camera `camera`), inset (an image: view `inset_camera`; or a video asset: cover-fit, looped).  The inset
    fades in at inset_delay_s over inset_fade_s; `inset_push_pct` grows the inset image's zoom linearly over the shot.  The white
    frame is drawn from the start, as in the reel (border_fades: it fades with the inset instead)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key, self.ikey = self.slot_asset("image"), self.slot_asset("inset")
        self.cam = cam_of(shot, ctx, "camera")
        self.icam = cam_of(shot, ctx, "inset_camera")
        self.d = max(self.t1 - self.t0, 1e-6)

    def _inset(self, t, w, h):
        ctx, p = self.ctx, self.p
        if ctx.asset(self.ikey).get("kind") == "video":
            fr = H.video_frame(ctx, self.ikey, t - self.t0 + float(p["video_offset_s"]), loop=True).astype(np.float32)
            s = max(w / fr.shape[1], h / fr.shape[0])
            r = cv2.resize(fr, (max(w, int(round(fr.shape[1] * s))), max(h, int(round(fr.shape[0] * s)))), interpolation=cv2.INTER_AREA)
            y0, x0 = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
            return r[y0:y0 + h, x0:x0 + w]
        img = ctx.image(self.ikey)
        if self.icam is not None:
            cx, cy, z = self.icam.at(t)
        else:
            cx, cy, z = img.w / 2, img.h / 2, max(w / img.w, h / img.h)
        if p["inset_push"]:
            z *= 1 + float(p["inset_push_pct"]) / 100.0 * (t - self.t0) / self.d
        return img.view(cx, cy, z, w, h)[0].astype(np.float32)

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        f = panel(ctx, self.key, self.cam, t, W, Hh, matte=True)
        w_, h_ = int(p["inset_w_px"]), int(p["inset_h_px"])
        mx, my = int(p["margin_x_px"]), int(p["margin_y_px"])
        corner = p["inset_corner"]
        x = W - w_ - mx if corner.endswith("right") else mx
        y = my if corner.startswith("top") else Hh - h_ - my
        a = ramp(tt, float(p["inset_delay_s"]), float(p["inset_fade_s"]))
        bw = int(p["border_px"])
        if bw > 0:
            ba = a if p["border_fades"] else 1.0
            if ba > 0:
                if ba >= 1.0:
                    cv2.rectangle(f, (x - 4, y - 4), (x + w_ + 4, y + h_ + 4), hexbgr(p["border_color"]), bw)
                else:
                    g = f.copy()
                    cv2.rectangle(g, (x - 4, y - 4), (x + w_ + 4, y + h_ + 4), hexbgr(p["border_color"]), bw)
                    f = f * (1 - ba) + g * ba
        if a > 0 and self.ikey:
            ins = self._inset(t, w_, h_)
            f[y:y + h_, x:x + w_] = f[y:y + h_, x:x + w_] * (1 - a) + ins * a
        return f

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 0.94 * 1080 / a["h"] * 2)
        b = context.get("asset_right") or {}
        if b.get("w"):
            d["inset_camera"] = fit_cam(b, d["inset_w_px"], d["inset_h_px"])
        return d


# ============================================================================================ LAY-05
@technique("LAY-05", "base")
class HeldSubject(BaseRenderer):
    """A cut-out subject (image + `mask` slot, camera `camera`) stays put while the background cross-dissolves through
    background_1..N (camera_bg_1..N, cover-fit when None).  Each background lasts seconds_per_background; the dissolve takes
    the last `dissolve_frac` of it (inout_sine); the last background holds.  Backgrounds are dimmed by background_dim."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key, self.mkey = self.slot_asset("image"), self.slot_asset("mask")
        self.bgs = [(i, self.slot_asset("background_%d" % i)) for i in range(1, 5)]
        self.bgs = [(k, cam_of(shot, ctx, "camera_bg_%d" % i)) for i, k in self.bgs if k]
        self.cam = cam_of(shot, ctx, "camera")

    def _bg(self, j, t):
        k, cam = self.bgs[j]
        return panel(self.ctx, k, cam, t, self.ctx.w, self.ctx.h)

    def render(self, t):
        ctx, p = self.ctx, self.p
        tt = t - self.t0
        n = len(self.bgs)
        seg = float(p["seconds_per_background"])
        dim = float(p["background_dim"])
        i = min(int(tt // seg), n - 1) if tt > 0 else 0
        if i < n - 1:
            q = ease("inout_sine", (tt - i * seg - seg * (1 - float(p["dissolve_frac"]))) / (seg * float(p["dissolve_frac"])))
            bg = self._bg(i, t) * dim if q <= 0 else blend(self._bg(i, t) * dim, self._bg(i + 1, t) * dim, q)
        else:
            bg = self._bg(i, t) * dim
        img = ctx.image(self.key)
        cx, cy, z = self.cam.at(t) if self.cam else (img.w / 2, img.h / 2, 0.94 * min(ctx.w / img.w, ctx.h / img.h))
        fg = img.view(cx, cy, z, ctx.w, ctx.h)[0].astype(np.float32)
        m = H.mask_alpha(ctx, self.mkey, cx, cy, z, image_key=self.key)
        return bg * (1 - m) + fg * m

    def view(self, t):
        img = self.ctx.image(self.key)
        cx, cy, z = self.cam.at(t) if self.cam else (img.w / 2, img.h / 2, 0.94 * min(self.ctx.w / img.w, self.ctx.h / img.h))
        return View(cx, cy, z, img, self.key)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(a["w"] / 2, a["h"] / 2, 0.94 * 1080 / a["h"])
        return d


# ============================================================================================ LAY-06
@technique("LAY-06", "base")
class VerticalStrips(BaseRenderer):
    """A dimmed base picture with `strip_count` semi-transparent vertical strips, each showing another crop and swaying sideways.

    Slots: image (strip source), background (base layer, defaults to image).  Strip i shows the crop centred at
    strip_start + i * strip_step (source px of `image`) at zoom strip_zoom * (1 + zoom_wobble * sin(tt + i)); it sits at
    x = (i * spacing + sway * sin(sway_rate * tt + i)) mod (W - strip_w) and fades in at i * stagger_s over fade_s to strip_opacity.
    The base is background * (1 - base_mix) ... base_mix of the picture over the matte (`camera_base`)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        self.bkey = self.slot_asset("background") or self.key
        self.cam_base = cam_of(shot, ctx, "camera_base")

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        base = panel(ctx, self.bkey, self.cam_base, t, W, Hh)
        mix = float(p["base_mix"])
        f = backdrop(W, Hh) * (1 - mix) + base * mix
        sw = int(p["strip_w_px"])
        img = ctx.image(self.key)
        sx0, sy0 = p["strip_start"] if p["strip_start"] is not None else (img.w / 2, img.h / 2)
        stx, sty = p["strip_step"]
        for i in range(int(p["strip_count"])):
            a = float(p["strip_opacity"]) * ramp(tt, float(p["stagger_s"]) * i, float(p["fade_s"]))
            if a <= 0:
                continue
            x = int((i * float(p["spacing_px"]) + float(p["sway_px"]) * math.sin(tt * float(p["sway_rate"]) + i)) % (W - sw))
            z = float(p["strip_zoom"]) * (1 + float(p["zoom_wobble"]) * math.sin(tt + i))
            strip = img.view(sx0 + stx * i, sy0 + sty * i, z, sw, Hh)[0].astype(np.float32)
            f[:, x:x + sw] = f[:, x:x + sw] * (1 - a) + strip * a
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            d["camera_base"] = static_cam(a["w"] / 2, a["h"] / 2, 1920 / a["w"] * 0.75)
            d["strip_start"] = [round(a["w"] * 0.46), round(a["h"] * 0.2)]
            d["strip_step"] = [round(a["w"] * 0.09), round(a["h"] * 0.1)]
            d["strip_zoom"] = round(0.5 * 4386 / a["w"], 4)
        return d


# ============================================================================================ LAY-07
@technique("LAY-07", "base")
class GridWithObject(BaseRenderer):
    """A grid of tiles (tile_1..tile_N in `columns` columns, camera_1..N, cover-fit when None) under a translucent circular
    view of `object` (camera `object_camera`, zoom wobbling by object_wobble * sin(object_wobble_rate * tt)).  The object fades
    in at overlay_delay_s over overlay_fade_s up to overlay_opacity; its edge is feathered over object_feather_px."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.tiles = [(self.slot_asset("tile_%d" % i), cam_of(shot, ctx, "camera_%d" % i)) for i in range(1, 7)]
        self.tiles = [x for x in self.tiles if x[0]]
        self.okey = self.slot_asset("object")
        self.ocam = cam_of(shot, ctx, "object_camera")

    def _mask(self):
        W, Hh, p = self.ctx.w, self.ctx.h, self.p
        r, fe = float(p["object_radius_px"]), float(p["object_feather_px"])
        def build():
            yy, xx = np.mgrid[0:Hh, 0:W].astype(np.float32)
            return np.clip(1 - (np.sqrt((xx - W / 2) ** 2 + (yy - Hh / 2) ** 2) - r) / max(fe, 1e-3), 0, 1)[:, :, None]
        return self.ctx.cached(("t1lay07mask", W, Hh, r, fe), build)

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        f = np.zeros((Hh, W, 3), np.float32) + np.array(hexbgr(p["background"]), np.float32)
        n = len(self.tiles)
        cols = int(p["columns"])
        rows = -(-n // cols)
        cw, ch = W // cols, Hh // rows
        for i, (k, cam) in enumerate(self.tiles):
            x, y = (i % cols) * cw, (i // cols) * ch
            f[y:y + ch, x:x + cw] = panel(ctx, k, cam, t, cw, ch)
        a = float(p["overlay_opacity"]) * ramp(tt, float(p["overlay_delay_s"]), float(p["overlay_fade_s"]))
        if a > 0 and self.okey:
            img = ctx.image(self.okey)
            cx, cy, z = self.ocam.at(t) if self.ocam else (img.w / 2, img.h / 2, max(W / img.w, Hh / img.h))
            z = z + float(p["object_wobble"]) * math.sin(float(p["object_wobble_rate"]) * tt)
            ov = img.view(cx, cy, z, W, Hh)[0].astype(np.float32)
            m = self._mask() * a
            f = f * (1 - m) + ov * m
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            for i in range(1, 5):
                d["camera_%d" % i] = fit_cam(a, 960, 540)
            cx, cy = region_xy(a, context)
            d["object_camera"] = static_cam(cx, cy, max(1920 / a["w"] * 0.9, 0.2))
        return d


# ============================================================================================ LAY-08
@technique("LAY-08", "base")
class MirroredMotif(BaseRenderer):
    """One motif view tiled `tiles` ("4x2" = columns x rows) over the canvas; with `mirror` every second column is flipped
    horizontally and every second row vertically (kaleidoscope symmetry).  The view is `camera` (source px of `image`), its zoom
    breathing by zoom_wobble * sin(wobble_rate * tt) (multiplicative)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        self.cam = cam_of(shot, ctx, "camera")
        c, r = str(self.p["tiles"]).lower().replace(" ", "").split("x")
        self.cols, self.rows = max(1, int(c)), max(1, int(r))

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        tw, th = W // self.cols, Hh // self.rows
        img = ctx.image(self.key)
        cx, cy, z = self.cam.at(t) if self.cam else (img.w / 2, img.h / 2, max(tw / img.w, th / img.h))
        z *= 1 + float(p["zoom_wobble"]) * math.sin(float(p["wobble_rate"]) * tt)
        tile = img.view(cx, cy, z, tw, th)[0].astype(np.float32)
        rows = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                x = tile
                if p["mirror"]:
                    if c % 2:
                        x = x[:, ::-1]
                    if r % 2:
                        x = x[::-1]
                row.append(x)
            rows.append(np.concatenate(row, 1))
        f = np.concatenate(rows, 0)
        if f.shape[:2] != (Hh, W):
            out = np.zeros((Hh, W, 3), np.float32)
            out[:f.shape[0], :f.shape[1]] = f
            f = out
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = _asset(context)
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, max(480 / a["w"] * 1.5, 0.1))
        return d


# ============================================================================================ registry entries (generated into the patch)
_COLORS = {"bg": "#0a0a0a"}
SPECS = {
    "LAY-02": dict(
        slots=[("tile_%d" % i, "image", True, False) for i in range(1, 5)],
        params=[pdef("tile_w_px", "number", 930, 100, 1900, "px"), pdef("tile_h_px", "number", 520, 100, 1080, "px"),
                pdef("margin_x_px", "number", 20, 0, 400, "px"), pdef("margin_y_px", "number", 15, 0, 400, "px"),
                pdef("gap_x_px", "number", 20, 0, 200, "px"), pdef("gap_y_px", "number", 10, 0, 200, "px"),
                pdef("background", "color", "#0a0a0a"),
                pdef("stagger_s", "number", 0.3, 0, 3, "s"), pdef("fade_s", "number", 0.4, 0, 3, "s")]
               + [pdef("camera_%d" % i, "camera", None) for i in range(1, 5)]
               + [pdef("connectors", "bool", True), pdef("connector_mode", "enum", "frame", values=["frame", "cross", "all"]),
                  pdef("connector_delay_s", "number", 1.8, 0, 10, "s"), pdef("connector_draw_s", "number", 1.2, 0, 4, "s"),
                  pdef("connector_color", "color", "#f5f5f5"), pdef("connector_px", "number", 3, 1, 20, "px")]),
    "LAY-03": dict(
        slots=[("tile_%d" % i, "image", i <= 2, False) for i in range(1, 7)],
        params=[pdef("columns", "number", 5, 2, 6, "count"), pdef("col_w_px", "number", 360, 100, 960, "px"),
                pdef("col_h_px", "number", 1000, 200, 1080, "px"), pdef("gap_px", "number", 24, 0, 100, "px"),
                pdef("y_px", "number", 40, 0, 400, "px"), pdef("background", "color", "#080808"),
                pdef("fit", "enum", "cover", values=["cover", "contain", "stretch"]),
                pdef("stagger_s", "number", 0.25, 0, 3, "s"), pdef("fade_s", "number", 0.35, 0, 3, "s")]
               + [pdef("treatment_%d" % i, "enum", "none", values=TREATMENTS) for i in range(1, 7)]),
    "LAY-04": dict(
        slots=[("image", "image", True, True), ("inset", "video", True, False)],
        params=[pdef("camera", "camera", None), pdef("inset_camera", "camera", None),
                pdef("inset_w_px", "number", 560, 200, 1000, "px"), pdef("inset_h_px", "number", 315, 100, 800, "px"),
                pdef("inset_corner", "enum", "top_right", values=["top_left", "top_right", "bottom_left", "bottom_right"]),
                pdef("margin_x_px", "number", 70, 0, 600, "px"), pdef("margin_y_px", "number", 60, 0, 600, "px"),
                pdef("inset_delay_s", "number", 1.0, 0, 10, "s"), pdef("inset_fade_s", "number", 0.4, 0, 3, "s"),
                pdef("inset_push", "bool", True), pdef("inset_push_pct", "number", 35, 0, 200, "%"),
                pdef("video_offset_s", "number", 0, 0, 3600, "s"),
                pdef("border_px", "number", 4, 0, 20, "px"), pdef("border_color", "color", "#f0f0f0"), pdef("border_fades", "bool", False)]),
    "LAY-05": dict(
        slots=[("image", "image", True, True), ("mask", "image", True, False)] + [("background_%d" % i, "image", i == 1, False) for i in range(1, 5)],
        params=[pdef("camera", "camera", None), pdef("seconds_per_background", "number", 1.5, 0.5, 20, "s"),
                pdef("dissolve_frac", "number", 0.4, 0.05, 1.0, "fraction"), pdef("background_dim", "number", 0.55, 0, 1, "factor")]
               + [pdef("camera_bg_%d" % i, "camera", None) for i in range(1, 5)]),
    "LAY-06": dict(
        slots=[("image", "image", True, True), ("background", "image", False, False)],
        params=[pdef("camera_base", "camera", None), pdef("base_mix", "number", 0.6, 0, 1, "alpha"),
                pdef("strip_count", "number", 6, 2, 10, "count"), pdef("strip_opacity", "number", 0.72, 0.2, 1.0, "alpha"),
                pdef("strip_w_px", "number", 260, 60, 800, "px"), pdef("spacing_px", "number", 330, 0, 1000, "px"),
                pdef("sway_px", "number", 120, 0, 600, "px"), pdef("sway_rate", "number", 0.9, 0, 10, "rad/s"),
                pdef("strip_start", "point", None), pdef("strip_step", "point", [0, 0]),
                pdef("strip_zoom", "number", 0.5, 0.02, 10, "zoom"), pdef("zoom_wobble", "number", 0.1, 0, 1, "fraction"),
                pdef("stagger_s", "number", 0.15, 0, 3, "s"), pdef("fade_s", "number", 0.5, 0, 3, "s")]),
    "LAY-07": dict(
        slots=[("tile_%d" % i, "image", i == 1, False) for i in range(1, 7)] + [("object", "image", True, True)],
        params=[pdef("columns", "number", 2, 1, 4, "count"), pdef("background", "color", "#0a0a0a")]
               + [pdef("camera_%d" % i, "camera", None) for i in range(1, 7)]
               + [pdef("object_camera", "camera", None), pdef("overlay_opacity", "number", 0.55, 0.1, 1.0, "alpha"),
                  pdef("overlay_delay_s", "number", 1.0, 0, 10, "s"), pdef("overlay_fade_s", "number", 0.6, 0, 3, "s"),
                  pdef("object_radius_px", "number", 360, 50, 1200, "px"), pdef("object_feather_px", "number", 40, 0, 400, "px"),
                  pdef("object_wobble", "number", 0.1, 0, 2, "zoom"), pdef("object_wobble_rate", "number", 1.0, 0, 10, "rad/s")]),
    "LAY-08": dict(
        slots=[("image", "image", True, True)],
        params=[pdef("camera", "camera", None), pdef("tiles", "string", "4x2"), pdef("mirror", "bool", True),
                pdef("zoom_wobble", "number", 0.06, 0, 1, "fraction"), pdef("wobble_rate", "number", 1.0, 0, 10, "rad/s")]),
}
