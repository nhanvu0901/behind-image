"""mediafix3: an OpenStreetMap import finds its place from its own source id (so it works after the app restarted), there is no
default centre, and the map cache can only serve a map that was drawn for the same centre and zoom. Fakes only."""
import json
import re
import urllib.error
from pathlib import Path

import pytest
from PIL import Image

import bti
from bti.media import api, http
from bti.media.sources import osm
from bti.media.sources.osm import OsmSource

from conftest import FakeResp, png_bytes

OSLO = {"place_id": 297322, "lat": "59.9133301", "lon": "10.7389701", "display_name": "Oslo, Norway",
        "boundingbox": ["59.8", "60.0", "10.5", "10.9"]}
GHENT = {"place_id": 1001, "lat": "51.0543", "lon": "3.7174", "display_name": "Ghent, East Flanders, Flanders, Belgium",
         "boundingbox": ["50.98", "51.12", "3.63", "3.81"]}
OSLO_ID = "297322:12:59.91333:10.73897:Oslo"
TILE = png_bytes(256, 256)


class Net:
    """Nominatim answers `places`; every tile is a 256 px PNG. Records the tiles asked for."""

    def __init__(self, places=(), fail_at=None, tile=TILE):
        self.places, self.urls, self.fail_at, self.tile = list(places), [], fail_at, tile

    def tiles(self):
        out = []
        for u in self.urls:
            m = re.search(r"tile\.openstreetmap\.org/(\d+)/(\d+)/(\d+)\.png", u)
            if m:
                out.append(tuple(int(g) for g in m.groups()))
        return out

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if "nominatim" in url:
            return FakeResp(json.dumps(self.places).encode())
        assert "tile.openstreetmap.org" in url, url
        if self.fail_at is not None and len(self.tiles()) - 1 == self.fail_at[0]:
            raise self.fail_at[1]
        return FakeResp(self.tile)


def make_source_id(*a):
    return osm.make_source_id(*a)


def parse_source_id(*a):
    return osm.parse_source_id(*a)


def make(tmp_path, net=None, **kw):
    net = net or Net()
    return OsmSource(opener=net, sleep=lambda s: None, cache_dir=tmp_path / "cache", **kw), net


def tile_window_of(lat, lon, z):
    cx, cy = osm._lat_lon_to_tile(lat, lon, z)
    return cx, cy


def near(tiles, lat, lon, z):
    """Every tile lies in the window of a 2400 x 1350 map centred on (lat, lon): 10 columns and 6 rows around the centre tile."""
    cx, cy = tile_window_of(lat, lon, z)
    return bool(tiles) and all(abs(x - cx) <= 6 and abs(y - cy) <= 4 for _, x, y in tiles)


def code_of(call, *a, **k):
    with pytest.raises(Exception) as e:
        call(*a, **k)
    assert getattr(e.value, "code", None) == "map_place_unknown", repr(e.value)
    assert isinstance(e.value, ValueError)
    return e.value


# ---------------------------------------------------------------- the id carries the place
def test_a_search_result_id_carries_the_coordinates_the_search_returned(tmp_path):
    src, _ = make(tmp_path, Net([OSLO]))
    (m,) = src.search("Oslo")
    assert m["source_id"] == OSLO_ID
    assert m["title"] == "Bản đồ Oslo" and (m["_lat"], m["_lon"], m["_zoom"]) == (59.91333, 10.73897, 12)
    assert parse_source_id(m["source_id"]) == {"pid": "297322", "lat": 59.91333, "lon": 10.73897, "zoom": 12, "name": "Oslo"}


def test_a_source_that_never_searched_rebuilds_the_same_meta_from_the_id(tmp_path):
    a, _ = make(tmp_path, Net([OSLO]))
    (searched,) = a.search("Oslo")
    b, _ = make(tmp_path)                               # a new process: no memory of any search
    assert b.fetch_meta(searched["source_id"]) == searched


def test_an_import_after_a_restart_draws_oslo_and_not_ghent(tmp_path):
    a, _ = make(tmp_path, Net([OSLO]))
    sid = a.search("Oslo")[0]["source_id"]
    b, net = make(tmp_path)                             # the app restarted between the search and the import
    meta = b.fetch_meta(sid)
    out = b.download(meta, tmp_path / "oslo.jpg")
    assert Image.open(out).size == (2400, 1350)
    assert near(net.tiles(), 59.91333, 10.73897, 12)    # the tiles of Oslo
    assert not any(abs(x - osm._lat_lon_to_tile(51.0543, 3.7174, 12)[0]) < 50 for _, x, _y in net.tiles())    # and nothing near Ghent


