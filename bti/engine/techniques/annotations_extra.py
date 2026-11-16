"""Annotation overlays and one base shot: AN-02, AN-03, AN-04, AN-06, AN-07, X-ANN-04, X-ANN-05.

Overlays draw through the parent shot's `View` (source pixels -> canvas), except the map annotations, which can also bring their
own backdrop (`background`: base / image / procedural, see `_t2_common.MapBackdrop`).  Sizes named *_px are CANVAS pixels (line
widths, marker sizes, text) so they stay legible whatever the camera does; positions are SOURCE pixels of the image they refer to.

Timing semantics (overlay start .. end), written down because they are part of the technique:
  AN-02    outline draws from start over draw_s; the base dims to `dim_base` over dim_ramp_s from start; everything fades out so that it
           is gone at end (fade_s before it); nothing is drawn at or after end.
  AN-03    ray i starts at start + i * stagger_s and takes each_draw_s; same dim and fade-out as AN-02.
  AN-04    ring i + label i appear at start + label_delay_s + i * label_stagger_s; the route draws from start + route_delay_s over route_draw_s,
           the arrow head follows its tip; the whole annotation fades out ending at end.
  AN-06    grid draws over grid_draw_s from start, the region fades in from start + region_delay_s over region_fade_s; fade-out ends at end.
  AN-07    (base shot) densifies over densify_frac of the shot, then cross-fades to the picture.
  X-ANN-04 group i is drawn from start + i * (per_group_draw_s + gap_s) ...; see the class.
  X-ANN-05 marker i pops in at start + start_delay_s + i * stagger_s; all markers fade out ending at end.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..base import BaseRenderer, OverlayRenderer, View
from ..registry import technique
from ..vfx import compose_matte, ease, ramp, blend
from . import _t2_common as C
from ._t2_common import (blend_color, dense_path, dim, draw_progress, hex_bgr, mask_contours, numbered_slots, out_env, slot_key,
                         stamp_circle, text_at, to_screen_arr)

EASE_NAMES = C.EASES


def _defaults(spec):
    return {p["name"]: p["default"] for p in spec["params"]}


def _asset_wh(context):
    a = context.get("asset") or {}
    return float(a.get("w") or 0), float(a.get("h") or 0)


# ============================================================================= AN-02
class _PathOverlay(OverlayRenderer):
    """Common part of AN-02 and X-ANN-04: path sources (mask contours or user points) in source pixels."""

    def _image_key(self, view):
        return view.asset_key

    def _path_from_points(self, pts, view, closed):
        key = view.asset_key
        res = [tuple(self.ctx.point(p, key)) for p in pts]
        return self.ctx.cached(("t2dense", tuple(res), bool(closed)), lambda: dense_path(res, closed))

    def _mask_paths(self, mask_key, max_n):
        return mask_contours(self.ctx, mask_key, None, max_n=max_n)


@technique("AN-02", "overlay")
class ObjectOutline(_PathOverlay):
    """A line traced progressively round an object: contour(s) of the `mask` slot, or a polyline from `points`."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        self.mask_key = slot_key(ov, "mask")

    def _paths(self, view):
        p = self.p
        if p.get("points"):
            return [self._path_from_points(p["points"], view, bool(p["closed"]))]
        if self.mask_key:
            return self._mask_paths(self.mask_key, int(p["max_contours"]))
        return []

    def apply(self, f, t, view):
        p = self.p
        if view is None or t < self.t0 or t >= self.t1:
            return f
        out = out_env(t, self.t1, float(p["fade_s"]))
        if out <= 0:
            return f
        paths = self._paths(view)
        if not paths:
            return f
        f = dim(f, float(p["dim_base"]), ramp(t, self.t0, float(p["dim_ramp_s"]), "inout_sine") * out)
        prog = ramp(t, self.t0, float(p["draw_s"]), p["ease"])
        if prog <= 0:
            return f
        canvas = np.zeros((self.ctx.h, self.ctx.w), np.uint8)
        draw_progress(canvas, [to_screen_arr(view, c) for c in paths], prog, p["stroke_px"], closed=bool(p["closed"]) if p.get("points") else True)
        return blend_color(f, canvas, hex_bgr(p["color"]), float(p["opacity"]) * out)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _defaults(spec)


