"""Tests for Pexels source (photos and videos). Tested with fixtures only (no network)."""
from pathlib import Path
import json
import pytest

from bti.media.errors import NotFound, ImageTooSmall
from bti.media.sources.pexels import PexelsSource, parse_video

PEXELS_PHOTO_SEARCH = {
    "page": 1,
    "per_page": 2,
    "total_results": 100,
    "photos": [
        {
            "id": 2014422,
            "width": 3024,
            "height": 4032,
            "url": "https://www.pexels.com/photo/brown-rocks-during-golden-hour-2014422/",
            "photographer": "Joey Farina",
            "photographer_url": "https://www.pexels.com/@joey",
            "photographer_id": 1056587,
            "src": {
                "original": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg",
                "large2x": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940",
                "large": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?auto=compress&cs=tinysrgb&h=650&w=940",
                "medium": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?auto=compress&cs=tinysrgb&h=350",
                "small": "https://images.pexels.com/photos/2014422/pexels-photo-2014422.jpeg?auto=compress&cs=tinysrgb&h=130",
            },
            "alt": "Brown Rocks During Golden Hour",
        }
    ],
}

PEXELS_VIDEO_SEARCH = {
    "page": 1,
    "per_page": 1,
    "total_results": 50,
    "url": "https://www.pexels.com/search/videos/nature/",
    "videos": [
        {
            "id": 857251,
            "width": 1920,
            "height": 1080,
            "duration": 34,
            "url": "https://www.pexels.com/video/857251/",
            "image": "https://images.pexels.com/videos/857251/free-video-857251.jpg",
            "user": {
                "id": 12345,
                "name": "Jane Videographer",
                "url": "https://www.pexels.com/@jane",
            },
            "video_files": [
                {
                    "id": 1234,
                    "quality": "hd",
                    "file_type": "video/mp4",
                    "width": 1920,
                    "height": 1080,
                    "fps": 29.97,
                    "link": "https://player.vimeo.com/external/857251.hd.mp4",
                },
                {
                    "id": 1235,
                    "quality": "sd",
                    "file_type": "video/mp4",
                    "width": 960,
                    "height": 540,
                    "fps": 29.97,
                    "link": "https://player.vimeo.com/external/857251.sd.mp4",
                },
            ],
        }
    ],
}


class MockResponse:
    def __init__(self, data: bytes | dict, status: int = 200, headers: dict | None = None):
        self._data = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data
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


