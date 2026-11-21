"""Every sentence the owner can read that the automatic picks job makes: part titles, progress lines, why a picture was not found,
the result sentence, and the failures of the job (Vietnamese; the page has its own copy of the failure sentences in `errmsg.js`,
block `c3picks`, and of the result sentence in `picks_logic.js`: a test keeps the two result sentences equal)."""
from __future__ import annotations

PART_TITLES = {
    "plan": "Lập danh sách hình cần tìm (1/4)",
    "search": "Tìm hình (2/4)",
    "choose": "Chọn hình (3/4)",
    "write": "Ghi vào chọn hình (4/4)",
}

TIGHTEN_PART_TITLES = {
    "tighten": "Đo lại khung chi tiết (1/2)",
    "write": "Ghi khung chi tiết mới (2/2)",
}

VI = {
    "picks_auto_no_output": "Agent không viết được tệp kết quả dùng được, kể cả sau một lần nhắc sửa. Chạy lại, hoặc chọn agent khác.",
    "picks_auto_limit": "Agent đã dùng hết giới hạn của một lần chạy mà chưa có kết quả dùng được. Chạy lại để làm tiếp.",
    "picks_auto_tampered": "Agent đã thay đổi tệp ngoài thư mục làm việc của nó. Kết quả bị bỏ; hãy kiểm tra dự án rồi chạy lại.",
    "picks_auto_stale": "Lời dẫn hoặc tranh chính đã đổi trong lúc agent làm việc, nên kết quả không còn khớp. Chạy lại.",
    "picks_approved": "Chọn hình đã được duyệt. Chọn lại sẽ phải duyệt lại: hãy xác nhận chọn lại cả những dòng đã có hình.",
    "picks_nothing_to_do": "Mọi dòng lời dẫn đều đã có hình.",
    "picks_no_main": "Chưa chọn tranh chính ở bước Chọn hình.",
    "narration_not_approved": "Lời dẫn chưa được duyệt (hoặc đã đổi sau khi duyệt). Duyệt lời dẫn ở bước Kịch bản trước.",
    "main_asset_unreadable": "Tranh chính chưa có tệp ảnh đọc được. Chọn lại tranh chính.",
    "retry_nothing_to_do": "Không có dòng nào đang thiếu hình vì nguồn giới hạn lượt tải.",
    "retry_no_files": "Các tệp của lần chạy trước (kế hoạch, kết quả tìm, lựa chọn) không còn trong dự án. Hãy cho agent chọn hình lại các dòng này.",
    "tighten_nothing_to_do": "Mọi vùng chi tiết trên tranh chính đều đã được đo khung khít (hoặc tranh chính chưa có vùng nào).",
    "agent_job_running": "Agent đang làm một việc khác cho dự án này (chọn hình, sửa bằng lời, dựng bản nháp hoặc chạy tự động). Chờ xong hoặc bấm Dừng rồi thử lại.",       # join2: the same sentence as the draft's
}


def vi(code: str, fallback: str = "") -> str:
    return VI.get(code) or fallback or code


def minutes_words(seconds: float | int | None) -> str:
    """`khoảng 3 phút` for the wait a source asked for (a minute when it gave none)."""
    s = int(seconds) if seconds else 60
    return "khoảng %d phút" % max(1, -(-s // 60))


# ---------------------------------------------------------------------------------------------------------------- why not found
def why(code: str, *, what: str = "", source: str = "", seconds: float | None = None, detail: str = "") -> str:
    """The sentence of a picture or a line that could not be filled. `what` is what was wanted, in the plan's own words."""
    w = ("\"%s\"" % what) if what else "hình này"
    if code == "no_candidates":
        return "Không tìm thấy hình nào cho %s ở các nguồn miễn phí." % w
    if code == "agent_none":
        return "Agent không thấy hình nào chắc chắn đúng cho %s%s." % (w, (": " + detail) if detail else "")
    if code == "source_limited":
        return "Nguồn %s đang giới hạn lượt tải, nên chưa tìm được %s. Thử lại sau %s." % (source or "ảnh", w, minutes_words(seconds))
    if code == "search_failed":
        return "Nguồn %s không trả lời, nên chưa tìm được %s." % (source or "ảnh", w)
    if code == "no_thumbs":
        return "Có hình cho %s nhưng không xem trước được để chọn." % w
    if code == "import_failed":
        return "Đã chọn được hình cho %s nhưng không tải về được%s." % (w, (": " + detail) if detail else "")
    if code == "import_limited":
        return "Nguồn %s đang giới hạn lượt tải, nên chưa tải được hình đã chọn cho %s. Thử lại sau %s." % (source or "ảnh", w, minutes_words(seconds))
    if code == "time_up":
        return "Hết thời gian của lần chạy này nên chưa tìm được %s. Chạy lại để làm tiếp." % w
    if code == "web_budget":
        return "Đã hết lượt tìm trên web của lần chạy này nên chưa tìm lại được %s. Chạy lại để tìm tiếp." % w
    if code == "web_no_key":
        return "Chưa có khóa để tìm trên web nên chưa tìm được %s ngoài các nguồn miễn phí. Thêm khóa You.com vào máy chủ rồi chạy lại." % w
    if code == "retry_not_in_plan":
        return "Dòng này không có trong kế hoạch của lần chạy trước nên không tải lại được."
    if code == "retry_no_choice":
        return "Lần chạy trước không ghi hình nào đã chọn cho chỗ còn thiếu của dòng này."
    if code == "retry_line_changed":
        return "Dòng này đã được sửa sau lần chạy của agent nên giữ nguyên."
    if code == "write_refused":
        return "Không ghi được hình cho %s%s." % (w, (": " + detail) if detail else "")
    if code == "box_dropped":
        return "Agent bỏ khung chi tiết %s: khung không chỉ đúng phần lời dẫn nói tới." % w
    return "Chưa có hình cho %s." % w


# ---------------------------------------------------------------------------------------------------------------- the result
def result_sentence(done: int, total: int, without: int) -> str:
    """`Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp.` The page computes the same sentence from the same numbers."""
    s = "Agent đã chọn hình cho %d/%d đoạn." % (done, total)
    if without > 0:
        s += " %d đoạn chưa có hình phù hợp." % without
    return s


def progress_session(label: str, steps: int, max_steps: int, elapsed: float, max_minutes: float) -> str:
    """The progress line of an agent session; the limits are in it, so the owner sees both what is spent and what is allowed."""
    return "%s: bước %d/%d, %d/%d phút." % (label, steps, max_steps, int(elapsed // 60), int(max_minutes))


def retry_sentence(fixed: int, total: int, still: int, left: int) -> str:
    """`Đã tải lại hình cho 5/6 đoạn. 1 đoạn vẫn bị giới hạn lượt tải.` (`picks.retry_missing`)."""
    s = "Đã tải lại hình cho %d/%d đoạn." % (fixed, total)
    if still > 0:
        s += " %d chỗ vẫn bị giới hạn lượt tải, thử lại sau." % still
    if left > 0:
        s += " %d đoạn giữ nguyên." % left
    return s


def tighten_sentence(tightened: int, total: int, unconfirmed: int = 0, dropped: int = 0) -> str:
    """Result sentence for `picks.tighten`."""
    s = "Đã đo khung khít cho %d/%d vùng chi tiết." % (tightened, total)
    if unconfirmed > 0:
        s += " %d vùng chưa được xác nhận nên giữ nguyên." % unconfirmed
    if dropped > 0:
        s += " %d vùng không có trong tranh." % dropped
    return s
