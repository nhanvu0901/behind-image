"""Each sub-command of `bti`, in text and with `--json`, against the app in the test process (tests/cli/conftest.py has the transports)."""
import json
import threading
import time

import pytest

from cli_helpers import AppTransport, run_bti
from state_helpers import PID, action, build, make_book_project

P = f"/api/projects/{PID}"


@pytest.fixture()
def at(client, monkeypatch):
    """`at(stage)` -> the id of a fresh book project brought to `stage` (the stages of tests/state)."""
    def go(stage="new"):
        make_book_project(client.root)
        return build(stage, client, monkeypatch)
    return go


def set_auto(client, **change):
    rev = client.get(P + "/auto").json()["rev"]
    assert client.put(P + "/auto", json={"base_rev": rev, **change}).status_code == 200


def real_job(outcome, started=None, release=None):
    """A stand-in for the voice starter that starts a REAL long job of the app's runner: it ends the way `outcome` says."""
    from bti.longjob import Part, PartError, manager

    def start(pdir, pid, **k):
        def run(ctx):
            ctx.progress(0.5, "nửa chừng")
            if started is not None:
                started.set()
            if release is not None:
                while not release.is_set() and not ctx.cancelled():
                    time.sleep(0.01)
            if outcome == "ok":
                return {"spoken": 3}
            if outcome == "wait":
                return None
            raise PartError(*outcome)
        return manager.start("voice", pid, pdir, [Part(key="p1", title="Đọc phần 1", run=run)])
    return start


# ------------------------------------------------------------------------------------------------------------------------ status
def test_status_without_a_project_lists_them(bti, at):
    at("new")
    r = bti("status")
    assert r.code == 0 and r.out.startswith("projects") and "arn" in r.out and "selected" in r.out and r.err == ""
    j = bti("--json", "status")
    assert j.code == 0 and [p["id"] for p in j.json] == ["arn"]
    assert bti("status", "--json").json == j.json                              # the option works before and after the sub-command


def test_status_says_where_the_project_stands_and_the_next_command(bti, at):
    at("picks_approved")
    r = bti("status", "arn")
    assert r.code == 0 and r.err == ""
    lines = r.out.splitlines()
    assert lines[0] == "project: arn   stage: picked   current step: edit (Dựng hình)"
    assert lines[1].startswith("automatic running: off") and lines[2].startswith("approvals: outline human; narration human; picks human; storyboard -")
    assert "pipeline: legacy" in lines
    assert "steps:" in lines and any(l.split()[:2] == ["done", "artwork"] for l in lines) and any(l.split()[:2] == ["current", "edit"] for l in lines)
    assert "jobs running: none" in lines and "can do now:" in lines
    assert any(l.strip().startswith("draft.start") and "advances" in l and "costs model (about 20 minutes); needs --yes-cost" in l for l in lines)
    assert lines[-1] == "next: bti do arn draft.start --yes-cost --wait   (Dựng bản nháp)"
    assert all("\x1b" not in l for l in lines)                                   # no colours


def test_status_json_is_the_state_answer_of_the_server(bti, at, client):
    at("picks_approved")
    r = bti("status", "arn", "--json")
    assert r.code == 0 and r.json == client.get(P + "/state").json() and r.json["auto"]["enabled"] is False


@pytest.mark.parametrize("stage, auto, expected", [
    ("new", None, "next: bti do arn outline.generate --yes-cost --wait   (Lập dàn ý)"),
    ("outline_waiting", None, "next: ask the owner to approve outline on the page (Duyệt dàn ý), or to turn automatic running on and allow this gate"),
    ("outline_waiting", {"enabled": True}, "next: bti approve arn outline   (Duyệt dàn ý)"),
    ("narration_approved", None, "next: bti do arn voice.generate --yes-cost --wait   (Tạo giọng đọc)"),
    ("narration_approved", {"spend": {"machine_time": False}}, "next: ask the owner: voice.generate is a machine_time spend that an agent may not confirm"),
])
def test_the_next_line_is_always_one_command_or_one_question_for_the_owner(bti, at, client, stage, auto, expected):
    at(stage)
    if auto:
        set_auto(client, **auto)
    assert bti("status", "arn").out.splitlines()[-1] == expected


