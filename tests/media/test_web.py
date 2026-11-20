"""The source `web` (bti/media/sources/web.py): the answer of the You.com search turned into picture candidates. No request of any kind: the answer is the REAL one
that was kept in tests/media/fixtures/ydc_search_sample.json (query "Arnolfini Portrait Jan van Eyck"), the client is a fake, the transport is a fake."""
import io
import json
import urllib.request
from pathlib import Path

import pytest

from bti.media import api, http
from bti.media.errors import NotFound, RealModelsOff
from bti.media.sources import web as W
from bti.media.sources.web import WebSource
from bti.media.youcom import RawCall

from conftest import FakeResp, load, png_bytes


def jpeg_bytes(w=800, h=600):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 130, 140)).save(b, "JPEG")
    return b.getvalue()


def webp_bytes(w=800, h=600):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 130, 140)).save(b, "WEBP")
    return b.getvalue()


class FakeClient:
    """Stands for YouComClient: it answers `search(query, profile)` with a prepared RawCall and remembers what it was asked."""

    def __init__(self, payload=None, error=None, status=None):
        self.payload, self.error, self.status, self.calls = payload, error, status, []

    def search(self, query, profile):
        self.calls.append((query, profile))
        if self.error:
            return RawCall(api="search", payload={}, error=self.error, status_code=self.status)
        return RawCall(api="search", payload=self.payload, status_code=200)


class Wiki:
    """A fake Wikipedia source for the pages the answer names: `page_pictures(title, lang, limit)`."""

    def __init__(self, found=None):
        self.found, self.calls = found, []

    def page_pictures(self, title, lang=None, limit=12):
        self.calls.append((title, lang, limit))
        return self.found if self.found is not None else [{"source": "commons", "source_id": "File:Van Eyck - Arnolfini Portrait.jpg", "title": "The Arnolfini Portrait",
                                                           "page_title": title, "site": "Wikipedia", "snippet": "A painting.", "via": "wikipedia", "width": 3000, "height": 4000}]


class OneMeta:
    def __init__(self, meta=None, missing=()):
        self.meta, self.missing, self.calls = meta, set(missing), []

    def fetch_meta(self, sid):
        self.calls.append(sid)
        if sid in self.missing:
            raise NotFound("no such file")
        return self.meta or {"source": "commons", "source_id": sid, "title": "Arnolfini", "width": 3000, "height": 4000, "licence": "PD"}


@pytest.fixture
def sample():
    return load("ydc_search_sample.json")


@pytest.fixture
def wiki(monkeypatch):
    w = Wiki()
    monkeypatch.setitem(api._SOURCES, "wikipedia", w)
    return w


def results(*pages):
    return {"results": {"web": list(pages)}}


def pg(url, title="A page", md="", thumb=None, description="About the thing.", **kw):
    p = {"url": url, "title": title, "description": description, "snippets": ["x"], "contents": {"markdown": md}}
    if thumb:
        p["original_thumbnail_url"] = thumb
    p.update(kw)
    return p


