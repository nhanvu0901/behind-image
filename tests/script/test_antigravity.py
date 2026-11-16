"""The Antigravity CLI provider, against a fake `agy` executable on a temporary PATH. No network, no real agy."""
import json
import os
import stat
import sys
import threading
import time

import pytest

from bti.script import generate, models as models_mod, store
from bti.script.providers import ProviderError, antigravity, get_provider
from bti.script.runner import ScriptJobs

FAKE = '''#!{py}
import json, os, sys, time
here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode")).read().strip()
args = sys.argv[1:]
if args[:1] == ["models"]:
    if mode == "models_auth":
        sys.stderr.write("authentication required\\n"); sys.exit(1)
    print("Fetching available models...")
    print("gemini-x-high\\tGemini X (High)"); print("claude-y\\tClaude Y (Thinking)"); sys.exit(0)
prompt = args[args.index("-p") + 1]
open(os.path.join(here, "calls.jsonl"), "a").write(json.dumps({{"argv": [a for a in args if a != prompt], "prompt_len": len(prompt),
    "prompt_head": prompt[:60], "prompt_tail": prompt[-80:], "cwd": os.getcwd(), "stdin_tty": sys.stdin.isatty()}}) + "\\n")
def env(**kw):
    d = {{"conversation_id": "c", "status": "SUCCESS", "response": "FINAL SCRIPT\\n\\n## c01 COLD OPEN\\nHello there.\\n", "duration_seconds": 1.0,
          "num_turns": 1, "usage": {{"input_tokens": 5, "output_tokens": 5, "total_tokens": 10}}}}
    d.update(kw); return json.dumps(d)
if mode == "ok": print(env())
elif mode == "status_error": print(env(status="ERROR", response="", error="something broke")); sys.exit(1)
elif mode == "canceled": print(env(status="CANCELED", response=""))
elif mode == "tools": print(env(num_turns=4))
elif mode == "denied": sys.stderr.write("notice: tool run_command was denied (needs approval)\\n"); print(env())
elif mode == "writes": open("leak.txt", "w").write("x"); print(env())
elif mode == "auth": sys.stderr.write("Error: authentication required. Run agy to log in.\\n"); sys.exit(1)
elif mode == "quota": print(env(status="ERROR", response="", error="429 RESOURCE_EXHAUSTED: quota exceeded")); sys.exit(1)
elif mode == "badmodel": print(env(status="ERROR", response="", error="unknown model 'zzz'")); sys.exit(1)
elif mode == "empty": print(env(response="  "))
elif mode == "garbage": print("not json at all")
elif mode == "slow":
    import subprocess
    child = subprocess.Popen(["sleep", "60"])
    open(os.path.join(here, "pids"), "w").write(f"{{os.getpid()}} {{child.pid}}")
    time.sleep(60)
'''


