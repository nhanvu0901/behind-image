import urllib.error

import pytest

from bti.media import http
from bti.media.errors import ImageTooSmall, NotFound
from bti.media.sources import commons
from bti.media.sources.commons import CommonsSource, credit, parse_page

from conftest import FakeNet, load, png_bytes


def make(routes, sleep=lambda s: None, **kw):
    net = FakeNet(routes)
    return CommonsSource(opener=net, sleep=sleep, **kw), net


def test_parse_page_fields():
    pages = {p["pageid"]: p for p in load("commons_search.json")["query"]["pages"]}
    m = parse_page(pages[2])
    assert m["source"] == "commons" and m["kind"] == "image"
    assert m["title"] == "The Arnolfini Portrait"
    assert m["author"] == "Jan van Eyck"                  # HTML stripped
    assert m["description"] == "Oil on oak panel"
    assert (m["width"], m["height"]) == (4386, 6000) and m["licence"] == "Public domain"
    assert m["thumb_url"].startswith("https://upload.wikimedia.org/thumb")
    assert parse_page({"title": "File:x.jpg", "missing": True}) is None


def test_search_images_filters_video_and_orders():
    src, net = make([("commons.wikimedia.org", load("commons_search.json"))])
    res = src.search("Arnolfini Portrait", "image", 10)
    assert [r["source_id"].split(":")[1][:12] for r in res][0].startswith("Arnolfini s")   # index order
    assert all(r["kind"] == "image" for r in res) and len(res) == 4
    url = net.urls[0]
    assert "filetype%3Abitmap" in url and "gsrnamespace=6" in url
    assert "url%7Csize%7Cmime%7Cextmetadata" in url


def test_search_video_filters_by_mime():
    src, net = make([("commons.wikimedia.org", load("commons_search.json"))])
    res = src.search("Arnolfini", "video", 10)
    assert [r["mime"] for r in res] == ["video/webm"]
    assert "filetype%3Avideo" in net.urls[0]


def test_fetch_meta_and_not_found():
    page = load("commons_search.json")["query"]["pages"][0]
    src, net = make([("commons.wikimedia.org", {"query": {"pages": [page]}})])
    assert src.fetch_meta("Arnolfini_nc.jpg")["title"] == "The Arnolfini Portrait"
    assert "titles=File%3A" in net.urls[0]
    src2, _ = make([("commons.wikimedia.org", {"query": {"pages": [{"title": "File:x", "missing": True}]}})])
    with pytest.raises(NotFound):
        src2.fetch_meta("File:x")


def test_credit_line():
    pages = {p["pageid"]: p for p in load("commons_search.json")["query"]["pages"]}
    c = credit(parse_page(pages[1]))
    assert c == {"source": "commons", "source_url": "https://commons.wikimedia.org/wiki/File:Arnolfini_small.png",
                 "author": "Someone", "licence": "CC BY-SA 4.0",
                 "licence_url": "https://creativecommons.org/licenses/by-sa/4.0"}
    c2 = credit(parse_page(pages[2]))
    assert c2["licence"] == "PD" and c2["author"] == "Jan van Eyck"
    assert credit({"page_url": "u"})["author"] == "unknown"


def test_download_refuses_small_image_without_fetching(tmp_path):
    pages = {p["pageid"]: p for p in load("commons_search.json")["query"]["pages"]}
    meta = parse_page(pages[1])                       # 800x600
    src, net = make([])
    with pytest.raises(ImageTooSmall):
        src.download(meta, tmp_path / "a.png")
    assert net.urls == [] and not (tmp_path / "a.png").exists()


def test_download_min_is_configurable(tmp_path):
    pages = {p["pageid"]: p for p in load("commons_search.json")["query"]["pages"]}
    meta = parse_page(pages[1])
    src, net = make([("upload.wikimedia.org", png_bytes(8, 6))])
    out = src.download(meta, tmp_path / "a.png", min_short_side=500)
    assert out.read_bytes()[:4] == b"\x89PNG"
    src2, _ = make([], min_short_side=700)
    with pytest.raises(ImageTooSmall):
        src2.download(meta, tmp_path / "b.png")


def test_download_unknown_size_checked_after(tmp_path):
    meta = {"source_id": "File:x.png", "kind": "image", "url": "https://upload.wikimedia.org/x.png"}
    src, _ = make([("upload.wikimedia.org", png_bytes(40, 30))])
    with pytest.raises(ImageTooSmall):
        src.download(meta, tmp_path / "x.png")
    assert not (tmp_path / "x.png").exists()


def test_download_size_cap(tmp_path):
    meta = {"source_id": "File:x.png", "kind": "image", "url": "https://upload.wikimedia.org/x.png",
            "width": 3000, "height": 3000, "size": 10_000}
    src, net = make([("upload.wikimedia.org", b"x" * 10_000)])
    with pytest.raises(http.MediaHTTPError):
        src.download(meta, tmp_path / "x.png", max_bytes=5_000)
    assert net.urls == []                              # declared size refused up front
    meta["size"] = 0
    with pytest.raises(http.MediaHTTPError):
        src.download(meta, tmp_path / "y.png", max_bytes=5_000)    # streamed cap
    assert not list(tmp_path.glob("y.png*"))


