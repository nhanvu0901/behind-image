"""Project stages added by the script step: `outlined` (outline approved) and `script` (narration approved)."""
from __future__ import annotations

from pathlib import Path

from .store import load_narration, load_outline

ORDER = ["selected", "outlined", "script", "voiced", "storyboard", "approved", "rendered"]


def script_stage(pdir: Path) -> str | None:
    try:
        n = load_narration(pdir)
        if n is not None and n.approved_fresh():
            return "script"
        o = load_outline(pdir)
        if o is not None and o.approved_fresh():
            return "outlined"
    except (OSError, ValueError):
        pass
    return None


def bump_stage(inferred: str, pdir: Path) -> str:
    """The later of the stage inferred from the files and the stage given by approved script files."""
    mine = script_stage(pdir)
    if mine and ORDER.index(mine) > (ORDER.index(inferred) if inferred in ORDER else 0):
        return mine
    return inferred
