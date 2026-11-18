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
from .inputs import (DraftError, DraftInputs, canon_hash, load_inputs,
                     normalize_timing, read_json_file, resolve_edit_scope)
from bti.settings import model_for
from .thread import (append_turn, clear_thread, format_previous_exchanges,
                     load_thread, record_acceptance, update_turn)

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
    "edit_outside_scope": "Agent đã thay đổi phần ngoài phạm vi được chỉ định hoặc cảnh đang khóa.",
    "edit_no_storyboard": "Chỉ sửa bằng prompt khi dự án đã có storyboard.",
    "edit_bad_scope": "Phạm vi sửa không hợp lệ (cần chọn cảnh, chương hoặc cả video).",
    "edit_empty_instruction": "Chưa nhập yêu cầu sửa (hãy gõ hướng dẫn cho agent).",
    "edit_needs_agy": "Sửa bằng prompt cần dùng agent agy, không dùng được chế độ tự động.",
    "edit_no_change": "Agent không thay đổi gì trong storyboard.",
    "compile_error": "Không thể ghép các cảnh do có lỗi thông số hoặc cú pháp.",
    "edit_degraded": "Lần sửa bị từ chối vì có cảnh bị hạ cấp hoặc không đầy đủ.",
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

    def __init__(self, project_dir: Path, provider: str, model: str | None, chapters: list | None,
                 instruction: str | None = None, edit_scope: dict | None = None, followup: bool = False,
                 turn_id: str | None = None, base_rev: str | None = None):
        self.project_dir, self.provider, self.model, self.chapters = Path(project_dir), provider, model, chapters
        self.instruction = instruction
        self.edit_scope = edit_scope
        self.followup = followup
        self.turn_id = turn_id
        self.base_rev = base_rev
        self.scope_words = ""
        self.conversation_id_in: str | None = None
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
    m = r.model or model_for("draft")
    slug = m[len("agy:"):] if m.startswith("agy:") else m
    return f"agent:agy:{slug}"


def shots_text(n_all: int, n_content: int, n_cards: int) -> str:
    """'54 cảnh: 48 cảnh nội dung, 6 thẻ': the number of shots of the storyboard, then how it splits."""
    return "%d cảnh: %d cảnh nội dung, %d thẻ" % (n_all, n_content, n_cards)


def _write_last(r: _Run, **kw) -> None:
    from bti.engine.storyboard import write_atomic
    d = {"id": r.run_id, "provider": r.provider, "model": r.model, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "chapters": r.chapters}
    d.update(kw)
    try:
        write_atomic(_cache(r.project_dir) / "last_run.json", json.dumps(d, ensure_ascii=False, indent=1))
        write_atomic(_cache(r.project_dir) / "last_run_draft.json", json.dumps(d, ensure_ascii=False, indent=1))
    except OSError:
        pass


