"""The quality bar of an automatic run: what it looks at before it approves a gate, and which warnings stop it.

A careful person who is about to press "Duyệt" reads the checks the page shows for that document: the list "Kiểm tra" of the outline and of the
narration (`issues` of GET .../outline and .../narration), the "Cảnh báo" of the picks (`issues` of GET .../picks) and the issues of the storyboard
(`issues` of GET /api/projects/{pid}). The approval routes already refuse error-level issues (and, for the storyboard, an item that cannot be drawn);
the run looks first, so it stops with the sentence of the problem and nothing is sent.

    * an ERROR-level issue always stops the run (`quality_error`).
    * a warning stops it when it is in STOPS of that gate: it is about the substance (a fact without a source, a line with no picture, a length that
      is off the promise) or it would spoil an expensive step that follows (the voice is about an hour, the export 25 minutes).
    * a warning in TOLERATED is style or housekeeping: the run goes on, and the log keeps the warning.
    * a warning that is in neither list STOPS (a new check somebody adds is looked at by the owner until it is sorted into one of the lists).
    * `info` issues are never looked at.

Every code in STOPS has a short reason, in English for an agent and in Vietnamese for the page. The lists are the decision; change them here.
"""
from __future__ import annotations

from typing import Any

ERROR_LEVELS = ("error",)
WARN_LEVELS = ("warning", "warn")           # the script documents say `warning`, the storyboard engine says `warn`

# gate -> {code: (why in English, why in Vietnamese)}
STOPS: dict[str, dict[str, tuple[str, str]]] = {
    "outline": {
        "fact_no_source": ("a fact cites no source paragraph, so nothing in the books backs it", "có dữ kiện chưa ghi nguồn sách"),
        "unknown_source_id": ("a fact cites a paragraph that is not in the brief", "có dữ kiện ghi nguồn không có trong sách"),
        "source_excluded": ("a fact leans on a source the owner excluded", "có dữ kiện dựa vào nguồn bạn đã loại"),
        "unknown_fact": ("a chapter uses a fact that is not in the fact table", "có chương dùng dữ kiện không có trong bảng dữ kiện"),
        "disputed_no_conflict": ("a disputed fact has no conflict described, so the narration would state it as certain",
                                 "có dữ kiện còn tranh cãi nhưng chưa nói rõ chỗ tranh cãi"),
    },
    "narration": {
        "words_off_target": ("the length is more than 15% away from the target: the video would not be the length that was planned",
                             "độ dài lời dẫn lệch quá 15% so với mục tiêu"),
        "unknown_fact": ("a line cites a fact that is not in the outline", "có dòng nhắc dữ kiện không có trong dàn ý"),
    },
    "picks": {
        "beat_no_pick": ("a line of the narration has no picture", "có dòng lời dẫn chưa có hình"),
        "asset_flag": ("a picture is flagged (size, licence or the like) and needs a look", "có hình bị gắn cờ, cần xem lại"),
        "beat_unknown": ("a picture is attached to a line that is not in the narration any more", "có hình gắn vào dòng không còn trong lời dẫn"),
    },
    "storyboard": {
        "audio_missing": ("the audio file does not exist", "thiếu tệp âm thanh"),
        "asset_size_mismatch": ("a picture's recorded size differs from its file: regions and camera keys are in the wrong space",
                                "kích thước ghi của một hình khác kích thước thật"),
        "first_shot_late": ("the first shot does not start at 0 s: the beginning is not covered", "cảnh đầu không bắt đầu ở giây 0"),
        "label_without_position": ("a label has no position and is not drawn", "có nhãn chưa có vị trí nên không được vẽ"),
        "end_after_audio": ("the video would end after the voice", "video dài hơn giọng đọc"),
        "canvas_not_1080p": ("the canvas is not 1920x1080", "khung hình không phải 1920x1080"),
        "map_view_coarse": ("a map is zoomed in too close: it has no detail there", "có bản đồ phóng quá gần, không có chi tiết"),
        "identity_technique_mismatch": ("a title or chapter shot does not follow the chosen identity style", "cảnh mở đầu hoặc thẻ chương không theo kiểu đã chọn"),
        "incomplete": ("an item is not filled in yet", "còn mục chưa điền đủ"),
    },
}
# gate -> codes that never stop the run (they stay in the log)
TOLERATED: dict[str, frozenset[str]] = {
    "outline": frozenset({"fact_unused", "no_hook_choice", "budget_sum"}),
    "narration": frozenset({"spoken_chars", "beat_too_long", "long_sentence", "no_show", "chapter_off_budget"}),
    "picks": frozenset(),
    "storyboard": frozenset({"project_name_differs", "unknown_source", "unknown_intent", "first_shot_transition"}),
}
UNKNOWN_WHY = ("a check the run does not know yet", "có cảnh báo mới mà chạy tự động chưa biết")

def document_path(approve_path: str, gate: str) -> str:
    """The GET route of the document of `gate`, from the path of its approval action (`.../outline/approve` -> `.../outline`; the storyboard's is
    `POST /api/projects/{pid}/approve`, its document `GET /api/projects/{pid}`)."""
    base = approve_path[: -len("/approve")] if approve_path.endswith("/approve") else approve_path
    return base


def _level(issue: dict) -> str:
    return str(issue.get("level") or "")


def judge(gate: str, issues: Any) -> dict:
    """{errors: [...], stopping: [...], tolerated: [...]} for the issues of the document of `gate`. Each entry is the issue with `why` (English) and
    `why_vi` added (a stopping warning) or as it is (an error: its own message)."""
    errors, stopping, tolerated = [], [], []
    stops, ok = STOPS.get(gate, {}), TOLERATED.get(gate, frozenset())
    for i in issues if isinstance(issues, list) else []:
        if not isinstance(i, dict):
            continue
        lv, code = _level(i), str(i.get("code") or "")
        if lv in ERROR_LEVELS:
            errors.append({**_brief(i), "why": str(i.get("message") or code), "why_vi": "có lỗi trong tài liệu này"})
        elif lv in WARN_LEVELS:
            if code in ok:
                tolerated.append(_brief(i))
            else:
                why, why_vi = stops.get(code, UNKNOWN_WHY)
                stopping.append({**_brief(i), "why": why, "why_vi": why_vi})
    return {"errors": errors, "stopping": stopping, "tolerated": tolerated}


def _brief(i: dict) -> dict:
    out = {"code": str(i.get("code") or ""), "level": _level(i), "message": str(i.get("message") or "")[:200]}
    for k in ("chapter", "beat", "fact", "asset", "path", "shot"):
        if i.get(k) not in (None, ""):
            out[k] = i[k]
    return out


def vet(gate: str, issues: Any) -> tuple[str, list[dict], list[dict]]:
    """('error' | 'warning' | 'ok', the entries that stop the run, the warnings it let through)."""
    v = judge(gate, issues)
    if v["errors"]:
        return "error", v["errors"], v["tolerated"] + v["stopping"]
    if v["stopping"]:
        return "warning", v["stopping"], v["tolerated"]
    return "ok", [], v["tolerated"]
