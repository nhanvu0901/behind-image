"""The agent run with Claude Code (bti/draft/providers/claudecode.py), against a FAKE `claude` executable (tests/script/fake_claude.py) that
replays the shapes recorded from the real program on 2026-11-18 (tests/draft/fixtures/claude/, Claude Code 2.1.327, `--model haiku`). No
network, no real Claude Code, no model call. The usage-limit answers are NOT recordings (a real limit could not be provoked)."""
import json
import os
import re
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from bti.draft import run as R
from bti.draft import workspace as W
from bti.draft.compile import summary_text
from bti.draft.guard import Guard
from bti.draft.inputs import DraftError, load_inputs
from bti.draft.providers import agy, claudecode as dcc
from bti.longjob import LongJobManager
from bti.script import models as models_mod
from bti.script.providers import claudecode as cc
from helpers import GOOD

HERE = Path(__file__).resolve().parent
SCRIPT_TESTS = HERE.parent / "script"
FIX = HERE / "fixtures" / "claude"
SCRIPT_FIX = SCRIPT_TESTS / "fixtures" / "claude"
MODEL = "claude:claude-opus-5-5@high"
OWNER_SIGNED_OUT = "Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại."


@pytest.fixture()
def fakec(tmp_path, monkeypatch, proj):
    d = tmp_path / "bin"
    d.mkdir()
    src = (SCRIPT_TESTS / "fake_claude.py").read_text(encoding="utf-8").replace('"@@FIX_SCRIPT@@"', repr(str(SCRIPT_FIX))).replace('"@@FIX_DRAFT@@"', repr(str(FIX)))
    script = d / "fake_claude.py"
    script.write_text(src, encoding="utf-8")
    if os.name == "nt":
        exe = d / "claude.cmd"
        exe.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        exe = d / "claude"
        exe.write_text(f"#!{sys.executable}\n" + src, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BTI_CLAUDE_BIN", str(exe))
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    cc._HELP_OK.clear()
    models_mod.reset_cache()
    (d / "cfg.json").write_text(json.dumps({"specs": GOOD, "victim": str(proj / "timing.json")}), encoding="utf-8")

    class F:
        dir = d
        exe_path = str(exe)

        def mode(self, m, **cfg):
            (d / "mode").write_text(m)
            c = json.loads((d / "cfg.json").read_text(encoding="utf-8"))
            c.update(cfg)
            (d / "cfg.json").write_text(json.dumps(c), encoding="utf-8")

        def calls(self, kind=None):
            p = d / "calls.jsonl"
            rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []
            if kind == "run":
                rows = [r for r in rows if r["argv"][:1] == ["-p"]]
            return rows

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


def gf(d):
    return Guard(d, extra=lambda: None, repo_root=d.parent)


# ------------------------------------------------------------------------------------------------ the command line
def test_normal_run_command_line_prompt_and_events(fakec, ws, proj):
    seen = []
    r = dcc.run(ws.root, model=MODEL, timeout=60, check=checker(ws), on_progress=seen.append, python=sys.executable,
                transcript_path=ws.root.parent / "events.jsonl", guard=Guard(proj, extra=lambda: None, repo_root=proj.parent))
    assert r.status == "ok" and r.turns == 1 and r.steps == 3 and r.last_action == "run_command" and r.conversation_id is None
    (c,) = fakec.calls("run")
    a = c["argv"]
    assert a == dcc.build_command(fakec.exe_path, MODEL)[1:]                                   # exactly the command the module builds
    assert a[0] == "-p" and a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--effort") + 1] == "high"
    assert a[a.index("--input-format") + 1] == "stream-json" and a[a.index("--output-format") + 1] == "stream-json" and "--verbose" in a
    assert a[a.index("--tools") + 1] == "Bash,Read,Write,Edit,Glob,Grep"                       # no web, no task tools, no notebook, no MCP
    for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in a, flag
    assert a[a.index("--setting-sources") + 1] == "" and a[a.index("--permission-mode") + 1] == "dontAsk"
    assert a[a.index("--append-system-prompt") + 1] == dcc.CONFINEMENT and "--system-prompt" not in a
    for never in ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "--bare", "--resume", "--continue", "--session-id", "--add-dir",
                  "--settings", "--mcp-config", "--plugin-dir", "--agents", "-r", "-c"):
        assert never not in a, never
    assert dcc.PROMPT not in a and not any(x.startswith("Read TASK.md") for x in a)               # the first message goes through stdin
    assert Path(c["cwd"]).resolve() == ws.root.resolve()
    assert "TASK.md" in fakec.prompts()[0] and (ws.root / "out" / "c01.json").is_file()
    assert seen and seen[-1]["steps"] == 3 and seen[-1]["out_files"] == 2 and seen[-1]["last_action"] == "run_command"
    lines = (ws.root.parent / "events.jsonl").read_text().splitlines()
    assert [json.loads(x)["type"] for x in lines].count("assistant") == 3 and json.loads(lines[-1])["type"] == "result"
    assert r.denials == [] and r.error_code is None and r.response == "done"


