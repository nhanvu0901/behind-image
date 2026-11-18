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
    """Compute changes list with [{shot_id, number, start, op: 'changed'|'added'|'removed', what}]."""
    b_shots = shots_map(before_sb)
    a_shots_list = shots_of(after_sb)
    a_shots = shots_map(after_sb)

    tm = Timing({"duration": timing.get("duration", 0), "words": timing.get("words", [])}) if timing else None

    # Map model change explanations by shot id if provided
    what_map: dict[str, str] = {}
    if model_changes:
        for idx, ch in enumerate(model_changes):
            if isinstance(ch, dict):
                target = str(ch.get("shot", ""))
                what = str(ch.get("what", ""))
                what_map[target] = what
                what_map[str(idx)] = what

    out: list[dict] = []
    for num, s in enumerate(a_shots_list, 1):
        sid = s.get("id")
        if not sid:
            continue
        st = s.get("start")
        start_val = st
        if tm and isinstance(st, dict):
            try:
                start_val = tm.resolve(st)
            except Exception:
                pass

        if sid not in b_shots:
            what = what_map.get(sid) or what_map.get(str(num - 1)) or "Thêm cảnh mới"
            out.append({"shot_id": sid, "number": num, "start": start_val, "op": "added", "what": what})
        elif canon(a_shots[sid]) != canon(b_shots[sid]):
            what = what_map.get(sid) or what_map.get(str(num - 1)) or "Thay đổi cảnh"
            out.append({"shot_id": sid, "number": num, "start": start_val, "op": "changed", "what": what})

    # Removed shots
    for sid, b_shot in b_shots.items():
        if sid not in a_shots:
            st = b_shot.get("start")
            start_val = st
            if tm and isinstance(st, dict):
                try:
                    start_val = tm.resolve(st)
                except Exception:
                    pass
            what = what_map.get(sid) or "Xóa cảnh"
            out.append({"shot_id": sid, "number": None, "start": start_val, "op": "removed", "what": what})

    return out


def merge_storyboard(
    base: dict,
    result: dict,
    current: dict,
    *,
    scope_shot_ids: set[str] | None = None,
    timing: dict | None = None,
) -> MergeResult:
    """Perform three-way merge: base -> result vs current."""
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
        if current_changed and canon(r_s) != canon(c_s):
            conflicts.append({"kind": "shot", "id": sid, "reason": "both sides modified shot"})

    # Check if shot list in scope changed in current
    if timing and (scope_shot_ids or touched_ids):
        target_ids = set(scope_shot_ids or touched_ids)
        tm = Timing({"duration": timing.get("duration", 0), "words": timing.get("words", [])})
        base_shots_list = shots_of(base)
        t_ranges = []
        for s in base_shots_list:
            if s.get("id") in target_ids:
                try:
                    t0 = tm.resolve(s["start"]) if isinstance(s.get("start"), dict) else None
                    if t0 is not None:
                        t_ranges.append(t0)
                except Exception:
                    pass
        if t_ranges:
            scope_t0 = min(t_ranges)
            def list_in_scope(sb):
                ids = []
                for s in shots_of(sb):
                    try:
                        st = tm.resolve(s["start"]) if isinstance(s.get("start"), dict) else None
                        if st is not None and st >= scope_t0 - 0.05:
                            ids.append(s.get("id"))
                    except Exception:
                        pass
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


def apply_direct_edit(
    project_dir: Any,
    turn_id: str,
    base_sb: dict,
    result_sb: dict,
    *,
    model_changes: list[dict] | None = None,
    timing: dict | None = None,
    scope_shot_ids: set[str] | None = None,
    engine: Any = None,
    pid: str | None = None,
) -> dict:
    """Apply compiled edit result directly with three-way merge (contract A3)."""
    from pathlib import Path
    project_dir = Path(project_dir)
    from bti.draft.thread import save_turn_storyboards

    # 1. Read current storyboard
    current_sb = None
    if engine and pid:
        try:
            p = engine.project(pid)
            from bti.editor.engine_adapter import ENGINE_LOCK
            with ENGINE_LOCK:
                current_sb = p.storyboard()
        except Exception:
            current_sb = None
    if current_sb is None:
        sb_file = project_dir / "storyboard.json"
        if not sb_file.is_file():
            raise FileNotFoundError(f"storyboard.json not found in {project_dir}")
        current_sb = json.loads(sb_file.read_text(encoding="utf-8"))

    # 2. Perform three-way merge
    res = merge_storyboard(base_sb, result_sb, current_sb, scope_shot_ids=scope_shot_ids, timing=timing)

    # 3. Handle conflict
    if res.status == "needs_choice":
        save_turn_storyboards(project_dir, turn_id, base_sb, result_sb)
        changes = compute_changes(base_sb, result_sb, model_changes=model_changes, timing=timing)
        return {
            "status": "needs_choice",
            "storyboard": None,
            "conflicts": res.conflicts,
            "changes": changes,
            "after_rev": None,
        }

    # 4. Handle clean merge (same or merged)
    final_sb = res.storyboard or copy.deepcopy(result_sb)
    # Approvals remain as in current
    if "approvals" in current_sb:
        final_sb["approvals"] = copy.deepcopy(current_sb["approvals"])
    else:
        final_sb["approvals"] = {"storyboard": None}

    # Commit storyboard
    after_rev = None
    if engine and pid:
        p = engine.project(pid)
        from bti.editor.engine_adapter import ENGINE_LOCK
        with ENGINE_LOCK:
            after_rev = p.save(final_sb)
    else:
        from bti.engine import storyboard as SB
        from bti.engine.api import open_project
        try:
            p_obj = open_project(project_dir)
            issues = p_obj.validate(final_sb)
        except Exception:
            issues = []
        after_rev = SB.save(project_dir, final_sb, issues)

    # Save turn before & after
    save_turn_storyboards(project_dir, turn_id, base_sb, final_sb)

    # Compute changes between base and final
    changes = compute_changes(base_sb, final_sb, model_changes=model_changes, timing=timing)
    status = "no_change" if not changes else "applied"

    return {
        "status": status,
        "storyboard": final_sb,
        "after_rev": after_rev,
        "changes": changes,
        "conflicts": [],
    }
