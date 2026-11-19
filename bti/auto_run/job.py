"""The automatic run as a long job of the shared runner (kind `auto`): one per project, with progress, cancel and "start again continues".

The runner limits one part of a job to 35 minutes and the run lasts hours (the voice alone is about an hour), so the job is a row of equal parts, one per
slice of time (25 minutes each, 12 hours in all): part 1 starts the loop, and each part that follows takes it over where the last one stopped (the loop keeps
what it needs in memory; a part that finds the run ended skips at once). The last slice that cannot finish the run ends it with `time_limit`.

What the page reads is the job's `meta` (set once at the start with every key it will ever have, so that it can be read while it changes):
    step, step_label, n, of     where the run is ("Giọng đọc", 3 of 6)
    action, action_label        what it is doing; child_job, child_progress   the job it follows
    steps_taken, note, result   how many calls it made; a note of the job it follows; the result of the run once it ended (reasons.py)
A run that fails raises the runner's `PartError` with the code of the failed action and the Vietnamese sentence, so the job's `error_code` and `error` say it
too; every other end is a normal end of the job with `result` (a cancel is the runner's own: the job is `cancelled`, `meta.result` says why).
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Callable

from bti.cli.transport import Transport
from bti.longjob import Part, PartError

from . import loop, runlog

KIND = "auto"
SLICE_SECONDS = 25 * 60.0
MAX_HOURS = 12.0
META_KEYS = ("run_id", "until", "max_steps", "step", "step_label", "n", "of", "action", "action_label", "steps_taken", "child_job", "child_progress", "note", "result")


def _slice(run: loop.Run, index: int, last: bool, seconds: float, hours: float) -> Callable[[Any], dict | None]:
    def go(ctx) -> dict | None:
        if run.result is not None:
            return None
        run.bind(ctx)
        res = run.advance(run.clock() + seconds)
        if res is None and last:
            res = run.stop_time(hours)
        if res is None:
            return None
        if res.get("outcome") == "failed":
            err = res.get("error") if isinstance(res.get("error"), dict) else {}
            raise PartError(str(err.get("code") or res.get("reason") or "auto_failed"), str(res.get("sentence") or "Chạy tự động không xong."))
        return res
    return go


def start(project_dir: Path | str, pid: str, transport: Transport, *, until: str | None = None, max_steps: int = loop.DEFAULT_MAX_STEPS, actor: str = "human",
          manager: Any = None, slice_seconds: float = SLICE_SECONDS, max_hours: float = MAX_HOURS, poll: float = loop.POLL_SECONDS,
          sleep: Callable[[float], None] = time.sleep) -> dict:
    """Start the run: returns {job_id, run_id}. Raises the runner's `Busy` when an automatic run of this project is already going."""
    if manager is None:
        from bti.longjob import manager as default
        manager = default
    run_id = runlog.new_run_id()
    log = runlog.RunLog(project_dir, run_id, pid=pid, until=until, max_steps=max_steps, actor=actor)
    run = loop.Run(transport, pid, run_id=run_id, log_=log, until=until, max_steps=max_steps, poll=poll, sleep=sleep)
    n = max(1, int(math.ceil(max_hours * 3600.0 / slice_seconds)))
    parts = [Part(key="slice%02d" % (i + 1), title="Chạy tự động", run=_slice(run, i, i == n - 1, slice_seconds, max_hours), est_seconds=slice_seconds,
                  is_done=lambda ctx: run.result is not None) for i in range(n)]
    meta: dict[str, Any] = {k: None for k in META_KEYS}
    meta.update(run_id=run_id, until=until, max_steps=max_steps, of=len(loop.reasons.STEPS), steps_taken=0)
    job = manager.start(kind=KIND, pid=pid, project_dir=project_dir, parts=parts, meta=meta)
    log.set_job(job["id"])
    log.prune()
    return {"job_id": job["id"], "run_id": run_id}
