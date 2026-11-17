"""The three routes of the long-job runner. Registered once by the app (`app.include_router(router)`)."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .manager import JOB_ID_RE, KIND_RE, PID_RE, LongJobManager, manager as default_manager


def _err(status: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse({"detail": detail, "code": code}, status_code=status)


def make_router(mgr: LongJobManager) -> APIRouter:
    r = APIRouter(prefix="/api")

    @r.get("/longjobs/{job_id}")
    def get_job(job_id: str):
        rec = mgr.get(job_id) if JOB_ID_RE.fullmatch(job_id) else None
        if rec is None:
            return _err(404, "Không tìm thấy việc này.", "longjob_not_found")
        return rec

    @r.post("/longjobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        rec = mgr.get(job_id) if JOB_ID_RE.fullmatch(job_id) else None
        if rec is None:
            return _err(404, "Không tìm thấy việc này.", "longjob_not_found")
        mgr.cancel(job_id)          # False for a job that already ended: nothing to do, the record below says so
        return mgr.get(job_id)

    @r.get("/projects/{pid}/longjobs")
    def project_jobs(pid: str, kind: str | None = None):
        if not PID_RE.fullmatch(pid):
            return _err(404, "Không tìm thấy dự án.", "project_not_found")
        if kind is not None and not KIND_RE.fullmatch(kind):
            return _err(422, "Loại việc không hợp lệ.", "longjob_bad_kind")
        if mgr._project_dir(pid) is None:
            return _err(404, "Không tìm thấy dự án.", "project_not_found")
        return {"items": mgr.for_project(pid, kind=kind)}

    return r


router = make_router(default_manager)
