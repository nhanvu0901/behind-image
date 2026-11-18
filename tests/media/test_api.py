import json
from pathlib import Path

import pytest

from bti.media import api
from bti.media.errors import ImageTooSmall
from bti.media.sources.commons import CommonsSource
from bti.media.sources.met import MetSource

from conftest import FakeNet, load, png_bytes


@pytest.fixture
def commons_net(monkeypatch):
    big = png_bytes(1300, 1250)
    net = FakeNet([("upload.wikimedia.org/wikipedia/commons/a/a0", big),
                   ("upload.wikimedia.org/x/nc", b"nope"),
                   ("commons.wikimedia.org", load("commons_search.json"))])
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    return net


def test_search_candidate_shape_and_licence_flags(commons_net):
    res = api.search("Arnolfini Portrait", "commons", "image", 10)
    keys = {"source", "source_id", "title", "thumb_url", "page_url", "width", "height", "mime",
            "author", "licence", "licence_ok", "licence_reason", "flag"}
    assert all(set(r) == keys for r in res)
    by = {r["source_id"]: r for r in res}
    assert by["File:Arnolfini nc.jpg"]["licence_ok"] is False
    assert "NC" in by["File:Arnolfini nc.jpg"]["licence_reason"]
    assert by["File:Arnolfini nolicence.jpg"]["licence_ok"] is False
    assert by["File:Arnolfini small.png"]["licence"] == "CC BY-SA 4.0"
    # the advisory flag: licence problems first, then a small picture
    assert by["File:Arnolfini nc.jpg"]["flag"] == "rejected" and by["File:Arnolfini nolicence.jpg"]["flag"] == "unknown"
    assert by["File:Arnolfini small.png"]["flag"] == "small"


def test_check_licence_facade():
    assert api.check_licence({"licence": "CC0"}) == (True, "CC0", "")


def test_import_writes_file_and_entry(commons_net, tmp_path):
    proj = tmp_path / "p1"
    sid = "File:Jan van Eyck - The Arnolfini Portrait - Google Art Project.jpg"
    # fetch_meta must find this title: serve only that page
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 2][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [dict(page)]}}))
    res = api.import_candidate(proj, "commons", sid, min_short_side=1200)
    key, asset = res["asset_key"], res["asset"]
    assert key == "arnolfini_portrait"
    assert set(asset) == {"file", "kind", "title", "artist", "year", "width", "height", "credit"}
    assert asset["file"] == "media/arnolfini_portrait.jpg" and (proj / asset["file"]).is_file()
    assert asset["kind"] == "image" and asset["artist"] == "Jan van Eyck" and asset["year"] == "1434"
    assert (asset["width"], asset["height"]) == (4386, 6000)
    assert asset["credit"]["licence"] == "PD" and asset["credit"]["source"] == "commons"
    assert not (proj / "storyboard.json").exists()       # the backend merges, we do not
    n = len(commons_net.urls)
    again = api.import_candidate(proj, "commons", sid)
    assert again == res and len(commons_net.urls) == n   # stable, no re-download


def test_key_avoids_clash_with_storyboard_assets(commons_net, tmp_path):
    proj = tmp_path / "p2"
    proj.mkdir()
    (proj / "storyboard.json").write_text(json.dumps({"assets": {"arnolfini_portrait": {}}}))
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 2][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [page]}}))
    res = api.import_candidate(proj, "commons", "File:x.jpg")
    assert res["asset_key"].startswith("arnolfini_portrait_") and len(res["asset_key"]) <= 24
    sb = json.loads((proj / "storyboard.json").read_text())
    assert list(sb["assets"]) == ["arnolfini_portrait"]            # untouched


def test_import_nc_licence_is_kept_and_flagged_not_refused(commons_net, tmp_path):
    # CHANGED (advisory gate, owner decision 2026-11-16): this used to assert LicenceRejected before any download.
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 3][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [page]}}))
    commons_net.routes.insert(0, ("x/nc", png_bytes(1300, 1250)))
    res = api.import_candidate(tmp_path / "p", "commons", "File:Arnolfini nc.jpg")
    assert res["asset"]["credit"]["flag"] == "rejected" and "NC" in api.check_licence({"licence": "CC BY-NC-SA 3.0"})[2]
    assert any("x/nc" in u for u in commons_net.urls) and (tmp_path / "p" / res["asset"]["file"]).is_file()


def test_import_too_small_is_flagged_not_refused(commons_net, tmp_path):
    # CHANGED (advisory size floor): this used to assert ImageTooSmall.
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 1][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [page]}}))
    commons_net.routes.insert(0, ("s/s0", png_bytes(800, 600)))
    res = api.import_candidate(tmp_path / "p", "commons", "File:Arnolfini small.png")
    assert res["asset"]["credit"]["flag"] == "small" and (res["asset"]["width"], res["asset"]["height"]) == (800, 600)
    # the threshold is still configurable: under a 500 px floor the same picture is fine
    res2 = api.import_candidate(tmp_path / "q", "commons", "File:Arnolfini small.png", min_short_side=500)
    assert res2["asset"]["credit"]["flag"] is None


