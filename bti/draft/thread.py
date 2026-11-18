"""Persistent conversation thread store for prompt-based storyboard editing (design section 7.4).

Each project has at most one thread stored at `<project_dir>/cache/draft/thread.json`.
Thread turns record:
- id: unique turn id (t_YYYYMMDD_HHMMSS_xxx)
- at: ISO timestamp
- instruction: user instruction verbatim
- scope: {kind: "shots"|"chapter"|"all", shots: list[str]|None, chapter: str|None}
- scope_words: Vietnamese scope description (e.g., "1 shot đang chọn", "chương c01", "cả video")
- model: model slug used
- base_rev: storyboard revision at the start of the edit
- status: "running" | "done" | "no_change" | "refused" | "error"
- job_id: longjob id
- proposal_id: proposal id if created
- conversation_id: provider conversation id if available
- notes: agent notes / summary
- error: error code if failed/refused
- accepted: None | "applied" | "partially_applied" | "none"
- accepted_at: ISO timestamp when proposal was applied
- accepted_shots: list of shot ids applied
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from bti.engine.storyboard import write_atomic

MAX_TURNS = 50

_THREAD_GUARD = threading.Lock()
_THREAD_LOCKS: dict[str, threading.RLock] = {}


def thread_path(project_dir: Path) -> Path:
    return Path(project_dir) / "cache" / "draft" / "thread.json"


def thread_lock(project_dir: Path) -> threading.RLock:
    """Per-project re-entrant lock for thread read-modify-write safety."""
    key = str(Path(project_dir).resolve())
    with _THREAD_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


def forget_thread_lock(project_dir: Path) -> None:
    with _THREAD_GUARD:
        _THREAD_LOCKS.pop(str(Path(project_dir).resolve()), None)


def _normalize_turn(raw: dict) -> dict:
    scope = raw.get("scope") or {}
    kind = scope.get("kind") if isinstance(scope, dict) else "all"
    return {
        "id": str(raw.get("id") or ""),
        "at": str(raw.get("at") or ""),
        "instruction": str(raw.get("instruction") or ""),
        "scope": {
            "kind": kind,
            "shots": list(scope.get("shots")) if isinstance(scope.get("shots"), list) else None,
            "chapter": str(scope.get("chapter")) if scope.get("chapter") is not None else None,
        },
        "scope_words": str(raw.get("scope_words") or ""),
        "model": str(raw.get("model") or ""),
        "base_rev": raw.get("base_rev"),
        "status": str(raw.get("status") or "running"),
        "job_id": raw.get("job_id"),
        "proposal_id": raw.get("proposal_id"),
        "conversation_id": raw.get("conversation_id"),
        "notes": str(raw.get("notes") or ""),
        "error": raw.get("error"),
        "accepted": raw.get("accepted"),
        "accepted_at": raw.get("accepted_at"),
        "accepted_shots": list(raw.get("accepted_shots")) if isinstance(raw.get("accepted_shots"), list) else None,
    }


def load_thread(project_dir: Path) -> list[dict]:
    """Read thread turns for project. Tolerates legacy entries/turns formats."""
    f = thread_path(project_dir)
    with thread_lock(project_dir):
        if not f.is_file():
            return []
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        raw_list = []
        if isinstance(data, dict):
            if isinstance(data.get("turns"), list):
                raw_list = data["turns"]
            elif isinstance(data.get("entries"), list):
                raw_list = data["entries"]
        elif isinstance(data, list):
            raw_list = data
        return [_normalize_turn(t) for t in raw_list if isinstance(t, dict)]


def save_thread(project_dir: Path, turns: list[dict]) -> None:
    """Atomically write capped thread turns under lock."""
    f = thread_path(project_dir)
    with thread_lock(project_dir):
        f.parent.mkdir(parents=True, exist_ok=True)
        capped = turns[-MAX_TURNS:]
        normalized = [_normalize_turn(t) for t in capped]
        write_atomic(f, json.dumps({"turns": normalized}, ensure_ascii=False, indent=1))


def append_turn(project_dir: Path, turn: dict) -> None:
    """Append a turn atomically under lock."""
    with thread_lock(project_dir):
        turns = load_thread(project_dir)
        turns.append(turn)
        save_thread(project_dir, turns)


def update_turn(project_dir: Path, turn_id: str, **updates) -> dict | None:
    """Update fields of an existing turn by id under lock."""
    with thread_lock(project_dir):
        turns = load_thread(project_dir)
        target = None
        for t in turns:
            if t.get("id") == turn_id:
                t.update(updates)
                target = t
                break
        if target is not None:
            save_thread(project_dir, turns)
        return target


def clear_thread(project_dir: Path) -> None:
    """Clear all turns under lock."""
    f = thread_path(project_dir)
    with thread_lock(project_dir):
        if f.is_file():
            try:
                write_atomic(f, json.dumps({"turns": []}, ensure_ascii=False, indent=1))
            except OSError:
                pass


def reconcile_thread(project_dir: Path, manager=None) -> list[dict]:
    """Reconcile running turns whose longjob has finished, cancelled, or vanished."""
    with thread_lock(project_dir):
        turns = load_thread(project_dir)
        changed = False
        running_turns = [t for t in turns if t.get("status") == "running"]
        if running_turns:
            if manager is None:
                try:
                    from bti.longjob import manager as global_mgr
                    manager = global_mgr
                except Exception:
                    manager = None
            for t in running_turns:
                jid = t.get("job_id")
                if not jid:
                    t["status"] = "error"
                    t["error"] = "interrupted"
                    changed = True
                    continue
                j = manager.get(jid) if manager else None
                if j is None:
                    t["status"] = "error"
                    t["error"] = "interrupted"
                    changed = True
                elif j.get("state") == "done":
                    res = j.get("result") or {}
                    if res.get("proposal_id"):
                        t["status"] = "done"
                        t["proposal_id"] = res["proposal_id"]
                    elif res.get("no_change"):
                        t["status"] = "no_change"
                    else:
                        t["status"] = "done"
                    if res.get("notes") and not t.get("notes"):
                        t["notes"] = res["notes"]
                    changed = True
                elif j.get("state") == "error":
                    t["status"] = "refused" if j.get("error_code") == "edit_outside_scope" else "error"
                    t["error"] = j.get("error_code") or "error"
                    changed = True
                elif j.get("state") == "cancelled":
                    t["status"] = "error"
                    t["error"] = "cancelled"
                    changed = True
                elif j.get("state") == "interrupted":
                    t["status"] = "error"
                    t["error"] = "interrupted"
                    changed = True
                elif j.get("state") not in ("queued", "waiting", "running"):
                    t["status"] = "error"
                    t["error"] = j.get("error_code") or "interrupted"
                    changed = True
        if changed:
            save_thread(project_dir, turns)
        return turns


def record_acceptance(project_dir: Path, proposal_id: str, status: str,
                      accepted_shots: list[str] | None = None) -> bool:
    """Record proposal acceptance on matching turn under lock."""
    with thread_lock(project_dir):
        turns = load_thread(project_dir)
        updated = False
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        for t in turns:
            if t.get("proposal_id") == proposal_id:
                t["accepted"] = status
                t["accepted_at"] = now
                if accepted_shots is not None:
                    t["accepted_shots"] = list(accepted_shots)
                updated = True
        if updated:
            save_thread(project_dir, turns)
        return updated


def format_previous_exchanges(turns: list[dict], limit: int = 3) -> str:
    """Include recent completed exchanges in INSTRUCTION.md with clear prior outcomes."""
    valid = [t for t in turns if t.get("instruction") and (t.get("notes") or t.get("status") in ("done", "no_change", "refused"))]
    recent = valid[-limit:]
    if not recent:
        return ""
    lines = ["# Previous exchanges in this editing thread:\n"]
    for i, t in enumerate(recent, 1):
        instr = t.get("instruction", "").strip()
        scope = t.get("scope_words") or (t.get("scope") or {}).get("kind") or "video"
        notes = (t.get("notes") or "").strip() or "(no notes)"
        status = t.get("status")
        prop_id = t.get("proposal_id")
        acc = t.get("accepted")

        outcome_parts = []
        if status == "done" and prop_id:
            if acc == "applied":
                outcome_parts.append(f"Proposal {prop_id} was APPLIED by the user.")
            elif acc == "partially_applied":
                shots = t.get("accepted_shots") or []
                outcome_parts.append(f"Proposal {prop_id} was PARTIALLY applied by the user on shots: {', '.join(shots)}.")
            else:
                outcome_parts.append(f"Proposal {prop_id} is PENDING (user has not accepted it yet).")
        elif status == "no_change":
            outcome_parts.append("No changes were made to the storyboard in this turn.")
        elif status == "refused":
            outcome_parts.append(f"Turn was refused due to scope violation ({t.get('error')}).")

        outcome_str = (" " + " ".join(outcome_parts)) if outcome_parts else ""
        lines.append(f"## Turn {i} ({scope}){outcome_str}\n- User: {instr}\n- Agent: {notes}\n")
    return "\n".join(lines).strip()
