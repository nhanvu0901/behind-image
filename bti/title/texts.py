"""Every sentence the owner can read that the title step makes: the part title, the progress and result lines, and the failures of the job (Vietnamese; the page has
its own copy of the failure sentences in `errmsg.js`, block `titlestep`)."""
from __future__ import annotations

PART_TITLE = "Viết tựa video"
LABEL = "Agent đang viết tựa video"

VI = {
    "title_no_output": "Agent không viết được tệp tựa video dùng được, kể cả sau một lần nhắc sửa. Chạy lại, hoặc chọn agent khác.",
    "title_limit": "Agent đã dùng hết giới hạn của một lần chạy mà chưa có tựa video dùng được. Chạy lại để làm tiếp.",
    "title_tampered": "Agent đã thay đổi tệp ngoài thư mục làm việc của nó. Kết quả bị bỏ; hãy kiểm tra dự án rồi chạy lại.",
    "narration_not_approved": "Lời dẫn chưa được duyệt (hoặc đã đổi sau khi duyệt). Duyệt lời dẫn ở bước Kịch bản trước.",
    "agent_job_running": "Agent đang làm một việc khác cho dự án này (chọn hình, sửa bằng lời, dựng bản nháp, viết tựa hoặc chạy tự động). Chờ xong hoặc bấm Dừng rồi thử lại.",
    "title_note_too_long": "Lời nhắn cho tựa video quá dài (tối đa 600 ký tự). Hãy rút gọn rồi thử lại.",
    "title_note_invalid": "Lời nhắn cho tựa video phải là chữ. Hãy gõ lại rồi thử lại.",
    "template_missing": "Thiếu tệp hướng dẫn viết tựa (skills/title/TASK.template.md) trong máy chủ.",
}


def vi(code: str, fallback: str = "") -> str:
    return VI.get(code) or fallback or code


def result_sentence(n_candidates: int, text: str) -> str:
    """`Agent đã viết 7 tựa và chọn: "The Saint Who Was Also an Advertisement".`"""
    return "Agent đã viết %d tựa và chọn: \"%s\"." % (n_candidates, text)


def storyboard_sentence(changed: int, approval_was_fresh: bool) -> str:
    """What the answer says about the storyboard when a title is set or written while one exists."""
    s = "Đã cập nhật tựa video trên storyboard (%d cảnh)." % changed if changed else "Storyboard đã có đúng tựa video này."
    if changed and approval_was_fresh:
        s += " Storyboard đã đổi nên cần được duyệt lại."
    return s
