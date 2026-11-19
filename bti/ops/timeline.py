"""Time on the storyboard: anchors, shot spans, camera keys and overlay spans.

A Python port of the pure editing logic of the page (`bti/editor/static/js/logic.js` and `edit.js`: `anchorFromTime`,
`cropCamera`, `rescaleRel`, `derive`, `fitOverlay`), so that `split_shot`, `merge_shots` and `move_boundary` leave a storyboard
exactly as the same edit by hand does. Times are seconds. A span is `(t0, t1)`; either can be None when an anchor cannot be
resolved (the engine's validation reports that; an operation then refuses to guess).
"""
from __future__ import annotations

import copy
import math
from typing import Any

from bti.engine.timing import AnchorError, Timing
from bti.engine.vfx import EASE

MIN_SHOT = 0.2          # a shot is never shorter (the engine's MIN_SHOT_S)
MIN_OV = 0.1            # an overlay is never shorter when the page fits it into a shot
SNAP_S = 0.35           # how far a time reaches for a word start (the page's SNAP_S)


def jround(v: float, n: int = 3) -> float:
    """JavaScript's `Math.round(v * 10**n) / 10**n` (halves go up), so a port gives the page's numbers."""
    k = 10 ** n
    return math.floor(v * k + 0.5) / k


def clamp(v: float, a: float, b: float) -> float:
    return min(b, max(a, v))


def clean_word(w: Any) -> str:
    s = str(w if w is not None else "")
    kept = "".join(c for c in s if c.isalnum() or c in "'-")
    return kept or s


def fmt_time(t: float | None) -> str | None:
    """`m:ss` (or `h:mm:ss` from one hour) for a time in seconds; None when there is none."""
    if t is None:
        return None
    s = max(0, int(t))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def camera_lists(params: Any) -> list[tuple[str, list]]:
    """Every camera key list inside a params object: `[(name, keys)]` (a technique may hold several)."""
    out = []
    for name, v in (params or {}).items():
        if isinstance(v, list) and v and all(isinstance(k, dict) and isinstance(k.get("at"), dict) and "zoom" in k for k in v):
            out.append((name, v))
    return out


