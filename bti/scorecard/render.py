"""Plain Vietnamese Markdown renderers for `scorecard.md` and `record.md`."""
from __future__ import annotations

from typing import Any

from bti.output import words

METRIC_LABEL: dict[str, str] = {
    "small_painting_share": "Tranh chính nhỏ giữa hai dải đen",
    "marks_per_minute": "Số dấu chỉ mỗi phút (đèn rọi / vòng tròn)",
    "biggest_mark": "Dấu chỉ lớn nhất so với chiều cao khung",
    "marks_on_person": "Dấu chỉ đặt lên người",
    "name_strips": "Nhãn tên trên màn hình",
    "borrowed_pictures": "Hình mượn ngoài tranh",
    "short_shots": "Cảnh thường ngắn dưới 2,5 giây",
    "repeated_regions": "Vùng tranh lặp lại nhiều nhất",
    "subject_not_shown": "Đoạn nhắc tới chủ thể nhưng không chiếu",
    "unfilled_identity": "Mốc chương hoặc đoạn tên kênh chưa phủ kín khung",
    "loudness": "Độ lớn tiếng tổng thể",
    "pause_vs_speech": "Độ chênh nhạc trong khoảng lặng so với lời nói",
}

STEP_VI: dict[str, str] = {
    "outline": "Lập dàn ý",
    "narration": "Viết lời dẫn",
    "title": "Viết tựa video",
    "voice": "Tạo giọng đọc",
    "picks": "Chọn hình",
    "draft": "Dựng bản nháp",
    "review": "Xem lại bằng khung hình",
    "edit": "Sửa storyboard bằng lời",
    "music": "Chọn nhạc",
    "export": "Xuất video",
}

MARK_VI: dict[str, str] = {
    "AN-01": "vòng tròn",
    "HI-01": "đèn rọi",
    "X-HI-01": "đèn rọi tách nền",
}


def _pct(v: Any, digits: int = 1) -> str:
    try:
        return "%s%%" % words.num(float(v) * 100.0, digits)
    except (TypeError, ValueError):
        return "—"


def _status_text(ok: Any) -> str:
    if ok is True:
        return "Đạt"
    if ok is False:
        return "Ngoài mục tiêu"
    return "Chưa áp dụng"


def _fmt_value(m: dict) -> str:
    k, v = m.get("key"), m.get("value")
    if v is None:
        return "Chưa có (chưa xuất video)" if k in ("loudness", "pause_vs_speech") else "Chưa có dữ liệu"
    if k == "small_painting_share":
        return "%s (%s giây / %d cảnh)" % (_pct(v, 1), words.num(m.get("seconds"), 1), m.get("shot_count") or 0)
    if k == "marks_per_minute":
        return "%s/phút (%d dấu: %d vòng tròn, %d đèn rọi)" % (words.num(v, 2), m.get("total") or 0, m.get("rings") or 0, m.get("spotlights") or 0)
    if k == "biggest_mark":
        return "%s (%d dấu > 30%%)" % (_pct(v, 1), m.get("over_30_count") or 0)
    if k in ("marks_on_person", "short_shots", "subject_not_shown", "unfilled_identity"):
        return "%d" % int(v)
    if k == "name_strips":
        thing = "chưa xét" if v.get("on_thing") is None else ("%d trên vật thường" % v["on_thing"])
        return "%d nhãn (%d lặp tên, %s)" % (v.get("count") or 0, v.get("sub_repeats") or 0, thing)
    if k == "borrowed_pictures":
        return "%d hình (%s giây, %s; khoảng trống dài nhất %s giây; %d hình < 3 giây)" % (
            v.get("count") or 0,
            words.num(v.get("seconds"), 1),
            _pct(v.get("share"), 1),
            words.num(v.get("longest_gap_s"), 1),
            v.get("under_3s_count") or 0,
        )
    if k == "repeated_regions":
        items = m.get("items") or []
        if not items:
            return "0"
        top = items[0]
        return "nhiều nhất %d lần (%s)" % (top.get("count") or 0, top.get("label") or top.get("region") or "")
    if k == "loudness":
        return "%s LUFS (đỉnh %s dB)" % (words.num(v.get("lufs"), 1), words.num(v.get("true_peak"), 1))
    if k == "pause_vs_speech":
        return "khoảng lặng thấp hơn lời %s dB (lời %s dB, lặng %s dB)" % (
            words.num(v.get("diff_db"), 1),
            words.num(v.get("speech_db"), 1),
            words.num(v.get("pause_db"), 1),
        )
    return str(v)