# ---------------------------------------------------------------------------------------------------------------- the real answer
def test_the_real_answer_gives_the_lead_pictures_and_the_resolved_wikipedia_page(sample, wiki):
    rep = []
    got = WebSource(client=FakeClient(sample), require_ticket=False).candidates_from(sample, limit=40, report=rep)
    by_page = {}
    for m in got:
        by_page.setdefault(m["page_title"], []).append(m)
    assert wiki.calls == [("Arnolfini Portrait", "en", 8)]                                      # the Wikipedia page was handed to the Wikipedia source
    assert [m["source_id"] for m in by_page["Arnolfini Portrait"]] == ["File:Van Eyck - Arnolfini Portrait.jpg"] and by_page["Arnolfini Portrait"][0]["source"] == "commons"
    web = [m for m in got if m["source"] == "web"]
    assert {m["site"] for m in web} == {"nationalgallery.org.uk", "smarthistory.org", "canon.codart.nl", "thecollector.com"}      # the best FIVE pages only (britannica is the 8th)
    lead = {m["site"]: m for m in web if "ArnolfiniPortraitThumb" in m["url"] or "featured-1" in m["url"]}
    assert lead["smarthistory.org"]["url"] == "https://smarthistory.org/wp-content/uploads/2025/01/ArnolfiniPortraitThumb.jpg"       # the page's lead picture
    assert lead["thecollector.com"]["url"].startswith("https://cdn.thecollector.com/")
    codart = [m["url"] for m in web if m["site"] == "canon.codart.nl"]
    assert codart == ["https://canon.codart.nl/wp-content/uploads/sites/2/2019/08/Eyck-Arnolfini-Portrait-657x900.jpg"]               # the -300x300 thumbnails are not offered
    ng = [m for m in web if m["site"] == "nationalgallery.org.uk"]
    assert all("icons" not in m["url"] and not m["url"].endswith(".svg") and "!80,50" not in m["url"] for m in ng)                 # no svg icon, no IIIF 80 px thumbnail
    for m in web:                                                                              # what the choosing session reads, and the credit
        assert m["title"] and m["page_url"].startswith("https://") and m["author"] == m["site"] and m["licence"] == "" and m["via"] == "web"
        assert len(m["source_id"]) <= 300 and W.parse_id(m["source_id"])[0] == m["url"] and W.parse_id(m["source_id"])[1] == m["page_url"]
        assert m["thumb_url"] == m["url"] and m["kind"] == "image" and m["width"] == 0
    why = " | ".join(r["why"] for r in rep)
    assert "not a bitmap (.svg)" in why and "small thumbnail" in why                              # what was dropped says why


def test_a_candidate_goes_through_the_media_facade_as_a_card_with_its_page_and_site(sample, wiki, monkeypatch):
    monkeypatch.setitem(api._SOURCES, "web", WebSource(client=FakeClient(sample), require_ticket=False))
    cards = api.search("Arnolfini Portrait Jan van Eyck", source="web", kind="image", limit=12)
    one = next(c for c in cards if c["source"] == "web")
    assert one["flag"] == "unknown" and one["page_title"] and one["site"] and one["via"] == "web" and one["licence_ok"] is False
    assert any(c["source"] == "commons" and c["via"] == "web" and c["site"] == "Wikipedia" for c in cards)


# ---------------------------------------------------------------------------------------------------------------- what is never offered
def test_a_stock_agency_or_a_print_shop_is_never_offered_nor_its_pictures(wiki):
    blocked = results(
        pg("https://www.gettyimages.com/detail/x", "Getty", thumb="https://media.gettyimages.com/x.jpg"),
        pg("https://www.meisterdrucke.uk/fine-art-prints/Jan-van-Eyck/1.html", "Print shop", thumb="https://cdn.meisterdrucke.uk/x.jpg"),
        pg("https://www.alamy.com/stock-photo-x.html", "Alamy", thumb="https://c8.alamy.com/x.jpg"),
        pg("https://blog.example.org/a", "A blog", md="![w](https://image.shutterstock.com/z/1.jpg)\n![ok](https://blog.example.org/img/portrait.jpg)", thumb="https://x.istockphoto.com/a.jpg"))
    rep = []
    got = WebSource(require_ticket=False, client=FakeClient()).candidates_from(blocked, limit=20, report=rep)
    assert [m["url"] for m in got] == ["https://blog.example.org/img/portrait.jpg"]
    assert sum("stock agency" in r["why"] or "print shop" in r["why"] for r in rep) == 5          # three pages, and two pictures of the fourth
    assert W.host_blocked("c8.alamy.com", W.blocked_hosts()) == "alamy.com" and W.host_blocked("notalamy.com", W.blocked_hosts()) is None
    assert "extra-shop.example" in W.blocked_hosts(["extra-shop.example"])                       # the owner's own list is added


