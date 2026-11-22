"""Where the program puts what is not the model's: the opening shot, the channel-name beat (the title slot) and the chapter cards. Pure
functions of the voice's timing: no model, no clock, no registry, no I/O. The draft compiler (`compile.py`, `_Compiler.zones`) and the
fit to the voice (`retime.py`) both call `place`, so a full compile and a retime agree to the hundredth of a second.

The silences the voice leaves (`timing.json`, `chapters[].lead`):

    the first chapter, a cold open:   [0 ........ first word)             `lead.kind` "plain": the opening shot fills it
    the first chapter after it:       [lead.start ... lead.end)           `lead.kind` "title": the beat, then (when the chapter has one) its card
    any later chapter with a card:    [lead.start ... lead.end)           `lead.kind` "card": the card sits at the end of it

The opening shot (`opening_span`): when the first word starts at 1.2 s or later, the video starts with a shot of the ENTIRE painting from
0 to 0.35 s before the first word; the model's first shot starts there. The shot is marked by its id, `OPENING_ID`: the compiler hands
out `s0001`, `s0002`, ... and `bti.ops` the next number after the largest in use, so `s0000` is never anybody's but this shot's; an id
survives every typed operation, an edit-mode compile (the id is read back from the saved storyboard), the fast edit and the identity
application, which `source`, `note` and the technique do not (an operation writes its own `source`, a change of picture clears the note).

The channel-name beat (`title_length`): `min(B, gap - cd - 1.2)` where `B` is the style's nominal length of the beat, `gap` the silence
that holds it and the card, `cd` the card's length and 1.2 s the breath after the last word of the cold open; when that leaves less than
`MIN_CARD_S`, `min(B, gap - cd)`.
"""
from __future__ import annotations

import copy

from bti.media import contentbox as CB          # panelbox: the painted area of a picture

CARD_S = 2.8                     # a chapter card
TITLE_CARD_S = 2.9               # the beat of a style that has no nominal length of its own (and the old title card)
MIN_CARD_S = 1.0
BREATH_S = 1.2                   # air after the last word of the cold open, before the beat starts
OPENING_MIN_FIRST_WORD_S = 1.2   # the opening shot exists when the first word starts this late or later
OPENING_LEAD_S = 0.35            # the model's first shot starts this long before the first word
OPENING_ID = "s0000"
OPENING_TECHNIQUE = "CAM-01"
OPENING_INTENT = "establish"
OPENING_NOTE = "opening shot: the whole painting before the first word"
DEFAULT_FIT_PCT = 95.5
EPS = 1e-6


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def is_opening(shot) -> bool:
    """The program's opening shot: the shot with the reserved id."""
    return isinstance(shot, dict) and shot.get("id") == OPENING_ID


# ------------------------------------------------------------------------------------------------------------ the beat
def brand_length(identity_cfg, style_id) -> float:
    """`B`: the nominal length of the channel-name beat of the style (`nominal.brand.dur_s`), else `TITLE_CARD_S`."""
    sd = identity_cfg.style(style_id) if identity_cfg is not None and style_id else None
    b = sd.dur_s.get("brand") if sd is not None else None
    return float(b) if _num(b) and b > 0 else TITLE_CARD_S


def title_length(brand_s: float, gap: float, cd: float) -> float:
    """The length of the title slot inside a silence of `gap` seconds that also holds a chapter card of `cd` seconds."""
    td = min(brand_s, gap - cd - BREATH_S)
    return td if td >= MIN_CARD_S else min(brand_s, gap - cd)


# ---------------------------------------------------------------------------------------------------------- the opening
def opening_span(chapters: list, words: list) -> dict | None:
    """`{"start": 0.0, "dur": seconds}` of the opening shot, or None when there is none: the first word starts before 1.2 s, or the video
    starts with a title or a card (no cold open: the first picture is the beat or the card)."""
    if not chapters or not words:
        return None
    c = chapters[0]
    lead = c.get("lead")
    kind = lead.get("kind") if isinstance(lead, dict) else ("card" if c.get("card") else "plain")
    if kind != "plain":
        return None
    first = float(words[0]["s"])
    if first < OPENING_MIN_FIRST_WORD_S - EPS:
        return None
    return {"start": 0.0, "dur": first - OPENING_LEAD_S}


