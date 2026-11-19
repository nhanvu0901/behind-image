"""`output/INDEX.md` and `output/index.json`: one line per folder of the output root, made from the folders' own `state.json` (so a folder that was copied in or restored shows up too).

`index.json` is what an automation that queues paintings reads (and `tools/paintings_table.py`):
    {"schema": "bti.output.index/1", "folders": [{"key", "title", "artist", "year", "project", "status": "done" | "in_progress", "step", "step_label", "last_run", "length_seconds",
                                                 "video": bool, "size_bytes", "out_of_date": [parts], "path"}]}"""
from __future__ import annotations

from pathlib import Path

from . import fsutil, words
from .paths import INDEX_JSON, INDEX_MD, STATE_FILE

SCHEMA = "bti.output.index/1"


def row_of(key: str, st: dict) -> dict:
    video = st.get("video") or {}
    parts = st.get("parts") or {}
    has_video = bool((parts.get("export") or {}).get("rev"))
    runs = st.get("runs") or []
    art = st.get("artwork") or {}
    return {"key": key, "title": art.get("title"), "artist": art.get("artist"), "year": art.get("year"), "project": st.get("project"),
            "status": "done" if (has_video and not (parts.get("export") or {}).get("out_of_date")) else "in_progress",
            "step": st.get("current"), "step_label": words.STEP_LABEL.get(st.get("current")) if st.get("current") else None,
            "last_run": runs[-1].get("last_write") if runs else st.get("updated"), "length_seconds": video.get("seconds") if has_video else None,
            "video": has_video, "size_bytes": video.get("size_bytes") if has_video else None,
            "out_of_date": sorted(k for k, v in parts.items() if v.get("out_of_date")), "path": key}


def rows(output_root: Path) -> list[dict]:
    out = []
    try:
        entries = sorted(p for p in Path(output_root).iterdir() if p.is_dir())
    except OSError:
        return out
    for d in entries:
        st = fsutil.read_json(d / STATE_FILE)
        if isinstance(st, dict) and st.get("schema") == "bti.output/1":
            out.append(row_of(d.name, st))
    return out


def index_md(rs: list[dict]) -> str:
    L = ["# Thư mục output: mỗi tác phẩm một thư mục", "",
         "Mỗi dòng là một tác phẩm. Mở thư mục của nó để xem video (`final.mp4`), `README.md` và các phần đánh số từ 1 đến 6. Tệp này do ứng dụng viết, đừng sửa tay.", "",
         "| Tác phẩm | Tình trạng | Bước | Lần làm gần nhất | Độ dài | Dung lượng | Thư mục |", "|---|---|---|---|---|---|---|"]
    for r in rs:
        title = " — ".join(x for x in (r.get("title"), r.get("artist")) if x) or r["key"]
        status = "đã xong" if r["status"] == "done" else "đang làm"
        if r.get("out_of_date"):
            status += " (có phần cũ: %s)" % ", ".join(words.PART_LABEL.get(p, p) for p in r["out_of_date"])
        L.append("| %s | %s | %s | %s | %s | %s | `%s/` |" % (words.md_cell(title), status, r.get("step_label") or "—", words.when(r.get("last_run")),
                                                              words.minutes(r["length_seconds"]) if r.get("length_seconds") else "—", words.size(r["size_bytes"]) if r.get("size_bytes") else "—", r["path"]))
    if not rs:
        L.append("| (chưa có thư mục nào) | | | | | | |")
    return "\n".join(L) + "\n"


def update(output_root: Path) -> list[dict]:
    rs = rows(output_root)
    fsutil.write_json(Path(output_root) / INDEX_JSON, {"schema": SCHEMA, "folders": rs})
    fsutil.write_text(Path(output_root) / INDEX_MD, index_md(rs))
    return rs
