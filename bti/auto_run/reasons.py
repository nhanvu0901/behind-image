"""How an automatic run ends: the six outcomes, every reason a run stops with, and the sentence for each (Vietnamese for the owner, English for an agent).

A run ends with exactly one RESULT, a dict:

    {outcome, reason, sentence, detail, fix, step, step_label, link, action, action_label, gate, kind, issues, waiting_for, error, steps_taken, ...}

    outcome   done | needs_owner | failed | nothing_to_do | cancelled | limit
    reason    one of REASONS below (a stable word)
    sentence  one Vietnamese sentence that says where the run stopped and why (the page shows it as it is)
    detail    the same in English, `fix` what to do (English imperative): what `bti run` prints
    step      the page step the owner should look at (`script`, `voice`, `picks`, `edit`, `export`), `link` its address on the page
    action    the id of the action the run was about to take, or took (`action_label` its Vietnamese label)
    gate      for a gate: outline, narration, picks or storyboard
    kind      for a cost: model, machine_time or paid
    issues    for a quality stop: [{code, level, message, why}] the stopping warnings (or the errors) found in the document
    waiting_for  for nothing_to_do: the words of `needs` the project waits on
    error     for failed: {status?, code, detail, fix?, retry?} of the refused call or the failed job

`make(reason, **info)` builds a result; the tables here are the only place the sentences are written.
"""
from __future__ import annotations

from typing import Any

OUTCOMES = ("done", "needs_owner", "failed", "nothing_to_do", "cancelled", "limit")

# the steps of the pipeline (the same ids and Vietnamese labels as bti/editor/pipeline_api.py STEPS; a test compares them)
STEPS = [("artwork", "Tác phẩm"), ("script", "Kịch bản"), ("voice", "Giọng đọc"), ("picks", "Chọn hình"), ("edit", "Dựng hình"), ("export", "Xuất video")]
STEP_IDS = [s for s, _ in STEPS]
STEP_LABEL = dict(STEPS)
GATES = ("outline", "narration", "picks", "storyboard")
GATE_STEP = {"outline": "script", "narration": "script", "picks": "picks", "storyboard": "edit"}
GATE_NAME = {"outline": "dàn ý", "narration": "lời dẫn", "picks": "chọn hình", "storyboard": "storyboard"}
KIND_VI = {"model": "để agent làm việc (gọi mô hình)", "machine_time": "chiếm máy chủ rất lâu", "paid": "tốn tiền"}
JOB_KIND_VI = {"outline": "dàn ý", "narration": "lời dẫn", "voice": "giọng đọc", "draft": "dựng hình hoặc sửa bằng lời", "export": "xuất video", "picks": "chọn hình",
               "preview": "xem thử", "title": "viết tựa video"}      # titlestep: `title`

# what a gate refusal means for the owner (the codes of the four approval routes that report a problem with the document)
REFUSAL_VI = {
    "outline_has_errors": "dàn ý còn lỗi",
    "narration_has_errors": "lời dẫn còn lỗi",
    "picks_have_errors": "chọn hình còn lỗi",
    "picks_no_main": "chưa chọn tranh chính",
    "storyboard_has_errors": "storyboard còn lỗi",
    "storyboard_incomplete": "còn cảnh chưa đủ hình hoặc đoạn phim",
    "undrawable": "có cảnh không vẽ được",
    "validation_failed": "storyboard còn lỗi",
    "narration_not_approved": "lời dẫn chưa được duyệt",
    "outline_not_approved": "dàn ý chưa được duyệt",
}
REFUSAL_CODES = frozenset(REFUSAL_VI)

