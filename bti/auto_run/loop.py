"""The loop of the automatic run: read the state answer, take the first action that is ready, advances and is allowed, follow its job, read the state again.

The rule, in five lines (the state answer decides what "advancing" means; nothing here knows the steps of the pipeline):

    1. Read `GET /api/projects/{pid}/state`. Stop when the project is exported (or the `until` step is done), when automatic running was turned off,
       or when a job that is not ours runs on the project (never two things at once).
    2. Take the FIRST action of `next_actions` with `ready` and `advances` (the state sorts them: the repair of a damaged project first, then what moves the
       project forward, in the order of the steps). It never picks another one, never edits a document, never sends operations.
    3. Allowed? A gate only when its `auto_ok` is true (the owner switched automatic running on and allowed the gate); a cost only when its kind is allowed in the
       owner's `spend`; a paid action never; `storyboard.restore` never (restoring a damaged file is the owner's decision). Otherwise stop and say which.
    4. Before a gate: read its document and apply the quality bar (bti/auto_run/checks.py): an error, or a warning that is not tolerated, stops the run before
       anything is sent. Then call the action exactly as the answer describes it (its method, path and body), as the actor `agent:auto`.
    5. If the call answers a job, follow it to its end (a failed job stops the run with the job's code and sentence), then go back to 1.
       Every step is written to the run log; the run ends with one result (bti/auto_run/reasons.py).

The loop is resumable in slices: `advance(deadline)` returns the result when the run has ended, or None when the deadline came first (the long-job runner
limits one part to 35 minutes; the job gives the loop one part per slice, see `job.py`). A Run holds what it needs between two calls.
"""
from __future__ import annotations

import copy
import json
import logging
import time
from typing import Any, Callable

from bti import auto as _rule
from bti.cli.transport import Reply, Transport, Unreachable

from . import checks, reasons, runlog

log = logging.getLogger("bti.auto_run")

ACTOR = _rule.RUN_ACTOR                    # the actor of every call the run makes (the form `agent:<name>` of bti/auto.py)
DEFAULT_MAX_STEPS = 40
MAX_STEPS_LIMIT = 200
POLL_SECONDS = 2.0
STALE_RETRIES = 3                          # a gate approved with a revision that went stale (somebody edited): read the state again, up to this many times in a row
NO_PROGRESS = 3                            # the same call this many times in a row without the state moving on: stop
ACTIVE = ("queued", "waiting", "running")
FINAL = ("done", "error", "cancelled", "interrupted")
NEVER_AUTO = frozenset({"storyboard.restore"})      # advancing actions an automatic run does not take: a restore picks an old copy over a damaged file
STALE_CODES = ("stale", "stale_revision")
BUSY_CODES = ("busy", "voice_busy", "model_job_busy", "script_job_running", "longjob_running", "agy_busy", "edit_running", "project_busy", "agent_job_running")


def _lines_of(doc: dict) -> int | None:
    """How many narration lines a document of the picks gate covers (`narration.beat_ids` of GET .../picks); None for another document or when it is not said."""
    ids = (doc.get("narration") or {}).get("beat_ids") if isinstance(doc.get("narration"), dict) else None
    return len(ids) if isinstance(ids, list) else None


def _outside_of(doc: dict) -> int | None:
    """How many lines of the narration are about something outside the painting (`outside.lines` of GET .../picks, the lines whose `kinds` hold `outside` or
    `compare`); None for another document or when it is not said (then the share of `outside_no_picture` cannot be judged and the warning stops the run)."""
    out = doc.get("outside")
    n = out.get("lines") if isinstance(out, dict) else None
    return n if isinstance(n, int) and not isinstance(n, bool) else None


class _Stop(Exception):
    def __init__(self, result: dict):
        super().__init__(result.get("reason"))
        self.result = result


