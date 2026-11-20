"""The two files the agent writes in its work folder, and what makes them valid.

    out/plan.json     part 1 (plan): what should be on screen for each narration line
    out/choice.json   part 3 (choose): which candidate picture fits each wanted picture, and what becomes of each proposed box

`bti.picks.auto.helper` (`./check` in the work folder) and the job use the same functions, so the agent is told exactly what the
program will accept. Every message is one plain English sentence that names the place in the file (`lines[3] (b0007)`) and what
to change; the agent reads them, so they are written to be acted on.

Three kinds of finding, kept apart on purpose:
  errors    the file cannot be used until they are fixed (the agent gets one repair round, then the part fails)
  notes     what the program will change by itself, by a rule (a second clip in a chapter is dropped, a clip is cut to 4..10 s)
  warnings  something worth a look that never blocks (the same framing for more than about half a minute)

The plan (`bti.picks.plan/1`):

    {"schema": "bti.picks.plan/1",
     "regions": [{"name": "HEAD", "box": [x0, y0, x1, y1], "what": "<a few words, Vietnamese>"}],
     "lines": [{"beat": "b0001", "reason": "<one short sentence, Vietnamese>", "kinds": ["outside"],
                "show": [{"type": "whole"},
                         {"type": "detail", "region": "HEAD"},
                         {"type": "context", "search": "english words", "alt": ["other words"], "kind": "portrait", "entity": "Philip the Good",
                          "period": "then", "what": "<what it should show, Vietnamese>"},
                         {"type": "map", "places": ["Lübeck, Germany", "Bruges, Belgium"], "what": "..."},
                         {"type": "clip", "search": "english words", "what": "...", "seconds": 6}],
                "fallback": {"type": "detail", "region": "HEAD"}}]}

`kinds` (required on every line; one or two of `KINDS`, in the order the line speaks) says what the line does, and the program checks that the pictures
asked for are the ones that kind needs (`kind_problems`): an `outside` line asks for a picture of the thing itself and names a `fallback` (a `whole` or
`detail` item shown when nothing is found), a map belongs only to a `journey` and names two or more `places`, a `compare` asks for the other work, and so on.
A plan saved before `kinds` existed is still read by the writing part (`write.py`) and the wants (`wants_of`): they take what is there.

`box` is in fractions of the painting (0 = left or top edge, 1 = right or bottom edge), so it does not depend on how the picture was
scaled. A line with `"show": []` needs nothing new. The choice (`bti.picks.choice/1`):

    {"schema": "bti.picks.choice/1",
     "wants": [{"id": "b0006.2", "pick": 3 | "B2" | null, "reason": "<one short sentence, Vietnamese>"}],
     "regions": [{"name": "HEAD", "action": "keep" | "adjust" | "drop", "box": [x0, y0, x1, y1], "reason": "..."}]}
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bti.picks import doc as pdoc

PLAN_SCHEMA = "bti.picks.plan/1"
CHOICE_SCHEMA = "bti.picks.choice/1"
MAX_FILE_BYTES = 1_000_000

TYPES = ("whole", "detail", "context", "map", "clip")
CONTEXT_KINDS = ("work", "portrait", "document", "photo", "place", "object", "event", "other")
PERIODS = ("then", "now")        # `then`: a picture made in the time the line speaks of; `now`: a photograph of today is right
DEFAULT_PERIOD = "then"
KINDS = pdoc.LINE_KINDS          # what a line does: the one list the plan, the picks document and the operations share
MAX_KINDS = pdoc.MAX_KINDS
MAX_PLACES = 6                   # names on the map of a journey
ACTIONS = ("keep", "adjust", "drop")

MAX_ITEMS = 3                    # pictures on one narration line
MAX_REGIONS = 20                 # regions the plan may add to the main painting (the choosing session looks at each one)
MAX_WANTS = 60                   # pictures a plan may ask for from elsewhere (context, map, clip): the choosing session looks at a sheet for each
                                 # (30 until 2026-11-20: a line about something outside the painting now always asks for its picture, see KINDS)
MAX_ALT = 2                      # alternative search words of a context picture
CLIPS_PER_CHAPTER = 1            # the owner's decision (2026-11-18)
CLIP_SECONDS = (4.0, 10.0)
DEFAULT_CLIP_SECONDS = 6.0
FRAMING_SECONDS = 30.0           # the same framing is not held longer than about this much narration
WORDS_PER_SECOND = 2.41          # the measured rate of the narrator's voice (docs/APP_GUIDE.md)
BOX_TOLERANCE = 0.01             # a box this much outside the picture is clamped; further out is an error
MIN_BOX_SIDE = 0.02              # a box thinner than 2% of the picture cannot show anything
MAX_BOX_AREA = 0.9               # a box over 90% of the picture is the whole painting
REASON_MAX = 300
VIETNAMESE = re.compile("[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
WHAT_MAX = 160
NAME_RE = re.compile(r"[A-Z][A-Z0-9_]{0,23}")
BOOK_PICK_RE = re.compile(r"[Bb](\d{1,3})")


# ---------------------------------------------------------------------------------------------------------------- the report
@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    value: dict | None = None          # the normalised document, only when there is no error

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        """What `./check` prints, and what the repair message carries."""
        lines = ["ERROR " + e for e in self.errors] + ["NOTE " + n for n in self.notes] + ["WARNING " + w for w in self.warnings]
        lines.append("%d error(s), %d note(s), %d warning(s)" % (len(self.errors), len(self.notes), len(self.warnings)))
        return "\n".join(lines)

    def problems(self) -> str | None:
        """The text the repair message carries, or None when the file is usable."""
        return None if self.ok else self.text()


def read_json_file(path: Path, what: str) -> tuple[Any, str | None]:
    """`(document, None)`, or `(None, problem)`. A link, a missing file, a file that is too big or not JSON is a problem, never followed."""
    p = Path(path)
    if p.is_symlink():
        return None, "%s is a link: write a real file" % what
    if not p.is_file():
        return None, "%s is missing: write it (see TASK.md for its shape)" % what
    try:
        if p.stat().st_size > MAX_FILE_BYTES:
            return None, "%s is bigger than %d bytes: write a shorter file" % (what, MAX_FILE_BYTES)
        return json.loads(p.read_text(encoding="utf-8")), None
    except UnicodeDecodeError:
        return None, "%s is not UTF-8 text" % what
    except ValueError as e:
        return None, "%s is not valid JSON (%s)" % (what, str(e)[:100])
    except OSError as e:
        return None, "%s cannot be read (%s)" % (what, type(e).__name__)


# ---------------------------------------------------------------------------------------------------------------- boxes
def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def clean_box(box: Any, where: str) -> tuple[list[float] | None, str | None]:
    """`([x0, y0, x1, y1], None)` for a usable box (fractions of the painting, a hair outside is clamped), else `(None, the problem)`."""
    if not (isinstance(box, (list, tuple)) and len(box) == 4 and all(_num(v) for v in box)):
        return None, "%s: box must be four numbers [x0, y0, x1, y1], fractions of the painting from 0 to 1" % where
    x0, y0, x1, y1 = (float(v) for v in box)
    if min(x0, y0, x1, y1) < -BOX_TOLERANCE or max(x0, y0, x1, y1) > 1 + BOX_TOLERANCE:
        return None, ("%s: box %s lies outside the painting; every number must be between 0 and 1 (0 is the left or top edge, 1 the right "
                      "or bottom edge)" % (where, [round(v, 3) for v in (x0, y0, x1, y1)]))
    x0, y0, x1, y1 = (min(1.0, max(0.0, v)) for v in (x0, y0, x1, y1))
    if x1 - x0 < MIN_BOX_SIDE or y1 - y0 < MIN_BOX_SIDE:
        return None, "%s: box is too small to show anything (each side must be at least %.2f of the painting) or is upside down (x0 < x1, y0 < y1)" % (where, MIN_BOX_SIDE)
    if (x1 - x0) * (y1 - y0) > MAX_BOX_AREA:
        return None, "%s: box covers almost the whole painting; use {\"type\": \"whole\"} instead of a detail" % where
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)], None


def box_to_region(box: list[float], width: int, height: int) -> dict:
    """The region of `bti.picks` (a centre and two radii, in pixels of the stored picture) whose bounding box is `box`."""
    x0, y0, x1, y1 = box
    x, y = (x0 + x1) / 2 * width, (y0 + y1) / 2 * height
    rx, ry = max(1.0, (x1 - x0) / 2 * width), max(1.0, (y1 - y0) / 2 * height)
    return {"x": int(round(x)), "y": int(round(y)), "rx": int(round(rx)), "ry": int(round(ry))}


def region_to_box(region: dict, width: int, height: int) -> list[float] | None:
    """The box a stored region covers, in fractions; None for a point (no radius) or a picture of unknown size."""
    try:
        if not (width > 0 and height > 0 and _num(region.get("x")) and _num(region.get("y")) and _num(region.get("rx")) and region["rx"] > 0):
            return None
        ry = region.get("ry") if _num(region.get("ry")) and region["ry"] > 0 else region["rx"]
        x0, x1 = (region["x"] - region["rx"]) / width, (region["x"] + region["rx"]) / width
        y0, y1 = (region["y"] - ry) / height, (region["y"] + ry) / height
        x0, y0, x1, y1 = (min(1.0, max(0.0, v)) for v in (x0, y0, x1, y1))
        return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)] if x1 > x0 and y1 > y0 else None
    except (TypeError, KeyError):
        return None


def crop_pixels(box: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = box
    px0, py0 = int(math.floor(x0 * width)), int(math.floor(y0 * height))
    px1, py1 = int(math.ceil(x1 * width)), int(math.ceil(y1 * height))
    return max(0, px0), max(0, py0), min(width, max(px0 + 1, px1)), min(height, max(py0 + 1, py1))


def region_name(raw: str, taken: set[str]) -> str:
    """A region name for the picks document from the agent's own: capitals, digits and `_`, never one that is taken."""
    base = re.sub(r"[^A-Z0-9_]+", "_", str(raw or "").upper()).strip("_")[:24] or "VUNG"
    if not re.fullmatch(r"[A-Z0-9_]+", base):
        base = "VUNG"
    if base not in taken:
        return base
    for n in range(2, 1000):
        cand = "%s_%d" % (base[:20], n)
        if cand not in taken:
            return cand
    return base


