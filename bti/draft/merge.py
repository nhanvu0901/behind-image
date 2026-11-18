"""Three-way merge and undo logic for storyboard editing (contract A3 and A4).

Pure, tested functions mirroring bti/editor/static/js/sbmerge.js.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any

from bti.engine.timing import Timing


def clean_shot(s: dict) -> dict:
    """Return a shot dictionary stripped of derived _ keys."""
    if not isinstance(s, dict):
        return {}
    out = {}
    for k, v in s.items():
        if not str(k).startswith("_"):
            out[k] = copy.deepcopy(v)
    return out


def canon(obj: Any) -> str:
    """Canonical JSON string for equality comparison."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


@dataclass
class MergeResult:
    status: str       # "same" | "merged" | "needs_choice"
    storyboard: dict | None
    conflicts: list[dict] = field(default_factory=list)
    touched_ids: set[str] = field(default_factory=set)
    from_theirs: list[str] = field(default_factory=list)


def shots_of(sb: dict | None) -> list[dict]:
    if not isinstance(sb, dict):
        return []
    return [s for s in sb.get("shots", []) if isinstance(s, dict)]


def shots_map(sb: dict | None) -> dict[str, dict]:
    return {s["id"]: clean_shot(s) for s in shots_of(sb) if s.get("id")}


def compute_changes(
    before_sb: dict,
    after_sb: dict,
    model_changes: list[dict] | None = None,
    timing: dict | None = None,
) -> list[dict]:
    """Changes list `[{shot_id, number, start, op: 'changed'|'added'|'removed', what, what_source, facts}]`.

    `facts` are built by code from the difference of the shot before and after, in plain Vietnamese (bti/draft/describe.py). `what` is
    the model's own sentence for that shot (found by shot id) when it passes the check of `describe.sentence_ok`, else the facts joined
    (`what_source` is `model` or `code`)."""
    from bti.draft import describe as DS
    b_shots = shots_map(before_sb)
    a_shots_list = shots_of(after_sb)
    a_shots = shots_map(after_sb)

    tm = Timing({"duration": timing.get("duration", 0), "words": timing.get("words", [])}) if timing else None
    bundle = DS._bundle(after_sb or before_sb)
    assets = (after_sb or {}).get("assets") or (before_sb or {}).get("assets") or {}

    what_map: dict[str, str] = {}
    for ch in model_changes or []:
        if isinstance(ch, dict) and isinstance(ch.get("shot"), str) and isinstance(ch.get("what"), str):
            what_map[ch["shot"]] = ch["what"]

    def start_of(shot):
        st = shot.get("start")
        if tm and isinstance(st, dict):
            try:
                return tm.resolve(st)
            except Exception:       # noqa: BLE001
                pass
        return st

    out: list[dict] = []
    for num, s in enumerate(a_shots_list, 1):
        sid = s.get("id")
        if not sid:
            continue
        if sid not in b_shots:
            facts = DS.added_facts(a_shots[sid], bundle=bundle)
            what, src = DS.what_for(None, facts)
            out.append({"shot_id": sid, "number": num, "start": start_of(s), "op": "added", "what": what, "what_source": src, "facts": facts})
        elif canon(a_shots[sid]) != canon(b_shots[sid]):
            facts = DS.shot_facts(b_shots[sid], a_shots[sid], assets=assets, bundle=bundle, tm=tm)
            what, src = DS.what_for(what_map.get(sid), facts)
            out.append({"shot_id": sid, "number": num, "start": start_of(s), "op": "changed", "what": what, "what_source": src, "facts": facts})

    for sid, b_shot in b_shots.items():
        if sid not in a_shots:
            facts = DS.removed_facts(b_shot, bundle=bundle)
            what, src = DS.what_for(what_map.get(sid), facts)
            out.append({"shot_id": sid, "number": None, "start": start_of(b_shot), "op": "removed", "what": what, "what_source": src, "facts": facts})

    return out