def _write_last_edit(project_dir: Path, turn_id: str | None, **kw) -> None:
    from bti.engine.storyboard import write_atomic
    d = {"turn_id": turn_id, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    d.update(kw)
    try:
        write_atomic(_cache(project_dir) / "last_run_edit.json", json.dumps(d, ensure_ascii=False, indent=1))
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
               guard_factory=None, python: str | None = None, instruction: str | None = None,
               edit_scope: dict | None = None, followup: bool = False, turn_id: str | None = None,
               base_rev: str | None = None):
    """The parts of the job (see the module docstring). `guard_factory(project_dir)` and `python` are for tests."""
    from bti.longjob import Part, PartError
    r = _Run(project_dir, provider, model, chapters, instruction=instruction, edit_scope=edit_scope,
             followup=followup, turn_id=turn_id, base_rev=base_rev)

    def fail(e: DraftError, **kw):
        _write_last(r, status="error", error=e.code, **kw)
        if r.turn_id:
            update_turn(r.project_dir, r.turn_id, status="error", error=e.code)
        return PartError(e.code, vi(e.code, e.message))

    def prepare(ctx):
        from . import workspace
        from .inputs import clone_inputs
        try:
            r.inputs = load_inputs(r.project_dir, chapters, for_edit=(r.instruction is not None))
            if r.instruction is not None:
                if provider != "agy":
                    raise DraftError("edit_needs_agy", "editing by prompt requires the agy agent provider")
                if not r.inputs.current:
                    raise DraftError("scope_needs_storyboard", "editing by prompt requires an existing storyboard")
                from bti.editor.common import compute_rev
                actual_rev = compute_rev(r.inputs.current)
                if r.base_rev is not None and r.base_rev != actual_rev:
                    raise DraftError("stale_revision", "storyboard revision changed before edit preparation")
                r.base_rev = actual_rev
                edit_shots, scope_chapters, scope_words = resolve_edit_scope(r.inputs, r.edit_scope or {})
                r.inputs = clone_inputs(r.inputs, scope=scope_chapters, edit_shots=edit_shots)
                r.scope_words = scope_words
                history = None
                if r.followup:
                    turns = [t for t in load_thread(r.project_dir) if t.get("id") != r.turn_id]
                    r.conversation_id_in = None
                    history = format_previous_exchanges(turns)
                workspace.clean_old()
                r.ws = workspace.build(r.inputs, instruction=r.instruction, scope_words=r.scope_words, history=history, python=python)
            elif provider == "agy":
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
                            transcript_path=r.cache / "events.jsonl", guard=guard, python=python, conversation_id=r.conversation_id_in)
        except DraftError as e:
            raise fail(e)
        a = r.agy
        info = {"steps": a.steps, "turns": a.turns, "elapsed": round(a.elapsed), "tampered": a.tampered}
        if r.turn_id and getattr(r.agy, "conversation_id", None):
            update_turn(r.project_dir, r.turn_id, conversation_id=r.agy.conversation_id)
        if a.status == "tampered":
            _write_last(r, status="tampered", **info)
            if r.turn_id:
                update_turn(r.project_dir, r.turn_id, status="error", error="draft_tampered")
            raise PartError("draft_tampered", vi("draft_tampered") + " (" + ", ".join(a.tampered[:5]) + ")")
        if a.status == "cancelled":
            _write_last(r, status="cancelled", **info)
            if r.turn_id:
                update_turn(r.project_dir, r.turn_id, status="error", error="cancelled")
            return
        if a.status == "error":
            _write_last(r, status="error", error=a.error_code, **info)
            if r.turn_id:
                update_turn(r.project_dir, r.turn_id, status="error", error=a.error_code)
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
                    if problems:
                        if r.instruction is not None:
                            err_msg = problems[0].get("message") if isinstance(problems[0], dict) else str(problems[0])
                            if r.turn_id:
                                update_turn(r.project_dir, r.turn_id, status="error", error="compile_error", notes=r.notes or "")
                            _write_last(r, status="error", error="compile_error")
                            raise PartError("compile_error", vi("compile_error", err_msg))
                        raise DraftError("draft_no_output", "no usable chapter file in out/")
                    if r.instruction is not None and (r.notes and r.notes.strip()):
                        dest = r.cache / "out"
                        dest.mkdir(parents=True, exist_ok=True)
                        for f in list((r.ws.root / "out").glob("*")):
                            if f.is_file() and not f.is_symlink() and f.suffix in (".json", ".md") and f.stat().st_size < 2_000_000:
                                shutil.copyfile(f, dest / f.name)
                        if r.turn_id:
                            update_turn(r.project_dir, r.turn_id, status="no_change", notes=r.notes or "", error=None, proposal_id=None)
                        _write_last(r, status="done", no_change=True)
                        if r.ws is not None:
                            shutil.rmtree(r.ws.root, ignore_errors=True)
                        _prune(r.project_dir)
                        ctx.progress(1.0, vi("edit_no_change", "Agent trả lời bằng ghi chú (không thay đổi storyboard)."))
                        return {"proposal_id": None, "no_change": True, "notes": r.notes}
                    raise DraftError("draft_no_output", "no usable chapter file in out/")
                dest = r.cache / "out"
                dest.mkdir(parents=True, exist_ok=True)
                for f in list((r.ws.root / "out").glob("*")):
                    if f.is_file() and not f.is_symlink() and f.suffix in (".json", ".md") and f.stat().st_size < 2_000_000:
                        shutil.copyfile(f, dest / f.name)
            ctx.progress(0.2, "Đang ghép và kiểm tra các cảnh.")
            is_edit = r.instruction is not None
            res = compile_specs(inp, r.specs, regions=regions, spec_problems=problems, degrade=(not is_edit), draw=True)
        except DraftError as e:
            raise fail(e)
        base_rev = r.base_rev
        if not base_rev and inp.current:
            from bti.editor.common import compute_rev
            base_rev = compute_rev(inp.current)

        if r.instruction is not None:
            # Edit mode semantics
            if res.violations:
                if r.turn_id:
                    update_turn(r.project_dir, r.turn_id, status="refused", error="edit_outside_scope", notes=r.notes or "")
                _write_last(r, status="error", error="edit_outside_scope")
                raise PartError("edit_outside_scope", vi("edit_outside_scope"))

            non_viol_errors = [e for e in res.errors if e not in res.violations and e.get("code") not in ("edit_outside_scope", "edit_locked_changed")]
            if non_viol_errors:
                err_msg = non_viol_errors[0].get("message") or "compile errors in edit"
                if r.turn_id:
                    update_turn(r.project_dir, r.turn_id, status="error", error="compile_error", notes=r.notes or "")
                _write_last(r, status="error", error="compile_error")
                raise PartError("compile_error", vi("compile_error", err_msg))

            if res.degraded:
                if r.turn_id:
                    update_turn(r.project_dir, r.turn_id, status="error", error="edit_degraded", notes=r.notes or "")
                _write_last(r, status="error", error="edit_degraded")
                raise PartError("edit_degraded", "strict edit cannot publish degraded shots")

            from bti.editor.proposals import diff
            changes = diff(inp.current, res.storyboard)
            if not changes:
                if r.turn_id:
                    update_turn(r.project_dir, r.turn_id, status="no_change", notes=r.notes or "", error=None, proposal_id=None)
                _write_last(r, status="done", no_change=True)
                if r.ws is not None:
                    shutil.rmtree(r.ws.root, ignore_errors=True)
                _prune(r.project_dir)
                ctx.progress(1.0, vi("edit_no_change", "Agent không thay đổi gì."))
                return {"proposal_id": None, "no_change": True, "notes": r.notes}

            left = [i for i in res.issues if i["level"] == "error" or i.get("code") == "incomplete"]
            notes_line = next((ln.strip(" #\t") for ln in (r.notes or "").splitlines() if ln.strip(" #\t")), "")
            summary = notes_line[:200] if notes_line else f"Sửa theo prompt: {r.instruction[:60]}"
            pid_ = "edit_" + r.run_id
            doc = {
                "id": pid_,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "author": _author(r),
                "summary": summary,
                "base_rev": base_rev,
                "storyboard": res.storyboard,
                "made_from": dict(inp.hashes(), base_rev=base_rev),
                "scope": inp.scope,
                "issues_left": [{"level": i["level"], "code": i["code"], "chapter": i.get("chapter"), "shot": i.get("shot"), "message": i["message"]} for i in left[:200]],
                "degraded": [{"code": i["code"], "message": i["message"]} for i in res.degraded[:100]],
                "stats": res.stats,
                "notes": (r.notes or "")[:4000],
            }
            write_atomic(r.project_dir / "proposals" / (pid_ + ".json"), json.dumps(doc, ensure_ascii=False, indent=1))
            info = {"steps": getattr(r.agy, "steps", None), "turns": getattr(r.agy, "turns", None), "elapsed": round(getattr(r.agy, "elapsed", 0) or 0)}
            _write_last(r, status="done", proposal=pid_, n_shots=len(res.storyboard["shots"]), degraded=len(res.degraded), partial=r.partial, **info)
            if r.turn_id:
                update_turn(r.project_dir, r.turn_id, status="done", proposal_id=pid_, notes=r.notes or "", error=None)
            if r.ws is not None:
                shutil.rmtree(r.ws.root, ignore_errors=True)
            _prune(r.project_dir)
            ctx.progress(1.0, "Đã ghi đề xuất %s." % pid_)
            return {"proposal_id": pid_, "n_shots": len(res.storyboard["shots"]), "issues_left": len(left)}

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
            Part(key="agent", title="Agent sửa storyboard" if instruction is not None else ("Dựng tự động" if provider == "auto" else "Agent dựng bản nháp"), run=agent,
                 est_seconds=5 if provider == "auto" else 900),
            Part(key="compile", title="Ghép và kiểm tra", run=compile_, est_seconds=60)]


