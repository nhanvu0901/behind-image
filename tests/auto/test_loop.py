"""The loop of the automatic run on made-up answers (no app, no jobs): the rule, each stop reason, the quality bar before a gate, the job that is followed, the
cancel, the step limit, the run log. The loop never knows the steps of the pipeline: it takes the first action of the answer that is ready, advances and is
allowed."""
import json

import pytest

from bti.auto_run import checks, loop, reasons, runlog
from bti.cli.transport import Reply, Unreachable
from auto_helpers import Scripted, act, made_state

PID = "arn"
ALL = {"enabled": True, "gates": {g: True for g in reasons.GATES}, "spend": {"model": True, "machine_time": True, "paid": False}}


def auto(**over):
    d = json.loads(json.dumps(ALL))
    for k, v in over.items():
        if isinstance(v, dict):
            d[k].update(v)
        else:
            d[k] = v
    return d


DOC = {"outline": "/api/projects/arn/outline", "narration": "/api/projects/arn/narration", "picks": "/api/projects/arn/picks", "storyboard": "/api/projects/arn"}
APPROVE = {"outline": "outline.approve", "narration": "narration.approve", "picks": "picks.approve", "storyboard": "storyboard.approve"}
STEP = {"outline": "script", "narration": "script", "picks": "picks", "storyboard": "edit"}


def exported():
    return made_state([], done=("artwork", "script", "voice", "picks", "edit", "export"), current="export")


class Clock:
    """A clock that only moves when the loop sleeps, so a poll of two seconds costs no real time."""

    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def sleep(self, seconds):
        self.t += max(seconds, 0.001)


def make_run(tmp_path, transport, *, until=None, max_steps=40, poll=0.0, cancelled=None):
    d = tmp_path / PID
    d.mkdir(exist_ok=True)
    clock = Clock()
    log = runlog.RunLog(d, runlog.new_run_id(), pid=PID, until=until, max_steps=max_steps, actor="human")
    r = loop.Run(transport, PID, run_id=log.rec["id"], log_=log, until=until, max_steps=max_steps, poll=poll, sleep=clock.sleep, clock=clock)
    if cancelled is not None:
        r.cancelled = cancelled
    return r, log


def run_loop(tmp_path, transport, *, until=None, max_steps=40, cancelled=None, deadline=1e6, poll=0.0):
    r, log = make_run(tmp_path, transport, until=until, max_steps=max_steps, poll=poll, cancelled=cancelled)
    res = r.advance(r.clock() + deadline)
    return res, r, log


def posts(t):
    return [(p, b) for m, p, b in t.log if m == "POST"]


