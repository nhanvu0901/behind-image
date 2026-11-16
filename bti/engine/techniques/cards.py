"""Cards (kind `card`): chapter card on black (X-CARD-01) and the main title card on blurred artwork (X-CARD-02).

Times in the params are relative to the shot start.  Lifted from build_v2.py card_shot / _card_layer / title_card_shot.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from .. import vfx
from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import blurred_bg, hline, ramp, text_layer, window


@technique("X-CARD-01", "card")
class ChapterCard(BaseRenderer):
    """Text low on a plain background; it pops in at text_in_delay_s and leaves at text_leave_at_s."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        text, trk = p["title"], int(p["tracking_px"])
        max_w = float(p["text_width_pct"]) / 100.0 * ctx.w
        ypos = int(ctx.h * float(p["text_y_pct"]) / 100.0)

        def build():
            size = int(p["size_px"])
            d = ImageDraw.Draw(Image.new("L", (10, 10)))
            while True:                                  # shrink until the tracked text fits the width budget
                ft = vfx.font("reg", size)
                w = sum(d.textlength(c, font=ft) for c in text) + trk * (len(text) - 1)
                if w <= max_w or size < 30:
                    break
                size -= 2
            return text_layer(text, ctx.w // 2, ypos, size, "reg", trk, shadow=False, w=ctx.w, h=ctx.h)
        self.layer = ctx.layer(("card", text, trk, max_w, ypos, int(p["size_px"])), build)
        self.bg = np.array(hex_to_bgr(p["background"]), np.float32)

    def render(self, t):
        p = self.p
        f = np.zeros((self.ctx.h, self.ctx.w, 3), np.float32)
        if self.bg.any():
            f += self.bg
        e = window(t, self.t0 + float(p["text_in_delay_s"]), self.t0 + float(p["text_leave_at_s"]), float(p["text_pop_s"]), float(p["text_fade_out_s"]))
        return self.layer.apply(f, e)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        for k, sk in (("text_in_delay_s", "chapter_text_in_delay_s"), ("text_pop_s", "chapter_text_pop_s"), ("text_leave_at_s", "chapter_text_leave_at_s"),
                      ("text_fade_out_s", "chapter_text_fade_out_s"), ("text_y_pct", "chapter_text_y_pct"), ("text_width_pct", "chapter_text_width_pct")):
            d[k] = bundle.sv("cards", sk, d[k])
        d["title"] = (context.get("title") or context.get("text") or d["title"]).upper()
        return d


@technique("X-CARD-02", "card")
class TitleCard(BaseRenderer):
    """Title, artist and year over a heavily blurred, darkened copy of the artwork (slot `background`)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        key = self.slot_asset("background")
        sigma, dark = float(p["blur_sigma"]), float(p["darken"])
        path = ctx.asset_path(key)
        self.bg = ctx.cached(("tcbg", path, sigma, dark), lambda: blurred_bg(ctx.raw_image_reduced(key, 4), W, H, sigma=sigma, dark=dark))
        mk = lambda text, y, size, trk: ctx.layer(("tc", text, y, size, trk), lambda: text_layer(text, W // 2, int(H * y), size, "reg", trk, w=W, h=H))
        self.l1 = mk(p["title"], .455, 78, 11)
        self.l2 = mk(p["artist"], .585, 38, 10)
        self.l3 = mk(p["year"], .65, 34, 10)

    def render(self, t):
        W, H = self.ctx.w, self.ctx.h
        e = ramp(t, self.t0, float(self.p["fade_in_s"]), "out_quad")
        f = self.bg.copy()
        self.l1.apply(f, e)
        hline(f, W // 2, int(H * .535), 200, 2, .75 * e)
        self.l2.apply(f, e)
        self.l3.apply(f, e)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a = context.get("asset") or {}
        d["title"] = (context.get("title") or a.get("title") or d["title"]).upper()
        d["artist"] = (context.get("artist") or a.get("artist") or d["artist"]).upper()
        d["year"] = str(context.get("year") or a.get("year") or d["year"])
        return d
