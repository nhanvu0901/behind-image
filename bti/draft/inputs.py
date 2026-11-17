"""What a draft is made from: the timed narration (`timing.json`), the owner's picks (`picks.json`), the optional narration
(`script/narration.json`, for facts and `show` words) and the saved storyboard (for a re-draft).

`normalize_timing` gives every chapter and beat an id and a time range, so that the rest of the package never has to guess.
The files are read once, here; the workspace, the compiler and the providers all work from a `DraftInputs`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

SPEC_SCHEMA = "bti.draft/1"
PICKS_SCHEMA = "bti.picks/1"
CHAPTER_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}")


class DraftError(Exception):
    """A failure with a stable `code` (the page maps it to Vietnamese) and an English sentence."""

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


def canon_hash(obj) -> str:
    """sha256 of the canonical JSON of `obj` (sorted keys, no spaces)."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json_file(path: Path, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DraftError(what + "_missing", "%s is missing" % Path(path).name)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise DraftError(what + "_corrupt", "%s is not readable JSON: %s" % (Path(path).name, str(e)[:120]))


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


# --------------------------------------------------------------------------------------------- timing
def normalize_timing(raw: dict, narration: dict | None = None) -> dict:
    """A copy of timing.json with `words` ({w, s, e}), `chapters` ({id, name, start, end, card, card_start, card_end}) and `beats`
    ({id, chapter (a chapter id), text, start, end, w0, w1}) filled in. Missing ids are made up in order: `c01...` and `b0001...`
    (the narration's beat ids are used when it has exactly as many beats). Raises DraftError("timing_shape") when the file cannot be used."""
    from bti.engine import timing as T
    problem = T.shape_problem(raw)
    if problem:
        raise DraftError("timing_shape", "timing.json cannot be used: " + problem)
    words = []
    for w in raw.get("words", []):
        s = float(w["s"])
        e = float(w["e"]) if _num(w.get("e")) else s
        words.append({"w": w["w"], "s": s, "e": max(e, s)})
    if not words:
        raise DraftError("timing_shape", "timing.json has no words")
    n = len(words)
    raw_beats = [b for b in (raw.get("beats") or []) if isinstance(b, dict)]
    raw_chaps = [c for c in (raw.get("chapters") or []) if isinstance(c, dict)]
    if not raw_beats:
        raise DraftError("timing_shape", "timing.json has no beats: the draft needs the beat ranges (w0, w1)")
    narr_ids: list[str] = []
    if isinstance(narration, dict):
        for c in narration.get("chapters") or []:
            for b in (c or {}).get("beats") or []:
                if isinstance(b, dict) and isinstance(b.get("id"), str):
                    narr_ids.append(b["id"])
    use_narr = len(narr_ids) == len(raw_beats)

    chapters = []
    for i, c in enumerate(raw_chaps):
        cid = c.get("id") if isinstance(c.get("id"), str) and c.get("id") else "c%02d" % (i + 1)
        if not CHAPTER_ID_RE.fullmatch(cid):
            raise DraftError("timing_shape", "chapter id %r is not usable (letters, digits, - _ . only)" % cid)
        card = c.get("card")
        ld = c.get("lead")
        lead = ({"kind": ld["kind"], "start": float(ld["start"]), "end": float(ld["end"])}
                if isinstance(ld, dict) and ld.get("kind") in ("title", "card", "plain") and _num(ld.get("start")) and _num(ld.get("end"))
                and ld["end"] > ld["start"] else None)
        chapters.append({"lead": lead, "id": cid, "name": str(c.get("name") or c.get("title") or cid),
                         "start": float(c["start"]) if _num(c.get("start")) else None,
                         "end": float(c["end"]) if _num(c.get("end")) else None,
                         "card": bool(card), "card_start": float(card["start"]) if isinstance(card, dict) and _num(card.get("start")) else None,
                         "card_end": float(card["end"]) if isinstance(card, dict) and _num(card.get("end")) else None})
    if len({c["id"] for c in chapters}) != len(chapters):
        raise DraftError("timing_shape", "two chapters of timing.json share an id")
    by_key: dict[str, str] = {}
    for c in chapters:
        by_key[c["id"]] = c["id"]
        by_key.setdefault(c["name"].strip().lower(), c["id"])

    beats = []
    for i, b in enumerate(raw_beats):
        w0, w1 = b.get("w0"), b.get("w1")
        if not (isinstance(w0, int) and isinstance(w1, int) and not isinstance(w0, bool) and not isinstance(w1, bool)
                and 0 <= w0 < w1 <= n):
            raise DraftError("timing_shape", "beat %d of timing.json needs integer word range 0 <= w0 < w1 <= %d" % (i + 1, n))
        bid = b.get("id") if isinstance(b.get("id"), str) and b.get("id") else (narr_ids[i] if use_narr else "b%04d" % (i + 1))
        ch = b.get("chapter")
        cid = by_key.get(ch) or by_key.get(str(ch).strip().lower()) if ch is not None else None
        beats.append({"id": bid, "chapter": cid, "text": str(b.get("text") or ""),
                      "start": float(b["start"]) if _num(b.get("start")) else words[w0]["s"],
                      "end": float(b["end"]) if _num(b.get("end")) else words[w1 - 1]["e"], "w0": w0, "w1": w1})
    if len({b["id"] for b in beats}) != len(beats):
        raise DraftError("timing_shape", "two beats of timing.json share an id")
    beats.sort(key=lambda b: b["w0"])
    if not chapters:
        chapters = [{"id": "c01", "name": "c01", "start": None, "end": None, "card": False, "card_start": None, "card_end": None, "lead": None}]
    # a beat without a (known) chapter belongs to the chapter whose time range holds it, else the last one started before it
    for b in beats:
        if b["chapter"] is None:
            pick = chapters[0]["id"]
            for c in chapters:
                if c["start"] is not None and c["start"] <= b["start"] + 1e-6:
                    pick = c["id"]
            b["chapter"] = pick
    keep = []
    for c in chapters:
        mine = [b for b in beats if b["chapter"] == c["id"]]
        if not mine:
            continue
        if c["start"] is None:
            c["start"] = mine[0]["start"]
        if c["end"] is None:
            c["end"] = mine[-1]["end"]
        c["w0"], c["w1"] = mine[0]["w0"], mine[-1]["w1"]
        keep.append(c)
    keep.sort(key=lambda c: c["w0"])
    for a, b in zip(keep, keep[1:]):
        if a["w1"] > b["w0"]:
            raise DraftError("timing_shape", "chapters %s and %s overlap in words" % (a["id"], b["id"]))
    duration = float(raw["duration"]) if _num(raw.get("duration")) else words[-1]["e"]
    return {"duration": duration, "words": words, "beats": beats, "chapters": keep}


