"""The two runners (`agy` and `claude`) driving the work-folder session of the automatic picks job, against FAKE executables (the ones of the
draft tests: tests/draft/fake_agy.py and tests/script/fake_claude.py). No real program, model or network. What is checked: the command lines (as
the draft tests check them), the repair round, the limits that stop a session that does not end, cancel, and whole jobs through each runner."""
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest
from auto_helpers import CHOICE, PLAN, FakeAgent, Env, fake_book_thumb, fake_thumb, install_sources, make_auto_project

from bti.draft.guard import Guard
from bti.draft.providers import agy, claudecode as dcc
from bti.picks.auto import helper, inputs as ainputs, job, session, workspace
from bti.script import models as models_mod
from bti.script.providers import claudecode as cc

REPO = Path(__file__).resolve().parents[2]
DRAFT_TESTS = REPO / "tests" / "draft"
SCRIPT_TESTS = REPO / "tests" / "script"
MODEL_CLAUDE = "claude:claude-opus-5-5@high"


def _alive(pid):
    if os.name == "nt":
        import subprocess
        return str(pid) in subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
    try:
        os.kill(pid, 0)
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class Fake:
    """A fake executable in a folder of its own, its mode and its recorded calls and prompts."""

    def __init__(self, d, exe):
        self.dir, self.exe_path = d, str(exe)

    def mode(self, m, **cfg):
        (self.dir / "mode").write_text(m)
        c = json.loads((self.dir / "cfg.json").read_text(encoding="utf-8"))
        c.update(cfg)
        (self.dir / "cfg.json").write_text(json.dumps(c), encoding="utf-8")

    def calls(self, kind=None):
        p = self.dir / "calls.jsonl"
        rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []
        return [r for r in rows if r["argv"][:1] == ["-p"]] if kind == "run" else rows

    def prompts(self):
        p = self.dir / "prompts.jsonl"
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []

    def pids(self):
        return [int(x) for x in (self.dir / "pids").read_text().split()]


def write_exe(d, name, script_text):
    script = d / ("fake_%s.py" % name)
    script.write_text(script_text, encoding="utf-8")
    if os.name == "nt":
        exe = d / (name + ".cmd")
        exe.write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8")
    else:
        exe = d / name
        exe.write_text("#!%s\n%s" % (sys.executable, script_text))
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return exe


