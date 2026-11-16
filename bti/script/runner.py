"""Background jobs for the model calls: progress per chapter, cancel, a hard timeout.

A job runs in its own daemon thread. A watchdog enforces the hard timeout: when it fires the job is marked as failed
and told to stop; whatever the worker does afterwards is ignored (it checks `job.stopped` before it writes anything).
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Callable

from .env import redact

HARD_TIMEOUT = 1800.0
KEEP = 100


class JobError(Exception):
    """Raised by a job body. `kind` is one of: timeout, rate_limit, auth, config, validation, parse, http, empty, blocked, conflict."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind, self.message = kind, message


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

    def finish(self, state: str, error: str | None = None, kind: str | None = None) -> None:
        with self._lock:
            if self.state in ("done", "error", "cancelled"):
                return
            self.state, self.error, self.error_kind, self.finished = state, error, kind, time.time()
            if state == "cancelled":
                for c in self.chapters:
                    if c["state"] in ("pending", "running", "retrying"):
                        c["state"] = "cancelled"

    def public(self) -> dict:
        return {"id": self.id, "kind": self.kind, "pid": self.pid, "model": self.model, "state": self.state,
                "progress": self.progress, "chapters": [dict(c) for c in self.chapters], "message": self.message,
                "error": self.error, "error_kind": self.error_kind, "alternatives": self.alternatives,
                "result": self.result, "created": self.created, "finished": self.finished}


class ScriptJobs:
    def __init__(self, hard_timeout: float = HARD_TIMEOUT):
        self.hard_timeout = hard_timeout
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def get(self, jid: str) -> Job | None:
        return self._jobs.get(jid)

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
              timeout: float | None = None, alternatives: Callable[[], list[str]] | None = None) -> Job:
        job = Job(kind, pid, model)
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > KEEP:
                for k in sorted(self._jobs, key=lambda k: self._jobs[k].created)[: len(self._jobs) - KEEP]:
                    if self._jobs[k].state in ("done", "error", "cancelled"):
                        self._jobs.pop(k, None)
        limit = timeout or self.hard_timeout

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