def test_the_permission_options_allow_only_the_workspace_and_the_three_helpers():
    allow = dcc.allow_rules(False)
    assert allow[0] == "Edit(./out/**)"                                                         # writes: only under out/
    assert all(x.startswith("Bash(./") or x == "Edit(./out/**)" for x in allow)
    for bare in ("Bash", "Edit", "Write", "Read", "Glob", "Grep", "WebFetch", "WebSearch", "Bash(*)", "Edit(*)", "Edit(**)", "Edit(./**)"):
        assert bare not in allow, bare                                                          # no tool is allowed everywhere
    cmds = {x.split("(", 1)[1].split(" ", 1)[0].rstrip(")") for x in allow if x.startswith("Bash(")}
    assert cmds == {"./check", "./defaults", "./still"}                                         # the three helper commands of the briefing, nothing else
    assert "Bash(./still *)" not in allow and "Bash(./check *)" not in allow                    # no free-form arguments for check and still
    deny = dcc.deny_rules(False)
    assert {"WebFetch", "WebSearch", "Bash(*..*)", "Bash(* /*)", "Bash(* ~*)", "Bash(*$(*)", "Bash(*--workspace*)"} <= set(deny)
    win = dcc.allow_rules(True)
    assert {"Bash(./check.cmd)", "Bash(.\\check.cmd)", "Bash(check.cmd --no-draw)", "Bash(.\\still.cmd --shot * -o look/*)"} <= set(win)
    assert any("\\" in d for d in dcc.deny_rules(True)) and not any("\\" in d for d in deny)


def test_helper_commands_of_the_briefing_are_the_ones_allowed():
    """skills/storyboard_draft/TASK.template.md section 7 names check, defaults and still; the workspace writes those wrappers."""
    tpl = (HERE.parents[1] / "skills" / "storyboard_draft" / "TASK.template.md").read_text(encoding="utf-8")
    assert "{{CHECK_CMD}}" in tpl and "{{DEFAULTS_CMD}}" in tpl and "{{STILL_CMD}}" in tpl
    assert set(dcc.HELPERS) == {"check", "defaults", "still"}
    src = (HERE.parents[1] / "bti" / "draft" / "workspace.py").read_text(encoding="utf-8")
    assert '("check", "bti.draft.check"), ("defaults", "bti.draft.defaults"), ("still", "bti.draft.still")' in src


# A model of the documented rule grammar (https://code.claude.com/docs/en/permissions: `*` matches any text, a trailing ` *` also matches
# the bare command, deny rules apply to any part of a compound command, every part must be allowed). The REAL decisions are in the recorded
# session: the test checks that this model gives the same answer for every command the real program was asked to run.
READ_ONLY = {"ls", "cat", "head", "tail", "wc", "pwd", "echo", "grep", "cd"}


def _matches(rule, cmd):
    spec = rule[len("Bash("):-1]
    rx = re.escape(spec[:-2]) + r"(?: .*)?" if spec.endswith(" *") and spec.count("*") == 1 else ".*".join(re.escape(p) for p in spec.split("*"))
    return re.fullmatch(rx, cmd, re.S) is not None


def decide(cmd, windows=False):
    rules_allow = [r for r in dcc.allow_rules(windows) if r.startswith("Bash(")]
    rules_deny = [r for r in dcc.deny_rules(windows) if r.startswith("Bash(")]
    parts = [p.strip() for p in re.split(r"&&|\|\||;|\||&(?!>)|\n", re.sub(r"\d?>&\d", "", cmd)) if p.strip()]
    if any(_matches(r, cmd) or any(_matches(r, p) for p in parts) for r in rules_deny):
        return "deny"
    if all(any(_matches(r, p) for r in rules_allow) or p.split()[0] in READ_ONLY for p in parts):
        return "allow"
    return "refuse"


def _session(path):
    uses, rows = {}, []
    for ln in (FIX / path).read_text(encoding="utf-8").splitlines():
        ev = json.loads(ln)
        if ev["type"] == "assistant":
            for b in ev["message"]["content"]:
                if b["type"] == "tool_use":
                    uses[b["id"]] = b
        elif ev["type"] == "user":
            for b in ev["message"]["content"]:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    rows.append((uses[b["tool_use_id"]], bool(b.get("is_error")), str(b.get("content"))))
    return rows


