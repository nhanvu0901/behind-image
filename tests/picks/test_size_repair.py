"""Step 4 and the stored size of a picture: the picks document is repaired when it is loaded, the routes use the stored space,
and a source that says "too many requests" is answered with its own code and the wait. Fakes only: no request leaves the process."""
import copy
import json
import urllib.error
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from picks_helpers import FakeNet, load_fix, mount, png_bytes

from bti.editor.app import create_app
from bti.media import api as media_api
from bti.media.http import MediaHTTPError
from bti.media.sources.commons import CommonsSource
from bti.picks import doc, service
from bti.picks.errors import PicksError


def write_legacy(pdir, declared=(4000, 2000), stored=(400, 200), regions=None, approved=False, extra=None):
    """A picks.json written before the size rule: the asset declares `declared` pixels, its file has `stored`."""
    (pdir / "media").mkdir(exist_ok=True)
    (pdir / "media" / "a.png").write_bytes(png_bytes(*stored))
    asset = {"file": "media/a.png", "kind": "image", "title": "A", "artist": "", "year": "", "width": declared[0], "height": declared[1],
             "credit": {"source": "commons", "source_url": "u", "author": "x", "licence": "PD", "licence_url": "", "flag": None},
             "regions": regions if regions is not None else {}, **(extra or {})}
    raw = {"schema": doc.SCHEMA, "main_asset": "A", "assets": {"A": asset}, "beats": {}, "approval": {"approved": False, "sha1": None, "approved_at": None}}
    if approved:
        raw["approval"] = {"approved": True, "sha1": doc.revision(doc.normalize(raw)), "approved_at": "2026-11-18T10:00:00+00:00"}
    (pdir / "picks.json").write_text(json.dumps(raw), encoding="utf-8")
    return raw


EYE = {"EYE": {"x": 2000, "y": 1000, "rx": 400, "ry": 200, "label": "Eye"}}


