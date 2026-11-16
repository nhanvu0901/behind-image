"""Transitions T1: TR-03 (panel opening) and X-TR-02 (strip slides in, becomes full frame, then splits beside the first image).

Both work on the two frames the Scene hands to a transition (`blend(f_out, f_in, p)`): the outgoing shot's frame and the incoming
shot's frame, so every pixel of content comes from the shots (their slots and cameras), never from the transition itself.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from ..base import TransitionRenderer
from ..registry import technique
from ..vfx import blend, ease, ramp
from ._t1common import pdef


def _box(v):
    return [int(round(x)) for x in v]


def _clamp01(p):
    return 0.0 if p < 0 else 1.0 if p > 1 else float(p)


# ============================================================================================ TR-03
@technique("TR-03", "transition")
class PanelOpening(TransitionRenderer):
    """Two wings (the left and right half of `box` in the OUTGOING frame) swing open like shutters, narrowing in perspective,
    and uncover the inner image (the same `box` of the INCOMING frame), which brightens from inner_dim to 1.

    p (0..1) is the progress of the transition (its `dur`).  Wing angle = hinge_angle_deg * inout_cubic(p); half-width = (box w / 2) *
    cos(angle); the outer edge of each wing shrinks by perspective_squeeze_pct of the half-height * sin(angle).  The inner
    image brightens with inout_sine over the first inner_fade_frac of the transition.  The wings fade out during the last
    wing_fade_frac so the end state is exactly the incoming frame; outside the box the frames cross-fade."""

    def blend(self, f_out, f_in, p):
        p = _clamp01(p)
        if p <= 0:
            return f_out
        if p >= 1:
            return f_in
        q = self.p
        x0, y0, x1, y1 = _box(q["box"])
        bw, bh = x1 - x0, y1 - y0
        f = blend(f_out, f_in, ease("inout_sine", p))
        dim = float(q["inner_dim"])
        f[y0:y1, x0:x1] = f_in[y0:y1, x0:x1] * (dim + (1 - dim) * ease("inout_sine", p / max(float(q["inner_fade_frac"]), 1e-6)))
        th = math.radians(float(q["hinge_angle_deg"]) * ease("inout_cubic", p))
        w_ = (bw / 2) * math.cos(th)
        sq = (bh / 2) * float(q["perspective_squeeze_pct"]) / 100.0 * math.sin(th)
        wa = 1.0 - ramp(p, 1.0 - float(q["wing_fade_frac"]), float(q["wing_fade_frac"])) if q["wing_fade_frac"] > 0 else 1.0
        hw = bw // 2
        crop = f_out[y0:y1, x0:x1]
        halves = [crop[:, :hw], crop[:, hw:]]
        quads = [np.float32([[0, 0], [w_, sq], [w_, bh - sq], [0, bh]]),
                 np.float32([[bw - w_, sq], [bw, 0], [bw, bh], [bw - w_, bh - sq]])]
        box = f[y0:y1, x0:x1]
        for img, dst in zip(halves, quads):
            ih, iw = img.shape[:2]
            src = np.float32([[0, 0], [iw - 1, 0], [iw - 1, ih - 1], [0, ih - 1]])
            M = cv2.getPerspectiveTransform(src, dst)
            wr = cv2.warpPerspective(np.ascontiguousarray(img), M, (bw, bh), flags=cv2.INTER_LINEAR)
            mk = cv2.warpPerspective(np.full((ih, iw), 255, np.uint8), M, (bw, bh), flags=cv2.INTER_LINEAR)[:, :, None].astype(np.float32) / 255 * wa
            box = box * (1 - mk) + wr.astype(np.float32) * mk
        f[y0:y1, x0:x1] = box
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


# ============================================================================================ X-TR-02
def _cover_resize(src, w, h):
    """cover-fit src (float32) into w x h (centre crop)."""
    sh, sw = src.shape[:2]
    s = max(w / sw, h / sh)
    nw, nh = max(w, int(round(sw * s))), max(h, int(round(sh * s)))
    r = cv2.resize(src, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    y0, x0 = (nh - h) // 2, (nw - w) // 2
    return r[y0:y0 + h, x0:x0 + w]


@technique("X-TR-02", "transition")
class StripSplit(TransitionRenderer):
    """New.  The incoming shot is a split layout (anchor beside a second image).  Over the transition: (1) a strip of the second
    image (the part of the INCOMING frame inside `target_box`) slides in from `slide_from` over slide_s while the outgoing frame
    stays; (2) the strip grows to the full frame over expand_s; (3) it is held full frame for hold_full_s; (4) it moves to
    `target_box` (split_s) while the background changes from the outgoing frame to the incoming one, ending exactly on the
    incoming frame.  Phase lengths are seconds; if they exceed the transition `dur` they are scaled down to fit.
    strip_px is the strip thickness; target_box null = the right (split_to right) or left (split_to left) panel of LAY-01 geometry."""

    def _phases(self):
        q = self.p
        ph = [float(q["slide_s"]), float(q["expand_s"]), float(q["hold_full_s"]), float(q["split_s"])]
        tot = sum(ph)
        if self.dur > 0 and tot > self.dur:
            ph = [x * self.dur / tot for x in ph]
        return ph

    def _target(self, W):
        q = self.p
        if q["target_box"] is not None:
            return _box(q["target_box"])
        return [970, 36, 1870, 776] if q["split_to"] == "right" else [50, 36, 950, 776]

    def blend(self, f_out, f_in, p):
        p = _clamp01(p)
        if p <= 0:
            return f_out
        if p >= 1:
            return f_in
        q = self.p
        Hh, W = f_in.shape[:2]
        tx0, ty0, tx1, ty1 = self._target(W)
        src = f_in[ty0:ty1, tx0:tx1]
        t = p * (self.dur if self.dur > 0 else sum(self._phases()))
        s1, s2, s3, s4 = self._phases()
        edge = q["slide_from"]
        th = int(q["strip_px"])
        vertical = edge in ("bottom", "top")            # strip is a tall band moving vertically
        # strip rect at the end of the slide: centred band
        if vertical:
            band = [(W - th) // 2, 0, (W - th) // 2 + th, Hh]
        else:
            band = [0, (Hh - th) // 2, W, (Hh - th) // 2 + th]
        full = [0, 0, W, Hh]
        if t < s1:
            e = ease(q["slide_ease"], t / max(s1, 1e-6))
            off = {"bottom": (0, Hh), "top": (0, -Hh), "right": (W, 0), "left": (-W, 0)}[edge]
            rect = [band[0] + off[0] * (1 - e), band[1] + off[1] * (1 - e), band[2] + off[0] * (1 - e), band[3] + off[1] * (1 - e)]
            bgmix = 0.0
        elif t < s1 + s2:
            e = ease("inout_cubic", (t - s1) / max(s2, 1e-6))
            rect = [band[i] + (full[i] - band[i]) * e for i in range(4)]
            bgmix = 0.0
        elif t < s1 + s2 + s3:
            rect, bgmix = full, 0.0
        else:
            e = ease("inout_cubic", (t - s1 - s2 - s3) / max(s4, 1e-6))
            rect = [full[0] + (tx0 - full[0]) * e, full[1] + (ty0 - full[1]) * e, full[2] + (tx1 - full[2]) * e, full[3] + (ty1 - full[3]) * e]
            bgmix = e
        f = blend(f_out, f_in, bgmix) if bgmix > 0 else f_out.copy()
        x0, y0, x1, y1 = [int(round(v)) for v in rect]
        w, h = x1 - x0, y1 - y0
        if w < 2 or h < 2:
            return f
        tile = _cover_resize(src, w, h)
        cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, Hh)
        if cx1 > cx0 and cy1 > cy0:
            f[cy0:cy1, cx0:cx1] = tile[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


SPECS = {
    "TR-03": dict(
        slots=[],
        params=[pdef("box", "box", [360, 90, 1560, 990], unit="canvas px"),
                pdef("hinge_angle_deg", "number", 84, 30, 90, "deg"), pdef("perspective_squeeze_pct", "number", 22, 0, 50, "%"),
                pdef("inner_dim", "number", 0.5, 0, 1, "factor"), pdef("inner_fade_frac", "number", 0.9375, 0.1, 1.0, "fraction"),
                pdef("wing_fade_frac", "number", 0.12, 0, 0.5, "fraction")]),
    "X-TR-02": dict(
        slots=[],
        params=[pdef("slide_from", "enum", "bottom", values=["bottom", "top", "left", "right"]),
                pdef("split_to", "enum", "right", values=["left", "right"]),
                pdef("target_box", "box", None, unit="canvas px"), pdef("strip_px", "number", 420, 60, 1500, "px"),
                pdef("slide_s", "number", 0.9, 0.3, 3.0, "s"), pdef("slide_ease", "enum", "out_cubic", values=["linear", "out_cubic", "out_quad", "inout_cubic", "inout_sine"]),
                pdef("expand_s", "number", 0.7, 0.1, 3, "s"), pdef("hold_full_s", "number", 0.6, 0, 6, "s"), pdef("split_s", "number", 0.9, 0.1, 3, "s")]),
}
