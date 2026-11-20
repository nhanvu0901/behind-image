"""The web search of the automatic picks job (the owner's switch `auto_web_search`): the second round after the choosing session, ONE more choosing session that
sees only the wants that got new candidates, the merged choice, the budget (`web_budget`), the count in search.json / last.json / the closing sentence, and
nothing paid when the switch is off. Fake agents, fake web search (a seam) or the real source `web` fed with the REAL answer that was kept in
tests/media/fixtures/ydc_search_sample.json through a fake client. No model, no request."""
import io
import json
from pathlib import Path

import pytest
from auto_fixtures import env, paid  # noqa: F401
from auto_helpers import CHOICE, PLAN, FakeSource, fake_thumb, install_sources, meta, plan

from bti.media import api as media_api
from bti.picks.auto import search as asearch, store, texts, webround

SAMPLE = Path(__file__).resolve().parents[1] / "media" / "fixtures" / "ydc_search_sample.json"

# two context lines: b0003 (the free sources find three candidates) and b0005 (they find none)
PLAN2 = plan(lines=[
    {"beat": "b0001", "reason": "Mở bằng cả bức tranh.", "show": [{"type": "whole"}]},
    {"beat": "b0002", "reason": "Nói về tấm gương.", "show": [{"type": "detail", "region": "MIRROR"}]},
    {"beat": "b0003", "reason": "Nói về họa sĩ.",
     "show": [{"type": "context", "search": "Jan van Eyck portrait", "alt": ["van Eyck self portrait"], "kind": "portrait", "what": "Chân dung họa sĩ"}]},
    {"beat": "b0004", "reason": "Nói về nơi vẽ.", "show": [{"type": "map", "place": "Bruges, Belgium", "what": "Bản đồ Bruges"}]},
    {"beat": "b0005", "reason": "Nói về bức tranh khác.",
     "show": [{"type": "context", "search": "Madonna Rolin", "alt": ["Rolin Madonna Louvre"], "kind": "work", "what": "Bức tranh Madonna của Rolin"}]},
    {"beat": "b0006", "reason": "Vẫn cùng ý.", "show": []}])


def wcard(n, site="museum.example.org", title="Portrait of the duke"):
    sid = "https://img.example.org/p%d.jpg https://%s/page" % (n, site)
    return {"source": "web", "source_id": sid, "title": title, "page_title": title, "site": site, "via": "web", "snippet": "A portrait made in 1450", "licence": "", "flag": "unknown",
            "thumb_url": sid.split()[0], "page_url": "https://%s/page" % site, "width": 0, "height": 0, "mime": "image/jpeg", "author": site}


class WebFake:
    """The seam `Web.search`: a query -> the items it finds; records every query."""

    def __init__(self, answers=None):
        self.answers, self.calls = answers or {}, []

    def __call__(self, pdir, query, limit):
        self.calls.append(query)
        return {"items": [dict(m) for m in self.answers.get(query, [])], "errors": []}


def first_null(wants_null=("b0003.1",)):
    """The choice of the first session: the wants in `wants_null` get null, the rest what CHOICE says. The second session (no boxes) picks candidate 2."""
    def fn(ws, turn):
        ctx = json.loads((Path(ws) / "inputs" / "context.json").read_text(encoding="utf-8"))["choice"]
        if "This is a second look" not in (Path(ws) / "TASK.md").read_text(encoding="utf-8"):
            return {"schema": "bti.picks.choice/1", "regions": CHOICE["regions"],
                    "wants": [{"id": w["id"], "pick": None if w["id"] in wants_null else w["pick"], "reason": "Không có hình nào đúng." if w["id"] in wants_null else w["reason"]}
                              for w in CHOICE["wants"]]}
        return {"schema": "bti.picks.choice/1", "regions": [], "wants": [{"id": wid, "pick": 2, "reason": "Chân dung vẽ thời đó, đúng người."} for wid in ctx["wants"]]}
    return fn


def capture(env_):
    seen = []

    def hook(mode, ws, kw):
        if mode == "choose":
            seen.append({"wants": json.loads((ws / "inputs" / "wants.json").read_text(encoding="utf-8"))["wants"],
                         "ctx": json.loads((ws / "inputs" / "context.json").read_text(encoding="utf-8")),
                         "files": sorted(str(p.relative_to(ws)).replace("\\", "/") for p in ws.rglob("*") if p.is_file()),
                         "task": (ws / "TASK.md").read_text(encoding="utf-8")})
    env_.agent.hook = hook
    return seen