def merge_storyboard(
    base: dict,
    result: dict,
    current: dict,
    *,
    scope_shot_ids: set[str] | None = None,
    timing: dict | None = None,
    overwrite: bool = False,
) -> MergeResult:
    """Perform three-way merge: base -> result vs current. With `overwrite` (the owner chose it after a conflict) a shot both
    sides changed takes the agent's version and a changed shot list is not a conflict; everything the owner changed elsewhere
    stays."""
    b_shots = shots_map(base)
    r_shots = shots_map(result)
    c_shots = shots_map(current)

    changed_ids = set()
    added_ids = set()
    removed_ids = set()

    for sid, r_shot in r_shots.items():
        if sid not in b_shots:
            added_ids.add(sid)
        elif canon(r_shot) != canon(b_shots[sid]):
            changed_ids.add(sid)

    for sid in b_shots:
        if sid not in r_shots:
            if scope_shot_ids is None or sid in scope_shot_ids:
                removed_ids.add(sid)

    touched_ids = changed_ids | added_ids | removed_ids

    # Fast check: If current equals base
    if canon(clean_shot(base)) == canon(clean_shot(current)) and canon(shots_of(base)) == canon(shots_of(current)):
        res_sb = copy.deepcopy(result)
        for s in res_sb.get("shots", []):
            if s.get("id") in touched_ids:
                s["source"] = "agent"
        return MergeResult(status="same", storyboard=res_sb, touched_ids=touched_ids)

    # Check for conflicts on touched shots
    conflicts: list[dict] = []
    for sid in touched_ids:
        b_s = b_shots.get(sid)
        c_s = c_shots.get(sid)
        r_s = r_shots.get(sid)

        current_changed = (canon(b_s) != canon(c_s))
        if current_changed and canon(r_s) != canon(c_s) and not overwrite:
            conflicts.append({"kind": "shot", "id": sid, "reason": "both sides modified shot"})

    # Check if shot list in scope changed in current
    if timing and not overwrite and (scope_shot_ids or touched_ids):
        target_ids = set(scope_shot_ids or touched_ids)
        tm = Timing({"duration": timing.get("duration", 0), "words": timing.get("words", [])})
        base_shots_list = shots_of(base)

        def start_of(sh):
            try:
                return tm.resolve(sh["start"]) if isinstance(sh.get("start"), dict) else None
            except Exception:       # noqa: BLE001
                return None

        base_starts = [start_of(sh) for sh in base_shots_list]
        t_starts, t_ends = [], []
        for i, sh in enumerate(base_shots_list):
            if sh.get("id") in target_ids and base_starts[i] is not None:
                t_starts.append(base_starts[i])
                t_ends.append(next((x for x in base_starts[i + 1:] if x is not None), float(timing.get("duration", 0) or 0)))
        if t_starts:
            # the scope's time range: from the first scope shot's start to the end of the last one. A shot the owner added or
            # removed elsewhere (before or after) is not a conflict.
            scope_t0, scope_t1 = min(t_starts), max(t_ends)

            def list_in_scope(sb):
                ids = []
                for sh in shots_of(sb):
                    st = start_of(sh)
                    if st is not None and scope_t0 - 0.05 <= st < scope_t1 - 0.05:
                        ids.append(sh.get("id"))
                return ids
            b_list = [sid for sid in list_in_scope(base) if sid not in target_ids]
            c_list = [sid for sid in list_in_scope(current) if sid not in target_ids]
            if b_list != c_list:
                conflicts.append({"kind": "list", "reason": "shot structure changed in current within scope range"})

    if conflicts:
        return MergeResult(status="needs_choice", storyboard=None, conflicts=conflicts, touched_ids=touched_ids)

    # Clean three-way merge
    merged_shots: list[dict] = []
    r_order = [s.get("id") for s in shots_of(result)]

    for s in shots_of(current):
        sid = s.get("id")
        if sid in removed_ids:
            continue
        if sid in changed_ids:
            new_s = copy.deepcopy(r_shots[sid])
            new_s["source"] = "agent"
            merged_shots.append(new_s)
        else:
            merged_shots.append(copy.deepcopy(s))

    # Add shots added by result
    for sid in added_ids:
        new_s = copy.deepcopy(r_shots[sid])
        new_s["source"] = "agent"
        pred_id = None
        if sid in r_order:
            idx = r_order.index(sid)
            for prev_idx in range(idx - 1, -1, -1):
                cand = r_order[prev_idx]
                if any(ms.get("id") == cand for ms in merged_shots):
                    pred_id = cand
                    break
        if pred_id:
            insert_at = next(i + 1 for i, ms in enumerate(merged_shots) if ms.get("id") == pred_id)
            merged_shots.insert(insert_at, new_s)
        else:
            merged_shots.append(new_s)

    merged_doc = copy.deepcopy(current)
    merged_doc["shots"] = merged_shots

    # Assets & regions merge
    if "assets" in result and isinstance(result["assets"], dict):
        merged_assets = copy.deepcopy(merged_doc.get("assets") or {})
        for akey, a in result["assets"].items():
            if akey not in merged_assets:
                merged_assets[akey] = copy.deepcopy(a)
            elif isinstance(a, dict) and isinstance(a.get("regions"), dict):
                cur_regions = merged_assets[akey].setdefault("regions", {})
                for rname, rbox in a["regions"].items():
                    if rname not in cur_regions:
                        cur_regions[rname] = copy.deepcopy(rbox)
        merged_doc["assets"] = merged_assets

    return MergeResult(status="merged", storyboard=merged_doc, touched_ids=touched_ids)