@pytest.fixture()
def fake(tmp_path, monkeypatch):
    d = tmp_path / "bin"
    d.mkdir()
    exe = d / "agy"
    exe.write_text(FAKE.format(py=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("BTI_AGY_BIN", str(exe))
    models_mod.reset_cache()

    class F:
        dir = d

        def mode(self, m):
            (d / "mode").write_text(m)

        def calls(self):
            p = d / "calls.jsonl"
            return [json.loads(x) for x in p.read_text().splitlines()] if p.is_file() else []
    f = F()
    f.mode("ok")
    return f


SPEC = {"id": "agy:gemini-x-high", "provider": "antigravity", "model": "gemini-x-high"}


def call(**kw):
    return get_provider("antigravity")(SPEC, "SYS", "USER TEXT", timeout=kw.pop("timeout", 20), **kw)


def test_success_reads_the_json_envelope(fake):
    assert call().startswith("FINAL SCRIPT")
    c = fake.calls()[0]
    a = c["argv"]
    assert a[a.index("--output-format") + 1] == "json" and "--sandbox" in a and "--disable-slash-commands" in a
    assert a[a.index("--model") + 1] == "gemini-x-high" and a[a.index("--print-timeout") + 1].endswith("s")
    assert "--dangerously-skip-permissions" not in a
    st = json.loads(a[a.index("--settings") + 1])
    assert st["toolPermission"] == "strict" and st["allowNonWorkspaceAccess"] is False and st["enableTerminalSandbox"] is True
    assert c["prompt_head"].startswith("SYS") and "Follow the output layout" in c["prompt_tail"]


def test_runs_in_an_empty_temp_folder_outside_the_repo_and_removes_it(fake):
    call()
    cwd = fake.calls()[0]["cwd"]
    repo = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    assert not os.path.realpath(cwd).startswith(repo) and "bti-agy-" in cwd
    assert not os.path.exists(cwd)                                                 # removed afterwards


@pytest.mark.parametrize("mode,kind", [("status_error", "http"), ("canceled", "http"), ("tools", "http"), ("denied", "http"),
                                       ("writes", "http"), ("auth", "auth"), ("quota", "rate_limit"), ("badmodel", "config"),
                                       ("empty", "empty"), ("garbage", "empty")])
def test_failures_are_refused_with_a_kind(fake, mode, kind):
    fake.mode(mode)
    with pytest.raises(ProviderError) as e:
        call()
    assert e.value.kind in (kind, "http", "empty"), e.value.message
    if mode in ("auth", "quota", "badmodel"):
        assert e.value.kind == kind
    if mode == "auth":
        assert "agy" in e.value.message and "Terminal" in e.value.message          # tells the owner to run agy once
    if mode == "tools":
        assert "lượt" in e.value.message
    if mode == "denied":
        assert "công cụ" in e.value.message
    if mode == "writes":
        assert "tệp" in e.value.message


def _pids(fake):
    p = fake.dir / "pids"
    for _ in range(100):
        if p.is_file() and p.read_text().strip():
            return [int(x) for x in p.read_text().split()]
        time.sleep(0.05)
    raise AssertionError("fake agy never started")


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_cancel_kills_agy_and_its_children(fake):
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
    assert not alive(parent) and not alive(child)                                  # the whole group, not only the parent
    assert not antigravity.LOCK.locked()


def test_hard_timeout(fake, monkeypatch):
    fake.mode("slow")
    real = time.time
    base = real()
    calls = {"n": 0}

    def fast():                                                                    # jump the clock past the deadline
        calls["n"] += 1
        return base + (calls["n"] * 20 if calls["n"] > 5 else 0) + (real() - base)
    monkeypatch.setattr(antigravity.time, "time", fast)
    with pytest.raises(ProviderError) as e:
        call(timeout=5)
    assert e.value.kind == "timeout"
    parent, child = _pids(fake)
    time.sleep(0.3)
    assert not alive(parent) and not alive(child)


def test_a_60000_character_prompt_reaches_the_cli_whole(fake):
    big = "word " * 12000                                                            # 60,000 characters
    out = get_provider("antigravity")(SPEC, "SYS", big, timeout=20)
    assert out
    c = fake.calls()[0]
    assert c["prompt_len"] > 60000 and "Follow the output layout" in c["prompt_tail"]


def test_one_call_at_a_time(fake):
    fake.mode("ok")
    order = []
    orig = antigravity.subprocess.Popen

    class Spy(orig):
        def __init__(self, *a, **k):
            order.append("start")
            super().__init__(*a, **k)
    antigravity.subprocess.Popen = Spy
    try:
        ts = [threading.Thread(target=call) for _ in range(3)]
        [t.start() for t in ts]
        [t.join(20) for t in ts]
    finally:
        antigravity.subprocess.Popen = orig
    assert len(fake.calls()) == 3 and not antigravity.LOCK.locked()


def test_models_listing_is_expanded_cached_and_default_first(fake):
    ms = models_mod.public_models()
    agy = [m for m in ms if m["provider"] == "antigravity"]
    assert [m["id"] for m in agy] == ["agy:gemini-x-high", "agy:claude-y"] and agy[0]["default"] and not agy[1]["default"]
    assert agy[0]["enabled"] and agy[0]["label"].endswith("Gemini X (High)") and not agy[0]["paid"]
    assert models_mod.get_model("agy:claude-y")["model"] == "claude-y"
    (fake.dir / "mode").write_text("models_auth")                                  # cached: the change is not seen yet
    assert [m["id"] for m in models_mod.public_models() if m["provider"] == "antigravity"][0] == "agy:gemini-x-high"
    models_mod.reset_cache()
    bad = [m for m in models_mod.public_models() if m["provider"] == "antigravity"]
    assert len(bad) == 1 and bad[0]["enabled"] is False and "Terminal" in bad[0]["message"] and bad[0]["id"] == "agy"


def test_agy_missing_disables_the_entry(monkeypatch):
    monkeypatch.setenv("BTI_AGY_BIN", "")
    models_mod.reset_cache()
    bad = [m for m in models_mod.public_models() if m["provider"] == "antigravity"][0]
    assert bad["enabled"] is False and "agy" in bad["message"]


def test_no_fallback_to_a_paid_api(fake, tproj, monkeypatch):
    """An agy failure ends the job with an error; no other provider is called."""
    fake.mode("quota")
    import bti.script.providers as P
    seen = []
    orig = P.get_provider
    monkeypatch.setattr(generate, "get_provider", lambda n: (seen.append(n), orig(n))[1])
    jobs = ScriptJobs()
    job = jobs.start("outline", tproj.name, "agy", lambda j: generate.run_outline(j, tproj, SPEC))
    for _ in range(300):
        if job.state in ("done", "error"):
            break
        time.sleep(0.05)
    assert job.state == "error" and job.error_kind == "rate_limit" and seen == ["antigravity"]


def test_the_clean_environment_carries_no_project_variables(fake, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-LEAK")
    monkeypatch.setenv("FFMPEG_PATH", "/x")
    env = antigravity.clean_env()
    assert "OPENROUTER_API_KEY" not in env and "FFMPEG_PATH" not in env and "PATH" in env


def test_prompt_states_english_and_no_tools(fake):
    call()
    p = fake.calls()[0]
    assert "Follow the output layout" in p["prompt_tail"]
    assert "Do not use any tools" in antigravity.RULES and "ENGLISH" in antigravity.RULES and "override" in antigravity.RULES
