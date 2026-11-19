"""mediafix3: a Commons image is downloaded as the largest standard-width rendition that is not wider than the original (when
that is at least 1920 px), because Wikimedia serves renditions to the server and refuses its originals (HTTP 429, Retry-After
120, for hours). Fakes only: no request leaves the test."""
import io
import json
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest
from PIL import Image

from bti.media import api, http
from bti.media.errors import ImageTooSmall
from bti.media.sources import commons
from bti.media.sources.commons import CommonsSource

from conftest import FakeResp, png_bytes

MB = 1024 * 1024
ORIG = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Munch.jpg"
TITLE = "File:Munch.jpg"


def thumb(w, host="thumb.wikimedia.org", name="Munch.jpg"):
    return f"https://{host}/wikipedia/commons/thumb/a/ab/Munch.jpg/{w}px-{name}"


def jpeg(w, h):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 110, 100)).save(buf, "JPEG", quality=60)
    return buf.getvalue()


def refused(wait="120"):
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": wait}, None)


class Wiki:
    """A fake Wikimedia. The API answers with the file's metadata and, for `iiurlwidth=N`, `thumburl` = the rendition address.
    `orig` / `thumbs` are what a GET of the original / of a rendition answers: bytes, an exception, or (thumbs) a dict by width."""

    def __init__(self, w, h, *, mime="image/jpeg", size=2 * MB, orig=b"ORIGINAL", thumbs=b"RENDITION", thumburl="rendition",
                 thumb_host="thumb.wikimedia.org", url=ORIG, thumb_name="Munch.jpg"):
        self.w, self.h, self.mime, self.size, self.url = w, h, mime, size, url
        self.orig, self.thumbs, self.thumburl, self.thumb_host, self.thumb_name = orig, thumbs, thumburl, thumb_host, thumb_name
        self.urls = []

    # ---- what the tests read back
    def api_calls(self):
        return [u for u in self.urls if "api.php" in u]

    def widths_asked(self):
        return [int(parse_qs(urlparse(u).query)["iiurlwidth"][0]) for u in self.api_calls()]

    def gets(self):
        return [u for u in self.urls if "api.php" not in u]

    # ---- the fake itself
    def _page(self, width):
        ii = {"url": self.url, "descriptionurl": "https://commons.wikimedia.org/wiki/" + TITLE, "width": self.w, "height": self.h,
              "size": self.size, "mime": self.mime,
              "extmetadata": {"LicenseShortName": {"value": "Public domain"}, "Artist": {"value": "Edvard Munch"}}}
        if self.thumburl == "rendition":
            ii["thumburl"] = thumb(width, self.thumb_host, self.thumb_name)
        elif self.thumburl == "original":
            ii["thumburl"] = self.url
        return {"title": TITLE, "index": 1, "imageinfo": [ii]}

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        if "api.php" in url:
            q = parse_qs(urlparse(url).query)
            return FakeResp(json.dumps({"query": {"pages": [self._page(int(q["iiurlwidth"][0]))]}}).encode())
        if url == self.url:
            out = self.orig
        else:
            width = int(url.rsplit("/", 1)[1].split("px-")[0].split("-")[-1])
            out = self.thumbs[width] if isinstance(self.thumbs, dict) else self.thumbs
        if isinstance(out, Exception):
            raise out
        return FakeResp(out)

    def meta(self, **over):
        m = {"source": "commons", "source_id": TITLE, "kind": "image", "url": self.url, "width": self.w, "height": self.h,
             "size": self.size, "mime": self.mime}
        m.update(over)
        return m


def source(wiki, sleeps=None, **kw):
    return CommonsSource(opener=wiki, sleep=(sleeps.append if sleeps is not None else (lambda s: None)), **kw)


