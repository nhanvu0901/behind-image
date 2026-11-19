"""Who may approve a gate (worker c5cli). Mounted by `create_app` (it needs the app's own `pdir`).

    GET /api/projects/{pid}/auto     -> {schema, rev, enabled, gates, spend, warnings}
    PUT /api/projects/{pid}/auto     {base_rev, enabled?, gates?: {gate: bool}, spend?: {kind: bool}, actor?}  -> the same answer.
                                     A key left out stays; the maps change only the names they list. 409 `stale` (with the current `rev`) for an
                                     old `base_rev`, 422 `invalid_field` (with `fields`). Only the owner changes it: a PUT whose `actor` is not
                                     `human` is 403 `auto_needs_human` (the page sends no actor).

The automatic run (`POST .../auto/run`, `GET .../auto/runs`) is in `bti/auto_run/` and is mounted at the end of `make_router`.

The rule the four approval routes use is in `gate_actor` below (the routes call it first, before they look at anything else):

    * `actor` is an optional field of the body of `outline/approve`, `narration/approve`, `picks/approve` and `approve` (the storyboard): `human`
      (the default: the page sends nothing), `agent:<model id>` or `cli:<name>`; anything else is 422 `invalid_field`.
    * an actor that is not `human` may approve only when the project's `auto.json` has `enabled` true and allows that gate; otherwise 403
      `gate_needs_human`, nothing is written.
    * the actor is recorded in the approval (`approval.by` of the script documents and of the picks, `approvals.storyboard.by` of the
      storyboard) and the state answer shows it.

`paid_actor` is the same idea for the one paid call (`picks/suggest`): an actor that is not `human` never starts it (403 `spend_needs_human`).
The actor is what the caller says it is: the rule keeps an honest agent (the `bti` command always sends `cli:...`) from approving or spending
what the owner did not allow; it is not an authentication.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Body

from bti import auto as A

from .common import ApiError


def auto_error(e: A.AutoError) -> ApiError:
    return ApiError(e.status, e.message, code=e.code, **e.extra)


def actor_of(body: Any) -> str:
    """The actor a body names: `human` when it names none; 422 `invalid_field` when it is not one of the three forms."""
    a = body.get("actor") if isinstance(body, dict) else None
    if a is None:
        return "human"
    if not isinstance(a, str) or not A.ACTOR_RE.match(a):
        raise ApiError(422, "actor must be human, agent:<model id> or cli:<name>", code="invalid_field",
                       fields=[{"path": "actor", "problem": "must be human, agent:<model id> or cli:<name>", "allowed": A.ACTOR_FORMS}])
    return a


def gate_actor(d: Path, gate: str, body: Any) -> str:
    """The actor of an approval of `gate`, after the rule: an actor that is not `human` needs the owner's `auto` to allow the gate (403
    `gate_needs_human` otherwise). Returns the actor to record."""
    actor = actor_of(body)
    if actor != "human":
        doc, _ = A.read_project(d)
        why = A.gate_refusal(doc, gate)
        if why:
            detail = ("The %s gate can only be approved by the owner: automatic running is off for this project." % gate if why == "auto_off"
                      else "The owner did not allow an agent to approve the %s gate of this project." % gate)
            raise ApiError(403, detail, code="gate_needs_human", gate=gate, actor=actor, reason=why, auto=A.public(doc))
    return actor


def paid_actor(body: Any) -> str:
    """The actor of the one paid call: an actor that is not `human` never starts it (403 `spend_needs_human`)."""
    actor = actor_of(body)
    if actor != "human":
        raise ApiError(403, "An agent never spends money: the owner starts a paid call on the page.", code="spend_needs_human", kind="paid", actor=actor)
    return actor


def make_router(*, pdir: Callable[[str], Path]) -> APIRouter:
    """`pdir(pid)` is the app's own helper: the project's folder, 404 for an unknown project."""
    router = APIRouter(prefix="/api", tags=["auto"])

    @router.get("/projects/{pid}/auto")
    def get_auto(pid: str):
        return A.view(pdir(pid))

    @router.put("/projects/{pid}/auto")
    def put_auto(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        if not isinstance(body, dict):
            raise ApiError(422, "body must be an object", code="invalid_field", fields=[{"path": "", "problem": "must be a JSON object"}])
        if actor_of(body) != "human":
            raise ApiError(403, "Only the owner changes automatic running: do it on the page.", code="auto_needs_human", actor=body.get("actor"))
        try:
            return A.update(d, {k: v for k, v in body.items() if k not in ("base_rev", "actor")}, body.get("base_rev"))
        except A.AutoError as e:
            raise auto_error(e)

    from bti.auto_run.api import make_router as _run_router      # c6auto: "Chạy tự động": POST .../auto/run, GET .../auto/runs
    router.include_router(_run_router(pdir=pdir))
    return router
