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
    return {"visual": document, "rev": store.revision(document) if document is not None else None}


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
