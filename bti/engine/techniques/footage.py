"""FOOT-01: real footage (or a still) of a material, a process, a palette, shown full-frame with an optional label and an optional slow push.

The slot `footage` takes a `video` asset (kind "video") or an image asset.  Everything the editor tunes is a param: the source in-point,
playback speed, fit on the canvas (cover or contain), the push (zoom ratio, focus point, easing) and what to do when the footage is shorter
than the shot (hold the last frame, loop between in-point and end, or slow down to stretch what is left over the shot).
Frames are pure functions of t: the source time is source_in_s + speed * (t - shot start), decoded through `helpers.video_frame`.
"""
from __future__ import annotations

import os

import cv2
import numpy as np

from .. import vfx
from ..base import BaseRenderer
from ..helpers import video_frame
from ..registry import technique
from ..vfx import label_layer, ramp, window
from . import _t3common as C

END_BEHAVIOURS = ("hold", "loop", "slow")


@technique("FOOT-01", "base")
class MaterialFootage(BaseRenderer):
    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        self.key = self.slot_asset("footage")
        self.is_video = bool(self.key) and ctx.asset(self.key).get("kind") == "video"
        self._info = None
        if self.key and self.is_video:
            path = ctx.asset_path(self.key)
            mt = os.stat(path).st_mtime_ns
            self._info = ctx.cached(("t3vprobe", path, mt), lambda: _probe(path))          # (fps, frames, w, h)
        elif self.key:
            self._info = (0.0, 1, *ctx.asset_size(self.key))
        # label strip (optional) and source line (optional)
        self.label = None
        text, sub = str(p["label"] or "").strip(), str(p["label_sub"] or "").strip() or None
        if text:
            if p["label_case"] == "upper":
                text, sub = text.upper(), (sub.upper() if sub else None)
            y0 = float(p["label_y_top_pct"]) / 100.0
            h = int(round((float(p["label_y_bottom_pct"]) - float(p["label_y_top_pct"])) * H / 100.0))
            size, ssz = int(p["label_size_px"]), int(round(int(p["label_size_px"]) * float(p["label_sub_scale"])))
            key = ("t3footlab", text, sub, y0, h, float(p["label_text_x_pct"]), size, ssz, float(p["label_opacity"]), float(p["label_right_fade_pct"]))
            self.label = ctx.layer(key, lambda: label_layer(text, sub, y0=y0, h=h, x_text=float(p["label_text_x_pct"]) / 100.0, w=W, hh=H,
                                                           opacity=float(p["label_opacity"]), fade_frac=float(p["label_right_fade_pct"]) / 100.0,
                                                           size=size, sub_size=ssz))
        self.source = None
        stext = str(p["source_text"] or "").strip()
        if stext:
            ssize, mx, mb = int(p["source_size_px"]), int(p["source_margin_left_px"]), int(p["source_margin_bottom_px"])
            self.source = ctx.layer(("t3footsrc", stext, ssize, mx, mb),
                                    lambda: _source_line(stext, ssize, mx, H - mb - ssize - 12, W, H))

    # -- timing -------------------------------------------------------------------------------------------------
    def source_time(self, t):
        """Source seconds shown at shot time t (applies speed and the end behaviour)."""
        p = self.p
        fps, n = self._info[0], self._info[1]
        tin = max(0.0, float(p["source_in_s"]))
        tt = max(0.0, t - self.t0)
        dur = n / fps if fps > 0 else 0.0
        remain = max(dur - tin, 1.0 / max(fps, 1.0))
        speed = max(0.01, float(p["speed"]))
        shot_len = max(self.t1 - self.t0, 1e-6)
        if p["end_behavior"] == "slow" and speed * shot_len > remain:
            speed = remain / shot_len
        s = tt * speed
        if p["end_behavior"] == "loop":
            s = s % remain
        else:
            s = min(s, remain - 1.0 / max(fps, 1.0))
        return tin + max(s, 0.0)

    def view_at(self, t, fw, fh):
        """(cx, cy, zoom) in footage pixels at time t: fit zoom times the push."""
        p = self.p
        W, H = self.ctx.w, self.ctx.h
        fit = max(W / fw, H / fh) if p["fit"] == "cover" else float(p["contain_pct"]) / 100.0 * min(W / fw, H / fh)
        cx, cy = fw / 2.0, fh / 2.0
        ratio = float(p["push_zoom"])
        z = fit
        if ratio != 1.0:
            e = vfx.ease(p["push_ease"], (t - self.t0) / max(self.t1 - self.t0, 1e-6))
            z = fit * float(np.exp(np.log(ratio) * e))
            if p["push_focus"] is not None and self.key:
                try:
                    fx, fy = self.ctx.point(p["push_focus"], self.key)
                    cx, cy = cx + (fx - cx) * e, cy + (fy - cy) * e
                except Exception:
                    pass
        if p["fit"] == "cover":                                            # keep the view inside the footage
            hw, hh = W / (2 * z), H / (2 * z)
            if 2 * hw < fw:
                cx = min(max(cx, hw), fw - hw)
            if 2 * hh < fh:
                cy = min(max(cy, hh), fh - hh)
        return cx, cy, z

    def _ambient(self):
        p = self.p
        W, H = self.ctx.w, self.ctx.h
        mode = p["contain_bg"]
        if mode == "black":
            return np.zeros((H, W, 3), np.float32)
        if mode == "matte":
            return vfx.backdrop(W, H)
        key = ("t3footamb", self.ctx.asset_path(self.key), float(p["source_in_s"]))

        def build():                                                    # always from the in-point frame: independent of render order
            frame0 = video_frame(self.ctx, self.key, float(p["source_in_s"])) if self.is_video else self.ctx.image(self.key).levels[-1]
            sc = max(W / frame0.shape[1], H / frame0.shape[0])
            big = cv2.resize(frame0, (int(frame0.shape[1] * sc) + 1, int(frame0.shape[0] * sc) + 1), interpolation=cv2.INTER_AREA)
            y0, x0 = (big.shape[0] - H) // 2, (big.shape[1] - W) // 2
            return cv2.GaussianBlur(big[y0:y0 + H, x0:x0 + W], (0, 0), 38).astype(np.float32) * 0.42
        return self.ctx.cached(key, build)

    def render(self, t):
        ctx, p = self.ctx, self.p
        W, H = ctx.w, ctx.h
        if not self.key or self._info is None:
            f = vfx.backdrop(W, H).copy()
        else:
            fw, fh = self._info[2], self._info[3]
            if self.is_video:
                fr = video_frame(ctx, self.key, self.source_time(t))
                fh, fw = fr.shape[:2]
            cx, cy, z = self.view_at(t, fw, fh)
            if self.is_video:
                f = self._warp_video(fr, cx, cy, z)
            else:
                out, a, (x0, y0, x1, y1) = ctx.image(self.key).view(cx, cy, z, W, H)
                if x0 <= 0 and y0 <= 0 and x1 >= W and y1 >= H:
                    f = out.astype(np.float32)
                else:
                    bg = self._ambient()
                    f = bg * (1 - a) + out.astype(np.float32) * a
        if self.label is not None:
            t_in = self.t0 + float(p["label_in_s"])
            hold = float(p["label_hold_s"])
            t_out = t_in + hold if hold > 0 else self.t1
            f = self.label.apply(f, window(t, t_in, t_out, float(p["label_fade_in_s"]), float(p["label_fade_out_s"])))
        if self.source is not None:
            f = self.source.apply(f, window(t, self.t0 + float(p["source_in_delay_s"]), self.t1, 0.3, 0.3))
        return f

    def _warp_video(self, fr, cx, cy, z):
        W, H = self.ctx.w, self.ctx.h
        fh, fw = fr.shape[:2]
        r = z if z < 0.75 else 1.0                                      # heavy downscale: area-average first, then a gentle warp
        src = cv2.resize(fr, (max(1, int(round(fw * r))), max(1, int(round(fh * r)))), interpolation=cv2.INTER_AREA) if r != 1.0 else fr
        s = z / r
        sx, sy = cx * src.shape[1] / fw, cy * src.shape[0] / fh
        M = np.array([[s, 0, W / 2 - s * sx], [0, s, H / 2 - s * sy]], np.float64)
        out = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC if s != 1.0 else cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
        x0, y0 = W / 2 - z * cx, H / 2 - z * cy
        x1, y1 = x0 + z * fw, y0 + z * fh
        if x0 <= 0.5 and y0 <= 0.5 and x1 >= W - 0.5 and y1 >= H - 0.5:
            return out.astype(np.float32)
        m = np.ones((src.shape[0], src.shape[1]), np.float32)
        a = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)[:, :, None]
        return self._ambient() * (1 - a) + out.astype(np.float32) * a

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        sty = lambda k, dv: bundle.sv("label_strip", k, dv)
        d.update(label_y_top_pct=sty("y_top_pct", 79.4), label_y_bottom_pct=sty("y_bottom_pct", 93.3), label_opacity=sty("opacity", 0.8),
                 label_text_x_pct=sty("text_x_pct", 7.0), label_right_fade_pct=sty("right_fade_pct_of_width", 20), label_size_px=sty("first_line_px_1080p", 58))
        t = context.get("label") or context.get("text")
        if isinstance(t, str) and t.strip():
            d["label"] = t
        return d


def _probe(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return (fps, n, w, h)


def _source_line(text, size, x, y, W, H):
    from PIL import Image, ImageDraw
    ft = C.font("reg", size)
    w = int(ImageDraw.Draw(Image.new("L", (10, 10))).textlength(text, font=ft)) + 12
    im = Image.new("RGBA", (max(w, 1), size + 12), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 2), text, font=ft, fill=(255, 255, 255, 235))
    return vfx.Layer(np.array(im), x, y)
