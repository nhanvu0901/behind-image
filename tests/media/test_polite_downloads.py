"""fixes4, point 1: the downloads of pictures are polite (at most one request a second to a host, Wikimedia counted as ONE host) and patient (a 429, or a
503 with Retry-After, is waited out: what the host asks, else 10, 30, 90 s, and the request is sent again, three times). Fakes and a fake clock only: no request
leaves the test and nothing sleeps."""
import urllib.error

import pytest

from bti.media import api, http
from bti.media.http import MediaHTTPError, download_file, open_url
from bti.media.sources.commons import CommonsSource

from conftest import FakeResp
from test_commons_rendition import ORIG, TITLE, Wiki, jpeg, refused, thumb


class Clock:
    """A clock that only moves when somebody sleeps: `sleeps` is what was waited, in order."""

    def __init__(self, start=1000.0):
        self.now, self.sleeps = start, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(round(s, 3))
        self.now += s


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(http, "_now", c)
    monkeypatch.setattr(http, "_PACE_LAST", {})
    return c


class _Dummy:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _limited(code, retry_after=None, url="https://example.org/test"):
    hdrs = {} if retry_after is None else {"Retry-After": str(retry_after)}
    return urllib.error.HTTPError(url, code, "limited", hdrs, None)


def _opener(*answers, stamps=None, clock=None):
    """An opener that raises or returns each answer in turn; `calls` counts the requests, `stamps` the fake time of each."""
    seq = list(answers)
    calls = {"n": 0}

    def opener(req, timeout=None):
        calls["n"] += 1
        if stamps is not None:
            stamps.append(clock.now)
        a = seq.pop(0)
        if isinstance(a, BaseException):
            raise a
        return a
    opener.calls = calls
    return opener


# ---------------------------------------------------------------------------------------------------------------- pacing
def test_two_requests_to_one_host_are_a_second_apart_and_other_hosts_do_not_wait(clock):
    http.pace("https://example.org/a", sleep=clock.sleep, clock=clock)
    http.pace("https://example.org/b", sleep=clock.sleep, clock=clock)
    http.pace("https://example.org/c", sleep=clock.sleep, clock=clock)
    http.pace("https://other.example.org/a", sleep=clock.sleep, clock=clock)
    assert clock.sleeps == [1.0, 1.0]                                      # the first goes at once, the next two wait a second; another host is not held
    clock.now += 5
    http.pace("https://example.org/d", sleep=clock.sleep, clock=clock)
    assert clock.sleeps == [1.0, 1.0]                                      # five seconds passed: no wait


def test_every_host_of_wikimedia_counts_as_one(clock):
    for url in ("https://commons.wikimedia.org/w/api.php", "https://upload.wikimedia.org/a.jpg", "https://en.wikipedia.org/w/api.php",
                "https://thumb.wikimedia.org/x.jpg"):
        http.pace(url, sleep=clock.sleep, clock=clock)
    assert clock.sleeps == [1.0, 1.0, 1.0]
    assert http.host_key("https://upload.wikimedia.org/a.jpg") == http.host_key("https://commons.wikimedia.org/x") == "wikimedia"
    assert http.host_key("https://notwikimedia.org/x") == "notwikimedia.org" and http.host_key("https://example.org/x") == "example.org"


def test_a_polite_request_is_paced_and_an_ordinary_one_is_not(clock):
    stamps = []
    op = _opener(_Dummy(), _Dummy(), _Dummy(), _Dummy(), stamps=stamps, clock=clock)
    open_url("https://example.org/1", sleep=clock.sleep, opener=op)
    open_url("https://example.org/2", sleep=clock.sleep, opener=op)
    assert clock.sleeps == [] and stamps == [1000.0, 1000.0]               # a search is not slowed
    with http.polite():
        open_url("https://example.org/3", sleep=clock.sleep, opener=op)
        open_url("https://example.org/4", sleep=clock.sleep, opener=op)
    assert clock.sleeps == [1.0] and stamps[2:] == [1000.0, 1001.0]        # a download waits for the second
    assert not http.POLITE.get() and not http.PATIENT.get()                # and the block leaves nothing behind


