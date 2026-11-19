"""README.md of one output folder: one page a person reads to see where a video stands. Written from the facts and the state document (never from the clock, so writing it
twice gives the same text)."""
from __future__ import annotations

from . import words
from .paths import FINAL_VIDEO, PARTS

STATE_TEXT = {"done": "xong", "current": "đang làm", "stale": "cần làm lại", "locked": "chưa tới"}
STEP_FOLDER = {"artwork": PARTS["sources"] + "/", "script": PARTS["script"] + "/", "voice": PARTS["voice"] + "/", "picks": PARTS["pictures"] + "/",
               "edit": PARTS["storyboard"] + "/", "export": "%s, %s/" % (FINAL_VIDEO, PARTS["export"])}
STEP_PARTS = {"artwork": ("sources",), "script": ("outline", "narration"), "voice": ("voice",), "picks": ("pictures",), "edit": ("storyboard",), "export": ("export",)}
CHECK_LABEL = {"video": "Mã hóa hình", "duration": "Độ dài", "frames": "Số khung hình", "audio": "Âm thanh", "audio_length": "Độ dài âm thanh", "loudness": "Độ lớn tiếng",
               "true_peak": "Đỉnh âm", "chapters": "Mục lục chương", "chapters_merged": "Chương bị gộp", "size": "Dung lượng"}
CHECK_STATUS = {"ok": "đạt", "warn": "cần xem", "warning": "cần xem", "error": "lỗi", "fail": "lỗi"}
NEXT_TEXT = {
    "script": "Duyệt dàn ý và lời dẫn ở bước Kịch bản.",
    "voice": "Tạo giọng đọc (bước Giọng đọc, khoảng một giờ máy).",
    "picks": "Chọn hình cho từng dòng lời dẫn rồi duyệt (bước Chọn hình).",
    "edit": "Dựng và duyệt storyboard (bước Dựng hình).",
    "export": "Xuất video (bước Xuất video, khoảng 25 phút máy).",
}


def _part_note(st: dict, part: str) -> str:
    p = (st.get("parts") or {}).get(part) or {}
    if p.get("out_of_date"):
        return "bản trong thư mục đã cũ (%s)" % words.REASON_WORD.get(p.get("reason"), "đã đổi")
    return ""


def _status_sentence(f, st: dict) -> str:
    parts = st.get("parts") or {}
    exp = parts.get("export") or {}
    if f.export_ok and exp.get("rev") and not exp.get("out_of_date"):
        v = st.get("video") or {}
        return "**Đã xong.** Video đã xuất và nằm ở `%s` (%s)." % (FINAL_VIDEO, words.minutes(v.get("seconds")))
    if exp.get("rev") and (exp.get("out_of_date") or not f.export_ok):
        return "**Video đã có nhưng đã cũ.** Storyboard hoặc giọng đọc đã đổi sau lần xuất cuối; xuất lại để cập nhật."
    if f.current:
        n = words.STEP_NUMBER[f.current]
        return "**Đang làm.** Đang ở bước %d, %s." % (n, words.STEP_LABEL[f.current])
    return "**Chưa bắt đầu.**"


