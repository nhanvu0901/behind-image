"""The exit codes of `bti` and the ONE table that maps what the server answered to one of them (documented in AGENTS.md, generated from here).

    0  done
    2  the command was typed wrong (nothing was sent)
    3  a person is needed: a gate the agent may not approve, a spend or a cost that is not confirmed or not allowed, a sign-in
    4  the data was refused: the server's `code`, `fix` and `fields` are printed
    5  busy: a job is running, a revision is stale, the service is not answering right now: call again
    6  the app cannot be reached
"""
from __future__ import annotations

from typing import Any

DONE, USAGE, PERSON, REFUSED, BUSY, UNREACHABLE = 0, 2, 3, 4, 5, 6

# (exit code, name, what it means for the agent, what to do)
EXIT_CODES: list[tuple[int, str, str, str]] = [
    (DONE, "done", "The command did what it was asked.", "Go on with the next command."),
    (USAGE, "usage", "The command was typed wrong (an unknown sub-command, a missing argument, an action id that does not exist). Nothing was sent.",
     "Read the message and the usage line, then type the command again."),
    (PERSON, "person_needed", "A person is needed: a gate the agent may not approve, a cost that is not confirmed (`--yes-cost`) or not allowed, "
     "a spend of money, a sign-in on the server.", "Stop and tell the owner what the line says; do not try another way round."),
    (REFUSED, "refused", "The data was refused (HTTP 4xx, or a job that failed): the server's `code`, `fix` and `fields` are printed.",
     "Do what `fix` says, then send the command again."),
    (BUSY, "busy", "Busy: a job of the same kind is running, a revision is stale, or the service is not answering right now.",
     "Wait (`bti job <id> --wait`), read the document again, then send the command again."),
    (UNREACHABLE, "unreachable", "The app cannot be reached (nothing listens at `BTI_URL`, the connection broke, or the answer was not the app's).",
     "Check that the app runs and that `BTI_URL` is right; do not retry in a loop."),
]
NAME_OF = {n: name for n, name, _, _ in EXIT_CODES}

# Codes that always need a person, whatever the status or the retry word says.
PERSON_CODES = frozenset({"gate_needs_human", "auto_needs_human", "spend_needs_human", "confirm_required", "agy_auth", "claude_auth",
                          "claude_outdated", "real_models_off"})
STALE_CODES = frozenset({"stale", "stale_revision"})

# The mapping from an HTTP answer to an exit code: the first rule that matches wins. (label, exit code); `exit_for_error` is this table in code.
MAPPING: list[tuple[str, int]] = [
    ("any 2xx answer", DONE),
    ("status 401 or 403, or a `code` of `gate_needs_human`, `auto_needs_human`, `spend_needs_human`, `confirm_required`, `agy_auth`, "
     "`claude_auth`, `claude_outdated`, `real_models_off`", PERSON),
    ("a stale revision (`code` `stale` or `stale_revision`)", BUSY),
    ("`retry` is `later` (a job is busy, a service is not answering, a quota opens later), whatever the status", BUSY),
    ("any other answer with a status of 400 or more (`retry` is `after_fix` or `no`)", REFUSED),
    ("no answer, a broken connection, a time-out, or an answer that is not JSON", UNREACHABLE),
]

# How a failed JOB ends: the job's `error_code` goes through the same rules (the `retry` word comes from the hint table of the server); a script job
# has an `error_kind` instead, which maps like this. A job that was cancelled or interrupted by a restart is busy (`later`: start it again).
JOB_KIND_EXIT = {"auth": PERSON, "timeout": BUSY, "rate_limit": BUSY, "http": BUSY, "empty": BUSY,
                 "config": REFUSED, "validation": REFUSED, "parse": REFUSED, "blocked": REFUSED, "conflict": REFUSED}


def retry_of(code: str | None) -> str | None:
    """The `retry` word of the server's hint table for `code` (None when this machine cannot load the table)."""
    if not code:
        return None
    try:
        from bti.editor.hints import HINTS
    except Exception:       # noqa: BLE001 - the command works without the app's code: the answer's own `retry` is used
        return None
    h = HINTS.get(code)
    return h["retry"] if h else None


def exit_for_error(status: int, body: Any) -> int:
    """The exit code of an error answer (status >= 400) with `body` (the decoded JSON, or None)."""
    if not isinstance(body, dict):
        return UNREACHABLE              # an error answer that is not the app's JSON (a proxy, another program on the port)
    code, retry = body.get("code"), body.get("retry")
    if status in (401, 403) or code in PERSON_CODES:
        return PERSON
    if code in STALE_CODES:
        return BUSY
    if retry == "later":
        return BUSY
    return REFUSED


def exit_for_job(job: dict) -> int:
    """The exit code of a job that has ended (`state` done, error, cancelled or interrupted)."""
    state = job.get("state")
    if state == "done":
        return DONE
    if state in ("cancelled", "interrupted"):
        return BUSY
    code = job.get("error_code")
    if code:
        if code in PERSON_CODES:
            return PERSON
        retry = retry_of(code)
        return BUSY if retry == "later" else REFUSED
    kind = job.get("error_kind")
    return JOB_KIND_EXIT.get(kind, REFUSED)