def test_the_rules_decide_like_the_real_program_did_for_every_recorded_command():
    rows = [r for r in _session("refusal_tightened.jsonl") if r[0]["name"] == "Bash"]
    assert len(rows) >= 14
    for use, is_err, text in rows:
        cmd = use["input"]["command"]
        got = decide(cmd)
        if is_err:
            assert "has been denied" in text and got in ("deny", "refuse"), (cmd, got)           # refused for real: the rules must not allow it
            assert ("don't ask mode" in text) == (got == "refuse"), (cmd, got, text[:80])         # not allowed -> "don't ask mode"; a deny rule -> its own sentence
        else:
            assert got == "allow", (cmd, got)                                                    # ran for real: the rules must allow it


def test_what_the_real_program_refused_without_our_deny_rules_and_what_it_let_through():
    """First real try (tests/draft/fixtures/claude/refusal_first_try.jsonl): `dontAsk` + only `Edit(./out/**)` and the helper rules."""
    rows = _session("refusal_first_try.jsonl")
    got = {(u["name"], json.dumps(u["input"], sort_keys=True)): is_err for u, is_err, _ in rows}
    refused = [(n, i) for (n, i), e in got.items() if e]
    allowed = [(n, i) for (n, i), e in got.items() if not e]
    assert [n for n, i in allowed] == ["Bash", "Bash"], allowed                                  # only `python3 --version` and `./check <folder>` ran
    assert "python3 --version" in allowed[0][1] and "./check /tmp/bti-outside" in allowed[1][1]
    names = {n for n, _ in refused}
    assert {"Read", "Write", "Grep", "Glob", "Bash"} <= names                                    # outside reads, writes, searches, cat, ls, redirects, sh -c: refused
    assert any("cat /tmp/bti-outside" in i for n, i in refused) and any("ls /tmp/bti-outside" in i for n, i in refused)
    # what it let through is exactly what the deny rules and the narrowed allow rules now close:
    assert decide("./check /tmp/bti-outside") in ("deny", "refuse") and decide("python3 --version") == "refuse"


def test_the_command_cannot_be_built_for_a_model_that_is_not_a_claude_id(fakec):
    for bad in ("agy:gemini-3.8-flash-high", "mock", "gemini-x", "claude:x@ultra"):
        with pytest.raises(DraftError) as e:
            dcc.build_command(fakec.exe_path, bad)
        assert e.value.code == "claude_model"