def test_met_search_and_import(monkeypatch, tmp_path):
    net = FakeNet([("/search", {"total": 1, "objectIDs": [436535]}),
                   ("/objects/436535", load("met_object.json")),
                   ("images.metmuseum.org", png_bytes(1500, 1300))])
    monkeypatch.setitem(api._SOURCES, "met", MetSource(opener=net, sleep=lambda s: None))
    res = api.search("wheat field", "met")
    assert res[0]["licence"] == "CC0" and res[0]["licence_ok"] and res[0]["author"] == "Vincent van Gogh"
    out = api.import_candidate(tmp_path / "m", "met", "436535")
    a = out["asset"]
    assert out["asset_key"] == "wheat_field_cypresses" and a["year"] == "1889"
    assert (a["width"], a["height"]) == (1500, 1300) and a["credit"]["source"] == "met"


def test_met_search_uses_the_documented_v1_1_url(monkeypatch):
    # LR-003: /v1/search answers 410 since 2026-10-01; the documented one is /v1.1/search with limit and offset.
    net = FakeNet([("/search", {"total": 1, "objectIDs": [436535]}), ("/objects/436535", load("met_object.json"))])
    MetSource(opener=net, sleep=lambda s: None).search("wheat field", limit=5)
    u = [x for x in net.urls if "/search" in x][0]
    assert u.startswith("https://collectionapi.metmuseum.org/public/collection/v1.1/search?")
    assert "limit=5" in u and "offset=0" in u and "q=wheat+field" in u
    assert any("/public/collection/v1/objects/436535" in x for x in net.urls)


def test_met_non_pd_is_flagged_not_refused(monkeypatch, tmp_path):
    # CHANGED (advisory gate): this used to assert LicenceRejected.
    obj = dict(load("met_object.json"), isPublicDomain=False)
    net = FakeNet([("/objects/1", obj), ("images.metmuseum.org", png_bytes(1500, 1300))])
    monkeypatch.setitem(api._SOURCES, "met", MetSource(opener=net, sleep=lambda s: None))
    res = api.import_candidate(tmp_path / "m", "met", "1")
    assert res["asset"]["credit"]["flag"] == "rejected"


def test_add_upload(tmp_path):
    f = tmp_path / "scan.png"
    f.write_bytes(png_bytes(64, 32))
    proj = tmp_path / "p"
    res = api.add_upload(proj, f, {"licence": "CC BY 4.0", "source_url": "https://example.org/x",
                                   "author": "unknown, PD", "title": "My Scan"})
    assert res["asset_key"] == "my_scan" and res["asset"]["width"] == 64
    assert res["asset"]["credit"]["source"] == "upload" and (proj / "media/my_scan.png").is_file()


def test_add_upload_needs_no_metadata_and_flags_the_licence(tmp_path):
    # CHANGED (advisory gate): this used to assert ValueError for missing fields and LicenceRejected for an NC licence.
    f = tmp_path / "scan.png"
    f.write_bytes(png_bytes(1300, 1250))
    bare = api.add_upload(tmp_path / "p", f, {})["asset"]["credit"]
    assert bare["flag"] == "unknown" and bare["author"] == "unknown" and bare["source"] == "upload"
    nc = api.add_upload(tmp_path / "p2", f, {"licence": "CC BY-NC 4.0", "source_url": "u", "author": "a"})["asset"]["credit"]
    assert nc["flag"] == "rejected" and nc["licence"] == "CC BY-NC 4.0"
    ok = api.add_upload(tmp_path / "p3", f, {"licence": "CC0", "source_url": "u", "author": "a"})["asset"]["credit"]
    assert ok["flag"] is None
    small = tmp_path / "small.png"
    small.write_bytes(png_bytes(40, 30))
    assert api.add_upload(tmp_path / "p4", small, {"licence": "CC0"})["asset"]["credit"]["flag"] == "small"


def test_unknown_source_and_kind():
    with pytest.raises(ValueError):
        api.search("x", "flickr")
    with pytest.raises(ValueError):
        api.search("x", "commons", "audio")


def test_get_new_sources():
    for name in ("pexels", "pixabay", "osm"):
        src = api.get_source(name)
        assert src.name == name


def test_import_video_candidate(tmp_path, monkeypatch):
    class FakeVideoSource:
        name = "testvideo"

        def fetch_meta(self, sid):
            return {
                "source": "testvideo",
                "source_id": sid,
                "title": "A Video Clip",
                "kind": "video",
                "mime": "video/mp4",
                "url": "https://example.com/video.mp4",
                "author": "Videographer",
                "licence": "CC BY 4.0",
                "licence_url": "https://example.com/lic",
            }

        def download(self, meta, dest, **kw):
            Path(dest).write_bytes(b"fake-video-bytes")
            return dest

        def credit(self, meta):
            return {
                "source": "testvideo",
                "source_url": meta.get("url", ""),
                "author": meta.get("author", ""),
                "licence": meta.get("licence", ""),
                "licence_url": meta.get("licence_url", ""),
            }

    monkeypatch.setitem(api._SOURCES, "testvideo", FakeVideoSource())
    monkeypatch.setattr("bti.media.clips.normalize", lambda src, dest, **kw: Path(dest).write_bytes(Path(src).read_bytes()))
    monkeypatch.setattr("bti.media.api._probe_upload_video", lambda p: {"width": 1920, "height": 1080, "duration": 12.5})

    proj = tmp_path / "proj"
    res = api.import_candidate(proj, "testvideo", "vid1")
    assert res["asset"]["kind"] == "video"
    assert res["asset"]["duration"] == 12.5
    assert res["asset"]["width"] == 1920
    assert res["asset"]["height"] == 1080
    assert (proj / res["asset"]["file"]).is_file()

