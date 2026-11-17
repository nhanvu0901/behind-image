import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from bti.draft import workspace as W
from bti.draft.compile import summary_text
from bti.draft.guard import Guard, diff, snapshot_dir
from bti.draft.inputs import DraftError, load_inputs
from bti.draft.providers import agy, auto
from helpers import GOOD

HERE = Path(__file__).resolve().parent


@pytest.fixture()
def fake(tmp_path, monkeypatch, proj):
    d = tmp_path / "bin"
    d.mkdir()
    script = d / "fake_agy.py"
    script.write_text((HERE / "fake_agy.py").read_text(encoding="utf-8"), encoding="utf-8")
    if os.name == "nt":
        exe = d / "agy.cmd"
        exe.write_text('@"%s" "%s" %%*\r\n' % (sys.executable, script), encoding="utf-8")
    else:
        exe = d / "agy"
        exe.write_text("#!%s\n%s" % (sys.executable, script.read_text(encoding="utf-8")), encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BTI_AGY_BIN", str(exe))
    agy._HELP_OK.clear()
    victim = proj / "timing.json"
    (d / "cfg.json").write_text(json.dumps({"specs": GOOD, "victim": str(victim)}), encoding="utf-8")

    class F:
        dir = d

        def mode(self, m):
            (d / "mode").write_text(m)

        def calls(self):
            p = d / "calls.jsonl"
            return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []

        def prompts(self):
            p = d / "prompts.jsonl"
            return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []
    f = F()
    f.mode("ok")
    return f


@pytest.fixture()
def ws(proj, tmp_path):
    return W.build(load_inputs(proj), root=tmp_path / "ws")


def checker(ws):
    def check(turn):
        res, _ = W.workspace_compile(ws.root, draw=False)
        return summary_text(res) if res.errors else None
    return check


def test_normal_run_command_line_prompt_and_events(fake, ws, proj):
    seen = []
    r = agy.run(ws.root, model="some-model", timeout=60, check=checker(ws), on_progress=seen.append, python=sys.executable,
                transcript_path=ws.root.parent / "events.jsonl", guard=Guard(proj, extra=lambda: None))
    assert r.status == "ok" and r.turns == 1 and r.steps == 3 and r.last_action == "view_file" and r.conversation_id == "conv-1"
    a = fake.calls()[0]["argv"]
    assert a[:1] == ["--dangerously-skip-permissions"] and a[a.index("--model") + 1] == "some-model"
    assert a[a.index("--input-format") + 1] == "stream-json" and a[a.index("--output-format") + 1] == "stream-json"
    assert "-p" not in a and not any("TASK.md" in x for x in a)                          # the prompt goes through stdin
    assert Path(fake.calls()[0]["cwd"]).resolve() == ws.root.resolve()
    assert "TASK.md" in fake.prompts()[0] and (ws.root / "out" / "c01.json").is_file()
    assert seen and seen[-1]["steps"] == 3 and seen[-1]["out_files"] == 2
    assert (ws.root.parent / "events.jsonl").read_text().count('"event": "step_update"') == 3
    assert agy.DEFAULT_MODEL == "gemini-pro-orchestrator-g1-pro"


def test_default_model_and_environment_whitelist(fake, ws, monkeypatch):
    monkeypatch.setenv("SECRET_THING", "x")
    agy.run(ws.root, timeout=60, python="/the/python")
    c = fake.calls()[0]
    assert c["argv"][c["argv"].index("--model") + 1] == agy.DEFAULT_MODEL
    assert "SECRET_THING" not in c["env"] and "BTI_PYTHON" in c["env"] and "BTI_AGY_BIN" not in c["env"]


def test_repair_turn_is_sent_to_the_same_conversation(fake, ws):
    fake.mode("repair")
    r = agy.run(ws.root, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "ok" and r.turns == 2 and r.repairs == 1
    p = fake.prompts()
    assert len(p) == 2 and "found problems" in p[1] and "chapter c01, shot 2" in p[1]
    assert len(fake.calls()) == 1                                            # one process: the same conversation


def test_repairs_stop_after_the_limit_and_leave_the_errors(fake, ws):
    fake.mode("bad")
    r = agy.run(ws.root, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "ok" and r.turns == 3 and r.repairs == 2
    res, _ = W.workspace_compile(ws.root, draw=False)
    assert res.errors


def test_repair_after_the_program_exited_uses_conversation_flag(fake, ws):
    fake.mode("exits")
    r = agy.run(ws.root, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "ok" and r.repairs == 1
    calls = fake.calls()
    assert len(calls) == 2 and calls[1]["argv"][-2:] == ["--conversation", "conv-1"] and "--conversation" not in calls[0]["argv"]


def test_time_out_kills_the_process_tree(fake, ws):
    fake.mode("slow")
    t0 = time.time()
    r = agy.run(ws.root, timeout=2.5, check=None)
    assert r.status == "timeout" and r.error_code == "agy_timeout" and time.time() - t0 < 25
    time.sleep(0.5)
    pids = [int(x) for x in (fake.dir / "pids").read_text().split()]
    for pid in pids:
        assert not _alive(pid), pid
    assert (ws.root / "out" / "c01.json").is_file()                          # what was written before is still there (partial result)


def test_cancel_kills_the_process_tree(fake, ws):
    fake.mode("slow")
    ev = threading.Event()
    threading.Timer(2.0, ev.set).start()
    r = agy.run(ws.root, timeout=60, cancel=ev)
    assert r.status == "cancelled"
    time.sleep(0.5)
    for pid in [int(x) for x in (fake.dir / "pids").read_text().split()]:
        assert not _alive(pid)


def _alive(pid):
    if os.name == "nt":
        import subprocess
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True).stdout
        return str(pid) in out
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


def test_tampering_is_detected(fake, ws, proj):
    fake.mode("tamper")
    r = agy.run(ws.root, timeout=60, guard=Guard(proj, extra=lambda: None))
    assert r.status == "tampered" and r.tampered == ["changed timing.json"]


def test_an_unrelated_change_in_cache_is_not_tampering(fake, ws, proj):
    g = Guard(proj, extra=lambda: None)
    g.before()
    (proj / "cache").mkdir()
    (proj / "cache" / "x.json").write_text("{}")
    (proj / "proposals").mkdir()
    (proj / "proposals" / "p.json").write_text("{}")
    assert g.after() == []
    (proj / "picks.json").write_text("{}")
    assert g.after() == ["changed picks.json"]


def test_guard_reports_extra_status_changes(proj):
    state = {"v": "a"}
    g = Guard(proj, extra=lambda: state["v"])
    g.before()
    state["v"] = "b"
    assert "comic repository" in g.after()[0]


def test_error_results_and_auth(fake, ws):
    fake.mode("error")
    r = agy.run(ws.root, timeout=30)
    assert r.status == "error" and r.error_code == "agy_error"
    fake.mode("auth")
    r = agy.run(ws.root, timeout=30)
    assert r.status == "error" and r.error_code == "agy_auth"
    fake.mode("noresult")
    r = agy.run(ws.root, timeout=30)
    assert r.status == "error" and r.error_code == "agy_no_result"


def test_missing_cli_and_old_cli_and_busy(ws, monkeypatch, fake):
    monkeypatch.setenv("BTI_AGY_BIN", "")
    with pytest.raises(DraftError) as e:
        agy.run(ws.root, timeout=5)
    assert e.value.code == "agy_missing"
    monkeypatch.setenv("BTI_AGY_BIN", str(fake.dir / ("agy.cmd" if os.name == "nt" else "agy")))
    assert agy.LOCK.acquire(blocking=False)
    try:
        with pytest.raises(DraftError) as e:
            agy.run(ws.root, timeout=5)
        assert e.value.code == "agy_busy"
    finally:
        agy.LOCK.release()


def test_snapshot_diff_helpers(tmp_path):
    (tmp_path / "a.txt").write_text("1")
    s1 = snapshot_dir(tmp_path)
    (tmp_path / "b.txt").write_text("2")
    assert diff(s1, snapshot_dir(tmp_path)) == ["added b.txt"]
