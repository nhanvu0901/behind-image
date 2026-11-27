"""Small reader for `visual.json` (`bti.visual/1`, design 2026-11-27 section 4.2)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA = "bti.visual/1"
SHOWN_KINDS = frozenset({"person", "place", "work", "thing"})


def load_visual(project_dir: Path) -> dict | None:
    """Return `visual.json` as a dict when present and valid (`bti.visual/1`), else None."""
    path = Path(project_dir) / "visual.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        return None
    return doc


def cast_by_id(visual: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for entry in visual.get("cast") or []:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]:
            out[entry["id"]] = entry
    return out


def cast_person_regions(visual: dict) -> dict[str, str]:
    """Return `{region_name: person_name}` for every `person` cast entry's `shown_by` regions."""
    out: dict[str, str] = {}
    for entry in visual.get("cast") or []:
        if not isinstance(entry, dict) or entry.get("kind") != "person":
            continue
        name = str(entry.get("name") or entry.get("id") or "")
        for place in entry.get("shown_by") or []:
            if isinstance(place, dict) and isinstance(place.get("region"), str) and place["region"]:
                out.setdefault(place["region"], name)
    return out


def cast_strip_entries(visual: dict) -> list[dict]:
    """Normalize `cast` entries into `{id, kind, name, also, strip, sub}` for strip checks."""
    out: list[dict] = []
    for entry in visual.get("cast") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        out.append({
            "id": entry.get("id"),
            "kind": entry.get("kind"),
            "name": entry["name"],
            "also": [a for a in (entry.get("also") or []) if isinstance(a, str)],
            "strip": entry.get("strip"),
            "sub": entry.get("sub") or "",
        })
    return out


def _show_matches_place(show: Any, place: dict, wanted_by_id: dict[str, dict]) -> bool:
    if not isinstance(show, dict) or not isinstance(place, dict):
        return False
    if "region" in place and show.get("region") == place["region"]:
        return True
    if "picture" in place:
        if show.get("picture") == place["picture"]:
            return True
        if isinstance(show.get("pair"), list) and any(isinstance(p, dict) and p.get("picture") == place["picture"] for p in show["pair"]):
            return True
    return False


def _moment_shows_member(moment: dict, member: dict, wanted_by_id: dict[str, dict]) -> bool:
    show = moment.get("show")
    if not isinstance(show, dict):
        return False
    mid = member.get("id")
    if "want" in show:
        w = wanted_by_id.get(show.get("want"))
        if w and w.get("subject") == mid:
            if w.get("status") != "none":
                return True
            show = show.get("else") or {}
    if "map" in show and member.get("kind") == "place":
        return True
    places = member.get("shown_by") or []
    return any(_show_matches_place(show, pl, wanted_by_id) for pl in places)


def moments_subject_not_shown(visual: dict, timing: dict | None = None, *, shot_by_moment: dict[str, tuple[str, float]] | None = None) -> list[dict]:
    """List moments where `about` names a concrete cast member that `show` does not show."""
    cast = cast_by_id(visual)
    wanted = {w["id"]: w for w in (visual.get("wanted") or []) if isinstance(w, dict) and isinstance(w.get("id"), str)}
    words = (timing or {}).get("words") if isinstance((timing or {}).get("words"), list) else []
    beats = {b["id"]: b for b in ((timing or {}).get("beats") or []) if isinstance(b, dict) and isinstance(b.get("id"), str)}
    out: list[dict] = []
    for m in visual.get("moments") or []:
        if not isinstance(m, dict):
            continue
        about = m.get("about")
        if not isinstance(about, str) or about not in cast:
            continue
        member = cast[about]
        if member.get("kind") not in SHOWN_KINDS:
            continue
        reason = m.get("about_not_shown")
        shown = _moment_shows_member(m, member, wanted)
        if shown and not reason:
            continue
        sid, t_val = (shot_by_moment or {}).get(str(m.get("id") or ""), (None, None))
        if t_val is None:
            w0 = m.get("w0")
            if isinstance(w0, int) and 0 <= w0 < len(words) and isinstance(words[w0].get("s"), (int, float)):
                t_val = float(words[w0]["s"])
            elif isinstance(m.get("line"), str) and m["line"] in beats:
                st = beats[m["line"]].get("start")
                if isinstance(st, (int, float)):
                    t_val = float(st)
        out.append({
            "shot": sid or str(m.get("id") or ""),
            "time": round(float(t_val), 2) if t_val is not None else None,
            "moment": m.get("id"),
            "beat": m.get("line"),
            "subject": about,
            "name": member.get("name") or about,
            "reason": str(reason) if reason else "show does not match subject",
        })
    return out
