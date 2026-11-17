"""Errors that say "the project's DATA is unusable" (as opposed to a bug).

The editor backend turns a `DataError` into a 4xx JSON answer that names the problem; anything else is a server bug.
"""
from __future__ import annotations


class DataError(Exception):
    """A document the engine needs (storyboard.json, timing, style) is missing, unreadable or malformed."""

    def __init__(self, message: str, *, what: str = "data"):
        super().__init__(message)
        self.message, self.what = message, what


class StyleError(DataError, FileNotFoundError):
    """Unknown or unreadable style id (a FileNotFoundError too, which older callers catch)."""

    def __init__(self, message: str):
        DataError.__init__(self, message, what="style")
        self.args = (message,)


class RenderError(DataError):
    """A technique failed while drawing because of the storyboard's values (not an engine bug).

    `shot` / `overlay` / `technique` name where it happened (`None` when unknown); `path` is the storyboard path of the failing
    item (`shots[3]`, `shots[3].overlays[1]`, `shots[3].transition_in`) when the engine can tell.
    """

    def __init__(self, message: str, *, shot: str | None = None, overlay: str | None = None, technique: str | None = None,
                 path: str | None = None):
        super().__init__(message, what="render")
        self.shot, self.overlay, self.technique, self.path = shot, overlay, technique, path
