"""What the two prompt boxes' routes share (worker c2box): the turns of the thread that edited a document through typed operations.

The turns of step 5 live behind `bti/editor/draft_api.py` (`/api/projects/{pid}/draft/...`), the turns of step 4 behind `picks_api.py`
(`/api/projects/{pid}/picks/edit/...`); both are in one thread file (`bti/draft/thread.py`, a turn has `doc`). A turn that was applied has
the id of its batch; its undo is the undo of that batch through the change log (`bti/ops/undo.py`), never a second mechanism. Turns made
before the typed operations (no batch) keep the older undo of `draft_api.py`.
"""
from __future__ import annotations

from pathlib import Path

from bti.draft import boxops
from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.draft.thread import update_turn
from bti.ops.errors import OpError
from bti.ops.log import ChangeLog

from .common import ApiError


def turns_of(d: Path, turns: list[dict], doc: str) -> list[dict]:
    """The turns that belong to one box (`storyboard` or `picks`)."""
    return [t for t in turns if (t.get("doc") or "storyboard") == doc]


def enrich(d: Path, turns: list[dict]) -> list[dict]:
    """A turn with a batch is judged by the change log: its undo works while the batch still has its copies and nothing undid it; a batch
    undone from the list of changes makes the turn `undone`. (A conflict is only known when the undo is tried: the route says why.)"""
    if not any(t.get("batch") for t in turns):
        return turns
    recs = {r["batch"]: r for r in ChangeLog(d).list(None, 200)}
    out = []
    for t in turns:
        if t.get("batch"):
            t = dict(t)
            r = recs.get(t["batch"])
            if r is None or not r.get("copies"):
                t["has_undo"] = False
            elif r.get("undone_by"):
                t["has_undo"] = False
                if t.get("status") == "applied":
                    t["status"] = "undone"
            else:
                t["has_undo"] = t.get("status") == "applied"
        out.append(t)
    return out


def to_api(e: OpError) -> ApiError:
    from .ops_api import to_api as ops_to_api
    return ops_to_api(e)


def undo_batch_turn(d: Path, turn: dict) -> dict:
    """The card's "Hoàn tác" for a turn that wrote a batch: undo that batch (actor `human`), then mark the turn. `undo_conflict` and
    `undo_unavailable` reach the page as the operations' own typed errors."""
    if turn.get("status") == "undone":
        raise ApiError(409, "turn already undone", code="already_undone")
    if turn.get("status") != "applied":
        raise ApiError(409, "turn was not applied", code="turn_not_applied")
    kind = turn.get("doc") or "storyboard"
    backend = boxops.Backend(d)
    recs = {r["batch"]: r for r in backend.log.list(kind, 200)}
    if (recs.get(turn["batch"]) or {}).get("undone_by"):
        update_turn(d, turn["id"], status="undone")
        raise ApiError(409, "turn already undone", code="already_undone")
    try:
        _doc, rev = backend.read(kind)
        ans = backend.undo(kind, turn["batch"], {"base_rev": rev, "actor": "human", "note": ""})
    except OpError as e:
        raise to_api(e)
    update_turn(d, turn["id"], status="undone")
    return {"ok": True, "status": "undone", "rev": ans["rev"], "after_rev": ans["rev"], "batch": ans.get("batch")}


def frame_source(d: Path, turn: dict, shot_id: str, when: str) -> tuple[dict | None, str]:
    """The storyboard to draw a frame of a batch turn from (the change log's copy before or after) and the id of the shot in that copy."""
    both = ChangeLog(d).copies(turn["batch"])
    if both is None:
        return None, shot_id
    row = next((c for c in turn.get("changes") or [] if c.get("shot_id") == shot_id), None) or {}
    sid = (row.get("before_id") if when == "before" else row.get("after_id")) or shot_id
    return both[0 if when == "before" else 1], sid


# ------------------------------------------------------------------------------------------------------------ step 4
def start_picks_edit(d: Path, pid: str, body: dict) -> dict:
    """`POST /api/projects/{pid}/picks/edit`: {instruction, scope: {beats | chapter | all}, base_rev?, model?}."""
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object", code="invalid_request")
    instruction = body.get("instruction")
    if not isinstance(instruction, str) or not instruction.strip():
        raise ApiError(422, "instruction cannot be empty", code="edit_empty_instruction")
    if len(instruction) > 2000:
        raise ApiError(422, "instruction must be 1 to 2000 characters", code="edit_bad_scope")
    scope = body.get("scope")
    if not isinstance(scope, dict):
        raise ApiError(422, "scope must be an object", code="edit_bad_scope")
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise ApiError(422, "model must be text", code="bad_model")
    base_rev = body.get("base_rev")
    if base_rev is not None and not isinstance(base_rev, str):
        raise ApiError(422, "base_rev must be text", code="invalid_field", field="base_rev")
    try:
        res = draft_run.start_picks(pid, d, instruction=instruction, edit_scope=scope, model=model or None, base_rev=base_rev)
    except DraftError as e:
        status = 409 if e.code in ("stale_revision", "agy_missing", "claude_missing", "claude_auth") else 422
        extra = {}
        if e.code == "stale_revision":
            try:
                extra = {"current_rev": boxops.Backend(d).read("picks")[1]}
            except Exception:       # noqa: BLE001
                extra = {}
        raise ApiError(status, e.message, code=e.code, **extra)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ApiError(409, "an edit is already running for this project", code="busy", job_id=getattr(e, "job_id", None))
        raise
    meta = res.get("meta") if isinstance(res.get("meta"), dict) else {}
    return {"job_id": res["id"], "turn_id": res["turn_id"], "model": meta.get("model"), "agent": meta.get("agent")}


def picks_thread(d: Path, request_app) -> dict:
    from bti.draft.thread import reconcile_thread
    from bti.longjob import manager as global_mgr
    mgr = getattr(request_app.state, "longjob_manager", None) or global_mgr
    turns = turns_of(d, reconcile_thread(d, manager=mgr), "picks")
    active = None
    try:
        act = mgr.active(d.name, "draft") if mgr else None
        if act and (act.get("meta") or {}).get("mode") == "edit" and (act.get("meta") or {}).get("doc") == "picks":
            active = act.get("id")
    except Exception:       # noqa: BLE001
        active = None
    return {"turns": enrich(d, turns), "active_job_id": active}
