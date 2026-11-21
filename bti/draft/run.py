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
from .inputs import (NOTE_MAX, DraftError, DraftInputs, canon_hash, clone_inputs, load_inputs,
                     normalize_timing, read_json_file, resolve_edit_scope)
from bti import agents as AG
from bti.settings import model_for
from .thread import (append_turn, clear_thread, format_previous_exchanges,
                     load_thread, record_acceptance, save_thread, thread_lock,
                     turns_dir, update_turn)
from bti.longjob import Part, PartError

KIND = "draft"
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@-]{0,79}")      # `@` is the effort part of a `claude:<model>@<effort>` id
AGENT_TIMEOUT_S = 30 * 60
DEEP_MAX_REPAIRS = 2             # the slow path's check-and-repair turns after its first answer (agy.run / claudecode.run `max_repairs`)
KEEP_RUNS = 5

VI = {
    "draft_not_ready": "Chưa đủ dữ liệu để dựng bản nháp: cần giọng đọc (timing.json) và danh sách hình đã duyệt (picks.json).",
    "agy_missing": "Chưa cài `agy` (Antigravity CLI) trên máy này. Dùng chế độ tự động, hoặc cài agy rồi thử lại.",
    "agy_config": "agy trên máy này không dùng được cho việc này (quá cũ hoặc không chạy được).",
    "agy_busy": "Một lần chạy agent khác đang diễn ra. Đợi nó xong rồi thử lại.",
    "agent_job_running": "Agent đang làm một việc khác cho dự án này (chọn hình, sửa bằng lời, dựng bản nháp hoặc chạy tự động). Chờ xong hoặc bấm Dừng rồi thử lại.",       # join2
    "agy_auth": "agy chưa đăng nhập trong phiên máy đang chạy ứng dụng. Đăng nhập agy một lần rồi thử lại.",
    "agy_rate_limit": "Hạn mức của gói Antigravity đã dùng hết hoặc bị giới hạn. Đợi hết chu kỳ hoặc chọn mô hình khác.",
    "agy_model": "agy không nhận ra tên mô hình này. Chọn mô hình khác trong danh sách.",
    "agy_error": "agy báo lỗi khi chạy.",
    "agy_no_result": "agy dừng mà không trả kết quả.",
    "agy_timeout": "Agent chạy quá thời gian cho phép nên đã bị dừng.",
    # worker claudeprov: the second runner, Claude Code (`claude`)
    "claude_missing": "Chưa cài Claude Code (lệnh `claude`) trên máy chủ. Cài Claude Code, đăng nhập một lần bằng lệnh `claude auth login`, rồi thử lại.",
    "claude_auth": "Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại.",
    "claude_rate_limit": "Hạn mức của gói Claude Code đã dùng hết hoặc bị giới hạn. Đợi hết chu kỳ hoặc chọn agent khác.",
    "claude_model": "Claude Code không nhận ra tên mô hình này. Chọn mô hình khác.",
    "claude_config": "Claude Code trên máy chủ không dùng được cho việc này (quá cũ hoặc không chạy được). Chạy `claude update` trên máy chủ rồi thử lại.",
    "claude_outdated": "Claude Code trên máy chủ quá cũ cho mô hình này. Chạy `claude update` trên máy chủ rồi thử lại.",       # the runner's own sentence adds the versions the answer stated
    "claude_error": "Claude Code báo lỗi khi chạy.",
    "claude_no_result": "Claude Code dừng mà không trả kết quả.",
    "claude_timeout": "Agent chạy quá thời gian cho phép nên đã bị dừng.",
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
    "draft_note_too_long": "Ghi chú cho bản nháp quá dài (tối đa 600 ký tự). Hãy rút gọn rồi dựng lại.",       # fixdraft
    "draft_note_invalid": "Ghi chú cho bản nháp phải là chữ. Hãy gõ lại rồi dựng lại.",                          # fixdraft
    "edit_needs_agy": "Sửa bằng prompt cần dùng agent agy, không dùng được chế độ tự động.",
    "edit_no_change": "Agent không thay đổi gì trong storyboard.",
    "compile_error": "Không thể ghép các cảnh do có lỗi thông số hoặc cú pháp.",
    "edit_degraded": "Lần sửa bị từ chối vì có cảnh bị hạ cấp hoặc không đầy đủ.",
    "spec_invalid": "Agent trả lời sai dạng cần thiết, kể cả sau một lần chỉnh lại, nên chưa đổi gì. Hãy gửi lại yêu cầu.",
    "escalate": "Yêu cầu này cần nhìn kỹ vào tranh hoặc sửa nhiều hơn phần đã chọn. Bấm \"Làm kỹ hơn\" để agent làm trong vài phút.",
    "real_models_off": "Máy này đang tắt việc gọi mô hình thật (chế độ thử), nên chưa sửa được.",
    "bad_model": "Mô hình đã chọn không dùng được. Chọn mô hình khác trong phần cài đặt.",
    "edit_failed": "Lần sửa gặp lỗi bất ngờ nên chưa có gì thay đổi. Hãy thử lại.",
    "cannot": "Yêu cầu này cần thứ mà dự án chưa có (ví dụ một bức tranh mới, hoặc đổi lời dẫn hay giọng đọc), nên chưa làm được.",
}

# what a single-turn provider's error kind is called for the owner (codes the page already has a sentence for)
PROVIDER_CODES = {"auth": "agy_auth", "rate_limit": "agy_rate_limit", "timeout": "agy_timeout", "config": "agy_config",
                  "real_models_off": "real_models_off", "empty": "agy_no_result", "http": "agy_error", "blocked": "agy_error"}


RATE_LIMIT_CODES = ("agy_rate_limit", "claude_rate_limit")


def provider_code(e, model_id: str | None) -> str:
    """The owner-facing code of a single-call provider error: the runner's own (`e.code`, set by the Claude Code provider), else the
    kind's code of the other runner."""
    return getattr(e, "code", None) or PROVIDER_CODES.get(getattr(e, "kind", None), "agy_error")


