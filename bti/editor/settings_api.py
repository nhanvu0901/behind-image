from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Body, Query

from bti.editor.common import ApiError
from bti.settings import SettingsError, get_model_settings, save_model_settings

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