# what each word of `needs` (bti/editor/state_api.py NEEDS) says when the project waits for it: "dự án đang chờ <this>". A test checks that every need has one.
NEED_VI = {
    "book_data": "dữ liệu sách (dự án này nhập từ bản dựng cũ, không có)",
    "documents_readable": "bạn sửa một tệp của dự án đang bị hỏng",
    "outline": "một bản dàn ý (chưa có)",
    "outline_approved": "bạn duyệt dàn ý",
    "narration": "một bản lời dẫn (chưa có)",
    "narration_approved": "bạn duyệt lời dẫn",
    "voice_done": "giọng đọc làm xong",
    "picks": "bạn chọn hình cho dự án (chưa có hình nào)",
    "main_asset": "bạn chọn tranh chính",
    "picks_errors": "bạn sửa lỗi trong phần chọn hình",
    "picks_approved": "bạn duyệt chọn hình",
    "storyboard": "bản nháp storyboard (chưa có)",
    "storyboard_readable": "bạn khôi phục tệp storyboard đang bị hỏng",
    "storyboard_approved": "bạn duyệt storyboard",
    "history_copy": "một bản storyboard cũ còn đọc được để khôi phục (không còn bản nào)",
    "audio_mix": "giọng đọc được làm lại (thiếu tệp âm thanh)",
    "timing": "giọng đọc được làm lại (thiếu tệp thời gian)",
    "no_running_job": "một việc khác của dự án (chọn hình, sửa bằng lời, dựng bản nháp, chạy tự động) chạy xong",
    "agent_usable": "bạn chọn agent khác hoặc đăng nhập lại agent (agent đang chọn chưa chạy được)",
    "suggest_enabled": "bạn bật gợi ý hình",
    "locked_beats": "bạn mở khóa các dòng lời dẫn đang khóa",
    "draft_proposal": "bản nháp dựng xong",
    "storyboard_fits_voice": "bạn bấm \"Khớp lại với giọng đọc\" (thẻ chương, tên kênh và điểm cuối đang lệch so với giọng đọc mới)",
    "auto_enabled": "bạn bật \"Cho agent tự chạy dự án này\"",
    "title_done": "tựa video được viết xong (hoặc bạn đặt tựa video)",      # titlestep
}


class _Info(dict):
    def __missing__(self, key: str) -> str:
        return "?"


def _fmt(template: str, info: dict) -> str:
    try:
        return template.format_map(_Info(info))
    except (ValueError, KeyError, IndexError):
        return template


