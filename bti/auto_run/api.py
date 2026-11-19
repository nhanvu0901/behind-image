"""The routes of the automatic run (mounted by `bti/editor/auto_api.py`, which has the app's own `pdir`).

    POST /api/projects/{pid}/auto/run   {until?: step id | null, max_steps?: 1..200 (40), actor?} -> {job_id, run_id}
        starts one long job of kind `auto` (follow it with GET /api/longjobs/{job_id}, stop it with POST /api/longjobs/{job_id}/cancel, or
        the `auto.cancel` action of the state answer). 409 `auto_not_enabled` while the project's `auto` is off, 409 `auto_running` while a run of this project
        goes on, 409 `longjob_running` / `script_job_running` while another job of the project runs; 422 `invalid_field` for an unknown step or a bad `max_steps`.
    GET  /api/projects/{pid}/auto/runs?limit=10   -> {items: [one line per run, newest first]}   (`state` running | finished, `outcome`, `reason`, `sentence`, `link`, `live`)
    GET  /api/projects/{pid}/auto/runs/{run_id}   -> the whole record, with one entry per step

The run calls the app's own routes over HTTP (`app.state.auto_transport()` when a test sets it; else the address this request reached the server at).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body, Request

from bti import auto as A
from bti.cli.transport import DEFAULT_URL, HttpTransport

from . import job as job_mod, loop, reasons, runlog


def _api_error(*a: Any, **k: Any):
    from bti.editor.common import ApiError
    return ApiError(*a, **k)


def local_url(request: Request) -> str:
    """Where the app answers, as seen from inside the process: the address of the socket this request came in on (the loop calls the same app over HTTP, like any agent)."""
    server = request.scope.get("server")
    if isinstance(server, (list, tuple)) and len(server) == 2 and server[1]:
        host = str(server[0])
        return "http://%s:%d" % ("[%s]" % host if ":" in host else host, int(server[1]))
    return os.environ.get("BTI_URL") or DEFAULT_URL


def check_body(body: Any) -> tuple[str | None, int, str]:
    """(until, max_steps, actor) of the body of POST .../auto/run; 422 `invalid_field` with `fields` for anything that is not right."""
    from bti.editor.auto_api import actor_of
    if not isinstance(body, dict):
        raise _api_error(422, "body must be an object", code="invalid_field", fields=[{"path": "", "problem": "must be a JSON object"}])
    fields = [{"path": str(k)[:40], "problem": "is not a field of this request", "allowed": ["until", "max_steps", "actor"]} for k in body if k not in ("until", "max_steps", "actor")]
    until, steps = body.get("until"), body.get("max_steps", loop.DEFAULT_MAX_STEPS)
    if until is not None and until not in reasons.STEP_IDS:
        fields.append({"path": "until", "problem": "must be null or a step id", "allowed": reasons.STEP_IDS})
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= loop.MAX_STEPS_LIMIT:
        fields.append({"path": "max_steps", "problem": "must be a whole number from 1 to %d" % loop.MAX_STEPS_LIMIT})
    if fields:
        raise _api_error(422, "The request is not valid: %s %s." % (fields[0]["path"] or "body", fields[0]["problem"]), code="invalid_field", fields=fields)
    return until, int(steps), actor_of(body)


def make_router(*, pdir: Callable[[str], Path]) -> APIRouter:
    router = APIRouter(tags=["auto"])                  # included into the router of auto_api, which has the prefix /api

    def manager_of(request: Request):
        from bti.longjob import manager as default
        return getattr(request.app.state, "longjob_manager", None) or default

    @router.post("/projects/{pid}/auto/run")
    def run(pid: str, request: Request, body: dict = Body(default={})):
        from bti.editor import state_api
        d = pdir(pid)
        until, max_steps, actor = check_body(body)
        doc, _ = A.read_project(d)
        if doc.get("enabled") is not True:
            raise _api_error(409, "Automatic running is off for this project: the owner turns it on (\"Cho agent tự chạy dự án này\").", code="auto_not_enabled", auto=A.public(doc))
        mgr = manager_of(request)
        busy = [j for j in state_api.running_jobs(pid, d, getattr(request.app.state, "script_jobs", None), None, mgr) if j.get("kind") != "preview"]
        if busy:
            j = next((x for x in busy if x.get("kind") == "auto"), busy[0])
            if j.get("kind") == "auto":
                raise _api_error(409, "An automatic run of this project is already going.", code="auto_running", job_id=j.get("id"), run=(runlog.list_runs(d, mgr, 1) or [{}])[0].get("id"))
            code = "script_job_running" if j.get("kind") in state_api.SCRIPT_JOB_KINDS else "longjob_running"
            raise _api_error(409, "Another job of this project is running (%s): an automatic run never starts a second one." % j.get("kind"), code=code, job_id=j.get("id"), kind=j.get("kind"))
        make = getattr(request.app.state, "auto_transport", None)
        transport = make() if callable(make) else HttpTransport(local_url(request))
        options = dict(getattr(request.app.state, "auto_options", None) or {})
        try:
            from bti.longjob import Busy
            started = job_mod.start(d, pid, transport, until=until, max_steps=max_steps, actor=actor, manager=mgr, **options)
        except Busy as e:
            raise _api_error(409, "An automatic run of this project is already going.", code="auto_running", job_id=(getattr(e, "job", None) or {}).get("id"))
        return started

    @router.get("/projects/{pid}/auto/runs")
    def runs(pid: str, request: Request, limit: int = 10):
        d = pdir(pid)
        return {"items": runlog.list_runs(d, manager_of(request), max(1, min(int(limit), 30)))}

    @router.get("/projects/{pid}/auto/runs/{run_id}")
    def one_run(pid: str, run_id: str, request: Request):
        d = pdir(pid)
        rec = runlog.read_run(d, run_id)
        if rec is None:
            raise _api_error(404, "run not found", code="auto_run_not_found")
        job = None
        if rec.get("ended") is None and isinstance(rec.get("job_id"), str):
            try:
                job = manager_of(request).get(rec["job_id"])
            except Exception:       # noqa: BLE001
                job = None
        s = runlog.summary(rec, job)
        return {**rec, **{k: s[k] for k in ("state", "outcome", "reason", "sentence", "result", "live") if k in s}}

    return router