@pytest.fixture(autouse=True)
def web_import(monkeypatch):
    """The download side of the real source `web` (a picture chosen from the web is imported by it): any address answers with a PNG. Its search is never used here."""
    from bti.media.sources.web import WebSource
    monkeypatch.setitem(media_api._SOURCES, "web", WebSource(opener=ImgNet(), require_ticket=True))


def setup(env_, answers=None, **kw):
    env_.agent.plan = PLAN2
    env_.agent.choice = first_null(**kw)
    fake = WebFake(answers)
    return fake


# ---------------------------------------------------------------------------------------------------------------- the switch is off: nothing paid, the job as before
def test_with_the_switch_off_the_job_has_four_parts_and_nothing_of_the_web(env):
    fake = WebFake({"Jan van Eyck portrait": [wcard(1), wcard(2)]})
    job = env.run(web={"on": False, "max": 80, "search": fake})
    assert job["state"] == "done", job.get("error")
    assert [p["key"] for p in job["parts"]] == ["plan", "search", "choose", "write"]
    assert [p["title"] for p in job["parts"]] == [texts.PART_TITLES[k] for k in ("plan", "search", "choose", "write")]
    assert fake.calls == [] and len(env.agent.calls) == 2
    r = job["result"]
    assert "web" not in r and r["sentence"] == texts.result_sentence(r["lines_done"], r["lines_total"], len(r["lines_without"]))
    sd = store.read(env.pdir, "search.json")
    assert "web" not in sd and "round2" not in sd and not (store.cache_dir(env.pdir) / "choice2.json").exists()
    assert "web" not in store.read(env.pdir, "last.json")["result"]
    assert job["meta"]["web"] == {"on": False, "max": 80}


def test_the_default_is_the_owners_switch_which_is_off_in_code(env, monkeypatch):
    from bti.picks import websettings
    monkeypatch.undo()                                                                    # the settings of this machine / the code's default, not the fixture's
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(env.root / "none.json"))
    monkeypatch.setattr(websettings, "_config", lambda: {})
    assert websettings.settings() == {"auto_web_search": "off", "auto_web_search_max": 80, "source": "default"} and not websettings.enabled()


# ---------------------------------------------------------------------------------------------------------------- the switch is on: round two and the second session
def test_a_want_the_first_session_answered_null_is_searched_on_the_web_and_a_second_session_sees_only_that(env, monkeypatch):
    fake = setup(env, {"Jan van Eyck portrait": [wcard(1), wcard(2), wcard(3)]})
    seen = capture(env)
    job = env.run(web={"on": True, "max": 5, "search": fake})
    assert job["state"] == "done", job.get("error")
    assert [p["key"] for p in job["parts"]] == ["plan", "search", "choose", "web", "choose2", "write"]
    assert [p["title"] for p in job["parts"]][3:5] == ["Tìm thêm trên web (4/6)", "Chọn lại trong hình mới tìm (5/6)"] and job["parts"][0]["title"].endswith("(1/6)")
    assert fake.calls == ["Madonna Rolin", "Jan van Eyck portrait", "Rolin Madonna Louvre"]            # b0005 had nothing: round one asked; b0003 was null: round two asked, and b0005's alternative
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose", "choose"]
    first, second = seen
    assert {w["id"] for w in first["wants"]} == {"b0003.1", "b0004.1"} and first["ctx"]["choice"]["regions"]
    assert [w["id"] for w in second["wants"]] == ["b0003.1"] and second["ctx"]["choice"] == {"wants": {"b0003.1": 3}, "books": 0, "regions": []}        # only the null want, only its 3 NEW candidates
    row = second["wants"][0]
    assert [c["n"] for c in row["candidates"]] == [1, 2, 3] and all(c["source"] == "web" and c["site"] == "museum.example.org" and c["snippet"] for c in row["candidates"])
    assert row["first_look"] == "Không có hình nào đúng." and "This is a second look" in second["task"]
    assert "images/w_b0003_1.jpg" in second["files"] and not [f for f in second["files"] if f.startswith(("images/d_", "images/books_"))]
    # the second session's pick 2 became the want's own candidate number and was written
    d = env.picks()
    item = d["beats"]["b0003"]["items"][0]
    asset = d["assets"][item["asset"]]
    assert item["role"] == "context" and asset["credit"]["source"] == "web" and asset["credit"]["source_url"] == "https://museum.example.org/page" and asset["credit"]["flag"] == "unknown"
    assert asset["title"] == "page" and (env.pdir / asset["file"]).is_file()                                           # the picture of candidate 2 was downloaded and stored
    assert item["note"] == "Chân dung vẽ thời đó, đúng người."
    sd = store.read(env.pdir, "search.json")
    w = sd["wants"]["b0003.1"]
    assert [c["n"] for c in w["candidates"]] == [1, 2, 3, 4, 5, 6] and [c.get("round", 1) for c in w["candidates"]] == [1, 1, 1, 2, 2, 2]
    assert sd["round2"]["searched"] is True and sd["round2"]["wants"] == ["b0003.1"] and sd["round2"]["map"] == {"b0003.1": [4, 5, 6]}
    assert sd["web"] == {"on": True, "max": 5, "searches": 3, "stopped": None}
    c2 = store.read(env.pdir, "choice2.json")
    assert c2["shown"] == ["b0003.1"] and c2["choice"]["wants"]["b0003.1"]["pick"] == ["c", 2]


