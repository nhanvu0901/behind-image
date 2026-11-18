"""Tests for D15 new picture sources (Pexels, Pixabay, OSM) in picks API and service."""
import pytest
from fastapi.testclient import TestClient
from picks_helpers import FakeNet, mount, png_bytes

from bti.editor.app import create_app
from bti.media import api as media_api
from bti.picks import service


@pytest.fixture
def client_sources(root, proj, monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app) as c:
        c.pid, c.pdir, c.root = proj.name, proj, root
        c.u = lambda tail="": f"/api/projects/{proj.name}/picks{tail}"
        yield c


def test_payload_contains_sources_status(client_sources):
    r = client_sources.get(client_sources.u()).json()
    assert "sources" in r
    s = r["sources"]
    assert s["commons"]["has_key"] is True
    assert s["met"]["has_key"] is True
    assert s["osm"]["has_key"] is True
    assert s["pexels"]["has_key"] is False
    assert s["pixabay"]["has_key"] is False


def test_search_keyed_source_without_key_reports_no_key_and_is_not_called(client_sources, monkeypatch):
    called = []

    class DummyPexels:
        name = "pexels"
        def search(self, *a, **k):
            called.append("pexels")
            return []

    monkeypatch.setitem(media_api._SOURCES, "pexels", DummyPexels())
    r = client_sources.post(client_sources.u("/search"), json={"query": "landscape", "sources": ["pexels"]}).json()
    assert called == []  # Source was not called
    err = next((e for e in r["errors"] if e["source"] == "pexels"), None)
    assert err is not None
    assert err["code"] == "source_no_key"
    assert "chưa có khóa" in err["message"]


def test_search_with_osm_source(client_sources, monkeypatch):
    class FakeOsm:
        name = "osm"
        def search(self, query, kind="image", limit=1):
            return [{
                "source": "osm",
                "source_id": "1001:12",
                "title": f"Bản đồ {query}",
                "page_url": "https://www.openstreetmap.org/#map=12/51.05/3.71",
                "thumb_url": "",
                "width": 2400,
                "height": 1350,
                "mime": "image/jpeg",
                "kind": "image",
                "author": "© OpenStreetMap contributors",
                "licence": "ODbL",
                "licence_ok": False,
                "licence_reason": "",
                "flag": "unknown",
            }]

    monkeypatch.setitem(media_api._SOURCES, "osm", FakeOsm())
    r = client_sources.post(client_sources.u("/search"), json={"query": "Ghent", "sources": ["osm"]}).json()
    assert r["errors"] == []
    assert len(r["items"]) == 1
    item = r["items"][0]
    assert item["source"] == "osm"
    assert item["author"] == "© OpenStreetMap contributors"
    assert item["licence"] == "ODbL"


def test_import_osm_map(client_sources, monkeypatch):
    class FakeOsm:
        name = "osm"
        def fetch_meta(self, sid):
            return {
                "source": "osm",
                "source_id": sid,
                "title": "Bản đồ Ghent",
                "width": 2400,
                "height": 1350,
                "mime": "image/jpeg",
                "kind": "image",
                "author": "© OpenStreetMap contributors",
                "licence": "ODbL",
                "page_url": "https://www.openstreetmap.org",
            }

        def download(self, meta, dest, **kw):
            dest.write_bytes(png_bytes(2400, 1350))
            return dest

        def credit(self, meta):
            return {
                "source": "osm",
                "source_url": meta.get("page_url", ""),
                "author": "© OpenStreetMap contributors",
                "licence": "ODbL",
                "licence_url": "https://www.openstreetmap.org/copyright",
            }

    monkeypatch.setitem(media_api._SOURCES, "osm", FakeOsm())
    r = client_sources.post(client_sources.u("/import"), json={"source": "osm", "source_id": "1001:12"})
    assert r.status_code == 200
    j = r.json()
    assert j["asset"]["credit"]["source"] == "osm"
    assert j["asset"]["credit"]["author"] == "© OpenStreetMap contributors"
    assert j["asset"]["credit"]["licence"] == "ODbL"


def test_import_video_candidate_refuses_as_main(client_sources, monkeypatch):
    class FakeVideoSource:
        name = "pexels"
        def fetch_meta(self, sid):
            return {
                "source": "pexels",
                "source_id": sid,
                "title": "Water Flow",
                "width": 1920,
                "height": 1080,
                "duration": 10.0,
                "mime": "video/mp4",
                "kind": "video",
                "author": "Videographer",
                "licence": "Pexels License",
                "page_url": "https://www.pexels.com/video/1/",
            }

        def download(self, meta, dest, **kw):
            dest.write_bytes(b"fake-video-data")
            return dest

        def credit(self, meta):
            return {
                "source": "pexels",
                "source_url": meta.get("page_url", ""),
                "author": "Videographer",
                "licence": "Pexels License",
                "licence_url": "https://www.pexels.com/license/",
            }

    monkeypatch.setitem(media_api._SOURCES, "pexels", FakeVideoSource())
    monkeypatch.setattr("bti.media.clips.normalize", lambda src, dest, **kw: dest.write_bytes(src.read_bytes()))
    monkeypatch.setattr("bti.media.api._probe_upload_video", lambda p: {"width": 1920, "height": 1080, "duration": 10.0})

    # Cannot be main painting
    r_main = client_sources.post(client_sources.u("/import"), json={"source": "pexels", "source_id": "1", "as_main": True})
    assert r_main.status_code == 422
    assert r_main.json()["code"] == "video_not_main"

    # Regular import works and gets registered as video
    r_ok = client_sources.post(client_sources.u("/import"), json={"source": "pexels", "source_id": "1", "as_main": False})
    assert r_ok.status_code == 200
    assert r_ok.json()["asset"]["kind"] == "video"
    assert r_ok.json()["asset"]["duration"] == 10.0