# ---------------------------------------------------------------------------------------------------------------- patience
def test_a_429_without_a_time_is_waited_out_10_30_90_seconds_and_the_request_goes_again(clock):
    op = _opener(_limited(429), _limited(429), _limited(429), _Dummy())
    with http.polite():
        assert isinstance(open_url("https://example.org/test", sleep=clock.sleep, opener=op), _Dummy)
    assert op.calls["n"] == 4 and clock.sleeps == [10.0, 30.0, 90.0]


def test_a_429_with_a_time_is_waited_for_exactly_that_time(clock):
    op = _opener(_limited(429, 20), _Dummy())
    with http.polite():
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 2 and clock.sleeps == [20.0]


def test_a_503_with_retry_after_is_waited_out_too_and_a_503_without_a_time_is_not(clock):
    op = _opener(_limited(503, 7), _Dummy())
    with http.polite():
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 2 and clock.sleeps == [7.0]
    clock.sleeps.clear()
    op = _opener(_limited(503), _Dummy())
    with http.polite(), pytest.raises(MediaHTTPError) as e:
        open_url("https://other.example.org/test2", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 1 and clock.sleeps == [] and e.value.status == 503 and not e.value.rate_limited


def test_after_the_three_tries_the_refusal_is_raised_with_the_hosts_last_time(clock):
    op = _opener(_limited(429, 5), _limited(429, 6), _limited(429, 7), _limited(429, 8), _Dummy())
    with http.polite(), pytest.raises(MediaHTTPError) as e:
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 4 and clock.sleeps == [5.0, 6.0, 7.0]           # three waits, four requests, never a fifth
    assert e.value.rate_limited and e.value.retry_after == 8


def test_after_the_three_tries_with_no_time_the_refusal_says_no_time_and_starts_no_cooldown(clock):
    op = _opener(_limited(429), _limited(429), _limited(429), _limited(429))
    with http.polite(), pytest.raises(MediaHTTPError) as e:
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 4 and clock.sleeps == [10.0, 30.0, 90.0]
    assert e.value.rate_limited and e.value.retry_after is None and not http._COOLDOWN


def test_a_host_that_asks_for_more_than_two_minutes_is_not_waited_for(clock):
    op = _opener(_limited(429, 121), _Dummy())
    with http.polite(), pytest.raises(MediaHTTPError) as e:
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 1 and clock.sleeps == [] and e.value.retry_after == 121
    op = _opener(_limited(429, 120), _Dummy())                              # two minutes is still waited
    with http.polite():
        open_url("https://other.example.org/test2", sleep=clock.sleep, opener=op)
    assert clock.sleeps == [120.0]


def test_a_patient_wait_is_not_one_of_the_tries_of_the_server_error_backoff(clock):
    op = _opener(_limited(429), _limited(429), _limited(429), _limited(502), _limited(502), _Dummy())
    with http.polite():
        open_url("https://example.org/test", sleep=clock.sleep, opener=op, tries=3)
    assert op.calls["n"] == 6 and clock.sleeps == [10.0, 30.0, 90.0, 2.0, 4.0]   # 429s do not use up the 3 tries of the 502s


def test_an_ordinary_request_keeps_its_old_rule_inside_nothing(clock):
    op = _opener(_limited(429), _Dummy())
    with pytest.raises(MediaHTTPError):
        open_url("https://example.org/test", sleep=clock.sleep, opener=op)
    assert op.calls["n"] == 1 and clock.sleeps == []                        # a search still fails at once and says when to come back


def test_a_polite_request_waits_out_a_host_cooldown_when_it_is_short(clock):
    op = _opener(_limited(429, 300), _Dummy())
    with pytest.raises(MediaHTTPError):                                     # an ordinary request: refused, the host is left alone for 300 s...
        open_url("https://upload.example.org/a.jpg", sleep=clock.sleep, opener=op)
    clock.now += 250                                                        # ... 50 s are left
    with http.polite():
        assert isinstance(open_url("https://upload.example.org/b.jpg", sleep=clock.sleep, opener=_opener(_Dummy())), _Dummy)
    assert clock.sleeps == [50.0]                                           # a download waits the 50 s out instead of failing
    clock.now += 1
    op2 = _opener(_limited(429, 500), _Dummy())
    with pytest.raises(MediaHTTPError):
        open_url("https://slow.example.org/a.jpg", sleep=clock.sleep, opener=op2)
    with http.polite(), pytest.raises(MediaHTTPError) as e:                 # 500 s left: more than two minutes, so it fails at once with the time
        open_url("https://slow.example.org/b.jpg", sleep=clock.sleep, opener=_opener(_Dummy()))
    assert e.value.rate_limited and e.value.retry_after in (499, 500)


def test_hasty_inside_polite_does_not_wait_but_is_still_paced(clock):
    stamps = []
    op = _opener(_Dummy(), _limited(429), _Dummy(), stamps=stamps, clock=clock)
    with http.polite():
        open_url("https://example.org/1", sleep=clock.sleep, opener=op)
        with http.hasty(), pytest.raises(MediaHTTPError):
            open_url("https://example.org/2", sleep=clock.sleep, opener=op)
        assert http.POLITE.get() and http.PATIENT.get()                     # patient again after the block
    assert clock.sleeps == [1.0] and stamps == [1000.0, 1001.0]


def test_a_refused_download_leaves_nothing_behind(clock, tmp_path):
    dest = tmp_path / "media" / "a.jpg"
    op = _opener(_limited(429), _limited(429), _limited(429), _limited(429))
    with http.polite(), pytest.raises(MediaHTTPError):
        download_file("https://example.org/a.jpg", dest, max_bytes=1000, opener=op, sleep=clock.sleep)
    assert not dest.exists() and not (tmp_path / "media" / "a.jpg.part").exists()


# ---------------------------------------------------------------------------------------------------------------- through the import of a picture
class RateLimitingWiki:
    """A fake Wikimedia that does what the real one did to the real run: it answers 429 when two requests come less than a second apart (the whole service,
    API and files alike), and that 429 carries no time. Every picture is a 1500 x 1300 JPEG: one API call for its metadata, one GET of the file."""

    def __init__(self, clock, names):
        self.clock, self.names, self.stamps, self.refused = clock, list(names), [], 0
        self.files = {"https://upload.wikimedia.org/wikipedia/commons/a/ab/%s.jpg" % n: n for n in names}
        self.urls = []

    def __call__(self, req, timeout=None):
        import json
        from urllib.parse import parse_qs, urlparse
        url = req.full_url
        self.urls.append(url)
        if self.stamps and self.clock.now - self.stamps[-1] < 1.0:
            self.refused += 1
            self.stamps.append(self.clock.now)
            raise _limited(429, url=url)
        self.stamps.append(self.clock.now)
        if "api.php" in url:
            title = parse_qs(urlparse(url).query)["titles"][0]
            name = title.split(":", 1)[1].replace(".jpg", "")
            ii = {"url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/%s.jpg" % name, "descriptionurl": "https://commons.wikimedia.org/wiki/" + title,
                  "width": 1500, "height": 1300, "size": 500_000, "mime": "image/jpeg",
                  "extmetadata": {"LicenseShortName": {"value": "Public domain"}, "Artist": {"value": "Somebody"}}}
            return FakeResp(json.dumps({"query": {"pages": [{"title": title, "index": 1, "imageinfo": [ii]}]}}).encode())
        return FakeResp(jpeg(1500, 1300))


NAMES = ["Charles the Bold 1460", "Philipp the Good", "Portrait of a Man", "Detail 2", "Frontispiece", "Pluenderung Grandson"]


def test_six_pictures_one_after_another_from_commons_never_get_a_429_because_they_keep_a_second_apart(clock, monkeypatch, tmp_path):
    wiki = RateLimitingWiki(clock, NAMES)
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=wiki, sleep=clock.sleep))
    for n in NAMES:
        res = api.import_candidate(tmp_path / "p", "commons", "File:%s.jpg" % n, min_short_side=0)
        assert res["asset"]["width"] == 1500
    assert wiki.refused == 0 and len(wiki.urls) == 12                       # two requests a picture, none refused
    gaps = [round(b - a, 3) for a, b in zip(wiki.stamps, wiki.stamps[1:])]
    assert min(gaps) >= 1.0                                                 # at most one request a second to the service, API and file alike