@pytest.fixture
def pdir(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    return make_auto_project(root)


@pytest.fixture
def ws(pdir, tmp_path):
    return workspace.build_plan(ainputs.load(pdir), job.PLAN_LIMITS, root=tmp_path / "ws")


def specs_for(ws_root):
    return {"plan": FakeAgent.fit(PLAN, ws_root, "plan")}


@pytest.fixture
def fakeagy(tmp_path, monkeypatch, pdir, ws):
    d = tmp_path / "bin_agy"
    d.mkdir()
    exe = write_exe(d, "agy", (DRAFT_TESTS / "fake_agy.py").read_text(encoding="utf-8"))
    monkeypatch.setenv("BTI_AGY_BIN", str(exe))
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    agy._HELP_OK.clear()
    (d / "cfg.json").write_text(json.dumps({"specs": specs_for(ws.root), "victim": str(pdir / "project.json")}), encoding="utf-8")
    f = Fake(d, exe)
    f.mode("ok")
    return f


@pytest.fixture
def fakeclaude(tmp_path, monkeypatch, pdir, ws):
    d = tmp_path / "bin_claude"
    d.mkdir()
    fix_script, fix_draft = SCRIPT_TESTS / "fixtures" / "claude", DRAFT_TESTS / "fixtures" / "claude"
    text = (SCRIPT_TESTS / "fake_claude.py").read_text(encoding="utf-8").replace('"@@FIX_SCRIPT@@"', repr(str(fix_script))).replace('"@@FIX_DRAFT@@"', repr(str(fix_draft)))
    exe = write_exe(d, "claude", text)
    monkeypatch.setenv("BTI_CLAUDE_BIN", str(exe))
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    cc._HELP_OK.clear()
    models_mod.reset_cache()
    (d / "cfg.json").write_text(json.dumps({"specs": specs_for(ws.root), "victim": str(pdir / "project.json")}), encoding="utf-8")
    f = Fake(d, exe)
    f.mode("ok")
    return f


def guard(pdir):
    return Guard(pdir, extra=lambda: None, repo_root=pdir.parent)


def go(ws, pdir, model, *, limits=session.Limits(2, 80, 1), check_fn=None, ctx=None, transcript=None):
    return session.run_session(ws.root, model=model, project_dir=pdir, ctx=ctx, label="Agent đang lập danh sách hình", limits=limits,
                               check_fn=check_fn or (lambda: helper.run_check(ws.root).problems()), transcript=transcript, python=sys.executable,
                               guard_factory=guard)


class JobCtx:
    """What a part of a long job hands to a session: cancel, progress, and the runner that ends the process tree."""

    def __init__(self):
        self.event, self.notes, self.meta = threading.Event(), [], {}
        self.run_process = agy.DefaultRunner(self.cancelled).run_process

    def cancelled(self):
        return self.event.is_set()

    def progress(self, frac, note=""):
        self.notes.append((frac, note))


# ---------------------------------------------------------------------------------------------------------------- the command lines
def test_agy_command_line_prompt_and_the_file_it_writes(fakeagy, ws, pdir):
    out = go(ws, pdir, "agy:some-model", transcript=ws.root.parent / "events.jsonl")
    assert out.status == "ok" and out.steps == 3 and out.turns == 1 and out.repairs == 0 and out.code is None
    (c,) = fakeagy.calls()
    a = c["argv"]
    assert a == agy.build_command(fakeagy.exe_path, "agy:some-model")[1:]                         # exactly the draft's command line
    assert a[:1] == ["--dangerously-skip-permissions"] and a[a.index("--model") + 1] == "some-model"
    assert a[a.index("--input-format") + 1] == "stream-json" and a[a.index("--output-format") + 1] == "stream-json"
    assert not any("TASK.md" in x for x in a) and Path(c["cwd"]).resolve() == ws.root.resolve()   # the prompt goes through stdin; the folder is the cwd
    assert "TASK.md" in fakeagy.prompts()[0] and (ws.root / "out" / "plan.json").is_file()
    assert helper.run_check(ws.root).ok
    assert (ws.root.parent / "events.jsonl").read_text().count('"event": "step_update"') == 3


def test_claude_command_line_names_the_two_helpers_and_nothing_else(fakeclaude, ws, pdir):
    out = go(ws, pdir, MODEL_CLAUDE)
    assert out.status == "ok" and out.steps == 3 and out.code is None and helper.run_check(ws.root).ok
    (c,) = fakeclaude.calls("run")
    a = c["argv"]
    rules = session.allow_rules()
    assert a == dcc.build_command(fakeclaude.exe_path, MODEL_CLAUDE, allow=rules)[1:]
    assert a[0] == "-p" and a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--effort") + 1] == "high"
    assert a[a.index("--tools") + 1] == "Bash,Read,Write,Edit,Glob,Grep" and a[a.index("--permission-mode") + 1] == "dontAsk"
    allowed = a[a.index("--allowedTools") + 1:a.index("--disallowedTools")]
    assert allowed == rules and "Edit(./out/**)" in allowed
    posix = [r for r in session.allow_rules(windows=False)]
    assert "Bash(./check)" in posix and "Bash(./check --help)" in posix and "Bash(./crop --box * -o look/*)" in posix and "Bash(./crop --grid -o look/*)" in posix
    assert not [r for r in posix if "still" in r or "defaults" in r or "--chapter" in r]          # the draft's helpers are not this job's
    assert "Bash(.\\check.cmd)" in session.allow_rules(windows=True) and "Bash(.\\crop.cmd --box * -o look/*)" in session.allow_rules(windows=True)
    denied = a[a.index("--disallowedTools") + 1:a.index("--append-system-prompt")]
    same = dcc.build_command(fakeclaude.exe_path, MODEL_CLAUDE)
    assert denied == same[same.index("--disallowedTools") + 1:same.index("--append-system-prompt")]      # the draft's confinement, unchanged
    assert "WebFetch" in denied and "Bash(*..*)" in denied
    for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in a
    for never in ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "--bare", "--resume", "--add-dir", "--settings", "-c"):
        assert never not in a
    assert a[a.index("--append-system-prompt") + 1] == dcc.CONFINEMENT and Path(c["cwd"]).resolve() == ws.root.resolve()
    assert "TASK.md" in fakeclaude.prompts()[0] and (ws.root / "out" / "plan.json").is_file()


def test_a_job_can_name_its_own_rules_and_the_default_stays_the_pictures_jobs(fakeclaude, ws, pdir):
    """fixes3: `run_session` takes `allow`; without it the rules are the pictures job's (`./check` and `./crop`), with it exactly the rules the caller names."""
    only_check = session.allow_rules(helpers=("check",))
    assert "Edit(./out/**)" in only_check and not [r for r in only_check if "crop" in r]
    assert "Bash(./check)" in session.allow_rules(windows=False, helpers=("check",)) and "Bash(.\\check.cmd)" in session.allow_rules(windows=True, helpers=("check",))
    assert session.allow_rules(helpers=("check", "crop")) == session.allow_rules() and session.HELPERS == ("check", "crop")
    assert session.allow_rules(helpers=()) == ["Edit(./out/**)"]
    out = session.run_session(ws.root, model=MODEL_CLAUDE, project_dir=pdir, label="x", limits=session.Limits(2, 80, 1),
                              check_fn=lambda: helper.run_check(ws.root).problems(), python=sys.executable, guard_factory=guard, allow=only_check)
    assert out.status == "ok"
    (c,) = fakeclaude.calls("run")
    a = c["argv"]
    assert a[a.index("--allowedTools") + 1:a.index("--disallowedTools")] == only_check
    assert a == dcc.build_command(fakeclaude.exe_path, MODEL_CLAUDE, allow=only_check)[1:]


