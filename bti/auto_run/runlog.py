"""The run log: one file per automatic run in the project folder, `projects/<pid>/auto_runs/<run id>.json`, rewritten atomically after every step.

    {"schema": "bti.autorun/1", "id": "20261119-142301-a1b2", "pid": ..., "job_id": ..., "started": iso, "ended": iso | null,
     "until": step | null, "max_steps": 40, "actor": "human", "agent": "agent:auto",
     "steps": [{"n": 1, "at": iso, "step": "script", "action": "outline.generate", "method": "POST", "path": ..., "body": {...} | null,
                "status": 200, "ok": true, "code": null, "job_id": "..." | null, "job_state": "done" | null, "note": "...", "seconds": 61.2}],
     "outcome": null | ..., "reason": ..., "sentence": ..., "result": {...the run's result...}}

A run that is still going has `ended` null. A run whose process died (a restart) keeps `ended` null for ever: `list_runs` reports it from the state of its job.
Writing never makes a deleted project folder again (the run goes on and ends with the project gone). The newest KEEP runs are kept.
"""
from __future__ import annotations

import itertools
import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from bti.script import store as sstore

SCHEMA = "bti.autorun/1"
DIR = "auto_runs"
KEEP = 30
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{4}$")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _iso(ts: Any) -> str | None:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(float(ts)))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


_COUNTER = itertools.count(secrets.randbelow(0x4000))
_COUNTER_LOCK = threading.Lock()


def new_run_id() -> str:
    """`<date>-<time>-<4 hex>`: the ids sort in the order the runs started, also inside one second (the 4 hex are a counter of this process)."""
    with _COUNTER_LOCK:
        n = next(_COUNTER) & 0xFFFF
    return "%s-%04x" % (time.strftime("%Y%m%d-%H%M%S"), n)


def runs_dir(project_dir: Path | str) -> Path:
    return Path(project_dir) / DIR


class RunLog:
    """The record of one run, held in memory and written after every change."""

    def __init__(self, project_dir: Path | str, run_id: str, *, pid: str, until: str | None, max_steps: int, actor: str, job_id: str | None = None):
        self.dir = Path(project_dir)
        self.path = runs_dir(self.dir) / (run_id + ".json")
        self.lock = threading.RLock()
        self.rec: dict[str, Any] = {"schema": SCHEMA, "id": run_id, "pid": pid, "job_id": job_id, "started": now_iso(), "ended": None, "until": until,
                                    "max_steps": max_steps, "actor": actor, "agent": "agent:auto", "steps": [], "outcome": None, "reason": None,
                                    "sentence": None, "result": None}
        self.write_error: str | None = None

    # -- writing
    def _write(self) -> None:
        try:
            sstore.write_json_atomic(self.path, self.rec, levels=1)           # makes auto_runs/, never the project folder
        except OSError as e:                                                   # a deleted project, a full disk: the run goes on without its log
            self.write_error = str(e)[:200]

    def start(self) -> None:
        with self.lock:
            self._write()
            self.prune()

    def set_job(self, job_id: str) -> None:
        with self.lock:
            self.rec["job_id"] = job_id
            self._write()

    def begin_step(self, n: int, step: str | None, action: dict, body: Any, note: str = "") -> dict:
        """A step starts: its record is in the log (with `ok` null) before the call is made."""
        with self.lock:
            s = {"n": n, "at": now_iso(), "step": step, "action": action.get("id"), "method": action.get("method"), "path": action.get("path"),
                 "body": _small(body), "status": None, "ok": None, "code": None, "job_id": None, "job_state": None, "note": note, "seconds": None}
            self.rec["steps"].append(s)
            self._write()
            return s

    def update_step(self, s: dict, **kw: Any) -> None:
        with self.lock:
            s.update(kw)
            self._write()

    def finish(self, result: dict) -> None:
        with self.lock:
            self.rec.update(ended=now_iso(), outcome=result.get("outcome"), reason=result.get("reason"), sentence=result.get("sentence"), result=result)
            self._write()

    def prune(self) -> None:
        try:
            files = sorted(runs_dir(self.dir).glob("*.json"), reverse=True)           # the id starts with the time: newest first
        except OSError:
            return
        for f in files[KEEP:]:
            try:
                f.unlink()
            except OSError:
                pass