def make_edit_parts(project_dir: Path, *, model: str | None = None, instruction: str,
                    edit_scope: dict | None = None, followup: bool = False,
                    turn_id: str | None = None, base_rev: str | None = None,
                    mode: str = "auto", guard_factory=None, python: str | None = None,
                    agent_timeout: float = AGENT_TIMEOUT_S):
    """The parts of an edit job (fast path or deep agentic path, then direct apply)."""
    from bti.longjob import Part, PartError
    from .inputs import clone_inputs
    from .guard import Guard

    class EditState:
        def __init__(self):
            self.inputs = None
            self.edit_shots = set()
            self.scope_chapters = None
            self.scope_words = ""
            self.chosen_path = mode
            self.escalated = False
            self.compiled_sb = None
            self.summary = ""
            self.model_changes = []
            self.notes = ""
            self.start_time = 0.0

    st = EditState()

    def prepare(ctx):
        st.start_time = time.time()
        st.inputs = load_inputs(project_dir, for_edit=True)
        if not st.inputs.current:
            raise DraftError("scope_needs_storyboard", "editing by prompt requires an existing storyboard")
        from bti.editor.common import compute_rev
        actual_rev = compute_rev(st.inputs.current)
        if base_rev is not None and base_rev != actual_rev:
            raise DraftError("stale_revision", "storyboard revision changed before edit preparation")
        
        edit_shots, scope_chapters, scope_words = resolve_edit_scope(st.inputs, edit_scope or {})
        st.edit_shots = edit_shots
        st.scope_chapters = scope_chapters
        st.scope_words = scope_words

        if mode == "auto":
            st.chosen_path = "fast" if len(edit_shots) <= 12 else "deep"
        else:
            st.chosen_path = mode

        if turn_id:
            update_turn(project_dir, turn_id, path=st.chosen_path)
        ctx.progress(1.0, f"Đã chuẩn bị ({len(edit_shots)} cảnh, chế độ {st.chosen_path}).")

    def edit(ctx):
        guard = guard_factory(project_dir) if guard_factory else Guard(project_dir)

        # 1. Try fast path if chosen
        if st.chosen_path == "fast":
            ctx.progress(0.1, "Đang nghĩ…")
            from bti.draft.fastedit import fast_edit
            m_fast = model or model_for("edit.fast")
            outcome = fast_edit(st.inputs, instruction, st.edit_shots, model=m_fast, guard=guard)
            ctx.progress(0.8, "Đang kiểm tra…")

            if outcome.status == "cannot":
                elapsed = round(time.time() - st.start_time, 2)
                if turn_id:
                    update_turn(project_dir, turn_id, status="no_change", summary=outcome.summary,
                                notes=outcome.summary, seconds=elapsed, path="fast")
                _write_last_edit(project_dir, turn_id, status="done", no_change=True, summary=outcome.summary)
                ctx.progress(1.0, outcome.summary)
                return {"status": "no_change", "no_change": True, "summary": outcome.summary}

            if outcome.status == "escalate":
                if mode == "auto":
                    ctx.progress(0.2, "Chuyển sang phân tích sâu…")
                    st.chosen_path = "deep"
                    st.escalated = True
                    if turn_id:
                        update_turn(project_dir, turn_id, path="deep", escalated=True)
                else:
                    elapsed = round(time.time() - st.start_time, 2)
                    if turn_id:
                        update_turn(project_dir, turn_id, status="failed", error="escalate",
                                    summary=outcome.summary, seconds=elapsed, path="fast")
                    _write_last_edit(project_dir, turn_id, status="error", error="escalate", summary=outcome.summary)
                    raise PartError("escalate", outcome.summary)

            elif outcome.status == "error":
                elapsed = round(time.time() - st.start_time, 2)
                err = outcome.error or "compile_error"
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error=err,
                                summary=outcome.summary, seconds=elapsed, path="fast")
                _write_last_edit(project_dir, turn_id, status="error", error=err)
                raise PartError(err, outcome.summary)

            elif outcome.status == "ok":
                st.compiled_sb = outcome.storyboard
                st.summary = outcome.summary
                st.model_changes = outcome.changes
                return

        # 2. Run deep path if chosen or escalated
        if st.chosen_path == "deep":
            from .providers import agy
            if not agy.find_agy():
                raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")
            from . import workspace
            from .workspace import workspace_compile, read_out
            from .compile import compile_specs, summary_text

            deep_inputs = clone_inputs(st.inputs, scope=st.scope_chapters, edit_shots=st.edit_shots)
            history = None
            if followup:
                turns = [t for t in load_thread(project_dir) if t.get("id") != turn_id]
                history = format_previous_exchanges(turns)

            workspace.clean_old()
            ws = workspace.build(deep_inputs, instruction=instruction, scope_words=st.scope_words, history=history, python=python)

            def on_progress(p):
                ctx.progress(0.05 + 0.9 * min(1.0, p["steps"] / 10), f"Bước {p['steps']}, {p['last_action'] or 'đang chạy'}…")

            def check(turn):
                res, _ = workspace_compile(ws.root, draw=True)
                return summary_text(res) if res.errors else None

            m_deep = model or model_for("edit.deep")
            cache_dir = _cache(project_dir) / time.strftime("%Y%m%d-%H%M%S")
            cache_dir.mkdir(parents=True, exist_ok=True)
            run_res = agy.run(ws.root, model=m_deep, timeout=agent_timeout, check=check, cancel=ctx.cancelled,
                              runner=ctx.run_process, on_progress=on_progress, transcript_path=cache_dir / "events.jsonl",
                              guard=guard, python=python)

            if turn_id and getattr(run_res, "conversation_id", None):
                update_turn(project_dir, turn_id, conversation_id=run_res.conversation_id)

            if run_res.status == "error":
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error=run_res.error_code)
                _write_last_edit(project_dir, turn_id, status="error", error=run_res.error_code)
                raise PartError(run_res.error_code or "agy_error", vi(run_res.error_code or "agy_error", run_res.error_message))
            if run_res.status == "cancelled":
                if turn_id:
                    update_turn(project_dir, turn_id, status="cancelled", error="cancelled")
                return

            out_data = read_out(ws.root, deep_inputs.in_scope(), {**deep_inputs.picks["assets"], **((deep_inputs.current or {}).get("assets") or {})})
            st.notes = out_data.notes

            if not out_data.specs:
                if out_data.notes and out_data.notes.strip():
                    elapsed = round(time.time() - st.start_time, 2)
                    if turn_id:
                        update_turn(project_dir, turn_id, status="no_change", summary=out_data.notes[:200], notes=out_data.notes, seconds=elapsed, path="deep")
                    _write_last_edit(project_dir, turn_id, status="done", no_change=True)
                    ctx.progress(1.0, "Agent không thay đổi gì.")
                    return {"status": "no_change", "no_change": True, "notes": out_data.notes}
                raise DraftError("draft_no_output", "no usable chapter file in out/")

            c_res = compile_specs(deep_inputs, out_data.specs, regions=out_data.regions, spec_problems=out_data.problems, degrade=False, draw=True)
            if c_res.violations:
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error="edit_outside_scope", notes=st.notes or "")
                _write_last_edit(project_dir, turn_id, status="error", error="edit_outside_scope")
                raise PartError("edit_outside_scope", vi("edit_outside_scope"))

            errs = [e for e in c_res.errors if e not in c_res.violations]
            if errs:
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error="compile_error", notes=st.notes or "")
                _write_last_edit(project_dir, turn_id, status="error", error="compile_error")
                raise PartError("compile_error", vi("compile_error", errs[0].get("message") or "compile errors in edit"))

            st.compiled_sb = c_res.storyboard
            notes_file = ws.root / "out" / "notes.json"
            if notes_file.is_file():
                try:
                    nd = json.loads(notes_file.read_text(encoding="utf-8"))
                    st.summary = str(nd.get("summary") or "")
                    if isinstance(nd.get("changes"), list):
                        st.model_changes = nd["changes"]
                except Exception:
                    pass
            if not st.summary:
                first_line = next((ln.strip(" #\t") for ln in (st.notes or "").splitlines() if ln.strip(" #\t")), "")
                st.summary = first_line[:200] if first_line else f"Sửa theo yêu cầu: {instruction[:60]}"

    def apply_(ctx):
        if not st.compiled_sb:
            return
        ctx.progress(0.9, "Đang áp dụng thay đổi…")
        from bti.draft.merge import apply_direct_edit
        res = apply_direct_edit(
            project_dir,
            turn_id or "turn_tmp",
            base_sb=st.inputs.current,
            result_sb=st.compiled_sb,
            model_changes=st.model_changes,
            timing=st.inputs.timing,
            scope_shot_ids=st.edit_shots,
        )
        elapsed = round(time.time() - st.start_time, 2)
        if turn_id:
            update_turn(
                project_dir,
                turn_id,
                status=res["status"],
                before_rev=base_rev,
                after_rev=res.get("after_rev"),
                path=st.chosen_path,
                escalated=st.escalated,
                seconds=elapsed,
                summary=st.summary,
                changes=res.get("changes", []),
                conflicts=res.get("conflicts"),
                notes=st.notes,
            )
        _write_last_edit(project_dir, turn_id, status="done" if res["status"] in ("applied", "no_change") else "needs_choice",
                         changes=len(res.get("changes", [])))
        msg = "Đã áp dụng thay đổi." if res["status"] == "applied" else ("Không có thay đổi." if res["status"] == "no_change" else "Cần lựa chọn ghi đè do xung đột.")
        ctx.progress(1.0, msg)
        return res

    return [
        Part(key="prepare", title="Chuẩn bị dữ liệu", run=prepare, est_seconds=5),
        Part(key="edit", title="Chỉnh sửa storyboard", run=edit, est_seconds=15),
        Part(key="apply", title="Áp dụng thay đổi", run=apply_, est_seconds=5),
    ]


