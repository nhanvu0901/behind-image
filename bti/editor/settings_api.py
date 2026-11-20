from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body, Query

from bti import agents as AG
from bti.editor.common import ApiError
from bti.settings import SettingsError, get_model_settings, get_output_settings, save_model_settings, set_output_clean   # outfolder: + the output switch

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/models")
def list_settings_models(refresh: int = Query(0)):
    return get_model_settings(refresh=bool(refresh))


@router.put("/models")
def update_settings_models(body: dict[str, Any] = Body(...)):
    try:
        return save_model_settings(body)
    except SettingsError as e:
        raise ApiError(e.status_code, e.message, code=e.code)


@router.put("/agent")
def update_settings_agent(body: dict[str, Any] = Body(...)):
    """The machine's default agent, for projects that have no choice of their own (`{agent: id}`; `{agent: null}` clears it).
    Answers like GET /api/agents. 422 `unknown_agent`."""
    if "agent" not in body:
        raise ApiError(422, "agent (id or null) is required", code="invalid_payload")
    try:
        return AG.set_machine_default(body["agent"])
    except AG.AgentError as e:
        raise ApiError(e.status, e.message, code=e.code, **e.extra)


# ---- outfolder: the switch of the output folder (bti/output/): clean the working folder's caches after a successful export
@router.get("/output")
def get_settings_output():
    return get_output_settings()


@router.put("/output")
def put_settings_output(body: dict[str, Any] = Body(...)):
    """`{clean_after_export: true|false}`. Answers `{clean_after_export}`. 422 `invalid_payload`."""
    if not isinstance(body, dict) or "clean_after_export" not in body:
        raise ApiError(422, "clean_after_export (true or false) is required", code="invalid_payload")
    try:
        return set_output_clean(body["clean_after_export"])
    except SettingsError as e:
        raise ApiError(e.status_code, e.message, code=e.code)


# ---- websearch: the owner's switch of the web search of the automatic choice of pictures (bti/picks/websettings.py; `run/settings.json`, block `picks`)
@router.get("/web-search")
def get_settings_web_search():
    """`{auto_web_search: "on" | "off", auto_web_search_max, source}`: whether the automatic choice of pictures may search the web (PAID, You.com) and how many
    searches one run may make. Off unless the owner switched it on."""
    from bti.picks import websettings
    return websettings.settings()


@router.put("/web-search")
def put_settings_web_search(body: dict[str, Any] = Body(...)):
    """`{auto_web_search?: "on" | "off", auto_web_search_max?: 1..500, actor?}`. Answers like GET. Only the owner changes it: a PUT whose `actor` is not
    `human` is 403 `spend_needs_human` (the page sends no actor; an agent never switches on a paid thing). 422 `invalid_payload`."""
    from bti.editor.auto_api import actor_of
    from bti.picks import websettings
    if not isinstance(body, dict):
        raise ApiError(422, "the body must be an object", code="invalid_payload")
    actor = actor_of(body)
    if actor != "human":
        raise ApiError(403, "An agent never switches on a paid search: the owner does it on the settings page.", code="spend_needs_human", kind="paid", actor=actor)
    try:
        return websettings.save(body.get("auto_web_search"), body.get("auto_web_search_max"))
    except SettingsError as e:
        raise ApiError(e.status_code, e.message, code=e.code)