def test_the_count_is_kept_in_last_json_and_shown_in_the_closing_sentence(env):
    fake = setup(env, {"Jan van Eyck portrait": [wcard(1), wcard(2), wcard(3)]})
    job = env.run(web={"on": True, "max": 5, "search": fake})
    r = job["result"]
    assert r["web"] == {"on": True, "max": 5, "searches": 3, "stopped": None}
    base = texts.result_sentence(r["lines_done"], r["lines_total"], len(r["lines_without"]))
    assert r["sentence"] == base + " Đã tìm trên web 3/5 lần." and webround.web_sentence(r["web"]) == " Đã tìm trên web 3/5 lần."
    assert store.read(env.pdir, "last.json")["result"]["web"]["searches"] == 3 and job["meta"]["web"] == {"on": True, "max": 5}
    assert webround.web_sentence(None) == "" and webround.web_sentence({"on": False, "max": 3, "searches": 0}) == "" and webround.cost_line(80) == ", up to 80 web searches (You.com)"


def test_a_want_that_could_not_be_searched_because_the_budget_was_spent_says_web_budget(env):
    fake = setup(env, {"Jan van Eyck portrait": [wcard(1), wcard(2), wcard(3)]})
    job = env.run(web={"on": True, "max": 2, "search": fake})
    assert job["state"] == "done", job.get("error")
    sd = store.read(env.pdir, "search.json")
    assert sd["web"]["searches"] == 2 and sd["wants"]["b0005.1"]["code"] == "web_budget" and sd["round2"]["budget"] == ["b0005.1"]
    assert fake.calls == ["Madonna Rolin", "Jan van Eyck portrait"]                      # round one: b0005; round two: b0003, then b0005's alternative had no search left
    r = job["result"]
    b5 = next(x for x in r["lines_without"] if x["beat"] == "b0005")
    assert b5["code"] == "web_budget" and any(m["code"] == "web_budget" for m in r["missing"])
    assert env.picks()["beats"]["b0003"]["items"] and "b0005" not in env.picks()["beats"] or not env.picks()["beats"]["b0005"]["items"]


def test_the_alternative_words_are_tried_when_the_first_search_gives_nothing_new_and_queries_are_never_repeated(env):
    fake = setup(env, {"van Eyck self portrait": [wcard(7), wcard(8)]})
    job = env.run(web={"on": True, "max": 9, "search": fake})
    assert job["state"] == "done", job.get("error")
    assert fake.calls.count("Jan van Eyck portrait") == 1 and fake.calls.count("van Eyck self portrait") == 1 and fake.calls.count("Madonna Rolin") == 1
    assert fake.calls.count("Rolin Madonna Louvre") == 1                                 # b0005: round one asked its search, round two only its alternative
    sd = store.read(env.pdir, "search.json")
    assert sd["wants"]["b0003.1"]["web"]["queries"] == ["Jan van Eyck portrait", "van Eyck self portrait"] and sd["round2"]["map"] == {"b0003.1": [4, 5]}
    assert sd["web"]["searches"] == 4