def _fmt_target(m: dict) -> str:
    k, t = m.get("key"), m.get("target")
    if k == "small_painting_share":
        return "Tối đa %s" % _pct(t, 0)
    if k == "marks_per_minute":
        return "Tối đa %s/phút" % words.num(t, 1)
    if k == "biggest_mark":
        return "Không quá %s" % _pct(t, 0)
    if k in ("marks_on_person", "short_shots", "subject_not_shown", "unfilled_identity"):
        return "0"
    if k == "name_strips":
        return "0 lặp tên, 0 vật thường"
    if k == "borrowed_pictures":
        return "Mỗi hình >= %s giây, không trống quá %s giây" % (words.num((t or {}).get("min_s"), 1), words.num((t or {}).get("max_gap_s"), 0))
    if k == "repeated_regions":
        return "Tối đa %s lần/vùng" % t
    if k == "loudness":
        return "%s ± %s LUFS" % (words.num((t or {}).get("lufs"), 1), words.num((t or {}).get("tolerance"), 1))
    if k == "pause_vs_speech":
        return "%s–%s dB dưới lời" % (words.num((t or {}).get("min_db"), 0), words.num((t or {}).get("max_db"), 0))
    return str(t)


def scorecard_md(sc: dict, title: str = "") -> str:
    """Render `scorecard.md` in plain Vietnamese."""
    sm = sc.get("summary") or {}
    head = title or sc.get("project") or "Video"
    L = [
        "# Bảng chấm chất lượng — %s" % head,
        "",
        "- Dự án: `%s` · Nguồn: %s · %d cảnh · dài %s" % (
            sc.get("project"),
            "kịch bản hình" if sc.get("source") == "visual" else "storyboard cũ",
            sc.get("shots") or 0,
            words.minutes(sc.get("duration_s")),
        ),
        "- Kết quả: **%d/%d mục đạt**, %d mục ngoài mục tiêu%s" % (
            sm.get("passed") or 0,
            (sm.get("passed") or 0) + (sm.get("failed") or 0),
            sm.get("failed") or 0,
            (" (%d mục chưa áp dụng)" % sm["na"]) if sm.get("na") else "",
        ),
        "",
        "| Chỉ số | Kết quả | Mục tiêu | Đánh giá |",
        "|---|---|---|---|",
    ]
    for m in sc.get("metrics") or []:
        label = METRIC_LABEL.get(m.get("key"), m.get("key"))
        L.append("| %s | %s | %s | %s |" % (
            words.md_cell(label),
            words.md_cell(_fmt_value(m)),
            words.md_cell(_fmt_target(m)),
            _status_text(m.get("ok")),
        ))
    L.append("")
    L += ["## Chi tiết các mục cần xem", ""]
    has_details = False
    for m in sc.get("metrics") or []:
        key = m.get("key")
        items = m.get("items") or []
        if key == "repeated_regions" and items:
            has_details = True
            L.append("### Năm vùng tranh lặp lại nhiều nhất")
            L.append("")
            for it in items:
                locs = ", ".join("%s (%s)" % (s["shot"], words.clock(s.get("time"))) for s in (it.get("shots") or []))
                L.append("- **%s**: %d cảnh — %s" % (it.get("label") or it.get("region"), it.get("count") or 0, locs))
            L.append("")
            continue
        if key == "name_strips" and items:
            bad = [it for it in items if it.get("sub_repeats") or it.get("on_thing")]
            if bad:
                has_details = True
                L.append("### Nhãn tên cần xem")
                L.append("")
                for it in bad:
                    reasons = []
                    if it.get("sub_repeats"):
                        reasons.append("dòng phụ lặp lại tên")
                    if it.get("on_thing"):
                        reasons.append("đặt trên vật thường")
                    L.append("- Cảnh `%s` (%s): “%s”%s — %s" % (
                        it.get("shot"), words.clock(it.get("time")), it.get("text"),
                        (" / “%s”" % it["sub"]) if it.get("sub") else "", ", ".join(reasons),
                    ))
                L.append("")
            continue
        if key == "borrowed_pictures":
            val = m.get("value") or {}
            under = [it for it in items if it.get("under_3s")]
            if under or (val.get("longest_gap_s") or 0) > float((m.get("target") or {}).get("max_gap_s") or 120):
                has_details = True
                L.append("### Hình mượn ngoài tranh")
                L.append("")
                L.append("- Khoảng trống dài nhất không có hình mượn: **%s giây** (từ %s đến %s)." % (
                    words.num(val.get("longest_gap_s"), 1), words.clock(val.get("longest_gap_from")), words.clock(val.get("longest_gap_to")),
                ))
                for it in under:
                    L.append("- Cảnh `%s` (%s): chỉ dài %s giây (dưới 3 giây)" % (it.get("shot"), words.clock(it.get("time")), words.num(it.get("duration"), 2)))
                L.append("")
            continue
        if m.get("ok") is False and items:
            has_details = True
            L.append("### %s" % METRIC_LABEL.get(key, key))
            L.append("")
            for it in items:
                at = it.get("at") or it.get("region") or it.get("title") or it.get("name") or ""
                extra = ""
                if "height_share" in it:
                    extra = " (%s chiều cao khung, %s)" % (_pct(it["height_share"], 0), MARK_VI.get(it.get("technique"), "dấu chỉ"))
                elif "duration" in it:
                    extra = " (%s giây)" % words.num(it["duration"], 2)
                elif "min_cover" in it:
                    extra = " (chỉ phủ %s khung)" % _pct(it["min_cover"], 1)
                elif "seconds" in it:
                    extra = " (%s giây)" % words.num(it["seconds"], 1)
                L.append("- Cảnh `%s` (%s)%s%s" % (it.get("shot"), words.clock(it.get("time")), (": " + str(at)) if at else "", extra))
            L.append("")
    if not has_details:
        L.append("Không có mục nào ngoài mục tiêu.")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def record_md(rec: dict) -> str:
    """Render `record.md` in plain Vietnamese with a section reserved for the owner's comments."""
    art = rec.get("artwork") or {}
    head = art.get("title") or rec.get("project") or "Video"
    L = [
        "# Hồ sơ dựng video — %s" % head,
        "",
        "- Ngày ghi: %s" % (words.when(rec.get("date")) if rec.get("date") else "—"),
        "- Dự án: `%s` · Thư mục tác phẩm: `%s`" % (rec.get("project"), art.get("key") or rec.get("project")),
        "- Tựa video: %s" % (rec.get("video_title") or "—"),
        "- Phiên bản mã nguồn: `%s`" % (rec.get("code_version") or "unknown"),
        "",
        "## Các bước đã chạy",
        "",
        "| Bước | Agent | Mô hình | Thời gian lần cuối | Số lượt | Kết quả |",
        "|---|---|---|---|---|---|",
    ]
    steps = rec.get("steps") or []
    if steps:
        for s in steps:
            L.append("| %s | %s | %s | %s | %s | %s |" % (
                words.md_cell(STEP_VI.get(s.get("step"), s.get("step"))),
                words.md_cell(s.get("agent") or "—"),
                words.md_cell(s.get("model") or "—"),
                words.minutes(s.get("duration_s")) if s.get("duration_s") is not None else "—",
                s.get("runs") or 0,
                words.JOB_END.get(s.get("state"), s.get("state") or "—"),
            ))
    else:
        L.append("| (chưa có bản ghi chạy) | | | | | |")
    L += ["", "## Số đo chính", "", "| Hạng mục | Giá trị |", "|---|---|"]
    c = rec.get("counts") or {}
    rows = [
        ("Số cảnh", c.get("shots")),
        ("Thời lượng", words.minutes(c.get("duration_s"))),
        ("Tranh chính nhỏ", "%s giây (%s)" % (words.num(c.get("small_painting_s"), 1), _pct(c.get("small_painting_share"), 1)) if c.get("small_painting_s") is not None else "—"),
        ("Dấu chỉ (vòng tròn / đèn rọi)", "%s (%s vòng tròn, %s đèn rọi; %s/phút)" % (c.get("marks_total"), c.get("rings"), c.get("spotlights"), words.num(c.get("marks_per_min"), 2)) if c.get("marks_total") is not None else "—"),
        ("Dấu lớn hơn 30% khung", "%s (lớn nhất %s)" % (c.get("marks_over_30_pct"), _pct(c.get("biggest_mark_pct"), 1)) if c.get("biggest_mark_pct") is not None else "—"),
        ("Dấu đặt lên người", c.get("marks_on_person")),
        ("Nhãn tên", "%s (%s lặp tên)" % (c.get("name_strips"), c.get("strip_sub_repeats")) if c.get("name_strips") is not None else "—"),
        ("Hình mượn", "%s (%s giây, %s; trống dài nhất %s giây)" % (c.get("borrowed_count"), words.num(c.get("borrowed_seconds"), 1), _pct(c.get("borrowed_share"), 1), words.num(c.get("borrowed_longest_gap_s"), 1)) if c.get("borrowed_count") is not None else "—"),
        ("Cảnh ngắn dưới 2,5 giây", c.get("short_shots")),
        ("Mốc chương / tên kênh chưa phủ kín", c.get("unfilled_identity")),
        ("Độ lớn tiếng", "%s LUFS" % words.num(c.get("loudness_lufs"), 1) if c.get("loudness_lufs") is not None else "Chưa xuất"),
        ("Khoảng lặng dưới lời nói", "%s dB" % words.num(c.get("pause_vs_speech_db"), 1) if c.get("pause_vs_speech_db") is not None else "Chưa xuất"),
    ]
    for k, v in rows:
        L.append("| %s | %s |" % (k, "—" if v is None else v))
    L += [
        "",
        "## Nhận xét của chủ kênh",
        "",
        "### Tốt (GOOD)",
        "",
        "- ",
        "",
        "### Chưa tốt (NOT GOOD)",
        "",
        "- ",
        "",
        "### Muốn đổi (WANTS)",
        "",
        "- ",
        "",
    ]
    return "\n".join(L)
