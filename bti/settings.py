"""Model and agent settings.

Tracked defaults live in `config/agents.json`.
The owner's choices live in `run/settings.json` (git-ignored, kept by deploy), written atomically.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from bti.fsio import atomic_replace
from bti.script.brief import REPO_ROOT
from bti.script.providers.claudecode import is_claude_id

DEFAULT_MODEL = "agy:gemini-3.8-flash-high"

ROLES = (
    "script.outline",
    "script.narration",
    "script.title",
    "draft",
    "edit.fast",
    "edit.deep",
    "picks",
    "music",
)
AGENTIC_ROLES = {"draft", "edit.deep", "script.title", "music"}

ROLE_LABELS = {
    "script.outline": "Dàn ý kịch bản",
    "script.narration": "Lời dẫn kịch bản",
    "script.title": "Tựa video",
    "draft": "Dựng storyboard",
    "edit.fast": "Sửa storyboard nhanh (1 lượt)",
    "edit.deep": "Sửa storyboard sâu (agent)",
    "picks": "Chọn hình ảnh",
    "music": "Chọn nhạc",
}


class SettingsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def agents_file_path() -> Path:
    return Path(os.environ.get("BTI_AGENTS_FILE") or (REPO_ROOT / "config" / "agents.json"))


def settings_file_path() -> Path:
    return Path(os.environ.get("BTI_SETTINGS_FILE") or (REPO_ROOT / "run" / "settings.json"))


def load_agent_defaults() -> dict[str, str]:
    p = agents_file_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: str(v) for k, v in data.items() if isinstance(v, str)}
        except (OSError, ValueError):
            pass
    return {r: DEFAULT_MODEL for r in ROLES}


def load_user_settings() -> dict:
    p = settings_file_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
    return {}


def model_for(role: str) -> str:
    user = load_user_settings()
    user_models = user.get("models") if isinstance(user.get("models"), dict) else {}
    val = user_models.get(role) or user.get(role)
    if isinstance(val, str) and val.strip():
        return val.strip()
    defaults = load_agent_defaults()
    val = defaults.get(role)
    if isinstance(val, str) and val.strip():
        return val.strip()
    return DEFAULT_MODEL


def validate_model_updates(updates: dict[str, Any]) -> None:
    if not isinstance(updates, dict) or not updates:
        raise SettingsError("invalid_payload", "Payload must be a non-empty object mapping roles to model ids", 422)
    from bti.script import models as models_mod
    for role, model_id in updates.items():
        if role not in ROLES:
            raise SettingsError("unknown_role", f"Unknown role: {role!r}", 422)
        if not isinstance(model_id, str) or not model_id.strip():
            raise SettingsError("invalid_model", f"Model id for role {role!r} must be a non-empty string", 422)
        model_id = model_id.strip()
        if role in AGENTIC_ROLES and not (model_id.startswith("agy:") or is_claude_id(model_id)):
            raise SettingsError("agentic_role_needs_agy",
                                f"Role {role!r} requires an agent model: 'agy:<model>' or 'claude:<model>@<effort>' (got {model_id!r})", 422)
        spec = models_mod.resolve(model_id)
        if spec is None:
            raise SettingsError("unknown_model", f"Unknown model id: {model_id!r}", 422)


def _write_user_settings(current: dict) -> None:
    """The owner's settings file, written atomically (every key of `current` is kept as given)."""
    p = settings_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp.{os.getpid()}_{time.time_ns()}")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_replace(tmp, p)


def save_model_settings(updates: dict[str, Any]) -> dict:
    validate_model_updates(updates)
    current = load_user_settings()
    models = dict(current.get("models") or {}) if isinstance(current.get("models"), dict) else {}
    for r, m in updates.items():
        models[r] = m.strip()
    current["models"] = models
    _write_user_settings(current)
    return get_model_settings()


def get_machine_agent() -> str | None:
    """The agent id the owner set as the default for projects without a choice (`run/settings.json`, key `agent`), or None.
    Whether the id is still listed in `config/agent_choices.json` is `bti.agents`' business."""
    val = load_user_settings().get("agent")
    return val.strip() if isinstance(val, str) and val.strip() else None


def set_machine_agent(agent_id: str | None) -> None:
    """Store (or, with None, remove) the machine's default agent id. The other settings are kept."""
    current = load_user_settings()
    if agent_id is None:
        if "agent" not in current:
            return
        current.pop("agent", None)
    else:
        current["agent"] = str(agent_id).strip()
    _write_user_settings(current)


def get_model_settings(refresh: bool = False) -> dict:
    from bti.script import models as models_mod
    available_models = models_mod.public_models(refresh=refresh)
    available_ids = {m["id"] for m in available_models}
    user = load_user_settings()
    user_models = user.get("models") if isinstance(user.get("models"), dict) else {}
    roles_list = []
    for r in ROLES:
        val = model_for(r)
        src = "setting" if (r in user_models or (r in user and not isinstance(user.get(r), dict))) else "default"
        in_avail = val in available_ids
        roles_list.append({
            "role": r,
            "label": ROLE_LABELS.get(r, r),
            "value": val,
            "model": val,
            "source": src,
            "in_available": in_avail,
            "agentic": r in AGENTIC_ROLES,
        })
    return {"roles": roles_list, "models": available_models}


# ---- outfolder: the one switch of the output folder (bti/output/): clean the working folder's caches after a successful export (`run/settings.json`, key `output`)
def get_output_settings() -> dict:
    """`{"clean_after_export": bool}`; the cleaning is on unless the owner switched it off."""
    block = load_user_settings().get("output")
    val = block.get("clean_after_export") if isinstance(block, dict) else None
    return {"clean_after_export": val if isinstance(val, bool) else True}


def set_output_clean(flag: bool) -> dict:
    """Switch the cleaning on or off; the other settings are kept. Returns `get_output_settings()`."""
    if not isinstance(flag, bool):
        raise SettingsError("invalid_payload", "clean_after_export must be true or false", 422)
    current = load_user_settings()
    block = dict(current.get("output")) if isinstance(current.get("output"), dict) else {}
    block["clean_after_export"] = flag
    current["output"] = block
    _write_user_settings(current)
    return get_output_settings()


# ---- websearch: the owner's choices about the pictures step (`run/settings.json`, key `picks`): the switch of the web search of the automatic choice of pictures
def get_picks_block() -> dict:
    """The owner's `picks` block of the settings file (a copy; {} when there is none)."""
    block = load_user_settings().get("picks")
    return dict(block) if isinstance(block, dict) else {}


def set_picks_block(updates: dict) -> dict:
    """Merge `updates` into the owner's `picks` block (the other settings are kept) and write it. Returns the block."""
    current = load_user_settings()
    block = dict(current.get("picks")) if isinstance(current.get("picks"), dict) else {}
    block.update(updates)
    current["picks"] = block
    _write_user_settings(current)
    return dict(block)
