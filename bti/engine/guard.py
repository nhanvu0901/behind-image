"""A hard limit on the size of any picture buffer whose size comes from storyboard values (R2B-017).

One bad value (a `frame_aspect` of "0:1": a panel 2 px wide, so a blurred ambient fill 1 million rows tall) once made the engine
allocate 24 GB.  The registry now bounds every parameter that sets a size, but a combination of in-range values can still ask for
an absurd buffer, so every resize and warp goes through `check_pixels` (cv2.resize, cv2.warpAffine and cv2.warpPerspective are
wrapped once, here, and checked only while a frame is being drawn: `with guard.limited():`) and the shared helpers that make buffers call it directly.  A request over the limit raises `BufferTooLarge`;
the scene turns it into a `RenderError` that names the shot.

The limit is 64 megapixels (a float32 BGR buffer of that size is about 770 MB). It comes from measurement (R2B-018): drawing every
shot of `projects/arnolfini` and `projects/technique_lab` at start, middle and end, every overlay, and every number param of every
technique at its registry min and max, the largest request that depends on the storyboard was 15.4 MP (an anti-aliasing mask at
the registry maximum), the usual maximum 6.6 MP (the blurred ambient fill of a 9:16 short), so 64 MP leaves more than 4x head-room.
The 24 GB case asked for 1920 x 1 036 800 = 2000 MP and is still refused. The size of a source image is not storyboard-driven (a
scan can be 100 MP): building its pyramid runs under `unlimited()`.
"""
from __future__ import annotations

import threading

import cv2


MAX_PIXELS = 64_000_000


class BufferTooLarge(ValueError):
    pass


_state = threading.local()


class limited:
    """Context manager: inside it (in this thread) every cv2.resize / warp is checked. Outside it OpenCV behaves as usual, so
    code that is not drawing a frame (media import, thumbnails, tools) is never limited."""

    def __enter__(self):
        _state.depth = getattr(_state, "depth", 0) + 1

    def __exit__(self, *exc):
        _state.depth -= 1


class unlimited:
    """Context manager: switches the check off for work whose size comes from a file, not from the storyboard (source pyramids)."""

    def __enter__(self):
        self._saved = getattr(_state, "depth", 0)
        _state.depth = 0

    def __exit__(self, *exc):
        _state.depth = self._saved


def active() -> bool:
    return getattr(_state, "depth", 0) > 0


def check_pixels(w, h, what: str = "picture buffer") -> None:
    """Raise BufferTooLarge when a w x h buffer would be over the limit (also for sizes that are not finite or negative)."""
    try:
        n = float(w) * float(h)
    except (TypeError, ValueError):
        raise BufferTooLarge("%s has an invalid size %r x %r" % (what, w, h))
    if not (n == n) or n > MAX_PIXELS:
        raise BufferTooLarge("a %s of %s x %s px is larger than the engine allows (%d px)" % (what, w, h, MAX_PIXELS))


_installed = False


def install() -> None:
    """Wrap the OpenCV calls that create a buffer of a requested size. Idempotent."""
    global _installed
    if _installed:
        return
    _installed = True
    orig_resize, orig_aff, orig_persp = cv2.resize, cv2.warpAffine, cv2.warpPerspective

    def resize(src, dsize=None, *a, **kw):
        if not active():
            return orig_resize(src, dsize, *a, **kw)
        fx, fy = kw.get("fx", a[0] if len(a) > 0 else 0), kw.get("fy", a[1] if len(a) > 1 else 0)
        if dsize is not None and dsize != (0, 0) and len(dsize) == 2:
            check_pixels(dsize[0], dsize[1], "resized picture")
        elif fx and fy:
            check_pixels(src.shape[1] * fx, src.shape[0] * fy, "resized picture")
        return orig_resize(src, dsize, *a, **kw) if dsize is not None else orig_resize(src, None, *a, **kw)

    def warp_affine(src, M, dsize, *a, **kw):
        if active():
            check_pixels(dsize[0], dsize[1], "warped picture")
        return orig_aff(src, M, dsize, *a, **kw)

    def warp_perspective(src, M, dsize, *a, **kw):
        if active():
            check_pixels(dsize[0], dsize[1], "warped picture")
        return orig_persp(src, M, dsize, *a, **kw)

    cv2.resize, cv2.warpAffine, cv2.warpPerspective = resize, warp_affine, warp_perspective