# ------------------------------------------------------------------------------------------------------------------------ the rule
def test_takes_the_first_action_that_is_ready_and_advances_and_ends_when_exported(tmp_path):
    first = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"}, body={"scope": "all"})
    other = act("picks.approve", "picks", gate=True)
    t = Scripted(PID, [made_state([first, other]), exported()], posts={first["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t)
    assert res["outcome"] == "done" and res["reason"] == "exported" and res["steps_taken"] == 1
    assert [p for p, _ in posts(t)] == [first["path"]]                   # the FIRST ready advancing action of the answer, not the one that comes later
    assert posts(t)[0][1] == {"scope": "all"}                            # exactly the body the answer gives (no actor: this route takes none)


def test_it_skips_what_is_not_ready_or_does_not_advance_and_never_takes_a_cancel_or_the_run_itself(tmp_path):
    acts = [act("storyboard.ops", "edit", advances=False), act("draft.start", "edit", ready=False, needs=["agent_usable"]),
            act("auto.run", "export"), act("voice.cancel", "voice"), act("export.start", "export", long_job=True)]
    t = Scripted(PID, [made_state(acts), exported()], posts={acts[-1]["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t)
    assert [p for p, _ in posts(t)] == [acts[-1]["path"]]
    assert res["outcome"] == "done"


def test_a_gate_is_sent_as_the_actor_agent_auto_with_the_body_of_the_answer(tmp_path):
    gate = act("outline.approve", "script", gate=True, body={"rev": "r1"})
    t = Scripted(PID, [made_state([gate]), exported()], docs={"/api/projects/arn/outline": {"issues": []}}, posts={gate["path"]: Reply(200, {"ok": True})})
    run_loop(tmp_path, t)
    assert posts(t) == [(gate["path"], {"rev": "r1", "actor": "agent:auto"})]
    assert loop.ACTOR == "agent:auto"


def test_the_actor_of_the_run_is_a_form_the_gate_rule_takes():
    from bti import auto
    assert auto.ACTOR_RE.match(loop.ACTOR)


def test_until_a_step_that_is_done_ends_at_once_without_a_call(tmp_path):
    t = Scripted(PID, [made_state([act("voice.generate", "voice")], done=("artwork", "script", "voice"))])
    res, _, _ = run_loop(tmp_path, t, until="voice")
    assert res["reason"] == "until_reached" and res["outcome"] == "done" and res["step"] == "voice" and posts(t) == []


def test_it_follows_the_steps_until_the_one_asked_for_and_not_further(tmp_path):
    a = act("outline.approve", "script", gate=True, body={"rev": "r"})
    t = Scripted(PID, [made_state([a]), made_state([act("voice.generate", "voice")], done=("artwork", "script"), current="voice")],
                 docs={"/api/projects/arn/outline": {"issues": []}}, posts={a["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t, until="script")
    assert res["reason"] == "until_reached" and [p for p, _ in posts(t)] == [a["path"]]


# ------------------------------------------------------------------------------------------------------- stops that need the owner
def test_a_gate_the_owner_did_not_allow_stops_there_and_nothing_is_sent(tmp_path):
    gate = act("narration.approve", "script", gate=True, auto_ok=False, body={"rev": "r"})
    t = Scripted(PID, [made_state([gate], auto=auto(gates={"narration": False}))])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["gate"], res["step"]) == ("needs_owner", "gate_not_allowed", "narration", "script")
    assert posts(t) == [] and not any(p.endswith("/narration") for p in t.paths("GET"))          # not even its document was read
    assert "lời dẫn" in res["sentence"] and "Kịch bản" in res["sentence"] and res["link"] == "#/project/arn/script"


def test_a_gate_whose_auto_ok_says_no_stops_even_when_the_settings_say_yes(tmp_path):
    gate = act("picks.approve", "picks", gate=True, auto_ok=False, body={"rev": "r"})
    t = Scripted(PID, [made_state([gate])])
    assert run_loop(tmp_path, t)[0]["reason"] == "gate_not_allowed" and posts(t) == []


def test_automatic_running_turned_off_in_the_middle_stops_the_run(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"})
    t = Scripted(PID, [made_state([a], auto=auto(enabled=False))])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"]) == ("needs_owner", "auto_turned_off") and posts(t) == []


@pytest.mark.parametrize("kind", ["model", "machine_time"])
def test_a_kind_of_cost_the_owner_did_not_allow_stops_before_the_action(tmp_path, kind):
    a = act("draft.start", "edit", cost={"kind": kind, "about": "x"}, auto_ok=False)
    t = Scripted(PID, [made_state([a], auto=auto(spend={kind: False}))])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["kind"], res["action"]) == ("needs_owner", "spend_not_allowed", kind, "draft.start")
    assert posts(t) == []


def test_the_settings_are_checked_too_when_the_action_says_it_is_fine(tmp_path):
    a = act("draft.start", "edit", cost={"kind": "model", "about": "x"}, auto_ok=True)
    t = Scripted(PID, [made_state([a], auto=auto(spend={"model": False}))])
    assert run_loop(tmp_path, t)[0]["reason"] == "spend_not_allowed" and posts(t) == []


@pytest.mark.parametrize("auto_ok", [True, False])
def test_a_paid_action_is_never_taken(tmp_path, auto_ok):
    a = act("picks.suggest", "picks", cost={"kind": "paid", "about": "x"}, auto_ok=auto_ok, long_job=True)
    t = Scripted(PID, [made_state([a])])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["kind"]) == ("needs_owner", "paid_needs_owner", "paid") and posts(t) == []


def test_restoring_a_damaged_storyboard_is_the_owners_decision(tmp_path):
    a = act("storyboard.restore", "edit", body={})
    t = Scripted(PID, [made_state([a], current="edit")])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"]) == ("needs_owner", "repair_needed") and posts(t) == []


# -------------------------------------------------------------------------------------------------------------- nothing to do and busy
def test_nothing_to_do_says_what_the_project_waits_for(tmp_path):
    acts = [act("picks.suggest", "picks", cost={"kind": "paid", "about": "x"}, needs=["suggest_enabled"]), act("picks.approve", "picks", gate=True, needs=["main_asset"]),
            act("picks.import", "picks", advances=False, fill=["source", "source_id"], body=None)]
    t = Scripted(PID, [made_state(acts, done=("artwork", "script", "voice"), current="picks")])
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["waiting_for"], res["step"], res["action"]) == ("nothing_to_do", "nothing_to_do", ["main_asset"], "picks", "picks.approve")
    assert "tranh chính" in res["sentence"] and "Chọn hình" in res["sentence"]
    assert posts(t) == []


def test_an_unusable_agent_is_named_with_its_own_reason(tmp_path):
    a = act("draft.start", "edit", needs=["agent_usable"], agent={"id": "gem", "label": "Gemini", "usable": False, "reason": "Chưa đăng nhập."})
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a], current="edit")]))
    assert res["reason"] == "nothing_to_do" and "Chưa đăng nhập" in res["sentence"] and res["waiting_for"] == ["agent_usable"]


def test_with_nothing_listed_the_sentence_of_the_step_is_used(tmp_path):
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([], current="picks")]))
    assert res["reason"] == "nothing_to_do" and "d-picks" in res["sentence"]


