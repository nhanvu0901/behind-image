"""Tamper detection for the unattended agent run (design 7.3): the project folder is listed (names, sizes, times) before and after the
run and the two listings are compared; on the server `git status --short` of the comic repository is compared as well.
Any difference marks the run `tampered`. It does not prevent a determined mistake; it makes one visible at once.

Ignored: `cache/`, `history/` and `proposals/` of the project (the app itself writes there while the run goes on: job records,
previews, backups) and temporary files of atomic writes. A storyboard saved in the page during the run IS a difference."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bti.proc import group_kwargs

IGNORE_TOP = ("cache", "history", "proposals")
REPO_ROOT = Path(__file__).resolve().parents[2]


def snapshot_dir(root: Path, ignore_top: tuple = IGNORE_TOP) -> dict:
    """relative path (with /) -> [size, mtime_ns] for every file under `root`, minus the ignored top folders."""
    root = Path(root)
    out: dict = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if rel_dir == Path("."):
            dirnames[:] = [d for d in dirnames if d not in ignore_top]
        for name in filenames:
            if name.endswith(".tmp"):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            out[(rel_dir / name).as_posix()] = [st.st_size, st.st_mtime_ns]
    return out


def diff(before: dict, after: dict) -> list[str]:
    """Human readable differences: `added x`, `removed x`, `changed x`."""
    out = []
    for k in sorted(set(before) | set(after)):
        if k not in before:
            out.append("added " + k)
        elif k not in after:
            out.append("removed " + k)
        elif before[k] != after[k]:
            out.append("changed " + k)
    return out


def comic_repo_status() -> str | None:
    """`git status --short` of the comic repository when `config/server.json` names it (key `comic_repo` of this platform's block);
    None when it is not configured or git cannot answer."""
    try:
        cfg = json.loads((REPO_ROOT / "config" / "server.json").read_text(encoding="utf-8"))
        block = cfg.get("windows" if os.name == "nt" else "default") or {}
        repo = block.get("comic_repo")
        if not repo or not Path(repo).is_dir():
            return None
        r = subprocess.run(["git", "-C", str(repo), "status", "--short"], capture_output=True, text=True, timeout=30, encoding="utf-8",
                           errors="replace", **group_kwargs())
        return r.stdout if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class Guard:
    """before() then after(): the list of differences (empty = nothing changed)."""

    def __init__(self, project_dir: Path, extra=None):
        self.project_dir = Path(project_dir)
        self.extra = extra if extra is not None else comic_repo_status
        self._before = None

    def before(self) -> None:
        self._before = {"files": snapshot_dir(self.project_dir), "extra": self.extra() if self.extra else None}

    def after(self) -> list[str]:
        if self._before is None:
            return []
        now = {"files": snapshot_dir(self.project_dir), "extra": self.extra() if self.extra else None}
        out = diff(self._before["files"], now["files"])
        if self._before["extra"] != now["extra"]:
            out.append("changed the comic repository (git status differs)")
        return out
