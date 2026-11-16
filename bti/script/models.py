"""config/models.json: the models the dropdown offers. A model whose key (or login) is missing is listed but disabled.

A `provider: "antigravity"` entry is expanded from `agy models` into one entry `<id>:<slug>` per model (the CLI's
default first), cached for about 10 minutes."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from .brief import REPO_ROOT
from .env import has_key

PROVIDERS = ("gemini", "openrouter", "mock", "antigravity")
CACHE_SECONDS = 600
FAIL_SECONDS = 30
_cache: dict = {"at": 0.0, "ttl": 0, "rows": None, "error": None}
_lock = threading.Lock()


def models_path() -> Path:
    return Path(os.environ.get("BTI_MODELS_FILE") or REPO_ROOT / "config" / "models.json")


def reset_cache() -> None:
    _cache.update({"at": 0.0, "ttl": 0, "rows": None, "error": None})


def agy_models() -> tuple[list[dict] | None, str | None]:
    """-> (rows, None) or (None, message). Cached ~10 minutes (30 seconds after a failure)."""
    from .providers import ProviderError
    from .providers import antigravity
    with _lock:
        if time.time() - _cache["at"] < _cache["ttl"]:
            return _cache["rows"], _cache["error"]
        try:
            rows, err, ttl = antigravity.list_models(), None, CACHE_SECONDS
        except ProviderError as e:
            rows, err, ttl = None, e.message, FAIL_SECONDS
        _cache.update({"at": time.time(), "ttl": ttl, "rows": rows, "error": err})
        return rows, err


def load_raw(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else models_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [m for m in raw if isinstance(m, dict) and m.get("id") and m.get("provider") in PROVIDERS] if isinstance(raw, list) else []


def load_models(path: Path | None = None) -> list[dict]:
    """Specs ready for the providers. An unavailable agy gives one entry with `unavailable` set to the message."""
    out = []
    for m in load_raw(path):
        if m["provider"] != "antigravity":
            out.append(m)
            continue
        rows, err = agy_models()
        if rows is None:
            out.append({**m, "id": m["id"], "unavailable": err, "model": None})
            continue
        for i, r in enumerate(rows):
            out.append({**m, "id": f"{m['id']}:{r['slug']}", "model": r["slug"], "label": f"{m.get('label') or 'Antigravity CLI'}: {r['label']}",
                        "default": bool(m.get("default")) and i == 0, "key_env": None})
    return out


def public(m: dict) -> dict:
    """What the API shows: never a key, only the NAME of the missing variable or a plain message."""
    env = m.get("key_env")
    if m.get("unavailable"):
        ok, why = False, m["unavailable"]
    elif m["provider"] in ("mock", "antigravity"):
        ok, why = True, None
    else:
        ok = has_key(env)
        why = None if ok else f"thiếu biến {env}"
    return {"id": m["id"], "label": m.get("label") or m["id"], "provider": m["provider"], "model": m.get("model"),
            "default": bool(m.get("default")), "enabled": ok, "missing_env": None if ok or m.get("unavailable") else env,
            "message": why, "paid": m["provider"] in ("openrouter", "gemini")}


def public_models(path: Path | None = None) -> list[dict]:
    return [public(m) for m in load_models(path)]


def get_model(model_id: str, path: Path | None = None) -> dict | None:
    return next((m for m in load_models(path) if m["id"] == model_id), None)