def test_a_job_that_is_not_ours_stops_the_run_but_a_preview_does_not(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"})
    other = [{"id": "j9", "kind": "export", "state": "running"}]
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a], jobs=other)]))
    assert (res["outcome"], res["reason"]) == ("nothing_to_do", "busy_elsewhere") and "xuất video" in res["sentence"]
    prev = [{"id": "p1", "kind": "preview", "state": "running"}, {"id": "a1", "kind": "auto", "state": "running"}]
    t = Scripted(PID, [made_state([a], jobs=prev), exported()], posts={a["path"]: Reply(200, {})})
    assert run_loop(tmp_path, t)[0]["reason"] == "exported" and len(posts(t)) == 1


def test_an_action_that_needs_content_from_a_person_stops_without_being_called(tmp_path):
    a = act("picks.auto", "picks", fill=["beats"], body=None)
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a], current="picks")]))
    assert res["reason"] == "needs_content" and res["action"] == "picks.auto"


# ------------------------------------------------------------------------------------------------------------------------ limits
def test_the_step_limit_ends_the_run_with_a_sentence_and_no_extra_call(tmp_path):
    acts = [[act("proposal.apply", "edit", body={"n": i})] for i in range(5)]
    t = Scripted(PID, [made_state(a) for a in acts], posts={acts[0][0]["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t, max_steps=2)
    assert (res["outcome"], res["reason"], res["steps_taken"]) == ("limit", "step_limit", 2) and len(posts(t)) == 2 and "2 việc" in res["sentence"]


def test_a_project_that_is_done_wins_over_the_limit(tmp_path):
    a = act("export.start", "export", cost={"kind": "machine_time", "about": "x"})
    t = Scripted(PID, [made_state([a]), exported()], posts={a["path"]: Reply(200, {})})
    assert run_loop(tmp_path, t, max_steps=1)[0]["reason"] == "exported"


def test_the_same_call_three_times_in_a_row_without_the_state_moving_is_stopped(tmp_path):
    a = act("proposal.apply", "edit", body={"accept": "all"})
    t = Scripted(PID, [made_state([a])], posts={a["path"]: Reply(200, {})})
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"]) == ("failed", "no_progress") and len(posts(t)) == 2


# ---------------------------------------------------------------------------------------------------------- a call that is refused
def test_a_failing_action_stops_the_run_with_its_code_and_what_the_server_said(tmp_path):
    a = act("voice.generate", "voice", label="Tạo giọng đọc", cost={"kind": "machine_time", "about": "x"})
    err = Reply(422, {"detail": "the voice worker is not configured", "code": "voice_not_configured", "fix": "x", "retry": "no"})
    res, _, log = run_loop(tmp_path, Scripted(PID, [made_state([a])], posts={a["path"]: err}))
    assert (res["outcome"], res["reason"], res["action"]) == ("failed", "action_failed", "voice.generate")
    assert res["error"]["code"] == "voice_not_configured" and res["error"]["status"] == 422 and "Tạo giọng đọc" in res["sentence"]
    assert log.rec["steps"][0]["ok"] is False and log.rec["steps"][0]["code"] == "voice_not_configured"


@pytest.mark.parametrize("code", sorted(reasons.REFUSAL_CODES))
def test_a_gate_that_the_server_refuses_for_its_document_is_for_the_owner(tmp_path, code):
    gate = gate_action("storyboard")
    t = Scripted(PID, [made_state([gate], current="edit")], docs={"/api/projects/arn": {"issues": []}},
                 posts={gate["path"]: Reply(422, {"detail": "x", "code": code, "issues": [{"level": "error"}]})})
    res, _, _ = run_loop(tmp_path, t)
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "gate_refused", "storyboard") and res["error"]["code"] == code


def test_the_server_refusing_the_actor_is_read_as_the_owners_rule(tmp_path):
    gate = act("outline.approve", "script", gate=True, body={"rev": "r"})
    docs = {"/api/projects/arn/outline": {"issues": []}}
    off = Scripted(PID, [made_state([gate])], docs=docs, posts={gate["path"]: Reply(403, {"detail": "x", "code": "gate_needs_human", "reason": "auto_off"})})
    assert run_loop(tmp_path, off)[0]["reason"] == "auto_turned_off"
    no = Scripted(PID, [made_state([gate])], docs=docs, posts={gate["path"]: Reply(403, {"detail": "x", "code": "gate_needs_human", "reason": "gate_not_allowed"})})
    assert run_loop(tmp_path, no)[0]["reason"] == "gate_not_allowed"
    paid = Scripted(PID, [made_state([act("outline.generate", "script", cost={"kind": "model", "about": "x"})])],
                    posts={"/api/projects/arn/outline/generate": Reply(403, {"detail": "x", "code": "spend_needs_human"})})
    assert run_loop(tmp_path, paid)[0]["reason"] == "paid_needs_owner"


def test_a_stale_revision_is_read_again_and_the_call_made_again(tmp_path):
    g1 = act("outline.approve", "script", gate=True, body={"rev": "old"})
    g2 = act("outline.approve", "script", gate=True, body={"rev": "new"})
    t = Scripted(PID, [made_state([g1]), made_state([g2]), exported()], docs={"/api/projects/arn/outline": {"issues": []}},
                 posts={g1["path"]: [Reply(409, {"detail": "x", "code": "stale", "current_rev": "new"}), Reply(200, {})]})
    res, _, _ = run_loop(tmp_path, t)
    assert res["reason"] == "exported" and [b["rev"] for _, b in posts(t)] == ["old", "new"] and res["steps_taken"] == 2


def test_a_job_started_elsewhere_that_blocks_the_call_is_not_a_failure(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"})
    t = Scripted(PID, [made_state([a])], posts={a["path"]: Reply(409, {"detail": "busy", "code": "voice_busy", "retry": "later"})})
    assert run_loop(tmp_path, t)[0]["reason"] == "busy_elsewhere"


def test_the_app_not_answering_ends_the_run_as_failed(tmp_path):
    class Dead(Scripted):
        def request(self, *a, **k):
            raise Unreachable("connection refused")
    res, _, _ = run_loop(tmp_path, Dead(PID, [made_state([])]))
    assert (res["outcome"], res["reason"]) == ("failed", "unreachable") and "connection refused" in res["sentence"]


def test_an_unexpected_bug_ends_the_run_with_a_reason_and_a_log(tmp_path, monkeypatch):
    def broken(self, st):
        raise KeyError("a bug")
    monkeypatch.setattr(loop.Run, "_decide", broken)
    res, _, log = run_loop(tmp_path, Scripted(PID, [made_state([])]))
    assert (res["outcome"], res["reason"]) == ("failed", "internal_error") and "KeyError" in res["detail"] and log.rec["ended"] and log.rec["outcome"] == "failed"


# -------------------------------------------------------------------------------------------------------------------- the job it follows
def job_path(jid="j1", kind="longjobs"):
    return "/api/%s/%s" % (kind, jid)


def test_it_follows_the_job_to_its_end_before_it_reads_the_state_again(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    jobs = {job_path(): [{"state": "running", "progress": 0.2}, {"state": "running", "progress": 0.8}, {"state": "done", "progress": 1.0}]}
    t = Scripted(PID, [made_state([a]), exported()], jobs=jobs, posts={a["path"]: Reply(200, {"job_id": "j1"})})
    res, run, log = run_loop(tmp_path, t)
    assert res["reason"] == "exported" and t.paths("GET").count(job_path()) == 3
    order = [(m, p) for m, p, _ in t.log]
    assert order.index(("GET", job_path())) > order.index(("POST", a["path"]))
    assert log.rec["steps"][0]["job_id"] == "j1" and log.rec["steps"][0]["job_state"] == "done" and log.rec["steps"][0]["seconds"] is not None


def test_a_script_job_is_followed_where_the_answer_says(tmp_path):
    a = act("outline.generate", "script", cost={"kind": "model", "about": "x"}, long_job=True)
    a["follow"] = "GET /api/jobs/{job_id}"
    t = Scripted(PID, [made_state([a]), exported()], jobs={job_path("s1", "jobs"): [{"state": "running"}, {"state": "done"}]}, posts={a["path"]: Reply(200, {"job_id": "s1"})})
    assert run_loop(tmp_path, t)[0]["reason"] == "exported" and job_path("s1", "jobs") in t.paths("GET")


def test_a_failed_job_ends_the_run_with_the_code_and_the_sentence_of_the_job(tmp_path):
    a = act("voice.generate", "voice", label="Tạo giọng đọc", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    jobs = {job_path(): [{"state": "running"}, {"state": "error", "error_code": "voice_worker_failed", "error": "Máy đọc giọng bị lỗi."}]}
    res, _, log = run_loop(tmp_path, Scripted(PID, [made_state([a])], jobs=jobs, posts={a["path"]: Reply(200, {"job_id": "j1"})}))
    assert (res["outcome"], res["reason"]) == ("failed", "job_failed") and res["error"]["code"] == "voice_worker_failed"
    assert "Máy đọc giọng bị lỗi" in res["sentence"] and log.rec["steps"][0]["job_state"] == "error"


def test_a_script_job_failure_is_read_by_its_error_kind(tmp_path):
    a = act("narration.generate", "script", cost={"kind": "model", "about": "x"}, long_job=True)
    a["follow"] = "GET /api/jobs/{job_id}"
    jobs = {job_path("s1", "jobs"): [{"state": "error", "error_kind": "rate_limit", "error": "The quota is used up."}]}
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a])], jobs=jobs, posts={a["path"]: Reply(200, {"job_id": "s1"})}))
    assert res["error"]["code"] == "rate_limit" and res["reason"] == "job_failed"


