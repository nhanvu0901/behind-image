import json

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
            "author", "licence", "licence_ok", "licence_reason"}
    assert all(set(r) == keys for r in res)
    by = {r["source_id"]: r for r in res}
    assert by["File:Arnolfini nc.jpg"]["licence_ok"] is False
    assert "NC" in by["File:Arnolfini nc.jpg"]["licence_reason"]
    assert by["File:Arnolfini nolicence.jpg"]["licence_ok"] is False
    assert by["File:Arnolfini small.png"]["licence"] == "CC BY-SA 4.0"


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


def test_import_rejects_licence_before_download(commons_net, tmp_path):
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 3][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [page]}}))
    with pytest.raises(api.LicenceRejected) as ei:
        api.import_candidate(tmp_path / "p", "commons", "File:Arnolfini nc.jpg")
    assert "NC" in str(ei.value)
    assert not any("x/nc" in u for u in commons_net.urls)
    assert not list((tmp_path / "p").rglob("*.jpg"))


def test_import_too_small(commons_net, tmp_path):
    page = [p for p in load("commons_search.json")["query"]["pages"] if p["pageid"] == 1][0]
    commons_net.routes.insert(0, ("titles=", {"query": {"pages": [page]}}))
    with pytest.raises(ImageTooSmall):
        api.import_candidate(tmp_path / "p", "commons", "File:Arnolfini small.png")


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


def test_met_non_pd_rejected(monkeypatch, tmp_path):
    obj = dict(load("met_object.json"), isPublicDomain=False)
    net = FakeNet([("/objects/1", obj)])
    monkeypatch.setitem(api._SOURCES, "met", MetSource(opener=net, sleep=lambda s: None))
    with pytest.raises(api.LicenceRejected):
        api.import_candidate(tmp_path / "m", "met", "1")


def test_add_upload(tmp_path):
    f = tmp_path / "scan.png"
    f.write_bytes(png_bytes(64, 32))
    proj = tmp_path / "p"
    res = api.add_upload(proj, f, {"licence": "CC BY 4.0", "source_url": "https://example.org/x",
                                   "author": "unknown, PD", "title": "My Scan"})
    assert res["asset_key"] == "my_scan" and res["asset"]["width"] == 64
    assert res["asset"]["credit"]["source"] == "upload" and (proj / "media/my_scan.png").is_file()


def test_add_upload_requires_fields_and_licence(tmp_path):
    f = tmp_path / "scan.png"
    f.write_bytes(png_bytes(4, 4))
    with pytest.raises(ValueError):
        api.add_upload(tmp_path / "p", f, {"licence": "CC0", "source_url": ""})
    with pytest.raises(api.LicenceRejected):
        api.add_upload(tmp_path / "p", f, {"licence": "CC BY-NC 4.0", "source_url": "u", "author": "a"})


def test_unknown_source_and_kind():
    with pytest.raises(ValueError):
        api.search("x", "flickr")
    with pytest.raises(ValueError):
        api.search("x", "commons", "audio")
