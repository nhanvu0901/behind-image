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
    # CHANGED (polite client): this used to be a 429 retried four times; a 429 is now never retried like this (see test_http.py)
    waits = []
    calls = {"n": 0}
    def boom():
        calls["n"] += 1
        return err(500)
    src, _ = make([("commons.wikimedia.org", boom)], sleep=waits.append)
    with pytest.raises(http.MediaHTTPError) as ei:
        src.search("x")
    assert calls["n"] == 4 and ei.value.status == 500
    assert waits == [2.0, 4.0, 8.0]


def test_a_429_is_not_retried_four_times():
    waits = []
    calls = {"n": 0}
    def boom():
        calls["n"] += 1
        return err(429)
    src, _ = make([("commons.wikimedia.org", boom)], sleep=waits.append)
    with pytest.raises(http.MediaHTTPError) as ei:
        src.search("x")
    assert calls["n"] == 1 and waits == [] and ei.value.status == 429 and ei.value.rate_limited and ei.value.retry_after is None


def test_backoff_recovers_on_5xx():
    seq = [err(502), err(500)]
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
    # 8000 x 5000 = 40 megapixels (> 25 MP). Wikimedia only serves its standard widths: the largest that fits is 3840.
    meta = {
        "source_id": "File:Huge_Landscape.jpg",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Huge_Landscape.jpg",
        "width": 8000,
        "height": 5000,
        "size": 30_000_000,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Huge_Landscape.jpg/3840px-Huge_Landscape.jpg"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Huge Landscape.jpg",
                    "imageinfo": [
                        {
                            "thumburl": thumb_url,
                            "url": meta["url"],
                            "width": 3840,
                            "height": 2400,
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
        ("3840px-Huge_Landscape.jpg", img_data),
    ])
    dest = tmp_path / "huge.jpg"
    out = src.download(meta, dest)
    assert out.exists()
    assert len(net.urls) == 2
    # First URL queried commons API with a standard width
    assert "iiurlwidth=3840" in net.urls[0]
    assert "Huge" in net.urls[0]
    # Second URL downloaded the thumb_url, NOT meta["url"]
    assert net.urls[1] == thumb_url


def test_download_large_megapixels_portrait_requests_scaled_rendering(tmp_path):
    # 5000 x 8000 = 40 megapixels (> 25 MP). Height > Width (portrait). 3750 is not a Wikimedia width: the largest standard
    # width is 3840, which gives 3840 x 6144 = 23.6 MP, under the 25 MP the app calls too big.
    meta = {
        "source_id": "File:Huge_Portrait.jpg",
        "kind": "image",
        "url": "https://upload.wikimedia.org/Huge_Portrait.jpg",
        "width": 5000,
        "height": 8000,
        "size": 35_000_000,
    }
    thumb_url = "https://upload.wikimedia.org/thumb/Huge_Portrait.jpg/3840px-Huge_Portrait.jpg"
    api_resp = {
        "query": {
            "pages": [
                {
                    "title": "File:Huge Portrait.jpg",
                    "imageinfo": [
                        {"thumburl": thumb_url, "url": meta["url"], "width": 3840, "height": 6144}
                    ],
                }
            ]
        }
    }
    img_data = png_bytes(20, 20)
    src, net = make([
        ("commons.wikimedia.org", api_resp),
        ("3840px-Huge_Portrait.jpg", img_data),
    ])
    dest = tmp_path / "huge_portrait.jpg"
    out = src.download(meta, dest)
    assert out.exists()
    assert "iiurlwidth=3840" in net.urls[0]
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
    thumb_url = "https://upload.wikimedia.org/thumb/Heavy.png/3840px-Heavy.png"
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
        ("3840px-Heavy.png", img_data),
    ])
    dest = tmp_path / "heavy.png"
    out = src.download(meta, dest)
    assert out.exists()
    assert "iiurlwidth=3840" in net.urls[0]          # 4000 px wide original, 48 MB: the largest standard width below it
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
    thumb_url = "https://upload.wikimedia.org/thumb/Giant.jpg/3840px-Giant.jpg"
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
        ("3840px-Giant.jpg", b"0" * (61 * 1024 * 1024)),
    ])
    dest = tmp_path / "giant.jpg"
    with pytest.raises(http.FileTooLarge) as exc_info:
        src.download(meta, dest)
    assert exc_info.value.code == "too_large"
    assert isinstance(exc_info.value, ValueError)
    assert not dest.exists()



# ---------------------------------------------------------------- only the widths Wikimedia serves
def test_the_standard_widths_are_the_documented_list():
    # https://www.mediawiki.org/wiki/Common_thumbnail_sizes (`$wgThumbnailSteps` of Wikimedia production)
    assert commons.THUMB_STEPS == (20, 40, 60, 120, 250, 330, 500, 960, 1280, 1920, 3840)
    assert commons.CARD_THUMB_WIDTH in commons.THUMB_STEPS


@pytest.mark.parametrize("w,h,want", [
    (6703, 8322, 3840),          # the owner's case: the rendition is 3840 x 4767
    (8000, 5000, 3840), (5000, 8000, 3840),      # 3840 x 6144 is 23.6 MP: not "too big" by the app's rule
    (4000, 4000, 3840), (3000, 3000, 1920), (3840, 2000, 1920), (1300, 1250, 1280),
    (20000, 20000, 3840), (100, 100, 60), (20, 20, None), (0, 0, 3840), (0, 5000, 3840),
])
def test_rendition_width_is_a_standard_width_smaller_than_the_original(w, h, want):
    got = commons.rendition_width(w, h)
    assert got == want
    if got:
        assert got in commons.THUMB_STEPS and (not (w and h) or got < w)


def test_a_rendition_never_exceeds_the_app_limits_when_a_standard_width_can_meet_them():
    for w, h in [(6703, 8322), (9000, 9000), (7000, 3600), (5000, 8000), (12000, 2000), (3000, 20000), (4000, 4000)]:
        got = commons.rendition_width(w, h)
        rh = h * got / w
        assert max(got, rh) <= commons.SCALED_LONGEST_SIDE or got * rh <= commons.MAX_ORIGINAL_PIXELS, (w, h, got)
        bigger = [s for s in commons.THUMB_STEPS if got < s < w]                      # and no larger standard width would have met them
        assert all(max(s, h * s / w) > commons.SCALED_LONGEST_SIDE and s * h * s / w > commons.MAX_ORIGINAL_PIXELS for s in bigger), (w, h, got)


def test_the_search_and_the_meta_ask_for_a_standard_card_width():
    pages = load("commons_search.json")["query"]["pages"]
    src, net = make([("commons.wikimedia.org", {"query": {"pages": [pages[1]]}})])
    src.search("x")
    src.fetch_meta("File:x.jpg")
    assert all("iiurlwidth=330" in u for u in net.urls) and len(net.urls) == 2


def test_a_thumb_address_equal_to_the_original_is_not_taken_for_a_rendition(tmp_path):
    meta = {"source_id": "File:Huge.png", "kind": "image", "url": "https://upload.wikimedia.org/Huge.png",
            "width": 8000, "height": 5000, "size": 30_000_000}
    api_resp = {"query": {"pages": [{"title": "File:Huge.png", "imageinfo": [{"thumburl": meta["url"], "url": meta["url"]}]}]}}
    src, net = make([("commons.wikimedia.org", api_resp), ("upload.wikimedia.org/Huge.png", png_bytes(20, 20))])
    src.download(meta, tmp_path / "h.png")
    assert net.urls[1] == meta["url"]