def _bad_model_name(model: str | None) -> bool:
    """A model name the request may not carry: not a plain id, or an id of the `claude:` family that is not `claude:<model>@<effort>`."""
    return model is not None and (not MODEL_RE.fullmatch(model) or (model.startswith("claude:") and not _is_claude(model)))


def _is_claude(model_id: str | None) -> bool:
    from bti.script.providers.claudecode import is_claude_id
    return is_claude_id(model_id)


def agy_mod():
    from .providers import agy
    return agy


def _agent_module(model_id: str | None):
    """The runner of an agent model id: the Claude Code one for `claude:<model>@<effort>`, else the Antigravity one (`agy:<slug>`)."""
    if _is_claude(model_id):
        from .providers import claudecode
        return claudecode
    from .providers import agy
    return agy


def _check_agent_installed(model_id: str | None) -> None:
    """Before a job starts: the runner of this model must be installed, and Claude Code must not be known to be signed out."""
    if _is_claude(model_id):
        from .providers import claudecode
        if not claudecode.find_claude():
            raise DraftError("claude_missing", "Claude Code (the `claude` command) is not installed on this machine")
        from bti.script import models as models_mod
        info = models_mod.claude_status()
        if not info["ok"]:
            info = models_mod.claude_status(refresh=True)         # the owner may have signed in since the answer was cached
        if not info["ok"] and info["reason"] == "not_signed_in":
            raise DraftError("claude_auth", "Claude Code is not signed in on this machine")
        return
    from .providers import agy
    if not agy.find_agy():
        raise DraftError("agy_missing", "agy (the Antigravity CLI) is not installed on this machine")


def _norm_model(model: str | None) -> str | None:
    """One id form: a bare slug is an Antigravity model (`agy:<slug>`); ids that are configured models (`mock`, ...) stay."""
    if not model or model.startswith("agy:"):
        return model
    from bti.script import models as models_mod
    return model if models_mod.resolve(model) is not None else "agy:" + model


def _resolve(project_dir: Path, role: str, model: str | None) -> "AG.Resolved":
    """The model of a call of `role` for this project: the one the request names, else the project's agent (`bti.agents`, contract section 4)."""
    return AG.model_for_project(project_dir, role, _norm_model(model))


def rate_limit_fields(seconds: int | None) -> dict:
    """`retry_after_seconds` and `retry_at` (a local clock time) for a quota that resets in `seconds`; {} when agy printed no time."""
    if not seconds:
        return {}
    from bti.script.providers.antigravity import retry_at
    return {"retry_after_seconds": int(seconds), "retry_at": retry_at(int(seconds))}


def rate_limit_sentence(code: str, seconds: int | None, message: str = "") -> str:
    """The owner's sentence for a failure: the code's own sentence, with when to try again for a quota."""
    base = vi(code, message) if code == "claude_outdated" else vi(code)
    if code not in RATE_LIMIT_CODES or not seconds:
        return base
    from bti.script.providers.antigravity import retry_at, wait_words
    plan = "Claude Code" if code == "claude_rate_limit" else "Antigravity"
    return "Hạn mức của gói %s đã hết. Thử lại sau %s (khoảng %s)." % (plan, wait_words(int(seconds)), retry_at(int(seconds)))


def _fail_turn(project_dir: Path, turn_id: str | None, code: str, summary: str, *, start: float | None = None,
               path: str | None = None, notes: str = "", retry_after_seconds: int | None = None) -> None:
    """The turn's record of a failure: the code and one Vietnamese sentence (never empty), and the last-run record of the edit."""
    if turn_id:
        upd = {"status": "failed", "error": code, "summary": summary}
        if start:
            upd["seconds"] = round(time.time() - start, 2)
        if path:
            upd["path"] = path
        if notes:
            upd["notes"] = notes[:2000]
        upd.update(rate_limit_fields(retry_after_seconds))
        update_turn(project_dir, turn_id, **upd)
    _write_last_edit(project_dir, turn_id, status="error", error=code)


def vi(code: str, fallback: str = "") -> str:
    if code == "claude_outdated":          # the runner's message is already the owner's sentence, with the versions the answer stated
        from bti.script.providers.claudecode import OUTDATED_HEAD
        if fallback.startswith(OUTDATED_HEAD):
            return fallback
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


def last_run_edit(project_dir: Path) -> dict | None:
    f = _cache(project_dir) / "last_run_edit.json"
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


def other_agent_job(pid: str, own_kind: str, manager=None, *, run_ok: bool = False) -> dict | None:
    """join2: the long job of another kind that holds the one agent run of this project, else None. The jobs that run an agent are the `draft`
    jobs (the storyboard draft and the prompt-box turns of both steps), the pictures agent (a `picks` job whose `meta.action` is `auto`) and an
    automatic run (kind `auto`: it takes the other three over by itself, step by step): they run one at a time, so a job of one of those kinds does
    not start while one of another kind runs (a job of its own kind is the long-job manager's `Busy`). `run_ok`: the caller IS the automatic run
    (it starts the work of its own job), so its own job is not a reason to refuse."""
    m = manager or _manager()
    if m is None:
        return None
    for kind in (KIND, "picks", "auto", "title"):          # titlestep: the title writer (kind `title`) is an agent run too
        if kind == own_kind or (kind == "auto" and run_ok):
            continue
        try:
            rec = m.active(pid, kind)
        except Exception:       # noqa: BLE001 - a registry that cannot answer never blocks a start
            continue
        if rec and (kind != "picks" or (rec.get("meta") or {}).get("action") == "auto"):
            return rec
    return None


AGENT_JOB_WHO = {"auto": "an automatic run", "picks": "the pictures agent", "draft": "a prompt-box turn or a draft", "title": "the title writer"}


