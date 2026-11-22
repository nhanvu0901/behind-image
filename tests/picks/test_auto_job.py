"""The automatic picks job on a fixture project: fake agent, fake sources, fake thumbnails. The real long-job runner runs the four parts."""
import json
import os
import time

import pytest
from auto_fixtures import env, paid  # noqa: F401
from auto_helpers import CHOICE, PLAN, FakeAgent, choice, plan

from bti.draft.providers.agy import AgyResult
from bti.media import http as mhttp
from bti.picks import doc, service
from bti.picks.auto import AutoError, store
from bti.picks.auto import write as awrite


def result(job):
    return job["result"]


def active_id(env):
    return env.manager.active(env.pid, kind="picks")["id"]


def cancel_in(env, mode):
    """A hook for the fake agent: the job is cancelled while the session of `mode` runs (the runner then reports `cancelled`)."""
    def hook(m, ws, kw):
        if m == mode:
            env.manager.cancel(active_id(env))
            return AgyResult(status="cancelled", elapsed=0.1)
    return hook


def part_states(job):
    return [(p["key"], p["state"]) for p in job["parts"]]


# ---------------------------------------------------------------------------------------------------------------- the whole job
def test_the_whole_job_fills_every_line_from_an_empty_picks_document(env):
    assert env.picks()["beats"] == {}
    job = env.run()
    assert job["state"] == "done", job.get("error")
    r = result(job)
    assert (r["lines_total"], r["lines_done"], r["lines_with_pictures"], r["lines_kept"]) == (6, 6, 5, 1)
    assert r["lines_without"] == [] and r["missing"] == []
    assert (r["pictures_imported"], r["regions_made"], r["regions_tight"], r["clips"]) == (3, 2, 2, 1)
    assert r["sentence"] == "Agent đã chọn hình cho 6/6 đoạn." and r["stopped"] is None
    assert part_states(job) == [("plan", "done"), ("search", "done"), ("choose", "done"), ("write", "done")]
    assert job["parts"][0]["title"] == "Lập danh sách hình cần tìm (1/4)"
    d = env.picks()
    a = d["assets"]["A"]
    assert set(a["regions"]) == {"MIRROR", "HEAD"}
    assert a["regions"]["HEAD"]["tight"] is True and a["regions"]["HEAD"]["thing"] == "man's face" and a["regions"]["HEAD"]["rough"] == [130, 62, 390, 313]
    assert a["regions"]["HEAD"]["label"] == "Khuôn mặt" and a["regions"]["HEAD"]["rx"] < 156
    assert a["regions"]["MIRROR"]["tight"] is True and a["regions"]["MIRROR"]["thing"] == "convex mirror on back wall" and a["regions"]["MIRROR"]["rough"] == [520, 375, 780, 688]
    assert a["regions"]["MIRROR"]["x"] == 650 and a["regions"]["MIRROR"]["rx"] == 122
    b = d["beats"]
    assert b["b0001"]["items"] == [{"asset": "A", "region": None, "role": "main", "note": ""}] and b["b0001"]["status"] == "picked"
    assert b["b0002"]["items"] == [{"asset": "A", "region": "MIRROR", "role": "detail", "note": ""}]
    assert [(i["role"], i["asset"] != "A") for i in b["b0003"]["items"]] == [("context", True)]
    assert [i["role"] for i in b["b0004"]["items"]] == ["map", "video"]
    assert [(i["asset"], i["region"], i["role"]) for i in b["b0005"]["items"]] == [("A", "HEAD", "detail"), ("A", None, "main")]
    assert b["b0006"]["items"] == [] and b["b0006"]["status"] == "skip"
    assert b["b0001"]["note"] == "Mở bằng cả bức tranh." and b["b0006"]["note"] == "Vẫn cùng ý."                                     # the agent's reason, per line
    assert b["b0003"]["items"][0]["note"] == "Bản chụp chân dung rõ nét." and "clip khoảng 6 giây" in b["b0004"]["items"][1]["note"]
    assert d["assets"][b["b0004"]["items"][1]["asset"]]["kind"] == "video"
    assert d["approval"]["approved"] is False and d["approval"]["sha1"] is None                                                       # it never approves
    # what the page reads afterwards
    from bti.picks import auto
    ov = auto.overview(env.pid, env.pdir)
    assert ov["running"] is None and ov["last"]["result"]["sentence"] == r["sentence"] and ov["reasons"]["b0003"] == b["b0003"]["note"]


def test_what_the_agent_is_given_and_the_limits_that_are_in_the_job(env):
    job = env.run()
    plan_call, choose_call = env.agent.calls
    assert (plan_call["mode"], choose_call["mode"]) == ("plan", "choose")
    assert plan_call["model"] == job["meta"]["model"] and plan_call["timeout"] == 30 * 60 and plan_call["max_repairs"] == 1
    ext = ".cmd" if os.name == "nt" else ""
    assert {"TASK.md", "check" + ext, "crop" + ext, "inputs/painting.json", "inputs/narration.json", "images/main.jpg", "inputs/main_large.jpg"} <= set(plan_call["files"])
    assert {"inputs/wants.json", "images/w_b0003_1.jpg", "images/w_b0004_2.jpg", "images/d_MIRROR.jpg", "images/d_HEAD.jpg"} <= set(choose_call["files"])
    assert "images/w_b0004_1.jpg" not in choose_call["files"]                                  # a map has no sheet: its candidate is a place
    assert job["meta"]["limits"] == {"plan": {"minutes": 30, "steps": 140, "repairs": 1}, "choose": {"minutes": 45, "steps": 280, "repairs": 2}}
    assert result(job)["limits"]["plan"]["steps"] == 140 and result(job)["limits"]["choose"]["steps"] == 280
    assert job["meta"]["action"] == "auto" and job["kind"] == "picks" and job["meta"]["agent"]["id"] in ("gemini", "opus")
    assert job["meta"]["beats"] == ["b0001", "b0002", "b0003", "b0004", "b0005", "b0006"]


