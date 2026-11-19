"""KEY-01, NUM-01 and DOC-01: three overlays that make one point visible over a picture (contract
docs/design/2026-11-18-explainer-components.md sections 2 to 5; the approved moving mock-up is
docs/design/mock/2026-11-18-explainer/components.html, functions `labels`, `number` and `doclit`).

    KEY-01  labels as a key to parts of a picture: small text beside each detail, on the word that names it, no box, no line.
    NUM-01  a big number with a comparison: one to four rows (label, figure, units, a count of marks that run out one by one).
    DOC-01  a line of a document that is lit while the rest dims, then its reading in today's words and the line as written.

What they share
  * Times (`at`, `reading_at`, ...) are seconds from the START OF THE OVERLAY; a word anchor in an `at` is the absolute time of that word
    (`registry.at_seconds`). Everything leaves by a fade that ENDS at the end of the overlay (`leave_s`), so an overlay is a closed span.
  * Text is EB Garamond (the bundled files), sized by CAP HEIGHT in percent of the frame height, colour #F1EADB with a soft shadow,
    faded in and out, never boxed, ruled, underlined, slid or grown. Text that follows a camera keeps its size and is drawn at
    sub-pixel positions (quarter pixels), so it moves as smoothly as the picture does.
  * The picture is dimmed by a gain on brightness (a multiplication), never by a box or a flat colour.
  * KEY-01 and DOC-01 take the base shot's camera (`view`): a region name or a pixel point of the shot's picture is mapped to the frame
    with `view.to_screen` and sizes in source pixels are multiplied by `view.z`, as the highlight and annotation overlays do. They are
    valid on every base technique whose renderer provides `view()` (see `NeedsCamera`); the others are refused by validation.
    NUM-01 needs no picture and is valid on every shot.
  * A frame is a pure function of the time. The only state is built once per overlay (and cached by every input it depends on).
"""
from __future__ import annotations

import math
import os
import re

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .. import registry as R
from .. import vfx
from ..base import BaseRenderer, OverlayRenderer, hex_to_bgr
from ..registry import technique

W, H = 1920, 1080

# ---- look (contract section 5, the mock-up)
INK = "#F1EADB"                         # text over pictures
SHADOW_SIGMA, SHADOW_ALPHA, SHADOW_DY = 0.0045 * H, 0.85, 0.002 * H      # the mock-up's `0 .2cqh .9cqh rgba(0,0,0,.85)` (a CSS blur radius is two sigmas)
SUBPX = 4                               # text is drawn at quarter-pixel positions
EDGE_MARGIN = 0.015                     # labels stay this far (share of the frame height) inside the frame
BOX_PAD = 0.006                         # labels keep this much air between them (share of the frame height)


def seg(x, a, d):
    """Linear progress of x over [a, a + d], clamped to 0..1 (a step at a when d <= 0)."""
    if d <= 0:
        return 1.0 if x >= a else 0.0
    return min(1.0, max(0.0, (x - a) / d))


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3.0 - 2.0 * u)


# ----------------------------------------------------------------------------- text
class Art:
    """One line of text, ready to be placed: its metrics and, on demand, its ink coverage at a quarter-pixel offset and its soft shadow.

    `cap_px` is the cap height of the capitals; the font size comes from the real glyph H of the font (`vfx.cap_ratio`). A line wider than
    `max_w` is made smaller (never wrapped). `tracking_em` > 0 sets the letters one by one (small capitals).

    Sub-pixel positions: the line is drawn once at four times the size (the layout and every metric come from that drawing, divided by four) and a
    position that is a multiple of a quarter pixel is made by shifting that drawing by whole pixels of the big one and shrinking it with INTER_AREA. A
    plain text call of Pillow places glyphs on whole pixels, which makes text on a moving camera advance in jumps."""

    SS = 4

    def __init__(self, text: str, kind: str, cap_px: float, tracking_em: float = 0.0, upper: bool = False, max_w: float | None = None):
        self.text = text.upper() if upper else text
        self.kind, self.trk_em = kind, float(tracking_em)
        ratio = vfx.cap_ratio(kind)
        size = max(6, int(round(cap_px / ratio)))
        self._set(size)
        if max_w and self.width > max_w:
            size = max(6, min(size - 1, int(size * max_w / self.width)))
            self._set(size)
            while self.width > max_w and size > 6:
                size -= 1
                self._set(size)
        self.cap = self.size * ratio
        asc, desc = self.ft4.getmetrics()
        self.asc, self.desc = int(math.ceil(asc / self.SS)), int(math.ceil(desc / self.SS))
        self.pad = int(self.size * 0.3) + int(3 * SHADOW_SIGMA) + 3
        self.w = int(math.ceil(self.width)) + 2 * self.pad + 2
        self.h = self.asc + self.desc + 2 * self.pad
        self.base = self.pad + self.asc                  # row of the baseline inside the patch
        self.below = 0.27 * self.size                    # how far descenders hang under the baseline
        self._hi = None
        self._ink: dict = {}
        self._shadow = None

    def _set(self, size: int) -> None:
        self.size = size
        self.ft4 = vfx.font(self.kind, size * self.SS)
        self.trk4 = self.trk_em * size * self.SS
        if self.trk4 > 0:
            self.adv4 = [self.ft4.getlength(c) for c in self.text]
            width4 = sum(self.adv4) + self.trk4 * max(0, len(self.text) - 1)
        else:
            self.adv4, width4 = None, self.ft4.getlength(self.text)
        self.width = float(width4) / self.SS

    def _hires(self) -> np.ndarray:
        if self._hi is None:
            ss = self.SS
            img = Image.new("L", (self.w * ss, self.h * ss), 0)
            d = ImageDraw.Draw(img)
            x0, y0 = self.pad * ss, self.base * ss
            if self.adv4 is None:
                d.text((x0, y0), self.text, font=self.ft4, fill=255, anchor="ls")
            else:
                x = float(x0)
                for c, adv in zip(self.text, self.adv4):
                    d.text((x, y0), c, font=self.ft4, fill=255, anchor="ls")
                    x += adv + self.trk4
            self._hi = np.asarray(img, np.uint8)
        return self._hi

    def ink(self, fx: float, fy: float) -> np.ndarray:
        """uint8 coverage (h x w) of the line with the origin of its baseline moved by (fx, fy) pixels; fx and fy are multiples of 1/SUBPX in [0, 1)."""
        key = (fx, fy)
        a = self._ink.get(key)
        if a is None:
            ss = self.SS
            hi = self._hires()
            dx, dy = int(round(fx * ss)), int(round(fy * ss))
            if dx or dy:
                sh = np.zeros_like(hi)
                sh[dy:, dx:] = hi[:hi.shape[0] - dy, :hi.shape[1] - dx]
                hi = sh
            a = self._ink[key] = cv2.resize(hi, (self.w, self.h), interpolation=cv2.INTER_AREA)
        return a

    def shadow(self) -> np.ndarray:
        """float32 soft shadow (opacity of black) of the whole line, from the ink at whole-pixel position."""
        if self._shadow is None:
            self._shadow = cv2.GaussianBlur(self.ink(0.0, 0.0).astype(np.float32) / 255.0, (0, 0), SHADOW_SIGMA) * SHADOW_ALPHA
        return self._shadow


