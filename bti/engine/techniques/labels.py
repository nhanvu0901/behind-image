"""Text overlays: label strips (X-ANN-01, X-ANN-02), recap / name labels (X-ANN-03, STATIC-08), year captions (STATIC-09).

Timing semantics (overlay start .. end):
  label strip   fades in over pop_in_s from start, fades out over fade_out_s ending at end      (vfx.window)
  screen text   same, with fade_in_s / fade_out_s
  year caption  same, with fade_in_s / fade_out_s
Lifted from build_v2.py Lbl, ScreenText, Years.
"""
from __future__ import annotations

from ..base import OverlayRenderer
from ..registry import technique
from ..vfx import label_layer, text_layer, window


def _strip_geometry(p, H):
    top, bottom = float(p["strip_y_top_pct"]), float(p["strip_y_bottom_pct"])
    return top / 100.0, int(round((bottom - top) * H / 100.0))


@technique("X-ANN-01", "overlay")
@technique("X-ANN-02", "overlay")
class LabelStrip(OverlayRenderer):
    """Dark translucent strip with a white caps title (and a smaller second line for X-ANN-02)."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        title = p["text"] if tid == "X-ANN-01" else p["title"]
        sub = p["artist_year"] if tid == "X-ANN-02" else None
        if p["case"] == "upper":
            title, sub = title.upper(), (sub.upper() if sub else None)
        y0, h = _strip_geometry(p, ctx.h)
        size = int(p["size_px"])
        sub_size = int(round(size * float(p.get("second_line_scale") or 0.55)))
        key = ("lab", title, sub, y0, h, float(p["text_x_pct"]), size, sub_size, float(p["strip_opacity"]), float(p["right_fade_pct"]))
        self.layer = ctx.layer(key, lambda: label_layer(title, sub, y0=y0, h=h, x_text=float(p["text_x_pct"]) / 100.0, w=ctx.w, hh=ctx.h,
                                                        opacity=float(p["strip_opacity"]), fade_frac=float(p["right_fade_pct"]) / 100.0,
                                                        size=size, sub_size=sub_size))

    def apply(self, f, t, view):
        return self.layer.apply(f, window(t, self.t0, self.t1, float(self.p["pop_in_s"]), float(self.p["fade_out_s"])))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        sty = lambda k, dv: bundle.sv("label_strip", k, dv)
        d.update(strip_y_top_pct=sty("y_top_pct", 79.4), strip_y_bottom_pct=sty("y_bottom_pct", 93.3), strip_opacity=sty("opacity", 0.8),
                 text_x_pct=sty("text_x_pct", 7.0), right_fade_pct=sty("right_fade_pct_of_width", 20), pop_in_s=sty("pop_in_s", 0.1),
                 fade_out_s=sty("fade_out_s", 0.2), size_px=sty("first_line_px_1080p", 58))
        a = context.get("asset") or {}
        if tid == "X-ANN-01":
            d["text"] = context.get("text") or (context.get("region") if isinstance(context.get("region"), str) else None) or d["text"]
        else:
            d["title"] = context.get("title") or a.get("title") or d["title"]
            ay = ", ".join(x for x in (a.get("artist"), a.get("year")) if x)
            d["artist_year"] = context.get("artist_year") or ay or d["artist_year"]
        return d


@technique("STATIC-08", "overlay")
@technique("X-ANN-03", "overlay")
class ScreenText(OverlayRenderer):
    """Plain white text with a soft shadow, glued to a source point (`at`) or fixed on screen (`screen`)."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        text, size, trk = p["text"], int(p["size_px"]), int(p["tracking_px"])
        self.layer = ctx.layer(("st", text, size, trk), lambda: text_layer(text, ctx.w // 2, ctx.h // 2, size, "reg", trk, shadow=True, w=ctx.w, h=ctx.h))

    def apply(self, f, t, view):
        p = self.p
        e = window(t, self.t0, self.t1, float(p["fade_in_s"]), float(p["fade_out_s"]))
        if e <= 0:
            return f
        if p.get("at") is not None:
            if view is None:
                return f
            x, y = view.to_screen(*self.ctx.point(p["at"], view.asset_key))
        elif p.get("screen") is not None:
            x, y = p["screen"]
        else:
            return f
        return self.layer.apply(f, e, x - self.ctx.w // 2, y - self.ctx.h // 2)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        d["size_px"] = 46 if tid == "X-ANN-03" else 34
        if context.get("text"):
            d["text"] = context["text"]
        if context.get("region") is not None:
            d["at"] = context["region"]
        return d


@technique("STATIC-09", "overlay")
class YearText(OverlayRenderer):
    """Large centred caption (a year) with a small line under it, at a horizontal screen position."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        x = int(ctx.w * float(p["x_pct"]) / 100.0)
        y = int(ctx.h * float(p["y_pct"]) / 100.0)
        text, sub = p["year"], (p["sub"] or None)
        size, trk, ssz = int(p["size_px"]), int(p["tracking_px"]), int(p["sub_px"])
        self.layer = ctx.layer(("yr", text, sub, x, y, size, trk, ssz),
                               lambda: text_layer(text, x, y, size, "reg", trk, sub=sub, subsize=ssz, w=ctx.w, h=ctx.h))

    def apply(self, f, t, view):
        self.layer.apply(f, window(t, self.t0, self.t1, float(self.p["fade_in_s"]), float(self.p["fade_out_s"])))
        return f


@technique("STATIC-02", "overlay")
class SourceLabel(OverlayRenderer):
    """Small source line at the bottom left, e.g. "Jan van Eyck, The Arnolfini Portrait, 1434" (the README's worked example).

    Timing: fades in over fade_in_s from the overlay start, out over fade_out_s ending at the overlay end.
    Lifted from build_reel.py st02 / _srclabel.
    """

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        text, size = p["text"], int(p["size_px"])
        x, y = int(p["margin_left_px"]), ctx.h - int(p["margin_bottom_px"]) - (size + 12)

        def build():
            from PIL import Image, ImageDraw
            import numpy as np
            from ..vfx import Layer, font
            ft = font("reg", size)
            w = int(ImageDraw.Draw(Image.new("L", (10, 10))).textlength(text, font=ft)) + 12
            im = Image.new("RGBA", (max(w, 1), size + 12), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((0, 2), text, font=ft, fill=(255, 255, 255, 235))
            return Layer(np.array(im), x, y)
        self.layer = ctx.layer(("srclabel", text, size, x, y), build)       # key = every input; size and font are added by Ctx.layer

    def apply(self, f, t, view):
        return self.layer.apply(f, window(t, self.t0, self.t1, float(self.p["fade_in_s"]), float(self.p["fade_out_s"])))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a = context.get("asset") or {}
        parts = [a.get("artist"), a.get("title"), a.get("year")]
        d["text"] = context.get("text") or ", ".join(x for x in parts if x) or d["text"]
        return d
