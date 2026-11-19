"""How the rest of the app reaches `publish.sync`, with one line each:

    register(projects_root, output_root)         create_app: this projects folder has an output folder (the long-job parts below look it up)
    notify(...)                                  call `sync` and never raise; a problem is logged and kept as a warning the state answer shows
    OutputSyncMiddleware                         after every successful change of a project through the API (an approval, a save, an edit, a new project from the library)
    job_part(Part, kind, project_dir)            the last part of the voice job and of the export job: publish what the job just made (and, after the export, clean the caches)
    warnings_for(output_root, project_dir)       what the state answer shows

Writing happens on one background thread (a request never waits for it); two changes of the same project in a row become one write. `flush()` waits for it (the tests)."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from . import fsutil, publish
from .paths import STATE_FILE, folder_key

log = logging.getLogger("bti.output")

_ROOTS: dict[str, Path] = {}                     # resolved projects folder -> output folder
_ERRORS: dict[tuple[str, str], dict] = {}        # (output root, project) -> the last failure
_EXEC = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bti-output")
_PENDING: set[tuple[str, str]] = set()
_LAST_END: dict[tuple[str, str], float] = {}
_GUARD = threading.Lock()
MIN_GAP = 1.0                                    # seconds between two background writes of one project
MUTATING = ("POST", "PUT", "PATCH", "DELETE")
_PROJECT_PATH = re.compile(r"^/api/projects/([a-z0-9][a-z0-9_-]{0,63})(?:/(.*))?$")
SKIP_SUFFIX = ("output", "output/build")         # the routes of this package do their own writing


def register(projects_root: Path | str, output_root: Path | str | None) -> None:
    key = str(Path(projects_root).resolve())
    if output_root is None:
        _ROOTS.pop(key, None)
    else:
        _ROOTS[key] = Path(output_root)


def output_root_of(project_dir: Path | str) -> Path | None:
    """The output folder of the app this project belongs to, or None (no app registered it, or it has none)."""
    return _ROOTS.get(str(Path(project_dir).resolve().parent))


def _key(output_root: Path, pid: str) -> tuple[str, str]:
    return (str(Path(output_root).resolve()), pid)


def notify(projects_root: Path | str, pid: str, moment: str, *, output_root: Path | str | None = None, job: dict | None = None, **kw: Any) -> dict | None:
    """`publish.sync` that never raises. Returns its answer, or None when the project has no output folder or the sync failed (then the failure is a warning)."""
    root = Path(output_root) if output_root else _ROOTS.get(str(Path(projects_root).resolve()))
    if root is None:
        return None
    try:
        res = publish.sync(Path(projects_root) / pid, root, moment=moment, job=job, **kw)
        with _GUARD:
            _ERRORS.pop(_key(root, pid), None)
        return res
    except publish.NotApplicable:
        return None
    except Exception as e:      # noqa: BLE001 - the step that called us must not fail because a folder could not be written
        log.warning("output: the folder of %s could not be written (%s)", pid, moment, exc_info=True)
        with _GUARD:
            _ERRORS[_key(root, pid)] = {"code": "output_failed", "detail": "%s: %s" % (type(e).__name__, str(e)[:200]),
                                        "sentence": "Chưa ghi được thư mục output của dự án này (%s). Việc đang làm không bị ảnh hưởng; thử lại bằng `bti output %s`." % (str(e)[:120] or type(e).__name__, pid),
                                        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        return None


def schedule(projects_root: Path | str, pid: str, moment: str, output_root: Path | str | None = None) -> None:
    """Write the folder of `pid` on the background thread. Several calls before it starts are one write."""
    root = Path(output_root) if output_root else _ROOTS.get(str(Path(projects_root).resolve()))
    if root is None:
        return
    k = _key(root, pid)
    with _GUARD:
        if k in _PENDING:
            return
        _PENDING.add(k)

    def run():
        with _GUARD:
            wait = MIN_GAP - (time.monotonic() - _LAST_END.get(k, -1e9))
        if wait > 0:
            time.sleep(wait)
        with _GUARD:
            _PENDING.discard(k)
        try:
            notify(projects_root, pid, moment, output_root=root)
        finally:
            with _GUARD:
                _LAST_END[k] = time.monotonic()
    try:
        _EXEC.submit(run)
    except RuntimeError:        # the interpreter is shutting down
        with _GUARD:
            _PENDING.discard(k)


def flush(timeout: float = 60.0) -> bool:
    """Wait until every write queued so far has been done (for the tests)."""
    try:
        _EXEC.submit(lambda: None).result(timeout)
        return True
    except Exception:       # noqa: BLE001
        return False


def warnings_for(output_root: Path | str | None, project_dir: Path | str) -> list[dict]:
    """The warnings of the output folder of a project, for the state answer: the last failure of a write, and the warnings the last write put in `state.json`."""
    if output_root is None:
        return []
    root, pdir = Path(output_root), Path(project_dir)
    out: list[dict] = []
    with _GUARD:
        err = _ERRORS.get(_key(root, pdir.name))
    if err:
        out.append({k: err[k] for k in ("code", "detail", "sentence")})
    try:
        meta = json.loads((pdir / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    st = fsutil.read_json(root / folder_key(meta if isinstance(meta, dict) else {}, pdir.name) / STATE_FILE)
    if isinstance(st, dict) and st.get("project") == pdir.name:
        for w in st.get("warnings") or []:
            if isinstance(w, dict) and w.get("sentence"):
                out.append({"code": w.get("code") or "output_warning", "detail": w.get("detail") or "", "sentence": w["sentence"]})
    return out


# ------------------------------------------------------------------------------------------------ the middleware
class OutputSyncMiddleware:
    """Pure ASGI. After a request that changed a project (POST, PUT, PATCH or DELETE under `/api/projects/{pid}/...`, answered below 400) the folder of that project is brought up to date in the
    background; after `POST /api/library/projects` (a new project) the same for the project the answer names. Nothing is done for any other request, and the answer is never delayed or changed."""

    def __init__(self, app, projects_root: Path | str, output_root: Path | str):
        self.app, self.projects_root, self.output_root = app, Path(projects_root), Path(output_root)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in MUTATING:
            return await self.app(scope, receive, send)
        path = scope["path"]
        m = _PROJECT_PATH.match(path)
        creating = path == "/api/library/projects" and scope["method"] == "POST"
        if not (m or creating):
            return await self.app(scope, receive, send)
        if m and (m.group(2) is None and scope["method"] == "DELETE" or (m.group(2) or "") in SKIP_SUFFIX):
            return await self.app(scope, receive, send)
        status = [0]
        body = bytearray()

        async def wrapped(message):
            if message["type"] == "http.response.start":
                status[0] = message["status"]
            elif message["type"] == "http.response.body" and creating and len(body) < 65536:
                body.extend(message.get("body", b""))
            await send(message)
        await self.app(scope, receive, wrapped)
        if status[0] >= 400 or status[0] == 0:
            return
        try:
            pid = m.group(1) if m else (json.loads(bytes(body).decode("utf-8")).get("id") if body else None)
            if isinstance(pid, str) and pid:
                schedule(self.projects_root, pid, "%s %s" % (scope["method"], (m.group(2) if m and m.group(2) else "project created")), self.output_root)
        except Exception:       # noqa: BLE001 - never a reason to touch the answer
            log.warning("output: could not schedule a write", exc_info=True)


# ------------------------------------------------------------------------------------------------ the last part of a long job
def job_part(part_cls: Any, kind: str, project_dir: Path | str) -> Any | None:
    """A part for the end of the voice job or the export job: publish what it made and, after the export, clean the caches. None when this project has no output folder.
    It never fails the job: whatever goes wrong is a warning (`warnings_for`)."""
    pdir = Path(project_dir)
    root = output_root_of(pdir)
    if root is None:
        return None
    pid = pdir.name

    def run(ctx) -> dict | None:
        try:
            if ctx.cancelled():
                return None
        except Exception:       # noqa: BLE001
            pass
        job = {"id": getattr(ctx, "job_id", None), "kind": kind}
        try:
            ctx.progress(0.1, "Lưu vào thư mục output")
        except Exception:       # noqa: BLE001
            pass
        res = notify(pdir.parent, pid, kind + " done", output_root=root, job=job)
        try:
            ctx.progress(1.0)
        except Exception:       # noqa: BLE001
            pass
        return {"output": (res or {}).get("key"), "output_warnings": len((res or {}).get("warnings") or [])} if res else {"output": None}
    return part_cls(key="output", title="Lưu vào thư mục output", run=run, heavy=False, est_seconds=120 if kind == "export" else 20)