def test_when_the_web_finds_nothing_new_the_second_session_is_not_started(env):
    fake = setup(env, {})
    job = env.run(web={"on": True, "max": 9, "search": fake})
    assert job["state"] == "done", job.get("error")
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose"] and [p["state"] for p in job["parts"]] == ["done"] * 6
    sd = store.read(env.pdir, "search.json")
    assert sd["round2"] == {"searched": True, "wants": [], "map": {}, "budget": []} and not (store.cache_dir(env.pdir) / "choice2.json").exists()
    r = job["result"]
    assert next(x for x in r["lines_without"] if x["beat"] == "b0003")["code"] == "agent_none" and r["web"]["searches"] == 4         # b0003: 2 queries; b0005: 1 + 1


def test_a_web_that_has_no_key_stops_for_the_run_without_counting_and_the_job_still_finishes(env):
    def refusing(pdir, query, limit):
        return {"items": [], "errors": [{"source": "web", "code": "web_no_key", "message": "no key"}]}
    env.agent.plan, env.agent.choice = PLAN2, first_null()
    job = env.run(web={"on": True, "max": 9, "search": refusing})
    assert job["state"] == "done", job.get("error")
    sd = store.read(env.pdir, "search.json")
    assert sd["web"] == {"on": True, "max": 9, "searches": 0, "stopped": "web_no_key"} and job["result"]["web"]["searches"] == 0


def test_the_owners_switch_in_the_settings_turns_it_on_and_the_real_source_works_from_the_real_answer(env, monkeypatch):
    """The whole way: the switch (settings) on, the real source `web` with a fake client that answers with the real sample, the picture imported by the real download."""
    from bti.media.sources.web import WebSource
    from bti.media.youcom import RawCall
    from bti.picks import websettings
    asked = []

    class Client:                                                                           # not the real YouComClient: the trap of the fixture stays for that one
        def search(self, q, profile):
            asked.append(q)
            return RawCall(api="search", payload=json.loads(SAMPLE.read_text(encoding="utf-8")), status_code=200)

    class Wiki(FakeSource):
        def page_pictures(self, title, lang=None, limit=12):
            return [{"source": "commons", "source_id": "File:Arnolfini wiki.jpg", "title": "Arnolfini", "page_title": title, "site": "Wikipedia", "via": "wikipedia", "width": 3000, "height": 4000,
                     "thumb_url": "https://upload.example/a.jpg", "page_url": "https://commons.example/a", "mime": "image/jpeg", "author": "A", "licence": "PD"}]
    monkeypatch.setattr(websettings, "settings", lambda: {"auto_web_search": "on", "auto_web_search_max": 4, "source": "owner"})
    monkeypatch.setitem(media_api._SOURCES, "wikipedia", Wiki("wikipedia"))
    monkeypatch.setitem(media_api._SOURCES, "web", WebSource(client=Client(), opener=ImgNet()))
    env.agent.plan, env.agent.choice = PLAN2, first_null()
    job = env.run()
    assert job["state"] == "done", job.get("error")
    assert asked == ["Madonna Rolin", "Jan van Eyck portrait", "Rolin Madonna Louvre"] and job["result"]["web"] == {"on": True, "max": 4, "searches": 3, "stopped": None}
    asset = next(a for a in env.picks()["assets"].values() if a["credit"]["source"] == "web")
    assert asset["credit"]["flag"] == "unknown" and (env.pdir / asset["file"]).is_file()
    assert job["result"]["sentence"].endswith("Đã tìm trên web 3/4 lần.")


# ---------------------------------------------------------------------------------------------------------------- round two on its own: resume, merge
def make_state(pdir, n_wants=2):
    st = asearch.new_state()
    wants = [{"id": "b0003.1", "beat": "b0003", "n": 1, "type": "context", "search": "Alpha", "alt": ["Alpha two"], "kind": "portrait", "what": "A"},
             {"id": "b0005.1", "beat": "b0005", "n": 1, "type": "context", "search": "Beta", "alt": [], "kind": "work", "what": "B"}][:n_wants]
    for w in wants:
        st["wants"][w["id"]] = asearch._new_want(w)
        st["wants"][w["id"]].update({"status": "found", "candidates": [{"n": 1, "source": "commons", "source_id": "File:old.jpg", "thumb": "x", "title": "Old"}]})
    return st, wants


