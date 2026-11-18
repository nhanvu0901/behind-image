"""A compiled shot is compared with the saved one before anything is listed as a change or written.

The compiler fills every parameter of a technique with the registry default (a camera shot gains `"shadow": true`). A shot the saved
storyboard did not carry that parameter for must not gain it: nothing visible changes, but the stored shot differs, and a shot the model
returned unchanged would be listed as changed. `keep_saved` does two things for every shot that has a saved version (same id):

1. a parameter whose value is the registry default and which the saved shot did not carry is not written (shot and overlays);
2. a shot that is then equal to the saved one (the `source` flag aside) is replaced by the saved one, verbatim.
"""
from __future__ import annotations

import copy
import json


def _clean(o):
    def strip(x):
        if isinstance(x, dict):
            return {k: strip(v) for k, v in x.items() if not str(k).startswith("_")}
        if isinstance(x, list):
            return [strip(v) for v in x]
        return x
    return json.dumps(strip(o), sort_keys=True, ensure_ascii=False, default=str)


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-9
    return a == b


def _strip_defaults(node: dict, saved: dict, bundle) -> None:
    sp = bundle.spec(node.get("technique")) or {}
    params = node.get("params")
    if not isinstance(params, dict):
        return
    saved_params = saved.get("params") or {}
    for p in sp.get("params") or []:
        name = p.get("name")
        if name in params and name not in saved_params and p.get("default") is not None and _same(params[name], p["default"]):
            del params[name]


def keep_saved(saved_sb: dict | None, compiled_sb: dict, bundle) -> dict:
    """`compiled_sb` (modified in place and returned) with registry defaults the saved shots did not carry removed, and every shot
    that equals its saved version replaced by it."""
    saved = {s["id"]: s for s in (saved_sb or {}).get("shots", []) if isinstance(s, dict) and s.get("id")}
    out = []
    for s in compiled_sb.get("shots", []):
        old = saved.get(s.get("id")) if isinstance(s, dict) else None
        if old is None:
            out.append(s)
            continue
        _strip_defaults(s, old, bundle)
        old_ovs = old.get("overlays") or []
        for i, o in enumerate(s.get("overlays") or []):
            if i < len(old_ovs) and isinstance(o, dict) and old_ovs[i].get("technique") == o.get("technique"):
                _strip_defaults(o, old_ovs[i], bundle)
        a = {k: v for k, v in s.items() if k != "source"}
        b = {k: v for k, v in old.items() if k != "source"}
        out.append(copy.deepcopy(old) if _clean(a) == _clean(b) else s)
    compiled_sb["shots"] = out
    return compiled_sb
