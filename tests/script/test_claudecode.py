"""The Claude Code provider (`claude -p`), against a FAKE `claude` executable on a temporary path. No network, no real Claude Code, no
model call. The fake (tests/script/fake_claude.py) replays the output shapes recorded from the real program on 2026-11-18
(tests/script/fixtures/claude/); the usage-limit answers are NOT recordings (see the fake's docstring)."""
import datetime
import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

import pytest

from bti.script import generate, models as models_mod
from bti.script.providers import ProviderError, claudecode as cc, get_provider
from bti.script.runner import ScriptJobs

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "claude"
DRAFT_FIX = HERE.parent / "draft" / "fixtures" / "claude"
SPEC = {"id": "claude:claude-opus-5-5@high", "provider": "claudecode", "model": "claude-opus-5-5", "effort": "high"}
OWNER_SIGNED_OUT = "Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại."


@pytest.fixture()
def fake(tmp_path, monkeypatch):
    d = tmp_path / "bin"
    d.mkdir()
    src = (HERE / "fake_claude.py").read_text(encoding="utf-8").replace('"@@FIX_SCRIPT@@"', repr(str(FIX))).replace('"@@FIX_DRAFT@@"', repr(str(DRAFT_FIX)))
    script = d / "fake_claude.py"
    script.write_text(src, encoding="utf-8")
    if os.name == "nt":                                                             # no shebang there: a .cmd launcher
        exe = d / "claude.cmd"
        exe.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        exe = d / "claude"
        exe.write_text(f"#!{sys.executable}\n" + src, encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    (d / "cfg.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BTI_CLAUDE_BIN", str(exe))
    monkeypatch.delenv("BTI_NO_REAL_MODELS", raising=False)
    cc._HELP_OK.clear()
    models_mod.reset_cache()

    class F:
        dir = d

        def mode(self, m, **cfg):
            (d / "mode").write_text(m)
            c = json.loads((d / "cfg.json").read_text(encoding="utf-8"))
            c.update(cfg)
            (d / "cfg.json").write_text(json.dumps(c), encoding="utf-8")

        def calls(self, kind=None):
            p = d / "calls.jsonl"
            rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []
            if kind == "call":                                                      # the model calls only (not --help, not auth)
                rows = [r for r in rows if r["argv"][:1] == ["-p"]]
            return rows
    f = F()
    f.mode("ok")
    return f


def call(**kw):
    return get_provider("claudecode")(SPEC, "SYS TEXT", "USER TEXT", timeout=kw.pop("timeout", 20), **kw)


# ------------------------------------------------------------------------------------------------ the id family
@pytest.mark.parametrize("model_id,parsed", [("claude:claude-opus-5-5@high", ("claude-opus-5-5", "high")), ("claude:haiku@low", ("haiku", "low")),
                                             ("claude:claude-sonnet-4.5@xhigh", ("claude-sonnet-4.5", "xhigh")), ("claude:opus@max", ("opus", "max")),
                                             ("claude:a@medium", ("a", "medium"))])
def test_the_family_parser_accepts_model_and_effort(model_id, parsed):
    assert cc.parse_model_id(model_id) == parsed and cc.is_claude_id(model_id)
    assert cc.make_model_id(*parsed) == model_id


@pytest.mark.parametrize("bad", ["claude:claude-opus-5-5", "claude:@high", "claude:x@ultra", "claude: x@high", "claude:x y@high", "claude:-x@high",
                                 "agy:claude@high", "claude:x@high ", "Claude:x@high", "claude:x@high;ls", "claude:../x@high", "", None, 5, "mock"])
def test_the_family_parser_refuses_everything_else(bad):
    assert cc.parse_model_id(bad) is None and not cc.is_claude_id(bad)


# ------------------------------------------------------------------------------------------------ the command line
def test_the_command_keeps_the_signed_in_users_own_setup_out_and_tools_off():
    cmd = cc.build_command("/x/claude", "claude-opus-5-5", "high", "SYS TEXT")
    assert cmd[:2] == ["/x/claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5" and cmd[cmd.index("--effort") + 1] == "high"
    assert cmd[cmd.index("--output-format") + 1] == "json" and "--input-format" not in cmd and "--verbose" not in cmd
    assert cmd[cmd.index("--tools") + 1] == ""                                       # no built-in tool at all
    for flag in ("--safe-mode", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in cmd, flag
    assert cmd[cmd.index("--setting-sources") + 1] == ""                             # no settings file of the user, the project or the folder
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--system-prompt") + 1] == "SYS TEXT" and "--append-system-prompt" not in cmd
    for never in ("--dangerously-skip-permissions", "--allow-dangerously-skip-permissions", "--bare", "--resume", "--continue", "--mcp-config",
                  "--add-dir", "--allowedTools", "--plugin-dir", "--settings", "--agents", "-r", "-c"):
        assert never not in cmd, never
    assert cc.build_command("/x/claude", "m", "low", None).count("--system-prompt") == 0


def test_the_isolation_options_exist_in_both_versions_checked():
    """The options both Claude Code 2.1.233 (the server) and 2.1.327 (the Mac) list in `--help` (read on 2026-11-18)."""
    for flag in cc.REQUIRED_FLAGS:
        assert flag.startswith("--")
    assert {"--safe-mode", "--setting-sources", "--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence", "--tools",
            "--permission-mode", "--system-prompt", "--output-format", "--model", "--effort"} <= set(cc.REQUIRED_FLAGS)


def test_success_and_what_the_program_was_given(fake, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-LEAK")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://elsewhere")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake.dir / "cfgdir"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-LEAK")
    assert call().startswith("FINAL SCRIPT")
    (c,) = fake.calls("call")
    a = c["argv"]
    assert a[a.index("--model") + 1] == "claude-opus-5-5" and a[a.index("--effort") + 1] == "high"
    assert a[a.index("--system-prompt") + 1] == "SYS TEXT" and a[a.index("--tools") + 1] == ""
    assert a == cc.build_command("claude", "claude-opus-5-5", "high", "SYS TEXT")[1:]          # exactly the command the module builds
    assert not any("USER TEXT" in x for x in a)                                      # the prompt is never an argument
    assert "ANTHROPIC_API_KEY" not in c["env"] and "ANTHROPIC_BASE_URL" not in c["env"] and "OPENROUTER_API_KEY" not in c["env"]
    assert "CLAUDE_CONFIG_DIR" in c["env"] and "PATH" in c["env"] and "BTI_CLAUDE_BIN" not in c["env"]
    assert c["stdin_head"] == "USER TEXT" and c["stdin_len"] == len("USER TEXT")      # no wrapper text is added to the owner's prompt


def test_runs_in_an_empty_temp_folder_outside_the_repo_and_removes_it(fake):
    call()
    cwd = fake.calls("call")[0]["cwd"]
    repo = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    assert not os.path.realpath(cwd).startswith(repo) and "bti-claude-" in cwd
    assert not os.path.exists(cwd)                                                   # removed afterwards


def test_the_recorded_answer_of_the_real_program_is_read():
    """tests/script/fixtures/claude/single_ok.json is the real `--output-format json` answer of the real program (`--model haiku`)."""
    res = cc.parse_result((FIX / "single_ok.json").read_text(encoding="utf-8"))
    assert res["type"] == "result" and res["subtype"] == "success" and res["is_error"] is False and res["result"] == "Hello!"
    assert res["num_turns"] == 1 and res["permission_denials"] == []
    assert cc.parse_result("") is None and cc.parse_result("not json") is None and cc.parse_result("[]") is None


def test_a_build_that_prints_the_event_list_is_read_too(fake):
    fake.mode("array")
    assert call().startswith("FINAL SCRIPT")


def test_the_system_text_that_cmd_exe_would_misread_goes_in_with_the_task(fake, monkeypatch):
    monkeypatch.setattr(cc, "is_shim", lambda exe: True)                              # a Windows .cmd shim
    get_provider("claudecode")(SPEC, 'Say "hi" 100% & more', "USER TEXT", timeout=20)
    (c,) = fake.calls("call")
    assert "--system-prompt" not in c["argv"]
    assert c["stdin_head"].startswith('Say "hi" 100%') and c["stdin_tail"].endswith("USER TEXT")
    call()                                                                            # a plain system text stays a system prompt
    assert "--system-prompt" in fake.calls("call")[1]["argv"]


# ------------------------------------------------------------------------------------------------ failures
def test_not_signed_in_is_an_auth_error_with_the_owners_sentence(fake):
    fake.mode("not_signed_in")                                        # the real answer of a program nobody is signed in to
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "auth" and e.value.message == OWNER_SIGNED_OUT and e.value.code == "claude_auth"


def test_a_refused_model_name_is_a_config_error(fake):
    fake.mode("wrong_model")                                          # the real answer for a model name that does not exist
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "config" and e.value.code == "claude_model" and "tên mô hình" in e.value.message


@pytest.mark.parametrize("text,status,kind,code", [
    ("You've hit your session limit · resets 7pm (Asia/Saigon)", 429, "rate_limit", "claude_rate_limit"),
    ("You've hit your weekly limit · resets Nov 25 at 3pm (Asia/Saigon)", 429, "rate_limit", "claude_rate_limit"),
    ("You've hit your Opus limit", None, "rate_limit", "claude_rate_limit"),
    ("Claude AI usage limit reached|1795100400", None, "rate_limit", "claude_rate_limit"),
    ("Server is temporarily limiting requests", 429, "rate_limit", "claude_rate_limit"),
    ("Invalid API key · Please run /login", 401, "auth", "claude_auth"),
    ("OAuth token has expired", None, "auth", "claude_auth"),
    ("API Error: 404 not_found_error model: zzz", 404, "config", "claude_model"),
    ("There's an issue with the selected model (zzz). It may not exist or you may not have access to it.", None, "config", "claude_model"),
    ("API Error: Repeated 529 Overloaded errors", 529, "http", "claude_error"),
    ("Something nobody planned for", 500, "http", "claude_error"),
])
def test_failure_texts_map_to_the_known_kinds(fake, text, status, kind, code):
    """The usage-limit wording is the documented one (not a recording): see the fake's docstring."""
    fake.mode("error", text=text, status=status)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == kind and e.value.code == code, e.value.message
    assert len(fake.calls("call")) == 1                                              # a failure is never retried inside the call


# ---- followups item 2: Claude Code too old for the model (the text of a real call on the server: fixtures/claude/too_old.txt)
TOO_OLD = (FIX / "too_old.txt").read_text(encoding="utf-8").strip()
TOO_OLD_SENTENCE = ("Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên, đang là 2.1.233). "
                    "Chạy `claude update` trên máy chủ rồi thử lại.")


@pytest.mark.parametrize("how,status", [("error", None), ("error", 404), ("error", 400), ("stderr_only", None)])
def test_claude_code_too_old_for_the_model_has_its_own_code_and_sentence(fake, how, status):
    """Whatever the program frames it as (a result, with any status, or a plain line), it is `claude_outdated`, kind config, never the
    unknown-model code (status 404) and never a quota."""
    fake.mode(how, text=TOO_OLD, status=status)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "config" and e.value.code == "claude_outdated", (e.value.code, e.value.message)
    assert e.value.message == TOO_OLD_SENTENCE
    assert "hết hạn mức" not in e.value.message and "mô hình khác" not in e.value.message and "Hạn mức" not in e.value.message
    assert len(fake.calls("call")) == 1                                              # never retried inside the call


@pytest.mark.parametrize("text,sentence", [
    ("Claude Code does not support this model; version 2.1.280 or newer is required. Run 'claude update'",
     "Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên). Chạy `claude update` trên máy chủ rồi thử lại."),
    ("Claude Code 2.1.233 does not support this model. Run 'claude update'",
     "Claude Code trên máy chủ quá cũ cho mô hình này (đang là 2.1.233). Chạy `claude update` trên máy chủ rồi thử lại."),
    ("This model requires Claude Code 2.1.280 or newer",
     "Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên). Chạy `claude update` trên máy chủ rồi thử lại."),
])
def test_a_version_the_answer_does_not_state_is_left_out(text, sentence):
    e = cc.classify(text, None, None)
    assert e.code == "claude_outdated" and e.kind == "config" and e.message == sentence


@pytest.mark.parametrize("text,code", [
    ("This account does not support this model", "claude_error"),                  # no mention of Claude Code, a version or `claude update`: not ours to call "too old"
    ("There's an issue with the selected model (zzz). It may not exist or you may not have access to it.", "claude_model"),
    ("You've hit your session limit · resets 7pm (Asia/Saigon)", "claude_rate_limit"),
    ("Not logged in · Please run /login", "claude_auth"),
])
def test_only_the_too_old_answer_gets_the_new_code(text, code):
    assert cc.classify(text, None, None).code == code


def test_the_usage_limit_names_the_time_it_opens_again(fake):
    fake.mode("error", text="You've hit your session limit · resets in 4 hr 30 min", status=429)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "rate_limit" and e.value.retry_after_seconds == 4 * 3600 + 30 * 60
    assert "Thử lại sau 4 giờ 30 phút" in e.value.message and "Claude Code" in e.value.message


def test_a_usage_limit_without_a_time_says_so_without_inventing_one(fake):
    fake.mode("error", text="You've hit your limit", status=429)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "rate_limit" and e.value.retry_after_seconds is None and "Thử lại sau" not in e.value.message


@pytest.mark.parametrize("mode,kind", [("denials", "http"), ("two_turns", "http"), ("writes", "http"), ("empty", "empty"), ("garbage", "http"),
                                       ("silent_fail", "empty")])
def test_output_that_cannot_be_trusted_is_refused(fake, mode, kind):
    fake.mode(mode)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == kind, e.value.message
    if mode == "denials":
        assert "công cụ" in e.value.message
    if mode == "two_turns":
        assert "lượt" in e.value.message
    if mode == "writes":
        assert "tệp" in e.value.message


def test_a_failure_written_only_on_stderr_is_still_classified(fake):
    fake.mode("stderr_only", text="Not logged in · Please run /login")
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "auth"


def test_an_old_build_without_the_isolation_options_is_refused_and_never_run(fake):
    fake.mode("old_cli")
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "config" and "--safe-mode" in e.value.message and "claude update" in e.value.message
    assert fake.calls("call") == []                                                  # the prompt never reached it


def test_a_missing_program_and_a_bad_spec_and_the_safety_switch(fake, monkeypatch):
    with pytest.raises(ProviderError) as e:
        get_provider("claudecode")({"model": "x;ls", "effort": "high"}, "S", "U", timeout=5)
    assert e.value.kind == "config" and e.value.code == "claude_model"
    with pytest.raises(ProviderError) as e:
        get_provider("claudecode")({"model": "x", "effort": "ultra"}, "S", "U", timeout=5)
    assert e.value.kind == "config"
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "config" and e.value.code == "claude_missing" and "claude auth login" in e.value.message
    monkeypatch.setenv("BTI_CLAUDE_BIN", str(fake.dir / ("claude.cmd" if os.name == "nt" else "claude")))
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind == "real_models_off" and fake.calls() == []


# ------------------------------------------------------------------------------------------------ the process
def _pids(fake):
    p = fake.dir / "pids"
    for _ in range(100):
        if p.is_file() and p.read_text().strip():
            return [int(x) for x in p.read_text().split()]
        time.sleep(0.05)
    raise AssertionError("fake claude never started")


def alive(pid):
    if os.name == "nt":                                                            # os.kill(pid, 0) is a Ctrl+C there
        import subprocess
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_cancel_kills_the_program_and_its_children(fake):
    fake.mode("slow")
    ev, box = threading.Event(), {}

    def run():
        try:
            call(cancel=ev, timeout=60)
        except ProviderError as e:
            box["e"] = e
    t = threading.Thread(target=run)
    t.start()
    parent, child = _pids(fake)
    assert alive(parent) and alive(child)
    ev.set()
    t.join(10)
    assert box["e"].kind == "cancelled"
    time.sleep(0.3)
    assert not alive(parent) and not alive(child)                                  # the whole tree, not only the parent
    assert not cc.LOCK.locked()


def test_the_time_limit_kills_the_tree(fake):
    fake.mode("slow")
    t0 = time.time()
    with pytest.raises(ProviderError) as e:
        call(timeout=2)
    assert e.value.kind == "timeout" and time.time() - t0 < 20 and e.value.code == "claude_timeout"
    parent, child = _pids(fake)
    time.sleep(0.3)
    assert not alive(parent) and not alive(child)
    assert not cc.LOCK.locked()


def test_a_60000_character_prompt_reaches_the_program_whole(fake):
    big = "word é " * 12000                                                         # 72,000 characters, non-ASCII too
    assert get_provider("claudecode")(SPEC, "SYS", big, timeout=20)
    c = fake.calls("call")[0]
    assert c["stdin_len"] == len(big) and c["stdin_nonascii"] and max(len(x) for x in c["argv"]) < 1000      # argv stays short


def test_a_large_prompt_reaches_a_program_that_starts_reading_late(fake):
    """The prompt goes through a file used as standard input (not a pipe fed by a polling loop): see antigravity.py."""
    fake.mode("late")
    t0 = time.time()
    assert get_provider("claudecode")(SPEC, "SYS", "A" * 300_000, timeout=60).startswith("FINAL SCRIPT")
    assert time.time() - t0 < 20 and fake.calls("call")[0]["stdin_len"] == 300_000


def test_cancel_interrupts_within_a_second_while_the_program_has_not_read_its_input_and_the_prompt_file_is_removed(fake):
    import tempfile
    fake.mode("never_reads")
    ev = threading.Event()
    threading.Timer(0.5, ev.set).start()
    before = set(os.listdir(tempfile.gettempdir()))
    t0 = time.time()
    with pytest.raises(ProviderError) as e:
        get_provider("claudecode")(SPEC, "SYS", "B" * 300_000, timeout=60, cancel=ev)
    assert e.value.kind == "cancelled" and time.time() - t0 < 3
    assert [n for n in set(os.listdir(tempfile.gettempdir())) - before if n.startswith(("bti-claude-in-", "bti-claude-"))] == []     # the owner's text is gone


def test_the_prompt_file_is_removed_after_a_normal_call_and_after_a_failure(fake):
    import tempfile
    before = set(os.listdir(tempfile.gettempdir()))
    call()
    fake.mode("empty")
    with pytest.raises(ProviderError):
        call()
    assert [n for n in set(os.listdir(tempfile.gettempdir())) - before if n.startswith("bti-claude-")] == []


def test_one_call_at_a_time(fake):
    order = []
    orig = cc.subprocess.Popen

    class Spy(orig):
        def __init__(self, *a, **k):
            order.append("start")
            super().__init__(*a, **k)
    cc.subprocess.Popen = Spy
    try:
        ts = [threading.Thread(target=call) for _ in range(3)]
        [t.start() for t in ts]
        [t.join(30) for t in ts]
    finally:
        cc.subprocess.Popen = orig
    assert len(fake.calls("call")) == 3 and not cc.LOCK.locked()


def test_no_fallback_to_a_paid_api(fake, tproj, monkeypatch):
    """A Claude Code failure ends the job with an error; no other provider is called."""
    fake.mode("error", text="You've hit your session limit · resets in 2 hr", status=429)
    import bti.script.providers as P
    seen = []
    orig = P.get_provider
    monkeypatch.setattr(generate, "get_provider", lambda n: (seen.append(n), orig(n))[1])
    jobs = ScriptJobs()
    job = jobs.start("outline", tproj.name, SPEC["id"], lambda j: generate.run_outline(j, tproj, SPEC))
    for _ in range(300):
        if job.state in ("done", "error"):
            break
        time.sleep(0.05)
    assert job.state == "error" and job.error_kind == "rate_limit" and seen == ["claudecode"]
    assert "2 giờ" in job.error and "Claude Code" in job.error                       # the owner is told how long, in Vietnamese


def test_the_clean_environment_carries_no_project_variable_and_no_key(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "FFMPEG_PATH", "BTI_PROJECTS"):
        monkeypatch.setenv(k, "x")
    env = cc.clean_env()
    assert not {"OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "FFMPEG_PATH", "BTI_PROJECTS"} & set(env)
    assert "PATH" in env and env.get("TERM")


# ------------------------------------------------------------------------------------------------ when the plan is used up
def _tz_ok(name):
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(name)
        return True
    except Exception:      # noqa: BLE001
        return False


NOW = datetime.datetime(2026, 11, 18, 12, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=7))).timestamp()    # 12:00 in Asia/Saigon (UTC+7)


@pytest.fixture()
def zones(monkeypatch):
    """Fixed offsets for the two zones of the cases below, so the arithmetic is tested on a machine with no time-zone database too
    (Windows without `tzdata`); `test_a_real_zone_name_is_read_with_the_machines_database` covers the real database where there is one."""
    fixed = {"Asia/Saigon": datetime.timezone(datetime.timedelta(hours=7)), "Asia/Tokyo": datetime.timezone(datetime.timedelta(hours=9))}
    monkeypatch.setattr(cc, "_zone", lambda name: fixed.get(name))


@pytest.mark.parametrize("text,seconds", [
    ("You've hit your session limit · resets 7pm (Asia/Saigon)", 7 * 3600),
    ("You've hit your limit · resets 7pm (Asia/Saigon)", 7 * 3600),
    ("You've hit your session limit · resets 11am (Asia/Saigon)", 23 * 3600),                      # already past today: tomorrow
    ("resets 1:50am (Asia/Saigon)", 13 * 3600 + 50 * 60),
    ("You've hit your weekly limit · resets Nov 25 at 3pm (Asia/Saigon)", 7 * 86400 + 3 * 3600),
    ("resets Nov 25, 3pm (Asia/Saigon)", 7 * 86400 + 3 * 3600),
    ("resets Jan 2 at 9am (Asia/Saigon)", 44 * 86400 + 21 * 3600),                                 # next year
    ("resets 7pm (Asia/Tokyo)", 5 * 3600),                                                         # 19:00 in UTC+9 is 17:00 in Saigon
])
def test_parse_reset_seconds_with_a_zone(zones, text, seconds):
    assert cc.parse_reset_seconds(text, NOW) == seconds


@pytest.mark.skipif(not _tz_ok("Asia/Saigon"), reason="no time-zone database on this machine")
def test_a_real_zone_name_is_read_with_the_machines_database():
    assert cc.parse_reset_seconds("You've hit your session limit · resets 7pm (Asia/Saigon)", NOW) == 7 * 3600
    assert cc.parse_reset_seconds("resets 7pm (Asia/Tokyo)", NOW) == 5 * 3600


@pytest.mark.parametrize("text,seconds", [
    ("You've hit your limit · resets in 4 hr 30 min", 16200), ("resets in 2h 5m", 7500), ("Resets in 45 minutes", 2700), ("resets in 1 day 2 hours", 93600),
    ("resets in 30 seconds", 30), ("Claude AI usage limit reached|%d" % (int(NOW) + 3600), 3600), ("Claude AI usage limit reached|%d" % (int(NOW) - 5), None),
    ("You've hit your limit", None), ("", None), ("resets 7", None), ("resets Dec 1", None), ("limit reached, try later", None),
])
def test_parse_reset_seconds_without_a_zone(text, seconds):
    assert cc.parse_reset_seconds(text, NOW) == seconds


def test_a_zone_name_this_machine_does_not_know_falls_back_to_the_local_clock():
    local = datetime.datetime.fromtimestamp(NOW)
    expect = (local.replace(hour=19, minute=0, second=0, microsecond=0) - local).total_seconds()
    expect = expect if expect > 0 else expect + 86400
    assert cc.parse_reset_seconds("resets 7pm (Not/AZone)", NOW) == int(expect)


def test_the_rate_limit_event_of_the_program_gives_the_exact_reset():
    events = [json.loads(x) for x in (FIX / "single_stream_init.jsonl").read_text(encoding="utf-8").splitlines()]
    allowed = next(e for e in events if e["type"] == "rate_limit_event")
    assert allowed["rate_limit_info"]["status"] == "allowed" and cc.reset_from_events([allowed]) is None          # recorded shape: nothing to wait for
    rejected = json.loads(json.dumps(allowed))
    rejected["rate_limit_info"].update(status="rejected", resetsAt=int(time.time()) + 5400)
    assert abs(cc.reset_from_events([allowed, rejected]) - 5400) <= 2
    err = cc.classify("You've hit your limit · resets 7pm", [rejected])
    assert err.kind == "rate_limit" and abs(err.retry_after_seconds - 5400) <= 2                                     # the exact epoch wins over the text


def test_the_quota_message_names_the_plan_and_the_time():
    assert "Claude Code" in cc.quota_message(16200) and "4 giờ 30 phút" in cc.quota_message(16200)
    assert "Thử lại sau" not in cc.quota_message(None)


# ------------------------------------------------------------------------------------------------ installed and signed in (no model call)
def test_availability_signed_in(fake):
    info = cc.availability()
    assert info == {"ok": True, "kind": None, "reason": None, "message": None}
    assert fake.calls("call") == []                                                  # `claude auth status` only: no model call
    assert fake.calls()[0]["argv"] == ["auth", "status"]


def test_availability_not_signed_in_uses_the_real_signed_out_answer(fake):
    fake.mode("signed_out")                                           # tests/script/fixtures/claude/auth_status_signed_out.json: exit 1
    info = cc.availability()
    assert info["ok"] is False and info["kind"] == "auth" and info["reason"] == "not_signed_in" and info["message"] == OWNER_SIGNED_OUT
    with pytest.raises(ProviderError) as e:
        cc.auth_status()
    assert e.value.kind == "auth"


def test_availability_not_installed(fake, monkeypatch):
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    info = cc.availability()
    assert info["ok"] is False and info["reason"] == "not_installed" and info["kind"] == "config" and "Chưa cài Claude Code" in info["message"]


def test_availability_unreadable_and_slow_answers_and_the_safety_switch(fake, monkeypatch):
    fake.mode("auth_garbage")
    info = cc.availability()
    assert info["ok"] is False and info["kind"] == "config" and info["reason"] == "unreadable"
    fake.mode("auth_slow")
    monkeypatch.setattr(cc, "STATUS_TIMEOUT_S", 1)
    info = cc.availability()
    assert info["ok"] is False and info["kind"] == "timeout" and info["reason"] == "timeout"
    parent, child = _pids(fake)
    time.sleep(0.3)
    assert not alive(parent) and not alive(child)                                    # the tree is killed
    n = len(fake.calls())
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    info = cc.availability()
    assert info["ok"] is False and info["reason"] == "real_models_off" and len(fake.calls()) == n


def test_the_account_details_of_the_status_answer_are_never_kept(fake):
    info = cc.availability()
    assert set(info) == {"ok", "kind", "reason", "message"} and "@" not in json.dumps(info)


# ------------------------------------------------------------------------------------------------ the model list
def test_the_tracked_entry_is_listed_and_enabled_when_signed_in(fake):
    ms = models_mod.public_models()
    m = next(x for x in ms if x["id"] == "claude:claude-opus-5-5@high")
    assert m["label"] == "Claude Code: Opus 5.5 High" and m["provider"] == "claudecode" and m["model"] == "claude-opus-5-5"
    assert m["enabled"] is True and m["message"] is None and m["paid"] is False and m["default"] is False and m["missing_env"] is None
    assert m["claude"] == {"ok": True, "reason": None}
    spec = next(x for x in models_mod.load_models() if x["id"] == m["id"])
    assert spec["effort"] == "high" and spec["provider"] == "claudecode"
    assert next(x for x in ms if x["provider"] == "mock")["enabled"]                 # the other entries are unchanged


def test_not_signed_in_and_not_installed_are_listed_with_a_reason(fake, monkeypatch):
    fake.mode("signed_out")
    m = next(x for x in models_mod.public_models(refresh=True) if x["provider"] == "claudecode")
    assert m["enabled"] is False and m["message"] == OWNER_SIGNED_OUT and m["claude"] == {"ok": False, "reason": "not_signed_in"}
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    m = next(x for x in models_mod.public_models(refresh=True) if x["provider"] == "claudecode")
    assert m["enabled"] is False and "Chưa cài Claude Code" in m["message"] and m["claude"] == {"ok": False, "reason": "not_installed"}


def test_the_answer_is_cached_like_the_agy_list_and_a_failure_for_a_minute(fake):
    models_mod.public_models()
    models_mod.public_models()
    assert len([c for c in fake.calls() if c["argv"][:1] == ["auth"]]) == 1          # cached ten minutes
    fake.mode("signed_out")
    assert next(x for x in models_mod.public_models() if x["provider"] == "claudecode")["enabled"] is True      # the change is not seen yet
    models_mod.reset_cache()
    assert next(x for x in models_mod.public_models() if x["provider"] == "claudecode")["enabled"] is False
    fake.mode("ok")
    assert next(x for x in models_mod.public_models() if x["provider"] == "claudecode")["enabled"] is False     # a failure is cached (1 minute)
    assert next(x for x in models_mod.public_models(refresh=True) if x["provider"] == "claudecode")["enabled"] is True
    assert models_mod.FAIL_SECONDS == 60 and models_mod.CACHE_SECONDS == 600


def test_three_requests_at_once_start_one_check(fake):
    out = []
    ts = [threading.Thread(target=lambda: out.append(models_mod.claude_status())) for _ in range(3)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert len(out) == 3 and all(o["ok"] for o in out)
    assert len([c for c in fake.calls() if c["argv"][:1] == ["auth"]]) == 1


def test_resolve_knows_the_tracked_entry_and_any_well_formed_id_without_starting_the_program(fake):
    s = models_mod.resolve("claude:claude-opus-5-5@high")
    assert s["provider"] == "claudecode" and s["model"] == "claude-opus-5-5" and s["effort"] == "high" and s["label"] == "Claude Code: Opus 5.5 High"
    assert models_mod.get_model("claude:claude-opus-5-5@high")["id"] == s["id"]
    u = models_mod.resolve("claude:claude-sonnet-4-5@medium")                        # no tracked entry: built from the id
    assert u["provider"] == "claudecode" and u["model"] == "claude-sonnet-4-5" and u["effort"] == "medium" and u["label"] == "Claude Code: claude-sonnet-4-5 (medium)"
    for bad in ("claude:claude-opus-5-5", "claude:x@ultra", "claude:", "claude", "claude:x y@high", "Claude:x@high"):
        assert models_mod.resolve(bad) is None, bad
    assert fake.calls() == []                                                        # resolve never starts the program


def test_resolve_folds_in_the_cached_availability_while_it_is_fresh(fake):
    assert "unavailable" not in models_mod.resolve("claude:claude-opus-5-5@high")
    fake.mode("signed_out")
    models_mod.public_models(refresh=True)
    s = models_mod.resolve("claude:claude-opus-5-5@high")
    assert s["unavailable"] == OWNER_SIGNED_OUT and s["unavailable_reason"] == "not_signed_in"
    assert models_mod.public(s)["enabled"] is False
    u = models_mod.resolve("claude:other@low")
    assert u["unavailable"] == OWNER_SIGNED_OUT
    models_mod.reset_cache()
    assert "unavailable" not in models_mod.resolve("claude:claude-opus-5-5@high")    # stale answers are not used


def test_the_models_file_with_no_claude_entry_still_resolves_the_family(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([{"id": "mock", "label": "Mock", "provider": "mock", "model": "mock", "key_env": None}]), encoding="utf-8")
    assert models_mod.resolve("claude:claude-opus-5-5@high", p)["timeout"] == 900
    assert [m["id"] for m in models_mod.public_models(p)] == ["mock"]


def test_the_tracked_file_has_exactly_one_claude_entry():
    raw = json.loads((HERE.parents[1] / "config" / "models.json").read_text(encoding="utf-8"))
    rows = [m for m in raw if m["provider"] == "claudecode"]
    assert len(rows) == 1 and rows[0]["id"] == "claude:claude-opus-5-5@high" and rows[0]["label"] == "Claude Code: Opus 5.5 High"
    assert cc.parse_model_id(rows[0]["id"]) == (rows[0]["model"], rows[0]["effort"])
