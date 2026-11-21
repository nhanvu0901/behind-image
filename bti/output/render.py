"""The readable documents: Markdown written from the JSON documents of the project, in Vietnamese. Pure functions (no file is read or written here): they take what `facts.py` read.

    outline_md   narration_md   shots_md   changes_md   jobs_md   auto_md   sources_md   credits_txt

Each carries the counts and the ids of the document it is made from, so a person can find the line in the JSON; free text that names a technique by its id (`CAM-03`) is
turned into the registry's Vietnamese name (`words.plain_ids`), and a picture detail called `D5` by the dossier's own name."""
from __future__ import annotations

import re
from typing import Any, Callable

from . import words

ROLE_WORD = {"cold_open": "mở đầu", "chapter": "chương", "closing": "kết"}
CERTAINTY_WORD = {"established": "chắc chắn", "likely": "có thể đúng", "disputed": "còn tranh cãi"}


def show_words(show: list, details: dict[str, str]) -> str:
    """The words of a `show` list. A bare `D5` is the dossier's name for that detail (the app's own convention, `bti.picks.context.details`); a `D5` in front of words that
    describe the picture themselves is dropped, so no label is guessed for it."""
    out = []
    for w in show or []:
        w = str(w).strip()
        if re.fullmatch(r"D\d{1,3}", w):
            w = details.get(w, "")
        else:
            w = re.sub(r"\bD\d{1,3}\b\s*", "", w)
        w = re.sub(r"\s{2,}", " ", w).strip(" ,;")
        if w:
            out.append(w)
    return ", ".join(out)


def _approval_line(approval: dict | None, stands: bool) -> str:
    if not approval:
        return "chưa duyệt"
    who = words.actor_words(approval.get("by")) if approval.get("by") else "không ghi người duyệt"
    base = "đã duyệt bởi %s lúc %s" % (who, words.when(approval.get("at")))
    return base if stands else base + " (nay không còn đúng: tài liệu đã đổi sau đó)"


def outline_md(f, details: dict[str, str]) -> str:
    o = f.outline
    if o is None:
        return ""
    L = ["# Dàn ý — %s" % (f.title or f.pid), "",
         "- Tình trạng: %s" % _approval_line(f.approvals.get("outline"), f.outline_ok),
         "- Phiên bản: `%s`" % (f.outline_rev or "")[:12],
         "- %d chương · %d dữ kiện · mục tiêu khoảng %d từ" % (len(o.chapters), len(o.facts), o.target_words), "",
         "## Luận điểm", "", o.thesis or "(chưa có)", ""]
    if o.hook_options:
        L += ["## Câu mở đầu (hook)", ""]
        for h in o.hook_options:
            L.append("- `%s`%s: %s" % (h.id, " (đã chọn)" if h.id == o.hook_choice else "", words.one_line(h.text, 600)))
        L.append("")
    L += ["## Các chương", ""]
    for i, c in enumerate(o.chapters, 1):
        L.append("### Chương %d · %s (`%s`)" % (i, c.title or "(chưa đặt tên)", c.id))
        L.append("")
        bits = ["vai trò: %s" % ROLE_WORD.get(c.role, c.role), "ngân sách khoảng %d từ" % c.word_budget]
        if c.card:
            bits.append("có thẻ chương")
        L.append("- " + " · ".join(bits))
        if c.purpose:
            L.append("- Mục đích: " + c.purpose)
        if c.facts:
            L.append("- Dữ kiện: " + ", ".join("`%s`" % x for x in c.facts))
        shown = show_words(c.show, details)
        if shown:
            L.append("- Cần cho xem: " + shown)
        L.append("")
    L += ["## Dữ kiện", "", "| Mã | Điều khẳng định | Nguồn | Độ chắc |", "|---|---|---|---|"]
    for x in o.facts:
        claim = words.md_cell(x.claim)
        if x.conflict:
            claim += " (mâu thuẫn: %s)" % words.md_cell(x.conflict)
        L.append("| `%s` | %s | %s | %s |" % (x.id, claim, words.md_cell(", ".join(x.sources)), CERTAINTY_WORD.get(x.certainty, x.certainty)))
    used = {fid for c in o.chapters for fid in c.facts}
    unused = [x.id for x in o.facts if x.id not in used]
    if unused:
        L += ["", "Dữ kiện chưa chương nào dùng: " + ", ".join("`%s`" % x for x in unused) + "."]
    return "\n".join(L).rstrip() + "\n"


