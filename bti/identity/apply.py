"""Apply a channel identity style to a storyboard: ONE deterministic function, no model, no network, no clock.

    apply_identity(storyboard, style_id, style, timing, meta=None, *, defaults=None, project_dir=None) -> (storyboard, report)

Contract: docs/design/2026-11-18-identity-raking-light.md section 6. In short, for the chosen style:
  1. the opening: the `ID-OPEN-*` and `ID-LABEL-*` overlays of every unlocked shot are removed and the style's own are put on the
     shot that is on screen at their nominal start (at least 3 s long: the start moves earlier inside the shot, else it is skipped);
  2. the title slot (the first `X-CARD-02` / `ID-BRAND-*` structure shot) becomes the style's channel-name beat, on the picture of
     the shot before it at that shot's last camera key, with a 3 % push. When the beat's technique has the params `title` and `subtitle`
     (`ID-BRAND-03`) they are written too: `title` is the video's title (`identity.video_title` of the storyboard) and `subtitle` the
     painting's title and the artist and year; without a video title `title` is the painting's title and `subtitle` the artist and year;
  3. every chapter card (`X-CARD-01`, `TXT-01`, `ID-MARK-*` structure shot) becomes the style's chapter mark "N. Title" on the
     picture of the next non-structure shot, with a camera that ENDS exactly on that shot's first camera key (start 4 % wider);
  4. id, start, intent, note and `locked` of a shot are kept; a locked shot is not changed and is listed in the report;
  5. the same style twice gives the same document, byte for byte; raking, dim, raking gives what raking alone gives.

`style` is the style.json document (its `identity` block is read, see `config.py`), `timing` a `Timing` or the dict of its
`words` and `duration`, `meta` the project's `title`, `artist`, `year` and `main_asset` (an asset key), all optional. `defaults(id)`
gives the registry defaults of a technique (`StyleBundle.param_defaults`): the params of what is written are then complete, the way the
draft compiler stores every shot and overlay, so that a later edit that rebuilds a shot does not "change" them. The input is
never changed. `report` is `{"style", "changed": [shot ids], "skipped": [{"shot", "reason", "what", "message"}]}`; the reasons
are `locked`, `no_title_slot`, `extra_title`, `no_title`, `too_short`, `no_room`, `no_time`.
"""
from __future__ import annotations

import copy
import json
import math

from bti.engine.limits import CAMERA_ZOOM_MAX
from bti.engine.timing import AnchorError, Timing
from bti.media import contentbox as CB          # panelbox: the painted area of the main painting

from . import config as C
from . import titles as T

MIN_OVERLAY_S = 3.0         # an opening overlay is never shorter unless the style's nominal length is itself shorter
OPEN_MIN_S = 0.5            # shortest duration of a scaled short-opening sweep (style `raking`, `lead` >= 1.2 s)
OPEN_HOLD_S = 0.30          # painting stays 100 % lit this long on s0000 after ID-OPEN-01 ends (+ 0.35 s before first word >= 0.65 s)
LABEL_MIN_S = 0.5           # shortest duration of one piece of a cross-cut label
LABEL_FIRST_NOMINAL_S = 1.5 # keeps the half-second fade-in smooth on a short opening shot
MIN_ELEMENT_S = 1.5         # a channel-name beat or a chapter mark is never shorter (section 3); the block's `min_element_s` wins
BRAND_PUSH = 1.03           # the picture under the channel name drifts in by 3 % over the beat
BRAND_SWEEP_PUSH = 1.08     # gentle continuous push-in over ID-BRAND-04
WHOLE_PUSH = 1.03           # the same for a mark that has no picture of its own to flow into
MARK_WIDER = 1.04           # a mark starts 4 % wider than the shot it flows into
FILL_COVER_MIN = 1.0 - CB.OFF_LIMIT   # >= 99% screen coverage on both axes (a frame that fills the screen)
STRIP_TECHNIQUES = frozenset({"X-ANN-01", "X-ANN-02"})
EPS = 1e-9

# The nominal timeline of the opening (contract section 3): (start second in the video, length). The block's own `nominal` numbers
# win (style.json: since the opening shot the opening is 0 to 3.6 s and the label 1.2 to 5.0 s); these older numbers are used only when it
# has none for a role. A style with neither starts at 0 and lasts 6 s.
NOMINAL = {
    "raking": {"open": (0.0, 9.0), "label": (6.2, 4.5)},
    "dim": {"open": (7.0, 5.0)},
}
DEFAULT_NOMINAL = (0.0, 6.0)

REASONS = {
    "locked": "the shot is locked, so it was not changed",
    "no_title_slot": "the video has no title slot (no title card) to turn into the channel-name beat",
    "extra_title": "a second title card was left as it is (only the first one becomes the channel-name beat)",
    "no_title": "the card has no title text",
    "too_short": "the shot is too short (under 1.5 s) for the new style",
    "no_room": "no shot is long enough (%.0f s) for the opening at its place" % MIN_OVERLAY_S,
    "no_time": "the start of the shot cannot be read from the timing",
}


# ----------------------------------------------------------------------------------------------------------- small helpers
def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def _ceil4(x: float) -> float:
    return math.ceil(x * 1e4 - 1e-7) / 1e4


def _floor3(x: float) -> float:
    return math.floor(x * 1e3 + 1e-7) / 1e3


def _floor6(x: float) -> float:
    return math.floor(max(0.0, x) * 1e6 + 1e-9) / 1e6