# reason -> (outcome, Vietnamese sentence, English detail, English fix or None)
REASONS: dict[str, tuple[str, str, str, str | None]] = {
    # ---- done
    "exported": ("done", "Xong: video đã được xuất.", "The project is exported.", None),
    "until_reached": ("done", "Đã chạy xong bước \"{step_label}\", như bạn yêu cầu.", "The step {step} is done, as asked.", None),
    # ---- needs the owner
    "gate_not_allowed": (
        "needs_owner",
        "Dừng trước cổng duyệt {gate_name}: bạn chưa cho agent tự duyệt cổng này. Hãy duyệt ở bước \"{step_label}\", hoặc cho phép cổng này trong \"Cho agent tự chạy dự án này\" rồi bấm \"Chạy tự động\" lại.",
        "The {gate} gate waits for the owner: automatic running may not approve it.",
        "Ask the owner to approve the {gate} gate on the page (step {step}), or to allow it in the project's `auto` (PUT /api/projects/{pid}/auto), then run again."),
    "auto_turned_off": (
        "needs_owner",
        "Dừng vì \"Cho agent tự chạy dự án này\" đã bị tắt. Bật lại rồi bấm \"Chạy tự động\" để làm tiếp.",
        "Automatic running was turned off for this project while the run was going.",
        "Ask the owner to turn automatic running on again (the switch on the page), then run again."),
    "spend_not_allowed": (
        "needs_owner",
        "Dừng trước việc \"{action_label}\": bạn không cho agent tự làm loại việc này ({kind_vi}). Hãy bấm việc đó ở bước \"{step_label}\".",
        "{action} costs {kind} and the owner did not allow an agent to spend that.",
        "Ask the owner to run {action} on the page (step {step}), or to allow {kind} spending in the project's `auto`."),
    "paid_needs_owner": (
        "needs_owner",
        "Dừng trước việc \"{action_label}\" vì nó tốn tiền. Việc tốn tiền luôn cần bạn: hãy làm ở bước \"{step_label}\" nếu bạn muốn.",
        "{action} costs money: an agent never starts it.",
        "Ask the owner to start {action} on the page (step {step}) if they want it."),
    "quality_warning": (
        "needs_owner",
        "Dừng trước cổng duyệt {gate_name}: {first}{more}. Xem ở bước \"{step_label}\", sửa rồi bấm \"Chạy tự động\" lại, hoặc tự duyệt nếu bạn thấy ổn.",
        "The {gate} gate has {count} warning(s) that stop an automatic run: {first_en}",
        "Ask the owner to look at the {gate} document (step {step}) and approve it, or fix it and run again."),
    "quality_error": (
        "needs_owner",
        "Dừng trước cổng duyệt {gate_name}: còn {count} lỗi chưa sửa. Hãy sửa ở bước \"{step_label}\" rồi bấm \"Chạy tự động\" lại.",
        "The {gate} document has {count} error(s): {first_en}",
        "Ask the owner to fix the errors listed in `issues` (step {step}), then run again."),
    "gate_refused": (
        "needs_owner",
        "Cổng duyệt {gate_name} từ chối vì {refusal_vi}. Hãy xem ở bước \"{step_label}\" rồi bấm \"Chạy tự động\" lại.",
        "The server refused to approve the {gate} gate: {error_code} ({error_detail}).",
        "Ask the owner to fix what the refusal names (step {step}), then run again."),
    "repair_needed": (
        "needs_owner",
        "Dừng vì storyboard bị hỏng. Hãy xem ở bước \"{step_label}\" và khôi phục bản gần nhất rồi bấm \"Chạy tự động\" lại.",
        "storyboard.json is unreadable: restoring a copy is the owner's decision, an automatic run does not do it.",
        "Ask the owner to restore the storyboard on the page (step {step}), then run again."),
    # ---- nothing to do
    "nothing_to_do": (
        "nothing_to_do",
        "Chưa có việc nào để chạy: dự án đang chờ {waiting_vi}. Làm việc đó ở bước \"{step_label}\" rồi bấm \"Chạy tự động\" lại.",
        "No action moves the project forward now: it waits for {waiting_en}.",
        "Meet what `waiting_for` names (step {step}), then run again."),
    "busy_elsewhere": (
        "nothing_to_do",
        "Dự án đang có việc khác chạy ({jobs_vi}). Chờ nó xong rồi bấm \"Chạy tự động\" lại.",
        "Another job of the project is running ({jobs_en}); an automatic run never starts a second one.",
        "Wait for the job (GET /api/projects/{pid}/longjobs) or cancel it, then run again."),
    "needs_content": (
        "nothing_to_do",
        "Việc \"{action_label}\" cần nội dung do bạn đưa vào. Làm ở bước \"{step_label}\" rồi bấm \"Chạy tự động\" lại.",
        "{action} needs content that only the owner or the caller can supply (its `fill` fields).",
        "Supply the content (step {step}), then run again."),
    # ---- failed
    "action_failed": (
        "failed",
        "Việc \"{action_label}\" không làm được: {error_vi}",
        "{action} was refused: {error_code} ({error_detail}).",
        "Read `error`, do what its `fix` says, then run again: finished work is kept."),
    "job_failed": (
        "failed",
        "Việc \"{action_label}\" chạy không xong: {error_vi}",
        "The job of {action} ended in error: {error_code} ({error_detail}).",
        "Read `error`, do what it says, then run again: finished parts are kept."),
    "unreachable": (
        "failed",
        "Không gọi được máy chủ của ứng dụng: {error_vi} Hãy kiểm tra rồi bấm \"Chạy tự động\" lại.",
        "The app could not be reached from inside the run: {error_detail}.",
        "Check that the app answers, then run again."),
    "no_progress": (
        "failed",
        "Việc \"{action_label}\" đã chạy xong {count} lần mà dự án vẫn như cũ, nên dừng lại để khỏi lặp mãi. Hãy xem bước \"{step_label}\".",
        "{action} was taken {count} times in a row and the state did not change.",
        "Look at the project (GET /api/projects/{pid}/state) and the run log; do not run again before the cause is known."),
    "internal_error": (
        "failed",
        "Chạy tự động gặp lỗi bất ngờ: {error_vi} Hãy báo cho người quản lý máy.",
        "The automatic run failed unexpectedly: {error_detail}.",
        "Report it; the run log of the project names the step."),
    # ---- cancelled
    "cancelled": (
        "cancelled",
        "Đã dừng theo yêu cầu của bạn. Bấm \"Chạy tự động\" để làm tiếp; phần đã xong được giữ lại.",
        "The run was cancelled; finished work is kept.",
        "Run again to continue from where the project stands."),
    "job_cancelled_elsewhere": (
        "cancelled",
        "Việc \"{action_label}\" đã bị dừng ở nơi khác nên chạy tự động cũng dừng. Bấm \"Chạy tự động\" để làm tiếp.",
        "The job of {action} was cancelled or interrupted outside the run.",
        "Run again to continue: finished parts are kept."),
    # ---- limit
    "step_limit": (
        "limit",
        "Đã làm {count} việc, hết số việc tối đa của một lần chạy. Bấm \"Chạy tự động\" để làm tiếp.",
        "The run took {count} actions, the most it may take (`max_steps`).",
        "Run again to continue, or raise `max_steps`."),
    "time_limit": (
        "limit",
        "Đã chạy quá {hours} giờ trong một lần nên dừng. Bấm \"Chạy tự động\" để làm tiếp.",
        "The run used up its {hours} hours.",
        "Run again to continue."),
}
REASON_OF_OUTCOME: dict[str, list[str]] = {o: [r for r, v in REASONS.items() if v[0] == o] for o in OUTCOMES}


