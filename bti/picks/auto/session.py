"""One session of the agent in a work folder (both runners: Antigravity's `agy` and Claude Code's `claude`).

The runners are those of the storyboard draft (`bti/draft/providers/`): the same command lines, the same confinement (the folder holds
copies only; `claude` may write only under out/ and run only the helper commands this job names; the project is listed before and after
by the draft's guard), the same repair message sent into the SAME conversation, the same result object. What is added here:

  * limits against a run that never ends: a time limit and a limit of steps (tool calls) per session, and one repair round. The time limit
    is the runner's own watchdog; the step limit is ours (the progress events count the steps, and the process tree is ended when the count
    passes the limit). Both are in the progress line the page shows.
  * the check after each turn is the program's own check of the output file (`helper.run_check`), the same that `./check` prints.

Nothing here reads the output file: the caller does, with the same check, and accepts a file that is valid even when the session ended
on a limit (a valid plan or choice is complete by construction: the check wants every line and every wanted picture).
"""
from __future__ import annotations

import threading
import types
from dataclasses import dataclass, field
from pathlib import Path

from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.proc import IS_WINDOWS, kill_tree

from . import texts


@dataclass(frozen=True)
class Limits:
    minutes: float
    steps: int
    repairs: int = 1

    def public(self) -> dict:
        return {"minutes": self.minutes, "steps": self.steps, "repairs": self.repairs}


# The limits of a session belong to the job that runs it (the pictures job: `bti.picks.auto.job.PLAN_LIMITS` and `CHOOSE_LIMITS`; the title job: `bti.title.job.LIMITS`):
# this module holds none, so that there is one place for each number.


@dataclass
class Outcome:
    status: str = "error"             # ok | cancelled | limit | timeout | error | tampered
    code: str | None = None
    message: str = ""
    steps: int = 0
    turns: int = 0
    repairs: int = 0
    elapsed: float = 0.0
    retry_after_seconds: int | None = None
    tampered: list = field(default_factory=list)
    transcript: Path | None = None


# ---------------------------------------------------------------------------------------------------------------- seams (tests replace them)
def agent_module(model_id: str | None):
    """The runner of a model id: Claude Code for `claude:<model>@<effort>`, else Antigravity (the draft's own rule)."""
    return draft_run._agent_module(model_id)


def check_installed(model_id: str | None) -> None:
    """Before a job starts: the runner of this model is installed (and Claude Code not known to be signed out). Raises DraftError."""
    draft_run._check_agent_installed(model_id)


HELPERS = ("check", "crop")        # the helper commands of the pictures job's work folder; another job names its own (the title job has `check` only)


def allow_rules(windows: bool | None = None, helpers: tuple = HELPERS) -> list[str]:
    """The permission rules of a `claude` session: write under out/, run the `helpers` (`./check`, and `./crop` for the pictures job) in the shapes TASK.md shows,
    and nothing else. (The deny rules are the draft's: no path that leaves the folder, no command substitution, no web.)"""
    from bti.draft.providers import claudecode as dcc
    win = IS_WINDOWS if windows is None else windows
    out = ["Edit(./out/**)"]
    if "check" in helpers:
        for f in dcc._forms("check", win):
            out += [f"Bash({f})", f"Bash({f} --help)"]
    if "crop" in helpers:
        for f in dcc._forms("crop", win):
            out += [f"Bash({f} --help)", f"Bash({f} --box * -o look/*)", f"Bash({f} --box * -o look/* --width *)",
                    f"Bash({f} --box * --width * -o look/*)", f"Bash({f} --grid -o look/*)"]
    return out


def _guard(project_dir: Path):
    from bti.draft.guard import Guard
    return Guard(project_dir)


