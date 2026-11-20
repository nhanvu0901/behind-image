"""The automatic run joined with the pictures agent (`picks.auto`) and the prompt boxes (`picks.edit`, `draft.edit`) (worker join2, round two).

    * the run takes `picks.auto` as one of its advancing steps with no change of its loop (real routes, the fake agent runner of tests/picks, the fake sources),
      then the picks gate by the rule of the owner; its cost counts the agent and not the box;
    * one agent job at a time, both ways: while a run goes on the boxes and a hand-started pictures agent are refused, and a job that is not the run's stops it;
    * the quality bar at the pictures gate: a flagged picture never stops it, a line with no picture stops it only above a quarter of the narration, and the run
      says how many lines it let through; every warning code of the picks document and of the storyboard is in one of the two lists.
No model, no program, no network."""
import ast
import re
import tempfile
import time
from pathlib import Path

import pytest

from run_helpers import P, PID, Scripted, act, actions_of, finish_run, made_state, run_to_end, set_auto, start_run, state
from picks_agent import PNG, FakeAgent, fake_book_thumb, fake_thumb, install_agent, install_sources
from test_loop import exported, posts, run_loop

from bti.auto_run import checks, reasons
from bti.cli.transport import Reply
from bti.draft import run as draft_run
from bti.picks import doc, service
from bti.picks.auto import search as asearch

REPO = Path(__file__).resolve().parents[2]
REAL_SEARCH = service.search               # the fake pipeline of `World` stands in for the picture search: the agent's search part needs the real one over the fake sources
REAL_DRAFT_START = draft_run.start         # ... and for the start of the draft and of the box of step 5: a test of their refusal needs the real one


# ---------------------------------------------------------------------------------------------------------------------------- the fixtures
def add_main_painting(c, pid: str = PID) -> None:
    """A main painting in the picks of the project (not approved)."""
    d = c.root / pid
    (d / "media").mkdir(exist_ok=True)
    (d / "media" / "main.png").write_bytes(PNG)
    pd = doc.empty()
    pd["main_asset"] = "A"
    pd["assets"]["A"] = {"file": "media/main.png", "kind": "image", "title": "The Arnolfini Portrait", "artist": "Jan Van Eyck", "year": "1434", "width": 1300, "height": 1250,
                         "credit": {"source": "upload", "flag": None}, "regions": {}}
    with doc.Held(d):
        doc.save(d, pd)


@pytest.fixture()
def agent(client, world, tmp_path, monkeypatch):
    """The project `arn` with an approved narration, the voice made, a main painting and no pictures; the fake agent runner and the fake sources. -> the fake agent."""
    world.build("voiced")
    add_main_painting(client)
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    install_sources(monkeypatch)
    monkeypatch.setattr(service, "search", REAL_SEARCH)
    monkeypatch.setattr(asearch, "default_fetch_thumb", fake_thumb)
    monkeypatch.setattr(asearch, "default_book_thumb", fake_book_thumb)
    return install_agent(monkeypatch, FakeAgent())


def act_of(st: dict, aid: str) -> dict:
    return next(a for a in st["next_actions"] if a["id"] == aid)