def _strip(obj):
    """Deep copy without the derived `_` keys."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return copy.deepcopy(obj)


def _timing(t) -> Timing:
    if isinstance(t, Timing):
        return t
    if isinstance(t, dict):
        return Timing({"duration": t.get("duration", 0.0), "words": t.get("words") or []})
    return Timing({"duration": 0.0, "words": []})


def _key(rel, cx, cy, zoom, ease="linear") -> dict:
    return {"at": {"rel": rel}, "cx": cx, "cy": cy, "zoom": zoom, "ease": ease}


def _clamp_zoom(z: float) -> float:
    return min(float(z), float(CAMERA_ZOOM_MAX))


def _tail(sid) -> int:
    digits = ""
    for ch in reversed(str(sid)):
        if not ch.isdigit():
            break
        digits = ch + digits
    return int(digits) if digits else 0


def _after(doc: dict, anchor: str, key: str, value) -> dict:
    """`doc` with `key` set; when it is new it goes right after `anchor` (so that the document reads in a fixed order)."""
    if key in doc:
        out = dict(doc)
        out[key] = value
        return out
    out = {}
    placed = False
    for k, v in doc.items():
        out[k] = v
        if k == anchor:
            out[key] = value
            placed = True
    if not placed:
        out[key] = value
    return out


class _Applier:
    def __init__(self, storyboard, style_id, style, timing, meta, defaults=None, project_dir=None):
        self.cfg = C.need(style)
        self.sd = self.cfg.style(style_id)
        if self.sd is None:
            raise C.IdentityError("unknown_style", "unknown style %r (choose one of: %s)" % (style_id, ", ".join(self.cfg.ids())),
                                  style=style_id, allowed=self.cfg.ids())
        self.style_id = style_id
        self.tm = _timing(timing)
        self.meta = meta if isinstance(meta, dict) else {}
        self._defaults = defaults
        self.project_dir = project_dir
        self._boxes: dict[str, tuple | None] = {}
        self._picks: dict | None = None
        self._timing_raw: dict | None = None
        self.sb = _strip(storyboard)
        shots = self.sb.get("shots")
        self.shots = shots if isinstance(shots, list) else []
        self.assets = self.sb.get("assets") if isinstance(self.sb.get("assets"), dict) else {}
        self.skipped: list = []
        self._skipped_keys: set = set()
        self.before = [_canon(s) for s in self.shots]
        self._resolve_times()
        self._text: dict | None = None

    # ------------------------------------------------------------------------------------------------------- times
    def _resolve_times(self):
        t0 = []
        for s in self.shots:
            try:
                t0.append(self.tm.resolve(s["start"]) if isinstance(s, dict) and isinstance(s.get("start"), dict) else None)
            except (AnchorError, KeyError, TypeError):
                t0.append(None)
        end = None
        try:
            if isinstance(self.sb.get("end"), dict):
                end = self.tm.resolve(self.sb["end"])
        except AnchorError:
            end = None
        self.t0 = t0
        self.t1 = []
        for i in range(len(self.shots)):
            nxt = next((t0[j] for j in range(i + 1, len(self.shots)) if t0[j] is not None), end)
            self.t1.append(nxt)

    def length(self, i):
        a, b = self.t0[i], self.t1[i]
        return None if a is None or b is None else b - a

    # ------------------------------------------------------------------------------------------------------- report
    def skip(self, i, reason, what, extra: str = ""):
        sid = self.shots[i].get("id") if i is not None and isinstance(self.shots[i], dict) else None
        key = (sid, reason, what)
        if key in self._skipped_keys:
            return
        self._skipped_keys.add(key)
        self.skipped.append({"shot": sid, "reason": reason, "what": what, "message": REASONS[reason] + (" (%s)" % extra if extra else "")})

    def defaults(self, tid) -> dict:
        if self._defaults is None:
            return {}
        try:
            d = self._defaults(tid)
        except Exception:               # noqa: BLE001 - a technique the registry does not know has no defaults to write
            return {}
        return copy.deepcopy(d) if isinstance(d, dict) else {}

    # ------------------------------------------------------------------------------------------------------- kinds
    @staticmethod
    def structure(s) -> bool:
        return isinstance(s, dict) and s.get("intent") == "structure"

    def is_title_slot(self, s) -> bool:
        t = s.get("technique")
        return self.structure(s) and (t in C.LEGACY_TITLE or self.cfg.is_family(t, "brand"))

    def is_chapter_card(self, s) -> bool:
        t = s.get("technique")
        return self.structure(s) and (t in C.LEGACY_MARKS or self.cfg.is_family(t, "mark"))

    # ------------------------------------------------------------------------------------------------------- pictures
    def image_asset(self, key) -> dict | None:
        a = self.assets.get(key) if isinstance(key, str) else None
        return a if isinstance(a, dict) and a.get("kind") in (None, "image") else None

    def main_asset(self) -> str | None:
        k = self.meta.get("main_asset")
        if self.image_asset(k):
            return k
        for s in self.shots:
            if isinstance(s, dict) and not self.structure(s):
                slots = s.get("slots") if isinstance(s.get("slots"), dict) else {}
                a = (slots.get("image") or {}).get("asset") if isinstance(slots.get("image"), dict) else None
                if self.image_asset(a):
                    return a
        return next((k for k in self.assets if self.image_asset(k)), None)

    def box_of(self, key) -> tuple | None:
        """panelbox: the painted area `(x0, y0, x1, y1)` of the main painting (`CB.box_of(asset, project_dir)`) when `key` is the main painting."""
        if not isinstance(key, str) or key != self.main_asset():
            return None
        if key not in self._boxes:
            a = self.image_asset(key)
            self._boxes[key] = CB.box_of(a, self.project_dir) if a is not None else None
        return self._boxes[key]

    def in_box(self, key, keys):
        """panelbox: camera keys written for the picture `key`, each moved or tightened (`fit_camera_to_box`) when it shows more than 1% of its frame
        outside the painted area of the main painting and does not hold the whole of it; the keys of any other picture, and keys inside, come back unchanged."""
        if not keys or key != self.main_asset():
            return keys
        box = self.box_of(key)
        if box is None:
            return keys
        fitted, _ = fit_camera_to_box(self.image_asset(key), keys, self.project_dir, box=box)
        return fitted

    def whole_keys(self, key) -> list | None:
        """The whole picture, fitted the way the matte shots fit it (painting height = `fit_pct` of the frame), with a 3 % push. The painting is the painted area of the
        picture (`content_box`) when it has one: the box is fitted and centred, not the black ground round it."""
        a = self.image_asset(key)
        if not a or not (_num(a.get("width")) and _num(a.get("height")) and a["width"] > 0 and a["height"] > 0):
            return None
        w, h = float(a["width"]), float(a["height"])
        box = self.box_of(key) or (0.0, 0.0, w, h)
        z = self.cfg.fit_pct / 100.0 * 1080.0 / (box[3] - box[1])
        cx, cy = round((box[0] + box[2]) / 2, 2), round((box[1] + box[3]) / 2, 2)
        return [_key(0.0, cx, cy, round(_clamp_zoom(z), 5)), _key(1.0, cx, cy, round(_clamp_zoom(z * WHOLE_PUSH), 5))]

    def _paint_box(self, key) -> tuple[float, float, float, float] | None:
        """Painted area `(x0, y0, x1, y1)` of `key`: `content_box` if available, else the full stored image bounds."""
        box = self.box_of(key)
        if box is not None:
            return box
        a = self.image_asset(key)
        if not a or not (_num(a.get("width")) and _num(a.get("height")) and a["width"] > 0 and a["height"] > 0):
            return None
        return (0.0, 0.0, float(a["width"]), float(a["height"]))

    @staticmethod
    def _cover_zoom(box: tuple[float, float, float, float]) -> float:
        """Minimum zoom at which a 1920x1080 frame fits completely inside `box` (width-filling for upright paintings)."""
        bw = max(box[2] - box[0], 1.0)
        bh = max(box[3] - box[1], 1.0)
        return math.ceil(max(1920.0 / bw, 1080.0 / bh) * 1e5 - 1e-9) / 1e5

    def _fills_screen(self, key, cam_key: dict) -> bool:
        """True when `cam_key` on `key` fills at least `FILL_COVER_MIN` of the 1920x1080 frame on both axes."""
        box = self._paint_box(key)
        if box is None or not isinstance(cam_key, dict):
            return False
        if not (_num(cam_key.get("cx")) and _num(cam_key.get("cy")) and _num(cam_key.get("zoom")) and cam_key["zoom"] > 0):
            return False
        cx, cy, z = float(cam_key["cx"]), float(cam_key["cy"]), float(cam_key["zoom"])
        vw, vh = 1920.0 / z, 1080.0 / z
        fx0, fy0, fx1, fy1 = cx - vw / 2.0, cy - vh / 2.0, cx + vw / 2.0, cy + vh / 2.0
        cov_w = max(0.0, min(box[2], fx1) - max(box[0], fx0)) / vw
        cov_h = max(0.0, min(box[3], fy1) - max(box[1], fy0)) / vh
        return cov_w >= FILL_COVER_MIN - 1e-6 and cov_h >= FILL_COVER_MIN - 1e-6

    @staticmethod
    def _clamp_fill_pose(box: tuple[float, float, float, float], cx: float, cy: float, z: float) -> tuple[float, float, float]:
        """Clamp `(cx, cy, z)` so the 1920x1080 frame stays wholly inside `box` and fills the screen."""
        z = _clamp_zoom(max(float(z), _Applier._cover_zoom(box)))
        hw, hh = 960.0 / z, 540.0 / z

        def _clamp_axis(c: float, lo: float, hi: float) -> float:
            lo2 = math.ceil(lo * 100.0 - 1e-9) / 100.0
            hi2 = math.floor(hi * 100.0 + 1e-9) / 100.0
            if lo2 > hi2:
                return round((lo + hi) / 2.0, 2)
            return min(max(round(float(c), 2), lo2), hi2)

        return (_clamp_axis(cx, box[0] + hw, box[2] - hw), _clamp_axis(cy, box[1] + hh, box[3] - hh), round(z, 5))

    def filling_band_keys(self, key, target_xy: tuple[float, float] | None = None, *,
                          push: float = WHOLE_PUSH, shift_frac: float = 0.0, ease: str = "linear") -> list | None:
        """A width-filling (screen-filling) band of `key` centred near `target_xy` (or painting centre) with a gentle push."""
        box = self._paint_box(key)
        if box is None:
            return None
        tx, ty = target_xy if target_xy is not None else ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
        cx0, cy0, z0 = self._clamp_fill_pose(box, tx, ty, self._cover_zoom(box))
        z1_raw = _clamp_zoom(z0 * push)
        cx1, cy1, z1 = self._clamp_fill_pose(box, cx0 + (tx - cx0) * shift_frac, cy0 + (ty - cy0) * shift_frac, z1_raw)
        return [_key(0.0, cx0, cy0, z0, ease=ease), _key(1.0, cx1, cy1, z1)]

    def camera_of(self, s) -> tuple | None:
        """(asset key, camera keys) of a shot that looks at one picture through a camera, else None."""
        if not isinstance(s, dict) or self.structure(s):
            return None
        slots = s.get("slots") if isinstance(s.get("slots"), dict) else {}
        img = slots.get("image") if isinstance(slots.get("image"), dict) else None
        key = img.get("asset") if img else None
        params = s.get("params") if isinstance(s.get("params"), dict) else {}
        cam = params.get("camera")
        if not (self.image_asset(key) and isinstance(cam, list) and cam):
            return None
        for k in cam:
            if not (isinstance(k, dict) and _num(k.get("cx")) and _num(k.get("cy")) and _num(k.get("zoom")) and k["zoom"] > 0):
                return None
        return key, cam

    def neighbour(self, i, step) -> dict | None:
        j = i + step
        while 0 <= j < len(self.shots):
            s = self.shots[j]
            if isinstance(s, dict) and not self.structure(s):
                return s
            j += step
        return None

    # ------------------------------------------------------------------------------------------------------- text
    def texts(self) -> dict:
        """The words of the opening: `title`, the label's second line (`artist_year`) and the small-capitals line (`sub`).
        From the old title card when the video has one; else from what an earlier application wrote (an opening overlay of either
        style, so that a second application gives the same words and an owner's edit of them is kept); else from the project."""
        meta = self.meta
        main = self.image_asset(self.main_asset()) or {}

        def text(v):
            return T.one_line(v) if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""

        def person(raw, *fallbacks):
            raw = text(raw)
            known = [text(f) for f in fallbacks if text(f)]
            if not raw:
                return known[0] if known else ""
            if T.is_shouting(raw):                      # a card in capitals: the project's own spelling when it is the same name
                return next((k for k in known if k.casefold() == raw.casefold()), None) or T.name_case(raw)
            return raw

        def lines(artist, year):
            return T.artist_year(artist, year), T.small_caps_line(artist, year)

        card = next((s for s in self.shots if isinstance(s, dict) and self.structure(s) and s.get("technique") in C.LEGACY_TITLE), None)
        if card is not None and isinstance(card.get("params"), dict) and text(card["params"].get("title")):
            p = card["params"]
            artist, year = person(p.get("artist"), meta.get("artist"), main.get("artist")), person(p.get("year"), meta.get("year"), main.get("year"))
            label, sub = lines(artist, year)
            return {"title": T.pretty(text(p.get("title"))), "artist_year": label, "sub": sub}
        for s in self.shots:
            for o in (s.get("overlays") if isinstance(s, dict) and isinstance(s.get("overlays"), list) else []):
                if not isinstance(o, dict) or not isinstance(o.get("params"), dict) or not text(o["params"].get("title")):
                    continue
                p, tech = o["params"], o.get("technique")
                if self.cfg.is_family(tech, "label") and "artist_year" in p:
                    line = text(p.get("artist_year"))
                    head, sep, tail = line.rpartition(", ")
                    return {"title": text(p["title"]), "artist_year": line, "sub": T.small_caps_line(head, tail) if sep else T.small_caps_line(line, "")}
                if self.cfg.is_family(tech, "open") and "sub" in p:
                    sub = text(p.get("sub"))
                    a, _, y = sub.partition(" · ")
                    artist, year = person(a, meta.get("artist"), main.get("artist")), person(y, meta.get("year"), main.get("year"))
                    label, _ = lines(artist, year)
                    return {"title": text(p["title"]), "artist_year": label, "sub": sub}
        title = T.pretty(text(meta.get("title"))) or T.pretty(text(self.sb.get("title"))) or T.pretty(text(main.get("title")))
        label, sub = lines(person("", meta.get("artist"), main.get("artist")), person("", meta.get("year"), main.get("year")))
        return {"title": title, "artist_year": label, "sub": sub}

    # ------------------------------------------------------------------------------------------------------- 1. opening
    def nominal(self, role) -> tuple:
        base = NOMINAL.get(self.style_id, {}).get(role, DEFAULT_NOMINAL)
        return self.sd.start_s.get(role, base[0]), self.sd.dur_s.get(role, base[1])

    def opening(self):
        cfg = self.cfg
        text = self._text if self._text is not None else self.texts()       # computed before the old overlays go: their words are one of the sources
        for i, s in enumerate(self.shots):
            if not isinstance(s, dict) or not isinstance(s.get("overlays"), list):
                continue
            mine = [o for o in s["overlays"] if isinstance(o, dict) and (cfg.is_family(o.get("technique"), "open") or cfg.is_family(o.get("technique"), "label"))]
            if not mine:
                continue
            if s.get("locked"):
                self.skip(i, "locked", "opening")
                continue
            drop = {id(o) for o in mine}
            s["overlays"] = [o for o in s["overlays"] if id(o) not in drop]
        for role in ("open", "label"):
            tech = self.sd.technique(role)
            if not tech:
                continue
            if role == "label" and self.sd.cross_cut.get("label"):
                self.add_label_span(role, tech, text)
            else:
                self.add_overlay(role, tech, text)

    def overlay_params(self, role, text) -> dict:
        writes_text = role == "label" or (role == "open" and not self.sd.label_role)
        if not writes_text:
            return {}
        if role == "label":
            return {"title": text["title"], "artist_year": text["artist_year"]}
        return {"title": text["title"], "sub": text["sub"]}

    def _next_overlay_id(self, overlays: list) -> str:
        n = max([_tail(o.get("id")) for o in overlays if isinstance(o, dict)] + [0]) + 1
        return "o%d" % n

    def _strip_cutoff(self, shot: dict, s0: float, s1: float, a: float, win_end: float) -> float:
        """Earliest time in [a, win_end) where a name strip starts or already plays on `shot`."""
        cut = win_end
        for o in shot.get("overlays") or []:
            if not isinstance(o, dict) or o.get("technique") not in STRIP_TECHNIQUES:
                continue
            try:
                st0 = self.tm.resolve(o["start"]) if isinstance(o.get("start"), dict) else None
            except (AnchorError, KeyError, TypeError):
                st0 = None
            if st0 is None:
                continue
            if isinstance(o.get("end"), dict):
                try:
                    st1 = self.tm.resolve(o["end"])
                except (AnchorError, KeyError, TypeError):
                    st1 = s1
            elif _num(o.get("dur")):
                st1 = st0 + float(o["dur"])
            else:
                st1 = s1
            if st0 <= a + EPS < st1:
                cut = min(cut, a)
            elif a < st0 < cut:
                cut = min(cut, st0)
        return cut

    def add_label_span(self, role: str, tech: str, text: dict):
        """Place the opening label from its nominal start to nominal end, crossing shot cuts seamlessly without blinking and stopping when a strip arrives."""
        start_nom, length_nom = self.nominal(role)
        win_start, win_end = start_nom, start_nom + length_nom
        idx = [i for i in range(len(self.shots)) if self.t0[i] is not None and self.t1[i] is not None and isinstance(self.shots[i], dict)]
        if not idx:
            self.skip(None, "no_time", role)
            return
        i0 = next((k for k in reversed(idx) if self.t0[k] <= win_start + EPS), idx[0])
        if self.structure(self.shots[i0]):
            earlier = [k for k in idx if k < i0 and not self.structure(self.shots[k])]
            if earlier:
                i0 = earlier[-1]
                win_start = max(self.t0[i0], self.t1[i0] - length_nom)
                win_end = min(self.t1[i0], win_start + length_nom)
        if self.shots[i0].get("locked"):
            self.skip(i0, "locked", role)
            return
        slices: list[tuple[int, float, float]] = []
        for i in range(i0, len(self.shots)):
            if self.t0[i] is None or self.t1[i] is None or not isinstance(self.shots[i], dict):
                continue
            s0, s1 = self.t0[i], self.t1[i]
            if s0 >= win_end - EPS:
                break
            if self.structure(self.shots[i]):
                break
            if i > i0 and self.shots[i].get("locked"):
                self.skip(i, "locked", role)
                break
            a = max(win_start, s0)
            win_end = self._strip_cutoff(self.shots[i], s0, s1, a, win_end)
            b = min(win_end, s1)
            if b - a < LABEL_MIN_S - EPS:
                if not slices:
                    a = max(s0, b - LABEL_MIN_S)
                if b - a < LABEL_MIN_S - 1e-6:
                    if not slices:
                        self.skip(i, "no_room", role)
                        return
                    break
            slices.append((i, a, b))
        if not slices:
            self.skip(i0, "no_room", role)
            return
        base_params = {**self.defaults(tech), **self.overlay_params(role, text)}
        base_nom = float(base_params.get("nominal_s") or 4.5)
        for k, (i, a, b) in enumerate(slices):
            s = self.shots[i]
            s0, s1 = self.t0[i], self.t1[i]
            if not isinstance(s.get("overlays"), list):
                s["overlays"] = []
            anchor, start_r = self.anchor_at(a, s0, s.get("start"))
            # Fit inside s1 within < 1 us when abutting the next piece so Scene switches shots before the overlay ends.
            raw_dur = min(b, s1) - start_r
            dur = _floor6(raw_dur) if (k < len(slices) - 1 or abs(b - s1) < 1e-6) else _floor3(raw_dur)
            while dur > 0 and start_r + dur > s1:
                dur = round(dur - 1e-6, 6)
            params = dict(base_params)
            if len(slices) > 1:
                if k == 0:
                    params["fade_out_s"] = 0.0
                    if dur < base_nom:
                        params["nominal_s"] = LABEL_FIRST_NOMINAL_S
                elif k < len(slices) - 1:
                    params["fade_in_s"] = 0.0
                    params["fade_out_s"] = 0.0
                else:
                    params["fade_in_s"] = 0.0
            s["overlays"].append({"id": self._next_overlay_id(s["overlays"]), "technique": tech, "intent": "structure",
                                  "start": anchor, "dur": dur, "params": params, "slots": {}, "locked": False, "source": "agent", "note": ""})

    def add_overlay(self, role, tech, text):
        start_nom, length_nom = self.nominal(role)
        idx = [i for i in range(len(self.shots)) if self.t0[i] is not None and self.t1[i] is not None and isinstance(self.shots[i], dict)]
        if not idx:
            self.skip(None, "no_time", role)
            return
        i = next((k for k in reversed(idx) if self.t0[k] <= start_nom + EPS), idx[0])
        if self.structure(self.shots[i]):
            # the opening never sits on a card (the channel-name beat, a chapter mark): it goes to the end of the shot before it
            earlier = [k for k in idx if k < i and not self.structure(self.shots[k])]
            if earlier:
                i = earlier[-1]
                start_nom = max(self.t0[i], self.t1[i] - length_nom)
        s = self.shots[i]
        s0, s1 = self.t0[i], self.t1[i]
        start = max(start_nom, s0)
        short_open = (role == "open" and length_nom < MIN_OVERLAY_S)
        floor = OPEN_MIN_S if short_open else max(MIN_OVERLAY_S, self.cfg.min_element_s)
        cap_end = s1
        if short_open and s.get("id") == "s0000" and s1 - start >= floor + OPEN_HOLD_S - EPS:
            cap_end = s1 - OPEN_HOLD_S
        end = min(start + length_nom, cap_end)
        if end - start < floor - EPS:
            start = max(s0, end - floor)
        if end - start < floor - 1e-6:
            self.skip(i, "no_room", role)
            return
        if s.get("locked"):
            self.skip(i, "locked", role)
            return
        if not isinstance(s.get("overlays"), list):
            s["overlays"] = []
        anchor, start_r = self.anchor_at(start, s0, s.get("start"))
        dur = _floor3(min(end, s1) - start_r)
        # `source` is the compiler's word for what a program wrote ("agent"): the draft compiler writes every overlay it builds that way,
        # so an edit that rebuilds this shot finds the overlay unchanged
        s["overlays"].append({"id": self._next_overlay_id(s["overlays"]), "technique": tech, "intent": "structure", "start": anchor, "dur": dur,
                              "params": {**self.defaults(tech), **self.overlay_params(role, text)}, "slots": {}, "locked": False, "source": "agent", "note": ""})

    def anchor_at(self, t: float, shot_t0: float, shot_start) -> tuple:
        """(anchor, seconds it resolves to) of an overlay start at `t`: a word anchor, as every overlay the compiler builds has, never
        earlier than `t` (so never before its shot). The shot's own start anchor is used when the overlay starts with the shot."""
        if abs(t - shot_t0) < 1e-9 and isinstance(shot_start, dict):
            return copy.deepcopy(shot_start), shot_t0
        words = self.tm.words
        if not words:
            r = _ceil4(t)
            return {"t": r}, r
        i = self.tm.nearest_word(t)
        ws = float(words[i]["s"])
        off = _ceil4(t - ws)
        return {"w": i, "off": off, "text": words[i]["w"]}, ws + off

    # ------------------------------------------------------------------------------------------------------- 2. title slot
    def title_slot(self):
        slots = [i for i, s in enumerate(self.shots) if isinstance(s, dict) and self.is_title_slot(s)]
        if not slots:
            self.skip(None, "no_title_slot", "brand")
            return
        for n, i in enumerate(slots):
            s = self.shots[i]
            if n > 0:
                self.skip(i, "extra_title", "brand")
                continue
            if s.get("locked"):
                self.skip(i, "locked", "brand")
                continue
            ln = self.length(i)
            if ln is None:
                self.skip(i, "no_time", "brand")
                continue
            if ln < self.cfg.min_element_s - EPS:
                self.skip(i, "too_short", "brand")
                continue
            defaults = self.defaults(self.sd.brand)
            same_brand = (s.get("technique") == self.sd.brand)
            main_k = self.main_asset()
            has_region = ("region" in defaults)
            picks = self.picks_data() if has_region else None
            rest_region = self.rest_region_of(main_k, picks) if (has_region and picks is not None and main_k) else None
            prev = self.neighbour(i, -1)
            pic = self.camera_of(prev) if prev is not None else None
            if has_region and main_k:
                key = main_k
                box = self._paint_box(key)
                a_main = self.image_asset(key) or {}
                reg_d = (a_main.get("regions") or {}).get(rest_region) if (rest_region and isinstance(a_main.get("regions"), dict)) else None
                if box is not None:
                    if isinstance(reg_d, dict) and _num(reg_d.get("x")) and _num(reg_d.get("y")):
                        tx, ty = float(reg_d["x"]), float(reg_d["y"])
                    else:
                        tx, ty = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
                    if pic and pic[0] == main_k and self._region_framed(main_k, rest_region, pic[1][-1]):
                        last = pic[1][-1]
                        cx0, cy0, z0 = float(last["cx"]), float(last["cy"]), _clamp_zoom(last["zoom"])
                        cx1, cy1, z1 = self._clamp_fill_pose(
                            box, cx0 + (tx - cx0) * 0.35, cy0 + (ty - cy0) * 0.35, _clamp_zoom(z0 * BRAND_SWEEP_PUSH)
                        )
                        keys = [_key(0.0, cx0, cy0, z0, ease="inout_sine"), _key(1.0, cx1, cy1, z1)]
                    else:
                        keys = self.filling_band_keys(key, (tx, ty), push=BRAND_SWEEP_PUSH, shift_frac=0.35, ease="inout_sine")
                else:
                    keys = None
            elif pic and self._fills_screen(pic[0], pic[1][-1]):
                key, cam = pic
                last = cam[-1]
                cx, cy, z = last["cx"], last["cy"], last["zoom"]
                keys = [_key(0.0, cx, cy, z), _key(1.0, cx, cy, round(_clamp_zoom(z * BRAND_PUSH), 5))]
            else:
                key = main_k
                target_xy = (pic[1][-1]["cx"], pic[1][-1]["cy"]) if (pic and pic[0] == key) else None
                keys = self.filling_band_keys(key, target_xy, push=BRAND_PUSH) if key else None
            wanted = {"camera": self.in_box(key, keys), "text": self.cfg.channel_name}
            for k, v in self.sd.brand_params.items():
                if k in defaults:
                    cur_v = (s.get("params") or {}).get(k) if (same_brand and isinstance(s.get("params"), dict)) else None
                    wanted[k] = cur_v if isinstance(cur_v, str) and cur_v else v
            if has_region:
                if picks is not None and main_k:
                    wanted["region"] = rest_region
                elif same_brand and isinstance(s.get("params"), dict) and "region" in s["params"]:
                    wanted["region"] = s["params"]["region"]
                else:
                    wanted["region"] = None
            wanted.update(self.brand_texts())
            self.rewrite(s, self.sd.brand, key, wanted, None)

    def picks_data(self) -> dict | None:
        """Load picks once from `meta["picks"]` or `project_dir/picks.json`, if present."""
        if self._picks is not None:
            return self._picks
        if isinstance(self.meta.get("picks"), dict):
            self._picks = self.meta["picks"]
            return self._picks
        if self.project_dir is not None:
            p = self.project_dir / "picks.json"
            if p.is_file():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._picks = raw
                        return self._picks
                except Exception:           # noqa: BLE001
                    pass
        return None

    def _timing_meta(self) -> dict | None:
        """Return timing mapping carrying `beats` and `chapters` (from `self.tm` or `project_dir/timing.json`)."""
        beats = getattr(self.tm, "beats", None)
        chapters = getattr(self.tm, "chapters", None)
        if isinstance(beats, list) and beats and isinstance(chapters, list) and chapters:
            return {"beats": beats, "chapters": chapters}
        if self._timing_raw is not None:
            return self._timing_raw
        if self.project_dir is not None:
            p = self.project_dir / "timing.json"
            if p.is_file():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(raw, dict):
                        self._timing_raw = raw
                        return raw
                except Exception:           # noqa: BLE001
                    pass
        return {"beats": beats or [], "chapters": chapters or []}

    def rest_region_of(self, main_k: str | None, picks: dict | None) -> str | None:
        if not main_k or not isinstance(picks, dict):
            return None
        asset = self.image_asset(main_k) or {}
        regions = asset.get("regions") if isinstance(asset.get("regions"), dict) else None
        return choose_rest_region(self._timing_meta(), picks, main_k, regions)

    def _region_framed(self, asset_key: str, region_name: str | None, cam_key: dict) -> bool:
        """True when `cam_key` fills the screen on `asset_key` and keeps `region_name` (or centre) in the safe middle band."""
        box = self._paint_box(asset_key)
        if box is None:
            return True
        if not self._fills_screen(asset_key, cam_key):
            return False
        z_cover = self._cover_zoom(box)
        z = float(cam_key["zoom"])
        if z > z_cover * 1.6:
            return False
        a = self.image_asset(asset_key) or {}
        if region_name:
            reg = (a.get("regions") or {}).get(region_name) if isinstance(a.get("regions"), dict) else None
            if not isinstance(reg, dict) or not (_num(reg.get("x")) and _num(reg.get("y"))):
                return False
            rx, ry = float(reg["x"]), float(reg["y"])
        else:
            rx, ry = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0
        sx = 960.0 + (rx - float(cam_key["cx"])) * z
        sy = 540.0 + (ry - float(cam_key["cy"])) * z
        return 0.18 * 1920.0 <= sx <= 0.82 * 1920.0 and 0.28 * 1080.0 <= sy <= 0.70 * 1080.0

    def video_title(self) -> str:
        """The video's title (`identity.video_title` of the storyboard) in one line, "" when there is none."""
        ident = self.sb.get("identity")
        v = ident.get("video_title") if isinstance(ident, dict) else None
        return T.one_line(v) if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""

    def brand_texts(self) -> dict:
        """The `title` and `subtitle` params of the channel-name beat, when its technique has them (the registry defaults say so): the video's
        title and under it a small line "<painting's title> · <Artist, year>" (the words of the label); without a video title the painting's
        title and "<Artist, year>"."""
        names = self.defaults(self.sd.brand)
        if "title" not in names or "subtitle" not in names:
            return {}
        text = self._text if self._text is not None else self.texts()
        vt = self.video_title()
        if vt:
            return {"title": vt, "subtitle": " · ".join(p for p in (text["title"], text["artist_year"]) if p)}
        return {"title": text["title"], "subtitle": text["artist_year"]}

    # ------------------------------------------------------------------------------------------------------- 3. chapter marks
    def chapter_marks(self):
        number = 0
        for i, s in enumerate(self.shots):
            if not isinstance(s, dict) or not self.is_chapter_card(s):
                continue
            number += 1
            if s.get("locked"):
                self.skip(i, "locked", "mark")
                continue
            ln = self.length(i)
            if ln is None:
                self.skip(i, "no_time", "mark")
                continue
            if ln < self.cfg.min_element_s - EPS:
                self.skip(i, "too_short", "mark")
                continue
            params = s.get("params") if isinstance(s.get("params"), dict) else {}
            slots = s.get("slots") if isinstance(s.get("slots"), dict) else {}
            raw = params.get("title") if isinstance(params.get("title"), str) else None
            if not raw and isinstance(slots.get("title"), dict) and isinstance(slots["title"].get("text"), str):
                raw = slots["title"]["text"]
            if not raw or not T.strip_number(raw):
                self.skip(i, "no_title", "mark")
                continue
            nxt = self.neighbour(i, +1)
            pic = self.camera_of(nxt) if nxt is not None else None
            if pic and self._fills_screen(pic[0], pic[1][0]):
                key, cam = pic
                first = cam[0]
                cx, cy, z = float(first["cx"]), float(first["cy"]), _clamp_zoom(first["zoom"])
                box = self._paint_box(key)
                if box is not None:
                    z_min = _clamp_zoom(self._cover_zoom(box))
                    z0_raw = _clamp_zoom(max(z_min, z / MARK_WIDER))
                    if z0_raw > z:
                        cx0, cy0, z0 = cx, cy, round(z, 5)
                    else:
                        cx0, cy0, z0 = self._clamp_fill_pose(box, cx, cy, z0_raw)
                else:
                    cx0, cy0, z0 = cx, cy, round(_clamp_zoom(z / MARK_WIDER), 5)
                keys = [_key(0.0, cx0, cy0, z0), _key(1.0, cx, cy, round(z, 5))]
            else:
                key = self.main_asset()
                target_xy = (pic[1][0]["cx"], pic[1][0]["cy"]) if (pic and pic[0] == key) else None
                keys = self.filling_band_keys(key, target_xy, push=WHOLE_PUSH) if key else None
            tr = None
            if self.sd.transition:
                tr = {"technique": self.sd.transition["technique"], "dur": round(min(self.sd.transition["dur"], max(0.0, ln - 0.05)), 3), "params": {}}
            self.rewrite(s, self.sd.mark, key, {"camera": self.in_box(key, keys), "title": T.mark_title(number, raw)}, tr, set_transition=True)

    # ------------------------------------------------------------------------------------------------------- rewriting a shot
    def rewrite(self, s, tech, key, wanted: dict, transition, set_transition=False):
        """Make `s` a shot of technique `tech` looking at `key` with `wanted` params. A shot that already has this technique keeps
        its other params (an owner's tuning); a shot of another technique starts clean (its old params would not fit)."""
        same = s.get("technique") == tech
        params = dict(s["params"]) if same and isinstance(s.get("params"), dict) else self.defaults(tech)
        for k, v in wanted.items():
            if k == "camera" and v is None:
                params.pop(k, None)           # no camera could be made: the picture is shown whole, still
            else:
                params[k] = v
        s["technique"] = tech
        s["slots"] = {"image": {"asset": key}} if key else {}
        s["params"] = params
        if set_transition:
            s["transition_in"] = transition

    # ------------------------------------------------------------------------------------------------------- everything
    def run(self):
        if self.shots:
            self._text = self.texts()
            self.opening()
            self.title_slot()
            self.chapter_marks()
        changed = []
        for i, s in enumerate(self.shots):
            if not isinstance(s, dict):
                continue
            if _canon(s) == self.before[i]:
                continue
            changed.append(s.get("id"))
            old = json.loads(self.before[i])
            # the shot itself is the identity's work when its picture or technique changed; an opening that only got overlays stays
            # the author's shot (the overlays carry the mark)
            core = {k: v for k, v in s.items() if k not in ("overlays", "source")}
            core_old = {k: v for k, v in old.items() if k not in ("overlays", "source")}
            if _canon(core) != _canon(core_old):
                s["source"] = "identity"
        ident = self.sb.get("identity") if isinstance(self.sb.get("identity"), dict) else {}
        self.sb = _after(self.sb, "style", "identity", {"style": self.style_id, **{k: v for k, v in ident.items() if k != "style"}})      # the video's title stays
        return self.sb, {"style": self.style_id, "changed": [c for c in changed if c is not None], "skipped": self.skipped}


def with_video_title(storyboard: dict, title: str | None) -> dict:
    """A copy of the storyboard whose `identity.video_title` is `title` (one line; None or "" removes it). The `identity` object keeps its other
    keys; when there is none yet it is made, right after `style`. The beat's texts follow when `apply_identity` runs on the result."""
    sb = copy.deepcopy(storyboard)
    ident = dict(sb["identity"]) if isinstance(sb.get("identity"), dict) else {}
    if title:
        ident["video_title"] = title
    else:
        ident.pop("video_title", None)
    if "identity" not in sb and not ident:
        return sb
    return _after(sb, "style", "identity", ident)


def fit_camera_to_box(asset: dict | None, keys: list | None, project_dir=None, *, box: tuple | None = None) -> tuple[list | None, list[dict]]:
    """Clamp camera `keys` onto the painted area of `asset` (`CB.box_of(asset, project_dir)` + `CB.fit_frame`).
    Returns `(fitted_keys, moved)` without mutating `keys`; `keys` itself is returned when `asset` has no box, `keys` is empty,
    or no key moved (`moved` is empty). Each entry in `moved` has `index`, `share`, `from`, `to`, and `box`."""
    if not keys:
        return keys, []
    resolved = box if box is not None else (CB.box_of(asset, project_dir) if isinstance(asset, dict) else None)
    if resolved is None:
        return keys, []
    out = []
    moved = []
    for n, k in enumerate(keys):
        if isinstance(k, dict) and _num(k.get("cx")) and _num(k.get("cy")) and _num(k.get("zoom")) and k["zoom"] > 0:
            cx0, cy0, z0 = k["cx"], k["cy"], k["zoom"]
            cx, cy, z = CB.fit_frame(resolved, cx0, cy0, z0)
            z_clamped = _clamp_zoom(z)
            if (cx, cy, z) != (cx0, cy0, z0) and (cx, cy, z_clamped) != (cx0, cy0, z0):
                moved.append({"index": n, "share": CB.outside_share(resolved, cx0, cy0, z0),
                              "from": (cx0, cy0, z0), "to": (cx, cy, z_clamped), "box": resolved})
                k = {**k, "cx": cx, "cy": cy, "zoom": z_clamped}
        out.append(k)
    return (out, moved) if moved else (keys, [])


def choose_rest_region(timing, picks: dict | None, main_asset: str | None, main_regions: dict | None = None) -> str | None:
    """Automatic rest-region rule for ID-BRAND-04 from project data (no model calls, no painting-specific names):
      1. If picks give the cold open's final sentence (question) line a region on the main painting, use that region.
      2. Else if the cold open names a subject of kind `person` or `thing` on the main painting, use its `tight: true` region.
      3. Else return None (rest on the centre of the painting).
    """
    if not isinstance(picks, dict):
        return None
    main_key = main_asset or picks.get("main_asset")
    if not isinstance(main_key, str) or not main_key:
        return None
    regions = main_regions
    if not isinstance(regions, dict):
        asset_entry = (picks.get("assets") or {}).get(main_key)
        regions = asset_entry.get("regions") if isinstance(asset_entry, dict) else None
    if not isinstance(regions, dict) or not regions:
        return None

    beats_raw = getattr(timing, "beats", None) if timing is not None and not isinstance(timing, dict) else (timing.get("beats") if isinstance(timing, dict) else None)
    chapters_raw = getattr(timing, "chapters", None) if timing is not None and not isinstance(timing, dict) else (timing.get("chapters") if isinstance(timing, dict) else None)
    beats = [b for b in (beats_raw or []) if isinstance(b, dict) and isinstance(b.get("id"), str)]
    chapters = [c for c in (chapters_raw or []) if isinstance(c, dict)]
    if not beats:
        return None

    cold: list[dict] = []
    if chapters:
        c0 = chapters[0]
        c0_id = c0.get("id")
        if isinstance(c0_id, str) and c0_id:
            cold = [b for b in beats if b.get("chapter") == c0_id]
        if not cold and _num(c0.get("w1")):
            cold = [b for b in beats if _num(b.get("w1")) and b["w1"] <= c0["w1"]]
        if not cold and len(chapters) >= 2 and _num(chapters[1].get("start")):
            cold = [b for b in beats if _num(b.get("end")) and b["end"] <= chapters[1]["start"] + 1e-6]
    if not cold:
        return None

    picks_beats = picks.get("beats") if isinstance(picks.get("beats"), dict) else {}

    # 1. Cold open's final sentence (question) line: picture region on the main painting.
    last_entry = picks_beats.get(cold[-1]["id"])
    if isinstance(last_entry, dict) and last_entry.get("status") != "skip":
        for item in last_entry.get("items") or []:
            if not isinstance(item, dict):
                continue
            item_asset = item.get("asset") or main_key
            reg = item.get("region")
            if item_asset == main_key and isinstance(reg, str) and isinstance(regions.get(reg), dict):
                return reg

    # 2. First subject of kind `person` or `thing` named in the cold open with a tight region on the main painting.
    subjects = {s["id"]: s for s in (picks.get("subjects") or []) if isinstance(s, dict) and isinstance(s.get("id"), str)}
    for beat in cold:
        entry = picks_beats.get(beat["id"])
        if not isinstance(entry, dict):
            continue
        for about in entry.get("about") or []:
            if not isinstance(about, dict):
                continue
            subj = subjects.get(about.get("id"))
            if not isinstance(subj, dict) or subj.get("kind") not in ("person", "thing"):
                continue
            where = subj.get("where")
            places = where if isinstance(where, list) else ([where] if isinstance(where, dict) else [])
            for place in places:
                if isinstance(place, dict) and place.get("asset") in (None, main_key) and isinstance(place.get("region"), str):
                    reg = place["region"]
                    r = regions.get(reg)
                    if isinstance(r, dict) and r.get("tight") is True:
                        return reg

    # 3. No matching region: light rests cleanly on the centre of the painting.
    return None


def apply_identity(storyboard: dict, style_id: str, style: dict, timing, meta: dict | None = None, *, defaults=None, project_dir=None) -> tuple[dict, dict]:
    """See the module docstring. Raises `IdentityError` for an unknown style or a style.json without an identity block."""
    return _Applier(storyboard, style_id, style, timing, meta, defaults, project_dir).run()
