"""Visual document routes. Mount `router` in the editor application."""
from fastapi import APIRouter, Body, Request
from bti.editor.common import ApiError
from bti.editor.picks_api import _pdir
from bti.ops.batch import _ACTOR
from bti.script.store import read_object, StaleRevision
from . import store
from .validate import validate

router = APIRouter(prefix="/api")


@router.get("/projects/{pid}/visual")
def get_visual(pid: str, request: Request):
    project = _pdir(request, pid)
    document = store.load(project)
    timing = read_object(project / "timing.json", "timing")
    picks = read_object(project / "picks.json", "picks")
    issues = validate(document, timing, picks) if document is not None and timing is not None else []
    return {"visual": document, "rev": store.revision(document) if document is not None else None, "issues": issues}


@router.get("/projects/{pid}/visual/words")
def get_visual_words(pid: str, request: Request):
    project = _pdir(request, pid)
    timing = read_object(project / "timing.json", "timing")
    if not isinstance(timing, dict):
        return {"present": False, "words": [], "beats": [], "chapters": [], "duration": None}
    return {
        "present": True,
        "words": timing.get("words") or [],
        "beats": timing.get("beats") or [],
        "chapters": timing.get("chapters") or [],
        "duration": timing.get("duration"),
    }


@router.put("/projects/{pid}/visual")
def put_visual(pid: str, request: Request, body: dict = Body(...)):
    project = _pdir(request, pid)
    if "base_rev" not in body or (body["base_rev"] is not None and not isinstance(body["base_rev"], str)):
        raise ApiError(422, "base_rev must be a revision or null", code="invalid_request", field="base_rev")
    actor = body.get("actor")
    if not isinstance(actor, str) or not _ACTOR.fullmatch(actor):
        raise ApiError(422, "actor must identify the caller", code="invalid_request", field="actor")
    document = body.get("visual")
    timing = read_object(project / "timing.json", "timing")
    if timing is None:
        raise ApiError(409, "timing is required", code="timing_missing")
    picks = read_object(project / "picks.json", "picks")
    issues = validate(document, timing, picks)
    if any(issue.get("level") != "review" for issue in issues):
        raise ApiError(422, "visual document has issues", code="validation_failed", issues=issues)
    try:
        rev = store.save(project, document, base_rev=body["base_rev"], actor=actor)
    except StaleRevision:
        current = store.load(project)
        raise ApiError(409, "base_rev is stale", code="stale_revision", current_rev=store.revision(current) if current else None)
    return {"visual": document, "rev": rev, "issues": issues}


@router.post('/projects/{pid}/visual/plan')
def plan_visual(pid: str, request: Request, body: dict = Body(default={})):
    from bti.visual import job
    from bti.picks.auto.inputs import AutoError
    from bti.draft.inputs import DraftError
    from bti.longjob import Busy
    from bti.editor.auto_api import actor_of
    from bti.auto import RUN_ACTOR
    try:
        actor = actor_of(body)
        web = {'on': False, 'max': 0} if actor != 'human' else None
        result = job.start(pid, _pdir(request, pid), model=body.get('model'),
                           manager=getattr(request.app.state, 'longjob_manager', None), by_run=actor == RUN_ACTOR, web=web)
    except AutoError as e:
        raise ApiError(e.status, e.message, code=e.code, **e.extra)
    except DraftError as e:
        raise ApiError(409, e.message, code=e.code)
    except Busy as e:
        raise ApiError(409, 'A picks job is already running.', code='busy', job_id=e.job_id)
    return {'job_id': result['id'], 'model': (result.get('meta') or {}).get('model'), 'agent': (result.get('meta') or {}).get('agent')}
