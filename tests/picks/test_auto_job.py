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
    assert (r["pictures_imported"], r["regions_made"], r["clips"]) == (3, 2, 1)
    assert r["sentence"] == "Agent đã chọn hình cho 6/6 đoạn." and r["stopped"] is None
    assert part_states(job) == [("plan", "done"), ("search", "done"), ("choose", "done"), ("write", "done")]
    assert job["parts"][0]["title"] == "Lập danh sách hình cần tìm (1/4)"
    d = env.picks()
    a = d["assets"]["A"]
    assert set(a["regions"]) == {"MIRROR", "HEAD"} and a["regions"]["HEAD"]["rx"] == 156 and a["regions"]["HEAD"]["ry"] == 150      # the agent's adjusted box
    assert a["regions"]["HEAD"]["label"] == "Khuôn mặt" and a["regions"]["MIRROR"]["x"] == 650 and a["regions"]["MIRROR"]["rx"] == 130
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
    assert plan_call["model"] == job["meta"]["model"] and plan_call["timeout"] == 20 * 60 and plan_call["max_repairs"] == 1
    ext = ".cmd" if os.name == "nt" else ""
    assert {"TASK.md", "check" + ext, "crop" + ext, "inputs/painting.json", "inputs/narration.json", "images/main.jpg", "inputs/main_large.jpg"} <= set(plan_call["files"])
    assert {"inputs/wants.json", "images/w_b0003_1.jpg", "images/w_b0004_2.jpg", "images/d_MIRROR.jpg", "images/d_HEAD.jpg"} <= set(choose_call["files"])
    assert "images/w_b0004_1.jpg" not in choose_call["files"]                                  # a map has no sheet: its candidate is a place
    assert job["meta"]["limits"] == {"plan": {"minutes": 20, "steps": 80, "repairs": 1}, "choose": {"minutes": 20, "steps": 80, "repairs": 1}}
    assert result(job)["limits"]["plan"]["steps"] == 80
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
    p["lines"][0]["show"] = [{"type": "detail", "region": "HEAD"}]                              # the agent now plans something else for the first line
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
    p = plan(lines=[{"beat": "b0001", "reason": "Cả tranh.", "show": [{"type": "whole"}, clip("1")]},                # on a painting line: dropped
                    {"beat": "b0002", "reason": "Chi tiết.", "show": [{"type": "detail", "region": "MIRROR"}]},
                    {"beat": "b0003", "reason": "Cảnh một.", "show": [clip("2")]},                                    # the first clip of c02
                    {"beat": "b0004", "reason": "Cảnh hai.", "show": [clip("3")]},                                    # a second one in c02: dropped
                    {"beat": "b0005", "reason": "Đầu.", "show": [{"type": "detail", "region": "HEAD"}]},
                    {"beat": "b0006", "reason": "Giữ.", "show": []}])
    env.agent.plan = p
    job = env.run()
    assert job["state"] == "done", job.get("error")
    saved = store.read(env.pdir, "plan.json")
    shown = {ln["beat"]: [i["type"] for i in ln["show"]] for ln in saved["plan"]["lines"]}
    assert shown == {"b0001": ["whole"], "b0002": ["detail"], "b0003": ["clip"], "b0004": [], "b0005": ["detail"], "b0006": []}
    assert len([n for n in saved["notes"] if "the clip was dropped" in n]) == 2 and any("a clip lasts 4 to 10 seconds" in n for n in saved["notes"])
    assert saved["plan"]["lines"][2]["show"][0]["seconds"] == 10.0
    r = result(job)
    assert r["clips"] == 1 and env.picks()["beats"]["b0003"]["items"][0]["role"] == "video" and env.picks()["beats"]["b0004"]["status"] == "skip"


def test_a_detail_the_choose_step_drops_shows_the_whole_painting_and_its_box_is_not_made(env):
    env.agent.choice = choice(regions=[CHOICE["regions"][0], {"name": "HEAD", "action": "drop", "reason": "Khung không trúng khuôn mặt."}])
    job = env.run()
    assert job["state"] == "done"
    d = env.picks()
    assert set(d["assets"]["A"]["regions"]) == {"MIRROR"}
    assert [(i["asset"], i["region"], i["role"]) for i in d["beats"]["b0005"]["items"]] == [("A", None, "main")]            # the whole painting, once
    r = result(job)
    assert r["regions_dropped"] == ["HEAD"] and r["regions_made"] == 1 and r["lines_done"] == 6