def narration_md(f, details: dict[str, str]) -> str:
    n = f.narration
    if n is None:
        return ""
    budget = {c.id: c.word_budget for c in f.outline.chapters} if f.outline is not None else {}
    total_words = sum(words.count_words(b.text) for c in n.chapters for b in c.beats)
    lines = sum(len(c.beats) for c in n.chapters)
    L = ["# Lời dẫn — %s" % (n.title or f.title or f.pid), "",
         "- Tình trạng: %s" % _approval_line(f.approvals.get("narration"), f.narration_ok),
         "- Phiên bản: `%s`" % (f.narration_rev or "")[:12],
         "- %d chương · %d dòng · %d từ" % (len(n.chapters), lines, total_words), ""]
    for i, c in enumerate(n.chapters, 1):
        w = sum(words.count_words(b.text) for b in c.beats)
        bud = budget.get(c.id)
        L.append("## Chương %d · %s (`%s`) — %d dòng · %d từ%s" % (i, c.title or "(chưa đặt tên)", c.id, len(c.beats), w, (" (ngân sách %d)" % bud) if bud else ""))
        L.append("")
        for b in c.beats:
            L.append("**%s** (%d từ)%s: %s" % (b.id, words.count_words(b.text), " [đã khóa]" if b.locked else "", b.text.strip()))
            L.append("")
            extra = []
            if b.show:
                extra.append("cần cho xem: " + show_words(b.show, details))
            if b.facts:
                extra.append("dữ kiện: " + ", ".join(b.facts))
            if b.note:
                extra.append("ghi chú: " + b.note)
            extra = [e for e in extra if e and not e.endswith(": ")]
            if extra:
                L.append("_%s_" % " · ".join(extra))
                L.append("")
    return "\n".join(L).rstrip() + "\n"


STATE_TITLE = {"done": "đang dùng", "stale": "đang dùng, nhưng lời dẫn đã đổi sau khi tựa này được viết: nên nhờ agent viết lại"}