def test_status_shows_the_running_job_and_says_to_wait_for_it(bti, at, client):
    from bti.longjob import Part, manager
    at("narration_approved")
    gate = threading.Event()
    job = manager.start("voice", "arn", client.root / "arn", [Part(key="p1", title="x", run=lambda ctx: gate.wait(20) and None)])
    try:
        r = bti("status", "arn")
        assert r.code == 0
        assert any(l.startswith("  %s  voice  " % job["id"]) and l.endswith("follow: bti job %s --wait" % job["id"]) for l in r.out.splitlines()), r.out
        assert r.out.splitlines()[-1].startswith("next: bti job %s --wait" % job["id"]) and "never start a second long job" in r.out
        assert any("voice.generate" in l and "no_running_job" in l for l in r.out.splitlines())          # the second job is not ready
    finally:
        gate.set()
        manager.cancel(job["id"])


def test_status_of_an_unknown_project_and_of_a_wrong_id(bti, at):
    at("new")
    r = bti("status", "nope")
    assert r.code == 4 and r.out == "" and r.err.splitlines()[0] == "refused: project_not_found (HTTP 404)" and "fix: Take the project id" in r.err
    j = bti("status", "nope", "--json")
    assert j.code == 4 and j.err == "" and j.json["ok"] is False and j.json["code"] == "project_not_found" and j.json["status"] == 404
    assert j.json["exit"] == 4 and j.json["exit_name"] == "refused" and j.json["fix"]
    w = bti("status", "../etc")
    assert w.code == 2 and "not a project id" in w.err


# ------------------------------------------------------------------------------------------------------------------------------ do
def test_do_calls_a_ready_action_with_the_body_the_state_gives(bti, at, fakes):
    at("narration_approved")
    r = bti("do", "arn", "picks.search")
    assert r.code == 0 and r.out.splitlines()[0] == "ok: picks.search" and "A picture" in r.out
    assert fakes.search and bti.transport.log[-1][:2] == ("POST", P + "/picks/search")
    assert bti.transport.log[-1][2]["kind"] == "image" and "Arnolfini" in bti.transport.log[-1][2]["query"]
    j = bti("do", "arn", "picks.search", "--json")
    assert j.code == 0 and j.json["items"][0]["source_id"] == "x1"


def test_do_fills_the_callers_fields_with_set_and_with_a_body_file(bti, at, client, tmp_path):
    at("narration_approved")
    r = bti("do", "arn", "picks.import_book_image")
    assert r.code == 2 and "needs content: give source_id" in r.err and "--set source_id=..." in r.err
    assert not any(c[1].endswith("import-book-image") for c in bti.transport.log)                         # nothing was sent
    r = bti("do", "arn", "picks.import", "--set", "source=commons", "--set", "source_id=File:x.jpg", "--set", "as_main=true")
    sent = [c for c in bti.transport.log if c[1] == P + "/picks/import"][0]
    assert sent[2] == {"source": "commons", "source_id": "File:x.jpg", "as_main": True}                    # JSON values stay JSON, None fields are dropped
    f = tmp_path / "body.json"
    f.write_text(json.dumps({"source": "met", "source_id": "7"}), encoding="utf-8")
    bti("do", "arn", "picks.import", "--body", str(f), "--set", "as_main=false")
    sent = [c for c in bti.transport.log if c[1] == P + "/picks/import"][-1]
    assert sent[2] == {"source": "met", "source_id": "7", "as_main": False}
    assert bti("do", "arn", "picks.search", "--set", "novalue").code == 2
    assert bti("do", "arn", "picks.search", "--set", "1x=2").code == 2
    assert bti("do", "arn", "picks.search", "--body", str(tmp_path / "missing.json")).code == 2


def test_do_refuses_an_action_that_is_not_ready_with_its_needs(bti, at):
    at("new")
    r = bti("do", "arn", "narration.generate")
    assert r.code == 4 and r.out == ""
    assert r.err.splitlines()[0] == "refused: not_ready" and "needs outline_approved" in r.err and "needs: outline_approved" in r.err
    assert "Call outline.approve." in r.err                                                                  # the fix of the need, from the app's own table
    assert not any(c[0] == "POST" for c in bti.transport.log)
    j = bti("do", "arn", "narration.generate", "--json").json
    assert j["code"] == "not_ready" and j["needs"] == ["outline_approved"] and j["exit"] == 4 and j["retry"] == "after_fix"


