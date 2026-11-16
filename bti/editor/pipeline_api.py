"""The pipeline of a project, computed in ONE place: the ordered steps with their state and the reason.

`GET /api/projects/{pid}/pipeline` feeds the stepper and the home list of the app shell.
`GET /api/pipeline` is the same list with no project (the "new video" flow, which starts in the library).
`DELETE /api/projects/{pid}?confirm=<pid>` removes a project folder; the protected projects are refused.
Mounted from app.py. Reads files only (never the engine), so it is cheap enough to call for every project."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Query

from .common import ApiError, compute_rev, read_json, valid_pid

def project_meta(d: Path) -> dict:
    """project.json of a folder as a dict ({} when missing or unreadable)."""
    try:
        pj = read_json(d / "project.json")
    except Exception:       # noqa: BLE001
        return {}
    return pj if isinstance(pj, dict) else {}


def is_protected(d: Path) -> bool:
    """A project is protected from delete when its project.json says `"protected": true` (the reference projects)."""
    return project_meta(d).get("protected") is True

# id, label, what the step is. The order here IS the order of the pipeline.
STEPS = [
    ("artwork", "Tác phẩm"),
    ("script", "Kịch bản"),
    ("voice", "Giọng đọc"),
    ("picks", "Chọn hình"),
    ("edit", "Dựng hình"),
    ("export", "Xuất video"),
]
NOT_BUILT = ("voice", "picks", "export")
STATES = ("done", "current", "available", "locked", "not_built", "no_data")

R_IMPORTED = "Dự án này được nhập từ bản dựng trước, chưa có dữ liệu cho bước này."
R_NOT_BUILT = "Bước này chưa được xây dựng."
R_NO_STORYBOARD = ("Chưa có storyboard. Storyboard được tạo sau hai bước Giọng đọc và Chọn hình, "
                   "hai bước này chưa được xây dựng.")
R_NO_PROJECT = "Chọn một tác phẩm và tạo dự án trước."


def _step(i: int, sid: str, label: str, state: str, reason: str = "", detail: str = "") -> dict:
    return {"id": sid, "n": i + 1, "label": label, "state": state, "reason": reason, "detail": detail}


def outputs_of(d: Path) -> list[dict]:
    """Rendered video files of a project (the same places `infer_stage` looks at)."""
    found: list[Path] = []
    for sub in ("render", "output", "out"):
        p = d / sub
        if p.is_dir() and not p.is_symlink():
            found += sorted(p.glob("*.mp4"))
    found += sorted(d.glob("*.mp4"))
    out = []
    for f in found:
        try:
            st = f.stat()
        except OSError:
            continue
        rel = f.relative_to(d).as_posix()
        out.append({"path": rel, "size": st.st_size, "url": f"/api/projects/{d.name}/files/{rel}"})
    return out


def _script_state(d: Path) -> tuple[str, str]:
    """('done'|'available', detail) from the approved script files."""
    from bti.script.store import DocumentCorrupt, load_narration, load_outline
    try:
        n, o = load_narration(d), load_outline(d)
    except (OSError, ValueError, DocumentCorrupt):
        return "available", "Tệp kịch bản không đọc được"
    if n is not None and n.approved_fresh() and o is not None and o.approved_fresh():
        return "done", "Lời dẫn đã duyệt"
    if o is not None and o.approved_fresh():
        return "available", "Dàn ý đã duyệt, chờ viết và duyệt lời dẫn"
    if o is not None:
        return "available", "Dàn ý đang soạn, chưa duyệt"
    return "available", "Chưa có dàn ý"


def _storyboard_state(d: Path) -> tuple[str, str]:
    """('done'|'available'|'locked', detail)."""
    f = d / "storyboard.json"
    if not f.is_file():
        return "locked", ""
    try:
        sb = read_json(f)
        ap = (sb.get("approvals") or {}).get("storyboard")
        if ap and ap.get("rev") == compute_rev(sb):
            return "done", "Storyboard đã duyệt"
        if ap:
            return "available", "Duyệt cũ: storyboard đã sửa sau khi duyệt"
        return "available", "Storyboard chưa duyệt"
    except Exception:
        return "available", "Storyboard không đọc được"


def _painting(d: Path, pj: dict) -> dict | None:
    if pj:
        return {"title": pj.get("title"), "artist": pj.get("artist"), "year": pj.get("year")}
    try:  # imported: take the first asset of the storyboard that names a work
        sb = read_json(d / "storyboard.json")
        for a in (sb.get("assets") or {}).values():
            if isinstance(a, dict) and a.get("title"):
                return {"title": a.get("title"), "artist": a.get("artist"), "year": a.get("year")}
    except Exception:
        pass
    return None


def template() -> dict:
    """No project: the library is step 1, everything after it waits for a project."""
    steps = []
    for i, (sid, label) in enumerate(STEPS):
        if sid == "artwork":
            steps.append(_step(i, sid, label, "current", detail="Chọn một tác phẩm và tạo dự án"))
        else:
            steps.append(_step(i, sid, label, "locked", R_NO_PROJECT))
    return {"project": None, "title": None, "painting": None, "stage": None, "imported": False, "protected": False, "artwork_key": None,
            "current": "artwork", "steps": steps, "outputs": []}


def compute(root: Path, pid: str) -> dict:
    from .library_api import stage_of
    d = root / pid
    has_project = (d / "project.json").is_file()
    pj = project_meta(d) if has_project else {}
    # imported = came from an earlier edit, has no book data. A project.json may exist only to carry flags (`protected`).
    imported = bool(pj.get("imported")) or (not has_project and not (d / "source").is_dir())
    has_sb = (d / "storyboard.json").is_file()
    outputs = outputs_of(d)

    title = pj.get("title")
    if not title and has_sb:
        try:
            title = read_json(d / "storyboard.json").get("title")
        except Exception:
            pass
    steps: list[dict] = []
    for i, (sid, label) in enumerate(STEPS):
        if sid in ("artwork", "script", "voice", "picks") and imported:
            steps.append(_step(i, sid, label, "no_data", R_IMPORTED))
        elif sid == "artwork":
            n = len(pj.get("sources") or [])
            steps.append(_step(i, sid, label, "done", detail=f"{n} nguồn sách" if n else "Đã chọn tác phẩm"))
        elif sid == "script":
            st, det = _script_state(d)
            steps.append(_step(i, sid, label, st, detail=det))
        elif sid == "edit":
            st, det = _storyboard_state(d)
            steps.append(_step(i, sid, label, st, R_NO_STORYBOARD if st == "locked" else "", det))
        else:  # voice, picks, export
            det = ""
            if sid == "export" and outputs:
                det = f"Đã có {len(outputs)} tệp video dựng sẵn"
            steps.append(_step(i, sid, label, "not_built", R_NOT_BUILT, det))

    # the step the stage calls for: the first one that is neither done nor without data nor locked
    current = next((s["id"] for s in steps if s["state"] in ("available", "current", "not_built")), steps[-1]["id"])
    for s in steps:
        if s["id"] == current and s["state"] == "available":
            s["state"] = "current"
    return {"project": pid, "title": title or pid, "painting": _painting(d, pj), "stage": stage_of(d),
            "imported": imported, "protected": is_protected(d), "artwork_key": pj.get("artwork_key"), "current": current, "steps": steps,
            "outputs": outputs}


def make_router(projects_root: Path, *, script_jobs=None, preview_jobs=None, on_delete=None) -> APIRouter:
    """`script_jobs` / `preview_jobs`: the job registries (a project with a running job cannot be deleted);
    `on_delete(pid)`: called after the folder is gone, to drop cached engine objects."""
    r = APIRouter(prefix="/api")
    root = Path(projects_root)

    def pdir(pid: str) -> Path:
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if not d.is_dir() or d.is_symlink() and not d.resolve().is_relative_to(root.resolve()):
            raise ApiError(404, "project not found")
        return d

    @r.get("/pipeline")
    def pipeline_template():
        return template()

    @r.get("/projects/{pid}/pipeline")
    def pipeline(pid: str):
        pdir(pid)
        return compute(root, pid)

    @r.delete("/projects/{pid}")
    def delete_project(pid: str, confirm: str = Query("")):
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if d.is_dir() and not d.is_symlink() and is_protected(d):
            raise ApiError(403, f"project {pid!r} is protected and cannot be deleted", protected=True)
        if d.is_symlink():
            raise ApiError(409, "project folder is a symbolic link; refusing to delete it")
        if not d.is_dir():
            raise ApiError(404, "project not found")
        rr = root.resolve()
        if d.resolve().parent != rr:  # never anything but a direct child of the projects root
            raise ApiError(400, "invalid project path")
        if confirm != pid:
            raise ApiError(422, "type the project id in `confirm` to delete it")
        busy = script_jobs.running(pid) if script_jobs is not None else None
        if busy is not None:
            raise ApiError(409, "a model job is running for this project; cancel it first (POST /api/jobs/{id}/cancel)",
                           job_id=busy.id)
        if preview_jobs is not None and preview_jobs.running(pid):
            raise ApiError(409, "a preview is being rendered for this project; wait for it to finish")
        shutil.rmtree(d)
        if on_delete is not None:
            on_delete(pid)
        return {"deleted": pid}

    return r
