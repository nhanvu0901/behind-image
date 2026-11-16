"""FastAPI app factory for the editing page backend (design section 9).

Run: uvicorn bti.editor.app:create_app --factory --host 127.0.0.1 --port 8560
"""
from __future__ import annotations

import json
import mimetypes
import os
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

from . import audio as audio_mod
from . import frames as frames_mod
from . import jobs as jobs_mod
from . import proposals as prop_mod
from .common import (ApiError, ITEM_RE, REPO_ROOT, STYLE_RE, compute_rev, now_iso, quarantine, read_json,
                     safe_join, strip_derived, valid_pid)
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
    jobs = jobs_mod.JobManager(workers)
    save_lock = threading.RLock()
    rev_cache: dict[str, tuple[tuple, str]] = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        jobs.shutdown()

    app = FastAPI(title="BTI editor", docs_url="/docs", redoc_url=None, lifespan=lifespan)
    app.state.engine, app.state.media, app.state.jobs = engine, media, jobs
    app.state.projects_root = root

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, e: ApiError):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    # ------------------------------------------------------------ helpers
    def pdir(pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if not d.is_dir() or d.is_symlink() and not d.resolve().is_relative_to(root):
            raise ApiError(404, "project not found")
        return d

    def project(pid: str):
        d = pdir(pid)
        if not (d / "storyboard.json").is_file():
            raise ApiError(404, "storyboard not found")
        return engine.project(pid)

    def saved_storyboard(pid: str) -> dict:
        p = project(pid)
        try:
            with ENGINE_LOCK:
                return p.storyboard()
        except json.JSONDecodeError as e:
            raise ApiError(500, f"storyboard.json is corrupt: {e}")

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

    def state(pid: str) -> dict:
        p = project(pid)
        with ENGINE_LOCK:
            sb = p.storyboard()
            resolved = p.resolve()
            issues = p.validate()
            timing = p.timing()
        return {"storyboard": resolved, "timing": timing, "issues": issues, "rev": compute_rev(sb)}

    def save_result(pid: str, p) -> dict:
        with ENGINE_LOCK:
            sb = p.storyboard()
            resolved = p.resolve()
            issues = p.validate()
        rev = compute_rev(sb)
        rev_cache.pop(pid, None)
        return {"rev": rev, "storyboard": resolved, "issues": issues}

    def commit(pid: str, p, doc: dict) -> dict:
        """validate, save through the engine, return PUT-shaped result. Caller holds save_lock."""
        doc = strip_derived(doc)
        with ENGINE_LOCK:
            issues = p.validate(doc)
        errors = [i for i in issues if i["level"] == "error"]
        if errors:
            raise ApiError(422, "validation failed", issues=issues)
        try:
            with ENGINE_LOCK:
                p.save(doc)
        except ApiError:
            raise
        except (ValueError, TypeError, KeyError) as e:
            raise ApiError(422, f"save refused: {e}", issues=getattr(e, "issues", []) or [])
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
        from .library_api import stage_of
        out = []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                f = d / "storyboard.json"
                if not (valid_pid(d.name) and d.is_dir() and (f.is_file() or (d / "project.json").is_file())):
                    continue
                extra = {"stage": stage_of(d), "has_storyboard": f.is_file()}
                if not f.is_file():  # selected from a book, no storyboard yet
                    try:
                        pj = read_json(d / "project.json")
                    except Exception:
                        pj = {}
                    out.append({"id": d.name, "title": pj.get("title") or d.name, "duration": None,
                                "updated_at": _iso((d / "project.json").stat().st_mtime), **extra,
                                "artist": pj.get("artist"), "year": pj.get("year"),
                                "artwork_key": pj.get("artwork_key"), "sources": pj.get("sources") or []})
                    continue
                try:
                    sb = read_json(f)
                    dur = None
                    try:
                        dur = read_json(d / (sb.get("timing") or "timing.json")).get("duration")
                    except Exception:
                        pass
                    if dur is None:
                        dur = (sb.get("end") or {}).get("t")
                    out.append({"id": d.name, "title": sb.get("title") or d.name, "duration": dur,
                                "updated_at": _iso(f.stat().st_mtime), **extra})
                except Exception:
                    out.append({"id": d.name, "title": d.name, "duration": None, "updated_at": _iso(f.stat().st_mtime),
                                "error": "storyboard unreadable", **extra})
        return out

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
        with save_lock:
            saved = saved_storyboard(pid)
            cur = compute_rev(saved)
            if base != cur:
                raise ApiError(409, "base_rev does not match the saved revision", rev=cur)
            doc = strip_derived(sb_new)
            doc["approvals"] = saved.get("approvals") or {"storyboard": None}  # server-owned
            return commit(pid, p, doc)

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
        p = project(pid)
        ctx = engine_context(ctx if isinstance(ctx, dict) else {})
        try:
            with ENGINE_LOCK:
                params = p.default_params(tech, ctx)
        except ApiError:
            raise
        except KeyError:
            raise ApiError(422, f"unknown technique {tech!r}")
        return {"params": params}

    @app.post("/api/projects/{pid}/approve")
    def approve(pid: str, body: dict = Body(...)):
        rev = body.get("rev")
        p = project(pid)
        with save_lock:
            saved = saved_storyboard(pid)
            cur = compute_rev(saved)
            if rev != cur:
                raise ApiError(409, "rev is not the current revision", rev=cur)
            with ENGINE_LOCK:
                issues = p.validate(saved)
            if any(i["level"] == "error" for i in issues):
                raise ApiError(422, "cannot approve while there are errors", issues=issues)
            doc = strip_derived(saved)
            doc["approvals"] = {**(doc.get("approvals") or {}), "storyboard": {"rev": cur, "approved_at": now_iso()}}
            commit(pid, p, doc)
            return {"approvals": doc["approvals"]}

    # ------------------------------------------------------------ frames, audio, previews
    JPEG_HEADERS = {"Content-Type": "image/jpeg"}

    @app.get("/api/projects/{pid}/frame")
    def get_frame(pid: str, t: float = Query(...), width: int = Query(960), rev: str | None = Query(None)):
        t = frames_mod.clean_t(t)
        width = frames_mod.clean_width(width)
        p = project(pid)
        cur = current_rev(pid)
        data = frames_mod.cached_jpeg(p, pdir(pid) / "cache" / "frames", cur, t, width)
        cc = "private, max-age=31536000, immutable" if rev == cur else "no-cache"
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": cc, "ETag": f'"{cur[:12]}"'})

    @app.post("/api/projects/{pid}/frame")
    def post_frame(pid: str, body: dict = Body(...)):
        t = frames_mod.clean_t(body.get("t"))
        width = frames_mod.clean_width(body.get("width"))
        draft = need_dict(body, "storyboard")
        p = project(pid)
        data = frames_mod.render_jpeg(p, t, width, draft=strip_derived(draft))
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/projects/{pid}/thumb/{shot_id}")
    def get_thumb(pid: str, shot_id: str, rev: str | None = Query(None)):
        if not ITEM_RE.fullmatch(shot_id):
            raise ApiError(404, "shot not found")
        p = project(pid)
        with ENGINE_LOCK:
            res = p.resolve()
        shot = next((s for s in res.get("shots") or [] if s.get("id") == shot_id), None)
        if shot is None or shot.get("_t0") is None or shot.get("_t1") is None:
            raise ApiError(404, "shot not found")
        t = shot["_t0"] + 0.4 * (shot["_t1"] - shot["_t0"])
        cur = current_rev(pid)
        data = frames_mod.cached_jpeg(p, pdir(pid) / "cache" / "frames", cur, t, 320, tag="th")
        cc = "private, max-age=31536000, immutable" if rev == cur else "no-cache"
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": cc})

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

    @app.post("/api/projects/{pid}/preview")
    def post_preview(pid: str, body: dict = Body(...)):
        try:
            t0, t1 = float(body.get("t0")), float(body.get("t1"))
        except (TypeError, ValueError):
            raise ApiError(422, "t0 and t1 must be numbers")
        frames_mod.clean_t(t0)
        frames_mod.clean_t(t1)
        if not t1 > t0:
            raise ApiError(422, "t1 must be greater than t0")
        if t1 - t0 > 60:
            raise ApiError(422, "a preview is limited to 60 seconds")
        try:
            width = int(body.get("width") or 640)
            fps = int(body.get("fps") or 15)
        except (TypeError, ValueError):
            raise ApiError(422, "width and fps must be integers")
        if not 160 <= width <= 1280 or not 1 <= fps <= 30:
            raise ApiError(422, "width must be 160..1280 and fps 1..30")
        draft = body.get("storyboard")
        if draft is not None and not isinstance(draft, dict):
            raise ApiError(422, "storyboard must be an object")
        p = project(pid)
        d = pdir(pid)
        a = audio_path(pid, strip_derived(draft) if draft else saved_storyboard(pid))
        draft = strip_derived(draft) if draft else None
        jid = jobs.submit(pid, lambda progress: jobs_mod.render_preview(p, d, a, t0, t1, width, fps, draft, pid,
                                                                         progress))
        return {"job_id": jid}

    from .script_api import make_router as _script_router; app.include_router(_script_router(root))  # script stage; also serves /api/jobs/{id} for both job kinds

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
        with save_lock:
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
        tmpdir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=ext, dir=str(tmpdir))
        try:
            size = 0
            with os.fdopen(fd, "wb") as out:
                while chunk := file.file.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise ApiError(413, "file too large")
                    out.write(chunk)
            meta = {"title": title, "artist": artist, "year": year, "licence": licence, "source_url": source_url,
                    "author": author}
            try:
                res = media.add_upload(d, Path(tmp), meta)
            except LicenceRejected as e:
                raise ApiError(422, str(e), reason=str(e))
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
        doc["id"] = prop_id
        return doc

    @app.get("/api/projects/{pid}/proposals")
    def list_proposals(pid: str):
        d = pdir(pid) / "proposals"
        saved = saved_storyboard(pid)
        out = []
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                if not ITEM_RE.fullmatch(f.stem):
                    continue
                try:
                    doc = load_proposal(pid, f.stem)
                except ApiError:
                    continue
                out.append({"id": doc["id"], "created_at": doc.get("created_at"), "author": doc.get("author"),
                            "summary": doc.get("summary"), "n_changes": len(prop_mod.diff(saved, doc["storyboard"]))})
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return out

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
        with save_lock:
            saved = saved_storyboard(pid)
            new, applied, skipped = prop_mod.apply(saved, doc["storyboard"], body.get("accept"))
            if not applied:
                out = save_result(pid, p)
            else:
                new["approvals"] = saved.get("approvals") or {"storyboard": None}
                out = commit(pid, p, new)
            return {**out, "applied": applied, "skipped_locked": skipped}

    from .library_api import make_router as _library_router
    app.include_router(_library_router(root))

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
        a = assets.get(k) or {}
        w, h = a.get("width") or a.get("w"), a.get("height") or a.get("h")
        if not (w and h):
            return k  # engine looks the key up in the saved storyboard
        return {"key": k, "w": w, "h": h, "title": a.get("title"), "artist": a.get("artist"), "year": a.get("year"),
                "regions": a.get("regions") or {}}
    if keys and "asset" not in out:
        out["asset"] = info(keys[0])
        a0 = assets.get(keys[0]) or {}
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
    cache.mkdir(parents=True, exist_ok=True)
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
