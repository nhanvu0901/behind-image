"""Tests for OpenStreetMap (OSM) map source. Tested with fixtures only (no network)."""
import io
import json
from pathlib import Path
from PIL import Image
import pytest

from bti.media.errors import NotFound
from bti.media.sources.osm import OsmSource, calculate_zoom

NOMINATIM_GHENT = [
    {
        "place_id": 1001,
        "lat": "51.0543",
        "lon": "3.7174",
        "display_name": "Ghent, East Flanders, Flanders, Belgium",
        "boundingbox": ["50.98", "51.12", "3.63", "3.81"],
        "type": "city",
    }
]


class MockResponse:
    def __init__(self, data: bytes | dict | list, status: int = 200, headers: dict | None = None):
        if isinstance(data, (dict, list)):
            self._data = json.dumps(data).encode("utf-8")
        else:
            self._data = data
        self.status = status
        self.code = status
        self.headers = headers or {"Content-Length": str(len(self._data))}

    def read(self, amt: int = -1) -> bytes:
        if amt == -1:
            res = self._data
            self._data = b""
            return res
        res = self._data[:amt]
        self._data = self._data[amt:]
        return res

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def make_tile_png() -> bytes:
    img = Image.new("RGB", (256, 256), (200, 220, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_osm_rate_limiting_nominatim():
    sleep_calls = []

    def mock_sleep(s):
        sleep_calls.append(s)

    now_val = [100.0]

    def mock_now():
        return now_val[0]

    def mock_opener(req, **kw):
        return MockResponse(NOMINATIM_GHENT)

    src = OsmSource(opener=mock_opener, sleep=mock_sleep, clock=mock_now)
    # First search: no sleep
    src.search("Ghent")
    assert len(sleep_calls) == 0

    # Second search 0.3s later: must sleep 0.7s
    now_val[0] = 100.3
    src.search("Ghent")
    assert len(sleep_calls) == 1
    assert pytest.approx(sleep_calls[0], 0.01) == 0.7


def test_calculate_zoom():
    # Large country/region vs city vs neighborhood
    z_world = calculate_zoom(["-60.0", "60.0", "-120.0", "120.0"])
    assert z_world <= 6
    z_city = calculate_zoom(["50.98", "51.12", "3.63", "3.81"])
    assert 10 <= z_city <= 14


def test_osm_search_and_metadata(tmp_path):
    tile_bytes = make_tile_png()

    def mock_opener(req, **kw):
        url = getattr(req, "full_url", str(req))
        if "nominatim" in url:
            return MockResponse(NOMINATIM_GHENT)
        if "tile.openstreetmap.org" in url:
            return MockResponse(tile_bytes)
        raise NotFound(url)

    src = OsmSource(opener=mock_opener, sleep=lambda s: None, cache_dir=tmp_path / "osm_cache")
    results = src.search("Ghent", kind="image")
    assert len(results) == 1
    m = results[0]
    assert m["source"] == "osm"
    assert m["source_id"].startswith("1001:")
    assert "Ghent" in m["title"]
    assert m["author"] == "© OpenStreetMap contributors"
    assert m["licence"] == "ODbL"
    assert m["licence_url"] == "https://www.openstreetmap.org/copyright"
    assert m["width"] == 2400
    assert m["height"] == 1350
    assert m["kind"] == "image"

    # Video search on osm returns empty
    assert src.search("Ghent", kind="video") == []


def test_osm_download_and_caching(tmp_path):
    tile_bytes = make_tile_png()
    tile_fetch_count = [0]

    def mock_opener(req, **kw):
        url = getattr(req, "full_url", str(req))
        if "nominatim" in url:
            return MockResponse(NOMINATIM_GHENT)
        if "tile.openstreetmap.org" in url:
            tile_fetch_count[0] += 1
            return MockResponse(tile_bytes)
        raise NotFound(url)

    cache_dir = tmp_path / "osm_cache"
    src = OsmSource(opener=mock_opener, sleep=lambda s: None, cache_dir=cache_dir)
    res = src.search("Ghent", kind="image")[0]

    dest1 = tmp_path / "ghent_map.jpg"
    src.download(res, dest1)
    assert dest1.is_file()
    assert dest1.stat().st_size > 0
    img1 = Image.open(dest1)
    assert img1.size == (2400, 1350)
    initial_tile_fetches = tile_fetch_count[0]
    assert initial_tile_fetches > 0

    # Second download should use cache, not fetching tiles again
    dest2 = tmp_path / "ghent_map_2.jpg"
    src.download(res, dest2)
    assert dest2.is_file()
    assert tile_fetch_count[0] == initial_tile_fetches


def test_osm_credit():
    src = OsmSource()
    meta = {
        "source": "osm",
        "page_url": "https://www.openstreetmap.org/#map=12/51.0543/3.7174",
        "author": "© OpenStreetMap contributors",
        "licence": "ODbL",
        "licence_url": "https://www.openstreetmap.org/copyright",
    }
    c = src.credit(meta)
    assert c["source"] == "osm"
    assert c["author"] == "© OpenStreetMap contributors"
    assert c["licence"] == "ODbL"
    assert c["licence_url"] == "https://www.openstreetmap.org/copyright"