def undo_turn(
    current: dict,
    before: dict,
    after: dict,
    touched_ids: set[str],
    *,
    force: bool = False,
) -> tuple[dict | None, list[str]]:
    """Undo an edit turn."""
    c_shots = shots_map(current)
    b_shots = shots_map(before)
    a_shots = shots_map(after)

    conflicts: list[str] = []
    for sid in touched_ids:
        c_s = c_shots.get(sid)
        a_s = a_shots.get(sid)
        if canon(c_s) != canon(a_s):
            conflicts.append(sid)

    if conflicts and not force:
        return None, conflicts

    restored_shots = []
    b_order = [s.get("id") for s in shots_of(before)]

    for s in shots_of(current):
        sid = s.get("id")
        if sid in touched_ids:
            if sid not in b_shots:
                continue
            restored_shots.append(copy.deepcopy(b_shots[sid]))
        else:
            restored_shots.append(copy.deepcopy(s))

    for sid in touched_ids:
        if sid in b_shots and not any(rs.get("id") == sid for rs in restored_shots):
            pred_id = None
            if sid in b_order:
                idx = b_order.index(sid)
                for prev_idx in range(idx - 1, -1, -1):
                    cand = b_order[prev_idx]
                    if any(rs.get("id") == cand for rs in restored_shots):
                        pred_id = cand
                        break
            if pred_id:
                pos = next(i + 1 for i, rs in enumerate(restored_shots) if rs.get("id") == pred_id)
                restored_shots.insert(pos, copy.deepcopy(b_shots[sid]))
            else:
                restored_shots.append(copy.deepcopy(b_shots[sid]))

    res_doc = copy.deepcopy(current)
    res_doc["shots"] = restored_shots
    return res_doc, []


def locked_update(project_dir: Any, make) -> tuple[str | None, Any, dict | None]:
    """Read the saved storyboard, let `make(current) -> (new_doc | None, payload)` decide, and save `new_doc` the way a storyboard
    save does (validation, `history/` copy, atomic write), all under the project's storyboard lock, the one every editor save
    holds. Approvals stay as they are. Returns `(revision, payload)`; the revision is the one the editor reads
    (`bti.editor.common.compute_rev`), None when nothing was written. The third value is the document that was written (read
    under the lock, never re-read later), None when nothing was written."""
    from pathlib import Path
    from bti.editor.common import compute_rev, save_lock, strip_derived
    from bti.engine import storyboard as SB
    from bti.engine.api import open_project
    project_dir = Path(project_dir)
    with save_lock(project_dir):
        if not (project_dir / "storyboard.json").is_file():
            raise FileNotFoundError(f"storyboard.json not found in {project_dir}")
        proj = open_project(project_dir)
        current = proj.storyboard()
        new_doc, payload = make(current)
        if new_doc is None:
            return None, payload, None
        new_doc = strip_derived(new_doc)
        new_doc["approvals"] = copy.deepcopy(current.get("approvals")) if current.get("approvals") is not None else {"storyboard": None}
        SB.save(project_dir, new_doc, proj.validate(new_doc))
        return compute_rev(new_doc), payload, new_doc