def art(ctx, text, kind, cap_px, tracking_em=0.0, upper=False, max_w=None) -> Art:
    """Cached `Art` (the key holds every input)."""
    key = ("explain-art", text, kind, round(float(cap_px), 3), round(float(tracking_em), 4), bool(upper), None if max_w is None else round(float(max_w), 1))
    return ctx.cached(key, lambda: Art(text, kind, cap_px, tracking_em, upper, max_w), sizeof=lambda a: a.w * a.h * 22 + 1000)


def draw_text(f, a: Art, left: float, baseline: float, bgr, alpha: float, shadow: bool = True) -> None:
    """Blend line `a` into the float frame `f` with its left edge at `left` and its baseline at `baseline` (frame pixels, fractions allowed)."""
    if alpha <= 0.003 or not a.text:
        return
    ix, iy = int(math.floor(left)), int(math.floor(baseline))
    qx, qy = round((left - ix) * SUBPX), round((baseline - iy) * SUBPX)
    if qx >= SUBPX:
        ix, qx = ix + 1, 0
    if qy >= SUBPX:
        iy, qy = iy + 1, 0
    x0, y0 = ix - a.pad, iy - a.base

    def clip(ox, oy):
        fx0, fy0, fx1, fy1 = max(ox, 0), max(oy, 0), min(ox + a.w, f.shape[1]), min(oy + a.h, f.shape[0])
        if fx1 <= fx0 or fy1 <= fy0:
            return None
        return (fy0, fy1, fx0, fx1), (slice(fy0 - oy, fy1 - oy), slice(fx0 - ox, fx1 - ox))
    if shadow:
        c = clip(x0, y0 + int(round(SHADOW_DY)))
        if c is not None:
            (fy0, fy1, fx0, fx1), sl = c
            roi = f[fy0:fy1, fx0:fx1]
            roi *= (1.0 - a.shadow()[sl] * alpha)[..., None]
    c = clip(x0, y0)
    if c is None:
        return
    (fy0, fy1, fx0, fx1), sl = c
    roi = f[fy0:fy1, fx0:fx1]
    cov = a.ink(qx / SUBPX, qy / SUBPX)[sl].astype(np.float32) * (alpha / 255.0)
    roi += (np.asarray(bgr, np.float32) - roi) * cov[..., None]


_DISCS: dict = {}


def draw_disc(f, cx: float, cy: float, r: float, bgr, alpha: float) -> None:
    """An anti-aliased disc (pixel i covers [i, i + 1))."""
    if alpha <= 0.003 or r <= 0:
        return
    x0, y0 = max(int(math.floor(cx - r - 2)), 0), max(int(math.floor(cy - r - 2)), 0)
    x1, y1 = min(int(math.ceil(cx + r + 2)), f.shape[1]), min(int(math.ceil(cy + r + 2)), f.shape[0])
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    cov = np.clip(r + 0.5 - np.hypot(xx + 0.5 - cx, yy + 0.5 - cy), 0, 1)
    roi = f[y0:y1, x0:x1]
    roi += (np.asarray(bgr, np.float32) - roi) * (cov * alpha)[..., None]


def gain(f, k: float):
    """Multiply the frame by k (in place)."""
    if k < 0.9999:
        f *= np.float32(max(k, 0.0))
    return f


# ----------------------------------------------------------------------------- the camera
class NeedsCamera:
    """Mixin for the overlays that map a picture's regions to the frame (KEY-01, DOC-01). `check_base(base_technique_id)` is called by
    `storyboard.validate` for the base shot an overlay sits on: a base whose renderer does not provide `view()` (cards, diagrams,
    MAP-01, TIME-01 ...) has no camera, so the overlay could not place anything and is refused with `overlay_needs_camera`."""

    @classmethod
    def check_base(cls, base_tid):
        entry = R.RENDERERS.get(base_tid)
        if entry is None:
            return None                                    # an unknown base technique is reported by validate itself
        if getattr(entry[0], "view", None) is BaseRenderer.view:
            return ("overlay_needs_camera", "%s shows no picture through a camera, so an overlay that is placed on a picture cannot sit on it" % base_tid)
        return None


def image_stamp(ctx, key):
    """What identifies the picture of an asset for a cache key: its file and the time it was written (as `Ctx.image` keys its cache). Two projects may both call their
    picture "A"."""
    try:
        path = ctx.asset_path(key)
        return path, os.stat(path).st_mtime_ns
    except Exception:      # noqa: BLE001 - a missing file is reported when the frame is drawn, not here
        return str(key), 0


def regions_of(ctx, view) -> dict:
    a = ctx.asset(view.asset_key) if view.asset_key else {}
    r = a.get("regions") or {}
    return r if isinstance(r, dict) else {}


def anchor_of(ctx, view, ref, min_r: float = 0.0):
    """(sx, sy, rx, ry): where the detail `ref` (region name or [x, y]) is on the frame and the radii of its ellipse in frame pixels."""
    x, y = ctx.point(ref, view.asset_key)
    rx = ry = 0.0
    if isinstance(ref, str):
        reg = regions_of(ctx, view).get(ref) or {}
        rx = float(reg.get("rx") or 0.0)
        ry = float(reg.get("ry") or rx)
        rx = rx or ry
    sx, sy = view.to_screen(x, y)
    return float(sx), float(sy), max(rx * view.z, min_r), max(ry * view.z, min_r)