def test_the_whole_import_through_the_facade_after_a_restart(tmp_path, monkeypatch):
    sid = make(tmp_path, Net([OSLO]))[0].search("Oslo")[0]["source_id"]
    fresh, net = make(tmp_path)
    monkeypatch.setitem(api._SOURCES, "osm", fresh)
    res = api.import_candidate(tmp_path / "p", "osm", sid)
    a = res["asset"]
    assert a["title"] == "Bản đồ Oslo" and (a["width"], a["height"]) == (2400, 1350)
    assert a["credit"]["source"] == "osm" and "#map=12/59.9133/10.7390" in a["credit"]["source_url"]
    assert near(net.tiles(), 59.91333, 10.73897, 12)
    n = len(net.urls)
    assert api.import_candidate(tmp_path / "p", "osm", sid) == res and len(net.urls) == n          # the same id: no new request


def test_the_id_of_a_long_unicode_name_stays_under_the_routes_limit_and_round_trips():
    name = "Thành phố Hồ Chí Minh: Việt Nam % ?# " * 8
    sid = make_source_id(297322, 12, 10.77689, 106.70081, name)
    assert len(sid) <= 300 and sid.count(":") >= 4
    worst = make_source_id("9" * 60, 12, -85.0, -179.99999, "ệ" * 100)           # every character takes 9 once encoded
    assert len(worst) <= 300 and parse_source_id(worst)["lat"] == -85.0 and parse_source_id(worst)["name"] == "ệ" * 16
    back = parse_source_id(sid)
    assert back["lat"] == 10.77689 and back["lon"] == 106.70081 and back["zoom"] == 12 and back["name"].startswith("Thành phố Hồ Chí Minh: Việt")
    assert parse_source_id(make_source_id(5, 3, -33.8688, 151.2093, ""))["name"] == ""
    assert parse_source_id(make_source_id(5, 3, -0.0000001, 0.0, ""))["lat"] == 0.0 and "-0.00000" not in make_source_id(5, 3, -0.0000001, 0.0, "")


def test_a_place_that_cannot_be_drawn_is_not_offered(tmp_path):
    polar = dict(OSLO, lat="89.9")
    assert make(tmp_path, Net([polar]))[0].search("North Pole") == []
    assert make(tmp_path, Net([{"place_id": 1, "display_name": "x"}]))[0].search("x") == []
    assert make(tmp_path, Net([]))[0].search("nowhere") == []


# ---------------------------------------------------------------- no default centre: an unplaced map is an error
@pytest.mark.parametrize("sid", ["297322:12", "297322", "", "x:12:nan:3", "x:12:95:3", "x:12:10:181", "x:99:10:10", "x:12:abc:def",
                                 "../../x:12:10:10", "x:12:10", "x:-1:10:10", "x:12.5:10:10", "x:12:inf:10"])
def test_an_id_without_a_usable_place_is_an_error_with_a_code_and_nothing_is_drawn(tmp_path, sid):
    src, net = make(tmp_path)
    code_of(src.fetch_meta, sid)
    code_of(src.download, {"source_id": sid}, tmp_path / "x.jpg")
    code_of(src.download, {"source_id": sid, "_place_id": "297322", "_zoom": 12}, tmp_path / "y.jpg")     # what the old fetch_meta made
    assert net.urls == [] and not (tmp_path / "x.jpg").exists() and not (tmp_path / "y.jpg").exists()
    assert not (tmp_path / "cache").exists() or not list((tmp_path / "cache").glob("*"))


def test_through_the_facade_an_old_style_id_leaves_nothing_in_the_project(tmp_path, monkeypatch):
    src, net = make(tmp_path)
    monkeypatch.setitem(api._SOURCES, "osm", src)
    code_of(api.import_candidate, tmp_path / "p", "osm", "297322:12")
    assert net.urls == [] and not list((tmp_path / "p" / "media").glob("*.jpg"))


def test_a_record_kept_under_an_old_form_id_is_not_served_as_the_map(tmp_path, monkeypatch):
    """The project's index may hold a map imported before the id carried its place (it can be the wrong city): asking again with
    that id is the error, not the old file."""
    proj = tmp_path / "p"
    (proj / "media").mkdir(parents=True)
    old_file = proj / "media" / "ban_do_oslo.jpg"
    old_file.write_bytes(png_bytes(8, 4))
    asset = {"file": "media/ban_do_oslo.jpg", "kind": "image", "title": "Bản đồ Oslo", "width": 8, "height": 4, "credit": {"source": "osm"}}
    (proj / "media" / "sources.json").write_text(json.dumps({"items": {"osm:297322:12": {"key": "ban_do_oslo", "asset": asset}}}))
    src, net = make(tmp_path)
    monkeypatch.setitem(api._SOURCES, "osm", src)
    code_of(api.import_candidate, proj, "osm", "297322:12")
    assert net.urls == [] and old_file.read_bytes() == png_bytes(8, 4)                # nothing drawn, the old record untouched
    assert json.loads((proj / "media" / "sources.json").read_text())["items"]["osm:297322:12"]["key"] == "ban_do_oslo"


