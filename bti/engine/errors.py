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
