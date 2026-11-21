"""Comparison family T1: CMP-01 .. CMP-05, X-CMP-01 (swap one side of a split), X-CMP-02 (vertical wipe compare).

CMP-* are ported from build_reel.py cmp01..cmp05; X-CMP-* are new (built from the research description, R3_style_inventory).
Shot time `tt` = seconds since the shot start.  Two images that show the same picture (scan vs print) are ALIGNED: one camera given
in the pixels of the main slot is applied to the other slot scaled by the size ratio (`_t1common.aligned_cam`).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .. import helpers as H
from ..base import BaseRenderer, View
from ..registry import technique
from ..vfx import backdrop, blend, compose_matte, ease, put, ramp
from ._t1common import (TREATMENTS, aligned_view, as_lines, caption, cam_of, fit_cam, floats, hexbgr, panel, pdef, region_xy, static_cam, treat)


def _defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}


# ============================================================================================ CMP-01
@technique("CMP-01", "base")
class GreyToColour(BaseRenderer):
    """Left panel: the grey scan.  Right panel: starts as the same grey and fades to colour (colour_delay_s, colour_fade_s).
    Slots: colour (main; camera `camera`), grey (optional aligned scan; when absent the grey is the desaturated colour image)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key, self.gkey = self.slot_asset("colour"), self.slot_asset("grey")
        self.cam = cam_of(shot, ctx, "camera")

    def render(self, t):
        ctx, p = self.ctx, self.p
        tt = t - self.t0
        w, h, y = int(p["panel_w_px"]), int(p["panel_h_px"]), int(p["panel_y_px"])
        xl, xr = int(p["left_x_px"]), int(p["right_x_px"])
        f = backdrop(ctx.w, ctx.h).copy()
        a = panel(ctx, self.key, self.cam, t, w, h)
        g = aligned_view(ctx, self.key, self.gkey, self.cam, t, w, h) if self.gkey else H.gray(a)
        put(f, xl, y, g)
        put(f, xr, y, blend(g, a, ramp(tt, float(p["colour_delay_s"]), float(p["colour_fade_s"]))))
        cy = int(p["caption_y_px"])
        if p["caption_left"]:
            caption(ctx, p["caption_left"], None, xl + w // 2, cy, 30, 6).apply(f)
        if p["caption_right"]:
            caption(ctx, p["caption_right"], None, xr + w // 2, cy, 30, 6).apply(f)
        return f

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 800 / (0.3 * a["h"]))
        return d


# ============================================================================================ CMP-02
@technique("CMP-02", "base")
class StagesVsFinished(BaseRenderer):
    """A column of `stages` small panels at the left (they appear one after the other) and the finished picture large beside it.

    Slots: finished (main, camera `finished_camera`), stage_1..stage_6 (optional real stage images, cover-fitted).  A stage
    without a slot is DERIVED from `finished` seen through `stage_camera` at derive_px x derive_px: stage_blur (px sigma, list),
    stage_grey (1 = desaturate) and stage_gain (brightness) are comma lists with one entry per stage.  Stage i appears at
    stage_delay_s + i * stage_step_s over stage_fade_s.  The stage camera is sampled at the shot start (stage tiles are static)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("finished")
        self.n = int(self.p["stages"])
        self.skeys = [self.slot_asset("stage_%d" % i) for i in range(1, self.n + 1)]
        self.fcam = cam_of(shot, ctx, "finished_camera")
        self.scam = cam_of(shot, ctx, "stage_camera")

    def _stage(self, i):
        ctx, p = self.ctx, self.p
        sz = int(p["stage_size_px"])
        k = self.skeys[i]
        if k:
            return ctx.cached(("t1stage", ctx.asset_path(k), sz), lambda: panel(ctx, k, None, 0, sz, sz))
        dpx = int(p["derive_px"])
        sig, grey, gain = floats(p["stage_blur"], self.n), floats(p["stage_grey"], self.n), floats(p["stage_gain"], self.n, 1.0)
        cam = self.scam.at(self.t0) if self.scam else None
        def build():
            img = ctx.image(self.key)
            cx, cy, z = cam if cam else (img.w / 2, img.h / 2, max(dpx / img.w, dpx / img.h))
            c = img.view(cx, cy, z, dpx, dpx)[0].astype(np.float32)
            if grey[i] >= 0.5:
                c = H.gray(c)
            if sig[i] > 0:
                c = cv2.GaussianBlur(c, (0, 0), sig[i])
            return cv2.resize(c * gain[i], (sz, sz), interpolation=cv2.INTER_AREA)
        return ctx.cached(("t1stage", ctx.asset_path(self.key), dpx, sz, i, cam, sig[i], grey[i], gain[i]), build)

    def render(self, t):
        ctx, p = self.ctx, self.p
        tt = t - self.t0
        f = backdrop(ctx.w, ctx.h).copy()
        sz, pitch, x0, y0 = int(p["stage_size_px"]), int(p["stage_pitch_px"]), int(p["stage_x_px"]), int(p["stage_y_px"])
        for i in range(self.n):
            a = ramp(tt, float(p["stage_delay_s"]) + float(p["stage_step_s"]) * i, float(p["stage_fade_s"]))
            if a <= 0:
                continue
            y = y0 + i * pitch
            put(f, x0, y, self._stage(i), a)
        bx0, by0, bx1, by1 = [int(v) for v in p["finished_box"]]
        put(f, bx0, by0, panel(ctx, self.key, self.fcam, t, bx1 - bx0, by1 - by0))
        return f

    def view(self, t):
        return None

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["finished_camera"] = static_cam(cx, cy, 1000 / min(a["w"], a["h"]) * 1.2)
            d["stage_camera"] = static_cam(cx, cy, 600 / min(a["w"], a["h"]) * 1.8)
        return d


# ============================================================================================ CMP-03
@technique("CMP-03", "base")
class ColourVersions(BaseRenderer):
    """Several versions of one picture side by side (panels appear left to right).

    `versions` is a comma list of treatments (white, sepia, warm, grey, contrast, none/colour), one per panel (2..5).
    Slots: image (the colour version, camera `camera`), version_1..version_5 (optional aligned alternative images; the same camera
    is applied scaled to their size).  Panel i fades in at delay_s + i * step_s over fade_s."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        self.cam = cam_of(shot, ctx, "camera")
        self.vers = [s.strip() for s in str(self.p["versions"]).split(",") if s.strip()]
        self.vkeys = [self.slot_asset("version_%d" % (i + 1)) or self.key for i in range(len(self.vers))]

    def render(self, t):
        ctx, p = self.ctx, self.p
        tt = t - self.t0
        f = backdrop(ctx.w, ctx.h).copy()
        w, h, y, x0, pitch = int(p["panel_w_px"]), int(p["panel_h_px"]), int(p["panel_y_px"]), int(p["x0_px"]), int(p["pitch_px"])
        for i, (v, k) in enumerate(zip(self.vers, self.vkeys)):
            al = ramp(tt, float(p["delay_s"]) + float(p["step_s"]) * i, float(p["fade_s"]))
            if al <= 0:
                continue
            im = aligned_view(ctx, self.key, k, self.cam, t, w, h)
            x = x0 + i * pitch
            put(f, x, y, np.clip(treat(im, v), 0, 255), al)
        return f

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 900 / a["h"] * 1.7)
        return d


