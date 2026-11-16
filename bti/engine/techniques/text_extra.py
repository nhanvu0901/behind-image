"""Text techniques ported from the reel: TXT-01 (chapter title card), TXT-02 (sliding italic lines), STATIC-04 (quote over image),
STATIC-05 (interviewee name tag).  All text is a storyboard param; fonts and colours are params with the reel's look as default.
These are the channel's own on-screen technique texts (titles, quotes, labels), never narration or subtitles.

Timing semantics
  TXT-01   card, times relative to the shot start: the title ramps in at text_in_delay_s over fade_in_s; if leave_at_s > 0 it fades out
           ending at leave_at_s (fade_out_s); the shot ends when the next shot starts.
  TXT-02   overlay, times relative to the overlay start; line i enters row_delay_s * i later and sits row_offset_px * i further back; the
           overlay ends at its end (dur) and the lines are simply cut (as in the reel). The base image is darkened by background_dim.
  STATIC-04 overlay: background dim (instant, or dim_in_s ramp) from the overlay start; the quote ramps in at delay_s over fade_in_s and fades
           out ending at the overlay end (fade_out_s, 0 = hard cut).
  STATIC-05 overlay: the strip pops in over pop_in_s at the overlay start and fades out ending at the overlay end (the reel's window()).
"""
from __future__ import annotations

import cv2
import numpy as np

from .. import vfx
from ..base import BaseRenderer, OverlayRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import blurred_bg, hline, label_layer, ramp, window
from . import _t3common as C
from ._t3common import param as P


def _bg_source(ctx, key):
    """Source for a blurred background: full resolution unless huge (blur of a 1/4-size copy is visually the same above 2x canvas)."""
    import os
    path = ctx.asset_path(key)
    w, h = ctx.asset_size(key)
    red = 1 if max(w, h) <= 2 * ctx.w else (2 if max(w, h) <= 4 * ctx.w else 4)

    def build():
        im = ctx.raw_image_reduced(key, red) if red > 1 else cv2.imread(path, cv2.IMREAD_COLOR)
        if im is None:
            raise FileNotFoundError(path)
        return im
    return ctx.cached(("t3bgsrc", path, os.stat(path).st_mtime_ns, red), build)


def _out_env(t, t1, fade_out):
    return 1.0 - ramp(t, t1 - fade_out, fade_out) if fade_out > 0 else (1.0 if t < t1 else 0.0)


