"""Part 2 of the automatic picks job (search, code only): what each source is asked, the caps, the thumbnails, the pictures of the owner's books."""
import json
import time
from pathlib import Path

import pytest
from auto_fixtures import env, paid  # noqa: F401
from auto_helpers import CHOICE, PLAN, FakeSource, PNG, choice, fake_thumb, install_sources, meta, plan

from bti.media import http as mhttp
from bti.picks.auto import search as asearch, shapes, store


CTX = {"type": "context", "search": "Bruges canal", "alt": ["Bruges old town"], "kind": "photo", "what": "Kênh đào ở Bruges"}


def want(**kw):
    base = {"id": "b0001.1", "beat": "b0001", "n": 1, **CTX}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------------------------------------------- which source, which query
def test_each_kind_of_want_asks_its_own_sources(monkeypatch):
    install_sources(monkeypatch, {}, keys=())
    assert asearch.sources_for(want(kind="work")) == ["commons", "met"] and asearch.sources_for(want(kind="portrait")) == ["commons", "met"]
    assert asearch.sources_for(want(kind="document")) == ["commons", "met"]
    assert asearch.sources_for(want(kind="photo")) == ["commons"]                               # stock photographs need a key that is not set
    assert asearch.sources_for(want(type="map", place="Oslo")) == ["osm"] and asearch.sources_for(want(type="clip")) == ["commons"]
    install_sources(monkeypatch, {}, keys=("pexels", "pixabay"))
    assert asearch.sources_for(want(kind="photo")) == ["commons", "pexels", "pixabay"] and asearch.sources_for(want(kind="place")) == ["commons", "pexels", "pixabay"]
    assert asearch.sources_for(want(kind="other")) == ["commons", "met", "pexels", "pixabay"]
    assert asearch.sources_for(want(type="clip")) == ["pexels", "pixabay", "commons"]
    assert asearch.queries_for(want()) == ["Bruges canal", "Bruges old town"] and asearch.queries_for(want(type="map", place="Oslo")) == ["Oslo"]


def run_search(env, wants, *, state=None, **kw):
    saved = []
    seams = dict(main_key="A", cancelled=lambda: False, progress=lambda f, n: None, save=lambda s: saved.append(json.loads(json.dumps(s))),
                 fetch_thumb=fake_thumb)
    seams.update(kw)
    st = asearch.run(env.pdir, {}, state, wants, **seams)
    return st, saved


def test_stock_photographs_are_asked_when_their_keys_are_set_and_the_candidates_are_mixed(env, monkeypatch):
    pexels = FakeSource("pexels", [meta("pexels", "p1", "Canal 1", "bruges"), meta("pexels", "p2", "Canal 2", "bruges")])
    pixabay = FakeSource("pixabay", [meta("pixabay", "x1", "Canal 3", "bruges")])
    commons = FakeSource("commons", [meta("commons", "File:c%d.jpg" % i, "Canal c%d" % i, "bruges") for i in range(1, 5)])
    install_sources(monkeypatch, {"commons": commons, "pexels": pexels, "pixabay": pixabay}, keys=("pexels", "pixabay"))
    st, saved = run_search(env, [want()])
    w = st["wants"]["b0001.1"]
    assert [q for q, k, n in commons.searches] == ["Bruges canal"] and [q for q, k, n in pexels.searches] == ["Bruges canal"]       # enough found: no alternative query
    assert w["status"] == "found" and len(w["candidates"]) == 6                                                                  # six at most
    assert [c["source"] for c in w["candidates"]][:3] == ["commons", "pexels", "pixabay"]                                         # one from each source in turn
    assert [c["n"] for c in w["candidates"]] == [1, 2, 3, 4, 5, 6] and all(c["thumb"] for c in w["candidates"])
    assert saved and saved[-1]["wants"]["b0001.1"]["status"] == "found"                                                         # saved after the want


def test_the_alternative_words_are_tried_only_while_few_candidates_were_found(env, monkeypatch):
    commons = FakeSource("commons", [meta("commons", "File:a.jpg", "A", "bruges canal")])
    install_sources(monkeypatch, {"commons": commons, "met": FakeSource("met")}, keys=())
    st, _ = run_search(env, [want(kind="work")])
    assert [q for q, k, n in commons.searches] == ["Bruges canal", "Bruges old town"]               # one found (< 3): the alternative is asked too
    assert [n for q, k, n in commons.searches] == [asearch.FIRST_LIMIT, asearch.MORE_LIMIT]
    assert st["wants"]["b0001.1"]["status"] == "found" and len(st["wants"]["b0001.1"]["candidates"]) == 1


