"""Highlight and annotation overlays: spotlight (HI-01), ring (AN-01), dimension annotation (AN-05).

Coordinates: `at` is a region name of the shot's image or [x, y] in SOURCE pixels; sizes named *radius*, rx, ry are source
pixels too (they scale with the camera zoom).  Lifted from build_v2.py Spot, RingOv, DimOv.

Timing semantics (overlay start .. end):
  HI-01  ramp_in starts at start; ramp_out STARTS at end and runs ramp_out seconds past it (the shot clips it).
  AN-01  draws on over draw_s from start, holds hold_s, fades over fade_s; nothing is drawn at or after end.
  AN-05  pops in over pop_s from start; pop-out starts at end (lingers pop_s past it).
"""
from __future__ import annotations

import cv2
import numpy as np

from ..base import OverlayRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import ramp, ring, spotlight, text_layer


def _ctx_zoom(context, asset, bundle=None):
    cam = context.get("camera") or {}
    if cam.get("zoom"):
        return float(cam["zoom"])
    if asset.get("h"):
        return 0.955 * 1080.0 / float(asset["h"])
    return 0.5


def _visible_w(context, asset):
    """Source-pixel width of the frame as seen at the playhead camera, never wider than the image itself."""
    z = _ctx_zoom(context, asset)
    vis = 1920.0 / z
    return min(vis, float(asset["w"])) if asset.get("w") else vis


def _region_xy(context, asset):
    r = context.get("region")
    if isinstance(r, str):
        reg = (asset.get("regions") or {}).get(r)
        if reg:
            return r, reg
    if isinstance(r, (list, tuple)) and len(r) == 2:
        return list(r), {}
    return None, {}


@technique("HI-01", "overlay")
class Spotlight(OverlayRenderer):
    """Darken everything outside a feathered ellipse around `at` to `floor` brightness."""

    def apply(self, f, t, view):
        p = self.p
        a = ramp(t, self.t0, float(p["ramp_in"]), "inout_sine") * (1 - ramp(t, self.t1, float(p["ramp_out"]), "inout_sine"))
        if a <= 0 or view is None:
            return f
        sx, sy = view.to_screen(*self.ctx.point(p["at"], view.asset_key))
        return spotlight(f, sx, sy, float(p["rx"]) * view.z, float(p["ry"]) * view.z, a, float(p["floor"]), float(p["feather"]))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        d["floor"] = bundle.sv("spotlight", "surround_floor_benchmark_final", d["floor"])
        d["ramp_in"] = d["ramp_out"] = bundle.sv("spotlight", "ramp_s", 0.5)
        asset = context.get("asset") or {}
        name, reg = _region_xy(context, asset)
        if name is not None:
            d["at"] = name
        else:
            d["at"] = [asset.get("w", 0) / 2, asset.get("h", 0) / 2] if asset.get("w") else [0, 0]
        z = _ctx_zoom(context, asset)
        d["rx"] = float(reg.get("rx") or round(0.12 * _visible_w(context, asset)))      # about a quarter of the visible frame width
        d["ry"] = float(reg.get("ry") or d["rx"])
        return d


