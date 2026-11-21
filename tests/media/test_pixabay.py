"""Tests for Pixabay source (photos and videos). Tested with fixtures only (no network)."""
from pathlib import Path
import json
import pytest

from bti.media.errors import NotFound
from bti.media.sources.pixabay import PixabaySource

PIXABAY_IMAGE_SEARCH = {
    "total": 100,
    "totalHits": 50,
    "hits": [
        {
            "id": 195893,
            "pageURL": "https://pixabay.com/photos/blossom-bloom-flower-195893/",
            "type": "photo",
            "tags": "blossom, bloom, flower",
            "previewURL": "https://cdn.pixabay.com/photo/preview_195893.jpg",
            "previewWidth": 150,
            "previewHeight": 99,
            "webformatURL": "https://pixabay.com/photo/webformat_195893.jpg",
            "webformatWidth": 640,
            "webformatHeight": 426,
            "largeImageURL": "https://pixabay.com/photo/large_195893.jpg",
            "imageWidth": 4000,
            "imageHeight": 2250,
            "imageSize": 4731420,
            "user": "FlowerPhotographer",
        }
    ],
}

PIXABAY_VIDEO_SEARCH = {
    "total": 42,
    "totalHits": 42,
    "hits": [
        {
            "id": 125,
            "pageURL": "https://pixabay.com/videos/id-125/",
            "type": "film",
            "tags": "flowers, yellow, blossom",
            "duration": 15,
            "picture_id": "529927645",
            "videos": {
                "large": {
                    "url": "https://player.vimeo.com/external/125.large.mp4",
                    "width": 1920,
                    "height": 1080,
                    "size": 6615235,
                    "thumbnail": "https://i.vimeocdn.com/video/529927645_640x360.jpg",
                },
                "medium": {
                    "url": "https://player.vimeo.com/external/125.medium.mp4",
                    "width": 1280,
                    "height": 720,
                    "size": 3562080,
                    "thumbnail": "https://i.vimeocdn.com/video/529927645_640x360.jpg",
                },
            },
            "user": "VideoCreator",
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


def test_pixabay_without_key_is_not_called(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    src = PixabaySource(key=None)
    assert not src.has_key()
    assert src.search("flowers") == []
    assert src.search("flowers", kind="video") == []


def test_pixabay_image_search():
    def mock_opener(req, **kw):
        assert "key=test-pixabay-key" in req.full_url
        assert "image_type=photo" in req.full_url
        return MockResponse(PIXABAY_IMAGE_SEARCH)

    src = PixabaySource(key="test-pixabay-key", opener=mock_opener, sleep=lambda s: None)
    assert src.has_key()
    results = src.search("flower", kind="image", limit=10)
    assert len(results) == 1
    r = results[0]
    assert r["source"] == "pixabay"
    assert r["source_id"] == "195893"
    assert r["title"] == "blossom, bloom, flower"
    assert r["kind"] == "image"
    assert r["mime"] == "image/jpeg"
    assert r["width"] == 4000
    assert r["height"] == 2250
    assert r["author"] == "FlowerPhotographer"
    assert r["licence"] == "Pixabay Content License"
    assert r["page_url"] == "https://pixabay.com/photos/blossom-bloom-flower-195893/"
    assert r["url"] == "https://pixabay.com/photo/large_195893.jpg"


def test_pixabay_video_search():
    def mock_opener(req, **kw):
        assert "key=test-pixabay-key" in req.full_url
        assert "api/videos" in req.full_url
        return MockResponse(PIXABAY_VIDEO_SEARCH)

    src = PixabaySource(key="test-pixabay-key", opener=mock_opener, sleep=lambda s: None)
    results = src.search("blossom", kind="video", limit=5)
    assert len(results) == 1
    v = results[0]
    assert v["source"] == "pixabay"
    assert v["source_id"] == "125"
    assert v["kind"] == "video"
    assert v["mime"] == "video/mp4"
    assert v["width"] == 1920
    assert v["height"] == 1080
    assert v["duration"] == 15.0
    assert v["author"] == "VideoCreator"
    assert v["url"] == "https://player.vimeo.com/external/125.large.mp4"
    assert v["licence"] == "Pixabay Content License"


def test_pixabay_fetch_meta_image():
    def mock_opener(req, **kw):
        if "id=195893" in req.full_url:
            return MockResponse(PIXABAY_IMAGE_SEARCH)
        return MockResponse({"total": 0, "hits": []})

    src = PixabaySource(key="test-key", opener=mock_opener, sleep=lambda s: None)
    meta = src.fetch_meta("195893")
    assert meta["source_id"] == "195893"
    assert meta["author"] == "FlowerPhotographer"


def test_pixabay_fetch_meta_video():
    def mock_opener(req, **kw):
        if "api/videos" in req.full_url and "id=125" in req.full_url:
            return MockResponse(PIXABAY_VIDEO_SEARCH)
        return MockResponse({"total": 0, "hits": []})

    src = PixabaySource(key="test-key", opener=mock_opener, sleep=lambda s: None)
    meta = src.fetch_meta("125")
    assert meta["source_id"] == "125"
    assert meta["kind"] == "video"
    assert meta["duration"] == 15.0


def test_pixabay_credit():
    src = PixabaySource(key="test-key")
    meta = {
        "source": "pixabay",
        "page_url": "https://pixabay.com/photos/123/",
        "author": "Bob",
        "licence": "Pixabay Content License",
        "licence_url": "https://pixabay.com/service/license-summary/",
    }
    c = src.credit(meta)
    assert c["source"] == "pixabay"
    assert c["author"] == "Bob"
    assert c["licence"] == "Pixabay Content License"
    assert c["licence_url"] == "https://pixabay.com/service/license-summary/"