def test_a_clip_is_searched_as_video_and_a_map_by_name(env, monkeypatch):
    commons = FakeSource("commons", [meta("commons", "File:v.mp4", "Canal film", "canal", kind="video"), meta("commons", "File:i.jpg", "Canal still", "canal")])
    osm = FakeSource("osm", [meta("osm", "1:12:51.2:3.2:Bruges", "Bản đồ Bruges", "bruges")])
    install_sources(monkeypatch, {"commons": commons, "osm": osm}, keys=())
    clip = want(id="b0001.1", type="clip", search="canal", alt=[], seconds=6, what="Kênh")
    mp = want(id="b0001.2", n=2, type="map", place="Bruges, Belgium", what="Bản đồ")
    st, _ = run_search(env, [clip, mp])
    assert [(q, k) for q, k, n in commons.searches] == [("canal", "video")] and [c["media"] for c in st["wants"]["b0001.1"]["candidates"]] == ["video"]
    assert [q for q, k, n in osm.searches] == ["Bruges, Belgium"]
    m = st["wants"]["b0001.2"]
    assert m["status"] == "found" and m["candidates"][0]["thumb"] is None and m["candidates"][0]["n"] == 1                       # a map has no thumbnail: its candidate is a place


def test_the_main_painting_found_by_the_search_is_never_a_candidate(env, monkeypatch):
    from bti.media import assets as massets
    commons = FakeSource("commons", [meta("commons", "File:main.jpg", "The Test Painting", "bruges"), meta("commons", "File:b.jpg", "B", "bruges")])
    install_sources(monkeypatch, {"commons": commons, "met": FakeSource("met")}, keys=())
    idx = massets.load_index(env.pdir)
    idx["items"]["commons:File:main.jpg"] = {"key": "A", "asset": env.picks()["assets"]["A"]}
    massets.save_index(env.pdir, idx)
    st, _ = run_search(env, [want(kind="work", alt=[])])
    assert [c["source_id"] for c in st["wants"]["b0001.1"]["candidates"]] == ["File:b.jpg"]


# ---------------------------------------------------------------------------------------------------------------- what happens when a source fails
def test_a_failing_source_is_a_failed_want_only_when_nothing_else_answered(env, monkeypatch):
    commons = FakeSource("commons", fail=RuntimeError("boom"))
    met = FakeSource("met", [meta("met", "1", "Met 1", "bruges")])
    install_sources(monkeypatch, {"commons": commons, "met": met}, keys=())
    st, _ = run_search(env, [want(kind="work")])
    assert st["wants"]["b0001.1"]["status"] == "found" and [c["source"] for c in st["wants"]["b0001.1"]["candidates"]] == ["met"]
    install_sources(monkeypatch, {"commons": FakeSource("commons", fail=RuntimeError("boom")), "met": FakeSource("met", fail=RuntimeError("boom"))}, keys=())
    st, _ = run_search(env, [want(kind="work")])
    w = st["wants"]["b0001.1"]
    assert (w["status"], w["code"]) == ("none", "search_failed") and w["candidates"] == []


def test_a_wait_the_source_asked_for_is_kept_for_the_run_and_a_resumed_search_tries_again(env, monkeypatch):
    clock = {"t": 1000.0}
    commons = FakeSource("commons", fail=mhttp.MediaHTTPError("HTTP 429", 429, retry_after=90))
    install_sources(monkeypatch, {"commons": commons, "met": FakeSource("met")}, keys=())
    w1, w2 = want(kind="work", alt=[]), want(id="b0001.2", n=2, kind="work", alt=[])
    st, _ = run_search(env, [w1, w2], clock=lambda: clock["t"])
    assert len(commons.searches) == 1                                                       # the second want did not ask a source that said "wait"
    assert [(w["status"], w["code"], w["seconds"]) for w in st["wants"].values()] == [("limited", "source_limited", 90)] * 2
    assert asearch.todo(st) == ["b0001.1", "b0001.2"]
    # a moment later, with the wait not over: still left alone. After it: asked again, and found
    clock["t"] += 30
    st, _ = run_search(env, [w1, w2], state=st, clock=lambda: clock["t"])
    assert len(commons.searches) == 1 and st["wants"]["b0001.1"]["seconds"] == 60
    clock["t"] += 100
    commons.fail, commons.items = None, [meta("commons", "File:a.jpg", "A", "")]
    st, _ = run_search(env, [w1, w2], state=st, clock=lambda: clock["t"])
    assert asearch.todo(st) == [] and st["wants"]["b0001.1"]["status"] == "found"


