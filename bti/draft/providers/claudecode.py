"""The agent run with Claude Code (`claude`): an unattended agent in a workspace of copies, confined to that workspace.

    claude -p --model <m> --effort <e> --input-format stream-json --output-format stream-json --verbose
           --tools Bash,Read,Write,Edit,Glob,Grep --permission-mode dontAsk
           --allowedTools Edit(./out/**) Bash(./check --chapter *) Bash(./defaults *) Bash(./still --shot * -o look/*) ...
           --disallowedTools WebFetch WebSearch Bash(*..*) "Bash(* /*)" "Bash(* ~*)" ... (see `deny_rules`)
           --safe-mode --setting-sources "" --strict-mcp-config --disable-slash-commands --no-session-persistence
           --append-system-prompt <the confinement in words>
    working directory = the workspace; the first message is one NDJSON line on standard input:
        {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "Read TASK.md in this folder and do the task."}]}}
    standard output is a stream of NDJSON events: `system` (init), `assistant` (text and tool_use blocks), `user` (tool results),
    `rate_limit_event`, and one `result` per turn.

It runs on the owner's production machine, so it is NOT run with its checks bypassed (that is what the agy runner does). The mode
`dontAsk` refuses everything that would ask, and the permission rules name what is allowed: reading anywhere inside the workspace
(always allowed without a rule), writing only under `./out/`, and running only the three helper commands of the briefing. Reading or
writing outside the workspace, any other command, the web, other tools: refused, and the agent is told so (`permission_denials`).

Same contract as `agy.run` (`run(...)`, the `AgyResult`, the guard that lists the project before and after, one run at a time, a time
limit that kills the whole process tree, cancel) with these differences, all deliberate:
  * a repair message is written to the SAME process (standard input stays open while the program waits for the next turn): that works
    on every version that has `--input-format stream-json` and keeps nothing on disk, so `--no-session-persistence` holds and no
    `--resume` is needed. A program that ends before its final result is a failure, not a restart;
  * `conversation_id` is accepted and ignored (a session is not kept, so there is nothing to continue; the caller then rebuilds the
    context from the thread, as it does for any run without a conversation), and the result's `conversation_id` stays None;
  * the tool names of the stream are shown with the step names the page already knows (`last_action`).
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from bti.proc import IS_WINDOWS, kill_tree
from bti.script.providers import ProviderError, claudecode as cc

from ..inputs import DraftError
from . import agy
from .agy import AgyResult, DefaultRunner, _cancel_fn

PROMPT = agy.PROMPT
TOOLS = "Bash,Read,Write,Edit,Glob,Grep"
HELPERS = ("check", "defaults", "still")           # the three commands the briefing names (skills/storyboard_draft/TASK.template.md, section 7)
REQUIRED_FLAGS = cc.REQUIRED_FLAGS + ("--input-format", "--verbose", "--allowedTools", "--disallowedTools", "--append-system-prompt")
CONFINEMENT = ("You work unattended inside one folder, the current directory. Only the files inside it exist for you: read them, and write "
               "only under out/. The only commands you may run are the helper commands that TASK.md names. Everything else, such as other "
               "commands, other folders, the web, is refused automatically. If something is refused, do not look for another way; "
               "carry on with what you can do and say so in out/notes.md.")
# What each tool of the stream is called for the owner (the vocabulary of the other runner, so the progress line reads the same).
STEP_NAMES = {"Bash": "run_command", "Read": "view_file", "Write": "write_to_file", "Edit": "write_to_file", "Glob": "list_dir",
              "Grep": "grep_search"}
CODES = {"auth": "claude_auth", "rate_limit": "claude_rate_limit", "config": "claude_model", "timeout": "claude_timeout"}


def find_claude() -> str | None:
    return cc.find_claude()


def clean_env(python: str | None = None) -> dict:
    """The environment of the script provider plus BTI_PYTHON (the Python of the helper commands) and UTF-8 for them."""
    env = cc.clean_env()
    if python:
        env["BTI_PYTHON"] = str(python)
    env["PYTHONUTF8"] = "1"
    return env


# ------------------------------------------------------------------------------------------------ the permissions
def _forms(name: str, windows: bool) -> list[str]:
    """How the briefing's helper command can be written: `./check` on POSIX; on Windows the briefing says `.\\check.cmd` and the Bash tool
    of Claude Code there is a Git Bash that wants `/`, so the three spellings are all allowed."""
    return [f"./{name}.cmd", f".\\{name}.cmd", f"{name}.cmd"] if windows else [f"./{name}"]


def helper_patterns(windows: bool | None = None) -> list[str]:
    """The Bash rules that allow exactly the shapes of command the briefing shows (TASK.template.md, section 7), and nothing else:
    `check [--no-draw] [--chapter ID]`, `defaults TECHNIQUE [--asset A] [--region R]`, `still --shot C:N [--at T] -o look/FILE`,
    and `--help` of each. A `*` matches any text, so the deny rules below close the arguments that could name another folder."""
    win = IS_WINDOWS if windows is None else windows
    out = []
    for f in _forms("check", win):
        out += [f"Bash({f})", f"Bash({f} --no-draw)", f"Bash({f} --chapter *)", f"Bash({f} --no-draw --chapter *)", f"Bash({f} --chapter * --no-draw)",
                f"Bash({f} --help)"]
    for f in _forms("defaults", win):
        out += [f"Bash({f} --help)", f"Bash({f} *)"]
    for f in _forms("still", win):
        out += [f"Bash({f} --help)", f"Bash({f} --shot * -o look/*)", f"Bash({f} --shot * --at * -o look/*)", f"Bash({f} --shot * -o look/* --at *)"]
    return out


def allow_rules(windows: bool | None = None) -> list[str]:
    return ["Edit(./out/**)"] + helper_patterns(windows)


def deny_rules(windows: bool | None = None) -> list[str]:
    """Deny rules win over allow rules and apply to every part of a compound command. They close what the allow rules' wildcards leave
    open: a path that leaves the folder (`..`, an absolute or home path, a drive), another workspace named to a helper, a command
    substitution. The web tools are not in `--tools` at all; they are named here as well."""
    win = IS_WINDOWS if windows is None else windows
    rules = ["WebFetch", "WebSearch", "Bash(*..*)", "Bash(* /*)", "Bash(*'/*)", 'Bash(*"/*)', "Bash(* ~*)", "Bash(*:/*)", "Bash(*--workspace*)",
             "Bash(*-o/*)", "Bash(*$(*)", "Bash(*`*)"]
    if win:
        rules += ["Bash(*:\\*)", "Bash(* \\*)"]
    return rules


def build_command(claude: str, model_id: str | None = None, *, windows: bool | None = None) -> list[str]:
    from bti.settings import model_for
    parsed = cc.parse_model_id(model_id or model_for("draft"))
    if parsed is None:
        raise DraftError("claude_model", "the model id is not a Claude Code id (claude:<model>@<effort>)")
    model, effort = parsed
    cmd = [claude, "-p", "--model", model, "--effort", effort, "--input-format", "stream-json", "--output-format", "stream-json",
           "--verbose", "--tools", TOOLS]
    cmd += cc.isolation_args()
    cmd += ["--permission-mode", "dontAsk", "--allowedTools"] + allow_rules(windows)
    deny = deny_rules(windows)
    if cc.is_shim(claude):          # a rule with a quote would be re-read by cmd.exe (see cc.arg_ok_for): that one rule is left out, the others stay
        deny = [d for d in deny if cc.arg_ok_for(claude, d)]
    cmd += ["--disallowedTools"] + deny
    cmd += ["--append-system-prompt", CONFINEMENT]
    return cmd


def user_line(text: str) -> str:
    """One NDJSON line for standard input. ASCII-only JSON, so no console or code page can change the text."""
    return json.dumps({"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}, ensure_ascii=True) + "\n"


def repair_text(problems: str) -> str:
    return agy.repair_text(problems)


def reset_seconds(text: str) -> int | None:
    return cc.parse_reset_seconds(text)


def classify(text: str, events: list | None = None, api_status=None) -> tuple[str, str]:
    """A failure text of the program -> (code, English message). The owner's sentence of each code lives in bti/draft/run.py."""
    err = cc.classify(text, events, api_status)
    if getattr(err, "code", None) == "claude_outdated":          # the message is the owner's sentence, with the versions the answer stated
        return "claude_outdated", err.message
    code = CODES.get(err.kind, "claude_error")
    if code == "claude_error":
        return code, (text or "Claude Code reported an error").strip()[:300]
    return code, {"claude_auth": "Claude Code is not signed in", "claude_rate_limit": "the Claude plan's usage limit is reached",
                  "claude_model": "Claude Code does not know this model", "claude_timeout": "Claude Code did not answer in time"}[code]