def test_the_search_asks_each_source_for_its_kind_and_never_the_paid_service(env, paid):
    env.run()
    commons, met, osm = env.sources["commons"], env.sources["met"], env.sources["osm"]
    assert [(q, k) for q, k, n in commons.searches if k == "image"] == [("Jan van Eyck portrait", "image")]       # a portrait: Commons and the Met
    assert [q for q, k, n in met.searches] == ["Jan van Eyck portrait"]
    assert [(q, k) for q, k, n in commons.searches if k == "video"] == [("canal boat", "video")]               # a clip: video search of the free sources that have a key
    assert [q for q, k, n in osm.searches] == ["Bruges, Belgium"]                                               # a map: OpenStreetMap by name
    assert paid == []


def test_the_package_never_reaches_the_paid_service(env):
    import ast
    from pathlib import Path
    import bti.picks.auto as pkg
    bad_modules = ("suggest", "youcom", "research")
    bad_names = {"video_search", "start_clip_job", "moment_search", "inspect_video_url", "visual_research", "YouComClient", "YouComProvider", "pick_provider"}
    for f in sorted(Path(pkg.__file__).parent.glob("*.py")):
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.ImportFrom):
                names = [n.module or ""] + [a.name for a in n.names]
            elif isinstance(n, ast.Import):
                names = [a.name for a in n.names]
            elif isinstance(n, ast.Attribute):
                assert n.attr not in bad_names, (f.name, n.attr)
                continue
            elif isinstance(n, ast.Name):
                assert n.id not in bad_names, (f.name, n.id)
                continue
            else:
                continue
            assert not [x for x in names if any(b in x.split(".") for b in bad_modules)], (f.name, names)


# ---------------------------------------------------------------------------------------------------------------- the writes
def test_every_write_is_a_batch_with_the_agent_as_actor_and_can_be_undone(env):
    from bti.ops import runner as ops_runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    job = env.run()
    recs = env.changes()
    assert len(recs) == 4 and all(r["actor"] == "agent:" + job["meta"]["model"] and r["doc"] == "picks" for r in recs)      # the regions, then one batch per chapter
    assert set(result(job)["batches"]) == {r["batch"] for r in recs}
    assert all(r["note"].startswith("Agent chọn hình") for r in recs)
    ops = [o["op"] for r in reversed(recs) for o in r["ops"]]
    assert ops.count("set_region") == 2 and ops.count("import") == 3 and ops.count("set_picks") == 5 and ops.count("skip_beat") == 1
    before = env.picks()
    d, rev = PicksAdapter(env.pdir).read()
    out = ops_runner.run_undo({"picks": PicksAdapter(env.pdir)}, recs[0]["batch"], {"base_rev": rev, "actor": "human"}, ChangeLog(env.pdir))
    assert out["undo_of"] == recs[0]["batch"]
    after = env.picks()
    assert after["beats"].get("b0005", {"items": []})["items"] == [] and after["beats"].get("b0006", {"items": []})["items"] == []   # the last chapter went back
    assert after["beats"]["b0001"] == before["beats"]["b0001"] and after["beats"]["b0003"] == before["beats"]["b0003"]


def test_redo_is_needed_for_lines_that_have_pictures_and_an_approved_document_needs_redo(env):
    from bti.picks import context
    env.run()
    with pytest.raises(AutoError) as e:
        env.start()
    assert e.value.code == "picks_nothing_to_do" and e.value.status == 409
    nv = context.narration_view(env.pdir)
    with doc.Held(env.pdir):
        doc.stamp_approval(env.pdir, doc.revision(doc.load(env.pdir)), nv["rev"])
    assert doc.approval_state(doc.load(env.pdir), nv["rev"], True)["approved"] is True
    for kw in ({}, {"beats": ["b0001"]}):
        with pytest.raises(AutoError) as e:
            env.start(**kw)
        assert e.value.code == "picks_approved" and e.value.status == 409
    calls = len(env.agent.calls)
    p = json.loads(json.dumps(PLAN))
    p["lines"][0]["show"], p["lines"][0]["kinds"] = [{"type": "detail", "region": "HEAD"}], ["detail"]      # the agent now plans something else for the first line
    env.agent.plan = p
    job = env.run(redo=True)
    assert job["state"] == "done" and result(job)["lines_total"] == 6 and result(job)["lines_done"] == 6
    after = doc.load(env.pdir)
    assert after["beats"]["b0001"]["items"][0]["region"] == "HEAD"
    assert after["approval"]["approved"] is False and doc.approval_state(after, nv["rev"], True)["approved"] is False        # dropped by the write, as by any save
    assert len(env.agent.calls) == calls + 2                                                       # the second run asked the agent again, from scratch


def test_a_line_the_owner_filled_is_not_touched_without_redo_and_a_named_line_can_be_redone(env):
    from bti.ops import runner as ops_runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    d, rev = PicksAdapter(env.pdir).read()
    ops_runner.run_batch(PicksAdapter(env.pdir), {"base_rev": rev, "actor": "human",
                                                  "ops": [{"op": "set_picks", "beat": "b0002", "items": [{"asset": "A"}], "reason": "Của chủ video."}]},
                         ChangeLog(env.pdir))
    job = env.run()
    assert job["state"] == "done" and result(job)["lines_total"] == 5 and set(job["meta"]["beats"]) == {"b0001", "b0003", "b0004", "b0005", "b0006"}
    assert env.picks()["beats"]["b0002"]["note"] == "Của chủ video." and env.picks()["beats"]["b0002"]["items"][0]["region"] is None
    # naming the line with redo replaces it (the region MIRROR exists by now, so the plan uses it by name)
    job = env.run(beats=["b0002"], redo=True)
    assert job["state"] == "done" and result(job)["lines_total"] == 1 and result(job)["regions_made"] == 1       # MIRROR was not made in the first run: no line used it
    assert env.picks()["beats"]["b0002"]["note"] == "Nói về tấm gương." and env.picks()["beats"]["b0002"]["items"][0]["region"] == "MIRROR"
    # once more: now the region exists, the plan uses it by name, there is nothing to look at and no choose session is started
    job = env.run(beats=["b0002"], redo=True)
    assert job["state"] == "done" and result(job)["lines_total"] == 1 and result(job)["regions_made"] == 0
    assert job["parts"][2]["state"] == "done" and job["parts"][2]["note"].startswith("Đã có sẵn")
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose", "plan", "choose", "plan"]