def test_the_time_the_search_may_take_is_capped_and_cancel_stops_it_between_wants(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons", [meta("commons", "File:a.jpg", "A", "")]), "met": FakeSource("met")}, keys=())
    ws = [want(id="b0001.%d" % n, n=n, kind="work", alt=[]) for n in (1, 2, 3)]
    t = {"now": 0.0}

    def clock():
        t["now"] += 400.0                                           # every look at the clock costs 400 s: the cap of 600 s is passed after the first want
        return t["now"]
    st, _ = run_search(env, ws, clock=clock, budget_s=600)
    assert [w["status"] for w in st["wants"].values()] == ["found", "pending", "pending"] and st["wants"]["b0001.2"]["code"] == "time_up"
    n = {"calls": 0}

    def cancelled():
        n["calls"] += 1
        return n["calls"] > 3
    st, saved = run_search(env, ws, cancelled=cancelled)
    assert [w["status"] for w in st["wants"].values()].count("found") < 3 and saved                       # it stopped, and what was done was saved


# ---------------------------------------------------------------------------------------------------------------- thumbnails
def test_a_thumbnail_is_downloaded_once_scaled_and_kept(env, monkeypatch, tmp_path):
    got = []

    def download(url, dest, *, max_bytes, **kw):
        got.append(url)
        Path(dest).write_bytes(PNG)
        return dest
    monkeypatch.setattr(mhttp, "download_file", download)
    c = {"source": "commons", "source_id": "File:t.jpg", "thumb_url": "https://upload.example/t.jpg"}
    rel = asearch.default_fetch_thumb(env.pdir, c)
    assert rel.startswith("cache/picks_auto/thumbs/") and rel.endswith(".jpg") and (env.pdir / rel).is_file()
    from bti.picks.auto import images
    assert max(images.read(env.pdir / rel).shape[:2]) == 640
    assert not list((env.pdir / "cache" / "picks_auto" / "thumbs").glob("*.raw"))                      # the raw download is not left behind
    assert asearch.default_fetch_thumb(env.pdir, c) == rel and got == ["https://upload.example/t.jpg"]  # the second call is the cache
    assert asearch.default_fetch_thumb(env.pdir, {**c, "source_id": "x", "thumb_url": "ftp://nope"}) is None
    assert asearch.default_fetch_thumb(env.pdir, {**c, "source_id": "y", "thumb_url": ""}) is None
    local = tmp_path / "map.jpg"
    local.write_bytes(PNG)
    import cv2
    cv2.imwrite(str(local), cv2.imread(str(env.pdir / rel)))
    assert asearch.default_fetch_thumb(env.pdir, {**c, "source_id": "z", "thumb_url": str(local)}) is not None            # a map the app drew earlier is a local file


def test_a_thumbnail_that_is_refused_costs_only_its_candidate_and_remembers_the_wait(env, monkeypatch):
    def refuse(url, dest, **kw):
        raise mhttp.MediaHTTPError("HTTP 429", 429, retry_after=40)
    monkeypatch.setattr(mhttp, "download_file", refuse)
    limited = {}
    assert asearch.default_fetch_thumb(env.pdir, {"source": "commons", "source_id": "q", "thumb_url": "https://x/q.jpg"}, limited, lambda: 100.0) is None
    assert limited == {"commons": 140.0}

    def garbage(url, dest, **kw):
        Path(dest).write_bytes(b"not a picture")
        return dest
    monkeypatch.setattr(mhttp, "download_file", garbage)
    assert asearch.default_fetch_thumb(env.pdir, {"source": "commons", "source_id": "g", "thumb_url": "https://x/g.jpg"}) is None
    assert not list((env.pdir / "cache" / "picks_auto" / "thumbs").glob("*.raw"))


def test_no_thumbnail_is_ever_fetched_for_real_in_a_test(env):
    with pytest.raises(Exception):
        mhttp.open_url("https://example.invalid/x.jpg")                                           # BTI_NO_REAL_MODELS: no real request can leave a test


# ---------------------------------------------------------------------------------------------------------------- the owner's books
def test_the_pictures_of_the_books_are_numbered_with_thumbnails_and_the_main_painting_is_left_out(env):
    from bti.picks.auto import search
    books = search.collect_books(env.pdir, "A", fetch=lambda pdir, it: fake_thumb(pdir, {"source": "book", "source_id": it["source_id"]}))
    assert [(b["n"], b["source_id"]) for b in books] == [(1, "payne_gae/img/850")] and "ảnh trang 23" in books[0]["label"] and books[0]["thumb"]
    assert search.collect_books(env.pdir, "A", fetch=lambda pdir, it: None) == []                  # a picture with no thumbnail cannot be looked at: not offered
    from bti.media import assets as massets
    idx = massets.load_index(env.pdir)
    idx["items"]["book:payne_gae/img/850"] = {"key": "A", "asset": env.picks()["assets"]["A"]}
    massets.save_index(env.pdir, idx)
    assert search.collect_books(env.pdir, "A", fetch=lambda pdir, it: fake_thumb(pdir, {"source": "book", "source_id": it["source_id"]})) == []


def test_a_picture_of_the_books_can_be_the_choice_for_a_context_picture(env, monkeypatch):
    from bti.media.sources.bookpage import BookPageSource
    monkeypatch.setitem(__import__("bti.media.api", fromlist=["x"])._SOURCES, "book", BookPageSource(renderer=lambda b, k, r, dest: Path(dest).write_bytes(PNG)))
    env.agent.choice = choice(wants=[{"id": "b0003.1", "pick": "B1", "reason": "Hình trong sách của bạn đúng ý."}, *CHOICE["wants"][1:]])
    job = env.run()
    assert job["state"] == "done", job.get("error")
    d = env.picks()
    item = d["beats"]["b0003"]["items"][0]
    assert item["role"] == "context" and item["asset"] != "A" and d["assets"][item["asset"]]["credit"]["source"] == "book"
    assert item["note"] == "Hình trong sách của bạn đúng ý."
    choose_call = env.agent.calls[1]
    assert "images/books_1.jpg" in choose_call["files"]


# ---------------------------------------------------------------------------------------------------------------- websearch: Wikipedia first, and the web
class WikiFake(FakeSource):
    """The Wikipedia source: its candidates are Commons files that say where they came from (the article, the site, a few words)."""

    def __init__(self, items=None, fail=None):
        super().__init__("wikipedia", items, fail)


def wmeta(sid, title="Noyon Cathedral", q="", **kw):
    return meta("commons", sid, "Picture " + sid, q, page_title=title, site="Wikipedia", snippet="Cathedral in France", via="wikipedia", **kw)


def ctx_want(**kw):
    base = dict(entity="Noyon Cathedral", search="Noyon Cathedral facade", alt=["Noyon cathedral nave"], kind="place", what="Nhà thờ Noyon")
    base.update(kw)
    return want(**base)


def test_a_context_want_asks_wikipedia_first_by_its_entity_and_then_the_free_sources(env, monkeypatch):
    wiki = WikiFake([wmeta("File:Noyon A.jpg"), wmeta("File:Noyon B.jpg")])
    commons = FakeSource("commons", [meta("commons", "File:C1.jpg", "C1", "noyon"), meta("commons", "File:C2.jpg", "C2", "noyon")])
    install_sources(monkeypatch, {"commons": commons, "wikipedia": wiki}, keys=())
    st, _ = run_search(env, [ctx_want()])
    w = st["wants"]["b0001.1"]
    assert [q for q, k, n in wiki.searches] == ["Noyon Cathedral"] and wiki.searches[0][2] == asearch.WIKI_LIMIT          # the name of the thing, not the plan's words
    assert [q for q, k, n in commons.searches] == ["Noyon Cathedral facade"]                                           # the free sources keep the plan's words
    assert [c["source_id"] for c in w["candidates"]][:2] == ["File:Noyon A.jpg", "File:Noyon B.jpg"] or w["candidates"][0]["via"] == "wikipedia"
    assert w["candidates"][0]["via"] == "wikipedia" and w["candidates"][0]["page_title"] == "Noyon Cathedral" and w["candidates"][0]["site"] == "Wikipedia"
    assert w["candidates"][0]["snippet"] == "Cathedral in France" and w["entity"] == "Noyon Cathedral" and w["period"] == "then"
    assert [c["source"] for c in w["candidates"]][:2] == ["commons", "commons"] and w["status"] == "found"


def test_wikipedia_is_asked_with_the_plans_words_when_there_is_no_entity_and_a_second_time_only_when_the_first_found_nothing(env, monkeypatch):
    wiki = WikiFake([wmeta("File:Noyon A.jpg", q="facade")])
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": wiki}, keys=())
    run_search(env, [ctx_want(entity="")])
    assert [q for q, k, n in wiki.searches] == ["Noyon Cathedral facade"]
    wiki.searches.clear()
    run_search(env, [ctx_want()])                                                          # the entity finds nothing ("noyon cathedral" is not in the item's words): the plan's words are asked too
    assert [q for q, k, n in wiki.searches] == ["Noyon Cathedral", "Noyon Cathedral facade"]
    wiki2 = WikiFake([wmeta("File:Noyon A.jpg", q="noyon")])
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": wiki2}, keys=())
    run_search(env, [ctx_want()])
    assert [q for q, k, n in wiki2.searches] == ["Noyon Cathedral"]                       # found: one ask


def test_a_map_and_a_clip_never_ask_wikipedia(env, monkeypatch):
    wiki = WikiFake([wmeta("File:Noyon A.jpg")])
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "osm": FakeSource("osm", [meta("osm", "1:12:51.2:3.2:Bruges", "Bruges", "bruges")]), "wikipedia": wiki}, keys=())
    run_search(env, [want(type="map", place="Bruges, Belgium", what="Bản đồ"), want(id="b0001.2", n=2, type="clip", search="canal", alt=[], seconds=6, what="Kênh")])
    assert wiki.searches == []


