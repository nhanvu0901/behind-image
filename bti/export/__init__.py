"""Step 6: export. From an approved storyboard, the audio mix and the timing to the finished MP4, chapter metadata, video description and report card.

The rest of the app sees exactly two things (design 2026-11-16, section 3): `bti.editor.export_api.router` and `state()`.
"""
from __future__ import annotations


def state(project_dir):
    """`{"state": "none|running|stale|done", "detail": str, ...}`; cheap (no ffprobe, no engine)."""
    from .run import state as _state
    return _state(project_dir)


__all__ = ["state"]
