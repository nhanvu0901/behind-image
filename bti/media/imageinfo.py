"""Image dimensions without hard dependencies (PNG/JPEG/GIF/WebP header sniff, PIL fallback)."""
from __future__ import annotations

import struct
from pathlib import Path


def image_size(path: Path) -> tuple[int, int]:
    """(width, height), or (0, 0) if it cannot be read."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    b = fh.read(1)
                    while b and b != b"\xff":
                        b = fh.read(1)
                    while b == b"\xff":
                        b = fh.read(1)
                    if not b:
                        break
                    marker = b[0]
                    if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                        continue
                    ln = struct.unpack(">H", fh.read(2))[0]
                    if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                        _, h, w = struct.unpack(">BHH", fh.read(5))
                        return w, h
                    fh.seek(ln - 2, 1)
    except (OSError, struct.error):
        pass
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        with Image.open(path) as im:
            return im.size
    except Exception:
        return 0, 0


def drawn_size(path: Path) -> tuple[int, int]:
    """The pixel size the engine DRAWS and the page SHOWS for the file at `path`, or (0, 0) when it cannot be read.

    It is `image_size` (the pixels of the file) with one correction: OpenCV (`cv2.imread`, what `bti.engine.vfx.Img` uses)
    and browsers turn a JPEG whose EXIF orientation is 5 to 8 a quarter turn, so for such a file the drawn width is the stored
    height. Every asset record must carry this size: it is the space the regions, the camera maths and the page agree on."""
    w, h = image_size(path)
    if not (w and h):
        return 0, 0
    try:
        with open(path, "rb") as fh:
            jpeg = fh.read(2) == b"\xff\xd8"
        if jpeg:
            from PIL import Image
            with Image.open(path) as im:
                if im.getexif().get(0x0112) in (5, 6, 7, 8):
                    return int(h), int(w)
    except Exception:       # noqa: BLE001  the header sniff above already gave a usable answer
        pass
    return int(w), int(h)


class ImageDamaged(ValueError):
    """An image file that does not decode completely. `code`: `image_empty`, `image_truncated` or `image_unreadable`."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def image_problem(path: Path) -> tuple[str, str] | None:
    """None when `path` is a non-empty image that decodes completely, else `(code, short reason)`. A file that only has a valid
    header (cut off part way, or junk after it) is refused: a stored asset must never break the stills that use it. This is the
    same completeness rule as the engine's `media_problem` (header reads AND all pixel data decodes); it is kept here because
    `bti.media` must not import the engine."""
    from PIL import Image
    try:
        if Path(path).stat().st_size == 0:
            return "image_empty", "the file is empty"
    except OSError:
        return "image_unreadable", "the file cannot be read"
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception:       # noqa: BLE001
        return "image_unreadable", "the file is not a readable image (damaged or not an image)"
    try:
        with Image.open(path) as im:
            im.load()
            if im.width < 1 or im.height < 1:
                return "image_unreadable", "the image has no pixels"
    except Exception:       # noqa: BLE001
        return "image_truncated", "the image is cut off: its picture does not decode completely"
    return None


def readable_problem(path: Path) -> str | None:
    """Short reason (see `image_problem`) or None."""
    p = image_problem(path)
    return p[1] if p else None
