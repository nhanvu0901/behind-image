"""One long job (design section 4): build the workspace, run a provider, compile, write the proposal.

    start(pid, project_dir, provider="agy"|"auto", model=None, chapters=None)   -> the job's public record (bti.longjob)
    state(project_dir)                                                          -> {"state": none|running|stale|done, "detail", ...}
    overview(pid, project_dir)                                                  -> what the panel shows

The job has three parts, none of them heavy (the model works, not this machine): `prepare` (read the inputs, make the workspace),
`agent` (the run; time limit 30 minutes), `compile` (read back `out/`, compile with degrade, draw check, write the proposal).
The proposal `proposals/draft_<time>.json` carries the hashes it was made from; it is never applied here. The workspace is
removed afterwards unless the run failed or was `tampered` (then it is kept for inspection). Only the event transcript and a copy
of `out/` stay under `cache/draft/<run>/`."""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import spec as S
from .inputs import DraftError, DraftInputs, canon_hash, load_inputs, normalize_timing, read_json_file

KIND = "draft"
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")
AGENT_TIMEOUT_S = 30 * 60
KEEP_RUNS = 5

VI = {
    "draft_not_ready": "Chưa đủ dữ liệu để dựng bản nháp: cần giọng đọc (timing.json) và danh sách hình đã duyệt (picks.json).",
    "agy_missing": "Chưa cài `agy` (Antigravity CLI) trên máy này. Dùng chế độ tự động, hoặc cài agy rồi thử lại.",
    "agy_config": "agy trên máy này không dùng được cho việc này (quá cũ hoặc không chạy được).",
    "agy_busy": "Một lần chạy agent khác đang diễn ra. Đợi nó xong rồi thử lại.",
    "agy_auth": "agy chưa đăng nhập trong phiên máy đang chạy ứng dụng. Đăng nhập agy một lần rồi thử lại.",
    "agy_rate_limit": "Hạn mức của gói Antigravity đã dùng hết hoặc bị giới hạn. Đợi hết chu kỳ hoặc chọn mô hình khác.",
    "agy_model": "agy không nhận ra tên mô hình này. Chọn mô hình khác trong danh sách.",
    "agy_error": "agy báo lỗi khi chạy.",
    "agy_no_result": "agy dừng mà không trả kết quả.",
    "agy_timeout": "Agent chạy quá thời gian cho phép nên đã bị dừng.",
    "draft_tampered": "Agent đã thay đổi tệp ngoài thư mục làm việc của nó. Kết quả bị bỏ; hãy kiểm tra dự án rồi chạy lại.",
    "draft_no_output": "Agent không viết tệp kết quả nào trong thư mục out/. Chưa có bản nháp.",
    "timing_missing": "Chưa có timing.json: làm bước Giọng đọc trước.", "picks_missing": "Chưa có picks.json: làm bước Chọn hình trước.",
    "picks_no_main": "Chưa chọn tranh chính trong bước Chọn hình.",
    "unknown_chapter": "Không có chương này trong dự án.", "scope_needs_storyboard": "Chỉ dựng lại một chương khi dự án đã có storyboard.",
    "compile_empty": "Không dựng được cảnh nào từ kết quả của agent.",
}


def vi(code: str, fallback: str = "") -> str:
    return VI.get(code) or fallback or code


# ------------------------------------------------------------------------------------------------ state
def _cache(project_dir: Path) -> Path:
    return Path(project_dir) / "cache" / "draft"


def readiness(project_dir: Path) -> dict:
    project_dir = Path(project_dir)
    voice = {"ok": False, "detail": "Chưa có giọng đọc: làm bước Giọng đọc trước."}
    try:
        raw = read_json_file(project_dir / "timing.json", "timing")
        t = normalize_timing(raw)
        voice = {"ok": True, "detail": "Giọng đọc xong: %d chữ, %d đoạn, %.0f giây." % (len(t["words"]), len(t["beats"]), t["duration"])}
    except DraftError as e:
        if e.code != "timing_missing":
            voice["detail"] = "timing.json không dùng được: " + e.message
    picks = {"ok": False, "detail": "Chưa có danh sách hình: làm bước Chọn hình trước."}
    try:
        d = read_json_file(project_dir / "picks.json", "picks")
        main = d.get("main_asset") if isinstance(d, dict) else None
        if not (isinstance(d, dict) and isinstance(d.get("assets"), dict) and main in d["assets"]):
            picks["detail"] = "Chưa chọn tranh chính."
        elif not (d.get("approval") or {}).get("approved"):
            picks["detail"] = "Danh sách hình chưa được duyệt."
        else:
            picks = {"ok": True, "detail": "Danh sách hình đã duyệt (%d hình)." % len(d["assets"])}
    except DraftError as e:
        if e.code != "picks_missing":
            picks["detail"] = "picks.json không dùng được: " + e.message
    return {"voice": voice, "picks": picks, "ok": voice["ok"] and picks["ok"]}