def test_do_an_action_that_waits_only_for_a_running_job_is_busy(bti, at, client):
    from bti.longjob import Part, manager
    at("narration_approved")
    gate = threading.Event()
    job = manager.start("voice", "arn", client.root / "arn", [Part(key="p1", title="x", run=lambda ctx: gate.wait(20) and None)])
    try:
        r = bti("do", "arn", "voice.generate", "--yes-cost")
        assert r.code == 5 and "no_running_job" in r.err
        j = bti("do", "arn", "voice.generate", "--yes-cost", "--json").json
        assert j["exit"] == 5 and j["retry"] == "later" and j["needs"] == ["no_running_job"]
    finally:
        gate.set()
        manager.cancel(job["id"])


def test_do_tells_a_typo_from_an_action_that_is_not_listed_now(bti, at):
    at("new")
    typo = bti("do", "arn", "outline.generat")
    assert typo.code == 2 and typo.err.splitlines()[0] == "usage: unknown_action" and "bti status arn" in typo.err
    locked = bti("do", "arn", "export.start")                       # a real action, but its step is locked
    assert locked.code == 4 and locked.err.splitlines()[0] == "refused: action_not_listed" and "listed: " in locked.err
    j = bti("do", "arn", "export.start", "--json").json
    assert j["code"] == "action_not_listed" and "outline.generate" in j["listed"]


def test_do_a_get_action_takes_no_body(bti, at):
    at("drafted")
    r = bti("do", "arn", "storyboard.validate")
    assert r.code == 0 and r.out.splitlines()[0].startswith("ok: storyboard.validate: ") and "error(s)" in r.out
    assert bti("do", "arn", "storyboard.validate", "--set", "a=1").code == 2


# ----------------------------------------------------------------------------------------------------------------------------- cost
def test_a_cost_runs_only_with_yes_cost(bti, at, fakes):
    at("narration_approved")
    r = bti("do", "arn", "voice.generate")
    assert r.code == 3 and r.out == "" and len(r.err.strip().splitlines()) <= 4
    assert r.err.splitlines()[0] == "a person is needed: cost_not_confirmed"
    assert "voice.generate costs machine_time (about 1 hour)." in r.err and "--yes-cost" in r.err
    assert fakes.voice == []                                                                        # the starter was never reached
    j = bti("do", "arn", "voice.generate", "--json").json
    assert j["exit"] == 3 and j["code"] == "cost_not_confirmed" and j["cost"] == {"kind": "machine_time", "about": "about 1 hour"}
    ok = bti("do", "arn", "voice.generate", "--yes-cost")
    assert ok.code == 0 and "started job fakevoicejob; follow it with: bti job fakevoicejob --wait" in ok.out and len(fakes.voice) == 1


def test_yes_cost_cannot_override_a_spend_the_owner_did_not_allow(bti, at, client, fakes):
    at("narration_approved")
    set_auto(client, spend={"machine_time": False})
    r = bti("do", "arn", "voice.generate", "--yes-cost")
    assert r.code == 3 and r.err.splitlines()[0] == "a person is needed: spend_not_allowed" and "did not allow an agent to spend" in r.err
    assert fakes.voice == [] and not any(c[0] == "POST" for c in bti.transport.log)
    set_auto(client, spend={"machine_time": True})
    assert bti("do", "arn", "voice.generate", "--yes-cost").code == 0 and len(fakes.voice) == 1


def test_money_is_never_spent_by_an_agent(bti, at, client, fakes, tmp_path):
    at("narration_approved")
    set_auto(client, enabled=True)
    for extra in ([], ["--set", "beats=[\"b0001\"]", "--set", "confirm_paid=true"]):
        r = bti("do", "arn", "picks.suggest", "--yes-cost", *extra)
        assert r.code == 3 and r.err.splitlines()[0] == "a person is needed: spend_not_allowed" and "an agent never spends money" in r.err, r
    f = tmp_path / "paid.json"
    f.write_text(json.dumps({"beats": ["b0001"], "confirm_paid": True}), encoding="utf-8")
    assert bti("do", "arn", "picks.suggest", "--yes-cost", "--body", str(f)).code == 3
    assert not any(c[1].endswith("/picks/suggest") for c in bti.transport.log)                       # not even sent
    direct = client.post(P + "/picks/suggest", json={"beats": ["b0001"], "confirm_paid": True, "actor": "cli:bti"})
    assert direct.status_code == 403 and direct.json()["code"] == "spend_needs_human"                    # and the server would refuse it anyway


