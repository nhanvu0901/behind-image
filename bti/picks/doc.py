"""The `bti.picks/1` document: what is on screen for each beat of the narration.

`projects/<pid>/picks.json`:

    {"schema": "bti.picks/1", "main_asset": "A",
     "assets": {"A": {file, kind, title, artist, year, width, height, credit{..., flag}, regions{NAME: {x, y, rx, ry, label}}}},
     "beats": {"b0007": {"items": [{asset, region, role, note}], "status": "todo|picked|skip", "note": "",
                         "kinds": ["outside"], "missing": [{"what": "...", "code": "agent_none"}]}},
     "approval": {"approved", "sha1", "approved_at", "narration_sha1"}}

`kinds` (optional, one or two of `LINE_KINDS`, in the order the line speaks) says what the line does; the automatic choice of pictures writes it from
its plan. `missing` (optional) lists the pictures that were asked for and not found (`what` is the thing, `code` why). A document made before these two
existed has neither: a beat without them is read, saved and hashed exactly as it was, and raises no warning that needs them.

The field names are read by the storyboard draft agent: do not rename them. `assets` has the shape of `storyboard.assets`.

An asset's `width` and `height` are the pixels of its stored file, and its regions are in that space. `original_width` /
`original_height` (optional) are what the source said its original was; they can be larger. `load` enforces the rule on
documents written before it existed (`bti.media.assets.reconcile_sizes`): a declared size that differs from the stored file is
corrected, the regions of that asset are scaled with it, and the correction reaches the disk with the next `save`.

An image asset may carry `content_box` (`{x0, y0, x1, y1, how, note?}`, pixels of the stored picture): the painted area, found by the program when
the picture is imported and when it is the main painting (`bti.media.contentbox`; a museum photograph of a panel often has a black ground round the
painting), or set by `set_content_box`. The camera of the video never leaves the box of the main painting. A document without it is read and saved exactly
as before; `save` gives the main painting the finding of its file when it has none.

Revision = sha1 of the canonical JSON without the `approval` block (the same rule as the script documents). An approval
stores that revision and the revision of the narration it was given against; it stands only while both still match and the
narration itself is approved. Saving a changed document drops the approval. Writes are atomic, take the picks lock, and
never re-create a project folder.
"""
from __future__ import annotations

import copy
import math
import re
import threading
from pathlib import Path
from typing import Any

from bti.media import assets as _mediaassets
from bti.media import contentbox as _contentbox          # panelbox: the painted area of a picture
from bti.script import store as sstore
from bti.script.store import DocumentCorrupt, ProjectGone, StaleRevision  # noqa: F401  (re-exported)

SCHEMA = "bti.picks/1"
FILE = "picks.json"
ROLES = ("main", "detail", "context", "compare", "document", "map", "video")
STATUSES = ("todo", "picked", "skip")
FLAGS = ("rejected", "unknown", "small")
BEAT_ID_RE = sstore.BEAT_ID_RE
KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}")
REGION_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ .-]{0,39}")
MAX_ITEMS = 30
MAX_ASSETS = 400
# what a line of the narration does (the plan of the automatic choice of pictures writes it, see bti/picks/auto/shapes.py for what each kind must show)
LINE_KINDS = ("detail", "whole", "outside", "compare", "journey", "dates", "figure", "inscription", "construction", "relations", "idea")
OUTSIDE_KINDS = ("outside", "compare")       # the kinds whose line needs a picture of something that is not in the painting
MAX_KINDS = 2
MAX_MISSING = 10
MISSING_WHAT_MAX = 160
THING_MAX = 120
CODE_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")


# ---------------------------------------------------------------- lock
_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


def picks_lock(pdir: Path) -> threading.RLock:
    """The one lock of a project's picks.json. Taken only for the final read-modify-write, never across a download or a
    network call. Lock order: if both are needed, the script lock comes first (this lock is never held while taking it)."""
    key = str(Path(pdir).resolve())
    with _GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def forget_lock(pdir: Path) -> None:
    with _GUARD:
        _LOCKS.pop(str(Path(pdir).resolve()), None)


# ---------------------------------------------------------------- shape
def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _num(v: Any, default: float = 0) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        return default
    return v


def _int(v: Any) -> int:
    return int(round(_num(v)))


def empty() -> dict:
    return {"schema": SCHEMA, "main_asset": None, "assets": {}, "beats": {}, "approval": _approval({})}


