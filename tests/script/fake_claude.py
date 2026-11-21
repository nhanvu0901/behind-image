"""A fake `claude` (Claude Code) that replays the shapes recorded from the real program (tests/script/fixtures/claude/, tests/draft/
fixtures/claude/: 2026-11-18, Claude Code 2.1.327, `--model haiku`). Behaviour is set by the file `mode` next to this script and the file
`cfg.json` (both written by the tests). Every start is logged to `calls.jsonl` (argv, cwd, the NAMES of the environment variables, stdin).

  claude --help                 a help text that lists the options the provider needs (mode `old_cli`: without --safe-mode)
  claude auth status            `{"loggedIn": true}`; mode `signed_out` replays the real answer of an empty config folder (exit 1)
  claude -p ... (no --input-format)   one call: the whole of stdin is the prompt; one JSON object on stdout
  claude -p ... --input-format stream-json   an agent: one `user` line per turn on stdin, events on stdout, until stdin closes

The usage-limit answers are NOT recordings (a real usage limit could not be provoked); they follow the documented wording
(`You've hit your session limit · resets 7pm (Asia/Saigon)`), the `rate_limit_event` shape recorded from the real program, and are named so.
The "too old" answer (fixtures/claude/too_old.txt) is the TEXT a real call on the server printed (Claude Code 2.1.233, 2026-11-18); how that
program frames it is not recorded, so the tests feed it every way: as the `result` of a call (mode `error`, `error_text`) and as a plain line (`stderr_only`, `stderr_text`).
"""
import copy
import json
import os
import subprocess
import sys
import time

here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode")).read().strip() if os.path.exists(os.path.join(here, "mode")) else "ok"
cfg = json.load(open(os.path.join(here, "cfg.json"))) if os.path.exists(os.path.join(here, "cfg.json")) else {}
args = sys.argv[1:]
FIX_SCRIPT = cfg.get("fixtures_script") or "@@FIX_SCRIPT@@"        # the tests replace these two quoted words with the fixture folders when they copy this file
FIX_DRAFT = cfg.get("fixtures_draft") or "@@FIX_DRAFT@@"


def log(extra=None):
    d = {"argv": args, "cwd": os.getcwd(), "env": sorted(os.environ)}
    d.update(extra or {})
    with open(os.path.join(here, "calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(d) + "\n")


HELP = """Usage: claude [options] [command] [prompt]
Options:
  --add-dir <directories...>   More directories
  --allowedTools, --allowed-tools <tools...>   Tools allowed
  --append-system-prompt <prompt>   Add text
  --disable-slash-commands   Disable all skills and commands
  --disallowedTools, --disallowed-tools <tools...>   Tools denied
  --effort <level>   Effort level
  --input-format <format>   Input format
  --model <model>   Model
  --no-session-persistence   Do not save sessions
  --output-format <format>   Output format
  --permission-mode <mode>   Permission mode
  -p, --print   Print response and exit
  --resume [value]   Resume
  --setting-sources <sources>   Setting sources
  --strict-mcp-config   Only MCP servers from --mcp-config
  --system-prompt <prompt>   System prompt
  --tools <tools...>   Built-in tools
  --verbose   Verbose
"""
if args[:1] == ["--help"]:
    log()
    text = HELP
    if mode == "old_cli":
        text = text.replace("  --safe-mode   Start with all customizations disabled\n", "").replace("--no-session-persistence", "--no-persist")
    else:
        text = text.replace("  --setting-sources", "  --safe-mode   Start with all customizations disabled\n  --setting-sources")
    print(text)
    sys.exit(0)

if args[:2] == ["auth", "status"]:
    log()
    if mode == "signed_out":
        print(open(os.path.join(FIX_SCRIPT, "auth_status_signed_out.json")).read())
        sys.exit(1)
    if mode == "auth_garbage":
        print("error: unknown command 'auth'")
        sys.exit(1)
    if mode == "auth_slow":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open(os.path.join(here, "pids"), "w").write("%d %d" % (os.getpid(), child.pid))
        time.sleep(60)
    print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}))
    sys.exit(0)


def load_json(path):
    return json.loads(open(path, encoding="utf-8").read())


