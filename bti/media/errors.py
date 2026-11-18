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


class RealModelsOff(MediaError, ValueError):
    """A real request or program was about to start while `BTI_NO_REAL_MODELS=1` (the A7 safety switch).

    Raised by `bti.media.safety.refuse_if_real_models_off`, at the point where a request or a program would really start.
    A ValueError with a `code`, like `VideoDamaged` and `FileTooLarge`: that is the shape both HTTP layers
    (`bti.picks.service._translate`, `bti.editor.media_adapter._translate`) already turn into an error with that code."""

    code = "real_models_off"
    kind = "real_models_off"

    def __init__(self, what: str = ""):
        super().__init__("real requests and programs are disabled (BTI_NO_REAL_MODELS=1)" + (f": {what}" if what else ""))