def _approval(a: Any) -> dict:
    a = a if isinstance(a, dict) else {}
    out = {"approved": bool(a.get("approved")), "sha1": a.get("sha1"), "approved_at": a.get("approved_at")}
    if a.get("narration_sha1"):
        out["narration_sha1"] = a["narration_sha1"]
    if isinstance(a.get("by"), str) and a["by"]:         # c5cli: who approved (`human`, `agent:...`, `cli:...`); absent in an approval made before this existed
        out["by"] = a["by"]
    return out


def _rough(v: Any) -> list[int] | None:
    """Four finite integers `[x0, y0, x1, y1]` (rough box in stored pixels, `x0 < x1` and `y0 < y1`), or None."""
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        return None
    if not all(isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n) and n >= 0 for n in v):
        return None
    x0, y0, x1, y1 = (int(round(float(n))) for n in v)
    return [x0, y0, x1, y1] if x1 > x0 and y1 > y0 else None


def _region(r: Any) -> dict | None:
    if not isinstance(r, dict) or not all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
                                          and math.isfinite(r[k]) for k in ("x", "y")):
        return None
    out: dict[str, Any] = {"x": r["x"], "y": r["y"]}
    for k in ("rx", "ry"):
        if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool) and math.isfinite(r[k]) and r[k] > 0:
            out[k] = r[k]
    out["label"] = _s(r.get("label"))
    if r.get("tight") is True:
        out["tight"] = True
    if isinstance(r.get("thing"), str):
        thing = " ".join(r["thing"].split())[:THING_MAX]
        if thing:
            out["thing"] = thing
    if r.get("rough") is not None:
        rb = _rough(r.get("rough"))
        if rb is not None:
            out["rough"] = rb
    return out


def _content_box(v: Any) -> dict | None:
    """The `content_box` object of an asset in its stored form (whole pixels, `how` one of `bti.media.contentbox.HOW`, `note` only when there is one), or None
    when `v` is not four finite numbers with x0 < x1 and y0 < y1."""
    box = _contentbox.clean(v)
    if box is None:
        return None
    note = v.get("note") if isinstance(v.get("note"), str) and v["note"].strip() else None
    return _contentbox.record(box, v.get("how") if v.get("how") in _contentbox.HOW else "set", note)


def _asset(a: Any) -> dict | None:
    if not isinstance(a, dict) or not _s(a.get("file")):
        return None
    credit = a.get("credit") if isinstance(a.get("credit"), dict) else {}
    credit = {k: v for k, v in credit.items() if isinstance(k, str)}
    credit["flag"] = credit.get("flag") if credit.get("flag") in FLAGS else None
    for k in ("source", "source_url", "author", "licence", "licence_url"):
        credit[k] = _s(credit.get(k))
    regions = {}
    for name, r in (a.get("regions") or {}).items() if isinstance(a.get("regions"), dict) else []:
        rr = _region(r)
        if rr is not None and isinstance(name, str) and name:
            regions[name] = rr
    out = {"file": _s(a["file"]), "kind": "video" if a.get("kind") == "video" else "image", "title": _s(a.get("title")),
           "artist": _s(a.get("artist")), "year": _s(a.get("year")), "width": _int(a.get("width")),
           "height": _int(a.get("height")), "credit": credit, "regions": regions}
    for k in ("original_width", "original_height"):          # the source's own size, kept apart from the stored one
        if _int(a.get(k)) > 0:
            out[k] = _int(a.get(k))
    dur = _num(a.get("duration"), 0.0)
    if out["kind"] == "video" and dur > 0:
        out["duration"] = round(float(dur), 2)
    box = _content_box(a.get("content_box")) if out["kind"] == "image" else None
    if box is not None:                                      # absent when there is none: a document made before the painted area existed keeps its revision
        out["content_box"] = box
    return out


def _item(i: Any) -> dict | None:
    if not isinstance(i, dict) or not _s(i.get("asset")):
        return None
    region = i.get("region")
    out = {"asset": _s(i["asset"]), "region": _s(region) if region else None,
            "role": i.get("role") if i.get("role") in ROLES else "detail", "note": _s(i.get("note"))}
    if i.get("step") in (2, 3):
        out["step"] = int(i["step"])
    return out


def _kinds(v: Any) -> list[str]:
    """The known words of a `kinds` list, without repeats, at most `MAX_KINDS` (an unknown word is dropped)."""
    out: list[str] = []
    for k in v if isinstance(v, list) else []:
        if k in LINE_KINDS and k not in out:
            out.append(k)
    return out[:MAX_KINDS]


