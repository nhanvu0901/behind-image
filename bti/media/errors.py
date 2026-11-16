"""Shared exceptions for bti.media."""


class MediaError(RuntimeError):
    """Base class."""


class LicenceRejected(MediaError):
    """The licence gate refused this item. `str(exc)` is the human-readable reason."""

    def __init__(self, reason: str, licence: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.licence = licence


class ImageTooSmall(MediaError):
    """Short side below the configured minimum."""


class NotFound(MediaError):
    """The source has no such item."""
