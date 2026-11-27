"""Background preview jobs.

Pattern (background job, status polling, unique result names, keep last N)
follows the comic pipeline's preview handling in ui/screens/s9_mascot.py and
stages/mascot/render.py, reimplemented with a thread pool.
"""
from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from bti.engine.errors import RenderError
from bti.script.runner import RESTART_MESSAGE, find_record, job_file, write_record
from bti.script.store import ProjectGone, make_parent

from .common import ApiError, safe_join, scrub_paths
from bti.fsio import atomic_replace

KEEP_PREVIEWS = 20
MAX_JOBS = 300


class JobManager:
    def __init__(self, workers: int = 2, projects_root: Path | None = None):
        """With `projects_root`, job records are written to projects/<pid>/cache/jobs/<id>.json (see bti.script.runner)."""
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bti-job")
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self.projects_root = Path(projects_root) if projects_root else None

    def running(self, pid: str) -> bool:
        return any(j["pid"] == pid and j["state"] in ("queued", "running") for j in list(self._jobs.values()))

    def active(self, pid: str) -> list[dict]:
        """The preview jobs of project `pid` that are queued or running, oldest first: `{id, state, progress, created}` (copies)."""
        with self._lock:
            rows = [j for j in self._jobs.values() if j["pid"] == pid and j["state"] in ("queued", "running")]
        return [{"id": j["id"], "state": j["state"], "progress": j["progress"], "created": j["created"]}
                for j in sorted(rows, key=lambda j: j["created"])]

    def _persist(self, job: dict) -> None:
        if self.projects_root is not None and (self.projects_root / job["pid"]).is_dir():
            write_record(job_file(self.projects_root, job["pid"], job["id"]), self._public(job))

    @staticmethod
    def _public(j: dict) -> dict:
        out = {"state": j["state"], "progress": j["progress"], "result_url": j["result_url"], "error": j["error"]}
        if j.get("error_code"):       # a technique could not draw: the page names the shot (code render_failed)
            out.update({k: j.get(k) for k in ("error_code", "shot", "overlay", "technique", "asset")})
        return out

    def submit(self, pid: str, fn: Callable[[Callable[[float], None]], str]) -> str:
        """`fn(progress_cb)` returns the result_url."""
        jid = uuid.uuid4().hex[:16]
        job = {"id": jid, "pid": pid, "state": "queued", "progress": 0.0, "result_url": None, "error": None,
               "created": time.time()}
        with self._lock:
            self._jobs[jid] = job
            from bti import deploy_guard
            if deploy_guard.active():
                self._jobs.pop(jid, None)
                raise deploy_guard.DeployBusy()
            if len(self._jobs) > MAX_JOBS:
                for k in sorted(self._jobs, key=lambda k: self._jobs[k]["created"])[: len(self._jobs) - MAX_JOBS]:
                    if self._jobs[k]["state"] in ("done", "error"):
                        self._jobs.pop(k, None)

        def progress(p: float) -> None:
            job["progress"] = round(max(0.0, min(1.0, float(p))), 3)

        def run() -> None:
            job["state"] = "running"
            self._persist(job)
            try:
                url = fn(progress)
                job["result_url"] = url
                job["progress"] = 1.0
                job["state"] = "done"
            except RenderError as e:
                job.update(error=scrub_paths(e.message), error_code="render_failed", shot=e.shot, overlay=e.overlay, technique=e.technique, asset=getattr(e, "asset", None),
                           state="error")
            except ApiError as e:
                job["error"] = e.detail
                job["state"] = "error"
            except BaseException as e:  # noqa: BLE001
                logging.getLogger("bti.editor").warning("job failed", exc_info=e)
                job["error"] = scrub_paths(f"{type(e).__name__}: {e}")[:400]
                job["state"] = "error"
            self._persist(job)

        self._persist(job)
        self._pool.submit(run)
        return jid

    def get(self, jid: str) -> dict | None:
        j = self._jobs.get(jid)
        if j is None:
            rec = find_record(self.projects_root, jid) if self.projects_root else None
            if rec is None or "kind" in rec:      # records of script jobs are served by the script router
                return None
            return {k: rec.get(k) for k in ("state", "progress", "result_url", "error", "error_code", "shot", "overlay", "technique", "asset")
                    if k in ("state", "progress", "result_url", "error") or rec.get(k)}
        return self._public(j)

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
                   draft: dict | None, pid: str, progress: Callable[[float], None], lock=None) -> str:
    """`project` is the PREVIEW instance of the engine project (not the one that answers stills), and `lock` serialises
    previews of that project among themselves. Stills and validation never wait for a preview."""
    lock = lock or threading.RLock()
    pdir = project_dir / "cache" / "previews"
    make_parent(pdir / "x", 2)                  # never re-creates the project folder itself (ProjectGone if it was deleted)
    uid = uuid.uuid4().hex[:8]
    silent = pdir / f"tmp_{uid}.mp4"
    final = pdir / f"pv_{int(t0 * 1000)}_{int(t1 * 1000)}_{uid}.mp4"
    try:
        with lock:
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
            atomic_replace(silent, final)
    except BaseException:
        silent.unlink(missing_ok=True)
        final.unlink(missing_ok=True)
        raise
    prune_previews(pdir)
    return f"/api/projects/{pid}/files/cache/previews/{final.name}"
