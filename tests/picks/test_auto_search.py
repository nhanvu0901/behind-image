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