# ---------------------------------------------------------------- the rule, as a table
@pytest.mark.parametrize("w,h,size,want", [
    (3048, 4000, 0, 1920),                       # the owner's file (Munch, self-portrait): 1920 x 2520
    (3870, 3042, 0, 3840), (6703, 8322, 0, 3840), (5000, 8000, 0, 3840), (8000, 5000, 0, 3840),
    (2400, 1800, 0, 1920), (1921, 1200, 0, 1920), (3000, 3000, 0, 1920),
    (1920, 1080, 0, None), (3840, 2160, 0, None),            # exactly a standard width: the rendition would BE the original
    (1919, 1200, 0, None), (1800, 2400, 0, None), (1500, 1300, 0, None), (1280, 720, 0, None),   # narrower than 1920: the original
    (1300, 1250, 48 * MB, 1280),                 # heavy and narrow: the older rule still applies (the largest width below it)
    (3840, 2160, 45 * MB, 1920),                 # heavy and exactly a standard width: the width below, as before
    (4000, 4000, 48 * MB, 3840),
    (2500, 30000, 0, 1280),                      # no width of 1920 or more is within the limits: the older rule (1280)
    (0, 0, 0, None), (0, 0, 48 * MB, 3840), (0, 5000, 0, None),
])
def test_rendition_target_table(w, h, size, want):
    assert commons.rendition_target(w, h, size) == want
    if want:
        assert want in commons.THUMB_STEPS


def test_a_rendition_is_never_wider_than_the_original_nor_over_the_limits():
    for w, h in [(3048, 4000), (3870, 3042), (6703, 8322), (5000, 8000), (2400, 1800), (1921, 1200), (9000, 9000), (7000, 3600)]:
        t = commons.rendition_target(w, h)
        rh = h * t / w
        assert t <= w and t >= commons.MIN_RENDITION_WIDTH
        assert max(t, rh) <= commons.SCALED_LONGEST_SIDE or t * rh <= commons.MAX_ORIGINAL_PIXELS, (w, h, t)
        assert not [s for s in commons.THUMB_STEPS if t < s <= w and (max(s, h * s / w) <= 6000 or s * h * s / w <= 25_000_000)], (w, h, t)


def test_expected_size_is_the_renditions_size():
    assert commons.expected_size({"kind": "image", "width": 3048, "height": 4000}) == (1920, 2520)
    assert commons.expected_size({"kind": "image", "width": 3870, "height": 3042}) == (3840, 3018)
    assert commons.expected_size({"kind": "image", "width": 1500, "height": 1300}) == (1500, 1300)
    assert commons.expected_size({"kind": "video", "width": 8000, "height": 5000}) == (8000, 5000)
    assert commons.expected_size({"kind": "image"}) == (0, 0)


# ---------------------------------------------------------------- download: the incident
def test_the_owners_file_is_downloaded_as_a_1920_rendition_and_the_original_is_never_requested(tmp_path):
    wiki = Wiki(3048, 4000, orig=refused("120"))          # the original answers 429 as it did for hours
    out = source(wiki).download(wiki.meta(), tmp_path / "munch.jpg")
    assert out == tmp_path / "munch.jpg" and out.read_bytes() == b"RENDITION"
    assert wiki.widths_asked() == [1920]
    assert wiki.gets() == [thumb(1920)] and ORIG not in wiki.urls


@pytest.mark.parametrize("w,h,want", [(3870, 3042, 3840), (6703, 8322, 3840), (5000, 8000, 3840), (2400, 1800, 1920), (1921, 1200, 1920)])
def test_the_width_asked_for_follows_the_rule(tmp_path, w, h, want):
    wiki = Wiki(w, h, orig=refused())
    source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert wiki.widths_asked() == [want] and wiki.gets() == [thumb(want)]


def test_an_image_narrower_than_1920_is_downloaded_as_the_original_with_no_api_call(tmp_path):
    wiki = Wiki(1500, 1300)
    out = source(wiki).download(wiki.meta(), tmp_path / "x.jpg")
    assert out.read_bytes() == b"ORIGINAL" and wiki.urls == [ORIG]


@pytest.mark.parametrize("w,h", [(1920, 1080), (3840, 2160)])
def test_an_original_that_is_exactly_a_standard_width_is_the_original(tmp_path, w, h):
    wiki = Wiki(w, h)
    out = source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert out.read_bytes() == b"ORIGINAL" and wiki.urls == [ORIG]            # no rendition exists, so no API call either


def test_an_api_answer_whose_thumburl_is_the_original_is_no_rendition(tmp_path):
    wiki = Wiki(3048, 4000, thumburl="original")
    out = source(wiki).download(wiki.meta(), tmp_path / "x.jpg")
    assert out.read_bytes() == b"ORIGINAL" and wiki.widths_asked() == [1920] and wiki.gets() == [ORIG]


