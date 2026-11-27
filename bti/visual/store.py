"""Revision-checked storage for visual.json; callers validate before saving."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from bti.script import store as common


def revision(document: dict) -> str:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def load(project: Path) -> dict | None:
    return common.read_object(Path(project) / "visual.json", "visual")


def save(project: Path, document: dict, *, base_rev: str | None, actor: str | None = None) -> str:
    """Save exactly the supplied document, preserving a prior version in history."""
    project = Path(project)
    with common.script_lock(project):
        if not project.is_dir():
            raise common.ProjectGone("project is gone")
        previous = load(project)
        current_rev = revision(previous) if previous is not None else None
        if current_rev != base_rev:
            raise common.StaleRevision("visual revision changed")
        if previous is not None and previous != document:
            history = project / "history"
            history.mkdir(exist_ok=True)
            common.write_json_atomic(history / f"visual_{time.time_ns()}.json", previous)
        common.write_json_atomic(project / "visual.json", document, levels=0)
        rev = revision(document)
        if actor and current_rev != rev:
            history = project / "history"
            history.mkdir(exist_ok=True)
            common.write_json_atomic(history / f"visual_change_{time.time_ns()}.json", {"actor": actor, "before": current_rev, "after": rev})
        return rev