# ------------------------------------------------------------------------------------------------------------------------- approve
def test_approve_is_refused_to_an_agent_by_default_and_nothing_is_written(bti, at, client):
    at("outline_waiting")
    r = bti("approve", "arn", "outline")
    assert r.code == 3 and r.out == ""
    assert r.err.splitlines()[0] == "a person is needed: gate_needs_human (HTTP 403)" and "owner" in r.err and "automatic running" in r.err
    assert not client.get(P + "/outline").json()["approved"]
    sent = [c for c in bti.transport.log if c[1].endswith("/outline/approve")][0]
    assert sent[2]["actor"] == "cli:bti"                                                                  # the server was asked and the server refused
    j = bti("approve", "arn", "outline", "--json").json
    assert j["exit"] == 3 and j["code"] == "gate_needs_human" and j["gate"] == "outline" and j["reason"] == "auto_off" and j["status"] == 403


def test_approve_goes_through_once_the_owner_allowed_the_gate_and_records_who(bti, at, client):
    at("outline_waiting")
    set_auto(client, enabled=True)
    r = bti("approve", "arn", "outline")
    assert r.code == 0 and r.out == "approved outline as cli:bti\n"
    assert client.get(P + "/outline").json()["outline"]["approval"]["by"] == "cli:bti"
    st = bti("status", "arn", "--json").json
    assert st["approvals"]["outline"]["by"] == "cli:bti"
    again = bti("approve", "arn", "outline")
    assert again.code == 0 and again.out == "outline is already approved by cli:bti (it still stands)\n"


@pytest.mark.parametrize("flag, expected", [("codex", "cli:codex"), ("cli:claude-code", "cli:claude-code"), ("agent:gemini-3.8-flash", "agent:gemini-3.8-flash")])
def test_the_actor_is_what_the_caller_names(bti, at, client, flag, expected):
    at("outline_waiting")
    set_auto(client, enabled=True)
    r = bti("approve", "arn", "outline", "--actor", flag)
    assert r.code == 0 and r.out == "approved outline as %s\n" % expected
    assert client.get(P + "/outline").json()["outline"]["approval"]["by"] == expected


def test_the_default_actor_can_come_from_the_environment(bti, at, client):
    at("outline_waiting")
    set_auto(client, enabled=True)
    assert bti("approve", "arn", "outline", env={"BTI_ACTOR": "gemini"}).out == "approved outline as cli:gemini\n"


@pytest.mark.parametrize("bad", ["human", "robot name", "cli:", "agent:"])
def test_the_command_never_speaks_for_the_owner(bti, at, bad):
    at("outline_waiting")
    r = bti("approve", "arn", "outline", "--actor", bad)
    assert r.code == 2 and r.err.startswith("usage: ") and not any(c[0] == "POST" for c in bti.transport.log)


def test_a_gate_that_is_not_ready_says_who_decides_first(bti, at, client):
    at("new")
    r = bti("approve", "arn", "narration")
    assert r.code == 3 and r.err.splitlines()[0] == "a person is needed: gate_needs_human" and "not ready" in r.err
    set_auto(client, enabled=True)
    r = bti("approve", "arn", "narration")
    assert r.code == 4 and r.err.splitlines()[0] == "refused: not_ready" and "narration" in r.err
    r = bti("approve", "arn", "picks")                                       # the picks step is still locked: not a gate that exists now
    assert r.code == 4 and r.err.splitlines()[0] == "refused: gate_not_available"
    assert bti("approve", "arn", "lunch").code == 2


def test_every_gate_can_be_approved_through_the_command(bti, at, client):
    at("drafted")                                                           # outline, narration and picks are approved by the owner; the storyboard is drafted
    set_auto(client, enabled=True)
    r = bti("approve", "arn", "storyboard")
    assert r.code == 0 and r.out == "approved storyboard as cli:bti\n"
    sb = json.loads((client.root / "arn" / "storyboard.json").read_text(encoding="utf-8"))
    assert sb["approvals"]["storyboard"]["by"] == "cli:bti"
    assert bti("status", "arn", "--json").json["approvals"]["storyboard"]["by"] == "cli:bti"


# ------------------------------------------------------------------------------------------------------------------ --json and exit
def test_every_error_is_one_json_object_of_the_commands_own(bti, at):
    at("new")
    for argv, code, name in ((("status", "nope"), 4, "refused"), (("do", "arn", "narration.generate"), 4, "refused"),
                             (("do", "arn", "zzz"), 2, "usage"), (("approve", "arn", "outline"), 3, "person_needed"),
                             (("do", "arn", "outline.generate"), 3, "person_needed")):
        r = bti(*argv, "--json")
        j = r.json
        assert r.code == code and r.err == "" and set(j) >= {"ok", "exit", "exit_name", "code", "detail"}, (argv, r)
        assert j["ok"] is False and j["exit"] == code and j["exit_name"] == name, (argv, j)


