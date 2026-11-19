"""The sub-commands of `bti`. See `bti/cli/__init__.py` for the list and `bti/cli/exitcodes.py` for the exit codes.

A command reads the state answer of the project (`GET /api/projects/{pid}/state`) and calls an action exactly as the answer describes it: its
method, its path and its example body with the caller's fields filled in. It works for any action the answer lists, not for a fixed list.
Whatever the server refuses is printed as the server said it (`code`, `detail`, `fix`, `fields`) and mapped to an exit code by the one table
in `exitcodes.py`. Nothing here reads or writes a project's files.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from . import exitcodes as X
from . import render as R
from .transport import DEFAULT_URL, HttpTransport, Reply, Transport, Unreachable

REPO = Path(__file__).resolve().parents[2]
PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
ACTOR_RE = re.compile(r"^(agent:[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,79}|cli:[A-Za-z0-9][A-Za-z0-9._-]{0,39})$")     # the forms `bti.ops` and `bti.auto` take, minus `human`
DEFAULT_ACTOR = "cli:bti"
GATES = R.GATES
DOC_STEPS = ("script", "voice", "picks", "storyboard", "export")
DOC_ALIAS = {"edit": "storyboard"}
OPS_DOCS = ("picks", "storyboard")
FINAL_STATES = ("done", "error", "cancelled", "interrupted")

# (name, usage, one line): the sub-commands, in the order the help and the documents list them
COMMANDS: list[tuple[str, str, str]] = [
    ("status", "bti status [project]", "Where a project stands, what blocks it, what can be done now and the next command (no project: the list of projects)."),
    ("do", "bti do <project> <action id> [--body FILE | --set key=value ...] [--wait] [--yes-cost]",
     "Call one action of the state answer. An action that is not ready is refused with its needs; one that costs runs only with --yes-cost."),
    ("approve", "bti approve <project> <gate>", "Approve outline, narration, picks or storyboard; refused (exit 3) when the owner did not allow an agent to approve it."),
    ("ops", "bti ops <project> picks|storyboard --file ops.json [--dry-run] [--note TEXT]",
     "Send a batch of typed operations (the command reads the current revision itself) and print the changes."),
    ("job", "bti job <id> [--wait] [--cancel]", "Look at a long job, follow it to its end, or stop it."),
    ("undo", "bti undo <project> <batch>", "Undo one batch of operations."),
    ("changes", "bti changes <project> [picks|storyboard]", "The change log of the project, newest batch first."),
    ("schema", "bti schema ops picks|storyboard", "The operations of a document with their schemas and examples."),
    ("doc", "bti doc [step]", "Print the skill document of a step (script, voice, picks, storyboard, export); without a step, AGENTS.md."),
]
COMMON_OPTIONS = [("--json", "Print the server's JSON (or one JSON object of the command's own on an error) instead of text; the progress lines of `--wait` then go to stderr."),
                  ("--actor NAME", "Who is calling, sent wherever the API takes an actor: `cli:NAME` (default `cli:bti`, or `BTI_ACTOR`); `agent:<model id>` is kept as it is; `human` is refused."),
                  ("--url URL", "The app's address (default `BTI_URL`, else http://127.0.0.1:8560)."),
                  ("--timeout SECONDS", "How long one request may take (default 60).")]


class Stop(Exception):
    """Unwinds to `main` after the failure was printed."""

    def __init__(self, code: int):
        super().__init__(code)
        self.code = code


class UsageError(Exception):
    pass


# --------------------------------------------------------------------------------------------------------------------- the context
class Ctx:
    def __init__(self, args: argparse.Namespace, transport: Transport, out, err, sleep: Callable[[float], None], clock: Callable[[], float]):
        self.args, self.transport, self.out, self.err, self.sleep, self.clock = args, transport, out, err, sleep, clock
        self.json = bool(getattr(args, "json", False))
        self.timeout = float(getattr(args, "timeout", None) or 60.0)
        self.actor = resolve_actor(getattr(args, "actor", None), getattr(args, "_env", {}))

    # -- output
    def line(self, text: str, stream=None) -> None:
        (stream or self.out).write(text + "\n")

    def lines(self, lines: list[str]) -> None:
        for t in lines:
            self.line(t)

    def success(self, data: Any, lines: list[str]) -> int:
        if self.json:
            self.line(json.dumps(data, ensure_ascii=False))
        else:
            self.lines(lines)
        return X.DONE

    def progress(self, text: str) -> None:
        """One line per change of a followed job: on stdout in text mode, on stderr in JSON mode (stdout stays one JSON document)."""
        self.line(text, self.err if self.json else self.out)

    def fail(self, exit_code: int, code: str, detail: str, *, fix: str | None = None, retry: str | None = None, lines: list[str] | None = None,
             **extra: Any) -> int:
        """Print a refusal and return its exit code. `extra` keys go to the JSON object (and, when not None, nowhere else)."""
        payload: dict[str, Any] = {"ok": False, "exit": exit_code, "exit_name": X.NAME_OF[exit_code], "code": code, "detail": detail}
        if fix:
            payload["fix"] = fix
        if retry:
            payload["retry"] = retry
        for k, v in extra.items():
            if v is not None:
                payload.setdefault(k, v)                       # what the server added (`fields`, `current_rev`, `gate`, ...) never replaces the command's own keys
        if self.json:
            self.line(json.dumps(payload, ensure_ascii=False))
            return exit_code
        head = {X.USAGE: "usage", X.PERSON: "a person is needed", X.REFUSED: "refused", X.BUSY: "busy", X.UNREACHABLE: "cannot reach the app"}[exit_code]
        status = payload.get("status")
        self.line("%s: %s%s" % (head, code, " (HTTP %s)" % status if status else ""), self.err)
        self.line("  detail: " + detail, self.err)
        if fix:
            self.line("  fix: " + fix, self.err)
        for f in payload.get("fields") or []:
            if isinstance(f, dict):
                allowed = " (allowed: %s)" % ", ".join(str(x) for x in f["allowed"][:12]) if isinstance(f.get("allowed"), list) else ""
                self.line("  field %s: %s%s" % (f.get("path"), f.get("problem"), allowed), self.err)
        for i in [i for i in payload.get("issues") or [] if isinstance(i, dict)][:8]:
            self.line("  issue %s %s: %s" % (i.get("level"), i.get("path") or i.get("shot") or "", i.get("message")), self.err)
        for k in ("current_rev", "needs", "listed", "retry_after_seconds"):
            if payload.get(k) not in (None, [], ""):
                self.line("  %s: %s" % (k, ", ".join(str(x) for x in payload[k]) if isinstance(payload[k], list) else payload[k]), self.err)
        if lines:
            for t in lines:
                self.line("  " + t, self.err)
        return exit_code

    def server_failure(self, reply: Reply) -> int:
        """Print what the server refused with and return the exit code the table of `exitcodes.py` gives."""
        body = reply.data if isinstance(reply.data, dict) else None
        code = X.exit_for_error(reply.status, body)
        if body is None:
            return self.fail(X.UNREACHABLE, "not_the_app", "The answer (HTTP %d) is not the app's JSON: %s" % (reply.status, (reply.text or "empty")[:120]),
                             fix="Check that BTI_URL points at the app and that nothing else answers on that port.", status=reply.status)
        extra = {k: v for k, v in body.items() if k not in ("detail", "code", "fix", "retry")}
        return self.fail(code, str(body.get("code") or "error"), R.detail_text(body.get("detail")), fix=body.get("fix"), retry=body.get("retry"),
                         status=reply.status, **extra)

    # -- http
    def call(self, method: str, path: str, body: Any = None) -> Reply:
        try:
            reply = self.transport.request(method, path, body, self.timeout)
        except Unreachable as e:
            raise Stop(self.fail(X.UNREACHABLE, "unreachable", "Cannot reach the app: %s" % e,
                                 fix="Check that the app runs and that BTI_URL (or --url) is right; do not retry in a loop."))
        if reply.data is None and reply.text:             # not JSON: another program on the port, a proxy
            raise Stop(self.server_failure(reply))
        return reply

    def ok_json(self, method: str, path: str, body: Any = None) -> Any:
        reply = self.call(method, path, body)
        if not reply.ok:
            raise Stop(self.server_failure(reply))
        return reply.data

    def project(self, pid: str) -> str:
        if not isinstance(pid, str) or not PID_RE.fullmatch(pid):
            raise UsageError("%r is not a project id (lowercase letters, digits, - and _)" % pid)
        return pid

    def state(self, pid: str) -> dict:
        st = self.ok_json("GET", "/api/projects/%s/state" % quote(pid, safe=""))
        if not isinstance(st, dict) or "next_actions" not in st:
            raise Stop(self.fail(X.UNREACHABLE, "not_the_app", "The answer of GET .../state is not the app's state answer.",
                                 fix="Check that BTI_URL points at the app."))
        return st


def resolve_actor(opt: str | None, env: dict) -> str:
    name = opt if opt is not None else (env.get("BTI_ACTOR") if isinstance(env, dict) else None)
    if not name or not str(name).strip():
        return DEFAULT_ACTOR
    name = str(name).strip()
    if name == "human":
        raise UsageError("the command speaks for an agent: the actor `human` is the owner on the page")
    actor = name if name.startswith(("cli:", "agent:")) else "cli:" + name
    if not ACTOR_RE.match(actor):
        raise UsageError("the actor %r is not agent:<model id> or cli:<name> (letters, digits, . _ -)" % name)
    return actor


# ------------------------------------------------------------------------------------------------------------------------ helpers
def find_action(st: dict, aid: str) -> dict | None:
    return next((a for a in st.get("next_actions") or [] if a.get("id") == aid), None)


def known_action_ids() -> set[str] | None:
    """Every action id the app has (None when this machine cannot load the app's code): tells a typo from an action that is not listed now."""
    try:
        from bti.editor.state_api import SPEC
    except Exception:       # noqa: BLE001
        return None
    return set(SPEC)


def need_words(needs: list[str]) -> list[str]:
    try:
        from bti.editor.state_api import NEEDS
    except Exception:       # noqa: BLE001
        return []
    return ["%s: %s %s" % (n, NEEDS[n][0], NEEDS[n][1]) for n in needs if n in NEEDS]


def parse_value(text: str) -> Any:
    """The value of `--set key=value`: JSON when it is JSON (true, 3, null, "x", [1,2]), else the text itself."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def read_json_file(spec: str, what: str) -> Any:
    try:
        raw = sys.stdin.read() if spec == "-" else Path(spec).read_text(encoding="utf-8")
    except OSError as e:
        raise UsageError("cannot read %s %s: %s" % (what, spec, e.strerror or e))
    try:
        return json.loads(raw)
    except ValueError as e:
        raise UsageError("%s %s is not valid JSON: %s" % (what, spec, e))


def build_body(act: dict, body_file: str | None, sets: list[str], actor: str) -> Any:
    """The body of a call: the example body of the action (or, when the caller supplies the content, its template) with `--body FILE` in place of it,
    then the `--set` pairs over it; the fields the caller must give are checked; the actor is put where the API takes one."""
    explicit = False
    if body_file is not None:
        body, explicit = read_json_file(body_file, "the body file"), True
    elif act.get("body") is not None:
        body = copy.deepcopy(act["body"])
    elif act.get("body_template") is not None:
        body = copy.deepcopy(act["body_template"])
    else:
        body = None
    pairs = []
    for s in sets or []:
        key, eq, val = s.partition("=")
        if not eq or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise UsageError("--set takes key=value (the key is a field name), not %r" % s)
        pairs.append((key, parse_value(val)))
    if act.get("method") == "GET":
        if body_file is not None or pairs:
            raise UsageError("%s is a GET: it takes no body" % act["id"])
        return None
    if pairs:
        if body is None:
            body = {}
        if not isinstance(body, dict):
            raise UsageError("--set needs a body that is a JSON object")
        for k, v in pairs:
            body[k] = v
    if isinstance(body, dict) and not explicit:
        missing = [f for f in act.get("fill") or [] if body.get(f) is None]
        if missing:
            raise UsageError("%s needs content: give %s (for example %s)" % (act["id"], ", ".join(missing), " ".join("--set %s=..." % m for m in missing)))
        body = {k: v for k, v in body.items() if v is not None}
    if isinstance(body, dict) and (act.get("gate") or act["id"] == "picks.suggest" or "actor" in body):
        body["actor"] = actor
    return body


# ----------------------------------------------------------------------------------------------------------------------- readiness
def refuse_not_ready(ctx: Ctx, act: dict) -> int:
    needs = list(act.get("needs") or [])
    if act.get("gate") and not act.get("auto_ok"):
        return ctx.fail(X.PERSON, "gate_needs_human",
                        "The gate %s is for the owner: an agent may not approve it now (automatic running is off for this project, or the owner did not allow "
                        "this gate); it is also not ready (needs: %s)." % (act["id"].split(".")[0], ", ".join(needs) or "nothing"),
                        fix="Ask the owner to approve this gate on the page, or to turn automatic running on for this project and allow the gate.", needs=needs)
    code = X.BUSY if set(needs) <= {"no_running_job"} else X.REFUSED
    return ctx.fail(code, "not_ready", "The action %s is not ready: it needs %s." % (act["id"], ", ".join(needs)),
                    fix=" ".join(need_words(needs)) or "Meet what `needs` says (see `bti status`), then call again.",
                    retry="later" if code == X.BUSY else "after_fix", needs=needs)


def refuse_spend(ctx: Ctx, act: dict) -> int | None:
    """A cost the owner did not allow an agent to spend (`paid` never) is for the owner, ready or not, `--yes-cost` or not: exit 3."""
    cost = act.get("cost")
    if not cost or act.get("auto_ok"):
        return None
    return ctx.fail(X.PERSON, "spend_not_allowed", "%s costs %s (%s) and the owner did not allow an agent to spend that." % (act["id"], cost.get("kind"), cost.get("about")),
                    fix="Ask the owner to run this on the page" + (", or to allow this kind of spending for the project." if cost.get("kind") != "paid" else ": an agent never spends money."),
                    cost=cost)


def refuse_unconfirmed(ctx: Ctx, act: dict, yes_cost: bool) -> int | None:
    """A cost the owner allowed runs only when the caller confirms it with `--yes-cost`: exit 3 with one line saying what it costs."""
    cost = act.get("cost")
    if not cost or yes_cost:
        return None
    return ctx.fail(X.PERSON, "cost_not_confirmed", "%s costs %s (%s)." % (act["id"], cost.get("kind"), cost.get("about")),
                    fix="Run it again with --yes-cost when the owner asked for this work.", cost=cost)


# -------------------------------------------------------------------------------------------------------------------------- the job
def job_paths(jid: str, follow: str | None) -> list[str]:
    q = quote(jid, safe="")
    paths = []
    if follow and follow.startswith("GET "):
        paths.append(follow[4:].replace("{job_id}", q))
    return paths + [p for p in ("/api/longjobs/%s" % q, "/api/jobs/%s" % q) if p not in paths]


def fetch_job(ctx: Ctx, jid: str, follow: str | None = None) -> tuple[dict, str]:
    """(the job record, the path it was read at); a job the app does not know is a refusal (404 `job_not_found`)."""
    last: Reply | None = None
    for path in job_paths(jid, follow):
        reply = ctx.call("GET", path)
        if reply.ok and isinstance(reply.data, dict):
            return reply.data, path
        last = reply
        if reply.status != 404:
            break
    raise Stop(ctx.server_failure(last))


def follow_job(ctx: Ctx, jid: str, follow: str | None, interval: float, max_wait: float) -> int:
    """Poll the job and print one line per change until it ends; the exit code says how it ended."""
    started, last = ctx.clock(), None
    try:
        while True:
            job, path = fetch_job(ctx, jid, follow)
            follow = "GET " + path
            line = R.job_line({"id": jid, **job})
            if line != last:
                ctx.progress(line)
                last = line
            if job.get("state") in FINAL_STATES:
                return finish_job(ctx, jid, job)
            if max_wait and ctx.clock() - started >= max_wait:
                return ctx.fail(X.BUSY, "still_running", "The job %s is still running after %d seconds." % (jid, max_wait),
                                fix="Follow it again with: bti job %s --wait" % jid, retry="later", job=job)
            ctx.sleep(interval)
    except KeyboardInterrupt:
        return ctx.fail(X.BUSY, "interrupted", "Stopped watching: the job %s keeps running on the server." % jid,
                        fix="Follow it again with: bti job %s --wait" % jid, retry="later")


def finish_job(ctx: Ctx, jid: str, job: dict) -> int:
    code = X.exit_for_job(job)
    if code == X.DONE:
        return ctx.success(job, R.job_end_lines(job))
    err_code = str(job.get("error_code") or job.get("error_kind") or job.get("state"))
    return ctx.fail(code, err_code, R.detail_text(job.get("error")) or "The job ended as %s." % job.get("state"),
                    fix=_job_fix(job), retry="later" if code == X.BUSY else None, job=job)


def _job_fix(job: dict) -> str:
    code = job.get("error_code")
    try:
        from bti.editor.hints import hint
        if code:
            return hint(code)["fix"]
    except Exception:       # noqa: BLE001
        pass
    return {"cancelled": "Start the action again: finished parts are kept.", "interrupted": "Start the action again: finished parts are kept."}.get(job.get("state"), "Read `detail`, fix what it says, then start the action again.")


# --------------------------------------------------------------------------------------------------------------------- the commands
def cmd_status(ctx: Ctx, a) -> int:
    if not a.project:
        rows = ctx.ok_json("GET", "/api/projects")
        return ctx.success(rows, R.projects_text(rows if isinstance(rows, list) else []))
    pid = ctx.project(a.project)
    st = ctx.state(pid)
    return ctx.success(st, R.status_text(st))


def send_action(ctx: Ctx, pid: str, act: dict, make_body: Callable[[], Any], *, wait: bool, yes_cost: bool, interval: float, max_wait: float,
                render: Callable[[Any], list[str]] | None = None) -> int:
    """The one way an action is called: a spend the owner did not allow is refused first, then it must be ready, then its body is made (a
    mistyped body is exit 2), then a cost must be confirmed, then it is sent exactly as the state answer says (method and path)."""
    refusal = refuse_spend(ctx, act)
    if refusal is not None:
        return refusal
    if not act.get("ready"):
        return refuse_not_ready(ctx, act)
    body = make_body()
    refusal = refuse_unconfirmed(ctx, act, yes_cost)
    if refusal is not None:
        return refusal
    reply = ctx.call(act["method"], act["path"], body)
    if not reply.ok:
        return ctx.server_failure(reply)
    data = reply.data
    jid = data.get("job_id") if isinstance(data, dict) else None
    if wait and isinstance(jid, str) and jid:
        ctx.progress("started job %s (%s)" % (jid, act["id"]))
        return follow_job(ctx, jid, act.get("follow"), interval, max_wait)
    if render is not None:
        return ctx.success(data, render(data))
    lines = ["ok: %s" % act["id"]]
    if isinstance(jid, str) and jid:
        lines.append("started job %s; follow it with: bti job %s --wait" % (jid, jid))
    elif act.get("gate"):
        lines.append("approved by %s" % ctx.actor)
    else:
        lines.append(R.compact(data, 500))
    if act["id"] == "storyboard.validate" and isinstance(data, dict):
        issues = [i for i in data.get("issues") or [] if isinstance(i, dict)]
        errs = [i for i in issues if i.get("level") == "error"]
        lines = ["ok: %s: %d error(s), %d warning(s)" % (act["id"], len(errs), len(issues) - len(errs))] + \
                ["  error %s: %s" % (i.get("path"), i.get("message")) for i in errs[:10]]
    return ctx.success(data, lines)


def unlisted(ctx: Ctx, pid: str, st: dict, aid: str) -> int:
    known = known_action_ids()
    listed = [a["id"] for a in st.get("next_actions") or []]
    if known is not None and aid in known:           # a real action whose step is locked or whose work is done: the project refuses, the command was typed right
        return ctx.fail(X.REFUSED, "action_not_listed", "The state of %s does not list %s now: its step is locked or it has nothing to do." % (pid, aid),
                        fix="Run `bti status %s`: it lists what can be called now and what each step waits for." % pid, retry="after_fix", listed=listed)
    return ctx.fail(X.USAGE, "unknown_action", "The state of %s does not list an action %r." % (pid, aid),
                    fix="Use an id from `bti status %s` (the first column of `can do now`)." % pid, listed=listed)


def cmd_do(ctx: Ctx, a) -> int:
    pid = ctx.project(a.project)
    st = ctx.state(pid)
    act = find_action(st, a.action)
    if act is None:
        return unlisted(ctx, pid, st, a.action)
    return send_action(ctx, pid, act, lambda: build_body(act, a.body, a.set, ctx.actor), wait=a.wait, yes_cost=a.yes_cost, interval=a.interval,
                       max_wait=a.max_wait)


def cmd_approve(ctx: Ctx, a) -> int:
    pid = ctx.project(a.project)
    st = ctx.state(pid)
    gate = a.gate
    act = find_action(st, gate + ".approve")
    if act is None:
        rec = (st.get("approvals") or {}).get(gate)
        if rec and rec.get("stands"):
            return ctx.success({"ok": True, "already": True, "gate": gate, "approval": rec},
                               ["%s is already approved by %s (it still stands)" % (gate, rec.get("by") or "(not recorded)")])
        return ctx.fail(X.REFUSED, "gate_not_available", "The gate %s cannot be approved now: its step is locked or there is nothing to approve." % gate,
                        fix="Run `bti status %s`: the gates that can be approved are listed with their needs." % pid, retry="after_fix")
    return send_action(ctx, pid, act, lambda: build_body(act, None, [], ctx.actor), wait=False, yes_cost=False, interval=0, max_wait=0,
                       render=lambda d: ["approved %s as %s" % (gate, ctx.actor)])


def load_ops_file(spec: str) -> dict:
    raw = read_json_file(spec, "the operations file")
    if isinstance(raw, list):
        raw = {"ops": raw}
    if not isinstance(raw, dict) or not isinstance(raw.get("ops"), list):
        raise UsageError("the operations file must be a JSON list of operations, or an object with an `ops` list")
    extra = [k for k in raw if k not in ("ops", "scope", "note", "base_rev", "actor", "dry_run")]
    if extra:
        raise UsageError("the operations file has fields the batch does not take: %s" % ", ".join(extra))
    return raw


def cmd_ops(ctx: Ctx, a) -> int:
    pid = ctx.project(a.project)
    spec = load_ops_file(a.file)
    st = ctx.state(pid)
    act = find_action(st, a.doc + ".ops")
    if act is None:
        return unlisted(ctx, pid, st, a.doc + ".ops")
    tmpl = act.get("body_template") or act.get("body") or {}
    body: dict[str, Any] = {"base_rev": tmpl.get("base_rev"), "actor": ctx.actor, "ops": spec["ops"], "dry_run": bool(a.dry_run or spec.get("dry_run"))}
    note = a.note if a.note is not None else spec.get("note")
    if note:
        body["note"] = note
    if spec.get("scope"):
        body["scope"] = spec["scope"]
    dry = body["dry_run"]
    return send_action(ctx, pid, act, lambda: body, wait=False, yes_cost=False, interval=0, max_wait=0, render=lambda d: R.ops_text(d, dry))


def cmd_job(ctx: Ctx, a) -> int:
    jid = a.id
    if not ID_RE.fullmatch(jid):
        raise UsageError("%r is not a job id" % jid)
    if a.cancel:
        job, path = fetch_job(ctx, jid)
        if job.get("state") in FINAL_STATES:
            return ctx.success(job, ["job %s has already ended: %s" % (jid, job.get("state"))])
        reply = ctx.call("POST", path + "/cancel")
        if not reply.ok:
            return ctx.server_failure(reply)
        data = reply.data if isinstance(reply.data, dict) else job
        if a.wait:
            return follow_job(ctx, jid, "GET " + path, a.interval, a.max_wait)
        return ctx.success(data, ["cancel asked for job %s: %s" % (jid, data.get("state"))])
    if a.wait:
        return follow_job(ctx, jid, None, a.interval, a.max_wait)
    job, _ = fetch_job(ctx, jid)
    return ctx.success(job, [R.job_line({"id": jid, **job})] + (R.job_end_lines(job) if job.get("state") in FINAL_STATES else []))


def cmd_changes(ctx: Ctx, a) -> int:
    pid = ctx.project(a.project)
    q = "?limit=%d" % a.limit + ("&doc=" + a.doc if a.doc else "")
    data = ctx.ok_json("GET", "/api/projects/%s/changes%s" % (quote(pid, safe=""), q))
    return ctx.success(data, R.log_text(data.get("changes") if isinstance(data, dict) else []))


def cmd_undo(ctx: Ctx, a) -> int:
    pid = ctx.project(a.project)
    if not re.fullmatch(r"batch_\d{1,8}", a.batch):
        raise UsageError("%r is not a batch id (like batch_0007: `bti changes %s` lists them)" % (a.batch, pid))
    log = ctx.ok_json("GET", "/api/projects/%s/changes?limit=200" % quote(pid, safe=""))
    rec = next((c for c in (log.get("changes") if isinstance(log, dict) else None) or [] if isinstance(c, dict) and c.get("batch") == a.batch), None)
    if rec is None:
        return ctx.fail(X.REFUSED, "batch_not_found", "There is no batch %s in the change log of %s." % (a.batch, pid),
                        fix="Take a batch id from `bti changes %s`." % pid, retry="no")
    st = ctx.state(pid)
    act = find_action(st, rec.get("doc", "") + ".ops")
    if act is None:
        return unlisted(ctx, pid, st, str(rec.get("doc")) + ".ops")
    tmpl = act.get("body_template") or act.get("body") or {}
    undo = {"method": "POST", "path": "/api/projects/%s/changes/%s/undo" % (quote(pid, safe=""), a.batch), "ready": True, "id": "changes.undo", "needs": []}
    body = {"base_rev": tmpl.get("base_rev"), "actor": ctx.actor, "note": a.note or ""}
    return send_action(ctx, pid, undo, lambda: body, wait=False, yes_cost=False, interval=0, max_wait=0,
                       render=lambda d: ["undone %s; the undo is batch %s; revision %s" % (a.batch, d.get("batch"), d.get("rev"))] + R.changes_lines(d.get("changes")))


def cmd_schema(ctx: Ctx, a) -> int:
    data = ctx.ok_json("GET", "/api/ops/schema")
    part = data.get(a.doc) if isinstance(data, dict) else None
    if not isinstance(part, dict):
        return ctx.fail(X.REFUSED, "schema_not_found", "The app has no operations for %r." % a.doc, retry="no")
    return ctx.success(part, R.schema_text(a.doc, part))


def doc_path(step: str | None) -> Path:
    return REPO / "AGENTS.md" if not step else REPO / "skills" / DOC_ALIAS.get(step, step) / "SKILL.md"


def cmd_doc(ctx: Ctx, a) -> int:
    path = doc_path(a.step)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ctx.fail(X.REFUSED, "doc_missing", "The document %s is missing from this checkout." % path.relative_to(REPO).as_posix(), retry="no")
    return ctx.success({"step": DOC_ALIAS.get(a.step, a.step) or "agents", "path": path.relative_to(REPO).as_posix(), "text": text}, text.rstrip("\n").split("\n"))


HANDLERS: dict[str, Callable[[Ctx, Any], int]] = {"status": cmd_status, "do": cmd_do, "approve": cmd_approve, "ops": cmd_ops, "job": cmd_job,
                                                   "undo": cmd_undo, "changes": cmd_changes, "schema": cmd_schema, "doc": cmd_doc}


# ----------------------------------------------------------------------------------------------------------------------- the parser
class Parser(argparse.ArgumentParser):
    def error(self, message: str):      # a mistyped command is exit 2, handled by `main`, not argparse's own exit
        raise UsageError(message)


def _common(p: argparse.ArgumentParser, top: bool) -> None:
    d = (lambda v: v) if top else (lambda v: argparse.SUPPRESS)
    p.add_argument("--json", action="store_true", default=d(False), help=COMMON_OPTIONS[0][1])
    p.add_argument("--actor", default=d(None), metavar="NAME", help=COMMON_OPTIONS[1][1])
    p.add_argument("--url", default=d(None), metavar="URL", help=COMMON_OPTIONS[2][1])
    p.add_argument("--timeout", type=float, default=d(None), metavar="SECONDS", help=COMMON_OPTIONS[3][1])


def _wait_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("--interval", type=float, default=2.0, metavar="SECONDS", help="seconds between two looks at a followed job (default 2)")
    p.add_argument("--max-wait", dest="max_wait", type=float, default=0.0, metavar="SECONDS", help="stop watching after this long (exit 5; the job keeps running); default: no limit")


def build_parser() -> argparse.ArgumentParser:
    epilog = "exit codes: " + "; ".join("%d %s" % (n, name) for n, name, _, _ in X.EXIT_CODES)
    p = Parser(prog="bti", description="Run a project of Behind the Image step by step through the app's API.", epilog=epilog)
    _common(p, True)
    sub = p.add_subparsers(dest="command", metavar="command", parser_class=Parser)
    usage = {n: (u, s) for n, u, s in COMMANDS}

    def add(name: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=usage[name][1], description=usage[name][1], usage=usage[name][0])
        _common(sp, False)
        return sp
    sp = add("status")
    sp.add_argument("project", nargs="?")
    sp = add("do")
    sp.add_argument("project")
    sp.add_argument("action", metavar="action id")
    sp.add_argument("--body", metavar="FILE", help="the whole body as JSON from a file (- is the standard input)")
    sp.add_argument("--set", action="append", default=[], metavar="key=value", help="one field of the body (the value is JSON when it is JSON, else text); repeatable")
    sp.add_argument("--wait", action="store_true", help="follow the long job the action starts to its end, one line per change")
    sp.add_argument("--yes-cost", dest="yes_cost", action="store_true", help="confirm a cost (machine time or a model call) the owner allowed an agent to spend")
    _wait_options(sp)
    sp = add("approve")
    sp.add_argument("project")
    sp.add_argument("gate", choices=GATES)
    sp = add("ops")
    sp.add_argument("project")
    sp.add_argument("doc", choices=OPS_DOCS)
    sp.add_argument("--file", required=True, metavar="FILE", help="the operations: a JSON list, or an object with `ops` (- is the standard input)")
    sp.add_argument("--dry-run", dest="dry_run", action="store_true", help="check everything and describe the changes, write nothing")
    sp.add_argument("--note", default=None, help="free text kept in the change log")
    sp = add("job")
    sp.add_argument("id")
    sp.add_argument("--wait", action="store_true", help="follow the job to its end, one line per change")
    sp.add_argument("--cancel", action="store_true", help="ask the app to stop the job")
    _wait_options(sp)
    sp = add("undo")
    sp.add_argument("project")
    sp.add_argument("batch")
    sp.add_argument("--note", default=None, help="free text kept in the change log")
    sp = add("changes")
    sp.add_argument("project")
    sp.add_argument("doc", nargs="?", choices=OPS_DOCS)
    sp.add_argument("--limit", type=int, default=20, help="how many batches (1 to 200, default 20)")
    sp = add("schema")
    sp.add_argument("what", choices=("ops",))
    sp.add_argument("doc", choices=OPS_DOCS)
    sp = add("doc")
    sp.add_argument("step", nargs="?", choices=DOC_STEPS + tuple(DOC_ALIAS))
    return p


def main(argv: list[str] | None = None, *, transport: Transport | None = None, stdout=None, stderr=None, env: dict | None = None,
         sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic) -> int:
    """Run one command; the return value is the exit code. `transport`, the streams, `env` and the clocks are replaceable for the tests."""
    argv = list(sys.argv[1:] if argv is None else argv)
    out, err = stdout or sys.stdout, stderr or sys.stderr
    if stdout is None and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    env = dict(os.environ) if env is None else env
    wants_json = "--json" in argv
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command is None:
            raise UsageError("a command is needed: " + ", ".join(n for n, _, _ in COMMANDS))
        args._env = env
        if args.timeout is not None and args.timeout <= 0:
            raise UsageError("--timeout must be a positive number of seconds")
        if getattr(args, "limit", 1) is not None and not 1 <= getattr(args, "limit", 1) <= 200:
            raise UsageError("--limit must be from 1 to 200")
        if transport is None:
            try:
                transport = HttpTransport(args.url or env.get("BTI_URL") or DEFAULT_URL)
            except ValueError as e:
                raise UsageError(str(e))
        ctx = Ctx(args, transport, out, err, sleep, clock)
        return HANDLERS[args.command](ctx, args)
    except Stop as s:
        return s.code
    except UsageError as e:
        if wants_json:
            out.write(json.dumps({"ok": False, "exit": X.USAGE, "exit_name": "usage", "code": "usage", "detail": str(e),
                                  "fix": "Run `bti --help` for the commands and `bti <command> --help` for its options."}, ensure_ascii=False) + "\n")
        else:
            err.write("usage: %s\n  (bti --help lists the commands; bti <command> --help its options)\n" % e)
        return X.USAGE
