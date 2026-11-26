"""The local, independently licensed recording library."""
from __future__ import annotations

import json
from pathlib import Path

from bti import settings
from bti.script.brief import REPO_ROOT
from bti.script.store import write_json_atomic


def directory():
    value = settings.load_user_settings().get("music_dir")
    return Path(value).expanduser() if isinstance(value, str) and value.strip() else REPO_ROOT / "music"


def read(path=None):
    index = Path(path or directory()) / "library.json"
    if not index.exists():
        return []
    raw = json.loads(index.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("music library must be a list")
    if any(not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in raw):
        raise ValueError("invalid recording in music library")
    if len({r["id"] for r in raw}) != len(raw):
        raise ValueError("duplicate recording id")
    return raw


def index(path=None):
    return {r["id"]: r for r in read(path)}


def write(rows, path=None):
    root = Path(path or directory())
    root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(root / "library.json", rows)