def test_the_job_refuses_when_it_cannot_start(env, monkeypatch):
    from bti.script import store as sstore
    with doc.Held(env.pdir):
        d = env.picks()
        d["main_asset"] = None
        doc.save(env.pdir, d)
    with pytest.raises(AutoError) as e:
        env.start()
    assert e.value.code == "picks_no_main"
    with doc.Held(env.pdir):
        d["main_asset"] = "A"
        doc.save(env.pdir, d)
    for beats, code, status in ((["b0099"], "not_found", 404), ([], "invalid", 422), ("b0001", "invalid", 422)):
        with pytest.raises(AutoError) as e:
            env.start(beats=beats)
        assert (e.value.code, e.value.status) == (code, status)
    from bti.picks.auto import inputs as ainputs
    monkeypatch.setattr(ainputs, "MAX_LINES", 3)                                                      # a narration of six lines is more than a job may take
    with pytest.raises(AutoError) as e:
        env.start()
    assert e.value.code == "too_many" and e.value.status == 422 and "a chapter at a time" in e.value.message
    monkeypatch.setattr(ainputs, "MAX_LINES", 150)
    with pytest.raises(AutoError) as e:
        env.start(base_rev="0" * 40)
    assert e.value.code == "stale" and e.value.extra["rev"] == doc.revision(env.picks())
    with pytest.raises(AutoError) as e:
        env.start(model="bad model name!")
    assert e.value.code == "bad_model"
    n = sstore.load_narration(env.pdir)
    n.chapters[0].beats[0].text += " More words."
    sstore.save_narration(env.pdir, n)
    with pytest.raises(AutoError) as e:
        env.start()
    assert e.value.code == "narration_not_approved"
    assert env.agent.calls == []                                                                  # nothing ran


def test_a_second_job_of_the_kind_is_refused_while_one_runs(env):
    gate = {"go": False}

    def hook(mode, ws, kw):
        while not gate["go"] and not kw["cancel"]():
            time.sleep(0.02)
        return AgyResult(status="cancelled")
    env.agent.hook = hook
    rec = env.start()
    with pytest.raises(AutoError) as e:
        env.start()
    assert e.value.code == "busy" and e.value.extra["job_id"] == rec["id"]
    env.manager.cancel(rec["id"])
    gate["go"] = True
    assert env.manager.wait(rec["id"], 20)["state"] == "cancelled"


# ---------------------------------------------------------------------------------------------------------------- the rules
def test_a_plan_with_two_clips_in_a_chapter_and_a_clip_on_a_painting_line_is_cut_to_the_rule(env):
    clip = lambda w: {"type": "clip", "search": "canal boat", "what": "Cảnh " + w, "seconds": 20}                    # noqa: E731
    pic = lambda w: {"type": "context", "search": "Jan van Eyck portrait", "kind": "portrait", "what": "Họa sĩ " + w}      # noqa: E731
    p = plan(lines=[{"beat": "b0001", "reason": "Cả tranh.", "kinds": ["outside"], "show": [{"type": "whole"}, pic("1"), clip("1")], "fallback": {"type": "whole"}},   # on a painting line: dropped
                    {"beat": "b0002", "reason": "Chi tiết.", "kinds": ["detail"], "show": [{"type": "detail", "region": "MIRROR"}]},
                    {"beat": "b0003", "reason": "Cảnh một.", "kinds": ["outside"], "show": [clip("2")], "fallback": {"type": "whole"}},      # the first clip of c02
                    {"beat": "b0004", "reason": "Cảnh hai.", "kinds": ["outside"], "show": [pic("4"), clip("3")], "fallback": {"type": "whole"}},      # a second one in c02: dropped
                    {"beat": "b0005", "reason": "Đầu.", "kinds": ["detail"], "show": [{"type": "detail", "region": "HEAD"}]},
                    {"beat": "b0006", "reason": "Giữ.", "kinds": ["idea"], "show": []}])
    env.agent.plan = p
    job = env.run()
    assert job["state"] == "done", job.get("error")
    saved = store.read(env.pdir, "plan.json")
    shown = {ln["beat"]: [i["type"] for i in ln["show"]] for ln in saved["plan"]["lines"]}
    assert shown == {"b0001": ["whole", "context"], "b0002": ["detail"], "b0003": ["clip"], "b0004": ["context"], "b0005": ["detail"], "b0006": []}
    assert len([n for n in saved["notes"] if "the clip was dropped" in n]) == 2 and any("a clip lasts 4 to 10 seconds" in n for n in saved["notes"])
    assert saved["plan"]["lines"][2]["show"][0]["seconds"] == 10.0
    r = result(job)
    assert r["clips"] == 1 and env.picks()["beats"]["b0003"]["items"][0]["role"] == "video" and env.picks()["beats"]["b0006"]["status"] == "skip"


def test_a_detail_the_choose_step_drops_shows_the_whole_painting_and_its_box_is_not_made(env):
    env.agent.choice = choice(regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "drop", "reason": "Khung không trúng khuôn mặt."}])
    job = env.run()
    assert job["state"] == "done"
    d = env.picks()
    assert set(d["assets"]["A"]["regions"]) == {"MIRROR"}
    assert [(i["asset"], i["region"], i["role"]) for i in d["beats"]["b0005"]["items"]] == [("A", None, "main")]            # the whole painting, once
    r = result(job)
    assert r["regions_dropped"] == ["HEAD"] and r["regions_made"] == 1 and r["lines_done"] == 6