# ---------------------------------------------------------------------------------------------------------------- the session
def run_session(ws_root: Path, *, model: str, project_dir: Path, ctx=None, label: str, limits: Limits, check_fn, transcript: Path | None = None,
                python: str | None = None, guard_factory=None, on_note=None, allow: list[str] | None = None) -> Outcome:
    """Run the agent in `ws_root` until it is done, the limits stop it, the job is cancelled or it fails. `check_fn()` returns the text of
    the problems of the output file (None when it is valid): it is the check after each turn and so the repair message. `ctx` is the long
    job's context (cancel, progress, the runner that kills the process tree). `allow`: the permission rules of a `claude` session (`allow_rules(helpers=...)`:
    the helper commands of THIS job's work folder); None is the pictures job's (`./check` and `./crop`). Raises `DraftError` before the program starts (not installed ...)."""
    mod = agent_module(model)
    guard = guard_factory(project_dir) if guard_factory else _guard(project_dir)
    hit = threading.Event()                                           # the step limit was reached
    box = types.SimpleNamespace(handle=None)

    def cancelled() -> bool:
        return bool(ctx.cancelled()) if ctx is not None else False

    base = ctx.run_process if ctx is not None else _default_runner(lambda: cancelled() or hit.is_set()).run_process

    def runner(cmd, cwd=None, env=None, on_line=None, *, stdin=None, on_start=None, separate_stderr=False, on_stderr=None):
        def started(h):
            box.handle = h
            if on_start is not None:
                on_start(h)
            if hit.is_set():                                          # the limit was reached before the handle was known
                stop_now()
        return base(cmd, cwd=cwd, env=env, on_line=on_line, stdin=stdin, on_start=started, separate_stderr=separate_stderr, on_stderr=on_stderr)

    def stop_now():
        h = box.handle
        if h is not None:
            try:
                h.close_stdin()
                kill_tree(h._proc)                                    # the one place the tree is ended on our own account (as agy.run's watchdog does)
            except Exception:       # noqa: BLE001
                pass

    def on_progress(p):
        steps, elapsed = int(p.get("steps") or 0), float(p.get("elapsed") or 0)
        if steps > limits.steps:
            hit.set()
            stop_now()                                                # (again on every tick: the first one may come before the handle exists)
        frac = min(0.95, max(steps / float(max(1, limits.steps)), elapsed / max(1.0, limits.minutes * 60.0)))
        line = texts.progress_session(label, min(steps, limits.steps), limits.steps, elapsed, limits.minutes)
        if ctx is not None:
            ctx.progress(frac, line)
        if on_note is not None:
            on_note(line)

    def check(turn):
        return check_fn()

    kw = {}
    if getattr(mod, "SUPPORTS_ALLOW", False):
        kw["allow"] = allow_rules() if allow is None else list(allow)
    a = mod.run(Path(ws_root), model=model, timeout=limits.minutes * 60.0, max_repairs=limits.repairs, check=check,
                cancel=lambda: cancelled() or hit.is_set(), on_progress=on_progress, transcript_path=transcript, guard=guard, python=python,
                runner=runner, **kw)
    out = Outcome(steps=int(getattr(a, "steps", 0) or 0), turns=int(getattr(a, "turns", 0) or 0), repairs=int(getattr(a, "repairs", 0) or 0),
                  elapsed=float(getattr(a, "elapsed", 0) or 0), transcript=transcript)
    status = getattr(a, "status", "error")
    if status == "tampered":
        out.status, out.code, out.tampered = "tampered", "picks_auto_tampered", list(getattr(a, "tampered", []) or [])
        out.message = texts.vi("picks_auto_tampered") + " (" + ", ".join(out.tampered[:5]) + ")"
    elif hit.is_set() and status != "ok":
        out.status, out.code, out.message = "limit", "picks_auto_limit", texts.vi("picks_auto_limit")
    elif status == "cancelled":
        out.status = "cancelled"
    elif status == "timeout":
        out.status = "timeout"
        out.code = getattr(a, "error_code", None) or "agy_timeout"
        out.message = draft_run.vi(out.code, getattr(a, "error_message", ""))
    elif status == "error":
        out.status = "error"
        out.code = getattr(a, "error_code", None) or "agy_error"
        wait = getattr(a, "retry_after_seconds", None) if out.code in draft_run.RATE_LIMIT_CODES else None
        out.retry_after_seconds = wait
        out.message = (draft_run.rate_limit_sentence(out.code, wait) if out.code in draft_run.RATE_LIMIT_CODES
                       else draft_run.vi(out.code, getattr(a, "error_message", "")))
    else:
        out.status = "ok"
    return out


def _default_runner(cancel):
    from bti.draft.providers import agy
    return agy.DefaultRunner(cancel)


def refuse_text(e: DraftError) -> str:
    """The owner's sentence of a refusal before the program started (not installed, not signed in, ...)."""
    return draft_run.vi(e.code, e.message)