def start(pid: str, project_dir: Path, *, provider: str = "agy", model: str | None = None, chapters: list | None = None,
          instruction: str | None = None, edit_scope: dict | None = None, followup: bool = False,
          base_rev: int | str | None = None, mode: str = "auto", manager=None,
          **kw) -> dict:
    """Start the draft or edit job. Raises DraftError (not ready, agy missing, ...) or bti.longjob.Busy."""
    if instruction is not None:
        if not isinstance(instruction, str) or not instruction.strip():
            raise DraftError("edit_empty_instruction", "instruction cannot be empty")
        if len(instruction) > 2000:
            raise DraftError("edit_bad_scope", "instruction must be 1 to 2000 characters")
        if model is not None and not MODEL_RE.fullmatch(model):
            raise DraftError("bad_model", "the model name is not valid")
        if mode not in ("auto", "fast", "deep"):
            raise DraftError("edit_bad_scope", "mode must be auto, fast, or deep")

        inp = load_inputs(project_dir, for_edit=True)
        if not inp.current:
            raise DraftError("scope_needs_storyboard", "editing by prompt requires an existing storyboard")
        from bti.editor.common import compute_rev
        cur_rev = compute_rev(inp.current)
        if base_rev is not None and base_rev != cur_rev:
            raise DraftError("stale_revision", "storyboard has changed since edit was requested")
        effective_base_rev = base_rev or cur_rev
        edit_shots, scope_chapters, scope_words = resolve_edit_scope(inp, edit_scope or {})

        # E9: For deep path, verify agy availability after validation
        needs_agy_check = (mode == "deep") or (mode == "auto" and len(edit_shots) > 12)
        if needs_agy_check:
            from .providers import agy
            if not agy.find_agy():
                raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")

        turn_id = f"t_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%1000:03d}"
        scope_kind = "shots" if "shots" in (edit_scope or {}) else ("chapter" if "chapter" in (edit_scope or {}) else "all")
        initial_path = "fast" if (mode == "fast" or (mode == "auto" and len(edit_shots) <= 12)) else "deep"
        default_model = model_for("edit.fast" if initial_path == "fast" else "edit.deep")

        turn = {
            "id": turn_id,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "instruction": instruction.strip(),
            "scope": {
                "kind": scope_kind,
                "shots": sorted(edit_shots) if scope_kind == "shots" else None,
                "chapter": (edit_scope or {}).get("chapter") if scope_kind == "chapter" else None,
            },
            "scope_words": scope_words,
            "model": (model if (model and model.startswith("agy:")) else (f"agy:{model}" if model else default_model)),
            "base_rev": effective_base_rev,
            "before_rev": effective_base_rev,
            "after_rev": None,
            "path": initial_path,
            "escalated": False,
            "seconds": 0.0,
            "summary": "",
            "changes": [],
            "status": "running",
            "job_id": None,
            "proposal_id": None,
            "notes": "",
            "conversation_id": None,
            "error": None,
        }

        # E13: Record turn in thread BEFORE job starts
        append_turn(project_dir, turn)

        m = manager or _manager()
        parts = make_edit_parts(project_dir, model=model, instruction=instruction,
                                edit_scope=edit_scope, followup=followup, turn_id=turn_id,
                                base_rev=effective_base_rev, mode=mode, **kw)
        try:
            rec = m.start(kind=KIND, pid=pid, project_dir=project_dir, parts=parts,
                          meta={"provider": provider, "model": model, "mode": "edit", "turn_id": turn_id, "instruction": instruction})
            update_turn(project_dir, turn_id, job_id=rec["id"])
        except Exception as e:
            update_turn(project_dir, turn_id, status="failed", error=getattr(e, "code", "busy") if type(e).__name__ == "Busy" else "start_failed")
            raise
        return {**rec, "turn_id": turn_id}

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