# ----------------------------------------------------------------------------- KEY-01
SIDES = ("auto", "n", "ne", "e", "se", "s", "sw", "w", "nw")
AUTO_ORDER = ("e", "w", "n", "s", "ne", "nw", "se", "sw")
KIND_OF = {"italic": "eb_italic", "regular": "eb_regular", "caps": "eb_regular"}
CAPS_SHARE, CAPS_TRACK = 0.8, 0.14        # small capitals: 80 percent of the cap height, tracked
LABEL_GAP, POINT_R = 0.013, 0.006         # gap between the ellipse of a detail and its label; the radius given to a bare point (shares of the frame height)
HAIRLINE = "#8D877A"                      # the hairline colour of the contract (section 5)
LEADER_MIN_GAP, LEADER_RADIUS_SHARE = 2.2 * LABEL_GAP, 0.35     # `leader` auto: a label whose box is farther from the edge of its detail than the larger of 2.2 natural gaps and 0.35 of the detail's larger radius gets a line
GROUND_WEIGHT = 0.4                       # cost of the brightness (0..1) of the picture under a label, to prefer the darker one among sides that are equally near


def _hit(a, b, pad=0.0) -> bool:
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])


def ground_level(view, box) -> float:
    """Mean brightness (0 black .. 1 white) of the picture under a screen box, read from the pyramid level that is nearest the screen scale; 0 where the box is off the
    picture (the backdrop is near black)."""
    levels = getattr(view.img, "levels", None)
    if not levels:
        return 0.5
    z = view.z
    k = max(0, min(int(round(math.log2(1.0 / z))) if z < 1 else 0, len(levels) - 1))
    s, a = 2 ** k, levels[k]
    x0, x1 = view.cx + (box[0] - W / 2) / z, view.cx + (box[2] - W / 2) / z
    y0, y1 = view.cy + (box[1] - H / 2) / z, view.cy + (box[3] - H / 2) / z
    ix0, ix1, iy0, iy1 = max(int(x0 / s), 0), min(int(math.ceil(x1 / s)), a.shape[1]), max(int(y0 / s), 0), min(int(math.ceil(y1 / s)), a.shape[0])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    m = a[iy0:iy1:2, ix0:ix1:2].reshape(-1, 3).mean(0)
    return float(0.114 * m[0] + 0.587 * m[1] + 0.299 * m[2]) / 255.0