def test_wikipedia_that_fails_never_makes_a_want_a_failed_one_and_a_wait_it_asks_for_is_kept(env, monkeypatch):
    wiki = WikiFake(fail=RuntimeError("boom"))
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": wiki}, keys=())
    st, _ = run_search(env, [ctx_want(kind="work")])
    assert (st["wants"]["b0001.1"]["status"], st["wants"]["b0001.1"]["code"]) == ("none", "no_candidates")          # Commons answered (with nothing): not "search failed"
    clock = {"t": 1000.0}
    wiki = WikiFake(fail=mhttp.MediaHTTPError("HTTP 429", 429, retry_after=90))
    install_sources(monkeypatch, {"commons": FakeSource("commons", [meta("commons", "File:a.jpg", "A", "")]), "wikipedia": wiki}, keys=())
    st, _ = run_search(env, [ctx_want(), ctx_want(id="b0001.2", n=2)], clock=lambda: clock["t"])
    assert len(wiki.searches) == 1 and st["limited"]["wikipedia"] == 1090.0                                           # the second want left it alone
    assert [w["status"] for w in st["wants"].values()] == ["found", "found"]


def test_up_to_eight_candidates_when_wikipedia_or_the_web_gave_some_and_six_otherwise(env, monkeypatch):
    wiki = WikiFake([wmeta("File:W%d.jpg" % i, q="noyon") for i in range(1, 6)])
    commons = FakeSource("commons", [meta("commons", "File:C%d.jpg" % i, "C%d" % i, "noyon") for i in range(1, 7)])
    install_sources(monkeypatch, {"commons": commons, "wikipedia": wiki}, keys=())
    st, _ = run_search(env, [ctx_want(kind="work")])
    c = st["wants"]["b0001.1"]["candidates"]
    assert len(c) == asearch.PER_WANT_WEB == 8 and [x["via"] if x.get("via") else "c" for x in c][:4] == ["wikipedia", "c", "wikipedia", "c"]      # mixed, Wikipedia's first
    install_sources(monkeypatch, {"commons": commons, "wikipedia": WikiFake()}, keys=())
    st, _ = run_search(env, [ctx_want(kind="work")])
    assert len(st["wants"]["b0001.1"]["candidates"]) == asearch.PER_WANT == 6


