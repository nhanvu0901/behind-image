"""Helpers of the picks tests: a project with an approved narration, fake media sources (no network), a PNG maker."""
import io
import json
import struct
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for p in (REPO, REPO / "tests" / "script"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from script_helpers import make_narration, make_outline  # noqa: E402

from bti.script import store  # noqa: E402

MEDIA_FIX = REPO / "tests" / "media" / "fixtures"


def load_fix(name):
    return json.loads((MEDIA_FIX / name).read_text(encoding="utf-8"))


def png_bytes(w, h):
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x80\x80\x80" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class FakeResp(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class FakeNet:
    """Opener routed by URL substring; records every URL. Nothing here reaches a network."""

    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        for sub, resp in self.routes:
            if sub in url:
                if isinstance(resp, Exception):
                    raise resp
                return FakeResp(resp if isinstance(resp, bytes) else json.dumps(resp).encode())
        raise AssertionError(f"unexpected URL {url}")


def make_project(root: Path, pid="pk1", approved=True, details=("THE MIRROR", "SIGNATURE")) -> Path:
    """A library-style project: project.json, a dossier with images and details, an outline and a narration (approved)."""
    d = root / pid
    (d / "source").mkdir(parents=True)
    (d / "project.json").write_text(json.dumps({
        "id": pid, "title": "The Test Painting", "artist": "A. Painter", "year": "1434", "stage": "script",
        "sources": [{"work_id": "payne_gae/002", "book_id": "payne_gae", "pdf_pages": [23, 25]}], "dossier": "source/dossier.json"}))
    (d / "source" / "dossier.json").write_text(json.dumps({
        "identity": {"title": "The Test Painting", "artist": "A. Painter", "year": "1434"}, "details": list(details),
        "images": [{"work_id": "payne_gae/002", "xref": 850, "page": 23, "width": 1358, "height": 1600},
                   {"work_id": "other/001", "xref": 9, "page": 1, "width": 500, "height": 500}], "sources": []}))
    o = make_outline(approved=True)
    store.save_outline(d, o)
    n = make_narration()
    store.save_narration(d, n)
    if approved:
        store.approve(d, "narration", n.rev())
    return d


def beat_ids(pdir):
    n = store.load_narration(pdir)
    return [b.id for c in n.chapters for b in c.beats]


def mount(app):
    """Add the picks router to an app made by `create_app` and put its routes before the app's `/{path:path}` catch-all
    (a router included after the catch-all would never see a GET). CORE includes it inside `create_app`, before the catch-all."""
    from bti.editor import picks_api
    if any(getattr(r, "path", "").endswith("/picks") for r in app.routes):
        return app
    before = len(app.router.routes)
    app.include_router(picks_api.router)
    new = app.router.routes[before:]
    del app.router.routes[before:]
    at = next((i for i, r in enumerate(app.router.routes) if getattr(r, "path", "") == "/{path:path}"), len(app.router.routes))
    app.router.routes[at:at] = new
    return app