def title_md(f) -> str:
    """titlestep: `2_script/title.md`. The chosen title first, then every candidate the agent returned (with the line numbers that make it true and its reason), then the earlier titles."""
    d = f.title_doc or {}
    ch = d.get("chosen") or {}
    L = ["# Tựa video — %s" % (f.title or f.pid), "", "**%s**" % words.md_cell(ch.get("text")), ""]
    L += ["- Tình trạng: %s" % STATE_TITLE.get(f.title_state, f.title_state),
          "- Ai chọn: %s%s" % (words.actor_words(ch.get("by")), (" · " + words.when(ch.get("at"))) if ch.get("at") else ""),
          "- Phiên bản: `%s`" % (f.title_rev or "")[:12], ""]
    cands = d.get("candidates") or []
    if cands:
        w = d.get("written") or {}
        L += ["## Các tựa agent đề xuất", ""]
        if w.get("agent"):
            L += ["Do %s viết%s." % ((w["agent"] or {}).get("label") or w.get("model") or "agent", (" theo lời nhắn của bạn: \"%s\"" % words.md_cell(w["note"])) if w.get("note") else ""), ""]
        L += ["| # | Tựa | Dạng | Điểm (tò mò / cụ thể / trọng tâm / rõ) | Dòng lời dẫn | Lý do |", "|---|---|---|---|---|---|"]
        for i, c in enumerate(cands, 1):
            s = c.get("scores") or {}
            mark = " **(đang dùng)**" if c.get("text") == ch.get("text") else ""
            L.append("| %d | %s%s | %s | %s | %s | %s |" % (i, words.md_cell(c.get("text")), mark, c.get("form") or "", " / ".join(str(s.get(k, "?")) for k in ("curiosity", "concrete", "central", "clear")),
                                                          words.md_cell(", ".join(c.get("lines") or [])), words.md_cell(c.get("why"))))
        L.append("")
    hist = d.get("history") or []
    if hist:
        L += ["## Các tựa đã dùng trước đó", ""]
        for h in reversed(hist):
            L.append("- %s — %s%s" % (words.md_cell(h.get("text")), words.actor_words(h.get("by")), (" · " + words.when(h.get("at"))) if h.get("at") else ""))
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def shots_md(f, rows: list[dict], chapters: list[dict]) -> str:
    """`rows`: one per shot {n, id, t0, t1, sentence, spoken, locked}; `chapters`: [{id, title, t0, t1}] by time."""
    total = len(rows)
    ends = [r["t1"] for r in rows if r.get("t1") is not None]
    L = ["# Các cảnh — %s" % (f.title or f.pid), "",
         "- Tình trạng: %s" % _approval_line(f.approvals.get("storyboard"), f.sb_approval == "fresh"),
         "- Phiên bản: `%s`" % (f.sb_rev or "")[:12],
         "- %d cảnh%s" % (total, (" · dài %s" % words.clock(max(ends))) if ends else ""), "",
         "Mỗi dòng là một cảnh: số thứ tự, giờ bắt đầu, điều xảy ra trên màn hình (bằng lời thường) và câu đang được đọc lúc đó. Mã cảnh nằm trong `storyboard.json`.", ""]

    def table(rs: list[dict]) -> list[str]:
        out = ["| # | Giờ | Điều xảy ra | Lời đang đọc | Mã cảnh |", "|---|---|---|---|---|"]
        for r in rs:
            out.append("| %d | %s | %s%s | %s | `%s` |" % (r["n"], words.clock(r["t0"]) if r.get("t0") is not None else "—", words.md_cell(r["sentence"]),
                                                          " (đã khóa)" if r.get("locked") else "", words.md_cell(r.get("spoken") or ""), r["id"]))
        return out
    if not chapters:
        return "\n".join(L + table(rows)).rstrip() + "\n"
    used: set[int] = set()
    for i, ch in enumerate(chapters, 1):
        rs = [r for r in rows if r.get("t0") is not None and ch["t0"] - 1e-6 <= r["t0"] < ch["t1"] - 1e-6 and r["n"] not in used]
        if i == 1:
            rs = [r for r in rows if r.get("t0") is not None and r["t0"] < ch["t1"] - 1e-6 and r["n"] not in used]
        if not rs:
            continue
        used.update(r["n"] for r in rs)
        L += ["## Chương %d · %s (%s – %s) — %d cảnh" % (i, ch["title"], words.clock(ch["t0"]), words.clock(ch["t1"]), len(rs)), ""] + table(rs) + [""]
    rest = [r for r in rows if r["n"] not in used]
    if rest:
        L += ["## Các cảnh còn lại", ""] + table(rest) + [""]
    return "\n".join(L).rstrip() + "\n"


def changes_md(f, label_of: Callable[[str], str | None]) -> str:
    recs = list(reversed(f.changes))
    kind_word = {"picks": "Chọn hình", "storyboard": "Storyboard"}
    L = ["# Nhật ký các lần sửa — %s" % (f.title or f.pid), "",
         "Mỗi mục là một lần sửa (một \"batch\"): lúc nào, ai sửa, yêu cầu, và những câu mô tả điều đã đổi. Mới nhất ở trên. Có %d lần sửa." % len(recs), ""]
    if not recs:
        L.append("Chưa có lần sửa nào.")
    for r in recs:
        head = "### %s · %s · %s · %s" % (r.get("batch"), kind_word.get(r.get("doc"), r.get("doc")), words.when(r.get("time")), words.actor_words(r.get("actor")))
        L += [head, ""]
        if r.get("undo_of"):
            L.append("Hoàn tác lần sửa %s." % r["undo_of"])
        if r.get("undone_by"):
            L.append("Đã bị hoàn tác bởi %s." % r["undone_by"])
        note = words.plain_ids(words.one_line(r.get("note") or "", 700), label_of)
        if note:
            L.append("Yêu cầu: " + note)
        ch = [c for c in (r.get("changes") or []) if isinstance(c, dict)]
        L.append("%d thao tác, %d thay đổi:" % (len(r.get("ops") or []), len(ch)))
        for c in ch:
            what = words.plain_ids(str(c.get("what") or ""), label_of)
            if what:
                L.append("- " + what)
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def jobs_md(f, rows: list[dict], label_of: Callable[[str], str | None]) -> str:
    L = ["# Nhật ký các việc dài — %s" % (f.title or f.pid), "",
         "Mỗi dòng là một việc máy chạy lâu (viết dàn ý, đọc giọng, dựng bản nháp, xuất video...). Có %d việc." % len(rows), "",
         "| Bắt đầu | Việc | Agent / mô hình | Thời gian | Kết thúc | Ghi chú |", "|---|---|---|---|---|---|"]
    for r in rows:
        dur = (r["finished"] - r["created"]) if r.get("finished") and r.get("created") else None
        who = " · ".join(x for x in (r.get("agent"), r.get("model")) if x) or "máy"
        end = words.JOB_END.get(r.get("state"), r.get("state") or "—")
        note = words.plain_ids(r.get("error") or r.get("detail") or "", label_of)
        if r.get("error") and r.get("error_code"):
            note = "%s (%s)" % (note, r["error_code"])
        L.append("| %s | %s | %s | %s | %s | %s |" % (words.when(r.get("created")), words.KIND_LABEL.get(r["kind"], r["kind"]), words.md_cell(who),
                                                      words.minutes(dur) if dur is not None else "—", end, words.md_cell(note)))
    return "\n".join(L).rstrip() + "\n"


