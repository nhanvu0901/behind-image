"""Fit the storyboard to the voice again: `off_voice` says what does not sit where the voice puts it, `retime` puts it right.

Why: the cards, the channel-name beat and the end of the video are anchored by absolute time (`{"t": ...}`), the shots of the model by word
(`{"w", "off", "text"}`). When the voice is assembled again (a longer lead or silence before the title, or a single sentence read again) every word
moves and the word anchors follow by themselves; the absolute times do not. This module is the one place that knows where the program's own
parts belong, from the same computation the compiler uses (`bti.draft.zones.place`), so that a full compile and a retime agree.

    off_voice(storyboard, timing, style) -> [problem]                     (tolerance 0.05 s; empty = the storyboard fits the voice)
    retime(storyboard, timing, style, meta=None, defaults=None, video_title=None) -> (storyboard, report)

Pure: no model, no clock, no file. `timing` is `timing.json` (or its normalized form), `style` the style.json document (its `identity` block is
read), `meta` the project's facts for the opening shot (`main_asset`), `defaults(id)` the registry defaults of a technique
(`StyleBundle.param_defaults`).

A problem is `{code, shot, chapter, message, repair}`: `repair` says whether `retime` can put it right. What is listed:

    first_shot_late   the first shot does not start at 0
    opening_missing   the first word starts at 1.2 s or later and the video has no opening shot (the first shot does not start at 0 either)
    opening_extra     the video has the opening shot although the first word starts earlier than 1.2 s (or the video starts with a card)
    title_off         the channel-name beat does not end where the chapter card starts (or the silence ends) or starts before its silence
    card_off          a chapter card does not end where its chapter's silence ends, or does not start where the compiler puts it
    card_count        the number of chapter cards is not the number of chapters that have one (reported, never repaired)
    retime_blocked    (only in the report of `retime`) the moves would put two shots out of order: nothing was moved
    end_off           the document's `end` is not what the compiler writes for this timing (the duration of the voice)
    overlay_off_shot  a explicitly timed overlay extends past its shot
    shot_too_short    a shot is shorter than the engine minimum (reported, never repaired)

The LENGTH of the beat inside its silence is not a problem: every video made before the beat grew has one of 2.9 s. A timing that was not written by the voice
code (no chapter has a `lead`: the reference and lab projects) says nothing about where the voice puts anything: `off_voice` is empty for it.

`retime` puts the opening shot in (or removes it and lets the next shot start at 0), sets the start of the beat and of every chapter card that
is off, sets `end`, then applies the storyboard's identity style again (`bti.identity.apply_identity`: the opening overlays on the opening shot, the
beat's texts and camera, the chapter marks). The video's title (`video_title`: what the project's title document holds, which wins over the storyboard's own
`identity.video_title`, as it does in a full compile) is written into `identity` first, so that the beat shows it as soon as the storyboard fits the voice (a
title that was set while the storyboard was off the voice could not be written then). It fits explicitly timed overlays that extend past the shot, and touches the start of the shot after an inserted or
removed opening shot; a locked shot is left and reported; what it cannot decide (the number of cards) is reported and left. The same call twice
changes nothing the second time.
"""
from __future__ import annotations

import copy
import json

from bti import identity as ID
from bti.engine.timing import AnchorError, Timing
from bti.identity import config as IDC

from . import zones as Z
from .inputs import normalize_timing

TOL = 0.05                 # seconds: what "sits where the voice puts it" means


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def normalized(timing: dict) -> dict:
    """The timing as the draft reads it (chapters with `w0`/`w1`/`lead`): `timing.json` is normalized, a normalized one is kept."""
    chs = timing.get("chapters") if isinstance(timing, dict) else None
    if isinstance(chs, list) and chs and all(isinstance(c, dict) and "w0" in c and "name" in c for c in chs):
        return timing
    return normalize_timing(timing)


def _kind_of(cfg, s) -> str | None:
    """`title` for a title slot, `mark` for a chapter mark / card (structure shots of the old look or of any identity style), else None."""
    if not isinstance(s, dict) or s.get("intent") != "structure":
        return None
    t = s.get("technique")
    if t in IDC.LEGACY_TITLE or (cfg is not None and cfg.is_family(t, "brand")):
        return "title"
    if t in IDC.LEGACY_MARKS or (cfg is not None and cfg.is_family(t, "mark")):
        return "mark"
    return None