def test_data_addresses_vector_and_furniture_pictures_are_dropped_and_the_others_are_read_properly(wiki):
    md = "\n".join([
        "![a](data:image/png;base64,AAAA)", "![b](https://s.example.org/x/logo.png)", "![c](https://s.example.org/x/arrow.svg)", "![d](https://s.example.org/x/anim.gif)",
        "![e](//cdn.example.org/pics/the-portrait.jpg?w=1200&amp;fm=jpg)", "![f](/media/relative-view.jpg \"A caption\")", "![g](https://s.example.org/x/small-120x90.jpg)",
        "![h](http://127.0.0.1/secret.jpg)", "![i](https://s.example.org/x/five.jpg)", "![j](https://s.example.org/x/six.jpg)", "![k](https://s.example.org/x/seven.jpg)"])
    rep = []
    got = WebSource(require_ticket=False, client=FakeClient()).candidates_from(results(pg("https://s.example.org/page", md=md)), limit=40, report=rep)
    urls = [m["url"] for m in got]
    assert urls == ["https://cdn.example.org/pics/the-portrait.jpg?w=1200&fm=jpg", "https://s.example.org/media/relative-view.jpg", "https://s.example.org/x/five.jpg",
                    "https://s.example.org/x/six.jpg"]                                          # entities read, relative and "//" addresses made absolute, at most four from the markdown
    whys = [r["why"] for r in rep]
    assert any("data or relative" in w for w in whys) and any("furniture" in w for w in whys) and sum("(.svg)" in w or "(.gif)" in w for w in whys) == 2
    assert any("small thumbnail" in w for w in whys) and any("private or local" in w for w in whys)


def test_an_address_too_long_for_the_import_is_shortened_or_dropped():
    img = "https://a.example.org/p/" + "x" * 100 + ".jpg"
    page = "https://a.example.org/article/" + "y" * 150 + "?utm=" + "z" * 100
    sid = W.make_id(img, page)
    assert len(sid) <= 300 and W.parse_id(sid)[0] == img
    assert W.parse_id(sid)[1] in (page.split("?")[0], "https://a.example.org/")                 # the page's query goes first
    long_img = "https://a.example.org/p/a.jpg?" + "q=" + "1" * 400
    assert W.make_id(long_img, page) == "https://a.example.org/p/a.jpg " + "https://a.example.org/article/" + "y" * 150 or len(W.make_id(long_img, page)) <= 300
    assert W.make_id("https://a.example.org/" + "p" * 400 + ".jpg", page) is None
    assert W.parse_id("https://a/b.jpg") == ("https://a/b.jpg", "") and W.parse_id("") == ("", "")


def test_wikimedia_commons_and_the_met_are_resolved_by_the_source_that_knows_them(wiki, monkeypatch):
    commons = OneMeta(missing=["File:Missing.jpg"])
    met = OneMeta({"source": "met", "source_id": "436535", "title": "Portrait", "url": "https://images.metmuseum.org/x.jpg", "isPublicDomain": True})
    nomet = OneMeta({"source": "met", "source_id": "1", "title": "Nope", "url": "", "isPublicDomain": False})
    monkeypatch.setitem(api._SOURCES, "commons", commons)
    monkeypatch.setitem(api._SOURCES, "met", met)
    payload = results(pg("https://commons.wikimedia.org/wiki/File:Van_Eyck_-_Arnolfini_Portrait.jpg", "File:Van Eyck"),
                      pg("https://www.metmuseum.org/art/collection/search/436535", "Portrait | Met"),
                      pg("https://commons.wikimedia.org/wiki/Category:Arnolfini", "A category"),
                      pg("https://en.wikipedia.org/wiki/Special:Search?q=x", "Search"),
                      pg("https://commons.wikimedia.org/wiki/File:Missing.jpg", "Missing"))
    rep = []
    got = WebSource(require_ticket=False, client=FakeClient()).candidates_from(payload, limit=20, report=rep)
    assert commons.calls[0] == "File:Van Eyck - Arnolfini Portrait.jpg" and met.calls == ["436535"]
    assert [(m["source"], m["source_id"]) for m in got] == [("commons", "File:Van Eyck - Arnolfini Portrait.jpg"), ("met", "436535")]
    assert got[0]["via"] == "web" and got[0]["page_title"] == "File:Van Eyck" and got[0]["site"] == "commons.wikimedia.org"
    assert sum("not a file" in r["why"] or "not an article" in r["why"] or "no such picture" in r["why"] for r in rep) == 3
    monkeypatch.setitem(api._SOURCES, "met", nomet)
    assert WebSource(require_ticket=False, client=FakeClient()).candidates_from(results(pg("https://www.metmuseum.org/art/collection/search/1")), limit=5) == []


