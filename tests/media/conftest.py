import io
import json
import os
import struct
import sys
import zlib
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def png_bytes(w, h):
    """A valid PNG of the given size, cheap (1-colour rows)."""
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class FakeResp(io.BytesIO):
    def __init__(self, body: bytes, headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeNet:
    """Opener that routes by substring and records every URL. No real network."""

    def __init__(self, routes):
        self.routes = routes      # list of (substring, bytes | callable | Exception)
        self.urls = []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        assert "nhanvu" not in url and "nhanvu" not in str(req.headers).lower()
        for sub, resp in self.routes:
            if sub in url:
                if isinstance(resp, Exception):
                    raise resp
                if callable(resp):
                    resp = resp()
                    if isinstance(resp, Exception):
                        raise resp
                return FakeResp(resp if isinstance(resp, bytes) else json.dumps(resp).encode())
        raise AssertionError(f"unexpected URL {url}")


@pytest.fixture
def no_sleep():
    waits = []
    return waits.append


@pytest.fixture(autouse=True)
def _no_cooldown_between_tests():
    """A source's "wait N seconds" is remembered per host for the life of the process: no test may inherit another's."""
    from bti.media import http
    http.reset_cooldowns()
    yield
    http.reset_cooldowns()
