"""Routes of the storyboard draft (design section 7). Mounted by CORE: `app.include_router(draft_api.router)`.

    GET  /api/projects/{pid}/draft          readiness (voice, picks), state, last run, the model and the agent the next draft will use
    GET  /api/projects/{pid}/draft/models   the models `agy models` lists (cached ten minutes). The page no longer reads it: the agent
                                            select (GET /api/agents, agent_api.py) replaced the model list of the draft panel. It stays for
                                            tools that name a model themselves; `default` is the model the next draft of THIS project uses
                                            (its agent), and `agent` says whose it is.
    POST /api/projects/{pid}/draft/start    {provider: "agy" | "auto", model?, chapters?}  -> {job_id, model, agent}   (a long job: /api/longjobs/{id})
                                            Without `model` the project's agent is used (bti.agents.model_for_project); a request that names a
                                            model keeps it.

The proposal the job writes is read and applied through the existing proposal routes. The projects folder is read from
`app.state.projects_root`."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Request, Response

from bti import agents as agents_mod
from bti.draft import run as draft_run
from bti.draft.inputs import DraftError

from . import boxroutes
from .common import ApiError, valid_pid

router = APIRouter(prefix="/api/projects/{pid}/draft")


def _pdir(request: Request, pid: str) -> Path:
    if not valid_pid(pid):
        raise ApiError(404, "project not found", code="project_not_found")
    root = Path(getattr(request.app.state, "projects_root", None) or Path(__file__).resolve().parents[2] / "projects")
    d = root / pid
    if not d.is_dir() or d.is_symlink():
        raise ApiError(404, "project not found", code="project_not_found")
    return d


def _current_rev(d: Path) -> dict:
    """`{current_rev}` of the saved storyboard, for an edit whose base_rev is stale ({} when the file cannot be read)."""
    try:
        from .common import compute_rev, read_json
        return {"current_rev": compute_rev(read_json(d / "storyboard.json"))}
    except Exception:       # noqa: BLE001
        return {}


def _who(rec: dict) -> dict:
    """The model and the agent a start route answers with, next to the job: what the job itself recorded in its `meta`."""
    meta = rec.get("meta") if isinstance(rec, dict) and isinstance(rec.get("meta"), dict) else {}
    return {"model": meta.get("model"), "agent": meta.get("agent")}


def _storyboard_lock(request: Request, pid: str, d: Path):
    """The project's storyboard lock (re-entrant, the one every editor save holds)."""
    from .common import save_lock
    return save_lock(d)


@router.get("")
def get_draft(pid: str, request: Request):
    d = _pdir(request, pid)
    return draft_run.overview(pid, d)


@router.get("/models")
def get_models(pid: str, request: Request, refresh: int = 0):
    _pdir(request, pid)
    try:
        from bti.script import models as models_mod
        rows, err = models_mod.agy_models(refresh=bool(refresh))
    except Exception:       # noqa: BLE001 - the list can never break the page
        rows, err = None, "`agy models` không đọc được."
    res = agents_mod.model_for_project(_pdir(request, pid), "draft")
    return {"default": res.model, "agent": res.public(), "models": rows or [], "error": err}


