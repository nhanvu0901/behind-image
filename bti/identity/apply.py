"""Apply a channel identity style to a storyboard: ONE deterministic function, no model, no network, no clock.

    apply_identity(storyboard, style_id, style, timing, meta=None, *, defaults=None) -> (storyboard, report)

Contract: docs/design/2026-11-18-identity-raking-light.md section 6. In short, for the chosen style:
  1. the opening: the `ID-OPEN-*` and `ID-LABEL-*` overlays of every unlocked shot are removed and the style's own are put on the
     shot that is on screen at their nominal start (at least 3 s long: the start moves earlier inside the shot, else it is skipped);
  2. the title slot (the first `X-CARD-02` / `ID-BRAND-*` structure shot) becomes the style's channel-name beat, on the picture of
     the shot before it at that shot's last camera key, with a 3 % push;
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

from . import config as C
from . import titles as T

MIN_OVERLAY_S = 3.0         # an opening overlay is never shorter (contract section 6, rule 1)
MIN_ELEMENT_S = 1.5         # a channel-name beat or a chapter mark is never shorter (section 3); the block's `min_element_s` wins
BRAND_PUSH = 1.03           # the picture under the channel name drifts in by 3 % over the beat
WHOLE_PUSH = 1.03           # the same for a mark that has no picture of its own to flow into
MARK_WIDER = 1.04           # a mark starts 4 % wider than the shot it flows into
EPS = 1e-9

# The nominal timeline of the opening (contract section 3): (start second in the video, length). The block's own `nominal` numbers
# win; these are used only when it has none for a role. A style with neither starts at 0 and lasts 6 s.
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
    def __init__(self, storyboard, style_id, style, timing, meta, defaults=None):
        self.cfg = C.need(style)
        self.sd = self.cfg.style(style_id)
        if self.sd is None:
            raise C.IdentityError("unknown_style", "unknown style %r (choose one of: %s)" % (style_id, ", ".join(self.cfg.ids())),
                                  style=style_id, allowed=self.cfg.ids())
        self.style_id = style_id
        self.tm = _timing(timing)
        self.meta = meta if isinstance(meta, dict) else {}
        self._defaults = defaults
        self.sb = _strip(storyboard)
        shots = self.sb.get("shots")
        self.shots = shots if isinstance(shots, list) else []
        self.assets = self.sb.get("assets") if isinstance(self.sb.get("assets"), dict) else {}
        self.skipped: list = []
        self._skipped_keys: set = set()
        self.before = [_canon(s) for s in self.shots]
        self._resolve_times()

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

    def whole_keys(self, key) -> list | None:
        """The whole picture, fitted the way the matte shots fit it (painting height = `fit_pct` of the frame), with a 3 % push."""
        a = self.image_asset(key)
        if not a or not (_num(a.get("width")) and _num(a.get("height")) and a["width"] > 0 and a["height"] > 0):
            return None
        w, h = float(a["width"]), float(a["height"])
        z = self.cfg.fit_pct / 100.0 * 1080.0 / h
        cx, cy = round(w / 2, 2), round(h / 2, 2)
        return [_key(0.0, cx, cy, round(_clamp_zoom(z), 5)), _key(1.0, cx, cy, round(_clamp_zoom(z * WHOLE_PUSH), 5))]

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
        text = self.texts()                     # before the old overlays go: their words are one of the sources
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
            self.add_overlay(role, tech, text)

    def overlay_params(self, role, text) -> dict:
        writes_text = role == "label" or (role == "open" and not self.sd.label_role)
        if not writes_text:
            return {}
        if role == "label":
            return {"title": text["title"], "artist_year": text["artist_year"]}
        return {"title": text["title"], "sub": text["sub"]}

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
        end = min(start + length_nom, s1)
        floor = max(MIN_OVERLAY_S, self.cfg.min_element_s)         # never below the engine's floor for an element of the identity
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
        n = max([_tail(o.get("id")) for o in s["overlays"] if isinstance(o, dict)] + [0]) + 1
        # `source` is the compiler's word for what a program wrote ("agent"): the draft compiler writes every overlay it builds that way,
        # so an edit that rebuilds this shot finds the overlay unchanged
        s["overlays"].append({"id": "o%d" % n, "technique": tech, "intent": "structure", "start": anchor, "dur": dur,
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
            prev = self.neighbour(i, -1)
            pic = self.camera_of(prev) if prev is not None else None
            if pic:
                key, cam = pic
                last = cam[-1]
                cx, cy, z = last["cx"], last["cy"], last["zoom"]
                keys = [_key(0.0, cx, cy, z), _key(1.0, cx, cy, round(_clamp_zoom(z * BRAND_PUSH), 5))]
            else:
                key = self.main_asset()
                keys = self.whole_keys(key) if key else None
            self.rewrite(s, self.sd.brand, key, {"camera": keys, "text": self.cfg.channel_name}, None)

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
            if pic:
                key, cam = pic
                first = cam[0]
                cx, cy, z = first["cx"], first["cy"], first["zoom"]
                keys = [_key(0.0, cx, cy, round(_clamp_zoom(z / MARK_WIDER), 5)), _key(1.0, cx, cy, _clamp_zoom(z))]
            else:
                key = self.main_asset()
                keys = self.whole_keys(key) if key else None
            tr = None
            if self.sd.transition:
                tr = {"technique": self.sd.transition["technique"], "dur": round(min(self.sd.transition["dur"], max(0.0, ln - 0.05)), 3), "params": {}}
            self.rewrite(s, self.sd.mark, key, {"camera": keys, "title": T.mark_title(number, raw)}, tr, set_transition=True)

    # ------------------------------------------------------------------------------------------------------- rewriting a shot
    def rewrite(self, s, tech, key, wanted: dict, transition, set_transition=False):
        """Make `s` a shot of technique `tech` looking at `key` with `wanted` params. A shot that already has this technique keeps
        its other params (an owner's tuning); a shot of another technique starts clean (its old params would not fit)."""
        same = s.get("technique") == tech
        params = dict(s["params"]) if same and isinstance(s.get("params"), dict) else self.defaults(tech)
        for k, v in wanted.items():
            if v is None:
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
        self.sb = _after(self.sb, "style", "identity", {"style": self.style_id})
        return self.sb, {"style": self.style_id, "changed": [c for c in changed if c is not None], "skipped": self.skipped}


def apply_identity(storyboard: dict, style_id: str, style: dict, timing, meta: dict | None = None, *, defaults=None) -> tuple[dict, dict]:
    """See the module docstring. Raises `IdentityError` for an unknown style or a style.json without an identity block."""
    return _Applier(storyboard, style_id, style, timing, meta, defaults).run()