def _image(assets: dict, key) -> dict | None:
    a = assets.get(key) if isinstance(key, str) else None
    return a if isinstance(a, dict) and a.get("kind") in (None, "image") else None


def main_key(sb: dict, meta: dict | None, cfg) -> str | None:
    """The main painting the opening shows: the project's (`meta.main_asset`), else the picture the first shot of the video looks at, else the
    first image of the storyboard."""
    assets = sb.get("assets") if isinstance(sb.get("assets"), dict) else {}
    k = (meta or {}).get("main_asset")
    if _image(assets, k):
        return k
    for s in sb.get("shots") or []:
        if isinstance(s, dict) and _kind_of(cfg, s) is None and not Z.is_opening(s):
            a = ((s.get("slots") or {}).get("image") or {}).get("asset") if isinstance(s.get("slots"), dict) and isinstance(s["slots"].get("image"), dict) else None
            if _image(assets, a):
                return a
    return next((k for k in assets if _image(assets, k)), None)


class _Fit:
    """What the document says and what the voice says, side by side. Read-only on `sb` (but it holds the lists of the document, not copies)."""

    def __init__(self, sb: dict, timing: dict, style, meta: dict | None = None):
        self.sb = sb
        self.shots = sb.get("shots") if isinstance(sb.get("shots"), list) else []
        tim = normalized(timing)
        self.words = tim["words"]
        self.duration = float(tim["duration"])
        self.tm = Timing({"duration": self.duration, "words": self.words})
        self.cfg = ID.read(style)
        self.style_id = ID.chosen_style(sb, style) if self.cfg is not None else None
        self.fit_pct = self.cfg.fit_pct if self.cfg is not None else Z.DEFAULT_FIT_PCT
        self.placed = Z.place(tim["chapters"], self.words, Z.brand_length(self.cfg, self.style_id))
        # only a timing the voice code wrote (every chapter says what its silence is for: `lead`) tells where the voice puts the cards; an older or hand-made
        # timing (the reference and lab projects) says nothing about it, so nothing of such a project is off the voice
        self.judges = all(c.get("lead") for c in tim["chapters"])
        self.meta = meta or {}
        self.main = main_key(sb, meta, self.cfg)
        self.canvas = sb.get("canvas") if isinstance(sb.get("canvas"), dict) else {"w": 1920, "h": 1080}
        self.t0: list = []
        for s in self.shots:
            try:
                self.t0.append(self.tm.resolve(s["start"]) if isinstance(s, dict) and isinstance(s.get("start"), dict) else None)
            except (AnchorError, KeyError, TypeError):
                self.t0.append(None)
        try:
            self.end = self.tm.resolve(sb["end"]) if isinstance(sb.get("end"), dict) else None
        except (AnchorError, KeyError, TypeError):
            self.end = None
        self.t1 = [next((self.t0[j] for j in range(i + 1, len(self.shots)) if self.t0[j] is not None), self.end) for i in range(len(self.shots))]

    # -- what the voice says
    def camera(self) -> list | None:
        a = _image(self.sb.get("assets") if isinstance(self.sb.get("assets"), dict) else {}, self.main)
        return Z.whole_camera((a or {}).get("width"), (a or {}).get("height"), self.canvas, self.fit_pct) if a else None

    def opening_needed(self) -> bool:
        return self.placed["opening"] is not None and self.camera() is not None

    def opening_index(self) -> int | None:
        return next((i for i, s in enumerate(self.shots) if Z.is_opening(s)), None)

    def title_index(self) -> int | None:
        return next((i for i, s in enumerate(self.shots) if _kind_of(self.cfg, s) == "title"), None)

    def mark_indexes(self) -> list:
        return [i for i, s in enumerate(self.shots) if _kind_of(self.cfg, s) == "mark"]

    def title_chapter(self) -> dict | None:
        return next((c for c in self.placed["chapters"] if c["title"]), None)

    def card_chapters(self) -> list:
        return [c for c in self.placed["chapters"] if c["card"]]


def _problem(code, shot, chapter, message, repair=True, locked=False) -> dict:
    return {"code": code, "shot": shot, "chapter": chapter, "message": message, "repair": bool(repair and not locked), "locked": bool(locked)}


def _fmt(t) -> str:
    return "%.2f s" % t if _num(t) else "?"


