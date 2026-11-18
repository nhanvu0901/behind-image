"""The agent run (design 7.3): Google Antigravity's `agy` as an unattended, auto-approved agent in a workspace of copies.

    agy --dangerously-skip-permissions --model <slug> --input-format stream-json --output-format stream-json
    working directory = the workspace; the prompt is one NDJSON line on standard input:
        {"event": "user", "message": {"content": "Read TASK.md in this folder and do the task."}}
    standard output is a stream of NDJSON events: `init`, many `step_update`, and one `result` per turn.

Containment: copies only (see workspace.py); an environment that holds only what the program needs plus the path of our Python;
one run at a time; a time limit for the whole run; cancel and time-out kill the whole process tree; the project folder is listed
before and after (guard.py) and a difference marks the run `tampered`.

After each turn the caller's `check` may return a text of problems; it is sent as the next turn of the same conversation, at most
`max_repairs` times. Nothing here reads the workspace's results: that is `workspace.read_out`.

Everything about the real program that is assumed and not verified is listed in docs/qa/BUILD_draft.md, "For the live test".
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from bti.proc import IS_WINDOWS, group_kwargs, kill_tree

from ..inputs import DraftError

PROMPT = "Read TASK.md in this folder and do the task."
LOCK = threading.Lock()                     # one agent run at a time
HELP_TIMEOUT = 30
EXIT_WAIT_S = 15.0
_ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "SHELL", "TERM", "XDG_CONFIG_HOME", "XDG_DATA_HOME")
_ENV_KEEP_WINDOWS = ("PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "USERNAME", "USERPROFILE", "USERDOMAIN",
                     "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
                     "COMMONPROGRAMFILES", "ALLUSERSPROFILE", "TEMP", "TMP", "COMPUTERNAME", "OS")
_HELP_OK: dict = {}


@dataclass
class AgyResult:
    status: str = "error"            # ok | timeout | cancelled | error | tampered
    turns: int = 0
    steps: int = 0
    last_action: str = ""
    conversation_id: str | None = None
    error_code: str | None = None
    error_message: str = ""
    retry_after_seconds: int | None = None   # for agy_rate_limit: seconds until the quota resets, when agy printed it
    tampered: list = field(default_factory=list)
    elapsed: float = 0.0
    returncode: int | None = None
    response: str = ""
    stderr_tail: str = ""
    n_events: int = 0
    repairs: int = 0


def find_agy() -> str | None:
    forced = os.environ.get("BTI_AGY_BIN")              # tests and odd installs: an exact path, no search
    if forced is not None:
        return forced if forced and os.access(forced, os.X_OK) else None
    p = shutil.which("agy")
    if p:
        return p
    names = ("agy.exe", "agy.cmd") if IS_WINDOWS else ("agy",)
    spots = [Path.home() / ".local" / "bin"]
    if IS_WINDOWS and os.environ.get("LOCALAPPDATA"):
        spots.append(Path(os.environ["LOCALAPPDATA"]) / "agy" / "bin")
    for d in spots:
        for n in names:
            if (d / n).is_file():
                return str(d / n)
    return None


def clean_env(python: str | None = None) -> dict:
    """Only what the program needs to find its login and run, plus BTI_PYTHON (the Python of the helper commands)."""
    keep = _ENV_KEEP + (_ENV_KEEP_WINDOWS if IS_WINDOWS else ())
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    env.setdefault("TERM", "dumb")
    if python:
        env["BTI_PYTHON"] = str(python)
    env["PYTHONUTF8"] = "1"
    return env


def build_command(agy: str, model: str | None) -> list[str]:
    from bti.settings import model_for
    m = model or model_for("draft")
    slug = m[len("agy:"):] if m.startswith("agy:") else m
    return [agy, "--dangerously-skip-permissions", "--model", slug, "--input-format", "stream-json",
            "--output-format", "stream-json"]


def user_line(text: str) -> str:
    """One NDJSON line for standard input. ASCII-only JSON, so no console or code page can change the text."""
    return json.dumps({"event": "user", "message": {"content": text}}, ensure_ascii=True) + "\n"


def repair_text(problems: str) -> str:
    return ("The check found problems in your files in out/. Fix them in the same files, run the check again, and repeat until it "
            "reports no errors. Do not change anything else. Problems:\n\n" + problems)


def reset_seconds(text: str) -> int | None:
    """`Resets in 2m56s` and the like (one parser, shared with the single-turn provider)."""
    from bti.script.providers.antigravity import parse_reset_seconds
    return parse_reset_seconds(text)


def classify(text: str) -> tuple[str, str]:
    t = (text or "").lower()
    if any(k in t for k in ("authentication required", "not logged in", "please log in", "login required", "sign in", "unauthenticated", "credentials")):
        return "agy_auth", "agy is not signed in"
    if any(k in t for k in ("quota", "exhausted", "rate limit", "rate_limit", "429", "resource_exhausted", "too many requests")):
        return "agy_rate_limit", "the Antigravity plan quota is used up or calls are limited"
    if "model" in t and any(k in t for k in ("unknown", "not found", "invalid", "unsupported", "not available")):
        return "agy_model", "agy does not know this model"
    return "agy_error", (text or "agy reported an error").strip()[:300]


def check_cli(agy: str, env: dict) -> None:
    """Refuse a build of agy that lacks the flags this run needs. Cached per executable."""
    if agy in _HELP_OK:
        err = _HELP_OK[agy]
    else:
        err = None
        work = tempfile.mkdtemp(prefix="bti-agy-")
        try:
            r = subprocess.run([agy, "--help"], cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=HELP_TIMEOUT, **group_kwargs())
            text = (r.stdout or "") + (r.stderr or "")
            missing = [f for f in ("--input-format", "--dangerously-skip-permissions", "--model") if f not in text]
            if missing:
                err = "this agy is too old (missing %s)" % ", ".join(missing)
        except (subprocess.TimeoutExpired, OSError):
            err = "`agy --help` did not answer"
        finally:
            shutil.rmtree(work, ignore_errors=True)
        _HELP_OK[agy] = err
    if err:
        raise DraftError("agy_config", err)


def _cancel_fn(cancel):
    if cancel is None:
        return lambda: False
    if hasattr(cancel, "is_set"):
        return cancel.is_set
    return cancel


class DefaultRunner:
    """`run_process` for use outside a long job (tests, a command line): the same interface as `Context.run_process` of bti.longjob
    (stdin, on_start with a handle, separate stderr), with the process tree killed on cancel. Inside a job the runner of the
    job is passed to `run` instead, so that cancel, the part limit and the tree kill are the job's."""

    def __init__(self, cancelled):
        self.cancelled = cancelled

    def run_process(self, cmd, cwd=None, env=None, on_line=None, *, stdin=None, on_start=None, separate_stderr=False, on_stderr=None) -> int:
        from bti.longjob.manager import ProcessHandle
        if self.cancelled():
            return -1
        proc = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE if separate_stderr else subprocess.STDOUT, text=True, encoding="utf-8",
                                errors="replace", bufsize=1, **group_kwargs())
        handle = ProcessHandle(proc)

        def pump(stream, cb):
            try:
                for line in stream:
                    if cb is not None:
                        try:
                            cb(line.rstrip("\r\n"))
                        except Exception:       # noqa: BLE001
                            pass
            except (OSError, ValueError):
                pass
        readers = [threading.Thread(target=pump, args=(proc.stdout, on_line), daemon=True)]
        if separate_stderr:
            readers.append(threading.Thread(target=pump, args=(proc.stderr, on_stderr), daemon=True))
        for r in readers:
            r.start()
        try:
            if stdin is not None:
                handle.write(stdin)
            if on_start is None:
                handle.close_stdin()
            else:
                on_start(handle)
            while True:
                try:
                    proc.wait(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancelled():
                        kill_tree(proc)
                        break
        finally:
            if proc.poll() is None:
                kill_tree(proc)
            for r in readers:
                r.join(timeout=5)
            for st in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if st is not None:
                        st.close()
                except (OSError, ValueError):
                    pass
        return -1 if proc.returncode is None else int(proc.returncode)


def run(ws_root: Path, *, model: str | None = None, timeout: float = 1800.0, max_repairs: int = 2, check=None, cancel=None,
        on_progress=None, transcript_path: Path | None = None, guard=None, prompt: str = PROMPT, python: str | None = None,
        agy: str | None = None, out_dir_name: str = "out", runner=None, conversation_id: str | None = None) -> AgyResult:
    """Run the agent. `runner` is `ctx.run_process` of the long job (cancel, the part limit and the process-tree kill are then the
    job's); without it a `DefaultRunner` is used. Raises DraftError before the program starts (not installed, too old, another
    run in progress); once it has started, everything is reported in the returned AgyResult (never raised).

    Own work, because the runner offers no way to do it: the 30 minute limit of the whole run kills the tree through bti.proc
    (`kill_tree` on the handle's process) and keeps the partial result."""
    import types
    if os.environ.get("BTI_NO_REAL_MODELS") == "1":
        raise DraftError("real_models_off", "real models are disabled (BTI_NO_REAL_MODELS=1)")
    agy = agy or find_agy()
    if not agy:
        raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")
    env = clean_env(python)
    check_cli(agy, env)
    if not LOCK.acquire(blocking=False):
        raise DraftError("agy_busy", "another agent run is in progress")
    res = AgyResult()
    cancelled = _cancel_fn(cancel)
    runner = runner or DefaultRunner(cancelled).run_process
    S = types.SimpleNamespace(handle=None, pending=None, final=False, timed_out=False, err="", quota="", respawns=0, last_tick=0.0)
    seen_steps: set = set()
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
            S.handle.close_stdin()

    def on_err(line):
        S.err = (S.err + line + "\n")[-20000:]

    def handle_event(ev):
        res.n_events += 1
        name = ev.get("event")
        if name == "step_update" and isinstance(ev.get("step_update"), dict):
            su = ev["step_update"]
            idx = su.get("step_index")
            if idx is None or idx not in seen_steps:
                res.steps += 1
                if idx is not None:
                    seen_steps.add(idx)
            if su.get("step_type"):
                res.last_action = str(su["step_type"])
            tick()
        elif name == "init":
            if isinstance(ev.get("conversation_id"), str):
                res.conversation_id = ev["conversation_id"]
        elif name == "result" and isinstance(ev.get("result"), dict):
            r = ev["result"]
            S.pending = None
            if isinstance(r.get("conversation_id"), str):
                res.conversation_id = r["conversation_id"]
            status = str(r.get("status") or "")
            res.response = str(r.get("response") or "")
            if status == "CANCELED":
                return finish("cancelled")
            if status != "SUCCESS":
                text = "%s %s %s" % (r.get("error") or "", S.err, S.quota)
                code, msg = classify(text)
                if code == "agy_rate_limit":
                    res.retry_after_seconds = reset_seconds(text + " " + res.response)
                return finish("error", code, msg)
            problems = check(res.turns) if check is not None else None
            if problems and res.repairs < max_repairs:
                res.repairs += 1
                res.turns += 1
                S.pending = user_line(repair_text(problems))
                if S.handle is not None:
                    S.handle.write(S.pending)           # when the program already ended the write is ignored: it is restarted below
                tick(True)
                return None
            return finish("ok")
        else:
            tick()
        return None

    def on_line(line):
        if tf is not None:
            try:
                tf.write(line + "\n")
                tf.flush()
            except (OSError, ValueError):
                pass
        line = line.strip()
        low = line.lower()
        if "quota" in low or "429" in low or "resets in" in low or "reset in" in low:      # kept: the reset time is printed there
            S.quota = (S.quota + line + "\n")[-4000:]
        if not line.startswith("{") or S.final:
            return
        try:
            ev = json.loads(line)
        except ValueError:
            return
        if isinstance(ev, dict):
            try:
                handle_event(ev)
            except Exception as e:      # noqa: BLE001 - a failure of our own check must not hang the run
                finish("error", "agy_error", "the run could not go on (%s)" % type(e).__name__)

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
        cmd = build_command(agy, model)
        res.turns = 1
        threading.Thread(target=watchdog, daemon=True).start()
        first, extra = user_line(prompt), []
        if conversation_id:
            res.conversation_id = str(conversation_id)
            extra = ["--conversation", str(conversation_id)]
        while True:
            try:
                rc = runner(cmd + extra, cwd=Path(ws_root), env=env, on_line=on_line, stdin=first, on_start=on_start,
                            separate_stderr=True, on_stderr=on_err)
            except OSError as e:
                raise DraftError("agy_config", "agy could not be started: %s" % type(e).__name__)
            res.returncode = rc
            S.handle = None
            if S.final or S.timed_out or cancelled():
                break
            if S.pending and res.conversation_id and S.respawns <= max_repairs:
                S.respawns += 1                          # the program ended after its turn: continue the same conversation
                extra, first = ["--conversation", res.conversation_id], S.pending
                continue
            code, msg = classify(S.err + " " + S.quota)
            if code == "agy_rate_limit":
                res.retry_after_seconds = reset_seconds(S.err + " " + S.quota)
            if S.err.strip() or S.quota.strip():
                finish("error", code, msg)
            else:
                finish("error", "agy_no_result", "agy ended without a result")
            break
        if S.timed_out and res.status != "ok":
            res.status, res.error_code = "timeout", "agy_timeout"
            res.error_message = "the agent did not finish within %d seconds" % int(timeout)
        elif cancelled() and res.status != "ok":
            res.status = "cancelled"
        tick(True)
    finally:
        done.set()
        res.stderr_tail = S.err[-2000:]
        if res.status == "error":
            # the result event can arrive before the reader of stderr has the quota sentence: look again with everything read
            full = S.err + " " + S.quota
            if res.error_code in (None, "agy_error") and classify(full)[0] == "agy_rate_limit":
                res.error_code, res.error_message = classify(full)
            if res.error_code == "agy_rate_limit" and res.retry_after_seconds is None:
                res.retry_after_seconds = reset_seconds(full + " " + res.response)
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
            LOCK.release()
    return res