def wait_until(fn, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    raise AssertionError("it did not happen in time")


# ------------------------------------------------------------------------------------------------------------------- the agent is a step of the run
def test_the_run_takes_the_pictures_agent_as_an_advancing_step_then_approves_the_picks_by_the_rule(client, agent):
    set_auto(client, enabled=True)
    a = act_of(state(client), "picks.auto")
    assert a["ready"] is True and a["advances"] is True and a["cost"]["kind"] == "model" and a["body"]["actor"].startswith("agent:")      # the answer names an actor, like the operations' examples
    job, run = run_to_end(client, until="picks")
    assert actions_of(run) == ["picks.auto", "picks.approve"] and run["reason"] == "until_reached" and all(s["ok"] is True for s in run["steps"]), run["result"]
    first = run["steps"][0]
    assert first["body"]["actor"] == "agent:auto" and first["job_state"] == "done"                       # the run named itself: the route let its own call through its own job
    assert [c["mode"] for c in agent.calls] == ["plan", "choose"]                                          # the fake agent was asked once for each of its two sessions
    log = client.get(P + "/changes").json()["changes"]
    assert log and all(c["actor"] == "agent:mock" for c in log)                                           # every picture the agent wrote is a batch of the change log
    picks = client.get(P + "/picks").json()
    assert picks["approved"] is True and picks["picks"]["approval"]["by"] == "agent:auto"
    assert not any("/picks/suggest" in p for _, p, _ in client.transport.log)                              # never the paid call


def test_the_gate_the_owner_did_not_allow_stops_the_run_right_after_the_agent(client, agent):
    set_auto(client, enabled=True, gates={"picks": False})
    job, run = run_to_end(client, until="picks")
    res = run["result"]
    assert actions_of(run) == ["picks.auto"] and (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "gate_not_allowed", "picks")
    assert client.get(P + "/picks").json()["approved"] is False
    assert len(client.get(P + "/changes").json()["changes"]) >= 1                                          # the agent's work is kept: the owner looks at it and approves


def test_a_model_spend_the_owner_did_not_allow_stops_before_the_agent_and_starts_nothing(client, agent):
    set_auto(client, enabled=True, spend={"model": False})
    job, run = run_to_end(client, until="picks")
    res = run["result"]
    assert actions_of(run) == [] and (res["reason"], res["action"], res["kind"]) == ("spend_not_allowed", "picks.auto", "model")
    assert agent.calls == [] and client.get(P + "/changes").json()["changes"] == []


def test_the_cost_of_the_run_counts_the_agent_and_not_the_request_box(client, agent):
    set_auto(client, enabled=True)
    a = act_of(state(client), "auto.run")
    assert "model" in a["cost"]["kinds"] and "picks (about 20 minutes)" in a["cost"]["about"]               # the pictures agent is in the sum
    assert "30 seconds" not in a["cost"]["about"]                                                          # the boxes are a person's own requests: never taken by the run
    set_auto(client, spend={"model": False})
    assert act_of(state(client), "auto.run")["cost"] is None or "picks" not in act_of(state(client), "auto.run")["cost"]["about"]


# ------------------------------------------------------------------------------------------------------------------- one agent job at a time, both ways
def test_while_a_run_goes_on_the_pictures_box_and_a_hand_started_agent_are_refused_like_any_busy_case(client, world, agent):
    world.flags["voice"] = False                                                                           # the voice is the run's first step: it holds the run in a step that is not an agent job
    world.hold["voice"] = 1.5
    set_auto(client, enabled=True)
    started = start_run(client)
    st = wait_until(lambda: (lambda s: s if any(j["kind"] == "voice" for j in s["jobs"]) else None)(state(client)))
    assert {j["kind"] for j in st["jobs"]} == {"auto", "voice"}
    box = act_of(st, "picks.edit")
    assert box["ready"] is False and "no_running_job" in box["needs"]                                    # the answer says so before the route does
    auto = act_of(st, "picks.auto")
    assert auto["ready"] is True and auto["needs"] == []                                                   # the run itself takes it: the answer is the run's own
    r = client.post(P + "/picks/edit", json={"instruction": "đổi hình", "scope": {"beats": ["b0001"]}})
    assert r.status_code == 409 and r.json()["code"] == "agent_job_running" and r.json()["retry"] == "later" and r.json()["job_id"] == started["job_id"], r.text
    for actor in ({}, {"actor": "cli:bti"}, {"actor": "human"}):
        r = client.post(P + "/picks/auto", json=actor)
        assert r.status_code == 409 and r.json()["code"] == "agent_job_running" and r.json()["job_id"] == started["job_id"], (actor, r.text)
    assert agent.calls == [] and client.get(P + "/changes").json()["changes"] == []                       # nothing started, nothing written
    job, run = finish_run(client, started)
    assert "picks.auto" in actions_of(run) and run["steps"][actions_of(run).index("picks.auto")]["ok"] is True      # the run took the agent itself, through its own busy answer
    assert "no_running_job" not in act_of(state(client), "picks.edit")["needs"]                          # and the box is free again once the run ended


def test_while_a_run_goes_on_the_storyboard_box_is_refused_too(client, world, monkeypatch):
    world.build("drafted")
    monkeypatch.setattr(draft_run, "start", REAL_DRAFT_START)                                              # the route of the box, not the fake draft of the world
    world.hold["export"] = 1.5
    set_auto(client, enabled=True)
    started = start_run(client)
    st = wait_until(lambda: (lambda s: s if any(j["kind"] == "export" for j in s["jobs"]) else None)(state(client)))
    box = act_of(st, "draft.edit")
    assert box["ready"] is False and "no_running_job" in box["needs"]
    r = client.post(P + "/draft/edit", json={"instruction": "làm chậm hơn", "scope": {"all": True}})
    assert r.status_code == 409 and r.json()["code"] == "agent_job_running" and r.json()["job_id"] == started["job_id"], r.text
    finish_run(client, started)


def test_a_job_that_is_not_the_runs_refuses_the_run_the_pictures_agent_included(client, agent):
    from bti.draft.providers.agy import AgyResult

    def hold(mode, ws, kw):
        while not kw["cancel"]():
            time.sleep(0.02)
        return AgyResult(status="cancelled")
    agent.hook = hold
    set_auto(client, enabled=True)
    r = client.post(P + "/picks/auto", json={})
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    refused = client.post(P + "/auto/run", json={})
    assert refused.status_code == 409 and refused.json()["code"] == "longjob_running" and refused.json()["kind"] == "picks" and refused.json()["job_id"] == jid
    run = next(a for a in state(client)["next_actions"] if a["id"] == "auto.run")
    assert run["ready"] is False and run["needs"] == ["no_running_job"]
    client.post("/api/longjobs/%s/cancel" % jid, json={})
    wait_until(lambda: not state(client)["jobs"])


@pytest.mark.parametrize("kind,words", [("picks", "chọn hình"), ("draft", "sửa bằng lời")])
def test_the_run_reports_busy_elsewhere_when_the_agent_or_a_box_turn_runs(tmp_path, kind, words):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"})
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a], jobs=[{"id": "j9", "kind": kind, "state": "running"}])]))
    assert (res["outcome"], res["reason"]) == ("nothing_to_do", "busy_elsewhere") and words in res["sentence"]


