"""The job `title.generate` (kind `title`), driven through the real long-job runner and the real session code with a FAKE agent (no program, model or network): a good answer, one
repair, a failure, a limit, a cancel, the refusals before it starts, a person's title, a narration that changes while the agent works, and the storyboard hook."""
import sys
import threading
import time

import pytest
from title_helpers import FakeTitleAgent, broken, good_choice, install_agent, make_title_project

from bti.draft.guard import Guard
from bti.draft.providers.agy import AgyResult
from bti.longjob import Part, manager
from bti.script import store as sstore
from bti.title import apply as tapply, job as tjob, store as T
from bti.title.store import TitleError


@pytest.fixture()
def pdir(root):
    return make_title_project(root)


def seams():
    return {"guard_factory": lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), "python": sys.executable}


def run(pdir, monkeypatch, agent, timeout=30, **kw):
    install_agent(monkeypatch, agent)
    rec = tjob.start(pdir.name, pdir, manager=manager, **{**seams(), **kw})
    return manager.wait(rec["id"], timeout)


def test_a_good_answer_writes_the_document_with_the_first_candidate_as_the_title(pdir, monkeypatch):
    agent = FakeTitleAgent()
    job = run(pdir, monkeypatch, agent)
    assert job["state"] == "done", job
    assert job["kind"] == "title" and job["meta"]["model"] == "mock" and job["meta"]["agent"]["id"] == "gem" and job["meta"]["limits"] == {"minutes": 10, "steps": 40, "repairs": 1}
    doc, _ = T.read(pdir)
    assert doc["chosen"]["text"] == "The Saint Who Was Also an Advertisement" and doc["chosen"]["by"] == "agent:mock" and doc["chosen"]["source"] == "agent"
    assert len(doc["candidates"]) == 6 and doc["narration_rev"] == T.narration_rev(pdir) and T.state(pdir) == "done"
    assert doc["written"]["model"] == "mock" and doc["written"]["job_id"] == job["id"] and doc["written"]["session"]["turns"] == 1 and doc["written"]["session"]["repairs"] == 0
    res = job["result"]
    assert res["title"] == doc["chosen"]["text"] and res["candidates"] == 6 and res["sentence"] == 'Agent đã viết 6 tựa và chọn: "The Saint Who Was Also an Advertisement".'
    assert any("The Ring on the Scales" in w for w in res["warnings"])
    (c,) = agent.calls
    assert c["max_repairs"] == 1 and c["timeout"] == 600.0 and c["model"] == "mock"
    assert sorted(c["files"]) == ["TASK.md", "check", "inputs/context.json", "inputs/narration.json", "inputs/outline.json", "inputs/painting.json"] or "check.cmd" in c["files"]
    assert '"The Hidden Meaning"' in c["task"] and "{{" not in c["task"]
    from bti.picks.auto import session
    rules = c["allow"]
    assert rules == session.allow_rules() and "Edit(./out/**)" in rules                           # write under out/, run ./check: the draft's confinement, nothing more
    assert "Bash(./check)" in session.allow_rules(windows=False) and "Bash(.\\check.cmd)" in session.allow_rules(windows=True)
    assert doc["history"] == []


def test_the_work_folder_of_a_good_run_is_removed(pdir, monkeypatch, tmp_path):
    seen = []
    agent = FakeTitleAgent(hook=lambda ws, kw: seen.append(ws) or None)
    run(pdir, monkeypatch, agent)
    assert seen and not seen[0].exists()


def test_one_repair_round_with_the_programs_own_message(pdir, monkeypatch):
    bad = broken(lambda d: d["candidates"][1].update(text="The Saint: A Ring Story"))
    agent = FakeTitleAgent(answer=[bad, good_choice()])
    job = run(pdir, monkeypatch, agent)
    assert job["state"] == "done" and job["result"]["session"]["turns"] == 2 and job["result"]["session"]["repairs"] == 1
    (c,) = agent.calls
    assert len(c["problems"]) == 2 and "colon" in c["problems"][0] and "1 error(s)" in c["problems"][0] and c["problems"][1] is None
    assert T.chosen_text(pdir) == "The Saint Who Was Also an Advertisement"


def test_a_file_that_is_still_wrong_after_the_repair_fails_the_job_and_writes_nothing(pdir, monkeypatch):
    bad = broken(lambda d: d["candidates"][1].update(text="The Saint: A Ring Story"))
    agent = FakeTitleAgent(answer=bad)
    job = run(pdir, monkeypatch, agent)
    assert job["state"] == "error" and job["error_code"] == "title_no_output" and "kể cả sau một lần nhắc sửa" in job["error"]
    assert not (pdir / "title.json").exists() and agent.calls[0]["turns"] == 2


def test_no_file_at_all_is_the_same_failure(pdir, monkeypatch):
    agent = FakeTitleAgent(hook=lambda ws, kw: AgyResult(status="ok", elapsed=1.0))
    job = run(pdir, monkeypatch, agent)
    assert job["state"] == "error" and job["error_code"] == "title_no_output" and not (pdir / "title.json").exists()


