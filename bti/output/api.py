"""The two routes of the output folder (mounted by app.py):

    POST /api/projects/{pid}/output/build    fill (or refill) the folder of the project from the project as it stands. Body (all optional): {"clean": true} also removes the working
                                             folder's caches when the export stands. A long call (the contact sheets of a finished video take a few seconds). The state answer lists it as
                                             the action `output.build`.
    GET  /api/projects/{pid}/output          what the folder holds: {"enabled", "key", "folder", "state"} (state = state.json, or null when the folder is not there yet)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Request

from bti.editor.common import ApiError, valid_pid

from . import fsutil, hooks, publish
from .facts import collect
from .paths import STATE_FILE

router = APIRouter(prefix="/api")


def _root(request: Request) -> Path:
    out = getattr(request.app.state, "output_root", None)
    if out is None:
        raise ApiError(409, "this app has no output folder", code="output_disabled")
    return Path(out)


def _pdir(request: Request, pid: str) -> Path:
    root = Path(request.app.state.projects_root)
    if not valid_pid(pid) or not (root / pid).is_dir():
        raise ApiError(404, "project not found", code="project_not_found")
    return root / pid


@router.post("/projects/{pid}/output/build")
def build(pid: str, request: Request, body: dict = Body(default={})):
    out = _root(request)
    d = _pdir(request, pid)
    body = body if isinstance(body, dict) else {}
    clean = body.get("clean")
    if clean is not None and not isinstance(clean, bool):
        raise ApiError(422, "clean must be true or false", code="invalid_field", field="clean")
    try:
        res = publish.sync(d, out, moment="rebuild", explicit=True, clean=bool(clean), force=True)
    except publish.NotApplicable as e:
        raise ApiError(409, "this project has no output folder (%s)" % e.reason, code="output_not_applicable")
    except OSError as e:
        raise ApiError(500, "the output folder could not be written: %s" % str(e)[:150], code="output_failed")
    return {"key": res["key"], "folder": "output/%s" % res["key"], "written": len(res.get("written") or []), "parts": res.get("parts"), "warnings": res.get("warnings") or [],
            "clean": res.get("clean"), "takeover": bool(res.get("takeover"))}


@router.get("/projects/{pid}/output")
def status(pid: str, request: Request):
    out = getattr(request.app.state, "output_root", None)
    d = _pdir(request, pid)
    if out is None:
        return {"enabled": False, "key": None, "folder": None, "state": None}
    f = collect(d, jobs=False)
    st = fsutil.read_json(Path(out) / f.key / STATE_FILE)
    return {"enabled": True, "key": f.key, "folder": "output/%s" % f.key, "state": st if isinstance(st, dict) else None, "warnings": hooks.warnings_for(out, d)}