def test_a_refusal_of_a_box_or_the_agent_that_blocks_the_call_is_busy_elsewhere_not_a_failure(tmp_path):
    a = act("picks.auto", "picks", cost={"kind": "model", "about": "x"}, long_job=True)
    t = Scripted(PID, [made_state([a], current="picks")], posts={a["path"]: Reply(409, {"detail": "busy", "code": "agent_job_running", "retry": "later"})})
    assert run_loop(tmp_path, t)[0]["reason"] == "busy_elsewhere"


def test_every_need_of_the_actions_the_run_waits_on_has_its_phrase():
    from bti.editor import state_api
    assert not set(state_api.NEEDS) - set(reasons.NEED_VI)
    assert "no_running_job" in reasons.NEED_VI and reasons._is_vietnamese(reasons.NEED_VI["no_running_job"])


# ------------------------------------------------------------------------------------------------------------------- the quality bar at the pictures gate
def no_pick(n):
    return [{"level": "warning", "code": "beat_no_pick", "message": "beat b%04d has no pick" % (i + 1), "beat": "b%04d" % (i + 1)} for i in range(n)]


def flags(n):
    return [{"level": "warning", "code": "asset_flag", "message": "asset K%d is flagged unknown" % i, "asset": "K%d" % i, "flag": "unknown"} for i in range(n)]


def picks_run(tmp_path, issues, lines, *, then=None, outside=None):
    """The loop at the picks gate with `lines` lines in the narration and these issues; `then`: the state that follows the approval (default: exported);
    `outside`: how many of the lines are about something outside the painting (`outside.lines` of GET .../picks; left out: the answer does not say)."""
    gate = act("picks.approve", "picks", gate=True, body={"rev": "r"})
    gate["path"] = "/api/projects/arn/picks/approve"
    narration = {"beat_ids": ["b%04d" % (i + 1) for i in range(lines)]} if lines is not None else {}
    docs = {"/api/projects/arn/picks": {"issues": issues, "narration": narration, **({"outside": {"lines": outside, "with_picture": 0, "without": []}} if outside is not None else {})}}
    t = Scripted(PID, [made_state([gate], current="picks"), then or exported()], docs=docs, posts={gate["path"]: Reply(200, {})})
    return (*run_loop(tmp_path, t), t)