@technique("KEY-01", "overlay")
class LabelsKey(NeedsCamera, OverlayRenderer):
    """Labels as a key to parts of a picture. Each label sits beside its detail, OUTSIDE the ellipse of its region on the stated side (a bare
    point gets a small radius), appears by a fade at its own time (`at`), follows the camera of the base shot and keeps its size. The picture
    dims to `dim_picture_to` from 0.4 s before the first label (0.6 s ramp) until the overlay's last `leave_s`.

    Placement is the technique's job: with `side` auto each label takes, among e, w, n, s, ne, nw, se, sw (all equally near the detail), the side
    whose box clears the other labels and the frame at seven sample times of the camera (and at the label's own time) and, when several do,
    the one with the darkest picture under the text (`ground_level`, cost GROUND_WEIGHT); the order e, w, n, s ... breaks the remaining ties; a fixed
    `side` is kept. Frame by frame a label is then held inside the frame and pushed along its side's tangent just far enough to leave BOX_PAD of air
    to another label, so labels never touch and never leave the frame (a detail that leaves the frame fades with it).

    `leader`: `none` draws no line; `hairline` a hairline (HAIRLINE colour, 2 px, over a soft dark underlay) from every label to the edge of its detail's
    ellipse; `auto` (the default) only from a label whose detail a viewer could not tell: (a) it is NOT beside its detail, the distance from its box to the ellipse
    (`leader_segment`) being more than max(LEADER_MIN_GAP of the height, LEADER_RADIUS_SHARE of the larger radius), which happens when the solver had to push it
    along its side; or (b) the box lies over, or within half its own distance of, the ellipse of ANOTHER label's detail (`crowded`). The line fades in over the next
    half of the distance (a) or over half the label's own distance (b), so it never pops, and fades with its label."""

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.cap_px = float(p["cap_pct"]) / 100.0 * H
        self.fade = max(0.02, float(p["fade_s"]))
        self.leave = max(0.02, float(p["leave_s"]))
        self.dur = self.t1 - self.t0
        self.labels = []
        for it in p["labels"]:
            style = it.get("style", "italic")
            self.labels.append({"text": str(it["text"]), "ref": it["ref"], "side": it.get("side", "auto"), "style": style,
                                "at": R.at_seconds(it.get("at"), self.t0, 0.0)})
        self.order = sorted(range(len(self.labels)), key=lambda i: (self.labels[i]["at"], i))
        self.arts = []
        for lb in self.labels:
            cap = self.cap_px * (CAPS_SHARE if lb["style"] == "caps" else 1.0)
            self.arts.append(art(ctx, lb["text"], KIND_OF.get(lb["style"], "eb_italic"), cap, CAPS_TRACK if lb["style"] == "caps" else 0.0,
                                 lb["style"] == "caps", 0.8 * W))
        self.first_at = min([lb["at"] for lb in self.labels] or [0.0])
        self.color = hex_to_bgr(INK)
        self._sides = None                                           # decided on the first frame (needs the camera), the same for every frame

    # -- geometry ----------------------------------------------------------------------------------------------
    def box_for(self, side, a: Art, sx, sy, rx, ry):
        """(left, baseline, (x0, y0, x1, y1)) of a label of art `a` on `side` of the ellipse (sx, sy, rx, ry), in frame pixels."""
        g = LABEL_GAP * H
        w, cap, below = a.width, a.cap, a.below
        d = math.sqrt(0.5)
        if side == "e":
            left, base = sx + rx + g, sy + cap / 2
        elif side == "w":
            left, base = sx - rx - g - w, sy + cap / 2
        elif side == "n":
            left, base = sx - w / 2, sy - ry - g - below
        elif side == "s":
            left, base = sx - w / 2, sy + ry + g + cap
        else:
            ex, ey = sx + (rx * d if "e" in side else -rx * d), sy + (ry * d if "s" in side else -ry * d)
            gx = g * d
            left = ex + gx if "e" in side else ex - gx - w
            base = ey + gx + cap if "s" in side else ey - gx - below
        return left, base, (left, base - cap, left + w, base + below)

    def sample_views(self):
        out = []
        times = [self.t0 + self.dur * k / 6.0 for k in range(7)] + [min(self.t1, self.t0 + lb["at"]) for lb in self.labels]
        for t in times:
            v = self.shot_r.view(t)
            if v is not None:
                out.append((t - self.t0, v))
        return out

    def plan(self, view):
        """The side of every label, decided once for the whole overlay (cached by every input; the same for every frame)."""
        if self._sides is None:
            self._sides = self._plan_cached(view)
        return self._sides

    def _plan_cached(self, view):
        samples = self.sample_views()
        regs = regions_of(self.ctx, view)
        sig = repr((view.asset_key, image_stamp(self.ctx, view.asset_key), [(lb["text"], lb["ref"], lb["side"], lb["style"], round(lb["at"], 3)) for lb in self.labels], round(self.cap_px, 2),
                    [(round(tau, 3), round(v.cx, 2), round(v.cy, 2), round(v.z, 6)) for tau, v in samples],
                    sorted((k, regs[k].get("rx"), regs[k].get("ry"), regs[k].get("x"), regs[k].get("y")) for k in regs if any(k == lb["ref"] for lb in self.labels))))
        return self.ctx.cached(("keyplan", sig), lambda: self._plan(samples), sizeof=lambda x: 800)

    def _plan(self, samples):
        ctx = self.ctx
        m = EDGE_MARGIN * H
        geo = {}                                                   # (label, sample) -> anchor
        for i, lb in enumerate(self.labels):
            for s, (tau, v) in enumerate(samples):
                geo[i, s] = anchor_of(ctx, v, lb["ref"], POINT_R * H)
        chosen, placed = {}, {s: [] for s in range(len(samples))}
        for i in self.order:
            lb, a = self.labels[i], self.arts[i]
            cands = AUTO_ORDER if lb["side"] == "auto" else (lb["side"],)
            seen = [s for s, (tau, v) in enumerate(samples) if tau >= lb["at"] - 1e-6 and -0.05 * W <= geo[i, s][0] <= 1.05 * W and -0.05 * H <= geo[i, s][1] <= 1.05 * H]
            best, best_cost = cands[0], None
            for rank, side in enumerate(cands):
                cost = rank * 0.01
                for s, (tau, v) in enumerate(samples):
                    if tau < lb["at"] - 1e-6:
                        continue
                    sx, sy, rx, ry = geo[i, s]
                    if not (-0.05 * W <= sx <= 1.05 * W and -0.05 * H <= sy <= 1.05 * H):
                        continue                                   # the detail is out of the frame at this moment: nothing to place
                    _l, _b, box = self.box_for(side, a, sx, sy, rx, ry)
                    if lb["side"] == "auto" and len(cands) > 1:
                        cost += GROUND_WEIGHT * ground_level(v, box) / max(1, len(seen))       # the darker ground under the text wins among sides that are equally near
                    if box[0] < m or box[2] > W - m or box[1] < m or box[3] > H - m:
                        cost += 4
                    for other in placed[s]:
                        if _hit(box, other, BOX_PAD * H):
                            cost += 10
                    for j, ob in enumerate(self.labels):
                        if j != i and (j, s) in geo:
                            ox, oy, orx, ory = geo[j, s]
                            if _hit(box, (ox - orx, oy - ory, ox + orx, oy + ory)):
                                cost += 0.5                        # covering another detail is a little worse
                if best_cost is None or cost < best_cost - 1e-9:
                    best, best_cost = side, cost
            chosen[i] = best
            for s, (tau, v) in enumerate(samples):
                sx, sy, rx, ry = geo[i, s]
                placed[s].append(self.box_for(best, a, sx, sy, rx, ry)[2])
        return chosen

    def layout(self, view, tau):
        """{label index: (left, baseline, alpha_factor)} for the labels whose time has come, kept inside the frame and apart."""
        sides = self.plan(view)
        m = EDGE_MARGIN * H
        pad = BOX_PAD * H
        out, boxes = {}, {}
        for i in self.order:
            lb, a = self.labels[i], self.arts[i]
            if tau < lb["at"]:
                continue
            sx, sy, rx, ry = anchor_of(self.ctx, view, lb["ref"], POINT_R * H)
            out_d = max(0.0, -sx, sx - W, -sy, sy - H)
            vis = 1.0 - min(1.0, out_d / (0.08 * H))                # a detail that is leaving the frame takes its label with it
            if vis <= 0:
                continue
            side = sides.get(i, "e")
            left, base, _ = self.box_for(side, a, sx, sy, rx, ry)
            left = min(max(left, m), W - m - a.width)
            base = min(max(base, m + a.cap), H - m - a.below)
            boxes[i] = [left, base, vis, side]
        placed = []
        for i in self.order:                                         # the label that came first keeps its place; later ones give way
            if i not in boxes:
                continue
            left, base, vis, side = boxes[i]
            a = self.arts[i]
            for _ in range(3):
                box = (left, base - a.cap, left + a.width, base + a.below)
                hit = next((o for o in placed if _hit(box, o, pad)), None)
                if hit is None:
                    break
                if side in ("n", "s"):                                # along the side: a label above or below its detail slides sideways
                    cx_l, cx_o = (box[0] + box[2]) / 2, (hit[0] + hit[2]) / 2
                    dx = min(box[2], hit[2]) - max(box[0], hit[0]) + pad
                    left += dx if cx_l >= cx_o else -dx
                    left = min(max(left, m), W - m - a.width)
                else:                                                 # a label beside its detail slides up or down
                    cy_l, cy_o = (box[1] + box[3]) / 2, (hit[1] + hit[3]) / 2
                    dy = min(box[3], hit[3]) - max(box[1], hit[1]) + pad
                    base += dy if cy_l >= cy_o else -dy
                    base = min(max(base, m + a.cap), H - m - a.below)
            placed.append((left, base - a.cap, left + a.width, base + a.below))
            out[i] = (left, base, vis)
        return out

    # -- one frame ---------------------------------------------------------------------------------------------
    def apply(self, f, t, view):
        if view is None or not self.labels:
            return f
        tau = t - self.t0
        leave = 1.0 - seg(t, self.t1 - self.leave, self.leave)
        if tau < 0 or leave <= 0:
            return f
        d = seg(tau, max(0.0, self.first_at - 0.4), 0.6) * leave
        gain(f, 1.0 - (1.0 - float(self.p["dim_picture_to"])) * d)
        pos = self.layout(view, tau)
        mode = self.p["leader"]
        anchors = {i: anchor_of(self.ctx, view, self.labels[i]["ref"], POINT_R * H) for i in pos} if mode == "auto" else {}
        for i in self.order:
            if i not in pos:
                continue
            left, base, vis = pos[i]
            al = seg(tau, self.labels[i]["at"], self.fade) * leave * vis
            if al <= 0:
                continue
            a = self.arts[i]
            if mode != "none":
                self.leader(f, view, i, a, left, base, al, mode, anchors)
            draw_text(f, a, left, base, self.color, al, bool(self.p["shadow"]))
        return f

    def leader_segment(self, view, lb, a, left, base):
        """The line a leader would follow: (px, py, ex, ey, gap, threshold), from the point of the label's box that is nearest its detail (px, py) to the edge of the detail's
        ellipse on the line to its centre (ex, ey); `gap` is the distance between the two and `threshold` the gap beyond which `leader` auto draws it. None when the centre of
        the detail lies under the label or the box touches the ellipse."""
        sx, sy, rx, ry = anchor_of(self.ctx, view, lb["ref"], POINT_R * H)
        bx0, by0, bx1, by1 = left, base - a.cap, left + a.width, base + a.below
        px, py = min(max(sx, bx0), bx1), min(max(sy, by0), by1)
        dx, dy = sx - px, sy - py
        n = math.hypot(dx, dy)
        if n < 1:
            return None
        k = 1.0 / math.sqrt((dx / n / rx) ** 2 + (dy / n / ry) ** 2)       # distance from the centre to the ellipse along that ray
        gap = n - k
        if gap <= 0:
            return None
        return px, py, sx - dx / n * k, sy - dy / n * k, gap, max(LEADER_MIN_GAP * H, LEADER_RADIUS_SHARE * max(rx, ry))

    def crowded(self, i, box, gap, anchors) -> float:
        """0..1: the doubt about which detail label `i` belongs to: the box lies over the ellipse of another label's detail (a different `ref`), or within half of its own
        distance `gap` from it (1 over it, 0 at half the gap)."""
        best = 0.0
        for j, (sx, sy, rx, ry) in anchors.items():
            if j == i or self.labels[j]["ref"] == self.labels[i]["ref"]:
                continue
            px, py = min(max(sx, box[0]), box[2]), min(max(sy, box[1]), box[3])
            dx, dy = sx - px, sy - py
            n = math.hypot(dx, dy)
            d = -1.0 if n < 1 else n - 1.0 / math.sqrt((dx / n / rx) ** 2 + (dy / n / ry) ** 2)
            best = max(best, smooth(1.0 - d / (0.5 * gap)))
        return best

    def leader(self, f, view, i, a, left, base, al, mode, anchors) -> None:
        """The line from a label to the edge of its detail: always for `hairline`, for `auto` only from a label that is far from its detail or whose detail is in doubt."""
        lb = self.labels[i]
        seg_ = self.leader_segment(view, lb, a, left, base)
        if seg_ is None:
            return
        px, py, ex, ey, gap, thr = seg_
        if mode == "hairline":
            vis = 1.0
        else:
            vis = max(smooth((gap - thr) / (0.5 * thr)), self.crowded(i, (left, base - a.cap, left + a.width, base + a.below), gap, anchors))
        if vis <= 0:
            return
        n = math.hypot(ex - px, ey - py)
        if n < 6:
            return
        px, py = px + (ex - px) / n * 3.0, py + (ey - py) / n * 3.0               # a little air between the letters and the line
        x0, y0 = int(min(px, ex)) - 4, int(min(py, ey)) - 4
        x1, y1 = int(max(px, ex)) + 5, int(max(py, ey)) + 5
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, f.shape[1]), min(y1, f.shape[0])
        if x1 <= x0 or y1 <= y0:
            return
        p0 = (int(round((px - x0) * 16)), int(round((py - y0) * 16)))
        p1 = (int(round((ex - x0) * 16)), int(round((ey - y0) * 16)))
        roi = f[y0:y1, x0:x1]
        under = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.line(under, p0, p1, 255, 4, cv2.LINE_AA, 4)
        roi *= (1.0 - under.astype(np.float32) * (0.35 * al * vis / 255.0))[..., None]                 # a soft dark underlay keeps the line visible on a bright ground
        line = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.line(line, p0, p1, 255, 2, cv2.LINE_AA, 4)
        roi += (np.asarray(hex_to_bgr(HAIRLINE), np.float32) - roi) * (line.astype(np.float32) * (0.9 * al * vis / 255.0))[..., None]

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        regs = (context.get("asset") or {}).get("regions") or {}
        if regs and any(isinstance(lb["ref"], str) and lb["ref"] not in regs for lb in d["labels"]):
            names = [k for k, r in regs.items() if isinstance(r, dict) and r.get("label")][:5]
            if names:
                d["labels"] = [{"text": str(regs[k]["label"])[:60], "ref": k, "side": "auto", "at": round(0.7 + 0.9 * n, 2), "style": "italic"} for n, k in enumerate(names)]
        return d