# ---------------------------------------------------------------------------------------------------------------- the plan
@dataclass
class PlanCtx:
    """What the plan is checked against: the narration lines, which of them the plan must cover, and the regions the painting already has."""
    beats: list[dict]                                   # every line in narration order: {"id", "chapter", "words"}
    targets: list[str]                                  # the lines the plan must cover
    existing_regions: dict = field(default_factory=dict)   # NAME -> [x0, y0, x1, y1] of the regions the main painting already has
    chapters: dict = field(default_factory=dict)        # beat id -> chapter id (same as `beats`, kept for quick lookups)
    painting_title: str = ""

    def __post_init__(self):
        self.chapters = {b["id"]: b.get("chapter") for b in self.beats}
        self.words = {b["id"]: int(b.get("words") or 0) for b in self.beats}

    def to_json(self) -> dict:
        return {"beats": self.beats, "targets": self.targets, "existing_regions": self.existing_regions,
                "painting_title": self.painting_title}

    @classmethod
    def from_json(cls, d: dict) -> "PlanCtx":
        return cls(beats=list(d.get("beats") or []), targets=list(d.get("targets") or []),
                   existing_regions={k: list(v) for k, v in (d.get("existing_regions") or {}).items()},
                   painting_title=str(d.get("painting_title") or ""))


