"""HTTP API of step 3, the voice (design section 5). `router` is mounted by CORE; tests build their own with `make_router`.

    GET  /api/projects/{pid}/voice               state, chunks by chapter, settings, pronunciation table, estimate, mix
    POST /api/projects/{pid}/voice/generate      {scope: "all" | "changed" | [chunk ids], reseed?: [chunk ids]} -> {job_id}
    PUT  /api/projects/{pid}/voice/settings      {tempo?, pad?, lead?, title?, pronounce?}
                                                 `lead` (0.2 to 15) is the silence before the first word and `title` (3 to 30) the silence that
                                                 holds the channel-name beat, in seconds; null takes the project's own value away (the GET shows
                                                 `silence`: the values in force and whether each is the project's own)
    GET  /api/projects/{pid}/voice/chunks/{id}.wav
    GET  /api/projects/{pid}/voice/mix

Progress and cancel go through the long-job routes (`/api/longjobs/...`)."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse

from bti.voice import describe, files, run as voice_run
from bti.voice.config import SILENCE_RANGES, clamp_tempo, load_voice_config, project_settings
from bti.voice.errors import VoiceError

from .common import ApiError, valid_pid

CHUNK_ID = re.compile(r"^[0-9a-f]{12}$")
MAX_TABLE = 500


def make_router(projects_root: Path | None = None, *, cfg: dict | None = None, server: dict | None = None,
                provider: str | None = None, manager=None) -> APIRouter:
    r = APIRouter(prefix="/api")

    def root_of(request: Request) -> Path:
        if projects_root is not None:
            return Path(projects_root)
        return Path(request.app.state.projects_root)

    def pdir(request: Request, pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found", code="project_not_found")
        d = root_of(request) / pid
        if not d.is_dir() or (d.is_symlink() and not d.resolve().is_relative_to(root_of(request).resolve())):
            raise ApiError(404, "project not found", code="project_not_found")
        return d

    def vcfg() -> dict:
        return cfg or load_voice_config()

    def fail(e: VoiceError):
        return ApiError(e.status, e.message, code=e.code, **e.extra)

    @r.get("/projects/{pid}/voice")
    def get_voice(pid: str, request: Request):
        d = pdir(request, pid)
        return describe(d, pid, cfg=vcfg(), server=server, provider_name=provider, manager=manager)

    @r.post("/projects/{pid}/voice/generate")
    def generate(pid: str, request: Request, body: dict = Body(default={})):
        d = pdir(request, pid)
        body = body if isinstance(body, dict) else {}
        scope = body.get("scope", "changed")
        if isinstance(scope, list):
            if len(scope) > 5000 or not all(isinstance(i, str) and CHUNK_ID.match(i) for i in scope):
                raise ApiError(422, "scope must list chunk ids", code="bad_scope")
        elif scope not in ("all", "changed"):
            raise ApiError(422, "scope must be all, changed or a list of chunk ids", code="bad_scope")
        rs = body.get("reseed")
        if rs is not None and (not isinstance(rs, list) or len(rs) > 5000 or not all(isinstance(i, str) and CHUNK_ID.match(i) for i in rs)):
            raise ApiError(422, "reseed must list chunk ids", code="bad_scope")
        try:
            from bti.longjob import Busy
        except ImportError:
            raise ApiError(500, "the long-job runner is not installed", code="longjob_missing")
        try:
            job = voice_run.start(d, pid, scope=scope, reseed_ids=rs, cfg=vcfg(), server=server, provider_name=provider, manager=manager)
        except VoiceError as e:
            raise fail(e)
        except Busy as e:
            j = getattr(e, "job", None) or {}
            raise ApiError(409, "a voice job is already running for this project", code="voice_busy", job_id=j.get("id") if isinstance(j, dict) else None)
        return {"job_id": job["id"] if isinstance(job, dict) else job}

    @r.put("/projects/{pid}/voice/settings")
    def put_settings(pid: str, request: Request, body: dict = Body(default={})):
        d = pdir(request, pid)
        if not isinstance(body, dict):
            raise ApiError(422, "the body must be an object", code="invalid_request")
        c = vcfg()
        with files.project_lock(d):
            cur = files.read_settings(d)
            if "tempo" in body:
                t = body["tempo"]
                if isinstance(t, bool) or not isinstance(t, (int, float)) or t != t:
                    raise ApiError(422, "tempo must be a number", code="bad_tempo")
                lo, hi = c["tempo_range"]
                if not lo <= t <= hi:
                    raise ApiError(422, "tempo must be between %s and %s" % (lo, hi), code="bad_tempo")
                cur["tempo"] = clamp_tempo(t, c)
            if "pad" in body:
                if not isinstance(body["pad"], bool):
                    raise ApiError(422, "pad must be true or false", code="bad_pad")
                cur["pad"] = body["pad"]
            wrote = "tempo" in body or "pad" in body
            for key, (lo, hi) in SILENCE_RANGES.items():              # the two silences of this project (null removes the project's own)
                if key not in body:
                    continue
                v = body[key]
                if v is None:
                    cur.pop(key, None)
                elif isinstance(v, bool) or not isinstance(v, (int, float)) or v != v or not lo <= v <= hi:
                    bad = "bad_lead" if key == "lead" else "bad_title"
                    raise ApiError(422, "%s must be a number of seconds from %s to %s (or null to use the standard one)" % (key, lo, hi), code=bad)
                else:
                    cur[key] = round(float(v), 3)
                wrote = True
            if wrote:
                files.write_settings(d, cur)
            if "pronounce" in body:
                tab = body["pronounce"]
                if not isinstance(tab, dict) or len(tab) > MAX_TABLE:
                    raise ApiError(422, "pronounce must be an object of at most %d entries" % MAX_TABLE, code="bad_pronounce")
                clean = {}
                for k, v in tab.items():
                    if not isinstance(k, str) or not isinstance(v, str) or not k.strip() or len(k) > 80 or len(v) > 160:
                        raise ApiError(422, "each pronunciation needs a written form (up to 80 characters) and a spoken form (up to 160)", code="bad_pronounce")
                    clean[" ".join(k.split())] = " ".join(v.split())
                files.write_pronounce(d, clean)
        return describe(d, pid, cfg=c, server=server, provider_name=provider, manager=manager)

    @r.get("/projects/{pid}/voice/chunks/{cid}.wav")
    def chunk_audio(pid: str, cid: str, request: Request):
        d = pdir(request, pid)
        if not CHUNK_ID.match(cid) or not files.chunk_path(d, cid).is_file():
            raise ApiError(404, "no audio for this sentence yet", code="no_chunk")
        return FileResponse(files.chunk_path(d, cid), media_type="audio/wav")

    @r.get("/projects/{pid}/voice/mix")
    def mix(pid: str, request: Request):
        d = pdir(request, pid)
        if not files.mix_path(d).is_file():
            raise ApiError(404, "there is no mix yet", code="no_voice")
        return FileResponse(files.mix_path(d), media_type="audio/mp4")

    return r


router = make_router()
