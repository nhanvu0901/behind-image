"""The quality bar of an automatic run: what it looks at before it approves a gate, and which warnings stop it.

A careful person who is about to press "Duyệt" reads the checks the page shows for that document: the list "Kiểm tra" of the outline and of the
narration (`issues` of GET .../outline and .../narration), the "Cảnh báo" of the picks (`issues` of GET .../picks) and the issues of the storyboard
(`issues` of GET /api/projects/{pid}). The approval routes already refuse error-level issues (and, for the storyboard, an item that cannot be drawn);
the run looks first, so it stops with the sentence of the problem and nothing is sent.

    * an ERROR-level issue always stops the run (`quality_error`).
    * a warning stops it when it is in STOPS of that gate: it is about the substance (a fact without a source, a line with no picture, a length that
      is off the promise) or it would spoil an expensive step that follows (the voice is about an hour, the export 25 minutes).
    * a warning in TOLERATED is style or housekeeping: the run goes on, and the log keeps the warning with its count.
    * a warning in SHARE_LIMITS stops the run only when MORE than that share of the lines of the document has it (a line with no picture: more than a
      quarter of the narration stops; at or below a quarter the run goes on, the storyboard draft shows the main painting there, and the run says how many).
      The share of `outside_no_picture` (a line about something outside the painting that shows only the main painting) is of the lines about something
      outside the painting (`outside.lines` of GET .../picks), not of all the lines: more than 34% of them stops, at or below it the run goes on and says how many.
    * a warning that is in neither list STOPS (a new check somebody adds is looked at by the owner until it is sorted into one of the lists).
    * `info` issues are never looked at.

Every code in STOPS has a short reason, in English for an agent and in Vietnamese for the page. The lists are the decision; change them here.
"""
from __future__ import annotations