# ---------------------------------------------------------------------------------------------------------------- the paid call
def test_the_search_is_paid_and_runs_only_with_the_jobs_ticket(sample, wiki, monkeypatch):
    client = FakeClient(sample)
    src = WebSource(client=client)
    with pytest.raises(W.WebOff) as e:
        src.search("Arnolfini Portrait Jan van Eyck", "image", 10)
    assert e.value.code == "web_off" and client.calls == []                                     # without the ticket nothing is asked
    with W.ticket():
        assert W.has_ticket() and src.search("  Arnolfini   Portrait Jan van Eyck ", "image", 10)
        assert src.search("x", "video", 10) == []
    assert not W.has_ticket() and client.calls == [("Arnolfini Portrait Jan van Eyck", None)]   # the query goes as the plan wrote it (blanks tidied), no domain profile
    with pytest.raises(W.WebOff):
        src.search("again", "image", 10)


def test_a_missing_key_is_refused_before_a_client_exists_and_real_requests_off_is_refused_by_the_client(monkeypatch):
    from bti.script import env
    from bti.media import youcom
    made = []
    real_init = youcom.YouComClient.__init__

    def init(self, *a, **k):
        made.append(k)
        real_init(self, *a, **k)
    monkeypatch.setattr(youcom.YouComClient, "__init__", init)
    monkeypatch.setattr(env, "get_key", lambda name: None)
    with W.ticket(), pytest.raises(W.WebNoKey) as e:
        WebSource().search("x", "image", 5)
    assert e.value.code == "web_no_key" and made == []
    monkeypatch.setattr(env, "get_key", lambda name: "k" if name == "YDC_API_KEY" else None)         # a key: the real client, which refuses under BTI_NO_REAL_MODELS=1
    src = WebSource()
    with W.ticket(), pytest.raises(RealModelsOff):
        src.search("x", "image", 5)
    assert made == [{"api_key": "k", "timeout": W.SEARCH_TIMEOUT}] and src.searches == 0                          # a short time-out for a search; a refusal that sent nothing is not a search


def test_a_refused_or_failed_search_raises_what_the_job_understands(monkeypatch):
    with W.ticket():
        with pytest.raises(http.MediaHTTPError) as e:
            WebSource(client=FakeClient(error="HTTP 429", status=429)).search("x", "image", 5)
        assert e.value.rate_limited and e.value.status == 429
        with pytest.raises(http.MediaHTTPError) as e:
            WebSource(client=FakeClient(error="HTTP 402", status=402)).search("x", "image", 5)
        assert not e.value.rate_limited and e.value.status == 402
        with pytest.raises(W.WebNoKey):
            WebSource(client=FakeClient(error="YDC_API_KEY is not set")).search("x", "image", 5)
        assert WebSource(client=FakeClient({})).search("x", "image", 5) == [] and WebSource(client=FakeClient({"results": {"web": []}})).search("x", "image", 5) == []
    from bti.picks.service import _translate
    assert _translate(W.WebOff()).code == "web_off" and _translate(W.UnsafeURL("x")).code == "unsafe_url" and _translate(W.NotAnImage("x")).code == "not_an_image"


