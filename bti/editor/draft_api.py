"""Routes of the storyboard draft (design section 7). Mounted by CORE: `app.include_router(draft_api.router)`.

    GET  /api/projects/{pid}/draft          readiness (voice, picks), state, last run, default model
    GET  /api/projects/{pid}/draft/models   the models `agy models` lists (cached ten minutes)
    POST /api/projects/{pid}/draft/start    {provider: "agy" | "auto", model?, chapters?}  -> {job_id}   (a long job: /api/longjobs/{id})

The proposal the job writes is read and applied through the existing proposal routes. The projects folder is read from
`app.state.projects_root`."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Request

from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.draft.providers.agy import DEFAULT_MODEL

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
    return draft_run.overview(pid, d, DEFAULT_MODEL)


@router.get("/models")
def get_models(pid: str, request: Request, refresh: int = 0):
    _pdir(request, pid)
    try:
        from bti.script import models as models_mod
        rows, err = models_mod.agy_models(refresh=bool(refresh))
    except Exception:       # noqa: BLE001 - the list can never break the page
        rows, err = None, "`agy models` không đọc được."
    return {"default": DEFAULT_MODEL, "models": rows or [], "error": err}


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