from collections import Counter
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
        # worker fixscript: the narration is written FROM the fact table, so a remark to the owner left in a fact gets spoken (it did, twice, in the first video made end
        # to end); taking it out is a ten-second edit before the gate, finding it after the voice is an hour of machine time
        "fact_for_owner": ("a fact's text holds a remark for the owner or an instruction, and the narration is written from it: it would be spoken",
                           "có dữ kiện chứa lời nhắn cho bạn, lời dẫn viết từ đó có thể đọc to lời nhắn ấy"),
    },
    "narration": {
        "words_off_target": ("the length is more than 15% away from the target: the video would not be the length that was planned",
                             "độ dài lời dẫn lệch quá 15% so với mục tiêu"),
        "unknown_fact": ("a line cites a fact that is not in the outline", "có dòng nhắc dữ kiện không có trong dàn ý"),
        # worker fixscript: the voice that follows is about an hour of machine time and says every word of the line, so a name or a remark that should not be
        # spoken is cheap to take out now and an hour to take out later; the viewer has never heard of the books, and these two read like a review of three books
        "source_author_named": ("a line names the author of a source book, and the voice would say it (the viewer has never heard of the books)",
                                "có dòng nêu tên tác giả sách nguồn, giọng đọc sẽ đọc to tên đó"),
        "source_talk": ("a line speaks about the sources themselves (the books, a passage, a doubt about a source) or carries a remark meant for the owner, and the voice would read it aloud",
                        "có dòng nói về chính các sách nguồn hoặc mang lời nhắn dành cho chủ kênh"),
        # worker introrules: cold-open hook and naming rules
        "cold_open_missing_name": ("the cold open does not speak both the painting's name and the painter's name in ordinary speech outside quotations",
                                   "mở đầu chưa đọc tên bức tranh hoặc tên họa sĩ ngoài ngoặc kép"),
        "cold_open_no_closing_question": ("the cold open does not close on an open question",
                                          "mở đầu chưa kết bằng một câu hỏi mở"),
        "cold_open_roadmap": ("the cold open uses a plan-of-the-video phrase instead of opening inside the painting and puzzle",
                              "mở đầu nói câu giới thiệu kế hoạch video thay vì đi thẳng vào tranh"),
        # worker voiceplain (2026-11-22): literature-review attribution phrases read aloud by the voice
        "attribution_phrase": ("a line attributes a claim to historians, scholars, critics or another reading instead of speaking in the channel's own voice, and the voice would read it aloud",
                               "có dòng quy nhận định cho học giả, nhà phê bình hoặc cách đọc khác thay vì kể bằng giọng của kênh"),
    },
    "picks": {
        "beat_no_pick": ("more than a quarter of the lines of the narration have no picture (up to a quarter the run goes on: the draft shows the main painting there)",
                         "hơn một phần tư số dòng lời dẫn chưa có hình"),
        "beat_unknown": ("a picture is attached to a line that is not in the narration any more", "có hình gắn vào dòng không còn trong lời dẫn"),
        # worker linekinds: the owner's first test video showed the painting for 86% of the time although half of the narration spoke of things that are not in it
        "outside_no_picture": ("more than 34% of the lines about something outside the painting show only the main painting, because no picture of the thing itself was found "
                               "(up to 34% the run goes on: the draft shows the main painting there)",
                               "hơn 34% số dòng nói về thứ ngoài bức tranh chỉ có tranh chính, chưa tìm được hình của chính thứ đó"),
    },
    "storyboard": {
        # worker viewreview: the viewer model found a remaining substantive issue.
        "review_picture_mismatch": ("the picture does not show the spoken subject", "hình chưa cho thấy điều lời dẫn đang nói"),
        "review_text_wrong": ("on-screen text is wrong or duplicated", "chữ trên hình chưa đúng hoặc bị lặp"),
        "review_context_missing": ("a name or detail lacks its introduction or meaning", "tên hoặc chi tiết chưa được giới thiệu rõ"),
        "review_picture_repeated": ("a picture repeats for unrelated lines", "hình bị lặp ở những câu không liên quan"),
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
        # --- fixdraft: what a viewer would see (bti/engine/viewchecks.py). Each of these is a look the owner rejected in the first video made end to end with a
        # real model, and the export that follows takes 15 to 25 minutes of machine time, so the run stops and the owner asks for the fix with one request.
        "upright_whole_share": ("the main painting is shown small between two black bars for more than 6% of the video (41 of 109 shots in the first real draft): "
                                "the video looks dark and the same", "bức tranh chính hiện nhỏ giữa hai dải đen quá lâu: video sẽ tối và đơn điệu"),
        "highlight_off_frame": ("a spotlight points outside the frame or at its edge: everything else is dimmed and nothing is lit",
                                "có vùng sáng nằm ngoài khung hình: tranh tối đi mà không sáng chỗ nào"),
        "highlight_too_dark": ("a spotlight leaves the frame almost black (mean luma under 32 on the 16 to 235 scale): the first export had three such stretches of five seconds",
                               "có vùng sáng làm cả khung hình gần như đen"),
        "caption_placeholder": ("a caption on the screen is a placeholder, a note to the reader or only the picture file's artist and year (\"UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950\")",
                                "có dòng chữ trên hình là chữ giữ chỗ hoặc không ai viết"),
        "caption_repeats": ("a caption on the screen says the same words twice", "có dòng chữ trên hình bị lặp hai lần"),
        "text_not_in_narration": ("a place, label, figure or name on the screen is not in the narration: it may be a guess, and the owner's rule is that facts come only from the narration",
                                  "có tên, nhãn hoặc con số trên hình mà lời dẫn không nói"),
        "asset_not_in_lines": ("a shot shows a picture that no line of the narration has: the owner took it out of every line", "có cảnh dùng hình mà không dòng lời dẫn nào chọn"),
        "explainer_early": ("a diagram on its own background (map, time axis, tree, two-state picture) fills part of the first half minute: the painting leaves the screen as the viewer arrives",
                            "có sơ đồ nền riêng che mất bức tranh trong nửa phút đầu"),
        # --- catalogue (worker catalogue, 2026-11-20): what the kinds of a line call for (bti/engine/viewchecks.py); silent on a line without `kinds`
        "device_wrong_kind": ("a device (map, time axis, large figure, lit line, perspective lines, tree, two panels) is used on a line whose kind does not call for it: the owner's first video put "
                              "maps on towns that were only mentioned and a figure over the wrong picture", "có hiệu ứng (bản đồ, trục thời gian, con số lớn...) đặt vào câu không thuộc loại cần đến nó"),
        "device_too_little": ("a device has too little to show (a map with one place, a time axis with one or two dates, a key or a tree with fewer than three entries)",
                              "có hiệu ứng chỉ có một hai mục để hiện nên không có ý nghĩa"),
        "figure_on_wrong_picture": ("a large figure is laid over another picture although the picks of its line hold the picture of the thing counted (the first video laid 42 ships over the saint)",
                                    "có con số lớn nằm trên hình không phải thứ được đếm"),
        # worker subjdraft: a named subject must be visible.
        "subject_not_on_screen": ("the named subject is not visible when spoken", "có chủ thể chưa hiện khi lời dẫn nhắc đến"),
        # pointfix: a viewer needs to locate details and read labels.
        "name_not_shown": ("a first-presented person has no on-screen name", "có người được giới thiệu nhưng chưa hiện tên"),
        "year_already_on_screen": ("a large year is already visible in a simultaneous label or caption", "năm đã hiện trong nhãn"),
        "small_detail_not_lit": ("a small named detail in the painting has no visual pointer", "có chi tiết nhỏ chưa được rọi sáng"),
        "highlight_nothing_to_dim": ("a spotlight covers so much of the frame that little can be darkened", "có vùng sáng chiếm quá nhiều khung hình"),
        "text_too_brief": ("on-screen text is not fully visible for long enough to read", "có chữ hiện quá nhanh"),
        "outside_on_painting": ("a line about something outside the painting has its picture but shows the painting for most of the line (the picture is on screen for less than 45% of it, 25% when the line has two kinds, or for less than 3.5 seconds): the viewer never sees what the narrator speaks of",
                                "có dòng nói về thứ ngoài tranh, đã có hình, nhưng vẫn chỉ hiện bức tranh"),
        "outside_picture_small": ("a picture that is not the painting is drawn smaller than 80% of its default fit: it sits small between black bars", "có hình ngoài tranh hiện nhỏ lọt thỏm giữa hai dải đen"),
        # --- panelbox (2026-11-20): the camera never leaves the painted surface of the main painting (bti/media/contentbox.py, bti/engine/viewchecks.py)
        "frame_off_painting": ("a camera key of a shot on the main painting shows more than 1% of the frame outside the painted area of the picture: a band of the museum photograph's black ground, "
                               "or of the matte past the picture's edge, stands at a side of the frame (the first test video had about a dozen such shots, the close-ups of the mirror)",
                               "có cảnh máy quay trượt ra ngoài mặt tranh: một dải đen của nền ảnh bảo tàng hiện ở mép khung hình"),
        # --- boxcam (2026-11-21): a named region must stay wholly inside the frame and arrive early enough to be seen (bti/engine/viewchecks.py)
        "camera_off_region": ("at the end of a main-painting shot pointing at a region, that region's box extends outside the frame so the viewer cannot see all of it",
                              "cuối cảnh chỉ vào một vùng của tranh chính nhưng vùng đó bị cắt mép ra ngoài khung hình"),
        "thing_arrives_late": ("a named region stays wholly inside the frame for less than 2 seconds and less than 55% of the shot, so the camera arrives too late",
                               "chi tiết được gọi tên chỉ nằm gọn trong khung quá muộn và quá ngắn nên người xem không kịp thấy"),
        # --- idfix (2026-11-21): a non-cast strip on the main painting needs a light unless its region covers > 60% of the frame (bti/engine/viewchecks.py)
        "strip_without_light": ("an X-ANN-01 strip naming a non-cast thing on the main painting has no HI-01, X-HI-01, or AN-01 on screen during the strip",
                                "nhãn gọi tên vật trên tranh chính chưa có đèn rọi hay vòng tròn cùng xuất hiện trong lúc hiện nhãn"),
    },
}
# gate -> codes that never stop the run (they stay in the log)
TOLERATED: dict[str, frozenset[str]] = {
    # outline_note (worker fixscript): the model's own remark to the owner (a NOTE line, never part of a fact or of the narration). The page shows it among the checks and the
    # run log keeps it with its count; it does not stop the run, because the narration never sees it and the outline already handled the thing it talks about
    "outline": frozenset({"fact_unused", "no_hook_choice", "budget_sum", "outline_note"}),
    "narration": frozenset({
        "spoken_chars", "beat_too_long", "long_sentence", "no_show", "chapter_off_budget",
        "cold_open_late_name", "cold_open_first_sentence_names", "cold_open_first_line_long", "cold_open_no_early_turn", "cold_open_word_count",
    }),
    # a flagged picture (size, licence or the like) is not a reason to stop: the owner said copyright is not a blocker, and a picture from the owner's own books always carries
    # the flag "unknown". The run goes on and writes the count into its log.
    # panelbox: the painted area of the main painting was not sure (`content_box_unsure`): the whole picture is used, which is the old behaviour; the warning stays in the log
    "picks": frozenset({"asset_flag", "content_box_unsure"}),
    # fixdraft: `shot_short` (under 1.5 s) is a flash, not a defect of substance: the video is still watchable and the owner sees it in the list
    "storyboard": frozenset({"project_name_differs", "unknown_source", "unknown_intent", "first_shot_transition", "shot_short"}),
}
# gate -> {code: share}: the warning stops the run only when MORE than this share of the lines of the document has it (the code is also in STOPS, for the sentence)
NO_PICK_LIMIT = 0.25
OUTSIDE_NO_PICTURE_LIMIT = 0.34          # worker linekinds: of the lines about something outside the painting (kinds `outside` or `compare`), not of all lines
SHARE_LIMITS: dict[str, dict[str, float]] = {"picks": {"beat_no_pick": NO_PICK_LIMIT, "outside_no_picture": OUTSIDE_NO_PICTURE_LIMIT}}
# the number a share is of: "lines" (the lines of the narration, the default) or "outside" (the lines about something outside the painting)
SHARE_OF: dict[str, str] = {"outside_no_picture": "outside"}
UNKNOWN_WHY = ("a check the run does not know yet", "có cảnh báo mới mà chạy tự động chưa biết")

