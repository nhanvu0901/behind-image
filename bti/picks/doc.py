"""The `bti.picks/1` document: what is on screen for each beat of the narration.

`projects/<pid>/picks.json`:

    {"schema": "bti.picks/1", "main_asset": "A",
     "assets": {"A": {file, kind, title, artist, year, width, height, credit{..., flag}, regions{NAME: {x, y, rx, ry, label}}}},
     "beats": {"b0007": {"items": [{asset, region, role, note}], "status": "todo|picked|skip", "note": ""}},
     "approval": {"approved", "sha1", "approved_at", "narration_sha1"}}

The field names are read by the storyboard draft agent: do not rename them. `assets` has the shape of `storyboard.assets`.

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
    return out


def _region(r: Any) -> dict | None:
    if not isinstance(r, dict) or not all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
                                          and math.isfinite(r[k]) for k in ("x", "y")):
        return None
    out = {"x": r["x"], "y": r["y"]}
    for k in ("rx", "ry"):
        if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool) and math.isfinite(r[k]) and r[k] > 0:
            out[k] = r[k]
    out["label"] = _s(r.get("label"))
    return out


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
    return {"file": _s(a["file"]), "kind": "video" if a.get("kind") == "video" else "image", "title": _s(a.get("title")),
            "artist": _s(a.get("artist")), "year": _s(a.get("year")), "width": _int(a.get("width")),
            "height": _int(a.get("height")), "credit": credit, "regions": regions}


def _item(i: Any) -> dict | None:
    if not isinstance(i, dict) or not _s(i.get("asset")):
        return None
    region = i.get("region")
    return {"asset": _s(i["asset"]), "region": _s(region) if region else None,
            "role": i.get("role") if i.get("role") in ROLES else "detail", "note": _s(i.get("note"))}


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
    main = d.get("main_asset")
    return {"schema": SCHEMA, "main_asset": main if isinstance(main, str) and main in assets else None,
            "assets": assets, "beats": beats, "approval": _approval(d.get("approval"))}


def doc_problem(d: Any) -> str | None:
    """None when `d`, sent by a client, has the right shape; else what is wrong. Strict: nothing is coerced."""
    if not isinstance(d, dict):
        return "picks (object) is required"
    if "main_asset" in d and d["main_asset"] is not None and not isinstance(d["main_asset"], str):
        return "picks.main_asset must be a string or null"
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
        regions = a.get("regions", {})
        if not isinstance(regions, dict):
            return f"picks.assets.{k}.regions must be an object"
        for name, r in regions.items():
            if not isinstance(name, str) or not REGION_RE.fullmatch(name):
                return f"region name {str(name)[:40]!r} is not valid"
            if _region(r) is None:
                return f"region {name!r} needs numeric x and y"
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


def load(pdir: Path) -> dict | None:
    """The saved document (normalised), None when there is none. DocumentCorrupt (409 `data_error: "picks"`) when the file
    is there but unreadable."""
    raw = sstore.read_object(path(pdir), "picks")
    return None if raw is None else normalize(raw)


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


def stamp_approval(pdir: Path, rev: str, narration_rev: str) -> dict:
    """Write the approval of the saved document; `rev` must be its revision. The caller holds the lock."""
    d = load(pdir)
    if d is None:
        raise FileNotFoundError("picks")
    cur = revision(d)
    if cur != rev:
        raise StaleRevision(cur)
    d["approval"] = {"approved": True, "sha1": cur, "approved_at": sstore.now_iso(), "narration_sha1": narration_rev}
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
    if known is not None:
        for bid in beat_ids or []:
            b = d["beats"].get(bid)
            if (b is None or not b["items"]) and (b is None or b["status"] != "skip"):
                out.append({"level": "warning", "code": "beat_no_pick", "beat": bid,
                            "message": f"beat {bid} has no pick: the draft will use the main painting there"})
    return out


def blocking(iss: list[dict]) -> list[dict]:
    return [i for i in iss if i["level"] == "error"]


def clone(d: dict) -> dict:
    return copy.deepcopy(d)
