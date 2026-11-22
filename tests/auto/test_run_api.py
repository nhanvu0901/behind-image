"""The automatic run through the app: `POST /api/projects/{pid}/auto/run` as one long job of the shared runner, walking the fixture project from each of its
stages with fake long jobs (real jobs of the runner with quick parts: nothing heavy, paid or model-driven), and ending as it should; the refusals of the
route; cancel and "start again continues"; the run log; the list of runs; the entries of the state answer; an advancing action nobody planned for."""
import json
import time

import pytest

from bti.auto_run import checks, loop, reasons, runlog
from run_helpers import (P, PID, STAGES, World, act, actions_of, finish_run, run_to_end, set_auto, start_run, state, wait_longjob)

EXPECTED = {
    "new": (["outline.generate", "outline.approve", "narration.generate", "narration.approve", "voice.generate"], "nothing_to_do"),
    "outline_waiting": (["outline.approve", "narration.generate", "narration.approve", "voice.generate"], "nothing_to_do"),
    "narration_approved": (["voice.generate"], "nothing_to_do"),
    "voiced": ([], "nothing_to_do"),
    "picks_approved": (["draft.start", "proposal.apply", "storyboard.review", "storyboard.approve", "export.start"], "exported"),
    "proposal_waiting": (["proposal.apply", "storyboard.review", "storyboard.approve", "export.start"], "exported"),
    "drafted": (["storyboard.review", "storyboard.approve", "export.start"], "exported"),
    "storyboard_approved": (["export.start"], "exported"),
    "exported": ([], "exported"),
}


def wait_until(fn, timeout=20.0):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    raise AssertionError("it did not happen in time")


def result_of(job: dict) -> dict:
    return job["meta"]["result"]


# --------------------------------------------------------------------------------------------------------------- from each stage
def test_the_stages_are_the_ones_expected_here():
    assert set(EXPECTED) == set(STAGES)


@pytest.mark.parametrize("stage", STAGES)
def test_from_every_stage_it_takes_the_expected_actions_in_order_and_ends_as_expected(client, world, stage):
    world.build(stage)
    set_auto(client, enabled=True)
    job, run = run_to_end(client)
    actions, reason = EXPECTED[stage]
    assert actions_of(run) == actions, (run["result"]["sentence"], [(i["code"], i["message"]) for i in run["result"].get("issues") or []])
    assert run["reason"] == reason, run["result"]
    assert job["state"] == "done" and result_of(job)["reason"] == reason and job["result"]["reason"] == reason
    assert run["ended"] and all(s["ok"] is True for s in run["steps"])
    assert not any("/picks/suggest" in p for _, p, _ in client.transport.log)                    # never the paid call
    if reason == "exported":
        assert run["outcome"] == "done" and state(client)["steps"][-1]["state"] == "done"


def test_a_whole_project_from_the_first_step_to_the_export_once_the_pictures_are_there(client, world):
    """A project at the start: the run stops where the pictures are needed; the owner picks; the next run goes on to the end."""
    world.build("new")
    set_auto(client, enabled=True)
    _, first = run_to_end(client)
    assert first["reason"] == "nothing_to_do" and first["result"]["waiting_for"] == ["main_asset"] and first["result"]["step"] == "picks"      # the first thing the picks step waits for is the pictures agent's own need: a main painting
    assert first["result"]["action"] == "picks.auto" and "chọn tranh chính" in first["result"]["sentence"]
    from state_helpers import make_picks
    make_picks(client)
    world.flags["picks_ok"] = True
    _, second = run_to_end(client)
    assert actions_of(second) == ["draft.start", "proposal.apply", "storyboard.review", "storyboard.approve", "export.start"] and second["reason"] == "exported"
    assert second["id"] != first["id"]