@technique("AN-01", "overlay")
class Ring(OverlayRenderer):
    """A light ring drawn on clockwise from the top around `at`, held, then faded."""

    def apply(self, f, t, view):
        p = self.p
        if t < self.t0 or t >= self.t1 or view is None:
            return f
        draw, hold, fade = float(p["draw_s"]), float(p["hold_s"]), float(p["fade_s"])
        prog = ramp(t, self.t0, draw, "out_quad")
        al = float(p["opacity"]) * (1 - ramp(t, self.t0 + draw + hold, fade))
        if al <= 0:
            return f
        x, y = view.to_screen(*self.ctx.point(p["at"], view.asset_key))
        thick = max(6, float(p["stroke_pct_width"]) / 100.0 * self.ctx.w)
        return ring(f, x, y, float(p["radius"]) * view.z, prog, al, thick, hex_to_bgr(p["color"]))

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        for k in ("draw_s", "hold_s", "fade_s", "opacity"):
            v = bundle.sv("ring", k)
            if v is not None:
                d[k] = v
        d["stroke_pct_width"] = bundle.sv("ring", "stroke_pct_width", d["stroke_pct_width"])
        asset = context.get("asset") or {}
        name, reg = _region_xy(context, asset)
        d["at"] = name if name is not None else ([asset["w"] / 2, asset["h"] / 2] if asset.get("w") else [0, 0])
        z = _ctx_zoom(context, asset)
        diam = bundle.sv("ring", "diameter_pct_width", 23.4)
        d["radius"] = float(reg.get("rx") or round(diam / 100.0 * _visible_w(context, asset) / 2))      # relative to the visible frame
        return d


@technique("AN-05", "overlay")
class DimensionAnnotation(OverlayRenderer):
    """Ruler lines along the top and left of the image with two measurements and a medium caption.

    The image rectangle follows the camera, unless `frame_zoom` is set: then the image is drawn centred in the canvas at that
    zoom, whatever the camera does (the benchmark pinned it, so the lines stay still during a slow push).
    """

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.sizes = (int(p["label_px"]), int(p["caption_px"]))
        W, H = ctx.w, ctx.h
        mk = lambda text, size: ctx.layer(("dim", text, size), lambda: text_layer(text, W // 2, H // 2, size, "sans_bold", 1, w=W, h=H))
        self.L_w = mk(p["width_label"], self.sizes[0])
        self.L_h = mk(p["height_label"], self.sizes[0])
        self.L_c = mk(p["medium_caption"], self.sizes[1])

    def _rect(self, view):
        W, H = self.ctx.w, self.ctx.h
        zz = self.p.get("frame_zoom")
        iw, ih = view.img.w, view.img.h
        if zz:
            xh, yh = (iw / 2.0) * zz, (ih / 2.0) * zz
            return W / 2 - xh, H / 2 - yh, W / 2 + xh, H / 2 + yh
        x0, y0 = view.to_screen(0, 0)
        x1, y1 = view.to_screen(iw, ih)
        return x0, y0, x1, y1

    def apply(self, f, t, view):
        p = self.p
        pop = float(p["pop_s"])
        e = ramp(t, self.t0, pop) * (1 - ramp(t, self.t1, pop))
        if e <= 0 or view is None:
            return f
        W, H = self.ctx.w, self.ctx.h
        x0, y0, x1, y1 = self._rect(view)
        ov = np.zeros((H, W), np.uint8)
        c, th = 255, int(p["line_px"])
        cv2.line(ov, (int(x0), int(y0 - 24)), (int(x1), int(y0 - 24)), c, th, cv2.LINE_AA)
        cv2.line(ov, (int(x0 - 40), int(y0)), (int(x0 - 40), int(y1)), c, th, cv2.LINE_AA)
        for a, b in (((x0, y0 - 38), (x0, y0 - 10)), ((x1, y0 - 38), (x1, y0 - 10)),
                     ((x0 - 54, y0), (x0 - 26, y0)), ((x0 - 54, y1), (x0 - 26, y1))):
            cv2.line(ov, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), c, th, cv2.LINE_AA)
        a = (ov.astype(np.float32) / 255 * e)[:, :, None]
        f = f * (1 - a) + 255 * a
        cx, cy = W // 2, H // 2
        self.L_w.apply(f, e, 0, int(y0 - 62) - cy)
        self.L_h.apply(f, e, int(x0 - 150) - cx, 0)
        self.L_c.apply(f, e, int(x1 + 330) - cx, int(y0 + 60) - cy)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        d["frame_zoom"] = None
        for k in ("width_label", "height_label", "medium_caption"):
            if context.get(k):
                d[k] = context[k]
        return d