def test_spare_wikipedia_candidates_replace_the_ones_whose_thumbnail_cannot_be_had(env, monkeypatch):
    wiki = WikiFake([wmeta("File:W%d.jpg" % i, q="noyon") for i in (1, 2)] + [wmeta("File:nothumb W3.jpg", q="noyon"), wmeta("File:nothumb W4.jpg", q="noyon")]
                    + [wmeta("File:W%d.jpg" % i, q="noyon") for i in (5, 6, 7, 8, 9, 10)])
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": wiki}, keys=())
    st, _ = run_search(env, [ctx_want(kind="work")])
    ids = [c["source_id"] for c in st["wants"]["b0001.1"]["candidates"]]
    assert len(ids) == 8 and not any("nothumb" in i for i in ids) and ids[-1].startswith("File:W")                  # eight with a thumbnail: two spares took the place of the two that had none
    assert [c["n"] for c in st["wants"]["b0001.1"]["candidates"]] == list(range(1, 9))


# ---- the paid web search of round one
def web_fake(answers=None, errors=None):
    """The `Web.search` seam: `answers` maps a query to the items it finds; every call is recorded."""
    calls = []

    def search(pdir, query, limit):
        calls.append((query, limit))
        return {"items": [dict(m) for m in (answers or {}).get(query, [])], "errors": list((errors or {}).get(query, []))}
    search.calls = calls
    return search


def wcard(sid, title="A page", site="museum.example.org", **kw):
    return {"source": "web", "source_id": sid, "title": title, "page_title": title, "site": site, "via": "web", "snippet": "About it", "licence": "", "flag": "unknown",
            "thumb_url": sid.split()[0], "page_url": "https://%s/p" % site, "width": 0, "height": 0, "mime": "image/jpeg", "author": site, **kw}