def _missing(v: Any) -> list[dict]:
    """The well-formed entries `{what, code}` of a `missing` list (at most `MAX_MISSING`)."""
    out: list[dict] = []
    for m in v if isinstance(v, list) else []:
        if isinstance(m, dict) and isinstance(m.get("what"), str) and m["what"].strip() and isinstance(m.get("code"), str) and CODE_RE.fullmatch(m["code"]):
            out.append({"what": " ".join(m["what"].split())[:MISSING_WHAT_MAX], "code": m["code"]})
    return out[:MAX_MISSING]


def normalize(d: Any) -> dict:
    """A forgiving read of a document on disk (older or hand-edited files). Unknown keys of an asset's credit are kept."""
    d = d if isinstance(d, dict) else {}
    assets = {}
    for k, a in (d.get("assets") or {}).items() if isinstance(d.get("assets"), dict) else []:
        na = _asset(a)
        if na is not None and isinstance(k, str) and k:
            assets[k] = na
    beats = {}
    for bid, b in (d.get("beats") or {}).items() if isinstance(d.get("beats"), dict) else []:
        if not isinstance(b, dict) or not isinstance(bid, str):
            continue
        raw_items = b.get("items") if isinstance(b.get("items"), list) else []
        items = [x for x in (_item(i) for i in raw_items) if x is not None]
        status = b.get("status") if b.get("status") in STATUSES else ("picked" if items else "todo")
        beats[bid] = {"items": items, "status": status, "note": _s(b.get("note"))}
        if isinstance(b.get("about"), list):
            beats[bid]["about"] = copy.deepcopy(b["about"])
        for key, val in (("kinds", _kinds(b.get("kinds"))), ("missing", _missing(b.get("missing")))):
            if val:                                          # absent when empty: a document made before these existed keeps its revision
                beats[bid][key] = val
    main = d.get("main_asset")
    result = {"schema": SCHEMA, "main_asset": main if isinstance(main, str) and main in assets else None,
              "assets": assets, "beats": beats, "approval": _approval(d.get("approval"))}
    if isinstance(d.get("subjects"), list):
        result["subjects"] = copy.deepcopy(d["subjects"])
    if isinstance(d.get("names"), list):
        result["names"] = copy.deepcopy(d["names"])
    return result


def subject_view(d: dict) -> tuple[list[dict], dict[str, list[dict]]]:
    """Read modern subjects or adapt an old first-presentation cast without rewriting it."""
    if isinstance(d.get("subjects"), list):
        return ([{**copy.deepcopy(subject), "also": copy.deepcopy(subject.get("also") or [])} for subject in d["subjects"] if isinstance(subject, dict)], {bid: copy.deepcopy(beat["about"])
                for bid, beat in (d.get("beats") or {}).items()
                if isinstance(beat, dict) and isinstance(beat.get("about"), list)})
    subjects, about = [], {}
    for i, row in enumerate(d.get("names") or [], 1):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not isinstance(row.get("line"), str):
            continue
        sid = "legacy_%d" % i
        subject = {"id": sid, "kind": "person", "name": row["name"], "also": copy.deepcopy(row.get("also") or []), "strip": True, "where": copy.deepcopy(row.get("where"))}
        if not row.get("sure") and row.get("words"):
            subject["sub"] = row["words"]
        subjects.append(subject)
        about.setdefault(row["line"], []).append({"id": sid, "words": row["name"]})
    return subjects, about


