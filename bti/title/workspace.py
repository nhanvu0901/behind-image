"""The agent's work folder for the title job: a new folder in the system temp directory that holds COPIES only.

    TASK.md                   the instructions (skills/title/TASK.template.md, rendered: the limits and the refused phrases come from `rules.py`)
    check (check.cmd)         the one helper command, a one-line wrapper around `python -m bti.title.helper check`
    inputs/context.json       what `check` validates against (do not edit): the narration lines by id
    inputs/narration.json     the approved narration, chapter by chapter, line by line (the ids a candidate cites)
    inputs/outline.json       the outline's thesis and the opening hook it chose, the chapters' roles and purposes
    inputs/painting.json      the painting's title, painter and year
    out/                      what the agent writes: title.json. Only this is read back.

The project folder and the repository are never inside it. The session itself is `bti.picks.auto.session.run_session` (the runners of the storyboard draft: the
same command lines, the same confinement, one repair round)."""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from bti.picks.auto.workspace import render

from . import rules as R
from .inputs import Inputs
from .store import TitleError

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "title"
TEMPLATE = "TASK.template.md"
IS_WINDOWS = os.name == "nt"
PREFIX = "bti-title-"
HELPER_MODULE = "bti.title.helper"
OUT_FILE = "title.json"


@dataclass
class Workspace:
    root: Path


def clean_old(max_age_s: float = 2 * 86400) -> int:
    """Remove work folders of earlier runs that are older than `max_age_s` (only folders this module made: its own name prefix)."""
    n = 0
    for d in Path(tempfile.gettempdir()).glob(PREFIX + "*"):
        try:
            if d.is_dir() and not d.is_symlink() and time.time() - d.stat().st_mtime > max_age_s:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        except OSError:
            continue
    return n


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _json(path: Path, obj) -> None:
    _write(path, json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def wrapper(root: Path, python: str, repo: Path) -> str:
    """`check`: a one-line wrapper, so that the agent runs `./check` and nothing else. -> the command to type."""
    if IS_WINDOWS:
        f = Path(root) / "check.cmd"
        _write(f, '@echo off\r\nset "PYTHONPATH=%s"\r\nset PYTHONUTF8=1\r\n"%s" -m %s check %%*\r\n' % (repo, python, HELPER_MODULE))
        return ".\\check.cmd"
    f = Path(root) / "check"
    _write(f, "#!/bin/sh\nPYTHONPATH='%s' PYTHONUTF8=1 exec '%s' -m %s check \"$@\"\n" % (str(repo).replace("'", "'\\''"), python.replace("'", "'\\''"), HELPER_MODULE))
    f.chmod(f.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return "./check"


def values(inp: Inputs, check_cmd: str, limits) -> dict:
    """Every placeholder of the template: the project's own, then the rules' (one place)."""
    p = inp.identity
    return {"CHECK_CMD": check_cmd, "CHANNEL": inp.channel, "TITLE": p.get("title") or "(no title)", "ARTIST": p.get("artist") or "(unknown)",
            "YEAR": p.get("year") or "(unknown)", "N_LINES": inp.n_lines, "N_CHAPTERS": inp.n_chapters, "MAX_MINUTES": int(limits.minutes),
            "MAX_STEPS": int(limits.steps), "OWNER_NOTE": inp.owner_note, **R.template_values()}


def template_text(template: Path | None = None) -> str:
    f = Path(template or (SKILL_DIR / TEMPLATE))
    if not f.is_file():
        raise TitleError("template_missing", "skills/title/%s is missing" % TEMPLATE, 500)
    return f.read_text(encoding="utf-8")


def build(inp: Inputs, limits, *, root: Path | None = None, template: Path | None = None, python: str | None = None) -> Workspace:
    """The folder of one session."""
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix=PREFIX))
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("inputs", "out"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    cmd = wrapper(root, python or sys.executable, REPO_ROOT)
    _json(root / "inputs" / "context.json", {"mode": "title", "lines": inp.lines})
    _json(root / "inputs" / "narration.json", {"note": "Every line has an id: a candidate cites the ids of the lines that make it true.", "language": inp.language,
                                              "chapters": [{"id": c["id"], "title": c["title"], "role": c["role"], "lines": c["lines"]} for c in inp.chapters]})
    _json(root / "inputs" / "outline.json", {"note": "Context only: a title is true to the narration, not to this file.", **inp.outline})
    _json(root / "inputs" / "painting.json", {"title": inp.identity.get("title"), "artist": inp.identity.get("artist"), "year": inp.identity.get("year"),
                                             "channel": inp.channel})
    _write(root / "TASK.md", render(template_text(template), values(inp, cmd, limits)))
    return Workspace(root=root)
