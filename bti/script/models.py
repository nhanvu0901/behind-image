"""config/models.json: the models the dropdown offers. A model whose key is not set is listed but disabled."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .brief import REPO_ROOT
from .env import has_key


def models_path() -> Path:
    return Path(os.environ.get("BTI_MODELS_FILE") or REPO_ROOT / "config" / "models.json")


def load_models(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else models_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for m in raw if isinstance(raw, list) else []:
        if isinstance(m, dict) and m.get("id") and m.get("provider") in ("gemini", "openrouter", "mock"):
            out.append(m)
    return out


def public(m: dict) -> dict:
    """What the API shows: never a key, only the NAME of the variable that is missing."""
    env = m.get("key_env")
    ok = m["provider"] == "mock" or has_key(env)
    return {"id": m["id"], "label": m.get("label") or m["id"], "provider": m["provider"], "model": m.get("model"),
            "default": bool(m.get("default")), "enabled": ok, "missing_env": None if ok else env}


def public_models(path: Path | None = None) -> list[dict]:
    return [public(m) for m in load_models(path)]


def get_model(model_id: str, path: Path | None = None) -> dict | None:
    return next((m for m in load_models(path) if m["id"] == model_id), None)