def doc_problem(d: Any) -> str | None:
    """None when `d`, sent by a client, has the right shape; else what is wrong. Strict: nothing is coerced."""
    if not isinstance(d, dict):
        return "picks (object) is required"
    if "main_asset" in d and d["main_asset"] is not None and not isinstance(d["main_asset"], str):
        return "picks.main_asset must be a string or null"
    if "names" in d:
        if not isinstance(d["names"], list):
            return "picks.names must be a list"
        cast_seen = set()
        for i, n in enumerate(d["names"]):
            if not (isinstance(n, dict) and isinstance(n.get("name"), str) and n["name"].strip()
                    and isinstance(n.get("also"), list) and all(isinstance(a, str) and a.strip() for a in n["also"])
                    and isinstance(n.get("line"), str) and BEAT_ID_RE.fullmatch(n["line"])
                    and isinstance(n.get("sure"), bool) and isinstance(n.get("words"), str)
                    and isinstance(n.get("where"), dict) and len(n["where"]) == 1
                    and next(iter(n["where"]), None) in ("region", "asset")
                    and isinstance(next(iter(n["where"].values()), None), str)
                    and next(iter(n["where"].values())).strip()):
                return f"picks.names[{i}] must name a person, line, region or asset, certainty and words"
            aliases = {a.strip().casefold() for a in [n["name"]] + n["also"]}
            if cast_seen & aliases:
                return f"picks.names[{i}] repeats a person or alias"
            cast_seen.update(aliases)
    subject_ids = set()
    if "subjects" in d:
        if not isinstance(d["subjects"], list):
            return "picks.subjects must be a list"
        for i, subject in enumerate(d["subjects"]):
            if not isinstance(subject, dict):
                return f"picks.subjects[{i}] must be an object"
            sid, kind, name, where = (subject.get(k) for k in ("id", "kind", "name", "where"))
            if not (isinstance(sid, str) and sid.strip() and sid not in subject_ids
                    and kind in ("person", "thing", "place", "work", "idea", "text")
                    and isinstance(name, str) and name.strip() and isinstance(subject.get("strip"), bool)
                    and ("sub" not in subject or isinstance(subject["sub"], str))
                    and ("also" not in subject or (isinstance(subject["also"], list) and all(isinstance(a, str) and a.strip() for a in subject["also"])))
                    and (kind not in ("idea", "text") or not subject["strip"])):
                return f"picks.subjects[{i}] needs a unique id, kind, name and strip"
            if where is not None and not (isinstance(where, dict) and len(where) == 1 and next(iter(where), None) in ("region", "asset")
                      and isinstance(next(iter(where.values()), None), str) and next(iter(where.values())).strip()):
                return f"picks.subjects[{i}].where must name one region or asset"
            subject_ids.add(sid)
    assets = d.get("assets", {})
    if not isinstance(assets, dict) or len(assets) > MAX_ASSETS:
        return "picks.assets must be an object"
    for k, a in assets.items():
        if not isinstance(k, str) or not KEY_RE.fullmatch(k):
            return f"asset key {str(k)[:40]!r} is not valid"
        if not isinstance(a, dict):
            return f"picks.assets.{k} must be an object"
        for f in ("title", "artist", "year"):
            if f in a and a[f] is not None and not isinstance(a[f], str):
                return f"picks.assets.{k}.{f} must be a string"
        if a.get("content_box") is not None and _content_box(a["content_box"]) is None:
            return f"picks.assets.{k}.content_box must be an object with numbers x0 < x1 and y0 < y1"
        regions = a.get("regions", {})
        if not isinstance(regions, dict):
            return f"picks.assets.{k}.regions must be an object"
        for name, r in regions.items():
            if not isinstance(name, str) or not REGION_RE.fullmatch(name):
                return f"region name {str(name)[:40]!r} is not valid"
            if _region(r) is None:
                return f"region {name!r} needs numeric x and y"
            if "tight" in r and not isinstance(r["tight"], bool):
                return f"picks.assets.{k}.regions.{name}.tight must be true or false"
            if "thing" in r and r["thing"] is not None and not isinstance(r["thing"], str):
                return f"picks.assets.{k}.regions.{name}.thing must be a string"
            if "rough" in r and r["rough"] is not None and _rough(r["rough"]) is None:
                return f"picks.assets.{k}.regions.{name}.rough must be four numbers [x0, y0, x1, y1] with x0 < x1 and y0 < y1"
    beats = d.get("beats", {})
    if not isinstance(beats, dict):
        return "picks.beats must be an object"
    for bid, b in beats.items():
        if not isinstance(bid, str) or not BEAT_ID_RE.fullmatch(bid):
            return f"beat id {str(bid)[:40]!r} is not valid (b followed by digits)"
        if not isinstance(b, dict):
            return f"picks.beats.{bid} must be an object"
        if "status" in b and b["status"] not in STATUSES:
            return f"picks.beats.{bid}.status must be one of {', '.join(STATUSES)}"
        if "note" in b and b["note"] is not None and not isinstance(b["note"], str):
            return f"picks.beats.{bid}.note must be a string"
        if "about" in b:
            about = b["about"]
            if not isinstance(about, list) or any(not isinstance(a, dict) or not isinstance(a.get("id"), str) or a.get("id") not in subject_ids
                    or not isinstance(a.get("words"), str) or not a["words"].strip() for a in about):
                return f"picks.beats.{bid}.about must list known subjects and their spoken words"
        kinds = b.get("kinds")
        if kinds is not None and not (isinstance(kinds, list) and len(kinds) <= MAX_KINDS and all(k in LINE_KINDS for k in kinds)):
            return f"picks.beats.{bid}.kinds must be a list of at most {MAX_KINDS} of: {', '.join(LINE_KINDS)}"
        missing = b.get("missing")
        if missing is not None and not (isinstance(missing, list) and len(missing) <= MAX_MISSING and all(
                isinstance(m, dict) and isinstance(m.get("what"), str) and isinstance(m.get("code"), str) for m in missing)):
            return f"picks.beats.{bid}.missing must be a list of at most {MAX_MISSING} objects like {{\"what\": \"...\", \"code\": \"agent_none\"}}"
        items = b.get("items", [])
        if not isinstance(items, list) or len(items) > MAX_ITEMS:
            return f"picks.beats.{bid}.items must be a list of at most {MAX_ITEMS}"
        for n, i in enumerate(items):
            p = f"picks.beats.{bid}.items[{n}]"
            if not isinstance(i, dict) or not isinstance(i.get("asset"), str) or not i["asset"]:
                return f"{p}.asset must be a string"
            if i.get("region") is not None and not isinstance(i.get("region"), str):
                return f"{p}.region must be a string or null"
            if "role" in i and i["role"] not in ROLES:
                return f"{p}.role must be one of {', '.join(ROLES)}"
            if "note" in i and i["note"] is not None and not isinstance(i["note"], str):
                return f"{p}.note must be a string"
    return None


