"""MAP-01, the atlas map: real geography (Natural Earth, bundled), Web Mercator, drawn at the frame's resolution every frame.

The look is the approved moving mock-up (`docs/design/mock/2026-11-18-explainer/components.html`, function `plate`): paper land, a sea
that has its own colour and is darker toward the coast (two presets), an ink coastline, two water lines in the sea, a graticule,
a place mark (accent dot inside an ink ring) with an italic label that appears on the word that names the place, a dotted accent route
drawn progressively with a travelling head, a tinted country, sea names in small capitals, paper grain and a vignette pinned to the
screen, and an eased push of the camera from a wide view to a view fitted to the places. Contract: docs/design/2026-11-18-explainer-components.md
sections 3, 4 (MAP-01), 5 and 6.

How a frame is made (all at 1920 x 1080, a pure function of the time):
  1. the view at time t: a centre and a ground width, eased between the start view and the end view (`geo.ease_view`);
  2. the land mask: the rings of the bundled land layer (1:10m for views narrower than 1,500 km, else 1:50m) projected and filled
     (anti-aliased) on a canvas that is 96 px larger than the frame on every side;
  3. a distance transform of the sea gives the distance of every sea pixel to the coast; ONE lookup table (distance -> colour) then
     paints the sea, its shade toward the coast (the blurred stroke of the mock-up has this profile), the flat strip of sea along the
     coast, and the two water lines. Land is the table's entry for distance 0. Cheap: one distance transform and one lookup per frame;
  4. graticule and the ink coastline (anti-aliased polylines), the tinted region, the dotted route and its head;
  5. paper grain and the vignette (a gain and an offset image made once, pinned to the screen);
  6. sea names, place marks and labels, which stay the same size in pixels while the map scales and only follow their positions.
Widths that live in map space in the mock-up (shade, water lines, route dots) scale with the push (`k`, the zoom since the start view,
held to 0.6 .. 1.65 so a push of a hundred times does not smear them); marks, labels and the hairlines keep their pixel size.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .. import geo
from .. import registry as R
from .. import vfx
from ..base import BaseRenderer, hex_to_bgr
from ..registry import technique

W, H = 1920, 1080
PAD = 96                                            # the working canvas is this much larger than the frame on every side
IDX_PER_PX = 2.5                                    # lookup table resolution: 2.5 entries per pixel of distance (up to 102 px)

# ---- colours (contract section 5)
INK, ACCENT = "#3B2F26", "#8C2F23"
PRESETS = {
    "blue_grey": {"land": "#F3EBD9", "sea": "#AFC6C4", "shade": "#6F9796", "shade_a": 0.55, "w1": 0.26, "w2": 0.42},
    "sepia": {"land": "#F5EEDF", "sea": "#C6B592", "shade": "#8E7A52", "shade_a": 0.50, "w1": 0.22, "w2": 0.36},
}
# ---- map-space widths of the mock-up at scale 1 (px of a 1920 x 1080 frame)
SHADE_HALF, SHADE_SIGMA = 26.0, 11.0                # the stroke of 52 px, blurred by 11 px
LINE1 = (11.8, 13.5)                                # the outer water line: from 11.8 to 13.5 px out of the coast
LINE2 = (5.8, 7.5)                                  # the inner one
K_MIN, K_MAX = 0.6, 1.65
# ---- screen-space sizes (percent of the frame height unless noted)
COAST_PX, COAST_A = 3, 0.85                         # ink coastline, 85 percent: the mock-up's 1.5 CSS px on a stage 540 px high is 3 px of 1080
GRAT_PX, GRAT_A = 2, 0.09                           # graticule: 1 CSS px of that stage, 9 percent
REGION_LINE_PX = 3                                  # region outline: 1.6 CSS px
MARK_R, MARK_RING, MARK_DOT = 1.15, 0.22, 0.475    # ring radius, ring thickness, dot radius
LABEL_GAP = 1.7                                    # distance from the mark to its label, at the diagonals and the sides
SEA_CAP, SEA_TRACK = 1.9, 0.14                      # sea names: cap height, tracking in em
REGION_CAP = 1.37
HALO_PX, HALO_A = 2.0, 0.85                         # a paper-coloured halo of 2 px around place labels (not in the mock-up: line work under a label no longer eats it)
DOT_D, DOT_SPACING, DOT_LEAD = 6.0, 15.0, 13.0      # route dots (map space at scale 1): diameter, spacing, reveal lead
HEAD_R, HALO_R, HALO_A = 7.5, 17.0, 0.22
SEA_NAME_ALPHA, REGION_ALPHA = 0.70, 0.85
GRAIN_COL = (0.45, 0.38, 0.30)                     # RGB of the paper-grain multiply layer of the mock-up
GRAIN_MU, GRAIN_SIGMA = 0.0213, 0.0224             # alpha of the grain: max(0, mu + sigma * z), z unit noise
VIG_COL, VIG_A, VIG_FROM = (59, 47, 38), 0.26, 0.58
SEA_MIN_SHARE = {0: 0.08, 1: 0.08, 2: 0.08, 3: 0.30}   # a sea of rank r is named when its extent is at least this share of the view width (rank 4 and up: 0.45)
LAND_UNDER_NAME = {0: 0.30, 1: 0.30}              # ... except that a major sea (rank 0, 1) may have up to 30 percent, else 10 percent
LAND_UNDER_DEFAULT = 0.10
#                             # a sea name is not printed when more of its box than this is land
MAX_VIA = 12                                       # bend points of one route
SIDES = ("auto", "n", "ne", "e", "se", "s", "sw", "w", "nw")
PREFERENCE = ("se", "ne", "e", "sw", "nw", "w", "s", "n")

NUM = r"-?\d{1,3}(?:\.\d+)?"
PAIR = NUM + r"\s*,\s*" + NUM
VIA_PATTERN = r"\s*(?:%s(?:\s*;\s*%s)*)?\s*;?\s*" % (PAIR, PAIR)
CENTER_PATTERN = r"\s*(?:%s)?\s*" % PAIR
VIA_HINT = "Gõ các điểm uốn của đường đi, mỗi điểm dạng kinh độ, vĩ độ, cách nhau bằng dấu chấm phẩy. Ví dụ: 5.5, 48.8; 7.6, 46.0"
CENTER_HINT = "Gõ kinh độ, vĩ độ, ví dụ 6.86, 47.66. Để trống thì lấy tâm của các địa điểm."


def parse_pairs(s) -> list | None:
    """`lon,lat; lon,lat` as [(lon, lat)]; [] for an empty text; None when a pair is malformed or outside the world."""
    if not isinstance(s, str):
        return None
    out = []
    for part in s.replace("\n", " ").split(";"):
        if not part.strip():
            continue
        try:
            lon, lat = (float(x) for x in part.split(","))
        except ValueError:
            return None
        if abs(lon) > 180 or abs(lat) > 85:
            return None
        out.append((lon, lat))
    return out


def seg(x, a, b):
    """0..1 progress of x over [a, b] (a step at a when b <= a)."""
    if b <= a:
        return 1.0 if x >= a else 0.0
    return min(1.0, max(0.0, (x - a) / (b - a)))


def ease_inout(x):
    x = min(1.0, max(0.0, x))
    return 2 * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 2 / 2


# ----------------------------------------------------------------------------- text patches
class Patch:
    """A pre-rendered text line: coverage (float32 h x w), a soft halo around the letters (same size), where its baseline and left edge
    sit, its width and cap height in px."""

    def __init__(self, a, left, baseline, width, cap):
        self.a, self.left, self.baseline, self.width, self.cap = a, left, baseline, width, cap
        r = max(1, int(round(HALO_PX)))
        grown = cv2.dilate(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        self.halo = np.clip(cv2.GaussianBlur(grown, (0, 0), HALO_PX * 0.5) * 1.15, 0, 1).astype(np.float32)
        self.nbytes = a.nbytes * 2 + 200


def text_patch(text: str, kind: str, cap_px: float, tracking_em: float = 0.0, upper: bool = False) -> Patch:
    text = text.upper() if upper else text
    ratio = vfx.cap_ratio(kind)
    size = max(6, int(round(cap_px / ratio)))
    ft = vfx.font(kind, size)
    trk = tracking_em * size
    if trk > 0:
        adv = [ft.getlength(c) for c in text]
        width = sum(adv) + trk * max(0, len(text) - 1)
    else:
        adv, width = None, ft.getlength(text)
    asc, desc = ft.getmetrics()
    pad = int(size * 0.25) + 2
    img = Image.new("L", (int(math.ceil(width)) + 2 * pad, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    base = pad + asc
    if adv is None:
        d.text((pad, base), text, font=ft, fill=255, anchor="ls")
    else:
        x = float(pad)
        for c, a in zip(text, adv):
            d.text((x, base), c, font=ft, fill=255, anchor="ls")
            x += a + trk
    return Patch(np.asarray(img, np.float32) / 255.0, pad, base, float(width), size * ratio)


def apply_patch(f, patch: Patch, left: float, baseline: float, bgr, alpha: float, halo=None) -> None:
    """Blend a text patch into the float frame `f` with its left edge and baseline at (left, baseline), in whole pixels. `halo` (a BGR colour)
    first paints the soft halo of the patch in that colour, so that line work under a label does not eat its letters."""
    if alpha <= 0.002:
        return
    x0, y0 = int(round(left)) - patch.left, int(round(baseline)) - patch.baseline
    h, w = patch.a.shape
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x0 + w, f.shape[1]), min(y0 + h, f.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return
    sl = (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))
    roi = f[fy0:fy1, fx0:fx1]
    if halo is not None:
        roi += (np.asarray(halo, np.float32) - roi) * (patch.halo[sl][..., None] * (HALO_A * alpha))
    roi += (np.asarray(bgr, np.float32) - roi) * (patch.a[sl][..., None] * alpha)


def blend_disc(f, cx, cy, r, bgr, alpha, r_in=0.0) -> None:
    """An anti-aliased disc (or ring when r_in > 0) blended into `f`; pixel i covers [i, i + 1)."""
    if alpha <= 0.002 or r <= 0:
        return
    x0, y0 = max(int(math.floor(cx - r - 2)), 0), max(int(math.floor(cy - r - 2)), 0)
    x1, y1 = min(int(math.ceil(cx + r + 2)), f.shape[1]), min(int(math.ceil(cy + r + 2)), f.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dist = np.hypot(xx + 0.5 - cx, yy + 0.5 - cy)
    cov = np.clip(r + 0.5 - dist, 0, 1)
    if r_in > 0:
        cov = cov - np.clip(r_in + 0.5 - dist, 0, 1)
    roi = f[y0:y1, x0:x1]
    roi += (np.asarray(bgr, np.float32) - roi) * (cov * alpha)[..., None]


def blend_mask(f, mask, bgr, alpha, box=None) -> None:
    """Blend colour `bgr` into `f` where the uint8 `mask` (same size as f) is non-zero, with opacity alpha * mask / 255 (sparse)."""
    if alpha <= 0.002:
        return
    x0, y0, x1, y1 = box if box else (0, 0, f.shape[1], f.shape[0])
    sub = mask[y0:y1, x0:x1]
    idx = np.flatnonzero(sub)
    if idx.size == 0:
        return
    roi = f[y0:y1, x0:x1].reshape(-1, 3)
    a = (sub.reshape(-1)[idx].astype(np.float32) * (alpha / 255.0))[:, None]
    roi[idx] += (np.asarray(bgr, np.float32) - roi[idx]) * a


# ----------------------------------------------------------------------------- the base map
_ERF = np.vectorize(math.erf, otypes=[np.float64])


def profile_lut(pr: dict, k: float) -> np.ndarray:
    """(256, 3) uint8 BGR: the colour of a sea pixel as a function of its distance to the coast, entry 0 being land. Distance of entry i
    is i / IDX_PER_PX - 0.5 px (a pixel next to the land is half a pixel from its edge)."""
    sea, shade, land, ink = (np.array(hex_to_bgr(pr[n]), np.float64) for n in ("sea", "shade", "land", "ink"))
    d = np.arange(256) / IDX_PER_PX - 0.5
    a, sg = SHADE_HALF * k, SHADE_SIGMA * k
    blur = 0.5 * (_ERF((a - d) / (sg * math.sqrt(2))) + _ERF((a + d) / (sg * math.sqrt(2))))   # the stroke of 2a px, blurred by sg
    flat = np.clip(d - LINE1[0] * k + 0.5, 0, 1)                                              # the strip of flat sea along the coast
    col = sea[None, :] + (shade - sea)[None, :] * (pr["shade_a"] * blur * flat)[:, None]
    for (lo, hi), op in ((LINE1, pr["w1"]), (LINE2, pr["w2"])):
        cover = np.clip(d - lo * k + 0.5, 0, 1) * np.clip(hi * k - d + 0.5, 0, 1)
        col = col + (ink - col) * (op * cover)[:, None]
    col[0] = land
    return np.clip(col + 0.5, 0, 255).astype(np.uint8)



def _edge_runs(x, y, flags, margin, w=W, h=H):
    """Polylines (lists of vertex index ranges into the closed ring x, y) that touch the frame window: the runs of consecutive edges
    whose box meets the window enlarged by `margin`, split where `flags` (edge is a coast; None = all) is false."""
    n = len(x)
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    keep = (np.minimum(x, xn) < w + margin) & (np.maximum(x, xn) > -margin) & (np.minimum(y, yn) < h + margin) & (np.maximum(y, yn) > -margin)
    if flags is not None:
        keep &= flags
    if not keep.any():
        return []
    if keep.all():
        return [(0, n, True)]                                           # the whole ring, closed
    d = np.diff(np.concatenate([[0], keep.astype(np.int8), [0]]))
    out = []
    for s, e in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
        out.append((int(s), int(e), False))                             # edges s .. e-1 : vertices s .. e (cyclic)
    return out


def clip_rect(x, y, x0, y0, x1, y1):
    """The closed ring (x, y) clipped to the rectangle (Sutherland-Hodgman, vectorised): arrays of the clipped ring, possibly empty."""
    for axis, bound, keep_above in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        if len(x) == 0:
            break
        v = x if axis == 0 else y
        inside = v >= bound if keep_above else v <= bound
        if inside.all():
            continue
        if not inside.any():
            return x[:0], y[:0]
        xn, yn, vn, in_n = np.roll(x, -1), np.roll(y, -1), np.roll(v, -1), np.roll(inside, -1)
        cross = inside != in_n
        t = np.zeros(len(x))
        t[cross] = (bound - v[cross]) / (vn[cross] - v[cross])
        ox = np.stack([x + t * (xn - x), xn], 1)
        oy = np.stack([y + t * (yn - y), yn], 1)
        keep = np.stack([cross, in_n], 1)
        x, y = ox[keep], oy[keep]
    return x, y


def chaikin(x, y, iterations, keep_over=160.0):
    """Corner cutting of a closed ring: every vertex is replaced by two points, at 1/4 of its edge toward the previous vertex and at 1/4
    toward the next one. A vertex next to an edge longer than `keep_over` px stays as it is: such an edge is a side of the clip window,
    and cutting its corners would eat into the picture."""
    for _ in range(iterations):
        xn, yn, xp, yp = np.roll(x, -1), np.roll(y, -1), np.roll(x, 1), np.roll(y, 1)
        long_next = np.hypot(xn - x, yn - y) > keep_over
        keep = long_next | np.roll(long_next, 1)
        ax, ay = np.where(keep, x, 0.75 * x + 0.25 * xp), np.where(keep, y, 0.75 * y + 0.25 * yp)
        bx, by = 0.75 * x + 0.25 * xn, 0.75 * y + 0.25 * yn
        m = np.stack([np.ones(len(x), bool), ~keep], 1)
        x, y = np.stack([ax, bx], 1)[m], np.stack([ay, by], 1)[m]
    return x, y


SMOOTH_FROM_PX, SMOOTH_TO_PX = 8.0, 6.0     # outlines whose median segment is longer than the first are smoothed until it is about the second


class BaseMap:
    """Everything of one frame that is the map itself (no marks, no text)."""

    def __init__(self, preset: str, grat_deg: float):
        self.pr = dict(PRESETS[preset], ink=INK)
        self.grat = float(grat_deg)

    # -- projection of rings ----------------------------------------------------------------------------------
    @staticmethod
    def project(layer, view, pad, extra=None):
        """Select the rings of `layer` that meet the view (with the world copied by 360 degrees when the view crosses the antimeridian)
        and project them. Returns (list of (ring index, x px, y px float64 arrays, the same as int32 x 16, shift, refined)) in draw order. `refined`: the ring was clipped to the canvas
        and its corners cut (a narrow view of coarse outlines, `chaikin`), so it no longer lines up with the per-vertex coast flags."""
        s = view.s
        half_w, half_h = (view.w / 2 + pad + 60) / s, (view.h / 2 + pad + 60) / s
        lon0 = math.radians(view.lon0)
        out = []
        for shift in (-2 * math.pi, 0.0, 2 * math.pi):
            idx = layer.visible(lon0 - half_w, lon0 + half_w, view.my0 - half_h, view.my0 + half_h, shift)
            if idx.size == 0:
                continue
            if extra is not None:
                idx = idx[extra[idx]]
                if idx.size == 0:
                    continue
            segs = [(layer.off[i], layer.off[i + 1]) for i in idx]
            lon = np.concatenate([layer.lon[a:b] for a, b in segs]) + shift
            my = np.concatenate([layer.my[a:b] for a, b in segs])
            x = (view.w / 2 + pad) + (lon - lon0) * s
            y = (view.h / 2 + pad) - (my - view.my0) * s
            lens = np.array([b - a for a, b in segs])
            ends = np.cumsum(lens)
            starts = ends - lens
            iters = 0
            inwin = (x > -20) & (x < view.w + 2 * pad + 20) & (y > -20) & (y < view.h + 2 * pad + 20)
            both = inwin[:-1] & inwin[1:]
            if both.sum() > 8:
                med = float(np.median(np.hypot(np.diff(x), np.diff(y))[both]))
                iters = int(min(3, max(0, math.ceil(math.log2(med / SMOOTH_TO_PX))))) if med > SMOOTH_FROM_PX else 0
            if iters:
                win = (-20.0, -20.0, view.w + 2 * pad + 20.0, view.h + 2 * pad + 20.0)
                for i, a, b in zip(idx, starts, ends):
                    rx, ry = x[a:b], y[a:b]
                    if not (rx.min() >= win[0] and rx.max() <= win[2] and ry.min() >= win[1] and ry.max() <= win[3]):
                        rx, ry = clip_rect(rx, ry, *win)
                    if len(rx) < 3:
                        continue
                    rx, ry = chaikin(rx, ry, iters)
                    out.append((int(i), rx, ry, np.rint(np.stack([rx, ry], 1) * 16).astype(np.int32), shift, True))
                continue
            p16 = np.rint(np.stack([x, y], 1) * 16).astype(np.int32)
            for i, a, b in zip(idx, starts, ends):
                out.append((int(i), x[a:b], y[a:b], p16[a:b], shift, False))
        out.sort(key=lambda r: r[0])                                       # draw order = ring order, across the three copies
        return out

    @staticmethod
    def fill(mask, rings, holes) -> None:
        """Fill the projected rings into the uint8 mask (anti-aliased); holes (given per ring index) are cleared, in ring order."""
        polys = [r[3] for r in rings]
        flags = [bool(holes[r[0]]) for r in rings]
        a = 0
        while a < len(polys):
            b = a
            while b < len(polys) and flags[b] == flags[a]:
                b += 1
            cv2.fillPoly(mask, polys[a:b], 0 if flags[a] else 255, lineType=cv2.LINE_AA, shift=4)
            a = b

    # -- one frame --------------------------------------------------------------------------------------------
    def draw(self, view, k: float):
        """(BGR uint8 frame, land coverage uint8 frame): the sea with its shade and water lines, the land, graticule and coastline."""
        res = geo.level_for(view.width_km)
        layer = geo.land(res)
        Hp, Wp = view.h + 2 * PAD, view.w + 2 * PAD
        rings = self.project(layer, view, PAD)
        m = np.zeros((Hp, Wp), np.uint8)
        if rings:
            self.fill(m, rings, layer.hole)
        sea = cv2.threshold(m, 127, 255, cv2.THRESH_BINARY_INV)[1]
        dist = cv2.distanceTransform(sea, cv2.DIST_L2, 5)
        idx = cv2.convertScaleAbs(dist, alpha=IDX_PER_PX)
        lut = profile_lut(self.pr, k)
        base = cv2.merge([cv2.LUT(idx, np.ascontiguousarray(lut[:, c])) for c in range(3)])
        edge = np.flatnonzero((m > 0) & (m < 255))                       # anti-aliased edge pixels: land over the flat sea beside the coast
        if edge.size:
            flat = lut[int(round((0.5 + 3.0) * IDX_PER_PX))].astype(np.float32)       # 3 px out of the coast: flat sea
            a = (m.reshape(-1)[edge].astype(np.float32) / 255.0)[:, None]
            flat_px = base.reshape(-1, 3)
            flat_px[edge] = np.clip(flat * (1 - a) + lut[0].astype(np.float32) * a + 0.5, 0, 255).astype(np.uint8)
        ink = np.zeros((Hp, Wp), np.uint8)
        self.draw_graticule(ink, view)
        self.draw_coast(ink, rings, layer)
        self.apply_ink(base, ink)
        crop = (slice(PAD, PAD + view.h), slice(PAD, PAD + view.w))
        return np.ascontiguousarray(base[crop]), np.ascontiguousarray(m[crop])

    def draw_graticule(self, ink, view) -> None:
        deg = self.grat
        if deg <= 0:
            return
        lon_lo, lat_a = view.to_lonlat(-PAD, view.h + PAD)
        lon_hi, lat_b = view.to_lonlat(view.w + PAD, -PAD)
        step_px = math.radians(deg) * view.s
        if step_px < 12:
            return                                                     # lines closer than 12 px are noise
        col = int(round(255 * GRAT_A))
        for lon in np.arange(math.ceil(lon_lo / deg) * deg, lon_hi + 1e-9, deg):
            x, _ = view.to_px(lon, 0.0, PAD, PAD)
            cv2.line(ink, (int(round(x * 16)), 0), (int(round(x * 16)), (ink.shape[0] - 1) * 16), col, GRAT_PX, cv2.LINE_AA, 4)
        for lat in np.arange(math.ceil(max(lat_a, -84) / deg) * deg, min(lat_b, 84) + 1e-9, deg):
            _, y = view.to_px(0.0, lat, PAD, PAD)
            cv2.line(ink, (0, int(round(y * 16))), ((ink.shape[1] - 1) * 16, int(round(y * 16))), col, GRAT_PX, cv2.LINE_AA, 4)

    def draw_coast(self, ink, rings, layer) -> None:
        """The ink coastline: every ring that meets the canvas, as anti-aliased polylines; rings with an edge that only cuts the world
        (antimeridian, southern limit) are walked edge by edge and those edges are skipped."""
        col, th = int(round(255 * COAST_A)), COAST_PX
        Hp, Wp = ink.shape
        closed_l, open_l = [], []
        for i, x, y, p16, _s, refined in rings:
            if refined or layer.cut is None or not layer.cut[i]:
                closed_l.append(p16)
                continue
            a, b = layer.off[i], layer.off[i + 1]
            for s0, e0, whole in _edge_runs(x, y, layer.coast[a:b], 8, Wp, Hp):
                ii = np.arange(s0, e0 + 1) % len(x)
                open_l.append(p16[ii])
        if closed_l:
            cv2.polylines(ink, closed_l, True, col, th, cv2.LINE_AA, 4)
        if open_l:
            cv2.polylines(ink, open_l, False, col, th, cv2.LINE_AA, 4)

    def apply_ink(self, base, ink) -> None:
        idx = np.flatnonzero(ink)
        if idx.size == 0:
            return
        px = base.reshape(-1, 3)
        a = (ink.reshape(-1)[idx].astype(np.float32) / 255.0)[:, None]
        ink_bgr = np.array(hex_to_bgr(INK), np.float32)
        px[idx] = np.clip(px[idx] * (1 - a) + ink_bgr * a + 0.5, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------- paper grain and vignette
def grain_and_vignette(seed: int, grain: float, vignette: float):
    """(gain, offset): float32 (H, W, 3) so that frame * gain + offset applies the paper grain (multiply) and the vignette (ink at the
    corners). Deterministic: `seed` fixes the grain, and both are pinned to the screen."""
    rng = np.random.RandomState(int(seed))
    n = cv2.GaussianBlur(rng.randn(H, W).astype(np.float32), (0, 0), 0.6)
    n = (n - n.mean()) / (n.std() + 1e-6)                                     # unit noise, neighbouring pixels correlated about .5 (measured on the mock-up)
    alpha = np.maximum(0.0, GRAIN_MU + GRAIN_SIGMA * n) * grain               # measured on the mock-up (flat land): mean .0275, std .0226
    gain = 1.0 - alpha[..., None] * (1.0 - np.array(GRAIN_COL[::-1], np.float32))[None, None, :]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx + 0.5 - W / 2) / (W / 2 * math.sqrt(2)), (yy + 0.5 - H / 2) / (H / 2 * math.sqrt(2)))
    av = np.clip((r - VIG_FROM) / (1 - VIG_FROM), 0, 1) * VIG_A * vignette
    gain = (gain * (1.0 - av[..., None])).astype(np.float32)
    off = (av[..., None] * np.array(VIG_COL[::-1], np.float32)[None, None, :]).astype(np.float32)
    return gain, off


# ----------------------------------------------------------------------------- routes
def catmull_rom(pts: np.ndarray, per_seg: int = 48) -> np.ndarray:
    """The smooth curve through `pts` (n, 2) as the mock-up draws it (cubic Béziers with control points p1 + (p2 - p0) / 6)."""
    n = len(pts)
    if n < 3:
        return pts.copy()
    u = np.linspace(0, 1, per_seg, endpoint=False)[:, None]
    out = []
    for i in range(n - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, n - 1)]
        c1, c2 = p1 + (p2 - p0) / 6.0, p2 - (p3 - p1) / 6.0
        out.append((1 - u) ** 3 * p1 + 3 * (1 - u) ** 2 * u * c1 + 3 * (1 - u) * u ** 2 * c2 + u ** 3 * p2)
    out.append(pts[-1:])
    return np.concatenate(out)


class RoutePath:
    """A route in map space (longitude in radians, Mercator ordinate), walked by distance along it."""

    def __init__(self, lonlat_pts, shape: str):
        pts = np.array([[math.radians(lo), float(geo.merc(la))] for lo, la in lonlat_pts], np.float64)
        self.pts = catmull_rom(pts) if shape == "curve" else pts
        seglen = np.hypot(*np.diff(self.pts, axis=0).T) if len(self.pts) > 1 else np.zeros(0)
        self.cum = np.concatenate([[0.0], np.cumsum(seglen)])
        self.length = float(self.cum[-1])

    def at(self, dist):
        """Map-space points at the given distances along the route (array or scalar)."""
        d = np.clip(np.asarray(dist, np.float64), 0, self.length)
        return np.interp(d, self.cum, self.pts[:, 0]), np.interp(d, self.cum, self.pts[:, 1])

    def samples(self, view, n: int = 200):
        """Screen points along the whole route for a view (used to keep labels clear of it)."""
        x, y = self.at(np.linspace(0, self.length, n))
        return np.stack([view.w / 2 + (x - math.radians(view.lon0)) * view.s, view.h / 2 - (y - view.my0) * view.s], 1)


def px_of(view, lon_rad, my):
    return view.w / 2 + (lon_rad - math.radians(view.lon0)) * view.s, view.h / 2 - (my - view.my0) * view.s


# ----------------------------------------------------------------------------- the technique
def _box_hits(a, b, pad=0.0) -> bool:
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def _box_near_points(box, pts, pad) -> bool:
    """Whether any of `pts` (n, 2) lies inside the box grown by `pad`."""
    if len(pts) == 0:
        return False
    return bool(((pts[:, 0] > box[0] - pad) & (pts[:, 0] < box[2] + pad) & (pts[:, 1] > box[1] - pad) & (pts[:, 1] < box[3] + pad)).any())


@technique("MAP-01", "base")
class AtlasMap(BaseRenderer):
    """MAP-01: the atlas map. Times (`at`, `region_at`, `push_s`, ...) are seconds from the start of the shot; an `at` that is a word anchor
    is the absolute time of that word, taken from the start of the shot (`registry.at_seconds`)."""

    # -- validation across params ------------------------------------------------------------------------------
    @classmethod
    def check_params(cls, p: dict):
        """Rules between params: place ids are unique, every route end names a place, `via` and the view centres are inside the world,
        every region code is a country of the bundled data. Returns [(param, code, args, message)]."""
        out = []
        seen = {}
        for i, pl in enumerate(p["places"]):
            pid = pl.get("id")
            if pid in seen:
                out.append(("places", "map_duplicate_place", {"id": pid, "index": i}, "item %d (%s): the id %r is already used by place %d" % (i + 1, pl.get("name", ""), pid, seen[pid] + 1)))
            seen.setdefault(pid, i)
        for i, rt in enumerate(p["route"]):
            for f in ("from", "to"):
                if rt.get(f) not in seen:
                    out.append(("route", "map_route_unknown_place", {"index": i, "field": f, "place": rt.get(f)},
                                "item %d: %s %r names no place" % (i + 1, f, rt.get(f))))
            via = parse_pairs(rt.get("via", ""))
            if via is None or len(via) > MAX_VIA:
                out.append(("route", "map_bad_via", {"index": i}, "item %d: via must be at most %d lon,lat pairs inside the world, separated by ;" % (i + 1, MAX_VIA)))
        for name in ("view_start_center", "view_end_center"):
            v = p.get(name) or ""
            pr = parse_pairs(v)
            if pr is None or len(pr) > 1:
                out.append((name, "map_bad_center", {}, "must be lon, lat inside the world (longitude -180..180, latitude -85..85)"))
        if p["region_iso"]:
            known = geo.iso_codes()
            for i, c in enumerate(p["region_iso"]):
                if str(c).strip().upper() not in known:
                    out.append(("region_iso", "map_unknown_iso", {"index": i, "code": c}, "line %d: %r is not the ISO code of a country in the bundled data" % (i + 1, c)))
        return out

    # -- construction ------------------------------------------------------------------------------------------
    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.preset = p["sea"] if p["sea"] in PRESETS else "blue_grey"
        self.pr = dict(PRESETS[self.preset], ink=INK)
        self.cap_px = float(p["label_cap_pct"]) / 100.0 * H
        self.fade = max(0.02, float(p["fade_s"]))
        self.places = []
        for pl in p["places"]:
            lon, lat = pl["lonlat"]
            self.places.append({"id": pl["id"], "name": str(pl["name"]), "lon": float(lon), "lat": float(lat),
                                "at": R.at_seconds(pl.get("at"), self.t0, 0.0), "side": pl.get("label_side", "auto"),
                                "lon_rad": math.radians(float(lon)), "my": float(geo.merc(lat))})
        by_id = {pl["id"]: pl for pl in self.places}
        self.routes = []
        for rt in p["route"]:
            a, b = by_id.get(rt["from"]), by_id.get(rt["to"])
            if a is None or b is None:
                continue                                             # `validate` refuses it; a draft that skips validation draws without it
            pts = [(a["lon"], a["lat"])] + (parse_pairs(rt.get("via", "")) or []) + [(b["lon"], b["lat"])]
            self.routes.append({"path": RoutePath(pts, rt.get("shape", "curve")), "at": R.at_seconds(rt.get("at"), self.t0, 0.0),
                                "draw": max(0.05, float(rt.get("draw_s", 3.0))), "head": rt.get("head", "dot") == "dot"})
        self.region = [str(c).strip().upper() for c in p["region_iso"]]
        # ---- views
        pts = [(pl["lon"], pl["lat"]) for pl in self.places] or [(0.0, 0.0)]
        for rt in p["route"]:
            pts += parse_pairs(rt.get("via", "")) or []                   # the bend points of a route are kept in the frame too (an addition to the contract's "all places")
        fit_view = geo.fit(pts, float(p["view_end_margin_pct"]))
        if p["view_end_mode"] == "manual":
            c = (parse_pairs(p["view_end_center"]) or [(fit_view.lon0, fit_view.lat0)])[0]
            self.end = geo.View(c[0], c[1], float(p["view_end_width_km"]))
        else:
            self.end = fit_view
        c = (parse_pairs(p["view_start_center"]) or [(self.end.lon0, self.end.lat0)])[0]
        self.start = geo.View(c[0], c[1], float(p["view_start_width_km"]))
        self.push_s = float(p["push_s"])
        self.s_ref = self.start.s if self.push_s > 0 else self.end.s
        self.base = BaseMap(self.preset, p["graticule_deg"])
        self.gv = ctx.cached(("map-grain", int(p["seed"]), float(p["grain"]), float(p["vignette"])), lambda: grain_and_vignette(p["seed"], p["grain"], p["vignette"]),
                             sizeof=lambda g: g[0].nbytes + g[1].nbytes)
        self.ink_bgr, self.acc_bgr, self.land_bgr = hex_to_bgr(INK), hex_to_bgr(ACCENT), hex_to_bgr(self.pr["land"])
        self.name_patch = {pl["id"]: self.patch(pl["name"], "eb_italic", self.cap_px) for pl in self.places}
        self.region_label = None
        if self.region and str(p["region_label"]).strip():
            self.region_label = self.patch(str(p["region_label"]).strip(), "eb_regular", REGION_CAP / 100.0 * H, SEA_TRACK, True)
        self.region_pole = self.pole_of_region() if self.region_label is not None else None
        self.sides = self.place_labels()
        self.region_nudge = self.nudge_region_label() if self.region_label is not None else (0.0, 0.0)

    def patch(self, text, kind, cap_px, tracking=0.0, upper=False):
        key = ("mappatch", text, kind, round(cap_px, 2), tracking, upper)
        return self.ctx.cached(key, lambda: text_patch(text, kind, cap_px, tracking, upper), sizeof=lambda x: x.nbytes)

    # -- the view of a time ------------------------------------------------------------------------------------
    def view_at(self, tau):
        e = 1.0 if self.push_s <= 0 else ease_inout(tau / self.push_s)
        return geo.ease_view(self.start, self.end, e)

    def scale_k(self, view) -> float:
        return min(K_MAX, max(K_MIN, view.s / self.s_ref))

    # -- labels ------------------------------------------------------------------------------------------------
    def label_box(self, pl, side, x, y):
        """(left, baseline, box) of the label of place `pl` on `side` of its mark at (x, y); box = (x0, y0, x1, y1) of the ink."""
        pt = self.name_patch[pl["id"]]
        w, cap, g = pt.width, pt.cap, LABEL_GAP / 100.0 * H
        gv = (LABEL_GAP + 0.2) / 100.0 * H
        left, base = {
            "ne": (x + g, y - g), "nw": (x - g - w, y - g), "se": (x + g, y + g + cap), "sw": (x - g - w, y + g + cap),
            "e": (x + g, y + cap / 2), "w": (x - g - w, y + cap / 2), "n": (x - w / 2, y - gv), "s": (x - w / 2, y + gv + cap),
        }[side]
        return left, base, (left, base - 1.1 * cap, left + w, base + 0.3 * cap)

    def sample_views(self):
        return [geo.ease_view(self.start, self.end, e) for e in (0.0, 0.5, 1.0)]

    def place_labels(self):
        """The side of every label: `label_side` when it is not `auto`, else the first of the preference order whose label touches neither
        the route nor another mark nor another label nor the frame edge in the start view, the middle of the push and the end view."""
        views = self.sample_views()
        route_pts = [[r["path"].samples(v) for r in self.routes] for v in views]
        marks = [[px_of(v, pl["lon_rad"], pl["my"]) for pl in self.places] for v in views]
        chosen, boxes = {}, [[] for _ in views]
        r_mark = (MARK_R + 0.3) / 100.0 * H
        for n, pl in enumerate(self.places):
            order = PREFERENCE if pl["side"] == "auto" else (pl["side"],)
            best, best_cost = order[0], None
            for rank, side in enumerate(order):
                cost = rank * 0.01
                for vi, v in enumerate(views):
                    x, y = marks[vi][n]
                    _l, _b, box = self.label_box(pl, side, x, y)
                    if any(_box_near_points(box, rp, 0.006 * H) for rp in route_pts[vi]):
                        cost += 10
                    for m, (mx, my) in enumerate(marks[vi]):
                        if m != n and _box_hits(box, (mx - r_mark, my - r_mark, mx + r_mark, my + r_mark), 2):
                            cost += 10
                    if any(_box_hits(box, o, 0.004 * H) for o in boxes[vi]):
                        cost += 10
                    if box[0] < 0.01 * W or box[2] > 0.99 * W or box[1] < 0.01 * H or box[3] > 0.99 * H:
                        cost += 4
                if best_cost is None or cost < best_cost - 1e-9:
                    best, best_cost = side, cost
                if cost < 0.5 and pl["side"] == "auto":
                    break                                              # the first side of the preference order that is clear
            chosen[pl["id"]] = best
            for vi in range(len(views)):
                x, y = marks[vi][n]
                boxes[vi].append(self.label_box(pl, best, x, y)[2])
        return chosen

    def pole_of_region(self):
        """Longitude and latitude (degrees) of the label of the region: the point of the biggest country ring that is furthest from its edge."""
        lay = geo.countries()
        wanted = [lay.iso.index(c) for c in self.region if c in lay.iso]
        if not wanted:
            return None
        sel = np.nonzero(np.isin(lay.aux, wanted) & ~lay.hole)[0]
        if sel.size == 0:
            return None
        areas = []
        for i in sel:
            lon, my = lay.ring(i)
            areas.append(abs(0.5 * (np.dot(lon[:-1], my[1:]) - np.dot(lon[1:], my[:-1]))))
        i = int(sel[int(np.argmax(areas))])
        lon, my = lay.ring(i)
        x0, y0 = lon.min(), my.min()
        sc = 160.0 / max(lon.max() - x0, my.max() - y0, 1e-9)
        wd, ht = int((lon.max() - x0) * sc) + 3, int((my.max() - y0) * sc) + 3
        m = np.zeros((ht, wd), np.uint8)
        cv2.fillPoly(m, [np.rint(np.stack([(lon - x0) * sc + 1, (my - y0) * sc + 1], 1)).astype(np.int32)], 255)
        dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
        j, k = np.unravel_index(int(np.argmax(dt)), dt.shape)
        return float(np.degrees((k - 1 + 0.5) / sc + x0)), float(geo.inv_merc((j - 1 + 0.5) / sc + y0))

    def nudge_region_label(self):
        """A small shift (px) that keeps the region's name off the marks, the labels, the route and the outline of the region: tried at the
        start view, the middle of the push and the end view (the end view counts most). (0, 0) when the pole of the region already is clear."""
        if self.region_pole is None:
            return (0.0, 0.0)
        rl = self.region_label
        w, cap = rl.width, rl.cap
        views = self.sample_views()
        lay = geo.countries()
        wanted = np.isin(np.arange(len(lay.iso)), [lay.iso.index(c) for c in self.region if c in lay.iso])
        masks = []
        for v in views:
            m = np.zeros((H, W), np.uint8)
            rings = BaseMap.project(lay, v, 0, wanted[lay.aux])
            if rings:
                BaseMap.fill(m, rings, lay.hole)
            masks.append(m)
        weight = (0.5, 1.5, 3.0)
        best, best_cost = (0.0, 0.0), None
        offsets = [(dx * w, dy * H) for dy in (0, 0.02, -0.02, 0.04, -0.04) for dx in (0, 0.3, -0.3, 0.55, -0.55)]
        for dx, dy in offsets:
            cost = 0.0
            for v, m, wt in zip(views, masks, weight):
                cx, cy = (float(a) for a in v.to_px(*self.region_pole))
                box = (cx + dx - w / 2, cy + dy - cap / 2 - 2, cx + dx + w / 2, cy + dy + cap / 2 + 2)
                inside = m[max(0, int(box[1]) - 3):int(box[3]) + 3, max(0, int(box[0]) - 3):int(box[2]) + 3]
                if inside.size:
                    cost += 10.0 * wt * float((inside < 128).mean())              # the part of the box that is outside the region (the outline is on the edge)
                for pl in self.places:
                    mx, my = px_of(v, pl["lon_rad"], pl["my"])
                    r = (MARK_R + 0.3) / 100.0 * H
                    if _box_hits(box, (mx - r, my - r, mx + r, my + r), 2):
                        cost += 10
                    if _box_hits(box, self.label_box(pl, self.sides[pl["id"]], mx, my)[2], 4):
                        cost += 10
                for r_ in self.routes:
                    if _box_near_points(box, r_["path"].samples(v), 4):
                        cost += 5
            cost += (abs(dx) + abs(dy)) * 1e-3
            if best_cost is None or cost < best_cost - 1e-9:
                best, best_cost = (float(dx), float(dy)), cost
        return best

    # -- one frame ---------------------------------------------------------------------------------------------
    def render(self, t):
        tau = float(t) - self.t0
        view = self.view_at(tau)
        k = self.scale_k(view)
        img, land = self.base.draw(view, k)
        f = img.astype(np.float32)
        self.draw_region(f, land, view, tau)
        self.draw_routes(f, view, k, tau)
        gain, off = self.gv
        cv2.multiply(f, gain, f)
        cv2.add(f, off, f)
        if self.p["sea_names"]:
            self.draw_sea_names(f, view, land)
        self.draw_places(f, view, tau)
        return f

    def draw_region(self, f, land, view, tau) -> None:
        ra = float(self.p["region_at"])
        rg = seg(tau, ra, ra + float(self.p["region_fill_s"]))
        if rg <= 0 or not self.region:
            return
        lay = geo.countries()
        wanted = np.isin(np.arange(len(lay.iso)), [lay.iso.index(c) for c in self.region if c in lay.iso])
        sel = wanted[lay.aux]
        rings = BaseMap.project(lay, view, 0, sel)
        if not rings:
            return
        fill = np.zeros((H, W), np.uint8)
        BaseMap.fill(fill, rings, lay.hole)
        if view.width_km < geo.NARROW_KM:
            fill = cv2.multiply(fill, land, scale=1.0 / 255.0)            # the 1:10m land and the 1:50m countries differ at the coast: the tint stays on land
        box = (0, 0, W, H)
        blend_mask(f, fill, self.acc_bgr, 0.2 * rg, box)
        line = np.zeros((H, W), np.uint8)
        open_l = []
        for i, x, y, p16, _s, _r in rings:
            if lay.hole[i]:
                continue
            for s0, e0, _whole in _edge_runs(x, y, None, 8):
                open_l.append(p16[np.arange(s0, e0 + 1) % len(x)])
        if open_l:
            cv2.polylines(line, open_l, False, 255, REGION_LINE_PX, cv2.LINE_AA, 4)
        if view.width_km < geo.NARROW_KM:
            line = cv2.multiply(line, land, scale=1.0 / 255.0)
        blend_mask(f, line, self.acc_bgr, 0.75 * rg, box)

    def draw_routes(self, f, view, k, tau) -> None:
        for r in self.routes:
            path = r["path"]
            if path.length <= 0:
                continue
            prog = seg(tau, r["at"], r["at"] + r["draw"])
            if prog <= 0:
                continue
            spacing = DOT_SPACING / self.s_ref
            n = int(path.length / spacing) + 1
            if n > 500:
                spacing, n = path.length / 500.0, 500
            lead = DOT_LEAD / self.s_ref
            d = np.arange(n) * spacing
            d = d[d <= prog * path.length + lead]
            if d.size:
                x, y = path.at(d)
                px, py = px_of(view, x, y)
                mask = np.zeros((H, W), np.uint8)
                rad = int(round(DOT_D / 2 * k * 16))
                for a, b in zip(px, py):
                    if -20 < a < W + 20 and -20 < b < H + 20:
                        cv2.circle(mask, (int(round(a * 16)), int(round(b * 16))), rad, 255, -1, cv2.LINE_AA, 4)
                blend_mask(f, mask, self.acc_bgr, 1.0)
            if r["head"]:
                ho = 1.0 - seg(tau, r["at"] + r["draw"], r["at"] + r["draw"] + 0.5)
                hx, hy = path.at(prog * path.length)
                px, py = px_of(view, float(hx), float(hy))
                blend_disc(f, px, py, HALO_R * k, self.acc_bgr, HALO_A * ho)
                blend_disc(f, px, py, HEAD_R * k, self.acc_bgr, ho)

    def draw_sea_names(self, f, view, land) -> None:
        """Up to `sea_names_max` names whose position is inside the view, whose sea is large enough for the view (extent at least 8 percent
        of its width for the major seas, more for the minor ones: `SEA_MIN_SHARE`) whose text lies mostly on water (land under at most 30 percent of it, as the mock-up's Mediterranean crosses Sardinia)
        and clear of the routes, the marks and the labels, most important sea first."""
        width = view.width_km
        cap = SEA_CAP / 100.0 * H
        picked, boxes = 0, []
        marks = [px_of(view, pl["lon_rad"], pl["my"]) for pl in self.places]
        route_pts = [r["path"].samples(view, 300) for r in self.routes if r["path"].length > 0]
        edge = 0.04 * H
        for s in geo.seas():
            if picked >= int(self.p["sea_names_max"]):
                break
            if s["extent_km"] / width < SEA_MIN_SHARE.get(s["rank"], 0.45):
                continue
            x, y = (float(a) for a in view.to_px(s["lon"], s["lat"]))
            d = min(x, W - x, y, H - y)
            if d <= 0:
                continue
            pt = self.patch(s["name"], "eb_regular", cap, SEA_TRACK, True)
            box = (x - pt.width / 2, y - pt.cap / 2 - 2, x + pt.width / 2, y + pt.cap / 2 + 2)
            if box[0] < 0.01 * W or box[2] > 0.99 * W or box[1] < 0.01 * H or box[3] > 0.99 * H:
                continue
            if any(_box_hits(box, o, 6) for o in boxes):
                continue
            under = land[max(0, int(box[1])):int(box[3]), max(0, int(box[0])):int(box[2])]
            if under.size and (under > 127).mean() > LAND_UNDER_NAME.get(s["rank"], LAND_UNDER_DEFAULT):
                continue
            if any(_box_near_points(box, rp, 0.006 * H) for rp in route_pts):
                continue
            rr = (MARK_R + 0.4) / 100.0 * H
            if any(_box_hits(box, (mx - rr, my - rr, mx + rr, my + rr), 4) for mx, my in marks):
                continue
            if any(_box_hits(box, self.label_box(pl, self.sides[pl["id"]], mx, my)[2], 6) for pl, (mx, my) in zip(self.places, marks)):
                continue
            boxes.append(box)
            picked += 1
            apply_patch(f, pt, x - pt.width / 2, y + pt.cap / 2, self.ink_bgr, SEA_NAME_ALPHA * min(1.0, d / edge))

    def draw_places(self, f, view, tau) -> None:
        if self.region_label is not None and self.region_pole is not None:
            ra = float(self.p["region_at"])
            al = REGION_ALPHA * seg(tau, ra + 0.4 * float(self.p["region_fill_s"]), ra + float(self.p["region_fill_s"]))
            cx, cy = (float(a) for a in view.to_px(*self.region_pole))
            rl = self.region_label
            apply_patch(f, rl, cx + self.region_nudge[0] - rl.width / 2, cy + self.region_nudge[1] + rl.cap / 2, self.acc_bgr, al)
        for pl in self.places:
            m = seg(tau, pl["at"], pl["at"] + self.fade)
            if m <= 0:
                continue
            x, y = (float(a) for a in px_of(view, pl["lon_rad"], pl["my"]))
            blend_disc(f, x, y, MARK_R / 100.0 * H, self.ink_bgr, m, (MARK_R - MARK_RING) / 100.0 * H)
            blend_disc(f, x, y, MARK_DOT / 100.0 * H, self.acc_bgr, m)
            la = seg(tau, pl["at"] + 0.2, pl["at"] + 0.2 + self.fade)
            if la > 0:
                left, base, _b = self.label_box(pl, self.sides[pl["id"]], x, y)
                apply_patch(f, self.name_patch[pl["id"]], left, base, self.ink_bgr, la, self.land_bgr)