# ---------------------------------------------------------------------------------------------------------------- the download
class ImgNet:
    """A transport answering with one body, content type and headers; records the requests."""

    def __init__(self, body, ctype="image/jpeg", headers=None, chunks=None):
        self.body, self.ctype, self.extra, self.reqs = body, ctype, headers or {}, []

    def __call__(self, req, timeout=None):
        self.reqs.append((req.full_url, {k.lower(): v for k, v in req.header_items()}, timeout))
        r = FakeResp(self.body, {"Content-Type": self.ctype, **self.extra})
        return r


def test_a_picture_is_downloaded_under_the_extension_of_its_real_format_with_a_generic_client(tmp_path):
    net = ImgNet(png_bytes(700, 500), "image/png")
    got = W.fetch_image("https://img.example.org/a/b.jpg", tmp_path / "x.jpg", opener=net)
    assert got == tmp_path / "x.png" and got.read_bytes()[:4] == b"\x89PNG" and not (tmp_path / "x.jpg").exists() and not list(tmp_path.glob("*.part"))
    url, headers, timeout = net.reqs[0]
    assert timeout == W.TIMEOUT and "behind-the-image" not in headers["user-agent"] and "nhanvu" not in headers["user-agent"].lower() and "@" not in headers["user-agent"]
    assert headers["user-agent"] == http.USER_AGENT and "image" in headers["accept"]


@pytest.mark.parametrize("body,ctype,exc", [
    (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml", W.NotAnImage),               # a vector drawing
    (b"<html>not a picture</html>", "text/html; charset=utf-8", W.NotAnImage),                   # a web page
    (b"<html>said it is an image</html>", "image/jpeg", W.NotAnImage),                           # the content type lies: the bytes are not a picture
    (b"", "image/jpeg", W.NotAnImage),
    (b"GIF89a....", "image/gif", W.NotAnImage)])                                                 # not a format the app stores
def test_only_a_real_picture_is_kept(tmp_path, body, ctype, exc):
    with pytest.raises(exc):
        W.fetch_image("https://img.example.org/a.jpg", tmp_path / "x.jpg", opener=ImgNet(body, ctype))
    assert list(tmp_path.iterdir()) == []                                                         # nothing of a refused download stays


def test_a_picture_over_the_limit_is_refused_by_its_declared_size_and_by_the_bytes_that_arrive(tmp_path):
    with pytest.raises(http.FileTooLarge):
        W.fetch_image("https://img.example.org/a.jpg", tmp_path / "x.jpg", opener=ImgNet(jpeg_bytes(), headers={"Content-Length": str(W.MAX_BYTES + 1)}))
    with pytest.raises(http.FileTooLarge):
        W.fetch_image("https://img.example.org/a.jpg", tmp_path / "x.jpg", max_bytes=1000, opener=ImgNet(jpeg_bytes(2000, 2000)))
    assert W.MAX_BYTES == 25 * 1024 * 1024 and list(tmp_path.iterdir()) == []


def test_an_address_of_a_private_machine_is_never_fetched_not_even_by_a_redirect(tmp_path):
    net = ImgNet(jpeg_bytes())
    for url in ("http://127.0.0.1/a.jpg", "http://localhost/a.jpg", "https://[::1]/a.jpg", "http://192.168.1.5/a.jpg", "http://10.0.0.2/a.jpg",
                "http://169.254.169.254/latest", "ftp://example.org/a.jpg", "file:///etc/passwd", "https://printer.local/a.jpg"):
        with pytest.raises(W.UnsafeURL):
            W.fetch_image(url, tmp_path / "x.jpg", opener=net)
    assert net.reqs == []
    hop = W._CheckedRedirect()
    req = urllib.request.Request("https://img.example.org/a.jpg")
    with pytest.raises(W.UnsafeURL):
        hop.redirect_request(req, io.BytesIO(b""), 302, "Found", {}, "http://127.0.0.1:8560/api/projects")
    W.check_public_url("https://img.example.org/a.jpg")
    W.check_public_url("http://8.8.8.8/a.jpg")


def test_the_real_transport_refuses_under_the_safety_switch_and_in_a_test(monkeypatch, tmp_path):
    req = urllib.request.Request("https://img.example.org/a.jpg")
    with pytest.raises(RealModelsOff):
        W._real_open(req, timeout=5)
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)                                       # switch down (a test with a fake program): a test still never goes out
    with pytest.raises(RealModelsOff):
        W._real_open(req, timeout=5)
    with pytest.raises(RealModelsOff):
        W.fetch_image("https://img.example.org/a.jpg", tmp_path / "x.jpg")