def test_pexels_without_key_is_not_called(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    src = PexelsSource(key=None)
    assert not src.has_key()
    assert src.search("landscape") == []
    assert src.search("waterfall", kind="video") == []


def test_pexels_photo_search(monkeypatch):
    calls = []

    def mock_opener(req, **kw):
        calls.append(req)
        assert req.headers.get("Authorization") == "test-pexels-key"
        assert "per_page=10" in req.full_url or "per_page=" in req.full_url
        return MockResponse(PEXELS_PHOTO_SEARCH)

    src = PexelsSource(key="test-pexels-key", opener=mock_opener, sleep=lambda s: None)
    assert src.has_key()
    results = src.search("rocks", kind="image", limit=10)
    assert len(results) == 1
    r = results[0]
    assert r["source"] == "pexels"
    assert r["source_id"] == "2014422"
    assert r["title"] == "Brown Rocks During Golden Hour"
    assert r["kind"] == "image"
    assert r["mime"] == "image/jpeg"
    assert r["width"] == 3024
    assert r["height"] == 4032
    assert r["author"] == "Joey Farina"
    assert r["licence"] == "Pexels License"
    assert r["page_url"] == "https://www.pexels.com/photo/brown-rocks-during-golden-hour-2014422/"
    assert "pexels-photo-2014422" in r["url"]


def test_pexels_video_search(monkeypatch):
    def mock_opener(req, **kw):
        assert req.headers.get("Authorization") == "test-pexels-key"
        assert "videos/search" in req.full_url
        return MockResponse(PEXELS_VIDEO_SEARCH)

    src = PexelsSource(key="test-pexels-key", opener=mock_opener, sleep=lambda s: None)
    results = src.search("nature", kind="video", limit=5)
    assert len(results) == 1
    v = results[0]
    assert v["source"] == "pexels"
    assert v["source_id"] == "857251"
    assert v["kind"] == "video"
    assert v["mime"] == "video/mp4"
    assert v["width"] == 1920
    assert v["height"] == 1080
    assert v["duration"] == 34.0
    assert v["author"] == "Jane Videographer"
    assert v["url"] == "https://player.vimeo.com/external/857251.hd.mp4"
    assert v["licence"] == "Pexels License"


def test_pexels_fetch_meta_photo():
    photo_data = PEXELS_PHOTO_SEARCH["photos"][0]

    def mock_opener(req, **kw):
        if "photos/2014422" in req.full_url:
            return MockResponse(photo_data)
        raise NotFound("not found")

    src = PexelsSource(key="test-key", opener=mock_opener, sleep=lambda s: None)
    meta = src.fetch_meta("2014422")
    assert meta["source_id"] == "2014422"
    assert meta["author"] == "Joey Farina"


def test_pexels_fetch_meta_video():
    video_data = PEXELS_VIDEO_SEARCH["videos"][0]

    def mock_opener(req, **kw):
        if "videos/videos/857251" in req.full_url:
            return MockResponse(video_data)
        import urllib.error
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    src = PexelsSource(key="test-key", opener=mock_opener, sleep=lambda s: None)
    meta = src.fetch_meta("857251")
    assert meta["source_id"] == "857251"
    assert meta["kind"] == "video"
    assert meta["duration"] == 34.0


def test_pexels_credit():
    src = PexelsSource(key="test-key")
    meta = {
        "source": "pexels",
        "page_url": "https://www.pexels.com/photo/123/",
        "author": "Alice",
        "licence": "Pexels License",
        "licence_url": "https://www.pexels.com/license/",
    }
    c = src.credit(meta)
    assert c["source"] == "pexels"
    assert c["author"] == "Alice"
    assert c["licence"] == "Pexels License"
    assert c["licence_url"] == "https://www.pexels.com/license/"


# ---------------------------------------------------------------- the title of a video (the record has no title field)
def _video(url, author="Jane Videographer", vid=857251):
    rec = json.loads(json.dumps(PEXELS_VIDEO_SEARCH["videos"][0]))
    rec["id"] = vid
    if url is None:
        rec.pop("url")
    else:
        rec["url"] = url
    rec["user"]["name"] = author
    return rec


@pytest.mark.parametrize("url,title", [
    ("https://www.pexels.com/video/aerial-view-of-oslo-fjord-12345/", "Aerial View of Oslo Fjord"),
    ("https://www.pexels.com/video/aerial-view-of-oslo-fjord-12345", "Aerial View of Oslo Fjord"),             # no trailing slash
    ("https://www.pexels.com/video/aerial-view-of-oslo-fjord-12345/?utm_source=api", "Aerial View of Oslo Fjord"),
    ("https://www.pexels.com/video/a-man-walking-on-the-beach-3571264/", "A Man Walking on the Beach"),
    ("https://www.pexels.com/video/waves-crashing-on-rocks-8-9/", "Waves Crashing on Rocks 8"),                 # only the last number is the id
    ("https://www.pexels.com/video/caf%C3%A9-in-paris-777/", "Café in Paris"),
    ("https://www.pexels.com/it-it/video/vista-aerea-del-fiordo-12345/", "Vista Aerea Del Fiordo"),             # a language prefix is not part of it
])
def test_video_title_comes_from_the_slug(url, title):
    assert parse_video(_video(url))["title"] == title


@pytest.mark.parametrize("url", [
    "https://www.pexels.com/video/857251/",              # a page URL with no words: today's fixture
    "https://www.pexels.com/video/12345/?x=1",
    "https://www.pexels.com/video/-12345/",
    "https://www.pexels.com/video//",
    "https://www.pexels.com/",
    "not a url",
    "https://www.pexels.com/search/videos/oslo-fjord/",       # a search page, not a video page
    "",
    None,
])
def test_video_title_falls_back_to_the_author(url):
    assert parse_video(_video(url))["title"] == "Video của Jane Videographer"


def test_video_title_with_neither_slug_nor_author():
    t = parse_video(_video(None, author=""))["title"]
    assert "857251" in t and t.strip() and "None" not in t


def test_video_title_is_one_short_line():
    t = parse_video(_video("https://www.pexels.com/video/" + "very-long-words-" * 30 + "99/"))["title"]
    assert len(t) <= 120 and "\n" not in t


def test_video_title_reaches_search_results_and_the_page_url_is_kept():
    def opener(req, **kw):
        return MockResponse({"videos": [_video("https://www.pexels.com/video/aerial-view-of-oslo-fjord-12345/")]})
    v = PexelsSource(key="k", opener=opener, sleep=lambda s: None).search("oslo", kind="video")[0]
    assert v["title"] == "Aerial View of Oslo Fjord" and v["page_url"].endswith("-12345/")