def test_every_call_of_the_run_is_a_call_the_answer_listed_with_the_gates_as_agent_auto(client, world):
    world.build("picks_approved")
    set_auto(client, enabled=True)
    _, run = run_to_end(client)
    gate = next(s for s in run["steps"] if s["action"] == "storyboard.approve")
    assert gate["body"]["actor"] == "agent:auto" and gate["method"] == "POST" and gate["path"] == P + "/approve"
    sb = json.loads((client.root / PID / "storyboard.json").read_text(encoding="utf-8"))
    assert sb["approvals"]["storyboard"]["by"] == "agent:auto"              # the server recorded who approved
    seen = [(m, p) for m, p, _ in client.transport.log if m == "POST"]
    assert seen == [("POST", s["path"]) for s in run["steps"]]                # and nothing else was ever sent: no operation batches, no edits


# --------------------------------------------------------------------------------------------------------------- what the owner allowed
def test_a_gate_the_owner_did_not_allow_stops_the_run_there_with_that_gate_named(client, world):
    world.build("outline_waiting")
    set_auto(client, enabled=True, gates={"narration": False})
    job, run = run_to_end(client)
    assert actions_of(run) == ["outline.approve", "narration.generate"]
    res = run["result"]
    assert (res["outcome"], res["reason"], res["gate"], res["step"]) == ("needs_owner", "gate_not_allowed", "narration", "script")
    assert res["link"] == "#/project/arn/script" and "lời dẫn" in res["sentence"]
    assert state(client)["approvals"]["narration"] is None


@pytest.mark.parametrize("kind,action", [("machine_time", "voice.generate"), ("model", "draft.start")])
def test_a_kind_of_cost_the_owner_did_not_allow_stops_the_run_and_starts_nothing(client, world, kind, action):
    world.build("narration_approved" if kind == "machine_time" else "picks_approved")
    set_auto(client, enabled=True, spend={kind: False})
    _, run = run_to_end(client)
    assert actions_of(run) == [] and run["reason"] == "spend_not_allowed" and run["result"]["kind"] == kind and run["result"]["action"] == action
    assert world.calls == []


def test_the_run_is_refused_while_automatic_running_is_off_and_leaves_no_trace(client, world):
    world.build("narration_approved")
    r = client.post(P + "/auto/run", json={})
    assert r.status_code == 409 and r.json()["code"] == "auto_not_enabled" and r.json()["fix"] and r.json()["retry"] == "after_fix"
    assert world.calls == [] and not (client.root / PID / "auto_runs").exists() and client.get(P + "/auto/runs").json() == {"items": []}
    set_auto(client, enabled=True)
    set_auto(client, enabled=False)
    assert client.post(P + "/auto/run", json={}).status_code == 409


