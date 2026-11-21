"""The channel identity ("Raking Light"): the opening, the channel-name beat and the chapter marks of a video, in one of the styles
the `identity` block of style.json lists. Contract: docs/design/2026-11-18-identity-raking-light.md.

    from bti.identity import apply_identity, options, chosen_style
"""
from __future__ import annotations

from .apply import REASONS, apply_identity, fit_camera_to_box, with_video_title
from .config import IdentityConfig, IdentityError, StyleDef, is_mismatch, need, options, read

__all__ = ["apply_identity", "fit_camera_to_box", "with_video_title", "video_title_of", "REASONS", "IdentityConfig", "IdentityError", "StyleDef", "is_mismatch", "need", "options", "read", "chosen_style"]


def chosen_style(storyboard, style) -> str | None:
    """The style a storyboard was given (`identity.style`) when the style.json still lists it, else None (the old look)."""
    ident = storyboard.get("identity") if isinstance(storyboard, dict) else None
    sid = ident.get("style") if isinstance(ident, dict) else None
    cfg = read(style)
    return sid if cfg is not None and isinstance(sid, str) and cfg.style(sid) is not None else None


def video_title_of(storyboard) -> str | None:
    """The video's own title (`identity.video_title`), None when there is none."""
    ident = storyboard.get("identity") if isinstance(storyboard, dict) else None
    v = ident.get("video_title") if isinstance(ident, dict) else None
    return v if isinstance(v, str) and v.strip() else None
