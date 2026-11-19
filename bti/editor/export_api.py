"""HTTP API of step 6, the export (design 2026-11-16 section 8).

    GET  /api/projects/{pid}/export                  what is ready, the plan, the manifest and report card, the files
    POST /api/projects/{pid}/export/start            start the long job (progress and cancel: /api/longjobs/{id})
    GET  /api/projects/{pid}/export/files/{name}     a file of the export folder, with range requests

Mounted by app.py through `router`; the projects folder comes from `app.state.projects_root`.
"""
from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from bti.export import check, run
from bti.export.errors import ExportError
from bti.export.settings import load_settings

from .common import ApiError, valid_pid

router = APIRouter(prefix="/api")

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,120}")
CHUNK = 1024 * 1024
TYPES = {".mp4": "video/mp4", ".txt": "text/plain; charset=utf-8", ".json": "application/json"}


def project_dir(request: Request, pid: str) -> Path:
    root = Path(request.app.state.projects_root)
    if not valid_pid(pid):
        raise ApiError(404, "project not found", code="project_not_found")
    d = root / pid
    if not d.is_dir() or (d.is_symlink() and not d.resolve().is_relative_to(root.resolve())):
        raise ApiError(404, "project not found", code="project_not_found")
    return d


def _fail(e: ExportError) -> ApiError:
    return ApiError(e.status, e.message, code=e.code, **e.extra)


class RangeNotSatisfiable(Exception):
    pass


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """`(first, last)` byte positions (inclusive) of a single `bytes=` range; None when there is no usable header (serve the
    whole file); RangeNotSatisfiable when the range lies outside the file. Several ranges are answered with the whole file."""
    if not header:
        return None
    m = re.fullmatch(r"\s*bytes\s*=\s*(\d*)\s*-\s*(\d*)\s*", header)
    if not m:
        return None
    a, b = m.groups()
    if a == "" and b == "":
        return None
    if a == "":                                   # the last n bytes
        n = int(b)
        if n == 0 or size == 0:
            raise RangeNotSatisfiable()
        return max(0, size - n), size - 1
    first = int(a)
    last = size - 1 if b == "" else min(int(b), size - 1)
    if first >= size or last < first:
        raise RangeNotSatisfiable()
    return first, last