# ---------------------------------------------------------------- revision, files
def revision(d: dict) -> str:
    return sstore.revision(d)


def path(pdir: Path) -> Path:
    return Path(pdir) / FILE


def _scale_rough_boxes(assets: dict, before: dict[str, tuple[int, int]]) -> None:
    """Scale each region's recorded `rough` pixel box alongside `_mediaassets.reconcile_sizes` when a stored image size is repaired."""
    for key, (ow, oh) in before.items():
        a = assets.get(key)
        if not isinstance(a, dict) or ow <= 0 or oh <= 0:
            continue
        nw, nh = int(a.get("width") or 0), int(a.get("height") or 0)
        if nw <= 0 or nh <= 0 or (nw, nh) == (ow, oh):
            continue
        kx, ky = nw / float(ow), nh / float(oh)
        for r in (a.get("regions") or {}).values():
            if isinstance(r, dict) and isinstance(r.get("rough"), list) and len(r["rough"]) == 4:
                x0, y0, x1, y1 = r["rough"]
                nx0 = max(0, min(nw - 1, int(round(x0 * kx))))
                ny0 = max(0, min(nh - 1, int(round(y0 * ky))))
                nx1 = max(nx0 + 1, min(nw, int(round(x1 * kx))))
                ny1 = max(ny0 + 1, min(nh, int(round(y1 * ky))))
                r["rough"] = [nx0, ny0, nx1, ny1]


def non_tight_regions(d: dict | None) -> list[str]:
    """Names of the main painting's regions that do not have `tight: true` yet (in document order)."""
    if not isinstance(d, dict):
        return []
    main = d.get("main_asset")
    a = (d.get("assets") or {}).get(main) if isinstance(main, str) else None
    if not isinstance(a, dict) or a.get("kind") == "video":
        return []
    return [name for name, r in (a.get("regions") or {}).items() if isinstance(r, dict) and r.get("tight") is not True]


def load(pdir: Path) -> dict | None:
    """The saved document (normalised), None when there is none. DocumentCorrupt (409 `data_error: "picks"`) when the file
    is there but unreadable. An image asset whose declared size differs from its stored file comes back corrected (size and
    regions, see the module doc); nothing is written here, so the revision of such a document is that of the corrected one."""
    raw = sstore.read_object(path(pdir), "picks")
    if raw is None:
        return None
    d = normalize(raw)
    before = {k: (int(a.get("width") or 0), int(a.get("height") or 0))
              for k, a in d["assets"].items() if isinstance(a, dict) and a.get("kind") != "video"}
    _mediaassets.reconcile_sizes(d["assets"], pdir)          # in memory only: the disk is rewritten by the next save
    _scale_rough_boxes(d["assets"], before)
    return d


