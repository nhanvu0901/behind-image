"""Tamper detection for the unattended agent run (design 7.3): what the agent has no reason to touch is listed before and after the
run (names, sizes, times) and compared. Any difference marks the run `tampered`; nothing is taken from it.

Watched:
  (a) on the server, `git status --short` of the comic repository (`comic_repo` of this platform's block in config/server.json;
      the check is skipped when the key is absent);
  (b) the repository's own `bti/`, `style/`, `config/`, `prompts/` and `skills/` folders (any added, removed or changed file;
      `__pycache__` is ignored): the agent has no reason to touch code;
  (c) inside the project: the files that existed before the run under `media/`, `audio/` and `source/`, plus `timing.json` and
      `project.json`. A change or a deletion of one of those is tampering. New files, and everything the app writes in normal use
      (`storyboard.json`, `picks.json`, `cache/`, `history/`, `proposals/`, `script/`, `voice/`, `export/`), are not looked at, so
      the owner saving or uploading during a run is not flagged."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from bti.proc import group_kwargs

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_DIRS = ("bti", "style", "config", "prompts", "skills")
PROJECT_DIRS = ("media", "audio", "source")
PROJECT_FILES = ("timing.json", "project.json")


def snapshot_dir(root: Path, only_top: tuple | None = None, skip_names: tuple = ("__pycache__",)) -> dict:
    """relative path (with /) -> [size, mtime_ns] for every file under `root` (limited to the top folders in `only_top`)."""
    root = Path(root)
    out: dict = {}
    if not root.is_dir():
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if d not in skip_names]
        if rel_dir == Path(".") and only_top is not None:
            dirnames[:] = [d for d in dirnames if d in only_top]
            filenames = []
        for name in filenames:
            if name.endswith((".tmp", ".pyc")):
                continue
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            out[(rel_dir / name).as_posix()] = [st.st_size, st.st_mtime_ns]
    return out


def project_snapshot(project_dir: Path) -> dict:
    """The watched files of a project (see the module docstring, (c))."""
    project_dir = Path(project_dir)
    snap = snapshot_dir(project_dir, only_top=PROJECT_DIRS)
    for name in PROJECT_FILES:
        p = project_dir / name
        try:
            st = p.stat()
            snap[name] = [st.st_size, st.st_mtime_ns]
        except OSError:
            pass
    return snap


def repo_snapshot(repo_root: Path, dirs: tuple = REPO_DIRS) -> dict:
    out: dict = {}
    for d in dirs:
        for k, v in snapshot_dir(Path(repo_root) / d).items():
            out["%s/%s" % (d, k)] = v
    return out


def diff(before: dict, after: dict, ignore_added: bool = False) -> list[str]:
    """Human readable differences: `added x`, `removed x`, `changed x` (`added` is left out with `ignore_added`)."""
    out = []
    for k in sorted(set(before) | set(after)):
        if k not in before:
            if not ignore_added:
                out.append("added " + k)
        elif k not in after:
            out.append("removed " + k)
        elif before[k] != after[k]:
            out.append("changed " + k)
    return out


def comic_repo_status() -> str | None:
    """`git status --short` of the comic repository when `config/server.json` names it (`comic_repo`, read through `bti.longjob.load_config()`);
    None when it is not configured or git cannot answer."""
    try:
        from bti.longjob.config import load as load_config
        repo = load_config().comic_repo
        if not repo or not Path(repo).is_dir():
            return None
        r = subprocess.run(["git", "-C", str(repo), "status", "--short"], capture_output=True, text=True, timeout=30, encoding="utf-8",
                           errors="replace", **group_kwargs())
        return r.stdout if r.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


class Guard:
    """before() then after(): the list of differences (empty = nothing the agent should not touch has changed)."""

    def __init__(self, project_dir: Path, extra=None, repo_root: Path | None = None):
        self.project_dir = Path(project_dir)
        self.repo_root = Path(repo_root) if repo_root is not None else REPO_ROOT
        self.extra = extra if extra is not None else comic_repo_status
        self._before = None

    def _now(self) -> dict:
        return {"project": project_snapshot(self.project_dir), "repo": repo_snapshot(self.repo_root),
                "extra": self.extra() if self.extra else None}

    def before(self) -> None:
        self._before = self._now()

    def after(self) -> list[str]:
        if self._before is None:
            return []
        now = self._now()
        out = diff(self._before["project"], now["project"], ignore_added=True)
        out += ["repository " + x for x in diff(self._before["repo"], now["repo"])]
        if self._before["extra"] != now["extra"]:
            out.append("changed the comic repository (git status differs)")
        return out
