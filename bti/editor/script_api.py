"""HTTP API of the script stage (design section 2.8): brief, prompts, outline, narration, model jobs.
Mounted from app.py. Local tool, bound to 127.0.0.1. Keys never appear in any response."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import PlainTextResponse

from bti.script import brief as brief_mod
from bti.script import generate, models as models_mod, ops as ops_mod, store, validate
from bti.script.parse import parse_outline, parse_script
from bti.script.prompting import PromptError, build_prompt
from bti.script.runner import JobError, ScriptJobs
from bti.script.stats import narration_stats

from .common import ApiError, valid_pid


def make_router(projects_root: Path, *, models_path: Path | None = None, jobs: ScriptJobs | None = None,
                library_root: Path | None = None) -> APIRouter:
    r = APIRouter(prefix="/api")
    jobs = jobs or ScriptJobs()
    root = Path(projects_root)

    def pdir(pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if not d.is_dir() or not (d / "project.json").is_file() and not (d / "source").is_dir():
            raise ApiError(404, "project not found")
        if d.is_symlink() and not d.resolve().is_relative_to(root.resolve()):
            raise ApiError(404, "project not found")
        return d

    def brief_for(d: Path) -> dict:
        return brief_mod.build_brief(d, library_root=library_root)

    def wps_for(d: Path) -> float:
        return brief_mod.load_options(d)["wps"]

    def narr_payload(d: Path, n: store.Narration | None, brief: dict | None = None) -> dict:
        o = store.load_outline(d)
        if n is None:
            return {"narration": None, "rev": None, "issues": [], "stats": None, "approved": False, "stale": False,
                    "last_paste": store.read_paste(d, "narration"), "outline_rev": o.rev() if o else None}
        wps = wps_for(d)
        issues = validate.validate_narration(n, o, wps=wps, brief=brief)
        rev = n.rev()
        ap = n.approval
        return {"narration": n.to_dict(), "rev": rev, "issues": issues, "stats": narration_stats(n, o, wps),
                "approved": bool(ap.get("approved")) and ap.get("sha1") == rev,
                "stale": bool(ap.get("approved")) and ap.get("sha1") != rev,
                "last_paste": store.read_paste(d, "narration"), "outline_rev": o.rev() if o else None}

    def outline_payload(d: Path, o: store.Outline | None, brief: dict | None = None) -> dict:
        if o is None:
            return {"outline": None, "rev": None, "issues": [], "approved": False, "stale": False,
                    "last_paste": store.read_paste(d, "outline")}
        rev = o.rev()
        ap = o.approval
        return {"outline": o.to_dict(), "rev": rev, "issues": validate.validate_outline(o, brief),
                "approved": bool(ap.get("approved")) and ap.get("sha1") == rev,
                "stale": bool(ap.get("approved")) and ap.get("sha1") != rev,
                "last_paste": store.read_paste(d, "outline")}

    def stale_409(cur: str):
        return ApiError(409, "the file changed since you loaded it; reload before saving", rev=cur)

    def model_for(model_id: str | None) -> dict:
        ms = models_mod.load_models(models_path)
        spec = next((m for m in ms if m["id"] == model_id), None) if model_id else next((m for m in ms if m.get("default")), None)
        if spec is None:
            raise ApiError(404, "unknown model")
        pub = models_mod.public(spec)
        if not pub["enabled"]:
            raise ApiError(409, f"the key {pub['missing_env']} is not set for this model", missing_env=pub["missing_env"])
        return spec

    def alternatives() -> list[str]:
        return [m["id"] for m in models_mod.public_models(models_path) if m["enabled"]]

    def start_job(kind: str, pid: str, spec: dict, body) -> dict:
        busy = jobs.running(pid)
        if busy:
            raise ApiError(409, "another model job is running for this project", job_id=busy.id)
        job = jobs.start(kind, pid, spec["id"], body, alternatives=alternatives)
        return {"job_id": job.id}

    # ------------------------------------------------------------ models and jobs
    @r.get("/models")
    def list_models():
        return models_mod.public_models(models_path)

    @r.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        j = jobs.get(job_id)
        if j is not None:
            return j.public()
        prev = getattr(request.app.state, "jobs", None)       # the editor's preview jobs share this path
        pj = prev.get(job_id) if prev is not None else None
        if pj is None:
            raise ApiError(404, "job not found")
        return pj

    @r.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        if not jobs.cancel(job_id):
            raise ApiError(404, "job not found")
        return jobs.get(job_id).public()

    @r.get("/projects/{pid}/script/jobs")
    def project_jobs(pid: str):
        pdir(pid)
        return jobs.for_project(pid)

    # ------------------------------------------------------------ brief and prompts
    @r.get("/projects/{pid}/brief")
    def get_brief(pid: str):
        return brief_for(pdir(pid))

    @r.put("/projects/{pid}/brief/options")
    def put_brief_options(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        brief_mod.save_options(d, body)
        return brief_for(d)["options"]

    @r.get("/projects/{pid}/prompt")
    def get_prompt(pid: str, phase: str = Query(...), chapters: str = Query(""), notes: str = Query("")):
        d = pdir(pid)
        if phase not in ("outline", "script"):
            raise ApiError(422, "phase must be outline or script")
        o = store.load_outline(d)
        want = [c for c in re.split(r"[,\s]+", chapters) if c] or None
        if phase == "script":
            gate = validate.outline_gate(o)
            if gate:
                raise ApiError(409, gate["message"])
        try:
            p = build_prompt(phase, d, notes=notes, chapters=want, outline=o, narration=store.load_narration(d),
                             brief=brief_for(d), wps=wps_for(d))
        except PromptError as e:
            raise ApiError(422, str(e))
        return PlainTextResponse(p["text"])

    # ------------------------------------------------------------ outline
    @r.post("/projects/{pid}/outline/generate")
    def outline_generate(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        spec = model_for(body.get("model"))
        notes = str(body.get("notes") or "")
        wps = wps_for(d)
        return start_job("outline", pid, spec, lambda job: generate.run_outline(job, d, spec, notes, wps=wps))

    @r.post("/projects/{pid}/outline/import")
    def outline_import(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        text = str(body.get("text") or "")
        brief = brief_for(d)
        res = parse_outline(text, set(brief["paragraph_ids"]), target_words=brief["options"]["target_words"])
        if not res.ok:
            store.keep_paste(d, "outline", text)
            raise ApiError(422, res.error or "the outline could not be read", paragraphs=res.paragraphs, issues=res.issues,
                           kept=True)
        res.outline.source = {"kind": "paste", "model": "", "created_at": store.now_iso()}
        store.save_outline(d, res.outline)
        store.clear_paste(d, "outline")
        return {"ok": True, "parse_issues": res.issues, **outline_payload(d, store.load_outline(d), brief)}

    @r.get("/projects/{pid}/outline")
    def get_outline(pid: str):
        d = pdir(pid)
        return outline_payload(d, store.load_outline(d), brief_for(d))

    @r.put("/projects/{pid}/outline")
    def put_outline(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        o = store.Outline.from_dict(body.get("outline") or {})
        cur = store.disk_rev(store.script_dir(d) / "outline.json", "outline")
        if cur is not None and body.get("base_rev") != cur:
            raise stale_409(cur)
        old = store.load_outline(d)
        o.approval = old.approval if old else o.approval
        try:
            store.save_outline(d, o, cur)
        except store.StaleRevision as e:
            raise stale_409(str(e))
        return outline_payload(d, store.load_outline(d), brief_for(d))

    @r.post("/projects/{pid}/outline/approve")
    def outline_approve(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        o = store.load_outline(d)
        if o is None:
            raise ApiError(404, "no outline to approve")
        errs = validate.blocking(validate.validate_outline(o, None))
        if errs:
            raise ApiError(422, "the outline has errors: " + "; ".join(e["message"] for e in errs), issues=errs)
        try:
            store.approve(d, "outline", str(body.get("rev") or ""))
        except store.StaleRevision as e:
            raise stale_409(str(e))
        return outline_payload(d, store.load_outline(d), brief_for(d))

    # ------------------------------------------------------------ narration
    @r.post("/projects/{pid}/narration/generate")
    def narration_generate(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        spec = model_for(body.get("model"))
        o = store.load_outline(d)
        gate = validate.outline_gate(o)
        if gate:
            raise ApiError(409, gate["message"])
        chapters = [str(c) for c in (body.get("chapters") or [])] or None
        if chapters:
            bad = [c for c in chapters if o.chapter(c) is None]
            if bad:
                raise ApiError(422, f"unknown chapter(s): {', '.join(bad)}")
        n = store.load_narration(d)
        if n and not body.get("force"):
            targets = chapters or [c.id for c in o.chapters]
            locked = [f"{c.id}:{b.id}" for c in n.chapters if c.id in targets for b in c.beats if b.locked]
            if locked:
                raise ApiError(409, "locked beats would be replaced (" + ", ".join(locked[:6]) + "); unlock them or send force", locked=locked)
        notes = str(body.get("notes") or "")
        wps = wps_for(d)
        return start_job("narration", pid, spec, lambda job: generate.run_narration(job, d, spec, chapters, notes, wps=wps))

    @r.post("/projects/{pid}/narration/import")
    def narration_import(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        text = str(body.get("text") or "")
        o = store.load_outline(d)
        if o is None:
            raise ApiError(409, "there is no outline yet: make or paste the outline first")
        old = store.load_narration(d)
        res = parse_script(text, o, project=pid, title=brief_for(d)["painting"]["title"],
                           counter_start=(old.counters["beat"] if old else 0))
        if not res.ok:
            store.keep_paste(d, "narration", text)
            raise ApiError(422, res.error or "the script could not be placed", paragraphs=res.paragraphs, issues=res.issues,
                           kept=True)
        n = res.narration
        if body.get("merge") and old:
            got = {c.id for c in n.chapters}
            n.chapters = [c for c in old.chapters if c.id not in got] + n.chapters
            order = {c.id: i for i, c in enumerate(o.chapters)}
            n.chapters.sort(key=lambda c: order.get(c.id, 10_000))
        n.source = {"kind": "paste", "model": "", "created_at": store.now_iso(), "outline_sha1": o.rev()}
        store.save_narration(d, n)
        store.clear_paste(d, "narration")
        return {"ok": True, "parse_issues": res.issues, **narr_payload(d, store.load_narration(d), brief_for(d))}

    @r.get("/projects/{pid}/narration")
    def get_narration(pid: str):
        d = pdir(pid)
        return narr_payload(d, store.load_narration(d), brief_for(d))

    @r.put("/projects/{pid}/narration")
    def put_narration(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        n = store.Narration.from_dict(body.get("narration") or {})
        path = store.script_dir(d) / "narration.json"
        cur = store.disk_rev(path)
        if cur is not None and body.get("base_rev") != cur:
            raise stale_409(cur)
        old = store.load_narration(d)
        if old:
            n.approval = old.approval
            n.counters["beat"] = max(n.counters["beat"], old.counters["beat"])
        n.project = n.project or pid
        try:
            store.save_narration(d, n, cur)
        except store.StaleRevision as e:
            raise stale_409(str(e))
        return narr_payload(d, store.load_narration(d), brief_for(d))

    @r.post("/projects/{pid}/narration/ops")
    def narration_ops(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        n = store.load_narration(d)
        if n is None:
            raise ApiError(404, "no narration yet")
        cur = n.rev()
        if body.get("base_rev") != cur:
            raise stale_409(cur)
        results = []
        try:
            for op in body.get("ops") or []:
                results.append(ops_mod.apply_op(n, op))
        except ops_mod.OpError as e:
            raise ApiError(422, str(e))
        store.save_narration(d, n, cur)
        return {"results": results, **narr_payload(d, store.load_narration(d), brief_for(d))}

    @r.post("/projects/{pid}/narration/approve")
    def narration_approve(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        n = store.load_narration(d)
        if n is None:
            raise ApiError(404, "no narration to approve")
        issues = validate.validate_narration(n, store.load_outline(d), wps=wps_for(d))
        errs = validate.blocking(issues)
        if errs:
            raise ApiError(422, "the narration has errors: " + "; ".join(e["message"] for e in errs[:5]), issues=issues)
        try:
            store.approve(d, "narration", str(body.get("rev") or ""))
        except store.StaleRevision as e:
            raise stale_409(str(e))
        return narr_payload(d, store.load_narration(d), brief_for(d))

    return r