def test_load_corrects_the_declared_size_and_the_regions_in_memory_only(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    before = (proj / "picks.json").read_text(encoding="utf-8")
    d = doc.load(proj)
    a = d["assets"]["A"]
    assert (a["width"], a["height"]) == (400, 200) and (a["original_width"], a["original_height"]) == (4000, 2000)
    assert a["regions"]["EYE"] == {"x": 200, "y": 100, "rx": 40, "ry": 20, "label": "Eye"}
    assert (proj / "picks.json").read_text(encoding="utf-8") == before            # reading writes nothing


def test_the_correction_reaches_the_disk_with_the_next_save_and_is_stable(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    d = doc.load(proj)
    rev = doc.revision(d)
    with doc.Held(proj):
        assert doc.save(proj, d) == rev
    on_disk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]
    assert (on_disk["width"], on_disk["height"]) == (400, 200) and on_disk["regions"]["EYE"]["x"] == 200
    assert (on_disk["original_width"], on_disk["original_height"]) == (4000, 2000)
    again = doc.load(proj)
    assert again == d and doc.revision(again) == rev                               # idempotent: loading a repaired file changes nothing


def test_an_asset_without_regions_is_repaired_too(proj):
    write_legacy(proj)
    a = doc.load(proj)["assets"]["A"]
    assert (a["width"], a["height"]) == (400, 200) and a["regions"] == {}


def test_a_document_that_already_agrees_is_untouched(proj):
    raw = write_legacy(proj, declared=(400, 200), regions={"EYE": {"x": 200, "y": 100, "label": ""}})
    d = doc.load(proj)
    assert d["assets"]["A"]["regions"]["EYE"]["x"] == 200 and "original_width" not in d["assets"]["A"]
    assert (d["assets"]["A"]["width"], d["assets"]["A"]["height"]) == (400, 200) and raw["assets"]["A"]["width"] == 400


def test_a_missing_or_damaged_file_leaves_the_record_alone(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    (proj / "media" / "a.png").write_bytes(b"junk")
    assert doc.load(proj)["assets"]["A"]["width"] == 4000
    (proj / "media" / "a.png").unlink()
    a = doc.load(proj)["assets"]["A"]
    assert (a["width"], a["height"]) == (4000, 2000) and a["regions"]["EYE"]["x"] == 2000


def test_the_original_size_is_kept_by_the_document(proj):
    d = doc.normalize({"assets": {"A": {"file": "m/a.jpg", "width": 3840, "height": 4767, "original_width": 6703, "original_height": 8322},
                                  "B": {"file": "m/b.jpg", "original_width": -5, "original_height": "big"}}})
    assert (d["assets"]["A"]["original_width"], d["assets"]["A"]["original_height"]) == (6703, 8322)
    assert "original_width" not in d["assets"]["B"] and "original_height" not in d["assets"]["B"]


def test_the_page_state_and_the_region_check_use_the_stored_space(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    p = service.payload(proj, proj.name)
    a = p["picks"]["assets"]["A"]
    assert (a["width"], a["height"]) == (400, 200) and a["regions"]["EYE"]["x"] == 200
    assert p["rev"] == doc.revision(doc.load(proj))
    with pytest.raises(PicksError) as e:                                            # a point of the OLD space is now outside the picture
        service.set_regions(proj, "A", {"FAR": {"x": 2000, "y": 1000}}, base_rev=p["rev"])
    assert e.value.code == "region_outside"
    rev = service.set_regions(proj, "A", {"EYE": {"x": 210, "y": 90, "label": "Eye"}}, base_rev=p["rev"])
    on_disk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]
    assert (on_disk["width"], on_disk["height"]) == (400, 200) and on_disk["regions"]["EYE"]["x"] == 210    # saved: repaired and persisted
    assert rev == doc.revision(doc.load(proj))


def test_the_save_of_the_whole_page_persists_the_repair_and_keeps_the_original_size(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    p = service.payload(proj, proj.name)
    rev = service.put(proj, p["picks"], p["rev"])                                   # what the page sends back after an edit
    on_disk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))["assets"]["A"]
    assert (on_disk["width"], on_disk["height"]) == (400, 200) and (on_disk["original_width"], on_disk["original_height"]) == (4000, 2000)
    assert on_disk["regions"]["EYE"]["rx"] == 40 and rev == doc.revision(doc.load(proj))


def test_a_page_that_still_holds_the_old_document_is_told_to_reload(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE))
    old_rev = doc.revision(doc.normalize(json.loads((proj / "picks.json").read_text(encoding="utf-8"))))   # the revision it had before the repair
    with pytest.raises(PicksError) as e:
        service.set_regions(proj, "A", {"EYE": {"x": 2100, "y": 1000}}, base_rev=old_rev)
    assert e.value.code == "stale"


def test_an_approval_given_before_the_repair_must_be_given_again_and_that_writes_the_repair(proj):
    write_legacy(proj, regions=copy.deepcopy(EYE), approved=True)
    p = service.payload(proj, proj.name)
    assert p["approved"] is False and p["approval_reason"] == "picks_edited"
    ap = service.approve(proj, p["rev"])
    assert ap["approved"] is True
    on_disk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    assert on_disk["assets"]["A"]["width"] == 400 and on_disk["approval"]["approved"] is True
    assert service.payload(proj, proj.name)["approved"] is True


def test_a_video_is_not_touched(proj):
    raw = write_legacy(proj)
    raw["assets"]["A"]["kind"] = "video"
    raw["assets"]["A"]["width"], raw["assets"]["A"]["height"] = 1920, 1080
    (proj / "picks.json").write_text(json.dumps(raw), encoding="utf-8")
    a = doc.load(proj)["assets"]["A"]
    assert (a["width"], a["height"]) == (1920, 1080)


# ---------------------------------------------------------------- "too many requests"
@pytest.mark.parametrize("status,retry_after,code,extra", [
    (429, 600, "source_rate_limited", {"retry_after": 600}),
    (429, None, "source_rate_limited", {"retry_after": None}),
    (503, 90, "source_rate_limited", {"retry_after": 90}),
    (503, None, "source_unreachable", {}),
    (502, None, "source_unreachable", {}),
    (504, None, "source_unreachable", {}),
    (404, None, "source_error", {}),
])
def test_what_the_download_layer_says_becomes_the_right_code(status, retry_after, code, extra):
    pe = service._translate(MediaHTTPError("HTTP %s" % status, status, retry_after=retry_after))
    assert pe.code == code and pe.status in (503, 502)
    for k, v in extra.items():
        assert pe.extra[k] == v
    assert ("retryable" in pe.extra) == (code != "source_error")