def load_lines(path):
    return [json.loads(x) for x in open(path, encoding="utf-8").read().splitlines() if x.strip()]


# ------------------------------------------------------------------------------------------------ one call
if "--input-format" not in args:
    if mode == "late":                       # a program that is slow to start reading its input
        time.sleep(1.5)
    elif mode == "never_reads":
        time.sleep(60)
    raw = sys.stdin.buffer.read().decode("utf-8")
    log({"stdin_len": len(raw), "stdin_head": raw[:80], "stdin_tail": raw[-80:], "stdin_nonascii": any(ord(c) > 127 for c in raw)})
    res = load_json(os.path.join(FIX_SCRIPT, "single_ok.json"))
    res["result"] = cfg.get("answer", "FINAL SCRIPT\n\n## c01 COLD OPEN\nHello there.\n")

    def out(obj, rc=0):
        print(json.dumps(obj))
        sys.exit(rc)

    if mode in ("ok", "late"):
        out(res)
    elif mode == "array":                    # some builds print the whole event list
        out([{"type": "system", "subtype": "init"}, res])
    elif mode == "not_signed_in":
        sys.stdout.write(open(os.path.join(FIX_SCRIPT, "not_signed_in.json")).read())
        sys.exit(1)
    elif mode == "wrong_model":
        sys.stdout.write(open(os.path.join(FIX_SCRIPT, "wrong_model.json")).read())
        sys.stderr.write(open(os.path.join(FIX_SCRIPT, "wrong_model.stderr.txt")).read())
        sys.exit(1)
    elif mode == "error":                    # any failure text, from cfg: {"text": ..., "status": 429}
        res.update(is_error=True, result=cfg["text"], api_error_status=cfg.get("status"), terminal_reason="api_error")
        out(res, 1)
    elif mode == "denials":
        res["permission_denials"] = [{"tool_name": "Bash", "tool_use_id": "toolu_x", "tool_input": {"command": "ls"}}]
        out(res)
    elif mode == "two_turns":
        res["num_turns"] = 2
        out(res)
    elif mode == "writes":
        open("leak.txt", "w").write("x")
        out(res)
    elif mode == "empty":
        res["result"] = "  "
        out(res)
    elif mode == "garbage":
        print("not json at all")
        sys.exit(0)
    elif mode == "silent_fail":
        sys.exit(1)
    elif mode == "stderr_only":
        sys.stderr.write(cfg.get("text", "Not logged in · Please run /login") + "\n")
        sys.exit(1)
    elif mode == "never_reads_done":
        out(res)
    elif mode == "slow":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open(os.path.join(here, "pids"), "w").write("%d %d" % (os.getpid(), child.pid))
        time.sleep(60)
    else:
        out(res)
    sys.exit(0)

# ------------------------------------------------------------------------------------------------ an agent in a folder
log()
events = load_lines(os.path.join(FIX_DRAFT, "agent_two_turns.jsonl"))
init = next(e for e in events if e.get("type") == "system" and e.get("subtype") == "init")
asst_write = next(e for e in events if e.get("type") == "assistant" and any(b.get("name") == "Write" for b in e["message"]["content"]))
asst_bash = next(e for e in events if e.get("type") == "assistant" and any(b.get("name") == "Bash" for b in e["message"]["content"]))
asst_read = next(e for e in events if e.get("type") == "assistant" and any(b.get("name") == "Read" for b in e["message"]["content"]))
user_ev = next(e for e in events if e.get("type") == "user")
result_tpl = next(e for e in events if e.get("type") == "result")
rate_ev = next((e for e in load_lines(os.path.join(FIX_SCRIPT, "single_stream_init.jsonl")) if e.get("type") == "rate_limit_event"), None)


def emit(ev):
    print(json.dumps(ev), flush=True)


def tool(asst, name_id):
    e = copy.deepcopy(asst)
    for b in e["message"]["content"]:
        if b.get("type") == "tool_use":
            b["id"] = name_id
    return e


def result(**kw):
    r = copy.deepcopy(result_tpl)
    r["result"] = "done"
    r.update(kw)
    emit(r)