def test_a_want_with_no_candidates_is_written_with_the_fallback_and_listed_as_missing(env):
    env.sources["commons"].items = [m for m in env.sources["commons"].items if m["kind"] == "video"]
    env.sources["met"].items = []
    job = env.run()
    assert job["state"] == "done"
    r = result(job)
    assert (r["lines_total"], r["lines_done"]) == (6, 6) and r["lines_without"] == []                                         # no longer left unwritten
    assert [(m["beat"], m["code"], m["no"]) for m in r["missing"]] == [("b0003", "no_candidates", 3)] and "Chân dung họa sĩ" in r["missing"][0]["why"]
    assert r["sentence"] == "Agent đã chọn hình cho 6/6 đoạn." and r["outside_without"] == ["b0003"]
    b = env.picks()["beats"]["b0003"]
    assert b["items"] == [{"asset": "A", "region": None, "role": "main", "note": ""}] and b["status"] == "picked"            # its fallback: the whole painting
    assert b["kinds"] == ["outside"] and b["missing"] == [{"what": "Chân dung họa sĩ", "code": "no_candidates"}]
    assert "Chưa tìm được: Chân dung họa sĩ." in b["note"]
    assert "images/w_b0003_1.jpg" not in env.agent.calls[1]["files"]                                                         # the agent was not shown an empty sheet
    assert store.read(env.pdir, "search.json")["wants"]["b0003.1"]["status"] == "none"
    d = env.picks()
    assert [i["beat"] for i in doc.issues(d, None, [f"b000{n}" for n in range(1, 7)]) if i["code"] == "outside_no_picture"] == ["b0003"]
    assert doc.outside_summary(d) == {"lines": 2, "with_picture": 1, "without": ["b0003"]}


def test_a_picture_the_agent_answered_null_for_is_written_with_the_fallback_the_plan_named(env):
    p = plan()
    p["lines"][2]["fallback"] = {"type": "detail", "region": "HEAD"}                                     # the part of the painting nearest to the line
    env.agent.plan = p
    env.agent.choice = choice(wants=[{"id": "b0003.1", "pick": None, "reason": "Không hình nào đúng người."}, *CHOICE["wants"][1:]])
    job = env.run()
    assert job["state"] == "done", job.get("error")
    r = result(job)
    assert r["lines_done"] == 6 and r["lines_without"] == [] and [(m["beat"], m["code"]) for m in r["missing"]] == [("b0003", "agent_none")]
    b = env.picks()["beats"]["b0003"]
    assert [(i["asset"], i["region"], i["role"]) for i in b["items"]] == [("A", "HEAD", "detail")]
    assert b["kinds"] == ["outside"] and b["missing"] == [{"what": "Chân dung họa sĩ", "code": "agent_none"}] and "Chưa tìm được" in b["note"]


def test_a_fallback_box_the_choosing_session_drops_shows_the_whole_painting(env):
    p = plan()
    p["lines"][2]["fallback"] = {"type": "detail", "region": "HEAD"}
    env.agent.plan = p
    env.agent.choice = choice(wants=[{"id": "b0003.1", "pick": None, "reason": "Không hình nào đúng người."}, *CHOICE["wants"][1:]],
                              regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "drop", "reason": "Khung không trúng khuôn mặt."}])
    job = env.run()
    assert job["state"] == "done"
    assert [(i["asset"], i["region"], i["role"]) for i in env.picks()["beats"]["b0003"]["items"]] == [("A", None, "main")]


def test_kinds_are_written_on_every_line_and_a_found_picture_leaves_no_missing_entry(env):
    job = env.run()
    assert job["state"] == "done" and result(job)["outside_without"] == [] and result(job)["missing"] == []
    beats = env.picks()["beats"]
    assert {b: v["kinds"] for b, v in beats.items()} == {"b0001": ["whole"], "b0002": ["detail"], "b0003": ["outside"], "b0004": ["outside", "journey"],
                                                         "b0005": ["detail", "whole"], "b0006": ["idea"]}              # a skipped line has them too
    assert all("missing" not in v for v in beats.values())
    assert [o.get("kinds") for r in env.changes() for o in r["ops"] if o["op"] == "skip_beat"] == [["idea"]]
    assert beats["b0003"]["items"][0]["asset"] != "A" and doc.outside_summary(env.picks()) == {"lines": 2, "with_picture": 2, "without": []}


def test_a_line_of_an_older_plan_has_no_fallback_and_nothing_found_leaves_it_as_it_was():
    """A plan saved before `kinds` existed (a resumed run reads it back from cache/picks_auto/plan.json): no kinds are written and a line with nothing stays unwritten."""
    from bti.picks.auto import texts
    old = {"lines": [{"beat": "b0003", "reason": "Nói về họa sĩ.", "show": [{"type": "context", "search": "x y z", "alt": [], "kind": "portrait", "what": "Chân dung họa sĩ"}]},
                     {"beat": "b0004", "reason": "Nơi vẽ.", "show": [{"type": "map", "place": "Bruges, Belgium", "what": "Bản đồ Bruges"}]}]}

    class Inp:
        def beat(self, bid):
            return {"no": int(bid[1:]), "chapter": "c02"}
    picks = {"b0003.1": {"id": "b0003.1", "beat": "b0003", "pick": None, "reason": "", "code": "no_candidates", "what": "Chân dung họa sĩ", "source": None, "seconds": None},
             "b0004.1": {"id": "b0004.1", "beat": "b0004", "pick": {"source": "osm", "source_id": "m1"}, "reason": "Đúng.", "code": None, "what": "Bản đồ Bruges"}}
    lines = awrite.build_lines(Inp(), old, picks, {("osm", "m1"): "K1"}, {}, {}, [], set())
    assert lines[0]["items"] == [] and lines[0]["kinds"] == [] and lines[0]["missing"][0]["code"] == "no_candidates"            # nothing to write: left as it was
    ops = awrite._ops_for([lines[1]], "A")
    assert ops[-1]["op"] == "set_picks" and "kinds" not in ops[-1] and ops[-1]["missing"] == []                                 # an older plan says no kinds
    assert texts.why("no_candidates", what="x")