def test_the_same_six_pictures_without_the_polite_client_are_refused(clock, monkeypatch, tmp_path):
    """What the real run did: the unpaced client sends the metadata call and the download back to back, and the service says no."""
    wiki = RateLimitingWiki(clock, NAMES)
    src = CommonsSource(opener=wiki, sleep=clock.sleep)
    with pytest.raises(MediaHTTPError) as e:
        meta = src.fetch_meta("File:%s.jpg" % NAMES[0])
        src.download(meta, tmp_path / "x.jpg", min_short_side=0)
    assert e.value.rate_limited and wiki.refused >= 1


def test_a_commons_import_that_is_refused_waits_and_gets_the_picture(clock, monkeypatch, tmp_path):
    wiki = Wiki(3048, 4000, orig=b"never asked", thumbs=jpeg(1920, 2520))      # a rendition is downloaded: no way round, so a refusal is waited out
    refused_gets = {"n": 0}

    def flaky(req, timeout=None):
        if "api.php" not in req.full_url and refused_gets["n"] < 2:
            refused_gets["n"] += 1
            raise _limited(429, url=req.full_url)                              # the file is refused twice, with no time
        return wiki(req, timeout)
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=flaky, sleep=clock.sleep))
    res = api.import_candidate(tmp_path / "p", "commons", TITLE)
    assert (tmp_path / "p" / res["asset"]["file"]).is_file() and (res["asset"]["width"], res["asset"]["height"]) == (1920, 2520)
    assert [s for s in clock.sleeps if s >= 10] == [10.0, 30.0]                # 10 s, then 30 s, then the third request went through


