"""A small stand-in for `bti.longjob` (CORE writes the real one; the interface is design section 4). It runs the parts one
after the other in the calling thread, with the same `ctx` the real runner gives a part."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Part:
    key: str
    title: str
    run: Callable
    heavy: bool = False
    est_seconds: int = 0
    is_done: Callable | None = None


class Busy(Exception):
    pass


class Ctx:
    def __init__(self, job, part, cancel_after=None):
        self.job, self.part, self._cancel_after = job, part, cancel_after
        self.workdir = None

    def progress(self, fraction, note=""):
        self.part["progress"] = fraction
        if note:
            self.part["note"] = note

    def log(self, text):
        self.job["log"].append(text)

    def cancelled(self):
        return self.job.get("cancel_requested", False)

    def run_process(self, cmd, cwd=None, env=None, on_line=None):
        import os
        e = {**os.environ, **(env or {})}
        p = subprocess.Popen(cmd, cwd=cwd, env=e, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in p.stdout:
            if on_line:
                on_line(line.rstrip("\n"))
        return p.wait()


class FakeManager:
    """`start` runs everything at once. `cancel_after_part=k` requests a cancel once part k (1-based) has finished."""

    def __init__(self, cancel_after_part=None):
        self.jobs: dict[str, dict] = {}
        self.running: set[tuple] = set()
        self.cancel_after_part = cancel_after_part
        self.starts = []

    def start(self, kind, pid, project_dir, parts, meta=None):
        if (pid, kind) in self.running:
            raise Busy()
        job = {"id": "j%d" % (len(self.jobs) + 1), "kind": kind, "pid": pid, "state": "running", "progress": 0.0, "error": None, "error_code": None,
               "result": None, "log": [], "parts": [], "meta": meta or {}, "created": time.time()}
        self.jobs[job["id"]] = job
        self.starts.append(job["id"])
        self.running.add((pid, kind))
        try:
            for i, p in enumerate(parts, 1):
                rec = {"key": p.key, "title": p.title, "state": "running", "progress": 0.0, "note": "", "error": None}
                job["parts"].append(rec)
                try:
                    if p.is_done and p.is_done(Ctx(job, rec)):
                        rec["state"] = "done"
                        rec["skipped"] = True
                        continue
                    res = p.run(Ctx(job, rec))
                    rec["state"] = "done"
                    if isinstance(res, dict) and res:
                        job["result"] = {**(job["result"] or {}), **res}
                except Exception as e:   # noqa: BLE001
                    rec["state"] = "error"
                    rec["error"] = str(e)
                    job["state"] = "error"
                    job["error"] = str(e)
                    job["error_code"] = getattr(e, "code", None)
                    job["exc"] = e
                    break
                if self.cancel_after_part == i:
                    job["cancel_requested"] = True
            else:
                job["state"] = "cancelled" if job.get("cancel_requested") else "done"
        finally:
            self.running.discard((pid, kind))
        return job

    def get(self, job_id):
        return self.jobs.get(job_id)

    def active(self, pid, kind=None):
        return None