# ----------------------------------------------------------------------------- NUM-01
# Sizes of the mock-up (`number`), in percent of the frame height for a figure whose cap height is 8 percent; everything scales with cap_pct / 8.
M_LABEL_CAP, M_LABEL_BASE = 2.35, 3.08          # the row's label (italic): cap height, baseline below the top of the row
M_VALUE_BASE = 15.45                            # the baseline of the figure (and of its units)
M_UNITS_CAP = M_LABEL_CAP                       # units (italic): no smaller than the row's label (the mock-up has them 5 percent smaller, which left them close to invisible at 1280 px)
M_MARK_D, M_MARK_PITCH, M_MARK_Y = 1.5, 3.6, 20.25      # a mark's diameter, the distance between lines of marks, the centre of the first line
M_ROW_H, M_ROW_H_PLAIN, M_ROW_GAP, M_ROW_GAP_MIN = 21.0, 17.0, 9.0, 3.5       # height of a row with / without marks, space between rows (down to the minimum before everything is scaled)
M_CAP_CAP, M_CAP_BASE = 1.9, 90.5                # the caption (italic): cap height and baseline, absolute
SRC_CAP, SRC_BASE = 1.7, 95.3                    # the source line (regular), absolute
MARK_SPACING = 0.0205 * W                        # distance between marks of a line
BAND_TOP, BAND_BOTTOM, BAND_CENTRE = 8.0, 85.0, 53.0     # the rows live between these heights (percent), centred on BAND_CENTRE if they fit
MARGIN_X = 0.08                                  # left (or right) margin of the block, share of the width