def test_an_api_answer_without_a_thumburl_falls_back_to_the_original(tmp_path):
    wiki = Wiki(3048, 4000, thumburl="none")
    assert source(wiki).download(wiki.meta(), tmp_path / "x.jpg").read_bytes() == b"ORIGINAL"


@pytest.mark.parametrize("mime,kind", [("video/webm", "video"), ("application/pdf", "other"), ("application/ogg", "video")])
def test_a_file_that_is_not_an_image_never_gets_a_rendition(tmp_path, mime, kind):
    wiki = Wiki(8000, 5000, mime=mime, size=30 * MB)
    out = source(wiki).download(wiki.meta(kind=kind), tmp_path / "x.bin")
    assert out.read_bytes() == b"ORIGINAL" and wiki.urls == [ORIG]


# ---------------------------------------------------------------- the size floor is about what is stored
def test_the_floor_is_applied_to_the_rendition_before_any_request(tmp_path):
    wiki = Wiki(3048, 4000)
    src = source(wiki)
    out = src.download(wiki.meta(), tmp_path / "ok.jpg", min_short_side=1920)           # 1920 x 2520: short side 1920
    assert out.exists()
    wiki2 = Wiki(3048, 4000)
    with pytest.raises(ImageTooSmall):
        source(wiki2).download(wiki2.meta(), tmp_path / "no.jpg", min_short_side=1921)
    assert wiki2.urls == [] and not (tmp_path / "no.jpg").exists()


def test_an_original_over_the_floor_whose_rendition_is_under_it_is_refused_as_what_would_be_stored(tmp_path):
    wiki = Wiki(2000, 1200)                              # the original's short side is 1200 (passes); the 1920 x 1152 rendition is not
    with pytest.raises(ImageTooSmall) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=1200)
    assert "1920x1152" in str(e.value) and wiki.urls == []
    wiki2 = Wiki(2000, 1200)
    source(wiki2).download(wiki2.meta(), tmp_path / "y.jpg", min_short_side=1152)       # exactly the rendition's short side: passes
    assert wiki2.widths_asked() == [1920]


def test_the_default_floor_of_the_source_still_refuses_a_small_original_without_a_request(tmp_path):
    wiki = Wiki(800, 600)
    with pytest.raises(ImageTooSmall):
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg")
    assert wiki.urls == []


# ---------------------------------------------------------------- a refused original: the next width down, or the refusal as today
def test_a_refused_narrow_original_takes_the_largest_width_below_it(tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("120"))
    out = source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=1100)       # 1280 x 1109 passes 1100
    assert out.read_bytes() == b"RENDITION"
    assert wiki.urls == [ORIG, wiki.api_calls()[0], thumb(1280)] and wiki.widths_asked() == [1280]
    assert wiki.urls.count(ORIG) == 1                                         # the original was asked for once: no extra retry


def test_a_refused_exact_standard_width_original_takes_the_width_below(tmp_path):
    wiki = Wiki(1920, 1280, orig=refused("120"))
    out = source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert out.read_bytes() == b"RENDITION" and wiki.widths_asked() == [1280]


def test_a_fallback_that_fails_the_floor_reports_the_refusal_and_asks_for_nothing_more(tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("120"))
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=1200)       # 1280 x 1109 < 1200
    assert e.value.rate_limited and e.value.retry_after == 120 and e.value.status == 429
    assert wiki.urls == [ORIG] and not (tmp_path / "x.jpg").exists()


def test_with_no_floor_the_fallback_is_taken_whatever_its_size(tmp_path):
    # the facade imports with min_short_side=0 (the floor is only a flag there): a refused original still becomes a picture
    wiki = Wiki(1500, 1300, orig=refused("120"))
    assert source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0).read_bytes() == b"RENDITION"


def test_no_rendition_address_for_the_fallback_reports_the_refusal(tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("120"), thumburl="none")
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert e.value.rate_limited and e.value.retry_after == 120


def test_a_fallback_that_is_refused_too_reports_the_originals_wait(tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("120"), thumbs=refused("60"))
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert e.value.rate_limited and e.value.retry_after == 120
    assert not list(tmp_path.glob("x.jpg*"))                                  # nothing left behind


def test_a_refusal_with_no_wait_time_is_reported_without_one(tmp_path):
    nowait = urllib.error.HTTPError("u", 429, "x", {}, None)
    wiki = Wiki(300, 300, orig=nowait, thumbs=nowait)
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)        # the largest width below 300 is 250: tried, refused too
    assert e.value.rate_limited and e.value.retry_after is None and wiki.widths_asked() == [250]