# ============================================================================================ CMP-04
@technique("CMP-04", "base")
class ColourBlocks(BaseRenderer):
    """The detail (camera `camera`) at the left and, at the right, the same view reduced to a coarse block mosaic whose block count
    grows from blocks_start to blocks_end (columns; rows follow the panel aspect) starting at grow_delay_s over grow_s."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        self.cam = cam_of(shot, ctx, "camera")

    def render(self, t):
        ctx, p = self.ctx, self.p
        tt = t - self.t0
        f = backdrop(ctx.w, ctx.h).copy()
        w, h, y, xl, xr = int(p["panel_w_px"]), int(p["panel_h_px"]), int(p["panel_y_px"]), int(p["left_x_px"]), int(p["right_x_px"])
        a = panel(ctx, self.key, self.cam, t, w, h)
        put(f, xl, y, a)
        b0, b1 = float(p["blocks_start"]), float(p["blocks_end"])
        nb = int(b0 + (b1 - b0) * ramp(tt, float(p["grow_delay_s"]), float(p["grow_s"])))
        nb = max(1, nb)
        nr = max(1, int(round(nb * h / w)))
        small = cv2.resize(a, (nb, nr), interpolation=cv2.INTER_AREA)
        put(f, xr, y, cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST))
        return f

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 900 / a["h"] * 3.5)
        return d


# ============================================================================================ CMP-05 / X-CMP-02 helpers
def _line(f, x, col, px, alpha=1.0):
    if alpha <= 0:
        return f
    if alpha >= 1:
        cv2.line(f, (x, 0), (x, f.shape[0]), col, px, cv2.LINE_AA)
        return f
    g = f.copy()
    cv2.line(g, (x, 0), (x, f.shape[0]), col, px, cv2.LINE_AA)
    return f * (1 - alpha) + g * alpha


@technique("CMP-05", "base")
class TwoStatesWipe(BaseRenderer):
    """Two aligned states of one scene full frame; a vertical boundary sweeps right (from_pct -> to_pct of the width, inout_sine,
    starting at wipe_delay_s over wipe_s); left of it state_b is shown, right of it state_a.  A line marks the boundary.
    Camera `camera` is in the pixels of state_a; state_b gets the same view scaled by the size ratio."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.ka, self.kb = self.slot_asset("state_a"), self.slot_asset("state_b")
        self.cam = cam_of(shot, ctx, "camera")

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        a = panel(ctx, self.ka, self.cam, t, W, Hh)
        b = aligned_view(ctx, self.ka, self.kb, self.cam, t, W, Hh)
        f0, f1 = float(p["from_pct"]), float(p["to_pct"])
        x = int(W * (f0 + (f1 - f0) * ease("inout_sine", (tt - float(p["wipe_delay_s"])) / float(p["wipe_s"]))))
        f = a.copy()
        f[:, :x] = b[:, :x]
        return _line(f, x, hexbgr(p["line_color"]), int(p["line_px"]))

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.ka), self.ka)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 1920 / a["w"] * 0.8)
        return d


