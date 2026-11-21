"""The words of the readable files of the output folder (README.md, outline.md, narration.md, shots.md, changes.md, jobs.md, INDEX.md). The owner reads Vietnamese, so
every sentence a person meets there is Vietnamese; the code and the comments are English. Dates are written day/month/year, numbers with a decimal comma."""
from __future__ import annotations

import re
import time
from typing import Any

STEP_LABEL = {"artwork": "Tác phẩm", "script": "Kịch bản", "voice": "Giọng đọc", "picks": "Chọn hình", "edit": "Dựng hình", "export": "Xuất video"}
STEP_ORDER = ["artwork", "script", "voice", "picks", "edit", "export"]
STEP_NUMBER = {s: i + 1 for i, s in enumerate(STEP_ORDER)}
STATE_WORD = {"done": "xong", "current": "đang làm", "available": "đang làm", "waiting": "chờ duyệt lại", "locked": "chưa tới", "no_data": "không áp dụng", "none": "chưa có"}

KIND_LABEL = {"outline": "Lập dàn ý", "narration": "Viết lời dẫn", "voice": "Tạo giọng đọc", "draft": "Dựng bản nháp", "edit": "Sửa storyboard bằng lời", "picks": "Agent chọn hình",
              "picks_edit": "Sửa chọn hình bằng lời", "export": "Xuất video", "auto": "Chạy tự động", "preview": "Xem thử", "title": "Viết tựa video"}
JOB_END = {"done": "xong", "error": "lỗi", "cancelled": "đã dừng", "interrupted": "bị ngắt (máy chủ khởi động lại)", "running": "đang chạy", "queued": "đang chờ", "waiting": "đang chờ máy"}
GATE_LABEL = {"outline": "Dàn ý", "narration": "Lời dẫn", "picks": "Chọn hình", "storyboard": "Storyboard"}
PART_LABEL = {"sources": "Nguồn sách", "outline": "Dàn ý", "narration": "Lời dẫn", "title": "Tựa video", "voice": "Giọng đọc", "pictures": "Hình ảnh", "storyboard": "Storyboard", "export": "Video"}
REASON_WORD = {"changed": "tài liệu đã đổi sau khi lưu vào đây", "approval_withdrawn": "việc duyệt đã bị rút lại", "not_approved": "chưa được duyệt lại"}

_RAW_ID = re.compile(r"\b[A-Z]{1,6}-[A-Z0-9]{1,3}(?:-\d+)?\b")


def parse_time(v: Any) -> float | None:
    """Seconds since the epoch of an ISO string (`2026-11-19T11:50:03-0800`, `+07:00`, or without a zone) or a number; None when it is neither."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?", s)
    if not m:
        return None
    y, mo, d, h, mi, se, tz = m.groups()
    import calendar
    secs = calendar.timegm((int(y), int(mo), int(d), int(h), int(mi), int(se or 0), 0, 0, 0))
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        t = tz[1:].replace(":", "")
        secs -= sign * (int(t[:2]) * 3600 + int(t[2:]) * 60)
    elif not tz:
        secs = time.mktime((int(y), int(mo), int(d), int(h), int(mi), int(se or 0), 0, 0, -1))
    return float(secs)


def when(v: Any) -> str:
    """`19/11/2026 11:50`: the clock of the string as it was written (the app's own zone), or of the epoch seconds in this machine's zone."""
    if v is None or v == "":
        return "—"
    if isinstance(v, str):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})", v.strip())
        if m:
            y, mo, d, h, mi = m.groups()
            return "%s/%s/%s %s:%s" % (d, mo, y, h, mi)
    try:
        t = time.localtime(float(v))
        return time.strftime("%d/%m/%Y %H:%M", t)
    except (TypeError, ValueError, OverflowError, OSError):
        return "—"


def clock(seconds: Any) -> str:
    """`2:37`, `1:02:03`."""
    try:
        s = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return "—"
    return "%d:%02d:%02d" % (s // 3600, s // 60 % 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)


def minutes(seconds: Any) -> str:
    """`12 phút 44 giây`, `45 giây`, `1 giờ 03 phút`."""
    try:
        s = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "—"
    if s >= 3600:
        return "%d giờ %02d phút" % (s // 3600, s // 60 % 60)
    if s >= 60:
        return "%d phút %02d giây" % (s // 60, s % 60)
    return "%d giây" % s


def size(n: Any) -> str:
    """`896 MB`, `1,8 GB`, `12 KB`."""
    try:
        b = float(n)
    except (TypeError, ValueError):
        return "—"
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if b >= div:
            v = b / div
            txt = ("%.1f" % v).replace(".", ",") if v < 10 else "%d" % round(v)
            return "%s %s" % (txt.replace(",0", "") if txt.endswith(",0") else txt, unit)
    return "%d B" % int(b)


def num(v: Any, digits: int = 1) -> str:
    try:
        return ("%.*f" % (digits, float(v))).replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def plural_words(n: int, word: str) -> str:
    return "%d %s" % (n, word)


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def md_cell(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text if text is not None else "")).replace("|", "/").strip()


def one_line(text: Any, limit: int = 200) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def plain_ids(text: str, label_of) -> str:
    """Replace every technique id in free text (`CAM-03`, `HI-01`) by the registry's Vietnamese name, so no raw id reaches the owner. An id the registry does not know is cut out."""
    def sub(m):
        lab = label_of(m.group(0))
        return lab if lab else ""
    out = _RAW_ID.sub(sub, str(text or ""))
    return re.sub(r"\s{2,}", " ", out).strip()


def actor_words(actor: Any) -> str:
    """Who made a change or an approval, as a person reads it."""
    a = str(actor or "").strip()
    if not a:
        return "(không ghi)"
    if a == "human":
        return "Bạn (trên trang)"
    if a.startswith("agent:"):
        return "Agent " + a[6:]
    if a.startswith("cli:"):
        return "Lệnh bti (" + a[4:] + ")"
    return a