def _iter_file(path: Path, first: int, last: int):
    remaining = last - first + 1
    with open(path, "rb") as f:
        f.seek(first)
        while remaining > 0:
            data = f.read(min(CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


def export_file(d: Path, name: str, range_header: str | None, head: bool = False, download: bool = False) -> Response:
    """A regular file directly inside `<project>/export`; never a link, never a path."""
    edir = d / "export"
    if not NAME_RE.fullmatch(name or "") or ".." in name:
        raise ApiError(404, "not found", code="export_file_not_found")
    if Path(name).suffix.lower() in (".srt", ".ass", ".ssa"):
        raise ApiError(404, "not found", code="export_file_not_found")
    p = edir / name
    try:
        if p.is_symlink() or not p.is_file() or p.resolve().parent != edir.resolve():
            raise ApiError(404, "not found", code="export_file_not_found")
        size = p.stat().st_size
    except OSError:
        raise ApiError(404, "not found", code="export_file_not_found")
    if name == "description.txt":
        try:
            original = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ApiError(404, "not found", code="export_file_not_found")
        cleaned = clean_description(original)
        if cleaned != original:
            data = cleaned.encode("utf-8")
            base = {"Accept-Ranges": "bytes", "Content-Disposition": '%s; filename="%s"' % ("attachment" if download else "inline", name), "Cache-Control": "no-cache"}
            try:
                rng = parse_range(range_header, len(data))
            except RangeNotSatisfiable:
                return Response(status_code=416, headers={**base, "Content-Range": "bytes */%d" % len(data)})
            first, last = rng if rng else (0, len(data) - 1)
            headers = {**base, "Content-Length": str(max(0, last - first + 1))}
            if rng:
                headers["Content-Range"] = "bytes %d-%d/%d" % (first, last, len(data))
            return Response(content=b"" if head else data[first:last + 1], status_code=206 if rng else 200,
                            headers=headers, media_type="text/plain; charset=utf-8")
    ctype = TYPES.get(p.suffix.lower()) or mimetypes.guess_type(name)[0] or "application/octet-stream"
    base = {"Accept-Ranges": "bytes", "Content-Disposition": '%s; filename="%s"' % ("attachment" if download else "inline", name), "Cache-Control": "no-cache"}
    try:
        rng = parse_range(range_header, size)
    except RangeNotSatisfiable:
        return Response(status_code=416, headers={**base, "Content-Range": "bytes */%d" % size})
    first, last = rng if rng else (0, size - 1)
    length = max(0, last - first + 1)
    headers = {**base, "Content-Length": str(length)}
    status = 200
    if rng:
        status = 206
        headers["Content-Range"] = "bytes %d-%d/%d" % (first, last, size)
    if head or length == 0:
        return Response(status_code=status, headers=headers, media_type=ctype)
    return StreamingResponse(_iter_file(p, first, last), status_code=status, headers=headers, media_type=ctype)


def _job_dict(manager, pid: str):
    try:
        return run._active(manager, pid)
    except Exception:   # noqa: BLE001 - the long-job runner is not there (yet): there is no job
        return None


def clean_description(text: str) -> str:
    """Remove the obsolete stock CC promise from a legacy description in responses."""
    return re.sub(r"(?im)^\s*Subtitles available\s*[-—]\s*turn on CC\.\s*$", "", text).rstrip() + "\n"


def public_manifest(m: dict | None) -> dict | None:
    if m is None:
        return None
    out = dict(m)
    names = m.get("files") if isinstance(m.get("files"), dict) else {}
    out["files"] = {k: v for k, v in names.items() if k in run.FILE_NAMES}
    out.pop("cues", None)
    out.pop("cue_problems", None)
    out["report"] = [item for item in (m.get("report") or []) if item.get("key") not in ("subtitles", "cues")]
    out["report_status"] = check.worst(out["report"])
    return out


def payload(d: Path, manager=None) -> dict:
    """The page's picture of the export. Never raises for a project that is simply not ready: `blocked` says why."""
    pid = d.name
    settings = load_settings()
    try:
        mgr = manager or run.get_manager()
    except Exception:   # noqa: BLE001
        mgr = None
    job = _job_dict(mgr, pid) if mgr is not None else None
    st = run.state(d, manager=mgr if mgr is not None else _NoManager())
    m = run.read_manifest(d)
    out: dict = {"state": st["state"], "detail": st["detail"], "reason": st.get("reason"), "job": job, "blocked": None, "plan": None,
                 "manifest": public_manifest(m), "files": [], "description": None}
    try:
        inp = run.load_inputs(d)
        out["plan"] = run.plan_for(d, settings, inputs=inp)
    except ExportError as e:
        out["blocked"] = {"code": e.code, "detail": e.message}
    except Exception:   # noqa: BLE001 - e.g. the engine cannot open the storyboard: say so, do not fail the page
        out["blocked"] = {"code": "plan_failed", "detail": "the export could not be planned"}
    if m and st["state"] in ("done", "stale"):
        names = m.get("files") if isinstance(m.get("files"), dict) else {}
        base = "/api/projects/%s/export/files/" % pid
        for key in run.FILE_NAMES:
            n = names.get(key)
            f = d / "export" / n if isinstance(n, str) else None
            if f is not None and f.is_file():
                out["files"].append({"key": key, "name": n, "size": f.stat().st_size, "url": base + n})
        try:
            if isinstance(names.get("description"), str):
                out["description"] = clean_description((d / "export" / names["description"]).read_text(encoding="utf-8")[:20000])
        except OSError:
            pass
    return out


class _NoManager:
    def active(self, *a, **k):
        return None


@router.get("/projects/{pid}/export")
def get_export(pid: str, request: Request):
    return payload(project_dir(request, pid))


@router.post("/projects/{pid}/export/start")
def start_export(pid: str, request: Request):
    d = project_dir(request, pid)
    try:
        job = run.start(d)
    except ExportError as e:
        raise _fail(e)
    jid = job.get("id") if isinstance(job, dict) else getattr(job, "id", job)
    return {"job_id": jid, "job": job if isinstance(job, dict) else None}


@router.api_route("/projects/{pid}/export/files/{name}", methods=["GET", "HEAD"])
def get_export_file(pid: str, name: str, request: Request, download: int = 0):
    return export_file(project_dir(request, pid), name, request.headers.get("range"), head=request.method == "HEAD", download=bool(download))