def test_an_agent_that_fails_gives_its_own_code_and_sentence(pdir, monkeypatch):
    job = run(pdir, monkeypatch, FakeTitleAgent(status="error"))
    assert job["state"] == "error" and job["error_code"] == "agy_error" and not (pdir / "title.json").exists()
    job = run(pdir, monkeypatch, FakeTitleAgent(status="error", error_code="agy_rate_limit"))
    assert job["state"] == "error" and job["error_code"] == "agy_rate_limit" and "Hạn mức" in job["error"]


def test_the_step_limit_stops_the_run_with_its_own_sentence(pdir, monkeypatch):
    def hook(ws, kw):
        kw["on_progress"]({"steps": 999, "elapsed": 1.0})
        return AgyResult(status="cancelled", elapsed=1.0)
    job = run(pdir, monkeypatch, FakeTitleAgent(hook=hook))
    assert job["state"] == "error" and job["error_code"] == "title_limit" and "giới hạn" in job["error"] and not (pdir / "title.json").exists()


def test_the_agent_that_touches_the_project_is_tampered(pdir, monkeypatch):
    def hook(ws, kw):
        return AgyResult(status="tampered", elapsed=1.0)
    job = run(pdir, monkeypatch, FakeTitleAgent(hook=hook))
    assert job["state"] == "error" and job["error_code"] == "title_tampered" and "ngoài thư mục làm việc" in job["error"] and not (pdir / "title.json").exists()


def test_a_cancel_ends_the_job_and_writes_nothing(pdir, monkeypatch):
    def hook(ws, kw):
        manager.cancel(manager.active(pdir.name, "title")["id"])
        return AgyResult(status="cancelled", elapsed=1.0)
    job = run(pdir, monkeypatch, FakeTitleAgent(hook=hook))
    assert job["state"] == "cancelled" and not (pdir / "title.json").exists()


def test_a_missing_program_is_refused_before_the_job_starts(pdir, monkeypatch):
    from bti.draft.inputs import DraftError
    from bti.picks.auto import session

    def refuse(model_id):
        raise DraftError("agy_missing", "agy is not installed")
    monkeypatch.setattr(session, "check_installed", refuse)
    with pytest.raises(TitleError) as e:
        tjob.start(pdir.name, pdir, manager=manager, **seams())
    assert e.value.code == "agy_missing" and e.value.status == 409 and manager.active(pdir.name, "title") is None


# ---------------------------------------------------------------------------------------------------------------- refusals
def test_an_unapproved_or_missing_narration_is_refused(root, monkeypatch):
    install_agent(monkeypatch, FakeTitleAgent())
    d = make_title_project(root, "unap", approved=False)
    with pytest.raises(TitleError) as e:
        tjob.start("unap", d, manager=manager, **seams())
    assert e.value.code == "narration_not_approved" and e.value.status == 409
    n = sstore.load_narration(make_title_project(root, "ok1"))
    d2 = root / "ok1"
    n.chapters[0].beats[0].text += " Changed after the approval."
    sstore.save_narration(d2, n)
    with pytest.raises(TitleError) as e2:
        tjob.start("ok1", d2, manager=manager, **seams())
    assert e2.value.code == "narration_not_approved"
    (root / "empty").mkdir()
    (root / "empty" / "project.json").write_text("{}", encoding="utf-8")
    with pytest.raises(TitleError):
        tjob.start("empty", root / "empty", manager=manager, **seams())


@pytest.mark.parametrize("note, code", [("x" * 601, "title_note_too_long"), (7, "title_note_invalid"), (["a"], "title_note_invalid")])
def test_the_owners_note_is_checked(pdir, monkeypatch, note, code):
    install_agent(monkeypatch, FakeTitleAgent())
    with pytest.raises(TitleError) as e:
        tjob.start(pdir.name, pdir, manager=manager, note=note, **seams())
    assert e.value.code == code and e.value.status == 422


def test_the_owners_note_reaches_the_agents_task_and_the_job_and_the_document(pdir, monkeypatch):
    agent = FakeTitleAgent()
    job = run(pdir, monkeypatch, agent, note="  make it about the\n mirror ")
    assert job["state"] == "done" and job["meta"]["note"] == "make it about the mirror"
    assert "The owner's request for this title" in agent.calls[0]["task"] and "make it about the mirror" in agent.calls[0]["task"]
    assert T.read(pdir)[0]["written"]["note"] == "make it about the mirror"


def test_a_bad_model_name_is_refused(pdir):
    with pytest.raises(TitleError) as e:
        tjob.start(pdir.name, pdir, manager=manager, model="bad model name!", **seams())
    assert e.value.code == "bad_model"


def quick(kind, pdir, hold):
    def run_(ctx):
        hold.wait(10)
    return manager.start(kind, pdir.name, pdir, [Part(key="p1", title="Phần", run=run_, est_seconds=1)], {"action": "auto"} if kind == "picks" else {})


