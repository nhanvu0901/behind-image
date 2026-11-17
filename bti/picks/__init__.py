"""Step 4 of the pipeline: choose what is on screen for each beat of the approved narration (picks).

The rest of the app sees two things: `bti.editor.picks_api.router` and `state(project_dir)` below.
"""
from __future__ import annotations

from pathlib import Path

from .doc import SCHEMA  # noqa: F401


def state(project_dir) -> dict:
    """`{"state": "none" | "running" | "stale" | "done", "detail": str, ...}` of step 4 for one project folder.
    done: the approval of the picks stands. stale: it was given, and the picks or the narration changed since.
    running: a suggestion job is working. none: anything else (no picks yet, or not approved yet). Never raises."""
    from . import context, doc, suggest
    pdir = Path(project_dir)
    try:
        d = doc.load(pdir)
        nv = context.narration_view(pdir)
    except Exception as e:      # noqa: BLE001   a damaged file is reported by the page; the stepper must still answer
        return {"state": "none", "detail": "Tệp chọn hình (picks.json) hoặc lời dẫn bị hỏng.", "error": type(e).__name__}
    if suggest.running(pdir.name):
        return {"state": "running", "detail": "Đang tìm gợi ý hình."}
    if d is None:
        return {"state": "none", "detail": "Chưa chọn hình.", "main_asset": None, "picked": 0, "beats": len(nv["beat_ids"])}
    beats = nv["beat_ids"]
    picked = sum(1 for b in beats if d["beats"].get(b, {}).get("items"))
    ap = doc.approval_state(d, nv["rev"], nv["approved"])
    info = {"main_asset": d.get("main_asset"), "picked": picked, "beats": len(beats)}
    if ap["approved"]:
        return {"state": "done", "detail": f"Đã duyệt: {picked}/{len(beats)} dòng có hình.", **info}
    if ap["reason"]:
        why = {"picks_edited": "chọn hình đã đổi sau khi duyệt", "narration_changed": "lời dẫn đã đổi sau khi duyệt hình",
               "narration_not_approved": "lời dẫn chưa được duyệt"}[ap["reason"]]
        return {"state": "stale", "detail": f"Cần duyệt lại: {why}.", "reason": ap["reason"], **info}
    if not d.get("main_asset"):
        return {"state": "none", "detail": "Chưa chọn tranh chính.", **info}
    return {"state": "none", "detail": f"Đang chọn: {picked}/{len(beats)} dòng có hình, chưa duyệt.", **info}
