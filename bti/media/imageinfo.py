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
