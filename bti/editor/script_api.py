"""HTTP API of the script stage (design section 2.8): brief, prompts, outline, narration, model jobs.
Mounted from app.py. Local tool, bound to 127.0.0.1. Keys never appear in any response."""
from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import PlainTextResponse

from bti import agents as agents_mod
from bti.script import brief as brief_mod
from bti.script import generate, models as models_mod, ops as ops_mod, store, validate
from bti.script.parse import parse_outline, parse_script
from bti.script.prompting import PromptError, build_prompt
from bti.script.runner import BusyError, JobError, ScriptJobs
from bti.script.stats import narration_stats

from .auto_api import gate_actor        # c5cli: who may approve a gate
from .common import ApiError, id_field, string_list, text_field, valid_pid
from .pipeline_api import project_meta


def make_router(projects_root: Path, *, models_path: Path | None = None, jobs: ScriptJobs | None = None,
                library_root: Path | None = None) -> APIRouter:
    r = APIRouter(prefix="/api")
    root = Path(projects_root)
    jobs = jobs or ScriptJobs(projects_root=root)

    def pdir(pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found", code="project_not_found")
        d = root / pid
        has_data = (d / "source").is_dir() or ((d / "project.json").is_file() and project_meta(d, strict=True).get("imported") is not True)
        if not d.is_dir() or not has_data:
            raise ApiError(404, "project not found", code="project_not_found")
        if d.is_symlink() and not d.resolve().is_relative_to(root.resolve()):
            raise ApiError(404, "project not found", code="project_not_found")
        return d

    @contextmanager
    def hold(d: Path):
        """The script lock of the project, and (under it) a check that the project still exists: a writer that waited for the
        lock while the project was being deleted answers 404 and writes nothing (lock order: see bti/script/store.py)."""
        with store.script_lock(d):
            if not d.is_dir():
                raise ApiError(404, "project not found", code="project_not_found")
            yield

    def brief_for(d: Path) -> dict:
        return brief_mod.build_brief(d, library_root=library_root)

    def wps_for(d: Path) -> float:
        return brief_mod.load_options(d)["wps"]

    def narr_payload(d: Path, n: store.Narration | None, brief: dict | None = None) -> dict:
        """The narration document with what the page needs to explain its state:
          approved         True only when the approval stands (`store.narration_approval`: same hash, outline approved and
                           fresh, and it is the outline this narration was approved against).
          approval_reason  why a recorded approval does NOT stand: "narration_edited" | "outline_not_approved" |
                           "outline_changed"; null when it stands or nothing was approved.
          stale            True when the outline changed after this narration was written (`source.outline_sha1` differs from
                           the outline's revision). Information only: it never blocks saving.
          outline_rev      the outline's revision now; `approved_outline_rev` the one the approval was given against.
          chapter_diff     {not_in_outline: [ids], missing_in_narration: [ids], empty_in_narration: [ids], order: bool}: the differences that refuse an approval."""
        o = store.load_outline(d)
        if n is None:
            return {"narration": None, "rev": None, "issues": [], "stats": None, "approved": False, "stale": False,
                    "approval_reason": None, "approved_outline_rev": None, "chapter_diff": store.chapter_diff(None, o),
                    "last_paste": store.read_paste(d, "narration"), "outline_rev": o.rev() if o else None}
        wps = wps_for(d)
        issues = validate.validate_narration(n, o, wps=wps, brief=brief)
        rev = n.rev()
        na = store.narration_approval(n, o)
        written_for = n.source.get("outline_sha1") if isinstance(n.source, dict) else None
        return {"narration": n.to_dict(), "rev": rev, "issues": issues, "stats": narration_stats(n, o, wps),
                "approved": na["approved"], "approval_reason": na["reason"],
                "stale": bool(o is not None and written_for and written_for != o.rev()),
                "approved_outline_rev": n.approval.get("outline_sha1") if n.approval.get("approved") else None,
                "chapter_diff": store.chapter_diff(n, o),
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

    def str_field(body, key: str, required: bool = False) -> str:
        return text_field(body, key, required)

    def rev_field(body) -> str:
        v = body.get("rev")
        if v is None:
            return ""
        if not isinstance(v, str):
            raise ApiError(422, "rev must be a string", code="invalid_field", field="rev")
        return v

    def stale_409(cur: str):
        return ApiError(409, "the file changed since you loaded it; reload before saving", rev=cur, code="stale_revision")

    def model_for(model_id) -> dict:
        """The spec of a model that is NAMED (by the request, or by the agent the project uses): unknown 404, not usable 409."""
        if not isinstance(model_id, str) or not model_id.strip():
            raise ApiError(400, "model is required: name the model to run (see GET /api/models)", code="model_required", field="model")
        from bti.script.providers import claudecode
        if claudecode.is_api_id(model_id) and not claudecode.api_key():
            raise ApiError(409, claudecode.API_KEY_MISSING, code="claude_api_key_missing", field="model")
        spec = models_mod.resolve(model_id, models_path)         # never runs `agy models` for a model that is not Antigravity
        if spec is None:
            raise ApiError(404, "unknown model", code="unknown_model", field="model")
        pub = models_mod.public(spec)
        if not pub["enabled"]:
            raise ApiError(409, pub["message"] or "this model is not available", missing_env=pub["missing_env"], code="model_unavailable", field="model")
        return spec

    def job_model(d: Path, role: str, body) -> tuple[dict, agents_mod.Resolved]:
        """The model of a job: the one the request names (kept for tests and outside tools), else the one the project's agent gives
        (`bti.agents.model_for_project`: the step's choice, the project's agent, the machine's default, the role's setting). A model a
        request names that is not a non-empty string is refused (400), as before; an agent whose model cannot run is 409 `agent_unavailable`."""
        named = body.get("model") if isinstance(body, dict) else None
        if named is not None and (not isinstance(named, str) or not named.strip()):
            raise ApiError(400, "model must be a model id: name the model to run, or leave it out to use the project's agent (see GET /api/agents)", code="model_invalid", field="model")
        res = agents_mod.model_for_project(d, role, named)
        if res.source == "request":
            return model_for(res.model), res
        try:
            return model_for(res.model), res
        except ApiError as e:
            if e.extra.get("code") == "claude_api_key_missing":
                raise
            if e.status not in (404, 409):
                raise
            why = e.detail if e.status == 409 and isinstance(e.detail, str) and e.detail != "this model is not available" else \
                "Agent %s chưa dùng được trên máy này." % res.label
            raise ApiError(409, why, code="agent_unavailable", agent=res.public())

    def alternatives() -> list[str]:
        return [m["id"] for m in models_mod.public_models(models_path) if m["enabled"]]

    def start_job(kind: str, pid: str, spec: dict, body, res: agents_mod.Resolved) -> dict:
        try:
            job = jobs.start(kind, pid, spec["id"], body, alternatives=alternatives, exclusive=True, agent=res.public())
        except BusyError as e:
            raise ApiError(409, "another model job is running for this project", job_id=e.job.id, code="model_job_busy")
        return {"job_id": job.id, "model": spec["id"], "agent": res.public()}

    # ------------------------------------------------------------ models and jobs
    @r.get("/models")
    def list_models(refresh: int = Query(0)):
        # `?refresh=1` forces a new `agy models` call; otherwise cached 10 minutes (1 minute after a failure).
        # An antigravity entry carries `agy: {ok, reason}` (reason: timeout, config, auth... when not ok).
        return models_mod.public_models(models_path, refresh=bool(refresh))

    @r.get("/jobs/{job_id}")
    def get_job(job_id: str, request: Request):
        j = jobs.get(job_id)
        if j is not None:
            return j.public()
        prev = getattr(request.app.state, "jobs", None)       # the editor's preview jobs share this path
        pj = prev.get(job_id) if prev is not None else None
        if pj is None:
            pj = jobs.persisted(job_id)          # a job of an earlier run of the server
        if pj is None:
            raise ApiError(404, "job not found", code="job_not_found")
        return pj

    @r.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        if not jobs.cancel(job_id):
            raise ApiError(404, "job not found", code="job_not_found")
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
        try:
            brief_mod.save_options(d, body, library_root=library_root)
        except brief_mod.OptionsError as e:
            code = getattr(e, "code", "options_error")
            raise ApiError(422, str(e), code=code)
        return brief_for(d)["options"]

    @r.get("/projects/{pid}/prompt")
    def get_prompt(pid: str, phase: str = Query(...), chapters: str = Query(""), notes: str = Query("")):
        d = pdir(pid)
        if phase not in ("outline", "script"):
            raise ApiError(422, "phase must be outline or script", code="invalid_field", field="phase")
        o = store.load_outline(d)
        want = [c for c in re.split(r"[,\s]+", chapters) if c] or None
        if phase == "script":
            gate = validate.outline_gate(o)
            if gate:
                raise ApiError(409, gate["message"], code=gate["code"])
        try:
            p = build_prompt(phase, d, notes=notes, chapters=want, outline=o, narration=store.load_narration(d),
                             brief=brief_for(d), wps=wps_for(d))
        except PromptError as e:
            raise ApiError(422, str(e), code="prompt_error")
        return PlainTextResponse(p["text"])

    # ------------------------------------------------------------ outline
    @r.post("/projects/{pid}/outline/generate")
    def outline_generate(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        spec, res = job_model(d, "script.outline", body)
        notes = str_field(body, "notes")
        wps = wps_for(d)
        base_rev = store.disk_rev(store.script_dir(d) / "outline.json", "outline")       # fixed here, before the job id is returned
        return start_job("outline", pid, spec, lambda job: generate.run_outline(job, d, spec, notes, wps=wps, base_rev=base_rev), res)

    @r.post("/projects/{pid}/outline/import")
    def outline_import(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        with hold(d):
            text = str_field(body, "text", True)
            brief = brief_for(d)
            res = parse_outline(text, set(brief["paragraph_ids"]), target_words=brief["options"]["target_words"])
            if not res.ok:
                store.keep_paste(d, "outline", text)
                raise ApiError(422, res.error or "the outline could not be read", paragraphs=res.paragraphs, issues=res.issues,
                               kept=True, code="outline_unreadable")
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
        with hold(d):
            raw = body.get("outline")
            problem = store.doc_problem("outline", raw)
            if problem:
                raise ApiError(422, problem, code="document_invalid", field="outline")
            o = store.Outline.from_dict(raw)
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
        actor = gate_actor(d, "outline", body)          # c5cli: an actor that is not `human` needs the owner's `auto` to allow the gate
        with hold(d):
            o = store.load_outline(d)
            if o is None:
                raise ApiError(404, "no outline to approve", code="no_outline")
            errs = validate.blocking(validate.validate_outline(o, brief_for(d)))
            if errs:
                raise ApiError(422, "the outline has errors: " + "; ".join(e["message"] for e in errs), issues=errs, code="outline_has_errors")
            try:
                store.approve(d, "outline", rev_field(body), actor)
            except store.StaleRevision as e:
                raise stale_409(str(e))
            return outline_payload(d, store.load_outline(d), brief_for(d))

        # ------------------------------------------------------------ narration
    @r.post("/projects/{pid}/narration/generate")
    def narration_generate(pid: str, body: dict = Body(default={})):
        d = pdir(pid)
        spec, res = job_model(d, "script.narration", body)
        o = store.load_outline(d)
        gate = validate.outline_gate(o)
        if gate:
            raise ApiError(409, gate["message"], code=gate["code"])
        raw_ch = string_list(body.get("chapters"), "chapters", max_items=200, max_len=40)
        chapters = list(raw_ch or []) or None
        if chapters:
            bad = [c for c in chapters if o.chapter(c) is None]
            if bad:
                raise ApiError(422, f"unknown chapter(s): {', '.join(bad)}", code="unknown_chapter", field="chapters")
        n = store.load_narration(d)
        if n and not body.get("force"):
            targets = chapters or [c.id for c in o.chapters]
            locked = [f"{c.id}:{b.id}" for c in n.chapters if c.id in targets for b in c.beats if b.locked]
            if locked:
                raise ApiError(409, "locked beats would be replaced (" + ", ".join(locked[:6]) + "); unlock them or send force", locked=locked, code="locked_beats")
        notes = str_field(body, "notes")
        wps = wps_for(d)
        base_locked = sorted(b.id for c in n.chapters for b in c.beats if b.locked) if n else []     # fixed here, not in the thread
        return start_job("narration", pid, spec, lambda job: generate.run_narration(job, d, spec, chapters, notes, wps=wps,
                                                                                     base_locked=base_locked), res)

    @r.post("/projects/{pid}/narration/import")
    def narration_import(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        with hold(d):
            text = str_field(body, "text", True)
            o = store.load_outline(d)
            if o is None:
                raise ApiError(409, "there is no outline yet: make or paste the outline first", code="no_outline")
            old = store.load_narration(d)
            res = parse_script(text, o, project=pid, title=brief_for(d)["painting"]["title"],
                               counter_start=(old.counters["beat"] if old else 0))
            if not res.ok:
                store.keep_paste(d, "narration", text)
                raise ApiError(422, res.error or "the script could not be placed", paragraphs=res.paragraphs, issues=res.issues,
                               kept=True, code="narration_unreadable")
            n = res.narration
            if old and not body.get("force"):
                # the same protection as `generate`: a paste never silently replaces a beat the owner locked
                got = {c.id for c in n.chapters}
                locked = [f"{c.id}:{b.id}" for c in old.chapters if c.id in got for b in c.beats if b.locked]
                if locked:
                    store.keep_paste(d, "narration", text)
                    raise ApiError(409, "locked beats would be replaced (" + ", ".join(locked[:6]) + "); unlock them or send force",
                                   locked=locked, kept=True, code="locked_beats")
            if body.get("merge") and old:
                got = {c.id for c in n.chapters}
                order = {c.id: i for i, c in enumerate(o.chapters)}
                n.chapters = [c for c in old.chapters if c.id not in got and c.id in order] + n.chapters
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
        with hold(d):
            raw = body.get("narration")
            problem = store.doc_problem("narration", raw)
            if problem:
                raise ApiError(422, problem, code="document_invalid", field="narration")
            n = store.Narration.from_dict(raw)
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
        with hold(d):
            n = store.load_narration(d)
            if n is None:
                raise ApiError(404, "no narration yet", code="no_narration")
            cur = n.rev()
            if body.get("base_rev") != cur:
                raise stale_409(cur)
            ops = body.get("ops")
            if not isinstance(ops, list) or not ops:
                raise ApiError(422, "ops must be a non-empty list of operations", code="invalid_field", field="ops")
            results = []
            outline = store.load_outline(d)
            try:
                for op in ops:
                    results.append(ops_mod.apply_op(n, op, outline))
            except ops_mod.OpError as e:
                raise ApiError(422, str(e), code="op_invalid", field="ops")
            store.save_narration(d, n, cur)
            return {"results": results, **narr_payload(d, store.load_narration(d), brief_for(d))}

    @r.post("/projects/{pid}/narration/approve")
    def narration_approve(pid: str, body: dict = Body(...)):
        d = pdir(pid)
        actor = gate_actor(d, "narration", body)        # c5cli
        with hold(d):
            n = store.load_narration(d)
            if n is None:
                raise ApiError(404, "no narration to approve", code="no_narration")
            o = store.load_outline(d)
            issues = validate.validate_narration(n, o, wps=wps_for(d), brief=brief_for(d))     # the same list as GET .../narration: a refusal shows the warnings too
            errs = validate.blocking(issues)
            if errs:
                diff = store.chapter_diff(n, o)
                raise ApiError(422, "the narration has errors: " + "; ".join(e["message"] for e in errs[:5]), issues=issues,
                               chapter_diff=diff, code="narration_has_errors")
            try:
                store.approve(d, "narration", rev_field(body), actor)
            except store.StaleRevision as e:
                raise stale_409(str(e))
            return narr_payload(d, store.load_narration(d), brief_for(d))

    return r