# ============================================================================= AN-03
@technique("AN-03", "overlay")
class PerspectiveRays(OverlayRenderer):
    """Lines drawn one after another from the frame edge (or from source points) to a vanishing point."""

    def apply(self, f, t, view):
        p = self.p
        if view is None or t < self.t0 or t >= self.t1:
            return f
        out = out_env(t, self.t1, float(p["fade_s"]))
        if out <= 0:
            return f
        W, H = self.ctx.w, self.ctx.h
        vp = view.to_screen(*self.ctx.point(p["vanishing_point"], view.asset_key))
        origins = list(p["origins"] or [])[: int(p["ray_count"])]
        f = dim(f, float(p["dim_base"]), ramp(t, self.t0, float(p["dim_ramp_s"]), "inout_sine") * out)
        canvas = np.zeros((H, W), np.uint8)
        drawn = False
        for i, o in enumerate(origins):
            pr = ramp(t, self.t0 + float(p["stagger_s"]) * i, float(p["each_draw_s"]), "out_quad")
            if pr <= 0:
                continue
            if p["origin_space"] == "frame":
                a = (float(o[0]) * W, float(o[1]) * H)
            else:
                a = view.to_screen(*self.ctx.point(o, view.asset_key))
            q = (int(a[0] + (vp[0] - a[0]) * pr), int(a[1] + (vp[1] - a[1]) * pr))
            cv2.line(canvas, (int(a[0]), int(a[1])), q, 255, int(p["line_px"]), cv2.LINE_AA)
            drawn = True
        if not drawn:
            return f
        return blend_color(f, canvas, hex_bgr(p["color"]), float(p["opacity"]) * out)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        w, h = _asset_wh(context)
        if w:
            d["vanishing_point"] = [round(w / 2, 1), round(h * 0.39, 1)]
        return d


# ============================================================================= AN-04 / X-ANN-05 (maps)
def _map_defaults(d, context, scale_keys):
    """Registry defaults are canvas pixels of the procedural map; scale them to a real map image when the context has one."""
    w, h = _asset_wh(context)
    if w:
        sx, sy = w / 1920.0, h / 1080.0
        for k in scale_keys:
            v = d.get(k)
            if isinstance(v, list) and v and isinstance(v[0], list):
                d[k] = [[round(x * sx, 1), round(y * sy, 1)] for x, y in v]
            elif isinstance(v, list) and len(v) == 2 and not isinstance(v[0], str):
                d[k] = [round(v[0] * sx, 1), round(v[1] * sy, 1)]
    return d


