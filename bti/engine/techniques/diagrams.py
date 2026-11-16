"""Procedural diagrams used as stand-ins in the Arnolfini episode.

  STATIC-06 (map_route)    a grey procedural map with a drawn route between two named places
  DIA-07    (eye_diagram)  convex-mirror optics: parallel rays hit a curved mirror and spread out

Coordinates of map points and the mirror are CANVAS pixels (1920x1080), not source pixels: these shots have no image.
Lifted from build_v2.py map_shot and dia_mirror_shot.  Randomness is seeded (param `seed`).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique
from ..vfx import ramp, text_layer


@technique("STATIC-06", "base")
class RouteMap(BaseRenderer):
    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        W, H = ctx.w, ctx.h
        self.a, self.b, self.ctrl = tuple(int(v) for v in p["from_point"]), tuple(int(v) for v in p["to_point"]), tuple(int(v) for v in p["control_point"])
        self.bg = ctx.cached(("routemap_bg", int(p["seed"])), lambda: self._background(W, H, int(p["seed"])))
        a, b, c = self.a, self.b, self.ctrl
        u = np.linspace(0, 1, 120)
        self.pts = np.array([[(1 - v) ** 2 * a[0] + 2 * (1 - v) * v * c[0] + v * v * b[0], (1 - v) ** 2 * a[1] + 2 * (1 - v) * v * c[1] + v * v * b[1]] for v in u])
        self.names = [(p["from_label"], self.a), (p["to_label"], self.b)]
        self.labels = [ctx.layer(("map", n, c), (lambda n=n, c=c: text_layer(n, c[0], c[1] - 60, 38, "reg", 4, w=W, h=H))) for n, c in self.names]
        self.color = hex_to_bgr(p["route_color"])

    @staticmethod
    def _background(W, H, seed):
        f = np.zeros((H, W, 3), np.float32) + (150, 150, 150)
        r = np.random.RandomState(seed)
        for _ in range(22):
            c = (int(r.randint(0, W)), int(r.randint(0, H)))
            cv2.ellipse(f, c, (int(r.randint(160, 420)), int(r.randint(80, 220))), int(r.randint(0, 180)), 0, 360, (172, 170, 168), -1, cv2.LINE_AA)
        f = cv2.GaussianBlur(f, (0, 0), 4)
        for gx in range(0, W, 160):
            cv2.line(f, (gx, 0), (gx, H), (140, 140, 140), 1)
        for gy in range(0, H, 160):
            cv2.line(f, (0, gy), (W, gy), (140, 140, 140), 1)
        return f

    def render(self, t):
        p = self.p
        f = self.bg.copy()
        pts, col = self.pts, self.color
        tdraw = self.t0 + float(p["draw_delay_s"])
        pr = ramp(t, tdraw, float(p["route_draw_s"]), "inout_sine")
        n = int(len(pts) * pr)
        for i in range(0, n - 1, 2):
            cv2.line(f, tuple(pts[i].astype(int)), tuple(pts[min(i + 1, n - 1)].astype(int)), col, 7, cv2.LINE_AA)
        for k, ((name, c), layer) in enumerate(zip(self.names, self.labels)):
            cv2.circle(f, c, 22, (255, 255, 255), 4, cv2.LINE_AA)
            layer.apply(f, ramp(t, self.t0 + float(p["label_delay_s"]) + float(p["label_stagger_s"]) * k, .3))
        if n > 30:
            e = pts[n - 1]
            v = pts[n - 1] - pts[n - 6]
            v /= np.linalg.norm(v) + 1e-6
            l = np.array([-v[1], v[0]])
            cv2.fillConvexPoly(f, np.array([e + v * 26, e - v * 18 + l * 18, e - v * 18 - l * 18], np.int32), col, cv2.LINE_AA)
        return f


@technique("DIA-07", "base")
class MirrorDiagram(BaseRenderer):
    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        W, H = ctx.w, ctx.h
        cap = self.p["caption"]
        self.cap = ctx.layer(("dia07cap", cap), lambda: text_layer(cap, W // 2, 960, 34, "reg", 4, w=W, h=H))

    def render(self, t):
        p = self.p
        W, H = self.ctx.w, self.ctx.h
        f = np.zeros((H, W, 3), np.float32) + 10
        c = (1300, 540)
        pr = ramp(t, self.t0 + float(p["draw_delay_s"]), float(p["draw_s"]), "inout_sine")
        cv2.ellipse(f, (c[0] + 330, c[1]), (330, 330), 0, 150, 210, (230, 230, 230), 8, cv2.LINE_AA)
        cv2.arrowedLine(f, (330, 780), (330, 380), (60, 190, 255), 8, cv2.LINE_AA, 0, .12)
        n = int(p["ray_count"])
        for k in range(n):
            y = int(c[1] + (k - (n - 1) / 2) * 160)
            q0 = (330, y)
            hit = (int(c[0] - (330 - math.sqrt(max(330 ** 2 - (y - c[1]) ** 2, 1)))), y)
            e1 = (int(q0[0] + (hit[0] - q0[0]) * min(pr * 2, 1)), y)
            cv2.line(f, q0, e1, (255, 255, 255), 3, cv2.LINE_AA)
            if pr > .5:
                kk = (pr - .5) * 2
                cv2.line(f, hit, (int(hit[0] - 600 * kk), int(y + (y - c[1]) * .7 * kk)), (40, 190, 255), 3, cv2.LINE_AA)
        self.cap.apply(f, ramp(t, self.t0 + float(p["caption_delay_s"]), .4))
        return f