def err(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def test_backoff_grows_and_gives_up_after_four():
    waits = []
    calls = {"n": 0}
    def boom():
        calls["n"] += 1
        return err(429)
    src, _ = make([("commons.wikimedia.org", boom)], sleep=waits.append)
    with pytest.raises(http.MediaHTTPError) as ei:
        src.search("x")
    assert calls["n"] == 4 and ei.value.status == 429
    assert waits == [2.0, 4.0, 8.0]


def test_backoff_recovers_on_5xx():
    seq = [err(503), err(500)]
    def flaky():
        return seq.pop(0) if seq else load("commons_search.json")
    waits = []
    src, _ = make([("commons.wikimedia.org", flaky)], sleep=waits.append)
    assert src.search("x", "image", 5)
    assert len(waits) == 2 and waits[1] > waits[0]


def test_no_retry_on_404():
    waits = []
    src, net = make([("commons.wikimedia.org", lambda: err(404))], sleep=waits.append)
    with pytest.raises(http.MediaHTTPError):
        src.search("x")
    assert waits == [] and len(net.urls) == 1


def test_user_agent_is_generic():
    assert "@" not in http.USER_AGENT and "nhanvu" not in http.USER_AGENT.lower()


def test_download_large_megapixels_requests_scaled_rendering(tmp_path):
    # 8000 x 5000 = 40 megapixels (> 25 MP). Width >= Height, so target_w = 6000.
    meta = {
        "source_id": "File:Huge_Landscape.jpg",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Huge_Landscape.jpg",
        "width": 8000,
        "height": 5000,
        "size": 30_000_000,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Huge_Landscape.jpg/6000px-Huge_Landscape.jpg"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Huge Landscape.jpg",
                    "imageinfo": [
                        {
                            "thumburl": thumb_url,
                            "url": meta["url"],
                            "width": 6000,
                            "height": 3750,
                            "size": 8_000_000,
                            "mime": "image/jpeg",
                        }
                    ],
                }
            ]
        }
    }
    img_data = png_bytes(20, 20)
    src, net = make([
        ("commons.wikimedia.org", api_resp),
        ("6000px-Huge_Landscape.jpg", img_data),
    ])
    dest = tmp_path / "huge.jpg"
    out = src.download(meta, dest)
    assert out.exists()
    assert len(net.urls) == 2
    # First URL queried commons API with iiurlwidth=6000
    assert "iiurlwidth=6000" in net.urls[0]
    assert "Huge" in net.urls[0]
    # Second URL downloaded the thumb_url, NOT meta["url"]
    assert net.urls[1] == thumb_url


def test_download_large_megapixels_portrait_requests_scaled_rendering(tmp_path):
    # 5000 x 8000 = 40 megapixels (> 25 MP). Height > Width (portrait).
    # Longest side is height (8000). Target width = round(5000 * 6000 / 8000) = 3750.
    meta = {
        "source_id": "File:Huge_Portrait.jpg",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Huge_Portrait.jpg",
        "width": 5000,
        "height": 8000,
        "size": 35_000_000,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Huge_Portrait.jpg/3750px-Huge_Portrait.jpg"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Huge Portrait.jpg",
                    "imageinfo": [
                        {"thumburl": thumb_url, "url": meta["url"], "width": 3750, "height": 6000}
                    ],
                }
            ]
        }
    }
    img_data = png_bytes(20, 20)
    src, net = make([
        ("commons.wikimedia.org", api_resp),
        ("3750px-Huge_Portrait.jpg", img_data),
    ])
    dest = tmp_path / "huge_portrait.jpg"
    out = src.download(meta, dest)
    assert out.exists()
    assert "iiurlwidth=3750" in net.urls[0]
    assert net.urls[1] == thumb_url


def test_download_large_bytes_requests_scaled_rendering(tmp_path):
    # 4000 x 4000 = 16 MP (< 25 MP), but 48 MB (> 40 MB).
    meta = {
        "source_id": "File:Heavy.png",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Heavy.png",
        "width": 4000,
        "height": 4000,
        "size": 48 * 1024 * 1024,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Heavy.png/6000px-Heavy.png"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Heavy.png",
                    "imageinfo": [{"thumburl": thumb_url, "url": meta["url"]}],
                }
            ]
        }
    }
    img_data = png_bytes(20, 20)
    src, net = make([
        ("commons.wikimedia.org", api_resp),
        ("6000px-Heavy.png", img_data),
    ])
    dest = tmp_path / "heavy.png"
    out = src.download(meta, dest)
    assert out.exists()
    assert "iiurlwidth=6000" in net.urls[0]
    assert net.urls[1] == thumb_url


def test_download_over_60mb_after_scaling_refused_with_code(tmp_path):
    meta = {
        "source_id": "File:Giant.jpg",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Giant.jpg",
        "width": 9000,
        "height": 9000,
        "size": 50 * 1024 * 1024,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Giant.jpg/6000px-Giant.jpg"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Giant.jpg",
                    "imageinfo": [{"thumburl": thumb_url, "url": meta["url"]}],
                }
            ]
        }
    }
    # Download response is 61 MB (> 60 MB cap)
    src, net = make([
        ("commons.wikimedia.org", api_resp),
        ("6000px-Giant.jpg", b"0" * (61 * 1024 * 1024)),
    ])
    dest = tmp_path / "giant.jpg"
    with pytest.raises(http.FileTooLarge) as exc_info:
        src.download(meta, dest)
    assert exc_info.value.code == "too_large"
    assert isinstance(exc_info.value, ValueError)
    assert not dest.exists()

