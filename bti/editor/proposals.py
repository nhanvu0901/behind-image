"""Proposals: diff of an agent's storyboard against the saved one, and apply.

Change ids are stable and readable: `shot.<id>`, `overlay.<shot>.<id>`,
`asset.<key>`, `end`. A change that touches an item with `locked: true` in the
SAVED storyboard is `blocked_by_lock` and is never applied.
"""
from __future__ import annotations

import copy
from typing import Any

from .common import ApiError, strip_derived

MISSING = object()
IGNORED_FIELDS = {"overlays", "source", "locked"}


def _fields_diff(a: dict, b: dict, ignore=IGNORED_FIELDS) -> tuple[dict, dict, list[str]]:
    before, after, names = {}, {}, []
    for k in sorted(set(a) | set(b)):
        if k in ignore:
            continue
        va, vb = a.get(k, MISSING), b.get(k, MISSING)
        if va != vb:
            names.append(k)
            before[k] = None if va is MISSING else va
            after[k] = None if vb is MISSING else vb
    return before, after, names


def _by_id(items: Any) -> dict[str, dict]:
    out = {}
    for it in items or []:
        if isinstance(it, dict) and isinstance(it.get("id"), str):
            out[it["id"]] = it
    return out


def shape_problem(sb: Any) -> str | None:
    """None when a proposed storyboard has the shape `diff` and `apply` rely on (lists of objects, assets by key), else why not."""
    if not isinstance(sb, dict):
        return "storyboard must be an object"
    if "assets" in sb and not (isinstance(sb["assets"], dict) and all(isinstance(a, dict) for a in sb["assets"].values())):
        return "assets must be an object of objects"
    if "end" in sb and sb["end"] is not None and not isinstance(sb["end"], dict):
        return "end must be an object"
    shots = sb.get("shots", [])
    if not (isinstance(shots, list) and all(isinstance(s, dict) for s in shots)):
        return "shots must be a list of objects"
    for s in shots:
        ovs = s.get("overlays", [])
        if not (isinstance(ovs, list) and all(isinstance(o, dict) for o in ovs)):
            return f"shot {s.get('id')!r}: overlays must be a list of objects"
    return None


def diff(saved: dict, proposed: dict) -> list[dict]:
    saved, proposed = strip_derived(saved), strip_derived(proposed)
    changes: list[dict] = []
    s_shots, p_shots = _by_id(saved.get("shots")), _by_id(proposed.get("shots"))

    def add(cid, op, kind, path, before, after, blocked, **extra):
        changes.append({"id": cid, "op": op, "kind": kind, "path": path, "before": before, "after": after,
                        "blocked_by_lock": bool(blocked), **extra})

    # assets (needed so that proposed shots can reference new media)
    sa, pa = saved.get("assets") or {}, proposed.get("assets") or {}
    for k in sorted(pa):
        if k not in sa:
            add(f"asset.{k}", "add", "asset", f"assets.{k}", None, pa[k], False, item_id=k)
        elif sa[k] != pa[k]:
            b, a, names = _fields_diff(sa[k], pa[k], ignore=set())
            add(f"asset.{k}", "change", "asset", f"assets.{k}", b, a, False, item_id=k, fields=names)

    for sid in p_shots:
        if sid in s_shots:
            continue
        add(f"shot.{sid}", "add", "shot", f"shots[id={sid}]", None, p_shots[sid], False, item_id=sid)
    for sid, ss in s_shots.items():
        path = f"shots[id={sid}]"
        locked = bool(ss.get("locked")) or any(bool(o.get("locked")) for o in (ss.get("overlays") or []) if isinstance(o, dict))
        if sid not in p_shots:
            add(f"shot.{sid}", "remove", "shot", path, ss, None, locked, item_id=sid)
            continue
        ps = p_shots[sid]
        b, a, names = _fields_diff(ss, ps)
        if names:
            add(f"shot.{sid}", "change", "shot", path, b, a, bool(ss.get("locked")), item_id=sid, fields=names)
        so, po = _by_id(ss.get("overlays")), _by_id(ps.get("overlays"))
        parent_locked = bool(ss.get("locked"))
        for oid, o in po.items():
            if oid not in so:
                add(f"overlay.{sid}.{oid}", "add", "overlay", f"{path}.overlays[id={oid}]", None, o, parent_locked,
                    item_id=oid, shot_id=sid)
        for oid, o in so.items():
            opath = f"{path}.overlays[id={oid}]"
            lk = parent_locked or bool(o.get("locked"))
            if oid not in po:
                add(f"overlay.{sid}.{oid}", "remove", "overlay", opath, o, None, lk, item_id=oid, shot_id=sid)
                continue
            ob, oa, onames = _fields_diff(o, po[oid])
            if onames:
                add(f"overlay.{sid}.{oid}", "change", "overlay", opath, ob, oa, lk, item_id=oid, shot_id=sid,
                    fields=onames)
    se, pe = saved.get("end"), proposed.get("end")
    if isinstance(pe, dict) and pe != se:
        add("end", "change", "end", "end", se, pe, False)
    return changes


