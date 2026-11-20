"""The free source `wikipedia` (bti/media/sources/wikipedia.py): a thing is looked up, the pictures of its best articles are offered as Commons files.
No real request: a fake transport answers the MediaWiki API of Wikipedia and of Commons."""
import io
import json
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest

from bti.media import api, http
from bti.media.sources import wikipedia as W
from bti.media.sources.wikipedia import WikipediaSource

from conftest import FakeResp


def cpage(title, w=1600, h=1200, mime="image/jpeg", licence="CC BY-SA 4.0", missing=False):
    if missing:
        return {"title": title, "missing": True}
    return {"title": title, "index": 0, "imageinfo": [{
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/%s" % title.split(":", 1)[1].replace(" ", "_"),
        "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/%s/500px-x.jpg" % title.split(":", 1)[1].replace(" ", "_"),
        "descriptionurl": "https://commons.wikimedia.org/wiki/%s" % title.replace(" ", "_"), "width": w, "height": h, "size": 400000, "mime": mime,
        "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": "<a href='x'>A. Photographer</a>"}, "ObjectName": {"value": title.split(":", 1)[1][:-4]}}}]}


def page(title, index, lead=None, files=(), extract="", description=""):
    p = {"pageid": index, "ns": 0, "title": title, "index": index, "images": [{"ns": 6, "title": f} for f in files]}
    if lead:
        p["pageimage"] = lead
    if extract:
        p["extract"] = extract
    if description:
        p["description"] = description
    return p


class Net:
    """A transport that answers by host: the Wikipedia API with `wiki`, the Commons API with a page for every title it is asked, from `commons`
    (a dict title -> page; a title that is not in it is `missing`). Records every URL and header."""

    def __init__(self, wiki, commons):
        self.wiki, self.commons = wiki, commons
        self.urls, self.headers = [], []

    def __call__(self, req, timeout=None):
        url = req.full_url
        self.urls.append(url)
        self.headers.append({k.lower(): v for k, v in req.header_items()})
        q = parse_qs(urlparse(url).query)
        host = urlparse(url).hostname
        if host.endswith("wikipedia.org"):
            body = self.wiki(q) if callable(self.wiki) else self.wiki
        else:
            titles = q.get("titles", [""])[0].split("|")
            body = {"query": {"pages": [self.commons.get(t) or cpage(t, missing=True) for t in titles]}}
        return FakeResp(json.dumps(body).encode())


def source(wiki, commons, **kw):
    clock = {"t": 100.0, "slept": []}

    def sleep(s):
        clock["slept"].append(s)
        clock["t"] += s
    net = Net(wiki, commons)
    src = WikipediaSource(opener=net, sleep=sleep, clock=lambda: clock["t"], **kw)
    return src, net, clock


NOYON = {"query": {"pages": [
    page("Noyon Cathedral", 1, lead="Noyon_cathedral.jpg", description="Cathedral in Noyon, France", extract="Noyon Cathedral is a Roman Catholic cathedral.",
         files=["File:Noyon cathedral.jpg", "File:Flag of France.svg", "File:Commons-logo.svg", "File:Noyon nave.jpg", "File:Noyon plan.png", "File:Noyon choir.ogg",
                "File:Locator map Noyon.png", "File:Fair use only.jpg", "File:Noyon tiny.jpg", "File:Noyon strip.jpg", "File:Noyon facade.webp", "File:Noyon seal.gif"]),
    page("Noyon", 2, lead="Noyon_town.jpg", description="Commune in Hauts-de-France", files=["File:Noyon town.jpg", "File:Noyon hall.jpg"]),
    page("Diocese of Noyon", 3, files=["File:Noyon arms.jpg"])]}}
COMMONS = {t: cpage(t) for t in ("File:Noyon cathedral.jpg", "File:Noyon nave.jpg", "File:Noyon town.jpg", "File:Noyon hall.jpg", "File:Noyon arms.jpg")}
COMMONS["File:Noyon plan.png"] = cpage("File:Noyon plan.png", 1200, 900, "image/png")
COMMONS["File:Noyon tiny.jpg"] = cpage("File:Noyon tiny.jpg", 300, 200)
COMMONS["File:Noyon strip.jpg"] = cpage("File:Noyon strip.jpg", 4000, 600)
COMMONS["File:Noyon facade.webp"] = cpage("File:Noyon facade.webp", 1400, 1000, "image/webp")
COMMONS["File:Noyon choir.ogg"] = cpage("File:Noyon choir.ogg", 0, 0, "application/ogg")
COMMONS["File:Noyon seal.gif"] = cpage("File:Noyon seal.gif", 900, 900, "image/gif")