def _small(body: Any) -> Any:
    """A body for the log: what was sent, without anything long."""
    try:
        text = json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return body if len(text) <= 600 else {"_cut": text[:200] + " ..."}


# --------------------------------------------------------------------------------------------------------------------------- reading
def read_run(project_dir: Path | str, run_id: str) -> dict | None:
    if not RUN_ID_RE.match(run_id or ""):
        return None
    try:
        rec = json.loads((runs_dir(project_dir) / (run_id + ".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) and rec.get("id") == run_id else None


def _ended_by_job(rec: dict, job: dict | None) -> dict:
    """What an unfinished record says about itself, from the state of its job: a run whose job is gone or has ended without writing its end (a restart,
    a cancel that came between two parts) is reported as such, never as `running` for ever."""
    from . import reasons
    state = (job or {}).get("state")
    if state == "cancelled":
        res = reasons.make("cancelled", pid=rec.get("pid") or "")
    elif state in ("error",):
        res = reasons.make("internal_error", pid=rec.get("pid") or "", error_detail=str((job or {}).get("error") or ""), error_vi=str((job or {}).get("error") or ""))
    else:
        res = reasons.make("job_cancelled_elsewhere", pid=rec.get("pid") or "", action_label="chạy tự động")
        res["reason"], res["detail"] = "interrupted", "The server stopped while the run was going; finished work is kept."
        res["sentence"] = "Máy chủ đã dừng khi đang chạy tự động. Bấm \"Chạy tự động\" để làm tiếp; phần đã xong được giữ lại."
    return res


def summary(rec: dict, job: dict | None = None) -> dict:
    """One line of GET .../auto/runs: the record without its steps, plus `state` (running | finished) and, while it runs, what it is doing now."""
    out = {k: rec.get(k) for k in ("id", "job_id", "started", "ended", "until", "max_steps", "actor", "outcome", "reason", "sentence")}
    steps = rec.get("steps") if isinstance(rec.get("steps"), list) else []
    out["steps_taken"] = len(steps)
    res = rec.get("result") if isinstance(rec.get("result"), dict) else None
    active = job is not None and job.get("state") in ("queued", "waiting", "running")
    if rec.get("ended") is None and not active:
        res = _ended_by_job(rec, job)
        fin = (job or {}).get("finished")
        out.update(outcome=res["outcome"], reason=res["reason"], sentence=res["sentence"], ended=_iso(fin) if fin else None)
    out["state"] = "running" if (rec.get("ended") is None and active) else "finished"
    if res is not None:
        out.update({k: res.get(k) for k in ("step", "step_label", "link", "action", "action_label", "gate", "kind", "detail", "fix") if k in res})
        out["result"] = res
    if out["state"] == "running" and isinstance(job, dict):
        meta = job.get("meta") if isinstance(job.get("meta"), dict) else {}
        out["live"] = {k: meta.get(k) for k in ("step", "step_label", "n", "of", "action", "action_label", "child_job", "child_progress", "note") if k in meta}
        out["live"]["progress"] = job.get("progress")
    return out


def list_runs(project_dir: Path | str, manager: Any = None, limit: int = 10) -> list[dict]:
    """The newest runs of the project, newest first (`summary` of each). `manager` is the long-job manager: it says whether a run that has not ended is still going."""
    out: list[dict] = []
    try:
        files = sorted(runs_dir(project_dir).glob("*.json"), reverse=True)
    except OSError:
        return out
    for f in files:
        if len(out) >= max(1, limit):
            break
        rec = read_run(project_dir, f.stem)
        if rec is None:
            continue
        job = None
        if rec.get("ended") is None and manager is not None and isinstance(rec.get("job_id"), str):
            try:
                job = manager.get(rec["job_id"])
            except Exception:       # noqa: BLE001 - a job that cannot be looked up counts as gone
                job = None
        out.append(summary(rec, job))
    return out