def check_cli(claude: str, env: dict) -> None:
    """Refuse a build of the program that lacks an option this run needs. Cached per executable."""
    try:
        cc.check_cli(claude, env, REQUIRED_FLAGS)
    except ProviderError as e:
        raise DraftError("claude_config", e.message)


_BIG = 20000


def _compact(line: str) -> str:
    """A stream line for the transcript file: a picture the agent looked at arrives as base64 text of hundreds of kilobytes."""
    if len(line) <= _BIG:
        return line
    try:
        def cut(x):
            if isinstance(x, dict):
                return {k: cut(v) for k, v in x.items()}
            if isinstance(x, list):
                return [cut(v) for v in x]
            if isinstance(x, str) and len(x) > 2000:
                return x[:200] + "...[%d characters left out]" % (len(x) - 200)
            return x
        return json.dumps(cut(json.loads(line)), ensure_ascii=False)
    except ValueError:
        return line[:_BIG] + "...[left out]"


def run(ws_root: Path, *, model: str | None = None, timeout: float = 1800.0, max_repairs: int = 2, check=None, cancel=None,
        on_progress=None, transcript_path: Path | None = None, guard=None, prompt: str = PROMPT, python: str | None = None,
        claude: str | None = None, out_dir_name: str = "out", runner=None, conversation_id: str | None = None) -> AgyResult:
    """Run the agent. `runner` is `ctx.run_process` of the long job (cancel, the part limit and the process-tree kill are then the
    job's); without it a `DefaultRunner` is used. Raises DraftError before the program starts (not installed, too old, not a Claude
    id, another run in progress); once it has started, everything is reported in the returned AgyResult (never raised)."""
    import types
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise DraftError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    claude = claude or find_claude()
    if not claude:
        raise DraftError("claude_missing", "Claude Code (the `claude` command) is not installed on this machine")
    env = clean_env(python)
    check_cli(claude, env)
    cmd = build_command(claude, model)
    if not all(cc.arg_ok_for(claude, a) for a in cmd):
        raise DraftError("claude_config", "the `claude` found here is a Windows .cmd shim and an option of the run cannot pass through cmd.exe; install the native claude.exe")
    if not agy.LOCK.acquire(blocking=False):             # one agent run at a time, whichever runner
        raise DraftError("agy_busy", "another agent run is in progress")
    res = AgyResult()
    res.denials = []                                    # what the program refused to do (tool and a short sentence), for the record
    cancelled = _cancel_fn(cancel)
    runner = runner or DefaultRunner(cancelled).run_process
    S = types.SimpleNamespace(handle=None, final=False, timed_out=False, err="", events=[], seen_tools=set(), last_tick=0.0, names={},
                              refused_keys=set())
    tf = None
    t0 = time.time()
    done = threading.Event()
    out_dir = Path(ws_root) / out_dir_name

    def tick(force=False):
        if on_progress and (force or time.time() - S.last_tick >= 1.0):
            S.last_tick = time.time()
            try:
                n_out = len(list(out_dir.glob("*.json"))) if out_dir.is_dir() else 0
            except OSError:
                n_out = 0
            on_progress({"steps": res.steps, "last_action": res.last_action, "turn": res.turns, "out_files": n_out, "elapsed": time.time() - t0})

    def finish(status=None, code=None, message=""):
        if status:
            res.status = status
        if code:
            res.error_code, res.error_message = code, message
        S.final = True
        if S.handle is not None:
            S.handle.close_stdin()                      # the program leaves after the end of its input

    def on_err(line):
        S.err = (S.err + line + "\n")[-20000:]

    def refused(key, tool, text):
        """Record one refusal once (the stream tells it twice: as the tool's result and in the final `permission_denials`)."""
        if key in S.refused_keys or len(res.denials) >= 50:
            return
        if key is not None:
            S.refused_keys.add(key)
        res.denials.append({"tool": str(tool), "what": str(text)[:200]})

    def handle_event(ev):
        res.n_events += 1
        kind = ev.get("type")
        if kind == "assistant":
            content = (ev.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    tid = b.get("id")
                    S.names[tid] = b.get("name")
                    if tid is None or tid not in S.seen_tools:
                        res.steps += 1
                        if tid is not None:
                            S.seen_tools.add(tid)
                    res.last_action = STEP_NAMES.get(str(b.get("name")), str(b.get("name") or "tool_call"))
            tick()
        elif kind == "user":
            content = (ev.get("message") or {}).get("content")
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                    c = b.get("content")
                    txt = c if isinstance(c, str) else " ".join(str(x.get("text") or "") for x in c if isinstance(x, dict)) if isinstance(c, list) else ""
                    if "permission" in txt.lower() or "not allowed" in txt.lower() or "denied" in txt.lower():
                        refused(b.get("tool_use_id"), S.names.get(b.get("tool_use_id")) or "tool", txt)
            tick()
        elif kind == "rate_limit_event":
            S.events = (S.events + [ev])[-5:]
        elif kind == "result":
            r = ev
            if isinstance(r.get("permission_denials"), list):
                for d in r["permission_denials"]:
                    if isinstance(d, dict):
                        refused(d.get("tool_use_id"), d.get("tool_name"), json.dumps(d.get("tool_input"), ensure_ascii=False))
            text = str(r.get("result") or "")
            res.response = text
            sub = str(r.get("subtype") or "success")
            if r.get("is_error") or sub != "success":
                full = "%s %s %s" % (text, "" if sub == "success" else sub, S.err)
                code, msg = classify(full, S.events, r.get("api_error_status"))
                if code == "claude_rate_limit":
                    res.retry_after_seconds = cc.reset_from_events(S.events) or reset_seconds(full)
                return finish("error", code, msg)
            problems = check(res.turns) if check is not None else None
            if problems and res.repairs < max_repairs:
                res.repairs += 1
                res.turns += 1
                if S.handle is not None:
                    S.handle.write(user_line(repair_text(problems)))        # the same process, the same conversation
                tick(True)
                return None
            return finish("ok")
        else:
            tick()
        return None

    def on_line(line):
        if tf is not None:
            try:
                tf.write(_compact(line) + "\n")
                tf.flush()
            except (OSError, ValueError):
                pass
        line = line.strip()
        if not line.startswith("{") or S.final:
            if line and not line.startswith("{"):
                S.err = (S.err + line + "\n")[-20000:]          # a plain sentence on stdout (older builds print errors there)
            return
        try:
            ev = json.loads(line)
        except ValueError:
            return
        if isinstance(ev, dict):
            try:
                handle_event(ev)
            except Exception as e:      # noqa: BLE001 - a failure of our own check must not hang the run
                finish("error", "claude_error", "the run could not go on (%s)" % type(e).__name__)

    def on_start(h):
        S.handle = h

    def watchdog():
        while not done.wait(0.5):
            if time.time() - t0 > timeout and not S.final:
                S.timed_out = True
                h = S.handle
                if h is not None:
                    h.close_stdin()
                    kill_tree(h._proc)      # the runner has no kill of its own; this is the one place bti.proc is used directly
                return

    try:
        if transcript_path is not None:
            Path(transcript_path).parent.mkdir(parents=True, exist_ok=True)
            tf = open(transcript_path, "w", encoding="utf-8")
        if guard is not None:
            guard.before()
        res.turns = 1
        threading.Thread(target=watchdog, daemon=True).start()
        try:
            rc = runner(cmd, cwd=Path(ws_root), env=env, on_line=on_line, stdin=user_line(prompt), on_start=on_start,
                        separate_stderr=True, on_stderr=on_err)
        except OSError as e:
            raise DraftError("claude_config", "Claude Code could not be started: %s" % type(e).__name__)
        res.returncode = rc
        S.handle = None
        if not (S.final or S.timed_out or cancelled()):
            # the program ended without a final result: say why from what it printed
            code, msg = classify(S.err, S.events) if S.err.strip() else ("claude_no_result", "Claude Code ended without a result")
            if code == "claude_rate_limit":
                res.retry_after_seconds = cc.reset_from_events(S.events) or reset_seconds(S.err)
            finish("error", code, msg)
        if S.timed_out and res.status != "ok":
            res.status, res.error_code = "timeout", "claude_timeout"
            res.error_message = "the agent did not finish within %d seconds" % int(timeout)
        elif cancelled() and res.status != "ok":
            res.status = "cancelled"
        tick(True)
    finally:
        done.set()
        res.stderr_tail = S.err[-2000:]
        if tf is not None:
            try:
                tf.close()
            except OSError:
                pass
        res.elapsed = time.time() - t0
        try:
            if guard is not None:
                diffs = guard.after()
                if diffs:
                    res.status, res.tampered = "tampered", diffs[:50]
        finally:
            agy.LOCK.release()
    return res
