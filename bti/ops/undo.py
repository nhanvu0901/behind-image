"""Undo of one batch: bring back what the batch changed, and nothing else.

The batch's record keeps copies of the document before and after it. The things it changed are the things whose value differs
between those two copies (`bti.ops.things`). The batch can be undone when each of those things is still as the batch left it
in the CURRENT document, whoever changed the document in between (a later batch, or a save of the page, which is not logged):
then each is put back to its value before the batch and everything else stays. When one of them was changed since, nothing is
undone and `undo_conflict` names it, with the later batches that touched it when the log knows them. A save of the page is not
in the log, so a thing it changed is named with no batch.

This is the same meaning as the three-way undo of the instruction box (`bti.draft.merge.undo_turn`: compare the shots the turn
touched with the version the turn left, restore the version before it), except that shots a batch removed come back in their
place in the order they had (the instruction box's version of that step depends on the order of a set).
"""
from __future__ import annotations

import copy
from typing import Any

from . import things
from .errors import OpError
from .ctx import pic_name
from .timeline import fmt_time

UNDO_SENTENCES = {
    "storyboard": {
        "restore": "Cảnh {n}: trở lại như trước khi sửa",
        "remove_added": "Đã bỏ cảnh {id} do lô được hoàn tác tạo ra",
        "restore_removed": "Cảnh {n}: đã khôi phục",
    },
    "picks": {
        "main": "Tranh chính: trở lại như trước, {pic}",
        "beat": "Đoạn {n}: trở lại như trước khi sửa",
        "regions": "Vùng của {pic}: trở lại như trước khi sửa",
        "asset_removed": "Đã bỏ {pic} khỏi dự án (do lô được hoàn tác nhập)",
        "asset_restored": "Đã trả lại {pic} vào dự án",
    },
}


def thing_ref(doc_kind: str, key: str) -> dict:
    kind, _, ident = key.partition(":")
    if doc_kind == "storyboard":
        return {"shot": ident}
    if key == "main":
        return {"main": True}
    if kind == "beat":
        return {"beat": ident}
    return {"asset": ident} if kind == "asset" else {"asset": ident, "part": "regions"}


def find_conflicts(doc_kind: str, current: dict, before: dict, after: dict, later: list[dict]) -> tuple[list[str], list[dict]]:
    """`(keys, conflicts)`: the things the batch changed, and those of them that are not as the batch left them any more.
    `later` are the records newer than the batch, to name who changed a conflicting thing."""
    keys = things.changed_keys(doc_kind, before, after)
    conflicts = []
    for key in keys:
        if not things.same(things.get(doc_kind, current, key), things.get(doc_kind, after, key)):
            by = [r["batch"] for r in later if key in (r.get("touched") or [])]
            conflicts.append({"thing": thing_ref(doc_kind, key), "key": key, "batches": by})
    return keys, conflicts


def conflict_error(conflicts: list[dict], batch: str) -> OpError:
    names = ", ".join(sorted({"%s %s" % next(iter(c["thing"].items())) for c in conflicts}))[:200]
    return OpError("undo_conflict", "Batch %s cannot be undone: %s changed since it was applied." % (batch, names), conflicts=conflicts)


# ---------------------------------------------------------------- restoring
def restore_picks(current: dict, before: dict, keys: list[str]) -> dict:
    """The current picks with each thing of `keys` put back to its value in `before` (assets that came back first, assets that
    go away last, so that nothing is ever without its asset in between)."""
    doc = copy.deepcopy(current)
    kind = lambda k: k.partition(":")[0]                                                   # noqa: E731
    adds = [k for k in keys if kind(k) == "asset" and things.get("picks", before, k) is not None]
    drops = [k for k in keys if kind(k) == "asset" and things.get("picks", before, k) is None]
    rest = [k for k in keys if kind(k) != "asset"]
    for k in adds + rest + drops:
        things.put_picks(doc, k, things.get("picks", before, k))
    return doc


def restore_shots(current: dict, before: dict, keys: list[str]) -> dict:
    """The current storyboard with each shot of `keys` put back to its version in `before`: a shot the batch added is removed, a shot
    it removed comes back right after the shot that preceded it before the batch."""
    doc = copy.deepcopy(current)
    ids = {k.partition(":")[2] for k in keys}
    before_shots = [s for s in before.get("shots") or [] if isinstance(s, dict)]
    before_by = {s.get("id"): s for s in before_shots}
    out = []
    for s in doc.get("shots") or []:
        sid = s.get("id") if isinstance(s, dict) else None
        if sid in ids:
            if sid in before_by:
                out.append(copy.deepcopy(things.strip_derived(before_by[sid])))
            continue
        out.append(s)
    for pos, s in enumerate(before_shots):             # in the order they had: a predecessor that came back first is found
        sid = s.get("id")
        if sid not in ids or any(isinstance(x, dict) and x.get("id") == sid for x in out):
            continue
        pred = next((p.get("id") for p in reversed(before_shots[:pos]) if any(isinstance(x, dict) and x.get("id") == p.get("id") for x in out)), None)
        at = 0 if pred is None else 1 + next(k for k, x in enumerate(out) if isinstance(x, dict) and x.get("id") == pred)
        out.insert(at, copy.deepcopy(things.strip_derived(s)))
    doc["shots"] = out
    return doc


def undo_changes(doc_kind: str, new_doc: dict, before: dict, after: dict, keys: list[str], facts: Any) -> list[dict]:
    """The `changes` entries of an undo: one Vietnamese sentence for each thing that was put back."""
    t = UNDO_SENTENCES[doc_kind]
    out = []
    if doc_kind == "storyboard":
        order = [s.get("id") for s in new_doc.get("shots") or []]
        for key in keys:
            sid = key.partition(":")[2]
            b, a = things.get("storyboard", before, key), things.get("storyboard", after, key)
            if b is None:
                out.append({"target": {"shot": sid}, "time": None, "what": t["remove_added"].format(id=sid)})
                continue
            n = order.index(sid) + 1 if sid in order else sid
            when = fmt_time(facts.timeline.resolve(b.get("start")))
            out.append({"target": {"shot": sid}, "time": when, "what": t["restore" if a is not None else "restore_removed"].format(n=n)})
        return out
    for key in keys:
        kind, _, ident = key.partition(":")
        if key == "main":
            main = new_doc.get("main_asset")
            out.append({"target": {"asset": main}, "time": None,
                        "what": t["main"].format(pic=pic_name(new_doc, main) if main else "chưa chọn tranh nào")})
        elif kind == "beat":
            out.append({"target": {"beat": ident}, "time": facts.beat_time(ident), "what": t["beat"].format(n=facts.beat_no(ident))})
        elif kind == "asset":
            gone = things.get("picks", before, key) is None
            out.append({"target": {"asset": ident}, "time": None,
                        "what": t["asset_removed" if gone else "asset_restored"].format(pic=pic_name(after if gone else new_doc, ident))})
        elif ident in (before.get("assets") or {}) and ident in (new_doc.get("assets") or {}) and ident in (after.get("assets") or {}):
            out.append({"target": {"asset": ident}, "time": None, "what": t["regions"].format(pic=pic_name(new_doc, ident))})
    return out