# ----------------------------------------------------------------------------- TXT-01
@technique("TXT-01", "card")
class ChapterTitleBlur(BaseRenderer):
    """Title centred over a blurred, darkened artwork (slot `background`), or (variant white_card) brown text on a plain white card."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        self.white = p["variant"] == "white_card"
        text = str(p["title"] or "")
        if p["case"] == "upper":
            text = text.upper()
        trk = int(p["tracking_px"])
        kind = p["font_kind"]
        max_w = float(p["max_width_pct"]) / 100.0 * W
        cy = int(round(H * float(p["y_pct"]) / 100.0))
        col = C.hex_rgb(p["card_text_color"] if self.white else p["text_color"])
        lines = [l for l in text.split("\n")]
        size0 = int(p["size_px"])
        size = min([C.fit_size(l, kind, size0, trk, max_w) for l in lines] or [size0]) if text.strip() else size0
        shadow = bool(p["shadow"]) and not self.white
        rows = [{"text": l, "size": size, "kind": kind, "tracking": trk, "color": col} for l in lines]
        gap = float(p["line_gap"])
        self.layer = ctx.layer(("t3txt01", tuple(l["text"] for l in rows), size, kind, trk, col, cy, shadow, gap, C.serif_signature()),
                               lambda: C.block_layer(W, H, rows, W // 2, cy, shadow, gap))
        self.bg = None
        if self.white:
            self.flat = np.array(hex_to_bgr(p["card_color"]), np.float32)
        else:
            self.flat = np.zeros(3, np.float32)
            key = self.slot_asset("background")
            if key:
                sigma, dark = float(p["blur_sigma"]), float(p["darken"])
                self.bg = ctx.cached(("t3txt01bg", ctx.asset_path(key), sigma, dark), lambda: blurred_bg(_bg_source(ctx, key), W, H, sigma=sigma, dark=dark))

    def render(self, t):
        p = self.p
        H, W = self.ctx.h, self.ctx.w
        f = self.bg.copy() if self.bg is not None else np.zeros((H, W, 3), np.float32) + self.flat
        e = ramp(t, self.t0 + float(p["text_in_delay_s"]), float(p["fade_in_s"]), "linear")
        leave = float(p["leave_at_s"])
        if leave > 0:
            e = min(e, _out_env(t, self.t0 + leave, float(p["fade_out_s"])))
        if bool(p["rule"]):
            hline(f, W // 2, int(H * (float(p["y_pct"]) / 100.0 + 0.085)), int(p["rule_w_px"]), 2, .75 * e)
        return self.layer.apply(f, e)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a = C.asset_dict(context)
        d["title"] = str(context.get("title") or context.get("text") or a.get("title") or d["title"])
        return d


# ----------------------------------------------------------------------------- TXT-02
@technique("TXT-02", "overlay")
class SlidingText(OverlayRenderer):
    """Lines of large (italic) text sliding horizontally across the shot's image, which is darkened by background_dim."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        lines = [str(l) for l in (p["lines"] or []) if str(l).strip()]
        size, kind, trk = int(p["size_px"]), p["font_kind"], int(p["tracking_px"])
        col = C.hex_rgb(p["color"])
        self.rows = []
        for i, line in enumerate(lines):
            cy = int(round(H * (float(p["row_y_pct"]) + float(p["row_step_pct"]) * i) / 100.0))
            L = ctx.layer(("t3txt02", line, size, kind, trk, col, cy, bool(p["shadow"]), C.serif_signature()),
                          lambda line=line, cy=cy: C.block_layer(W, H, [{"text": line, "size": size, "kind": kind, "tracking": trk, "color": col}],
                                                                 W // 2, cy, bool(p["shadow"])))
            self.rows.append(L)

    def apply(self, f, t, view):
        p = self.p
        W = self.ctx.w
        tt = t - self.t0
        if t < self.t0 - 1e-6:
            return f
        g = float(p["background_dim"])
        if g != 1.0:
            f = f * g
        speed, x0 = float(p["speed_px_s"]), float(p["start_x_pct"]) / 100.0 * W
        ltr = p["direction"] == "left_to_right"
        for i, L in enumerate(self.rows):
            x = x0 - (tt - float(p["row_delay_s"]) * i) * speed - float(p["row_offset_px"]) * i     # right_to_left centre of row i
            if ltr != (bool(p["alternate"]) and i % 2 == 1):
                x = W - x
            f = L.apply(f, 1.0, int(x) - W // 2, 0)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        txt = context.get("text")
        if isinstance(txt, str) and txt.strip():
            d["lines"] = [l for l in txt.split("\n") if l.strip()]
        return d


# ----------------------------------------------------------------------------- STATIC-04
@technique("STATIC-04", "overlay")
class QuoteOverlay(OverlayRenderer):
    """A quotation (auto-wrapped to max_width_pct, optional attribution line) over the shot's image dimmed to background_dim."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        size, kind, trk = int(p["size_px"]), p["font_kind"], int(p["tracking_px"])
        max_w = float(p["max_width_pct"]) / 100.0 * W
        lines = C.wrap(p["quote"], kind, size, trk, max_w)
        rows = [{"text": l, "size": size, "kind": kind, "tracking": trk, "color": C.hex_rgb(p["color"])} for l in lines]
        attr = str(p["attribution"] or "").strip()
        if attr and rows:
            asz = int(p["attribution_size_px"])
            rows.append({"text": attr, "size": asz, "kind": p["attribution_font_kind"], "tracking": int(p["attribution_tracking_px"]),
                         "color": C.hex_rgb(p["attribution_color"]), "attr": True})
        cx = int(round(W * float(p["x_pct"]) / 100.0))
        cy = int(round(H * float(p["y_pct"]) / 100.0))
        key = ("t3quote", tuple((r["text"], r["size"], r["kind"], r["tracking"], r["color"], r.get("attr", False)) for r in rows),
               cx, cy, float(p["line_gap"]), int(p["attribution_gap_px"]), bool(p["shadow"]), C.serif_signature())
        self.layer = ctx.layer(key, lambda: C.block_layer(W, H, rows, cx, cy, bool(p["shadow"]), float(p["line_gap"]), int(p["attribution_gap_px"])))

    def apply(self, f, t, view):
        p = self.p
        if t < self.t0 - 1e-6:
            return f
        tt = t - self.t0
        g = float(p["background_dim"])
        if g != 1.0:
            d = ramp(tt, 0.0, float(p["dim_in_s"]))
            f = f * (1 - (1 - g) * d)
        e = ramp(tt, float(p["delay_s"]), float(p["fade_in_s"])) * _out_env(t, self.t1, float(p["fade_out_s"]))
        return self.layer.apply(f, e)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        q = context.get("quote") or context.get("text")
        if isinstance(q, str) and q.strip():
            d["quote"] = q
        if isinstance(context.get("attribution"), str):
            d["attribution"] = context["attribution"]
        return d


# ----------------------------------------------------------------------------- STATIC-05
@technique("STATIC-05", "overlay")
class IntervieweeTag(OverlayRenderer):
    """Lower-third name strip (name + role) over footage or a still: the label_strip look of X-ANN-02 with its own position and text."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        name, role = str(p["name"] or ""), str(p["role"] or "").strip() or None
        if p["case"] == "upper":
            name = name.upper()                      # the reel's label strip upper-cases the name only; the role stays as typed
        h = int(p["strip_height_px"])
        y0 = float(p["y_pct"]) / 100.0
        size, sub = int(p["size_px"]), int(p["role_size_px"])
        key = ("t3tag", name, role, y0, h, float(p["text_x_pct"]), size, sub, float(p["strip_opacity"]), float(p["right_fade_pct"]))
        self.layer = ctx.layer(key, lambda: label_layer(name, role, y0=y0, h=h, x_text=float(p["text_x_pct"]) / 100.0, w=ctx.w, hh=ctx.h,
                                                        opacity=float(p["strip_opacity"]), fade_frac=float(p["right_fade_pct"]) / 100.0,
                                                        size=size, sub_size=sub))

    def apply(self, f, t, view):
        return self.layer.apply(f, window(t, self.t0, self.t1, float(self.p["pop_in_s"]), float(self.p["fade_out_s"])))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        sty = lambda k, dv: bundle.sv("label_strip", k, dv)
        d.update(strip_opacity=sty("opacity", 0.8), text_x_pct=sty("text_x_pct", 7.0),
                 size_px=sty("first_line_px_1080p", 58), role_size_px=sty("second_line_px_1080p", 32))
        n = context.get("name") or context.get("text")
        if isinstance(n, str) and n.strip():
            d["name"] = n
        return d