def last_run(project_dir: Path) -> dict | None:
    f = _cache(project_dir) / "last_run.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def latest_proposal(project_dir: Path) -> dict | None:
    pdir = Path(project_dir) / "proposals"
    if not pdir.is_dir():
        return None
    for f in sorted(pdir.glob("draft_*.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            return {"id": f.stem, "doc": d}
    return None


def _manager():
    try:
        from bti.longjob import manager
        return manager
    except Exception:       # noqa: BLE001
        return None


def state(project_dir) -> dict:
    project_dir = Path(project_dir)
    m = _manager()
    try:
        job = m.active(project_dir.name, KIND) if m else None
    except Exception:       # noqa: BLE001
        job = None
    if job:
        return {"state": "running", "detail": "Đang dựng bản nháp.", "job_id": job.get("id")}
    prop = latest_proposal(project_dir)
    if prop is None:
        return {"state": "none", "detail": "Chưa có bản nháp." if readiness(project_dir)["ok"] else "Chưa đủ dữ liệu để dựng bản nháp.", "proposal": None}
    made = (prop["doc"].get("made_from") or {})
    stale = False
    try:
        inp = load_inputs(project_dir)
        h = inp.hashes()
        stale = made.get("timing") != h["timing"] or made.get("picks") != h["picks"]
    except DraftError:
        stale = True
    if stale:
        return {"state": "stale", "detail": "Bản nháp %s được dựng từ giọng đọc hoặc danh sách hình đã đổi." % prop["id"], "proposal": prop["id"]}
    return {"state": "done", "detail": "Đã có bản nháp %s." % prop["id"], "proposal": prop["id"]}


def overview(pid: str, project_dir: Path, default_model: str) -> dict:
    st = state(project_dir)
    return {"ready": readiness(project_dir), "state": st, "last_run": last_run(project_dir), "default_model": default_model,
            "providers": ["agy", "auto"], "job_id": st.get("job_id")}


# ------------------------------------------------------------------------------------------------ the job
class _Run:
    """What the three parts share."""

    def __init__(self, project_dir: Path, provider: str, model: str | None, chapters: list | None):
        self.project_dir, self.provider, self.model, self.chapters = Path(project_dir), provider, model, chapters
        self.run_id = time.strftime("%Y%m%d-%H%M%S")
        self.inputs: DraftInputs | None = None
        self.ws = None
        self.agy = None
        self.specs: dict = {}
        self.notes = ""
        self.out = None
        self.partial = False

    @property
    def cache(self) -> Path:
        return _cache(self.project_dir) / self.run_id


def _author(r: _Run) -> str:
    if r.provider == "auto":
        return "agent:auto"
    from .providers.agy import DEFAULT_MODEL
    return "agent:agy:%s" % (r.model or DEFAULT_MODEL)


def shots_text(n_all: int, n_content: int, n_cards: int) -> str:
    """'54 cảnh: 48 cảnh nội dung, 6 thẻ': the number of shots of the storyboard, then how it splits."""
    return "%d cảnh: %d cảnh nội dung, %d thẻ" % (n_all, n_content, n_cards)


def _write_last(r: _Run, **kw) -> None:
    from bti.engine.storyboard import write_atomic
    d = {"id": r.run_id, "provider": r.provider, "model": r.model, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "chapters": r.chapters}
    d.update(kw)
    try:
        write_atomic(_cache(r.project_dir) / "last_run.json", json.dumps(d, ensure_ascii=False, indent=1))
    except OSError:
        pass


def _prune(project_dir: Path) -> None:
    base = _cache(project_dir)
    try:
        runs = sorted(p for p in base.iterdir() if p.is_dir())
        for p in runs[:-KEEP_RUNS]:
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass


def make_parts(project_dir: Path, provider: str, model: str | None, chapters: list | None, *, agent_timeout: float = AGENT_TIMEOUT_S,
               guard_factory=None, python: str | None = None):
    """The parts of the job (see the module docstring). `guard_factory(project_dir)` and `python` are for tests."""
    from bti.longjob import Part, PartError
    r = _Run(project_dir, provider, model, chapters)

    def fail(e: DraftError, **kw):
        _write_last(r, status="error", error=e.code, **kw)
        return PartError(e.code, vi(e.code, e.message))

    def prepare(ctx):
        from . import workspace
        try:
            r.inputs = load_inputs(r.project_dir, chapters)
            if provider == "agy":
                workspace.clean_old()
                r.ws = workspace.build(r.inputs, python=python)
        except DraftError as e:
            raise fail(e)
        ctx.progress(1.0, "Đã chuẩn bị dữ liệu.")

    def agent(ctx):
        try:
            if provider == "auto":
                from .providers import auto
                r.specs = {cid: S.shape_problems(sp, cid)[0] for cid, sp in auto.draft(r.inputs).items()}
                r.notes = auto.NOTES
                ctx.progress(1.0, "Đã dựng tự động.")
                return
            from .providers import agy
            from .guard import Guard
            from .workspace import workspace_compile
            guard = guard_factory(r.project_dir) if guard_factory else Guard(r.project_dir)
            n_ch = max(1, len(r.inputs.in_scope()))

            def on_progress(p):
                frac = 0.05 + 0.9 * min(1.0, p["out_files"] / n_ch)
                ctx.progress(frac, "Bước %d, %s; đã viết %d/%d chương." % (p["steps"], p["last_action"] or "đang bắt đầu", p["out_files"], n_ch))

            def check(turn):
                res, _ = workspace_compile(r.ws.root, draw=True)
                ctx.log("check after turn %d: %d errors, %d warnings" % (turn, len(res.errors), len(res.warnings)))
                from .compile import summary_text
                return summary_text(res) if res.errors else None

            r.cache.mkdir(parents=True, exist_ok=True)
            r.agy = agy.run(r.ws.root, model=model, timeout=agent_timeout, check=check, cancel=ctx.cancelled, runner=ctx.run_process, on_progress=on_progress,
                            transcript_path=r.cache / "events.jsonl", guard=guard, python=python)
        except DraftError as e:
            raise fail(e)
        a = r.agy
        info = {"steps": a.steps, "turns": a.turns, "elapsed": round(a.elapsed), "tampered": a.tampered}
        if a.status == "tampered":
            _write_last(r, status="tampered", **info)
            raise PartError("draft_tampered", vi("draft_tampered") + " (" + ", ".join(a.tampered[:5]) + ")")
        if a.status == "cancelled":
            _write_last(r, status="cancelled", **info)
            return
        if a.status == "error":
            _write_last(r, status="error", error=a.error_code, **info)
            raise PartError(a.error_code or "agy_error", vi(a.error_code or "agy_error", a.error_message))
        if a.status == "timeout":
            r.partial = True

    def compile_(ctx):
        from .compile import compile_specs
        from .workspace import read_out
        from bti.engine.storyboard import write_atomic
        if ctx.cancelled():
            return
        try:
            inp = r.inputs
            regions = None
            problems: list = []
            if provider == "agy":
                r.out = read_out(r.ws.root, inp.in_scope(), {**inp.picks["assets"], **((inp.current or {}).get("assets") or {})})
                r.specs, regions, problems, r.notes = r.out.specs, r.out.regions, r.out.problems, r.out.notes
                if not r.specs:
                    raise DraftError("draft_no_output", "no usable chapter file in out/")
                dest = r.cache / "out"
                dest.mkdir(parents=True, exist_ok=True)
                for f in list((r.ws.root / "out").glob("*")):
                    if f.is_file() and not f.is_symlink() and f.suffix in (".json", ".md") and f.stat().st_size < 2_000_000:
                        shutil.copyfile(f, dest / f.name)
            ctx.progress(0.2, "Đang ghép và kiểm tra các cảnh.")
            res = compile_specs(inp, r.specs, regions=regions, spec_problems=problems, degrade=True, draw=True)
        except DraftError as e:
            raise fail(e)
        base_rev = None
        if inp.current:
            from bti.editor.common import compute_rev
            base_rev = compute_rev(inp.current)
        left = [i for i in res.issues if i["level"] == "error" or i.get("code") == "incomplete"]
        notes_line = next((ln.strip(" #\t") for ln in (r.notes or "").splitlines() if ln.strip(" #\t")), "")
        # ONE number everywhere: the shots of the compiled storyboard (what the editor will show), the split said once
        n_all = len(res.storyboard["shots"])
        n_content = len([o for o in res.origin if o["kind"] == "agent"])
        n_cards = max(n_all - n_content, 0)
        summary = notes_line[:200] if (provider == "agy" and notes_line) else \
            "Bản nháp %s: %s" % ("tự động" if provider == "auto" else "của agent", shots_text(n_all, n_content, n_cards))
        if r.partial:
            summary += " (agent hết giờ; các chương thiếu do chế độ tự động dựng)"
        pid_ = "draft_" + r.run_id
        doc = {"id": pid_, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "author": _author(r), "summary": summary, "base_rev": base_rev,
               "storyboard": res.storyboard,
               "made_from": dict(inp.hashes(), base_rev=base_rev), "scope": inp.scope,
               "issues_left": [{"level": i["level"], "code": i["code"], "chapter": i.get("chapter"), "shot": i.get("shot"), "message": i["message"]} for i in left[:200]],
               "degraded": [{"code": i["code"], "message": i["message"]} for i in res.degraded[:100]],
               "stats": res.stats, "notes": (r.notes or "")[:4000]}
        write_atomic(r.project_dir / "proposals" / (pid_ + ".json"), json.dumps(doc, ensure_ascii=False, indent=1))
        info = {"steps": getattr(r.agy, "steps", None), "turns": getattr(r.agy, "turns", None), "elapsed": round(getattr(r.agy, "elapsed", 0) or 0)}
        _write_last(r, status="done", proposal=pid_, n_shots=n_all, n_content=n_content, n_cards=n_cards, errors_left=len([i for i in left if i["level"] == "error"]),
                    incomplete=len([i for i in left if i["level"] != "error"]), degraded=len(res.degraded), partial=r.partial, **info)
        if r.ws is not None:
            shutil.rmtree(r.ws.root, ignore_errors=True)
        _prune(r.project_dir)
        ctx.progress(1.0, "Đã ghi đề xuất %s." % pid_)
        return {"proposal_id": pid_, "n_shots": len(res.storyboard["shots"]), "issues_left": len(left)}

    return [Part(key="prepare", title="Chuẩn bị dữ liệu", run=prepare, est_seconds=20),
            Part(key="agent", title="Dựng tự động" if provider == "auto" else "Agent dựng bản nháp", run=agent,
                 est_seconds=5 if provider == "auto" else 900),
            Part(key="compile", title="Ghép và kiểm tra", run=compile_, est_seconds=60)]


def start(pid: str, project_dir: Path, *, provider: str = "agy", model: str | None = None, chapters: list | None = None, manager=None,
          **kw) -> dict:
    """Start the draft job. Raises DraftError (not ready, agy missing, ...) or bti.longjob.Busy."""
    if provider not in ("agy", "auto"):
        raise DraftError("bad_provider", "provider must be agy or auto")
    if model is not None and not MODEL_RE.fullmatch(model):
        raise DraftError("bad_model", "the model name is not valid")
    if not readiness(project_dir)["ok"]:
        raise DraftError("draft_not_ready", "voice (timing.json) and approved picks (picks.json) are needed first")
    if provider == "agy":
        from .providers import agy
        if not agy.find_agy():
            raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")
    if chapters:
        load_inputs(project_dir, chapters)            # unknown chapter, no storyboard: refused here, not inside the job
    m = manager or _manager()
    return m.start(kind=KIND, pid=pid, project_dir=project_dir, parts=make_parts(project_dir, provider, model, chapters, **kw),
                   meta={"provider": provider, "model": model, "chapters": chapters})
