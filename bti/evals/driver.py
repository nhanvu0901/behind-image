"""The drivers of the bench: for each step, the calls an agent makes through the app's API to ask the model for the work, and the OUTPUTS the criteria read.

A driver gets a `Session` (the transport to the app, the id of the project COPY the run works on, the case) and returns the outputs: documents read back through
GET routes (`outline`, `issues`, `brief`, `narration`, `storyboard`, `timing`, `picks`, `before`, `after`, `answer`, ...; bti/evals/criteria.py says which kind needs
which). It starts the model only through the route a person's button calls, never by another way, and it never edits a document itself.

The `request` of a case, per step:

    step              request keys
    ----------------  -------------------------------------------------------------------------------------------------------------------------------------
    outline           options: body of PUT .../brief/options (target_words, exclude, include_low, notes, wps); body: body of POST .../outline/generate (notes)
    narration         body: body of POST .../narration/generate (chapters, notes, force)
    draft             body: body of POST .../draft/start (chapters, provider); apply: true (default) puts the proposal on the project as its storyboard
    edit_storyboard   instruction (text); scope ({"shots": [ids]} | {"chapter": id} | {"all": true}); mode (auto | fast | deep)  -> POST .../draft/edit
    edit_picks        action (the id in the state answer; default picks.edit); instruction; scope ({"beats": [ids]}); body (more fields)
    picks_agent       action (default picks.auto); body (fields of the action)

`edit_picks` and `picks_agent` call an action of the STATE ANSWER by its id (`GET .../state`: the route, the method and the example body come from the answer, as for any
agent): `picks.edit` (the step-4 prompt box) and `picks.auto` (the pictures agent). When the app does not list the action, or lists it but not ready (a project without an approved
narration or a main painting: `needs` says which), the repeat is SKIPPED, with that sentence, and never counted as a failure.

The answers the criteria read, as the joined app gives them. Both prompt boxes answer through typed operations: the model says `applied`, `cannot` or `escalate`, and the turn ends as
`applied`, `no_change` (the model said `cannot`: nothing was written, its reason is the turn's `summary`), `escalate` (it needs a picture the project does not have) or `failed`.
Step 5 (`POST .../draft/edit`): the turn is read from `GET .../draft/thread` (`status`, `summary`, `error`); step 4 (`picks.edit`): the job's `result` (`status`, `summary`).
`answer.code` is that status, `answer.reason` the sentence; `edit.answered_cannot` accepts `cannot`, `no_change` and `escalate`. The pictures agent's job (`picks.auto`) ends `done`
with the sentence of its result (`Agent đã chọn hình cho 6/6 đoạn.`); the driver reads the picks back.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Callable
from urllib.parse import quote

from bti.cli.transport import Reply, Transport, Unreachable

FINAL = ("done", "error", "cancelled", "interrupted")
ACTIVE = ("queued", "waiting", "running")
EDIT_MODES = ("auto", "fast", "deep")
DEFAULT_ACTION = {"edit_picks": "picks.edit", "picks_agent": "picks.auto"}


class Skipped(Exception):
    """The case cannot be run on this app or this sample: not a failure of the agent."""


class DriverError(Exception):
    """A call the driver needed was refused or a job did not end: the repeat is recorded with this sentence, and its criteria fail with 'nothing to check'."""

    def __init__(self, what: str, detail: str = "", code: str | None = None):
        super().__init__(("%s: %s" % (what, detail)) if detail else what)
        self.what, self.detail, self.code = what, detail, code


# ------------------------------------------------------------------------------------------------------------------------------- the session
class Session:
    def __init__(self, transport: Transport, pid: str, case, *, poll: float = 2.0, job_timeout: float = 3 * 3600.0, timeout: float = 180.0,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.t, self.pid, self.case = transport, pid, case
        self.poll, self.job_timeout, self.timeout, self.sleep, self.clock = poll, job_timeout, timeout, sleep, clock
        self.calls: list[tuple[str, str, int]] = []
        self.jobs: list[dict] = []

    @property
    def P(self) -> str:
        return "/api/projects/%s" % quote(self.pid, safe="")

    def call(self, method: str, path: str, body: Any = None) -> Reply:
        try:
            r = self.t.request(method, path, body, self.timeout)
        except Unreachable as e:
            raise DriverError("the app cannot be reached", str(e))
        self.calls.append((method, path, r.status))
        return r

    def ok(self, method: str, path: str, body: Any = None, what: str | None = None) -> Any:
        r = self.call(method, path, body)
        if not r.ok:
            d = r.data if isinstance(r.data, dict) else {}
            raise DriverError(what or "%s %s" % (method, path), "HTTP %d %s: %s" % (r.status, d.get("code") or "", str(d.get("detail") or r.text or "")[:200]), d.get("code"))
        return r.data

    def wait_job(self, jid: str, follow: str | None = None) -> dict:
        """The record of the job once it has ended (a long job or a script job: the follow path says which)."""
        paths = ([follow[4:].replace("{job_id}", quote(jid, safe=""))] if follow and follow.startswith("GET ") else []) + \
                ["/api/longjobs/%s" % quote(jid, safe=""), "/api/jobs/%s" % quote(jid, safe="")]
        t0, found = self.clock(), None
        while True:
            for p in paths:
                r = self.call("GET", p)
                if r.ok and isinstance(r.data, dict):
                    found = p
                    break
                if r.status != 404:
                    raise DriverError("the job %s cannot be read" % jid, "HTTP %d" % r.status)
            else:
                raise DriverError("the job %s is not known to the app" % jid)
            paths = [found]
            job = r.data
            if job.get("state") in FINAL:
                self.jobs.append(summary_of(job, self.clock() - t0))
                return job
            if self.clock() - t0 > self.job_timeout:
                self.call("POST", found + "/cancel")
                raise DriverError("the job %s did not end in %d minutes (it was asked to stop)" % (jid, self.job_timeout // 60))
            self.sleep(self.poll)


def summary_of(job: dict, seconds: float | None = None) -> dict:
    return {"id": job.get("id"), "kind": job.get("kind"), "state": job.get("state"), "error_code": job.get("error_code") or job.get("error_kind"),
            "error": job.get("error"), "seconds": round(seconds, 1) if seconds is not None else None}


def _job_failed(job: dict) -> str | None:
    if job.get("state") == "done":
        return None
    return "the job ended as %s%s" % (job.get("state"), (": %s %s" % (job.get("error_code") or job.get("error_kind") or "", job.get("error") or "")).rstrip() if job.get("error") or job.get("error_code") else "")


# ---------------------------------------------------------------------------------------------------------------------------------- checks
def check_request(step: str, req: dict) -> list[str]:
    """The problems of the `request` of a case of `step` (an empty list when it is fine)."""
    keys = {"outline": {"options", "body"}, "narration": {"body"}, "draft": {"body", "apply"}, "edit_storyboard": {"instruction", "scope", "mode"},
            "edit_picks": {"action", "instruction", "scope", "body"}, "picks_agent": {"action", "body"}}
    out = ["request: %r is not a key of a %s request (it takes: %s)" % (k, step, ", ".join(sorted(keys[step]))) for k in req if k not in keys[step]]
    for k in ("options", "body", "scope"):
        if k in req and not isinstance(req[k], dict):
            out.append("request.%s must be an object" % k)
    if step in ("edit_storyboard", "edit_picks"):
        if not isinstance(req.get("instruction"), str) or not req["instruction"].strip():
            out.append("request.instruction must be the text of the request")
        sc = req.get("scope")
        if not isinstance(sc, dict) or not sc:
            out.append("request.scope must say what the request is about")
        elif step == "edit_storyboard" and len([k for k in ("shots", "chapter", "all") if k in sc]) != 1:
            out.append("request.scope must be exactly one of {shots: [...]}, {chapter: id}, {all: true}")
        elif step == "edit_picks" and not (isinstance(sc.get("beats"), list) and sc["beats"]):
            out.append("request.scope must be {beats: [ids]}")
    if step == "edit_storyboard" and req.get("mode", "auto") not in EDIT_MODES:
        out.append("request.mode must be one of %s" % ", ".join(EDIT_MODES))
    if "action" in req and not (isinstance(req["action"], str) and "." in req["action"]):
        out.append("request.action must be an action id like picks.auto")
    if "apply" in req and not isinstance(req["apply"], bool):
        out.append("request.apply must be true or false")
    return out


# ---------------------------------------------------------------------------------------------------------------------------------- drivers
def drive_outline(s: Session) -> dict:
    req = s.case.request
    if req.get("options"):
        s.ok("PUT", s.P + "/brief/options", req["options"], "the brief options were refused")
    r = s.ok("POST", s.P + "/outline/generate", req.get("body") or {}, "the outline could not be started")
    job = s.wait_job(r["job_id"], "GET /api/jobs/{job_id}")
    payload = s.ok("GET", s.P + "/outline")
    return {"outline": payload.get("outline"), "issues": payload.get("issues") or [], "brief": s.ok("GET", s.P + "/brief"), "approved": payload.get("approved"),
            "job": summary_of(job), "error": _job_failed(job)}


def drive_narration(s: Session) -> dict:
    r = s.ok("POST", s.P + "/narration/generate", s.case.request.get("body") or {}, "the narration could not be started")
    job = s.wait_job(r["job_id"], "GET /api/jobs/{job_id}")
    n = s.ok("GET", s.P + "/narration")
    o = s.ok("GET", s.P + "/outline")
    return {"narration": n.get("narration"), "outline": o.get("outline"), "brief": s.ok("GET", s.P + "/brief"), "issues": n.get("issues") or [], "stats": n.get("stats"),
            "job": summary_of(job), "error": _job_failed(job)}


def _project_view(s: Session) -> dict | None:
    r = s.call("GET", s.P)
    return r.data if r.ok and isinstance(r.data, dict) and r.data.get("storyboard") else None


def drive_draft(s: Session) -> dict:
    req = s.case.request
    before = _project_view(s)
    r = s.ok("POST", s.P + "/draft/start", {"provider": "agy", **(req.get("body") or {})}, "the draft could not be started")
    job = s.wait_job(r["job_id"], "GET /api/longjobs/{job_id}")
    out: dict = {"before": before["storyboard"] if before else None, "job": summary_of(job), "error": _job_failed(job)}
    if out["error"]:
        return out
    prop = ((s.ok("GET", s.P + "/draft").get("state") or {}).get("proposal"))
    if not prop:
        out["error"] = "the draft made no proposal"
        return out
    if req.get("apply", True):
        s.ok("POST", "%s/proposals/%s/apply" % (s.P, quote(prop, safe="")), {"accept": "all"}, "the proposal could not be applied")
    view = s.ok("GET", s.P)
    picks = s.ok("GET", s.P + "/picks")
    out.update(storyboard=view.get("storyboard"), timing=view.get("timing"), issues=view.get("issues") or [], picks=picks.get("picks"), proposal=prop)
    return out


def drive_edit_storyboard(s: Session) -> dict:
    req = s.case.request
    before = s.ok("GET", s.P)
    body = {"instruction": req["instruction"], "scope": req["scope"], "mode": req.get("mode", "auto"), "base_rev": before.get("rev")}
    r = s.ok("POST", s.P + "/draft/edit", body, "the edit could not be started")
    job = s.wait_job(r["job_id"], "GET /api/longjobs/{job_id}")
    thread = s.ok("GET", s.P + "/draft/thread")
    turns = thread if isinstance(thread, list) else (thread or {}).get("turns") or []
    turn = next((t for t in turns if t.get("id") == r.get("turn_id")), {})
    after = s.ok("GET", s.P)
    code = turn.get("status") or ("failed" if job.get("state") == "error" else job.get("state"))
    answer = {"code": code, "status": code, "state": job.get("state"), "reason": turn.get("summary") or turn.get("notes") or "", "error": turn.get("error") or job.get("error_code"),
              "summary": turn.get("summary") or ""}
    return {"before": before.get("storyboard"), "after": after.get("storyboard"), "storyboard": after.get("storyboard"), "timing": after.get("timing"), "issues": after.get("issues") or [],
            "scope": req["scope"], "answer": answer, "job": summary_of(job), "error": None if code in ("applied", "cannot", "escalate", "no_change", "done") else _job_failed(job) or "the edit ended as %s" % code}


def _listed_action(s: Session, step: str) -> dict:
    want = s.case.request.get("action") or DEFAULT_ACTION[step]
    st = s.ok("GET", s.P + "/state", None, "the state of the project cannot be read")
    act = next((a for a in st.get("next_actions") or [] if isinstance(a, dict) and a.get("id") == want), None)
    if act is None:
        raise Skipped("the app does not list the action %s for this project (the project is not at that step, or this app is older than the action)" % want)
    if not act.get("ready"):
        raise Skipped("the action %s is listed but not ready: it needs %s" % (want, ", ".join(act.get("needs") or ["?"])))
    return act


def _picks_view(s: Session) -> dict:
    p = s.ok("GET", s.P + "/picks")
    return {"picks": p.get("picks"), "issues": p.get("issues") or [], "beat_ids": (p.get("narration") or {}).get("beat_ids") or []}


def _call_action(s: Session, act: dict, extra: dict) -> dict | None:
    body = copy.deepcopy(act.get("body") if act.get("body") is not None else act.get("body_template") or {})
    body = {k: v for k, v in {**(body if isinstance(body, dict) else {}), **extra}.items() if v is not None}
    if isinstance(body, dict) and "actor" in (act.get("body_template") or act.get("body") or {}):
        body["actor"] = "agent:eval"
    r = s.ok(act["method"], act["path"], body or None, "the action %s was refused" % act["id"])
    jid = r.get("job_id") if isinstance(r, dict) else None
    return s.wait_job(jid, act.get("follow")) if isinstance(jid, str) and jid else None


def drive_edit_picks(s: Session) -> dict:
    req = s.case.request
    act = _listed_action(s, "edit_picks")
    before = _picks_view(s)
    extra = {"instruction": req["instruction"], "scope": req["scope"], **(req.get("body") or {})}
    if "base_rev" in (act.get("body_template") or {}):
        extra["base_rev"] = act["body_template"]["base_rev"]
    job = _call_action(s, act, extra)
    after = _picks_view(s)
    code = (job or {}).get("error_code") or ("done" if not job or job.get("state") == "done" else job.get("state"))
    answer = {"code": ((job or {}).get("result") or {}).get("status") or code, "state": (job or {}).get("state") or "done", "reason": ((job or {}).get("result") or {}).get("summary") or (job or {}).get("error") or ""}
    return {"before": before["picks"], "after": after["picks"], "picks": after["picks"], "issues": after["issues"], "beat_ids": after["beat_ids"], "scope": req["scope"], "answer": answer,
            "job": summary_of(job) if job else None, "error": _job_failed(job) if job else None}


def drive_picks_agent(s: Session) -> dict:
    act = _listed_action(s, "picks_agent")
    job = _call_action(s, act, s.case.request.get("body") or {})
    after = _picks_view(s)
    return {"picks": after["picks"], "issues": after["issues"], "beat_ids": after["beat_ids"], "job": summary_of(job) if job else None, "error": _job_failed(job) if job else None}


DRIVERS: dict[str, Callable[[Session], dict]] = {"outline": drive_outline, "narration": drive_narration, "draft": drive_draft, "edit_storyboard": drive_edit_storyboard,
                                                 "edit_picks": drive_edit_picks, "picks_agent": drive_picks_agent}

# the model work one run of a case asks for, to say before anything starts: (calls in words, the least number of agent runs)
COST = {"outline": ("1 agent call (the outline; one repeat of it when the first answer cannot be read)", 1),
        "narration": ("1 job of about one agent call per chapter (6 to 8), each repeated once when it fails the checks, and one call more for a chapter that comes out "
                      "more than 10% over its budget (at most 4 of those per job)", 8),
        "draft": ("1 agent session in a folder, about 20 minutes for the whole video (less with `chapters`)", 1),
        "edit_storyboard": ("1 agent call (fast) or 1 agent session (deep), 30 seconds to 20 minutes", 1),
        "edit_picks": ("1 agent call", 1),
        "picks_agent": ("1 agent session", 1)}
