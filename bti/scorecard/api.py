"""HTTP API routes for the scorecard and its contact sheets."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse

from bti.editor.common import ApiError, read_json, storyboard_shape_problem, valid_pid

from . import build

router = APIRouter(prefix="/api", tags=["scorecard"])
SHEET_NAME_RE = re.compile(r"sheet_\d{2,3}\.jpg")


def _pdir(request: Request, pid: str) -> Path:
    root = Path(request.app.state.projects_root)
    if not valid_pid(pid):
        raise ApiError(404, "project not found", code="project_not_found")
    d = root / pid
    if not d.is_dir() or (d.is_symlink() and not d.resolve().is_relative_to(root.resolve())):
        raise ApiError(404, "project not found", code="project_not_found")
    return d


def _is_ready(d: Path) -> bool:
    try:
        sb = read_json(d / "storyboard.json")
        if not isinstance(sb, dict) or storyboard_shape_problem(sb):
            return False
        t_rel = sb.get("timing") if isinstance(sb.get("timing"), str) and sb.get("timing") else "timing.json"
        tm = read_json(d / t_rel)
        return isinstance(tm, dict) and isinstance(tm.get("words"), list)
    except (OSError, ValueError):
        return False


def _sheet_list(pid: str, d: Path, sc: dict | None) -> list[dict]:
    sdir = build.scorecard_dir(d) / "sheets"
    if not sdir.is_dir():
        return []
    meta_by_name = {
        s["name"]: s
        for s in ((sc or {}).get("sheets") or [])
        if isinstance(s, dict) and isinstance(s.get("name"), str)
    }
    out: list[dict] = []
    for p in sorted(sdir.glob("sheet_*.jpg")):
        if not p.is_file() or p.is_symlink():
            continue
        meta = meta_by_name.get(p.name) or {}
        out.append({
            "name": p.name,
            "url": "/api/projects/%s/scorecard/sheets/%s" % (pid, p.name),
            "shots": meta.get("shots"),
            "count": meta.get("count"),
        })
    return out


def _payload(pid: str, d: Path) -> dict:
    sc = build.load_scorecard(d)
    rec = build.load_record(d)
    exists = sc is not None
    return {
        "exists": exists,
        "stale": build.is_stale(d, sc) if exists else False,
        "ready": _is_ready(d),
        "scorecard": sc,
        "record": rec,
        "sheets": _sheet_list(pid, d, sc),
    }


@router.get("/projects/{pid}/scorecard")
def get_scorecard(pid: str, request: Request):
    d = _pdir(request, pid)
    return _payload(pid, d)


@router.post("/projects/{pid}/scorecard/make")
def make_scorecard(pid: str, request: Request, body: dict = Body(default={})):
    d = _pdir(request, pid)
    if not _is_ready(d):
        raise ApiError(409, "storyboard and timing are required before making a scorecard", code="scorecard_not_ready")
    body = body if isinstance(body, dict) else {}
    want_sheets = body.get("sheets")
    if want_sheets is not None and not isinstance(want_sheets, bool):
        raise ApiError(422, "sheets must be true or false", code="invalid_field", field="sheets")
    try:
        build.make_for_project(d, sheets=True if want_sheets is None else want_sheets)
    except Exception as exc:     # noqa: BLE001
        raise ApiError(500, "the scorecard could not be built: %s" % str(exc)[:180], code="scorecard_failed") from exc
    return _payload(pid, d)


@router.get("/projects/{pid}/scorecard/sheets/{name}")
def get_scorecard_sheet(pid: str, name: str, request: Request):
    d = _pdir(request, pid)
    if not SHEET_NAME_RE.fullmatch(name or "") or ".." in name:
        raise ApiError(404, "sheet not found", code="sheet_not_found")
    sdir = build.scorecard_dir(d) / "sheets"
    p = sdir / name
    try:
        if p.is_symlink() or not p.is_file() or p.resolve().parent != sdir.resolve():
            raise ApiError(404, "sheet not found", code="sheet_not_found")
    except OSError:
        raise ApiError(404, "sheet not found", code="sheet_not_found")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