@pytest.mark.parametrize("kind", ["draft", "picks", "auto"])
def test_another_agent_job_of_the_project_refuses_the_title_job_unless_the_run_asks(pdir, monkeypatch, kind):
    install_agent(monkeypatch, FakeTitleAgent())
    hold = threading.Event()
    other = quick(kind, pdir, hold)
    try:
        with pytest.raises(TitleError) as e:
            tjob.start(pdir.name, pdir, manager=manager, **seams())
        assert e.value.code == "agent_job_running" and e.value.status == 409 and e.value.extra["job_id"] == other["id"]
        if kind == "auto":                                          # the automatic run takes the title itself: its own job is no reason to refuse
            rec = tjob.start(pdir.name, pdir, manager=manager, by_run=True, **seams())
            assert manager.wait(rec["id"], 30)["state"] == "done"
    finally:
        hold.set()


def test_the_title_job_holds_the_agent_against_the_other_jobs(pdir, monkeypatch):
    from bti.draft import run as draft_run
    from bti.draft.inputs import DraftError
    gate = threading.Event()
    agent = FakeTitleAgent(hook=lambda ws, kw: (gate.wait(10), None)[1])
    install_agent(monkeypatch, agent)
    rec = tjob.start(pdir.name, pdir, manager=manager, **seams())
    try:
        with pytest.raises(TitleError) as e:                          # a second title job of the project
            tjob.start(pdir.name, pdir, manager=manager, **seams())
        assert e.value.code == "longjob_running" and e.value.extra["job_id"] == rec["id"]
        with pytest.raises(DraftError) as e2:                         # the draft and the prompt boxes
            draft_run.refuse_while_agent_busy(pdir.name, manager)
        assert e2.value.code == "agent_job_running" and "title writer" in e2.value.message
        assert draft_run.other_agent_job(pdir.name, "picks", manager)["id"] == rec["id"]
        assert draft_run.other_agent_job(pdir.name, "title", manager) is None
    finally:
        gate.set()
    assert manager.wait(rec["id"], 30)["state"] == "done"


# ---------------------------------------------------------------------------------------------------------------- what the job does to the rest
def test_a_generation_asked_for_by_hand_replaces_a_persons_title_and_keeps_it(pdir, monkeypatch):
    T.set_title(pdir, base_rev=T.EMPTY_REV, actor="human", text="My Own Title")
    assert T.state(pdir) == "done"
    job = run(pdir, monkeypatch, FakeTitleAgent(), actor="cli:operator")
    assert job["state"] == "done" and job["meta"]["requested_by"] == "cli:operator"
    doc, _ = T.read(pdir)
    assert doc["chosen"]["source"] == "agent" and [h["text"] for h in doc["history"]] == ["My Own Title"] and doc["written"]["requested_by"] == "cli:operator"


def test_a_narration_that_changes_while_the_agent_works_leaves_a_stale_title(pdir, monkeypatch):
    def hook(ws, kw):
        n = sstore.load_narration(pdir)
        n.chapters[2].beats[1].text += " One more thing."
        sstore.save_narration(pdir, n)
    job = run(pdir, monkeypatch, FakeTitleAgent(hook=hook))
    assert job["state"] == "done"
    doc, _ = T.read(pdir)
    assert doc["narration_rev"] != T.narration_rev(pdir) and T.state(pdir) == "stale"          # written from the narration the job read, so the state says it is old


def test_the_storyboard_takes_the_title_through_the_hook_and_a_failure_of_the_hook_never_fails_the_job(pdir, monkeypatch, root):
    calls = []

    def ok(pid, title):
        calls.append((pid, title))
        return {"rev": "r1", "changed": ["s0001"], "approval_was_fresh": True, "sentence": "S"}
    tapply.register(root, ok)
    try:
        job = run(pdir, monkeypatch, FakeTitleAgent())
        assert job["state"] == "done" and calls == [(pdir.name, "The Saint Who Was Also an Advertisement")]
        assert job["result"]["storyboard"] == {"rev": "r1", "changed": ["s0001"], "approval_was_fresh": True, "sentence": "S"}

        def boom(pid, title):
            raise RuntimeError("the engine refused")
        tapply.register(root, boom)
        job = run(pdir, monkeypatch, FakeTitleAgent())
        assert job["state"] == "done" and "the engine refused" in job["result"]["storyboard"]["error"] and job["result"]["storyboard"]["changed"] == []
        tapply.register(root, lambda pid, title: None)                              # no storyboard: the answer has no `storyboard` key
        job = run(pdir, monkeypatch, FakeTitleAgent())
        assert "storyboard" not in job["result"]
    finally:
        tapply.register(root, None)


def test_the_transcripts_are_kept_for_five_runs(pdir, monkeypatch):
    for _ in range(7):
        run(pdir, monkeypatch, FakeTitleAgent())
        time.sleep(1.05)                                                             # the run folder is named by the second
    runs = [p for p in (pdir / "cache" / "title" / "runs").iterdir() if p.is_dir()]
    assert len(runs) <= tjob.KEEP_RUNS
