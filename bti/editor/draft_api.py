"""Routes of the storyboard draft (design section 7). Mounted by CORE: `app.include_router(draft_api.router)`.

    GET  /api/projects/{pid}/draft          readiness (voice, picks), state, last run, default model
    GET  /api/projects/{pid}/draft/models   the models `agy models` lists (cached ten minutes)
    POST /api/projects/{pid}/draft/start    {provider: "agy" | "auto", model?, chapters?}  -> {job_id}   (a long job: /api/longjobs/{id})

The proposal the job writes is read and applied through the existing proposal routes. The projects folder is read from
`app.state.projects_root`."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Request, Response

from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.settings import model_for

from .common import ApiError, valid_pid

router = APIRouter(prefix="/api/projects/{pid}/draft")


def _pdir(request: Request, pid: str) -> Path:
    if not valid_pid(pid):
        raise ApiError(404, "project not found")
    root = Path(getattr(request.app.state, "projects_root", None) or Path(__file__).resolve().parents[2] / "projects")
    d = root / pid
    if not d.is_dir() or d.is_symlink():
        raise ApiError(404, "project not found")
    return d


@router.get("")
def get_draft(pid: str, request: Request):
    d = _pdir(request, pid)
    return draft_run.overview(pid, d, model_for("draft"))


@router.get("/models")
def get_models(pid: str, request: Request, refresh: int = 0):
    _pdir(request, pid)
    try:
        from bti.script import models as models_mod
        rows, err = models_mod.agy_models(refresh=bool(refresh))
    except Exception:       # noqa: BLE001 - the list can never break the page
        rows, err = None, "`agy models` không đọc được."
    return {"default": model_for("draft"), "models": rows or [], "error": err}


@router.post("/start")
def post_start(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object")
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
        status = 409 if e.code in ("draft_not_ready", "agy_missing", "scope_needs_storyboard", "picks_missing", "timing_missing", "picks_no_main") else 422
        raise ApiError(status, e.message, code=e.code)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ApiError(409, "a draft is already running for this project", code="busy", job_id=getattr(e, "job_id", None))
        raise
    return {"job_id": job["id"]}


@router.post("/edit")
def post_edit(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    if not isinstance(body, dict):
        raise ApiError(422, "body must be an object")
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
    followup = bool(body.get("followup", False))
    base_rev = body.get("base_rev")

    try:
        res = draft_run.start(pid, d, instruction=instruction, edit_scope=scope, model=model or None,
                              followup=followup, base_rev=base_rev)
    except DraftError as e:
        status = 409 if e.code in ("draft_not_ready", "agy_missing", "scope_needs_storyboard", "edit_no_storyboard", "edit_needs_agy", "picks_missing", "timing_missing", "picks_no_main", "stale_revision") else 422
        raise ApiError(status, e.message, code=e.code)
    except Exception as e:      # noqa: BLE001
        if type(e).__name__ == "Busy":
            raise ApiError(409, "a draft is already running for this project", code="busy", job_id=getattr(e, "job_id", None))
        raise
    return {"job_id": res["id"], "turn_id": res["turn_id"]}


@router.get("/thread")
def get_thread(pid: str, request: Request):
    d = _pdir(request, pid)
    from bti.draft.thread import reconcile_thread
    from bti.longjob import manager as global_mgr
    mgr = getattr(request.app.state, "longjob_manager", None) or global_mgr
    turns = reconcile_thread(d, manager=mgr)
    active_job_id = None
    try:
        if mgr:
            act = mgr.active(pid, "draft")
            if act and (act.get("meta") or {}).get("mode") == "edit":
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
                raise ApiError(409, "Không thể xóa lịch sử khi đang có yêu cầu sửa đang chạy. Hãy hủy tác vụ trước.")
    except ApiError:
        raise
    except Exception:
        pass
    draft_run.clear_thread(d)
    return {"ok": True}