def auto_md(f, action_label: Callable[[str], str]) -> str:
    runs = f.auto_runs
    if not runs:
        return ""
    L = ["# Các lần chạy tự động — %s" % (f.title or f.pid), "", "Có %d lần chạy tự động." % len(runs), ""]
    for r in reversed(runs):
        L += ["## %s · %s" % (r.get("id"), words.when(r.get("started"))), ""]
        L.append("- Kết thúc: %s" % (words.when(r["ended"]) if r.get("ended") else "chưa ghi (máy chủ có thể đã dừng giữa chừng)"))
        if r.get("sentence"):
            L.append("- Kết quả: %s" % words.one_line(r["sentence"], 400))
        steps = [s for s in r.get("steps") or [] if isinstance(s, dict)]
        L.append("- %d việc:" % len(steps))
        for s in steps:
            ok = "xong" if s.get("ok") else ("lỗi" if s.get("ok") is False else "dở dang")
            L.append("  - %s · %s · %s%s" % (words.when(s.get("at")), action_label(str(s.get("action") or "")), ok,
                                              (" · " + words.one_line(s["note"], 160)) if s.get("note") else ""))
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def sources_md(f, books: dict[str, dict], files: list[dict]) -> str:
    """`files`: [{name, words}] the book texts copied; `books`: {book_id: {title, author}}."""
    srcs = [s for s in (f.meta.get("sources") or []) if isinstance(s, dict)]
    L = ["# Nguồn sách — %s" % (f.title or f.pid), "",
         "Dự án làm từ %d nguồn trong sách. Văn bản các nguồn nằm cạnh tệp này; `dossier.json` là hồ sơ của tác phẩm (các chi tiết, hình trong sách)." % len(srcs), "",
         "| Sách | Tác giả | Mã nguồn | Trang PDF |", "|---|---|---|---|"]
    for s in srcs:
        b = books.get(s.get("book_id")) or {}
        pp = s.get("pdf_pages") or []
        L.append("| %s | %s | `%s` | %s |" % (words.md_cell(b.get("title") or s.get("book_id")), words.md_cell(b.get("author") or ""), s.get("work_id") or "",
                                              "%s–%s" % (pp[0], pp[1]) if len(pp) == 2 else ""))
    if files:
        L += ["", "## Tệp văn bản", ""]
        for x in files:
            L.append("- `%s` — %s từ" % (x["name"], x["words"]))
    return "\n".join(L).rstrip() + "\n"


def credits_txt(assets: dict, keys: list[str], credit_line: Callable[[dict], str], flag_note: Callable[[dict], str | None]) -> str:
    lines = [credit_line(assets[k]) for k in keys if k in assets]
    notes = [n for n in (flag_note(assets[k]) for k in keys if k in assets) if n]
    out = ["Credits of the pictures on screen (one line each):", ""] + lines
    if notes:
        out += ["", "Notes:"] + notes
    return "\n".join(out) + "\n"