def test_a_want_with_no_candidates_is_listed_and_the_job_goes_on(env):
    env.sources["commons"].items = [m for m in env.sources["commons"].items if m["kind"] == "video"]
    env.sources["met"].items = []
    job = env.run()
    assert job["state"] == "done"
    r = result(job)
    assert (r["lines_total"], r["lines_done"]) == (6, 5) and [x["beat"] for x in r["lines_without"]] == ["b0003"]
    assert r["lines_without"][0]["code"] == "no_candidates" and "Chân dung họa sĩ" in r["lines_without"][0]["why"] and r["lines_without"][0]["no"] == 3
    assert r["sentence"] == "Agent đã chọn hình cho 5/6 đoạn. 1 đoạn chưa có hình phù hợp."
    assert "b0003" not in env.picks()["beats"] or env.picks()["beats"]["b0003"]["items"] == []                              # left as it was
    assert "images/w_b0003_1.jpg" not in env.agent.calls[1]["files"]                                                         # the agent was not shown an empty sheet
    assert store.read(env.pdir, "search.json")["wants"]["b0003.1"]["status"] == "none"


def test_a_source_that_is_rate_limited_is_left_alone_and_its_wants_are_listed_without_waiting(env):
    slow = mhttp.MediaHTTPError("HTTP 429", 429, retry_after=120)
    env.sources["commons"].fail, env.sources["met"].fail = slow, slow
    t0 = time.monotonic()
    job = env.run()
    assert time.monotonic() - t0 < 20 and job["state"] == "done"                                                             # nothing waited for the two minutes
    r = result(job)
    assert [x["beat"] for x in r["lines_without"]] == ["b0003"] and r["lines_without"][0]["code"] == "source_limited"
    assert "đang giới hạn lượt tải" in r["lines_without"][0]["why"] and "khoảng 2 phút" in r["lines_without"][0]["why"]
    assert len(env.sources["commons"].searches) == 1 and len(env.sources["met"].searches) == 1                                # left alone: not asked again by the clip want either
    wants = store.read(env.pdir, "search.json")["wants"]
    assert wants["b0003.1"]["status"] == "limited" and wants["b0004.2"]["status"] == "limited" and wants["b0004.1"]["status"] == "found"
    # the line with a map and a clip is written with the map; what is missing is listed
    assert [i["role"] for i in env.picks()["beats"]["b0004"]["items"]] == ["map"]
    assert {m["want"] for m in r["missing"]} == {"b0003.1", "b0004.2"}
    assert "Chưa tìm được: Kênh đào." in env.picks()["beats"]["b0004"]["note"]


def test_a_candidate_with_no_thumbnail_cannot_be_chosen_and_the_main_painting_is_never_a_context_picture(env):
    from auto_helpers import meta
    env.sources["commons"].items = [meta("commons", "File:nothumb.jpg", "No thumbnail", "portrait"), meta("commons", "File:Canal boat.mp4", "Canal boat", "canal boat", kind="video")]
    env.sources["met"].items = []
    job = env.run()
    r = result(job)
    assert [x["beat"] for x in r["lines_without"]] == ["b0003"] and r["lines_without"][0]["code"] == "no_thumbs"
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


# ---------------------------------------------------------------------------------------------------------------- the agent's files
def test_an_output_that_fails_the_check_is_repaired_once(env):
    bad = plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.5, 0.6], "what": "Gương"}, PLAN["regions"][1]])
    env.agent.plan = [bad, PLAN]
    job = env.run()
    assert job["state"] == "done"
    first = env.agent.calls[0]
    assert len(first["problems"]) == 2 and "outside the painting" in first["problems"][0] and first["problems"][1] is None
    assert "ERROR regions[0] (MIRROR)" in first["problems"][0]                                  # the repair message says where and what to change


def test_an_output_that_fails_the_check_twice_fails_the_part_with_its_sentence_and_writes_nothing(env):
    bad = plan(regions=[{"name": "MIRROR", "box": [0.4, 0.3, 1.5, 0.6], "what": "Gương"}, PLAN["regions"][1]])
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