class Run:
    def __init__(self, transport: Transport, pid: str, *, run_id: str, log_: runlog.RunLog, until: str | None = None, max_steps: int = DEFAULT_MAX_STEPS,
                 poll: float = POLL_SECONDS, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic, actor: str = ACTOR,
                 timeout: float = 120.0):
        self.t, self.pid, self.run_id, self.log = transport, pid, run_id, log_
        self.until, self.max_steps, self.poll, self._sleep_fn, self.clock, self.actor, self.timeout = until, max_steps, poll, sleep, clock, actor, timeout
        self.cancelled: Callable[[], bool] = lambda: False
        self.report: Callable[[float, str], None] = lambda fraction, note: None
        self.meta: dict = {}
        self.steps = 0
        self.child: dict | None = None
        self.result: dict | None = None
        self.stale = 0
        self.recent: list[str] = []
        self.tolerated: dict[tuple[str, str], dict] = {}          # (gate, code) -> {gate, code, count, lines?}: the warnings the run let through (the last look at each gate)
        self.done_steps = 0
        self.of = len(reasons.STEPS)
        self.t0 = clock()
        self.started = runlog.now_iso()

    # ----------------------------------------------------------------------------------------------------------------------- wiring
    def bind(self, ctx: Any) -> None:
        """Take the progress, the cancel flag and the public `meta` of the long-job part that runs the loop now."""
        self.cancelled = ctx.cancelled
        self.report = ctx.progress
        self.meta = ctx.meta

    def sleep(self, seconds: float) -> None:
        """A sleep that notices a cancel within a fifth of a second."""
        end = self.clock() + seconds
        while not self.cancelled():
            left = end - self.clock()
            if left <= 0:
                return
            self._sleep_fn(min(0.2, left))

    # ------------------------------------------------------------------------------------------------------------------------- http
    def call(self, method: str, path: str, body: Any = None) -> Reply:
        last: Unreachable | None = None
        for attempt in range(3):
            try:
                return self.t.request(method, path, body, self.timeout)
            except Unreachable as e:
                last = e
                if attempt < 2:
                    self.sleep(1.0)
                if self.cancelled():
                    break
        raise _Stop(reasons.make("unreachable", pid=self.pid, error_detail=str(last or "")[:200], error_vi=str(last or "")[:200]))

    @staticmethod
    def _error(reply: Reply) -> dict:
        body = reply.data if isinstance(reply.data, dict) else {}
        out = {"status": reply.status, "code": body.get("code") or ("http_%d" % reply.status), "detail": body.get("detail") if isinstance(body.get("detail"), str) else
               json.dumps(body.get("detail"), ensure_ascii=False)[:300] if body.get("detail") is not None else (reply.text or "")[:200]}
        for k in ("fix", "retry", "retry_after_seconds"):
            if body.get(k) is not None:
                out[k] = body[k]
        if isinstance(body.get("fields"), list):
            out["fields"] = body["fields"][:6]
        return out

    # ---------------------------------------------------------------------------------------------------------------------- the loop
    def advance(self, deadline: float) -> dict | None:
        """Work until the run ends (the result is returned) or `deadline` (the loop's clock) passes (None). Never raises."""
        try:
            while self.result is None:
                if self.cancelled():
                    return self._cancel()
                if self.clock() >= deadline:
                    return None
                if self.child is not None:
                    self._poll_child()
                    continue
                st = self._state()
                self._note(st)
                stop, action = self._decide(st)
                if stop is not None:
                    self._finish(stop)
                else:
                    self._take(action, st)
        except _Stop as s:
            self._finish(s.result)
        except Exception as e:      # noqa: BLE001 - a bug must end the run with a reason and a log, never leave it hanging
            log.exception("automatic run %s: unexpected error", self.run_id)
            self._finish(reasons.make("internal_error", pid=self.pid, error_detail="%s: %s" % (type(e).__name__, str(e)[:200]),
                                      error_vi="%s: %s." % (type(e).__name__, str(e)[:160])))
        return self.result

    def stop_time(self, hours: float) -> dict | None:
        """The run used up its time: end it (a child job is left running: it is the project's, the owner sees it)."""
        if self.result is None:
            self._finish(reasons.make("time_limit", pid=self.pid, hours=("%g" % hours), step=self._current_step()))
        return self.result

    # ------------------------------------------------------------------------------------------------------------------------ state
    def _state(self) -> dict:
        rep = self.call("GET", "/api/projects/%s/state" % self.pid)
        if not rep.ok or not isinstance(rep.data, dict) or "next_actions" not in rep.data:
            raise _Stop(reasons.make("action_failed", pid=self.pid, action="state", action_label="Đọc trạng thái dự án", error=self._error(rep)))
        return rep.data

    def _current_step(self) -> str | None:
        return self.meta.get("step")

    def _note(self, st: dict, action: dict | None = None, text: str = "") -> None:
        steps = [s for s in st.get("steps") or [] if isinstance(s, dict)]
        self.of = len(steps) or self.of
        self.done_steps = sum(1 for s in steps if s.get("state") == "done")
        step = (action or {}).get("step") or st.get("current")
        pos = next((i for i, s in enumerate(steps) if s.get("step") == step), None)
        label = next((s.get("label") for s in steps if s.get("step") == step), None) or reasons.label_of_step(step)
        self.meta.update(step=step, step_label=label, n=(pos + 1) if pos is not None else None, of=self.of, steps_taken=self.steps,
                         action=(action or {}).get("id"), action_label=(action or {}).get("label"), note=text)
        self.report(min(0.99, self.done_steps / max(1, self.of)), ("%s (%s/%s)" % (label, pos + 1, self.of) if pos is not None and label else text or ""))

    # --------------------------------------------------------------------------------------------------------------------- decision
    def _decide(self, st: dict) -> tuple[dict | None, dict | None]:
        """(a result that ends the run, None) or (None, the action to take)."""
        steps = {s.get("step"): s for s in st.get("steps") or [] if isinstance(s, dict)}
        acts = [a for a in st.get("next_actions") or [] if isinstance(a, dict) and isinstance(a.get("id"), str)]
        auto = st.get("auto") if isinstance(st.get("auto"), dict) else {}
        target = self.until or "export"
        if (steps.get(target) or {}).get("state") == "done":
            return reasons.make("until_reached" if self.until and self.until != "export" else "exported", pid=self.pid, step=target), None
        if auto.get("enabled") is not True:
            return reasons.make("auto_turned_off", pid=self.pid, step=st.get("current")), None
        busy = [j for j in st.get("jobs") or [] if isinstance(j, dict) and j.get("kind") not in ("auto", "preview") and j.get("state") in ACTIVE]
        if busy:
            kinds = sorted({str(j.get("kind")) for j in busy})
            return reasons.make("busy_elsewhere", pid=self.pid, step=st.get("current"),
                                jobs_vi=", ".join(reasons.JOB_KIND_VI.get(k, k) for k in kinds), jobs_en=", ".join(kinds)), None
        todo = [a for a in acts if a.get("ready") is True and a.get("advances") is True and not a["id"].startswith("auto.") and not a["id"].endswith(".cancel")]
        if not todo:
            return self._nothing_to_do(st, acts), None
        a = todo[0]
        # A human may approve directly, but the automatic run must never bypass
        # a required viewer review merely because its agent is unavailable.
        pending_review = next((x for x in acts if x["id"] == "storyboard.review" and x.get("ready") is False), None)
        if a["id"] == "storyboard.approve" and pending_review is not None:
            return self._nothing_to_do(st, [pending_review]), None
        refusal = self._allowed(a, auto)
        if refusal is not None:
            return refusal, None
        return None, a

    def _allowed(self, a: dict, auto: dict) -> dict | None:
        aid, kind = a["id"], (a.get("cost") or {}).get("kind")
        base = {"pid": self.pid, "action": aid, "action_label": a.get("label"), "step": a.get("step")}
        if aid in NEVER_AUTO:
            return reasons.make("repair_needed", **base)
        if kind == "paid":
            return reasons.make("paid_needs_owner", kind=kind, **base)
        if a.get("gate"):
            gate = aid.split(".")[0]
            gates = auto.get("gates") if isinstance(auto.get("gates"), dict) else {}
            if a.get("auto_ok") is not True or gates.get(gate) is not True:
                return reasons.make("gate_not_allowed", gate=gate, **base)
            return None
        spend = auto.get("spend") if isinstance(auto.get("spend"), dict) else {}
        if a.get("auto_ok") is not True or (kind and spend.get(kind) is not True):
            return reasons.make("spend_not_allowed", kind=kind or "model", **base)
        if a.get("body") is None and a.get("fill"):
            return reasons.make("needs_content", **base)
        return None

    def _nothing_to_do(self, st: dict, acts: list[dict]) -> dict:
        """No action moves the project forward: say what it waits for (the needs of the first action that is not ready, on the step it is at)."""
        skip = ("changes.", "auto.")
        waiting = [a for a in acts if a.get("ready") is False and not a["id"].startswith(skip) and (a.get("cost") or {}).get("kind") != "paid"
                   and a["id"] != "storyboard.validate" and [n for n in a.get("needs") or [] if n != "no_running_job"]]
        cur = st.get("current")
        pick = next((a for a in waiting if a.get("step") == cur), waiting[0] if waiting else None)
        if pick is not None:
            needs = [n for n in pick.get("needs") or [] if n != "no_running_job"]
            vi = reasons.NEED_VI.get(needs[0], needs[0])
            ag = pick.get("agent") if isinstance(pick.get("agent"), dict) else {}
            if needs[0] == "agent_usable" and ag.get("reason"):
                vi += ": " + str(ag["reason"]).rstrip(".")
            return reasons.make("nothing_to_do", pid=self.pid, step=pick.get("step") or cur, action=pick["id"], action_label=pick.get("label"),
                                waiting_for=needs, waiting_vi=vi)
        probs = [p for p in st.get("problems") or [] if isinstance(p, dict)]
        steps = [s for s in st.get("steps") or [] if isinstance(s, dict)]
        here = next((s for s in steps if s.get("step") == cur), steps[0] if steps else {})
        vi = ("một lỗi của dự án (%s)" % probs[0].get("code")) if probs else str(here.get("detail") or "").strip().rstrip(".") or "một việc chưa rõ"
        return reasons.make("nothing_to_do", pid=self.pid, step=cur, waiting_vi=vi, waiting_en=(probs[0].get("detail") if probs else str(here.get("detail") or "something unknown")))

    # ------------------------------------------------------------------------------------------------------------------------- acting
    def _take(self, a: dict, st: dict) -> None:
        if self.steps >= self.max_steps:
            self._finish(reasons.make("step_limit", pid=self.pid, count=self.steps, step=a.get("step")))
            return
        body = copy.deepcopy(a.get("body"))
        if a.get("gate") or (isinstance(body, dict) and "actor" in body):
            body = body if isinstance(body, dict) else {}
            body["actor"] = self.actor
        base = {"pid": self.pid, "action": a["id"], "action_label": a.get("label"), "step": a.get("step")}
        warnings: list[dict] = []
        if a.get("gate"):
            warnings = self._quality_bar(a, base)
        sig = a["id"] + str(a.get("path")) + json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
        if len(self.recent) >= NO_PROGRESS - 1 and all(s == sig for s in self.recent[-(NO_PROGRESS - 1):]):
            self._finish(reasons.make("no_progress", count=NO_PROGRESS - 1, **base))
            return
        self.steps += 1
        self._note(st, a, text=str(a.get("label") or a["id"]))
        counts = checks.tally(warnings)
        rec = self.log.begin_step(self.steps, a.get("step"), a, body, note=("tolerated warnings: " + ", ".join("%s x%d" % (c, n) for c, n in counts.items())) if counts else "")
        if counts:
            self.log.update_step(rec, tolerated=[{"code": c, "count": n} for c, n in counts.items()])
        t0 = self.clock()
        rep = self.call(a["method"], a["path"], body)
        secs = round(self.clock() - t0, 2)
        if not rep.ok:
            err = self._error(rep)
            self.log.update_step(rec, status=rep.status, ok=False, code=err["code"], seconds=secs, note=(rec.get("note") or "") + (" " if rec.get("note") else "") + str(err.get("detail") or "")[:160])
            self._refused(a, base, rep, err)
            return
        self.recent.append(sig)
        del self.recent[:-NO_PROGRESS]
        jid = rep.data.get("job_id") if isinstance(rep.data, dict) else None
        if isinstance(jid, str) and jid:
            follow = str(a.get("follow") or "")
            path = follow[4:] if follow.startswith("GET ") else "/api/longjobs/{job_id}"
            self.child = {"id": jid, "path": path.replace("{job_id}", jid), "action": a, "rec": rec, "t0": t0}
            self.log.update_step(rec, status=rep.status, ok=True, job_id=jid, job_state="running")
            self.meta.update(child_job=jid, child_progress=0.0)
            return
        self.stale = 0
        self.log.update_step(rec, status=rep.status, ok=True, seconds=secs)

    def _quality_bar(self, a: dict, base: dict) -> list[dict]:
        """Read the document behind the gate and judge its checks; ends the run (raises _Stop) when it should not be approved. Returns the tolerated warnings."""
        gate = a["id"].split(".")[0]
        rep = self.call("GET", checks.document_path(a["path"], gate))
        if not rep.ok or not isinstance(rep.data, dict):
            raise _Stop(reasons.make("action_failed", **{**base, "action": "%s (reading its document)" % a["id"]}, error=self._error(rep)))
        lines, outside = _lines_of(rep.data), _outside_of(rep.data)
        verdict, stoppers, tolerated = checks.vet(gate, rep.data.get("issues"), lines, outside)
        if verdict == "error":
            raise _Stop(reasons.make("quality_error", gate=gate, count=len(stoppers), issues=stoppers, **base))
        if verdict == "warning":
            raise _Stop(reasons.make("quality_warning", gate=gate, count=len(stoppers), issues=stoppers, **base))
        for code, n in checks.tally(tolerated).items():
            base = checks.share_base(code, lines, outside)
            self.tolerated[(gate, code)] = {"gate": gate, "code": code, "count": n, **({"lines": base} if code in checks.SHARE_LIMITS.get(gate, {}) and base else {})}
        return tolerated

    def _refused(self, a: dict, base: dict, rep: Reply, err: dict) -> None:
        code = err["code"]
        body = rep.data if isinstance(rep.data, dict) else {}
        if code in STALE_CODES and self.stale < STALE_RETRIES:
            self.stale += 1                                   # somebody edited the document between the state and the call: read it again
            return
        if code == "gate_needs_human":
            self._finish(reasons.make("auto_turned_off" if body.get("reason") == "auto_off" else "gate_not_allowed", gate=a["id"].split(".")[0], **base))
        elif code == "auto_needs_human":
            self._finish(reasons.make("auto_turned_off", **base))
        elif code == "spend_needs_human":
            self._finish(reasons.make("paid_needs_owner", kind="paid", **base))
        elif a.get("gate") and code in reasons.REFUSAL_CODES:
            self._finish(reasons.make("gate_refused", gate=a["id"].split(".")[0], error=err, **base))
        elif code in BUSY_CODES or err.get("retry") == "later" and rep.status == 409:
            self._finish(reasons.make("busy_elsewhere", jobs_vi="một việc khác", jobs_en="another job", **base))
        else:
            self._finish(reasons.make("action_failed", error=err, **base))

    # ---------------------------------------------------------------------------------------------------------------------- the job
    def _poll_child(self) -> None:
        c = self.child
        a, rec = c["action"], c["rec"]
        base = {"pid": self.pid, "action": a["id"], "action_label": a.get("label"), "step": a.get("step")}
        rep = self.call("GET", c["path"])
        if not rep.ok or not isinstance(rep.data, dict):
            self.log.update_step(rec, ok=False, job_state="unknown", code=self._error(rep)["code"], seconds=round(self.clock() - c["t0"], 2))
            self.child = None
            self._finish(reasons.make("job_failed", error=self._error(rep), **base))
            return
        job = rep.data
        state = job.get("state")
        prog = job.get("progress")
        prog = float(prog) if isinstance(prog, (int, float)) else 0.0
        label = self.meta.get("step_label") or ""
        n = self.meta.get("n")
        self.meta.update(child_job=c["id"], child_progress=prog, note=str(job.get("message") or ""))
        self.report(min(0.99, (self.done_steps + prog) / max(1, self.of)), "%s (%s/%s)" % (label, n, self.of) if n else label)
        if state in ACTIVE:
            self.sleep(self.poll)
            return
        secs = round(self.clock() - c["t0"], 2)
        self.child = None
        self.log.update_step(rec, job_state=state, seconds=secs)
        if state == "done":
            self.stale = 0
            self.meta.update(child_job=None, child_progress=None)
            return
        if state in ("cancelled", "interrupted"):
            self._finish(reasons.make("job_cancelled_elsewhere", **base))
            return
        err = {"code": str(job.get("error_code") or job.get("error_kind") or state or "job_failed"), "detail": str(job.get("error") or job.get("message") or "")[:300]}
        self._finish(reasons.make("job_failed", error=err, error_vi=(err["detail"] if reasons._is_vietnamese(err["detail"]) else ""), **base))

    def _cancel(self) -> dict:
        c, self.child = self.child, None
        if c is not None:                                         # stop what this run started: the owner pressed "Dừng"
            try:
                self.t.request("POST", c["path"].split("?")[0] + "/cancel", None, 20.0)
            except Exception:       # noqa: BLE001 - best effort: the job stays visible on the project
                log.warning("automatic run %s: could not cancel job %s", self.run_id, c["id"], exc_info=True)
            self.log.update_step(c["rec"], job_state="cancelled", note="the run was cancelled: its job was asked to stop")
        return self._finish(reasons.make("cancelled", pid=self.pid, step=self._current_step()))

    def _finish(self, result: dict) -> dict:
        if self.result is not None:
            return self.result
        result = reasons.add_tolerated(dict(result), list(self.tolerated.values()))
        result.setdefault("link", ("#/project/%s/%s" % (self.pid, result["step"])) if result.get("step") else None)
        result.update(steps_taken=self.steps, run_id=self.run_id, started=self.started, ended=runlog.now_iso(), seconds=round(self.clock() - self.t0, 1))
        self.result = result
        self.meta["result"] = result
        self.meta.update(child_job=None)
        self.log.finish(result)
        return result
