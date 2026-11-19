"""TIME-01, TREE-01 and STATE-01: three explanatory devices that make one point visible (family of the atlas map `MAP-01`).

    TIME-01   a time axis with dates on the dark ground: a hairline axis grows from the left, ticks fade in, each item's stalk grows and
              its year and label fade in at the item's own time; at `focus_s` the accented item brightens and the others dim.
    TREE-01   relations between people on the dark ground: names with a smaller second line, hairline connectors drawn progressively,
              marriage as a short horizontal line, descent running down in right angles, edge labels in small italic.
    STATE-01  the same picture in two states: two image slots framed by one camera that does not move during a change, a dissolve,
              the holds given as text, the state's name in small capitals at the bottom left.

The look is the approved moving mock-up (`docs/design/mock/2026-11-18-explainer/components.html`, functions `timeline`, `tree` and
`states`); the colours, the rules for text and the data are the contract `docs/design/2026-11-18-explainer-components.md` (sections 2, 3, 4
and 5). Everything here is a pure function of the time (frames are drawn in any order); nothing opens a socket; nothing is random.

The agent supplies data only; the technique solves the layout:
  * TIME-01 chooses, for every item, the side of the axis, the length of the stalk (three lengths above the axis, two below) and the
    place of the label so that no label touches another label or another item's stalk and every label stays inside the frame
    (`solve_time`: a depth first search over those choices, accented items first). Data that cannot be laid out that way is refused by
    `check_params` (`time_crowded`), so what `validate` accepts can be drawn without a clash.
  * TREE-01 lays the tree out itself when `row` and `col` are left out (`solve_tree`): generations from the direction of descent, spouses
    side by side, crossings reduced by barycentre sweeps, coordinates by a least-squares relaxation with minimum gaps, right-angle
    connectors that run through the gaps between rows. Text is made smaller (down to 64 percent) when the tree is too wide for the frame;
    a tree that still does not fit is refused (`tree_too_big`).
  * STATE-01 maps the second picture onto the frame of the first (see `TwoStates`).
Sizes are cap heights in percent of the frame height (the real glyph H of the bundled EB Garamond, `vfx.cap_ratio`).
"""
from __future__ import annotations

import functools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .. import registry as R
from .. import vfx
from ..base import BaseRenderer, View, hex_to_bgr
from ..registry import technique
from ..vfx import Cam, compose_matte
from .camera import camera_keys, fit_zoom

W, H = 1920, 1080

# ---- colours (contract section 5)
GROUND, TEXT, HAIR = "#131519", "#E9E2D0", "#8D877A"
OVER_PICTURE = "#F1EADB"                       # text over a picture (with a soft shadow)
SECOND = 0.72                                  # secondary text: 72 percent
HAIR_PX = 2                                    # the mock-up's 1 CSS px on a stage 540 px high is 2 px of 1080
LINE_PX = 3.2                                  # the connectors of the tree: 1.6 CSS px of the mock-up's stage, 3.2 px of 1080


def _bgr(c):
    return np.array(hex_to_bgr(c), np.float32)


GROUND_F, TEXT_F, HAIR_F, PICTURE_F = _bgr(GROUND), _bgr(TEXT), _bgr(HAIR), _bgr(OVER_PICTURE)


def seg(x, a, b):
    """0..1 progress of x over [a, b] (a step at a when b <= a)."""
    if b <= a:
        return 1.0 if x >= a else 0.0
    return min(1.0, max(0.0, (x - a) / (b - a)))


def ease_inout(x):
    x = min(1.0, max(0.0, x))
    return 2 * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 2 / 2


def ease_out(x):
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def lerp(a, b, x):
    return a + (b - a) * x


# ----------------------------------------------------------------------------- text
def font_size(kind: str, cap_px: float) -> int:
    return max(6, int(round(cap_px / vfx.cap_ratio(kind))))


@functools.lru_cache(maxsize=8192)
def measure(text: str, kind: str, size: int, tracking_em: float = 0.0):
    """(advance width, (x0, y0, x1, y1) ink box) of one line, relative to its origin (left edge, baseline), y downward."""
    ft = vfx.font(kind, size)
    if not text:
        return 0.0, (0.0, 0.0, 0.0, 0.0)
    if tracking_em > 0:
        adv = [ft.getlength(c) for c in text]
        width = sum(adv) + tracking_em * size * max(0, len(text) - 1)
        boxes = [ft.getbbox(c, anchor="ls") for c in text]
        return width, (float(boxes[0][0]), float(min(b[1] for b in boxes)), width - adv[-1] + float(boxes[-1][2]), float(max(b[3] for b in boxes)))
    bb = ft.getbbox(text, anchor="ls")
    return float(ft.getlength(text)), (float(bb[0]), float(bb[1]), float(bb[2]), float(bb[3]))


class Ink:
    """A pre-rendered text line: coverage (float32, h x w), where its origin sits in that array, its advance width and its ink box."""

    def __init__(self, cov, ox, oy, width, box):
        self.cov, self.ox, self.oy, self.width, self.box = cov, ox, oy, width, box
        self._shadow = None
        self.nbytes = cov.nbytes * 2 + 300

    def shadow(self):
        """The soft shadow of the mock-up's captions (offset 0.2 % of the height down, blur 0.8 %, black at 90 percent), same size as the coverage."""
        if self._shadow is None:
            dy = int(round(0.002 * H))
            moved = np.zeros_like(self.cov)
            moved[dy:] = self.cov[:self.cov.shape[0] - dy]
            self._shadow = (cv2.GaussianBlur(moved, (0, 0), 0.004 * H) * 0.9).astype(np.float32)
        return self._shadow


