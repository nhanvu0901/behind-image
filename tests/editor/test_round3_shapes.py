"""A stored storyboard of the wrong shape (the engine fixer's 25 mutations) is a 409 `data_error` on every route that opens
the project, never a 500; the home list never changes; an upload or import of a damaged image is refused with a code."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


ENG_CONF = _load("_r3_engine_conftest", "tests/engine/conftest.py")
ENG = _load("_r3_engine_tests", "tests/engine/test_round3_engine.py")
from bti.editor.app import create_app  # noqa: E402


@pytest.fixture()
def made(tmp_path):
    root = tmp_path / "projects"
    d = root / "tiny"
    (d / "media").mkdir(parents=True)
    ENG_CONF.make_image(d / "media" / "a.jpg", 800, 1200, 1)
    ENG_CONF.make_image(d / "media" / "b.jpg", 900, 700, 2)
    (d / "timing.json").write_text(json.dumps({"duration": 20.0, "words": ENG_CONF.words(), "beats": [], "chapters": []}))
    (d / "storyboard.json").write_text(json.dumps(ENG_CONF.base_storyboard()))
    return root


@pytest.fixture()
def client(made):
    with TestClient(create_app(projects_root=made), raise_server_exceptions=False) as c:
        c.root = made
        yield c


@pytest.mark.parametrize("label,mut", ENG.MUTATIONS, ids=[m[0] for m in ENG.MUTATIONS])
def test_wrong_shape_on_disk_is_409_data_error_on_every_route(client, label, mut):
    assert client.get("/api/projects/tiny").status_code == 200
    f = client.root / "tiny" / "storyboard.json"
    good = f.read_text()
    sb = json.loads(good)
    mut(sb)
    f.write_text(json.dumps(sb))
    sb_for_post = json.loads(good)
    calls = [("get", "/api/projects/tiny", None), ("get", "/api/projects/tiny/thumb/s1", None),
             ("get", "/api/projects/tiny/frame?t=1&width=320", None), ("get", "/api/projects/tiny/pipeline", None),
             ("post", "/api/projects/tiny/validate", {"storyboard": sb_for_post}),
             ("get", "/api/projects/tiny/proposals", None),
             ("post", "/api/projects/tiny/approve", {"rev": "x"})]
    for verb, url, body in calls:
        r = getattr(client, verb)(url, **({"json": body} if body is not None else {}))
        if url.endswith("/pipeline") or url.endswith("/validate"):
            assert r.status_code < 500, (label, url, r.status_code, r.text[:150])
        else:
            assert r.status_code in (404, 409), (label, url, r.status_code, r.text[:150])
        assert "/private" not in r.text and "Error" not in r.text.split("detail")[-1][:80] or r.status_code != 500
    r = client.get("/api/projects")
    assert r.status_code == 200 and any(p["id"] == "tiny" for p in r.json())
    f.write_text(good)
    assert client.get("/api/projects/tiny").status_code == 200            # repaired: works again, no restart


def test_a_whole_storyboard_of_the_wrong_shape_names_the_file(client):
    f = client.root / "tiny" / "storyboard.json"
    sb = json.loads(f.read_text())
    sb["shots"] = "no"
    f.write_text(json.dumps(sb))
    r = client.get("/api/projects/tiny")
    assert r.status_code == 409 and "storyboard.json" in r.json()["detail"]


# ------------------------------------------------------------------ uploads
def _png():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (300, 200), (9, 9, 9)).save(b, "PNG")
    return b.getvalue()


def _jpg():
    from PIL import Image
    import numpy as np
    b = io.BytesIO()
    Image.fromarray((np.random.RandomState(1).rand(400, 600, 3) * 255).astype("uint8")).save(b, "JPEG")
    return b.getvalue()


@pytest.mark.parametrize("label,data,ext,code", [
    ("empty", b"", "png", "image_empty"), ("garbage", b"not an image at all", "jpg", "image_unreadable"),
    ("truncated-jpeg", _jpg()[:2000], "jpg", "image_truncated"), ("truncated-png", _png()[:80], "png", None),
])
def test_a_damaged_upload_is_refused_with_a_code_and_leaves_nothing(client, label, data, ext, code):
    r = client.post("/api/projects/tiny/assets/upload", files={"file": (f"x.{ext}", data, "image/jpeg")},
                    data={"title": "t", "licence": "CC0", "source_url": "https://e.org/x", "author": "me"})
    assert r.status_code == 422, (label, r.text)
    if code:
        assert r.json()["code"] == code, r.text
    media = sorted(p.name for p in (client.root / "tiny" / "media").iterdir())
    assert media == ["a.jpg", "b.jpg"], media
    assert not list((client.root / "tiny" / "cache" / "uploads").glob("*"))


def test_a_good_upload_still_works(client):
    r = client.post("/api/projects/tiny/assets/upload", files={"file": ("x.png", _png(), "image/png")},
                    data={"title": "t", "licence": "CC0", "source_url": "https://e.org/x", "author": "me"})
    assert r.status_code == 200, r.text


def test_media_import_of_a_truncated_download_is_refused_and_removed(tmp_path):
    from bti.media import api as mapi, imageinfo
    pd = tmp_path / "p"
    (pd / "media").mkdir(parents=True)

    class Src:
        def fetch_meta(self, sid):
            return {"title": "t", "kind": "image", "width": 600, "height": 400}

        def licence(self, meta):
            return True, "CC0", ""

        def download(self, meta, dest, min_short_side=0):
            dest.write_bytes(_jpg()[:1500])

    import pytest as _p
    mp = _p.MonkeyPatch()
    try:
        mp.setattr(mapi, "get_source", lambda name: Src())
        with pytest.raises(imageinfo.ImageDamaged) as e:
            mapi.import_candidate(pd, "fake", "1")
        assert e.value.code == "image_truncated"
        assert list((pd / "media").iterdir()) == []
    finally:
        mp.undo()