def test_the_web_is_asked_once_for_a_want_that_has_fewer_than_three_candidates_and_it_is_counted(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons", [meta("commons", "File:a.jpg", "A", "noyon")]), "wikipedia": WikiFake()}, keys=())
    fake = web_fake({"Noyon Cathedral facade": [wcard("https://img.example.org/a.jpg https://museum.example.org/p"), wcard("https://img.example.org/b.jpg https://museum.example.org/p")]})
    web = asearch.Web(on=True, max=5, search=fake)
    st, saved = run_search(env, [ctx_want(kind="work")], web=web)
    w = st["wants"]["b0001.1"]
    assert fake.calls == [("Noyon Cathedral facade", asearch.WEB_LIMIT)] and web.spent == 1                        # the plan's words, once, counted
    assert [c["source"] for c in w["candidates"]] == ["web", "commons", "web"] or [c["source"] for c in w["candidates"]][0] == "web"   # the web's candidates go first
    assert all(c["thumb"] for c in w["candidates"]) and w["web"] == {"queries": ["Noyon Cathedral facade"]}
    assert st["web"] == {"on": True, "max": 5, "searches": 1, "stopped": None} and saved[-1]["web"]["searches"] == 1          # kept in search.json
    assert [c["page_title"] for c in w["candidates"] if c["source"] == "web"] == ["A page", "A page"] and w["candidates"][0]["site"] == "museum.example.org"


def test_enough_candidates_from_the_free_sources_mean_no_web_search_and_a_switch_that_is_off_means_none_at_all(env, monkeypatch):
    commons = FakeSource("commons", [meta("commons", "File:c%d.jpg" % i, "C%d" % i, "noyon") for i in range(1, 5)])
    install_sources(monkeypatch, {"commons": commons, "wikipedia": WikiFake()}, keys=())
    fake = web_fake({"Noyon Cathedral facade": [wcard("https://img.example.org/a.jpg")]})
    web = asearch.Web(on=True, max=5, search=fake)
    run_search(env, [ctx_want(kind="work")], web=web)
    assert fake.calls == [] and web.spent == 0
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    st, _ = run_search(env, [ctx_want(kind="work")], web=None)                                              # no `Web` = the owner's switch is off: no way to a paid call
    assert fake.calls == [] and "web" not in st and st["wants"]["b0001.1"]["code"] == "no_candidates"
    st, _ = run_search(env, [ctx_want(kind="work")], web=asearch.Web(on=False, max=5, search=fake))
    assert fake.calls == []


def test_outside_or_compare_context_want_searches_web_in_round_one_even_with_three_or_more_free_candidates(env, monkeypatch):
    commons = FakeSource("commons", [meta("commons", "File:c%d.jpg" % i, "C%d" % i, "noyon") for i in range(1, 5)])
    install_sources(monkeypatch, {"commons": commons, "wikipedia": WikiFake()}, keys=())
    fake = web_fake({"Noyon Cathedral facade": [wcard("https://img.example.org/a.jpg")]})
    web = asearch.Web(on=True, max=5, search=fake)
    # Line of kind "outside": web is searched in round one although free sources brought 4 candidates (>= 3)
    run_search(env, [ctx_want(kind="work", kinds=["outside"])], web=web)
    assert fake.calls == [("Noyon Cathedral facade", asearch.WEB_LIMIT)] and web.spent == 1
    # Line of kind "compare": web is also searched in round one
    fake.calls.clear()
    web.spent = 0
    run_search(env, [ctx_want(kind="work", kinds=["compare"])], web=web)
    assert fake.calls == [("Noyon Cathedral facade", asearch.WEB_LIMIT)] and web.spent == 1


def test_stock_sources_are_not_asked_for_then_want_and_still_are_for_now_want(monkeypatch):
    install_sources(monkeypatch, {}, keys=("pexels", "pixabay"))
    # period "then": stock sources are never asked
    assert asearch.sources_for(want(kind="photo", period="then")) == ["commons"]
    assert asearch.sources_for(want(kind="place", period="then")) == ["commons"]
    assert asearch.sources_for(want(kind="event", period="then")) == ["commons"]
    assert asearch.sources_for(want(kind="other", period="then")) == ["commons", "met"]
    # period "now": stock sources are asked
    assert asearch.sources_for(want(kind="photo", period="now")) == ["commons", "pexels", "pixabay"]
    assert asearch.sources_for(want(kind="place", period="now")) == ["commons", "pexels", "pixabay"]
    assert asearch.sources_for(want(kind="event", period="now")) == ["commons", "pexels", "pixabay"]
    assert asearch.sources_for(want(kind="other", period="now")) == ["commons", "met", "pexels", "pixabay"]


def test_only_context_pictures_are_searched_on_the_web(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "osm": FakeSource("osm"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake({})
    run_search(env, [want(type="map", place="Bruges, Belgium", what="Bản đồ"), want(id="b0001.2", n=2, type="clip", search="canal", alt=[], seconds=6, what="Kênh")],
               web=asearch.Web(on=True, max=5, search=fake))
    assert fake.calls == []


def test_a_want_that_could_not_be_searched_because_the_budget_was_spent_has_the_code_web_budget(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake({})
    web = asearch.Web(on=True, max=1, search=fake)
    st, _ = run_search(env, [ctx_want(kind="work"), ctx_want(id="b0001.2", n=2, kind="work")], web=web)
    first, second = st["wants"]["b0001.1"], st["wants"]["b0001.2"]
    assert len(fake.calls) == 1 and web.spent == 1 and web.left() == 0
    assert (first["status"], first["code"]) == ("none", "no_candidates") and (second["status"], second["code"]) == ("none", "web_budget")


def test_a_refusal_before_anything_was_sent_stops_the_web_for_the_run_and_costs_nothing(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake(errors={"Noyon Cathedral facade": [{"source": "web", "code": "web_no_key", "message": "x"}]})
    web = asearch.Web(on=True, max=5, search=fake)
    st, _ = run_search(env, [ctx_want(kind="work"), ctx_want(id="b0001.2", n=2, kind="work")], web=web)
    assert len(fake.calls) == 1 and web.spent == 0 and web.stopped == "web_no_key" and st["web"]["stopped"] == "web_no_key"        # the second want did not even try
    assert not web.usable()


def test_a_web_search_that_the_service_limits_is_counted_and_the_host_is_left_alone(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake(errors={"Noyon Cathedral facade": [{"source": "web", "code": "source_rate_limited", "retry_after": 120}]})
    web = asearch.Web(on=True, max=5, search=fake)
    st, _ = run_search(env, [ctx_want(kind="work"), ctx_want(id="b0001.2", n=2, kind="work")], web=web, clock=lambda: 500.0)
    assert len(fake.calls) == 1 and web.spent == 1 and st["limited"]["web"] == 620.0
    assert st["wants"]["b0001.2"]["status"] == "limited" and st["wants"]["b0001.2"]["code"] == "source_limited"


def test_a_resumed_search_goes_on_counting_from_what_the_run_spent(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake({})
    st, _ = run_search(env, [ctx_want(kind="work")], web=asearch.Web(on=True, max=2, search=fake))
    resumed = asearch.Web.from_state(st, True, 2, search=fake)
    assert resumed.spent == 1 and resumed.left() == 1
    assert asearch.Web.from_state(st, False, 2).stopped is None and asearch.Web.from_state({}, True, 3).spent == 0


def test_a_web_picture_whose_real_size_is_small_is_dropped_after_its_thumbnail(env, monkeypatch):
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "wikipedia": WikiFake()}, keys=())
    fake = web_fake({"Noyon Cathedral facade": [wcard("https://img.example.org/big.jpg"), wcard("https://img.example.org/tiny.jpg"), wcard("https://img.example.org/mid.jpg")]})

    def thumbs(pdir, cand, limited=None, clock=None):
        rel = fake_thumb(pdir, cand, limited, clock)
        cand["width"], cand["height"] = {"big.jpg": (2000, 1500), "tiny.jpg": (580, 120), "mid.jpg": (600, 40)}[cand["source_id"].rsplit("/", 1)[1]]
        return rel
    st, _ = run_search(env, [ctx_want(kind="work")], web=asearch.Web(on=True, max=5, search=fake), fetch_thumb=thumbs)
    assert [c["source_id"] for c in st["wants"]["b0001.1"]["candidates"]] == ["https://img.example.org/big.jpg", "https://img.example.org/mid.jpg"]       # 580 px on the long side: dropped


def test_the_paid_search_goes_only_through_the_one_door_with_the_ticket_and_the_permission_of_the_job(env, monkeypatch):
    from bti.media.sources.web import WebSource
    from bti.picks import service
    from bti.media.youcom import RawCall
    asked = []

    class Client:
        def search(self, q, profile):
            asked.append(q)
            return RawCall(api="search", payload={"results": {"web": [{"url": "https://s.example.org/p", "title": "A page", "original_thumbnail_url": "https://s.example.org/i/a.jpg"}]}},
                           status_code=200)
    monkeypatch.setitem(__import__("bti.media.api", fromlist=["x"])._SOURCES, "web", WebSource(client=Client()))
    r = service.search(env.pdir, "x", None, ["web"], 5)                                      # a page or an agent asking for it: left out silently
    assert r["items"] == [] and r["errors"] == [] and asked == []
    assert service.search(env.pdir, "x", None, None, 5)["errors"] == [] and asked == []      # not in a default search either
    r = service.search(env.pdir, "x", None, ["web"], 5, allow_paid=True)                      # allowed, but without the ticket the source itself refuses
    assert r["items"] == [] and [e["code"] for e in r["errors"]] == ["web_off"] and asked == []
    r = asearch.default_web_search(env.pdir, "Noyon", 5)                                      # the job's own function: allowed and ticketed
    assert [(i["source"], i["page_title"]) for i in r["items"]] == [("web", "A page")] and asked == ["Noyon"]


def test_a_web_thumbnail_is_fetched_with_the_web_clients_rules_and_its_real_size_is_noted(env, monkeypatch):
    from bti.media.sources import web as webmod
    got = []

    def fetch_image(url, dest, *, max_bytes, **kw):
        got.append((url, max_bytes))
        p = Path(dest).with_suffix(".png")
        p.write_bytes(PNG)
        return p
    monkeypatch.setattr(webmod, "fetch_image", fetch_image)
    c = {"source": "web", "source_id": "https://img.example.org/a.png https://site.example.org/p", "thumb_url": "https://img.example.org/a.png"}
    rel = asearch.default_fetch_thumb(env.pdir, c)
    assert rel.endswith(".jpg") and (env.pdir / rel).is_file() and (c["width"], c["height"]) == (1300, 1250) and got == [("https://img.example.org/a.png", asearch.WEB_THUMB_BYTES)]
    th = env.pdir / "cache" / "picks_auto" / "thumbs"
    assert not list(th.glob("*.raw")) and not list(th.glob("*_web.*"))                       # nothing is left behind
    monkeypatch.setattr(webmod, "fetch_image", lambda url, dest, **kw: (_ for _ in ()).throw(webmod.NotAnImage("a page")))
    assert asearch.default_fetch_thumb(env.pdir, {**c, "source_id": "https://img.example.org/b.png"}) is None


def test_thumbnails_from_a_wikimedia_host_are_a_second_apart_and_other_hosts_are_not_paced(env, monkeypatch):
    t = {"now": 100.0, "slept": []}

    def sleep(s):
        t["slept"].append(round(s, 3))
        t["now"] += s
    from bti.media import http
    monkeypatch.setattr(http, "_PACE_LAST", {})                                          # the one clock of the Wikimedia service (thumbnails and imports alike)
    for _ in range(3):
        asearch.pace_wikimedia("https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/x.jpg/500px-x.jpg", sleep=sleep, clock=lambda: t["now"])
    assert t["slept"] == [1.0, 1.0]                                                       # the first goes at once, the next two wait out the second
    t["now"] += 5
    asearch.pace_wikimedia("https://upload.wikimedia.org/x.jpg", sleep=sleep, clock=lambda: t["now"])
    asearch.pace_wikimedia("https://img.example.org/x.jpg", sleep=sleep, clock=lambda: t["now"])
    asearch.pace_wikimedia("https://upload.example/t.jpg", sleep=sleep, clock=lambda: t["now"])
    assert t["slept"] == [1.0, 1.0]                                                       # five seconds passed: no wait; other hosts: never


# ---------------------------------------------------------------------------------------------------------------- the contract: kinds, entity, period, places, object and event
def test_object_is_searched_like_work_and_event_like_other_without_the_met(monkeypatch):
    install_sources(monkeypatch, {}, keys=("pexels", "pixabay"))
    assert asearch.sources_for(want(kind="object")) == ["commons", "met"] == asearch.sources_for(want(kind="work"))
    assert asearch.sources_for(want(kind="event")) == ["commons", "pexels", "pixabay"] and "met" not in asearch.sources_for(want(kind="event"))
    assert asearch.sources_for(want(kind="other")) == ["commons", "met", "pexels", "pixabay"]


def test_a_want_carries_its_entity_period_kinds_and_places_with_defaults_when_the_plan_has_none():
    old = asearch._new_want({"id": "b1.1", "beat": "b1", "n": 1, "type": "context", "search": "x", "alt": [], "kind": "work", "what": "A"})
    assert (old["entity"], old["period"], old["kinds"], old["places"]) == ("", "then", [], [])
    new = asearch._new_want({"id": "b1.1", "beat": "b1", "n": 1, "type": "context", "search": "x", "alt": [], "kind": "event", "what": "A", "entity": " Battle  of Nancy ",
                             "period": "now", "kinds": ["outside", "journey"]})
    assert (new["entity"], new["period"], new["kinds"]) == ("Battle of Nancy", "now", ["outside", "journey"])


def test_a_map_want_that_names_places_is_searched_by_the_first_one_and_never_fails(env, monkeypatch):
    osm = FakeSource("osm", [meta("osm", "1:12:45.7:4.8:Lyon", "Bản đồ Lyon", "lyon")])
    install_sources(monkeypatch, {"commons": FakeSource("commons"), "osm": osm, "wikipedia": WikiFake()}, keys=())
    journey = {"id": "b0008.2", "beat": "b0008", "n": 2, "type": "map", "places": ["Lyon, France", "Lübeck, Germany"], "kinds": ["outside", "journey"], "what": "Hành trình"}
    assert asearch.place_of(journey) == "Lyon, France" and asearch.queries_for(journey) == ["Lyon, France"]
    assert asearch.place_of({"place": "Oslo", "places": ["Oslo", "Bergen"]}) == "Oslo" and asearch.place_of({"type": "map"}) == ""
    st, _ = run_search(env, [journey])
    w = st["wants"]["b0008.2"]
    assert [q for q, k, n in osm.searches] == ["Lyon, France"] and w["status"] == "found" and w["places"] == ["Lyon, France", "Lübeck, Germany"] and w["kinds"] == ["outside", "journey"]
    nameless = {"id": "b0008.3", "beat": "b0008", "n": 3, "type": "map", "places": ["Lyon, France"]}
    assert asearch._new_want(nameless)["what"] == "Lyon, France"
