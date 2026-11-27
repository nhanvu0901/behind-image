"""Where the output folder is and what its parts are called.

    <data root>/projects/<project id>/      the working folder of a project (the app works in it)
    <data root>/output/<artwork key>/       the folder a person reads (this package fills it)

The output root is `BTI_OUTPUT_ROOT` when that is set, else `output/` beside the projects folder, the way the projects root itself is configured
(`BTI_PROJECTS_ROOT`). `output_root_for` answers None ("no output folder on this app") when the app was given an explicit projects folder and no output
folder: that is what the tests of the other stages do, so they never write an `output/` next to their temporary projects."""
from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

ENV_ROOT = "BTI_OUTPUT_ROOT"
KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}")
FINAL_VIDEO = "final.mp4"
STATE_FILE = "state.json"
README_FILE = "README.md"
INDEX_JSON = "index.json"
INDEX_MD = "INDEX.md"

# the seven numbered parts, in the order of the pipeline, and the log
PARTS = {"sources": "1_sources", "script": "2_script", "voice": "3_voice", "pictures": "4_pictures", "storyboard": "5_storyboard", "export": "6_export", "quality": "7_quality"}
LOG_DIR = "log"


def output_root_for(projects_root: Path | str, explicit: Path | str | bool | None = None, *, projects_root_given: bool = False) -> Path | None:
    """The output root of an app, or None when it has none. `explicit`: a path (use it), False (no output folder), None (decide: the environment, else beside the projects
    folder unless the caller gave the projects folder explicitly)."""
    if explicit is False:
        return None
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get(ENV_ROOT)
    if env:
        return Path(env).resolve()
    if projects_root_given:
        return None
    return Path(projects_root).resolve().parent / "output"


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:100].strip("-")


def folder_key(meta: dict, pid: str) -> str:
    """The folder of a project: its library artwork key, else its project id. Always one safe path segment."""
    for cand in (meta.get("artwork_key") if isinstance(meta, dict) else None, pid):
        if isinstance(cand, str) and KEY_RE.fullmatch(cand) and ".." not in cand and not cand.endswith("."):
            return cand
        s = slug(cand) if isinstance(cand, str) else ""
        if s:
            return s
    return "project"


def folder_of(output_root: Path, key: str) -> Path:
    return Path(output_root) / key