@pytest.mark.parametrize("lines,none", [(12, 0), (12, 1), (12, 3), (4, 1), (8, 2), (100, 25)])
def test_lines_with_no_picture_up_to_a_quarter_of_the_narration_let_the_run_go_on_and_it_says_how_many(tmp_path, lines, none):
    res, r, log, t = picks_run(tmp_path, no_pick(none), lines)
    assert res["reason"] == "exported" and len(posts(t)) == 1                                              # the gate was approved
    step = log.rec["steps"][0]
    if none:
        assert res["lines_without_pick"] == none and res["tolerated"] == [{"gate": "picks", "code": "beat_no_pick", "count": none, "lines": lines}]
        assert res["sentence"].endswith("Có %d dòng lời dẫn không có hình riêng: bản nháp dùng tranh chính ở các dòng đó." % none) and res["sentence"].startswith("Xong: video đã được xuất.")
        assert "%d line(s)" % none in res["detail"] and "beat_no_pick x%d" % none in step["note"] and step["tolerated"] == [{"code": "beat_no_pick", "count": none}]
        assert log.rec["result"]["lines_without_pick"] == none                                              # the run log has the same result
    else:
        assert "lines_without_pick" not in res and "tolerated" not in res and res["sentence"] == "Xong: video đã được xuất."


@pytest.mark.parametrize("lines,none", [(12, 4), (12, 12), (4, 2), (1, 1), (8, 3), (100, 26)])
def test_more_than_a_quarter_of_the_lines_without_a_picture_stops_the_run_before_the_gate(tmp_path, lines, none):
    res, r, log, t = picks_run(tmp_path, no_pick(none), lines)
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "quality_warning", "picks") and posts(t) == []
    assert [i["code"] for i in res["issues"]] == ["beat_no_pick"] * none and "hơn một phần tư" in res["sentence"] and res["step"] == "picks"


def test_without_the_number_of_lines_a_missing_picture_stops_the_run_the_safe_side(tmp_path):
    res, _, _, t = picks_run(tmp_path, no_pick(1), None)
    assert res["reason"] == "quality_warning" and posts(t) == []
    res, _, _, t = picks_run(tmp_path, no_pick(1), 0)
    assert res["reason"] == "quality_warning" and posts(t) == []


def test_a_flagged_picture_never_stops_the_run_and_its_count_is_in_the_log(tmp_path):
    res, _, log, t = picks_run(tmp_path, flags(3), 10)
    assert res["reason"] == "exported" and len(posts(t)) == 1
    assert res["tolerated"] == [{"gate": "picks", "code": "asset_flag", "count": 3}] and "lines_without_pick" not in res and res["sentence"] == "Xong: video đã được xuất."
    assert "3 picture(s) carry a flag" in res["detail"]
    assert "asset_flag x3" in log.rec["steps"][0]["note"] and log.rec["steps"][0]["tolerated"] == [{"code": "asset_flag", "count": 3}]
    assert "asset_flag" in checks.TOLERATED["picks"] and "asset_flag" not in checks.STOPS["picks"]


def test_flags_do_not_hide_a_real_stop_and_a_stop_names_only_what_stops(tmp_path):
    res, _, _, t = picks_run(tmp_path, flags(2) + no_pick(5), 12)
    assert res["reason"] == "quality_warning" and {i["code"] for i in res["issues"]} == {"beat_no_pick"} and posts(t) == []
    res, _, _, t = picks_run(tmp_path, no_pick(2) + [{"level": "warning", "code": "beat_unknown", "message": "m", "beat": "b0099"}], 12)
    assert res["reason"] == "quality_warning" and [i["code"] for i in res["issues"]] == ["beat_unknown"] and posts(t) == []         # a picture on a line that is gone still stops it
    res, _, _, t = picks_run(tmp_path, no_pick(2) + [{"level": "warning", "code": "brand_new_check", "message": "m"}], 12)
    assert res["reason"] == "quality_warning" and [i["code"] for i in res["issues"]] == ["brand_new_check"] and posts(t) == []        # a warning nobody sorted stops it too


def test_an_error_still_stops_the_run_whatever_the_share(tmp_path):
    res, _, _, t = picks_run(tmp_path, no_pick(1) + [{"level": "error", "code": "no_main", "message": "no main painting is chosen"}], 12)
    assert (res["reason"], res["issues"][0]["code"]) == ("quality_error", "no_main") and posts(t) == []


