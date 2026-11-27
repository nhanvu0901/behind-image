"""The long-job manager: a job is a list of parts run in order, in one thread, with cancel, a 35-minute limit per part,
persistence under projects/<pid>/cache/longjobs/ and the heavy slot around the parts that ask for it.

Resume is "start the same kind of job again": a part answers for itself whether its output already exists and is current
(`Part.is_done(ctx)` before the heavy slot is taken, or by returning at once from `run`)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from bti.proc import group_kwargs, kill_tree
from bti import deploy_guard

from .config import REPO_ROOT, load as load_config
from .heavy import Cancelled, HeavyError, HeavySlot
from bti.fsio import atomic_replace

PART_LIMIT_SECONDS = 35 * 60.0
CANCEL_GRACE_SECONDS = 10.0
KEEP_IN_MEMORY = 200
KEEP_PER_PROJECT = 30
LOG_TAIL = 40
JOB_ID_RE = re.compile(r"[0-9a-f]{16}")
PID_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
KIND_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
ACTIVE = ("queued", "waiting", "running")
FINAL = ("done", "error", "cancelled", "interrupted")
RESTART_MESSAGE = "Máy chủ đã khởi động lại khi việc này đang chạy; kết quả chưa được ghi. Bấm chạy lại để làm tiếp phần còn thiếu."


def _jid(job) -> str:
    return job.get("id", "") if isinstance(job, dict) else job


class Busy(Exception):
    """This project already runs a job of this kind. `job` is that job's public record."""

    def __init__(self, job: dict):
        super().__init__("a job of this kind is already running for this project")
        self.job = job
        self.job_id = job.get("id")


