"""Cards: X-CARD-03 (end credit line over the closing matte) and X-CARD-04 (brown serif question on a white card).

Both are built from the research descriptions (R3; measurements.md "Closing: ... end credit centred bottom";
visual-a/T9JvUDrrXmY.md A-T9-02 for the white card), not from a reel segment.  Times are relative to the shot start.

  X-CARD-03  text fades in at delay_s over fade_in_s; if leave_at_s > 0 it fades out ending at leave_at_s (fade_out_s).
  X-CARD-04  same envelope on the wrapped question text.
"""
from __future__ import annotations

import os

import numpy as np

from .. import vfx
from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import compose_matte, ramp
from . import _t3common as C


def _env(t, t0, p):
    e = ramp(t, t0 + float(p["delay_s"]), float(p["fade_in_s"]), "out_quad")
    leave, fo = float(p["leave_at_s"]), float(p["fade_out_s"])
    if leave > 0:
        e = min(e, 1.0 - ramp(t, t0 + leave - fo, fo) if fo > 0 else (1.0 if t < t0 + leave else 0.0))
    return e


@technique("X-CARD-03", "card")
class EndCredit(BaseRenderer):
    """Credit text (lines separated by newlines) centred near the bottom over the designed matte or a flat colour; an optional
    `image` slot shows a painting on the matte behind it (the closing shot of the episode)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        size, kind, trk = int(p["size_px"]), p["font_kind"], int(p["tracking_px"])
        text = str(p["credit_text"] or "")
        if p["case"] == "upper":
            text = text.upper()
        max_w = float(p["max_width_pct"]) / 100.0 * W
        rows = []
        for ln in text.split("\n"):
            for w in (C.wrap(ln, kind, size, trk, max_w) or [""]):
                rows.append({"text": w, "size": size, "kind": kind, "tracking": trk, "color": C.hex_rgb(p["color"])})
        cy = int(round(H * float(p["y_pct"]) / 100.0))
        gap = float(p["line_gap"])
        key = ("t3credit", tuple(r["text"] for r in rows), size, kind, trk, C.hex_rgb(p["color"]), cy, gap, bool(p["shadow"]), C.serif_signature())
        self.layer = ctx.layer(key, lambda: C.block_layer(W, H, rows, W // 2, cy, bool(p["shadow"]), gap))
        self.flat = np.array(hex_to_bgr(p["background"]), np.float32)
        self.img_key = self.slot_asset("image")
        self.base = None
        if self.img_key:
            k, pct, matte = self.img_key, float(p["image_height_pct"]), bool(p["use_matte"])
            path = ctx.asset_path(k)

            def build():
                im = ctx.image(k)
                z = pct / 100.0 * H / im.h
                f = compose_matte(im, im.w / 2.0, im.h / 2.0, z, W, H) if matte else self._flat_frame(im, z)
                return np.clip(f, 0, 255).astype(np.uint8)
            self.base = ctx.cached(("t3creditbase", path, os.stat(path).st_mtime_ns, pct, matte, tuple(self.flat)), build)

    def _flat_frame(self, im, z):
        W, H = self.ctx.w, self.ctx.h
        out, a, _ = im.view(im.w / 2.0, im.h / 2.0, z, W, H)
        return np.zeros((H, W, 3), np.float32) + self.flat * (1 - a) + out.astype(np.float32) * a

    def render(self, t):
        W, H = self.ctx.w, self.ctx.h
        if self.base is not None:
            f = self.base.astype(np.float32)
        elif self.p["use_matte"]:
            f = vfx.backdrop(W, H).copy()
        else:
            f = np.zeros((H, W, 3), np.float32) + self.flat
        return self.layer.apply(f, _env(t, self.t0, self.p))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        d["background"] = bundle.sv("cards", "chapter_background", d["background"])
        t = context.get("credit_text") or context.get("text")
        if isinstance(t, str) and t.strip():
            d["credit_text"] = t
        return d


@technique("X-CARD-04", "card")
class QuestionCardWhite(BaseRenderer):
    """A question or title in a serif face, brown on white by default, wrapped to max_width_pct and centred."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        size, kind, trk = int(p["size_px"]), p["font_kind"], int(p["tracking_px"])
        text = str(p["text"] or "")
        if p["case"] == "upper":
            text = text.upper()
        lines = C.wrap(text, kind, size, trk, float(p["max_width_pct"]) / 100.0 * W)
        col = C.hex_rgb(p["text_color"], (90, 58, 34))
        rows = [{"text": l, "size": size, "kind": kind, "tracking": trk, "color": col} for l in lines]
        cx, cy = int(round(W * float(p["x_pct"]) / 100.0)), int(round(H * float(p["y_pct"]) / 100.0))
        gap = float(p["line_gap"])
        self.layer = ctx.layer(("t3question", tuple(lines), size, kind, trk, col, cx, cy, gap, bool(p["shadow"]), C.serif_signature()),
                               lambda: C.block_layer(W, H, rows, cx, cy, bool(p["shadow"]), gap))
        self.bg = np.array(hex_to_bgr(p["background"]), np.float32)

    def render(self, t):
        f = np.zeros((self.ctx.h, self.ctx.w, 3), np.float32) + self.bg
        return self.layer.apply(f, _env(t, self.t0, self.p))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        t = context.get("text") or context.get("title")
        if isinstance(t, str) and t.strip():
            d["text"] = t
        return d
