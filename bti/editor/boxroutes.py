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
        status = 409 if e.code in ("stale_revision", "agy_missing", "claude_missing", "claude_auth", "agent_job_running") else 422
        extra = dict(e.extra) if e.code == "agent_job_running" else {}
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
    turns = finish_agent_turns(d, turns_of(d, reconcile_thread(d, manager=mgr), "picks"), mgr)
    active = None
    try:
        act = mgr.active(d.name, "draft") if mgr else None
        if act and (act.get("meta") or {}).get("mode") == "edit" and (act.get("meta") or {}).get("doc") == "picks":
            active = act.get("id")
    except Exception:       # noqa: BLE001
        active = None
    if active is None:                                      # join2: a turn handed to the pictures agent runs in a job of kind `picks`
        run = next((t for t in turns if t.get("status") == "running" and t.get("path") == AGENT_PATH and t.get("job_id")), None)
        active = run["job_id"] if run else None
    return {"turns": enrich(d, turns), "active_job_id": active}


# ------------------------------------------------------------------------------------------------ step 4: a turn handed to the pictures agent (join2)
AGENT_PATH = "agent"           # `path` of a turn that the owner handed to the pictures agent ("Để agent chọn hình") after the box answered `escalate`


def _scope_payload(turn: dict) -> dict:
    """The scope the owner chose for a turn, in the form the box's route takes it."""
    sc = turn.get("scope") or {}
    if sc.get("kind") == "all":
        return {"all": True}
    if sc.get("kind") == "chapter" and sc.get("chapter"):
        return {"chapter": sc["chapter"]}
    return {"beats": list(sc.get("beats") or [])}


def escalate_picks_turn(d: Path, pid: str, turn_id: str, body: dict | None = None) -> dict:
    """`POST /api/projects/{pid}/picks/edit/{turn_id}/escalate`: the box answered `escalate` (the request needs a picture the project does not have);
    the owner now hands the same lines to the pictures agent. The agent works on exactly the lines of the turn's scope, choosing them again, with the
    owner's request in front of it (`bti.picks.auto.escalate`); the turn becomes `running` on that job (path `agent`) and the thread follows it to its
    result. A turn whose agent run failed or was stopped can be handed over again. Body (optional): {model}."""
    from bti.draft import picksedit
    from bti.draft.thread import load_thread, update_turn
    from bti.picks import auto, context
    body = {} if body is None else body
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object", code="invalid_request")
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise ApiError(422, "model must be text", code="bad_model")
    turn = next((t for t in turns_of(d, load_thread(d), "picks") if t.get("id") == turn_id), None)
    if turn is None:
        raise ApiError(404, "turn not found", code="turn_not_found")
    again = turn.get("path") == AGENT_PATH and turn.get("status") in ("failed", "cancelled")
    if turn.get("status") != "escalate" and not again:
        raise ApiError(409, "the turn did not end as escalate", code="turn_not_escalated")
    backend = boxops.Backend(d)
    doc, _rev = backend.read("picks")
    try:
        sc = picksedit.picks_scope(backend.adapter("picks").facts(doc), doc, _scope_payload(turn), context.narration_view(d))
    except DraftError as e:
        raise ApiError(422, e.message, code=e.code)
    try:
        rec = auto.escalate(pid, d, list(sc.ids), note=turn.get("instruction") or "", model=model or None)
    except auto.AutoError as e:
        raise ApiError(e.status, e.message, code=e.code, **e.extra)
    meta = rec.get("meta") or {}
    update_turn(d, turn_id, status="running", path=AGENT_PATH, escalated=True, job_id=rec["id"], error=None, retry_at=None, retry_after_seconds=None,
                agent=meta.get("agent") or turn.get("agent"), model=meta.get("model") or turn.get("model"), summary="", summary_source=None,
                batch=None, batch_changes=[], result=None, seconds=0.0)
    return {"job_id": rec["id"], "turn_id": turn_id, "model": meta.get("model"), "agent": meta.get("agent"), "lines": len(meta.get("beats") or [])}


def _batch_sentences(d: Path, batches: list) -> list[dict]:
    """The sentences (`target`, `time`, `what`) the change log holds for these batches, in order."""
    log = ChangeLog(d)
    out: list[dict] = []
    for b in batches or []:
        rec = log.get(b) if isinstance(b, str) else None
        out += [c for c in (rec or {}).get("changes") or [] if isinstance(c, dict)]
    return out


def finish_agent_turns(d: Path, turns: list[dict], mgr) -> list[dict]:
    """The turns handed to the pictures agent end with the job's result: the sentence of the result, the sentences of the batches it wrote, the lines it
    could not fill (`result`); a failed turn keeps when its quota opens again. The thread reconcile has already given the status; this adds the words,
    once (a turn with a summary is done)."""
    from bti.draft.thread import update_turn
    out = []
    for t in turns:
        if t.get("path") == AGENT_PATH and t.get("job_id") and mgr is not None:
            rec = None
            try:
                rec = mgr.get(t["job_id"])
            except Exception:       # noqa: BLE001
                rec = None
            if rec is not None and t.get("status") == "applied" and not t.get("summary") and rec.get("state") == "done":
                res = rec.get("result") or {}
                fields = {"summary": str(res.get("sentence") or ""), "summary_source": "code",
                          "batch_changes": _batch_sentences(d, res.get("batches")), "doc": "picks",
                          "seconds": round(max(0.0, float(rec.get("finished") or 0) - float(rec.get("created") or 0)), 1),
                          "result": {k: res.get(k) for k in ("lines_total", "lines_done", "lines_without", "stopped") if k in res}}
                t = update_turn(d, t["id"], **fields) or t
            elif rec is not None and t.get("status") == "failed" and t.get("retry_at") in (None, "") and t.get("retry_after_seconds") in (None, ""):
                m = rec.get("meta") or {}
                if m.get("retry_at") or m.get("retry_after_seconds"):
                    t = update_turn(d, t["id"], retry_at=m.get("retry_at"), retry_after_seconds=m.get("retry_after_seconds")) or t
        out.append(t)
    return out
