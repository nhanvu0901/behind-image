"""Camera shots over the matte that need more than one layer or a label: CAM-02 (foreground cut-out against a background, each with its own
camera track) and CAM-06 (hold on the matte, then a label appears).

CAM-02 coordinates: the foreground camera is in pixels of the `foreground` image, the background camera in pixels of the `background`
image; the cut-out is the `mask` slot (aligned to the foreground).  `zoom_interp` is how zoom moves between two keys: linear (the
benchmark: zoom = z0 * (1 + k * p)) or log (the engine's other cameras).
CAM-06 timing: the label starts at label_delay_s from the shot start, pops in over label_pop_s, holds label_hold_s, fades over label_fade_out_s.
"""
from __future__ import annotations

import numpy as np

from .. import helpers as Hh
from ..base import BaseRenderer, View
from ..registry import technique
from ..vfx import compose_matte, label_layer, window
from . import _t2_common as C
from .camera import MatteShot


def _defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}


@technique("CAM-02", "base")
class LayerRelativeMotion(BaseRenderer):
    """background (matte-composed) with the masked foreground on top; the two layers follow separate camera tracks."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.fg, self.bg, self.mask = self.slot_asset("foreground"), self.slot_asset("background"), self.slot_asset("mask")
        self.fg_track = self._track("fg_camera", self.fg, float(p["fg_zoom"]))
        self.bg_track = self._track("bg_camera", self.bg, float(p["bg_zoom"]))

    def _track(self, name, key, ratio):
        keys = C.keys_from_param(self.shot, self.ctx, name)
        if keys is None:                                   # no explicit track: width-fit, centred, zoom pushed by `ratio` over the shot
            w, h = self.ctx.asset_size(key)
            z = max(self.ctx.w / w, self.ctx.h / h)
            keys = [(self.t0, w / 2, h / 2, z, self.p["easing"]), (self.t1, w / 2, h / 2, z * ratio, "linear")]
        return C.Track(keys, self.p["zoom_interp"])

    def view(self, t):
        cx, cy, z = self.fg_track.at(t)
        return View(cx, cy, z, self.ctx.image(self.fg), self.fg)

    def render(self, t):
        p, ctx = self.p, self.ctx
        bx, by, bz = self.bg_track.at(t)
        bg = compose_matte(ctx.image(self.bg), bx, by, bz, ctx.w, ctx.h, shadow=bool(p["shadow"]))
        fx, fy, fz = self.fg_track.at(t)
        fg = ctx.image(self.fg).view(fx, fy, fz, ctx.w, ctx.h)[0].astype(np.float32)
        m = Hh.mask_alpha(ctx, self.mask, fx, fy, fz, image_key=self.fg)
        return bg * (1 - m) + fg * m

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w") and a.get("h"):
            w, h = float(a["w"]), float(a["h"])
            z = max(1920.0 / w, 1080.0 / h)
            d["fg_camera"] = [C.cam_key_json(0.0, w / 2, h / 2, z, d["easing"]), C.cam_key_json(1.0, w / 2, h / 2, z * d["fg_zoom"])]
            d["bg_camera"] = [C.cam_key_json(0.0, w / 2, h / 2, z, d["easing"]), C.cam_key_json(1.0, w / 2, h / 2, z * d["bg_zoom"])]
        return d


@technique("CAM-06", "base")
class HoldAndLabel(MatteShot):
    """The picture held on the matte (camera as every matte shot; default: whole picture) and a label strip that pops in."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        title, sub = p["label_text"], p["label_sub"] or None
        if p["label_case"] in ("upper", "upper_all"):          # upper: the title only (benchmark); upper_all: the second line too
            title, sub = title.upper(), (sub.upper() if sub and p["label_case"] == "upper_all" else sub)
        y0, hh = float(p["strip_y_top_pct"]) / 100.0, int(p["strip_height_px"])
        size, ssize, x_pct = int(p["label_px"]), int(p["label_sub_px"]), float(p["text_x_pct"])
        op, rf = float(p["strip_opacity"]), float(p["right_fade_pct"])
        key = ("cam06lab", title, sub, y0, hh, size, ssize, x_pct, op, rf)
        self.layer = ctx.layer(key, lambda: label_layer(title, sub, y0=y0, h=hh, x_text=x_pct / 100.0, w=ctx.w, hh=ctx.h, opacity=op,
                                                        fade_frac=rf / 100.0, size=size, sub_size=ssize))

    def render(self, t):
        f = super().render(t)
        p = self.p
        t_on = self.t0 + float(p["label_delay_s"])
        env = window(t, t_on, t_on + float(p["label_hold_s"]), float(p["label_pop_s"]), float(p["label_fade_out_s"]))
        return self.layer.apply(f, env)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        sty = lambda k, dv: bundle.sv("label_strip", k, dv)
        top, bot = sty("y_top_pct", 79.4), sty("y_bottom_pct", 93.3)
        d.update(strip_y_top_pct=top, strip_height_px=int(round((bot - top) * 10.8)), strip_opacity=sty("opacity", 0.8), text_x_pct=sty("text_x_pct", 7.0),
                 right_fade_pct=sty("right_fade_pct_of_width", 20), label_px=sty("first_line_px_1080p", 58), label_sub_px=sty("second_line_px_1080p", 32),
                 label_pop_s=sty("pop_in_s", 0.1), label_hold_s=sty("hold_s", 3.2), label_fade_out_s=sty("fade_out_s", 0.2))
        a = context.get("asset") or {}
        d["label_text"] = context.get("title") or context.get("text") or a.get("title") or d["label_text"]
        ay = ", ".join(x for x in (a.get("artist"), a.get("year")) if x)
        d["label_sub"] = context.get("artist_year") or ay or d["label_sub"]
        if a.get("w") and a.get("h"):
            from .camera import fit_zoom
            h, w = float(a["h"]), float(a["w"])
            d["camera"] = [C.cam_key_json(0.0, w / 2, h / 2, fit_zoom(h)), C.cam_key_json(1.0, w / 2, h / 2, fit_zoom(h))]
        return d