def load_or_new(pdir: Path) -> dict:
    return load(pdir) or empty()


def disk_rev(pdir: Path) -> str | None:
    d = load(pdir)
    return None if d is None else revision(d)


def save(pdir: Path, d: dict, base_rev: str | None = None) -> str:
    """Write `d`; the approval is dropped unless it still matches the new revision. `base_rev`, when given, must be the
    revision on disk (StaleRevision otherwise; a missing file has no revision, `None` matches it). The caller holds the
    picks lock and has checked that the project exists."""
    p = path(pdir)
    if p.is_dir():
        raise DocumentCorrupt("%s is corrupt: it is a folder, not a file" % p.name, "picks")
    if base_rev is not None:
        cur = disk_rev(pdir)
        if cur is not None and cur != base_rev:
            raise StaleRevision(cur)
    d = normalize(d)
    _ensure_main_box(pdir, d)
    rev = revision(d)
    if d["approval"].get("sha1") != rev:
        d["approval"] = _approval({})
    if p.is_file():
        try:
            sstore.write_text_atomic(p.with_suffix(".prev.json"), p.read_text(encoding="utf-8"))
        except OSError:
            pass
    sstore.write_json_atomic(p, d)
    return rev


def _ensure_main_box(pdir: Path, d: dict) -> None:
    """The main painting gets the program's finding of its painted area when it has none (a picture made the main one, or a project made before the box
    existed). In place, only an image whose file reads; the box that is there is never replaced."""
    main = d.get("main_asset")
    a = d["assets"].get(main) if isinstance(main, str) else None
    if a is not None and a.get("kind") == "image":
        _contentbox.ensure(a, pdir)


class Held:
    """`with Held(pdir):` the picks lock plus a check that the project still exists (a writer that waited while the project
    was deleted gets ProjectGone and writes nothing)."""

    def __init__(self, pdir: Path):
        self.pdir = Path(pdir)
        self.lock = picks_lock(self.pdir)

    def __enter__(self):
        self.lock.acquire()
        if not self.pdir.is_dir():
            self.lock.release()
            raise ProjectGone("project not found")
        return self

    def __exit__(self, *exc):
        self.lock.release()


# ---------------------------------------------------------------- approval
def approval_state(d: dict | None, narration_rev: str | None, narration_ok: bool) -> dict:
    """`{approved, reason}`: does the recorded approval stand? `reason` (only when an approval was recorded and does not stand):
    `picks_edited` | `narration_changed` | `narration_not_approved`."""
    ap = (d or {}).get("approval") or {}
    if not ap.get("approved"):
        return {"approved": False, "reason": None}
    if ap.get("sha1") != revision(d):
        return {"approved": False, "reason": "picks_edited"}
    if ap.get("narration_sha1") != narration_rev:
        return {"approved": False, "reason": "narration_changed"}
    if not narration_ok:
        return {"approved": False, "reason": "narration_not_approved"}
    return {"approved": True, "reason": None}


def stamp_approval(pdir: Path, rev: str, narration_rev: str, by: str | None = None) -> dict:
    """Write the approval of the saved document; `rev` must be its revision. The caller holds the lock. `by` (c5cli) is who approved."""
    d = load(pdir)
    if d is None:
        raise FileNotFoundError("picks")
    cur = revision(d)
    if cur != rev:
        raise StaleRevision(cur)
    d["approval"] = {"approved": True, "sha1": cur, "approved_at": sstore.now_iso(), "narration_sha1": narration_rev, **({"by": by} if by else {})}
    sstore.write_json_atomic(path(pdir), d)
    return d["approval"]


