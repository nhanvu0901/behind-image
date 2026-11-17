"""FastAPI app factory for the editing page backend (design section 9).

Run: uvicorn bti.editor.app:create_app --factory --host 127.0.0.1 --port 8560
"""
from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from PIL import Image

from bti.engine import limits
from bti.engine.errors import DataError, RenderError
from bti.library.catalogue import LibraryDataError
from bti.script.runner import ScriptJobs
from bti.script.store import DocumentCorrupt, ProjectGone, forget_lock, make_parent, script_lock

from . import audio as audio_mod
from . import frames as frames_mod
from . import jobs as jobs_mod
from . import proposals as prop_mod
from .common import (ApiError, DepthLimitMiddleware, ITEM_RE, REPO_ROOT, STYLE_RE, compute_rev, finite_number,
                     forget_save_lock, id_field, now_iso, quarantine, read_json, safe_join, save_lock as storyboard_lock,
                     segment_ok, storyboard_approval, strip_derived, text_field, valid_pid, write_json_atomic)
from .engine_adapter import ENGINE_LOCK, EngineAdapter
from .media_adapter import LicenceRejected, MediaAdapter

PLACEHOLDER = """<!doctype html><meta charset="utf-8"><title>BTI editor</title>
<body style="font-family:sans-serif;margin:3em"><h1>BTI editor backend is running</h1>
<p>The frontend has not been installed yet (<code>bti/editor/static/index.html</code> is missing).</p>
<p><a href="/api/health">/api/health</a> &middot; <a href="/api/projects">/api/projects</a> &middot;
<a href="/docs">/docs</a></p></body>"""

for _ext, _mt in ((".m4a", "audio/mp4"), (".mp4", "video/mp4"), (".webp", "image/webp"), (".js", "text/javascript")):
    mimetypes.add_type(_mt, _ext)

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_EXT = IMG_EXT
MAX_UPLOAD = 80 * 1024 * 1024