def apply_direct_edit(
    project_dir: Any,
    turn_id: str,
    base_sb: dict,
    result_sb: dict,
    *,
    model_changes: list[dict] | None = None,
    timing: dict | None = None,
    scope_shot_ids: set[str] | None = None,
) -> dict:
    """Apply compiled edit result directly with three-way merge (contract A3). Returns
    `{status: applied|no_change|needs_choice, after_rev, changes, conflicts, storyboard}`."""
    from pathlib import Path
    project_dir = Path(project_dir)
    from bti.draft.thread import save_turn_storyboards

    def make(current_sb):
        res = merge_storyboard(base_sb, result_sb, current_sb, scope_shot_ids=scope_shot_ids, timing=timing)
        if res.status == "needs_choice":
            return None, res
        return (res.storyboard or copy.deepcopy(result_sb)), res

    # The merge and the write happen under one lock: a save of the editor cannot slip in between.
    after_rev, res, written = locked_update(project_dir, make)

    if res.status == "needs_choice":
        save_turn_storyboards(project_dir, turn_id, base_sb, result_sb)
        changes = compute_changes(base_sb, result_sb, model_changes=model_changes, timing=timing)
        return {"status": "needs_choice", "storyboard": None, "conflicts": res.conflicts, "changes": changes, "after_rev": None}

    # The turn owns only what the agent's result changed against its base (`touched_ids`). A shot the owner changed, added or
    # removed meanwhile is in the written document too, but it is not the turn's change and undo must not touch it.
    changes = turn_changes(base_sb, written, res.touched_ids, model_changes=model_changes, timing=timing)
    save_turn_storyboards(project_dir, turn_id, base_sb, written)
    status = "no_change" if not changes else "applied"
    return {"status": status, "no_change": (status == "no_change"), "storyboard": written, "after_rev": after_rev,
            "changes": changes, "conflicts": [], "touched_ids": sorted(res.touched_ids)}


def turn_changes(base_sb: dict, final_sb: dict, touched_ids: set[str], *, model_changes: list[dict] | None = None,
                 timing: dict | None = None) -> list[dict]:
    """`compute_changes(base, final)` restricted to the shots the agent's result touched."""
    return [c for c in compute_changes(base_sb, final_sb, model_changes=model_changes, timing=timing) if c.get("shot_id") in touched_ids]


def resolve_overwrite(project_dir: Any, turn_id: str, *, timing: dict | None = None, model_changes: list[dict] | None = None,
                      scope_shot_ids: set[str] | None = None) -> dict:
    """The owner chose to overwrite after a conflict: apply the turn's stored result (its `after.json`) onto the storyboard as it
    is now; a shot both sides changed takes the agent's version, every other change of the owner stays. The turn's stored
    `after.json` becomes what was written, so that undo compares against it. Returns like `apply_direct_edit`."""
    from pathlib import Path
    from bti.draft.thread import get_turn_storyboard, save_turn_storyboards
    project_dir = Path(project_dir)
    base_sb = get_turn_storyboard(project_dir, turn_id, "before")
    result_sb = get_turn_storyboard(project_dir, turn_id, "after")
    if not base_sb or not result_sb:
        raise LookupError("turn storyboard data lost")

    def make(current_sb):
        res = merge_storyboard(base_sb, result_sb, current_sb, scope_shot_ids=scope_shot_ids, timing=timing, overwrite=True)
        return res.storyboard, res

    after_rev, res, written = locked_update(project_dir, make)
    changes = turn_changes(base_sb, written, res.touched_ids, model_changes=model_changes, timing=timing)
    save_turn_storyboards(project_dir, turn_id, base_sb, written)
    return {"status": "applied" if changes else "no_change", "after_rev": after_rev, "changes": changes, "conflicts": [],
            "touched_ids": sorted(res.touched_ids)}


class UndoConflict(Exception):
    def __init__(self, conflicts: list[str]):
        super().__init__("shots changed since the turn: " + ", ".join(conflicts))
        self.conflicts = conflicts


def undo_apply(project_dir: Any, turn_id: str, touched_ids: set[str] | None = None, *, force: bool = False) -> str:
    """Put the shots a turn touched back as they were before it (one more revision), under the storyboard lock. Raises
    UndoConflict (nothing written) when some of them changed since and `force` is not set, LookupError when the stored
    storyboards are gone. Returns the new revision."""
    from pathlib import Path
    from bti.draft.thread import get_turn_storyboard
    project_dir = Path(project_dir)
    before_sb = get_turn_storyboard(project_dir, turn_id, "before")
    after_sb = get_turn_storyboard(project_dir, turn_id, "after")
    if not before_sb or not after_sb:
        raise LookupError("undo data lost")
    ids = set(touched_ids or ())
    if not ids:
        b_s, a_s = shots_map(before_sb), shots_map(after_sb)
        ids = {sid for sid in (set(b_s) | set(a_s)) if canon(b_s.get(sid)) != canon(a_s.get(sid))}

    def make(current_sb):
        restored, conflicts = undo_turn(current_sb, before_sb, after_sb, ids, force=force)
        if conflicts and not force:
            raise UndoConflict(sorted(conflicts))
        return restored, None

    rev, _, _ = locked_update(project_dir, make)
    return rev
