"""Background jobs for the model calls: progress per chapter, cancel, a hard timeout.

A job runs in its own daemon thread. A watchdog enforces the hard timeout: when it fires the job is marked as failed
and told to stop; whatever the worker does afterwards is ignored (it checks `job.stopped` before it writes anything).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from .env import redact
from .store import make_parent

HARD_TIMEOUT = 1800.0
KEEP = 100


class JobError(Exception):
    """Raised by a job body. `kind` is one of: timeout, rate_limit, auth, config, validation, parse, http, empty, blocked, conflict."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


class BusyError(Exception):
    """Another model job is already running for the project (`job` is that job)."""

    def __init__(self, job: "Job"):
        super().__init__("another model job is running for this project")
        self.job = job


JOB_ID_RE = re.compile(r"[0-9a-f]{16}")
RESTART_MESSAGE = "the server was restarted while this job was running; its result was not written. Start it again."


def write_record(path: Path, rec: dict) -> None:
    """Atomic write of one job record (best effort: a full disk must not break the job itself)."""
    try:
        make_parent(path, 2)        # <project>/cache/jobs: never re-creates a project folder that was deleted
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        os.replace(tmp, path)
    except (OSError, ValueError, TypeError):      # ProjectGone is an OSError too
        pass


def read_record(path: Path) -> dict | None:
    """A persisted job record; a job that was queued or running when it was written is reported as failed: the process that ran
    it is gone (the file is updated, so the answer stays the same afterwards)."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict):
        return None
    if rec.get("state") in ("queued", "running"):
        rec.update(state="error", error=RESTART_MESSAGE, error_kind="interrupted", finished=time.time())
        for c in rec.get("chapters") or []:
            if isinstance(c, dict) and c.get("state") in ("pending", "running", "retrying"):
                c["state"] = "failed" if c["state"] != "pending" else "skipped"
        write_record(path, rec)
    return rec


def job_file(projects_root: Path, pid: str, jid: str) -> Path:
    return Path(projects_root) / pid / "cache" / "jobs" / f"{jid}.json"


def find_record(projects_root: Path, jid: str) -> dict | None:
    """Look a job id up among the persisted records of every project (None when unknown or the id is malformed)."""
    if not (isinstance(jid, str) and JOB_ID_RE.fullmatch(jid)) or not Path(projects_root).is_dir():
        return None
    for d in sorted(Path(projects_root).iterdir()):
        f = d / "cache" / "jobs" / f"{jid}.json"
        if f.is_file() and not d.is_symlink():
            return read_record(f)
    return None


class Job:
    def __init__(self, kind: str, pid: str, model: str):
        self.id = uuid.uuid4().hex[:16]
        self.kind, self.pid, self.model = kind, pid, model
        self.state = "queued"       # queued | running | done | error | cancelled
        self.chapters: list[dict] = []
        self.message = ""
        self.error: str | None = None
        self.error_kind: str | None = None
        self.alternatives: list[str] = []
        self.result: dict = {}
        self.created = time.time()
        self.finished: float | None = None
        self.cancel = threading.Event()
        self._lock = threading.Lock()
        self.on_change: Callable[["Job"], None] | None = None     # persistence hook, set by ScriptJobs

    @property
    def stopped(self) -> bool:
        return self.cancel.is_set() or self.state in ("done", "error", "cancelled")

    @property
    def progress(self) -> float:
        if self.state == "done":
            return 1.0
        if not self.chapters:
            return 0.0
        done = sum(1 for c in self.chapters if c["state"] == "done")
        return round(done / len(self.chapters), 3)

    def set_chapter(self, cid: str, **kw) -> None:
        with self._lock:
            for c in self.chapters:
                if c["id"] == cid:
                    c.update(kw)
        if "state" in kw:
            self.changed()

    def finish(self, state: str, error: str | None = None, kind: str | None = None) -> None:
        with self._lock:
            if self.state in ("done", "error", "cancelled"):
                return
            self.state, self.error, self.error_kind, self.finished = state, error, kind, time.time()
            for c in self.chapters:
                if c["state"] in ("pending", "running", "retrying"):
                    # no live spinner on a dead job: the chapter in flight failed, the ones not reached were skipped
                    c["state"] = "cancelled" if state == "cancelled" else ("skipped" if c["state"] == "pending" else "failed")
        self.changed()

    def changed(self) -> None:
        if self.on_change is not None:
            self.on_change(self)

    def public(self) -> dict:
        return {"id": self.id, "kind": self.kind, "pid": self.pid, "model": self.model, "state": self.state,
                "progress": self.progress, "chapters": [dict(c) for c in self.chapters], "message": self.message,
                "error": self.error, "error_kind": self.error_kind, "alternatives": self.alternatives,
                "result": self.result, "created": self.created, "finished": self.finished}


class ScriptJobs:
    def __init__(self, hard_timeout: float = HARD_TIMEOUT, projects_root: Path | None = None):
        """With `projects_root`, every change of a job is written to projects/<pid>/cache/jobs/<id>.json, so that after a
        restart the job is still known (and reported as failed with the reason when it was in flight)."""
        self.hard_timeout = hard_timeout
        self.projects_root = Path(projects_root) if projects_root else None
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, jid: str) -> Job | None:
        return self._jobs.get(jid)

    def persisted(self, jid: str) -> dict | None:
        return find_record(self.projects_root, jid) if self.projects_root else None

    def _persist(self, job: Job) -> None:
        if self.projects_root is not None and (self.projects_root / job.pid).is_dir():
            write_record(job_file(self.projects_root, job.pid, job.id), job.public())

    def for_project(self, pid: str) -> list[dict]:
        js = sorted((j for j in self._jobs.values() if j.pid == pid), key=lambda j: j.created, reverse=True)
        return [j.public() for j in js[:10]]

    def running(self, pid: str, kind: str | None = None) -> Job | None:
        return next((j for j in self._jobs.values()
                     if j.pid == pid and j.state in ("queued", "running") and (kind is None or j.kind == kind)), None)

    def cancel(self, jid: str) -> bool:
        j = self._jobs.get(jid)
        if j is None:
            return False
        j.cancel.set()
        if j.state == "queued":
            j.finish("cancelled")
        return True

    def start(self, kind: str, pid: str, model: str, body: Callable[[Job], None], *,
              timeout: float | None = None, alternatives: Callable[[], list[str]] | None = None,
              exclusive: bool = False) -> Job:
        """`exclusive`: refuse (BusyError) when a job of the project is queued or running; the check and the registration
        happen under one lock, so two simultaneous requests cannot both start."""
        job = Job(kind, pid, model)
        job.on_change = self._persist
        with self._lock:
            if exclusive:
                busy = self.running(pid)
                if busy:
                    raise BusyError(busy)
            self._jobs[job.id] = job
            if len(self._jobs) > KEEP:
                for k in sorted(self._jobs, key=lambda k: self._jobs[k].created)[: len(self._jobs) - KEEP]:
                    if self._jobs[k].state in ("done", "error", "cancelled"):
                        self._jobs.pop(k, None)
        limit = timeout or self.hard_timeout
        job.changed()

        def offer() -> None:
            if alternatives:
                try:
                    job.alternatives = [m for m in alternatives() if m != model]
                except Exception:       # noqa: BLE001
                    job.alternatives = []

        def watchdog() -> None:
            if job.cancel.wait(limit):
                return
            if job.state in ("queued", "running"):
                job.cancel.set()
                offer()
                job.finish("error", f"the job passed its hard limit of {int(limit)} seconds and was stopped", "timeout")

        def run() -> None:
            if job.state != "queued":
                return
            job.state = "running"
            job.changed()
            try:
                body(job)
                if job.cancel.is_set():
                    job.finish("cancelled")
                else:
                    job.finish("done")
            except JobError as e:
                if job.cancel.is_set() and e.kind != "timeout" and job.state == "running":
                    job.finish("cancelled")
                else:
                    if e.kind in ("timeout", "rate_limit"):
                        offer()
                    job.finish("error", redact(e.message), e.kind)
            except BaseException as e:      # noqa: BLE001
                job.finish("error", redact(f"{type(e).__name__}: {e}")[:400], "internal")

        threading.Thread(target=run, daemon=True, name=f"script-job-{job.id}").start()
        threading.Thread(target=watchdog, daemon=True, name=f"script-watch-{job.id}").start()
        return job