def test_the_end_of_a_later_stop_still_says_how_many_lines_have_none(tmp_path):
    sb = act("storyboard.approve", "edit", gate=True, auto_ok=False, body={"rev": "r"})
    sb["path"] = "/api/projects/arn/approve"
    gate = act("picks.approve", "picks", gate=True, body={"rev": "r"})
    gate["path"] = "/api/projects/arn/picks/approve"
    docs = {"/api/projects/arn/picks": {"issues": no_pick(2), "narration": {"beat_ids": ["b%04d" % i for i in range(1, 11)]}}}
    t = Scripted(PID, [made_state([gate], current="picks"), made_state([sb], current="edit")], docs=docs, posts={gate["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "gate_not_allowed", "storyboard")
    assert res["lines_without_pick"] == 2 and "Có 2 dòng lời dẫn không có hình riêng" in res["sentence"] and res["sentence"].count("Có 2 dòng") == 1


def no_outside(n, first=1):
    return [{"level": "warning", "code": "outside_no_picture", "message": "beat b%04d is about something outside the painting but shows only the main painting" % (first + i),
             "beat": "b%04d" % (first + i)} for i in range(n)]


@pytest.mark.parametrize("outside,none", [(10, 0), (10, 3), (3, 1), (6, 2), (100, 34), (1, 0), (50, 17)])
def test_lines_about_something_outside_that_have_only_the_painting_up_to_34_percent_of_them_let_the_run_go_on_and_it_says_how_many(tmp_path, outside, none):
    res, r, log, t = picks_run(tmp_path, no_outside(none), 61, outside=outside)
    assert res["reason"] == "exported" and len(posts(t)) == 1
    step = log.rec["steps"][0]
    if none:
        assert res["tolerated"] == [{"gate": "picks", "code": "outside_no_picture", "count": none, "lines": outside}]                      # the share is of the outside lines
        assert res["lines_outside_without_picture"] == none and "outside_no_picture x%d" % none in step["note"]
        assert res["sentence"].endswith("Có %d dòng nói về thứ ngoài bức tranh mà chưa tìm được hình của thứ đó (trong %d dòng như vậy): bản nháp dùng tranh chính ở các dòng đó."
                                        % (none, outside))
        assert "%d of the %d line(s) about something outside the painting show only the main painting" % (none, outside) in res["detail"]
        assert step["tolerated"] == [{"code": "outside_no_picture", "count": none}] and log.rec["result"]["lines_outside_without_picture"] == none        # the run log says how many
    else:
        assert "tolerated" not in res and "lines_outside_without_picture" not in res and res["sentence"] == "Xong: video đã được xuất."


@pytest.mark.parametrize("outside,none", [(10, 4), (3, 2), (1, 1), (6, 3), (100, 35), (50, 18), (30, 11)])
def test_more_than_34_percent_of_the_outside_lines_with_only_the_painting_stops_the_run_with_the_list(tmp_path, outside, none):
    res, r, log, t = picks_run(tmp_path, no_outside(none, first=7), 61, outside=outside)
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "quality_warning", "picks") and posts(t) == []
    assert [i["code"] for i in res["issues"]] == ["outside_no_picture"] * none and [i["beat"] for i in res["issues"]] == ["b%04d" % (7 + k) for k in range(none)]    # the list
    assert "hơn 34% số dòng nói về thứ ngoài bức tranh" in res["sentence"] and res["step"] == "picks"
    assert res["issues"][0]["why"].startswith("more than 34% of the lines about something outside the painting")


def test_the_share_is_of_the_outside_lines_not_of_all_the_lines_and_a_missing_number_stops_the_run_the_safe_side(tmp_path):
    res, _, _, t = picks_run(tmp_path, no_outside(4), 100, outside=10)                      # 4% of the narration but 40% of the outside lines
    assert res["reason"] == "quality_warning" and posts(t) == []
    res, _, _, t = picks_run(tmp_path, no_outside(30), 100, outside=100)                    # more than a quarter of all lines, but 30% of the outside lines
    assert res["reason"] == "exported" and len(posts(t)) == 1
    for outside in (None, 0):
        res, _, _, t = picks_run(tmp_path, no_outside(1), 61, outside=outside)
        assert res["reason"] == "quality_warning" and posts(t) == []


def test_the_two_shares_are_judged_apart(tmp_path):
    both = no_pick(3) + no_outside(3, first=20)                                             # 3 of 61 lines have no picture; 3 of 10 outside lines have only the painting
    res, _, _, t = picks_run(tmp_path, both, 61, outside=10)
    assert res["reason"] == "exported" and {x["code"] for x in res["tolerated"]} == {"beat_no_pick", "outside_no_picture"}
    assert res["lines_without_pick"] == 3 and res["lines_outside_without_picture"] == 3
    assert res["sentence"].count("Có 3 dòng") == 2
    res, _, _, t = picks_run(tmp_path, no_pick(3) + no_outside(4, first=20), 61, outside=10)
    assert res["reason"] == "quality_warning" and {i["code"] for i in res["issues"]} == {"outside_no_picture"} and posts(t) == []         # only the one that is over the share stops it
    res, _, _, t = picks_run(tmp_path, no_pick(20) + no_outside(3, first=20), 61, outside=10)
    assert res["reason"] == "quality_warning" and {i["code"] for i in res["issues"]} == {"beat_no_pick"} and posts(t) == []


def test_a_picks_document_without_kinds_gives_no_outside_lines_and_raises_nothing_new(tmp_path):
    res, _, _, t = picks_run(tmp_path, no_pick(2), 12, outside=0)
    assert res["reason"] == "exported" and [x["code"] for x in res["tolerated"]] == ["beat_no_pick"] and "lines_outside_without_picture" not in res


def test_the_lists_and_the_share_rule_are_the_ones_the_documents_say():
    assert checks.NO_PICK_LIMIT == 0.25 and checks.OUTSIDE_NO_PICTURE_LIMIT == 0.34
    assert checks.SHARE_LIMITS == {"picks": {"beat_no_pick": 0.25, "outside_no_picture": 0.34}} and checks.SHARE_OF == {"outside_no_picture": "outside"}
    assert "beat_no_pick" in checks.STOPS["picks"] and checks.STOPS["picks"]["beat_no_pick"][1].startswith("hơn một phần tư")
    assert checks.STOPS["picks"]["outside_no_picture"][1].startswith("hơn 34% số dòng nói về thứ ngoài bức tranh")
    assert set(checks.STOPS["picks"]) == {"beat_no_pick", "beat_unknown", "outside_no_picture"} and checks.TOLERATED["picks"] == frozenset({"asset_flag"})
    text = (REPO / "docs" / "AGENT_API.md").read_text(encoding="utf-8")
    assert "`beat_no_pick` (only when more than 25% of the lines have it)" in text
    assert "`outside_no_picture` (only when more than 34% of the lines about something outside the painting have it)" in text
    assert "| `picks` | `beat_no_pick` (only when more than 25% of the lines have it), `beat_unknown`, `outside_no_picture` (only when more than 34% of the lines about something outside the painting have it) |" in text
    for words in ("hơn một phần tư", "asset_flag", "beat_no_pick"):
        assert words in (REPO / "docs" / "APP_GUIDE.md").read_text(encoding="utf-8") + (REPO / "AGENTS.md").read_text(encoding="utf-8") + text, words


# ------------------------------------------------------------------------------------------------------------------- every warning is sorted
def warning_codes(files) -> dict[str, str]:
    """Every `code` the sources give an issue of level warn / warning: a dict literal with `level` and `code`, or a call `warn(path, message, "code", ...)`."""
    found: dict[str, str] = {}
    for f in files:
        tree = ast.parse(Path(f).read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.Dict):
                d = {k.value: v.value for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
                if d.get("level") in ("warn", "warning") and isinstance(d.get("code"), str):
                    found.setdefault(d["code"], str(f))
            if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", None)) == "warn" and len(n.args) >= 3 \
                    and isinstance(n.args[2], ast.Constant) and isinstance(n.args[2].value, str):
                found.setdefault(n.args[2].value, str(f))
    return found


def test_every_warning_code_the_picks_document_and_the_storyboard_can_give_is_in_one_of_the_two_lists():
    from bti.engine import storyboard as SB
    picks = warning_codes([REPO / "bti" / "picks" / "doc.py"])
    assert {"beat_no_pick", "asset_flag", "beat_unknown", "outside_no_picture"} <= set(picks)
    engine = warning_codes(sorted((REPO / "bti" / "engine").rglob("*.py")))
    engine.update({c: "ISSUE_CODES" for c, text in SB.ISSUE_CODES.items() if "(warning)" in text})
    assert {"audio_missing", "canvas_not_1080p", "incomplete"} <= set(engine)
    for gate, codes in (("picks", picks), ("storyboard", engine)):
        sorted_codes = set(checks.STOPS[gate]) | set(checks.TOLERATED[gate])
        missing = sorted(c for c in codes if c not in sorted_codes)
        assert not missing, "a warning the %s document can give is in neither list of bti/auto_run/checks.py (it stops the run until it is sorted): %s" % (gate, missing)