def test_default_model_is_the_settings_model_and_the_environment_is_a_whitelist(fakec, ws, monkeypatch):
    monkeypatch.setenv("SECRET_THING", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-LEAK")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "owner-token")
    monkeypatch.setattr("bti.settings.model_for", lambda role: MODEL if role == "draft" else "mock")
    dcc.run(ws.root, timeout=60, python="/the/python")
    c = fakec.calls("run")[0]
    assert c["argv"][c["argv"].index("--model") + 1] == "claude-opus-5-5"
    assert "SECRET_THING" not in c["env"] and "ANTHROPIC_API_KEY" not in c["env"] and "BTI_CLAUDE_BIN" not in c["env"]
    assert "BTI_PYTHON" in c["env"] and "PYTHONUTF8" in c["env"] and "CLAUDE_CODE_OAUTH_TOKEN" in c["env"]       # the owner's own login stays


def test_the_settings_default_of_the_other_runner_is_refused_not_run(fakec, ws):
    with pytest.raises(DraftError) as e:
        dcc.run(ws.root, timeout=5)                                                              # model_for("draft") is an agy: id
    assert e.value.code == "claude_model" and fakec.calls("run") == []                           # nothing was started


# ------------------------------------------------------------------------------------------------ the conversation
def test_repair_turn_is_written_to_the_same_process(fakec, ws):
    fakec.mode("repair")
    r = dcc.run(ws.root, model=MODEL, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "ok" and r.turns == 2 and r.repairs == 1
    p = fakec.prompts()
    assert len(p) == 2 and "found problems" in p[1] and "chapter c01, shot 2" in p[1]
    assert len(fakec.calls("run")) == 1                                                          # one process: the same conversation, no --resume


def test_repairs_stop_after_the_limit_and_leave_the_errors(fakec, ws):
    fakec.mode("bad")
    r = dcc.run(ws.root, model=MODEL, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "ok" and r.turns == 3 and r.repairs == 2
    res, _ = W.workspace_compile(ws.root, draw=False)
    assert res.errors


def test_a_program_that_leaves_between_turns_is_a_failure_not_a_restart(fakec, ws):
    fakec.mode("exits")
    r = dcc.run(ws.root, model=MODEL, timeout=60, check=checker(ws), max_repairs=2)
    assert r.status == "error" and r.error_code == "claude_no_result"
    assert len(fakec.calls("run")) == 1                                                          # nothing is kept on disk, so nothing is resumed


def test_the_user_line_is_ascii_json_of_the_recorded_input_shape():
    line = dcc.user_line("Đọc TASK.md")
    assert line.endswith("\n") and line.isascii()
    ev = json.loads(line)
    assert ev == {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Đọc TASK.md"}]}}


def test_a_conversation_id_of_another_runner_is_ignored(fakec, ws):
    r = dcc.run(ws.root, model=MODEL, timeout=60, conversation_id="conv-from-agy")
    assert r.status == "ok" and r.conversation_id is None
    assert "conv-from-agy" not in json.dumps(fakec.calls())


# ------------------------------------------------------------------------------------------------ failures
@pytest.mark.parametrize("mode,code", [("error", "claude_error"), ("auth", "claude_auth"), ("stderr_auth", "claude_auth"), ("wrong_model", "claude_model"),
                                       ("noresult", "claude_no_result")])
def test_error_results_get_their_own_code(fakec, ws, mode, code):
    fakec.mode(mode)
    r = dcc.run(ws.root, model=MODEL, timeout=30)
    assert r.status == "error" and r.error_code == code, (r.error_code, r.error_message)
    assert len(fakec.calls("run")) == 1


# ---- followups item 2: Claude Code too old for the model (the text of a real call on the server: fixtures/claude/too_old.txt)
TOO_OLD = (SCRIPT_FIX / "too_old.txt").read_text(encoding="utf-8").strip()
TOO_OLD_SENTENCE = ("Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên, đang là 2.1.233). "
                    "Chạy `claude update` trên máy chủ rồi thử lại.")


@pytest.mark.parametrize("mode,status", [("error_text", None), ("error_text", 404), ("stderr_text", None)])
def test_claude_code_too_old_is_its_own_code_in_the_agent_run(fakec, ws, mode, status):
    fakec.mode(mode, text=TOO_OLD, status=status)
    r = dcc.run(ws.root, model=MODEL, timeout=30)
    assert r.status == "error" and r.error_code == "claude_outdated", (r.error_code, r.error_message)
    assert r.error_message == TOO_OLD_SENTENCE and not getattr(r, "retry_after_seconds", None)
    assert len(fakec.calls("run")) == 1


def test_the_usage_limit_reset_time_is_kept_from_the_text(fakec, ws):
    fakec.mode("quota")                                  # NOT a recording: `You've hit your session limit · resets 7pm (Asia/Saigon)`
    r = dcc.run(ws.root, model=MODEL, timeout=30)
    assert r.status == "error" and r.error_code == "claude_rate_limit"
    assert r.retry_after_seconds is not None and 0 < r.retry_after_seconds <= 86400
    assert len(fakec.calls("run")) == 1                  # a rate limit is never retried inside the run


def test_the_usage_limit_reset_time_is_exact_from_the_rate_limit_event(fakec, ws):
    fakec.mode("quota_event")                            # the recorded `rate_limit_event` shape with status rejected (not a recording of a real refusal)
    r = dcc.run(ws.root, model=MODEL, timeout=30)
    assert r.error_code == "claude_rate_limit" and abs(r.retry_after_seconds - 3600) <= 3


def test_a_refused_tool_is_reported_and_the_run_still_finishes_the_recorded_session(fakec, ws):
    fakec.mode("replay", replay="refusal_tightened.jsonl")
    r = dcc.run(ws.root, model=MODEL, timeout=60)
    assert r.status == "ok" and r.error_code is None
    assert len(r.denials) == 9 and {d["tool"] for d in r.denials} == {"Bash"}                    # once each, though the stream tells it twice
    assert r.steps == 21 and r.last_action == "write_to_file"                                    # 19 attempts, the Edit and the notes file
    fakec.mode("replay", replay="refusal_first_try.jsonl")
    r = dcc.run(ws.root, model=MODEL, timeout=60)
    assert r.status == "ok" and len(r.denials) == 17 and {"Read", "Write", "Grep", "Glob", "Bash"} <= {d["tool"] for d in r.denials}


def test_a_picture_the_agent_looked_at_is_an_image_block_in_a_tool_result(fakec, ws):
    """Real call 10: Read of a PNG gives a `user` event whose tool_result content is `[{"type": "image", "source": {"type": "base64", ...}}]`
    (the stored fixture has the data cut). The run goes on; the transcript line of a real, big picture is shortened."""
    fakec.mode("replay", replay="image_read.jsonl")
    r = dcc.run(ws.root, model=MODEL, timeout=60, transcript_path=ws.root.parent / "ev.jsonl")
    assert r.status == "ok" and r.steps == 2 and r.last_action == "write_to_file" and r.denials == [] and "done" in r.response
    kinds = [b["content"][0]["type"] for ln in (FIX / "image_read.jsonl").read_text(encoding="utf-8").splitlines() for b in json.loads(ln).get("message", {}).get("content", [])
             if isinstance(b, dict) and b.get("type") == "tool_result" and isinstance(b.get("content"), list)]
    assert kinds == ["image"]


def test_the_recorded_real_session_is_understood(fakec, ws):
    fakec.mode("replay", replay="agent_two_turns.jsonl")
    seen = []
    r = dcc.run(ws.root, model=MODEL, timeout=60, on_progress=seen.append)
    assert r.status == "ok" and r.response == "done" and r.steps == 3 and r.last_action == "run_command" and r.denials == []


def test_tampering_is_detected(fakec, ws, proj):
    fakec.mode("tamper")
    r = dcc.run(ws.root, model=MODEL, timeout=60, guard=Guard(proj, extra=lambda: None, repo_root=proj.parent))
    assert r.status == "tampered" and r.tampered == ["changed timing.json"]


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


def test_time_out_kills_the_process_tree_and_keeps_the_partial_result(fakec, ws):
    fakec.mode("slow")
    t0 = time.time()
    r = dcc.run(ws.root, model=MODEL, timeout=2.5, check=None)
    assert r.status == "timeout" and r.error_code == "claude_timeout" and time.time() - t0 < 25
    time.sleep(0.5)
    for pid in [int(x) for x in (fakec.dir / "pids").read_text().split()]:
        assert not _alive(pid), pid
    assert (ws.root / "out" / "c01.json").is_file()                                              # what was written before is still there
    assert not agy.LOCK.locked()


def test_cancel_kills_the_process_tree(fakec, ws):
    fakec.mode("slow")
    ev = threading.Event()
    threading.Timer(2.0, ev.set).start()
    r = dcc.run(ws.root, model=MODEL, timeout=60, cancel=ev)
    assert r.status == "cancelled"
    time.sleep(0.5)
    for pid in [int(x) for x in (fakec.dir / "pids").read_text().split()]:
        assert not _alive(pid)
    assert not agy.LOCK.locked()


def test_missing_old_busy_and_the_safety_switch(ws, monkeypatch, fakec):
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    with pytest.raises(DraftError) as e:
        dcc.run(ws.root, model=MODEL, timeout=5)
    assert e.value.code == "claude_missing"
    monkeypatch.setenv("BTI_CLAUDE_BIN", fakec.exe_path)
    fakec.mode("old_cli")
    with pytest.raises(DraftError) as e:
        dcc.run(ws.root, model=MODEL, timeout=5)
    assert e.value.code == "claude_config" and fakec.calls("run") == []
    fakec.mode("ok")
    cc._HELP_OK.clear()
    assert agy.LOCK.acquire(blocking=False)                                                      # one run at a time, whichever runner
    try:
        with pytest.raises(DraftError) as e:
            dcc.run(ws.root, model=MODEL, timeout=5)
        assert e.value.code == "agy_busy"
    finally:
        agy.LOCK.release()
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    with pytest.raises(DraftError) as e:
        dcc.run(ws.root, model=MODEL, timeout=5)
    assert e.value.code == "real_models_off"


def test_the_agent_run_needs_the_same_options_as_the_single_call_plus_its_own(fakec):
    assert set(cc.REQUIRED_FLAGS) < set(dcc.REQUIRED_FLAGS)
    assert {"--input-format", "--verbose", "--allowedTools", "--disallowedTools", "--append-system-prompt"} <= set(dcc.REQUIRED_FLAGS)


def test_a_transcript_line_of_a_picture_is_shortened():
    big = json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": [{"type": "image", "source": {"data": "A" * 400000}}]}]}})
    out = dcc._compact(big)
    assert len(out) < 2000 and "characters left out" in out and json.loads(out)["type"] == "user"
    small = json.dumps({"type": "result"})
    assert dcc._compact(small) == small


# ------------------------------------------------------------------------------------------------ the owner's sentences (bti/draft/run.py)
def test_every_claude_code_is_a_sentence_for_the_owner_and_the_signed_out_one_is_exact():
    codes = ["claude_missing", "claude_auth", "claude_rate_limit", "claude_model", "claude_config", "claude_error", "claude_no_result", "claude_timeout"]
    for c in codes:
        assert R.vi(c) == R.VI[c] and re.search(r"[ạảãàáâăèéêìíòóôõùúýđ]", R.VI[c])            # Vietnamese, not a bare code
    assert R.VI["claude_auth"] == OWNER_SIGNED_OUT
    assert "claude auth login" in R.VI["claude_missing"]
    assert R.rate_limit_sentence("claude_rate_limit", 16200).startswith("Hạn mức của gói Claude Code đã hết. Thử lại sau 4 giờ 30 phút (khoảng ")
    assert R.rate_limit_sentence("claude_rate_limit", None) == R.VI["claude_rate_limit"]
    assert R.rate_limit_sentence("agy_rate_limit", 176).startswith("Hạn mức của gói Antigravity đã hết. Thử lại sau 2 phút 56 giây")      # the other runner is unchanged


def test_claude_outdated_sentence_for_the_owner_with_and_without_the_versions():
    assert R.vi("claude_outdated") == R.VI["claude_outdated"] == "Claude Code trên máy chủ quá cũ cho mô hình này. Chạy `claude update` trên máy chủ rồi thử lại."
    assert R.vi("claude_outdated", TOO_OLD_SENTENCE) == TOO_OLD_SENTENCE                  # the runner's sentence names the versions the answer stated
    assert R.vi("claude_outdated", "Claude Code 2.1.233 does not support this model") == R.VI["claude_outdated"]      # any other text never replaces ours
    assert R.rate_limit_sentence("claude_outdated", None, TOO_OLD_SENTENCE) == TOO_OLD_SENTENCE
    assert R.rate_limit_sentence("claude_outdated", None) == R.VI["claude_outdated"]
    assert "claude_outdated" not in R.RATE_LIMIT_CODES                                   # not a quota
    assert "hết hạn mức" not in R.VI["claude_outdated"] and "mô hình khác" not in R.VI["claude_outdated"]


def test_the_page_has_the_same_codes():
    text = (HERE.parents[1] / "bti" / "editor" / "static" / "js" / "errmsg.js").read_text(encoding="utf-8")
    for c in ("claude_missing", "claude_auth", "claude_rate_limit", "claude_model", "claude_config", "claude_outdated", "claude_error", "claude_no_result", "claude_timeout"):
        assert re.search(r"\b%s:" % c, text), c
    assert OWNER_SIGNED_OUT in text


def test_provider_codes_for_a_single_call_error_name_the_runner():
    e = cc.classify("Not logged in · Please run /login")
    assert R.provider_code(e, MODEL) == "claude_auth"
    from bti.script.providers import ProviderError
    assert R.provider_code(ProviderError("auth", "x"), "agy:x") == "agy_auth" and R.provider_code(ProviderError("rate_limit", "x"), "mock") == "agy_rate_limit"
    assert R.provider_code(ProviderError("real_models_off", "x"), MODEL) == "real_models_off"


# ------------------------------------------------------------------------------------------------ the job (bti/draft/run.py)
@pytest.fixture()
def mgr(proj):
    return LongJobManager(projects_root=proj.parent)


def finish(mgr, rec, timeout=120):
    j = mgr.wait(rec, timeout=timeout)
    assert j is not None and j["state"] not in ("queued", "running", "waiting"), j
    return j


def test_a_claude_model_picks_the_claude_runner_end_to_end(proj, mgr, fakec):
    rec = R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["error_code"], j["log_tail"])
    doc = json.loads((proj / "proposals" / (j["result"]["proposal_id"] + ".json")).read_text(encoding="utf-8"))
    assert doc["author"] == "agent:claude:claude-opus-5-5@high" and doc["summary"] == "Fake agent summary"
    assert [e for e in doc["issues_left"] if e["level"] == "error"] == []
    run_dir = next(p for p in (proj / "cache" / "draft").iterdir() if p.is_dir())
    assert (run_dir / "events.jsonl").is_file() and (run_dir / "out" / "c01.json").is_file()
    assert fakec.calls("run")[0]["argv"][0] == "-p" and not [c for c in fakec.calls() if "--conversation" in c["argv"]]


def test_an_agy_model_still_picks_agy(proj, mgr, fakec, monkeypatch):
    monkeypatch.setenv("BTI_AGY_BIN", "")
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="agy", model="gemini-x", manager=mgr)
    assert e.value.code == "agy_missing" and fakec.calls() == []                               # Claude Code was not asked about


def test_start_is_refused_in_words_when_claude_is_missing_or_signed_out(proj, mgr, fakec, monkeypatch):
    fakec.mode("signed_out")
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr)
    assert e.value.code == "claude_auth" and R.vi(e.value.code) == OWNER_SIGNED_OUT
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr)
    assert e.value.code == "claude_missing"