def test_the_best_pages_give_their_lead_image_and_their_pictures_as_commons_files():
    src, net, _ = source(NOYON, COMMONS)
    got = src.search("Noyon Cathedral", "image", 20)
    ids = [m["source_id"] for m in got]
    assert ids[0] == "File:Noyon cathedral.jpg"                                      # the lead image of the best page first
    assert set(ids) == {"File:Noyon cathedral.jpg", "File:Noyon nave.jpg", "File:Noyon plan.png", "File:Noyon facade.webp", "File:Noyon town.jpg",
                        "File:Noyon hall.jpg", "File:Noyon arms.jpg"}
    assert all(m["source"] == "commons" and m["kind"] == "image" for m in got)       # the card is Commons' own: its download and credit are Commons'
    top = got[0]
    assert (top["page_title"], top["site"], top["via"]) == ("Noyon Cathedral", "Wikipedia", "wikipedia")
    assert top["snippet"] == "Cathedral in Noyon, France" and top["author"] == "A. Photographer" and top["licence"] == "CC BY-SA 4.0"
    assert top["article_url"] == "https://en.wikipedia.org/wiki/Noyon_Cathedral"
    assert {m["page_title"] for m in got} == {"Noyon Cathedral", "Noyon", "Diocese of Noyon"}


def test_what_is_never_offered_is_left_out():
    src, _, _ = source(NOYON, COMMONS)
    ids = {m["source_id"] for m in src.search("Noyon Cathedral", "image", 40)}
    for gone in ("File:Flag of France.svg",           # a flag (and a vector drawing)
                 "File:Commons-logo.svg",             # furniture of the article
                 "File:Noyon choir.ogg",              # audio
                 "File:Locator map Noyon.png",        # a locator map (named)
                 "File:Fair use only.jpg",            # not on Commons (a picture only Wikipedia has)
                 "File:Noyon tiny.jpg",               # under 600 px
                 "File:Noyon strip.jpg",              # a banner: more than four times longer than high
                 "File:Noyon seal.gif"):              # not a bitmap the app stores
        assert gone not in ids, gone
    assert W.junk_name("File:Flag of France.svg") and W.junk_name("File:Coat of arms of Noyon.png") and W.junk_name("File:Locator map X.png")
    assert not W.junk_name("File:Icon of Saint Eligius.jpg") and not W.junk_name("File:Noyon Cathedral portal.jpg")         # an icon painting and a portal are subjects


def test_the_pages_are_mixed_so_that_the_best_one_gives_about_half():
    src, _, _ = source(NOYON, COMMONS)
    got = src.search("Noyon Cathedral", "image", 4)
    assert [m["page_title"] for m in got] == ["Noyon Cathedral", "Noyon", "Noyon Cathedral", "Diocese of Noyon"]
    assert [m["source_id"] for m in src.search("Noyon Cathedral", "image", 1)] == ["File:Noyon cathedral.jpg"]


def test_one_search_is_two_requests_with_the_names_the_caller_gave_and_a_generic_client():
    src, net, _ = source(NOYON, COMMONS)
    src.search("Noyon Cathedral", "image", 8)
    assert len(net.urls) == 2 and src.requests == 2
    u = urlparse(net.urls[0])
    q = parse_qs(u.query)
    assert u.hostname == "en.wikipedia.org" and q["generator"] == ["search"] and q["gsrsearch"] == ["Noyon Cathedral"] and q["gsrlimit"] == ["3"]
    assert "pageimages" in q["prop"][0] and "images" in q["prop"][0]
    assert urlparse(net.urls[1]).hostname == "commons.wikimedia.org" and "File:Noyon cathedral.jpg" in parse_qs(urlparse(net.urls[1]).query)["titles"][0]
    for h in net.headers:
        ua = h["user-agent"].lower()
        assert ua and "behind-the-image" not in ua and "nhanvu" not in ua and "@" not in ua            # a generic client: no person, no project, no address