@technique("NUM-01", "overlay")
class BigNumber(OverlayRenderer):
    """A big number with a comparison (the mock-up's `number`). The picture dims to `dim_picture_to` (a 0.7 s ramp that ends 0.1 s before the
    first row). Each row: its label (italic) fades in over 0.35 s at `at`, the figure (EB Garamond Medium, cap height `cap_pct`) 0.25 s later
    (0.35 s), the units (italic, as big as the label, 72 percent: the contract's secondary-text level) 0.4 s later; then `count` marks (discs, 92 percent)
    appear one after another, each fading over 0.12 s, spread over `marks_s` (1.1 s) starting 0.6 s after `at`. The caption (70 percent) fades in over
    0.5 s when the first marks start to appear (0.6 s after the `at` of the first row that has marks; 0.75 s after the first row when none has) and stays to
    the end, because it is the line that explains the marks; the source line (75 percent) comes with the first figure. All of it leaves over the last `leave_s`.

    Layout: rows are stacked and centred on the frame (53 percent of the height) from the sizes of the mock-up, which scale with `cap_pct`;
    when they do not fit between 8 and 85 percent of the height the rows come closer (down to 3.5 percent at the mock-up's size) and then everything is made smaller by one factor. `align` right mirrors the block to the right margin."""

    TEXT_ALPHA, UNITS_ALPHA, MARK_ALPHA, CAPTION_ALPHA, SOURCE_ALPHA = 1.0, 0.72, 0.92, 0.7, 0.75

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.leave = max(0.02, float(p["leave_s"]))
        self.marks_s = max(0.05, float(p["marks_s"]))
        self.rows = [{"label": str(r.get("label", "")), "value": str(r["value"]), "units": str(r.get("units", "")), "count": max(0, int(round(float(r.get("count", 0))))),
                      "at": R.at_seconds(r.get("at"), self.t0, 0.0)} for r in p["rows"]]
        self.color = hex_to_bgr(INK)
        self.right = p["align"] == "right"
        self.first_at = min([r["at"] for r in self.rows] or [0.0])
        self.build_layout()

    @staticmethod
    def per_line(count: int) -> int:
        return 20 if count <= 40 else 30

    def build_layout(self) -> None:
        ctx, p = self.ctx, self.p
        m = float(p["cap_pct"]) / 8.0                                # the mock-up's figures are 8 percent high
        heights = []
        for r in self.rows:
            lines = math.ceil(r["count"] / self.per_line(r["count"])) if r["count"] else 0
            heights.append(M_ROW_H_PLAIN if not lines else M_ROW_H + (lines - 1) * M_MARK_PITCH)
        avail = BAND_BOTTOM - BAND_TOP
        gap, n_rows = M_ROW_GAP, len(heights)
        if n_rows > 1 and (sum(heights) + gap * (n_rows - 1)) * m > avail:               # too much: the rows come closer first, down to M_ROW_GAP_MIN, then everything shrinks
            gap = max(M_ROW_GAP_MIN, min(M_ROW_GAP, (avail / m - sum(heights)) / (n_rows - 1)))
        total = sum(heights) + gap * (n_rows - 1)
        s = min(1.0, avail / (total * m)) if total * m > 0 else 1.0
        k = m * s                                                    # percent of the mock-up -> percent of the frame height
        top = min(max(BAND_CENTRE - total * k / 2, BAND_TOP), BAND_BOTTOM - total * k)
        self.scale = k
        x_edge = (1 - MARGIN_X) * W if self.right else MARGIN_X * W
        mark_r = M_MARK_D * k / 100.0 * H / 2.0
        spacing = MARK_SPACING * min(1.0, k)
        ph = H / 100.0
        y = top
        self.lay = []
        for r, hgt in zip(self.rows, heights):
            ar = {
                "label": art(ctx, r["label"], "eb_italic", M_LABEL_CAP * k * ph, 0.0, False, 0.84 * W) if r["label"].strip() else None,
                "value": art(ctx, r["value"], "eb_medium", float(p["cap_pct"]) * s * ph, 0.0, False, 0.84 * W),
                "units": art(ctx, r["units"], "eb_italic", M_UNITS_CAP * k * ph, 0.0, False, 0.5 * W) if r["units"].strip() else None,
            }
            gap_u = 0.6 * float(p["cap_pct"]) * s * ph
            vw = ar["value"].width + (gap_u + ar["units"].width if ar["units"] else 0.0)
            per = self.per_line(r["count"])
            n_first = min(r["count"], per)
            ytop = y * ph
            row = {"ar": ar, "mark_r": mark_r}
            vleft = x_edge - vw if self.right else x_edge
            lleft = x_edge - ar["label"].width if (self.right and ar["label"]) else x_edge
            row["label_pos"] = (lleft, ytop + M_LABEL_BASE * k * ph) if ar["label"] else None
            row["value_pos"] = (vleft, ytop + M_VALUE_BASE * k * ph)
            row["units_pos"] = (vleft + ar["value"].width + gap_u, ytop + M_VALUE_BASE * k * ph) if ar["units"] else None
            x0 = (x_edge - n_first * spacing) if self.right else (x_edge + 0.01 * W)          # the marks are indented a little under the label (mock-up)
            row["marks"] = [(x0 + col * spacing + mark_r, ytop + (M_MARK_Y + line * M_MARK_PITCH) * k * ph)
                            for line, col in (divmod(n, per) for n in range(r["count"]))]
            self.lay.append(row)
            y += (hgt + gap) * k
        starts = [r["at"] + 0.6 for r in self.rows if r["count"]]                  # the caption explains the marks: it comes when the first of them appear
        self.caption_at = min(starts) if starts else (self.first_at + 0.75 if self.rows else 0.0)
        cap_txt, src_txt = str(p["caption"]).strip(), str(p["source"]).strip()
        self.caption = art(ctx, cap_txt, "eb_italic", M_CAP_CAP / 100.0 * H, 0.0, False, 0.84 * W) if cap_txt else None
        self.source = art(ctx, src_txt, "eb_regular", SRC_CAP / 100.0 * H, 0.0, False, 0.84 * W) if src_txt else None
        self.x_edge = x_edge

    def apply(self, f, t, view):
        tau = t - self.t0
        leave = 1.0 - seg(t, self.t1 - self.leave, self.leave)
        if tau < 0 or leave <= 0 or not self.rows:
            return f
        d = seg(tau, max(0.0, self.first_at - 0.8), 0.7) * leave
        gain(f, 1.0 - (1.0 - float(self.p["dim_picture_to"])) * d)
        col = self.color
        for r, ly in zip(self.rows, self.lay):
            a, ar = r["at"], ly["ar"]
            if ly["label_pos"]:
                draw_text(f, ar["label"], *ly["label_pos"], col, seg(tau, a, 0.35) * leave)
            draw_text(f, ar["value"], *ly["value_pos"], col, seg(tau, a + 0.25, 0.35) * leave)
            if ly["units_pos"]:
                draw_text(f, ar["units"], *ly["units_pos"], col, self.UNITS_ALPHA * seg(tau, a + 0.4, 0.35) * leave)
            n = len(ly["marks"])
            if n:
                per = self.marks_s / n
                for i, (cx, cy) in enumerate(ly["marks"]):
                    al = self.MARK_ALPHA * seg(tau, a + 0.6 + i * per, 0.12) * leave
                    if al <= 0:
                        break                                          # marks appear in order: none after this one is there yet
                    draw_disc(f, cx, cy, ly["mark_r"], col, al)
        if self.caption is not None:
            x = self.x_edge - self.caption.width if self.right else self.x_edge
            draw_text(f, self.caption, x, M_CAP_BASE / 100.0 * H, col, self.CAPTION_ALPHA * seg(tau, self.caption_at, 0.5) * leave)
        if self.source is not None:
            x = self.x_edge - self.source.width if self.right else self.x_edge
            draw_text(f, self.source, x, SRC_BASE / 100.0 * H, col, self.SOURCE_ALPHA * seg(tau, self.first_at + 0.25, 0.4) * leave)
        return f

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        return {p["name"]: p["default"] for p in spec["params"]}