def test_a_job_stopped_somewhere_else_ends_the_run_as_cancelled(tmp_path):
    a = act("export.start", "export", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a])], jobs={job_path(): [{"state": "cancelled"}]}, posts={a["path"]: Reply(200, {"job_id": "j1"})}))
    assert (res["outcome"], res["reason"]) == ("cancelled", "job_cancelled_elsewhere")


def test_a_job_the_app_does_not_know_ends_the_run_as_failed(tmp_path):
    a = act("export.start", "export", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([a])], posts={a["path"]: Reply(200, {"job_id": "nope"})}))
    assert res["reason"] == "job_failed" and res["error"]["code"] == "route_not_found"


def test_cancelling_the_run_stops_the_job_it_started_and_says_so(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    t = Scripted(PID, [made_state([a])], jobs={job_path(): [{"state": "running", "progress": 0.1}]}, posts={a["path"]: Reply(200, {"job_id": "j1"})})
    seen = {"n": 0}

    def cancelled():
        seen["n"] += 1
        return seen["n"] > 6
    res, _, log = run_loop(tmp_path, t, cancelled=cancelled)
    assert (res["outcome"], res["reason"]) == ("cancelled", "cancelled")
    assert ("POST", job_path() + "/cancel", None) in t.log                       # the job the run started is asked to stop
    assert log.rec["steps"][0]["job_state"] == "cancelled"


def test_the_loop_gives_the_deadline_back_and_goes_on_where_it_was(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"}, long_job=True)
    jobs = {job_path(): [{"state": "running"}] * 4 + [{"state": "done"}]}
    t = Scripted(PID, [made_state([a]), exported()], jobs=jobs, posts={a["path"]: Reply(200, {"job_id": "j1"})})
    r, log = make_run(tmp_path, t, poll=1.0)
    assert r.advance(r.clock() - 1) is None and t.log == []                      # no time at all: it did not even read the state
    assert r.advance(r.clock() + 2.5) is None                                    # the time of one part is over while the job runs
    assert r.child is not None and len([x for x in t.log if x[0] == "POST"]) == 1
    res = r.advance(r.clock() + 1000)                                            # the next part goes on with the same job
    assert res["reason"] == "exported" and len([x for x in t.log if x[0] == "POST"]) == 1          # the call was made once, not again
    assert r.advance(r.clock() + 1000) is res                                    # an ended run stays ended


# -------------------------------------------------------------------------------------------------------------- the quality bar
def gate_action(gate, body=None):
    a = act(APPROVE[gate], STEP[gate], gate=True, body={"rev": "r"} if body is None else body)
    a["path"] = DOC[gate] + "/approve"                       # the four routes of the app: .../outline/approve, .../narration/approve, .../picks/approve, /api/projects/{pid}/approve
    return a


def gate_run(tmp_path, gate, issues):
    a = gate_action(gate)
    t = Scripted(PID, [made_state([a], current=STEP[gate]), exported()], docs={DOC[gate]: {"issues": issues}}, posts={a["path"]: Reply(200, {})})
    res, _, log = run_loop(tmp_path, t)
    return res, t, log


@pytest.mark.parametrize("gate", reasons.GATES)
def test_an_error_level_issue_stops_before_the_gate_and_nothing_is_sent(tmp_path, gate):
    res, t, _ = gate_run(tmp_path, gate, [{"level": "error", "code": "no_thesis", "message": "The thesis is empty."}])
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "quality_error", gate) and posts(t) == []
    assert res["issues"][0]["code"] == "no_thesis"


@pytest.mark.parametrize("gate,code", [(g, c) for g, d in checks.STOPS.items() for c in d])
def test_a_stopping_warning_stops_before_the_gate_and_the_run_names_it(tmp_path, gate, code):
    level = "warn" if gate == "storyboard" else "warning"
    res, t, _ = gate_run(tmp_path, gate, [{"level": level, "code": code, "message": "m", "beat": "b0001"}])
    assert (res["outcome"], res["reason"], res["gate"]) == ("needs_owner", "quality_warning", gate) and posts(t) == []
    assert res["issues"][0]["code"] == code and res["issues"][0]["why"] and res["issues"][0]["why_vi"] and res["issues"][0]["why_vi"] in res["sentence"]


@pytest.mark.parametrize("gate,code", [(g, c) for g, d in checks.TOLERATED.items() for c in d])
def test_a_tolerated_warning_does_not_stop_the_run_and_stays_in_the_log(tmp_path, gate, code):
    level = "warn" if gate == "storyboard" else "warning"
    res, t, log = gate_run(tmp_path, gate, [{"level": level, "code": code, "message": "m"}, {"level": "info", "code": "length", "message": "x"}])
    assert res["reason"] == "exported" and len(posts(t)) == 1
    assert code in log.rec["steps"][0]["note"]


def test_a_warning_nobody_has_sorted_yet_stops_the_run(tmp_path):
    res, t, _ = gate_run(tmp_path, "storyboard", [{"level": "warn", "code": "brand_new_check", "message": "m"}])
    assert res["reason"] == "quality_warning" and res["issues"][0]["code"] == "brand_new_check" and posts(t) == []


def test_info_issues_are_never_looked_at(tmp_path):
    res, t, _ = gate_run(tmp_path, "narration", [{"level": "info", "code": "overlap", "message": "3%"}])
    assert res["reason"] == "exported" and len(posts(t)) == 1


def test_the_lists_do_not_overlap_and_every_stopping_code_has_both_reasons():
    for gate in reasons.GATES:
        assert not set(checks.STOPS[gate]) & set(checks.TOLERATED[gate]), gate
        for code, (why, vi) in checks.STOPS[gate].items():
            assert why and vi and reasons._is_vietnamese(vi), (gate, code)


def test_the_codes_of_the_lists_are_codes_the_checks_really_make():
    """A code in a list that no check makes any more would hide a renamed warning behind the 'unknown stops' rule; this reads the code of the checks."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "bti"
    src = {"outline": (root / "script" / "validate.py").read_text(encoding="utf-8"), "narration": (root / "script" / "validate.py").read_text(encoding="utf-8"),
           "picks": (root / "picks" / "doc.py").read_text(encoding="utf-8"),
           "storyboard": (root / "engine" / "storyboard.py").read_text(encoding="utf-8") + (root / "engine" / "registry.py").read_text(encoding="utf-8")}
    for gate in reasons.GATES:
        for code in list(checks.STOPS[gate]) + list(checks.TOLERATED[gate]):
            assert re.search(r'["\']%s["\']' % code, src[gate]), (gate, code)


def test_a_document_that_cannot_be_read_before_a_gate_is_a_failure_not_an_approval(tmp_path):
    gate = act("outline.approve", "script", gate=True, body={"rev": "r"})
    res, _, _ = run_loop(tmp_path, Scripted(PID, [made_state([gate])], posts={gate["path"]: Reply(200, {})}))              # the script has no document route: 404
    assert (res["outcome"], res["reason"]) == ("failed", "action_failed") and "reading its document" in res["detail"]


# ------------------------------------------------------------------------------------------------------------------------ the run log
def test_the_log_has_one_record_per_step_and_the_end(tmp_path):
    a = act("voice.generate", "voice", cost={"kind": "machine_time", "about": "x"}, long_job=True, body={"scope": "all"})
    b = act("export.start", "export", cost={"kind": "machine_time", "about": "x"}, long_job=True, body=None)
    jobs = {job_path("j1"): [{"state": "done"}], job_path("j2"): [{"state": "done"}]}
    t = Scripted(PID, [made_state([a]), made_state([b]), exported()], jobs=jobs, posts={a["path"]: Reply(200, {"job_id": "j1"}), b["path"]: Reply(200, {"job_id": "j2"})})
    res, _, log = run_loop(tmp_path, t, until="export")
    rec = runlog.read_run(tmp_path / PID, log.rec["id"])
    assert [s["action"] for s in rec["steps"]] == ["voice.generate", "export.start"] and [s["n"] for s in rec["steps"]] == [1, 2]
    s = rec["steps"][0]
    assert s["step"] == "voice" and s["method"] == "POST" and s["path"] == a["path"] and s["body"] == {"scope": "all"} and s["status"] == 200 and s["ok"] is True
    assert s["job_id"] == "j1" and isinstance(s["seconds"], float) and s["at"]
    assert rec["outcome"] == "done" and rec["reason"] == "exported" and rec["ended"] and rec["result"]["steps_taken"] == 2 and rec["sentence"] == res["sentence"]


def test_a_step_is_in_the_log_before_its_call_is_made(tmp_path):
    a = act("proposal.apply", "edit", body={"accept": "all"})
    seen = {}

    def during(body):
        seen["rec"] = runlog.read_run(tmp_path / PID, seen["id"])
        return Reply(200, {})
    t = Scripted(PID, [made_state([a]), exported()], posts={a["path"]: during})
    d = tmp_path / PID
    d.mkdir()
    log = runlog.RunLog(d, runlog.new_run_id(), pid=PID, until=None, max_steps=40, actor="human")
    seen["id"] = log.rec["id"]
    loop.Run(t, PID, run_id=log.rec["id"], log_=log, poll=0.0, sleep=lambda s: None).advance(1e12)
    assert seen["rec"]["steps"][0]["action"] == "proposal.apply" and seen["rec"]["steps"][0]["ok"] is None and seen["rec"]["ended"] is None


def test_the_log_of_a_project_that_is_gone_writes_nothing_and_does_not_make_the_folder_again(tmp_path):
    a = act("proposal.apply", "edit")
    d = tmp_path / "gone"                                # a project folder that does not exist
    log = runlog.RunLog(d, runlog.new_run_id(), pid=PID, until=None, max_steps=40, actor="human")
    log.start()
    log.begin_step(1, "edit", a, None)
    assert not d.exists() and log.write_error


def test_old_runs_are_pruned(tmp_path):
    d = tmp_path / PID
    d.mkdir()
    for i in range(runlog.KEEP + 5):
        (runlog.runs_dir(d)).mkdir(exist_ok=True)
        (runlog.runs_dir(d) / ("20260101-0000%02d-aaaa.json" % i)).write_text("{}", encoding="utf-8")
    log = runlog.RunLog(d, runlog.new_run_id(), pid=PID, until=None, max_steps=1, actor="human")
    log.start()
    assert len(list(runlog.runs_dir(d).glob("*.json"))) == runlog.KEEP