def document_path(approve_path: str, gate: str) -> str:
    """The GET route of the document of `gate`, from the path of its approval action (`.../outline/approve` -> `.../outline`; the storyboard's is
    `POST /api/projects/{pid}/approve`, its document `GET /api/projects/{pid}`)."""
    base = approve_path[: -len("/approve")] if approve_path.endswith("/approve") else approve_path
    return base


def _level(issue: dict) -> str:
    return str(issue.get("level") or "")


def share_base(code: str, lines: int | None, outside: int | None) -> int | None:
    """The number of lines the share of a warning `code` is of: `outside` for a warning of the lines about something outside the painting, else `lines`."""
    return outside if SHARE_OF.get(code) == "outside" else lines


def judge(gate: str, issues: Any, lines: int | None = None, outside: int | None = None) -> dict:
    """{errors: [...], stopping: [...], tolerated: [...]} for the issues of the document of `gate`. Each entry is the issue with `why` (English) and
    `why_vi` added (a stopping warning) or as it is (an error: its own message). `lines`: how many lines the document has (the narration's, for the picks);
    `outside`: how many of them are about something outside the painting (`outside.lines` of GET .../picks). A warning of SHARE_LIMITS passes while it is on
    no more than that share of them (unknown number of lines: it stops, the safe side)."""
    errors, stopping, tolerated = [], [], []
    stops, ok, limits = STOPS.get(gate, {}), TOLERATED.get(gate, frozenset()), SHARE_LIMITS.get(gate, {})
    rows = [i for i in (issues if isinstance(issues, list) else []) if isinstance(i, dict)]
    counts = Counter(str(i.get("code") or "") for i in rows if _level(i) in WARN_LEVELS)
    for i in rows:
        lv, code = _level(i), str(i.get("code") or "")
        if lv in ERROR_LEVELS:
            errors.append({**_brief(i), "why": str(i.get("message") or code), "why_vi": "có lỗi trong tài liệu này"})
        elif lv in WARN_LEVELS:
            base = share_base(code, lines, outside)
            if code in ok or (code in limits and isinstance(base, int) and base > 0 and counts[code] <= limits[code] * base + 1e-9):
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


def tally(tolerated: list[dict]) -> dict[str, int]:
    """{code: how many} of the warnings the run let through (what the run log and the end of the run say)."""
    return dict(Counter(str(t.get("code") or "") for t in tolerated))


def vet(gate: str, issues: Any, lines: int | None = None, outside: int | None = None) -> tuple[str, list[dict], list[dict]]:
    """('error' | 'warning' | 'ok', the entries that stop the run, the warnings it let through)."""
    v = judge(gate, issues, lines, outside)
    if v["errors"]:
        return "error", v["errors"], v["tolerated"] + v["stopping"]
    if v["stopping"]:
        return "warning", v["stopping"], v["tolerated"]
    return "ok", [], v["tolerated"]