def test_only_a_rate_limit_triggers_the_fallback(tmp_path):
    for status in (403, 404, 500):
        wiki = Wiki(1500, 1300, orig=urllib.error.HTTPError("u", status, "x", {}, None))
        with pytest.raises(http.MediaHTTPError) as e:
            source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
        assert e.value.status == status and not e.value.rate_limited
        assert wiki.api_calls() == []


def test_a_rendition_that_is_refused_is_not_retried_as_the_original(tmp_path):
    wiki = Wiki(3048, 4000, thumbs=refused("120"))
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg")
    assert e.value.rate_limited and e.value.retry_after == 120
    assert ORIG not in wiki.urls


# ---------------------------------------------------------------- the polite client is unchanged
def test_a_short_retry_after_is_waited_once_then_the_original_is_not_asked_again(tmp_path):
    waits = []
    wiki = Wiki(1500, 1300, orig=refused("3"))
    out = source(wiki, waits).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert out.read_bytes() == b"RENDITION"
    assert waits == [3.0] and wiki.urls.count(ORIG) == 2                      # one honoured retry, as before, never more


def test_the_original_hosts_cooldown_does_not_block_the_rendition_host(tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("120"))
    source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert set(http._COOLDOWN) == {"upload.wikimedia.org"}                    # keyed by host: thumb.wikimedia.org was not touched
    wiki2 = Wiki(3048, 4000, orig=b"never asked")
    assert source(wiki2).download(wiki2.meta(), tmp_path / "y.jpg").read_bytes() == b"RENDITION"      # a rendition is served meanwhile
    wiki3 = Wiki(1500, 1300, orig=b"must not be sent", thumburl="none")
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki3).download(wiki3.meta(), tmp_path / "z.jpg", min_short_side=0)
    assert e.value.rate_limited and ORIG not in wiki3.urls                    # an original inside the cooldown is not even requested


def test_a_rendition_on_the_same_host_as_the_refused_original_waits_too(tmp_path):
    # the cooldown is per host on purpose (a host that said "wait" gets nothing): if the API ever answers a rendition address on
    # the original's own host, the fallback is held back by that cooldown and the original refusal is what is reported
    wiki = Wiki(1500, 1300, orig=refused("120"), thumb_host="upload.wikimedia.org")
    with pytest.raises(http.MediaHTTPError) as e:
        source(wiki).download(wiki.meta(), tmp_path / "x.jpg", min_short_side=0)
    assert e.value.rate_limited and e.value.retry_after == 120
    assert wiki.gets() == [ORIG]


# ---------------------------------------------------------------- another format than the original
def test_a_tiff_original_comes_as_a_jpeg_rendition_named_for_what_it_is(tmp_path):
    tif = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Munch.tif"
    wiki = Wiki(4000, 3000, mime="image/tiff", url=tif, thumb_name="Munch.tif.jpg", thumbs=jpeg(40, 30))
    out = source(wiki).download(wiki.meta(), tmp_path / "munch.tif")
    assert out == tmp_path / "munch.jpg" and out.is_file() and not (tmp_path / "munch.tif").exists()


def test_jpg_and_jpeg_and_tif_and_tiff_are_the_same_format():
    from bti.media.sources.commons import _beside
    from pathlib import Path
    assert _beside(Path("a/x.jpg"), "https://h/1920px-X.jpeg") == Path("a/x.jpg")
    assert _beside(Path("a/x.JPEG"), "https://h/1920px-X.jpg") == Path("a/x.JPEG")
    assert _beside(Path("a/x.tif"), "https://h/1920px-X.tiff") == Path("a/x.tif")
    assert _beside(Path("a/x.tif"), "https://h/lossy-page1-1920px-X.tif.jpg") == Path("a/x.jpg")
    assert _beside(Path("a/x.svg"), "https://h/1920px-X.svg.png") == Path("a/x.png")
    assert _beside(Path("a/x.jpg"), "https://h/no-extension") == Path("a/x.jpg")


# ---------------------------------------------------------------- through the facade: what is recorded is what is stored
@pytest.fixture
def wiki_api(monkeypatch):
    def install(wiki):
        monkeypatch.setitem(api._SOURCES, "commons", source(wiki))
        return wiki
    return install