def adopt(proposed: dict) -> dict:
    """The first storyboard of a project, from a proposal: the whole document, every shot and overlay marked `source: "agent"`
    and not locked, and an empty approval."""
    doc = strip_derived(copy.deepcopy(proposed))
    for s in doc.get("shots") or []:
        if not isinstance(s, dict):
            continue
        s["source"], s["locked"] = "agent", False
        for o in s.get("overlays") or []:
            if isinstance(o, dict):
                o["source"], o["locked"] = "agent", False
    doc["approvals"] = {"storyboard": None}
    return doc


def apply(saved: dict, proposed: dict, accept: Any) -> tuple[dict, list[str], list[str]]:
    """Return (new storyboard, applied ids, skipped-by-lock ids)."""
    saved, proposed = strip_derived(saved), strip_derived(proposed)
    changes = diff(saved, proposed)
    by_id = {c["id"]: c for c in changes}
    if accept == "all":
        chosen = [c["id"] for c in changes]
    elif isinstance(accept, list) and all(isinstance(x, str) for x in accept):
        unknown = [x for x in accept if x not in by_id]
        if unknown:
            raise ApiError(422, f"unknown change ids: {unknown}")
        chosen = list(dict.fromkeys(accept))
    else:
        raise ApiError(422, 'accept must be "all" or a list of change ids')
    skipped = [i for i in chosen if by_id[i]["blocked_by_lock"]]
    todo = [by_id[i] for i in chosen if not by_id[i]["blocked_by_lock"]]

    doc = copy.deepcopy(saved)
    shots: list = doc.setdefault("shots", [])
    p_shots = _by_id(proposed.get("shots"))
    p_order = [s["id"] for s in proposed.get("shots") or [] if isinstance(s, dict) and "id" in s]

    def find(sid):
        return next((s for s in shots if isinstance(s, dict) and s.get("id") == sid), None)

    for c in [c for c in todo if c["kind"] == "asset"]:
        doc.setdefault("assets", {})[c["item_id"]] = copy.deepcopy(proposed["assets"][c["item_id"]])
    for c in [c for c in todo if c["kind"] == "shot" and c["op"] == "remove"]:
        shots[:] = [s for s in shots if s.get("id") != c["item_id"]]
    for c in [c for c in todo if c["kind"] == "shot" and c["op"] == "change"]:
        s = find(c["item_id"])
        if s is None:
            continue
        ps = p_shots[c["item_id"]]
        for k in c["fields"]:
            if k in ps:
                s[k] = copy.deepcopy(ps[k])
            else:
                s.pop(k, None)
        s["source"] = "agent"
    for sid in p_order:
        c = by_id.get(f"shot.{sid}")
        if not c or c["op"] != "add" or c not in todo:
            continue
        new = copy.deepcopy(p_shots[sid])
        new["source"] = "agent"
        new["locked"] = False
        for o in new.get("overlays") or []:
            o["source"] = "agent"
            o["locked"] = False
        idx = 0
        for prev in reversed(p_order[: p_order.index(sid)]):
            pos = next((i for i, s in enumerate(shots) if s.get("id") == prev), None)
            if pos is not None:
                idx = pos + 1
                break
        shots.insert(idx, new)
    for c in [c for c in todo if c["kind"] == "overlay"]:
        s = find(c["shot_id"])
        if s is None:
            continue
        ovs = s.setdefault("overlays", [])
        po = _by_id(p_shots[c["shot_id"]].get("overlays")) if c["shot_id"] in p_shots else {}
        if c["op"] == "remove":
            ovs[:] = [o for o in ovs if o.get("id") != c["item_id"]]
        elif c["op"] == "add":
            new = copy.deepcopy(po[c["item_id"]])
            new["source"] = "agent"
            new["locked"] = False
            ovs.append(new)
        else:
            o = next((o for o in ovs if o.get("id") == c["item_id"]), None)
            if o is None:
                continue
            for k in c["fields"]:
                if k in po[c["item_id"]]:
                    o[k] = copy.deepcopy(po[c["item_id"]][k])
                else:
                    o.pop(k, None)
            o["source"] = "agent"
    for c in todo:
        if c["kind"] == "end":
            doc["end"] = copy.deepcopy(proposed["end"])
    return doc, [c["id"] for c in todo], skipped
