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

DEFAULT_MODEL = "gemini-pro-orchestrator-g1-pro"
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
    return [agy, "--dangerously-skip-permissions", "--model", model or DEFAULT_MODEL, "--input-format", "stream-json",
            "--output-format", "stream-json"]


def user_line(text: str) -> str:
    """One NDJSON line for standard input. ASCII-only JSON, so no console or code page can change the text."""
    return json.dumps({"event": "user", "message": {"content": text}}, ensure_ascii=True) + "\n"


def repair_text(problems: str) -> str:
    return ("The check found problems in your files in out/. Fix them in the same files, run the check again, and repeat until it "
            "reports no errors. Do not change anything else. Problems:\n\n" + problems)


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


class _Proc:
    """The child, with a thread that reads its events into a queue and a thread that keeps the tail of its error output."""

    def __init__(self, cmd: list[str], cwd: Path, env: dict, transcript):
        self.p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, encoding="utf-8", errors="replace", bufsize=1, **group_kwargs())
        self.q: queue.Queue = queue.Queue()
        self.err = ""
        self.transcript = transcript
        threading.Thread(target=self._read_out, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()

    def _read_out(self):
        try:
            for line in self.p.stdout:
                line = line.strip()
                if not line:
                    continue
                if self.transcript is not None:
                    try:
                        self.transcript.write(line + "\n")
                        self.transcript.flush()
                    except (OSError, ValueError):
                        pass
                if line.startswith("{"):
                    try:
                        ev = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ev, dict):
                        self.q.put(("ev", ev))
        except (OSError, ValueError):
            pass
        self.q.put(("eof", None))

    def _read_err(self):
        try:
            for line in self.p.stderr:
                self.err = (self.err + line)[-20000:]
        except (OSError, ValueError):
            pass

    def send(self, text: str) -> bool:
        try:
            self.p.stdin.write(text)
            self.p.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def alive(self) -> bool:
        return self.p.poll() is None

    def finish(self, grace: float = EXIT_WAIT_S) -> None:
        try:
            self.p.stdin.close()
        except (OSError, ValueError):
            pass
        end = time.time() + grace
        while self.alive() and time.time() < end:
            time.sleep(0.05)
        if self.alive():
            kill_tree(self.p)


def _cancel_fn(cancel):
    if cancel is None:
        return lambda: False
    if hasattr(cancel, "is_set"):
        return cancel.is_set
    return cancel


def run(ws_root: Path, *, model: str | None = None, timeout: float = 1800.0, max_repairs: int = 2, check=None, cancel=None,
        on_progress=None, transcript_path: Path | None = None, guard=None, prompt: str = PROMPT, python: str | None = None,
        agy: str | None = None, out_dir_name: str = "out") -> AgyResult:
    """Run the agent. Raises DraftError before the program starts (not installed, too old, another run in progress); once it has
    started, everything is reported in the returned AgyResult (never raised)."""
    agy = agy or find_agy()
    if not agy:
        raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")
    env = clean_env(python)
    check_cli(agy, env)
    if not LOCK.acquire(blocking=False):
        raise DraftError("agy_busy", "another agent run is in progress")
    res = AgyResult()
    cancelled = _cancel_fn(cancel)
    proc = None
    tf = None
    t0 = time.time()
    seen_steps: set = set()
    try:
        if transcript_path is not None:
            Path(transcript_path).parent.mkdir(parents=True, exist_ok=True)
            tf = open(transcript_path, "w", encoding="utf-8")
        if guard is not None:
            guard.before()
        cmd = build_command(agy, model)
        try:
            proc = _Proc(cmd, Path(ws_root), env, tf)
        except OSError as e:
            raise DraftError("agy_config", "agy could not be started: %s" % type(e).__name__)
        proc.send(user_line(prompt))
        res.turns = 1
        awaiting = True
        last_msg = None                      # the repair text last sent, kept so that it can be sent once more to a restarted program
        resent = False
        last_tick = 0.0
        out_dir = Path(ws_root) / out_dir_name

        def tick(force=False):
            nonlocal last_tick
            if on_progress and (force or time.time() - last_tick >= 1.0):
                last_tick = time.time()
                try:
                    n_out = len(list(out_dir.glob("*.json"))) if out_dir.is_dir() else 0
                except OSError:
                    n_out = 0
                on_progress({"steps": res.steps, "last_action": res.last_action, "turn": res.turns, "out_files": n_out,
                             "elapsed": time.time() - t0})

        while True:
            if cancelled():
                res.status = "cancelled"
                break
            if time.time() - t0 > timeout:
                res.status = "timeout"
                res.error_code = "agy_timeout"
                res.error_message = "the agent did not finish within %d seconds" % int(timeout)
                break
            try:
                kind, ev = proc.q.get(timeout=0.2)
            except queue.Empty:
                tick()
                continue
            if kind == "eof":
                if awaiting and last_msg is not None and not resent and res.conversation_id and not cancelled():
                    resent = True                    # the program ended just as the repair turn arrived: continue the conversation in a new one
                    proc.finish(1.0)
                    proc = _Proc(cmd + ["--conversation", res.conversation_id], Path(ws_root), env, tf)
                    if proc.send(last_msg):
                        continue
                if awaiting:
                    code, msg = classify(proc.err)
                    res.status, res.error_code = "error", code if proc.err.strip() else "agy_no_result"
                    res.error_message = msg if proc.err.strip() else "agy ended without a result"
                break
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
                awaiting, last_msg, resent = False, None, False
                if isinstance(r.get("conversation_id"), str):
                    res.conversation_id = r["conversation_id"]
                status = str(r.get("status") or "")
                res.response = str(r.get("response") or "")
                if status == "CANCELED":
                    res.status = "cancelled"
                    break
                if status != "SUCCESS":
                    res.status = "error"
                    res.error_code, res.error_message = classify("%s %s" % (r.get("error") or "", proc.err))
                    break
                problems = check(res.turns) if check is not None else None
                if problems and res.repairs < max_repairs:
                    res.repairs += 1
                    res.turns += 1
                    msg = user_line(repair_text(problems))
                    sent = proc.alive() and proc.send(msg)
                    if not sent and res.conversation_id:             # the program ended after its turn: continue the same conversation
                        proc.finish(1.0)
                        proc = _Proc(cmd + ["--conversation", res.conversation_id], Path(ws_root), env, tf)
                        sent = proc.send(msg)
                    if not sent:
                        res.status, res.error_code, res.error_message = "error", "agy_no_result", "the repair turn could not be sent"
                        break
                    last_msg = msg
                    awaiting = True
                    tick(True)
                    continue
                res.status = "ok"
                break
            else:
                tick()
        tick(True)
    finally:
        if proc is not None:
            if res.status in ("cancelled", "timeout"):
                kill_tree(proc.p)
            proc.finish(EXIT_WAIT_S if res.status == "ok" else 2.0)
            res.returncode = proc.p.returncode
            res.stderr_tail = proc.err[-2000:]
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