def _overlay_times(f: _Fit, overlay: dict) -> tuple[float, float] | None:
    try:
        start = f.tm.resolve(overlay["start"])
        if isinstance(overlay.get("end"), dict):
            end = f.tm.resolve(overlay["end"])
        elif _num(overlay.get("dur")):
            end = start + overlay["dur"]
        else:
            return None
        return start, end
    except (AnchorError, KeyError, TypeError):
        return None


def _check(f: _Fit) -> list:
    out: list = []
    shots = f.shots
    if not shots:
        return out
    sid = lambda i: shots[i].get("id") if isinstance(shots[i], dict) else None          # noqa: E731
    from bti.engine.storyboard import MIN_SHOT_S
    for i, shot in enumerate(shots):
        if f.t0[i] is not None and f.t1[i] is not None and f.t1[i] - f.t0[i] < MIN_SHOT_S - 1e-6:
            out.append(_problem("shot_too_short", sid(i), None, "shot lasts %.2f s, less than %.2f s" % (f.t1[i] - f.t0[i], MIN_SHOT_S), repair=False))
        if not isinstance(shot, dict) or f.t0[i] is None or f.t1[i] is None:
            continue
        for overlay in shot.get("overlays") or []:
            times = _overlay_times(f, overlay) if isinstance(overlay, dict) else None
            if times is None:
                continue
            start, end = times
            if end > f.t1[i] + 1e-6:
                out.append(_problem("overlay_off_shot", sid(i), None,
                                    "overlay %s ends outside its shot" % overlay.get("id"), locked=bool(shot.get("locked"))))
    if not f.judges:
        return out
    # the first shot starts at 0; the opening shot is there exactly when the first word starts at 1.2 s or later
    first_ok = f.t0[0] is not None and abs(f.t0[0]) <= TOL
    if not first_ok and f.t0[0] is not None:
        out.append(_problem("first_shot_late", sid(0), None, "the first shot starts at %s, not at 0" % _fmt(f.t0[0]), locked=bool(shots[0].get("locked"))))
    oi = f.opening_index()
    if f.placed["opening"] is not None:
        if oi is None and not first_ok and f.t0[0] is not None:
            out.append(_problem("opening_missing", None, None, "the first word starts at %s: the video needs the opening shot (the whole painting) before it" % _fmt(f.words[0]["s"]),
                                repair=f.opening_needed()))
    elif oi is not None:
        out.append(_problem("opening_extra", sid(oi), None, "the video has the opening shot but the first word starts at %s" % _fmt(f.words[0]["s"]), locked=bool(shots[oi].get("locked"))))
    # the channel-name beat: it ends where the chapter card starts (or the silence ends) and does not start before its silence
    ti, tc = f.title_index(), f.title_chapter()
    if ti is not None and tc is not None and f.t0[ti] is not None:
        exp_end = tc["card"]["start"] if tc["card"] else tc["gap"][1]
        locked = bool(shots[ti].get("locked"))
        if f.t1[ti] is None or abs(f.t1[ti] - exp_end) > TOL:
            out.append(_problem("title_off", sid(ti), tc["id"], "the channel-name beat ends at %s, the voice puts its end at %s" % (_fmt(f.t1[ti]), _fmt(exp_end)), locked=locked))
        elif f.t0[ti] < tc["gap"][0] - TOL:
            out.append(_problem("title_off", sid(ti), tc["id"], "the channel-name beat starts at %s, before its silence (%s)" % (_fmt(f.t0[ti]), _fmt(tc["gap"][0])), locked=locked))
    # the chapter cards: one for each chapter that has one, each ending where its silence ends
    marks, want = f.mark_indexes(), f.card_chapters()
    if len(marks) != len(want):
        out.append(_problem("card_count", None, None, "the storyboard has %d chapter card(s), the voice has %d chapter(s) with a card: nothing was moved" % (len(marks), len(want)), repair=False))
    else:
        for i, c in zip(marks, want):
            if f.t0[i] is None:
                continue
            locked = bool(shots[i].get("locked"))
            gap_start, gap_end = c["gap"]
            if f.t1[i] is None or abs(f.t1[i] - gap_end) > TOL:
                out.append(_problem("card_off", sid(i), c["id"], "the chapter card ends at %s, its silence ends at %s" % (_fmt(f.t1[i]), _fmt(gap_end)), repair=False, locked=locked))
            elif f.t0[i] < gap_start - TOL or abs(f.t0[i] - c["card"]["start"]) > TOL:
                out.append(_problem("card_off", sid(i), c["id"], "the chapter card starts at %s, the voice puts it at %s" % (_fmt(f.t0[i]), _fmt(c["card"]["start"])), locked=locked))
    if f.end is not None and abs(f.end - f.duration) > TOL:
        out.append(_problem("end_off", None, None, "the video ends at %s, the voice lasts %s" % (_fmt(f.end), _fmt(f.duration))))
    return out