def readme_md(f, st: dict) -> str:
    parts = st.get("parts") or {}
    L = ["# %s" % (f.title or f.pid), ""]
    sub = " · ".join(x for x in (f.artist, f.year) if x)
    if sub:
        L += [sub, ""]
    L += [_status_sentence(f, st), "",
          "- Dự án: `%s` · Thư mục này: `output/%s/`" % (f.pid, st.get("key")),
          "- Cập nhật lần cuối (theo dự án): %s" % words.when(st.get("updated")), ""]
    stale = [(k, v) for k, v in parts.items() if v.get("out_of_date")]
    if stale:
        L += ["## Phần đã cũ", "", "Các phần này trong thư mục là bản cũ: tài liệu của dự án đã đổi sau khi lưu vào đây. Chúng sẽ được cập nhật khi bước đó xong lại (duyệt lại, xuất lại).", ""]
        for k, v in stale:
            L.append("- %s — %s" % (words.PART_LABEL.get(k, k), words.REASON_WORD.get(v.get("reason"), "đã đổi")))
        L.append("")
    # the video
    v = st.get("video")
    if v:
        L += ["## Video", "", "| | |", "|---|---|",
              "| Tệp | `%s` |" % FINAL_VIDEO,
              "| Độ dài | %s (%s giây) |" % (words.minutes(v.get("seconds")), words.num(v.get("seconds"), 1)),
              "| Dung lượng | %s |" % words.size(v.get("size_bytes")),
              "| Độ phân giải | %s × %s, %s khung hình/giây |" % (v.get("width"), v.get("height"), v.get("fps")),
              "| Số chương | %s |" % v.get("chapters")]
        loud = v.get("loudness") or {}
        if loud.get("lufs") is not None:
            L.append("| Độ lớn tiếng | %s LUFS (đỉnh %s dB) |" % (words.num(loud.get("lufs")), words.num(loud.get("true_peak"))))
        L.append("| Xuất xong lúc | %s (máy dựng mất %s) |" % (words.when(v.get("created")), words.minutes(v.get("render_seconds"))))
        checks = v.get("checks") or []
        bad = [c for c in checks if str(c.get("status")) != "ok"]
        L += ["", "Kiểm tra tự động: " + ("tất cả %d mục đều đạt." % len(checks) if checks and not bad else "%d mục cần xem." % len(bad) if bad else "không có số liệu.")]
        for c in bad:
            L.append("- %s: %s (giá trị %s, mong đợi %s)%s" % (CHECK_LABEL.get(c.get("key"), c.get("key")), CHECK_STATUS.get(str(c.get("status")), c.get("status")), c.get("value"),
                                                                 c.get("expected"), (" — " + c["note"]) if c.get("note") else ""))
        L.append("")
    # the steps
    L += ["## Các bước", "", "| # | Bước | Tình trạng | Xong lúc | Ai duyệt | Agent | Nằm ở |", "|---|---|---|---|---|---|---|"]
    gate_of = {"script": ("outline", "narration"), "picks": ("picks",), "edit": ("storyboard",)}
    when = st.get("reached") or {}
    for s in f.steps:
        sid = s["step"]
        who = []
        for g in gate_of.get(sid, ()):
            a = f.approvals.get(g)
            if a:
                who.append("%s: %s%s" % (words.GATE_LABEL[g], words.actor_words(a.get("by")) if a.get("by") else "không ghi", "" if a.get("stands") else " (không còn đúng)"))
        note = "; ".join(x for x in (_part_note(st, p) for p in STEP_PARTS[sid]) if x)
        text = STATE_TEXT.get(s["state"], s["state"]) + ((" — " + note) if note else "")
        L.append("| %d | %s | %s | %s | %s | %s | `%s` |" % (words.STEP_NUMBER[sid], words.STEP_LABEL[sid], text, words.when(when.get(sid)) if s["state"] == "done" else "—",
                                                            words.md_cell("; ".join(who)) or "—", words.md_cell(f.agents.get(sid) or "—"), STEP_FOLDER[sid]))
    L.append("")
    # what is in the folder
    L += ["## Trong thư mục này", ""]
    L += _contents(st)
    L.append("")
    # next
    L += ["## Xem gì tiếp", ""]
    if f.export_ok and not (parts.get("export") or {}).get("out_of_date"):
        sheets = (parts.get("export") or {}).get("sheets") or []
        L.append("- Xem video `%s`." % FINAL_VIDEO)
        L.append("- Đọc `%s/narration.md` (lời dẫn) và `%s/shots.md` (từng cảnh bằng lời thường)." % (PARTS["script"], PARTS["storyboard"]))
        if sheets:
            first, last = sheets[0].split("/")[-1], sheets[-1].split("/")[-1]
            L.append("- Lướt nhanh cả video qua các tờ ảnh %s (mỗi cảnh một khung hình, có số và giờ)." % ("`%s`" % first if len(sheets) == 1 else "`%s` đến `%s`" % (first, last)))
        L.append("- Xem `%s/credits.txt` và `%s/description.txt` trước khi đăng." % (PARTS["pictures"], PARTS["export"]))
        L.append("- Chép video về máy: `tools/deploy/fetch_video.sh %s`." % st.get("key"))
    else:
        if f.current:
            L.append("- " + NEXT_TEXT.get(f.current, "Làm tiếp bước %s." % words.STEP_LABEL[f.current]))
        for k, v in stale:
            L.append("- %s trong thư mục đã cũ: %s." % (words.PART_LABEL.get(k, k), words.REASON_WORD.get(v.get("reason"), "đã đổi")))
        if not f.current and not stale:
            L.append("- Chưa có gì cần làm.")
    L.append("")
    # cleaning
    cl = st.get("clean")
    if cl:
        L += ["## Dọn dẹp thư mục làm việc", ""]
        if cl.get("done"):
            L.append("Sau khi xuất video xong, ứng dụng đã xóa các tệp tạm của dự án `%s` (bản dựng từng đoạn, ảnh xem thử, bản ghi từng lượt chạy của agent, nhật ký dài): giải phóng **%s** (%d tệp), lúc %s." %
                     (f.pid, words.size(cl.get("freed_bytes")), cl.get("files") or 0, words.when(cl.get("at"))))
            L.append("Tài liệu, lịch sử sửa, các bản lưu cũ, hình, giọng đọc và video **không** bị xóa. Xuất lại cùng một storyboard sẽ dựng lại từ đầu (khoảng 25 phút).")
        else:
            L.append("Chưa dọn thư mục làm việc: %s." % CLEAN_REASON.get(cl.get("reason"), cl.get("reason") or "không rõ lý do"))
        L.append("Tắt việc tự dọn ở Cài đặt → \"Dọn thư mục làm việc sau khi xuất video\".")
        L.append("")
    # runs
    runs = st.get("runs") or []
    if runs:
        L += ["## Các lần làm trong thư mục này", "", "| Dự án | Lần ghi đầu | Lần ghi cuối | Tới bước |", "|---|---|---|---|"]
        for r in runs:
            L.append("| `%s` | %s | %s | %s |" % (r.get("project"), words.when(r.get("first_write")), words.when(r.get("last_write")), words.STEP_LABEL.get(r.get("reached"), "chưa xong bước nào")))
        L.append("")
    # warnings
    ws = st.get("warnings") or []
    if ws:
        L += ["## Cảnh báo", ""] + ["- %s" % w.get("sentence") for w in ws] + [""]
    L += ["---", "Tệp này do ứng dụng viết, đừng sửa tay: lần ghi tiếp theo sẽ ghi đè. Ghi lại từ dự án bất cứ lúc nào: `bti output %s`." % f.pid, ""]
    return "\n".join(L)