def refuse_while_agent_busy(pid: str, manager=None, *, run_ok: bool = False) -> None:
    """Raise `agent_job_running` (a DraftError) when another agent job (the pictures agent, an automatic run) is working on this project; the draft and the
    prompt boxes call it first. `run_ok`: the automatic run's own job does not count (it is the run that calls)."""
    other = other_agent_job(pid, KIND, manager, run_ok=run_ok)
    if other is not None:
        raise DraftError("agent_job_running", "%s is working on this project: wait for it or cancel it, then call again" % AGENT_JOB_WHO.get(other.get("kind"), "another job"),
                         job_id=other.get("id"))


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


def overview(pid: str, project_dir: Path, default_model: str | None = None) -> dict:
    """What the panel shows. `default_model` and `agent` are the model and the agent the next draft will use (the project's choice for the
    storyboard step, else the project's agent, the machine's default, the role's setting)."""
    st = state(project_dir)
    res = _resolve(project_dir, "draft", None)
    return {"ready": readiness(project_dir), "state": st, "last_run": last_run(project_dir), "default_model": default_model or res.model,
            "agent": res.public(), "providers": ["agy", "auto"], "job_id": st.get("job_id")}


# ------------------------------------------------------------------------------------------------ the job
class _Run:
    """What the three parts share."""

    def __init__(self, project_dir: Path, provider: str, model: str | None, chapters: list | None,
                 instruction: str | None = None, edit_scope: dict | None = None, followup: bool = False,
                 turn_id: str | None = None, base_rev: str | None = None, note: str | None = None):
        self.project_dir, self.provider, self.model, self.chapters = Path(project_dir), provider, model, chapters
        self.note = note                                    # the owner's wish for this draft (`draft.start`); None for an edit
        self.instruction = instruction
        self.edit_scope = edit_scope
        self.followup = followup
        self.turn_id = turn_id
        self.base_rev = base_rev
        self.scope_words = ""
        self.conversation_id_in: str | None = None
        self.run_id = time.strftime("%Y%m%d-%H%M%S")
        # the model and agent of this run (the request's model, else the project's agent); the "auto" provider has none
        self.resolved = _resolve(self.project_dir, "draft", model) if provider != "auto" else None
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
    m = r.resolved.model if r.resolved else (r.model or model_for("draft"))
    if _is_claude(m):
        return f"agent:{m}"
    slug = m[len("agy:"):] if m.startswith("agy:") else m
    return f"agent:agy:{slug}"


def shots_text(n_all: int, n_content: int, n_cards: int) -> str:
    """'54 cảnh: 48 cảnh nội dung, 6 thẻ': the number of shots of the storyboard, then how it splits."""
    return "%d cảnh: %d cảnh nội dung, %d thẻ" % (n_all, n_content, n_cards)


def _write_last(r: _Run, **kw) -> None:
    from bti.engine.storyboard import write_atomic
    d = {"id": r.run_id, "provider": r.provider, "model": r.resolved.model if r.resolved else r.model,
         "agent": r.resolved.public() if r.resolved else None, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "chapters": r.chapters}
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


def _chapters_written(r: "_Run", n_json: int, n_ch: int) -> int:
    """How many of the chapters in scope have their file in out/: out/ also holds regions.json (and, in edit mode, notes.json), so the count of
    *.json files can be one more than there are chapters ("9/8 chapters"). Never more than `n_ch`."""
    try:
        out = Path(r.ws.root) / "out"
        return min(n_ch, sum(1 for c in r.inputs.in_scope() if (out / ("%s.json" % c)).is_file()))
    except (AttributeError, OSError):
        return min(n_ch, n_json)


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
               base_rev: str | None = None, note: str | None = None):
    """The parts of the job (see the module docstring). `guard_factory(project_dir)` and `python` are for tests."""
    from bti.longjob import Part, PartError
    r = _Run(project_dir, provider, model, chapters, instruction=instruction, edit_scope=edit_scope,
             followup=followup, turn_id=turn_id, base_rev=base_rev, note=note)

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
                r.ws = workspace.build(r.inputs, python=python, note=r.note)
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
            from .guard import Guard
            from .workspace import workspace_compile
            m_agent = r.resolved.model                          # the request's model, else the project's agent
            agent_mod = _agent_module(m_agent)                  # agy for `agy:<slug>`, Claude Code for `claude:<model>@<effort>`
            guard = guard_factory(r.project_dir) if guard_factory else Guard(r.project_dir)
            n_ch = max(1, len(r.inputs.in_scope()))

            def on_progress(p):
                done = _chapters_written(r, p["out_files"], n_ch)
                frac = 0.05 + 0.9 * min(1.0, done / n_ch)
                ctx.progress(frac, "Bước %d, %s; đã viết %d/%d chương." % (p["steps"], p["last_action"] or "đang bắt đầu", done, n_ch))

            def check(turn):
                res, _ = workspace_compile(r.ws.root, draw=True)
                from bti.engine.viewchecks import CODES as VIEWER_CODES      # fixdraft: the looks the owner rejects are sent back too, not only the errors
                viewer = sorted({w["code"] for w in res.warnings if w.get("code") in VIEWER_CODES})
                ctx.log("check after turn %d: %d errors, %d warnings (%d of them looks the owner rejects)" % (turn, len(res.errors), len(res.warnings), len(viewer)))
                if not res.errors and not viewer:
                    return None
                from .compile import summary_text
                text = summary_text(res)
                if viewer:
                    text += "\nThe warnings %s are looks the owner rejects (see section 1, rules 13 to 17): fix them too." % ", ".join(viewer)
                return text

            r.cache.mkdir(parents=True, exist_ok=True)
            r.agy = agent_mod.run(r.ws.root, model=m_agent, timeout=agent_timeout, check=check, cancel=ctx.cancelled,
                                  runner=ctx.run_process, on_progress=on_progress, transcript_path=r.cache / "events.jsonl", guard=guard, python=python,
                                  conversation_id=r.conversation_id_in)
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
            wait = a.retry_after_seconds if a.error_code in RATE_LIMIT_CODES else None
            _write_last(r, status="error", error=a.error_code, **rate_limit_fields(wait), **info)
            if r.turn_id:
                update_turn(r.project_dir, r.turn_id, status="error", error=a.error_code, **rate_limit_fields(wait))
            ctx.meta.update(rate_limit_fields(wait))
            raise PartError(a.error_code or "agy_error", rate_limit_sentence(a.error_code, wait) if a.error_code in RATE_LIMIT_CODES else vi(a.error_code or "agy_error", a.error_message))
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


