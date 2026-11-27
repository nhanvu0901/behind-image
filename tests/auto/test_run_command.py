"""`bti run <project> [--until STEP] [--max-steps N] [--wait] [--yes-cost]`: the command line of the automatic run, against the app with the fake pipeline."""
import json

import pytest

from bti.cli import exitcodes as X, main as cli_main
from cli_helpers import AppTransport, run_bti
from run_helpers import PID, set_auto, state, wait_longjob


def bti(client, *argv, **kw):
    return run_bti(AppTransport(client), *argv, **kw)


@pytest.fixture
def saytwice_fake_writer(monkeypatch):
    # worker saytwice: the synthetic writer repeats filler; these tests exercise later pipeline stages.
    # The three real gate decisions are covered in test_script_checks.py.
    from bti.script import validate, generate
    monkeypatch.setattr(validate, "repetition_issues", lambda *args: [])
    monkeypatch.setattr(generate, "repetition_repairs", lambda *args: {})


def test_the_command_is_listed_with_its_options_and_documented():
    names = [n for n, _, _ in cli_main.COMMANDS]
    assert "run" in names
    usage = next(u for n, u, _ in cli_main.COMMANDS if n == "run")
    assert all(x in usage for x in ("--until STEP", "--wait", "--yes-cost", "--max-steps"))
    from bti.cli import docgen
    assert "`bti run <project>" in docgen.commands_table()
    from bti.editor import pipeline_api
    assert cli_main.RUN_STEPS == tuple(s for s, _ in pipeline_api.STEPS)


def test_it_is_a_person_that_turns_automatic_running_on(client, world):
    world.build("narration_approved")
    r = bti(client, "run", PID, "--yes-cost")
    assert r.code == X.PERSON and "auto_not_enabled" in r.err and "only the owner" in r.err
    assert world.calls == []
    j = bti(client, "run", PID, "--yes-cost", "--json")
    assert j.code == X.PERSON and json.loads(j.out)["code"] == "auto_not_enabled"


def test_a_cost_must_be_confirmed_like_every_cost_of_the_command(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID)
    assert r.code == X.PERSON and "cost_not_confirmed" in r.err and "auto.run costs" in r.err
    assert world.calls == [] and client.get("/api/projects/%s/auto/runs" % PID).json() == {"items": []}


def test_a_run_without_wait_says_how_to_follow_and_stop_it(client, world):
    world.build("narration_approved")
    world.hold["voice"] = 0.3
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost")
    assert r.code == 0 and "started run " in r.out and "bti job " in r.out and "--wait" in r.out and "--cancel" in r.out and "/auto/runs/" in r.out
    jid = next(l for l in r.out.splitlines() if l.startswith("follow it:")).split()[4]
    assert wait_longjob(client, jid)["state"] == "done"


def test_wait_follows_the_run_and_a_finished_project_is_exit_0(client, world):
    world.build("storyboard_approved")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == 0, r
    assert "run " in r.out and "ended: done (exported)" in r.out and "after 1 step(s)" in r.out and "log: GET /api/projects/arn/auto/runs/" in r.out
    assert "job " in r.out                                                          # the progress lines of the job it followed


def test_a_run_that_waits_for_the_owner_is_exit_3_and_says_what_for(client, world, saytwice_fake_writer):
    world.build("new")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == X.PERSON, r
    assert "nothing_to_do" in r.err and "waiting for: main_asset" in r.err and "where: step picks" in r.err and "#/project/arn/picks" in r.err      # the picks step waits first for what the pictures agent needs: a main painting
    assert "action: picks.auto" in r.err and "5 step(s)" in r.err


def test_a_gate_the_owner_did_not_allow_is_exit_3_with_the_gate(client, world):
    world.build("outline_waiting")
    set_auto(client, enabled=True, gates={"narration": False})
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == X.PERSON and "gate_not_allowed" in r.err and "narration gate waits for the owner" in r.err and "fix: Ask the owner" in r.err


def test_a_warning_that_stops_the_run_is_listed(client, world):
    world.build("drafted")
    set_auto(client, enabled=True)
    sb = json.loads((client.root / PID / "storyboard.json").read_text(encoding="utf-8"))
    sb["end"] = {"t": 99999.0}                                                        # the stub engine warns that the video would end after the voice (the real engine's `end_after_audio`)
    (client.root / PID / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == X.PERSON and "quality_warning" in r.err and "warning" in r.err, r


def test_the_step_limit_and_a_cancel_are_exit_5_so_a_caller_can_run_again(client, world):
    world.build("drafted")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0", "--max-steps", "1")
    assert r.code == X.BUSY and "step_limit" in r.err and "1 step(s)" in r.err
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == 0 and "ended: done (exported)" in r.out


def test_a_failed_job_is_mapped_by_its_code_like_any_job(client, world):
    world.build("narration_approved")
    world.fail["voice"] = ("voice_not_configured", "Máy này chưa có giọng đọc.")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == X.REFUSED and "job_failed" in r.err and "voice_not_configured" in r.err                    # retry `no`: 4
    world.fail["voice"] = ("voice_worker_failed", "Máy đọc giọng bị lỗi.")
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0")
    assert r.code == X.BUSY and "voice_worker_failed" in r.err                                                  # retry `later`: 5


def test_json_mode_prints_one_object_with_the_result(client, world):
    world.build("storyboard_approved")
    set_auto(client, enabled=True)
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0", "--json")
    assert r.code == 0
    last = json.loads(r.out.strip().splitlines()[-1])
    assert last["ok"] is True and last["result"]["reason"] == "exported" and last["result"]["outcome"] == "done"
    r = bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0", "--json")                              # exported already: the run is not listed any more
    assert r.code == X.REFUSED and json.loads(r.out)["code"] == "action_not_listed"


def test_until_and_max_steps_are_checked_before_anything_is_sent(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    t = AppTransport(client)
    assert run_bti(t, "run", PID, "--yes-cost", "--until", "lunch").code == X.USAGE
    assert run_bti(t, "run", PID, "--yes-cost", "--max-steps", "0").code == X.USAGE
    assert run_bti(t, "run", PID, "--yes-cost", "--max-steps", "500").code == X.USAGE
    assert not [x for x in t.log if x[0] == "POST"] and world.calls == []
    r = run_bti(t, "run", PID, "--yes-cost", "--until", "voice", "--wait", "--interval", "0")
    assert r.code == 0 and "ended: done (until_reached)" in r.out


def test_the_actor_of_the_run_is_agent_auto_whoever_started_it(client, world):
    world.build("drafted")
    set_auto(client, enabled=True)
    bti(client, "run", PID, "--yes-cost", "--wait", "--interval", "0", "--actor", "claude-code")
    sb = json.loads((client.root / PID / "storyboard.json").read_text(encoding="utf-8"))
    assert sb["approvals"]["storyboard"]["by"] == "agent:auto"
    rec = client.get("/api/projects/%s/auto/runs" % PID).json()["items"][0]
    assert rec["actor"] == "cli:claude-code"                                            # the run log says who started the run


def test_the_state_answer_of_the_run_is_what_bti_status_lists(client, world):
    world.build("narration_approved")
    set_auto(client, enabled=True)
    r = bti(client, "status", PID)
    assert r.code == 0 and "auto.run" in r.out and "Chạy tự động" in r.out
    assert state(client)["current"]