def test_only_images_are_asked_for_and_nothing_is_sent_for_an_empty_question():
    src, net, _ = source(NOYON, COMMONS)
    assert src.search("Noyon Cathedral", "video", 8) == [] and src.search("   ", "image", 8) == [] and net.urls == []
    empty, _, _ = source({"query": {"pages": []}}, {})
    assert empty.search("zzz", "image", 8) == []                                                      # no page: nothing (and no second request)
    assert empty.requests == 1


def test_at_most_one_request_a_second_across_calls():
    src, net, clock = source(NOYON, COMMONS)
    src.search("Noyon Cathedral", "image", 8)                        # two requests
    src.search("Noyon Cathedral", "image", 8)                        # two more
    assert len(net.urls) == 4 and len(clock["slept"]) == 3           # the first request goes at once, each of the next three waits out the second
    assert all(abs(s - 1.0) < 1e-9 for s in clock["slept"])
    assert clock["t"] - 100.0 >= 3.0


def test_too_many_requests_is_honoured_by_the_polite_layer():
    def wiki(q):
        raise urllib.error.HTTPError("https://en.wikipedia.org/w/api.php", 429, "Too Many Requests", {"Retry-After": "120"}, io.BytesIO(b""))
    src, net, _ = source(wiki, {})
    with pytest.raises(http.MediaHTTPError) as e:
        src.search("Noyon Cathedral", "image", 8)
    assert e.value.rate_limited and e.value.retry_after == 120                                        # the caller (the job) leaves the host alone for that time
    with pytest.raises(http.MediaHTTPError):                                                          # and nothing more is sent to that host meanwhile
        src.search("Noyon Cathedral", "image", 8)
    assert len(net.urls) == 1


def test_one_named_article_gives_its_pictures_in_its_own_language():
    wiki = {"query": {"pages": [page("Cathédrale Notre-Dame de Noyon", 1, lead="Noyon_cathedral.jpg", files=["File:Noyon nave.jpg"])]}}
    src, net, _ = source(wiki, COMMONS)
    got = src.page_pictures("Cath%C3%A9drale_Notre-Dame_de_Noyon".replace("%C3%A9", "é"), "fr", limit=5)
    assert [m["source_id"] for m in got] == ["File:Noyon cathedral.jpg", "File:Noyon nave.jpg"] and got[0]["site"] == "Wikipedia (fr)"
    q = parse_qs(urlparse(net.urls[0]).query)
    assert urlparse(net.urls[0]).hostname == "fr.wikipedia.org" and q["titles"] == ["Cathédrale Notre-Dame de Noyon"] and "generator" not in q
    assert W.lang_of("en.wikipedia.org") == "en" and W.lang_of("fr.m.wikipedia.org") == "fr" and W.lang_of("commons.wikimedia.org") is None


def test_a_candidate_is_handed_to_commons_for_its_data_its_download_and_its_credit(monkeypatch, tmp_path):
    calls = []

    class FakeCommons:
        def fetch_meta(self, sid):
            calls.append(("meta", sid))
            return {"source": "commons", "source_id": sid}

        def licence(self, meta):
            calls.append(("licence", meta["source_id"]))
            return True, "CC0", ""

        def credit(self, meta):
            calls.append(("credit", meta["source_id"]))
            return {"source": "commons"}

        def download(self, meta, dest, **kw):
            calls.append(("download", meta["source_id"]))
            return dest
    monkeypatch.setitem(api._SOURCES, "commons", FakeCommons())
    src, _, _ = source(NOYON, COMMONS)
    m = src.fetch_meta("File:x.jpg")
    assert src.licence(m)[0] is True and src.credit(m) == {"source": "commons"} and src.download(m, tmp_path / "a.jpg") == tmp_path / "a.jpg"
    assert [c[0] for c in calls] == ["meta", "licence", "credit", "download"]
    assert src.stored_size({"width": 3048, "height": 4000, "mime": "image/jpeg", "size": 1000}) == (1920, 2520)            # Commons' own rendition rule


def test_the_real_transport_is_never_used_by_a_test(monkeypatch):
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)                                           # even with the A7 switch down (some tests do that for a fake program)
    from bti.media.errors import RealModelsOff
    with pytest.raises(RealModelsOff):
        WikipediaSource().search("Noyon Cathedral", "image", 5)