def test_an_import_records_the_rendition_as_stored_and_the_original_as_original(wiki_api, tmp_path):
    wiki = wiki_api(Wiki(3048, 4000, orig=refused("120"), thumbs=jpeg(1920, 2520)))
    res = api.import_candidate(tmp_path / "p", "commons", TITLE)
    a = res["asset"]
    assert (a["width"], a["height"]) == (1920, 2520)                           # the pixels of the stored file
    assert (a["original_width"], a["original_height"]) == (3048, 4000)         # what Commons says about the original
    assert api.stored_image_size(tmp_path / "p" / a["file"]) == (1920, 2520)
    assert a["credit"]["flag"] is None
    assert ORIG not in wiki.urls                                               # the refused address was never asked
    again = api.import_candidate(tmp_path / "p", "commons", TITLE)
    assert again == res and wiki.urls.count(thumb(1920)) == 1                  # no second download


def test_the_stored_size_and_not_the_originals_decides_the_small_flag(wiki_api, tmp_path):
    wiki_api(Wiki(2000, 1200, thumbs=jpeg(1920, 1152)))
    a = api.import_candidate(tmp_path / "p", "commons", TITLE)["asset"]
    assert (a["width"], a["height"]) == (1920, 1152) and (a["original_width"], a["original_height"]) == (2000, 1200)
    assert a["credit"]["flag"] == "small"                                       # short side 1152 < 1200: judged on the stored file
    b = api.import_candidate(tmp_path / "q", "commons", TITLE, min_short_side=1100)["asset"]
    assert b["credit"]["flag"] is None                                          # the floor is configurable and is applied to the same size


def test_a_search_card_shows_the_size_the_import_will_store_and_the_import_stores_it(wiki_api, tmp_path):
    wiki_api(Wiki(2400, 1800, thumbs=jpeg(1920, 1440)))
    (card,) = api.search("munch", "commons", "image", 5)
    assert (card["width"], card["height"]) == (1920, 1440)                     # not 2400 x 1800, a size the stored file does not have
    a = api.import_candidate(tmp_path / "p", "commons", card["source_id"])["asset"]
    assert (a["width"], a["height"]) == (card["width"], card["height"])        # card before the import = asset after it
    assert (a["original_width"], a["original_height"]) == (2400, 1800)


def test_a_narrow_original_keeps_its_own_size_on_the_card(wiki_api):
    wiki_api(Wiki(1500, 1300))
    (card,) = api.search("munch", "commons", "image", 5)
    assert (card["width"], card["height"]) == (1500, 1300) and card["flag"] is None


def test_a_search_card_of_a_rendition_below_the_floor_is_flagged_small(wiki_api):
    wiki_api(Wiki(2000, 1200))
    (card,) = api.search("munch", "commons", "image", 5)
    assert (card["width"], card["height"]) == (1920, 1152) and card["flag"] == "small"


def test_a_tiff_is_stored_under_the_extension_of_its_jpeg_rendition(wiki_api, tmp_path):
    tif = "https://upload.wikimedia.org/wikipedia/commons/a/ab/Munch.tif"
    w = Wiki(4000, 3000, mime="image/tiff", url=tif, thumb_name="Munch.tif.jpg", thumbs=jpeg(1920, 1440))
    wiki_api(w)
    res = api.import_candidate(tmp_path / "p", "commons", TITLE)
    f = res["asset"]["file"]
    assert f.endswith(".jpg") and (tmp_path / "p" / f).is_file()
    assert not list((tmp_path / "p" / "media").glob("*.tif"))
    assert (res["asset"]["width"], res["asset"]["height"]) == (1920, 1440)
    assert api.import_candidate(tmp_path / "p", "commons", TITLE) == res


def test_an_original_refused_for_good_leaves_nothing_in_media(wiki_api, tmp_path):
    wiki_api(Wiki(1500, 1300, orig=refused("120"), thumbs=refused("120"), thumburl="none"))
    with pytest.raises(http.MediaHTTPError) as e:
        api.import_candidate(tmp_path / "p", "commons", TITLE)
    assert e.value.rate_limited and e.value.retry_after == 120
    assert not list((tmp_path / "p" / "media").glob("*.jpg")) and not list((tmp_path / "p" / "media").glob("*.part"))
