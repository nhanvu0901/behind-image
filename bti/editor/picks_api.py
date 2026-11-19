"""HTTP API of step 4, the picks (design section 6). Mounted by app.py with `app.include_router(router)`.

`router` finds the projects folder in `app.state.projects_root`, and an optional suggestion provider in
`app.state.picks_provider` (tests set a fake one; the running app leaves it unset and gets the real, paid one, which still
needs `confirm_paid` from the owner's click). Local tool, bound to 127.0.0.1."""
from __future__ import annotations

import functools
import os
import re
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, Request, UploadFile

from bti.picks import context, service, suggest
from bti.picks.errors import PicksError
from bti.script.store import make_parent

from .auto_api import gate_actor, paid_actor        # c5cli: who may approve a gate, who may start the paid call
from .common import ApiError, valid_pid

router = APIRouter(prefix="/api")
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXT = {".mp4", ".webm", ".mov", ".m4v"}
UPLOAD_EXT = IMG_EXT | VID_EXT
MAX_UPLOAD = 80 * 1024 * 1024


def make_router(projects_root=None):
    """Same router, for the `make_router(root)` style of the other stages (the root is read from the app, not from here)."""
    return router


def _pdir(request: Request, pid: str) -> Path:
    root = Path(request.app.state.projects_root)
    if not valid_pid(pid):
        raise ApiError(404, "project not found", code="project_not_found")
    d = root / pid
    if not d.is_dir() or (d.is_symlink() and not d.resolve().is_relative_to(root.resolve())):
        raise ApiError(404, "project not found", code="project_not_found")
    return d


def _override(request: Request):
    return getattr(request.app.state, "picks_provider", None)


def guard(fn):
    """PicksError becomes `{detail, code, ...}` with its status."""
    @functools.wraps(fn)
    def inner(*a, **k):
        try:
            return fn(*a, **k)
        except PicksError as e:
            raise ApiError(e.status, e.detail, **({"code": e.code or "picks_error"}), **e.extra)
    return inner


def _flag(v) -> bool:
    return v is True or str(v).strip().lower() in ("1", "true", "yes", "on")


def _full(request: Request, pid: str, d: Path, **extra) -> dict:
    return {**service.payload(d, pid, suggest.provider_info(_override(request))), **extra}


def _str(body, key: str, required: bool = False, max_len: int = 400) -> str:
    v = body.get(key) if isinstance(body, dict) else None
    if v is None:
        if required:
            raise ApiError(422, f"{key} (string) is required", code="invalid_field", field=key)
        return ""
    if not isinstance(v, str) or len(v) > max_len:
        raise ApiError(422, f"{key} must be a short string", code="invalid_field", field=key)
    return v


# ------------------------------------------------------------------ the document
@router.get("/projects/{pid}/picks")
@guard
def get_picks(pid: str, request: Request):
    d = _pdir(request, pid)
    return _full(request, pid, d)


@router.put("/projects/{pid}/picks")
@guard
def put_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    service.put(d, body.get("picks"), body.get("base_rev"))
    return _full(request, pid, d)


@router.post("/projects/{pid}/picks/approve")
@guard
def approve_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    actor = gate_actor(d, "picks", body)        # c5cli
    service.approve(d, body.get("rev"), actor)
    return _full(request, pid, d)


# ------------------------------------------------------------------ candidates
@router.post("/projects/{pid}/picks/search")
@guard
def search_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    srcs = body.get("sources")
    if srcs is not None and not (isinstance(srcs, list) and all(isinstance(s, str) for s in srcs)):
        raise ApiError(422, "sources must be a list of strings", code="invalid_field", field="sources")
    beat = body.get("beat")
    if beat is not None and not isinstance(beat, str):
        raise ApiError(422, "beat must be a string", code="invalid_field", field="beat")
    limit = body.get("limit", 18)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ApiError(422, "limit must be an integer", code="invalid_field", field="limit")
    kind = body.get("kind")
    if kind is not None and kind not in ("image", "video", "all"):
        raise ApiError(422, "kind must be 'image', 'video' or 'all'", code="invalid_field", field="kind")
    return service.search(d, _str(body, "query"), beat, srcs, limit, kind=kind or "image")


