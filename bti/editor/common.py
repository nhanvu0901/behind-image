"""Shared helpers: id validation, safe paths, atomic JSON, revisions.

Atomic JSON write and corrupt-file quarantine follow the pattern of the comic
pipeline (utils/atomic_json.py and ui/bridge.py::_quarantine_corrupt), rewritten
here; nothing is imported from that repo.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
STYLE_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
ITEM_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
SCHEMA = "bti.storyboard/1"

REPO_ROOT = Path(__file__).resolve().parents[2]


class ApiError(Exception):
    """Error carried to the client as JSON `{detail, ...extra}`."""

    def __init__(self, status: int, detail: str, **extra: Any):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = extra


def valid_pid(pid: str) -> bool:
    return isinstance(pid, str) and PID_RE.fullmatch(pid) is not None


def safe_join(root: Path, rel: str) -> Path:
    """Resolve `rel` under `root`; raise ApiError(404) when it escapes."""
    if not isinstance(rel, str) or not rel or "\x00" in rel or "\\" in rel:
        raise ApiError(404, "not found")
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise ApiError(404, "not found")
    parts = rel.split("/")
    if any(p in ("..", "") for p in parts):
        raise ApiError(404, "not found")
    root_r = root.resolve()
    target = (root_r / rel).resolve()
    try:
        target.relative_to(root_r)
    except ValueError:
        raise ApiError(404, "not found")
    return target


def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def quarantine(path: Path) -> Path | None:
    """Move a corrupt file aside so it is not re-read; returns the new path."""
    try:
        dest = path.with_name(f"{path.name}.corrupt-{int(time.time())}")
        os.replace(path, dest)
        return dest
    except OSError:
        return None


def strip_derived(obj: Any) -> Any:
    """Deep copy without keys that start with `_`."""
    if isinstance(obj, dict):
        return {k: strip_derived(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, list):
        return [strip_derived(v) for v in obj]
    return copy.deepcopy(obj)


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_rev(storyboard: dict) -> str:
    """sha256 of the canonical JSON, without `_` keys and without `approvals`
    (approving must not change the revision it approves)."""
    doc = strip_derived(storyboard)
    doc.pop("approvals", None)
    return hashlib.sha256(canonical(doc).encode("utf-8")).hexdigest()


def file_signature(path: Path) -> str:
    st = path.stat()
    return hashlib.sha1(f"{path.name}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:16]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
