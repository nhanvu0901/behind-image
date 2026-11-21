"""Checks of what a VIEWER would see in a storyboard that the schema cannot express (worker fixdraft, 2026-11-19).

The first video made end to end with a real model validated with no issue and still needed twenty-one corrections: the whole painting
small between two black bars in 41 of 109 shots, spotlights that dimmed the frame to black or lit a spot outside it, a time axis on
black in the first half minute, pictures that no line of the narration uses, a caption "UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950", a country
label and a sea name that the narration never says. `check` is called at the end of `storyboard.validate`; every issue is a WARNING (a
look the owner would reject, never something that cannot be drawn) with a `code`, an `args` dict, a `hint` (one English sentence that
says what to do) and a `message` (what is wrong, then the hint).

Nothing here renders. The geometry is the camera of the shot (`cx`, `cy`, `zoom`, eased in log space as `vfx.Cam` does), the size of the
picture and the parameters of the technique. The one thing read from disk is a tiny grey-scale copy of a picture, to tell how bright
the frame is under a spotlight: on the seventeen spotlights of the real run it agrees with the luma measured in the exported file to
within 0.6 on the 16..235 scale (docs/qa/FIX_draft_checks.md). A picture that cannot be read only switches that one estimate off.

    check(sb, tm, bundle, project_dir, starts, end_t, safe_rel) -> list of issues
"""
from __future__ import annotations

import math
import re
import threading
from pathlib import Path

from . import limits as L
from .timing import norm
from .vfx import EASE

# ----------------------------------------------------------------------------------------------------------- thresholds
MIN_SHOT_S = 1.5            # the briefings: "none under 1.5 s" (the engine's own error floor, `shot_too_short`, is 0.2 s)
SMALL_COVER = 0.6           # the main painting covers less of the screen than this: it is "small between black bars"
SMALL_SHARE = 0.06          # more than this share of the running time with the painting small raises `upright_whole_share`
SMALL_SHOT_S = 1.0          # a shot counts in the report when the painting is small for at least this long in it
SMALL_MIN_TOTAL_S = 60.0    # a share of the running time means nothing for a clip shorter than this
HI_MARGIN = 0.05            # a lit spot whose centre is nearer the edge of the frame than this share of the frame is "at the edge"
HI_MIN_LUMA = 32.0          # mean luma (16 black .. 235 white) of the frame under a highlight, below which the screen is "almost black"
HI_LOST = 0.75              # ... and the highlight is to blame: the frame keeps less than this share of the brightness it had without it
EARLY_S = 30.0              # no base explanatory component (map, time axis, tree, two-state picture) before this second
TEXT_MISSING_SHARE = 0.25   # a long on-screen sentence may have this share of words the narration does not say
SAMPLE_S = 0.25             # camera sampling step for the share of small frames
GRID_W, GRID_H = 48, 27     # the frame is sampled on this grid to estimate its brightness
LUMA_W = 96                 # width of the grey-scale copy of a picture
LUMA_MAX_PIXELS = 36_000_000  # a picture that is not a JPEG and has more pixels than this is not decoded for the estimate

BASE_EXPLAINERS = ("MAP-", "TIME-", "TREE-", "STATE-")
HIGHLIGHTS = {"HI-01": "floor", "X-HI-01": "surround_floor"}        # technique -> the parameter that says how dark the rest goes

HINTS = {
    "shot_short": "Merge this shot into the one before it or move its cut later so that it lasts at least %.1f seconds." % MIN_SHOT_S,
    "upright_whole_share": ("Keep the whole painting only for the pull back that ends the cold open, for one chapter opening and for the last shot; "
                            "give every other shot a framing that fills the screen (the painting at full width with a slow travel up or down, or a wide band of it)."),
    "highlight_off_frame": "Aim the camera so that the region stays well inside the frame for the whole window of the highlight, or remove the highlight.",
    "highlight_too_dark": ("Remove the highlight when the camera already frames its subject closely; otherwise raise its floor (`floor` for HI-01, `surround_floor` "
                           "for X-HI-01) to about 0.6 so that the rest of the picture stays visible."),
    "caption_placeholder": "Write a caption that comes from the narration or from the picture's own title, or leave it empty; never a placeholder or a note to the reader.",
    "caption_repeats": "Say it once: remove the repeated words from the caption.",
    "text_not_in_narration": ("Show only what the narration says: take the word or figure from the narration, or leave it out (an empty label is better than a guess; "
                              "for MAP-01 also leave `sea_names` off and clear `region_label` when the narration names no sea or country)."),
    "asset_not_in_lines": ("Use a picture that some line of the narration has chosen (step 4), or the main painting; a picture the owner took out of every line "
                           "must not come back."),
    "explainer_early": ("Keep the painting on screen for the first half minute: say the dates as large figures on the picture (STATIC-09) and move the map or "
                        "time axis to a later chapter."),
}


def _issue(code: str, path: str, problem: str, **args) -> dict:
    hint = HINTS[code]
    return {"level": "warn", "path": path, "message": "%s %s" % (problem, hint), "code": code, "args": args, "hint": hint}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def _r(v: float, n: int = 1) -> float:
    return round(float(v), n)


# ----------------------------------------------------------------------------------------------------------- the camera
def camera_at(keys: list, t: float) -> tuple[float, float, float]:
    """(cx, cy, zoom) of resolved keys [(t, cx, cy, zoom, ease)] at `t`: positions linear in the eased progress, zoom in log space."""
    if t <= keys[0][0]:
        return keys[0][1], keys[0][2], keys[0][3]
    for a, b in zip(keys[:-1], keys[1:]):
        if t <= b[0]:
            p = EASE.get(a[4], EASE["linear"])(min(1.0, max(0.0, (t - a[0]) / (b[0] - a[0]))))
            return (a[1] + (b[1] - a[1]) * p, a[2] + (b[2] - a[2]) * p, math.exp(math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * p))
    return keys[-1][1], keys[-1][2], keys[-1][3]


def coverage(cx: float, cy: float, z: float, w: float, h: float) -> float:
    """The share of the 1920x1080 frame that the picture (w x h source pixels) covers under camera (cx, cy, z)."""
    vw, vh = L.CANVAS_W / z, L.CANVAS_H / z
    ow = max(0.0, min(w, cx + vw / 2) - max(0.0, cx - vw / 2))
    oh = max(0.0, min(h, cy + vh / 2) - max(0.0, cy - vh / 2))
    return (ow / vw) * (oh / vh)


# ----------------------------------------------------------------------------------------------------------- the grey copy of a picture
_LUMA: dict = {}
_LUMA_LOCK = threading.Lock()