def whole_camera(w, h, canvas: dict | None, fit_pct: float = DEFAULT_FIT_PCT, box=None) -> list | None:
    """The two camera keys of the opening shot: the ENTIRE painting inside the frame, centred and held still. zoom = the smaller of fit-by-height and fit-by-width at `fit_pct` (the style's
    `matte.painting_height_pct`) of the canvas; None when the painting's size is not known.
    `box` (panelbox): the painted area `(x0, y0, x1, y1)` of the picture, in its pixels (`bti.media.contentbox`): the painting that is fitted and centred is
    the box, not the file (a museum photograph has a black ground round the painting); without one, or one that is not inside the picture, the whole picture."""
    if not (_num(w) and _num(h) and w > 0 and h > 0):
        return None
    c = canvas if isinstance(canvas, dict) else {}
    cw = float(c["w"]) if _num(c.get("w")) and c["w"] > 0 else 1920.0
    ch = float(c["h"]) if _num(c.get("h")) and c["h"] > 0 else 1080.0
    b = CB.clean(dict(zip(CB.FIELDS, box)), w, h) if isinstance(box, (list, tuple)) and len(box) == 4 else None
    if b is not None:
        cx, cy, z, _ = CB.whole_frame(b, fit_pct, cw, ch)
        cx, cy = round(cx, 2), round(cy, 2)
    else:
        z = min(fit_pct / 100.0 * ch / float(h), fit_pct / 100.0 * cw / float(w))
        cx, cy = round(float(w) / 2, 2), round(float(h) / 2, 2)

    def key(rel, zoom):
        return {"at": {"rel": rel}, "cx": cx, "cy": cy, "zoom": round(zoom, 5), "ease": "linear"}
    return [key(0.0, z), key(1.0, z)]


def opening_shot(asset_key: str, asset: dict | None, canvas: dict | None, fit_pct: float, base_params: dict | None) -> dict:
    """The opening shot as the compiler writes it (without `start`, which is `{"t": 0.0}`). `base_params` are the registry defaults of the
    technique (`shadow` and the rest); the camera is the whole painting."""
    params = copy.deepcopy(base_params) if isinstance(base_params, dict) else {}
    a = asset if isinstance(asset, dict) else {}
    cam = whole_camera(a.get("width"), a.get("height"), canvas, fit_pct, CB.box_of(a))          # panelbox: the box the asset carries, not the file
    if cam is not None:
        params["camera"] = cam
    return {"id": OPENING_ID, "start": {"t": 0.0}, "technique": OPENING_TECHNIQUE, "slots": {"image": {"asset": asset_key}}, "params": params,
            "intent": OPENING_INTENT, "transition_in": None, "overlays": [], "locked": False, "source": "agent", "note": OPENING_NOTE}


# ---------------------------------------------------------------------------------------------------------- the placement
def place(chapters: list, words: list, brand_s: float) -> dict:
    """Where the cards and the beat go, for each chapter of a normalized timing (`bti.draft.inputs.normalize_timing`).

    Returns `{"chapters": [{"id", "gap": [start, end] | None, "card": {"start", "dur"} | None, "title": {"start", "dur"} | None,
    "first_start": seconds | None}], "opening": {"start", "dur"} | None, "issues": [(chapter id, message)]}`. `gap` is the silence
    that holds the chapter's cards (None when the chapter has no silence of its own to show anything in); `first_start` is where the
    chapter's first shot starts when it is not the chapter's start (the cards end there). The code is the compiler's own, moved here
    unchanged except for the length of the beat."""
    out: list = []
    issues: list = []
    prev_end = 0.0
    title_done = False
    for k, c in enumerate(chapters):
        card = title = None
        gap_span = None
        first_start = None
        lead = c.get("lead")
        if lead and lead["kind"] in ("title", "card", "plain"):
            end, gap = lead["end"], lead["end"] - lead["start"]
            gap_span = [lead["start"], end]
            want_card = lead["kind"] == "card" or (lead["kind"] == "title" and c["card"])
            cd = min(CARD_S, gap) if want_card else 0.0
            if want_card and cd >= MIN_CARD_S:
                card = {"start": end - cd, "dur": cd}
            elif want_card:
                issues.append((c["id"], "the silence before the chapter is only %.1f s: no card was placed" % gap))
                cd = 0.0
            if lead["kind"] == "title" and not title_done:
                td = title_length(brand_s, gap, cd)
                if td >= MIN_CARD_S:
                    title = {"start": end - cd - td, "dur": td}
                    title_done = True
            if card or title:
                first_start = end                       # the first shot starts where the cards end
        elif c["card"]:
            if c["card_start"] is not None and c["card_end"] is not None and c["card_end"] > c["card_start"]:
                cs, cd = c["card_start"], c["card_end"] - c["card_start"]
            else:
                gap = c["start"] - prev_end
                cd = min(CARD_S, gap)
                cs = c["start"] - cd
            if cd >= MIN_CARD_S:
                gap_span = [prev_end, cs + cd]
                card = {"start": max(0.0, cs), "dur": cd}
                if not title_done and cs - TITLE_CARD_S >= prev_end + 0.2 - EPS:
                    title = {"start": cs - TITLE_CARD_S, "dur": TITLE_CARD_S}
                    title_done = True
            else:
                issues.append((c["id"], "the chapter has a card but the silence before it is only %.1f s: no card was placed" % max(0.0, c["start"] - prev_end)))
        if k == 0 and (title or card):                  # the first picture of the video starts at 0
            f = title or card
            f["dur"] += f["start"]
            f["start"] = 0.0
        out.append({"id": c["id"], "gap": gap_span, "card": card, "title": title, "first_start": first_start})
        prev_end = c["end"]
    return {"chapters": out, "opening": opening_span(chapters, words), "issues": issues}
