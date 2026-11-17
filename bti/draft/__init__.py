"""The storyboard draft: from the timed narration and the owner's picks to a proposal the owner reviews in step 5.

The model (or the no-model `auto` drafter) writes a short shot list per chapter (`bti.draft/1`, see `spec.py`); fixed code
(`compile.py`) turns it into a full `bti.storyboard/1` document. Only two things are exposed to the rest of the app:
`router` (in `bti/editor/draft_api.py`) and `state(project_dir)`."""
from __future__ import annotations


def state(project_dir) -> dict:
    """{"state": "none|running|stale|done", "detail": str, ...}. Imported lazily so that `import bti.draft` stays light."""
    from .run import state as _state
    return _state(project_dir)