def test_the_two_codes_of_the_web_search_have_a_sentence_of_their_own_and_do_not_fall_to_the_general_one():
    """fixes3: `web_budget` (the run's count of web searches was used up) and `web_no_key` (the web search has no key) used to say "Chưa có hình cho ..."."""
    from bti.picks.auto import texts
    general = texts.why("never_heard_of_it", what="Eligius")
    assert general == "Chưa có hình cho \"Eligius\"."
    budget, no_key = texts.why("web_budget", what="Eligius"), texts.why("web_no_key", what="Eligius")
    assert budget.startswith("Đã hết lượt tìm trên web của lần chạy này nên chưa tìm lại được \"Eligius\".") and "chạy lại" in budget.lower()
    assert "khóa" in no_key and "\"Eligius\"" in no_key and "web" in no_key
    assert len({general, budget, no_key}) == 3
    assert "hình này" in texts.why("web_budget") and "hình này" in texts.why("web_no_key")          # no `what`: the same words the other codes use


def test_a_source_that_is_rate_limited_is_left_alone_and_its_wants_are_listed_without_waiting(env):
    slow = mhttp.MediaHTTPError("HTTP 429", 429, retry_after=120)
    env.sources["commons"].fail, env.sources["met"].fail = slow, slow
    t0 = time.monotonic()
    job = env.run()
    assert time.monotonic() - t0 < 20 and job["state"] == "done"                                                             # nothing waited for the two minutes
    r = result(job)
    assert r["lines_without"] == [] and r["lines_done"] == 6                                                                  # the line about the painter shows its fallback
    assert {m["want"] for m in r["missing"]} == {"b0003.1", "b0004.2"} and {m["code"] for m in r["missing"]} == {"source_limited"}
    miss = {m["beat"]: m for m in r["missing"]}
    assert "đang giới hạn lượt tải" in miss["b0003"]["why"] and "khoảng 2 phút" in miss["b0003"]["why"]
    assert len(env.sources["commons"].searches) == 1 and len(env.sources["met"].searches) == 1                                # left alone: not asked again by the clip want either
    wants = store.read(env.pdir, "search.json")["wants"]
    assert wants["b0003.1"]["status"] == "limited" and wants["b0004.2"]["status"] == "limited" and wants["b0004.1"]["status"] == "found"
    # the line with a map and a clip is written with the map; what is missing is listed
    b4 = env.picks()["beats"]["b0004"]
    assert [i["role"] for i in b4["items"]] == ["map"] and b4["missing"] == [{"what": "Kênh đào", "code": "source_limited"}]
    assert "Chưa tìm được: Kênh đào." in b4["note"]
    assert [i["role"] for i in env.picks()["beats"]["b0003"]["items"]] == ["main"] and result(job)["outside_without"] == ["b0003"]      # b0004 has its map


def test_a_candidate_with_no_thumbnail_cannot_be_chosen_and_the_main_painting_is_never_a_context_picture(env):
    from auto_helpers import meta
    env.sources["commons"].items = [meta("commons", "File:nothumb.jpg", "No thumbnail", "portrait"), meta("commons", "File:Canal boat.mp4", "Canal boat", "canal boat", kind="video")]
    env.sources["met"].items = []
    job = env.run()
    r = result(job)
    assert r["lines_without"] == [] and [(m["beat"], m["code"]) for m in r["missing"]] == [("b0003", "no_thumbs")]
    assert env.picks()["beats"]["b0003"]["missing"] == [{"what": "Chân dung họa sĩ", "code": "no_thumbs"}]
    # the main painting itself, found by the search, is dropped from the candidates
    from bti.media import assets as massets
    src = env.sources["commons"]
    src.items = [meta("commons", "File:Main painting.jpg", "The Test Painting", "portrait"), meta("commons", "File:Portrait B.jpg", "Portrait B", "portrait")]
    idx = massets.load_index(env.pdir)
    idx["items"]["commons:File:Main painting.jpg"] = {"key": "A", "asset": env.picks()["assets"]["A"]}
    massets.save_index(env.pdir, idx)
    job = env.run(beats=["b0003"], redo=True)
    cand = store.read(env.pdir, "search.json")["wants"]["b0003.1"]["candidates"]
    assert [c["source_id"] for c in cand] == ["File:Portrait B.jpg"]
    assert "missing" not in env.picks()["beats"]["b0003"]                                                                     # found this time: the old entry is cleared


# ---------------------------------------------------------------------------------------------------------------- the agent's files
def test_an_output_that_fails_the_check_is_repaired_once(env):
    bad = plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.5, 0.6], "what": "Gương", "thing": "convex mirror"}, PLAN["regions"][1]])
    env.agent.plan = [bad, PLAN]
    job = env.run()
    assert job["state"] == "done"
    first = env.agent.calls[0]
    assert len(first["problems"]) == 2 and "outside the painting" in first["problems"][0] and first["problems"][1] is None
    assert "ERROR regions[0] (MIRROR)" in first["problems"][0]                                  # the repair message says where and what to change