@router.post("/projects/{pid}/picks/import")
@guard
def import_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    source, sid = _str(body, "source", True, 40), _str(body, "source_id", True, 300)
    out = service.import_asset(d, source, sid, _flag(body.get("as_main")))
    return _full(request, pid, d, asset_key=out["asset_key"], asset=out["asset"])


@router.get("/projects/{pid}/picks/book-images")
@guard
def book_images(pid: str, request: Request):
    return context.book_images(_pdir(request, pid))


@router.post("/projects/{pid}/picks/import-book-image")
@guard
def import_book_image(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    out = service.import_book(d, _str(body, "source_id", True, 80), _flag(body.get("as_main")))
    return _full(request, pid, d, asset_key=out["asset_key"], asset=out["asset"])


def _stem(name: str | None, limit: int = 80) -> str:
    stem = Path((name or "").replace("\\", "/")).stem
    stem = re.sub(r"[\x00-\x1f]", "", stem).replace("_", " ").strip()
    return stem[:limit] or "upload"


@router.post("/projects/{pid}/picks/upload")
@guard
def upload_picks(pid: str, request: Request, file: UploadFile = File(...), title: str = Form(""), artist: str = Form(""),
                 year: str = Form(""), licence: str = Form(""), source_url: str = Form(""), author: str = Form(""),
                 as_main: str = Form("")):
    d = _pdir(request, pid)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in UPLOAD_EXT:
        raise ApiError(422, f"unsupported file type {ext!r}; use {sorted(UPLOAD_EXT)}", code="unsupported_file_type", field="file")
    if ext in VID_EXT and _flag(as_main):
        raise ApiError(422, "a video cannot be set as the main painting", code="video_not_main")
    tmpdir = d / "cache" / "uploads"
    make_parent(tmpdir / "x", 2)
    fd, tmp = tempfile.mkstemp(suffix=ext, dir=str(tmpdir))
    try:
        size = 0
        with os.fdopen(fd, "wb") as out:
            while chunk := file.file.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise ApiError(413, "file too large", code="file_too_large")
                out.write(chunk)
        meta = {"title": title.strip() or _stem(file.filename), "artist": artist, "year": year, "licence": licence,
                "source_url": source_url, "author": author, "original_name": _stem(file.filename)}
        res = service.upload(d, Path(tmp), meta, _flag(as_main))
    finally:
        Path(tmp).unlink(missing_ok=True)
    return _full(request, pid, d, asset_key=res["asset_key"], asset=res["asset"])


# ------------------------------------------------------------------ video search & clip import
@router.post("/projects/{pid}/picks/video-search")
@guard
def video_search_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    beat = body.get("beat")
    if beat is not None and not isinstance(beat, str):
        raise ApiError(422, "beat must be a string", code="invalid_field", field="beat")
    limit = body.get("limit", 6)
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ApiError(422, "limit must be an integer", code="invalid_field", field="limit")
    search_fn = getattr(request.app.state, "video_search_fn", None)
    metadata_fn = getattr(request.app.state, "video_metadata_fn", None)
    return service.video_search(
        d,
        query=_str(body, "query"),
        beat=beat,
        url=_str(body, "url", max_len=600),
        confirm_paid=_flag(body.get("confirm_paid")),
        limit=limit,
        search_fn=search_fn,
        metadata_fn=metadata_fn,
    )


@router.post("/projects/{pid}/picks/import-clip")
@guard
def import_clip_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    url = _str(body, "url", True, 600)
    beat_id = body.get("beat_id")
    if beat_id is not None and not isinstance(beat_id, str):
        raise ApiError(422, "beat_id must be a string", code="invalid_field", field="beat_id")
    role = _str(body, "role", max_len=40) or "video"
    clip_imp = getattr(request.app.state, "clip_importer", None)
    out = service.start_clip_job(
        d,
        pid,
        url,
        body.get("start"),
        body.get("end"),
        title=_str(body, "title", max_len=200),
        beat_id=beat_id,
        role=role,
        note=_str(body, "note", max_len=400),
        clip_importer=clip_imp,
    )
    if _flag(body.get("wait")):
        import bti.longjob as lj
        rec = lj.manager.wait(out["job_id"], timeout=180)
        res = rec.get("result") or {}
        ak = res.get("asset_key")
        ass = res.get("asset")
        return _full(request, pid, d, asset_key=ak, asset=ass, job_id=out["job_id"])
    return out



# ------------------------------------------------------------------ regions
@router.put("/projects/{pid}/picks/assets/{key}/regions")
@guard
def put_regions(pid: str, key: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    base = body.get("base_rev")
    if base is not None and not isinstance(base, str):
        raise ApiError(422, "base_rev must be a string", code="invalid_field", field="base_rev")
    service.set_regions(d, key, body.get("regions"), base)
    return _full(request, pid, d)


# ------------------------------------------------------------------ suggestions (paid, long job)
@router.post("/projects/{pid}/picks/suggest")
@guard
def suggest_picks(pid: str, request: Request, body: dict = Body(...)):
    d = _pdir(request, pid)
    paid_actor(body)        # c5cli: an agent never starts the paid call
    return suggest.start(d, pid, body.get("beats"), confirm_paid=body.get("confirm_paid"), refresh=_flag(body.get("refresh")),
                         override=_override(request))


@router.get("/projects/{pid}/picks/suggestions")
@guard
def get_suggestions(pid: str, request: Request):
    d = _pdir(request, pid)
    return suggest.load_suggestions(d)


# ------------------------------------------------------------------ c2box: the prompt box of step 4 (typed picks operations; see boxroutes.py)
@router.post("/projects/{pid}/picks/edit")
def post_picks_edit(pid: str, request: Request, body: dict = Body(...)):
    from . import boxroutes
    return boxroutes.start_picks_edit(_pdir(request, pid), pid, body)


@router.get("/projects/{pid}/picks/edit/thread")
def get_picks_edit_thread(pid: str, request: Request):
    from . import boxroutes
    return boxroutes.picks_thread(_pdir(request, pid), request.app)


@router.post("/projects/{pid}/picks/edit/{turn_id}/undo")
def undo_picks_edit(pid: str, turn_id: str, request: Request):
    from bti.draft.thread import load_thread
    from . import boxroutes
    d = _pdir(request, pid)
    turn = next((t for t in boxroutes.turns_of(d, load_thread(d), "picks") if t.get("id") == turn_id), None)
    if turn is None:
        raise ApiError(404, "turn not found", code="turn_not_found")
    if not turn.get("batch"):
        raise ApiError(409, "turn was not applied", code="turn_not_applied")
    return boxroutes.undo_batch_turn(d, turn)


@router.delete("/projects/{pid}/picks/edit/thread")
def delete_picks_edit_thread(pid: str, request: Request):
    from bti.draft import run as draft_run
    from bti.longjob import manager as global_mgr
    d = _pdir(request, pid)
    mgr = getattr(request.app.state, "longjob_manager", None) or global_mgr
    try:
        act = mgr.active(pid, "draft") if mgr else None
        running = bool(act and (act.get("meta") or {}).get("mode") == "edit" and (act.get("meta") or {}).get("doc") == "picks")
    except Exception:       # noqa: BLE001
        running = False
    if running:
        raise ApiError(409, "Không thể xóa lịch sử khi đang có yêu cầu sửa đang chạy. Hãy hủy tác vụ trước.", code="edit_running")
    draft_run.clear_thread(d, "picks")
    return {"ok": True}
