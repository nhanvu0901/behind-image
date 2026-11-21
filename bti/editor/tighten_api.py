"""HTTP routes for the standalone second look (`picks.tighten`, worker tightbox):

    POST /api/projects/{pid}/picks/tighten   optional {regions?, base_rev?, model?, actor?} -> {job_id, job}
    GET  /api/projects/{pid}/picks/tighten   -> {running, non_tight, agent, limits}
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Request

from bti.picks import auto
from bti.picks.auto import tighten_job

from .auto_api import actor_of
from .common import ApiError
from .picks_api import _pdir

router = APIRouter(prefix="/api")


@router.post("/projects/{pid}/picks/tighten")
def start_tighten(pid: str, request: Request, body: dict = Body(None)):
    """Start the standalone region-tightening long job (`kind='picks'`, `meta.action='tighten'`)."""
    from bti import auto as rule
    d = _pdir(request, pid)
    body = body if body is not None else {}
    if not isinstance(body, dict):
        raise ApiError(422, "the body must be an object", code="invalid_request")
    by_run = actor_of(body) == rule.RUN_ACTOR
    regions, base_rev, model = body.get("regions"), body.get("base_rev"), body.get("model")
    if regions is not None and not (isinstance(regions, list) and all(isinstance(r, str) for r in regions) and 0 < len(regions) <= 60):
        raise ApiError(422, "regions must be null or a list of region names", code="invalid_field", field="regions")
    if base_rev is not None and not isinstance(base_rev, str):
        raise ApiError(422, "base_rev must be a string", code="invalid_field", field="base_rev")
    if model is not None and not isinstance(model, str):
        raise ApiError(422, "model must be text", code="bad_model")
    try:
        rec = tighten_job.start(pid, d, regions=regions, base_rev=base_rev, model=model or None, by_run=by_run)
    except auto.AutoError as e:
        raise ApiError(e.status, e.message, code=e.code, **e.extra)
    meta = rec.get("meta") or {}
    return {"job_id": rec["id"], "model": meta.get("model"), "agent": meta.get("agent"), "regions": len(meta.get("regions") or [])}


@router.get("/projects/{pid}/picks/tighten")
def get_tighten(pid: str, request: Request):
    """The running `picks.tighten` job and the main painting's non-tight region names."""
    return tighten_job.overview(pid, _pdir(request, pid))