# what the run says at its end about the warnings it let through (only a line without a picture is said in the sentence: the draft shows the main painting there)
NO_PICK_VI = "Có {count} dòng lời dẫn không có hình riêng: bản nháp dùng tranh chính ở các dòng đó."
NO_PICK_EN = "{count} line(s) of the narration have no picture of their own: the draft shows the main painting there."
FLAG_EN = "{count} picture(s) carry a flag (size or licence): an automatic run lets them through."
OUTSIDE_VI = "Có {count} dòng nói về thứ ngoài bức tranh mà chưa tìm được hình của thứ đó (trong {lines} dòng như vậy): bản nháp dùng tranh chính ở các dòng đó."
OUTSIDE_EN = "{count} of the {lines} line(s) about something outside the painting show only the main painting (no picture of the thing itself was found)."


def add_tolerated(result: dict, tolerated: list[dict]) -> dict:
    """Put what the run let through at the quality bar into its result: `tolerated` (`{gate, code, count}` of every warning that did not stop it) and, when
    lines of the narration have no picture, one more sentence that says how many (`lines_without_pick`). A run that let nothing through is as it was."""
    tolerated = [t for t in tolerated if isinstance(t, dict) and t.get("count")]
    if not tolerated:
        return result
    result["tolerated"] = tolerated
    n = sum(int(t["count"]) for t in tolerated if t.get("code") == "beat_no_pick")
    if n:
        result["lines_without_pick"] = n
        result["sentence"] = (str(result.get("sentence") or "").rstrip() + " " + NO_PICK_VI.format(count=n)).strip()
        result["detail"] = (str(result.get("detail") or "").rstrip() + " " + NO_PICK_EN.format(count=n)).strip()
    out = [t for t in tolerated if t.get("code") == "outside_no_picture"]
    if out:                                                  # worker linekinds: the lines about something outside the painting that have only the painting
        n_out, of = sum(int(t["count"]) for t in out), max(int(t.get("lines") or 0) for t in out)
        result["lines_outside_without_picture"] = n_out
        result["sentence"] = (str(result.get("sentence") or "").rstrip() + " " + OUTSIDE_VI.format(count=n_out, lines=of or n_out)).strip()
        result["detail"] = (str(result.get("detail") or "").rstrip() + " " + OUTSIDE_EN.format(count=n_out, lines=of or n_out)).strip()
    flags = sum(int(t["count"]) for t in tolerated if t.get("code") == "asset_flag")
    if flags:
        result["detail"] = (str(result.get("detail") or "").rstrip() + " " + FLAG_EN.format(count=flags)).strip()
    return result


