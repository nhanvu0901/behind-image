"""A small loader for this project's own `.env` (never the comic repo's). Nothing here prints or returns a value
except `get_key`, which hands it to a provider. Values are never put into os.environ, logs or API responses."""
from __future__ import annotations

import os
from pathlib import Path

from .brief import REPO_ROOT

# The .env may be shared with other projects (the comic pipeline). Only these names are ever read from it.
ALLOWED = ("OPENROUTER_API_KEY", "YDC_API_KEY", "GEMINI_API_KEY")
_cache: dict[str, tuple[float, dict]] = {}


def env_path() -> Path:
    return Path(os.environ.get("BTI_ENV_FILE") or REPO_ROOT / ".env")


def parse_env(text: str, only: tuple[str, ...] | None = ALLOWED) -> dict[str, str]:
    """KEY=VALUE lines; with `only` (the default) every other line is ignored, not even kept in memory."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif " #" in v:
            v = v.split(" #", 1)[0].rstrip()
        if k and (only is None or k in only):
            out[k] = v
    return out


def _dotenv() -> dict[str, str]:
    p = env_path()
    try:
        mt = p.stat().st_mtime
    except OSError:
        return {}
    hit = _cache.get(str(p))
    if hit and hit[0] == mt:
        return hit[1]
    try:
        d = parse_env(p.read_text(encoding="utf-8"))
    except OSError:
        d = {}
    _cache[str(p)] = (mt, d)
    return d


def get_key(name: str | None) -> str | None:
    """The key named `name` from the process environment, else from this project's .env; None when unset or empty."""
    if not name:
        return None
    v = os.environ.get(name) or _dotenv().get(name)
    return v or None


def has_key(name: str | None) -> bool:
    return bool(get_key(name))


def redact(text: str, *names: str) -> str:
    """Remove any configured key value from a message before it is logged or returned."""
    for n in names:
        k = get_key(n)
        if k and len(k) >= 6:
            text = text.replace(k, "***")
    return text
