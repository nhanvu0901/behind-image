"""Project stages added by the script step: `outlined` (outline approved) and `script` (narration approved)."""
from __future__ import annotations

from pathlib import Path

from .store import DocumentCorrupt, load_narration, load_outline, narration_approval

ORDER = ["selected", "outlined", "script", "voiced", "storyboard", "approved", "rendered"]


def script_stage(pdir: Path) -> str | None:
    try:
        n, o = load_narration(pdir), load_outline(pdir)
        if n is not None and narration_approval(n, o)["approved"]:
            return "script"          # the narration approval counts only against the outline it was approved with
        if o is not None and o.approved_fresh():
            return "outlined"
    except (OSError, ValueError, DocumentCorrupt):
        pass
    return None


def bump_stage(inferred: str, pdir: Path) -> str:
    """The later of the stage inferred from the files and the stage given by approved script files."""
    mine = script_stage(pdir)
    if mine and ORDER.index(mine) > (ORDER.index(inferred) if inferred in ORDER else 0):
        return mine
    return inferred
