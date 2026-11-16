"""Background preview jobs.

Pattern (background job, status polling, unique result names, keep last N)
follows the comic pipeline's preview handling in ui/screens/s9_mascot.py and
stages/mascot/render.py, reimplemented with a thread pool.
"""
from __future__ import annotations

import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from .common import ApiError, safe_join
from .engine_adapter import ENGINE_LOCK

KEEP_PREVIEWS = 20
MAX_JOBS = 300


class JobManager:
    def __init__(self, workers: int = 2):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bti-job")
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def submit(self, pid: str, fn: Callable[[Callable[[float], None]], str]) -> str:
        """`fn(progress_cb)` returns the result_url."""
        jid = uuid.uuid4().hex[:16]
        job = {"id": jid, "pid": pid, "state": "queued", "progress": 0.0, "result_url": None, "error": None,
               "created": time.time()}
        with self._lock:
            self._jobs[jid] = job
            if len(self._jobs) > MAX_JOBS:
                for k in sorted(self._jobs, key=lambda k: self._jobs[k]["created"])[: len(self._jobs) - MAX_JOBS]:
                    if self._jobs[k]["state"] in ("done", "error"):
                        self._jobs.pop(k, None)

        def progress(p: float) -> None:
            job["progress"] = round(max(0.0, min(1.0, float(p))), 3)

        def run() -> None:
            job["state"] = "running"
            try:
                url = fn(progress)
                job["result_url"] = url
                job["progress"] = 1.0
                job["state"] = "done"
            except ApiError as e:
                job["error"] = e.detail
                job["state"] = "error"
            except BaseException as e:  # noqa: BLE001
                job["error"] = f"{type(e).__name__}: {e}"[:400]
                job["state"] = "error"

        self._pool.submit(run)
        return jid

    def get(self, jid: str) -> dict | None:
        j = self._jobs.get(jid)
        if j is None:
            return None
        return {"state": j["state"], "progress": j["progress"], "result_url": j["result_url"], "error": j["error"]}

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


def prune_previews(pdir: Path, keep: int = KEEP_PREVIEWS) -> None:
    try:
        files = [f for f in pdir.iterdir() if f.name.startswith("pv_") and f.suffix == ".mp4"]
        files.sort(key=lambda f: f.stat().st_mtime)
        for f in files[: max(0, len(files) - keep)]:
            f.unlink(missing_ok=True)
        for f in pdir.glob("tmp_*.mp4"):
            if time.time() - f.stat().st_mtime > 3600:
                f.unlink(missing_ok=True)
    except OSError:
        pass


def render_preview(project, project_dir: Path, audio: Path | None, t0: float, t1: float, width: int, fps: int,
                   draft: dict | None, pid: str, progress: Callable[[float], None]) -> str:
    pdir = project_dir / "cache" / "previews"
    pdir.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    silent = pdir / f"tmp_{uid}.mp4"
    final = pdir / f"pv_{int(t0 * 1000)}_{int(t1 * 1000)}_{uid}.mp4"
    try:
        with ENGINE_LOCK:
            try:
                if draft is not None:
                    project.use_draft(draft)
                project.render_range(t0, t1, silent, width=width, fps=fps,
                                     on_progress=lambda p: progress(float(p) * 0.9))
            finally:
                if draft is not None:
                    try:
                        project.use_draft(None)
                    except Exception:
                        pass
        if audio is not None and audio.is_file():
            cmd = ["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(silent), "-ss", f"{t0:.3f}", "-t",
                   f"{t1 - t0:.3f}", "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                   "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(final)]
            r = subprocess.run(cmd, capture_output=True, timeout=300)
            if r.returncode != 0:
                raise RuntimeError("audio mux failed: " + r.stderr.decode("utf-8", "replace")[-200:])
            silent.unlink(missing_ok=True)
        else:
            silent.replace(final)
    except BaseException:
        silent.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        raise
    prune_previews(pdir)
    return f"/api/projects/{pid}/files/cache/previews/{final.name}"