def luma_map(path: Path):
    """(w, h, rows of 0..255 grey values) of a small copy of the picture at `path`, cached by file version; None when it cannot be read."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_mtime_ns, st.st_size)
    with _LUMA_LOCK:
        if key in _LUMA:
            return _LUMA[key]
    val = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            if im.format != "JPEG" and im.size[0] * im.size[1] > LUMA_MAX_PIXELS:
                return None                              # a huge PNG or TIFF would be decoded whole: the estimate is not worth that (a JPEG is read at 1/8)
            try:
                im.draft("L", (LUMA_W * 2, LUMA_W * 2))
            except Exception:       # noqa: BLE001 - a format that has no draft mode
                pass
            g = im.convert("L")
            w, h = g.size
            gw, gh = LUMA_W, max(1, int(round(LUMA_W * h / float(max(w, 1)))))
            g = g.resize((gw, gh), Image.BOX)
            data = g.tobytes()
            val = (gw, gh, [list(data[r * gw:(r + 1) * gw]) for r in range(gh)])
    except Exception:       # noqa: BLE001 - not an image, too big, a missing library: the estimate is simply off
        val = None
    with _LUMA_LOCK:
        if len(_LUMA) >= 24:
            _LUMA.pop(next(iter(_LUMA)))
        _LUMA[key] = val
    return val


def _smooth(u: float) -> float:
    u = 0.0 if u < 0 else 1.0 if u > 1 else u
    return u * u * (3.0 - 2.0 * u)


def frame_sums(lm, w: float, h: float, cx: float, cy: float, z: float, spot=None) -> tuple[float, float, int]:
    """(lit, dim, n): over a GRID_W x GRID_H sample of the frame, the sum of the picture's grey value times (1 - m) and times m, where m is
    the spotlight mask (0 inside the lit ellipse, 1 outside, smooth between; no `spot`: m is 0 everywhere); outside the picture the grey is 0.
    `spot` = (sx, sy, rxs, rys, feather, rect): screen position and screen radii. The brightness of the frame with the rest dimmed to `floor`
    is (lit + floor * dim) / n."""
    gw, gh, rows = lm
    lit = dim = 0.0
    for gy in range(GRID_H):
        py = (gy + 0.5) * L.CANVAS_H / GRID_H
        y = cy + (py - L.CANVAS_H / 2.0) / z
        if not 0 <= y < h:
            continue
        row = rows[min(gh - 1, int(y / h * gh))]
        for gx in range(GRID_W):
            px = (gx + 0.5) * L.CANVAS_W / GRID_W
            x = cx + (px - L.CANVAS_W / 2.0) / z
            if not 0 <= x < w:
                continue
            v = row[min(gw - 1, int(x / w * gw))]
            if spot is None:
                lit += v
                continue
            sx, sy, rxs, rys, feather, rect = spot
            dx, dy = abs(px - sx) / max(rxs, 1.0), abs(py - sy) / max(rys, 1.0)
            d = max(dx, dy) if rect else math.sqrt(dx * dx + dy * dy)
            m = _smooth((d - (1 - feather * 0.5)) / max(feather, 1e-3))
            lit += v * (1 - m)
            dim += v * m
    return lit, dim, GRID_W * GRID_H


def to_luma(mean_grey: float) -> float:
    """Video luma on the 16..235 scale of a frame whose mean grey value is `mean_grey` (0..255)."""
    return 16.0 + 219.0 / 255.0 * mean_grey


# ----------------------------------------------------------------------------------------------------------- words and numbers
_WORD = re.compile(r"[^\W_]+", re.U)
_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}


def tokens(text: str) -> list[str]:
    """The words of `text`, case and accents folded (the engine's own `norm`)."""
    return [norm(m) for m in _WORD.findall(str(text or ""))]


def numbers_in(toks: list[str]) -> set[int]:
    """The whole numbers that a run of tokens says: digits (`1434`; `1430s` is 1430) and English number words (`twenty three` is 23, `a hundred` is 100,
    `six hundred` is 600, `two thousand` is 2000, `one hundred and five` is 105). Words that do not make one number together (`one two`) are two numbers."""
    out: set[int] = set()
    total = cur = 0
    open_ = False

    def flush():
        nonlocal total, cur, open_
        if open_:
            out.add(total + cur)
        total = cur = 0
        open_ = False

    for t in toks:
        m = re.fullmatch(r"(\d+)s?", t)
        if m:
            flush()
            out.add(int(m.group(1)))
        elif t in _UNITS or t in _TENS:
            v = _UNITS[t] if t in _UNITS else _TENS[t]
            tens = t in _TENS
            if open_ and not (cur % 100 == 0 or (not tens and v < 10 and cur % 100 >= 20 and cur % 10 == 0)):
                flush()                                  # `one two`: a new number, not 3
            cur += v
            open_ = True
        elif t == "hundred":
            if open_ and cur % 100 != 0 and cur >= 10:
                flush()
            cur = (cur or 1) * 100
            open_ = True
        elif t == "thousand":
            total += (cur or 1) * 1000
            cur = 0
            open_ = True
        elif t in ("a", "an", "and", "about", "some") and (not open_ or t == "and"):
            continue
        else:
            flush()
    flush()
    return out


# ----------------------------------------------------------------------------------------------------------- the context
class _Ctx:
    """What every check needs, computed once: spans, specs, camera keys, the main picture, the words of the narration."""

    def __init__(self, sb, tm, bundle, project_dir, starts, end_t, safe_rel):
        self.sb, self.tm, self.bundle, self.project_dir, self.safe_rel = sb, tm, bundle, project_dir, safe_rel
        self.shots = [s if isinstance(s, dict) else {} for s in (sb.get("shots") or [])]
        self.assets = sb.get("assets") if isinstance(sb.get("assets"), dict) else {}
        self.end_t = end_t
        self.spans: list = []
        for i in range(len(self.shots)):
            t0 = starts[i] if i < len(starts) else None
            t1 = starts[i + 1] if i + 1 < len(starts) else end_t
            self.spans.append((t0, t1) if _num(t0) and _num(t1) and t1 > t0 else None)
        self.specs = [bundle.spec(s.get("technique")) if isinstance(s.get("technique"), str) else None for s in self.shots]
        first = next((sp[0] for sp in self.spans if sp), None)
        self.total = (end_t - first) if _num(end_t) and first is not None and end_t > first else 0.0
        self._narr = None
        self._picks = None          # catalogue pass: the project's picks.json and the beats of the timing with their kinds, read when a check of the kinds needs them
        self._beats = None

    # --- shots and pictures
    def sid(self, i: int) -> str:
        return str(self.shots[i].get("id") or "shot %d" % (i + 1))

    def primary(self, i: int):
        slots = self.shots[i].get("slots")
        if not isinstance(slots, dict):
            return None
        img = slots.get("image")
        if isinstance(img, dict) and isinstance(img.get("asset"), str):
            return img["asset"]
        for v in slots.values():
            if isinstance(v, dict) and isinstance(v.get("asset"), str):
                return v["asset"]
        return None

    def size(self, key):
        a = self.assets.get(key)
        if isinstance(a, dict) and _num(a.get("width")) and _num(a.get("height")) and a["width"] > 0 and a["height"] > 0:
            return float(a["width"]), float(a["height"])
        return None

    def keys_of(self, i: int, span, name: str = "camera"):
        """Resolved camera keys [(t, cx, cy, zoom, ease)] of shot i's param `name`, or None when absent or unreadable."""
        raw = (self.shots[i].get("params") or {}).get(name) if isinstance(self.shots[i].get("params"), dict) else None
        if not isinstance(raw, list) or not raw:
            return None
        out = []
        try:
            for k in raw:
                if not (isinstance(k, dict) and isinstance(k.get("at"), dict) and _num(k.get("cx")) and _num(k.get("cy")) and _num(k.get("zoom")) and k["zoom"] > 0):
                    return None
                out.append((self.tm.resolve(k["at"], span[0], span[1]), float(k["cx"]), float(k["cy"]), float(k["zoom"]), k.get("ease") or "linear"))
        except Exception:       # noqa: BLE001 - an unresolvable anchor is the structural checks' business
            return None
        return out if all(b[0] > a[0] for a, b in zip(out, out[1:])) else None

    def has_camera(self, i: int) -> bool:
        spec = self.specs[i]
        return bool(spec and any(p.get("name") == "camera" and p.get("type") == "camera" for p in spec["params"]))

    def main_asset(self):
        """The picture that is on screen the longest as the main image of a shot with a camera."""
        secs: dict = {}
        for i in range(len(self.shots)):
            if self.spans[i] is None or not self.has_camera(i):
                continue
            k = self.primary(i)
            if k is not None:
                secs[k] = secs.get(k, 0.0) + self.spans[i][1] - self.spans[i][0]
        return max(secs, key=secs.get) if secs else None

    # --- the narration
    def narration(self):
        """(set of folded words, set of whole numbers) of everything the voice says; (None, None) when there is no timing."""
        if self._narr is None:
            words = [w.get("w") for w in (getattr(self.tm, "words", None) or []) if isinstance(w, dict) and isinstance(w.get("w"), str)]
            if not words:
                self._narr = (None, None)
            else:
                toks: list[str] = []
                for w in words:
                    toks += tokens(w)
                self._narr = (set(toks), numbers_in(toks))
        return self._narr


# ----------------------------------------------------------------------------------------------------------- 1. a shot that flickers
def _short_shots(c: _Ctx) -> list[dict]:
    out = []
    for i, sp in enumerate(c.spans):
        if sp is None:
            continue
        d = sp[1] - sp[0]
        if 0.2 <= d < MIN_SHOT_S - 1e-6:
            out.append(_issue("shot_short", "shots[%d]" % i, "Shot %s lasts only %.2f seconds: a shot under %.1f seconds flickers." % (c.sid(i), d, MIN_SHOT_S),
                              shot=c.sid(i), min=MIN_SHOT_S, got=_r(d, 2)))
    return out


# ----------------------------------------------------------------------------------------------------------- 2. the painting small between black bars
def _small_painting(c: _Ctx) -> list[dict]:
    main = c.main_asset()
    size = c.size(main) if main else None
    if size is None or c.total < SMALL_MIN_TOTAL_S:
        return []
    per = []                                       # (shot index, seconds with the painting small, smallest cover)
    for i, sp in enumerate(c.spans):
        if sp is None or not c.has_camera(i) or c.primary(i) != main:
            continue
        keys = c.keys_of(i, sp)
        if keys is None:
            continue
        d = sp[1] - sp[0]
        n = max(2, min(240, int(math.ceil(d / SAMPLE_S))))
        small, low = 0.0, 1.0
        for j in range(n):
            cov = coverage(*camera_at(keys, sp[0] + (j + 0.5) * d / n), size[0], size[1])
            low = min(low, cov)
            if cov < SMALL_COVER:
                small += d / n
        if small > 0:
            per.append((i, small, low))
    secs = sum(p[1] for p in per)
    share = secs / c.total
    if share <= SMALL_SHARE:
        return []
    worst = sorted(per, key=lambda p: -p[1])
    count = sum(1 for p in per if p[1] >= SMALL_SHOT_S)
    top = ", ".join("%s (%.1f s)" % (c.sid(p[0]), p[1]) for p in worst[:4])
    title = (c.assets.get(main) or {}).get("title") or main
    return [_issue("upright_whole_share", "shots[%d]" % worst[0][0],
                   "The main painting (%s) is shown small between black bars for %.0f%% of the video (%.0f s in %d shots; the limit is %.0f%%). Worst: %s."
                   % (title, share * 100, secs, count, SMALL_SHARE * 100, top),
                   asset=main, share=_r(share, 3), seconds=_r(secs), count=count, limit=SMALL_SHARE,
                   worst=[{"shot": c.sid(p[0]), "seconds": _r(p[1])} for p in worst[:5]])]


# ----------------------------------------------------------------------------------------------------------- 3. highlights
def _region_xy(asset: dict, at):
    if isinstance(at, str):
        r = (asset.get("regions") or {}).get(at) if isinstance(asset.get("regions"), dict) else None
        if isinstance(r, dict) and _num(r.get("x")) and _num(r.get("y")):
            return float(r["x"]), float(r["y"]), at
        return None
    if isinstance(at, (list, tuple)) and len(at) == 2 and _num(at[0]) and _num(at[1]):
        return float(at[0]), float(at[1]), "[%d, %d]" % (round(at[0]), round(at[1]))
    return None


def _file_of(c: _Ctx, key):
    a = c.assets.get(key)
    if c.project_dir is None or not isinstance(a, dict) or not isinstance(a.get("file"), str) or a.get("kind") not in ("image", None):
        return None
    f = c.safe_rel(c.project_dir, a["file"])
    return f if f is not None and f.is_file() else None


def estimate_highlight(c: _Ctx, key, keys, t: float, spot_xy, rx: float, ry: float, feather: float, rect: bool, floor: float):
    """(luma with the highlight, luma without it, the floor that would give HI_MIN_LUMA or None) at time t; None when the picture cannot be read."""
    size = c.size(key)
    f = _file_of(c, key)
    lm = luma_map(f) if f is not None and size else None
    if lm is None:
        return None
    cx, cy, z = camera_at(keys, t)
    spot = (L.CANVAS_W / 2 + (spot_xy[0] - cx) * z, L.CANVAS_H / 2 + (spot_xy[1] - cy) * z, rx * z, ry * z, feather, rect)
    lit, dim, n = frame_sums(lm, size[0], size[1], cx, cy, z, spot)
    now = to_luma((lit + floor * dim) / n)
    plain = to_luma((lit + dim) / n)
    need = None
    if dim > 0:
        want = ((HI_MIN_LUMA - 16.0) * 255.0 / 219.0 * n - lit) / dim
        need = min(1.0, max(0.0, want)) if want <= 1.0 else None
    return now, plain, need


def _highlights(c: _Ctx) -> list[dict]:
    out = []
    for i, shot in enumerate(c.shots):
        sp = c.spans[i]
        if sp is None or not c.has_camera(i) or not isinstance(shot.get("overlays"), list):
            continue
        key = c.primary(i)
        asset = c.assets.get(key)
        keys = c.keys_of(i, sp) if isinstance(asset, dict) else None
        if keys is None:
            continue
        for j, o in enumerate(shot["overlays"]):
            tid = o.get("technique") if isinstance(o, dict) else None
            if tid not in HIGHLIGHTS or not isinstance(o.get("params"), dict) or not isinstance(o.get("start"), dict):
                continue
            p = {**c.bundle.param_defaults(tid), **o["params"]} if c.bundle.spec(tid) else o["params"]
            where = _region_xy(asset, p.get("at"))
            if where is None or not (_num(p.get("rx")) and _num(p.get("ry"))):
                continue
            try:
                ot0 = c.tm.resolve(o["start"])
                if isinstance(o.get("end"), dict):
                    ot1 = c.tm.resolve(o["end"])
                elif _num(o.get("dur")) and o["dur"] > 0:
                    ot1 = ot0 + float(o["dur"])
                else:
                    ot1 = sp[1]
            except Exception:       # noqa: BLE001
                continue
            ot0, ot1 = max(ot0, sp[0]), min(ot1, sp[1])
            if ot1 <= ot0:
                continue
            path = "shots[%d].overlays[%d]" % (i, j)
            # (a) the lit spot is inside the frame, away from its edge, for the whole window
            bad = None
            for fr in (0.0, 0.25, 0.5, 0.75, 1.0):
                t = ot0 + fr * (ot1 - ot0)
                cx, cy, z = camera_at(keys, t)
                sx, sy = L.CANVAS_W / 2 + (where[0] - cx) * z, L.CANVAS_H / 2 + (where[1] - cy) * z
                if not (L.CANVAS_W * HI_MARGIN <= sx <= L.CANVAS_W * (1 - HI_MARGIN) and L.CANVAS_H * HI_MARGIN <= sy <= L.CANVAS_H * (1 - HI_MARGIN)):
                    bad = (t, sx, sy)
                    break
            if bad is not None:
                out.append(_issue("highlight_off_frame", path,
                                  "The highlight on %s in shot %s (%s) has its lit spot at %.0f%% across and %.0f%% down the frame at %.1f s, at or outside the edge: "
                                  "everything else is dimmed and nothing is lit." % (where[2], c.sid(i), tid, bad[1] / L.CANVAS_W * 100, bad[2] / L.CANVAS_H * 100, bad[0]),
                                  shot=c.sid(i), overlay=o.get("id"), technique=tid, region=where[2], at=_r(bad[0]),
                                  x_pct=_r(bad[1] / L.CANVAS_W * 100, 0), y_pct=_r(bad[2] / L.CANVAS_H * 100, 0)))
                continue
            # (b) the frame under the highlight is not almost black
            floor = p.get(HIGHLIGHTS[tid])
            if not _num(floor):
                continue
            feather = float(p["feather"]) if _num(p.get("feather")) else 0.55
            worst = None
            for fr in (0.4, 0.6, 0.85):
                est = estimate_highlight(c, key, keys, ot0 + fr * (ot1 - ot0), where[:2], float(p["rx"]), float(p["ry"]), feather, p.get("shape") == "rect", float(floor))
                if est is None:
                    worst = None
                    break
                if worst is None or est[0] < worst[0][0]:
                    worst = (est, ot0 + fr * (ot1 - ot0))
            if worst is not None and worst[0][0] < HI_MIN_LUMA and worst[0][0] < HI_LOST * worst[0][1]:
                (now, plain, need), t = worst
                fix = ("a floor of %.2f would do" % (math.ceil(need * 20) / 20.0)) if need is not None and need < 0.95 else "no floor would do, remove it"
                out.append(_issue("highlight_too_dark", path,
                                  "The highlight on %s in shot %s (%s) leaves the frame at a mean brightness of %.0f at %.1f s (%.0f without it; the video's median is about "
                                  "55 and under %.0f looks almost black): %s."
                                  % (where[2], c.sid(i), tid, now, t, plain, HI_MIN_LUMA, fix),
                                  shot=c.sid(i), overlay=o.get("id"), technique=tid, region=where[2], luma=_r(now), luma_without=_r(plain), min=HI_MIN_LUMA,
                                  floor=_r(float(floor), 2), floor_needed=(math.ceil(need * 20) / 20.0) if need is not None and need < 0.95 else None))
    return out


# ----------------------------------------------------------------------------------------------------------- text on the screen
NOT_TEXT = {"id", "via", "holds", "from", "to", "view_start_center", "view_end_center", "box", "ref", "region_iso"}
PLACEHOLDER = re.compile(r"\b(unknown author|anonymous author|lorem ipsum|placeholder|your text here|sample narration|todo|tbd)\b", re.I)
PLACEHOLDER_WHOLE = {"unknown", "anonymous", "untitled", "n/a", "na", "none", "null", "undefined", "nan", "xxx", "test", "example"}
META_WORD = re.compile(r"\b(narration|narrator|voice[- ]?over)\b", re.I)


def _texts(spec: dict, params: dict):
    """Every piece of text a technique's parameters put on the screen: (param, index or None, field or None, text)."""
    defs = {d.get("name"): d for d in spec.get("params") or []}
    for name, v in params.items():
        d = defs.get(name)
        if d is None or name in NOT_TEXT:
            continue
        t = d.get("type")
        if t in ("string", "text") and isinstance(v, str):
            yield name, None, None, v
        elif t == "lines" and isinstance(v, list):
            for k, line in enumerate(v):
                if isinstance(line, str):
                    yield name, k, None, line
        elif t == "items" and isinstance(v, list):
            fdefs = {f.get("name"): f for f in d.get("fields") or []}
            for k, it in enumerate(v):
                if not isinstance(it, dict):
                    continue
                for fname, fv in it.items():
                    if fname not in NOT_TEXT and isinstance(fv, str) and (fdefs.get(fname) or {}).get("type") in ("string", "text"):
                        yield name, k, fname, fv


def _repeated(toks: list[str]):
    """The first run of words that is said twice in a row (`unknown author unknown author`), or None."""
    for n in range(1, 5):
        for i in range(0, len(toks) - 2 * n + 1):
            a, b = toks[i:i + n], toks[i + n:i + 2 * n]
            if a == b and (n >= 2 or (len(a[0]) >= 3 and not a[0].isdigit())):
                return " ".join(a)
    return None


def _items_of(c: _Ctx):
    """Every shot and overlay with a registry spec and its params: (path, shot index, overlay id or None, spec, params, assets of the element)."""
    for i, shot in enumerate(c.shots):
        spec = c.specs[i]
        if spec and isinstance(shot.get("params"), dict):
            yield "shots[%d]" % i, i, None, spec, shot["params"], shot
        for j, o in enumerate(shot.get("overlays") or []):
            if isinstance(o, dict) and isinstance(o.get("params"), dict):
                ospec = c.bundle.spec(o.get("technique")) if isinstance(o.get("technique"), str) else None
                if ospec:
                    yield "shots[%d].overlays[%d]" % (i, j), i, o.get("id"), ospec, o["params"], shot


def _asset_words(c: _Ctx, shot: dict) -> set:
    """The words of the title, artist and year of every picture a shot (or one of its overlays) shows: text taken from the picture itself."""
    keys = set()
    for holder in [shot] + [o for o in shot.get("overlays") or [] if isinstance(o, dict)]:
        for v in (holder.get("slots") or {}).values() if isinstance(holder.get("slots"), dict) else []:
            if isinstance(v, dict) and isinstance(v.get("asset"), str):
                keys.add(v["asset"])
    out: set = set()
    for k in keys:
        a = c.assets.get(k)
        if isinstance(a, dict):
            for f in ("title", "artist", "year"):
                out.update(tokens(a.get(f) if isinstance(a.get(f), str) else str(a.get(f) or "")))
    return out


def _captions(c: _Ctx) -> list[dict]:
    out = []
    for path, i, oid, spec, params, shot in _items_of(c):
        tid = spec.get("id")
        for name, k, field, text in _texts(spec, params):
            if not text.strip():
                continue
            where = name + ("[%d]" % k if k is not None else "") + ("." + field if field else "")
            toks = tokens(text)
            bad = None
            m = PLACEHOLDER.search(text) or META_WORD.search(text)
            if m:
                bad = ("placeholder", m.group(0))
            elif text.strip().lower() in PLACEHOLDER_WHOLE:
                bad = ("placeholder", text.strip())
            if bad:
                out.append(_issue("caption_placeholder", path,
                                  "The text %r of %s in shot %s (%s) is a placeholder or a note to the reader (%r), not something the viewer should read."
                                  % (text[:60], where, c.sid(i), tid, bad[1]), shot=c.sid(i), overlay=oid, technique=tid, param=where, text=text[:80], kind=bad[0]))
                continue
            rep = _repeated(toks)
            if rep:
                out.append(_issue("caption_repeats", path, "The text %r of %s in shot %s (%s) says %r twice in a row." % (text[:60], where, c.sid(i), tid, rep),
                                  shot=c.sid(i), overlay=oid, technique=tid, param=where, text=text[:80], repeated=rep))
        if oid is None and tid == "LAY-01":
            out.extend(_panel_metadata(c, path, i, params, shot))
    return out


def _panel_metadata(c: _Ctx, path: str, i: int, params: dict, shot: dict) -> list[dict]:
    """A `caption_*_sub` of a two-panel shot that is just "artist, year" of the panel's picture, under a caption of the shot's own."""
    out = []
    for side in ("left", "right"):
        key = ((shot.get("slots") or {}).get(side) or {}).get("asset") if isinstance(shot.get("slots"), dict) else None
        a = c.assets.get(key)
        main, sub = params.get("caption_%s" % side), params.get("caption_%s_sub" % side)
        if not (isinstance(a, dict) and isinstance(main, str) and isinstance(sub, str) and main.strip() and sub.strip()):
            continue
        meta = tokens("%s %s" % (a.get("artist") or "", a.get("year") or ""))
        own = set(tokens(a.get("title") or "")) | set(tokens(a.get("artist") or ""))
        if meta and tokens(sub) == meta and not set(tokens(main)) <= own:
            out.append(_issue("caption_placeholder", path,
                              "The small caption %r under %r in shot %s (LAY-01) is only the artist and year of the picture's file, which has nothing to do with %r."
                              % (sub[:60], main[:40], c.sid(i), main[:40]), shot=c.sid(i), overlay=None, technique="LAY-01", param="caption_%s_sub" % side,
                              text=sub[:80], kind="metadata"))
    return out


# --- what the narration must carry: a figure, a place name, a country label, a sea name
def _fact_fields(tid: str, params: dict):
    """(where, text, kind) of the on-screen pieces that state a fact and must come from the narration: kind `figure` (its numbers), `name` (its
    words) or `sentence` (its words, a quarter may be the model's own)."""
    if tid == "MAP-01":
        if isinstance(params.get("region_label"), str):
            yield "region_label", params["region_label"], "name"
        for k, pl in enumerate(params.get("places") or []):
            if isinstance(pl, dict) and isinstance(pl.get("name"), str):
                yield "places[%d].name" % k, pl["name"], "name"
    elif tid == "NUM-01":
        for k, r in enumerate(params.get("rows") or []):
            if isinstance(r, dict) and isinstance(r.get("value"), str):
                yield "rows[%d].value" % k, r["value"], "figure"
        if isinstance(params.get("source"), str):
            yield "source", params["source"], "sentence"
    elif tid == "TIME-01":
        for k, it in enumerate(params.get("items") or []):
            if isinstance(it, dict) and _num(it.get("date")):
                yield "items[%d].date" % k, str(int(it["date"])), "figure"
    elif tid == "STATIC-09":
        if isinstance(params.get("year"), str):
            yield "year", params["year"], "figure"
    elif tid == "DOC-01":
        if isinstance(params.get("reading"), str):
            yield "reading", params["reading"], "sentence"
    elif tid == "TREE-01":
        for k, n in enumerate(params.get("nodes") or []):
            if isinstance(n, dict) and isinstance(n.get("name"), str):
                yield "nodes[%d].name" % k, n["name"], "name"


SEA_WORDS = {"sea", "seas", "ocean", "gulf", "bay", "strait", "straits", "atlantic", "pacific", "mediterranean", "baltic", "adriatic", "aegean", "caribbean"}


def _texts_not_in_narration(c: _Ctx) -> list[dict]:
    words, nums = c.narration()
    if words is None:
        return []
    out = []
    for path, i, oid, spec, params, shot in _items_of(c):
        tid = spec.get("id")
        allowed = None
        for where, text, kind in _fact_fields(tid, params):
            if not text.strip():
                continue
            if allowed is None:
                allowed = _asset_words(c, shot)
            toks = tokens(text)
            if kind == "figure":
                missing = [str(n) for n in sorted(numbers_in(toks)) if n not in nums and str(n) not in allowed]
            else:
                content = [t for t in toks if len(t) > 2 and not t.isdigit()]
                miss = [t for t in content if t not in words and t not in allowed]
                limit = 0 if kind == "name" or len(content) <= 4 else int(len(content) * TEXT_MISSING_SHARE)
                missing = miss if len(miss) > limit else []
                missing += [str(n) for n in sorted(numbers_in(toks)) if n not in nums and str(n) not in allowed]
            if missing:
                out.append(_issue("text_not_in_narration", path,
                                  "Shot %s (%s) shows %r in %s, but the narration never says %s." % (c.sid(i), tid, text[:60], where, ", ".join(repr(m) for m in missing[:4])),
                                  shot=c.sid(i), overlay=oid, technique=tid, param=where, text=text[:80], missing=missing[:6]))
        if tid == "MAP-01" and params.get("sea_names") is True and not (words & SEA_WORDS):
            out.append(_issue("text_not_in_narration", path,
                              "Shot %s (MAP-01) draws sea names (`sea_names` is on), but the narration names no sea or ocean." % c.sid(i),
                              shot=c.sid(i), overlay=oid, technique=tid, param="sea_names", text="sea_names", missing=["sea names"]))
    return out


# ----------------------------------------------------------------------------------------------------------- 6. pictures no line uses
def lines_assets(project_dir) -> set | None:
    """The pictures that some line of the narration has (picks.json of the project) and the main painting; None when there is no picks.json."""
    if project_dir is None:
        return None
    import json
    f = Path(project_dir) / "picks.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("assets"), dict) or not isinstance(doc.get("beats"), dict):
        return None
    out = {doc["main_asset"]} if isinstance(doc.get("main_asset"), str) else set()
    for entry in doc["beats"].values():
        if isinstance(entry, dict) and entry.get("status") != "skip":
            for it in entry.get("items") or []:
                if isinstance(it, dict) and isinstance(it.get("asset"), str):
                    out.add(it["asset"])
    return out


def _unused_pictures(c: _Ctx) -> list[dict]:
    allowed = lines_assets(c.project_dir)
    if allowed is None:
        return []
    used: dict = {}
    for i, shot in enumerate(c.shots):
        for holder in [shot] + [o for o in shot.get("overlays") or [] if isinstance(o, dict)]:
            for v in (holder.get("slots") or {}).values() if isinstance(holder.get("slots"), dict) else []:
                if isinstance(v, dict) and isinstance(v.get("asset"), str) and v["asset"] not in allowed:
                    used.setdefault(v["asset"], [])
                    if i not in used[v["asset"]]:
                        used[v["asset"]].append(i)
    out = []
    for key, idx in used.items():
        a = c.assets.get(key) if isinstance(c.assets.get(key), dict) else {}
        title = a.get("title") or key
        ids = [c.sid(i) for i in idx]
        out.append(_issue("asset_not_in_lines", "shots[%d]" % idx[0],
                          "The picture %r (%s) is used by %d shot(s) (%s) but no line of the narration has it." % (str(title)[:60], key, len(idx), ", ".join(ids[:5])),
                          asset=key, title=str(title)[:80], count=len(idx), shots=ids[:8]))
    return out


# ----------------------------------------------------------------------------------------------------------- 7. an explainer on black as the viewer arrives
def _early_explainer(c: _Ctx) -> list[dict]:
    out = []
    for i, sp in enumerate(c.spans):
        spec = c.specs[i]
        tid = c.shots[i].get("technique")
        if sp is None or spec is None or spec.get("kind") != "base" or not (isinstance(tid, str) and tid.startswith(BASE_EXPLAINERS)):
            continue
        if sp[0] < EARLY_S - 1e-6:
            out.append(_issue("explainer_early", "shots[%d]" % i,
                              "Shot %s (%s) is an explanatory diagram on its own background from %.0f s to %.0f s: the painting leaves the screen in the first %.0f seconds."
                              % (c.sid(i), tid, sp[0], sp[1], EARLY_S), shot=c.sid(i), technique=tid, start=_r(sp[0]), end=_r(sp[1]), limit=EARLY_S))
    return out


# ----------------------------------------------------------------------------------------------------------- catalogue pass: what the kinds of a beat call for
# Worker catalogue, 2026-11-20. The pictures step stores per beat `kinds` (one or two of KINDS) in picks.json; these checks judge a device (and an outside picture) only on beats
# that carry them, so a project made before has none of these warnings. A device that overlaps several beats is judged on all of them: it is wrong only when NONE of them calls for it.
KINDS = ("detail", "whole", "outside", "compare", "journey", "dates", "figure", "inscription", "construction", "relations", "idea")
DEVICE_KINDS = {"MAP-01": ("journey",), "TIME-01": ("dates",), "NUM-01": ("figure",), "DOC-01": ("inscription",), "AN-03": ("construction",), "AN-06": ("construction",),
                "TREE-01": ("relations",), "LAY-01": ("compare",), "X-CMP-01": ("compare",)}
OUTSIDE_ROLES = ("context", "document", "video")            # an outside picture of a beat (a `map` is drawn by MAP-01; a `compare` picture is another work, not the thing the line is about)
NOT_THE_PAINTING_ROLES = OUTSIDE_ROLES + ("compare", "map")  # every picture that is not (a detail of) the main painting
OUTSIDE_ON_PAINTING_SHARE = 0.45        # an outside picture must be on screen for at least this share of a beat that has ONE kind (`outside` alone) ...
OUTSIDE_ON_PAINTING_SHARE_TWO = 0.25    # ... and of a beat that has TWO kinds (`detail`, `outside`): the picture comes when the sentence reaches the thing, after the part about the painting
OUTSIDE_ON_PAINTING_MIN_SECONDS = 3.5   # ... and in both cases for at least this long (a beat shorter than this: the whole of it)
OUTSIDE_SMALL_SHARE = 0.8               # ... and drawn at no less than this share of its default fit
SMALL_PICTURE_PX = 1000                 # a picture whose long side is under this is never enlarged beyond SMALL_PICTURE_MAX_ZOOM
SMALL_PICTURE_MAX_ZOOM = 2.0
OVERLAP_MIN_S = 1.0                     # a device belongs to a beat when they share at least this long (or half of the device, when it is shorter)
MIN_ITEMS = {"MAP-01": ("places", 2), "TIME-01": ("items", 3), "KEY-01": ("labels", 3), "TREE-01": ("nodes", 3)}

HINTS.update({
    "device_wrong_kind": ("Use a device only on a line whose kinds call for it (MAP-01: journey; TIME-01: dates; NUM-01: figure; DOC-01: inscription; AN-03 and AN-06: construction; TREE-01: relations; "
                          "LAY-01 and X-CMP-01: compare). On this line remove it and keep the picture the picks give, with a camera move."),
    "device_too_little": ("Remove the device or give it what it needs: a map needs two places or a route (for one place show the picture of the place), a time axis three dated events (for one year "
                          "use STATIC-09), a key three labels (for one or two use X-ANN-01), a tree three people."),
    "outside_on_painting": ("Show the outside picture of this line for longer (X-LAY-01 for a picture, FOOT-01 for a clip): at least 45% of the line when it has one kind, 25% when it has two (the picture comes "
                            "when the sentence reaches the thing), and never less than 3.5 seconds, instead of the painting."),
    "figure_on_wrong_picture": ("Put the large figure over the picture of the thing counted (the outside picture of this line, as a shot of its own or the base of the figure), not over the painting; "
                                "if the picture was not found, leave the figure out and say the number with the camera move."),
    "outside_picture_small": ("Show the outside picture at its default fit: leave `camera` out (X-LAY-01 fills the frame's height) and write no zoom that leaves it small between black bars; "
                              "a picture whose long side is under 1000 px is never enlarged beyond twice its size."),
})


def _picks_doc(project_dir) -> dict:
    """The project's picks.json as a dict, {} when there is none."""
    if project_dir is None:
        return {}
    import json
    try:
        doc = json.loads((Path(project_dir) / "picks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def outside_asset_keys(picks) -> set:
    """The pictures of a picks document that are not the main painting: those that some line shows as a `context`, `document`, `video`, `compare` or `map` item and
    none shows as `main` or `detail`, and that are not the main asset. The compiler and `outside_picture_small` use it."""
    if not isinstance(picks, dict) or not isinstance(picks.get("beats"), dict):
        return set()
    out, own = set(), set()
    for entry in picks["beats"].values():
        for it in (entry.get("items") if isinstance(entry, dict) else None) or []:
            if isinstance(it, dict) and isinstance(it.get("asset"), str):
                (out if it.get("role") in NOT_THE_PAINTING_ROLES else own).add(it["asset"])
    if isinstance(picks.get("main_asset"), str):
        own.add(picks["main_asset"])
    return out - own


def is_small_picture(w: float, h: float) -> bool:
    return max(w, h) < SMALL_PICTURE_PX


def default_fit_zoom(w: float, h: float) -> float:
    """The zoom at which a w x h picture fills the frame's height or width (whichever it reaches first); a picture whose long side is under 1000 px is held to twice its size."""
    z = min(L.CANVAS_W / float(w), L.CANVAS_H / float(h))
    return min(z, SMALL_PICTURE_MAX_ZOOM) if is_small_picture(w, h) else z


def outside_camera_problem(zooms, w: float, h: float):
    """'small' when the smallest zoom of a camera shows an outside picture under 80% of its default fit, 'large' when it enlarges a small picture beyond twice its size, else None."""
    zs = [float(z) for z in zooms if _num(z) and z > 0]
    if not zs:
        return None
    if min(zs) < OUTSIDE_SMALL_SHARE * default_fit_zoom(w, h) - 1e-9:
        return "small"
    if is_small_picture(w, h) and max(zs) > SMALL_PICTURE_MAX_ZOOM + 1e-9:
        return "large"
    return None


def _beat_rows(c: _Ctx) -> list:
    """[{id, t0, t1, kinds (a list, or None when the beat has none), entry}] for the beats of the timing; [] when no beat has kinds."""
    if c._beats is None:
        c._picks = _picks_doc(c.project_dir)
        pb = c._picks.get("beats") if isinstance(c._picks.get("beats"), dict) else {}
        rows = []
        for b in getattr(c.tm, "beats", None) or []:
            if not (isinstance(b, dict) and isinstance(b.get("id"), str) and _num(b.get("start")) and _num(b.get("end")) and b["end"] > b["start"]):
                continue
            entry = pb.get(b["id"]) if isinstance(pb.get(b["id"]), dict) else {}
            kinds = [k for k in entry.get("kinds") if k in KINDS] if isinstance(entry.get("kinds"), list) else []
            rows.append({"id": b["id"], "t0": float(b["start"]), "t1": float(b["end"]), "kinds": kinds or None, "entry": entry})
        c._beats = rows if any(r["kinds"] for r in rows) else []
    return c._beats


def _judged_beats(c: _Ctx, t0: float, t1: float) -> list:
    """The beats a stretch [t0, t1] belongs to, when every one of them carries kinds; [] (nothing is judged) when one has none or there is no beat."""
    rows = [r for r in _beat_rows(c) if min(t1, r["t1"]) - max(t0, r["t0"]) >= min(OVERLAP_MIN_S, 0.5 * (t1 - t0)) - 1e-9]
    return rows if rows and all(r["kinds"] for r in rows) else []


def _overlay_span(c: _Ctx, o: dict, sp):
    """(start, end) in seconds of an overlay of a shot that spans `sp`, clipped to the shot; None when it cannot be resolved."""
    try:
        t0 = c.tm.resolve(o["start"])
        if isinstance(o.get("end"), dict):
            t1 = c.tm.resolve(o["end"])
        elif _num(o.get("dur")) and o["dur"] > 0:
            t1 = t0 + float(o["dur"])
        else:
            t1 = sp[1]
    except Exception:       # noqa: BLE001
        return None
    t0, t1 = max(t0, sp[0]), min(t1, sp[1])
    return (t0, t1) if t1 > t0 else None


def _device_elements(c: _Ctx):
    """Every shot and overlay that is a device of DEVICE_KINDS or MIN_ITEMS: (path, shot index, element, technique, span)."""
    wanted = set(DEVICE_KINDS) | set(MIN_ITEMS)
    for i, shot in enumerate(c.shots):
        sp = c.spans[i]
        if sp is None:
            continue
        if shot.get("technique") in wanted:
            yield "shots[%d]" % i, i, shot, shot["technique"], sp
        for j, o in enumerate(shot.get("overlays") or []):
            if isinstance(o, dict) and o.get("technique") in wanted and isinstance(o.get("start"), dict):
                osp = _overlay_span(c, o, sp)
                if osp is not None:
                    yield "shots[%d].overlays[%d]" % (i, j), i, o, o["technique"], osp


def _device_kinds(c: _Ctx) -> list[dict]:
    out = []
    for path, i, el, tid, span in _device_elements(c):
        rows = _judged_beats(c, span[0], span[1])
        if not rows:
            continue
        have = sorted({k for r in rows for k in r["kinds"]})
        if tid in DEVICE_KINDS and not any(set(r["kinds"]) & set(DEVICE_KINDS[tid]) for r in rows):
            out.append(_issue("device_wrong_kind", path,
                              "%s in shot %s is drawn on line %s, whose kinds are %s, but it serves only a line of kind %s."
                              % (tid, c.sid(i), ", ".join(r["id"] for r in rows), ", ".join(have), " or ".join(DEVICE_KINDS[tid])),
                              shot=c.sid(i), overlay=el.get("id") if el is not c.shots[i] else None, technique=tid, beats=[r["id"] for r in rows], kinds=have, needs=list(DEVICE_KINDS[tid])))
        if tid in MIN_ITEMS and isinstance(el.get("params"), dict):
            name, need = MIN_ITEMS[tid]
            items = el["params"].get(name)
            n = len([x for x in items if x]) if isinstance(items, list) else None
            if n is not None and n < need and not (tid == "MAP-01" and isinstance(el["params"].get("route"), list) and len(el["params"]["route"]) > 0):
                out.append(_issue("device_too_little", path,
                                  "%s in shot %s has %d %s but needs at least %d%s." % (tid, c.sid(i), n, name, need, " (or a route)" if tid == "MAP-01" else ""),
                                  shot=c.sid(i), overlay=el.get("id") if el is not c.shots[i] else None, technique=tid, count=n, min=need, items=name, beats=[r["id"] for r in rows]))
    return out


def _figure_on_wrong_picture(c: _Ctx) -> list[dict]:
    """A large figure (NUM-01) on a line of kind `figure` whose picks hold the picture of the thing counted (an outside picture), laid over another picture: the owner's first video laid 42 ships over the saint."""
    out = []
    for path, i, el, tid, span in _device_elements(c):
        if tid != "NUM-01":
            continue
        rows = _judged_beats(c, span[0], span[1])
        assets = {it["asset"] for r in rows if "figure" in r["kinds"] and r["entry"].get("status") != "skip" for it in r["entry"].get("items") or []
                  if isinstance(it, dict) and it.get("role") in OUTSIDE_ROLES and isinstance(it.get("asset"), str)}
        key = c.primary(i)
        if assets and key is not None and key not in assets:
            title = (c.assets.get(key) or {}).get("title") or key
            out.append(_issue("figure_on_wrong_picture", path,
                              "The large figure of shot %s is laid over %r, but the picks of line %s hold the picture of the thing counted (%s)."
                              % (c.sid(i), str(title)[:50], ", ".join(r["id"] for r in rows), ", ".join(sorted(assets))),
                              shot=c.sid(i), overlay=el.get("id") if el is not c.shots[i] else None, asset=key, assets=sorted(assets), beats=[r["id"] for r in rows]))
    return out


def outside_needed(kinds: list, dur: float) -> tuple[float, float]:
    """(the share, the seconds) an outside picture must be on screen in a beat of `dur` seconds whose kinds are `kinds`: 45% of a beat that has one kind, 25% of a beat that has two,
    and in both cases at least 3.5 seconds (a beat shorter than that needs the picture for all of it). The two kinds of a line that does two things (`detail`, `outside`) say that the
    picture comes when the sentence reaches the thing, not from its first word."""
    share = OUTSIDE_ON_PAINTING_SHARE if len(kinds) <= 1 else OUTSIDE_ON_PAINTING_SHARE_TWO
    return share, min(dur, max(share * dur, OUTSIDE_ON_PAINTING_MIN_SECONDS))


def _outside_on_painting(c: _Ctx) -> list[dict]:
    out = []
    for r in _beat_rows(c):
        if not r["kinds"] or "outside" not in r["kinds"] or r["entry"].get("status") == "skip":
            continue
        assets = {it["asset"] for it in r["entry"].get("items") or [] if isinstance(it, dict) and it.get("role") in OUTSIDE_ROLES and isinstance(it.get("asset"), str)}
        if not assets:
            continue                                    # the picture was not found (`missing`): the line stays on the detail the picks give
        secs, first = 0.0, None
        for i, shot in enumerate(c.shots):
            sp = c.spans[i]
            if sp is None or max(0.0, min(sp[1], r["t1"]) - max(sp[0], r["t0"])) <= 0:
                continue
            first = i if first is None or sp[0] <= r["t0"] + 1e-6 else first
            slots = shot.get("slots") if isinstance(shot.get("slots"), dict) else {}
            if any(isinstance(v, dict) and v.get("asset") in assets for v in slots.values()):
                secs += min(sp[1], r["t1"]) - max(sp[0], r["t0"])
        dur = r["t1"] - r["t0"]
        share, need = outside_needed(r["kinds"], dur)
        if first is not None and secs < need - 1e-9:
            out.append(_issue("outside_on_painting", "shots[%d]" % first,
                              "Line %s is about something outside the painting and the picks hold a picture of it, but that picture is on screen for only %.1f of the line's %.1f seconds (%.0f%%); "
                              "it needs %.0f%% of the line (%.1f seconds at the least)." % (r["id"], secs, dur, secs / dur * 100, share * 100, need),
                              beat=r["id"], shot=c.sid(first), assets=sorted(assets), seconds=_r(secs), beat_seconds=_r(dur), share=_r(secs / dur, 2), limit=share,
                              min_seconds=OUTSIDE_ON_PAINTING_MIN_SECONDS, needed_seconds=_r(need)))
    return out


def _outside_small(c: _Ctx) -> list[dict]:
    out = []
    if not _beat_rows(c):
        return out
    keys_out = outside_asset_keys(c._picks)
    for i, shot in enumerate(c.shots):
        sp = c.spans[i]
        key = c.primary(i)
        if sp is None or key not in keys_out or not c.has_camera(i) or not _judged_beats(c, sp[0], sp[1]):
            continue
        size = c.size(key)
        raw = (shot.get("params") or {}).get("camera") if isinstance(shot.get("params"), dict) else None
        if size is None or not isinstance(raw, list):
            continue
        zooms = [k.get("zoom") for k in raw if isinstance(k, dict)]
        if outside_camera_problem(zooms, *size) == "small":
            fit = default_fit_zoom(*size)
            lo = min(float(z) for z in zooms if _num(z) and z > 0)
            title = (c.assets.get(key) or {}).get("title") or key
            out.append(_issue("outside_picture_small", "shots[%d]" % i,
                              "Shot %s shows the outside picture %r at a zoom of %.2f, %.0f%% of its default fit (%.2f): it sits small between black bars."
                              % (c.sid(i), str(title)[:50], lo, lo / fit * 100, fit), shot=c.sid(i), asset=key, zoom=round(lo, 3), fit=round(fit, 3), share=_r(lo / fit, 2), limit=OUTSIDE_SMALL_SHARE))
    return out


CATALOGUE_ISSUES = {
    "device_wrong_kind": "A device (MAP-01, TIME-01, NUM-01, DOC-01, AN-03, AN-06, TREE-01, LAY-01, X-CMP-01) on a line whose `kinds` (picks.json) do not call for it (warning). Judged only on lines that carry kinds. args: shot, overlay, technique, beats, kinds, needs.",
    "device_too_little": "A device with too little to show: MAP-01 with fewer than two places and no route, TIME-01 with fewer than three items, KEY-01 with fewer than three labels, TREE-01 with fewer than three people (warning). Judged only on lines that carry kinds. args: shot, overlay, technique, count, min, items, beats.",
    "outside_on_painting": ("A line of kind `outside` whose outside picture (a `context`, `document` or `video` item of its picks) is on screen for less than 45% of the line, or for less than 25% when the line has two kinds "
                            "(the picture comes when the sentence reaches the thing), or in both cases for less than 3.5 seconds (the whole line when it is shorter) (warning). "
                            "args: beat, shot, assets, seconds, beat_seconds, share, limit (the share this line needs), min_seconds, needed_seconds."),
    "figure_on_wrong_picture": "A large figure (NUM-01) on a line of kind `figure` whose picks hold the picture of the thing counted, laid over another picture (warning). Judged only on lines that carry kinds. args: shot, overlay, asset, assets, beats.",
    "outside_picture_small": "An outside picture drawn smaller than 80% of its default fit (the frame's height or width; a picture under 1000 px is held to twice its size) (warning). Judged only on lines that carry kinds. args: shot, asset, zoom, fit, share, limit.",
}


# ----------------------------------------------------------------------------------------------------------- entry
def check(sb: dict, tm, bundle, project_dir, starts: list, end_t, safe_rel) -> list[dict]:
    """The viewer checks of a storyboard whose shots start at `starts` (seconds, None when unresolvable) and end at `end_t`. Never raises."""
    try:
        c = _Ctx(sb, tm, bundle, project_dir, starts, end_t, safe_rel)
    except Exception:       # noqa: BLE001
        return []
    out: list[dict] = []
    for fn in (_short_shots, _small_painting, _highlights, _captions, _texts_not_in_narration, _unused_pictures, _early_explainer,
               _device_kinds, _figure_on_wrong_picture, _outside_on_painting, _outside_small):         # the last four: catalogue pass, silent on beats without kinds
        try:
            out.extend(fn(c))
        except Exception:       # noqa: BLE001 - a structure the structural checks already report: say nothing more
            continue
    try:                                                          # panelbox: the camera stays inside the painted area of the main painting
        out.extend(_frame_off_painting(c))
    except Exception:       # noqa: BLE001
        pass
    return out


CODES = {
    "shot_short": "A shot lasts less than 1.5 s (warning): it flickers. args: shot, min, got.",
    "upright_whole_share": "The main painting covers less than 60% of the screen (small between black bars) for more than 6% of the running time (warning). args: asset, share, seconds, count, limit, worst ([{shot, seconds}]).",
    "highlight_off_frame": "The lit spot of a spotlight (HI-01, X-HI-01) is at the edge of the frame or outside it during its window (warning). args: shot, overlay, technique, region, at (seconds), x_pct, y_pct.",
    "highlight_too_dark": "A spotlight leaves the frame at a mean luma under 32 on the 16..235 scale (warning). args: shot, overlay, technique, region, luma, luma_without, min, floor, floor_needed.",
    "caption_placeholder": "On-screen text that is a placeholder, a note to the reader (it says `narration`) or only the artist and year of a picture's file under a caption of the shot's own (warning). args: shot, overlay, technique, param, text, kind (placeholder|metadata).",
    "caption_repeats": "On-screen text that says the same words twice in a row (warning). args: shot, overlay, technique, param, text, repeated.",
    "text_not_in_narration": "A map label, place or sea name, a figure, a date or a name on the screen that the narration never says (warning). args: shot, overlay, technique, param, text, missing.",
    "asset_not_in_lines": "A shot shows a picture that no line of the narration has (picks.json) and that is not the main painting (warning). args: asset, title, count, shots.",
    "explainer_early": "A base explanatory component (MAP-01, TIME-01, TREE-01, STATE-01) starts in the first 30 seconds (warning). args: shot, technique, start, end, limit.",
}
CODES.update(CATALOGUE_ISSUES)       # catalogue pass: the four checks of what the kinds of a beat call for (their sentences: `CATALOGUE_SENTENCES` of errmsg.js)


# ----------------------------------------------------------------------------------------------------------- panelbox: the camera stays on the painted surface
# Worker panelbox, 2026-11-20. A museum photograph of a panel has a black ground round the painting (`content_box` of the asset, bti/media/contentbox.py); the first test video
# let the camera of about a dozen shots go past the edge of the painting and a black band stood at one side of the frame. A camera KEY of a shot on the main painting must show at
# most OFF_LIMIT (1%) of its frame outside the painted area (`contentbox.outside_share`), unless the frame holds the whole painting (a pull-back: the matte round the painting is by
# design) or is, along an axis, a quarter wider than the painting or more and holds it there (a narrow painting in a wide frame: bars at both sides are the look). Between two keys
# that are inside the box the camera is inside it too (the corners of the frame move on a concave and a convex curve), so the keys are the whole check.
HINTS["frame_off_painting"] = ("Keep every camera key inside the painted area of the main painting (`content_box` of the asset): move the centre away from the edge, or zoom in; "
                               "a frame that shows the whole painting is the only one that may show the ground round it.")


def _main_painting(c: _Ctx):
    """The key of the main painting: the project's (`main_asset` of picks.json) when the storyboard has it, else the picture on screen the longest."""
    key = _picks_doc(c.project_dir).get("main_asset") if c.project_dir is not None else None
    return key if isinstance(key, str) and isinstance(c.assets.get(key), dict) else c.main_asset()


def _frame_off_painting(c: _Ctx) -> list[dict]:
    from bti.media import contentbox as CB
    main = _main_painting(c)
    asset = c.assets.get(main) if main else None
    box = CB.box_of(asset, c.project_dir) if isinstance(asset, dict) else None
    if box is None:
        return []
    out = []
    for i, shot in enumerate(c.shots):
        if c.spans[i] is None or not c.has_camera(i) or c.primary(i) != main:
            continue
        raw = (shot.get("params") or {}).get("camera") if isinstance(shot.get("params"), dict) else None
        worst = None
        for n, k in enumerate(raw if isinstance(raw, list) else []):
            if not (isinstance(k, dict) and all(_num(k.get(f)) for f in ("cx", "cy", "zoom")) and k["zoom"] > 0):
                continue
            share = CB.outside_share(box, float(k["cx"]), float(k["cy"]), float(k["zoom"]))
            if share > CB.OFF_LIMIT and (worst is None or share > worst[0]):
                worst = (share, n, k)
        if worst is None:
            continue
        share, n, k = worst
        title = (asset.get("title") or main)
        out.append(_issue("frame_off_painting", "shots[%d].params.camera[%d]" % (i, n),
                          "Camera key %d of shot %s (centre %.0f, %.0f at zoom %.3g) shows %.0f%% of the frame outside the painted area of the main painting (%s: x %d to %d, y %d to %d): "
                          "a band of the photograph's ground or of the matte stands at a side of the frame."
                          % (n + 1, c.sid(i), k["cx"], k["cy"], k["zoom"], share * 100, str(title)[:40], box[0], box[2], box[1], box[3]),
                          shot=c.sid(i), asset=main, key=n, share=_r(share, 3), limit=CB.OFF_LIMIT, box=[int(round(v)) for v in box],
                          cx=_r(k["cx"], 0), cy=_r(k["cy"], 0), zoom=round(float(k["zoom"]), 4)))
    return out


# panelbox (2026-11-20): the camera stays inside the painted area of the main painting (`_frame_off_painting`)
CODES["frame_off_painting"] = ("A camera key of a shot on the main painting shows more than 1% of its frame outside the painted area of the main painting (`content_box` of the asset, "
                               "bti/media/contentbox.py), judged along the axes where the frame is not a pull-back round the painting, and does not hold the whole painting (warning). args: shot, asset, key (0-based), share, limit, box [x0, y0, x1, y1], cx, cy, zoom.")