def label_of_step(step: str | None) -> str:
    return STEP_LABEL.get(step or "", "") or (step or "")


def make(reason: str, *, pid: str = "", **info: Any) -> dict:
    """The result of a run that ends for `reason`. `info` names what the sentence needs: step, gate, action, action_label, kind, count, issues,
    waiting_for, error ({status, code, detail, ...}) and the like; what is missing is derived (the step of a gate, the label of a step)."""
    outcome, vi, en, fix = REASONS[reason]
    gate = info.get("gate")
    step = info.get("step") or (GATE_STEP.get(gate) if gate else None)
    if reason == "exported":
        step = step or "export"
    error = info.get("error") if isinstance(info.get("error"), dict) else None
    issues = [i for i in (info.get("issues") or []) if isinstance(i, dict)]
    first = issues[0] if issues else {}
    n_more = max(0, int(info.get("count") or len(issues)) - 1) if issues else 0
    err_detail = str((error or {}).get("detail") or info.get("error_detail") or "")[:300]
    err_code = str((error or {}).get("code") or info.get("error_code") or "unknown")
    err_vi = str(info.get("error_vi") or "")
    if not err_vi:
        err_vi = (err_detail if _is_vietnamese(err_detail) else ("(mã %s) %s" % (err_code, err_detail)).strip() + ".") if (err_detail or err_code != "unknown") else "không rõ lý do."
    waiting = [w for w in (info.get("waiting_for") or []) if isinstance(w, str)]
    fields = {
        "pid": pid, "step": step or "", "step_label": label_of_step(step), "gate": gate or "", "gate_name": GATE_NAME.get(gate or "", gate or ""),
        "action": info.get("action") or "", "action_label": info.get("action_label") or info.get("action") or "",
        "kind": info.get("kind") or "", "kind_vi": KIND_VI.get(info.get("kind") or "", info.get("kind") or ""),
        "count": info.get("count", len(issues) or 0), "hours": info.get("hours", ""),
        "first": first.get("why_vi") or first.get("code") or "", "first_en": first.get("why") or first.get("message") or "",
        "more": (", và còn %d điều nữa" % n_more) if n_more else "",
        "refusal_vi": REFUSAL_VI.get(err_code, "máy chủ không cho duyệt (mã %s)" % err_code),
        "error_code": err_code, "error_detail": err_detail, "error_vi": err_vi,
        "waiting_vi": info.get("waiting_vi") or (NEED_VI.get(waiting[0], waiting[0]) if waiting else "một việc chưa rõ"),
        "waiting_en": info.get("waiting_en") or (", ".join(waiting) if waiting else "something unknown"),
        "jobs_vi": info.get("jobs_vi") or "", "jobs_en": info.get("jobs_en") or "",
    }
    out: dict[str, Any] = {
        "outcome": outcome, "reason": reason, "sentence": _fmt(vi, fields), "detail": _fmt(en, fields), "fix": _fmt(fix, fields) if fix else None,
        "step": step, "step_label": label_of_step(step) or None, "link": ("#/project/%s/%s" % (pid, step)) if pid and step else None,
        "action": info.get("action"), "action_label": info.get("action_label"), "gate": gate, "kind": info.get("kind"),
    }
    if issues:
        out["issues"] = issues
    if waiting:
        out["waiting_for"] = waiting
    if error:
        out["error"] = {k: v for k, v in error.items() if k in ("status", "code", "detail", "fix", "retry", "fields", "retry_after_seconds")}
    return out


def _is_vietnamese(text: str) -> bool:
    return any(ch in "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ" for ch in (text or "").lower())