# --------------------------------------------------------------------------------------------- picks
def check_picks(picks) -> dict:
    """The picks document, or DraftError. It needs a main asset that exists in `assets`."""
    if not isinstance(picks, dict) or not isinstance(picks.get("assets"), dict):
        raise DraftError("picks_shape", "picks.json must be an object with an `assets` object")
    main = picks.get("main_asset")
    if not (isinstance(main, str) and isinstance(picks["assets"].get(main), dict)):
        raise DraftError("picks_no_main", "picks.json has no main asset: choose the main painting first")
    for k, a in picks["assets"].items():
        if not isinstance(a, dict):
            raise DraftError("picks_shape", "asset %r of picks.json is not an object" % k)
    if not isinstance(picks.get("beats", {}), dict):
        raise DraftError("picks_shape", "`beats` of picks.json must be an object")
    return picks


def beat_picks(picks: dict, beat_id: str) -> list[dict]:
    """The items of a beat: [{asset, region, role, note}], only those whose asset exists."""
    entry = (picks.get("beats") or {}).get(beat_id)
    if not isinstance(entry, dict) or entry.get("status") == "skip":
        return []
    out = []
    for it in entry.get("items") or []:
        if isinstance(it, dict) and isinstance(it.get("asset"), str) and it["asset"] in picks["assets"]:
            out.append({"asset": it["asset"], "region": it.get("region") if isinstance(it.get("region"), str) else None,
                        "role": it.get("role") or "detail", "note": str(it.get("note") or "")})
    return out


def narration_notes(narration: dict | None) -> dict:
    """beat id -> {facts, show, locked} from narration.json (empty when there is none)."""
    out: dict = {}
    if isinstance(narration, dict):
        for c in narration.get("chapters") or []:
            for b in (c or {}).get("beats") or []:
                if isinstance(b, dict) and isinstance(b.get("id"), str):
                    out[b["id"]] = {"facts": list(b.get("facts") or []), "show": [str(x) for x in (b.get("show") or [])],
                                    "text": str(b.get("text") or "")}
    return out