class Timeline:
    """The words of a project's timing and what can be asked of them."""

    def __init__(self, timing: Timing):
        self.tm = timing
        self.words = timing.words

    # ---------------------------------------------------------------- anchors
    def resolve(self, a: Any, t0: float | None = None, t1: float | None = None) -> float | None:
        if not isinstance(a, dict):
            return None
        try:
            return float(self.tm.resolve(a, t0, t1))
        except (AnchorError, KeyError, TypeError, ValueError, IndexError):
            return None

    def spans(self, doc: dict) -> list[tuple[float | None, float | None]]:
        """The `(t0, t1)` of every shot, like `engine.storyboard.resolve`: a shot ends where the next one starts, the last at `end`."""
        shots = [s for s in doc.get("shots") or []]
        end = doc.get("end")
        end_t = self.resolve(end) if isinstance(end, dict) and end else None
        starts = [self.resolve(s.get("start")) if isinstance(s, dict) else None for s in shots]
        return [(starts[i], starts[i + 1] if i + 1 < len(shots) else end_t) for i in range(len(shots))]

    def nearest_word(self, t: float) -> tuple[int, float, float] | None:
        """`(index, start, distance)` of the word start nearest to `t` (the one at or before, or the next), None without words."""
        words = self.words
        if not words:
            return None
        lo, hi, last = 0, len(words) - 1, -1
        while lo <= hi:
            mid = (lo + hi) // 2
            if float(words[mid]["s"]) <= t:
                last, lo = mid, mid + 1
            else:
                hi = mid - 1
        cands = [k for k in (last, last + 1) if 0 <= k < len(words)]
        best = cands[0]
        for k in cands:
            if abs(float(words[k]["s"]) - t) < abs(float(words[best]["s"]) - t):
                best = k
        st = float(words[best]["s"])
        return best, st, abs(st - t)

    def anchor_from_time(self, t: float, snap: bool = True, max_dist: float = SNAP_S) -> dict:
        """The page's `anchorFromTime`: a word anchor when a word starts within `max_dist` of `t`, else a free `{t}`."""
        t = jround(max(0.0, t), 3)
        if not snap or not self.words:
            return {"t": t}
        n = self.nearest_word(t)
        if n is None or n[2] > max_dist:
            return {"t": t}
        return {"w": n[0], "off": 0, "text": clean_word(self.words[n[0]]["w"])}

    def parse_anchor(self, a: Any) -> tuple[dict | None, str | None]:
        """A user-given anchor, cleaned: `({t} | {w, off, text}, None)` or `(None, problem)`."""
        if not isinstance(a, dict):
            return None, "must be an anchor object such as {\"t\": 12.5} or {\"w\": 31}"
        if "t" in a:
            if not is_num(a["t"]) or a["t"] < 0:
                return None, "t must be a number of seconds, 0 or more"
            return {"t": float(a["t"])}, None
        if "w" in a:
            w = a["w"]
            if isinstance(w, bool) or not isinstance(w, (int, float)) or not float(w).is_integer():
                return None, "w must be a word index (a whole number)"
            w = int(w)
            if not 0 <= w < len(self.words):
                return None, "w is a word index from 0 to %d" % (len(self.words) - 1)
            off = a.get("off", 0)
            if not is_num(off):
                return None, "off must be a number of seconds"
            word = self.words[w]["w"]
            text = a.get("text")
            if text is None:
                text = clean_word(word)
            elif not isinstance(text, str) or clean_word(text).lower() != clean_word(word).lower():
                return None, "text %r is not the word at index %d (%r)" % (str(text)[:30], w, str(word)[:30])
            return {"w": w, "off": float(off) if off else 0, "text": text}, None
        return None, "an anchor needs t (seconds) or w (a word index)"

    def anchor_for(self, v: Any, snap: bool = True) -> tuple[dict | None, str | None]:
        """A number of seconds (snapped to a word start within SNAP_S when `snap`) or an anchor object, as an anchor."""
        if is_num(v):
            if v < 0:
                return None, "must be 0 seconds or more"
            return self.anchor_from_time(float(v), snap), None
        return self.parse_anchor(v)

    # ---------------------------------------------------------------- overlays
    def overlay_span(self, o: dict, t0: float, t1: float) -> tuple[float, float]:
        """`derive`'s span of an overlay, clamped into its shot."""
        a = self.resolve(o.get("start"))
        ot0 = a if a is not None else t0
        if is_num(o.get("dur")):
            ot1 = ot0 + float(o["dur"])
        elif isinstance(o.get("end"), dict):
            e = self.resolve(o["end"])
            ot1 = e if e is not None else t1
        else:
            ot1 = t1
        ot0 = clamp(ot0, t0, t1)
        ot1 = clamp(ot1, ot0, t1)
        return ot0, ot1

    def fit_overlay(self, o: dict, lo: float, hi: float, span: tuple[float, float]) -> None:
        """The page's `fitOverlay`: keep overlay `o` (whose span is `span`) inside [lo, hi]: shift it in when it starts early,
        shorten it when it ends late."""
        o0, o1 = span
        length = o1 - o0
        s, e = o0, o1
        if s < lo:
            s = lo
            e = min(lo + length, hi)
        if s > hi - MIN_OV:
            s = max(lo, hi - max(MIN_OV, min(length, hi - lo)))
        e = clamp(min(e, hi), s + MIN_OV, max(hi, s + MIN_OV))
        runs_to_end = not is_num(o.get("dur")) and not o.get("end")
        moved = abs(s - o0) > 1e-6
        if moved:
            free = not (isinstance(o.get("start"), dict) and isinstance(o["start"].get("w"), (int, float)))
            a = self.anchor_from_time(s, snap=not free)
            at = a["t"] if "t" in a else float(self.words[a["w"]]["s"])
            if at < lo - 1e-6 or at > hi - MIN_OV + 1e-6:
                a = {"t": jround(s, 3)}
            o["start"] = a
        if not runs_to_end or e < o1 - 1e-6 or moved:
            st = o["start"]
            if "t" in st:
                start_t = float(st["t"])
            elif st.get("w") is not None:
                start_t = float(self.words[st["w"]]["s"]) + float(st.get("off") or 0)
            else:
                start_t = s
            if runs_to_end and e >= hi - 1e-6:
                pass                                        # it still runs to the end of the shot
            else:
                o.pop("end", None)
                o["dur"] = jround(max(MIN_OV, e - (start_t if moved else o0)), 3)

    def fit_overlays(self, overlays: list, lo: float, hi: float, shot_t0: float, shot_t1: float, source: str) -> list[dict]:
        """`fitOverlays` over the overlays of one shot (whose span is [shot_t0, shot_t1] before the change); returns the overlays
        that were changed."""
        changed = []
        for o in overlays:
            span = self.overlay_span(o, shot_t0, shot_t1)
            if span[0] < lo - 1e-6 or span[1] > hi + 1e-6 or span[0] > hi - MIN_OV:
                self.fit_overlay(o, lo, hi, span)
                o["source"] = source
                changed.append(o)
        return changed

    # ---------------------------------------------------------------- camera keys
    def _points(self, keys: list, t0: float, t1: float) -> list[tuple[dict, float]]:
        out = []
        for k in keys:
            t = self.resolve(k.get("at"), t0, t1)
            if t is not None:
                out.append((k, t))
        return out

    @staticmethod
    def _pose_at(pts: list[tuple[dict, float]], t: float) -> dict:
        def pose(k):
            return {"cx": k["cx"], "cy": k["cy"], "zoom": k["zoom"]}
        if t <= pts[0][1]:
            return pose(pts[0][0])
        for (a, ta), (b, tb) in zip(pts, pts[1:]):
            if t <= tb:
                span = (tb - ta) or 1e-9
                fn = EASE.get(a.get("ease"), EASE["linear"])
                e = fn(clamp((t - ta) / span, 0.0, 1.0))
                return {"cx": a["cx"] + (b["cx"] - a["cx"]) * e, "cy": a["cy"] + (b["cy"] - a["cy"]) * e,
                        "zoom": math.exp(math.log(a["zoom"]) + (math.log(b["zoom"]) - math.log(a["zoom"])) * e)}
        return pose(pts[-1][0])

    def pose_at_start(self, keys: list, t0: float, t1: float) -> dict | None:
        """The camera pose of a key list at the start of its shot (what a new camera technique continues from)."""
        pts = self._points(keys, t0, t1)
        return self._pose_at(pts, t0) if pts else None

    def crop_camera(self, keys: list, ta: float, tb: float, t0: float, t1: float) -> list:
        """The page's `cropCamera`: re-express a camera key list over the sub-range [ta, tb] of a shot that spans [t0, t1]. rel
        anchors are rescaled to stay at the same absolute time, word and time anchors are kept, and the poses at both cuts are
        interpolated like the engine does, so the picture is continuous across a cut."""
        pts = self._points(keys, t0, t1)
        if not pts:
            return copy.deepcopy(keys)

        def re(k: dict, kt: float) -> dict:
            c = copy.deepcopy(k)
            if isinstance(c["at"].get("rel"), (int, float)):
                c["at"] = {"rel": jround(clamp((kt - ta) / (tb - ta), 0.0, 1.0), 4)}
            return c
        inside = [(k, kt) for k, kt in pts if ta + 1e-6 < kt < tb - 1e-6]
        p0, p1 = self._pose_at(pts, ta), self._pose_at(pts, tb)
        before = [k for k, kt in pts if kt <= ta + 1e-6]
        after = next((k for k, kt in pts if kt >= tb - 1e-6), None)
        first = {"at": {"rel": 0}, "cx": jround(p0["cx"], 2), "cy": jround(p0["cy"], 2), "zoom": jround(p0["zoom"], 5),
                 "ease": (before[-1].get("ease") if before else None) or "linear"}
        last = {"at": {"rel": 1}, "cx": jround(p1["cx"], 2), "cy": jround(p1["cy"], 2), "zoom": jround(p1["zoom"], 5),
                "ease": (after.get("ease") if after else None) or "linear"}
        return [first] + [re(k, kt) for k, kt in inside] + [last]

    @staticmethod
    def rescale_rel(keys: list, old_dur: float, new_dur: float) -> list:
        """After a shot got longer, keep every camera pose at the same absolute time: rel anchors shrink, the last pose is held."""
        f = old_dur / new_dur
        out = []
        for k in keys:
            c = copy.deepcopy(k)
            if isinstance(c.get("at"), dict) and isinstance(c["at"].get("rel"), (int, float)):
                c["at"] = {"rel": jround(c["at"]["rel"] * f, 4)}
            out.append(c)
        return out