# ----------------------------------------------------------------------------------------------------------------------------- samples
def samples(pid: str = "arn") -> list[dict]:
    """One result for every reason, made the way the loop makes it from typical facts: for the tests (every sentence is read, the page's own test reads the
    same list from tests/editor_frontend/fixtures/autorun_results.json, which `python -m bti.auto_run.reasons --write` makes)."""
    iss = [{"code": "beat_no_pick", "level": "warning", "message": "beat b0003 has no pick", "why": "more than a quarter of the lines of the narration have no picture", "why_vi": "hơn một phần tư số dòng lời dẫn chưa có hình"},
           {"code": "beat_unknown", "level": "warning", "message": "picks for beat b0099, which is not in the narration", "why": "a picture is attached to a line that is not in the narration any more", "why_vi": "có hình gắn vào dòng không còn trong lời dẫn"}]
    err = {"status": 422, "code": "voice_not_configured", "detail": "this machine has no voice worker configured", "fix": "Ask the owner."}
    facts: dict[str, dict] = {
        "exported": {}, "until_reached": {"step": "voice"},
        "gate_not_allowed": {"gate": "narration", "action": "narration.approve", "action_label": "Duyệt lời dẫn", "step": "script"},
        "auto_turned_off": {"step": "voice"},
        "spend_not_allowed": {"kind": "machine_time", "action": "voice.generate", "action_label": "Tạo giọng đọc", "step": "voice"},
        "paid_needs_owner": {"kind": "paid", "action": "picks.suggest", "action_label": "Gợi ý hình (tốn tiền)", "step": "picks"},
        "quality_warning": {"gate": "picks", "action": "picks.approve", "action_label": "Duyệt chọn hình", "issues": iss, "count": 2},
        "quality_error": {"gate": "outline", "action": "outline.approve", "action_label": "Duyệt dàn ý",
                          "issues": [{"code": "no_thesis", "level": "error", "message": "The thesis is empty.", "why": "The thesis is empty.", "why_vi": "có lỗi trong tài liệu này"}], "count": 1},
        "gate_refused": {"gate": "storyboard", "action": "storyboard.approve", "action_label": "Duyệt storyboard", "error": {"status": 422, "code": "undrawable", "detail": "x"}},
        "repair_needed": {"step": "edit", "action": "storyboard.restore", "action_label": "Khôi phục bản gần nhất"},
        "nothing_to_do": {"step": "picks", "action": "picks.approve", "action_label": "Duyệt chọn hình", "waiting_for": ["main_asset"]},
        "busy_elsewhere": {"step": "voice", "jobs_vi": "giọng đọc", "jobs_en": "voice"},
        "needs_content": {"step": "picks", "action": "picks.auto", "action_label": "Để agent chọn hình"},
        "action_failed": {"step": "voice", "action": "voice.generate", "action_label": "Tạo giọng đọc", "error": err},
        "job_failed": {"step": "voice", "action": "voice.generate", "action_label": "Tạo giọng đọc",
                       "error": {"code": "voice_worker_failed", "detail": "Máy đọc giọng bị lỗi."}, "error_vi": "Máy đọc giọng bị lỗi."},
        "unreachable": {"error_detail": "Connection refused", "error_vi": "Connection refused."},
        "no_progress": {"step": "edit", "action": "proposal.apply", "action_label": "Áp dụng", "count": 2},
        "internal_error": {"error_detail": "KeyError: 'x'", "error_vi": "KeyError: 'x'."},
        "cancelled": {"step": "voice"},
        "job_cancelled_elsewhere": {"step": "voice", "action": "voice.generate", "action_label": "Tạo giọng đọc"},
        "step_limit": {"count": 40, "step": "edit"}, "time_limit": {"hours": "12", "step": "voice"},
    }
    return [make(r, pid=pid, **facts[r]) for r in REASONS]



if __name__ == "__main__":
    import json
    import sys
    if "--write" in sys.argv:
        from pathlib import Path
        target = Path(sys.argv[sys.argv.index("--write") + 1]) if len(sys.argv) > sys.argv.index("--write") + 1 else Path("tests/editor_frontend/fixtures/autorun_results.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(samples(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("wrote", target)
    else:
        print(json.dumps(samples(), ensure_ascii=False, indent=1))