def make_ink(text: str, kind: str, size: int, tracking_em: float = 0.0) -> Ink:
    ft = vfx.font(kind, size)
    width, box = measure(text, kind, size, tracking_em)
    asc, desc = ft.getmetrics()
    pad = int(size * 0.3) + 8
    img = Image.new("L", (int(math.ceil(width)) + 2 * pad, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    base = pad + asc
    if tracking_em > 0:
        x = float(pad)
        for c in text:
            d.text((x, base), c, font=ft, fill=255, anchor="ls")
            x += ft.getlength(c) + tracking_em * size
    else:
        d.text((pad, base), text, font=ft, fill=255, anchor="ls")
    return Ink(np.asarray(img, np.float32) / 255.0, pad, base, width, box)


def get_ink(ctx, text, kind, size, tracking_em=0.0) -> Ink:
    return ctx.cached(("explain-ink", text, kind, int(size), float(tracking_em)), lambda: make_ink(text, kind, int(size), tracking_em), sizeof=lambda x: x.nbytes)


def paint(f, ink: Ink, left: float, baseline: float, bgr, alpha: float, shadow: bool = False) -> None:
    """Blend a text line into the float frame with its origin at (left, baseline) in whole pixels."""
    if alpha <= 0.002 or ink is None:
        return
    x0, y0 = int(round(left)) - ink.ox, int(round(baseline)) - ink.oy
    h, w = ink.cov.shape
    fx0, fy0, fx1, fy1 = max(x0, 0), max(y0, 0), min(x0 + w, f.shape[1]), min(y0 + h, f.shape[0])
    if fx1 <= fx0 or fy1 <= fy0:
        return
    sl = (slice(fy0 - y0, fy1 - y0), slice(fx0 - x0, fx1 - x0))
    roi = f[fy0:fy1, fx0:fx1]
    if shadow:
        roi *= (1.0 - ink.shadow()[sl] * alpha)[..., None]
    roi += (np.asarray(bgr, np.float32) - roi) * (ink.cov[sl] * alpha)[..., None]


# ----------------------------------------------------------------------------- pixel primitives
def fill_rect(f, x0, y0, x1, y1, bgr, alpha=1.0) -> None:
    """A rectangle with exact (anti-aliased) edges at fractional coordinates; pixel i covers [i, i + 1)."""
    if x1 <= x0 or y1 <= y0 or alpha <= 0.002:
        return
    ix0, iy0 = max(int(math.floor(x0)), 0), max(int(math.floor(y0)), 0)
    ix1, iy1 = min(int(math.ceil(x1)), f.shape[1]), min(int(math.ceil(y1)), f.shape[0])
    if ix1 <= ix0 or iy1 <= iy0:
        return
    xs, ys = np.arange(ix0, ix1, dtype=np.float32), np.arange(iy0, iy1, dtype=np.float32)
    cx = np.clip(np.minimum(xs + 1, x1) - np.maximum(xs, x0), 0, 1)
    cy = np.clip(np.minimum(ys + 1, y1) - np.maximum(ys, y0), 0, 1)
    a = (cy[:, None] * cx[None, :] * alpha)[..., None]
    roi = f[iy0:iy1, ix0:ix1]
    roi += (np.asarray(bgr, np.float32) - roi) * a


def blend_disc(f, cx, cy, r, bgr, alpha) -> None:
    if alpha <= 0.002 or r <= 0:
        return
    x0, y0 = max(int(math.floor(cx - r - 2)), 0), max(int(math.floor(cy - r - 2)), 0)
    x1, y1 = min(int(math.ceil(cx + r + 2)), f.shape[1]), min(int(math.ceil(cy + r + 2)), f.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    cov = np.clip(r + 0.5 - np.hypot(xx + 0.5 - cx, yy + 0.5 - cy), 0, 1)
    roi = f[y0:y1, x0:x1]
    roi += (np.asarray(bgr, np.float32) - roi) * (cov * alpha)[..., None]


def fill_union(f, rects, bgr, alpha=1.0) -> None:
    """Several rectangles (x0, y0, x1, y1), fractional, drawn as ONE shape: exact edge coverage, the largest coverage where they overlap."""
    rects = [r for r in rects if r[2] > r[0] and r[3] > r[1]]
    if not rects or alpha <= 0.002:
        return
    x0, y0 = max(int(math.floor(min(r[0] for r in rects))), 0), max(int(math.floor(min(r[1] for r in rects))), 0)
    x1, y1 = min(int(math.ceil(max(r[2] for r in rects))), f.shape[1]), min(int(math.ceil(max(r[3] for r in rects))), f.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    mask = np.zeros((y1 - y0, x1 - x0), np.float32)
    for rx0, ry0, rx1, ry1 in rects:
        ix0, iy0, ix1, iy1 = max(int(math.floor(rx0)), x0), max(int(math.floor(ry0)), y0), min(int(math.ceil(rx1)), x1), min(int(math.ceil(ry1)), y1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        xs, ys = np.arange(ix0, ix1, dtype=np.float32), np.arange(iy0, iy1, dtype=np.float32)
        cx = np.clip(np.minimum(xs + 1, rx1) - np.maximum(xs, rx0), 0, 1)
        cy = np.clip(np.minimum(ys + 1, ry1) - np.maximum(ys, ry0), 0, 1)
        sl = mask[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0]
        np.maximum(sl, cy[:, None] * cx[None, :], out=sl)
    roi = f[y0:y1, x0:x1]
    roi += (np.asarray(bgr, np.float32) - roi) * (mask * alpha)[..., None]


def path_rects(pts, width) -> list:
    """The rectangles of a polyline made of horizontal and vertical segments (square joints); a slanted segment is drawn as the nearer of the two."""
    out, h = [], width / 2.0
    for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
        if abs(bx - ax) >= abs(by - ay):
            out.append((min(ax, bx) - h, ay - h, max(ax, bx) + h, ay + h))
        else:
            out.append((ax - h, min(ay, by) - h, ax + h, max(ay, by) + h))
    return out


def _hit(a, b, padx=0.0, pady=0.0) -> bool:
    """Whether the boxes (x0, y0, x1, y1) a and b come within the padding of each other."""
    return not (a[2] + padx <= b[0] or b[2] + padx <= a[0] or a[3] + pady <= b[1] or b[3] + pady <= a[1])


# ============================================================================= TIME-01
AXIS_Y = 0.56 * H                              # the axis sits at 56 percent of the height
AXIS_X0, AXIS_X1 = 0.06 * W, 0.94 * W          # the hairline runs from 6 to 94 percent of the width
SCALE_X0, SCALE_X1 = 0.09, 0.91                # the years are spread from 9 to 91 percent
AXIS_S = 0.8                                   # the axis grows from the left in 0.8 s
TICK_FROM, TICK_S, TICK_STAGGER = 0.2, 0.3, 0.04
TICK_MAJOR, TICK_MINOR = 0.018 * H, 0.009 * H  # half lengths of the ticks
STALK_S, YEAR_AT, YEAR_S, LABEL_AT, LABEL_S = 0.35, 0.2, 0.3, 0.35, 0.35
FOCUS_S = 0.8                                  # the accented item brightens and the others dim over 0.8 s
DOT_D, DOT_GROWTH = 0.016 * H, 1.5
TIERS = {"up": (0.13 * H, 0.24 * H, 0.35 * H), "down": (0.13 * H, 0.24 * H)}   # stalk lengths: three above the axis, two below
YEAR_K = 1.4375                                # the year is 4.6 / 3.2 of the label (the mock-up's font sizes)
GAP_UP, GAP_DOWN, LINE_K = 1.56, 1.4, 2.06     # in label cap heights: stalk end to label baseline, stalk end to year cap top, year baseline to label baseline
ANCHORS = (("c", 0.5), ("l", 0.22), ("r", 0.78))   # a label centred on its stalk (pushed into the frame), or shifted as the mock-up's two outer labels are
FRAME_X, FRAME_Y0, FRAME_Y1 = 0.03 * W, 0.04 * H, 0.965 * H
PAD_X, PAD_Y, STALK_PAD = 0.012 * W, 0.008 * H, 0.006 * W
NICE_STEPS = (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)
MAX_TICKS = 120
TIME_SEARCH_BUDGET = 60000

YEAR_PATTERN = r"\s*(?:-?\d{1,4})?\s*"
YEAR_HINT = "Gõ một năm, số âm là trước Công nguyên (ví dụ -500). Để trống thì lấy theo các mốc, chừa một năm ở hai đầu."


def parse_year(s):
    """The whole year of a text (`-500`, `1434`), None for an empty text."""
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return int(round(s))
    s = (s or "").strip() if isinstance(s, str) else ""
    return int(s) if s else None


def year_text(d) -> str:
    d = int(round(d))
    return "%d BC" % -d if d < 0 else str(d)


def time_range(p: dict):
    """(from, to) in whole years: the given ones, else the items' range with one year of margin."""
    dates = [int(round(it["date"])) for it in p["items"]] or [0]
    a, b = parse_year(p.get("from")), parse_year(p.get("to"))
    return (min(dates) - 1 if a is None else a), (max(dates) + 1 if b is None else b)


def tick_years(a: int, b: int, every) -> list:
    every = int(round(every or 0))
    if every <= 0 or (b - a) // every + 1 > MAX_TICKS:
        span = max(1, b - a)
        every = next((s for s in NICE_STEPS if span / s <= 12), NICE_STEPS[-1])
        while (b - a) // every + 1 > MAX_TICKS:
            every *= 2
    first = -((-a) // every) * every
    return [y for y in range(first, b + 1, every)], every


def time_x(d, a, b) -> float:
    return (SCALE_X0 + (d - a) / float(b - a) * (SCALE_X1 - SCALE_X0)) * W


class TimePlace:
    """Where one item of TIME-01 goes: its side, stalk length and the baselines and left edges of its year and label."""
    __slots__ = ("x", "side", "tier", "anchor", "length", "year_left", "year_base", "label_left", "label_base", "rects", "stalk")


@functools.lru_cache(maxsize=256)
def solve_time(items: tuple, a: int, b: int, cap_key: int):
    """Lay the items of a time axis out. `items` = ((date, label, side, accent), ...), `cap_key` = 100 x the label's cap height in percent.
    Returns (places in the order of `items`, solved): a depth first search over (side, tier, anchor) for every item, the accented items first;
    `solved` is False when no arrangement leaves every label clear of the others and inside the frame (then the first choices are returned)."""
    cap_pct = cap_key / 100.0
    c = cap_pct / 100.0 * H
    kl, ky = "eb_italic", "eb_medium"
    szl, szy = font_size(kl, c), font_size(ky, c * YEAR_K)
    year_cap = szy * vfx.cap_ratio(ky)
    n = len(items)
    rank = {i: r for r, i in enumerate(sorted(range(n), key=lambda i: (items[i][0], i)))}
    cands, meas = [], []
    for i, (d, label, side, accent) in enumerate(items):
        x = time_x(d, a, b)
        wl, bl = measure(label, kl, szl)
        wy, by = measure(year_text(d), ky, szy)
        meas.append((x, wl, bl, wy, by))
        pref = "up" if rank[i] % 2 == 0 else "down"
        if side == "auto":
            order = [pref, "down" if pref == "up" else "up"]
        else:
            order = [side]
        lst = []

        def make(sd, tier, anchor):
            length = TIERS[sd][tier]
            if sd == "up":
                lbase = AXIS_Y - length - GAP_UP * c
                ybase = lbase - LINE_K * c
            else:
                ybase = AXIS_Y + length + GAP_DOWN * c + year_cap
                lbase = ybase + LINE_K * c
            if anchor == "c":
                left = min(max(x - wl / 2.0, FRAME_X), W - FRAME_X - wl)
            else:
                left = x - dict(ANCHORS)[anchor] * wl
            yleft = x - wy / 2.0
            yr = (yleft + by[0], ybase + by[1], yleft + by[2], ybase + by[3])
            lr = (left + bl[0], lbase + bl[1], left + bl[2], lbase + bl[3])
            for r in (yr, lr):
                if r[0] < FRAME_X or r[2] > W - FRAME_X or r[1] < FRAME_Y0 or r[3] > FRAME_Y1:
                    return None
            pl = TimePlace()
            pl.x, pl.side, pl.tier, pl.anchor, pl.length = x, sd, tier, anchor, length
            pl.year_left, pl.year_base, pl.label_left, pl.label_base = yleft, ybase, left, lbase
            pl.rects = (yr, lr)
            y_end = AXIS_Y - length if sd == "up" else AXIS_Y + length
            pl.stalk = (x - 1 - STALK_PAD, min(AXIS_Y, y_end), x + 1 + STALK_PAD, max(AXIS_Y, y_end))
            return pl
        for anchors in (("c",), ("l", "r")):
            for sd in order:
                for tier in range(len(TIERS[sd])):
                    for an in anchors:
                        pl = make(sd, tier, an)
                        if pl is not None:
                            lst.append(pl)
        cands.append(lst)

    def clash(p, q) -> bool:
        for ra in p.rects:
            for rb in q.rects:
                if _hit(ra, rb, PAD_X, PAD_Y):
                    return True
            if _hit(ra, q.stalk, 0.0, PAD_Y):
                return True
        for rb in q.rects:
            if _hit(rb, p.stalk, 0.0, PAD_Y):
                return True
        return False

    order = sorted((i for i in range(n) if items[i][3]), key=lambda i: (items[i][0], i)) + sorted((i for i in range(n) if not items[i][3]), key=lambda i: (items[i][0], i))
    sol = [None] * n
    budget = [TIME_SEARCH_BUDGET]

    def dfs(k) -> bool:
        if k == n:
            return True
        i = order[k]
        for cand in cands[i]:
            budget[0] -= 1
            if budget[0] < 0:
                return False
            if all(not clash(cand, sol[j]) for j in order[:k]):
                sol[i] = cand
                if dfs(k + 1):
                    return True
        sol[i] = None
        return False
    solved = bool(all(cands)) and dfs(0)
    if not solved:                                   # the best the greedy choice gives: least clashes with what is already placed
        placed = {}
        for i in order:
            pool = cands[i] or [_fallback_place(meas[i], items[i], a, b, c, szl, szy)]
            placed[i] = min(pool, key=lambda p: sum(clash(p, placed[j]) for j in placed))
        sol = [placed[i] for i in range(n)]
    return tuple(sol), solved


def _fallback_place(m, item, a, b, c, szl, szy):
    """A place for an item that has no candidate inside the frame (a label wider than the frame): centred above or below the axis, on the first tier."""
    x, wl, bl, wy, by = m
    sd = "down" if item[2] == "down" else "up"
    length = TIERS[sd][0]
    lbase = AXIS_Y - length - GAP_UP * c if sd == "up" else AXIS_Y + length + GAP_DOWN * c + szy * vfx.cap_ratio("eb_medium") + LINE_K * c
    ybase = lbase - LINE_K * c if sd == "up" else lbase - LINE_K * c
    pl = TimePlace()
    pl.x, pl.side, pl.tier, pl.anchor, pl.length = x, sd, 0, "c", length
    pl.year_left, pl.year_base, pl.label_left, pl.label_base = x - wy / 2.0, ybase, x - wl / 2.0, lbase
    pl.rects = ((pl.year_left + by[0], ybase + by[1], pl.year_left + by[2], ybase + by[3]), (pl.label_left + bl[0], lbase + bl[1], pl.label_left + bl[2], lbase + bl[3]))
    y_end = AXIS_Y - length if sd == "up" else AXIS_Y + length
    pl.stalk = (x - 1 - STALK_PAD, min(AXIS_Y, y_end), x + 1 + STALK_PAD, max(AXIS_Y, y_end))
    return pl


def time_items_key(p) -> tuple:
    return tuple((int(round(it["date"])), str(it["label"]), it["side"], bool(it["accent"])) for it in p["items"])


@technique("TIME-01", "base")
class TimeAxis(BaseRenderer):
    """TIME-01, the time axis with dates. Times (`at` of an item, `focus_s`) are seconds from the start of the shot; an `at` that is a word
    anchor is the absolute time of that word, taken from the start of the shot (`registry.at_seconds`). The axis grows over the first 0.8 s;
    an item's stalk grows over 0.35 s from its `at` (an ease out), its year fades in from +0.2 s and its label from +0.35 s; the accented
    item gets a dot on the axis from its `at`; from `focus_s` (0.8 s) the accented items brighten and the others dim to `dim_to`."""

    @classmethod
    def check_params(cls, p: dict):
        out = []
        fa, fb = parse_year(p.get("from")), parse_year(p.get("to"))
        if fa is not None and fb is not None and fa >= fb:
            out.append(("to", "time_range_inverted", {"from": fa, "to": fb}, "`to` (%d) must be after `from` (%d)" % (fb, fa)))
            return out
        a, b = time_range(p)
        if b <= a:
            out.append(("to", "time_range_inverted", {"from": a, "to": b}, "`to` (%d) must be after `from` (%d)" % (b, a)))
            return out
        for i, it in enumerate(p["items"]):
            d = int(round(it["date"]))
            if not a <= d <= b:
                out.append(("items", "time_date_outside", {"index": i, "date": d, "from": a, "to": b, "item": str(it["label"])[:40]},
                            "item %d (%s): the date %d is outside the axis (%d to %d)" % (i + 1, str(it["label"])[:40], d, a, b)))
        if not out:
            _places, solved = solve_time(time_items_key(p), a, b, int(round(float(p["cap_pct"]) * 100)))
            if not solved:
                out.append(("items", "time_crowded", {"count": len(p["items"])}, "the items are too close together: no arrangement keeps every label clear of the others and inside the frame"))
        return out

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.a, self.b = time_range(p)
        if self.b <= self.a:
            self.a, self.b = self.a, self.a + 1
        self.cap_px = float(p["cap_pct"]) / 100.0 * H
        self.items = []
        key = time_items_key(p)
        self.places, self.solved = solve_time(key, self.a, self.b, int(round(float(p["cap_pct"]) * 100)))
        kl, ky = "eb_italic", "eb_medium"
        szl, szy = font_size(kl, self.cap_px), font_size(ky, self.cap_px * YEAR_K)
        for it, pl in zip(p["items"], self.places):
            self.items.append({"at": R.at_seconds(it.get("at"), self.t0, 0.0), "accent": bool(it["accent"]), "pl": pl,
                               "year": get_ink(ctx, year_text(it["date"]), ky, szy), "label": get_ink(ctx, str(it["label"]), kl, szl)})
        self.ticks, self.step = tick_years(self.a, self.b, p["tick_every"])
        self.has_accent = any(i["accent"] for i in self.items)
        self.dim_to = float(p["dim_to"])
        self.focus_s = float(p["focus_s"])

    def focus(self, tau) -> float:
        return seg(tau, self.focus_s, self.focus_s + FOCUS_S) if self.has_accent else 0.0

    def render(self, t):
        tau = float(t) - self.t0
        f = np.empty((H, W, 3), np.float32)
        f[:] = GROUND_F
        grow = ease_inout(seg(tau, 0.0, AXIS_S))
        fill_rect(f, AXIS_X0, AXIS_Y - HAIR_PX / 2.0, AXIS_X0 + grow * (AXIS_X1 - AXIS_X0), AXIS_Y + HAIR_PX / 2.0, HAIR_F)
        n = len(self.ticks)
        stagger = min(TICK_STAGGER, 0.48 / max(1, n - 1))
        for k, y in enumerate(self.ticks):
            al = seg(tau, TICK_FROM + k * stagger, TICK_FROM + TICK_S + k * stagger)
            major = (y // self.step) % 5 == 0 and y % self.step == 0
            half = TICK_MAJOR if major else TICK_MINOR
            x = time_x(y, self.a, self.b)
            fill_rect(f, x - HAIR_PX / 2.0, AXIS_Y - half, x + HAIR_PX / 2.0, AXIS_Y + half, HAIR_F, al)
        focus = self.focus(tau)
        for it in self.items:
            pl = it["pl"]
            dim = 1.0 if it["accent"] else lerp(1.0, self.dim_to, focus)
            grown = ease_out(seg(tau, it["at"], it["at"] + STALK_S))
            if grown > 0:
                y_end = AXIS_Y - grown * pl.length if pl.side == "up" else AXIS_Y + grown * pl.length
                fill_rect(f, pl.x - HAIR_PX / 2.0, min(AXIS_Y, y_end), pl.x + HAIR_PX / 2.0, max(AXIS_Y, y_end), TEXT_F if it["accent"] else HAIR_F, dim)
            paint(f, it["year"], pl.year_left, pl.year_base, TEXT_F, seg(tau, it["at"] + YEAR_AT, it["at"] + YEAR_AT + YEAR_S) * dim)
            paint(f, it["label"], pl.label_left, pl.label_base, TEXT_F, seg(tau, it["at"] + LABEL_AT, it["at"] + LABEL_AT + LABEL_S) * dim)
        for it in self.items:
            if it["accent"]:
                blend_disc(f, it["pl"].x, AXIS_Y, DOT_D / 2.0 * lerp(1.0, DOT_GROWTH, focus), TEXT_F, seg(tau, it["at"], it["at"] + 0.3))
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


# ============================================================================= TREE-01
EDGE_S, EDGE_LABEL_AT, EDGE_LABEL_S, NODE_S = 0.7, 0.4, 0.4, 0.4
NAME_STRONG, SUB_K, EDGE_LABEL_K = 1.1, 0.72, 0.667      # strong names are 10 percent larger; the second line is 0.72, an edge label 0.667 of the name (mock-up)
SUB_BASE_K = 1.5                                          # baseline of the second line below the name baseline, in name cap heights
ROW_CENTRE, ROW_PITCH_MAX, ROW_SPAN = 0.515, 0.3275, 0.66
MAX_ROWS = 5
UNIT_GAP, DUMMY_W, MARRY_GAP, MARRY_PAD = 0.045 * W, 0.022 * W, 0.09 * W, 0.0125 * W
START_GAP, END_GAP, LANE = 0.016 * H, 0.011 * H, 0.011 * H
TREE_FRAME_X = 0.03 * W
TREE_SCALES = (1.0, 0.94, 0.88, 0.82, 0.76, 0.70, 0.64)
TREE_ID_PATTERN = r"[A-Za-z0-9_-]{1,24}"


class TreeResult:
    """The solved layout of a tree: `nodes` and `edges` in the order of the data (edges that name a missing node or join a node to itself are left
    out), `ok`, and why not (`reason`: wide, rows, overlap, marriage_rows, marriage_shape)."""

    def __init__(self):
        self.ok, self.reason, self.scale, self.nodes, self.edges, self.manual, self.detail, self.label_size = True, None, 1.0, [], [], False, None, 0


def _node_metrics(n, cap):
    nid, name, sub, row, col, strong = n
    kind = "eb_medium" if strong else "eb_regular"
    c1 = cap * (NAME_STRONG if strong else 1.0)
    s1 = font_size(kind, c1)
    w1, b1 = measure(name, kind, s1)
    m = {"kind": kind, "s1": s1, "w1": w1, "b1": b1, "sub": sub, "w2": 0.0, "b2": None, "s2": None}
    if sub:
        m["s2"] = font_size("eb_italic", cap * SUB_K)
        m["w2"], m["b2"] = measure(sub, "eb_italic", m["s2"])
    m["w"] = max(w1, m["w2"])
    return m


def _pav(d, s, w=None):
    """Positions closest (weighted least squares) to the wanted `d` that keep the distance `s[i]` between neighbours i and i + 1 at least."""
    n = len(d)
    w = w or [1.0] * n
    c = [0.0] * n
    for i in range(1, n):
        c[i] = c[i - 1] + s[i - 1]
    blocks = []                                      # pool adjacent violators: [sum of weight x value, sum of weights, count]
    for i in range(n):
        blocks.append([w[i] * (d[i] - c[i]), w[i], 1])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            a, b, k = blocks.pop()
            blocks[-1][0] += a
            blocks[-1][1] += b
            blocks[-1][2] += k
    out = []
    for sm, ws, cn in blocks:
        out += [sm / ws] * cn
    return [out[i] + c[i] for i in range(n)]


def _chain_order(members, partners):
    """The members of one marriage group in a row: walk the chain from an end; None when the group is not a chain (a person with three spouses, or a ring)."""
    if len(members) == 1:
        return list(members)
    ends = [m for m in members if len(partners[m]) == 1]
    if any(len(partners[m]) > 2 for m in members) or not ends:
        return None
    out, prev, cur = [], None, min(ends)
    while cur is not None:
        out.append(cur)
        nxt = [q for q in partners[cur] if q != prev and q not in out]
        prev, cur = cur, (nxt[0] if nxt else None)
    return out if len(out) == len(members) else None


def _marriages(n, es):
    """(partners, unit_of, chains): who is married to whom, the group (unit) of every node and the members of every unit in a chain; None when a group is not a chain."""
    partners = {i: [] for i in range(n)}
    for a, b, k, _lab in es:
        if k == "marriage" and b not in partners[a]:
            partners[a].append(b)
            partners[b].append(a)
    root = list(range(n))

    def find(x):
        while root[x] != x:
            root[x] = root[root[x]]
            x = root[x]
        return x
    for a in range(n):
        for b in partners[a]:
            root[find(a)] = find(b)
    members = {}
    for i in range(n):
        members.setdefault(find(i), []).append(i)
    chains = {}
    for g, mem in members.items():
        ch = _chain_order(sorted(mem), partners)
        if ch is None:
            return None
        chains[g] = ch
    return partners, {i: find(i) for i in range(n)}, chains


def _auto_rows(es, unit_of, chains):
    """Row of every unit: the longest path down from the sources along descent and link edges (spouses share a row); a source whose people
    are all further down moves down next to them; edges that close a ring are ignored. Returns ({unit: row}, units in order)."""
    groups = sorted(chains, key=lambda g: min(chains[g]))
    succ = {g: set() for g in chains}
    for a, b, k, _lab in es:
        if k != "marriage" and unit_of[a] != unit_of[b]:
            succ[unit_of[a]].add(unit_of[b])
    indeg = {g: 0 for g in chains}
    for g in succ:
        for h in succ[g]:
            indeg[h] += 1
    row, deg = {g: 0 for g in chains}, dict(indeg)
    queue, done = [g for g in groups if deg[g] == 0], []
    while queue:
        g = queue.pop(0)
        done.append(g)
        for h in sorted(succ[g], key=lambda h: min(chains[h])):
            row[h] = max(row[h], row[g] + 1)
            deg[h] -= 1
            if deg[h] == 0:
                queue.append(h)
    for g in groups:
        if g not in done:                                      # on a ring: below whatever is already placed above it
            above = [row[q] for q in done if g in succ[q]]
            row[g] = max(above) + 1 if above else 0
            done.append(g)
    for g in reversed(done):
        if indeg[g] == 0 and succ[g]:
            row[g] = max(row[g], min(row[h] for h in succ[g]) - 1)
    return row, groups


def _crossings(layers, hops):
    pos = {it: k for lay in layers for k, it in enumerate(lay)}
    lay_of = {it: r for r, lay in enumerate(layers) for it in lay}
    tot = 0
    for i, (u1, _a, v1, _b) in enumerate(hops):
        for (u2, _c, v2, _d) in hops[i + 1:]:
            if u1 != u2 and v1 != v2 and lay_of[u1] == lay_of[u2] and (pos[u1] - pos[u2]) * (pos[v1] - pos[v2]) < 0:
                tot += 1
    return tot


@functools.lru_cache(maxsize=128)
def solve_tree(nodes: tuple, edges: tuple, cap_key: int):
    """Lay a tree out. `nodes` = ((id, name, sub, row, col, strong), ...), `edges` = ((from, to, kind, label), ...), `cap_key` = 100 x the name's cap height in
    percent. Makes the text smaller (down to 64 percent) while the tree is too wide for the frame. Returns a `TreeResult`."""
    last = None
    for s in TREE_SCALES:
        cap = cap_key / 100.0 / 100.0 * H * s
        last = _tree_attempt(nodes, edges, cap, s)
        if not last.ok:
            if last.reason != "wide":
                return last
            continue
        if not last.manual:                                  # a small tree is spread out over the frame, as far as 82 percent of its width
            for spread in (3.4, 2.8, 2.3, 1.8, 1.4):
                wide = _tree_attempt(nodes, edges, cap, s, spread)
                if wide.ok and max(nd["box"][2] for nd in wide.nodes) - min(nd["box"][0] for nd in wide.nodes) <= 0.82 * W:
                    return wide
        return last
    return last


def _tree_attempt(nodes, edges, cap, scale, spread=1.0) -> TreeResult:
    res = TreeResult()
    res.scale = scale
    n = len(nodes)
    if n == 0:
        return res
    idx = {nd[0]: i for i, nd in enumerate(nodes)}
    es = [(idx[a], idx[b], k, lab) for (a, b, k, lab) in edges if a in idx and b in idx and a != b]
    M = [_node_metrics(nd, cap) for nd in nodes]
    el_size = font_size("eb_italic", cap * EDGE_LABEL_K)
    res.label_size = el_size
    manual = all(nd[3] >= 0 and nd[4] >= 0 for nd in nodes)
    res.manual = manual
    gs = scale
    mar = _marriages(n, es)
    if mar is None:
        res.ok, res.reason = False, "marriage_shape"
        return res
    partners, unit_of, chains = mar

    def marry_gap(a, b):
        lab = next((l for (x, y, k, l) in es if k == "marriage" and {x, y} == {a, b} and l), "")
        w = measure(lab, "eb_italic", el_size)[0] if lab else 0.0
        return max(MARRY_GAP * gs, w + 0.045 * W * gs)

    dummies = {}                                       # dummy item -> x
    chain_of = {}                                      # edge index -> (upper member, lower member, items from upper unit to lower unit)
    if manual:
        for a, b, k, _lab in es:
            if k == "marriage" and abs(nodes[a][3] - nodes[b][3]) > 1e-9:
                res.ok, res.reason, res.detail = False, "marriage_rows", (a, b)
                return res
        row_key = [float(nd[3]) for nd in nodes]
        rmin, rmax = min(row_key), max(row_key)
        n_rows = int(math.floor(rmax - rmin)) + 1
        cmin, cmax = min(nd[4] for nd in nodes), max(nd[4] for nd in nodes)
        need_l = max(M[i]["w"] / 2.0 for i in range(n) if nodes[i][4] == cmin)
        need_r = max(M[i]["w"] / 2.0 for i in range(n) if nodes[i][4] == cmax)
        xl, xr = TREE_FRAME_X + need_l, W - TREE_FRAME_X - need_r
        span = cmax - cmin
        pitch_x = min(0.2 * W, (xr - xl) / span) if span > 0 else 0.0
        x0 = W / 2.0 - span * pitch_x / 2.0
        xs = [x0 + (nd[4] - cmin) * pitch_x for nd in nodes]
        mid_row = (rmin + rmax) / 2.0
    else:
        urow, order = _auto_rows(es, unit_of, chains)
        row_key = [float(urow[unit_of[i]]) for i in range(n)]
        n_rows = int(max(row_key)) + 1
        if n_rows > MAX_ROWS:
            res.ok, res.reason, res.detail = False, "rows", n_rows
            return res
        mid_row = (n_rows - 1) / 2.0
        layers = [[] for _ in range(n_rows)]
        for g in order:
            layers[urow[g]].append(("u", g))
        seen_hop = set()
        hops, hop_cp = [], []                          # (upper item, upper member or None, lower item, lower member or None) between adjacent layers; the flag: from a couple's middle
        for ei, (a, b, k, _lab) in enumerate(es):
            if k == "marriage":
                continue
            up, dn = (a, b) if row_key[a] <= row_key[b] else (b, a)
            ra, rb = int(row_key[up]), int(row_key[dn])
            if rb == ra:
                continue                               # a link inside one row: drawn as a line between the two names
            items = [("u", unit_of[up])]
            for r in range(ra + 1, rb):
                d = ("d", ei, r)
                layers[r].append(d)
                dummies[d] = 0.0
                items.append(d)
            items.append(("u", unit_of[dn]))
            chain_of[ei] = (up, dn, items)
            from_couple = k == "descent" and up == a and len(partners[a]) == 1
            if from_couple:
                twin = (dn, min(a, partners[a][0]))
                if twin in seen_hop:                       # both spouses write the same child: one connector, one pull
                    continue
                seen_hop.add(twin)
            for q, (u, v) in enumerate(zip(items[:-1], items[1:])):
                hops.append((u, up if q == 0 else None, v, dn if q == len(items) - 2 else None))
                hop_cp.append(from_couple)
        up_nb, dn_nb = {}, {}
        for u, _mu, v, _mv in hops:
            dn_nb.setdefault(u, []).append(v)
            up_nb.setdefault(v, []).append(u)
        best, best_c = [list(lay) for lay in layers], _crossings(layers, hops)
        for sweep in range(10):
            down = sweep % 2 == 0
            for r in (range(1, n_rows) if down else range(n_rows - 2, -1, -1)):
                pos = {it: k for lay in layers for k, it in enumerate(lay)}
                key = {}
                for k, it in enumerate(layers[r]):
                    nb = [pos[q] for q in (up_nb if down else dn_nb).get(it, [])]
                    key[it] = sum(nb) / len(nb) if nb else k
                layers[r] = sorted(layers[r], key=lambda it: (key[it], pos[it]))
            c = _crossings(layers, hops)
            if c < best_c:
                best, best_c = [list(lay) for lay in layers], c
        layers = best
        pos = {it: k for lay in layers for k, it in enumerate(lay)}
        for g, ch in list(chains.items()):                 # the spouse whose neighbours lie further left goes first
            if len(ch) < 2:
                continue

            def where(m):                                    # where the parents of this spouse stand
                ps = [pos[u] for (u, mu, v, mv) in hops if mv == m]
                return sum(ps) / len(ps) if ps else None
            l0, l1 = where(ch[0]), where(ch[-1])
            if l0 is not None and l1 is not None and l0 > l1:
                chains[g] = list(reversed(ch))
        uw, off = {}, {}                                   # width of a unit, offset of every member's centre from the centre of its unit
        for g, ch in chains.items():
            x = 0.0
            cen = {}
            for k, m in enumerate(ch):
                if k:
                    x += marry_gap(ch[k - 1], m)
                cen[m] = x + M[m]["w"] / 2.0
                x += M[m]["w"]
            uw[("u", g)] = x
            for m in ch:
                off[m] = cen[m] - x / 2.0
        for d in dummies:
            uw[d] = DUMMY_W
        ux = {}
        for lay in layers:
            total = sum(uw[it] for it in lay) + UNIT_GAP * gs * spread * (len(lay) - 1)
            x = W / 2.0 - total / 2.0
            for it in lay:
                ux[it] = x + uw[it] / 2.0
                x += uw[it] + UNIT_GAP * gs * spread
        hop_of = {}
        for (u, mu, v, mv), cp in zip(hops, hop_cp):
            au = sum(off[m] for m in chains[u[1]]) / len(chains[u[1]]) if cp and u[0] == "u" and mu is not None else 0.0     # the middle of the marriage
            av = off[mv] if cp and mv is not None else 0.0                                                                 # the child's own name, straight below it
            hop_of.setdefault(u, []).append((v, av, au))     # (the other end, its anchor, my anchor)
            hop_of.setdefault(v, []).append((u, au, av))

        def wanted(it):                                       # (where the unit wants to stand, how strongly): units are lined up by their centres
            ts = [ux[o] + oa - ma for (o, oa, ma) in hop_of.get(it, [])]
            return (sum(ts) / len(ts), float(len(ts))) if ts else (ux[it], 0.01)
        def relax(rows_order):
            for r in rows_order:
                lay = layers[r]
                des = [wanted(it) for it in lay]
                sep = [(uw[lay[k]] + uw[lay[k + 1]]) / 2.0 + UNIT_GAP * gs * spread * (0.45 if "d" in (lay[k][0], lay[k + 1][0]) else 1.0) for k in range(len(lay) - 1)]
                for it, xv in zip(lay, _pav([x for x, _w in des], sep, [w for _x, w in des])):
                    ux[it] = xv
        for sweep in range(120):                              # symmetric Gauss-Seidel: down, then up; the picture is re-centred so that it cannot drift
            before = dict(ux)
            relax(range(n_rows))
            relax(range(n_rows - 2, -1, -1))
            lo, hi = min(ux[it] - uw[it] / 2.0 for it in ux), max(ux[it] + uw[it] / 2.0 for it in ux)
            for it in ux:
                ux[it] += W / 2.0 - (lo + hi) / 2.0
            if sweep > 4 and max(abs(ux[k] - before[k]) for k in ux) < 0.05:
                break
        xs = [ux[("u", unit_of[m])] + off[m] for m in range(n)]
        left, right = min(xs[m] - M[m]["w"] / 2.0 for m in range(n)), max(xs[m] + M[m]["w"] / 2.0 for m in range(n))
        shift = W / 2.0 - (left + right) / 2.0
        xs = [x + shift for x in xs]
        for d in dummies:
            dummies[d] = ux[d] + shift
    pitch = min(ROW_PITCH_MAX, ROW_SPAN / (n_rows - 1)) if n_rows > 1 else 0.0
    y_of = lambda r: (ROW_CENTRE if n_rows > 1 else 0.5) * H + (r - mid_row) * pitch * H
    # ---- the names: baselines, boxes, inside the frame, nothing touching
    base1, boxes = [], []
    for i in range(n):
        b1 = y_of(row_key[i]) - 0.225 * cap
        m = M[i]
        base1.append(b1)
        bottom = b1 + SUB_BASE_K * cap + m["b2"][3] if m["sub"] else b1 + m["b1"][3]
        boxes.append((xs[i] - m["w"] / 2.0, b1 + m["b1"][1], xs[i] + m["w"] / 2.0, bottom))
    for i in range(n):
        if boxes[i][0] < TREE_FRAME_X or boxes[i][2] > W - TREE_FRAME_X or boxes[i][1] < 0.02 * H or boxes[i][3] > 0.98 * H:
            res.ok, res.reason = False, "wide"
        for j in range(i):
            if _hit(boxes[i], boxes[j], 0.018 * W * scale, 0.01 * H):
                res.ok, res.reason, res.detail = False, ("overlap" if manual else "wide"), (j, i)
    res.nodes = [{"x": xs[i], "base1": base1[i], "base2": base1[i] + SUB_BASE_K * cap, "box": boxes[i], "metrics": M[i], "row": row_key[i]} for i in range(n)]
    # ---- connectors
    row_bottom, row_top = {}, {}
    for i in range(n):
        r = row_key[i]
        row_bottom[r] = max(row_bottom.get(r, -1e9), boxes[i][3])
        row_top[r] = min(row_top.get(r, 1e9), boxes[i][1])

    def gap_mid(ra, rb):
        return (row_bottom[ra] + row_top[rb]) / 2.0 if ra in row_bottom and rb in row_top else (y_of(ra) + y_of(rb)) / 2.0
    marry_y = lambda i: base1[i] - 0.28 * cap

    def side_line(a, b):
        """A horizontal line between the facing ends of two names of one row, drawn from a to b."""
        lo, hi = (a, b) if xs[a] <= xs[b] else (b, a)
        y = marry_y(a)
        x0 = xs[lo] + M[lo]["w1"] / 2.0 + MARRY_PAD * gs
        x1 = xs[hi] - M[hi]["w1"] / 2.0 - MARRY_PAD * gs
        pts = [(x0, y), (x1, y)] if x1 > x0 + 4 else [(xs[lo], y), (xs[hi], y)]
        return pts if a == lo else list(reversed(pts))
    spouse = {i: ps[0] for i, ps in partners.items() if len(ps) == 1}
    seen_descent, plans = set(), []
    for ei, (a, b, k, lab) in enumerate(es):
        item = {"from": a, "to": b, "kind": k, "label": lab, "path": None, "skip": False, "label_at": None}
        plans.append(item)
        if k == "marriage" or abs(row_key[a] - row_key[b]) < 1e-9:
            item["path"] = side_line(a, b)
            continue
        flip = row_key[a] > row_key[b]                      # `to` lies above `from`: route from the upper name and draw backwards
        up, dn = (b, a) if flip else (a, b)
        if k == "descent" and not flip and a in spouse and abs(row_key[a] - row_key[spouse[a]]) < 1e-9:
            key = (b, min(a, spouse[a]))                    # both spouses write the same child: one connector, from the middle of the marriage
            item["skip"] = key in seen_descent
            seen_descent.add(key)
            start = ((xs[a] + xs[spouse[a]]) / 2.0, marry_y(a) + 0.012 * H)
        else:
            start = (xs[up], boxes[up][3] + START_GAP)
        end = (xs[dn], boxes[dn][1] - END_GAP)
        inter = [(dummies[d], d[2]) for d in (chain_of[ei][2][1:-1] if ei in chain_of else [])]
        item["plan"] = (flip, start, end, [(row_key[up], None)] + [(r, x) for x, r in inter] + [(row_key[dn], None)])
    # lanes: horizontal runs of different edges that would lie on top of each other get their own heights inside the gap between two rows
    runs = {}
    for ei, item in enumerate(plans):
        if item.get("plan") is None or item["skip"]:
            continue
        flip, start, end, rows_seq = item["plan"]
        x_prev = start[0]
        for q in range(1, len(rows_seq)):
            x_next = rows_seq[q][1] if rows_seq[q][1] is not None else end[0]
            if abs(x_next - x_prev) > 0.5:
                runs.setdefault((rows_seq[q - 1][0], rows_seq[q][0]), []).append((ei, q, min(x_prev, x_next), max(x_prev, x_next), x_prev, x_next))
            x_prev = x_next
    lane_of = {}
    for key, lst in runs.items():
        lanes = []
        for rec in sorted(lst, key=lambda r: (r[2], r[3])):
            for lane in lanes:
                if all(rec[2] >= o[3] - 2 or o[2] >= rec[3] - 2 or abs(rec[4] - o[4]) < 1 or abs(rec[5] - o[5]) < 1 for o in lane):
                    lane.append(rec)
                    break
            else:
                lanes.append([rec])
        for li, lane in enumerate(lanes):
            for rec in lane:
                lane_of[(rec[0], rec[1])] = (li - (len(lanes) - 1) / 2.0) * LANE
    for ei, item in enumerate(plans):
        if item.get("plan") is None or item["skip"]:
            continue
        flip, start, end, rows_seq = item["plan"]
        pts, x_cur = [start], start[0]
        for q in range(1, len(rows_seq)):
            x_next = rows_seq[q][1] if rows_seq[q][1] is not None else end[0]
            ym = gap_mid(rows_seq[q - 1][0], rows_seq[q][0]) + lane_of.get((ei, q), 0.0)
            pts += [(x_cur, ym), (x_next, ym)]
            x_cur = x_next
        pts.append(end)
        clean = [pts[0]]
        for pnt in pts[1:]:
            if abs(pnt[0] - clean[-1][0]) > 0.5 or abs(pnt[1] - clean[-1][1]) > 0.5:
                clean.append(pnt)
        k = 1
        while k < len(clean) - 1:                                  # a point in the middle of a straight run is not a corner
            a_, b_, c_ = clean[k - 1], clean[k], clean[k + 1]
            if (abs(a_[0] - b_[0]) < 0.5 and abs(b_[0] - c_[0]) < 0.5) or (abs(a_[1] - b_[1]) < 0.5 and abs(b_[1] - c_[1]) < 0.5):
                del clean[k]
            else:
                k += 1
        item["path"] = list(reversed(clean)) if flip else clean
    res.edges = plans
    # ---- labels of the edges: beside the longest vertical run, above a horizontal line, else wherever they touch least
    segs = []
    for e in plans:
        if e["path"] and not e["skip"]:
            for p, q in zip(e["path"][:-1], e["path"][1:]):
                segs.append((min(p[0], q[0]) - LINE_PX, min(p[1], q[1]) - LINE_PX, max(p[0], q[0]) + LINE_PX, max(p[1], q[1]) + LINE_PX))
    placed = []
    for e in plans:
        if not e["label"] or e["skip"] or not e["path"]:
            continue
        wl, bl = measure(e["label"], "eb_italic", el_size)
        c_l = el_size * vfx.cap_ratio("eb_italic")
        pts = e["path"]
        cands = []
        if len(pts) == 2 and abs(pts[0][1] - pts[1][1]) < 1.0:
            mx, my = (pts[0][0] + pts[1][0]) / 2.0, pts[0][1]
            cands += [(mx - wl / 2.0, my - 1.4 * c_l), (mx - wl / 2.0, my + 2.4 * c_l)]
        else:
            hors = sorted(((abs(q[0] - p[0]), p, q) for p, q in zip(pts[:-1], pts[1:]) if abs(q[1] - p[1]) < 0.5), key=lambda v: -v[0])
            for ln, p, q in hors:                                # above its own horizontal run when that is long enough for the words
                if ln >= wl + 16:
                    cands.append(((p[0] + q[0]) / 2.0 - wl / 2.0, p[1] - 1.1 * c_l))
            for ln, p, q in sorted(((abs(q[1] - p[1]), p, q) for p, q in zip(pts[:-1], pts[1:]) if abs(q[0] - p[0]) < 0.5), key=lambda v: -v[0]):
                cy = (p[1] + q[1]) / 2.0
                cands += [(p[0] + 0.024 * W, cy + c_l / 2.0), (p[0] - 0.024 * W - wl, cy + c_l / 2.0)]
            for ln, p, q in hors:
                cands.append(((p[0] + q[0]) / 2.0 - wl / 2.0, p[1] - 1.1 * c_l))
        best = None
        for lx, lb in cands or [(pts[0][0], pts[0][1])]:
            box = (lx + bl[0], lb + bl[1], lx + bl[2], lb + bl[3])
            cost = (4 if box[0] < TREE_FRAME_X * 0.5 or box[2] > W - TREE_FRAME_X * 0.5 else 0)
            cost += 3 * sum(_hit(box, nb, 6, 4) for nb in boxes) + 3 * sum(_hit(box, sg, 4, 4) for sg in segs) + 3 * sum(_hit(box, pb, 10, 6) for pb in placed)
            if best is None or cost < best[0]:
                best = (cost, lx, lb, box)
                if cost == 0:
                    break
        e["label_at"] = (best[1], best[2])
        placed.append(best[3])
    return res


@functools.lru_cache(maxsize=512)
def _partial(path: tuple, prog: float):
    """The vertices of a polyline drawn up to the fraction `prog` of its length."""
    pts = [np.array(p, np.float64) for p in path]
    seglen = [float(np.hypot(*(q - p))) for p, q in zip(pts[:-1], pts[1:])]
    total = sum(seglen)
    if total <= 0:
        return tuple(path[:1])
    goal, out, acc = prog * total, [tuple(pts[0])], 0.0
    for p, q, ln in zip(pts[:-1], pts[1:], seglen):
        if acc + ln <= goal + 1e-9:
            out.append(tuple(q))
            acc += ln
        else:
            u = (goal - acc) / ln if ln > 0 else 0.0
            out.append(tuple(p + (q - p) * u))
            break
    return tuple(out)


@technique("TREE-01", "base")
class RelationTree(BaseRenderer):
    """TREE-01, relations between people. Times (`at` of a node and of an edge) are seconds from the start of the shot (or word anchors). A node
    fades in over 0.4 s; a connector is drawn over 0.7 s from the `from` end (an ease in and out) and its label fades in from +0.4 s over 0.4 s."""

    @classmethod
    def check_params(cls, p: dict):
        out = []
        nodes = p["nodes"]
        seen = {}
        for i, nd in enumerate(nodes):
            if nd["id"] in seen:
                out.append(("nodes", "tree_duplicate_node", {"id": nd["id"], "index": i}, "item %d (%s): the id %r is already used by node %d" % (i + 1, nd["name"], nd["id"], seen[nd["id"]] + 1)))
            seen.setdefault(nd["id"], i)
        for i, e in enumerate(p["edges"]):
            for f in ("from", "to"):
                if e[f] not in seen:
                    out.append(("edges", "tree_edge_unknown_node", {"index": i, "field": f, "node": e[f]}, "item %d: %s %r names no node" % (i + 1, f, e[f])))
            if e["from"] == e["to"] and e["from"] in seen:
                out.append(("edges", "tree_edge_self", {"index": i, "node": e["from"]}, "item %d: an edge cannot join a node to itself" % (i + 1)))
        if out:
            return out
        res = solve_tree(tree_nodes_key(p), tree_edges_key(p), int(round(float(p["cap_pct"]) * 100)))
        if not res.ok:
            if res.reason == "marriage_shape":
                out.append(("edges", "tree_marriage_shape", {}, "a person can have at most two marriages and marriages must not form a ring"))
            elif res.reason == "marriage_rows":
                out.append(("edges", "tree_marriage_rows", {}, "two people who are married must be in the same row"))
            elif res.reason == "overlap":
                a, b = res.detail
                out.append(("nodes", "tree_overlap", {"a": nodes[a]["id"], "b": nodes[b]["id"]}, "the names of %r and %r touch: give them cells that are further apart" % (nodes[a]["id"], nodes[b]["id"])))
            elif res.reason == "rows":
                out.append(("nodes", "tree_too_big", {"reason": "rows", "rows": res.detail}, "the tree has %s generations; at most %d fit" % (res.detail, MAX_ROWS)))
            else:
                out.append(("nodes", "tree_too_big", {"reason": "wide"}, "the tree is too wide for the frame even with smaller text: leave out some names"))
        return out

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.layout = solve_tree(tree_nodes_key(p), tree_edges_key(p), int(round(float(p["cap_pct"]) * 100)))
        L = self.layout
        self.nodes = []
        for nd, nl in zip(p["nodes"], L.nodes):
            m = nl["metrics"]
            self.nodes.append({"at": R.at_seconds(nd.get("at"), self.t0, 0.0), "nl": nl, "name": get_ink(ctx, nd["name"], m["kind"], m["s1"]),
                               "sub": get_ink(ctx, nd["sub"], "eb_italic", m["s2"]) if nd["sub"] else None})
        valid = [(e, ed) for e, ed in zip(p["edges"], self._edge_source(p, L))]
        self.edges = []
        for e, el in valid:
            if el is None or el["skip"] or not el["path"]:
                continue
            self.edges.append({"at": R.at_seconds(e.get("at"), self.t0, 0.0), "el": el, "path": tuple((float(x), float(y)) for x, y in el["path"]),
                               "label": get_ink(ctx, e["label"], "eb_italic", L.label_size) if e["label"] and el["label_at"] else None})

    @staticmethod
    def _edge_source(p, L):
        """The solved edge of every edge of the data (None for an edge that names a missing node: `validate` refuses it, a draft draws without it)."""
        ids = {nd["id"] for nd in p["nodes"]}
        it = iter(L.edges)
        out = []
        for e in p["edges"]:
            ok = e["from"] in ids and e["to"] in ids and e["from"] != e["to"]
            out.append(next(it) if ok else None)
        return out

    def render(self, t):
        tau = float(t) - self.t0
        f = np.empty((H, W, 3), np.float32)
        f[:] = GROUND_F
        rects = []
        for e in self.edges:
            pr = ease_inout(seg(tau, e["at"], e["at"] + EDGE_S))
            if pr > 0:
                rects += path_rects(_partial(e["path"], round(pr, 5)), LINE_PX)
        fill_union(f, rects, HAIR_F)
        for e in self.edges:
            if e["label"] is not None:
                lx, lb = e["el"]["label_at"]
                paint(f, e["label"], lx, lb, TEXT_F, seg(tau, e["at"] + EDGE_LABEL_AT, e["at"] + EDGE_LABEL_AT + EDGE_LABEL_S) * SECOND)
        for nd in self.nodes:
            a = seg(tau, nd["at"], nd["at"] + NODE_S)
            if a <= 0:
                continue
            nl = nd["nl"]
            x = nl["x"]
            paint(f, nd["name"], x - nd["name"].width / 2.0, nl["base1"], TEXT_F, a)
            if nd["sub"] is not None:
                paint(f, nd["sub"], x - nd["sub"].width / 2.0, nl["base2"], TEXT_F, a * SECOND)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


def tree_nodes_key(p) -> tuple:
    return tuple((nd["id"], str(nd["name"]), str(nd["sub"] or ""), -1 if nd["row"] is None else float(nd["row"]), -1 if nd["col"] is None else float(nd["col"]), bool(nd["strong"])) for nd in p["nodes"])


def tree_edges_key(p) -> tuple:
    return tuple((e["from"], e["to"], e["kind"], str(e["label"] or "")) for e in p["edges"])


# ============================================================================= STATE-01
HOLDS_PATTERN = r"\s*\d+(?:\.\d+)?(?:\s*;\s*\d+(?:\.\d+)?){1,5}\s*;?\s*"
HOLDS_HINT = "Gõ số giây giữ từng trạng thái, cách nhau bằng dấu chấm phẩy, từ hai đến sáu số. Ví dụ: 1.5; 2.5; 1.5"
HOLD_MIN, HOLD_MAX = 0.2, 60.0
CAPTION_IN, CAPTION_IN_S, CAPTION_OUT_S, CAPTION_END_GAP = 0.3, 0.4, 0.5, 0.1
CAPTION_X, CAPTION_BOTTOM, CAPTION_TRACK = 0.045 * W, 0.94 * H, 0.14
SIZE_TOLERANCE = 0.02


def parse_holds(s):
    """The seconds of a `holds` text as a list of floats, or None when it is malformed."""
    if not isinstance(s, str):
        return None
    try:
        v = [float(x) for x in s.replace("\n", " ").split(";") if x.strip()]
    except ValueError:
        return None
    return v or None


@technique("STATE-01", "base")
class TwoStates(BaseRenderer):
    """STATE-01, the same picture in two states. Slot `a` and slot `b` hold two images of the same crop (a colour photograph and its infrared
    scan, a work before and after restoration); `camera` is one framing for both (source pixels of `a`) and, as in CAM-01, defaults to the
    whole of `a`. Image `b` is mapped onto the frame of `a`: scaled to the width of `a` and centred on it, so two images of one crop line up
    at any resolution; two crops of different shapes do not (the shape of `b` is not corrected).

    Timeline, in seconds from the start of the shot: `holds` = "h0; h1; ..." and `dissolve_s` d give hold 0 (the state `first`, then the other, and
    so on, alternating), a linear dissolve of d, hold 1, ...; the last state is held to the end of the shot, a shot shorter than the schedule is cut.
    The camera does not move during a dissolve: its clock stops while one is under way and runs faster in the holds by the time lost, so the
    whole move of its keys is still made by the end of the shot. A hold is drawn
    exactly as its state's picture alone. The name of the state (`label_a`, `label_b`) stands in small capitals at the bottom left: it fades in at
    0.3 s, flips at the middle of each dissolve through a fade out and in, and fades out over 0.5 s ending 0.1 s before the shot's end."""

    @classmethod
    def check_params(cls, p: dict):
        out = []
        holds = parse_holds(p["holds"])
        if holds is None or not 2 <= len(holds) <= 6:
            out.append(("holds", "state_holds_count", {}, "holds needs two to six numbers of seconds separated by ;"))
        elif any(not HOLD_MIN <= h <= HOLD_MAX for h in holds):
            out.append(("holds", "state_hold_range", {"min": HOLD_MIN, "max": HOLD_MAX}, "every hold must be between %s and %s seconds" % (HOLD_MIN, HOLD_MAX)))
        return out

    def __init__(self, tid, shot, ctx):
        super().__init__(tid, shot, ctx)
        p = self.p
        self.ka, self.kb = self.slot_asset("a"), self.slot_asset("b")
        self.holds = parse_holds(p["holds"]) or [1.5, 2.5, 1.5]
        self.d = float(p["dissolve_s"])
        self.starts, t = [], 0.0
        for h in self.holds[:-1]:
            t += h
            self.starts.append(t)
            t += self.d
        self.first_b = p["first"] == "b"
        self.cap_px = float(p["label_cap_pct"]) / 100.0 * H
        self.size = font_size("eb_regular", self.cap_px)
        keys = camera_keys(shot, ctx)
        if keys is None:
            w, h = ctx.asset_size(self.ka)
            keys = [(self.t0, w / 2.0, h / 2.0, fit_zoom(h), "linear")]
        self.cam = Cam(keys)
        self.labels = {"a": str(p["label_a"]).strip(), "b": str(p["label_b"]).strip()}

    # -- the schedule ------------------------------------------------------------------------------------------
    def state(self, tau):
        """(state shown, state it dissolves into or the same, progress of the dissolve 0..1): states are 0 = `first`, 1 = the other."""
        for k, s in enumerate(self.starts):
            if tau < s:
                return k % 2, k % 2, 0.0
            if tau < s + self.d:
                return k % 2, (k + 1) % 2, (tau - s) / self.d
        return (len(self.starts)) % 2, (len(self.starts)) % 2, 0.0

    def name_of(self, s) -> str:
        b = (s == 1) != self.first_b                      # is state `s` the picture b?
        return "b" if b else "a"

    def weight_b(self, tau) -> float:
        s0, s1, q = self.state(tau)
        wb0, wb1 = (1.0 if self.name_of(s) == "b" else 0.0 for s in (s0, s1))
        return wb0 + (wb1 - wb0) * q

    def cam_time(self, t) -> float:
        """The time the camera is at: its clock stands still through every dissolve and runs faster in the holds by the time that was lost, so
        the whole move of its keys is still made by the end of the shot."""
        dur = max(1e-6, self.t1 - self.t0)
        tau = min(max(0.0, float(t) - self.t0), dur)
        lost = sum(min(max(tau - s, 0.0), self.d) for s in self.starts)
        total = sum(min(max(dur - s, 0.0), self.d) for s in self.starts)
        return self.t0 + (tau - lost) * (dur / (dur - total) if dur > total + 1e-6 else 1.0)

    def view(self, t):
        cx, cy, z = self.cam.at(self.cam_time(t))
        return View(cx, cy, z, self.ctx.image(self.ka), self.ka)

    def view_b(self, v: View):
        """Where image b is looked at so that it falls on the frame of a: scaled to the width of a and centred on a."""
        ib = self.ctx.image(self.kb)
        k = v.img.w / float(ib.w)
        return ((v.cx - v.img.w / 2.0) / k + ib.w / 2.0, (v.cy - v.img.h / 2.0) / k + ib.h / 2.0, v.z * k), ib

    def caption(self, tau):
        """(text, opacity) of the name of the state."""
        s0, s1, q = self.state(tau)
        text = self.labels[self.name_of(s0 if q < 0.5 else s1)]
        a = abs(2.0 * q - 1.0) if q > 0 else 1.0
        dur = self.t1 - self.t0
        a *= seg(tau, CAPTION_IN, CAPTION_IN + CAPTION_IN_S) * (1.0 - seg(tau, dur - CAPTION_END_GAP - CAPTION_OUT_S, dur - CAPTION_END_GAP))
        return text, a

    def render(self, t):
        tau = float(t) - self.t0
        v = self.view(t)
        w = self.weight_b(tau)
        shadow = bool(self.p["shadow"])
        if w < 1.0:
            f = compose_matte(v.img, v.cx, v.cy, v.z, self.ctx.w, self.ctx.h, shadow=shadow)
        if w > 0.0:
            (bx, by, bz), ib = self.view_b(v)
            fb = compose_matte(ib, bx, by, bz, self.ctx.w, self.ctx.h, shadow=shadow)
            f = fb if w >= 1.0 else f * (1.0 - w) + fb * w
        text, a = self.caption(tau)
        if text and a > 0.002:
            ink = get_ink(self.ctx, text.upper(), "eb_regular", self.size, CAPTION_TRACK)
            paint(f, ink, CAPTION_X, CAPTION_BOTTOM - 0.222 * self.cap_px, PICTURE_F, a, shadow=True)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        a = context.get("asset") or {}
        if a.get("w") and a.get("h"):
            cur = context.get("camera") or {}
            w, h = float(a["w"]), float(a["h"])
            cx, cy, z = float(cur.get("cx", w / 2.0)), float(cur.get("cy", h / 2.0)), float(cur.get("zoom") or fit_zoom(h))
            key = lambda rel: {"at": {"rel": rel}, "cx": round(cx, 2), "cy": round(cy, 2), "zoom": round(z, 5), "ease": "linear"}
            d["camera"] = [key(0.0), key(1.0)]
        return d