def deep_limits(agent_timeout: float = AGENT_TIMEOUT_S) -> dict:
    """What bounds a slow-path run, told to the card when the run starts: the agent is stopped after `minutes` of working (the watchdog of
    `bti.draft.providers.agy` / `claudecode`), it is sent back at most `repairs` times after its first answer, and the job part may not last
    longer than `part_minutes` (`bti.longjob.manager.PART_LIMIT_SECONDS`). The owner can stop it at any time."""
    from bti.longjob.manager import PART_LIMIT_SECONDS
    return {"minutes": int(agent_timeout // 60), "repairs": DEEP_MAX_REPAIRS, "part_minutes": int(PART_LIMIT_SECONDS // 60)}


def provider_failed(project_dir: Path, turn_id: str | None, ctx, e, model_id: str | None, start_time: float, path: str):
    """A single-call model that could not answer (no login, quota, time out, cancelled): the turn fails with the owner's sentence."""
    if e.kind == "cancelled":
        if turn_id:
            update_turn(project_dir, turn_id, status="cancelled", error="cancelled")
        return None
    code = provider_code(e, model_id)
    wait = getattr(e, "retry_after_seconds", None) if code in RATE_LIMIT_CODES else None
    words = rate_limit_sentence(code, wait, e.message)
    ctx.meta.update(rate_limit_fields(wait))            # the job's own record carries it too (never retried in this job)
    _fail_turn(project_dir, turn_id, code, words, start=start_time, path=path, notes=e.message, retry_after_seconds=wait)
    raise PartError(code, words)


def finish_box_turn(project_dir: Path, turn_id: str | None, ctx, kind: str, res, backend, timing: dict | None, start_time: float, path: str):
    """Record the end of a box turn in the thread and give the job its small result. `res` is a `boxops.TurnResult`. An applied turn carries
    its batch (the card's undo is the undo of that batch), the batch's own sentences and the summary; `cannot` changes nothing and says why;
    `escalate` offers the slower path; a failure carries the code and one Vietnamese sentence."""
    from . import boxops
    elapsed = round(time.time() - start_time, 2)
    base = {"seconds": elapsed, "path": path, "doc": kind, "repairs": res.repairs}
    last = (lambda **kw: _write_last_edit(project_dir, turn_id, **kw)) if kind == "storyboard" else (lambda **kw: None)
    if res.status == "applied":
        if turn_id:
            update_turn(project_dir, turn_id, **{**base, **boxops.applied_fields(kind, backend, res, timing)}, escalated=False, error=None, conflicts=None)
        last(status="done", changes=len(res.changes))
        ctx.progress(1.0, "Đã áp dụng thay đổi.")
        return {"status": "applied", "no_change": False, "after_rev": res.rev_after, "summary": res.summary, "n_changes": len(res.changes),
                "batch": res.batch}
    if res.status in ("cannot", "escalate"):
        said = (res.reason or "").strip()
        words = said or vi(res.status)              # a reason that is not in the owner's language was sent back once; if it still is not, a fixed sentence
        unfit = said or str((res.refusal or {}).get("reason_unfit") or "")
        status = "no_change" if res.status == "cannot" else "escalate"
        if turn_id:
            update_turn(project_dir, turn_id, **base, status=status, summary=words, summary_source="model" if said else "code", reason=words,
                        notes=unfit[:2000], error=None)
        last(status="done", no_change=True, summary=words)
        ctx.progress(1.0, words)
        return {"status": status, "no_change": status == "no_change", "summary": words}
    if res.status == "no_change":
        words = vi("edit_no_change")
        if turn_id:
            update_turn(project_dir, turn_id, **base, status="no_change", summary=words, summary_source="code", error=None)
        last(status="done", no_change=True)
        ctx.progress(1.0, words)
        return {"status": "no_change", "no_change": True, "summary": words}
    code = res.code or "edit_failed"
    words = res.words or vi(code)
    if turn_id:
        update_turn(project_dir, turn_id, doc=kind, repairs=res.repairs)
    _fail_turn(project_dir, turn_id, code, words, start=start_time, path=path, notes=json.dumps(res.refusal, ensure_ascii=False)[:2000] if res.refusal else "")
    raise PartError(code, words)


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
            self.done = False                     # the fast path wrote its batch in the edit part: nothing is left for the apply part
            self.deep_model = None
            self.compiled_sb = None
            self.summary = ""
            self.model_changes = []
            self.notes = ""
            self.start_time = 0.0

    st = EditState()

    def guarded(fn):
        """An error nobody planned for (a bug, a full disk) must still leave the turn `failed` with a sentence the owner can read,
        not `running` until the thread is next read."""
        def run_part(ctx):
            try:
                return fn(ctx)
            except PartError:
                raise
            except DraftError as e:
                _fail_turn(project_dir, turn_id, e.code, vi(e.code, e.message), start=st.start_time or None)
                raise PartError(e.code, vi(e.code, e.message))
            except Exception as e:      # noqa: BLE001
                from bti.longjob import Cancelled
                if isinstance(e, Cancelled):
                    raise
                _fail_turn(project_dir, turn_id, "edit_failed", vi("edit_failed"), start=st.start_time or None,
                           notes="%s: %s" % (type(e).__name__, str(e)[:300]))
                raise
        run_part.__name__ = fn.__name__
        return run_part

    def prepare(ctx):
        st.start_time = time.time()
        try:
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
        except DraftError as e:
            _write_last_edit(project_dir, turn_id, status="error", error=e.code)
            if turn_id:
                update_turn(project_dir, turn_id, status="failed", error=e.code, summary=vi(e.code, e.message))
            raise PartError(e.code, vi(e.code, e.message))

        if mode == "auto":
            st.chosen_path = "deep" if (python is not None or guard_factory is not None or len(edit_shots) > 12) else "fast"
        else:
            st.chosen_path = mode

        if turn_id:
            update_turn(project_dir, turn_id, path=st.chosen_path, **({"limits": deep_limits(agent_timeout)} if st.chosen_path == "deep" else {}))
        ctx.progress(1.0, f"Đã chuẩn bị ({len(edit_shots)} cảnh, chế độ {st.chosen_path}).")

    def edit(ctx):
        # 1. The fast path: one model call, typed operations, one batch (bti/draft/boxops.py)
        if st.chosen_path == "fast":
            ctx.progress(0.1, "Đang nghĩ…")
            from bti.draft import boxops, fastedit
            from bti.script.providers import ProviderError
            m_fast = _resolve(project_dir, "edit.fast", model).model
            fast_inp = clone_inputs(st.inputs, scope=st.scope_chapters, edit_shots=st.edit_shots)
            prior = [t for t in load_thread(project_dir) if t.get("id") != turn_id]
            backend = boxops.Backend(project_dir)
            try:
                res, _scope = fastedit.fast_edit(backend, fast_inp, edit_scope or {}, instruction, model=m_fast, thread_turns=prior,
                                                 progress=ctx.progress, cancel=ctx.cancelled)
            except ProviderError as e:
                return provider_failed(project_dir, turn_id, ctx, e, m_fast, st.start_time, "fast")
            except DraftError as e:
                _fail_turn(project_dir, turn_id, e.code, vi(e.code, e.message), start=st.start_time, path="fast")
                raise PartError(e.code, vi(e.code, e.message))
            st.done = True
            return finish_box_turn(project_dir, turn_id, ctx, "storyboard", res, backend, st.inputs.timing, st.start_time, "fast")

        # 2. The slow path: an agent in a work folder; its result is put on the storyboard by apply_ as operations
        if st.chosen_path == "deep":
            res_deep = _resolve(project_dir, "edit.deep", model)
            m_deep = res_deep.model
            st.deep_model = m_deep
            if turn_id:                                         # an edit that escalated from the fast path says which agent did the deep part
                update_turn(project_dir, turn_id, model=m_deep, agent=res_deep.public())
            deep_mod = _agent_module(m_deep)                    # agy for `agy:<slug>`, Claude Code for `claude:<model>@<effort>`
            try:
                _check_agent_installed(m_deep)
            except DraftError as e:
                _fail_turn(project_dir, turn_id, e.code, vi(e.code, e.message), start=st.start_time, path="deep")
                raise PartError(e.code, vi(e.code, e.message))
            from . import workspace
            from .workspace import workspace_compile, read_out
            from .compile import compile_specs, summary_text

            guard = guard_factory(project_dir) if guard_factory else Guard(project_dir)      # the deep run only
            deep_inputs = clone_inputs(st.inputs, scope=st.scope_chapters, edit_shots=st.edit_shots)
            
            # E6: Continue conversation if previous deep turn < 2 hours old, else copy last 3 turns
            conv_id = None
            turns = load_thread(project_dir)
            now_ts = time.time()
            for t in reversed(turns if deep_mod is agy_mod() else []):         # a Claude Code run keeps no session: its context is rebuilt from the thread
                if t.get("id") != turn_id and t.get("conversation_id") and t.get("at"):
                    try:
                        t_struct = time.strptime(t["at"][:19], "%Y-%m-%dT%H:%M:%S")
                        diff_s = now_ts - time.mktime(t_struct)
                        if 0 <= diff_s < 2 * 3600:
                            conv_id = t["conversation_id"]
                            break
                    except Exception:
                        pass
            history = None
            if not conv_id:
                history = format_previous_exchanges(turns, limit=3)

            workspace.clean_old()
            ws = workspace.build(deep_inputs, instruction=instruction, scope_words=st.scope_words, history=history, python=python)

            def preserve_out():
                if turn_id and ws and (ws.root / "out").is_dir():
                    dest = turns_dir(project_dir) / turn_id / "out"
                    dest.mkdir(parents=True, exist_ok=True)
                    for f in (ws.root / "out").glob("*"):
                        if f.is_file() and not f.is_symlink():
                            try:
                                shutil.copyfile(f, dest / f.name)
                            except OSError:
                                pass

            def on_progress(p):
                ctx.progress(0.05 + 0.9 * min(1.0, p["steps"] / 10), f"Bước {p['steps']}, {p['last_action'] or 'đang chạy'}…")

            def check(turn):
                res, _ = workspace_compile(ws.root, draw=True)
                if res.violations:
                    v_shots = sorted({str(v.get("shot_id") or v.get("shot")) for v in res.violations if (v.get("shot_id") or v.get("shot"))})
                    return f"Scope violation: you modified shots outside the allowed scope ({', '.join(v_shots)}). Keep them unchanged."
                if res.errors:
                    return summary_text(res)
                return None

            cache_dir = _cache(project_dir) / time.strftime("%Y%m%d-%H%M%S")
            cache_dir.mkdir(parents=True, exist_ok=True)
            run_res = deep_mod.run(ws.root, model=m_deep, timeout=agent_timeout, max_repairs=DEEP_MAX_REPAIRS, check=check, cancel=ctx.cancelled,
                              runner=ctx.run_process, on_progress=on_progress, transcript_path=cache_dir / "events.jsonl",
                              guard=guard, python=python, conversation_id=conv_id)

            if turn_id and getattr(run_res, "conversation_id", None):
                update_turn(project_dir, turn_id, conversation_id=run_res.conversation_id)

            if run_res.status == "tampered":        # nothing is taken from a run that touched files outside its folder
                preserve_out()
                msg = vi("draft_tampered") + " (" + ", ".join(run_res.tampered[:5]) + ")"
                _fail_turn(project_dir, turn_id, "draft_tampered", msg, start=st.start_time, path="deep", notes=run_res.error_message)
                raise PartError("draft_tampered", msg)
            if run_res.status in ("error", "timeout"):     # a run that did not finish applies nothing (a draft may use a partial result, an edit may not)
                preserve_out()
                code = run_res.error_code or "agy_error"
                wait = getattr(run_res, "retry_after_seconds", None) if code in RATE_LIMIT_CODES else None
                msg = rate_limit_sentence(code, wait) if code in RATE_LIMIT_CODES else vi(code, run_res.error_message)
                ctx.meta.update(rate_limit_fields(wait))
                _fail_turn(project_dir, turn_id, code, msg, start=st.start_time, path="deep", notes=run_res.error_message, retry_after_seconds=wait)
                raise PartError(code, msg)
            if run_res.status == "cancelled":
                preserve_out()
                if turn_id:
                    update_turn(project_dir, turn_id, status="cancelled", error="cancelled")
                return

            preserve_out()
            out_data = read_out(ws.root, deep_inputs.in_scope(), {**deep_inputs.picks["assets"], **((deep_inputs.current or {}).get("assets") or {})})
            st.notes = out_data.notes

            if not out_data.specs:
                if out_data.problems:
                    err_msg = out_data.problems[0].get("message") if isinstance(out_data.problems[0], dict) else str(out_data.problems[0])
                    if turn_id:
                        update_turn(project_dir, turn_id, status="failed", error="compile_error", summary=vi("compile_error"), notes=st.notes or "")
                    _write_last_edit(project_dir, turn_id, status="error", error="compile_error")
                    raise PartError("compile_error", vi("compile_error", err_msg))
                if out_data.notes and out_data.notes.strip():
                    elapsed = round(time.time() - st.start_time, 2)
                    if turn_id:
                        from bti.draft.describe import sentence_ok
                        said = out_data.notes.strip().splitlines()[0][:200] if out_data.notes.strip() else ""
                        update_turn(project_dir, turn_id, status="no_change", summary=said if sentence_ok(said) else vi("edit_no_change"),
                                    summary_source="model" if sentence_ok(said) else "code", notes=out_data.notes, seconds=elapsed, path="deep")
                    _write_last_edit(project_dir, turn_id, status="done", no_change=True)
                    ctx.progress(1.0, "Agent không thay đổi gì.")
                    return {"status": "no_change", "no_change": True, "notes": out_data.notes}
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error="draft_no_output", summary=vi("draft_no_output"))
                _write_last_edit(project_dir, turn_id, status="error", error="draft_no_output")
                raise PartError("draft_no_output", vi("draft_no_output"))

            c_res = compile_specs(deep_inputs, out_data.specs, regions=out_data.regions, spec_problems=out_data.problems, degrade=False, draw=True)
            if c_res.violations:
                num_map = {s["id"]: i + 1 for i, s in enumerate(deep_inputs.current.get("shots", [])) if s.get("id")}
                shot_ids = set()
                for v in c_res.violations:
                    sid = v.get("shot_id")
                    if not sid and "shot " in v.get("message", ""):
                        m = re.search(r"shot\s+([a-zA-Z0-9_-]+)", v["message"])
                        if m:
                            sid = m.group(1)
                    if sid:
                        shot_ids.add(sid)
                shot_nums = sorted({num_map[sid] for sid in shot_ids if sid in num_map})
                if shot_nums:
                    if len(shot_nums) == 1:
                        c_text = f"Cảnh {shot_nums[0]}"
                    else:
                        c_text = f"Cảnh {', '.join(str(n) for n in shot_nums[:-1])} và {shot_nums[-1]}"
                    viol_msg = f"{c_text} nằm ngoài phần bạn chọn."
                else:
                    viol_msg = vi("edit_outside_scope")
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error="edit_outside_scope", summary=viol_msg, notes=st.notes or "")
                _write_last_edit(project_dir, turn_id, status="error", error="edit_outside_scope")
                raise PartError("edit_outside_scope", viol_msg)

            errs = [e for e in c_res.errors if e not in c_res.violations]
            if errs:
                if turn_id:
                    update_turn(project_dir, turn_id, status="failed", error="compile_error", summary=vi("compile_error"), notes=st.notes or "")
                _write_last_edit(project_dir, turn_id, status="error", error="compile_error")
                raise PartError("compile_error", vi("compile_error", errs[0].get("message") or "compile errors in edit"))

            from .normalize import keep_saved
            from bti.engine import registry as _R
            st.compiled_sb = keep_saved(deep_inputs.current, c_res.storyboard, _R.load_bundle(deep_inputs.style))
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
        """The slow path's result goes onto the storyboard as ONE batch of `replace_range` operations (change log, actor, note, undo), after the
        three-way merge that keeps what the owner saved meanwhile (bti.draft.boxops.apply_deep)."""
        if st.done or not st.compiled_sb:
            return
        ctx.progress(0.9, "Đang áp dụng thay đổi…")
        from bti.draft import boxops
        from bti.draft.thread import save_turn_storyboards
        from bti.ops.errors import OpError
        backend = boxops.Backend(project_dir)
        try:
            res = boxops.apply_deep(backend, base_sb=st.inputs.current, result_sb=st.compiled_sb, scope_ids=st.edit_shots, timing=st.inputs.timing,
                                    instruction=instruction, actor="agent:" + (st.deep_model or "agent"), model_changes=st.model_changes)
        except OpError as e:
            words = boxops.refusal_words("storyboard", e.code, e.extra, st.inputs.current)
            _fail_turn(project_dir, turn_id, e.code, words, start=st.start_time, path=st.chosen_path)
            raise PartError(e.code, words)
        elapsed = round(time.time() - st.start_time, 2)
        status = res["status"]
        if status == "failed":
            words = vi(res.get("code") or "compile_error", res.get("detail") or "")
            _fail_turn(project_dir, turn_id, res.get("code") or "compile_error", words, start=st.start_time, path=st.chosen_path, notes=res.get("detail") or "")
            raise PartError(res.get("code") or "compile_error", words)
        from bti.draft.describe import summary_for
        if status == "no_change":
            summary, summary_source = vi("edit_no_change"), "code"
        else:       # the model's sentence when it is plain Vietnamese without codes, else one built from the changes
            summary, summary_source = summary_for(st.summary, res.get("changes", []))
        if status == "needs_choice":
            save_turn_storyboards(project_dir, turn_id or "turn_tmp", st.inputs.current, st.compiled_sb)         # `resolve` (overwrite) reads them
        if turn_id:
            update_turn(project_dir, turn_id, status=status, doc="storyboard", before_rev=base_rev, after_rev=res.get("after_rev"), path=st.chosen_path,
                        escalated=st.escalated, seconds=elapsed, summary=summary, summary_source=summary_source, changes=res.get("changes", []),
                        conflicts=res.get("conflicts"), notes=st.notes, batch=res.get("batch"), batch_changes=res.get("batch_changes") or [])
        _write_last_edit(project_dir, turn_id, status="done" if status in ("applied", "no_change") else "needs_choice",
                         changes=len(res.get("changes", [])))
        msg = "Đã áp dụng thay đổi." if status == "applied" else ("Không có thay đổi." if status == "no_change" else "Cần lựa chọn ghi đè do xung đột.")
        ctx.progress(1.0, msg)
        # the job's result is small: the batch and its sentences live in the change log
        return {"status": status, "no_change": status == "no_change", "after_rev": res.get("after_rev"), "summary": summary,
                "n_changes": len(res.get("changes", [])), "batch": res.get("batch")}

    return [
        Part(key="prepare", title="Chuẩn bị dữ liệu", run=guarded(prepare), est_seconds=5),
        Part(key="edit", title="Chỉnh sửa storyboard", run=guarded(edit), est_seconds=15),
        Part(key="apply", title="Áp dụng thay đổi", run=guarded(apply_), est_seconds=5),
    ]