def test_there_is_no_default_centre_anywhere_in_the_code():
    root = Path(bti.__file__).parent
    for f in list(root.rglob("*.py")) + list((root / "editor" / "static").rglob("*.js")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        assert "51.0543" not in text and "3.7174" not in text, f


# ---------------------------------------------------------------- the cache holds only what was drawn for that centre and zoom
def test_a_cached_map_is_served_only_for_the_same_centre_and_zoom(tmp_path):
    src, net = make(tmp_path, Net([OSLO, GHENT]))
    meta = src.search("Oslo")[0]
    src.download(meta, tmp_path / "a.jpg")
    first = len(net.tiles())
    assert first > 0
    assert Path(src._cache_path(59.91333, 10.73897, 12)).name == "osm_2400x1350_z12_59.91333_10.73897.jpg"
    assert Path(src._cache_path(59.91333, 10.73897, 12)).is_file()

    src.download(meta, tmp_path / "b.jpg")                                       # the same centre and zoom: from the cache
    assert len(net.tiles()) == first and (tmp_path / "b.jpg").read_bytes() == (tmp_path / "a.jpg").read_bytes()
    src.download({**meta, "_lat": 59.913330001}, tmp_path / "b2.jpg")            # the same rounded centre: still the cache
    assert len(net.tiles()) == first

    src.download({**meta, "_zoom": 11}, tmp_path / "c.jpg")                      # another zoom: drawn again
    second = len(net.tiles())
    assert second > first
    src.download({**meta, "_lat": 59.92333}, tmp_path / "d.jpg")                 # another centre (0.01 degree): drawn again
    third = len(net.tiles())
    assert third > second
    ghent = make(tmp_path, Net([GHENT]))[0].search("Ghent")[0]
    src.download(ghent, tmp_path / "e.jpg")                                      # another place: drawn again, for that place
    assert len(net.tiles()) > third and near(net.tiles()[third:], 51.0543, 3.7174, ghent["_zoom"])
    assert len(list((tmp_path / "cache").glob("*.jpg"))) == 4                    # four different maps, four files, no overwriting


def test_the_wrong_file_the_old_code_left_in_the_cache_is_never_served(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "297322_z12.jpg").write_bytes(b"A MAP OF GHENT SAVED UNDER OSLO'S NAME")       # the old name: place id and zoom only
    src, net = make(tmp_path, Net([OSLO]))
    meta = src.search("Oslo")[0]
    assert meta["thumb_url"] == "" and meta["size"] == 0                          # a search does not present the unproven file either
    out = src.download(meta, tmp_path / "oslo.jpg")
    assert Image.open(out).size == (2400, 1350) and near(net.tiles(), 59.91333, 10.73897, 12)    # drawn again, for Oslo
    assert (cache / "297322_z12.jpg").read_bytes() == b"A MAP OF GHENT SAVED UNDER OSLO'S NAME"    # nothing was deleted by hand


def test_an_empty_cache_file_is_drawn_again(tmp_path):
    src, net = make(tmp_path, Net([OSLO]))
    meta = src.search("Oslo")[0]
    cache = src._cache_path(59.91333, 10.73897, 12)
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"")
    out = src.download(meta, tmp_path / "oslo.jpg")
    assert Image.open(out).size == (2400, 1350) and net.tiles()


# ---------------------------------------------------------------- a map is cached only when every tile arrived
def test_a_refused_tile_ends_the_map_and_caches_nothing(tmp_path):
    refused = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "120"}, None)
    src, net = make(tmp_path, Net([OSLO], fail_at=(2, refused)))
    meta = src.search("Oslo")[0]
    with pytest.raises(http.MediaHTTPError) as e:
        src.download(meta, tmp_path / "oslo.jpg")
    assert e.value.rate_limited and e.value.retry_after == 120
    assert len(net.tiles()) == 3                                                  # the tile server said "wait": the others are not asked for
    assert not list((tmp_path / "cache").glob("*")) and not (tmp_path / "oslo.jpg").exists()


def test_a_tile_that_is_not_an_image_ends_the_map_and_caches_nothing(tmp_path):
    src, net = make(tmp_path, Net([OSLO], tile=b"<html>maintenance</html>"))
    meta = src.search("Oslo")[0]
    with pytest.raises(http.MediaHTTPError):
        src.download(meta, tmp_path / "oslo.jpg")
    assert len(net.tiles()) == 1 and not list((tmp_path / "cache").glob("*"))


def test_a_map_is_drawn_from_one_search_request_and_one_set_of_tiles(tmp_path):
    src, net = make(tmp_path, Net([OSLO]))
    src.download(src.search("Oslo")[0], tmp_path / "oslo.jpg")
    assert len([u for u in net.urls if "nominatim" in u]) == 1 and 40 <= len(net.tiles()) <= 90
    assert len(set(net.tiles())) == len(net.tiles())                              # no tile twice
