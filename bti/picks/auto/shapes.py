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
     "lines": [{"beat": "b0001", "reason": "<one short sentence, Vietnamese>",
                "show": [{"type": "whole"},
                         {"type": "detail", "region": "HEAD"},
                         {"type": "context", "search": "english words", "alt": ["other words"], "kind": "portrait",
                          "what": "<what it should show, Vietnamese>"},
                         {"type": "map", "place": "Oslo, Norway"},
                         {"type": "clip", "search": "english words", "what": "...", "seconds": 6}]}]}

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

PLAN_SCHEMA = "bti.picks.plan/1"
CHOICE_SCHEMA = "bti.picks.choice/1"
MAX_FILE_BYTES = 1_000_000

TYPES = ("whole", "detail", "context", "map", "clip")
CONTEXT_KINDS = ("work", "portrait", "document", "photo", "place", "other")
ACTIONS = ("keep", "adjust", "drop")

MAX_ITEMS = 3                    # pictures on one narration line
MAX_REGIONS = 20                 # regions the plan may add to the main painting (the choosing session looks at each one)
MAX_WANTS = 30                   # pictures a plan may ask for from elsewhere (context, map, clip): the choosing session looks at a sheet for each
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

    def __post_init__(self):
        self.chapters = {b["id"]: b.get("chapter") for b in self.beats}
        self.words = {b["id"]: int(b.get("words") or 0) for b in self.beats}

    def to_json(self) -> dict:
        return {"beats": self.beats, "targets": self.targets, "existing_regions": self.existing_regions}

    @classmethod
    def from_json(cls, d: dict) -> "PlanCtx":
        return cls(beats=list(d.get("beats") or []), targets=list(d.get("targets") or []),
                   existing_regions={k: list(v) for k, v in (d.get("existing_regions") or {}).items()})


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


def _item(it: Any, where: str, regions: dict, errors: list, notes: list) -> dict | None:
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
        if search is None or what is None or kind_of not in CONTEXT_KINDS:
            return None
        return {"type": "context", "search": search, "alt": alts, "kind": kind_of, "what": _short(what, WHAT_MAX)}
    if kind == "map":
        place = _text(it.get("place"), 2, 80)
        if place is None:
            errors.append("%s: `place` must be the name of the place, 2 to 80 characters (for example \"Oslo, Norway\")" % where)
            return None
        what = _text(it.get("what"), 2, WHAT_MAX + 80) or ("Bản đồ " + place)
        return {"type": "map", "place": place, "what": _short(what, WHAT_MAX)}
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
        items: list[dict] = []
        for n, it in enumerate(show_raw):
            got = _item(it, "%s.show[%d]" % (where, n), known, err, notes)
            if got is None:
                continue
            if got in items:
                notes.append("%s.show[%d]: the same picture twice in a line; the second one is dropped" % (where, n))
                continue
            items.append(got)
        seen[bid] = {"beat": bid, "reason": reason, "show": items}
    asked = sum(1 for ln in seen.values() for i in ln["show"] if i["type"] in ("context", "map", "clip"))
    if asked > MAX_WANTS:
        err.append("the plan asks for %d pictures from elsewhere (context, map, clip); ask for at most %d, the most important ones, and show the painting on the other lines"
                   % (asked, MAX_WANTS))
    missing = [b for b in ctx.targets if b not in seen]
    if missing:
        more = " and %d more" % (len(missing) - 12) if len(missing) > 12 else ""
        err.append("these lines have no entry in `lines`: %s%s (give a line `\"show\": []` when it needs nothing new)" % (", ".join(missing[:12]), more))
    if err:
        return rep
    lines = [seen[b] for b in ctx.targets]                # ctx.targets is in narration order
    notes.extend(apply_clip_rule(lines, ctx.chapters))
    used = {i["region"] for ln in lines for i in ln["show"] if i["type"] == "detail"}
    for name in regions:
        if name not in used:
            notes.append("region %s is not used by any line, so it will not be made" % name)
    rep.warnings.extend(pacing_warnings(lines, ctx))
    rep.value = {"schema": PLAN_SCHEMA, "regions": {n: r for n, r in regions.items() if n in used}, "lines": lines}
    return rep


# ---------------------------------------------------------------------------------------------------------------- wants
def wants_of(plan: dict) -> list[dict]:
    """The pictures the plan asks for that must be found elsewhere (context, map, clip), numbered per line: `b0006.2` is the second
    picture of line b0006. In the order of the narration."""
    out = []
    for ln in plan["lines"]:
        for n, it in enumerate(ln["show"], 1):
            if it["type"] in ("context", "map", "clip"):
                out.append({"id": "%s.%d" % (ln["beat"], n), "beat": ln["beat"], "n": n, **it})
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