def make_picks_edit_parts(project_dir: Path, *, model: str | None, instruction: str, edit_scope: dict, turn_id: str | None, base_rev: str | None):
    """The parts of a prompt-box turn on the pictures (step 4): one model call, typed picks operations, one batch."""
    from bti.longjob import Part, PartError
    from . import boxops, picksedit
    box = {"start": 0.0}

    def guarded(fn):
        def run_part(ctx):
            try:
                return fn(ctx)
            except PartError:
                raise
            except DraftError as e:
                _fail_turn(project_dir, turn_id, e.code, vi(e.code, e.message), start=box["start"] or None)
                raise PartError(e.code, vi(e.code, e.message))
            except Exception as e:      # noqa: BLE001
                from bti.longjob import Cancelled
                if isinstance(e, Cancelled):
                    raise
                _fail_turn(project_dir, turn_id, "edit_failed", vi("edit_failed"), start=box["start"] or None, notes="%s: %s" % (type(e).__name__, str(e)[:300]))
                raise
        run_part.__name__ = fn.__name__
        return run_part

    def prepare(ctx):
        box["start"] = time.time()
        _doc, rev = boxops.Backend(project_dir).read("picks")
        if base_rev is not None and base_rev != rev:
            raise DraftError("stale_revision", "the picks changed before the edit was prepared")
        ctx.progress(1.0, "Đã chuẩn bị.")

    def edit(ctx):
        ctx.progress(0.1, "Đang nghĩ…")
        from bti.script.providers import ProviderError
        m = _resolve(project_dir, "picks", model).model
        prior = [t for t in load_thread(project_dir) if t.get("id") != turn_id]
        backend = boxops.Backend(project_dir)
        try:
            res, _scope = picksedit.picks_edit(backend, edit_scope, instruction, model=m, thread_turns=prior, progress=ctx.progress, cancel=ctx.cancelled)
        except ProviderError as e:
            return provider_failed(project_dir, turn_id, ctx, e, m, box["start"], "fast")
        return finish_box_turn(project_dir, turn_id, ctx, "picks", res, backend, None, box["start"], "fast")

    return [Part(key="prepare", title="Chuẩn bị dữ liệu", run=guarded(prepare), est_seconds=3),
            Part(key="edit", title="Sửa chọn hình", run=guarded(edit), est_seconds=25)]