def fill_sizes(assets: dict, project_dir: Path) -> None:
    """Give every image asset that lacks `width`/`height` its real size (read from the file header), in place."""
    for a in assets.values():
        if not isinstance(a, dict) or a.get("kind") not in ("image", "mask") or (a.get("width") and a.get("height")):
            continue
        f = Path(project_dir) / a["file"] if isinstance(a.get("file"), str) and a["file"] and ".." not in a["file"] else None
        if f is not None and f.is_file():
            try:
                from PIL import Image
                with Image.open(f) as im:
                    a["width"], a["height"] = im.size
            except Exception:       # noqa: BLE001 - the validator reports an unreadable image
                pass


# --------------------------------------------------------------------------------------------- the bundle
@dataclass
class DraftInputs:
    timing: dict
    picks: dict
    narration: dict | None = None
    current: dict | None = None          # the saved storyboard, for a re-draft
    title: str = ""
    style: str = "gae"
    audio: str | None = None
    project_dir: Path | None = None      # where asset files are looked up (the project, or a workspace)
    scope: list[str] | None = None       # chapter ids to (re)draft; None = all
    edit_shots: set | None = None        # edit mode (7.4): ids of the shots the agent may change; None = a draft
    reserved_ids: list[str] = field(default_factory=list)   # shot ids that must never be handed out again
    timing_file: str = "timing.json"

    def chapter_ids(self) -> list[str]:
        return [c["id"] for c in self.timing["chapters"]]

    def in_scope(self) -> list[str]:
        ids = self.chapter_ids()
        return ids if not self.scope else [c for c in ids if c in set(self.scope)]

    def hashes(self) -> dict:
        return {"timing": canon_hash(self.timing), "picks": canon_hash(self.picks),
                "narration": canon_hash(self.narration) if self.narration else None}


def load_inputs(project_dir: Path, chapters: list[str] | None = None) -> DraftInputs:
    """Read a project's draft inputs. DraftError with a stable code when a piece is missing or unusable."""
    project_dir = Path(project_dir)
    narration = None
    nf = project_dir / "script" / "narration.json"
    if nf.is_file():
        try:
            narration = json.loads(nf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            narration = None
    current = None
    sf = project_dir / "storyboard.json"
    if sf.is_file():
        current = read_json_file(sf, "storyboard")
        if not isinstance(current, dict):
            raise DraftError("storyboard_corrupt", "storyboard.json is not an object")
    timing_file = "timing.json"
    if isinstance(current, dict) and isinstance(current.get("timing"), str) and current["timing"]:
        timing_file = current["timing"]
    timing = normalize_timing(read_json_file(project_dir / timing_file, "timing"), narration)
    picks = check_picks(read_json_file(project_dir / "picks.json", "picks"))
    if chapters:
        known = {c["id"] for c in timing["chapters"]}
        bad = [c for c in chapters if c not in known]
        if bad:
            raise DraftError("unknown_chapter", "no such chapter: %s (chapters: %s)" % (", ".join(bad), ", ".join(sorted(known))))
        if not isinstance(current, dict):
            raise DraftError("scope_needs_storyboard", "a single chapter can only be re-drafted when the project already has a storyboard")
    fill_sizes(picks["assets"], project_dir)
    if isinstance(current, dict) and isinstance(current.get("assets"), dict):
        fill_sizes(current["assets"], project_dir)
    title = ""
    for cand in (current or {}).get("title"), (narration or {}).get("title"):
        if isinstance(cand, str) and cand.strip():
            title = cand.strip()
            break
    if not title:
        title = project_dir.name
    audio = "audio/mix.m4a" if (project_dir / "audio" / "mix.m4a").is_file() else (current or {}).get("audio")
    reserved: list[str] = []
    if isinstance(current, dict):
        reserved += [s.get("id") for s in current.get("shots") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)]
    pdir = project_dir / "proposals"
    if pdir.is_dir():
        for f in sorted(pdir.glob("draft_*.json"))[-20:]:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
                reserved += [s.get("id") for s in (doc.get("storyboard") or {}).get("shots") or []
                             if isinstance(s, dict) and isinstance(s.get("id"), str)]
            except (OSError, ValueError, AttributeError):
                continue
    return DraftInputs(timing=timing, picks=picks, narration=narration, current=current, title=title,
                       style=(current or {}).get("style") or "gae", audio=audio if isinstance(audio, str) else None,
                       project_dir=project_dir, scope=list(chapters) if chapters else None,
                       reserved_ids=sorted(set(reserved)), timing_file=timing_file)


def clone_inputs(inp: DraftInputs, **changes) -> DraftInputs:
    out = copy.copy(inp)
    for k, v in changes.items():
        setattr(out, k, v)
    return out
