"""Which agent works on a project (contract docs/design/2026-11-18-agent-choice.md, section 5). Mounted by `create_app` (it needs the app's
own `pdir`, so that an unknown or deleted project is the same 404 as everywhere).

    GET /api/agents                      -> {agents: [{id, label, model, available, reason, reason_code}], default, machine_default, warnings}
                                            `available` comes from what the app already caches (`agy models`, the Claude Code check); the route
                                            never calls a model. `?refresh=1` asks those two checks again.
    GET /api/projects/{pid}/agent        -> {rev, agent, steps, effective: {step: {id, label, model, source}}, warnings}
    PUT /api/projects/{pid}/agent        {agent?, steps?, base_rev}  -> the same answer. A key present with null clears that choice (`steps: null`
                                            clears every step choice); a key left out stays. 409 `stale` for an old `base_rev` (with the current
                                            `rev`), 422 `unknown_agent` / `unknown_step` / `invalid_payload`.
The machine's default agent is `PUT /api/settings/agent` (settings_api.py). Whatever the page chooses is read by every model call of steps 2
to 5 through `bti.agents.model_for_project`; no route here starts a model.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Body, Query

from bti import agents as AG

from .common import ApiError


def agent_error(e: AG.AgentError) -> ApiError:
    return ApiError(e.status, e.message, code=e.code, **e.extra)


def make_router(*, pdir: Callable[[str], Path]) -> APIRouter:
    """`pdir(pid)` is the app's own helper: the project's folder, 404 for an unknown project."""
    router = APIRouter(prefix="/api", tags=["agents"])

    @router.get("/agents")
    def list_agents(refresh: int = Query(0)):
        return AG.public_agents(refresh=bool(refresh))

    @router.get("/projects/{pid}/agent")
    def get_project_agent(pid: str):
        return AG.project_view(pdir(pid))

    @router.put("/projects/{pid}/agent")
    def put_project_agent(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        if not isinstance(body, dict):
            raise ApiError(422, "body must be an object", code="invalid_payload")
        try:
            return AG.update_project(d, {k: body[k] for k in ("agent", "steps") if k in body}, body.get("base_rev"))
        except AG.AgentError as e:
            raise agent_error(e)

    return router