def test_turning_the_switch_off_in_the_middle_stops_the_run_after_the_step_in_hand(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 0.6
    set_auto(client, enabled=True)
    started = start_run(client)
    wait_until(lambda: world.calls)
    set_auto(client, enabled=False)
    job, run = finish_run(client, started)
    assert actions_of(run) == ["voice.generate"] and run["reason"] == "auto_turned_off" and run["outcome"] == "needs_owner"
    assert world.flags["voice"] is True                                       # the step in hand was finished, nothing new was started


# --------------------------------------------------------------------------------------------------------------- refusals of the route
def test_the_body_is_checked(client, world):
    world.build("voiced")
    set_auto(client, enabled=True)
    for body, path in [({"until": "lunch"}, "until"), ({"max_steps": 0}, "max_steps"), ({"max_steps": 201}, "max_steps"), ({"max_steps": True}, "max_steps"),
                       ({"max_steps": "9"}, "max_steps"), ({"nope": 1}, "nope"), ({"actor": "root"}, "actor")]:
        r = client.post(P + "/auto/run", json=body)
        assert r.status_code == 422 and r.json()["code"] == "invalid_field", body
        assert any(f["path"] == path for f in r.json()["fields"]), (body, r.json())
    assert client.post(P + "/auto/run", content=b"[1]", headers={"content-type": "application/json"}).status_code == 422
    assert client.get(P + "/auto/runs").json() == {"items": []}


def test_another_job_of_the_project_refuses_the_run_and_a_second_run_is_refused_too(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    world.hold["voice"] = 0.5
    assert client.post(P + "/voice/generate", json={}).status_code == 200
    r = client.post(P + "/auto/run", json={})
    assert r.status_code == 409 and r.json()["code"] == "longjob_running" and r.json()["kind"] == "voice" and r.json()["job_id"]
    wait_until(lambda: not state(client)["jobs"])
    world.hold["voice"] = 1.5
    world.flags["voice"] = False                                                 # the voice made by hand is forgotten: the run has a voice to make
    started = start_run(client)
    wait_until(lambda: any(j["kind"] == "voice" for j in state(client)["jobs"]))
    again = client.post(P + "/auto/run", json={})
    assert again.status_code == 409 and again.json()["code"] == "auto_running" and again.json()["job_id"] == started["job_id"]
    finish_run(client, started)
    assert world.calls.count("voice") == 2                                      # the by-hand one and the run's: the refused run started nothing


def test_an_unknown_project_is_404(client):
    assert client.post("/api/projects/nope/auto/run", json={}).status_code == 404
    assert client.get("/api/projects/nope/auto/runs").status_code == 404


# --------------------------------------------------------------------------------------------------------------- cancel, continue, limits
def test_cancel_in_the_middle_of_a_step_stops_its_job_and_start_again_continues(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 30.0
    set_auto(client, enabled=True)
    started = start_run(client)
    jobs = wait_until(lambda: [j for j in state(client)["jobs"] if j["kind"] == "voice"])
    cancel = next(a for a in state(client)["next_actions"] if a["id"] == "auto.cancel")           # the state answer offers the stop while the run goes on
    assert cancel["job_id"] == started["job_id"] and cancel["method"] == "POST" and cancel["path"] == "/api/longjobs/%s/cancel" % started["job_id"]
    assert client.post(cancel["path"]).status_code == 200
    job, run = finish_run(client, started)
    assert job["state"] == "cancelled" and run["outcome"] == "cancelled" and run["reason"] == "cancelled"
    assert run["steps"][0]["action"] == "voice.generate" and run["steps"][0]["job_state"] == "cancelled"
    voice = wait_longjob(client, jobs[0]["id"])
    assert voice["state"] == "cancelled" and world.flags["voice"] is False                        # the job the run started was stopped, nothing was made
    assert state(client)["jobs"] == [] and not any(a["id"] == "auto.cancel" for a in state(client)["next_actions"])
    world.hold["voice"] = 0.04                                                                    # start again: the project still stands where it did
    job2, run2 = run_to_end(client)
    assert actions_of(run2) == ["voice.generate"] and world.flags["voice"] is True and run2["id"] != run["id"]
    assert run2["reason"] == "nothing_to_do"


def test_the_step_limit(client, world):
    world.build("picks_approved")
    set_auto(client, enabled=True)
    job, run = run_to_end(client, max_steps=2)
    assert actions_of(run) == ["draft.start", "proposal.apply"] and run["outcome"] == "limit" and run["reason"] == "step_limit"
    assert result_of(job)["steps_taken"] == 2 and job["state"] == "done"
    _, more = run_to_end(client, max_steps=3)                                                      # and it goes on from there
    assert actions_of(more) == ["storyboard.review", "storyboard.approve", "export.start"] and more["reason"] == "exported"


def test_until_a_step(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    _, run = run_to_end(client, until="voice")
    assert actions_of(run) == ["voice.generate"] and run["reason"] == "until_reached" and run["result"]["step"] == "voice" and run["outcome"] == "done"


def test_a_failing_job_ends_the_job_with_the_code_and_the_sentence(client, world):
    world.build("narration_approved")
    world.fail["voice"] = ("voice_worker_failed", "Máy đọc giọng bị lỗi.")
    set_auto(client, enabled=True)
    job, run = run_to_end(client)
    assert job["state"] == "error" and job["error_code"] == "voice_worker_failed" and "Máy đọc giọng bị lỗi" in job["error"]
    assert (run["outcome"], run["reason"]) == ("failed", "job_failed") and run["result"]["action"] == "voice.generate" and run["result"]["error"]["code"] == "voice_worker_failed"
    assert result_of(job)["reason"] == "job_failed"
    assert run["steps"][0]["job_state"] == "error"


def test_a_refused_action_ends_the_job_as_failed_with_the_servers_words(client, world, monkeypatch):
    import bti.voice.run as voice_run
    from bti.voice.errors import VoiceError

    def refuse(*a, **k):
        raise VoiceError("voice_not_configured", "no voice worker is configured on this machine", 422)
    world.build("narration_approved")
    monkeypatch.setattr(voice_run, "start", refuse)
    set_auto(client, enabled=True)
    job, run = run_to_end(client)
    assert job["state"] == "error" and job["error_code"] == "voice_not_configured"
    res = run["result"]
    assert (res["outcome"], res["reason"], res["action"]) == ("failed", "action_failed", "voice.generate") and res["error"]["status"] == 422
    assert res["error"]["fix"] and run["steps"][0]["ok"] is False and run["steps"][0]["code"] == "voice_not_configured"


def test_a_job_cancelled_from_the_page_ends_the_run_as_cancelled(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 0.3
    set_auto(client, enabled=True)
    started = start_run(client)
    wait_until(lambda: world.calls)
    from bti.longjob import manager
    manager.cancel(next(j["id"] for j in state(client)["jobs"] if j["kind"] == "voice"))
    job, run = finish_run(client, started)
    assert (run["outcome"], run["reason"]) == ("cancelled", "job_cancelled_elsewhere") and job["state"] == "done"          # the job it follows was stopped under it


# --------------------------------------------------------------------------------------------------------------- a step nobody planned for
def test_an_advancing_action_added_to_the_state_answer_is_taken_without_a_change_in_the_run(client, world, monkeypatch):
    """The state answer decides what advancing means: a new step (the agent that chooses the pictures will be `picks.auto`) is picked up by the run as it is."""
    from bti.editor import state_api
    spec = state_api.Spec("fake.step", "picks", "Việc giả", "POST", state_api.P + "/fake/step", when="a test")
    seen = []

    def builder(c):
        return state_api.E([], {"note": "fake"}, advances=not world.flags.get("fake")) if c.open("picks") and not world.flags.get("fake") else None
    monkeypatch.setattr(state_api, "SPECS", state_api.SPECS + [spec])
    monkeypatch.setitem(state_api.SPEC, "fake.step", spec)
    monkeypatch.setitem(state_api.BUILDERS, "fake.step", builder)

    def fake_route(pid: str, body: dict):
        seen.append(body)
        world.flags["fake"] = True
        return {"ok": True}
    client.app.add_api_route("/api/projects/{pid}/fake/step", fake_route, methods=["POST"])
    world.build("voiced")
    set_auto(client, enabled=True)
    assert "fake.step" in [a["id"] for a in state(client)["next_actions"]]
    _, run = run_to_end(client)
    assert actions_of(run) == ["fake.step"] and seen == [{"note": "fake"}] and run["reason"] == "nothing_to_do"


def test_a_paid_advancing_action_is_never_called_whatever_the_answer_says(client, world, monkeypatch):
    from bti.editor import state_api
    spec = state_api.Spec("fake.paid", "picks", "Việc tốn tiền", "POST", state_api.P + "/fake/paid", cost=("paid", "money"), when="a test")
    called = []
    monkeypatch.setattr(state_api, "SPECS", state_api.SPECS + [spec])
    monkeypatch.setitem(state_api.SPEC, "fake.paid", spec)
    monkeypatch.setitem(state_api.BUILDERS, "fake.paid", lambda c: state_api.E([], {}, advances=True) if c.open("picks") else None)
    monkeypatch.setattr(state_api, "_auto_ok", lambda spec_, c: True)                  # even an answer that says an agent may
    client.app.add_api_route("/api/projects/{pid}/fake/paid", lambda pid: called.append(pid), methods=["POST"])
    world.build("voiced")
    set_auto(client, enabled=True)
    _, run = run_to_end(client)
    assert called == [] and run["reason"] == "paid_needs_owner" and run["result"]["action"] == "fake.paid" and actions_of(run) == []


# --------------------------------------------------------------------------------------------------------------- the log and the list
def test_the_run_log_is_a_file_of_the_project_and_the_list_says_the_same(client, world):
    world.build("storyboard_approved")
    set_auto(client, enabled=True)
    started = start_run(client, until="export")
    job, run = finish_run(client, started)
    f = client.root / PID / "auto_runs" / (started["run_id"] + ".json")
    on_disk = json.loads(f.read_text(encoding="utf-8"))
    assert on_disk["id"] == started["run_id"] and on_disk["job_id"] == started["job_id"] and on_disk["until"] == "export" and on_disk["max_steps"] == 40
    assert on_disk["schema"] == "bti.autorun/1" and on_disk["steps"][0]["action"] == "export.start" and on_disk["ended"] and on_disk["outcome"] == "done"
    items = client.get(P + "/auto/runs").json()["items"]
    assert len(items) == 1 and items[0]["id"] == started["run_id"] and items[0]["state"] == "finished" and items[0]["steps_taken"] == 1
    assert items[0]["outcome"] == "done" and items[0]["sentence"] == "Xong: video đã được xuất." and "steps" not in items[0]
    assert items[0]["link"] == "#/project/arn/export"
    assert client.get(P + "/auto/runs/20200101-000000-0000").status_code == 404
    assert client.get(P + "/auto/runs/..%2F..%2Fproject").status_code in (404, 422)


def test_the_list_is_newest_first_and_a_run_that_goes_on_shows_what_it_does(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    run_to_end(client)                                                          # the first ends: voice made, then it waits for the pictures
    world.flags["voice"] = False
    world.hold["voice"] = 1.0
    started = start_run(client)
    item = wait_until(lambda: next((i for i in client.get(P + "/auto/runs").json()["items"] if i["id"] == started["run_id"] and i.get("live", {}).get("child_job")), None))
    assert item["state"] == "running" and item["live"]["step"] == "voice" and item["live"]["of"] == 6 and item["live"]["n"] == 3 and item["live"]["step_label"] == "Giọng đọc"
    items = client.get(P + "/auto/runs").json()["items"]
    assert [i["id"] for i in items][0] == started["run_id"] and len(items) == 2 and items[1]["state"] == "finished"
    finish_run(client, started)


def test_a_run_whose_process_died_is_not_reported_as_running_for_ever(client, world):
    world.build("voiced")
    d = client.root / PID
    log = runlog.RunLog(d, runlog.new_run_id(), pid=PID, until=None, max_steps=3, actor="human", job_id="0123456789abcdef")
    log.start()                                                                 # a record that was never ended, whose job the app does not know
    items = client.get(P + "/auto/runs").json()["items"]
    assert items[0]["state"] == "finished" and items[0]["outcome"] == "cancelled" and "Máy chủ đã dừng" in items[0]["sentence"]


# --------------------------------------------------------------------------------------------------------------- the state answer
def test_the_state_answer_lists_the_run_while_the_switch_is_on_and_marks_its_cost(client, world):
    world.build("narration_approved")
    assert not [a for a in state(client)["next_actions"] if a["id"].startswith("auto.")]
    set_auto(client, enabled=True)
    a = next(x for x in state(client)["next_actions"] if x["id"] == "auto.run")
    assert (a["method"], a["path"], a["ready"], a["needs"], a["advances"], a["gate"], a["long_job"], a["auto_ok"]) == ("POST", P + "/auto/run", True, [], False, False, True, True)
    assert a["body"] == {"until": None, "max_steps": 40} and a["follow"] == "GET /api/longjobs/{job_id}" and a["step"] == state(client)["current"]
    assert a["cost"]["kind"] == "machine_time" and a["cost"]["kinds"] == ["machine_time", "model"]
    assert "voice" in a["cost"]["about"] and "export" in a["cost"]["about"] and "draft" in a["cost"]["about"] and "outline" not in a["cost"]["about"]
    set_auto(client, spend={"machine_time": False})
    a = next(x for x in state(client)["next_actions"] if x["id"] == "auto.run")
    assert a["cost"]["kind"] == "model" and a["cost"]["kinds"] == ["model"] and "voice" not in a["cost"]["about"]               # the sum of what it MAY start
    set_auto(client, spend={"model": False})
    assert next(x for x in state(client)["next_actions"] if x["id"] == "auto.run")["cost"] is None


def test_the_state_answer_while_the_run_goes_on_and_when_the_project_is_exported(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 1.0
    set_auto(client, enabled=True)
    started = start_run(client)
    st = wait_until(lambda: (lambda s: s if any(j["kind"] == "voice" for j in s["jobs"]) else None)(state(client)))
    run = next(a for a in st["next_actions"] if a["id"] == "auto.run")
    assert run["ready"] is False and run["needs"] == ["no_running_job"] and run["advances"] is False
    kinds = {j["kind"] for j in st["jobs"]}
    assert kinds == {"auto", "voice"}
    assert [a["id"] for a in st["next_actions"]].count("auto.cancel") == 1
    assert not [a for a in st["next_actions"] if a["id"].startswith("auto.") and a["advances"]]              # the run is never what advances the project
    finish_run(client, started)


def test_a_project_that_is_exported_has_no_run_to_offer(client, world):
    world.build("exported")
    set_auto(client, enabled=True)
    assert not [a for a in state(client)["next_actions"] if a["id"].startswith("auto.")]
    _, run = run_to_end(client)                                                       # the route itself still answers: the run ends at once, "done"
    assert run["reason"] == "exported" and run["steps"] == []


def test_a_walker_that_takes_the_first_advancing_action_never_takes_the_run(client, world):
    world.build("voiced")
    set_auto(client, enabled=True)
    ready = [a["id"] for a in state(client)["next_actions"] if a["ready"] and a["advances"]]
    assert "auto.run" not in ready


def test_the_job_is_one_job_of_kind_auto_with_progress_and_a_note_the_page_can_read(client, world):
    world.build("picks_approved")
    world.hold["draft"] = 0.5
    set_auto(client, enabled=True)
    started = start_run(client)
    job = wait_until(lambda: (lambda j: j if j["meta"].get("child_job") else None)(client.get("/api/longjobs/%s" % started["job_id"]).json()))
    assert job["kind"] == "auto" and job["state"] in ("running", "waiting")
    meta = job["meta"]
    assert (meta["step"], meta["n"], meta["of"], meta["action"], meta["run_id"]) == ("edit", 5, 6, "draft.start", started["run_id"]) and meta["step_label"] == "Dựng hình"
    assert "Dựng hình (5/6)" in " ".join(p["note"] for p in job["parts"])
    jobs = client.get(P + "/longjobs", params={"kind": "auto"}).json()["items"]
    assert started["job_id"] in [j["id"] for j in jobs] and {j["kind"] for j in jobs} == {"auto"}
    finish_run(client, started)


def test_the_run_goes_through_the_slices_of_the_runner_when_one_slice_is_not_enough(client, world):
    """One part of a long job may last 35 minutes at most: the run is a row of parts, each takes the loop over where the last stopped."""
    world.build("narration_approved")
    world.hold["voice"] = 1.2
    client.app.state.auto_options = {"poll": 0.02, "slice_seconds": 0.3, "max_hours": 0.0019}          # 6.84 s in slices of 0.3 s: 23 parts
    set_auto(client, enabled=True)
    job, run = run_to_end(client)
    parts = job["parts"]
    assert len(parts) == 23 and sum(1 for p in parts if p["state"] == "done") == len(parts)
    assert any("Đã có sẵn" in p["note"] for p in parts) and actions_of(run) == ["voice.generate"] and world.calls.count("voice") == 1        # started once, followed across slices


def test_the_time_limit_ends_the_run_with_its_own_sentence(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 5.0
    client.app.state.auto_options = {"poll": 0.02, "slice_seconds": 0.2, "max_hours": 0.0003}          # about one second in all
    set_auto(client, enabled=True)
    job, run = run_to_end(client)
    assert (run["outcome"], run["reason"]) == ("limit", "time_limit") and "giờ" in run["sentence"]
    from bti.longjob import manager
    for j in state(client)["jobs"]:
        manager.cancel(j["id"])