def test_the_limits_of_the_two_sessions_are_written_once_in_the_job(ws):
    """fixes3: `session.py` used to carry the old numbers under the same names as `job.py`; now only the job has them, and the work folder's task says the job's numbers."""
    assert not hasattr(session, "PLAN_LIMITS") and not hasattr(session, "CHOOSE_LIMITS")
    assert (job.PLAN_LIMITS.minutes, job.PLAN_LIMITS.steps) == (30, 120) and (job.CHOOSE_LIMITS.minutes, job.CHOOSE_LIMITS.steps) == (40, 220)
    task = (ws.root / "TASK.md").read_text(encoding="utf-8")
    assert "**120 steps**" in task and "**30 minutes**" in task


def test_the_drafts_own_command_line_is_unchanged(fakeclaude):
    default = dcc.build_command(fakeclaude.exe_path, MODEL_CLAUDE)
    assert default == dcc.build_command(fakeclaude.exe_path, MODEL_CLAUDE, allow=None)
    allowed = default[default.index("--allowedTools") + 1:default.index("--disallowedTools")]
    assert allowed == dcc.allow_rules() and any("still" in r for r in allowed) and any("defaults" in r for r in allowed) and not any("crop" in r for r in allowed)
    assert dcc.SUPPORTS_ALLOW is True and not getattr(agy, "SUPPORTS_ALLOW", False)


# ---------------------------------------------------------------------------------------------------------------- the repair round
@pytest.mark.parametrize("which", ["agy", "claude"])
def test_a_repair_message_goes_into_the_same_conversation_once(which, request, ws, pdir):
    fake = request.getfixturevalue("fakeagy" if which == "agy" else "fakeclaude")
    model = "agy:some-model" if which == "agy" else MODEL_CLAUDE
    seen = []

    def check_fn():
        seen.append(1)
        return "ERROR lines[0] (b0001): reason must be one short sentence" if len(seen) == 1 else None
    out = go(ws, pdir, model, check_fn=check_fn)
    assert out.status == "ok" and out.turns == 2 and out.repairs == 1
    p = fake.prompts()
    assert len(p) == 2 and "found problems" in p[1] and "ERROR lines[0] (b0001)" in p[1]
    assert len(fake.calls("run") if which == "claude" else fake.calls()) == 1                         # one process: the same conversation


@pytest.mark.parametrize("which", ["agy", "claude"])
def test_only_one_repair_round_then_the_session_ends_with_the_problems_left(which, request, ws, pdir):
    fake = request.getfixturevalue("fakeagy" if which == "agy" else "fakeclaude")
    out = go(ws, pdir, "agy:some-model" if which == "agy" else MODEL_CLAUDE, check_fn=lambda: "ERROR always")
    assert out.status == "ok" and out.turns == 2 and out.repairs == 1 and len(fake.prompts()) == 2


# ---------------------------------------------------------------------------------------------------------------- limits and cancel
def test_the_step_limit_ends_a_session_that_does_not_end_and_kills_its_processes(fakeagy, ws, pdir):
    fakeagy.mode("slow")
    ctx = JobCtx()
    t0 = time.time()
    out = go(ws, pdir, "agy:some-model", limits=session.Limits(minutes=5, steps=0, repairs=1), ctx=ctx)
    assert out.status == "limit" and out.code == "picks_auto_limit" and time.time() - t0 < 30
    assert "giới hạn" in out.message
    time.sleep(0.5)
    assert not any(_alive(p) for p in fakeagy.pids())
    assert (ws.root / "out" / "plan.json").is_file()                                               # what was written before the stop is still there
    assert ctx.notes and ctx.notes[-1][1].startswith("Agent đang lập danh sách hình: bước ")


def test_the_time_limit_ends_a_session_that_does_not_end_and_kills_its_processes(fakeagy, ws, pdir):
    fakeagy.mode("slow")
    t0 = time.time()
    out = go(ws, pdir, "agy:some-model", limits=session.Limits(minutes=0.04, steps=80, repairs=1))
    assert out.status == "timeout" and out.code == "agy_timeout" and "quá thời gian" in out.message and time.time() - t0 < 30
    time.sleep(0.5)
    assert not any(_alive(p) for p in fakeagy.pids())