def off_voice(storyboard: dict, timing: dict, style, meta: dict | None = None) -> list:
    """What does not sit where the voice puts it (tolerance 0.05 s): a list of problems, empty when the storyboard fits the voice. `style` is the
    style.json document; a storyboard without an identity style is judged by the old cards (the beat is `X-CARD-02`, the marks `X-CARD-01`)."""
    if not isinstance(storyboard, dict):
        return []
    return _check(_Fit(storyboard, timing, style, meta))


# --------------------------------------------------------------------------------------------------------------------- the repair
def _anchor_at(f: _Fit, shot: dict, t: float) -> dict:
    """The start of a shot that must begin at `t` (0 or 0.35 s before the first word): a word anchor on the word it already starts on, else an
    absolute time."""
    a = shot.get("start") if isinstance(shot.get("start"), dict) else {}
    w = a.get("w")
    if isinstance(w, int) and not isinstance(w, bool) and 0 <= w < len(f.words):
        return {"w": w, "off": round(t - float(f.words[w]["s"]), 4), "text": a.get("text", f.words[w]["w"])}
    return {"t": round(t, 3)}


def retime(storyboard: dict, timing: dict, style, meta: dict | None = None, defaults=None, video_title: str | None = None) -> tuple[dict, dict]:
    """See the module docstring. The input is never changed. `report` is `{"inserted": [ids], "removed": [ids], "moved": [{"shot", "what", "from", "to"}],
    "end": {"from", "to"} | None, "left": [problems that are still there], "identity": {"style", "changed", "skipped"} | None, "before": [codes],
    "video_title": {"from", "to"} | None}` (`video_title`: the title the beat now shows when this call wrote another one, else None). `video_title` None or ""
    leaves the title the storyboard has."""
    sb = copy.deepcopy(storyboard)
    if not isinstance(sb.get("shots"), list):
        return sb, {"inserted": [], "removed": [], "moved": [], "end": None, "left": [], "identity": None, "before": [], "video_title": None, "overlays": []}
    report: dict = {"inserted": [], "removed": [], "moved": [], "end": None, "left": [], "identity": None, "before": [], "video_title": None, "overlays": []}
    f = _Fit(sb, timing, style, meta)
    report["before"] = [p["code"] for p in _check(f)]

    def move(shot, what, frm, to):
        report["moved"].append({"shot": shot.get("id"), "what": what, "from": frm, "to": to})

    # 1. the opening shot (and the start of the shot after it)
    shots = sb["shots"]
    oi = f.opening_index()
    if f.placed["opening"] is not None:
        first_ok = bool(f.t0 and f.t0[0] is not None and abs(f.t0[0]) <= TOL)
        if oi is None and shots and not first_ok and f.opening_needed():
            asset = (sb.get("assets") or {}).get(f.main)
            base = defaults(Z.OPENING_TECHNIQUE) if callable(defaults) else None
            op = Z.opening_shot(f.main, asset, f.canvas, f.fit_pct, base)
            nxt = shots[0] if isinstance(shots[0], dict) else None
            if nxt is not None and not nxt.get("locked") and isinstance(nxt.get("start"), dict) and nxt["start"].get("w") == 0:
                before = copy.deepcopy(nxt["start"])
                nxt["start"] = _anchor_at(f, nxt, float(f.words[0]["s"]) - Z.OPENING_LEAD_S)          # the model's first shot starts 0.35 s before the first word
                if nxt["start"] != before:
                    move(nxt, "start", before, nxt["start"])
            shots.insert(0, op)
            report["inserted"].append(Z.OPENING_ID)
        elif oi is not None and isinstance(shots[oi], dict) and not shots[oi].get("locked") and shots[oi].get("start") != {"t": 0.0} and oi == 0:
            before = copy.deepcopy(shots[oi].get("start"))
            shots[oi]["start"] = {"t": 0.0}
            move(shots[oi], "start", before, shots[oi]["start"])
    elif oi is not None and not shots[oi].get("locked"):
        gone = shots.pop(oi)
        report["removed"].append(gone.get("id"))
        nxt = shots[oi] if oi == 0 and len(shots) > 0 and isinstance(shots[0], dict) else None
        if nxt is not None and not nxt.get("locked"):
            before = copy.deepcopy(nxt.get("start"))
            nxt["start"] = _anchor_at(f, nxt, 0.0)                                                        # the next shot starts at 0
            if nxt["start"] != before:
                move(nxt, "start", before, nxt["start"])
    f = _Fit(sb, timing, style, meta)

    # 2. the chapter cards: the start of each that is off (the end is the next shot's start: the voice moves it by itself). A card that cannot be moved (locked,
    #    its end not where its silence ends, a number of cards that is not the number of chapters) is left, and so is the beat before it.
    ti, tc = f.title_index(), f.title_chapter()
    marks, want = f.mark_indexes(), f.card_chapters()
    card_ok: dict = {}
    if len(marks) == len(want):
        for i, c in zip(marks, want):
            if f.t0[i] is None or f.t1[i] is None or abs(f.t1[i] - c["gap"][1]) > TOL or shots[i].get("locked"):
                card_ok[c["id"]] = bool(f.t0[i] is not None and f.t1[i] is not None and abs(f.t1[i] - c["gap"][1]) <= TOL
                                        and f.t0[i] >= c["gap"][0] - TOL and abs(f.t0[i] - c["card"]["start"]) <= TOL)        # a stuck card that already sits right is fine
                continue
            card_ok[c["id"]] = True
            if f.t0[i] < c["gap"][0] - TOL or abs(f.t0[i] - c["card"]["start"]) > TOL:
                before = copy.deepcopy(shots[i].get("start"))
                shots[i]["start"] = {"t": round(c["card"]["start"], 3)}
                move(shots[i], "start", before, shots[i]["start"])
    # 3. the channel-name beat: when it is off, it ends where the card starts (the silence ends) and takes the new length
    if ti is not None and tc is not None and f.t0[ti] is not None and not shots[ti].get("locked") and (tc["card"] is None or card_ok.get(tc["id"])):
        exp_end = tc["card"]["start"] if tc["card"] else tc["gap"][1]
        if f.t1[ti] is None or abs(f.t1[ti] - exp_end) > TOL or f.t0[ti] < tc["gap"][0] - TOL:
            before = copy.deepcopy(shots[ti].get("start"))
            shots[ti]["start"] = {"t": round(tc["title"]["start"], 3)}
            move(shots[ti], "start", before, shots[ti]["start"])
    # 4. the end of the video is the end of the voice
    if f.end is not None and abs(f.end - f.duration) > TOL:
        before = copy.deepcopy(sb.get("end"))
        keep = {k: v for k, v in before.items() if k not in ("t", "w", "off", "text")} if isinstance(before, dict) else {}
        sb["end"] = {**keep, "t": round(f.duration, 4)}
        report["end"] = {"from": before, "to": sb["end"]}
    # a move that would put two shots out of order (a locked card the beat cannot get past, say) is not made: the document stays as it was and says why
    f = _Fit(sb, timing, style, meta)
    starts = [t for t in f.t0 if t is not None]
    if any(b <= a + 1e-6 for a, b in zip(starts, starts[1:])):
        orig = copy.deepcopy(storyboard)
        left = _check(_Fit(orig, timing, style, meta)) + [_problem("retime_blocked", None, None, "moving the cards and the beat would put two shots out of order: nothing was moved", repair=False)]
        return orig, {"inserted": [], "removed": [], "moved": [], "end": None, "left": left, "identity": None, "before": report["before"], "video_title": None, "overlays": []}
    # 5. the identity style again: the opening overlays on the opening shot, the beat's texts and camera, the marks (and the video's title, which the beat shows)
    if f.style_id:
        if video_title and ID.video_title_of(sb) != video_title:
            report["video_title"] = {"from": ID.video_title_of(sb), "to": video_title}
            sb = ID.with_video_title(sb, video_title)
        meta2 = dict(meta or {})
        if f.main and not meta2.get("main_asset"):
            meta2["main_asset"] = f.main
        sb, rep = ID.apply_identity(sb, f.style_id, style, normalized(timing), meta2, defaults=defaults)
        report["identity"] = rep
    # Fit timed overlays only after all structural and identity changes have settled.
    f = _Fit(sb, timing, style, meta)
    from bti.engine import registry as R
    try:
        bundle = R.load_bundle(sb.get("style") or "gae")
    except Exception:
        bundle = None
    for i, shot in enumerate(f.shots):
        if not isinstance(shot, dict) or shot.get("locked") or f.t0[i] is None or f.t1[i] is None:
            continue
        overlays = shot.get("overlays")
        if not isinstance(overlays, list):
            continue
        kept = []
        for overlay in overlays:
            times = _overlay_times(f, overlay) if isinstance(overlay, dict) else None
            if times is None:
                kept.append(overlay)
                continue
            start, end = times
            if end <= f.t1[i] + 1e-6:
                kept.append(overlay)
                continue
            old = copy.deepcopy(overlay)
            spec = bundle.spec(overlay.get("technique")) if bundle else None
            minimum = (spec or {}).get("timing", {}).get("min_s", 1.0)
            minimum = min(1.0, minimum) if _num(minimum) and minimum > 0 else 1.0
            duration = f.t1[i] - start
            if duration >= minimum - 1e-6:
                if isinstance(overlay.get("end"), dict):
                    overlay["end"] = {"t": round(f.t1[i], 6)}
                else:
                    overlay["dur"] = round(duration, 6)
                what = "shortened"
            elif f.t1[i] - f.t0[i] >= minimum - 1e-6:
                overlay["start"] = {"t": round(f.t1[i] - minimum, 6)}
                if isinstance(overlay.get("end"), dict):
                    overlay["end"] = {"t": round(f.t1[i], 6)}
                else:
                    overlay["dur"] = round(minimum, 6)
                what = "moved"
            else:
                what = "removed"
            if what != "removed":
                kept.append(overlay)
            report["overlays"].append({"shot": shot.get("id"), "overlay": old.get("id"), "what": what,
                                       "from": old, "to": copy.deepcopy(overlay) if what != "removed" else None})
        shot["overlays"] = kept
    f = _Fit(sb, timing, style, meta)
    report["left"] = _check(f)
    return sb, report