def test_an_output_that_fails_the_check_twice_fails_the_part_with_its_sentence_and_writes_nothing(env):
    bad = plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.5, 0.6], "what": "Gương", "thing": "convex mirror"}, PLAN["regions"][1]])
    env.agent.plan = bad
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "picks_auto_no_output"
    assert job["error"].startswith("Agent không viết được tệp kết quả dùng được") and part_states(job)[0] == ("plan", "error")
    assert len(env.agent.calls) == 1 and len(env.agent.calls[0]["problems"]) == 2                 # one repair round, then it stops
    assert env.picks()["beats"] == {} and env.changes() == [] and store.read(env.pdir, "plan.json") is None
    assert env.agent.calls[0]["problems"][0] and not any(p["state"] == "done" for p in job["parts"][1:])


def test_the_choose_part_fails_the_same_way_and_a_new_run_keeps_the_plan_and_the_search(env):
    env.agent.choice = lambda ws, t: json.dumps({"wants": "nothing"})
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "picks_auto_no_output" and part_states(job)[:3] == [("plan", "done"), ("search", "done"), ("choose", "error")]
    assert env.picks()["beats"] == {}
    searches = sum(len(s.searches) for s in env.sources.values())
    env.agent.choice = CHOICE
    job = env.run()
    assert job["state"] == "done" and part_states(job)[0] == ("plan", "done") and job["parts"][0]["note"].startswith("Đã có sẵn")            # skipped: its file is there
    assert sum(len(s.searches) for s in env.sources.values()) == searches                                                              # nothing was searched again
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose", "choose"]


def test_a_session_that_changed_files_outside_its_folder_is_dropped(env):
    env.agent.hook = lambda m, ws, kw: AgyResult(status="tampered", tampered=["changed media/main.png"])
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "picks_auto_tampered" and "media/main.png" in job["error"]
    assert store.read(env.pdir, "plan.json") is None and env.picks()["beats"] == {}


def test_a_quota_failure_names_the_agent_and_the_time_and_keeps_what_finished(env):
    env.agent.hook = lambda m, ws, kw: AgyResult(status="error", error_code="agy_rate_limit", error_message="quota", retry_after_seconds=16200) if m == "choose" else None
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "agy_rate_limit" and "4 giờ 30 phút" in job["error"]
    assert job["meta"]["retry_after_seconds"] == 16200 and job["meta"]["retry_at"]
    assert part_states(job)[:2] == [("plan", "done"), ("search", "done")] and store.read(env.pdir, "plan.json") is not None
    assert env.picks()["beats"] == {}


def test_a_file_that_is_valid_is_taken_even_when_the_session_ended_on_a_limit(env):
    """The session wrote a good plan and went on past its step limit: it is stopped, and the file, which is complete, is used."""
    def hook(mode, ws, kw):
        if mode == "plan":
            (ws / "out").mkdir(exist_ok=True)
            (ws / "out" / "plan.json").write_text(json.dumps(FakeAgent.fit(PLAN, ws, "plan")), encoding="utf-8")
            kw["on_progress"]({"steps": 999, "last_action": "run_command", "turn": 1, "out_files": 1, "elapsed": 1.0})
            assert kw["cancel"]()                                                   # the runner is told to stop
            return AgyResult(status="cancelled", elapsed=1.0)
    env.agent.hook = hook
    job = env.run()
    assert job["state"] == "done" and result(job)["lines_done"] == 6


def test_a_session_stopped_by_a_limit_with_no_valid_file_fails_with_its_sentence(env):
    def hook(mode, ws, kw):
        kw["on_progress"]({"steps": 999, "last_action": "run_command", "turn": 1, "out_files": 0, "elapsed": 1.0})
        return AgyResult(status="cancelled", elapsed=1.0)
    env.agent.hook = hook
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "picks_auto_limit" and "giới hạn" in job["error"]


# ---------------------------------------------------------------------------------------------------------------- resume
def test_resume_after_a_cancel_in_the_plan(env):
    env.agent.hook = cancel_in(env, "plan")
    job = env.run()
    assert job["state"] == "cancelled" and env.picks()["beats"] == {} and store.read(env.pdir, "plan.json") is None
    env.agent.hook = None
    job = env.run()
    assert job["state"] == "done" and result(job)["lines_done"] == 6
    assert [c["mode"] for c in env.agent.calls] == ["plan", "plan", "choose"]


def test_resume_after_a_cancel_in_the_search(env):
    seen = []

    def search(pdir, query, beat, sources, limit, kind="image"):
        seen.append((query, tuple(sources)))
        if len(seen) == 3:                                    # the first want is done (Commons, the Met); the second is being searched
            env.manager.cancel(active_id(env))
        return service.search(pdir, query, beat, sources, limit, kind=kind)
    job = env.run(search=search)
    assert job["state"] == "cancelled" and [p["state"] for p in job["parts"]][:2] == ["done", "cancelled"] and env.picks()["beats"] == {}
    saved = store.read(env.pdir, "search.json")
    assert saved["wants"]["b0003.1"]["status"] == "found" and saved["wants"]["b0004.1"]["status"] == "pending"
    job = env.run(search=search)
    assert job["state"] == "done" and result(job)["lines_done"] == 6
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose"]                              # the plan was not asked for again
    assert [q for q, s in seen].count("Jan van Eyck portrait") == 2                                # the first want was searched once (two sources), not again
    assert len(env.sources["commons"].searches) == 2                                               # one image search + the clip search; no repeat of the portrait


def test_resume_after_a_cancel_in_the_choose(env):
    env.agent.hook = cancel_in(env, "choose")
    job = env.run()
    assert job["state"] == "cancelled" and part_states(job)[:3] == [("plan", "done"), ("search", "done"), ("choose", "cancelled")]
    assert env.picks()["beats"] == {} and store.read(env.pdir, "choice.json") is None
    searches = sum(len(s.searches) for s in env.sources.values())
    env.agent.hook = None
    job = env.run()
    assert job["state"] == "done" and result(job)["lines_done"] == 6
    assert [c["mode"] for c in env.agent.calls] == ["plan", "choose", "choose"] and sum(len(s.searches) for s in env.sources.values()) == searches