@technique("X-CMP-02", "base")
class WipeCompare(BaseRenderer):
    """New (no reel segment).  state_a (colour) fills the frame.  After start_delay_s a second version (state_b, optionally
    treated: grey, sepia ...) enters from `from_edge`: a vertical boundary sweeps from that edge to covering `split_pct` of the
    width (wipe_s, inout_sine; the content does not move, it is revealed).  The two versions are held side by side for
    hold_split_s, then state_b dissolves back into state_a over end_dissolve_s (the boundary line fades with it) and the frame
    ends on state_a.  state_b is aligned to state_a (same camera scaled)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.ka, self.kb = self.slot_asset("state_a"), self.slot_asset("state_b")
        self.cam = cam_of(shot, ctx, "camera")

    def phases(self, tt):
        """(boundary x fraction of the width covered by b, dissolve 0..1)."""
        p = self.p
        d0, ws, hs, ed = float(p["start_delay_s"]), float(p["wipe_s"]), float(p["hold_split_s"]), float(p["end_dissolve_s"])
        cov = float(p["split_pct"]) * ease("inout_sine", (tt - d0) / ws)
        return cov, ramp(tt, d0 + ws + hs, ed, "inout_sine")

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        a = panel(ctx, self.ka, self.cam, t, W, Hh)
        cov, dis = self.phases(tt)
        if cov <= 0 or dis >= 1:
            return a
        b = treat(aligned_view(ctx, self.ka, self.kb, self.cam, t, W, Hh), p["state_b_treatment"])
        x = int(round(W * cov))
        right = p["from_edge"] == "right"
        f = a.copy()
        sl = slice(W - x, W) if right else slice(0, x)
        f[:, sl] = a[:, sl] * dis + b[:, sl] * (1 - dis) if dis > 0 else b[:, sl]
        bx = W - x if right else x
        return _line(f, bx, hexbgr(p["line_color"]), int(p["line_px"]), 1.0 - dis)

    def view(self, t):
        if self.cam is None:
            return None
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.ka), self.ka)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w"):
            cx, cy = region_xy(a, context)
            d["camera"] = static_cam(cx, cy, 0.94 * 1080 / a["h"] * (1 if a["w"] * 1080 > a["h"] * 1920 else 1))
        return d


# ============================================================================================ X-CMP-01
@technique("X-CMP-01", "base")
class SwapSplit(BaseRenderer):
    """New.  Two panels (LAY-01 geometry).  The anchor picture stays in one panel (anchor_side; matte, or cover) while the other
    panel shows swap_1..swap_N in turn, each for seconds_per_swap (the last one holds).  swap_transition: cut, dissolve
    (dissolve_s) or slide (slide_s, the new image enters from the outer edge).  Each swap image is cover-fitted and pushes in
    by swap_push_pct over its time on screen (swap_focus: optional list of focus points in source px, centre when missing).
    anchor_push grows the anchor camera by anchor_push_pct over the shot.  Captions: anchor_caption (+_sub) and the lines lists
    swap_captions / swap_subs (one entry per swap) under their panels."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.akey = self.slot_asset("anchor")
        self.swaps = [self.slot_asset("swap_%d" % i) for i in range(1, 7)]
        self.swaps = [k for k in self.swaps if k]
        self.acam = cam_of(shot, ctx, "camera_anchor")
        self.d = max(self.t1 - self.t0, 1e-6)
        self.caps = as_lines(self.p["swap_captions"])
        self.subs = as_lines(self.p["swap_subs"])
        self.focus = self.p["swap_focus"] or []

    def _swap_img(self, i, t, pw, ph):
        ctx, p = self.ctx, self.p
        k = self.swaps[i]
        img = ctx.image(k)
        fx, fy = self.focus[i] if i < len(self.focus) and self.focus[i] is not None else (img.w / 2, img.h / 2)
        z = max(pw / img.w, ph / img.h) * (1 + float(p["swap_push_pct"]) / 100.0 * max(0.0, (t - self.t0) - i * float(p["seconds_per_swap"])) / float(p["seconds_per_swap"]))
        # keep the view inside the image
        hw, hh = pw / z / 2, ph / z / 2
        fx, fy = min(max(fx, hw), img.w - hw), min(max(fy, hh), img.h - hh)
        return img.view(fx, fy, z, pw, ph)[0].astype(np.float32)

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, Hh = ctx.w, ctx.h
        tt = t - self.t0
        pw, ph, py, xl, xr = int(p["panel_w_px"]), int(p["panel_h_px"]), int(p["panel_y_px"]), int(p["left_x_px"]), int(p["right_x_px"])
        f = backdrop(W, Hh).copy()
        left_anchor = p["anchor_side"] == "left"
        ax, sx = (xl, xr) if left_anchor else (xr, xl)
        # anchor
        img = ctx.image(self.akey)
        if self.acam is not None:
            cx, cy, z = self.acam.at(t)
        else:
            cx, cy, z = img.w / 2, img.h / 2, (0.94 * min(pw / img.w, ph / img.h) if p["anchor_fit"] == "matte" else max(pw / img.w, ph / img.h))
        if p["anchor_push"]:
            z *= 1 + float(p["anchor_push_pct"]) / 100.0 * tt / self.d
        put(f, ax, py, compose_matte(img, cx, cy, z, pw, ph) if p["anchor_fit"] == "matte" else img.view(cx, cy, z, pw, ph)[0].astype(np.float32))
        # swap panel
        n = len(self.swaps)
        sps = float(p["seconds_per_swap"])
        i = min(int(max(tt, 0) // sps), n - 1)
        cur = self._swap_img(i, t, pw, ph)
        u = tt - i * sps
        mode = p["swap_transition"]
        dur = float(p["dissolve_s"] if mode == "dissolve" else p["slide_s"])
        env = 1.0
        panel_img = cur
        if i > 0 and mode != "cut" and 0 <= u < dur:
            old = self._swap_img(i - 1, t, pw, ph)
            env = ease("inout_sine" if mode == "dissolve" else "out_cubic", u / dur)
            if mode == "dissolve":
                panel_img = blend(old, cur, env)
            else:
                shift = int(round(pw * (1 - env)))
                panel_img = old.copy()
                if left_anchor:                        # swap panel is on the right: new image enters from the right edge
                    panel_img[:, shift:] = cur[:, :pw - shift]
                else:
                    panel_img[:, :pw - shift] = cur[:, shift:]
        put(f, sx, py, panel_img)
        # captions
        cy = py + ph + 52
        if p["anchor_caption"]:
            caption(ctx, p["anchor_caption"], p["anchor_caption_sub"] or None, ax + pw // 2, cy, 30, 2).apply(f, ramp(tt, float(p["caption_delay_s"]), 0.2))
        def cap(j):
            return caption(ctx, self.caps[j], self.subs[j] if j < len(self.subs) and self.subs[j] else None, sx + pw // 2, cy, 30, 2) if j < len(self.caps) and self.caps[j] else None
        c_cur = cap(i)
        c_old = cap(i - 1) if i > 0 and mode != "cut" and 0 <= u < dur else None
        if c_old is not None:
            c_old.apply(f, 1 - env)
        if c_cur is not None:
            c_cur.apply(f, ramp(tt, float(p["caption_delay_s"]), 0.2) * env)
        return f

    def view(self, t):
        return None

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        d["anchor_caption"] = (a.get("title") or "").upper()
        d["anchor_caption_sub"] = ", ".join(x for x in (a.get("artist"), a.get("year")) if x).upper()
        return d


# ============================================================================================ registry entries (generated into the patch)
_PANEL = lambda w, h, y, xl, xr: [pdef("panel_w_px", "number", w, 100, 1900, "px"), pdef("panel_h_px", "number", h, 100, 1080, "px"),
                                  pdef("panel_y_px", "number", y, 0, 1000, "px"), pdef("left_x_px", "number", xl, 0, 1900, "px"),
                                  pdef("right_x_px", "number", xr, 0, 1900, "px")]
SPECS = {
    "CMP-01": dict(
        slots=[("colour", "image", True, True), ("grey", "image", False, False)],
        params=[pdef("camera", "camera", None)] + _PANEL(930, 800, 140, 20, 970)
               + [pdef("colour_delay_s", "number", 1.0, 0, 10, "s"), pdef("colour_fade_s", "number", 0.8, 0, 3, "s"),
                  pdef("caption_left", "string", "GREYSCALE"), pdef("caption_right", "string", "COLOUR"),
                  pdef("caption_y_px", "number", 1000, 0, 1080, "px")]),
    "CMP-02": dict(
        slots=[("finished", "image", True, True)] + [("stage_%d" % i, "image", False, False) for i in range(1, 7)],
        params=[pdef("stages", "number", 3, 2, 6, "count"), pdef("finished_camera", "camera", None), pdef("stage_camera", "camera", None),
                pdef("finished_box", "box", [520, 40, 1520, 1040], unit="canvas px"),
                pdef("stage_size_px", "number", 320, 60, 600, "px"), pdef("stage_pitch_px", "number", 340, 60, 700, "px"),
                pdef("stage_x_px", "number", 80, 0, 1600, "px"), pdef("stage_y_px", "number", 40, 0, 800, "px"),
                pdef("stage_delay_s", "number", 0.5, 0, 10, "s"), pdef("stage_step_s", "number", 0.9, 0, 5, "s"),
                pdef("stage_fade_s", "number", 0.5, 0, 3, "s"), pdef("derive_px", "number", 600, 100, 1200, "px"),
                pdef("stage_blur", "string", "14,5,0"), pdef("stage_grey", "string", "1,0,0"), pdef("stage_gain", "string", "0.9,1,1")]),
    "CMP-03": dict(
        slots=[("image", "image", True, True)] + [("version_%d" % i, "image", False, False) for i in range(1, 6)],
        params=[pdef("camera", "camera", None), pdef("versions", "string", "white,sepia,colour"),
                pdef("panel_w_px", "number", 610, 100, 1900, "px"), pdef("panel_h_px", "number", 900, 100, 1080, "px"),
                pdef("panel_y_px", "number", 90, 0, 1000, "px"), pdef("x0_px", "number", 60, 0, 1800, "px"),
                pdef("pitch_px", "number", 620, 100, 1900, "px"), pdef("delay_s", "number", 0.3, 0, 10, "s"),
                pdef("step_s", "number", 0.6, 0, 5, "s"), pdef("fade_s", "number", 0.5, 0, 3, "s")]),
    "CMP-04": dict(
        slots=[("image", "image", True, True)],
        params=[pdef("camera", "camera", None)] + _PANEL(900, 900, 90, 40, 980)
               + [pdef("blocks_start", "number", 8, 2, 64, "count"), pdef("blocks_end", "number", 32, 4, 128, "count"),
                  pdef("grow_delay_s", "number", 0.8, 0, 10, "s"), pdef("grow_s", "number", 2.0, 0, 10, "s")]),
    "CMP-05": dict(
        slots=[("state_a", "image", True, True), ("state_b", "image", True, False)],
        params=[pdef("camera", "camera", None), pdef("wipe_s", "number", 3.5, 0.5, 8, "s"), pdef("wipe_delay_s", "number", 1.0, 0, 10, "s"),
                pdef("from_pct", "number", 0.1, 0, 1, "fraction"), pdef("to_pct", "number", 0.9, 0, 1, "fraction"),
                pdef("line_px", "number", 3, 0, 20, "px"), pdef("line_color", "color", "#ffffff")]),
    "X-CMP-01": dict(
        slots=[("anchor", "image", True, True)] + [("swap_%d" % i, "image", i == 1, False) for i in range(1, 7)],
        params=[pdef("anchor_side", "enum", "left", values=["left", "right"]),
                pdef("swap_transition", "enum", "cut", values=["cut", "dissolve", "slide"]),
                pdef("seconds_per_swap", "number", 2.5, 1.0, 30, "s"), pdef("dissolve_s", "number", 0.5, 0.1, 3, "s"),
                pdef("slide_s", "number", 0.6, 0.1, 3, "s"), pdef("swap_push_pct", "number", 5, 0, 50, "%"),
                pdef("swap_focus", "points", None), pdef("anchor_fit", "enum", "matte", values=["matte", "cover"]),
                pdef("camera_anchor", "camera", None), pdef("anchor_push", "bool", False), pdef("anchor_push_pct", "number", 4, 0, 50, "%"),
                pdef("anchor_caption", "string", ""), pdef("anchor_caption_sub", "string", ""),
                pdef("swap_captions", "lines", None), pdef("swap_subs", "lines", None), pdef("caption_delay_s", "number", 0.3, 0, 10, "s")]
               + _PANEL(900, 740, 36, 50, 970)),
    "X-CMP-02": dict(
        slots=[("state_a", "image", True, True), ("state_b", "image", True, False)],
        params=[pdef("camera", "camera", None), pdef("from_edge", "enum", "right", values=["left", "right"]),
                pdef("start_delay_s", "number", 0.4, 0, 10, "s"), pdef("wipe_s", "number", 2.5, 0.5, 8, "s"),
                pdef("split_pct", "number", 0.5, 0.1, 0.9, "fraction"), pdef("hold_split_s", "number", 1.6, 0, 6, "s"),
                pdef("end_dissolve_s", "number", 1.0, 0, 3, "s"), pdef("state_b_treatment", "enum", "none", values=TREATMENTS),
                pdef("line_px", "number", 3, 0, 20, "px"), pdef("line_color", "color", "#ffffff")]),
}
