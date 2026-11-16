"""STATIC-07: circular multi-cell diagram (sectors holding crops of one image, with labels, appearing in a stagger).

Lifted from build_reel.py st07.  Timing (relative to the shot start): cell i fades in at appear_delay_s + stagger_s * i over fade_s; its label
fades with it; the outline circle is always drawn.  The crops are static, so each sector (crop x mask, cropped to its bounding box) is built once.
"""
from __future__ import annotations

import math
import os

import cv2
import numpy as np

from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import ramp
from . import _t3common as C


def _num(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@technique("STATIC-07", "base")
class CircleDiagram(BaseRenderer):
    """`labels` / `centers` / `zooms` are parallel lists (one entry per sector, in clockwise order from start_angle_deg).
    centers: region names of the slot image or [x, y] source pixels; missing ones are spread over the image; zooms: screen px per source px
    (missing or empty -> cell_zoom). The number of sectors is the longest of labels and centers (at most 12)."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.key = self.slot_asset("image")
        labels = [str(l) for l in (p["labels"] or [])]
        centers = list(p["centers"] or [])
        self.n = min(12, max(len(labels), len(centers)))
        self.labels = labels + [""] * (self.n - len(labels))
        iw, ih = ctx.asset_size(self.key) if self.key else (ctx.w, ctx.h)
        self.cells = []
        zooms = list(p["zooms"] or [])
        for i in range(self.n):
            if i < len(centers):
                try:
                    c = ctx.point(centers[i], self.key)
                except Exception:
                    c = (iw / 2.0, ih / 2.0)
            else:
                a = 2 * math.pi * i / max(self.n, 1) - math.pi / 2
                c = (iw / 2.0 + 0.22 * iw * math.cos(a), ih / 2.0 + 0.22 * ih * math.sin(a))
            z = _num(zooms[i], None) if i < len(zooms) else None
            self.cells.append((c[0], c[1], z if z and z > 0 else float(p["cell_zoom"])))
        W, H, R = ctx.w, ctx.h, int(p["radius_px"])
        self.centre = (W // 2, H // 2)
        size, trk = int(p["label_size_px"]), int(p["label_tracking_px"])
        self.label_layers = []
        for i, name in enumerate(self.labels):
            sw = 360.0 / max(self.n, 1)
            mid = (math.radians(sw * i + float(p["start_angle_deg"])) + math.radians(sw * (i + 1) + float(p["start_angle_deg"]))) / 2
            lx = int(self.centre[0] + (R + float(p["label_gap_x_px"])) * math.cos(mid))
            ly = int(self.centre[1] + (R + float(p["label_gap_y_px"])) * math.sin(mid))
            L = ctx.layer(("t3c7lab", name, lx, ly, size, trk, p["font_kind"], bool(p["shadow"])),
                          lambda name=name, lx=lx, ly=ly: C.block_layer(W, H, [{"text": name, "size": size, "kind": p["font_kind"], "tracking": trk}],
                                                                        lx, ly, bool(p["shadow"])))
            self.label_layers.append(L)
        self.bg = np.array(hex_to_bgr(p["background"]), np.float32)

    def _sector(self, i):
        """(y0, y1, x0, x1, crop float32, mask float32) of sector i, cached."""
        ctx, p = self.ctx, self.p
        W, H, R, n = ctx.w, ctx.h, int(p["radius_px"]), self.n
        cx, cy, z = self.cells[i]
        path = ctx.asset_path(self.key)
        key = ("t3c7sec", path, os.stat(path).st_mtime_ns, cx, cy, z, i, n, R, float(p["start_angle_deg"]), int(p["edge_erode_px"]))

        def build():
            sweep = 360.0 / n
            ang0 = math.radians(sweep * i + float(p["start_angle_deg"]))
            ang1 = math.radians(sweep * (i + 1) + float(p["start_angle_deg"]))
            c = self.centre
            mk = np.zeros((H, W), np.uint8)
            if n == 1:
                cv2.circle(mk, c, R, 255, -1, cv2.LINE_AA)
            else:
                npts = max(8, int(round(24 * sweep / 60.0)))
                pts = [c] + [(int(c[0] + R * math.cos(x)), int(c[1] + R * math.sin(x))) for x in np.linspace(ang0, ang1, npts)]
                cv2.fillConvexPoly(mk, np.array(pts, np.int32), 255, cv2.LINE_AA)
            e = int(p["edge_erode_px"])
            if e > 0:
                mk = cv2.erode(mk, np.ones((e, e), np.uint8))
            ys, xs = np.where(mk > 0)
            if ys.size == 0:
                return (0, 1, 0, 1, np.zeros((1, 1, 3), np.float32), np.zeros((1, 1, 1), np.float32))
            y0, y1, x0, x1 = int(ys.min()), int(ys.max()) + 1, int(xs.min()), int(xs.max()) + 1
            ov = ctx.image(self.key).view(cx, cy, z, W, H)[0][y0:y1, x0:x1].astype(np.float32)
            m = (mk[y0:y1, x0:x1].astype(np.float32) / 255)[:, :, None]
            return (y0, y1, x0, x1, ov, m)
        return ctx.cached(key, build, lambda r: r[4].nbytes + r[5].nbytes)

    def render(self, t):
        ctx, p = self.ctx, self.p
        f = np.zeros((ctx.h, ctx.w, 3), np.float32) + self.bg
        tt = t - self.t0
        if self.key:
            for i in range(self.n):
                a = ramp(tt, float(p["appear_delay_s"]) + float(p["stagger_s"]) * i, float(p["fade_s"]))
                if a <= 0:
                    continue
                y0, y1, x0, x1, ov, mk = self._sector(i)
                m = mk * a
                f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - m) + ov * m
                f = self.label_layers[i].apply(f, a)
        th = int(p["outline_px"])
        if th > 0:
            cv2.circle(f, self.centre, int(p["radius_px"]), (255, 255, 255), th, cv2.LINE_AA)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a = C.asset_dict(context)
        regs = a.get("regions")
        if isinstance(regs, dict) and regs:
            names = list(regs)[:6]
            d["centers"] = names
            d["labels"] = [str((regs[n] or {}).get("label") or n).upper() for n in names]
            d["zooms"] = []
        return d