def test_the_model_name_of_a_claude_id_passes_the_name_check_and_a_malformed_one_is_refused(proj, mgr):
    assert R.MODEL_RE.fullmatch(MODEL) and R.MODEL_RE.fullmatch("agy:gemini-x") and not R.MODEL_RE.fullmatch("claude:x;ls@high")
    assert not R._bad_model_name(MODEL) and not R._bad_model_name("gemini-x") and not R._bad_model_name(None)
    for bad in ("claude:x@ultra", "claude:claude-opus-5-5", "claude:x;ls@high"):
        assert R._bad_model_name(bad), bad
        with pytest.raises(DraftError) as e:
            R.start(proj.name, proj, provider="agy", model=bad, manager=mgr)
        assert e.value.code == "bad_model"


@pytest.mark.parametrize("mode,code", [("auth", "claude_auth"), ("wrong_model", "claude_model"), ("error", "claude_error"), ("noresult", "claude_no_result")])
def test_claude_error_codes_reach_the_job(proj, mgr, fakec, mode, code):
    fakec.mode(mode)
    j = finish(mgr, R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == code, (j["error"], j["error_code"])
    assert j["error"] == R.vi(code)
    if code == "claude_auth":
        assert j["error"] == OWNER_SIGNED_OUT


@pytest.mark.parametrize("mode,status", [("error_text", None), ("error_text", 404), ("stderr_text", None)])
def test_claude_outdated_reaches_the_job_with_the_versions_and_is_not_a_quota(proj, mgr, fakec, mode, status):
    fakec.mode(mode, text=TOO_OLD, status=status)
    j = finish(mgr, R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == "claude_outdated", (j["error"], j["error_code"])
    assert j["error"] == TOO_OLD_SENTENCE
    assert not (j.get("meta") or {}).get("retry_after_seconds") and "hết hạn mức" not in j["error"]


def test_the_usage_limit_reaches_the_job_with_the_time(proj, mgr, fakec):
    fakec.mode("quota_event")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", model=MODEL, manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == "claude_rate_limit"
    assert re.search(r"Hạn mức của gói Claude Code đã hết\. Thử lại sau (1 giờ|59 phút)", j["error"]), j["error"]
    assert abs(j["meta"]["retry_after_seconds"] - 3600) <= 3 and re.fullmatch(r"\d\d:\d\d|\d\d/\d\d \d\d:\d\d", j["meta"]["retry_at"])


# ------------------------------------------------------------------------------------------------ the edit routes with a Claude Code model
from test_edit_routes_e2e import env, sb_proj, why  # noqa: E402,F401  (the app, the saved storyboard and the helpers of the edit route tests)


def test_fast_edit_runs_through_claude_code_when_the_request_names_it(env, fakec):
    ids = env.content_ids("c01")[:2]
    fakec.mode("ok", answer=env.edit_answer(ids, {ids[0]: {"technique": "CAM-03"}, ids[1]: {"note": "slow look at the mirror"}}))
    job, turn = env.run_edit("zoom chậm hơn vào hai cảnh đầu", ids, mode="fast", model=MODEL)
    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["path"] == "fast" and turn["model"] == MODEL, turn
    (c,) = fakec.calls("run")
    a = c["argv"]
    assert a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--effort") + 1] == "high" and a[a.index("--tools") + 1] == ""
    assert a[a.index("--system-prompt") + 1].startswith("You edit a video project for its owner") and "--allowedTools" not in a



def test_deep_edit_runs_through_claude_code_and_keeps_no_conversation(env, fakec):
    ids = env.content_ids("c01")
    before = env.saved()
    env.deep_cfg(fakec.dir, {ids[0]: {"note": "slower push-in"}},
                 notes_json={"summary": "Đã làm chậm cú đẩy máy ở cảnh đầu.", "changes": [{"shot": ids[0], "what": "Đẩy máy chậm hơn."}]})
    job, turn = env.run_edit("làm chậm cú đẩy máy trong chương này", chapter="c01", mode="deep", model=MODEL)
    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["path"] == "deep" and turn["summary"] == "Đã làm chậm cú đẩy máy ở cảnh đầu."
    assert turn["conversation_id"] is None                                         # a Claude Code run keeps no session
    a = fakec.calls("run")[0]["argv"]
    assert "--input-format" in a and "--dangerously-skip-permissions" not in a and "--resume" not in a
    after = env.saved()
    b, n = {s["id"]: s for s in before["shots"]}, {s["id"]: s for s in after["shots"]}
    assert [sid for sid in n if sid not in b] and ids[0] not in n                    # the slow path replaces the shot (a batch of replace_range): a new id
    assert all(n[sid] == b[sid] for sid in n if sid in b)
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200 and env.saved() == before


def test_deep_edit_after_an_agy_turn_does_not_hand_its_conversation_to_claude(env, fakec):
    from bti.draft.thread import append_turn
    ids = env.content_ids("c01")
    append_turn(env.pdir, {"id": "t_old", "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "instruction": "trước đó", "status": "applied", "conversation_id": "conv-from-agy",
                           "summary": "Đã sửa.", "scope": {"kind": "all"}, "model": "agy:x", "path": "deep"})
    env.deep_cfg(fakec.dir, {ids[0]: {"note": "x"}})
    job, turn = env.run_edit("sửa nữa", chapter="c01", mode="deep", model=MODEL, followup=True)
    assert job["state"] == "done", why(job)
    assert "conv-from-agy" not in json.dumps(fakec.calls()) and turn["conversation_id"] is None


def test_the_usage_limit_reaches_the_turn_and_the_job_on_the_deep_path_with_claude(env, fakec):
    ids = env.content_ids("c01")
    env.deep_cfg(fakec.dir, {ids[0]: {"note": "never applied"}})
    fakec.mode("quota_event")                       # NOT a recording: the recorded rate_limit_event shape, status rejected, resets in an hour
    rev0 = env.rev()
    job, turn = env.run_edit("sửa", chapter="c01", mode="deep", model=MODEL)
    assert job["state"] == "error" and job["error_code"] == "claude_rate_limit", why(job)
    assert "Claude Code" in job["error"] and re.search(r"Thử lại sau (1 giờ|59 phút)", job["error"])
    assert abs(job["meta"]["retry_after_seconds"] - 3600) <= 3
    assert turn["status"] == "failed" and turn["error"] == "claude_rate_limit" and abs(turn["retry_after_seconds"] - 3600) <= 3
    assert len(fakec.calls("run")) == 1 and env.rev() == rev0                  # never retried inside the job, nothing applied


def test_fast_edit_quota_and_signed_out_are_told_in_words(env, fakec):
    ids = env.content_ids("c01")[:1]
    fakec.mode("error", text="You've hit your session limit · resets in 2 hr", status=429)
    job, turn = env.run_edit("đổi", ids, mode="fast", model=MODEL)
    assert job["state"] == "error" and job["error_code"] == "claude_rate_limit" and "2 giờ" in job["error"], why(job)
    assert turn["status"] == "failed" and turn["error"] == "claude_rate_limit" and turn["retry_after_seconds"] == 2 * 3600
    fakec.mode("not_signed_in")
    job, turn = env.run_edit("đổi", ids, mode="fast", model=MODEL)
    assert job["error_code"] == "claude_auth" and job["error"] == OWNER_SIGNED_OUT and turn["error"] == "claude_auth"


def test_claude_outdated_is_told_in_words_on_the_fast_and_the_deep_path(env, fakec):
    ids = env.content_ids("c01")[:1]
    fakec.mode("error", text=TOO_OLD, status=404)                  # the single call (fast edit): a status that would otherwise read "unknown model"
    job, turn = env.run_edit("đổi", ids, mode="fast", model=MODEL)
    assert job["state"] == "error" and job["error_code"] == "claude_outdated" and job["error"] == TOO_OLD_SENTENCE, why(job)
    assert turn["status"] == "failed" and turn["error"] == "claude_outdated" and turn["summary"] == TOO_OLD_SENTENCE and not turn.get("retry_after_seconds")
    env.deep_cfg(fakec.dir, {ids[0]: {"note": "never applied"}})
    fakec.mode("error_text", text=TOO_OLD, status=None)            # the agent in a folder (deep edit)
    job, turn = env.run_edit("sửa", chapter="c01", mode="deep", model=MODEL)
    assert job["state"] == "error" and job["error_code"] == "claude_outdated" and job["error"] == TOO_OLD_SENTENCE, why(job)
    assert turn["status"] == "failed" and turn["error"] == "claude_outdated" and turn["summary"] == TOO_OLD_SENTENCE


def test_deep_edit_with_claude_missing_or_signed_out_is_refused_before_a_turn_exists(env, fakec, monkeypatch):
    fakec.mode("signed_out")
    r = env.post_edit("sửa", chapter="c01", mode="deep", model=MODEL)
    assert r.status_code in (409, 422) and r.json()["code"] == "claude_auth", r.text
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    models_mod.reset_cache()
    r = env.post_edit("sửa", chapter="c01", mode="deep", model=MODEL)
    assert r.status_code in (409, 422) and r.json()["code"] == "claude_missing", r.text
    assert env.client.get(env.u("/draft/thread")).json()["turns"] == []