# ---------------------------------------------------------------- checks
def issues(d: dict | None, pdir: Path | None = None, beat_ids: list[str] | None = None) -> list[dict]:
    """What is wrong or worth a look, as `{level, code, message, beat?, asset?}` (`level` is `error` or `warning`).
    Errors stop the approval: no main painting, an item that points at an asset or a region that does not exist, a missing
    file. Warnings do not: a beat with no pick (the draft shows the main painting there), a flagged asset.
    `beat_ids` is the beat list of the approved narration (None: not known, so no per-beat check)."""
    out: list[dict] = []
    d = d or empty()
    assets = d["assets"]
    main = d.get("main_asset")
    if not main or main not in assets:
        out.append({"level": "error", "code": "no_main", "message": "no main painting is chosen"})
    cb = (assets.get(main) or {}).get("content_box") if main else None
    if isinstance(cb, dict) and cb.get("how") == "unsure":      # panelbox: the program found a dark or light band it did not believe: it uses the whole picture, and says so
        out.append({"level": "warning", "code": "content_box_unsure", "asset": main,
                    "message": "the painted area of the main painting is not sure: " + _contentbox.NOTES.get(cb.get("note"), "the whole picture is used")})
    for key, a in assets.items():
        if pdir is not None and not (Path(pdir) / a["file"]).is_file():
            out.append({"level": "error", "code": "asset_file_missing", "asset": key,
                        "message": f"the file of asset {key} is missing"})
        flag = (a.get("credit") or {}).get("flag")
        if flag:
            out.append({"level": "warning", "code": "asset_flag", "asset": key, "flag": flag,
                        "message": f"asset {key} is flagged {flag}"})
    known = set(beat_ids) if beat_ids is not None else None
    for bid, b in d["beats"].items():
        for n, i in enumerate(b["items"]):
            a = assets.get(i["asset"])
            if a is None:
                out.append({"level": "error", "code": "unknown_asset", "beat": bid, "asset": i["asset"],
                            "message": f"beat {bid} uses asset {i['asset']}, which is not in the picks"})
            elif i["region"] and i["region"] not in a["regions"]:
                out.append({"level": "error", "code": "unknown_region", "beat": bid, "asset": i["asset"], "region": i["region"],
                            "message": f"beat {bid} uses region {i['region']} of {i['asset']}, which does not exist"})
        if known is not None and bid not in known:
            out.append({"level": "warning", "code": "beat_unknown", "beat": bid,
                        "message": f"picks for beat {bid}, which is not in the narration"})
        elif outside_without_picture(d, bid):
            out.append({"level": "warning", "code": "outside_no_picture", "beat": bid,
                        "message": f"beat {bid} is about something outside the painting but shows only the main painting: no picture of the thing itself "
                                   f"was found{_missing_words(b)}"})
    if known is not None:
        for bid in beat_ids or []:
            b = d["beats"].get(bid)
            if (b is None or not b["items"]) and (b is None or b["status"] != "skip"):
                out.append({"level": "warning", "code": "beat_no_pick", "beat": bid,
                            "message": f"beat {bid} has no pick: the draft will use the main painting there"})
    return out


def _missing_words(b: dict) -> str:
    what = [m["what"] for m in b.get("missing") or []]
    return " (looked for: %s)" % "; ".join(what[:3]) if what else ""


def outside_without_picture(d: dict, bid: str) -> bool:
    """Is this beat a line about something outside the painting (`kinds` holds `outside` or `compare`) that shows only the main painting, so that the picture
    of the thing itself is missing? A line the owner or the agent settled with `skip` (the main picture again, on purpose) is not; a beat without `kinds`
    (a document made before they existed) never is."""
    b = (d.get("beats") or {}).get(bid)
    if not b or b.get("status") == "skip" or not set(b.get("kinds") or ()) & set(OUTSIDE_KINDS):
        return False
    main = d.get("main_asset")
    if all(i["asset"] == main for i in b["items"]):
        return True
    return isinstance(d.get("subjects"), list) and bool(b.get("missing"))


def outside_summary(d: dict | None, beat_ids: list[str] | None = None) -> dict:
    """`{"lines": n, "with_picture": n, "without": [beat ids]}`: the lines about something outside the painting (kinds `outside` or `compare`, not `skip`),
    how many of them show a picture of something else than the main painting, and which do not. `beat_ids`: the narration's lines, in order (a beat that
    is not in it is not counted); None: the beats of the document. A document with no `kinds` anywhere says `{"lines": 0, "with_picture": 0, "without": []}`."""
    d = d or empty()
    order = [b for b in (beat_ids if beat_ids is not None else d["beats"]) if b in d["beats"]]
    lines, without = 0, []
    for bid in order:
        b = d["beats"][bid]
        if b.get("status") == "skip" or not set(b.get("kinds") or ()) & set(OUTSIDE_KINDS):
            continue
        lines += 1
        if outside_without_picture(d, bid):
            without.append(bid)
    return {"lines": lines, "with_picture": lines - len(without), "without": without}


def blocking(iss: list[dict]) -> list[dict]:
    return [i for i in iss if i["level"] == "error"]


def clone(d: dict) -> dict:
    return copy.deepcopy(d)