def test_a_typed_wrong_command_is_exit_2_and_prints_the_usage(bti):
    for argv in ((), ("frobnicate",), ("status", "a", "b"), ("do", "arn"), ("ops", "arn", "picks"), ("changes", "arn", "lunch"),
                 ("schema", "ops", "lunch"), ("--timeout", "0", "status"), ("changes", "arn", "--limit", "0")):
        r = bti(*argv)
        assert r.code == 2 and r.out == "" and r.err.startswith("usage: "), (argv, r)
    j = bti("--json", "frobnicate")
    assert j.code == 2 and j.json["code"] == "usage" and j.json["fix"]


# --------------------------------------------------------------------------------------------------------------------------- the job
@pytest.mark.parametrize("outcome, exit_code, last_err", [
    ("ok", 0, None),
    (("voice_worker_failed", "Máy đọc giọng bị dừng giữa chừng."), 5, "voice_worker_failed"),       # retry later: busy
    (("agy_auth", "Chưa đăng nhập agy."), 3, "agy_auth"),                                          # a person is needed
    (("invalid", "Dữ liệu sai."), 4, "invalid"),                                                   # after_fix: refused
])
def test_wait_follows_a_real_long_job_to_its_end(bti, at, monkeypatch, outcome, exit_code, last_err):
    import bti.voice.run as voice_run
    at("narration_approved")
    monkeypatch.setattr(voice_run, "start", real_job(outcome))
    r = bti("do", "arn", "voice.generate", "--yes-cost", "--wait", "--interval", "0")
    assert r.code == exit_code, r
    out = r.out.splitlines()
    assert out[0].startswith("started job ") and any(l.startswith("job ") for l in out[1:])                      # one line per change, the first is the job's own
    if exit_code == 0:
        assert out[-1].startswith("done: ") and '"spoken":3' in out[-1] and r.err == ""
    else:
        assert r.err.splitlines()[0].startswith(("busy: %s" % last_err, "a person is needed: %s" % last_err, "refused: %s" % last_err))
        assert "fix: " in r.err


def test_wait_with_json_prints_the_final_job_and_keeps_stdout_one_object(bti, at, monkeypatch):
    import bti.voice.run as voice_run
    at("narration_approved")
    monkeypatch.setattr(voice_run, "start", real_job("ok"))
    r = bti("do", "arn", "voice.generate", "--yes-cost", "--wait", "--interval", "0", "--json")
    assert r.code == 0 and r.json["state"] == "done" and r.json["result"] == {"spoken": 3} and r.json["kind"] == "voice"
    assert r.err.startswith("started job ") and "job " in r.err                                     # the progress lines are on stderr


def test_job_shows_a_job_and_waits_for_it_and_cancels_it(bti, at, client, monkeypatch):
    import bti.voice.run as voice_run
    at("narration_approved")
    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(voice_run, "start", real_job("wait", started, release))
    jid = bti("do", "arn", "voice.generate", "--yes-cost", "--json").json["job_id"]
    assert started.wait(10)
    seen = bti("job", jid)
    assert seen.code == 0 and seen.out.startswith("job %s: running 50%% - Đọc phần 1 (nửa chừng)" % jid)
    cut = bti("job", jid, "--cancel")
    assert cut.code == 0 and cut.out.startswith("cancel asked for job %s" % jid)
    end = bti("job", jid, "--wait", "--interval", "0")
    assert end.code == 5 and end.err.splitlines()[0] == "busy: cancelled" and "Start the action again" in end.err
    assert bti("job", jid, "--cancel").out == "job %s has already ended: cancelled\n" % jid
    release.set()
    j = bti("job", jid, "--json")
    assert j.code == 0 and j.json["state"] == "cancelled"


def test_job_finished_prints_how_it_ended(bti, at, monkeypatch):
    import bti.voice.run as voice_run
    at("narration_approved")
    monkeypatch.setattr(voice_run, "start", real_job("ok"))
    jid = bti("do", "arn", "voice.generate", "--yes-cost", "--json").json["job_id"]
    bti("job", jid, "--wait", "--interval", "0")
    r = bti("job", jid)
    assert r.code == 0 and r.out.splitlines()[0] == "job %s: done 100%%" % jid and r.out.splitlines()[1].startswith("done: ")