def test_a_refused_original_with_a_rendition_to_fall_back_on_is_not_waited_for(clock, monkeypatch, tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("90"), thumbs=jpeg(1280, 1100))
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=wiki, sleep=clock.sleep))
    res = api.import_candidate(tmp_path / "p", "commons", TITLE, min_short_side=0)
    assert (res["asset"]["width"], res["asset"]["height"]) == (1280, 1100)    # the rendition took its place at once
    assert 90.0 not in clock.sleeps and wiki.urls.count(ORIG) == 1            # the original was asked once, not waited for
    assert http.PATIENT.get() is False


def test_the_import_route_of_a_source_that_keeps_refusing_raises_the_refusal_after_the_tries(clock, monkeypatch, tmp_path):
    wiki = Wiki(1500, 1300, orig=refused("100"), thumbs=refused("100"), thumburl="none")
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=wiki, sleep=clock.sleep))
    with pytest.raises(MediaHTTPError) as e:
        api.import_candidate(tmp_path / "p", "commons", TITLE)
    assert e.value.rate_limited and e.value.retry_after == 100
    assert not list((tmp_path / "p" / "media").glob("*.jpg"))


def test_a_download_with_nothing_wrong_costs_no_wait_beyond_the_pacing(clock, monkeypatch, tmp_path):
    wiki = Wiki(3048, 4000, orig=b"never asked", thumbs=jpeg(1920, 2520))
    monkeypatch.setitem(api._SOURCES, "commons", CommonsSource(opener=wiki, sleep=clock.sleep))
    api.import_candidate(tmp_path / "p", "commons", TITLE)
    assert all(s <= 1.0 for s in clock.sleeps) and len(clock.sleeps) == 2     # fetch_meta, then the rendition address, then the file: two waits of a second