@router.post("/start")
def post_start(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object", code="invalid_request")
    provider = body.get("provider", "agy")
    model = body.get("model")
    chapters = body.get("chapters")
    if provider not in ("agy", "auto"):
        raise ApiError(422, "provider must be agy or auto", code="bad_provider")
    if model is not None and not isinstance(model, str):
        raise ApiError(422, "model must be text", code="bad_model")
    if chapters is not None and not (isinstance(chapters, list) and all(isinstance(c, str) for c in chapters) and len(chapters) <= 100):
        raise ApiError(422, "chapters must be a list of chapter ids", code="bad_chapters")
    try:
        job = draft_run.start(pid, d, provider=provider, model=model or None, chapters=chapters or None)
    except DraftError as e:
        status = 409 if e.code in ("draft_not_ready", "agy_missing", "claude_missing", "claude_auth", "scope_needs_storyboard", "picks_missing", "timing_missing", "picks_no_main", "agent_job_running") else 422
        raise ApiError(status, e.message, code=e.code, **(e.extra if e.code == "agent_job_running" else {}))
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ApiError(409, "a draft is already running for this project", code="busy", job_id=getattr(e, "job_id", None))
        raise
    return {"job_id": job["id"], **_who(job)}


@router.post("/edit")
def post_edit(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
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
    has_shots = "shots" in scope
    has_chapter = "chapter" in scope
    has_all = bool(scope.get("all"))
    targets_set = sum([has_shots, has_chapter, has_all])
    if targets_set == 0:
        raise ApiError(422, "scope must specify shots, chapter, or all", code="edit_bad_scope")
    if targets_set > 1:
        raise ApiError(422, "scope must specify only one of shots, chapter, or all", code="edit_bad_scope")
    if has_shots:
        shots = scope.get("shots")
        if not isinstance(shots, list) or not all(isinstance(s, str) for s in shots) or not shots:
            raise ApiError(422, "shots must be a non-empty list of shot ids", code="edit_bad_scope")
    if has_chapter:
        chapter = scope.get("chapter")
        if not isinstance(chapter, str) or not chapter.strip():
            raise ApiError(422, "chapter must be a string", code="edit_bad_scope")
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise ApiError(422, "model must be text", code="bad_model")
    mode = body.get("mode", "auto")
    if mode not in ("auto", "fast", "deep"):
        raise ApiError(422, "mode must be auto, fast, or deep", code="edit_bad_scope")
    followup = bool(body.get("followup", False))
    base_rev = body.get("base_rev")

    try:
        res = draft_run.start(pid, d, instruction=instruction, edit_scope=scope, model=model or None,
                              followup=followup, base_rev=base_rev, mode=mode)
    except DraftError as e:
        status = 409 if e.code in ("draft_not_ready", "agy_missing", "claude_missing", "claude_auth", "scope_needs_storyboard", "edit_no_storyboard", "edit_needs_agy", "picks_missing", "timing_missing", "picks_no_main", "stale_revision", "agent_job_running") else 422
        raise ApiError(status, e.message, code=e.code, **(_current_rev(d) if e.code == "stale_revision" else e.extra if e.code == "agent_job_running" else {}))
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ApiError(409, "a draft is already running for this project", code="busy", job_id=getattr(e, "job_id", None))
        raise
    return {"job_id": res["id"], "turn_id": res["turn_id"], **_who(res)}


@router.post("/edit/{turn_id}/resolve")
def resolve_edit(pid: str, turn_id: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object", code="invalid_request")
    action = body.get("action")
    if action not in ("overwrite", "discard"):
        raise ApiError(422, "action must be 'overwrite' or 'discard'", code="bad_action")

    from bti.draft.thread import load_thread, update_turn
    turns = load_thread(d)
    turn = next((t for t in turns if t.get("id") == turn_id), None)
    if turn is None:
        raise ApiError(404, "turn not found", code="turn_not_found")
    if turn.get("status") != "needs_choice":
        raise ApiError(409, "turn does not need choice", code="not_needs_choice")

    if action == "discard":
        update_turn(d, turn_id, status="cancelled")
        return {"ok": True, "action": "discard", "status": "cancelled"}

    # action == "overwrite": the agent's result goes onto the storyboard as it is NOW (the owner's other changes stay), as ONE batch of operations
    from bti.draft import boxops
    from bti.draft.inputs import DraftError, load_inputs
    from bti.draft.thread import get_turn_storyboard
    from bti.ops.errors import OpError
    if not get_turn_storyboard(d, turn_id, "after") or not get_turn_storyboard(d, turn_id, "before"):
        raise ApiError(410, "turn storyboard data lost", code="turn_data_lost")
    try:
        timing = load_inputs(d, for_edit=True).timing
    except DraftError:
        raise ApiError(409, "the timing of the project cannot be read", code="timing_unusable")
    scope_ids = set((turn.get("scope") or {}).get("shots") or []) or None
    try:
        res = boxops.apply_deep(boxops.Backend(d), base_sb=get_turn_storyboard(d, turn_id, "before"), result_sb=get_turn_storyboard(d, turn_id, "after"),
                                scope_ids=scope_ids, timing=timing, instruction=turn.get("instruction") or "", actor="agent:" + (turn.get("model") or "agent"),
                                model_changes=[{"shot": c.get("shot_id"), "what": c.get("what")} for c in turn.get("changes") or [] if c.get("what_source") == "model"],
                                overwrite=True)
    except OpError as e:
        raise boxroutes.to_api(e)
    if res["status"] == "failed":
        raise ApiError(422, res.get("detail") or "the result cannot be applied", code="compile_error")
    update_turn(d, turn_id, status=res["status"], after_rev=res["after_rev"], changes=res["changes"], conflicts=[], batch=res.get("batch"),
                batch_changes=res.get("batch_changes") or [])
    return {"ok": True, "action": "overwrite", "status": res["status"], "rev": res["after_rev"], "after_rev": res["after_rev"]}


@router.post("/edit/{turn_id}/undo")
def undo_edit(pid: str, turn_id: str, request: Request, body: dict = Body(None)):
    d = _pdir(request, pid)
    force = False
    if isinstance(body, dict):
        force = bool(body.get("force", False))

    from bti.draft.thread import load_thread, update_turn, get_turn_storyboard
    from bti.draft.merge import undo_apply, UndoConflict
    turns = load_thread(d)
    turn = next((t for t in turns if t.get("id") == turn_id), None)
    if turn is None:
        raise ApiError(404, "turn not found", code="turn_not_found")
    if turn.get("batch"):                      # a turn made through typed operations: its undo is the undo of its batch (the change log)
        return boxroutes.undo_batch_turn(d, turn)
    if turn.get("status") == "undone":
        raise ApiError(409, "turn already undone", code="already_undone")
    if turn.get("status") != "applied":
        raise ApiError(409, "turn was not applied", code="turn_not_applied")
    if not get_turn_storyboard(d, turn_id, "before") or not get_turn_storyboard(d, turn_id, "after"):
        raise ApiError(410, "Bản nháp trước lượt này không còn lưu; chỉ giữ 20 lượt gần nhất.", code="undo_unavailable")

    touched_ids = {c["shot_id"] for c in turn.get("changes", []) if c.get("shot_id")}
    try:
        with _storyboard_lock(request, pid, d):
            new_rev = undo_apply(d, turn_id, touched_ids, force=force)
    except UndoConflict as e:
        raise ApiError(409, "undo conflict: some shots were modified since this turn", code="undo_conflict", conflicts=e.conflicts)
    except LookupError:
        raise ApiError(410, "Bản nháp trước lượt này không còn lưu; chỉ giữ 20 lượt gần nhất.", code="undo_unavailable")
    except Exception as e:      # noqa: BLE001
        if hasattr(e, "issues"):
            raise ApiError(422, f"save refused: {e}", issues=getattr(e, "issues", []) or [], code="save_refused")
        raise

    update_turn(d, turn_id, status="undone")
    return {"ok": True, "status": "undone", "rev": new_rev, "after_rev": new_rev}


@router.get("/edit/{turn_id}/frames/{shot_id}/{when}.jpg")
def get_turn_frame(pid: str, turn_id: str, shot_id: str, when: str, request: Request):
    d = _pdir(request, pid)
    if when not in ("before", "after"):
        raise ApiError(404, "when must be 'before' or 'after'", code="turn_frame_not_found", field="when")

    from bti.draft.thread import get_turn_storyboard, load_thread
    turn = next((t for t in load_thread(d) if t.get("id") == turn_id), None)
    if turn is not None and turn.get("batch"):     # a batch turn: the change log's copy of the storyboard before or after the batch
        sb, shot_id = boxroutes.frame_source(d, turn, shot_id, when)
    else:
        sb = get_turn_storyboard(d, turn_id, when)
    if not sb:
        raise ApiError(404, "turn storyboard not found", code="turn_frame_not_found")

    shot = next((s for s in sb.get("shots", []) if isinstance(s, dict) and s.get("id") == shot_id), None)
    if not shot:
        raise ApiError(404, "shot not found", code="shot_not_found")

    # Compute frame time t
    t = None
    if shot.get("_t0") is not None and shot.get("_t1") is not None:
        t = shot["_t0"] + 0.4 * (shot["_t1"] - shot["_t0"])
    else:
        try:
            from bti.draft.inputs import read_json_file, normalize_timing
            from bti.engine.timing import Timing
            raw_t = read_json_file(d / "timing.json", "timing")
            tm = Timing(normalize_timing(raw_t))
            t0 = tm.resolve(shot["start"]) if isinstance(shot.get("start"), dict) else 0.0
            t = t0 + 0.5
        except Exception:
            t = 0.5

    from bti.editor import frames as frames_mod
    engine = getattr(request.app.state, "engine", None)
    p = engine.project(pid) if engine else None
    if p is None:
        from bti.editor.engine_adapter import EngineAdapter
        root = d.parent
        sroot = root.parent / "styles"
        eng = EngineAdapter(root, sroot)
        p = eng.project(pid)

    data = frames_mod.render_jpeg(p, t, 320, draft=sb)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=3600"})


@router.get("/thread")
def get_thread(pid: str, request: Request):
    d = _pdir(request, pid)
    from bti.draft.thread import reconcile_thread
    from bti.longjob import manager as global_mgr
    mgr = getattr(request.app.state, "longjob_manager", None) or global_mgr
    turns = boxroutes.enrich(d, boxroutes.turns_of(d, reconcile_thread(d, manager=mgr), "storyboard"))
    active_job_id = None
    try:
        if mgr:
            act = mgr.active(pid, "draft")
            if act and (act.get("meta") or {}).get("mode") == "edit" and (act.get("meta") or {}).get("doc") != "picks":
                active_job_id = act.get("id")
    except Exception:
        pass
    return {"turns": turns, "active_job_id": active_job_id}


@router.delete("/thread")
def delete_thread(pid: str, request: Request):
    d = _pdir(request, pid)
    from bti.longjob import manager as global_mgr
    mgr = getattr(request.app.state, "longjob_manager", None) or global_mgr
    try:
        if mgr:
            act = mgr.active(pid, "draft")
            if act and (act.get("meta") or {}).get("mode") == "edit":
                raise ApiError(409, "Không thể xóa lịch sử khi đang có yêu cầu sửa đang chạy. Hãy hủy tác vụ trước.", code="edit_running")
    except ApiError:
        raise
    except Exception:
        pass
    draft_run.clear_thread(d, "storyboard")          # the turns of the pictures' box (step 4) are kept
    return {"ok": True}
