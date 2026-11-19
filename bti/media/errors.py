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


class MapPlaceUnknown(MediaError, ValueError):
    """A map was asked for with a source id that does not say where it is (no usable coordinates). The map is never drawn for a
    guessed place: this is the error instead. A ValueError with a `code`, the shape both HTTP layers already turn into a 422 with
    that code (the page's sentence for it is in `errmsg.js`)."""

    code = "map_place_unknown"

    def __init__(self, what: str = ""):
        super().__init__("the map has no known place" + (f": {what}" if what else "") + "; search for the place again and pick it again")