def test_resume_after_a_cancel_in_the_write_skips_the_lines_already_written(env, monkeypatch):
    sent = {"n": 0}
    real = awrite.Writer.send

    def send(self, ops, note):
        out = real(self, ops, note)
        sent["n"] += 1
        if sent["n"] == 2:                                    # the regions and the first chapter are written
            env.manager.cancel(active_id(env))
        return out
    monkeypatch.setattr(awrite.Writer, "send", send)
    job = env.run()
    assert job["state"] == "cancelled"
    written = env.picks()["beats"]
    assert set(written) == {"b0001", "b0002"} and set(env.picks()["assets"]["A"]["regions"]) == {"MIRROR", "HEAD"}
    assert sorted(store.read(env.pdir, "run.json")["lines"]) == ["b0001", "b0002"] and store.read(env.pdir, "run.json")["stage"] != "done"
    monkeypatch.setattr(awrite.Writer, "send", real)
    before = [r["batch"] for r in env.changes()]
    job = env.run()
    assert job["state"] == "done" and [c["mode"] for c in env.agent.calls] == ["plan", "choose"]
    r = result(job)
    assert (r["lines_total"], r["lines_done"], r["pictures_imported"], r["regions_made"]) == (6, 6, 3, 2)                      # the counters of both attempts
    assert len(env.changes()) == 4 and len(before) == 2                                                                         # two more chapters, nothing written twice
    assert len(set(r["batches"])) == 4 and env.picks()["beats"]["b0006"]["status"] == "skip"
    assert sum(1 for r in env.changes() for o in r["ops"] if o["op"] == "set_region") == 2                                      # the regions were made once


def test_a_finished_run_is_not_resumed_and_a_different_request_starts_again(env):
    env.run()
    assert store.read(env.pdir, "run.json")["stage"] == "done"
    job = env.run(redo=True)
    assert job["state"] == "done" and [c["mode"] for c in env.agent.calls] == ["plan", "choose", "plan", "choose"]


def test_when_the_narration_changes_while_the_agent_works_the_result_is_not_written(env):
    from bti.script import store as sstore

    def hook(mode, ws, kw):
        if mode == "choose":
            n = sstore.load_narration(env.pdir)
            n.chapters[0].beats[0].text += " More words."
            sstore.save_narration(env.pdir, n)
    env.agent.hook = hook
    job = env.run()
    assert job["state"] == "error" and job["error_code"] == "picks_auto_stale" and env.picks()["beats"] == {}


def test_the_write_leaves_alone_a_line_the_owner_fills_while_the_job_runs(env):
    from bti.ops import runner as ops_runner
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog

    def hook(mode, ws, kw):
        if mode == "choose":
            d, rev = PicksAdapter(env.pdir).read()
            ops_runner.run_batch(PicksAdapter(env.pdir), {"base_rev": rev, "actor": "human",
                                                          "ops": [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "A"}], "reason": "Của chủ video."}]},
                                 ChangeLog(env.pdir))
    env.agent.hook = hook
    job = env.run()
    assert job["state"] == "done" and env.picks()["beats"]["b0003"]["note"] == "Của chủ video."
    r = result(job)
    assert (r["lines_total"], r["lines_by_others"]) == (5, 1) and r["lines_done"] == 5


# ---------------------------------------------------------------------------------------------------------------- fixes4, point 1: the downloads of the write part
def refusing(env, *, fail=("commons",), wait=None):
    """A `fetch_asset` seam that is the real one, except that a source in `fail` answers "too many requests" (the answer the facade gives after its own
    patient tries): `calls` lists what was asked, in order."""
    from bti.picks.errors import PicksError
    calls = []

    def fetch(pdir, source, source_id):
        calls.append((source, source_id))
        if source in fail:
            raise PicksError(503, "the image source limits downloads", "source_rate_limited", retryable=True, retry_after=wait)
        return service.fetch_asset(pdir, source, source_id)
    fetch.calls = calls
    return fetch


def test_a_picture_that_is_refused_after_the_patient_tries_closes_its_source_for_the_rest_of_the_write(env):
    fetch = refusing(env, wait=75)
    job = env.run(fetch_asset=fetch)
    assert job["state"] == "done", job.get("error")
    assert [s for s, _ in fetch.calls].count("commons") == 1                                       # the second Commons picture (the clip) was not even asked
    assert ("osm", "1:12:51.2090:3.2247:Bruges") in fetch.calls                                    # another source is not held back
    r = result(job)
    miss = {m["beat"]: m for m in r["missing"]}
    assert {m["code"] for m in r["missing"]} == {"import_limited"} and set(miss) == {"b0003", "b0004"}
    assert "khoảng 2 phút" in miss["b0003"]["why"] and "khoảng 2 phút" in miss["b0004"]["why"]    # the wait the host asked for (75 s), said for both
    b3, b4 = env.picks()["beats"]["b0003"], env.picks()["beats"]["b0004"]
    assert [(i["asset"], i["role"]) for i in b3["items"]] == [("A", "main")] and b3["missing"] == [{"what": "Chân dung họa sĩ", "code": "import_limited"}]
    assert [i["role"] for i in b4["items"]] == ["map"] and b4["missing"] == [{"what": "Kênh đào", "code": "import_limited"}]


def test_a_refusal_with_no_time_is_listed_with_the_default_wait_of_a_minute(env):
    job = env.run(fetch_asset=refusing(env, wait=None))
    assert {m["code"] for m in result(job)["missing"]} == {"import_limited"}
    assert all("khoảng 1 phút" in m["why"] for m in result(job)["missing"])


def test_a_source_that_is_not_refused_is_downloaded_whole_and_nothing_is_missing(env):
    fetch = refusing(env, fail=())
    job = env.run(fetch_asset=fetch)
    assert result(job)["missing"] == [] and len(fetch.calls) == 3 and result(job)["pictures_imported"] == 3