def _text(v: Any, lo: int, hi: int) -> str | None:
    if not isinstance(v, str):
        return None
    s = " ".join(v.split())
    return s if lo <= len(s) <= hi else None


def _vietnamese(s: str) -> bool:
    """Does a sentence the owner will read look like Vietnamese? (Every Vietnamese sentence of a few words has a letter with a mark.)"""
    return bool(VIETNAMESE.search(s))


def _short(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _clean_wider(raw: Any, where: str, painting_title: str, errors: list) -> list[dict] | None:
    """Check and normalise `wider`: at most two wider searches (step 2, then step 3 with kind 'object')."""
    if raw is None:
        return None
    if not isinstance(raw, list) or not (1 <= len(raw) <= 2):
        errors.append("%s: `wider` must be a list of 1 or 2 wider searches [wider_shape]" % where)
        return None
    out = []
    pt = painting_title.strip().lower() if len(painting_title.strip()) >= 3 else ""
    for idx, step_item in enumerate(raw):
        swhere = "%s.wider[%d]" % (where, idx)
        if not isinstance(step_item, dict):
            errors.append("%s must be an object with step, search, kind and what [wider_shape]" % swhere)
            continue
        expected_step = idx + 2
        step_val = step_item.get("step")
        if step_val != expected_step:
            errors.append("%s: wider step must have \"step\": %d [wider_step]" % (swhere, expected_step))
        skind = step_item.get("kind")
        if expected_step == 3:
            if skind != "object":
                errors.append("%s: step 3 must have kind \"object\" (a real surviving object of the same kind in a museum) [wider_kind]" % swhere)
        else:
            if skind not in CONTEXT_KINDS:
                errors.append("%s: kind %r is not one of %s [wider_kind]" % (swhere, str(skind)[:30], ", ".join(CONTEXT_KINDS)))
        ssearch = _text(step_item.get("search"), 3, 120)
        if ssearch is None:
            errors.append("%s: `search` must be 3 to 120 characters of search words [wider_search]" % swhere)
        elif pt and pt in ssearch.lower():
            errors.append("%s: search words must not contain the main painting's title (%r) [wider_painting_title]" % (swhere, painting_title))
        swhat = _text(step_item.get("what"), 3, WHAT_MAX + 80)
        if swhat is None:
            errors.append("%s: `what` must say in a few words what the picture should show (3 to %d characters) [wider_what]" % (swhere, WHAT_MAX))
        if step_val == expected_step and ssearch and swhat and (skind == "object" if expected_step == 3 else skind in CONTEXT_KINDS):
            out.append({"step": expected_step, "search": ssearch, "kind": skind, "what": _short(swhat, WHAT_MAX)})
    return out if len(out) == len(raw) else None


def _item(it: Any, where: str, regions: dict, errors: list, notes: list, painting_title: str = "") -> dict | None:
    if not isinstance(it, dict):
        errors.append("%s must be an object like {\"type\": \"whole\"}" % where)
        return None
    kind = it.get("type")
    if kind not in TYPES:
        errors.append("%s: type %r is not one of %s" % (where, str(kind)[:30], ", ".join(TYPES)))
        return None
    if kind == "whole":
        return {"type": "whole"}
    if kind == "detail":
        name = it.get("region")
        if not isinstance(name, str) or name not in regions:
            errors.append("%s: region %r is not declared in `regions` and is not a region the painting already has (%s)"
                          % (where, str(name)[:30], ", ".join(sorted(regions)[:12]) or "none"))
            return None
        return {"type": "detail", "region": name}
    if kind == "context":
        search = _text(it.get("search"), 3, 120)
        what = _text(it.get("what"), 3, WHAT_MAX + 80)
        if search is None:
            errors.append("%s: `search` must be 3 to 120 characters of search words (English words work best on Wikimedia Commons)" % where)
        else:
            pt = painting_title.strip().lower() if len(painting_title.strip()) >= 3 else ""
            if pt and pt in search.lower():
                errors.append("%s: search words must not contain the main painting's title (%r)" % (where, painting_title))
        if what is None:
            errors.append("%s: `what` must say, in a few words, what the picture should show (3 to %d characters)" % (where, WHAT_MAX))
        kind_of = it.get("kind", "other")
        if kind_of not in CONTEXT_KINDS:
            errors.append("%s: kind %r is not one of %s" % (where, str(kind_of)[:30], ", ".join(CONTEXT_KINDS)))
        alts_raw = it.get("alt", [])
        alts: list[str] = []
        if alts_raw is not None and not isinstance(alts_raw, list):
            errors.append("%s: `alt` must be a list of other search words (at most %d)" % (where, MAX_ALT))
        else:
            for a in alts_raw or []:
                s = _text(a, 3, 120)
                if s is None:
                    errors.append("%s: every entry of `alt` must be 3 to 120 characters of search words" % where)
                elif s.lower() != (search or "").lower() and s not in alts:
                    alts.append(s)
            if len(alts) > MAX_ALT:
                notes.append("%s: only the first %d alternatives of `alt` are searched" % (where, MAX_ALT))
                alts = alts[:MAX_ALT]
        entity = None
        if it.get("entity") is not None:
            entity = _text(it.get("entity"), 2, 120)
            if entity is None:
                errors.append("%s: `entity` must be the name under which an encyclopedia knows the thing (\"Philip the Good\", \"Noyon Cathedral\"), 2 to 120 characters" % where)
        period = it.get("period", DEFAULT_PERIOD)
        if period not in PERIODS:
            errors.append("%s: `period` must be \"then\" (a picture made in the time the line speaks of) or \"now\" (a photograph of today is right), not %r" % (where, str(period)[:30]))
        wider_raw = it.get("wider")
        wider = _clean_wider(wider_raw, where, painting_title, errors) if wider_raw is not None else None
        if search is None or what is None or kind_of not in CONTEXT_KINDS or period not in PERIODS or (it.get("entity") is not None and entity is None) or (wider_raw is not None and wider is None):
            return None
        out = {"type": "context", "search": search, "alt": alts, "kind": kind_of, "what": _short(what, WHAT_MAX), "period": period}
        if entity:
            out["entity"] = entity
        if wider:
            out["wider"] = wider
        return out
    if kind == "map":
        raw_places = it.get("places")
        if raw_places is None and it.get("place") is not None:
            raw_places = [it.get("place")]                       # a plan made before `places` existed
        if not isinstance(raw_places, list) or not raw_places or len(raw_places) > MAX_PLACES:
            errors.append("%s: `places` must be a list of 1 to %d place names, each with its country (for example [\"Lübeck, Germany\", \"Bruges, Belgium\"])"
                          % (where, MAX_PLACES))
            return None
        places = []
        for pl in raw_places:
            name = _text(pl, 2, 80)
            if name is None:
                errors.append("%s: every entry of `places` must be the name of a place, 2 to 80 characters (for example \"Oslo, Norway\")" % where)
                return None
            if name not in places:
                places.append(name)
        what = _text(it.get("what"), 2, WHAT_MAX + 80) or ("Bản đồ " + ", ".join(places[:3]))
        return {"type": "map", "place": places[0], "places": places, "what": _short(what, WHAT_MAX)}       # `place` stays: the map search reads it
    # clip
    search = _text(it.get("search"), 3, 120)
    what = _text(it.get("what"), 3, WHAT_MAX + 80)
    if search is None:
        errors.append("%s: a clip needs `search`, 3 to 120 characters of search words" % where)
    if what is None:
        errors.append("%s: a clip needs `what`, a few words on what the clip should show" % where)
    sec = it.get("seconds", DEFAULT_CLIP_SECONDS)
    if not _num(sec):
        errors.append("%s: `seconds` must be a number (4 to 10)" % where)
        sec = DEFAULT_CLIP_SECONDS
    if search is None or what is None:
        return None
    if not CLIP_SECONDS[0] <= float(sec) <= CLIP_SECONDS[1]:
        fixed = min(CLIP_SECONDS[1], max(CLIP_SECONDS[0], float(sec)))
        notes.append("%s: a clip lasts 4 to 10 seconds, so %g s becomes %g s" % (where, float(sec), fixed))
        sec = fixed
    return {"type": "clip", "search": search, "what": _short(what, WHAT_MAX), "seconds": float(sec)}


# ---------------------------------------------------------------------------------------------------------------- what each kind of line must ask for
# kind -> (what the line does, what it must ask for): the table of the plan template (skills/picks_auto/PLAN.template.md) in the same words
KIND_TABLE = {
    "detail": ("points at a thing that is in the painting", "a `detail` item"),
    "whole": ("speaks of the painting as one object (its date, its size, where it hangs, its fate)", "a `whole` item"),
    "outside": ("is about a person, a place, an object, an event or a custom that is NOT in the painting",
                "at least one `context` (or `clip`) item, and a line-level `fallback` (a `detail` or `whole` item shown when nothing is found)"),
    "compare": ("sets the painting or one detail beside another work", "a `context` item of kind `work` and a `detail` or `whole` item"),
    "journey": ("is about a movement or a tie between two or more places", "a `map` item with `places` (two or more names)"),
    "dates": ("gives three or more dated events of one story", "a `detail` or `whole` item (the storyboard adds the time axis)"),
    "figure": ("has a quantity as its point", "the picture of the thing counted: a `context` item when it is outside the painting, else a `detail`"),
    "inscription": ("reads words that are visible in the picture", "a `detail` item on the words"),
    "construction": ("explains how the picture is built (perspective, geometry, a visible technique)", "a `detail` or `whole` item"),
    "relations": ("ties three or more people together (family, patrons)", "a `detail`, `whole` or `context` item"),
    "idea": ("gives a reading or an opinion that no picture can show", "a `detail` or `whole` item"),
}
CONTEXT_ITEM = '{"type": "context", "search": "<the thing and what sort of picture>", "entity": "<its name>", "period": "then", "kind": %s, "what": "<Vietnamese>"}'
DETAIL_ITEM = '{"type": "detail", "region": "<NAME>"}'
FALLBACK_ITEM = '"fallback": {"type": "whole"} (or {"type": "detail", "region": "<NAME>"} for the part of the painting nearest to what the line says)'
CODES_OF_KINDS = ("kinds_missing", "kinds_shape", "kinds_unknown", "kinds_too_many", "kinds_repeated", "outside_only_painting", "outside_no_fallback",
                  "map_without_journey", "journey_no_map", "journey_one_place", "compare_no_work", "compare_no_painting", "kind_needs_painting",
                  "figure_no_picture", "context_without_kind", "fallback_bad", "wider_missing")


def kind_words() -> str:
    return ", ".join(KINDS)


def kinds_problem(raw: Any, where: str) -> tuple[list[str] | None, str | None]:
    """`(kinds, None)` for a usable `kinds` of one line, else `(None, the sentence that says what to write)`. A line without `kinds` is not reported here
    (the plan check lists those together)."""
    if not isinstance(raw, list) or not raw:
        return None, ("%s: `kinds` must be a list of one or two words saying what the line does, from: %s; for example \"kinds\": [\"detail\"] [kinds_shape]"
                      % (where, kind_words()))
    if len(raw) > MAX_KINDS:
        return None, ("%s: `kinds` has %d words; a line has one or two (in the order it speaks). Keep the one or two that matter most, and give the other things the "
                      "line says no picture of their own [kinds_too_many]" % (where, len(raw)))
    bad = [str(k)[:30] for k in raw if k not in KINDS]
    if bad:
        return None, "%s: kind %s is not one of: %s [kinds_unknown]" % (where, ", ".join(repr(b) for b in bad), kind_words())
    if len(set(raw)) != len(raw):
        return None, "%s: `kinds` names %r twice; write each thing the line does once [kinds_repeated]" % (where, raw[0])
    return list(raw), None


def kind_problems(kinds: list[str], show: list[dict], fallback: dict | None, where: str) -> list[str]:
    """What is wrong between a line's `kinds` and the pictures it asks for, one sentence per rule, each saying exactly what to add. `show` and `fallback` are
    the normalised items (no error in them). The rules are the table `KIND_TABLE`."""
    out: list[str] = []
    types = [i["type"] for i in show]
    contexts = [i for i in show if i["type"] == "context"]
    clips = [i for i in show if i["type"] == "clip"]
    maps = [(n, i) for n, i in enumerate(show) if i["type"] == "map"]
    has_detail, has_whole = "detail" in types, "whole" in types
    if "outside" in kinds:
        if not contexts and not clips:
            painting = has_detail or has_whole
            what_it_shows = ("only the painting and a map (a map is not the picture of a place that is merely mentioned)" if maps and painting else
                             "only a map (a map is not the picture of a place that is merely mentioned)" if maps else
                             "only the painting" if types else "nothing new (`\"show\": []`)")
            out.append("%s: kinds says \"outside\", so the line must ask for a picture of the thing itself, but it shows %s. Add %s to `show` (or a clip of "
                       "the thing); if the line is really about something in the painting, change kinds to \"detail\" or \"whole\" [outside_only_painting]"
                       % (where, what_it_shows, CONTEXT_ITEM % '"<portrait|place|object|event|work|document|photo>"'))
        if fallback is None:
            out.append("%s: an \"outside\" line needs a line-level `fallback`, the picture of the painting that is shown when nothing is found for the line. Add %s [outside_no_fallback]"
                       % (where, FALLBACK_ITEM))
        for n, c in enumerate(contexts):
            period = c.get("period", DEFAULT_PERIOD)
            ckind = c.get("kind", "other")
            needs_wider = (period == "then" and ckind in ("document", "object"))
            if needs_wider and not c.get("wider"):
                out.append("%s.show[%d]: a line about %s from that period needs `wider` (two steps to search before falling back to the painting: "
                           "step 2 for the same kind of thing from the period, step 3 for a surviving object in a museum) [wider_missing]"
                           % (where, n, ckind))
    if "journey" in kinds:
        if not maps:
            out.append("%s: kinds says \"journey\" but the line asks for no map. Add {\"type\": \"map\", \"places\": [\"<place A, country>\", \"<place B, country>\"], "
                       "\"what\": \"<Vietnamese>\"} to `show`, or change kinds [journey_no_map]" % where)
        for n, m in maps:
            if len(m["places"]) < 2:
                out.append("%s.show[%d]: the map of a \"journey\" needs two or more names in `places` and this one has %d (%s). Give the places the line moves between "
                           "or ties together, each with its country (\"Lübeck, Germany\", \"Bruges, Belgium\"); one place is not a journey [journey_one_place]"
                           % (where, n, len(m["places"]), m["places"][0]))
    elif maps:
        n = maps[0][0]
        out.append("%s.show[%d]: a map belongs only to a line about a journey or a tie between two or more places, and kinds says %s, not \"journey\". For a place that is "
                   "merely mentioned (\"born at Limoges\", \"Bruges was the commercial capital\") ask for a view of the place instead: %s with kinds \"outside\". If "
                   "the line does move between places, put \"journey\" in kinds and give the map two or more `places` [map_without_journey]"
                   % (where, n, ", ".join(repr(k) for k in kinds), CONTEXT_ITEM % '"<place>"'))
    if "compare" in kinds:
        if not any(c["kind"] == "work" for c in contexts):
            out.append("%s: kinds says \"compare\" but the line asks for no other work. Add %s next to the painting, with the other work's title and painter in `search` "
                       "[compare_no_work]" % (where, CONTEXT_ITEM % '"work"'))
        if not (has_detail or has_whole):
            out.append("%s: kinds says \"compare\" but the line shows no part of this painting beside the other work. Add %s or {\"type\": \"whole\"} to `show` "
                       "[compare_no_painting]" % (where, DETAIL_ITEM))
    if show:                                                    # `"show": []` keeps the picture before it: only the kinds that need a picture are asked for one
        for k, ok, add in (("detail", has_detail, DETAIL_ITEM + " (declare its box in `regions`)"),
                           ("whole", has_whole, '{"type": "whole"}'),
                           ("dates", has_detail or has_whole, DETAIL_ITEM + " or {\"type\": \"whole\"}"),
                           ("inscription", has_detail, DETAIL_ITEM + " on the words (declare its box in `regions`)"),
                           ("construction", has_detail or has_whole, DETAIL_ITEM + " or {\"type\": \"whole\"}"),
                           ("idea", has_detail or has_whole, DETAIL_ITEM + " or {\"type\": \"whole\"}"),
                           ("relations", has_detail or has_whole or bool(contexts), DETAIL_ITEM + ", {\"type\": \"whole\"} or a context picture")):
            if k in kinds and not ok:
                out.append("%s: kinds says \"%s\" (the line %s) but its pictures do not match: add %s to `show`, or change kinds to what the line really does [kind_needs_painting]"
                           % (where, k, KIND_TABLE[k][0], add))
    if "figure" in kinds and not (contexts or clips or has_detail):
        out.append("%s: kinds says \"figure\", so the line must show the thing that is counted. Add %s when the thing is outside the painting, else %s [figure_no_picture]"
                   % (where, CONTEXT_ITEM % '"<photo|object|place|event>"', DETAIL_ITEM))
    if (contexts or clips) and not {"outside", "compare", "figure", "relations"} & set(kinds):
        out.append("%s: the line asks for a picture from elsewhere (%s) but kinds says %s. Put \"outside\" in kinds (and name a `fallback`), or \"compare\" when it is "
                   "another work set beside this one, or take the picture out of `show` [context_without_kind]"
                   % (where, "a context picture" if contexts else "a clip", ", ".join(repr(k) for k in kinds)))
    return out


def _fallback(raw: Any, where: str, regions: dict, errors: list, painting_title: str = "") -> dict | None:
    """The line-level `fallback`: one item, `whole` or `detail`, shown when the picture asked for is not found. None when it is not given or not usable."""
    if raw is None:
        return None
    if isinstance(raw, list) and len(raw) == 1:
        raw = raw[0]
    if not (isinstance(raw, dict) and raw.get("type") in ("whole", "detail")):
        errors.append("%s: `fallback` must be one item, {\"type\": \"whole\"} or {\"type\": \"detail\", \"region\": \"NAME\"}: the part of the painting shown when nothing is "
                      "found for the line [fallback_bad]" % where)
        return None
    n = len(errors)
    got = _item(raw, where + ".fallback", regions, errors, [], painting_title=painting_title)
    return got if len(errors) == n else None


def apply_clip_rule(lines: list[dict], chapters: dict) -> list[str]:
    """The rule of the owner's decision, applied in place: a clip only on a context line (a line that shows neither the whole painting nor
    a detail of it), and at most one clip per chapter (the first one in the narration). Returns one sentence per clip dropped."""
    cuts: list[str] = []
    used: set = set()
    for ln in lines:
        clips = [i for i in ln["show"] if i["type"] == "clip"]
        if not clips:
            continue
        painting_line = any(i["type"] in ("whole", "detail") for i in ln["show"])
        chap = chapters.get(ln["beat"])
        keep = []
        for it in ln["show"]:
            if it["type"] != "clip":
                keep.append(it)
            elif painting_line:
                cuts.append("line %s: the clip was dropped because the line shows the painting itself (a clip belongs on a context line)" % ln["beat"])
            elif chap in used:
                cuts.append("line %s: the clip was dropped because chapter %s already has one (one clip per chapter)" % (ln["beat"], chap))
            else:
                used.add(chap)
                keep.append(it)
        ln["show"] = keep
    return cuts


def framing_key(item: dict, beat: str, n: int) -> str:
    if item["type"] == "whole":
        return "whole"
    if item["type"] == "detail":
        return "detail:" + item["region"]
    return "%s:%s:%d" % (item["type"], beat, n)         # a picture from elsewhere is a framing of its own


def pacing_warnings(lines: list[dict], ctx: PlanCtx) -> list[str]:
    """Runs of consecutive lines whose framing stays the same (`keep` lines continue the one before) for more than about half a minute."""
    out: list[str] = []
    by = {ln["beat"]: ln for ln in lines}
    run: list[str] = []
    cur: str | None = None
    secs = 0.0

    def close():
        nonlocal run, cur, secs
        if len(run) >= 2 and secs > FRAMING_SECONDS:
            out.append("lines %s to %s (about %d seconds of narration) keep the same framing (%s): give one of them another detail, a context picture, or the "
                       "whole painting after a detail" % (run[0], run[-1], round(secs), (cur or "").replace("detail:", "detail ")))
        run, cur, secs = [], None, 0.0

    for b in ctx.beats:
        ln = by.get(b["id"])
        if ln is None:                                   # a line that is not yours (it has pictures of its own) breaks the run
            close()
            continue
        keys = tuple(framing_key(i, b["id"], n) for n, i in enumerate(ln["show"]))
        key = "|".join(keys) if keys else None           # None: nothing new, the previous framing stays
        if key is not None and (cur is None or key != cur):
            close()
            cur = key
        if key is None and cur is None:
            cur = "the painting as it was"
        run.append(b["id"])
        secs += ctx.words.get(b["id"], 0) / WORDS_PER_SECOND
    close()
    return out


def check_plan(obj: Any, ctx: PlanCtx) -> Report:
    """Check a decoded `out/plan.json` against the narration lines of this job. The returned `value` is the plan with the rules applied."""
    rep = Report()
    err, notes = rep.errors, rep.notes
    if not isinstance(obj, dict):
        err.append("the plan must be one JSON object with `regions` and `lines`")
        return rep
    if obj.get("schema") not in (None, PLAN_SCHEMA):
        err.append("schema must be %r (or left out)" % PLAN_SCHEMA)
    regions: dict[str, dict] = {}
    raw_regions = obj.get("regions", [])
    if not isinstance(raw_regions, list):
        err.append("`regions` must be a list of {name, box, what}")
        raw_regions = []
    if len(raw_regions) > MAX_REGIONS:
        err.append("`regions` has %d entries; at most %d" % (len(raw_regions), MAX_REGIONS))
    for k, r in enumerate(raw_regions[:MAX_REGIONS]):
        where = "regions[%d]" % k
        if not isinstance(r, dict):
            err.append("%s must be {name, box, what}" % where)
            continue
        name = r.get("name")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            err.append("%s: name %r must be capital letters, digits and _ only, starting with a letter, at most 24 characters (for example HEAD)" % (where, str(name)[:30]))
            continue
        where = "regions[%d] (%s)" % (k, name)
        if name in regions:
            err.append("%s: the name is used twice" % where)
            continue
        if name in ctx.existing_regions:
            err.append("%s: the painting already has a region with this name; use it in a line without declaring it, or pick another name" % where)
            continue
        box, problem = clean_box(r.get("box"), where)
        what = _text(r.get("what"), 2, WHAT_MAX + 80)
        if problem:
            err.append(problem)
        if what is None:
            err.append("%s: `what` must say in a few words what the box shows" % where)
        if box is not None and what is not None:
            regions[name] = {"box": box, "what": _short(what, WHAT_MAX)}
    known = {**{n: {"box": b, "what": ""} for n, b in ctx.existing_regions.items()}, **regions}

    raw_lines = obj.get("lines")
    if not isinstance(raw_lines, list):
        err.append("`lines` must be a list with one entry for every line you must cover")
        return rep
    target_set = set(ctx.targets)
    seen: dict[str, dict] = {}
    no_kinds: list[str] = []                                     # lines that left `kinds` out, listed in one sentence
    judged: dict[str, tuple[str, int]] = {}                      # line -> (where, how many pictures it asked for) of the lines whose kinds were compared with their pictures
    for k, ln in enumerate(raw_lines):
        where = "lines[%d]" % k
        if not isinstance(ln, dict):
            err.append("%s must be {beat, reason, show}" % where)
            continue
        bid = ln.get("beat")
        if not isinstance(bid, str) or bid not in target_set:
            err.append("%s: beat %r is not one of the lines you must cover (see inputs/narration.json, `target: true`)" % (where, str(bid)[:20]))
            continue
        where = "lines[%d] (%s)" % (k, bid)
        if bid in seen:
            err.append("%s: this line is written twice" % where)
            continue
        reason = _text(ln.get("reason"), 3, REASON_MAX * 2)
        if reason is None:
            err.append("%s: `reason` must be one short sentence saying why this is on screen (Vietnamese)" % where)
            reason = ""
        elif not _vietnamese(reason):
            err.append("%s: `reason` must be written in Vietnamese, with its accents (the owner reads it); it says %r" % (where, reason[:60]))
        elif len(reason) > REASON_MAX:
            notes.append("%s: the reason is cut to %d characters" % (where, REASON_MAX))
            reason = _short(reason, REASON_MAX)
        show_raw = ln.get("show")
        if not isinstance(show_raw, list):
            err.append("%s: `show` must be a list (an empty list means nothing new is needed)" % where)
            continue
        if len(show_raw) > MAX_ITEMS:
            err.append("%s: `show` has %d pictures; a line shows at most %d" % (where, len(show_raw), MAX_ITEMS))
            continue
        n_before = len(err)
        items: list[dict] = []
        for n, it in enumerate(show_raw):
            got = _item(it, "%s.show[%d]" % (where, n), known, err, notes, painting_title=ctx.painting_title)
            if got is None:
                continue
            if got in items:
                notes.append("%s.show[%d]: the same picture twice in a line; the second one is dropped" % (where, n))
                continue
            items.append(got)
        fallback = _fallback(ln.get("fallback"), where, known, err, painting_title=ctx.painting_title) if "fallback" in ln else None
        kinds = None
        if ln.get("kinds") is None:
            no_kinds.append(bid)
        else:
            kinds, problem = kinds_problem(ln.get("kinds"), where)
            if problem:
                err.append(problem)
        sound = len(err) == n_before
        if kinds and sound:                                      # the pictures are only compared with the kinds when each of them is sound by itself
            err.extend(kind_problems(kinds, items, fallback, where))
        if kinds and sound:
            judged[bid] = (where, len(items))
        seen[bid] = {"beat": bid, "reason": reason, "kinds": kinds or [], "show": items, **({"fallback": fallback} if fallback else {})}
    asked = sum(1 for ln in seen.values() for i in ln["show"] if i["type"] in ("context", "map", "clip"))
    if asked > MAX_WANTS:
        err.append("the plan asks for %d pictures from elsewhere (context, map, clip); ask for at most %d: a line about something outside the painting asks for its picture, "
                   "but a line about the painting itself, an idea or a date needs none" % (asked, MAX_WANTS))
    if no_kinds:
        more = " and %d more" % (len(no_kinds) - 20) if len(no_kinds) > 20 else ""
        err.append("%d line(s) have no `kinds`: %s%s. Every line says what it does with one or two words of: %s (see the table in TASK.md); for example "
                   "`\"kinds\": [\"detail\"]`, and a line about something outside the painting `\"kinds\": [\"outside\"]` with a `context` picture and a `fallback` [kinds_missing]"
                   % (len(no_kinds), ", ".join(no_kinds[:20]), more, kind_words()))
    missing = [b for b in ctx.targets if b not in seen]
    if missing:
        more = " and %d more" % (len(missing) - 12) if len(missing) > 12 else ""
        err.append("these lines have no entry in `lines`: %s%s (give a line `\"show\": []` when it needs nothing new)" % (", ".join(missing[:12]), more))
    if err:
        return rep
    lines = [seen[b] for b in ctx.targets]                # ctx.targets is in narration order
    notes.extend(apply_clip_rule(lines, ctx.chapters))
    for ln in lines:                                             # a clip the rule took out may have been the only picture an `outside` line asked for
        where, asked_n = judged.get(ln["beat"], (None, 0))
        if where and len(ln["show"]) != asked_n:
            err.extend(kind_problems(ln["kinds"], ln["show"], ln.get("fallback"), where + " after the clip rule"))
    if err:
        return rep
    used = {i["region"] for ln in lines for i in ln["show"] + ([ln["fallback"]] if ln.get("fallback") else []) if i["type"] == "detail"}
    for name in regions:
        if name not in used:
            notes.append("region %s is not used by any line, so it will not be made" % name)
    rep.warnings.extend(pacing_warnings(lines, ctx))
    rep.value = {"schema": PLAN_SCHEMA, "regions": {n: r for n, r in regions.items() if n in used}, "lines": lines}
    return rep


# ---------------------------------------------------------------------------------------------------------------- wants
def wants_of(plan: dict) -> list[dict]:
    """The pictures the plan asks for that must be found elsewhere (context, map, clip), numbered per line: `b0006.2` is the second
    picture of line b0006. In the order of the narration. Each carries the line's `kinds`, and a context picture its `entity` (when given) and `period`."""
    out = []
    for ln in plan["lines"]:
        for n, it in enumerate(ln["show"], 1):
            if it["type"] in ("context", "map", "clip"):
                row = {"id": "%s.%d" % (ln["beat"], n), "beat": ln["beat"], "n": n, **it, "kinds": list(ln.get("kinds") or [])}
                if it["type"] == "context":
                    row["period"] = it.get("period") or DEFAULT_PERIOD           # `entity` comes with the item when the plan gave it
                    if it.get("wider"):
                        row["wider"] = list(it["wider"])
                if it["type"] == "map" and "places" not in it:
                    row["places"] = [it["place"]]                                # a plan saved before `places` existed
                out.append(row)
    return out


# ---------------------------------------------------------------------------------------------------------------- the choice
@dataclass
class ChoiceCtx:
    wants: dict                                       # want id -> number of candidates the agent was shown (its numbers are 1..n)
    books: int = 0                                    # how many book pictures were shown (B1..Bn)
    regions: list = field(default_factory=list)       # the names of the boxes it was shown

    def to_json(self) -> dict:
        return {"wants": self.wants, "books": self.books, "regions": self.regions}

    @classmethod
    def from_json(cls, d: dict) -> "ChoiceCtx":
        return cls(wants=dict(d.get("wants") or {}), books=int(d.get("books") or 0), regions=list(d.get("regions") or []))


def parse_pick(v: Any, n: int, books: int) -> tuple[tuple | None, str | None]:
    """`(("c", number) | ("b", number) | None, problem)`; null means "none of them fits"."""
    if v is None:
        return None, None
    if isinstance(v, bool):
        return None, "must be a number, \"B<number>\" or null"
    if isinstance(v, int) or (isinstance(v, str) and v.strip().isdigit()):
        k = int(v)
        return (("c", k), None) if 1 <= k <= n else (None, "%s is not one of its candidates (1 to %d)" % (k, n))
    if isinstance(v, str):
        m = BOOK_PICK_RE.fullmatch(v.strip())
        if m:
            k = int(m.group(1))
            return (("b", k), None) if 1 <= k <= books else (None, "%s is not one of the book pictures (B1 to B%d)" % (v, books))
    return None, "must be a number, \"B<number>\" or null"


def check_choice(obj: Any, ctx: ChoiceCtx) -> Report:
    rep = Report()
    err = rep.errors
    if not isinstance(obj, dict):
        err.append("the choice must be one JSON object with `wants` and `regions`")
        return rep
    if obj.get("schema") not in (None, CHOICE_SCHEMA):
        err.append("schema must be %r (or left out)" % CHOICE_SCHEMA)
    wants: dict[str, dict] = {}
    raw = obj.get("wants", [])
    if not isinstance(raw, list):
        err.append("`wants` must be a list of {id, pick, reason}")
        raw = []
    for k, w in enumerate(raw):
        where = "wants[%d]" % k
        if not isinstance(w, dict) or not isinstance(w.get("id"), str):
            err.append("%s must be {id, pick, reason}" % where)
            continue
        wid = w["id"]
        where = "wants[%d] (%s)" % (k, wid)
        if wid not in ctx.wants:
            err.append("%s: there is no such wanted picture (see inputs/wants.json)" % where)
            continue
        if wid in wants:
            err.append("%s: written twice" % where)
            continue
        pick, problem = parse_pick(w.get("pick"), int(ctx.wants[wid]), ctx.books)
        if problem:
            err.append("%s: pick %s" % (where, problem))
            continue
        reason = _text(w.get("reason"), 3, REASON_MAX * 2)
        if reason is None:
            err.append("%s: `reason` must say in one short sentence why this picture shows what the line says, or why none fits (Vietnamese)" % where)
            continue
        if not _vietnamese(reason):
            err.append("%s: `reason` must be written in Vietnamese, with its accents (the owner reads it); it says %r" % (where, reason[:60]))
            continue
        wants[wid] = {"pick": pick, "reason": _short(reason, REASON_MAX)}
    left = [w for w in ctx.wants if w not in wants]
    if left and not any("wants[" in e for e in err):
        more = " and %d more" % (len(left) - 12) if len(left) > 12 else ""
        err.append("these wanted pictures have no entry in `wants`: %s%s (pick null when none of the candidates is sure to fit)" % (", ".join(left[:12]), more))
    regions: dict[str, dict] = {}
    raw_r = obj.get("regions", [])
    if not isinstance(raw_r, list):
        err.append("`regions` must be a list of {name, action, box?, reason}")
        raw_r = []
    for k, r in enumerate(raw_r):
        where = "regions[%d]" % k
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            err.append("%s must be {name, action, box?, reason}" % where)
            continue
        name = r["name"]
        where = "regions[%d] (%s)" % (k, name)
        if name not in ctx.regions:
            err.append("%s: there is no such box among those you were shown (%s)" % (where, ", ".join(ctx.regions) or "none"))
            continue
        if name in regions:
            err.append("%s: written twice" % where)
            continue
        action = r.get("action")
        if action not in ACTIONS:
            err.append("%s: action must be one of %s" % (where, ", ".join(ACTIONS)))
            continue
        box = None
        if action == "adjust":
            box, problem = clean_box(r.get("box"), where)
            if problem:
                err.append(problem)
                continue
        reason = _text(r.get("reason"), 3, REASON_MAX * 2)
        if reason is None and action != "keep":
            err.append("%s: `reason` must say in one short sentence why the box is %s" % (where, "moved" if action == "adjust" else "dropped"))
            continue
        if reason is not None and not _vietnamese(reason):
            err.append("%s: `reason` must be written in Vietnamese, with its accents (the owner reads it); it says %r" % (where, reason[:60]))
            continue
        regions[name] = {"action": action, "box": box, "reason": _short(reason or "", REASON_MAX)}
    left_r = [n for n in ctx.regions if n not in regions]
    if left_r and not any("regions[" in e for e in err):
        err.append("these boxes have no entry in `regions`: %s (say keep, adjust or drop for each)" % ", ".join(left_r[:12]))
    if not err:
        rep.value = {"schema": CHOICE_SCHEMA, "wants": wants, "regions": regions}
    return rep