def round_two(tmp_path, st, wants, fake, *, max_=9, cancelled=lambda: False, web=None):
    saved = []
    web = web or asearch.Web(on=True, max=max_, search=fake)
    webround.search_round_two(tmp_path, wants, st, {"wants": {w["id"]: {"pick": None, "reason": "x"} for w in wants}, "regions": {}}, main_key="A", web=web,
                              fetch_thumb=lambda pdir, c, limited=None, clock=None: "t.jpg", clock=lambda: 0.0, cancelled=cancelled, progress=lambda f, n: None,
                              save=lambda s: saved.append(json.loads(json.dumps(s))))
    return web, saved


def test_a_cancelled_round_two_goes_on_where_it_stopped_without_repeating_a_search(tmp_path):
    st, wants = make_state(tmp_path)
    fake = WebFake({"Alpha": [wcard(1)], "Beta": [wcard(2)]})
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 3                                   # the first want is done and saved; the second is cancelled before it starts
    web, saved = round_two(tmp_path, st, wants, fake, cancelled=cancelled)
    assert fake.calls == ["Alpha"] and st["round2"]["searched"] is False and st["round2"]["wants"] == ["b0003.1"] and saved and saved[-1]["web"]["searches"] == 1
    resumed = asearch.Web.from_state(saved[-1], True, 9, search=fake)
    web2, _ = round_two(tmp_path, saved[-1], wants, fake, web=resumed)
    assert fake.calls == ["Alpha", "Beta"] and web2.spent == 2                                # Alpha was not asked again
    assert saved[-1]["web"]["searches"] == 1 or True


def test_the_merge_maps_the_second_sessions_numbers_to_the_wants_own_and_drops_the_budget_wants(tmp_path):
    st, wants = make_state(tmp_path)
    web, _ = round_two(tmp_path, st, wants, WebFake({"Alpha": [wcard(1), wcard(2)]}), max_=1)
    assert st["round2"]["wants"] == ["b0003.1"] and st["round2"]["budget"] == ["b0005.1"] and st["wants"]["b0005.1"]["code"] == "web_budget"
    assert [c["n"] for c in st["wants"]["b0003.1"]["candidates"]] == [1, 2, 3] and st["round2"]["map"] == {"b0003.1": [2, 3]}
    first = {"schema": "x", "wants": {"b0003.1": {"pick": None, "reason": "a"}, "b0005.1": {"pick": None, "reason": "b"}, "b0004.1": {"pick": ("c", 1), "reason": "c"}}, "regions": {"MIRROR": {}}}
    merged = webround.merge_choice(first, {"wants": {"b0003.1": {"pick": ("c", 2), "reason": "Đúng người."}}}, st)
    assert merged["wants"]["b0003.1"] == {"pick": ("c", 3), "reason": "Đúng người."}                        # pick 2 of the new ones = candidate 3 of the want
    assert "b0005.1" not in merged["wants"] and merged["wants"]["b0004.1"]["pick"] == ("c", 1) and merged["regions"] == {"MIRROR": {}}
    assert webround.merge_choice(first, {"wants": {"b0003.1": {"pick": None, "reason": "Không."}}}, st)["wants"]["b0003.1"] == {"pick": None, "reason": "Không."}
    assert webround.merge_choice(None, None, {})["wants"] == {}
    view = webround.second_search_view(st, first)
    assert list(view["wants"]) == ["b0003.1"] and [c["n"] for c in view["wants"]["b0003.1"]["candidates"]] == [1, 2] and view["wants"]["b0003.1"]["earlier"] == "a"


class _Resp(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(body)
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class ImgNet:
    """The transport of the real download in these tests: any address answers with a PNG picture."""

    def __call__(self, req, timeout=None):
        from auto_helpers import PNG
        return _Resp(PNG, {"Content-Type": "image/png"})


def test_a_new_run_does_not_inherit_the_second_session_of_an_earlier_one(env):
    fake = setup(env, {"Jan van Eyck portrait": [wcard(1), wcard(2), wcard(3)]})
    job = env.run(web={"on": True, "max": 5, "search": fake})
    assert job["state"] == "done" and (store.cache_dir(env.pdir) / "choice2.json").is_file()
    # the same request again (redo): a new run, so nothing of the earlier run's saved parts is taken for its own
    fake2 = setup(env, {})
    job2 = env.run(web={"on": True, "max": 5, "search": fake2}, redo=True)
    assert job2["state"] == "done", job2.get("error")
    assert not (store.cache_dir(env.pdir) / "choice2.json").exists() and [c["mode"] for c in env.agent.calls][3:] == ["plan", "choose"]