def changed_ids(before: dict, after: dict) -> list:
    """The ids of the shots whose content differs between two versions of a storyboard, plus the shots one has and the other has not."""
    a = {s.get("id"): s for s in (before.get("shots") or []) if isinstance(s, dict)}
    b = {s.get("id"): s for s in (after.get("shots") or []) if isinstance(s, dict)}
    out = [sid for sid in b if sid not in a or _canon(a[sid]) != _canon(b[sid])]
    out += [sid for sid in a if sid not in b]
    return [sid for sid in out if sid is not None]


# ------------------------------------------------------------------------------------------------------------ a project on disk
def project_off_voice(project_dir, storyboard: dict | None = None) -> list:
    """`off_voice` of the saved storyboard of a project against the timing file it names, with the style's identity block. Never raises: a
    project whose storyboard, timing or style cannot be read (other checks say so) has nothing to report here."""
    from pathlib import Path
    try:
        d = Path(project_dir)
        sb = storyboard if isinstance(storyboard, dict) else json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
        rel = sb.get("timing") if isinstance(sb.get("timing"), str) and sb.get("timing") else "timing.json"
        from bti.engine import registry as R
        from bti.engine import storyboard as SB
        tpath = SB.safe_rel(d, rel)
        timing = json.loads(tpath.read_text(encoding="utf-8")) if tpath is not None and tpath.is_file() else None
        if not isinstance(timing, dict):
            return []
        style = R.load_bundle(sb.get("style") if isinstance(sb.get("style"), str) and sb.get("style") else "gae").style
        return off_voice(sb, timing, style)
    except Exception:           # noqa: BLE001 - see the docstring
        return []


def off_voice_message(problems: list) -> str:
    """One English sentence for a refusal: how many things sit where an earlier voice put them, and the first of them."""
    first = problems[0]["message"] if problems else ""
    return "the storyboard does not fit the voice: %d thing(s) sit where an earlier voice put them (first: %s)" % (len(problems), first)