def start_picks(pid: str, project_dir: Path, *, instruction: str, edit_scope: dict, model: str | None = None, base_rev: str | None = None,
                manager=None) -> dict:
    """Start a prompt-box turn on the pictures (step 4). Raises DraftError (empty instruction, a scope that cannot be used, a stale revision)
    or bti.longjob.Busy. The turn is recorded in the same thread as the storyboard's, with `doc: "picks"`."""
    from . import boxops, picksedit
    from bti.picks import context
    if not isinstance(instruction, str) or not instruction.strip():
        raise DraftError("edit_empty_instruction", "instruction cannot be empty")
    if len(instruction) > 2000:
        raise DraftError("edit_bad_scope", "instruction must be 1 to 2000 characters")
    if _bad_model_name(model):
        raise DraftError("bad_model", "the model name is not valid")
    refuse_while_agent_busy(pid, manager)                  # join2: not while the pictures agent works, nor an automatic run
    backend = boxops.Backend(project_dir)
    doc, rev = backend.read("picks")
    if base_rev is not None and base_rev != rev:
        raise DraftError("stale_revision", "the picks have changed since the edit was requested")
    sc = picksedit.picks_scope(backend.adapter("picks").facts(doc), doc, edit_scope or {}, context.narration_view(project_dir))
    res_edit = _resolve(project_dir, "picks", model)
    turn_id = f"t_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%1000:03d}"
    turn = {"id": turn_id, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "instruction": instruction.strip(), "doc": "picks",
            "scope": {"kind": sc.kind, "shots": None, "beats": list(sc.ids) if sc.kind == "beats" else None, "chapter": sc.chapter},
            "scope_words": sc.words, "model": res_edit.model, "agent": res_edit.public(), "base_rev": rev, "before_rev": rev, "after_rev": None,
            "path": "fast", "escalated": False, "seconds": 0.0, "summary": "", "changes": [], "status": "running", "job_id": None,
            "proposal_id": None, "notes": "", "conversation_id": None, "error": None}
    append_turn(project_dir, turn)
    m = manager or _manager()
    parts = make_picks_edit_parts(project_dir, model=model, instruction=instruction, edit_scope=edit_scope, turn_id=turn_id, base_rev=rev)
    try:
        rec = m.start(kind=KIND, pid=pid, project_dir=project_dir, parts=parts,
                      meta={"provider": "agy", "model": res_edit.model, "agent": res_edit.public(), "mode": "edit", "doc": "picks", "turn_id": turn_id,
                            "instruction": instruction})
        update_turn(project_dir, turn_id, job_id=rec["id"])
    except Exception:
        with thread_lock(project_dir):
            save_thread(project_dir, [t for t in load_thread(project_dir) if t.get("id") != turn_id])
        raise
    return {**rec, "turn_id": turn_id}