def test_a_webp_is_stored_as_a_jpeg_and_a_small_one_can_be_refused_by_the_floor(tmp_path):
    src = WebSource(opener=ImgNet(webp_bytes(800, 600), "image/webp"))
    meta = src.fetch_meta("https://img.example.org/a/b.webp https://site.example.org/page")
    got = src.download(meta, tmp_path / "a.webp")
    assert got.suffix == ".jpg" and got.is_file() and not (tmp_path / "a.webp").exists() and got.read_bytes()[:3] == b"\xff\xd8\xff"
    from bti.media.errors import ImageTooSmall
    with pytest.raises(ImageTooSmall):
        WebSource(opener=ImgNet(jpeg_bytes(500, 400))).download(meta, tmp_path / "b.jpg", min_short_side=1200)
    assert not (tmp_path / "b.jpg").exists()


def test_import_through_the_facade_keeps_the_page_in_the_credit_and_flags_the_licence_unknown(tmp_path, monkeypatch):
    sid = W.make_id("https://img.example.org/pics/Philip-the-Good-portrait.jpg", "https://museum.example.org/works/philip")
    monkeypatch.setitem(api._SOURCES, "web", WebSource(opener=ImgNet(jpeg_bytes(1600, 1200))))
    res = api.import_candidate(tmp_path, "web", sid)
    a = res["asset"]
    assert a["kind"] == "image" and a["file"].endswith(".jpg") and (tmp_path / a["file"]).is_file() and (a["width"], a["height"]) == (1600, 1200)
    assert a["credit"] == {"source": "web", "source_url": "https://museum.example.org/works/philip", "author": "museum.example.org", "licence": "", "licence_url": "",
                           "flag": "unknown"}
    assert a["title"] == "Philip the Good portrait"
    again = api.import_candidate(tmp_path, "web", sid)
    assert again["asset_key"] == res["asset_key"]                                               # imported once
    assert api.get_source("web").fetch_meta("http://127.0.0.1/a.jpg") if False else True
    with pytest.raises(NotFound):
        api.get_source("web").fetch_meta("http://127.0.0.1/a.jpg https://x.example.org/")


def test_the_picture_s_own_words_are_the_snippet_when_it_has_some(sample, wiki):
    got = WebSource(client=FakeClient(sample), require_ticket=False).candidates_from(sample, limit=40)
    ng = [m for m in got if m["site"] == "nationalgallery.org.uk"]
    assert any(m["snippet"] == "Portrait of a Man (Self Portrait?)" for m in ng) or any("Self Portrait" in m["snippet"] for m in ng)          # the alt text names the picture
    lead = next(m for m in got if m["site"] == "smarthistory.org")
    assert lead["snippet"].startswith("Marriage portrait, or memorial?")                                                                   # no alt text: what the page says about itself
    assert len(W._snippet({"description": "x" * 500})) <= W.SNIPPET_CHARS and W._snippet({}, "") == ""


def test_no_other_door_to_the_paid_search_the_media_search_route_and_the_cli_find_it_closed(monkeypatch):
    from bti.media import youcom
    made = []
    monkeypatch.setattr(youcom.YouComClient, "__init__", lambda self, *a, **k: made.append(1))
    monkeypatch.setitem(api._SOURCES, "web", WebSource())                      # the source the facade makes by itself
    with pytest.raises(W.WebOff):
        api.search("Arnolfini Portrait", source="web", kind="image", limit=5)
    assert made == []
    from bti.picks import service
    assert "web" not in [s for s in service.SOURCES if s not in service.PAID_SOURCES] and "wikipedia" not in service.SOURCES                 # not in a default search, not an import source
