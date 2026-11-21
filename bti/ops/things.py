"""The "things" of a document: the units a batch changes and an undo puts back.

A thing has a key. Storyboard: `shot:<id>` (the whole shot, its overlays included). Picks: `main` (the main picture),
`beat:<id>` (the pictures, status and note of one narration line), `regions:<asset>` (the regions of one asset) and
`asset:<key>` (the asset itself, without its regions). Two versions of a document differ exactly in the things whose values
differ, and an undo compares the current value of each such thing with the value the batch left (`after`).
"""
from __future__ import annotations

import copy
import json
from typing import Any


def strip_derived(obj: Any) -> Any:
    """A copy without the keys that start with `_` (derived values never take part in a comparison)."""
    if isinstance(obj, dict):
        return {k: strip_derived(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [strip_derived(v) for v in obj]
    return obj


def canon(obj: Any) -> str:
    return json.dumps(strip_derived(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def same(a: Any, b: Any) -> bool:
    return canon(a) == canon(b)


def _split(key: str) -> tuple[str, str]:
    kind, _, ident = key.partition(":")
    return kind, ident


def get(doc_kind: str, doc: dict, key: str) -> Any:
    """The current value of a thing, None when it does not exist. The value is not copied."""
    kind, ident = _split(key)
    if doc_kind == "storyboard":
        if kind == "shot":
            return next((s for s in doc.get("shots") or [] if isinstance(s, dict) and s.get("id") == ident), None)
        raise KeyError(key)
    if key == "main":
        return doc.get("main_asset")
    if key == "names":
        return doc.get("names")
    if kind == "beat":
        return (doc.get("beats") or {}).get(ident)
    asset = (doc.get("assets") or {}).get(ident)
    if kind == "regions":
        return None if asset is None else asset.get("regions") or {}
    if kind == "asset":
        return None if asset is None else {k: v for k, v in asset.items() if k != "regions"}
    raise KeyError(key)


def keys(doc_kind: str, doc: dict) -> set[str]:
    """Every thing key a document has."""
    if doc_kind == "storyboard":
        return {"shot:%s" % s["id"] for s in doc.get("shots") or [] if isinstance(s, dict) and isinstance(s.get("id"), str)}
    out = {"main"}
    if "names" in doc:
        out.add("names")
    out.update("beat:%s" % b for b in (doc.get("beats") or {}))
    for k in (doc.get("assets") or {}):
        out.add("asset:%s" % k)
        out.add("regions:%s" % k)
    return out


def changed_keys(doc_kind: str, before: dict, after: dict) -> list[str]:
    """The things whose value differs between two versions of a document, sorted."""
    out = []
    for key in sorted(keys(doc_kind, before) | keys(doc_kind, after)):
        if not same(get(doc_kind, before, key), get(doc_kind, after, key)):
            out.append(key)
    return out


def put_picks(doc: dict, key: str, value: Any) -> None:
    """Set a picks thing to `value` (a copy is stored); None removes it (an asset and its regions go together)."""
    kind, ident = _split(key)
    value = copy.deepcopy(value)
    if key == "main":
        doc["main_asset"] = value
    elif key == "names":
        if value is None:
            doc.pop("names", None)
        else:
            doc["names"] = value
    elif kind == "beat":
        if value is None:
            doc["beats"].pop(ident, None)
        else:
            doc["beats"][ident] = value
    elif kind == "asset":
        if value is None:
            doc["assets"].pop(ident, None)
        else:
            doc["assets"][ident] = {**value, "regions": (doc["assets"].get(ident) or {}).get("regions") or {}}
    elif kind == "regions":
        if ident in doc["assets"]:
            doc["assets"][ident]["regions"] = value or {}
    else:
        raise KeyError(key)


def target_of(doc_kind: str, key: str) -> dict:
    """The `target` object of a change entry for a thing key."""
    kind, ident = _split(key)
    if doc_kind == "storyboard":
        return {"shot": ident}
    if key == "main":
        return {"asset": None}
    if key == "names":
        return {"part": "names"}
    return {"beat": ident} if kind == "beat" else {"asset": ident}
