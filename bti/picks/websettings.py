"""The owner's standing permission for the web search of the automatic picks job ("Tìm hình trên web khi chọn hình tự động").

The switch has three layers, the last one that says something wins:

    code           off, 80 searches a run                                   (so every existing test and project behaves as before)
    config         `config/picks.json`: {"auto_web_search": "off" | "on", "auto_web_search_max": 80}   (tracked; the machine's default)
    the owner's    `run/settings.json`, block `picks`: the same two keys    (`PUT /api/settings/web-search`; git-ignored, kept by a deploy)

With the switch ON, `picks.auto` may be started by an agent and by the automatic run exactly as without it (the switch IS the owner's permission
for this one paid thing; its cost line says "up to N web searches"). With it OFF nothing paid is ever called. The searches themselves
(`bti.picks.auto.search`, `bti.picks.auto.webround`) count against `auto_web_search_max` for one run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bti import settings as S

REPO_ROOT = Path(__file__).resolve().parents[2]
MODES = ("off", "on")
DEFAULT_MODE = "off"
DEFAULT_MAX = 80
MAX_CEILING = 500


def _config() -> dict:
    try:
        d = json.loads((REPO_ROOT / "config" / "picks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _mode(v: Any) -> str | None:
    if v is True:
        return "on"
    if v is False:
        return "off"
    return v if v in MODES else None


def _max(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= MAX_CEILING else None


def settings() -> dict:
    """`{"auto_web_search": "off" | "on", "auto_web_search_max": int, "source": "default" | "config" | "owner"}` (what the next run will use)."""
    mode, mx, source = DEFAULT_MODE, DEFAULT_MAX, "default"
    cfg = _config()
    if _mode(cfg.get("auto_web_search")) is not None or _max(cfg.get("auto_web_search_max")) is not None:
        mode, mx, source = _mode(cfg.get("auto_web_search")) or mode, _max(cfg.get("auto_web_search_max")) or mx, "config"
    own = S.get_picks_block()
    if _mode(own.get("auto_web_search")) is not None or _max(own.get("auto_web_search_max")) is not None:
        mode, mx, source = _mode(own.get("auto_web_search")) or mode, _max(own.get("auto_web_search_max")) or mx, "owner"
    return {"auto_web_search": mode, "auto_web_search_max": mx, "source": source}


def enabled() -> bool:
    return settings()["auto_web_search"] == "on"


def max_searches() -> int:
    return settings()["auto_web_search_max"]


def for_run() -> dict:
    """`{"on": bool, "max": int}`: what a run that starts now is allowed."""
    s = settings()
    return {"on": s["auto_web_search"] == "on", "max": s["auto_web_search_max"]}


def save(mode: Any = None, max_n: Any = None) -> dict:
    """The owner's choice. `mode`: "on" | "off" (or true | false); `max_n`: a whole number 1..500; a value left as None stays. Raises
    `bti.settings.SettingsError` (`invalid_payload`) for anything else, writing nothing. Returns `settings()`."""
    updates: dict = {}
    if mode is not None:
        m = _mode(mode)
        if m is None:
            raise S.SettingsError("invalid_payload", "auto_web_search must be \"on\" or \"off\"", 422)
        updates["auto_web_search"] = m
    if max_n is not None:
        if _max(max_n) is None:
            raise S.SettingsError("invalid_payload", "auto_web_search_max must be a whole number from 1 to %d" % MAX_CEILING, 422)
        updates["auto_web_search_max"] = max_n
    if not updates:
        raise S.SettingsError("invalid_payload", "auto_web_search (\"on\" or \"off\") or auto_web_search_max (a number) is required", 422)
    S.set_picks_block(updates)
    return settings()
