"""Two-panel comparison (LAY-01) with a slide-in of the right panel and synchronised camera moves.

Lifted from build_v2.py split_shot.  Panels are `panel_w_px` x `panel_h_px` at `panel_y_px`; the left panel is matted
(`compose_matte`), the right one covers its panel.  Each side has its own camera (params camera_left / camera_right, keys in
source pixels of its own image).  The right panel slides in from the right edge over slide_s seconds starting
slide_delay_s (+0.05 s) after the shot start; the left caption appears at slide_delay_s, the right one 0.75 s later.
"""
from __future__ import annotations

import numpy as np

from ..base import BaseRenderer, View
from ..registry import technique
from ..vfx import Cam, backdrop, compose_matte, ease, put, ramp, text_layer
from .camera import _key, camera_keys, fit_zoom


@technique("LAY-01", "base")
class TwoPanel(BaseRenderer):
    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.kl, self.kr = self.slot_asset("left"), self.slot_asset("right")
        self.pw, self.ph, self.py = int(p["panel_w_px"]), int(p["panel_h_px"]), int(p["panel_y_px"])
        self.xl, self.xr = int(p["left_x_px"]), int(p["right_x_px"])
        wl, hl = ctx.asset_size(self.kl)
        wr, hr = ctx.asset_size(self.kr)
        kl = camera_keys(shot, ctx, "camera_left") or [(self.t0, wl / 2, hl / 2, 0.94 * self.ph / hl, "linear")]
        kr = camera_keys(shot, ctx, "camera_right") or [(self.t0, wr / 2, hr / 2, max(self.pw / wr, self.ph / hr), "linear")]
        self.camL, self.camR = Cam(kl), Cam(kr)
        W = ctx.w
        cap = lambda text, sub, x, size: ctx.layer(("lay01cap", text, sub, x, self.py + self.ph + 52, size),
                                                   lambda: text_layer(text, x, self.py + self.ph + 52, size, "reg", 2, sub=sub or None, subsize=26, w=W, h=ctx.h))
        self.capL = cap(p["caption_left"], p["caption_left_sub"], self.xl + self.pw // 2, 30)
        self.capR = cap(p["caption_right"], p["caption_right_sub"], self.xr + self.pw // 2, 30)

    def view(self, t):
        cx, cy, z = self.camL.at(t)
        return View(cx, cy, z, self.ctx.image(self.kl), self.kl)

    def render(self, t):
        W, H, p = self.ctx.w, self.ctx.h, self.p
        pw, ph, py, xl, xr = self.pw, self.ph, self.py, self.xl, self.xr
        f = backdrop(W, H).copy()
        cx, cy, z = self.camL.at(t)
        put(f, xl, py, compose_matte(self.ctx.image(self.kl), cx, cy, z, pw, ph))
        t_slide = self.t0 + float(p["slide_delay_s"])
        sl = ease("out_cubic", (t - t_slide - .05) / float(p["slide_s"]))
        x = int(round(W + 10 - (W + 10 - xr) * sl))
        cx, cy, z = self.camR.at(t)
        right = self.ctx.image(self.kr).view(cx, cy, z, pw, ph)[0].astype(np.float32)
        put(f, x, py, right)
        self.capL.apply(f, ramp(t, t_slide, .2))
        self.capR.apply(f, ramp(t, t_slide + .75, .25))
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a, b = context.get("asset") or {}, context.get("asset_right") or {}
        ph = d["panel_h_px"]
        if a.get("w"):
            z = 0.94 * ph / a["h"]
            d["camera_left"] = [_key(0.0, a["w"] / 2, a["h"] / 2, z), _key(1.0, a["w"] / 2, a["h"] / 2, z)]
            d["caption_left"] = (a.get("title") or "").upper()
            d["caption_left_sub"] = ", ".join(x for x in (a.get("artist"), a.get("year")) if x).upper()
        if b.get("w"):
            z = max(d["panel_w_px"] / b["w"], ph / b["h"])
            d["camera_right"] = [_key(0.0, b["w"] / 2, b["h"] / 2, z), _key(1.0, b["w"] / 2, b["h"] / 2, z)]
            d["caption_right"] = (b.get("title") or "").upper()
            d["caption_right_sub"] = ", ".join(x for x in (b.get("artist"), b.get("year")) if x).upper()
        return d