CLEAN_REASON = {"switched_off": "bạn đã tắt việc tự dọn trong Cài đặt", "export_failed": "lần xuất này có mục kiểm tra lỗi, giữ lại để xuất lại cho nhanh",
                "job_running": "dự án đang có việc khác chạy", "some_not_removed": "một số tệp không xóa được (đang bị chương trình khác giữ)", "nothing_to_clean": "không có gì để dọn"}


def _contents(st: dict) -> list[str]:
    parts = st.get("parts") or {}
    L: list[str] = []

    def add(text: str, part: str) -> None:
        p = parts.get(part) or {}
        if p.get("rev"):
            L.append("- " + text + (" **(bản cũ)**" if p.get("out_of_date") else ""))

    v = st.get("video") or {}
    add("`%s`: video đã xuất, %s, %s." % (FINAL_VIDEO, words.minutes(v.get("seconds")), words.size(v.get("size_bytes"))), "export")
    s = parts.get("sources") or {}
    add("`%s/`: nguồn sách (%d tệp), danh sách nguồn `sources.md`, hồ sơ `dossier.json`." % (PARTS["sources"], len(s.get("files") or [])), "sources")
    o, n = parts.get("outline") or {}, parts.get("narration") or {}
    add("`%s/outline.md`: dàn ý (%s chương, %s dữ kiện)." % (PARTS["script"], (o.get("counts") or {}).get("chapters"), (o.get("counts") or {}).get("facts")), "outline")
    add("`%s/narration.md`: lời dẫn (%s chương, %s dòng, %s từ). Cùng thư mục có hai tệp JSON." % (PARTS["script"], (n.get("counts") or {}).get("chapters"),
                                                                                                    (n.get("counts") or {}).get("lines"), (n.get("counts") or {}).get("words")), "narration")
    vo = parts.get("voice") or {}
    add("`%s/`: giọng đọc (`narration.wav`), bản trộn (`mix.m4a`), thời gian từng từ (`timing.json`, %s từ)." % (PARTS["voice"], vo.get("words")), "voice")
    pi = parts.get("pictures") or {}
    add("`%s/`: tranh chính (`main.*`) và %s hình khác trên màn hình, `picks.json`, `regions.jpg` (%s vùng vẽ trên tranh chính), `credits.txt`%s." %
        (PARTS["pictures"], max(0, (pi.get("count") or 0) - 1), pi.get("regions") or 0,
         "; đã bỏ %s hình không dùng" % pi["unused_left_out"] if pi.get("unused_left_out") else ""), "pictures")
    sb = parts.get("storyboard") or {}
    ex = parts.get("export") or {}
    sheets = ex.get("sheets") or []
    add("`%s/`: `shots.md` (%s cảnh bằng lời thường), `storyboard.json`%s." % (PARTS["storyboard"], (sb.get("counts") or {}).get("shots"),
                                                                              (", %d tờ ảnh tổng hợp (mỗi cảnh một khung hình)" % len(sheets)) if sheets else ""), "storyboard")
    add("`%s/`: `description.txt` (mô tả đăng video), `chapters.txt` (mục lục), `report.json` (báo cáo kiểm tra)." % PARTS["export"], "export")
    lg = st.get("log") or {}
    L.append("- `log/`: `changes.md` (%s lần sửa), `jobs.md` (%s việc dài)%s." % (lg.get("changes", 0), lg.get("jobs", 0), (", `auto_runs.md` (%s lần chạy tự động)" % lg["auto_runs"]) if lg.get("auto_runs") else ""))
    return L