def test_job_unknown_and_wrong_ids(bti, at):
    at("new")
    r = bti("job", "0123456789abcdef")
    assert r.code == 4 and r.err.splitlines()[0].startswith("refused: job_not_found")
    assert bti("job", "bad id!").code == 2


def test_max_wait_stops_watching_with_busy(bti, at, monkeypatch):
    import bti.voice.run as voice_run
    at("narration_approved")
    release = threading.Event()
    monkeypatch.setattr(voice_run, "start", real_job("wait", None, release))
    now = [0.0]

    def tick(s):
        now[0] += 30
    try:
        r = bti("do", "arn", "voice.generate", "--yes-cost", "--wait", "--max-wait", "60", sleep=tick, clock=lambda: now[0])
        assert r.code == 5 and r.err.splitlines()[0] == "busy: still_running" and "bti job " in r.err
    finally:
        release.set()


# ---------------------------------------------------------------------------------------------------------------------- the other jobs
def test_a_script_job_and_a_preview_follow_the_same_way(at):
    from bti.cli.transport import Reply
    from cli_helpers import Scripted
    script = [Reply(200, {"id": "a1", "kind": "outline", "state": "queued", "progress": 0.0, "chapters": [], "message": ""}),
              Reply(200, {"id": "a1", "kind": "narration", "state": "running", "progress": 0.33, "chapters": [{"id": "c01", "state": "running"}], "message": ""}),
              Reply(200, {"id": "a1", "kind": "narration", "state": "error", "progress": 0.33, "chapters": [], "message": "", "error": "x", "error_kind": "rate_limit"})]
    t = Scripted({("GET", "/api/longjobs/a1"): Reply(404, {"detail": "n", "code": "longjob_not_found", "retry": "no", "fix": "f"}), ("GET", "/api/jobs/a1"): script})
    r = run_bti(t, "job", "a1", "--wait", "--interval", "0")
    assert r.code == 5 and "job a1: queued 0%" in r.out and "job a1: running 33% - chapter c01 running" in r.out
    assert r.err.splitlines()[0] == "busy: rate_limit"                                                  # error_kind rate_limit: a quota opens later
    pv = Scripted({("GET", "/api/longjobs/p1"): Reply(404, {"detail": "n", "code": "longjob_not_found", "retry": "no", "fix": "f"}),
                   ("GET", "/api/jobs/p1"): [Reply(200, {"state": "running", "progress": 0.5, "result_url": None, "error": None}),
                                             Reply(200, {"state": "done", "progress": 1.0, "result_url": "/api/x.mp4", "error": None})]})
    r = run_bti(pv, "job", "p1", "--wait", "--interval", "0")
    assert r.code == 0 and r.out.splitlines()[0] == "job p1: running 50%" and r.out.splitlines()[-1].startswith("done")


# --------------------------------------------------------------------------------------------------------------------------- ops, undo
@pytest.fixture()
def ops_app(root, make_client):
    pytest.importorskip("bti.engine.api")
    from bti.engine import api as engine_api
    from ops_helpers import PID as OPS_PID, make_project
    make_project(root)
    return make_client(engine_module=engine_api), OPS_PID


def write_ops(tmp_path, data, name="ops.json"):
    f = tmp_path / name
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f)