def test_the_claude_time_limit_too(fakeclaude, ws, pdir):
    fakeclaude.mode("slow")
    out = go(ws, pdir, MODEL_CLAUDE, limits=session.Limits(minutes=0.04, steps=80, repairs=1))
    assert out.status == "timeout" and out.code == "claude_timeout"
    time.sleep(0.5)
    assert not any(_alive(p) for p in fakeclaude.pids())


def test_the_limits_are_in_the_progress_line(fakeagy, ws, pdir):
    ctx = JobCtx()
    go(ws, pdir, "agy:some-model", limits=session.Limits(minutes=20, steps=80, repairs=1), ctx=ctx)
    assert ctx.notes and ctx.notes[-1][1] == "Agent đang lập danh sách hình: bước 3/80, 0/20 phút."


def test_cancel_ends_the_session_and_its_processes(fakeagy, ws, pdir):
    fakeagy.mode("slow")
    ctx = JobCtx()
    threading.Timer(2.0, ctx.event.set).start()
    out = go(ws, pdir, "agy:some-model", ctx=ctx)
    assert out.status == "cancelled"
    time.sleep(0.5)
    assert not any(_alive(p) for p in fakeagy.pids())


def test_a_session_that_touched_the_project_is_marked_tampered(fakeagy, ws, pdir):
    fakeagy.mode("tamper")
    out = go(ws, pdir, "agy:some-model")
    assert out.status == "tampered" and out.code == "picks_auto_tampered" and any("project.json" in t for t in out.tampered)


def test_a_quota_failure_carries_the_time_it_opens_again(fakeagy, ws, pdir):
    fakeagy.mode("quota")
    out = go(ws, pdir, "agy:some-model")
    assert out.status == "error" and out.code == "agy_rate_limit" and out.retry_after_seconds == 176 and "Hạn mức của gói Antigravity" in out.message


def test_a_program_that_is_not_installed_is_refused_before_it_starts(ws, pdir, monkeypatch):
    from bti.draft.inputs import DraftError
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    with pytest.raises(DraftError) as e:
        go(ws, pdir, "agy:some-model")
    assert e.value.code == "agy_missing" and "Chưa cài `agy`" in session.refuse_text(e.value)
    with pytest.raises(DraftError) as e:
        session.check_installed("agy:some-model")
    assert e.value.code == "agy_missing"


# ---------------------------------------------------------------------------------------------------------------- whole jobs through each runner
def whole_job(tmp_path, monkeypatch, pdir_root, fake, model):
    """The job from an empty picks document to every line filled, with the agent being the fake EXECUTABLE (so the real runner module drives it)."""
    from bti.longjob import manager
    monkeypatch.setattr(session, "check_installed", lambda m: None)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "work"))
    (tmp_path / "work").mkdir(exist_ok=True)
    pd = pdir_root
    manager.configure(projects_root=pd.parent)
    sources = install_sources(monkeypatch)
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)                                         # the fake executable is the "real" program here
    e = Env(pd.parent, pd, None, sources, manager)
    # one file of specs for both sessions: the plan (fitted to the lines) and the choice (the wanted pictures and boxes of this fixture)
    plan_ws = workspace.build_plan(ainputs.load(pd), job.PLAN_LIMITS, root=tmp_path / "probe")
    fake.mode("ok", specs={"plan": FakeAgent.fit(PLAN, plan_ws.root, "plan"), "choice": CHOICE})
    return e, e.run(model=model, timeout=120)


@pytest.mark.parametrize("which,model", [("fakeagy", "agy:some-model"), ("fakeclaude", MODEL_CLAUDE)])
def test_the_whole_job_runs_through_each_runner(which, model, request, pdir, tmp_path, monkeypatch):
    fake = request.getfixturevalue(which)
    e, job = whole_job(tmp_path, monkeypatch, pdir, fake, model)
    assert job["state"] == "done", job.get("error")
    assert job["result"]["lines_done"] == 6 and job["result"]["sentence"] == "Agent đã chọn hình cho 6/6 đoạn."
    assert job["meta"]["model"] == model
    runs = fake.calls("run") if which == "fakeclaude" else fake.calls()
    assert len(runs) == 2                                                                           # the plan session and the choose session
    assert all(Path(r["cwd"]).name.startswith("bti-picks-") for r in runs)                          # each session ran in a work folder of its own
    assert e.picks()["beats"]["b0006"]["status"] == "skip" and e.picks()["approval"]["approved"] is False
    assert {r["actor"] for r in e.changes()} == {"agent:" + model}