def check_note(note) -> str | None:
    """The owner's note of `draft.start`, trimmed (None when there is none). DraftError `draft_note_invalid` for something that is not text,
    `draft_note_too_long` for more than `inputs.NOTE_MAX` characters."""
    if note is None:
        return None
    if not isinstance(note, str):
        raise DraftError("draft_note_invalid", "note must be text")
    text = note.strip()
    if len(text) > NOTE_MAX:
        raise DraftError("draft_note_too_long", "note must be at most %d characters (it has %d)" % (NOTE_MAX, len(text)))
    return text or None


def start(pid: str, project_dir: Path, *, provider: str = "agy", model: str | None = None, chapters: list | None = None,
          instruction: str | None = None, edit_scope: dict | None = None, followup: bool = False,
          base_rev: int | str | None = None, mode: str = "auto", manager=None, note: str | None = None,
          **kw) -> dict:
    """Start the draft or edit job. Raises DraftError (not ready, agy missing, ...) or bti.longjob.Busy. `note` (draft only) is the owner's wish for
    this draft, put into the agent's task file."""
    if instruction is not None:
        if provider != "agy":
            raise DraftError("edit_needs_agy", "editing by prompt requires the agy agent provider")
        if not isinstance(instruction, str) or not instruction.strip():
            raise DraftError("edit_empty_instruction", "instruction cannot be empty")
        if len(instruction) > 2000:
            raise DraftError("edit_bad_scope", "instruction must be 1 to 2000 characters")
        if _bad_model_name(model):
            raise DraftError("bad_model", "the model name is not valid")
        if mode not in ("auto", "fast", "deep"):
            raise DraftError("edit_bad_scope", "mode must be auto, fast, or deep")

        refuse_while_agent_busy(pid, manager)              # join2: not while the pictures agent works, nor an automatic run
        inp = load_inputs(project_dir, for_edit=True)
        if not inp.current:
            raise DraftError("scope_needs_storyboard", "editing by prompt requires an existing storyboard")
        from bti.editor.common import compute_rev
        cur_rev = compute_rev(inp.current)
        if base_rev is not None and base_rev != cur_rev:
            raise DraftError("stale_revision", "storyboard has changed since edit was requested")
        effective_base_rev = base_rev or cur_rev
        edit_shots, scope_chapters, scope_words = resolve_edit_scope(inp, edit_scope or {})

        # E9: For deep path, verify the agent's availability after validation (agy, or Claude Code for a `claude:` model)
        needs_agy_check = (mode == "deep") or (mode == "auto" and len(edit_shots) > 12)
        if needs_agy_check:
            _check_agent_installed(_resolve(project_dir, "edit.deep", model).model)

        turn_id = f"t_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%1000:03d}"
        scope_kind = "shots" if "shots" in (edit_scope or {}) else ("chapter" if "chapter" in (edit_scope or {}) else "all")
        initial_path = "fast" if (mode == "fast" or (mode == "auto" and len(edit_shots) <= 12)) else "deep"
        res_edit = _resolve(project_dir, "edit.fast" if initial_path == "fast" else "edit.deep", model)

        turn = {
            "id": turn_id,
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "instruction": instruction.strip(),
            "doc": "storyboard",
            "scope": {
                "kind": scope_kind,
                "shots": sorted(edit_shots) if scope_kind == "shots" else None,
                "chapter": (edit_scope or {}).get("chapter") if scope_kind == "chapter" else None,
            },
            "scope_words": scope_words,
            "model": res_edit.model,
            "agent": res_edit.public(),
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
                          meta={"provider": provider, "model": res_edit.model, "agent": res_edit.public(), "mode": "edit", "turn_id": turn_id,
                                "instruction": instruction})
            update_turn(project_dir, turn_id, job_id=rec["id"])
        except Exception:
            with thread_lock(project_dir):
                turns = [t for t in load_thread(project_dir) if t.get("id") != turn_id]
                save_thread(project_dir, turns)
            raise
        return {**rec, "turn_id": turn_id}

    if provider not in ("agy", "auto"):
        raise DraftError("bad_provider", "provider must be agy or auto")
    if _bad_model_name(model):
        raise DraftError("bad_model", "the model name is not valid")
    note = check_note(note)
    if not readiness(project_dir)["ok"]:
        raise DraftError("draft_not_ready", "voice (timing.json) and approved picks (picks.json) are needed first")
    refuse_while_agent_busy(pid, manager, run_ok=True)     # join2: not while the pictures agent works (an automatic run takes the draft itself)
    res = _resolve(project_dir, "draft", model) if provider == "agy" else None
    if res is not None:
        _check_agent_installed(res.model)
    if chapters:
        load_inputs(project_dir, chapters)            # unknown chapter, no storyboard: refused here, not inside the job
    m = manager or _manager()
    return m.start(kind=KIND, pid=pid, project_dir=project_dir, parts=make_parts(project_dir, provider, model, chapters, note=note, **kw),
                   meta={"provider": provider, "model": res.model if res else model, "agent": res.public() if res else None, "chapters": chapters,
                         **({"note": note} if note else {})})
