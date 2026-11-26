"""Read, set, clear and generate a project's music document."""
from fastapi import APIRouter, Body
from fastapi.responses import FileResponse
from urllib.parse import quote

from bti.engine.timing import Timing
from bti.music import inputs, library, store
from bti.music.document import validate
from bti.music.export import recording_path
from bti.music.document import MusicError
from .common import ApiError
from .auto_api import actor_of


def _api(exc):
    return ApiError(409 if exc.code in ("stale_revision", "agent_job_running") else 422, exc.detail, code=exc.code, fix=exc.fix, retry=exc.retry,
                    **({"field": exc.field} if exc.field else {}), **({"job_id": exc.job_id} if getattr(exc, "job_id", None) else {}))


def make_router(*, pdir):
    router = APIRouter(prefix="/api/projects/{pid}/music")

    @router.get("")
    def get_music(pid: str):
        d = pdir(pid)
        doc = store.read(d)
        try:
            rows = library.index()
        except (OSError, ValueError):
            rows = {}
        out = {"music": doc, "rev": store.revision(doc), "cues": [], "library_count": len(rows),
               "ready": (d / "storyboard.json").is_file() and (d / "timing.json").is_file() and bool(rows), "problem": None}
        try:
            from bti.longjob import manager
            active = manager.active(pid, kind="title")
            out["job"] = active if active and (active.get("meta") or {}).get("action") == "music" else None
        except Exception:
            out["job"] = None
        if doc is not None:
            try:
                data = inputs.load(d, need_library=False)
                cues = validate(doc, data["library"], Timing(data["timing"]), data["duration"], data["landmarks"])
                for cue in cues:
                    rec = rows[cue["recording"]]
                    out["cues"].append({"start": cue["start"], "end": cue["end"], "role": cue["role"], "title": rec.get("title", ""),
                                        "composer": rec.get("composer", ""), "audio_url": "/api/projects/%s/music/recordings/%s" % (quote(pid, safe=""), quote(cue["recording"], safe=""))})
            except (MusicError, OSError, ValueError, KeyError):
                out["problem"] = "music_invalid"
        return out

    @router.get("/recordings/{recording_id}")
    def get_recording(pid: str, recording_id: str):
        pdir(pid)
        try:
            row = library.index().get(recording_id)
            if row is None:
                raise ValueError("unknown recording")
            path = recording_path(library.directory(), row)
        except (MusicError, OSError, ValueError):
            raise ApiError(404, "recording not found", code="not_found")
        return FileResponse(path, media_type="audio/ogg")

    @router.put("")
    def set_music(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        try:
            inp = inputs.load(d, need_library=False)
            doc = store.set_document(d, body.get("music"), inp["library"], Timing(inp["timing"]), inp["duration"],
                                     landmarks=inp["landmarks"], base_rev=body.get("base_rev"))
        except MusicError as exc:
            raise _api(exc)
        return {"music": doc, "rev": store.revision(doc)}

    @router.post("/clear")
    def clear_music(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        try:
            store.clear(d, base_rev=body.get("base_rev"))
        except MusicError as exc:
            raise _api(exc)
        return {"music": None, "rev": store.revision(None)}

    @router.post("/auto")
    def auto_music(pid: str, body: dict = Body(default={})):
        from bti.music import job
        actor = actor_of(body)
        try:
            rec = job.start(pid, pdir(pid), actor=actor, model=body.get("model"), by_run=actor == "agent:auto")
        except MusicError as exc:
            raise _api(exc)
        return {"job_id": rec["id"], "model": (rec.get("meta") or {}).get("model"), "agent": (rec.get("meta") or {}).get("agent")}

    return router