def test_ops_dry_run_prints_the_changes_and_writes_nothing(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    before = (c.root / pid / "storyboard.json").read_bytes()
    f = write_ops(tmp_path, [{"op": "lock", "shot": "s0003"}])
    r = run_bti(t, "ops", pid, "storyboard", "--file", f, "--dry-run")
    assert r.code == 0, r
    assert r.out.splitlines()[0].startswith("dry run: nothing was written; 1 operation(s) applied; revision ") and "changes:" in r.out
    assert any("s0003" in l or "Cảnh 3" in l for l in r.out.splitlines()[2:])
    assert (c.root / pid / "storyboard.json").read_bytes() == before
    body = [x for x in t.log if x[1].endswith("/storyboard/ops")][0][2]
    assert body["dry_run"] is True and body["actor"] == "cli:bti" and body["base_rev"] == c.get("/api/projects/%s" % pid).json()["rev"]


def test_ops_writes_a_batch_and_undo_takes_it_back(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    f = write_ops(tmp_path, {"ops": [{"op": "lock", "shot": "s0003"}], "note": "owner asked"})
    r = run_bti(t, "ops", pid, "storyboard", "--file", f, "--note", "from the flag")
    assert r.code == 0 and r.out.splitlines()[0].startswith("batch batch_0001 written; 1 operation(s) applied") and "undo: bti undo <project> batch_0001" in r.out
    assert next(s for s in json.loads((c.root / pid / "storyboard.json").read_text(encoding="utf-8"))["shots"] if s["id"] == "s0003")["locked"] is True
    log = run_bti(t, "changes", pid)
    assert log.code == 0 and log.out.splitlines()[0].startswith("batch ") and log.out.splitlines()[1].split()[:3] == ["batch_0001", "storyboard", "cli:bti"] and "from the flag" in log.out
    only = run_bti(t, "changes", pid, "picks")
    assert only.out == "no changes in the log\n"
    j = run_bti(t, "changes", pid, "storyboard", "--json")
    assert j.json["changes"][0]["batch"] == "batch_0001" and j.json["changes"][0]["actor"] == "cli:bti"
    u = run_bti(t, "undo", pid, "batch_0001", "--note", "changed my mind")
    assert u.code == 0 and u.out.splitlines()[0].startswith("undone batch_0001; the undo is batch batch_0002; revision ")
    assert next(s for s in json.loads((c.root / pid / "storyboard.json").read_text(encoding="utf-8"))["shots"] if s["id"] == "s0003")["locked"] is False
    assert run_bti(t, "changes", pid).out.count("(undone)") == 1
    gone = run_bti(t, "undo", pid, "batch_0099")
    assert gone.code == 4 and gone.err.splitlines()[0] == "refused: batch_not_found"
    assert run_bti(t, "undo", pid, "nonsense").code == 2
    again = run_bti(t, "undo", pid, "batch_0001")
    assert again.code == 4 and again.err.splitlines()[0].startswith("refused: undo_conflict")


def test_ops_picks_batches_go_to_the_picks(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    r = run_bti(t, "ops", pid, "picks", "--file", write_ops(tmp_path, [{"op": "skip_beat", "beat": "b0004"}]))
    assert r.code == 0 and r.out.splitlines()[0].startswith("batch batch_0001 written"), r
    assert [x for x in t.log if x[1].endswith("/picks/ops")][0][2]["base_rev"]
    assert json.loads((c.root / pid / "picks.json").read_text(encoding="utf-8"))["beats"]["b0004"]["status"] == "skip"


def test_ops_refused_is_exit_4_with_the_field_and_the_fix(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    before = (c.root / pid / "storyboard.json").read_bytes()
    r = run_bti(t, "ops", pid, "storyboard", "--file", write_ops(tmp_path, [{"op": "lock", "shot": "s9999"}]))
    assert r.code == 4 and r.out == ""
    assert r.err.splitlines()[0] == "refused: unknown_shot (HTTP 422)"
    assert "fix: Use a shot id from allowed" in r.err and "field ops[0].shot:" in r.err and "(allowed: s0001" in r.err
    assert (c.root / pid / "storyboard.json").read_bytes() == before
    j = run_bti(t, "ops", pid, "storyboard", "--file", write_ops(tmp_path, [{"op": "lock", "shot": "s9999"}]), "--json").json
    assert j["exit"] == 4 and j["code"] == "unknown_shot" and j["fields"][0]["path"] == "ops[0].shot" and "s0001" in j["fields"][0]["allowed"]


def test_ops_on_a_stale_revision_is_exit_5(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    rev_of = lambda: c.get("/api/projects/%s" % pid).json()["rev"]                          # noqa: E731
    f = write_ops(tmp_path, [{"op": "lock", "shot": "s0003"}])

    def someone_else():                                                                       # a save of the page between the command's two requests
        r = c.post("/api/projects/%s/storyboard/ops" % pid, json={"base_rev": rev_of(), "actor": "human", "ops": [{"op": "lock", "shot": "s0004"}]})
        assert r.status_code == 200, r.text
    t.after("/state", someone_else)
    r = run_bti(t, "ops", pid, "storyboard", "--file", f)
    assert r.code == 5 and r.err.splitlines()[0] == "busy: stale_revision (HTTP 409)" and "current_rev: " in r.err
    assert "base_rev set to it" in r.err                                                       # the fix says how to start again
    again = run_bti(t, "ops", pid, "storyboard", "--file", f)
    assert again.code == 0


def test_ops_file_mistakes_are_exit_2_before_anything_is_sent(ops_app, tmp_path):
    c, pid = ops_app
    t = AppTransport(c)
    for data in ({"things": []}, "text", {"ops": [], "colour": 1}):
        assert run_bti(t, "ops", pid, "storyboard", "--file", write_ops(tmp_path, data)).code == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert run_bti(t, "ops", pid, "storyboard", "--file", str(bad)).code == 2
    assert run_bti(t, "ops", pid, "storyboard", "--file", str(tmp_path / "none.json")).code == 2
    assert t.log == []


def test_ops_on_a_project_whose_step_is_locked_is_refused(bti, at, tmp_path):
    at("new")
    r = bti("ops", "arn", "storyboard", "--file", write_ops(tmp_path, [{"op": "lock", "shot": "s1"}]))
    assert r.code == 4 and r.err.splitlines()[0] == "refused: action_not_listed"


# --------------------------------------------------------------------------------------------------------------------------- schema
def test_schema_prints_the_operations_of_a_document(bti):
    r = bti("schema", "ops", "picks")
    assert r.code == 0 and r.out.splitlines()[0] == "operations of the picks (send them with: bti ops <project> picks --file ops.json):"
    assert "  set_main: " in r.out and "    required: asset" in r.out and '    example: {"op":"set_main","asset":"B"}' in r.out
    s = bti("schema", "ops", "storyboard")
    assert "  split_shot: " in s.out and "  lock: " in s.out
    j = bti("schema", "ops", "storyboard", "--json").json
    assert "set_params" in j and set(j["lock"]) == {"summary", "schema", "example"}
    from bti.ops import registry
    assert list(j) == list(registry.defs("storyboard"))


# -------------------------------------------------------------------------------------------------------------------------------- doc
def test_doc_prints_the_skill_document_of_a_step(bti):
    from bti.cli.main import REPO
    r = bti("doc", "script")
    assert r.code == 0 and r.out == (REPO / "skills" / "script" / "SKILL.md").read_text(encoding="utf-8").rstrip("\n") + "\n"
    assert bti("doc", "edit").out == bti("doc", "storyboard").out                         # the page's step id works too
    assert bti("doc").out == (REPO / "AGENTS.md").read_text(encoding="utf-8").rstrip("\n") + "\n"
    j = bti("doc", "voice", "--json").json
    assert j["step"] == "voice" and j["path"] == "skills/voice/SKILL.md" and j["text"].startswith("---\nname: bti-voice")
    assert bti("doc", "lunch").code == 2


# -------------------------------------------------------------------------------------------------------------------- the app is away
def test_the_app_cannot_be_reached_is_exit_6(tmp_path):
    from bti.cli.transport import Unreachable
    from cli_helpers import Scripted
    t = Scripted({("GET", "/api/projects/arn/state"): Unreachable("Connection refused"), ("GET", "/api/projects"): Unreachable("timed out")})
    r = run_bti(t, "status", "arn")
    assert r.code == 6 and r.out == "" and r.err.splitlines()[0] == "cannot reach the app: unreachable" and "Connection refused" in r.err and "BTI_URL" in r.err
    j = run_bti(t, "status", "--json")
    assert j.code == 6 and j.json["code"] == "unreachable" and j.json["exit"] == 6 and j.json["exit_name"] == "unreachable"


def test_an_answer_that_is_not_the_apps_is_exit_6(tmp_path):
    from bti.cli.transport import Reply
    from cli_helpers import Scripted
    t = Scripted({("GET", "/api/projects/arn/state"): Reply(200, None, "<html>hello</html>"), ("GET", "/api/projects"): Reply(502, None, "Bad gateway")})
    r = run_bti(t, "status", "arn")
    assert r.code == 6 and r.err.splitlines()[0] == "cannot reach the app: not_the_app (HTTP 200)"
    assert run_bti(t, "status").code == 6
    odd = Scripted({("GET", "/api/projects/arn/state"): Reply(200, {"hello": 1})})
    assert run_bti(odd, "status", "arn").code == 6


def test_finished_voice_assembly_job_shows_detail_and_specific_fix(bti, at, monkeypatch):
    import bti.voice.run as voice_run
    at('narration_approved')
    reason='true peak measurements -1.26, -1.24 dBTP exceed limit -1.50'
    monkeypatch.setattr(voice_run, 'start', real_job(('voice_assemble_failed', reason)))
    jid=bti('do','arn','voice.generate','--yes-cost','--json').json['job_id']
    bti('job',jid,'--wait','--interval','0')
    plain=bti('job',jid)
    assert reason in plain.out and 'limiter' in plain.out
    js=bti('job',jid,'--json').json
    assert reason in js['error'] and 'limiter' in js['fix']
