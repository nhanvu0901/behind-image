"""Synchronous, revision-aware storyboard composition action."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Body, Request

from bti.editor.common import ApiError, compute_rev, read_json, save_lock, valid_pid
from bti.engine import registry, storyboard
from bti.engine.timing import Timing
from . import compose

router = APIRouter(prefix="/api/projects/{pid}/storyboard", tags=["composer"])


@router.post("/compose")
def post_compose(pid: str, request: Request, body: dict = Body(default={})):
    root = Path(request.app.state.projects_root)
    project = root / pid
    if not valid_pid(pid) or not project.is_dir() or project.is_symlink():
        raise ApiError(404, "project not found", code="project_not_found")
    return compose_project(project, body)


def compose_project(project: Path, body: dict | None = None):
    """Compose and persist a project under its storyboard save lock."""
    body = body or {}
    pid = project.name
    with save_lock(project):
        try:
            visual = read_json(project / "visual.json")
            timing = read_json(project / "timing.json")
            picks = read_json(project / "picks.json")
            current = read_json(project / "storyboard.json") if (project / "storyboard.json").is_file() else None
        except (OSError, ValueError) as exc:
            raise ApiError(409, "composition input is missing or unreadable", code="invalid_request") from exc
        if "base_rev" in body and body["base_rev"] != (compute_rev(current) if current else None):
            raise ApiError(409, "storyboard revision changed", code="stale_revision")
        from bti.visual.validate import validate as validate_visual
        visual_issues = [i for i in validate_visual(visual, timing, picks) if i.get("level") != "review"]
        if visual_issues:
            raise ApiError(422, "Kịch bản hình còn lỗi. Hãy xem và sửa danh sách lỗi.", code="validation_failed", issues=visual_issues)
        style = (current or {}).get("style", "gae")
        doc, notes = compose(visual, timing, picks, {"id": style}, current)
        doc["project"], doc["timing"] = pid, "timing.json"
        if (project / "audio" / "mix.m4a").is_file():
            doc["audio"] = "audio/mix.m4a"
        elif current and current.get("audio"):
            doc["audio"] = current["audio"]
        if current and current.get("title"):
            doc["title"] = current["title"]
        doc["approvals"] = {**((current or {}).get("approvals") or {}), "storyboard": None}
        issues = storyboard.validate(doc, Timing(timing), registry.load_bundle(style), project)
        if any(i["level"] == "error" for i in issues):
            raise ApiError(422, "composition failed validation", code="validation_failed", issues=issues)
        storyboard.save(project, doc, issues)
    from bti.scorecard import build
    build.make_for_project(project)
    return {"rev": compute_rev(doc), "notes": notes, "issues": issues}


def compose_if_approved(project: Path):
    """Recompose visual projects only after the current picks approval stands."""
    from bti.editor.pipeline_api import project_meta
    from bti.picks import context, doc
    if project_meta(project).get("pipeline", "legacy") != "visual":
        return None
    if not (project / "visual.json").is_file() or not (project / "timing.json").is_file():
        return None
    nv = context.narration_view(project)
    if not doc.approval_state(doc.load(project), nv["rev"], nv["approved"])["approved"]:
        return None
    return compose_project(project)