def create_app(projects_root: str | Path | None = None, style_root: str | Path | None = None,
               engine_module: Any = "auto", media_module: Any = "auto",
               static_dir: str | Path | None = None, workers: int = 2) -> FastAPI:
    """`engine_module` / `media_module`: "auto" imports the real facade lazily,
    None forces the stub, a module object is used as given (tests)."""
    root = Path(projects_root or os.environ.get("BTI_PROJECTS_ROOT") or REPO_ROOT / "projects").resolve()
    sroot = Path(style_root or REPO_ROOT / "style").resolve()
    static = Path(static_dir or Path(__file__).parent / "static")
    engine = EngineAdapter(root, sroot, engine_module)
    media = MediaAdapter(root, media_module)
    jobs = jobs_mod.JobManager(workers, root)
    script_jobs = ScriptJobs(projects_root=root)          # one registry, shared by the script router and by delete-project
    rev_cache: dict[str, tuple[tuple, str]] = {}
    readable: dict[str, tuple] = {}                        # pid -> (mtime_ns, size) of a storyboard.json known to load

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jobs.shutdown()

    app = FastAPI(title="BTI editor", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.add_middleware(DepthLimitMiddleware)       # a JSON body nested deeper than 40 levels is 422 before any route sees it
    app.state.engine, app.state.media, app.state.jobs = engine, media, jobs
    app.state.script_jobs = script_jobs
    app.state.projects_root = root

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    @app.exception_handler(DataError)
    async def _data_error(_: Request, e: DataError):
        # the project's own data is unusable (missing or corrupt timing, unknown style...): the page can show the message
        return JSONResponse({"detail": e.message, "data_error": e.what}, status_code=409)

    @app.exception_handler(RenderError)
    async def _render_error(_: Request, e: RenderError):
        # a technique could not draw because of the storyboard's values: the owner can fix them (never a 500)
        return JSONResponse(render_failed_body(e), status_code=422)

    @app.exception_handler(DocumentCorrupt)
    async def _doc_corrupt(_: Request, e: DocumentCorrupt):
        # a file of the project (script document, project.json, a source text, a library file) cannot be read: 409 naming it
        return JSONResponse({"detail": str(e), "data_error": getattr(e, "what", "script")}, status_code=409)

    @app.exception_handler(LibraryDataError)
    async def _library_error(_: Request, e: LibraryDataError):
        return JSONResponse({"detail": str(e), "data_error": "library"}, status_code=409)

    @app.exception_handler(ProjectGone)
    async def _project_gone(_: Request, e: ProjectGone):
        return JSONResponse({"detail": "project not found"}, status_code=404)

    @app.exception_handler(UnicodeEncodeError)
    async def _unicode_error(_: Request, e: UnicodeEncodeError):
        return JSONResponse({"detail": "the text contains a character that cannot be stored (a lone surrogate); "
                                       "remove it and send again"}, status_code=422)

    @app.exception_handler(Exception)
    async def _any_error(request: Request, e: Exception):
        m = re.match(r"^/api/projects/([^/]+)", request.url.path)
        if isinstance(e, (FileNotFoundError, NotADirectoryError)) and m and not (root / m.group(1)).is_dir():
            return JSONResponse({"detail": "project not found"}, status_code=404)     # deleted while this request was running
        # last line of defence: a bug is still answered as JSON, without the Python message; the traceback goes to the log
        logging.getLogger("bti.editor").exception("unhandled error", exc_info=e)
        return JSONResponse({"detail": f"internal error ({type(e).__name__}); this is a bug of the server, not of your input"},
                            status_code=500)

    # ------------------------------------------------------------ helpers
    def pdir(pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if not d.is_dir() or d.is_symlink() and not d.resolve().is_relative_to(root):
            raise ApiError(404, "project not found")
        return d

    def slock(pid: str):
        """The storyboard lock of project `pid` (lock order: see bti/script/store.py). The project must exist (404)."""
        return storyboard_lock(pdir(pid))

    def render_failed_body(e: RenderError) -> dict:
        return {"detail": e.message, "code": "render_failed", "shot": e.shot, "overlay": e.overlay, "technique": e.technique}

    def history_files(d: Path) -> list[Path]:
        h = d / "history"
        if not h.is_dir() or h.is_symlink():
            return []
        fs = [f for f in h.glob("*.json") if f.is_file() and not f.is_symlink()]
        return sorted(fs, key=lambda f: (f.stat().st_mtime_ns, f.name), reverse=True)

    def newest_valid_history(d: Path) -> str | None:
        for f in history_files(d):
            try:
                if isinstance(read_json(f), dict):
                    return f.name
            except (OSError, ValueError):
                continue
        return None

    def check_readable(pid: str, d: Path) -> None:
        """storyboard.json must load as an object, else a 409 that names the problem and the newest good copy in history/.
        (The answer is cached per file version, so the check costs one stat for a healthy file.)"""
        f = d / "storyboard.json"
        try:
            st = f.stat()
        except OSError:
            raise ApiError(404, "storyboard not found")
        sig = (st.st_mtime_ns, st.st_size)
        if readable.get(pid) == sig:
            return
        try:
            doc = read_json(f)
            problem = None if isinstance(doc, dict) else "the top level must be an object"
        except (OSError, ValueError) as e:
            problem = str(e)[:120]
        if problem:
            readable.pop(pid, None)
            engine.forget(pid)
            best = newest_valid_history(d)
            raise ApiError(409, "storyboard.json is corrupt: " + problem
                           + (f"; the newest good copy is history/{best} (POST .../storyboard/restore brings it back)" if best
                              else "; there is no good copy in history/"),
                           corrupt=True, restore_from=best)
        readable[pid] = sig

    def project(pid: str):
        d = pdir(pid)
        if not (d / "storyboard.json").is_file():
            raise ApiError(404, "storyboard not found")
        check_readable(pid, d)
        return engine.project(pid)

    def saved_storyboard(pid: str) -> dict:
        p = project(pid)
        with ENGINE_LOCK:
            return p.storyboard()

    def current_rev(pid: str) -> str:
        f = pdir(pid) / "storyboard.json"
        try:
            st = f.stat()
        except OSError:
            raise ApiError(404, "storyboard not found")
        sig = (st.st_mtime_ns, st.st_size)
        hit = rev_cache.get(pid)
        if hit and hit[0] == sig:
            return hit[1]
        rev = compute_rev(saved_storyboard(pid))
        rev_cache[pid] = (sig, rev)
        return rev

    def render_key(pid: str) -> str:
        """Key of everything a still depends on: the storyboard, the timing file, the style files and the media files it uses.
        The cached JPEGs and the ETag use it, so none of them can outlive a change of any of those."""
        d = pdir(pid)
        sb = saved_storyboard(pid)

        def sig(path: Path | None) -> str:
            try:
                st = path.stat() if path is not None else None
            except OSError:
                st = None
            return f"{st.st_mtime_ns}:{st.st_size}" if st else "-"
        parts = [current_rev(pid)]
        rel = sb.get("timing") or "timing.json"
        tf = None
        if isinstance(rel, str):
            try:
                tf = safe_join(d, rel)
            except ApiError:
                tf = None
        parts.append("timing=" + sig(tf))
        style = sb.get("style", "gae")
        sd = sroot / style if isinstance(style, str) and STYLE_RE.fullmatch(style) else None
        if sd is not None:
            parts.append("style=" + ",".join(sig(sd / n) for n in ("style.json", "techniques.json")))
            parts.append("patches=" + ",".join(sig(f) for f in sorted((sd / "patches").glob("*.json"))) if (sd / "patches").is_dir() else "patches=-")
        for k, a in sorted((sb.get("assets") or {}).items()) if isinstance(sb.get("assets"), dict) else []:
            f = None
            if isinstance(a, dict) and isinstance(a.get("file"), str):
                try:
                    f = safe_join(d, a["file"])
                except ApiError:
                    f = None
            parts.append(f"{k}={sig(f)}")
        return hashlib.sha1("|".join(parts).encode()).hexdigest()

    def state(pid: str) -> dict:
        p = project(pid)
        with ENGINE_LOCK:
            sb = p.storyboard()
            resolved = p.resolve()
            issues = p.validate()
            timing = p.timing()
        return {"storyboard": resolved, "timing": timing, "issues": issues, "rev": compute_rev(sb),
                "render_key": render_key(pid)}

    def save_result(pid: str, p) -> dict:
        with ENGINE_LOCK:
            sb = p.storyboard()
            resolved = p.resolve()
            issues = p.validate()
        rev = compute_rev(sb)
        rev_cache.pop(pid, None)
        return {"rev": rev, "storyboard": resolved, "issues": issues, "render_key": render_key(pid)}

    def commit(pid: str, p, doc: dict) -> dict:
        """validate, save through the engine, return PUT-shaped result. Caller holds the project's storyboard lock."""
        doc = strip_derived(doc)
        with ENGINE_LOCK:
            issues = p.validate(doc)
        errors = [i for i in issues if i["level"] == "error"]
        if errors:
            raise ApiError(422, "validation failed", issues=issues)
        try:
            with ENGINE_LOCK:
                p.save(doc)
        except (ApiError, DataError):
            raise
        except Exception as e:      # noqa: BLE001 - the engine's ValidationError carries the issues; nothing was written
            if isinstance(e, (ValueError, TypeError, KeyError)) or hasattr(e, "issues"):
                raise ApiError(422, f"save refused: {e}", issues=getattr(e, "issues", []) or [])
            raise
        readable.pop(pid, None)
        return save_result(pid, p)

    def audio_path(pid: str, sb: dict) -> Path | None:
        rel = sb.get("audio")
        if not isinstance(rel, str) or not rel:
            return None
        try:
            f = safe_join(pdir(pid), rel)
        except ApiError:
            return None
        return f if f.is_file() else None

    def need_dict(body: Any, key: str) -> dict:
        v = body.get(key) if isinstance(body, dict) else None
        if not isinstance(v, dict):
            raise ApiError(422, f"{key} (object) is required")
        return v

    def with_thumb(pid: str, asset: dict) -> dict:
        out = dict(asset)
        f = asset.get("file")
        out["thumb_url"] = f"/api/projects/{pid}/files/{f}?w=320" if isinstance(f, str) and f else None
        return out

    # ------------------------------------------------------------ health, style
    @app.get("/api/health")
    def health():
        return {"ok": True, **engine.health(), **media.health()}

    @app.get("/api/styles/{style}")
    def get_style(style: str):
        if not STYLE_RE.fullmatch(style):
            raise ApiError(404, "style not found")
        out = engine.load_style(style)  # the engine returns the MERGED registry (techniques.json plus patches)
        techs = fill_previews(out["techniques"], sroot / style / "previews")
        return {"style": out.get("style", {}), "techniques": techs, "intents": out.get("intents", [])}

    @app.get("/style/{style}/previews/{file}")
    def style_preview(style: str, file: str):
        if not STYLE_RE.fullmatch(style):
            raise ApiError(404, "not found")
        f = safe_join(sroot / style / "previews", file)
        if not f.is_file():
            raise ApiError(404, "not found")
        return FileResponse(f)

    # ------------------------------------------------------------ projects
    @app.get("/api/projects")
    def list_projects():
        """One row per project folder. A folder whose data cannot be read is a row `{id, title: <folder>, data_error, stage: null}`
        (the page shows it as damaged); one damaged project never breaks the list for the others."""
        out = []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if not (valid_pid(d.name) and d.is_dir()):
                    continue
                try:
                    row = project_row(d)
                except (DocumentCorrupt, LibraryDataError) as e:
                    row = damaged_row(d, str(e))
                except Exception as e:      # noqa: BLE001 - whatever is wrong inside one folder, the others are still listed
                    row = damaged_row(d, f"the project data cannot be read ({type(e).__name__})")
                if row is not None:
                    out.append(row)
        return out

    def damaged_row(d: Path, why: str) -> dict:
        try:
            ts = _iso(d.stat().st_mtime)
        except OSError:
            ts = None
        return {"id": d.name, "title": d.name, "duration": None, "updated_at": ts, "stage": None,
                "has_storyboard": (d / "storyboard.json").is_file(), "data_error": why[:300]}

    def project_row(d: Path) -> dict | None:
        from .library_api import stage_of
        from .pipeline_api import project_meta
        f = d / "storyboard.json"
        has_pj = (d / "project.json").is_file()
        if not (f.is_file() or has_pj):
            return None
        pj = project_meta(d, strict=True)             # DocumentCorrupt (naming project.json) when it is not an object
        extra = {"stage": stage_of(d), "has_storyboard": f.is_file()}
        if not f.is_file():  # selected from a book, no storyboard yet
            return {"id": d.name, "title": pj.get("title") or d.name, "duration": None,
                    "updated_at": _iso((d / "project.json").stat().st_mtime), **extra,
                    "artist": pj.get("artist"), "year": pj.get("year"),
                    "artwork_key": pj.get("artwork_key"), "sources": pj.get("sources") if isinstance(pj.get("sources"), list) else []}
        try:
            sb = read_json(f)
            if not isinstance(sb, dict):
                raise ValueError("not an object")
            dur = None
            try:
                tf = sb.get("timing") if isinstance(sb.get("timing"), str) and sb.get("timing") else "timing.json"
                dur = read_json(safe_join(d, tf)).get("duration")
            except Exception:
                pass
            if dur is None:
                dur = (sb.get("end") or {}).get("t") if isinstance(sb.get("end"), dict) else None
            title = sb.get("title") if isinstance(sb.get("title"), str) and sb.get("title") else d.name
            return {"id": d.name, "title": title, "duration": dur, "updated_at": _iso(f.stat().st_mtime), **extra}
        except Exception:
            return {"id": d.name, "title": d.name, "duration": None, "updated_at": _iso(f.stat().st_mtime),
                    "error": "storyboard unreadable", **extra}

    @app.get("/api/projects/{pid}")
    def get_project(pid: str):
        return state(pid)

    @app.put("/api/projects/{pid}/storyboard")
    def put_storyboard(pid: str, body: dict = Body(...)):
        sb_new = need_dict(body, "storyboard")
        base = body.get("base_rev")
        if not isinstance(base, str) or not base:
            raise ApiError(422, "base_rev (string) is required")
        p = project(pid)
        with slock(pid):
            saved = saved_storyboard(pid)               # also re-checks, under the lock, that the project still exists
            cur = compute_rev(saved)
            if base != cur:
                raise ApiError(409, "base_rev does not match the saved revision", rev=cur)
            doc = strip_derived(sb_new)
            doc["approvals"] = saved.get("approvals") or {"storyboard": None}  # server-owned
            return commit(pid, p, doc)

    @app.post("/api/projects/{pid}/storyboard/restore")
    def restore_storyboard(pid: str, body: dict = Body(default={})):
        """Bring back a good copy from history/ when storyboard.json is unreadable (or missing). The damaged file is moved
        aside (storyboard.json.corrupt-<time>), never deleted. Body: {file?} (a name in history/; default: the newest good one)."""
        d = pdir(pid)
        with slock(pid):
            d = pdir(pid)                               # still there, now that we hold the lock?
            f = d / "storyboard.json"
            if f.is_file():
                try:
                    healthy = isinstance(read_json(f), dict)
                except (OSError, ValueError):
                    healthy = False
                if healthy:
                    raise ApiError(409, "storyboard.json is readable; there is nothing to restore")
            name = body.get("file")
            if name is None:
                name = newest_valid_history(d)
                if name is None:
                    raise ApiError(404, "there is no good copy in history/")
            elif not isinstance(name, str) or name not in {h.name for h in history_files(d)}:
                raise ApiError(404, "no such file in history/")
            try:
                doc = read_json(d / "history" / name)
            except (OSError, ValueError):
                doc = None
            if not isinstance(doc, dict):
                raise ApiError(422, f"history/{name} is not a readable storyboard")
            moved = quarantine(f) if f.exists() else None
            write_json_atomic(f, doc)
            readable.pop(pid, None)
            rev_cache.pop(pid, None)
            engine.forget(pid)
        return {"restored_from": name, "quarantined": moved.name if moved else None, "rev": compute_rev(doc)}

    @app.post("/api/projects/{pid}/validate")
    def post_validate(pid: str, body: dict = Body(...)):
        sb = need_dict(body, "storyboard")
        p = project(pid)
        with ENGINE_LOCK:
            return {"issues": p.validate(strip_derived(sb))}

    @app.post("/api/projects/{pid}/defaults")
    def post_defaults(pid: str, body: dict = Body(...)):
        tech = body.get("technique")
        if not isinstance(tech, str) or not tech:
            raise ApiError(422, "technique is required")
        ctx = body.get("context") or {}
        if not isinstance(ctx, dict):
            raise ApiError(422, "context must be an object")
        p = project(pid)
        saved_assets = saved_storyboard(pid).get("assets")
        slots = default_slots(engine.load_style(_style_of(saved_storyboard(pid))).get("techniques") or [], tech, ctx,
                              saved_assets if isinstance(saved_assets, dict) else {})
        ectx = engine_context(ctx)
        try:
            with ENGINE_LOCK:
                params = p.default_params(tech, ectx)
        except (ApiError, DataError):
            raise
        except KeyError:
            raise ApiError(422, f"unknown technique {tech!r}")
        return {"params": params, "slots": slots}

    @app.post("/api/projects/{pid}/approve")
    def approve(pid: str, body: dict = Body(...)):
        rev = body.get("rev")
        p = project(pid)
        with slock(pid):
            saved = saved_storyboard(pid)
            cur = compute_rev(saved)
            if rev != cur:
                raise ApiError(409, "rev is not the current revision", rev=cur)
            with ENGINE_LOCK:
                issues = p.validate(saved)
            if any(i["level"] == "error" for i in issues):
                raise ApiError(422, "cannot approve while there are errors", issues=issues)
            todo = [i for i in issues if i.get("code") == "incomplete"]
            if todo:
                raise ApiError(422, "cannot approve while items are incomplete: "
                               + "; ".join(f"{i['path']}: {i['message']}" for i in todo[:8])
                               + (f" (and {len(todo) - 8} more)" if len(todo) > 8 else ""), issues=issues, incomplete=True)
            # whatever validate accepts the engine must be able to draw: draw one small frame in every shot and overlay
            with ENGINE_LOCK:
                drawn = p.draw_check(saved)
            bad = [i for i in drawn if i.get("code") == "undrawable"]
            if bad:
                raise ApiError(422, "cannot approve while items cannot be drawn: "
                               + "; ".join(f"{i['path']}: {i['message']}" for i in bad[:8])
                               + (f" (and {len(bad) - 8} more)" if len(bad) > 8 else ""),
                               issues=issues + bad, undrawable=True, code="undrawable")
            doc = strip_derived(saved)
            doc["approvals"] = {**(doc.get("approvals") or {}), "storyboard": {"rev": cur, "approved_at": now_iso()}}
            commit(pid, p, doc)
            return {"approvals": doc["approvals"]}

    # ------------------------------------------------------------ frames, audio, previews
    JPEG_HEADERS = {"Content-Type": "image/jpeg"}

    def guarded(p, doc: dict | None, fn):
        """Run a render. When it fails and the document has validation errors, the answer is a 422 that carries those issues
        (the page debounces drafts that are half edited: that is not a server bug); otherwise the 500 stays (JSON)."""
        try:
            return fn()
        except RenderError as e:        # a technique failed on the storyboard's values: 422 render_failed, with the issues if any
            with ENGINE_LOCK:
                issues = p.validate(doc) if doc is not None else p.validate()
            errs = [i for i in issues if i["level"] == "error"]
            body = render_failed_body(e)
            body.pop("detail")
            raise ApiError(422, e.message, **body, **({"issues": issues} if errs else {}))
        except ApiError as e:
            if e.status == 500 and e.extra.get("render_failed"):
                with ENGINE_LOCK:
                    issues = p.validate(doc) if doc is not None else p.validate()
                errs = [i for i in issues if i["level"] == "error"]
                if errs:
                    raise ApiError(422, "this storyboard cannot be drawn: " + f"{errs[0]['path']}: {errs[0]['message']}",
                                   issues=issues)
            raise

    def etag_response(request: Request, data: bytes, key: str, rev: str | None, extra: str = "") -> Response:
        """`rev` is what the page put in the URL. Only the RENDER key (`render_key` of GET /api/projects/{pid}: storyboard +
        timing + style + media) makes the URL immutable; the storyboard revision alone cannot, because timing.json can change
        behind it. Any other value is revalidated by ETag."""
        tag = f'"{key[:16]}{extra}"'
        cc = "private, max-age=31536000, immutable" if rev == key else "private, no-cache"
        headers = {"Cache-Control": cc, "ETag": tag}
        if request.headers.get("if-none-match") == tag:
            return Response(status_code=304, headers=headers)
        return Response(data, media_type="image/jpeg", headers=headers)

    @app.get("/api/projects/{pid}/frame")
    def get_frame(pid: str, request: Request, t: float = Query(...), width: int = Query(960), rev: str | None = Query(None)):
        t = frames_mod.clean_t(t)
        width = frames_mod.clean_width(width)
        p = project(pid)
        key = render_key(pid)
        data = guarded(p, None, lambda: frames_mod.cached_jpeg(p, pdir(pid) / "cache" / "frames", key, t, width))
        return etag_response(request, data, key, rev)

    @app.post("/api/projects/{pid}/frame")
    def post_frame(pid: str, body: dict = Body(...)):
        t = frames_mod.clean_t(body.get("t"))
        width = frames_mod.clean_width(body.get("width"))
        draft = strip_derived(need_dict(body, "storyboard"))
        p = project(pid)
        data = guarded(p, draft, lambda: frames_mod.render_jpeg(p, t, width, draft=draft))
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/projects/{pid}/thumb/{shot_id}")
    def get_thumb(pid: str, shot_id: str, request: Request, rev: str | None = Query(None)):
        if not ITEM_RE.fullmatch(shot_id):
            raise ApiError(404, "shot not found")
        p = project(pid)
        with ENGINE_LOCK:
            res = p.resolve()
        shot = next((s for s in res.get("shots") or [] if s.get("id") == shot_id), None)
        if shot is None or shot.get("_t0") is None or shot.get("_t1") is None:
            raise ApiError(404, "shot not found")
        t = shot["_t0"] + 0.4 * (shot["_t1"] - shot["_t0"])
        key = render_key(pid)
        data = guarded(p, None, lambda: frames_mod.cached_jpeg(p, pdir(pid) / "cache" / "frames", key, t, 320, tag="th"))
        return etag_response(request, data, key, rev, extra=f"-{shot_id}-{int(round(t * 1000))}")

    @app.get("/api/projects/{pid}/waveform")
    def get_waveform(pid: str, bins: int = Query(4000)):
        if not 100 <= bins <= 20000:
            raise ApiError(422, "bins must be between 100 and 20000")
        sb = saved_storyboard(pid)
        a = audio_path(pid, sb)
        if a is None:
            raise ApiError(404, "no audio file")
        return audio_mod.waveform(a, pdir(pid) / "cache", bins)

    @app.get("/api/projects/{pid}/audio")
    def get_audio(pid: str):
        sb = saved_storyboard(pid)
        a = audio_path(pid, sb)
        if a is None:
            raise ApiError(404, "no audio file")
        return FileResponse(a, media_type=mimetypes.guess_type(a.name)[0] or "application/octet-stream")

    MAX_PREVIEW_S = limits.PREVIEW_MAX_SECONDS
    MAX_PREVIEW_FRAMES = limits.PREVIEW_MAX_FRAMES

    def int_field(body: dict, key: str, default: int, lo: int, hi: int) -> int:
        return int(finite_number(body.get(key), key, lo, hi, integer=True, default=default))

    @app.post("/api/projects/{pid}/preview")
    def post_preview(pid: str, body: dict = Body(...)):
        t0 = float(frames_mod.clean_t(body.get("t0"), "t0"))
        t1 = float(frames_mod.clean_t(body.get("t1"), "t1"))
        if not t1 > t0:
            raise ApiError(422, "t1 must be greater than t0")
        if t1 - t0 > MAX_PREVIEW_S:
            raise ApiError(422, f"a preview is limited to {int(MAX_PREVIEW_S)} seconds")
        width = int_field(body, "width", 640, limits.PREVIEW_WIDTH_MIN, limits.PREVIEW_WIDTH_MAX)
        fps = int_field(body, "fps", 15, limits.FPS_MIN, limits.FPS_MAX)
        if (t1 - t0) * fps > MAX_PREVIEW_FRAMES:
            raise ApiError(422, f"a preview is limited to {MAX_PREVIEW_FRAMES} frames (seconds x fps); shorten it or lower fps")
        draft = body.get("storyboard")
        if draft is not None and not isinstance(draft, dict):
            raise ApiError(422, "storyboard must be an object")
        p = project(pid)
        d = pdir(pid)
        doc = strip_derived(draft) if draft else saved_storyboard(pid)
        with ENGINE_LOCK:
            issues = p.validate(doc)
        if any(i["level"] == "error" for i in issues):
            raise ApiError(422, "this storyboard cannot be rendered: fix its errors first", issues=issues)
        a = audio_path(pid, doc)
        draft = strip_derived(draft) if draft else None
        pp, plock = engine.preview_project(pid)       # a separate engine instance: the render never holds ENGINE_LOCK
        jid = jobs.submit(pid, lambda progress: jobs_mod.render_preview(pp, d, a, t0, t1, width, fps, draft, pid, progress,
                                                                         plock))
        return {"job_id": jid}

    from .script_api import make_router as _script_router; app.include_router(_script_router(root, jobs=script_jobs))  # script stage; also serves /api/jobs/{id} for both job kinds

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        j = jobs.get(job_id)
        if j is None:
            raise ApiError(404, "job not found")
        return j

    @app.get("/api/projects/{pid}/files/{path:path}")
    def get_file(pid: str, path: str, w: int | None = Query(None)):
        f = safe_join(pdir(pid), path)
        if not f.is_file():
            raise ApiError(404, "not found")
        if w is not None:
            return _thumb_response(pdir(pid), f, w)
        return FileResponse(f, media_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")

    # ------------------------------------------------------------ assets, media
    def confirm_alive(d: Path) -> None:
        """After a media import or upload (no lock was held while it ran): take the script and storyboard locks, in the usual
        order, and check the project still exists. If a delete won the race the media facade (`require_root`) could not
        re-create anything, what it had written went away with the folder; nothing is left under the old slug and the
        answer is 404. The lock objects of the deleted project are dropped again."""
        with script_lock(d), storyboard_lock(d):
            alive = d.is_dir()
        if not alive:
            forget_lock(d)
            forget_save_lock(d)
            raise ApiError(404, "project not found")

    @app.get("/api/projects/{pid}/assets")
    def get_assets(pid: str):
        sb = saved_storyboard(pid)
        return {k: with_thumb(pid, a) for k, a in (sb.get("assets") or {}).items() if isinstance(a, dict)}

    @app.put("/api/projects/{pid}/assets/{key}/regions")
    def put_regions(pid: str, key: str, body: dict = Body(...)):
        regions = body.get("regions")
        if not isinstance(regions, dict):
            raise ApiError(422, "regions (object) is required")
        for name, r in regions.items():
            if not (isinstance(name, str) and name and isinstance(r, dict)
                    and all(isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool) for k in ("x", "y"))):
                raise ApiError(422, f"region {name!r} needs numeric x and y")
        p = project(pid)
        with slock(pid):
            doc = strip_derived(saved_storyboard(pid))
            if key not in (doc.get("assets") or {}):
                raise ApiError(404, "asset not found")
            doc["assets"][key]["regions"] = regions
            out = commit(pid, p, doc)
        return {"key": key, "regions": regions, "rev": out["rev"], "issues": out["issues"]}

    @app.get("/api/media/search")
    def media_search(q: str = "", source: str = "commons", kind: str = "image", limit: int = 24):
        return media.search(q, source, kind, max(1, min(100, limit)))

    @app.get("/api/media/stub-thumb/{name}")
    def stub_thumb(name: str):
        if media.mode != "stub" or not ITEM_RE.fullmatch(name):
            raise ApiError(404, "not found")
        return Response(media.stub_thumb(name), media_type="image/jpeg")

    @app.post("/api/projects/{pid}/assets/import")
    def assets_import(pid: str, body: dict = Body(...)):
        source, sid = body.get("source"), body.get("source_id")
        if not isinstance(source, str) or not isinstance(sid, str) or not source or not sid:
            raise ApiError(422, "source and source_id are required")
        d = pdir(pid)
        try:
            out = media.import_candidate(d, source, sid)
        except LicenceRejected as e:
            raise ApiError(422, str(e), reason=str(e))
        confirm_alive(d)              # the network work is done: only now take the locks and make sure the project still exists
        return {"asset_key": out["asset_key"], "asset": with_thumb(pid, out["asset"])}

    @app.post("/api/projects/{pid}/assets/upload")
    def assets_upload(pid: str, file: UploadFile = File(...), title: str = Form(""), artist: str = Form(""),
                      year: str = Form(""), licence: str = Form(""), source_url: str = Form(""),
                      author: str = Form("")):
        d = pdir(pid)
        ext = Path(file.filename or "").suffix.lower()
        if ext not in UPLOAD_EXT:
            raise ApiError(422, f"unsupported file type {ext!r}; use {sorted(UPLOAD_EXT)}")
        tmpdir = d / "cache" / "uploads"
        make_parent(tmpdir / "x", 2)
        fd, tmp = tempfile.mkstemp(suffix=ext, dir=str(tmpdir))
        try:
            size = 0
            with os.fdopen(fd, "wb") as out:
                while chunk := file.file.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise ApiError(413, "file too large")
                    out.write(chunk)
            from bti.media.imageinfo import readable_problem
            problem = readable_problem(Path(tmp))
            if problem:
                raise ApiError(422, problem)
            title = title.strip() or title_from_filename(file.filename)       # never the name of our own temp file
            meta = {"title": title, "artist": artist, "year": year, "licence": licence, "source_url": source_url,
                    "author": author, "original_name": title_from_filename(file.filename)}
            try:
                res = media.add_upload(d, Path(tmp), meta)
            except LicenceRejected as e:
                raise ApiError(422, str(e), reason=str(e))
            confirm_alive(d)
        finally:
            Path(tmp).unlink(missing_ok=True)
        return {"asset_key": res["asset_key"], "asset": with_thumb(pid, res["asset"])}

    # ------------------------------------------------------------ proposals
    def load_proposal(pid: str, prop_id: str) -> dict:
        if not ITEM_RE.fullmatch(prop_id):
            raise ApiError(404, "proposal not found")
        f = pdir(pid) / "proposals" / f"{prop_id}.json"
        if not f.is_file():
            raise ApiError(404, "proposal not found")
        try:
            doc = read_json(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            quarantine(f)
            raise ApiError(404, "proposal file was corrupt and has been quarantined")
        if not isinstance(doc, dict) or not isinstance(doc.get("storyboard"), dict):
            raise ApiError(422, "proposal has no storyboard object")
        problem = prop_mod.shape_problem(doc["storyboard"])
        if problem:
            raise ApiError(422, f"proposal {prop_id!r} is malformed: {problem}")
        doc["id"] = prop_id
        return doc

    @app.get("/api/projects/{pid}/proposals")
    def list_proposals(pid: str):
        """`{items: [...], skipped: [{file, reason}]}`: a file that cannot be read never breaks the list and never vanishes
        silently; it is named here with the reason."""
        d = pdir(pid) / "proposals"
        saved = saved_storyboard(pid)
        out, skipped = [], []
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                if not ITEM_RE.fullmatch(f.stem):
                    skipped.append({"file": f.name, "reason": "the file name is not a valid proposal id"})
                    continue
                try:
                    doc = load_proposal(pid, f.stem)
                    n = len(prop_mod.diff(saved, doc["storyboard"]))
                except ApiError as e:
                    skipped.append({"file": f.name, "reason": str(e.detail)[:200]})
                    continue
                except Exception as e:      # noqa: BLE001 - a shape the checks did not foresee: skip it, say so
                    skipped.append({"file": f.name, "reason": f"unreadable ({type(e).__name__})"})
                    continue
                out.append({"id": doc["id"], "created_at": doc.get("created_at"), "author": doc.get("author"),
                            "summary": doc.get("summary"), "n_changes": n})
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"items": out, "skipped": skipped}

    @app.get("/api/projects/{pid}/proposals/{prop_id}")
    def get_proposal(pid: str, prop_id: str):
        doc = load_proposal(pid, prop_id)
        saved = saved_storyboard(pid)
        changes = prop_mod.diff(saved, doc["storyboard"])
        return {"proposal": {**doc, "stale": doc.get("base_rev") != compute_rev(saved)}, "changes": changes}

    @app.post("/api/projects/{pid}/proposals/{prop_id}/apply")
    def apply_proposal(pid: str, prop_id: str, body: dict = Body(...)):
        doc = load_proposal(pid, prop_id)
        p = project(pid)
        with slock(pid):
            saved = saved_storyboard(pid)
            new, applied, skipped = prop_mod.apply(saved, doc["storyboard"], body.get("accept"))
            if not applied:
                out = save_result(pid, p)
            else:
                new["approvals"] = saved.get("approvals") or {"storyboard": None}
                out = commit(pid, p, new)
            return {**out, "applied": applied, "skipped_locked": skipped}

    def forget_project(pid: str) -> None:
        engine.forget(pid)
        rev_cache.pop(pid, None)
        readable.pop(pid, None)

    from .library_api import make_router as _library_router
    app.include_router(_library_router(root))
    from .pipeline_api import make_router as _pipeline_router
    app.include_router(_pipeline_router(root, script_jobs=script_jobs, preview_jobs=jobs, on_delete=forget_project))  # steps of a project (stepper, home) and delete-project

    # ------------------------------------------------------------ static (dynamic, so a late frontend works)
    @app.get("/{path:path}", include_in_schema=False)
    def static_files(path: str):
        if path.startswith("api/"):
            raise ApiError(404, "not found")
        if path == "" or path.endswith("/"):
            path += "index.html"
        try:
            f = safe_join(static, path)
        except ApiError:
            raise
        if f.is_file():
            return FileResponse(f, headers={"Cache-Control": "no-cache"})
        if path == "index.html":
            return HTMLResponse(PLACEHOLDER)
        raise ApiError(404, "not found")

    return app


def fill_previews(techniques: list, pdir: Path) -> list:
    """An entry whose `preview` is null gets previews/<ID>.mp4 and .jpg when those files exist (registry is read-only here)."""
    out = []
    for t in techniques:
        pv = t.get("preview")
        if not (isinstance(pv, dict) and (pv.get("clip") or pv.get("thumb"))):
            clip, thumb = pdir / f"{t.get('id')}.mp4", pdir / f"{t.get('id')}.jpg"
            if clip.is_file() or thumb.is_file():
                t = {**t, "preview": {"clip": f"previews/{clip.name}" if clip.is_file() else None,
                                      "thumb": f"previews/{thumb.name}" if thumb.is_file() else None}}
        out.append(t)
    return out


def title_from_filename(name: str | None, limit: int = 120) -> str:
    """The title of an upload that came without one: the stem of the file's own name, cleaned (no folders, no control
    characters, one space between words)."""
    base = re.split(r"[\\/]", name or "")[-1]
    stem = Path(base).stem if base else ""
    stem = re.sub(r"\s+", " ", "".join(ch for ch in stem if ch.isprintable())).strip()
    return stem[:limit] or "upload"


def _style_of(sb) -> str:
    st = sb.get("style", "gae") if isinstance(sb, dict) else "gae"
    return st if isinstance(st, str) else "gae"


def _pos_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 < v < 1e9


def default_slots(techniques: list, tech: str, ctx: dict, saved_assets: dict) -> dict:
    """Slots `/defaults` proposes for technique `tech`: {slot name: {"asset": key}}.
    An `image` slot may take the context image (the first image asset of the context). A `video` or `mask` slot is filled only
    when the context names, for that very slot, an asset of exactly that kind; otherwise it stays empty and the item is
    incomplete (a warning), never wrongly filled."""
    from bti.engine.storyboard import slot_kind
    spec = next((t for t in techniques if isinstance(t, dict) and t.get("id") == tech), None)
    if spec is None:
        return {}
    c_assets = ctx.get("assets") if isinstance(ctx.get("assets"), dict) else {}
    c_slots = ctx.get("slots") if isinstance(ctx.get("slots"), dict) else {}

    def kind_of(k):
        a = c_assets.get(k) if isinstance(c_assets.get(k), dict) and c_assets[k].get("kind") else saved_assets.get(k)
        return a.get("kind") if isinstance(a, dict) else None

    def key_of(slot):
        v = c_slots.get(slot)
        k = v.get("asset") if isinstance(v, dict) else None
        return k if isinstance(k, str) and k else None
    image_key = next((key_of(n) for n in sorted(c_slots, key=lambda n: (n not in ("image", "left", "background"), n))
                      if key_of(n) and kind_of(key_of(n)) in ("image", None)), None)
    out, first_image = {}, True
    for sd in spec.get("slots") or []:
        want = slot_kind(sd)
        if want is None:
            continue
        named = key_of(sd["name"])
        if named and kind_of(named) == want:
            out[sd["name"]] = {"asset": named}
        elif want == "image" and first_image and image_key:
            out[sd["name"]] = {"asset": image_key}
        if want == "image":
            first_image = False
    return out


def engine_context(ctx: dict) -> dict:
    """Translate the page's /defaults context (item, shot_id, slots, assets{key:{width,height,regions,...}}, canvas, camera)
    into what Project.default_params understands: `asset`, `asset_right`, `shot_id`, `camera`, `region`, `text`..."""
    out = {k: v for k, v in ctx.items() if k not in ("item", "slots", "assets", "canvas", "duration", "overlay_id")}
    assets = ctx.get("assets") if isinstance(ctx.get("assets"), dict) else {}
    slots = ctx.get("slots") if isinstance(ctx.get("slots"), dict) else {}
    keys = []
    for name in sorted(slots, key=lambda n: (n not in ("image", "left", "background"), n)):
        v = slots[name]
        k = v.get("asset") if isinstance(v, dict) else None
        if isinstance(k, str) and k not in keys:
            keys.append(k)

    def info(k):
        a = assets.get(k) if isinstance(assets.get(k), dict) else {}
        w, h = a.get("width") or a.get("w"), a.get("height") or a.get("h")
        if not (_pos_num(w) and _pos_num(h)):
            return k  # no usable size in the context (missing, negative, not a number): the engine looks the key up in the saved storyboard
        return {"key": k, "w": w, "h": h, "title": a.get("title"), "artist": a.get("artist"), "year": a.get("year"),
                "regions": a.get("regions") or {}}
    if keys and "asset" not in out:
        out["asset"] = info(keys[0])
        a0 = assets.get(keys[0]) if isinstance(assets.get(keys[0]), dict) else {}
        out.setdefault("title", a0.get("title"))
        ay = ", ".join(x for x in (a0.get("artist"), a0.get("year")) if x)
        if ay:
            out.setdefault("artist_year", ay)
    if len(keys) > 1 and "asset_right" not in out:
        out["asset_right"] = info(keys[1])
    return {k: v for k, v in out.items() if v is not None}


def _iso(ts: float) -> str:
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(ts))


def _thumb_response(pdir_: Path, f: Path, w: int) -> Response:
    if not 16 <= w <= 2048:
        raise ApiError(422, "w must be between 16 and 2048")
    from .common import file_signature
    cache = pdir_ / "cache" / "thumbs"
    make_parent(cache / "x", 2)                # never re-creates a deleted project folder (ProjectGone -> 404)
    out = cache / f"{file_signature(f)}_{w}.jpg"
    if not out.is_file():
        try:
            if f.suffix.lower() in IMG_EXT:
                with Image.open(f) as im:
                    im.draft("RGB", (w * 2, w * 2))
                    im = im.convert("RGB")
                    im.thumbnail((w, w * 4))
                    tmp = out.with_suffix(".tmp.jpg")
                    im.save(tmp, "JPEG", quality=82)
                    tmp.replace(out)
            else:
                tmp = out.with_suffix(".tmp.jpg")
                r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(f), "-frames:v", "1",
                                    "-vf", f"scale={w}:-2", str(tmp)], capture_output=True, timeout=60)
                if r.returncode != 0 or not tmp.is_file():
                    raise ApiError(415, "cannot make a thumbnail of this file")
                tmp.replace(out)
        except ApiError:
            raise
        except Exception:
            raise ApiError(415, "cannot make a thumbnail of this file")
    return FileResponse(out, media_type="image/jpeg")
