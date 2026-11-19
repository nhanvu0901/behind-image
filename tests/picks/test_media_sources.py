"""mediafix3 through the picks routes (real media facade, fake transports, no network): a Commons import takes a standard-width
rendition and records the stored size, and an OpenStreetMap import after a restart draws the place it was searched for."""
import io
import json
import re
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from picks_helpers import FakeResp, mount, png_bytes
from PIL import Image

from bti.editor.app import create_app
from bti.media import api as media_api
from bti.media.sources import osm as osm_mod
from bti.media.sources.commons import CommonsSource
from bti.media.sources.osm import OsmSource
from bti.script import env

ORIG = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Munch.jpg"
TITLE = "File:Munch.jpg"
OSLO = {"place_id": 297322, "lat": "59.9133301", "lon": "10.7389701", "display_name": "Oslo, Norway",
        "boundingbox": ["59.8", "60.0", "10.5", "10.9"]}


def jpeg(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 110, 100)).save(buf, "JPEG", quality=60)
    return buf.getvalue()


class Wiki:
    def __init__(self, w, h, orig, rendition, with_thumb=True):
        self.w, self.h, self.orig, self.rendition, self.with_thumb, self.urls = w, h, orig, rendition, with_thumb, []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if "api.php" in url:
            width = int(parse_qs(urlparse(url).query)["iiurlwidth"][0])
            ii = {"url": ORIG, "descriptionurl": "https://commons.wikimedia.org/wiki/" + TITLE, "width": self.w, "height": self.h,
                  "size": 2_000_000, "mime": "image/jpeg",
                  "extmetadata": {"LicenseShortName": {"value": "Public domain"}, "Artist": {"value": "Edvard Munch"}}}
            if self.with_thumb:
                ii["thumburl"] = f"https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Munch.jpg/{width}px-Munch.jpg"
            return FakeResp(json.dumps({"query": {"pages": [{"title": TITLE, "index": 1, "imageinfo": [ii]}]}}).encode())
        out = self.orig if url == ORIG else self.rendition
        if isinstance(out, Exception):
            raise out
        return FakeResp(out)


class Maps:
    """Nominatim finds Oslo; every tile is a 256 px PNG. Records every URL."""

    def __init__(self, places=()):
        self.places, self.urls = list(places), []
        self.tile = png_bytes(256, 256)

    def tiles(self):
        return [tuple(int(g) for g in m.groups()) for u in self.urls for m in [re.search(r"tile\.openstreetmap\.org/(\d+)/(\d+)/(\d+)\.png", u)] if m]

    def __call__(self, req, timeout=None):
        self.urls.append(req.full_url)
        if "nominatim" in req.full_url:
            return FakeResp(json.dumps(self.places).encode())
        assert "tile.openstreetmap.org" in req.full_url
        return FakeResp(self.tile)


@pytest.fixture
def client(root, proj, monkeypatch):
    monkeypatch.setattr(env, "has_key", lambda name: False)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app) as c:
        c.pid, c.pdir, c.root = proj.name, proj, root
        c.u = lambda tail="": f"/api/projects/{proj.name}/picks{tail}"
        yield c


def commons(monkeypatch, wiki):
    monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=wiki, sleep=lambda s: None))
    return wiki


# ---------------------------------------------------------------- Commons
def test_a_commons_import_stores_the_rendition_and_the_card_shows_the_stored_size(client, monkeypatch):
    refused = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "120"}, None)
    wiki = commons(monkeypatch, Wiki(2400, 1800, orig=refused, rendition=jpeg(1920, 1440)))
    (card,) = client.post(client.u("/search"), json={"query": "munch", "sources": ["commons"]}).json()["items"]
    assert (card["width"], card["height"]) == (1920, 1440)              # the card says what the file will be, not the 2400 x 1800 original
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": card["source_id"], "as_main": True})
    assert r.status_code == 200, r.text
    a = r.json()["asset"]
    assert (a["width"], a["height"]) == (card["width"], card["height"])        # the picture's card after the import shows the same
    assert (a["original_width"], a["original_height"]) == (2400, 1800)
    assert ORIG not in wiki.urls                                                # the refused address was never asked
    page = client.get(client.u()).json()["picks"]["assets"][r.json()["asset_key"]]     # what the step-4 page reads (picks.js: a.width x a.height)
    assert (page["width"], page["height"]) == (1920, 1440)
    stored = Image.open(client.pdir / page["file"]).size
    assert stored == (1920, 1440)                                               # the card's size is the file's size


def test_a_refused_commons_original_with_no_way_round_is_reported_with_its_wait(client, monkeypatch):
    refused = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "120"}, None)
    commons(monkeypatch, Wiki(1500, 1300, orig=refused, rendition=b"", with_thumb=False))
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": TITLE})
    assert r.status_code == 503
    assert r.json()["code"] == "source_rate_limited" and r.json()["retry_after"] == 120 and r.json()["retryable"] is True
    assert not list((client.pdir / "media").glob("*.jpg"))


# ---------------------------------------------------------------- OpenStreetMap
def test_an_osm_import_after_a_restart_is_a_map_of_the_searched_place(client, monkeypatch, tmp_path):
    cache = tmp_path / "osmcache"
    searching = Maps([OSLO])
    monkeypatch.setitem(media_api._SOURCES, "osm", OsmSource(opener=searching, sleep=lambda s: None, cache_dir=cache))
    (card,) = client.post(client.u("/search"), json={"query": "Oslo", "sources": ["osm"]}).json()["items"]
    assert card["source_id"] == "297322:12:59.91333:10.73897:Oslo"

    restarted = Maps()                                                          # a new process: no memory of the search, no Nominatim
    monkeypatch.setitem(media_api._SOURCES, "osm", OsmSource(opener=restarted, sleep=lambda s: None, cache_dir=cache))
    r = client.post(client.u("/import"), json={"source": "osm", "source_id": card["source_id"]})
    assert r.status_code == 200, r.text
    a = r.json()["asset"]
    assert a["title"] == "Bản đồ Oslo" and (a["width"], a["height"]) == (2400, 1350)
    assert not [u for u in restarted.urls if "nominatim" in u]
    cx, cy = osm_mod._lat_lon_to_tile(59.91333, 10.73897, 12)
    assert restarted.tiles() and all(z == 12 and abs(x - cx) <= 6 and abs(y - cy) <= 4 for z, x, y in restarted.tiles())     # Oslo, not Ghent
    assert Image.open(client.pdir / a["file"]).size == (2400, 1350)


def test_an_osm_import_without_a_place_is_a_422_with_a_code_and_draws_nothing(client, monkeypatch, tmp_path):
    maps = Maps()
    monkeypatch.setitem(media_api._SOURCES, "osm", OsmSource(opener=maps, sleep=lambda s: None, cache_dir=tmp_path / "osmcache"))
    r = client.post(client.u("/import"), json={"source": "osm", "source_id": "297322:12"})         # the form ids had before coordinates
    assert r.status_code == 422
    assert r.json()["code"] == "map_place_unknown"
    assert maps.urls == [] and not list((client.pdir / "media").glob("*")) and not (tmp_path / "osmcache").exists()
    assert not (client.pdir / "picks.json").exists()                                              # nothing was added to the picks