class PartError(Exception):
    """Raised by a part to fail the job with its own code and a sentence for the owner (Vietnamese)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


class ProjectGone(OSError):
    pass


@dataclass
class Part:
    key: str
    title: str
    run: Callable[["Context"], dict | None]
    heavy: bool = False
    est_seconds: float | None = None
    is_done: Callable[["Context"], bool] | None = None      # optional: True = output already current, skip without the slot


# ---------------------------------------------------------------- persistence

def _write_json(path: Path, rec: dict, project_dir: Path) -> None:
    """Atomic, best effort, and never re-creates a project folder that was deleted."""
    try:
        if not project_dir.is_dir():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        atomic_replace(tmp, path)
    except (OSError, ValueError, TypeError):
        pass


def mark_interrupted(rec: dict) -> bool:
    """A record that says queued/waiting/running belongs to a process that is gone: report it as `interrupted`."""
    if rec.get("state") not in ACTIVE:
        return False
    rec.update(state="interrupted", error=RESTART_MESSAGE, error_code="interrupted", finished=time.time())
    for p in rec.get("parts") or []:
        if isinstance(p, dict) and p.get("state") != "done":
            p["state"] = "interrupted"
    return True


def read_record(path: Path) -> dict | None:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(rec, dict) or not isinstance(rec.get("id"), str):
        return None
    if mark_interrupted(rec):
        _write_json(path, rec, path.parents[2])
    return rec


def jobs_dir(project_dir: Path) -> Path:
    return Path(project_dir) / "cache" / "longjobs"


# ---------------------------------------------------------------- runtime objects

class _Run:
    """Per-part runtime flags shared by the supervisor, the part thread and the context."""

    def __init__(self) -> None:
        self.timed_out = False
        self.children: set[subprocess.Popen] = set()
        self.lock = threading.Lock()

    def kill_children(self) -> None:
        with self.lock:
            kids = list(self.children)
        for p in kids:
            kill_tree(p)


class Context:
    """What a part's function receives."""

    def __init__(self, job: "_Job", index: int, run: _Run, workdir: Path):
        self._job, self._i, self._run = job, index, run
        self.workdir = workdir

    @property
    def job_id(self) -> str:
        return self._job.id

    @property
    def meta(self) -> dict:
        return self._job.meta

    def progress(self, fraction: float, note: str = "") -> None:
        self._job.part_progress(self._i, fraction, note)

    def log(self, text: str) -> None:
        self._job.log(text)

    def cancelled(self) -> bool:
        return self._job.cancel.is_set() or self._run.timed_out

    def run_process(self, cmd: list[str], cwd: str | Path | None = None, env: dict | None = None,
                    on_line: Callable[[str], None] | None = None, *, stdin: str | bytes | None = None,
                    on_start: Callable[["ProcessHandle"], None] | None = None, separate_stderr: bool = False,
                    on_stderr: Callable[[str], None] | None = None) -> int:
        """Run a child in its own process group, feed each output line to `on_line` and to the log, and return its exit code.
        If the job is cancelled or the part overruns, the whole process tree is killed first (the child is gone when this
        returns). `env`, when given, is the complete environment of the child.

        Optional, for programs that are talked to:
        - `stdin`: text (or bytes) written to the child's standard input. It is then closed, unless `on_start` is given.
        - `on_start(handle)`: called once the child runs, with a handle (`write(text)`, `close_stdin()`, `pid`) so the caller can
          send more input later, from the part's own thread or from `on_line`; standard input stays open until `close_stdin()`
          or the end of the child.
        - `separate_stderr`: the child's standard error is not mixed into `on_line`; each of its lines goes to `on_stderr` (and to
          the log, marked with "[stderr] "). Without it both streams arrive, in order, at `on_line`."""
        if self.cancelled():
            return -1
        use_stdin = stdin is not None or on_start is not None
        proc = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env,
                                stdin=subprocess.PIPE if use_stdin else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE if separate_stderr else subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1, **group_kwargs())
        handle = ProcessHandle(proc) if use_stdin else None
        with self._run.lock:
            self._run.children.add(proc)

        def pump(stream, callback, tag: str) -> None:
            try:
                for line in stream:
                    line = line.rstrip("\r\n")
                    self._job.log(tag + line)
                    if callback is not None:
                        try:
                            callback(line)
                        except Exception:           # noqa: BLE001 - a broken line parser must not kill the child
                            pass
            except (OSError, ValueError):
                pass

        readers = [threading.Thread(target=pump, args=(proc.stdout, on_line, ""), daemon=True)]
        if separate_stderr:
            readers.append(threading.Thread(target=pump, args=(proc.stderr, on_stderr, "[stderr] "), daemon=True))
        for r in readers:
            r.start()
        try:
            if handle is not None:
                if stdin is not None:
                    handle.write(stdin.decode("utf-8", "replace") if isinstance(stdin, bytes) else stdin)
                if on_start is None:
                    handle.close_stdin()
                else:
                    on_start(handle)
            while True:
                try:
                    proc.wait(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    if self.cancelled():
                        kill_tree(proc)
                        break
        finally:
            if proc.poll() is None:
                kill_tree(proc)
            for r in readers:
                r.join(timeout=5)
            for st in (proc.stdout, proc.stderr, proc.stdin):
                try:
                    if st is not None:
                        st.close()
                except (OSError, ValueError):
                    pass
            with self._run.lock:
                self._run.children.discard(proc)
        rc = proc.returncode
        return -1 if rc is None else int(rc)


class ProcessHandle:
    """What `on_start` receives: a way to talk to the child's standard input. Writes after the child ended are ignored."""

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self.pid = proc.pid

    def write(self, text: str) -> bool:
        try:
            self._proc.stdin.write(text)            # type: ignore[union-attr]
            self._proc.stdin.flush()                # type: ignore[union-attr]
            return True
        except (OSError, ValueError):
            return False

    def close_stdin(self) -> None:
        try:
            self._proc.stdin.close()                # type: ignore[union-attr]
        except (OSError, ValueError, AttributeError):
            pass

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None


class _Job:
    def __init__(self, kind: str, pid: str, project_dir: Path, parts: list[Part], meta: dict, persist: Callable[["_Job", bool], None]):
        self.id = uuid.uuid4().hex[:16]
        self.kind, self.pid, self.project_dir = kind, pid, Path(project_dir)
        self.parts = parts
        self.meta = meta
        self.state = "queued"
        self.error: str | None = None
        self.error_code: str | None = None
        self.result: dict = {}
        self.created = time.time()
        self.finished: float | None = None
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self._persist = persist
        self.tail: deque[str] = deque(maxlen=LOG_TAIL)
        self.rows = [{"key": p.key, "title": p.title, "state": "queued", "progress": 0.0, "note": "", "started": None,
                      "ended": None, "error": None, "heavy": bool(p.heavy), "est_seconds": p.est_seconds} for p in parts]
        self._weights = [float(p.est_seconds) if p.est_seconds else 60.0 for p in parts]
        self._log_path = jobs_dir(self.project_dir) / f"{self.id}.log"

    # -- views
    def progress(self) -> float:
        if self.state == "done":
            return 1.0
        total = sum(self._weights) or 1.0
        got = sum(w * (1.0 if r["state"] == "done" else r["progress"]) for w, r in zip(self._weights, self.rows))
        return round(min(1.0, got / total), 4)

    def public(self) -> dict:
        with self.lock:
            return {"id": self.id, "kind": self.kind, "pid": self.pid, "state": self.state, "progress": self.progress(),
                    "parts": [dict(r) for r in self.rows], "error": self.error, "error_code": self.error_code,
                    "result": self.result, "created": self.created, "finished": self.finished,
                    "meta": self.meta, "log_tail": list(self.tail)}

    # -- changes
    def _row(self, i: int, force: bool = True, **kw) -> None:
        with self.lock:
            self.rows[i].update(kw)
        self._persist(self, force)

    def part_progress(self, i: int, fraction: float, note: str) -> None:
        try:
            f = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            return
        with self.lock:
            r = self.rows[i]
            if r["state"] != "running":
                return
            r["progress"] = f
            if note:
                r["note"] = str(note)
        self._persist(self, False)

    def log(self, text: str) -> None:
        text = str(text)
        with self.lock:
            self.tail.append(text)
        try:
            if self.project_dir.is_dir():
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
        except OSError:
            pass

    def set_state(self, state: str, error: str | None = None, code: str | None = None) -> None:
        with self.lock:
            self.state = state
            if error is not None:
                self.error, self.error_code = error, code
            if state in FINAL:
                self.finished = time.time()
        self._persist(self, True)

    def close_rows(self, state: str) -> None:
        """Rows that never finished take the final state of the job (no spinner on a dead job)."""
        with self.lock:
            for r in self.rows:
                if r["state"] in ("queued", "waiting", "running"):
                    r["state"] = state
                    if r["started"] and not r["ended"]:
                        r["ended"] = time.time()


class LongJobManager:
    def __init__(self, heavy: HeavySlot | None = None, *, part_limit: float = PART_LIMIT_SECONDS,
                 clock: Callable[[], float] = time.monotonic, projects_root: Path | None = None,
                 cancel_grace: float = CANCEL_GRACE_SECONDS):
        self._heavy = heavy
        self.part_limit, self.clock, self.cancel_grace = part_limit, clock, cancel_grace
        self.projects_root = Path(projects_root) if projects_root else None
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()
        self._roots: set[Path] = set()
        self._last_write: dict[str, float] = {}

    # -- setup
    def configure(self, projects_root: Path | str | None = None, heavy: HeavySlot | None = None) -> None:
        """Phase-2 wiring: tell the manager where the projects are (for lookups by job id) and, in tests, which heavy slot."""
        if projects_root is not None:
            self.projects_root = Path(projects_root)
        if heavy is not None:
            self._heavy = heavy

    @property
    def heavy(self) -> HeavySlot:
        with self._lock:
            if self._heavy is None:
                cfg = load_config()
                self._heavy = HeavySlot(cfg, own_markers=(str(REPO_ROOT), str(REPO_ROOT).replace("\\", "/")))
            return self._heavy

    def startup(self) -> None:
        """Release a heavy lock of ours whose process is dead. Called once when the app starts (also done lazily)."""
        self.heavy.startup()

    # -- persistence
    def _persist(self, job: _Job, force: bool) -> None:
        now = time.monotonic()
        if not force and now - self._last_write.get(job.id, 0.0) < 0.5:
            return
        self._last_write[job.id] = now
        _write_json(jobs_dir(job.project_dir) / f"{job.id}.json", job.public(), job.project_dir)

    def _prune(self, project_dir: Path) -> None:
        d = jobs_dir(project_dir)
        try:
            files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return
        with self._lock:
            live = {j.id for j in self._jobs.values() if j.state in ACTIVE}
        for f in files[KEEP_PER_PROJECT:]:
            if f.stem in live:
                continue
            for g in (f, f.with_suffix(".log")):
                try:
                    g.unlink()
                except OSError:
                    pass

    # -- public api
    def start(self, kind: str, pid: str, project_dir: Path | str, parts: list[Part], meta: dict | None = None) -> dict:
        """Start a job and return its public record (`["id"]` is the id; `get`, `cancel` and `wait` accept the record or the id).
        Raises Busy when this project already runs a job of this kind."""
        if not KIND_RE.fullmatch(kind or ""):
            raise ValueError("bad job kind")
        if not PID_RE.fullmatch(pid or ""):
            raise ValueError("bad project id")
        parts = list(parts)
        if not parts or len({p.key for p in parts}) != len(parts):
            raise ValueError("a job needs at least one part, and part keys must be unique")
        project_dir = Path(project_dir)
        if not project_dir.is_dir():
            raise ProjectGone("the project folder is gone")
        job = _Job(kind, pid, project_dir, parts, dict(meta or {}), self._persist)
        with self._lock:
            busy = next((j for j in self._jobs.values() if j.pid == pid and j.kind == kind and j.state in ACTIVE), None)
            if busy is not None:
                raise Busy(busy.public())
            self._jobs[job.id] = job
            # Register before checking the deploy lock: the deploy's subsequent
            # state read either sees this job or this registration is removed.
            if deploy_guard.active():
                self._jobs.pop(job.id, None)
                raise deploy_guard.DeployBusy()
            self._roots.add(project_dir.parent)
            if len(self._jobs) > KEEP_IN_MEMORY:
                for k in sorted(self._jobs, key=lambda k: self._jobs[k].created)[: len(self._jobs) - KEEP_IN_MEMORY]:
                    if self._jobs[k].state in FINAL:
                        self._jobs.pop(k, None)
                        self._last_write.pop(k, None)
        self._persist(job, True)
        threading.Thread(target=self._run_job, args=(job,), daemon=True, name=f"longjob-{job.id}").start()
        self._prune(project_dir)
        return job.public()

    def get(self, job_id: str | dict) -> dict | None:
        job_id = _jid(job_id)
        with self._lock:
            j = self._jobs.get(job_id)
        if j is not None:
            return j.public()
        if not (isinstance(job_id, str) and JOB_ID_RE.fullmatch(job_id)):
            return None
        for root in self._known_roots():
            if not root.is_dir():
                continue
            try:
                dirs = sorted(root.iterdir())
            except OSError:
                continue
            for d in dirs:
                f = d / "cache" / "longjobs" / f"{job_id}.json"
                if f.is_file() and not d.is_symlink():
                    return read_record(f)
        return None

    def cancel(self, job_id: str | dict) -> bool:
        """Ask the job to stop; True when it was still active. The child process is killed within moments."""
        job_id = _jid(job_id)
        with self._lock:
            j = self._jobs.get(job_id)
        if j is None or j.state not in ACTIVE:
            return False
        j.cancel.set()
        return True

    def active(self, pid: str, kind: str | None = None) -> dict | None:
        """The newest queued/waiting/running job of the project (of that kind, when given), else None."""
        with self._lock:
            js = [j for j in self._jobs.values() if j.pid == pid and j.state in ACTIVE and (kind is None or j.kind == kind)]
        if not js:
            return None
        return max(js, key=lambda j: j.created).public()

    def for_project(self, pid: str, project_dir: Path | str | None = None, kind: str | None = None) -> list[dict]:
        """Jobs of a project, newest first: those in memory plus the persisted records of earlier runs."""
        out: dict[str, dict] = {}
        d = Path(project_dir) if project_dir else self._project_dir(pid)
        if d is not None:
            for f in jobs_dir(d).glob("*.json"):
                rec = read_record(f)
                if rec and rec.get("pid") == pid:
                    out[rec["id"]] = rec
        with self._lock:
            live = [j for j in self._jobs.values() if j.pid == pid]
        for j in live:
            out[j.id] = j.public()
        rows = [r for r in out.values() if kind is None or r.get("kind") == kind]
        return sorted(rows, key=lambda r: r.get("created") or 0, reverse=True)

    def wait(self, job_id: str | dict, timeout: float = 30.0) -> dict | None:
        """Block until the job is in a final state (for tests and scripts)."""
        job_id = _jid(job_id)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rec = self.get(job_id)
            if rec is None or rec["state"] in FINAL:
                return rec
            time.sleep(0.01)
        return self.get(job_id)

    # -- roots
    def _known_roots(self) -> list[Path]:
        roots = []
        if self.projects_root is not None:
            roots.append(self.projects_root)
        with self._lock:
            roots.extend(r for r in self._roots if r != self.projects_root)
        if not roots:
            roots.append(REPO_ROOT / "projects")
        return roots

    def _project_dir(self, pid: str) -> Path | None:
        for root in self._known_roots():
            if (root / pid).is_dir():
                return root / pid
        return None

    # -- running
    def _run_job(self, job: _Job) -> None:
        try:
            if job.cancel.is_set():
                raise Cancelled()
            job.set_state("running")
            for i, part in enumerate(job.parts):
                if job.cancel.is_set():
                    raise Cancelled()
                self._run_part(job, i, part)
            job.set_state("done")
        except Cancelled:
            job.close_rows("cancelled")
            job.set_state("cancelled")
        except PartError as e:
            job.close_rows("cancelled")
            job.set_state("error", e.message, e.code)
        except BaseException as e:      # noqa: BLE001
            job.close_rows("cancelled")
            job.set_state("error", f"Việc bị lỗi không mong đợi: {type(e).__name__}: {str(e)[:200]}", "longjob_internal")

    def _fail_row(self, job: _Job, i: int, code: str, message: str) -> PartError:
        job._row(i, state="error", error=message, ended=time.time())
        return PartError(code, message)

    def _run_part(self, job: _Job, i: int, part: Part) -> None:
        run = _Run()
        workdir = jobs_dir(job.project_dir) / "work" / job.kind
        if not job.project_dir.is_dir():
            raise PartError("project_gone", "Dự án đã bị xóa khi việc này đang chạy.")
        workdir.mkdir(parents=True, exist_ok=True)
        ctx = Context(job, i, run, workdir)
        if part.is_done is not None:
            try:
                already = bool(part.is_done(ctx))
            except Exception:       # noqa: BLE001 - when the check itself fails, do the work
                already = False
            if already:
                now = time.time()
                job._row(i, state="done", progress=1.0, note="Đã có sẵn, bỏ qua.", started=now, ended=now)
                return
        if part.heavy:
            def on_wait(note: str) -> None:
                if job.rows[i]["note"] != note or job.rows[i]["state"] != "waiting":
                    job.log(note)
                    job._row(i, state="waiting", note=note)
                    with job.lock:
                        if job.state == "running":
                            job.state = "waiting"
                    job._persist(job, True)
            what = f"{job.kind}: {part.title} ({job.pid})"
            cm = self.heavy.hold(what, cancelled=job.cancel.is_set, on_wait=on_wait, expected_seconds=part.est_seconds)
        else:
            cm = nullcontext()
        try:
            with cm:
                with job.lock:
                    if job.state == "waiting":
                        job.state = "running"
                job._row(i, state="running", note="", started=time.time())
                result = self._supervise(job, i, part, ctx, run)
        except HeavyError as e:
            raise self._fail_row(job, i, "heavy_unavailable",
                                 f"Không dùng được khóa máy nặng ({e}). Hãy báo cho chủ máy.") from e
        except Cancelled:
            job._row(i, state="cancelled", ended=time.time())
            raise
        job._row(i, state="done", progress=1.0, ended=time.time())
        if result:
            with job.lock:
                job.result.update(result)

    def _supervise(self, job: _Job, i: int, part: Part, ctx: Context, run: _Run) -> dict | None:
        box: dict = {}

        def target() -> None:
            try:
                box["result"] = part.run(ctx)
            except BaseException as e:      # noqa: BLE001
                box["error"] = e

        t = threading.Thread(target=target, daemon=True, name=f"longjob-{job.id}-{part.key}")
        t0 = self.clock()
        t.start()
        while t.is_alive():
            t.join(0.05)
            if not t.is_alive():
                break
            if self.clock() - t0 > self.part_limit and not run.timed_out:
                run.timed_out = True
            if run.timed_out or job.cancel.is_set():
                run.kill_children()
                t.join(self.cancel_grace)
                break      # a part that ignores the flag is abandoned (its thread is a daemon; its children are dead)
        if run.timed_out and not job.cancel.is_set():
            mins = int(self.part_limit // 60)
            raise self._fail_row(job, i, "part_timeout",
                                 f"Bước \"{part.title}\" chạy quá {mins} phút nên đã bị dừng. Bấm chạy lại để làm tiếp.")
        if job.cancel.is_set():
            raise Cancelled()
        err = box.get("error")
        if t.is_alive():
            raise self._fail_row(job, i, "part_stuck", f"Bước \"{part.title}\" không dừng lại được.")
        if isinstance(err, Cancelled):
            raise err
        if isinstance(err, PartError):
            raise self._fail_row(job, i, err.code, err.message) from err
        if err is not None:
            raise self._fail_row(job, i, "part_failed",
                                 f"Bước \"{part.title}\" bị lỗi: {type(err).__name__}: {str(err)[:200]}") from err
        res = box.get("result")
        return res if isinstance(res, dict) else None


manager = LongJobManager()