def test_the_write_part_has_the_limit_and_the_estimate_that_the_paced_downloads_need():
    import importlib
    part_limit = importlib.import_module("bti.longjob.manager").PART_LIMIT_SECONDS
    from bti.picks.auto import job as ajob
    assert awrite.WRITE_SECONDS == 25 * 60 and ajob.EST_SECONDS["write"] == 300
    patience = len(mhttp.PATIENT_WAITS) * mhttp.PATIENT_MAX_WAIT                                  # the longest wait of the one download that is under way at the deadline
    assert awrite.WRITE_SECONDS + patience + 120 < part_limit                                     # the manager stops a part at 35 minutes: the deadline is inside it


def test_cast_is_written_with_pictures_and_partial_redo_preserves_other_lines(env):
    import re
    from bti.picks.auto import inputs
    inp = inputs.load(env.pdir)
    def spoken(bid):
        return re.search(r'[A-Za-z]+', inp.beat(bid)['text']).group()
    first = spoken('b0002')
    second = next((w for w in re.findall(r'[A-Za-z]+', inp.beat('b0003')['text']) if w.casefold() != first.casefold()), None)
    assert second
    env.agent.plan = plan(names=[{'name': first, 'also': [], 'line': 'b0002', 'where': {'region': 'MIRROR'}, 'sure': True, 'words': ''}])
    job = env.run(beats=['b0002'])
    assert job['state'] == 'done', job
    one = env.picks()['names']
    assert len(one) == 1 and one[0]['line'] == 'b0002' and one[0]['where'] == {'region': 'MIRROR'}
    env.agent.plan = plan(names=[{'name': second, 'also': [], 'line': 'b0003', 'where': {'want': 'b0003.1'}, 'sure': True, 'words': ''}])
    job = env.run(beats=['b0003'])
    assert job['state'] == 'done', job
    names = env.picks()['names']
    assert names[0] == one[0] and names[1]['line'] == 'b0003'
    assert names[1]['where']['asset'] in env.picks()['assets']


def test_subject_plan_search_choice_and_write_end_to_end(env):
    import re
    from bti.picks.auto import inputs
    inp = inputs.load(env.pdir)
    word = re.search(r'[A-Za-z]+', inp.beat('b0003')['text']).group()
    data = plan()
    data['subjects'] = [{'id': 'painter', 'kind': 'person', 'name': word, 'strip': True, 'where': {'want': 'b0003.1'}}]
    for row in data['lines']:
        row['about'] = []
    row = next(row for row in data['lines'] if row['beat'] == 'b0003')
    row['about'] = [{'id': 'painter', 'words': word}]
    row['show'][0]['entity'] = 'painter'
    env.agent.plan = data
    picked = choice()
    for entry in picked['wants']:
        entry['shows_subject'] = True
        entry['period_picture'] = True
    env.agent.choice = picked
    job = env.run(beats=['b0003'])
    assert job['state'] == 'done', job
    picks = env.picks()
    assert picks['subjects'][0]['where']['asset'] in picks['assets']
    assert picks['beats']['b0003']['about'] == [{'id': 'painter', 'words': word}]


def test_subject_job_retries_modern_photo_after_period_candidates_rejected(env, monkeypatch):
    import re
    from auto_helpers import FakeSource, install_sources, meta
    from bti.picks.auto import inputs
    sources = dict(env.sources)
    sources['pexels'] = FakeSource('pexels', [meta('pexels', 'p1', 'Modern portrait', 'portrait')])
    install_sources(monkeypatch, sources, keys=('pexels',))
    word = re.search(r'[A-Za-z]+', inputs.load(env.pdir).beat('b0003')['text']).group()
    data = plan()
    data['subjects'] = [{'id': 'painter', 'kind': 'person', 'name': word, 'strip': True, 'where': {'want': 'b0003.1'}}]
    for row in data['lines']:
        row['about'] = []
    row = next(row for row in data['lines'] if row['beat'] == 'b0003')
    row['about'] = [{'id': 'painter', 'words': word}]
    row['show'][0]['entity'] = 'painter'
    env.agent.plan = data
    calls = []
    def select(root, turn):
        calls.append(root)
        return {'wants': [{'id': 'b0003.1', 'pick': None if len(calls) == 1 else 1,
                           'shows_subject': True, 'period_picture': len(calls) == 1, 'no_period_picture': len(calls) > 1,
                           'reason': 'Chân dung phù hợp.'}], 'regions': []}
    env.agent.choice = select
    job = env.run(beats=['b0003'])
    assert job['state'] == 'done', job
    assert len(calls) == 2
    d = env.picks()
    assert d['subjects'][0]['where']['asset'] in d['assets']
    assert sources['pexels'].searches


def test_subject_job_reuses_one_picture_for_two_lines(env):
    import re
    from bti.picks.auto import inputs
    inp = inputs.load(env.pdir)
    names = {bid: re.search(r'[A-Za-z]+', inp.beat(bid)['text']).group() for bid in ('b0003', 'b0004')}
    data = plan()
    data['subjects'] = [{'id': 'painter', 'kind': 'person', 'name': names['b0003'], 'strip': True, 'where': {'want': 'b0003.1'}}]
    for row in data['lines']:
        row['about'] = []
    first, second = data['lines'][2:4]
    first['show'][0]['entity'] = 'painter'
    first['about'] = [{'id': 'painter', 'words': names['b0003']}]
    second.update(show=[], kinds=['outside'], about=[{'id': 'painter', 'words': names['b0004']}])
    env.agent.plan = data
    picked = choice()
    for item in picked['wants']:
        item.update(shows_subject=True, period_picture=True)
    env.agent.choice = picked
    job = env.run(beats=['b0003', 'b0004'])
    assert job['state'] == 'done', job
    picks = env.picks()
    assert picks['beats']['b0003']['items'][0]['asset'] == picks['beats']['b0004']['items'][0]['asset']
    assert picks['beats']['b0004']['about'][0]['id'] == 'painter'
