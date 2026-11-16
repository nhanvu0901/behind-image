"""Highlights: HI-02 (figures revealed group by group, base shot), HI-03 (colour kept inside a mask, overlay), X-HI-01 (dim to isolate, then
restore, overlay).

Masks are `mask` assets aligned to an image (`helpers.mask_alpha`); a good mask is assumed, nothing here hides a rough one.

Timing semantics:
  HI-02   (base)  group k starts at first_group_delay_s + k * group_stagger_s from the shot start; it fades in over group_fade_s while sliding
                  in from `slide_from[k]` over group_slide_s (out_cubic).
  HI-03   (overlay) desaturation ramps in from start over desaturate_ramp_s; it ramps back so as to be gone at end - restore_s .. end
                  (restore_s 0: it stays until end and is cut there, as in the benchmark where the shot ends).
  X-HI-01 (overlay) dim ramps in over ramp_in_s from start, holds hold_s (null: until the restore starts), restore runs ramp_out_s; with
                  hold_s null the restore ENDS at end, with hold_s set it starts at start + ramp_in_s + hold_s.
"""
from __future__ import annotations

import cv2
import numpy as np

from .. import helpers as Hh
from ..base import BaseRenderer, OverlayRenderer, View
from ..registry import technique
from ..vfx import compose_matte, ease, ramp, blend
from . import _t2_common as C
from ._t2_common import numbered_slots, slot_key, soft_region

SLIDE_DIRS = ["left", "right", "top", "bottom", "none"]


def _defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}


# ============================================================================= HI-02
@technique("HI-02", "base")
class FigureReveal(BaseRenderer):
    """A plate (`room_plate`) with the figure groups of `figure_groups` revealed one group at a time through masks `mask_1 .. mask_6`.
    Plate, figures and masks share one coordinate system (the masks are aligned to the figure image, which is registered to the plate)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.plate, self.fig = self.slot_asset("room_plate"), self.slot_asset("figure_groups")
        self.masks = [k for _, k in numbered_slots(shot, "mask")]
        keys = C.keys_from_param(shot, ctx, "camera")
        if keys is None:
            w, h = ctx.asset_size(self.plate)
            keys = C.fit_key(self.t0, w, h)
        self.cam = C.Track(keys, "log")

    def view(self, t):
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.fig), self.fig)

    def render(self, t):
        p, ctx = self.p, self.ctx
        W, H = ctx.w, ctx.h
        cx, cy, z = self.cam.at(t)
        f = compose_matte(ctx.image(self.plate), cx, cy, z, W, H, shadow=bool(p["shadow"])) * float(p["plate_dim"])
        fig = ctx.image(self.fig)
        zf = z * float(p["figure_scale"])
        dirs = list(p["slide_from"] or ["none"])
        for k, mk in enumerate(self.masks):
            tk = self.t0 + float(p["first_group_delay_s"]) + float(p["group_stagger_s"]) * k
            a = ramp(t, tk, float(p["group_fade_s"]))
            if a <= 0:
                continue
            prog = ease("out_cubic", (t - tk) / max(float(p["group_slide_s"]), 1e-3))
            d = dirs[k % len(dirs)]
            ux, uy = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}.get(d, (0, 0))
            dx, dy = ux * (1 - prog) * float(p["slide_px"]), uy * (1 - prog) * float(p["slide_px"])
            col = fig.view(cx, cy, zf, W, H)[0].astype(np.float32)
            m = Hh.mask_alpha(ctx, mk, cx, cy, zf, image_key=self.fig)
            if dx or dy:
                M = np.float32([[1, 0, dx], [0, 1, dy]])
                col = cv2.warpAffine(col, M, (W, H))
                m = cv2.warpAffine(m[:, :, 0], M, (W, H))[:, :, None]
            f = f * (1 - m * a) + col * m * a
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w") and a.get("h"):
            w, h = float(a["w"]), float(a["h"])
            z = 0.78 * 1920.0 / w
            d["camera"] = [C.cam_key_json(0.0, w / 2, h / 2, z), C.cam_key_json(1.0, w / 2, h / 2, z)]
        return d


# ============================================================================= HI-03
@technique("HI-03", "overlay")
class ColourKeep(OverlayRenderer):
    """The frame under the overlay goes monochrome (and slightly darker) everywhere except inside the `mask` slot."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        self.mask_key = slot_key(ov, "mask")

    def apply(self, f, t, view):
        p = self.p
        if view is None or not self.mask_key or t < self.t0 or t >= self.t1:
            return f
        a = ramp(t, self.t0, float(p["desaturate_ramp_s"]), "inout_sine")
        rs = float(p["restore_s"])
        if rs > 0:
            a *= 1 - ramp(t, self.t1 - rs, rs, "inout_sine")
        if a <= 0:
            return f
        m = Hh.mask_alpha(self.ctx, self.mask_key, view.cx, view.cy, view.z)
        sat = float(p["outside_saturation"])
        target = (Hh.gray(f) * (1 - sat) + f * sat) * float(p["outside_brightness"])
        g = blend(f, target, a)
        return g * (1 - m) + f * m

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _defaults(spec)


# ============================================================================= X-HI-01
@technique("X-HI-01", "overlay")
class DimIsolateRestore(OverlayRenderer):
    """Dim the whole frame to `surround_floor` brightness around a soft ellipse or rounded rectangle centred on `at`
    (radii rx, ry in source pixels), hold, then restore.  Differs from the spotlight HI-01 by the explicit hold and restore phases and the
    rectangular option."""

    def _envelope(self, t):
        p = self.p
        rin, rout = float(p["ramp_in_s"]), float(p["ramp_out_s"])
        if p["hold_s"] is not None:
            out0 = self.t0 + rin + float(p["hold_s"])
        else:
            out0 = self.t1 - rout
        return ramp(t, self.t0, rin, "inout_sine") * (1 - ramp(t, out0, rout, "inout_sine"))

    def apply(self, f, t, view):
        p = self.p
        if view is None or t < self.t0:
            return f
        a = self._envelope(t)
        if a <= 0:
            return f
        sx, sy = view.to_screen(*self.ctx.point(p["at"], view.asset_key))
        m = soft_region(self.ctx.h, self.ctx.w, sx, sy, float(p["rx"]) * view.z, float(p["ry"]) * view.z, p["shape"], float(p["feather"]))
        return f * (1 - (1 - float(p["surround_floor"])) * m * a)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        d["surround_floor"] = bundle.sv("spotlight", "surround_floor_benchmark_final", d["surround_floor"])
        asset = context.get("asset") or {}
        reg = {}
        r = context.get("region")
        if isinstance(r, str):
            reg = (asset.get("regions") or {}).get(r) or {}
            d["at"] = r
        elif isinstance(r, (list, tuple)) and len(r) == 2:
            d["at"] = list(r)
        elif asset.get("w"):
            d["at"] = [asset["w"] / 2, asset["h"] / 2]
        cam = context.get("camera") or {}
        z = float(cam.get("zoom") or (0.955 * 1080.0 / float(asset["h"]) if asset.get("h") else 0.5))
        d["rx"] = float(reg.get("rx") or round(0.12 * 1920 / z))
        d["ry"] = float(reg.get("ry") or d["rx"])
        return d