# ----------------------------------------------------------------------------- DOC-01
BOX_RE = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*")
READING_CAP, READING_Y = 2.87, 79.76             # the reading (italic): cap height and baseline, percent of the frame height (the mock-up's 4.4cqh at 76 percent)
ORIGINAL_CAP, ORIGINAL_Y = 1.5, 86.5             # the line as written (small capitals, tracked)
ABOVE_SHIFT = 62.0                               # when the text goes above the window instead of below, it moves up by this much
ORIGINAL_ALPHA = 0.7
CORNER_PX = 22                                   # the window's corner radius


def parse_box(s):
    """(x0, y0, x1, y1) from the text `x0, y0, x1, y1` (source pixels); None when it is not four numbers."""
    m = BOX_RE.fullmatch(s) if isinstance(s, str) else None
    return tuple(float(g) for g in m.groups()) if m else None


@technique("DOC-01", "overlay")
class LitLine(NeedsCamera, OverlayRenderer):
    """A line of a document that is lit while everything else dims, with its reading (the mock-up's `doclit`).

    Each `lit` item is a window (a region's ellipse box or `box`, in source pixels, grown by `pad_px` on every side) that follows the base shot's
    camera. Window k rises over `ramp_s` at its `at` and falls over `ramp_s` at `at + hold_s` (hold_s 0: when the next window rises, or never, until
    the overlay leaves), so windows light one after another. Everything outside every window is dimmed to `dim_to`; the gain is 1 inside the window and
    `dim_to` outside, with a soft edge `edge_px` wide centred on the window's border (smoothstep of the signed distance to a rounded rectangle), no outline.
    The reading (italic) fades in at `reading_at` over 0.4 s, the line as written (small capitals, 70 percent) 0.4 s later. The text goes below the
    window (mock-up: baseline of the reading at 79.8 percent of the height) unless the window comes down into that place at some moment of the camera's
    path, then above it. All of it leaves over the last `leave_s`."""

    @classmethod
    def check_params(cls, p: dict):
        out = []
        for i, it in enumerate(p["lit"]):
            box = str(it.get("box") or "").strip()
            has_ref = it.get("ref") not in (None, "", [])
            if box:
                b = parse_box(box)
                if b is None or b[2] <= b[0] or b[3] <= b[1]:
                    out.append(("lit", "doc_bad_box", {"index": i}, "item %d: box must be x0, y0, x1, y1 in source pixels with x1 > x0 and y1 > y0" % (i + 1)))
            elif not has_ref:
                out.append(("lit", "doc_lit_no_target", {"index": i}, "item %d: give a region name in `ref` or a box in source pixels in `box`" % (i + 1)))
        return out

    def __init__(self, tid, ov, shot_r, ctx):
        super().__init__(tid, ov, shot_r, ctx)
        p = self.p
        self.leave = max(0.02, float(p["leave_s"]))
        self.ramp = max(0.02, float(p["ramp_s"]))
        self.dur = self.t1 - self.t0
        wins = sorted(({"ref": it.get("ref"), "box": parse_box(str(it.get("box") or "")), "at": R.at_seconds(it.get("at"), self.t0, 0.0),
                        "hold": float(it.get("hold_s") or 0.0), "i": i} for i, it in enumerate(p["lit"])), key=lambda w: (w["at"], w["i"]))
        for k, w in enumerate(wins):
            if w["hold"] > 0:
                w["end"] = w["at"] + w["hold"]
            elif k + 1 < len(wins):
                w["end"] = max(wins[k + 1]["at"], w["at"] + self.ramp)
            else:
                w["end"] = math.inf
        self.wins = wins
        self.color = hex_to_bgr(INK)
        reading, original = str(p["reading"]).strip(), str(p["original"]).strip()
        self.reading = art(ctx, reading, "eb_italic", READING_CAP / 100.0 * H, 0.0, False, 0.86 * W) if reading else None
        self.original = art(ctx, original, "eb_regular", ORIGINAL_CAP / 100.0 * H, 0.14, True, 0.86 * W) if original else None
        self.reading_at = float(p["reading_at"])
        self._above = None

    # -- the windows ------------------------------------------------------------------------------------------
    def envelopes(self, tau):
        es = [seg(tau, w["at"], self.ramp) * (1.0 - (seg(tau, w["end"], self.ramp) if math.isfinite(w["end"]) else 0.0)) for w in self.wins]
        return es

    def screen_box(self, view, w):
        """(X0, Y0, X1, Y1) of window `w` on the frame, with `pad_px` of room on every side."""
        if w["box"] is not None:
            x0, y0, x1, y1 = w["box"]
        else:
            ref = w["ref"]
            x, y = self.ctx.point(ref, view.asset_key)
            reg = regions_of(self.ctx, view).get(ref) or {} if isinstance(ref, str) else {}
            iw, ih = self.ctx.asset_size(view.asset_key)
            rx = float(reg.get("rx") or 0.0) or (0.07 * iw if not reg.get("ry") else float(reg["ry"]))
            ry = float(reg.get("ry") or 0.0) or (0.02 * iw if not reg.get("rx") else float(reg["rx"]))
            x0, y0, x1, y1 = x - rx, y - ry, x + rx, y + ry
        a, b = view.to_screen(x0, y0), view.to_screen(x1, y1)
        pad = float(self.p["pad_px"])
        return float(a[0]) - pad, float(a[1]) - pad, float(b[0]) + pad, float(b[1]) + pad

    def mask(self, box, x0, y0, x1, y1):
        """Coverage (0 outside, 1 inside) of the rounded rectangle `box` with a soft edge of edge_px, over the pixel window [x0, x1) x [y0, y1)."""
        X0, Y0, X1, Y1 = box
        edge = float(self.p["edge_px"])
        cx, cy, hx, hy = (X0 + X1) / 2, (Y0 + Y1) / 2, max((X1 - X0) / 2, 1.0), max((Y1 - Y0) / 2, 1.0)
        r = min(CORNER_PX, hx, hy)
        xs = (np.arange(x0, x1, dtype=np.float32) + 0.5 - cx)
        ys = (np.arange(y0, y1, dtype=np.float32) + 0.5 - cy)
        qx = np.abs(xs)[None, :] - (hx - r)
        qy = np.abs(ys)[:, None] - (hy - r)
        d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
        if edge <= 0.5:
            return np.clip(0.5 - d, 0, 1)
        u = np.clip(0.5 - d / edge, 0, 1)
        return u * u * (3.0 - 2.0 * u)

    def text_above(self, view) -> bool:
        """Whether the reading goes above the windows: some window comes down into the place of the text at one of the camera's sample moments
        while there is room above (cached for the whole overlay)."""
        if self._above is None:
            self._above = self._above_cached(view)
        return self._above

    def _above_cached(self, view) -> bool:
        samples = []
        for t in [self.t0 + self.dur * k / 6.0 for k in range(7)] + [min(self.t1, self.t0 + w["at"]) for w in self.wins] + [min(self.t1, self.t0 + self.reading_at)]:
            v = self.shot_r.view(t)
            if v is not None:
                samples.append((t - self.t0, v))
        sig = repr((view.asset_key, image_stamp(self.ctx, view.asset_key), [(w["ref"], w["box"], round(w["at"], 3), round(w["end"], 3) if math.isfinite(w["end"]) else None) for w in self.wins], float(self.p["pad_px"]),
                    round(self.reading_at, 3), [(round(tau, 3), round(v.cx, 2), round(v.cy, 2), round(v.z, 6)) for tau, v in samples]))

        def build():
            lowest, highest = 0.0, float(H)
            for tau, v in samples:
                if tau < self.reading_at - 1e-6:
                    continue                                       # the text is not there yet
                for w, e in zip(self.wins, self.envelopes(tau)):
                    if e <= 0:
                        continue
                    X0, Y0, X1, Y1 = self.screen_box(v, w)
                    if X1 < 0 or X0 > W or Y1 < 0 or Y0 > H:
                        continue
                    lowest, highest = max(lowest, Y1), min(highest, Y0)
            below_top = (READING_Y - READING_CAP - 2.0) / 100.0 * H                 # the place of the text under the window
            above_bottom = (ORIGINAL_Y - ABOVE_SHIFT + 1.0) / 100.0 * H + 0.03 * H     # and above it, with some air
            return bool(lowest > below_top and highest > above_bottom)
        return self.ctx.cached(("docplan", sig), build, sizeof=lambda x: 100)

    # -- one frame ---------------------------------------------------------------------------------------------
    def apply(self, f, t, view):
        if view is None or not self.wins:
            return f
        tau = t - self.t0
        leave = 1.0 - seg(t, self.t1 - self.leave, self.leave)
        if tau < 0 or leave <= 0:
            return f
        es = self.envelopes(tau)
        dim_to = float(self.p["dim_to"])
        Dr = min(1.0, sum(es))                  # how far the surroundings are dimmed: the windows share the dimming, so a crossfade between two keeps it complete
        D = Dr * leave
        if D > 0:
            g0 = 1.0 - (1.0 - dim_to) * D
            pad = float(self.p["edge_px"]) / 2 + 2
            rects = []
            for w, e in zip(self.wins, es):
                if e <= 0:
                    continue
                box = self.screen_box(view, w)
                r = (max(int(math.floor(box[0] - pad)), 0), max(int(math.floor(box[1] - pad)), 0),
                     min(int(math.ceil(box[2] + pad)), f.shape[1]), min(int(math.ceil(box[3] + pad)), f.shape[0]))
                if r[2] > r[0] and r[3] > r[1]:
                    rects.append((box, e, r))
            if rects:
                ux0, uy0 = min(x[2][0] for x in rects), min(x[2][1] for x in rects)
                ux1, uy1 = max(x[2][2] for x in rects), max(x[2][3] for x in rects)
                acc = np.zeros((uy1 - uy0, ux1 - ux0), np.float32)
                for box, e, (x0, y0, x1, y1) in rects:
                    acc[y0 - uy0:y1 - uy0, x0 - ux0:x1 - ux0] += self.mask(box, x0, y0, x1, y1) * np.float32(e)
                E = np.minimum(acc, np.float32(Dr)) * np.float32(leave)
                hh, ww = f.shape[:2]                                  # the dimmed surroundings by one gain, the union of the windows by the map: no pixel is multiplied twice
                if g0 < 0.9999:
                    for band in (f[:uy0], f[uy1:], f[uy0:uy1, :ux0], f[uy0:uy1, ux1:]):
                        if band.size:
                            band *= np.float32(g0)
                f[uy0:uy1, ux0:ux1] *= (1.0 - (1.0 - dim_to) * (D - E))[..., None].astype(np.float32)
            else:
                gain(f, g0)
        if self.reading is not None or self.original is not None:
            self.draw_reading(f, view, tau, leave)
        return f

    def draw_reading(self, f, view, tau, leave) -> None:
        shift = -ABOVE_SHIFT if self.text_above(view) else 0.0
        if self.reading is not None:
            a = self.reading
            draw_text(f, a, (W - a.width) / 2, (READING_Y + shift) / 100.0 * H, self.color, seg(tau, self.reading_at, 0.4) * leave)
        if self.original is not None:
            a = self.original
            draw_text(f, a, (W - a.width) / 2, (ORIGINAL_Y + shift) / 100.0 * H, self.color, ORIGINAL_ALPHA * seg(tau, self.reading_at + 0.4, 0.4) * leave)

    @classmethod
    def default_params(cls, tid, spec, context, bundle):
        d = {p["name"]: p["default"] for p in spec["params"]}
        regs = (context.get("asset") or {}).get("regions") or {}
        if regs and any(isinstance(it.get("ref"), str) and it["ref"] not in regs and not it.get("box") for it in d["lit"]):
            wide = sorted((k for k, r in regs.items() if isinstance(r, dict) and r.get("rx") and r.get("ry")), key=lambda k: -(regs[k]["rx"] / regs[k]["ry"]))
            if wide:
                d["lit"] = [dict(d["lit"][0], ref=wide[0])]
        return d
