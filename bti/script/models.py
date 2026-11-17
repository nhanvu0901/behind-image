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
FAIL_SECONDS = 60
_cache: dict = {"at": 0.0, "ttl": 0, "rows": None, "error": None, "kind": None}
_lock = threading.Lock()
_flight: threading.Event | None = None


def models_path() -> Path:
    return Path(os.environ.get("BTI_MODELS_FILE") or REPO_ROOT / "config" / "models.json")


def reset_cache() -> None:
    _cache.update({"at": 0.0, "ttl": 0, "rows": None, "error": None, "kind": None})


def _cached():
    """(fresh, rows, error) of the cache; never calls the CLI."""
    with _lock:
        fresh = time.time() - _cache["at"] < _cache["ttl"]
        return fresh, _cache["rows"], _cache["error"]


def agy_models(refresh: bool = False) -> tuple[list[dict] | None, str | None]:
    """-> (rows, None) or (None, message). Cached 10 minutes in this process (1 minute after a failure); `refresh` forces a
    new call. NO lock is held while the CLI runs (the lock only guards the cache): two requests at once start ONE `agy models`,
    the second waits for its answer without holding anything. Whatever goes wrong (garbage bytes, no program, time-out, any
    exception) is a failure answer that is cached for a minute; it never raises."""
    from .providers import ProviderError
    from .providers import antigravity
    global _flight
    while True:
        with _lock:
            if not refresh and time.time() - _cache["at"] < _cache["ttl"]:
                return _cache["rows"], _cache["error"]
            flight = _flight
            if flight is None:
                flight = _flight = threading.Event()
                leader = True
            else:
                leader = False
        if not leader:
            flight.wait(timeout=antigravity.LIST_TIMEOUT_S + 5)
            with _lock:
                if _flight is flight:
                    _flight = None          # the leader died without answering: take over
                    flight.set()
                    continue
                if _cache["at"]:
                    return _cache["rows"], _cache["error"]
            continue
        try:
            try:
                rows, err, ttl, kind = antigravity.list_models(), None, CACHE_SECONDS, None
            except ProviderError as e:
                rows, err, ttl, kind = None, e.message, FAIL_SECONDS, e.kind
            except Exception as e:      # noqa: BLE001 - the list can never break a request
                rows, err, ttl, kind = None, "`agy models` cho kết quả không đọc được.", FAIL_SECONDS, "http"
            with _lock:
                _cache.update({"at": time.time(), "ttl": ttl, "rows": rows, "error": err, "kind": kind})
        finally:
            with _lock:
                _flight = None
            flight.set()
        return rows, err


def load_raw(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else models_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [m for m in raw if isinstance(m, dict) and m.get("id") and m.get("provider") in PROVIDERS] if isinstance(raw, list) else []


def load_models(path: Path | None = None, refresh: bool = False) -> list[dict]:
    """Specs ready for the providers. An unavailable agy gives one entry with `unavailable` set to the message."""
    out = []
    for m in load_raw(path):
        if m["provider"] != "antigravity":
            out.append(m)
            continue
        rows, err = agy_models(refresh)
        if rows is None:
            out.append({**m, "id": m["id"], "unavailable": err, "unavailable_kind": _cache.get("kind"), "model": None})
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
    extra = ({"agy": {"ok": not m.get("unavailable"), "reason": m.get("unavailable_kind") if m.get("unavailable") else None}}
             if m["provider"] == "antigravity" else {})
    return {**extra, "id": m["id"], "label": m.get("label") or m["id"], "provider": m["provider"], "model": m.get("model"),
            "default": bool(m.get("default")), "enabled": ok, "missing_env": None if ok or m.get("unavailable") else env,
            "message": why, "paid": m["provider"] in ("openrouter", "gemini")}


def public_models(path: Path | None = None, refresh: bool = False) -> list[dict]:
    return [public(m) for m in load_models(path, refresh)]


def resolve(model_id: str, path: Path | None = None) -> dict | None:
    """The spec of ONE model id, as `load_models` would list it, without running the CLI for a model that is not an
    Antigravity one. For `<antigravity id>:<slug>` the slug is checked against the cached list while that is fresh; with no
    fresh list the spec is built from the slug and a wrong slug fails when the job runs (with the CLI's own message)."""
    raw = load_raw(path)
    for m in raw:
        if m["provider"] != "antigravity" and m["id"] == model_id:
            return m
    for m in raw:
        if m["provider"] != "antigravity":
            continue
        if model_id == m["id"]:                      # the unexpanded entry exists only while the list is unavailable
            fresh, rows, err = _cached()
            if fresh and rows is None and err:
                return {**m, "unavailable": err, "unavailable_kind": _cache.get("kind"), "model": None}
            return None
        pre = m["id"] + ":"
        if model_id.startswith(pre) and len(model_id) > len(pre):
            slug = model_id[len(pre):]
            fresh, rows, err = _cached()
            if fresh and rows is not None:
                row = next((r for r in rows if r["slug"] == slug), None)
                if row is None:
                    return None
                i = rows.index(row)
                return {**m, "id": model_id, "model": slug, "label": f"{m.get('label') or 'Antigravity CLI'}: {row['label']}",
                        "default": bool(m.get("default")) and i == 0, "key_env": None}
            if fresh and rows is None and err:
                return {**m, "id": m["id"], "unavailable": err, "unavailable_kind": _cache.get("kind"), "model": None}
            return {**m, "id": model_id, "model": slug, "label": f"{m.get('label') or 'Antigravity CLI'}: {slug}",
                    "default": False, "key_env": None}
    return None


def get_model(model_id: str, path: Path | None = None) -> dict | None:
    return resolve(model_id, path)