@technique("AN-04", "overlay")
class MapCircleArrow(OverlayRenderer):
    """Rings on named places and an arrowed route between the first and the last of them, with place labels.
    `background`: auto (map slot if present, else the procedural stand-in), base, image or procedural."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        self.bd = C.MapBackdrop(ctx, ov, self.p["background"], int(self.p["seed"]))

    def apply(self, f, t, view):
        p = self.p
        if t < self.t0 or t >= self.t1:
            return f
        out = out_env(t, self.t1, float(p["fade_s"]))
        if out <= 0:
            return f
        base = f
        g, tos, _ = self.bd.frame(f.copy() if self.bd.mode == "base" else f, view)
        if tos is None:
            return f
        places = [tos(pt) for pt in (p["places"] or [])]
        if len(places) < 1:
            return f
        W, H = self.ctx.w, self.ctx.h
        col = hex_bgr(p["route_color"])
        # route: quadratic Bezier from the first to the last place
        if len(places) >= 2:
            a, b = np.array(places[0], np.float64), np.array(places[-1], np.float64)
            if p["control"] is not None:
                c = np.array(tos(p["control"]), np.float64)
            else:
                d = b - a
                nrm = np.array([-d[1], d[0]]) / (np.hypot(*d) + 1e-6)
                if nrm[1] > 0:
                    nrm = -nrm
                c = (a + b) / 2 + nrm * float(p["bend"]) * np.hypot(*d)
            u = np.linspace(0, 1, 120)[:, None]
            pts = (1 - u) ** 2 * a + 2 * (1 - u) * u * c + u * u * b
            pr = ramp(t, self.t0 + float(p["route_delay_s"]), float(p["route_draw_s"]), "inout_sine")
            n = int(len(pts) * pr)
            m = np.zeros((H, W), np.uint8)
            if n > 2:
                step = 2 if p["dashed"] else 1
                for i in range(0, n - 1, step):
                    cv2.line(m, tuple(pts[i].astype(int)), tuple(pts[min(i + 1, n - 1)].astype(int)), 255, int(p["route_px"]), cv2.LINE_AA)
            if n > int(len(pts) * float(p["arrow_after"])):
                e = pts[n - 1]
                v = pts[n - 1] - pts[n - 6]
                v = v / (np.linalg.norm(v) + 1e-6)
                l = np.array([-v[1], v[0]])
                s = float(p["arrow_px"]) / 26.0
                tri = np.array([e + v * 26 * s, e - v * 18 * s + l * 18 * s, e - v * 18 * s - l * 18 * s], np.int32)
                cv2.fillConvexPoly(m, tri, 255, cv2.LINE_AA)
            g = blend_color(g, m, col, 1.0)
        ring_col = hex_bgr(p["ring_color"])
        for k, (x, y) in enumerate(places):
            tk = self.t0 + float(p["label_delay_s"]) + float(p["label_stagger_s"]) * k
            stamp_circle(g, x, y, float(p["ring_radius_px"]), ring_col, ramp(t, self.t0 + float(p["ring_delay_s"]), float(p["ring_fade_s"])), float(p["ring_px"]))
            labels = p["labels"] or []
            if k < len(labels) and labels[k]:
                L = text_at(self.ctx, str(labels[k]), int(p["label_px"]), int(p["label_tracking"]))
                L.apply(g, ramp(t, tk, float(p["label_fade_s"])), int(x) - W // 2, int(y - float(p["label_offset_px"])) - H // 2)
        return g if out >= 1 else base * (1 - out) + g * out

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _map_defaults(_defaults(spec), context, ("places", "control"))
        if context.get("text"):
            d["labels"] = [context["text"]] + list(d["labels"] or [])[1:]
        return d


@technique("X-ANN-05", "overlay")
class MapMarkers(OverlayRenderer):
    """Red dots appearing one by one on a map, optionally with a place label and a short pulse ring."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        self.bd = C.MapBackdrop(ctx, ov, self.p["background"], int(self.p["seed"]))

    def apply(self, f, t, view):
        p = self.p
        if t < self.t0 or t >= self.t1:
            return f
        out = out_env(t, self.t1, float(p["fade_s"]))
        if out <= 0:
            return f
        base = f
        g, tos, _ = self.bd.frame(f.copy() if self.bd.mode == "base" else f, view)
        if tos is None:
            return f
        pts = list(p["points"] or [])
        if p["marker_count"]:
            pts = pts[: int(p["marker_count"])]
        W, H = self.ctx.w, self.ctx.h
        col, ocol = hex_bgr(p["color"]), hex_bgr(p["outline_color"])
        r0 = float(p["radius_px"])
        labels = p["labels"] or []
        for k, pt in enumerate(pts):
            tk = self.t0 + float(p["start_delay_s"]) + float(p["stagger_s"]) * k
            u = (t - tk) / max(float(p["pop_s"]), 1e-3)
            if u <= 0:
                continue
            x, y = tos(pt)
            s = 0.35 + 0.65 * ease("out_cubic", u)
            al = min(1.0, u * 3)
            if p["pulse"]:
                pu = (t - tk) / max(float(p["pulse_s"]), 1e-3)
                if 0 < pu < 1:
                    stamp_circle(g, x, y, r0 * (1 + 1.6 * ease("out_cubic", pu)), col, 0.7 * (1 - pu), 3)
            if float(p["outline_px"]) > 0:
                stamp_circle(g, x, y, r0 * s + float(p["outline_px"]) / 2, ocol, al)
            stamp_circle(g, x, y, r0 * s, col, al)
            if k < len(labels) and labels[k]:
                L = text_at(self.ctx, str(labels[k]), int(p["label_px"]), int(p["label_tracking"]))
                L.apply(g, ramp(t, tk + float(p["label_delay_s"]), float(p["label_fade_s"])), int(x) - W // 2, int(y - float(p["label_offset_px"])) - H // 2)
        return g if out >= 1 else base * (1 - out) + g * out

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _map_defaults(_defaults(spec), context, ("points",))


# ============================================================================= AN-06
@technique("AN-06", "overlay")
class GridGeometry(OverlayRenderer):
    """A rule-of-thirds style grid drawn over the picture and one translucent geometric region (triangle, circle or rectangle).
    `space`: frame (positions are fractions 0..1 of the canvas, as in the benchmark) or image (source pixels, follows the camera; the
    grid then divides the image rectangle)."""

    def _shape_mask(self, view):
        p = self.p
        W, H = self.ctx.w, self.ctx.h
        pts = p["shape_points"] or []
        if not pts:
            return None
        if p["space"] == "frame":
            sp = [(float(x) * W, float(y) * H) for x, y in pts]
        else:
            sp = [view.to_screen(*self.ctx.point(q, view.asset_key)) for q in pts]
        m = np.zeros((H, W), np.uint8)
        shape = p["shape"]
        if shape == "triangle" and len(sp) >= 3:
            cv2.fillConvexPoly(m, np.array(sp[:3], np.float32).astype(np.int32), 255, cv2.LINE_AA)
        elif shape == "circle" and len(sp) >= 2:
            r = float(np.hypot(sp[1][0] - sp[0][0], sp[1][1] - sp[0][1]))
            cv2.circle(m, (int(sp[0][0]), int(sp[0][1])), int(r), 255, -1, cv2.LINE_AA)
        elif shape == "rect" and len(sp) >= 2:
            cv2.rectangle(m, (int(sp[0][0]), int(sp[0][1])), (int(sp[1][0]), int(sp[1][1])), 255, -1, cv2.LINE_AA)
        else:
            return None
        return m

    def _grid_lines(self, view):
        """[(x0, y0, x1, y1)] screen segments (full length) of the vertical then horizontal grid lines."""
        p = self.p
        W, H = self.ctx.w, self.ctx.h
        nc, nr = int(p["grid_cols"]), int(p["grid_rows"])
        if p["space"] == "frame":
            x0, y0, x1, y1 = 0, 0, W, H
        else:
            x0, y0 = view.to_screen(0, 0)
            x1, y1 = view.to_screen(view.img.w, view.img.h)
        v = [(x0 + (x1 - x0) * k / nc, y0, x0 + (x1 - x0) * k / nc, y1) for k in range(1, nc)]
        h = [(x0, y0 + (y1 - y0) * k / nr, x1, y0 + (y1 - y0) * k / nr) for k in range(1, nr)]
        return v, h

    def apply(self, f, t, view):
        p = self.p
        if t < self.t0 or t >= self.t1 or (view is None and p["space"] == "image"):
            return f
        out = out_env(t, self.t1, float(p["fade_s"]))
        if out <= 0:
            return f
        W, H = self.ctx.w, self.ctx.h
        f = dim(f, float(p["dim_base"]), ramp(t, self.t0, float(p["dim_ramp_s"]), "inout_sine") * out)
        gp = ramp(t, self.t0, float(p["grid_draw_s"]))
        if gp > 0:
            m = np.zeros((H, W), np.uint8)
            v, h = self._grid_lines(view)
            lt = cv2.LINE_AA if p["grid_antialias"] else cv2.LINE_8
            for (a, b, c, d) in v:
                cv2.line(m, (int(a), int(b)), (int(c), int(b + (d - b) * gp)), 255, int(p["grid_px"]), lt)
            for (a, b, c, d) in h:
                cv2.line(m, (int(a), int(b)), (int(a + (c - a) * gp), int(d)), 255, int(p["grid_px"]), lt)
            f = blend_color(f, m, hex_bgr(p["grid_color"]), float(p["grid_opacity"]) * out)
        ra = float(p["region_opacity"]) * ramp(t, self.t0 + float(p["region_delay_s"]), float(p["region_fade_s"])) * out
        if ra > 0:
            sm = self._shape_mask(view)
            if sm is not None:
                f = blend_color(f, sm, hex_bgr(p["region_color"]), ra)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _defaults(spec)


# ============================================================================= AN-07
@technique("AN-07", "base")
class DotField(BaseRenderer):
    """The picture (on the matte, camera `camera`) re-drawn as a field of round dots that multiplies and shrinks until it resolves into the
    picture.  Dot colours are sampled from the live picture; positions come from a seeded generator."""

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        self.key = self.slot_asset("image")
        keys = C.keys_from_param(shot, ctx, "camera")
        if keys is None:
            w, h = ctx.asset_size(self.key)
            keys = C.fit_key(self.t0, w, h)
        self.cam = C.Track(keys, "log")
        n_max = int(self.p["dots_end"])
        seed, W, H = int(self.p["seed"]), ctx.w, ctx.h

        def build():
            r = np.random.RandomState(seed)
            return r.randint(0, W, n_max), r.randint(0, H, n_max)
        self.xs, self.ys = ctx.cached(("t2dots", seed, n_max, W, H), build, lambda a: a[0].nbytes * 2)

    def view(self, t):
        cx, cy, z = self.cam.at(t)
        return View(cx, cy, z, self.ctx.image(self.key), self.key)

    def render(self, t):
        p, ctx = self.p, self.ctx
        v = self.view(t)
        base = compose_matte(v.img, v.cx, v.cy, v.z, ctx.w, ctx.h, shadow=bool(p["shadow"]))
        d = max(self.t1 - self.t0, 1e-6)
        lt = t - self.t0
        pg = ease(p["ease"], lt / (d * float(p["densify_frac"])))
        n0, n1 = int(p["dots_start"]), int(p["dots_end"])
        n = int(n0 + (n1 - n0) * pg ** float(p["count_curve"]))
        rad = max(float(p["radius_end_px"]), float(p["radius_start_px"]) * (1 - pg) ** float(p["radius_curve"]) + float(p["radius_end_px"]))
        ov = np.zeros_like(base) + float(p["paper_level"])
        gain, off = float(p["colour_gain"]), float(p["colour_offset"])
        r_i = int(rad)
        xs, ys = self.xs[:n], self.ys[:n]
        cols = np.clip(base[ys, xs] * gain + off, 0, 255)
        for i in range(n):
            c = cols[i]
            cv2.circle(ov, (int(xs[i]), int(ys[i])), r_i, (float(c[0]), float(c[1]), float(c[2])), -1, cv2.LINE_AA)
        if not p["crossfade_to_painting"]:
            return ov
        mix = ramp(t, self.t0 + d * float(p["crossfade_start_frac"]), d * float(p["crossfade_frac"]))
        return blend(ov, base, mix)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = _defaults(spec)
        a = context.get("asset") or {}
        if a.get("w") and a.get("h"):
            w, h = float(a["w"]), float(a["h"])
            z = 0.955 * 1080.0 / h
            d["camera"] = [C.cam_key_json(0.0, w / 2, h / 2, z), C.cam_key_json(1.0, w / 2, h / 2, z)]
        return d


# ============================================================================= X-ANN-04
@technique("X-ANN-04", "overlay")
class SequentialGroupOutlines(_PathOverlay):
    """Outlines drawn round several groups one after another.

    Groups come from slots `mask_1 .. mask_6` (contours) or params `points_1 .. points_6` (polylines in source pixels); a group with
    points wins over its mask.  The first `group_count` groups that exist are used (0 = all).  Group i starts drawing at
    start + i * (per_group_draw_s + gap_s).  After the hold, `after_hold` decides: `clear` fades each outline `fade_s` after `hold_s`
    (the groups are shown one at a time), `keep` leaves it until the end, where, if `clear_all_at_end`, everything fades together
    so as to be gone at end (the painting stays).  `per_group_draw_s` null spreads the groups over the overlay's duration."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        masks = dict(numbered_slots(ov, "mask"))
        src = []
        for i in range(1, 7):
            if self.p.get("points_%d" % i):
                src.append(("points", self.p["points_%d" % i]))
            elif i in masks:
                src.append(("mask", masks[i]))
        n = int(self.p["group_count"])
        self.groups = src[:n] if n > 0 else src

    def _timeline(self):
        p = self.p
        n = max(len(self.groups), 1)
        hold, fade, gap = float(p["hold_s"]), float(p["fade_s"]), float(p["gap_s"])
        dur = max(self.t1 - self.t0, 0.1)
        if p["per_group_draw_s"] is not None:
            draw = float(p["per_group_draw_s"])
        elif p["after_hold"] == "keep":
            draw = (dur - hold - (fade if p["clear_all_at_end"] else 0) - (n - 1) * gap) / n
        else:
            draw = dur / n - hold - fade - gap
        return max(draw, 0.3), gap

    def apply(self, f, t, view):
        p = self.p
        if view is None or t < self.t0 or t >= self.t1 or not self.groups:
            return f
        draw, gap = self._timeline()
        hold, fade = float(p["hold_s"]), float(p["fade_s"])
        W, H = self.ctx.w, self.ctx.h
        keep = p["after_hold"] == "keep"
        end_env = out_env(t, self.t1, fade) if (keep and p["clear_all_at_end"]) else 1.0
        if end_env <= 0:
            return f
        items = []
        for i, (kind, src) in enumerate(self.groups):
            ts = self.t0 + i * (draw + gap)
            prog = ramp(t, ts, draw, p["ease"])
            if prog <= 0:
                continue
            al = end_env
            if not keep:
                al = 1 - ramp(t, ts + draw + hold, fade)
            if al <= 0:
                continue
            paths = [self._path_from_points(src, view, True)] if kind == "points" else self._mask_paths(src, int(p["max_contours"]))
            items.append((prog, al, paths))
        if items:
            f = dim(f, float(p["dim_base"]), ramp(t, self.t0, float(p["dim_ramp_s"]), "inout_sine") * out_env(t, self.t1, fade))
        col = hex_bgr(p["color"])
        for prog, al, paths in items:
            m = np.zeros((H, W), np.uint8)
            draw_progress(m, [to_screen_arr(view, c) for c in paths], prog, p["stroke_px"])
            f = blend_color(f, m, col, float(p["opacity"]) * al)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return _defaults(spec)