COMMONS = {p["pageid"]: p for p in load_fix("commons_search.json")["query"]["pages"]}
PD_ID = "File:Jan van Eyck - The Arnolfini Portrait - Google Art Project.jpg"


@pytest.fixture
def commons(monkeypatch):
    def install(routes):
        net = FakeNet(routes)
        monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
        return net
    return install


@pytest.fixture
def client(root, proj):
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app) as c:
        c.pid, c.pdir = proj.name, proj
        c.u = lambda tail="": f"/api/projects/{proj.name}/picks{tail}"
        yield c


def limited(retry_after=None):
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {} if retry_after is None else {"Retry-After": str(retry_after)}, None)


def test_import_answers_429_with_its_own_code_and_the_wait_and_sends_one_request(client, commons):
    net = commons([("commons.wikimedia.org", limited(180))])
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})
    assert r.status_code == 503 and r.json()["code"] == "source_rate_limited" and r.json()["retry_after"] == 180
    assert r.json()["retryable"] is True and len(net.urls) == 1                     # one request, no retry loop
    assert not (client.pdir / "picks.json").exists()


def test_a_second_try_inside_the_wait_sends_nothing_to_the_source(client, commons):
    net = commons([("commons.wikimedia.org", limited(180))])
    client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})
    assert len(net.urls) == 1 and r.json()["code"] == "source_rate_limited" and 0 < r.json()["retry_after"] <= 180


def test_import_answers_429_without_a_time_with_a_null_wait(client, commons):
    # fixes4: a download is patient: no time given, so it waits 10, 30, 90 s (no real sleep here) and asks again, three times: four requests, then the refusal
    net = commons([("commons.wikimedia.org", limited())])
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})
    assert r.json()["code"] == "source_rate_limited" and r.json()["retry_after"] is None and len(net.urls) == 4
    again = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID})      # no time given: nothing is remembered
    assert len(net.urls) == 8 and again.json()["code"] == "source_rate_limited"


def test_search_lists_the_limited_source_with_its_wait(client, commons, monkeypatch):
    commons([("commons.wikimedia.org", limited(300))])
    r = client.post(client.u("/search"), json={"query": "Arnolfini", "sources": ["commons"]}).json()
    assert r["items"] == [] and r["errors"] == [{"source": "commons", "code": "source_rate_limited", "message": r["errors"][0]["message"],
                                                  "retry_after": 300}]


def test_the_import_of_a_large_original_records_the_stored_pixels_and_the_page_uses_them(client, commons):
    page = copy.deepcopy(COMMONS[2])
    page["imageinfo"][0].update(width=6703, height=8322, size=30_000_000)
    rendition = {"query": {"pages": [{"title": "File:x", "imageinfo": [{"url": page["imageinfo"][0]["url"], "thumburl": "https://upload.wikimedia.org/thumb/x/3840px-x.jpg"}]}]}}
    net = commons([("iiurlwidth=3840", rendition), ("Google+Art+Project", {"query": {"pages": [page]}}),
                   ("3840px-x.jpg", png_bytes(384, 477))])
    r = client.post(client.u("/import"), json={"source": "commons", "source_id": PD_ID, "as_main": True})
    assert r.status_code == 200, r.text
    a = r.json()["asset"]
    key = r.json()["asset_key"]
    assert (a["width"], a["height"]) == (384, 477) and (a["original_width"], a["original_height"]) == (6703, 8322)
    saved = json.loads((client.pdir / "picks.json").read_text(encoding="utf-8"))["assets"][key]
    assert (saved["width"], saved["height"]) == (384, 477)
    url = client.u(f"/assets/{key}/regions")
    assert client.put(url, json={"regions": {"FACE": {"x": 190, "y": 200, "rx": 30, "ry": 40}}}).status_code == 200
    assert client.put(url, json={"regions": {"FACE": {"x": 3000, "y": 200}}}).json()["code"] == "region_outside"      # 3000 is inside the ORIGINAL, outside the file
    asked = [int(v) for u in net.urls for v in parse_qs(urlparse(u).query).get("iiurlwidth", [])]
    assert sorted(asked) == [330, 3840]                                             # the card thumbnail and the one rendition, both standard widths