def write_specs(good=True):
    os.makedirs("out", exist_ok=True)
    for cid, sp in cfg["specs"].items():
        sp = json.loads(json.dumps(sp))
        if not good:
            sp["shots"][1]["technique"] = "NOPE-9"
        open(os.path.join("out", cid + ".json"), "w").write(json.dumps(sp))
    open(os.path.join("out", "notes.md"), "w").write("Fake agent summary\n")
    if cfg.get("notes_json"):
        open(os.path.join("out", "notes.json"), "w", encoding="utf-8").write(json.dumps(cfg["notes_json"], ensure_ascii=False))


turn = 0
if mode == "exits":                      # the turn counter survives the process
    tf = os.path.join(here, "turns")
    turn = int(open(tf).read()) if os.path.exists(tf) else 0
init = copy.deepcopy(init)
init["cwd"] = os.getcwd()
emit(init)
if mode == "stderr_auth":
    sys.stderr.write("Not logged in · Please run /login\n")
    sys.exit(1)
if mode == "stderr_text":                # any failure text from cfg, printed as a plain sentence on stderr before anything runs (followups: fixtures/claude/too_old.txt)
    sys.stderr.write(cfg["text"] + "\n")
    sys.exit(1)
if mode == "noresult_at_start":
    sys.exit(0)
for line in sys.stdin:
    msg = json.loads(line)
    assert msg["type"] == "user" and msg["message"]["role"] == "user", msg
    content = msg["message"]["content"]
    text = content if isinstance(content, str) else "".join(b.get("text", "") for b in content if b.get("type") == "text")
    turn += 1
    with open(os.path.join(here, "prompts.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(text) + "\n")
    if mode == "replay":                 # the recorded events of a real session, verbatim, as the answer to the first message
        for ev in load_lines(os.path.join(FIX_DRAFT, cfg["replay"])):
            if not (ev.get("type") == "system" and ev.get("subtype") == "init"):
                emit(ev)
        continue
    emit(tool(asst_read, "toolu_r%d" % turn))
    emit(user_ev)
    if mode == "ok":
        write_specs(True)
    elif mode == "repair":
        write_specs(turn >= 2)
    elif mode == "bad":
        write_specs(False)
    elif mode == "tamper":
        write_specs(True)
        open(cfg["victim"], "a").write("x")
    elif mode == "exits":
        write_specs(turn >= 2)
    elif mode == "slow":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        open(os.path.join(here, "pids"), "w").write("%d %d" % (os.getpid(), child.pid))
        write_specs(True)
        time.sleep(120)
    else:
        write_specs(True)
    emit(tool(asst_write, "toolu_w%d" % turn))
    emit(user_ev)
    emit(tool(asst_bash, "toolu_b%d" % turn))
    emit(user_ev)
    if mode == "error":
        result(is_error=True, result="API Error: something broke", api_error_status=500)
        sys.exit(1)
    elif mode == "auth":
        result(is_error=True, result="Not logged in · Please run /login")
        sys.exit(1)
    elif mode == "wrong_model":
        result(is_error=True, result="There's an issue with the selected model (zzz). It may not exist or you may not have access to it.", api_error_status=404)
        sys.exit(1)
    elif mode == "error_text":               # any failure text from cfg as the result of the run: {"text": ..., "status": 404}
        result(is_error=True, result=cfg["text"], api_error_status=cfg.get("status"))
        sys.exit(1)
    elif mode in ("quota", "quota_event"):    # NOT recordings: the documented wording and the recorded rate_limit_event shape
        if mode == "quota_event":
            ev = copy.deepcopy(rate_ev)
            ev["rate_limit_info"].update(status="rejected", resetsAt=int(time.time()) + 3600)
            emit(ev)
        result(is_error=True, result="You've hit your session limit · resets 7pm (Asia/Saigon)", api_error_status=429)
        sys.exit(1)
    elif mode == "denials":
        write_specs(True)
        result(permission_denials=[{"tool_name": "Bash", "tool_use_id": "toolu_x", "tool_input": {"command": "cat /etc/hosts"}}])
    elif mode == "noresult":
        sys.exit(0)
    elif mode == "exits":
        open(os.path.join(here, "turns"), "w").write(str(turn))
        result()
        sys.exit(0)
    else:
        result()
