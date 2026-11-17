"""The pipeline of a project, computed in ONE place: the ordered steps with their state and the reason.

`GET /api/projects/{pid}/pipeline` feeds the stepper and the home list of the app shell.
`GET /api/pipeline` is the same list with no project (the "new video" flow, which starts in the library).
`DELETE /api/projects/{pid}?confirm=<pid>` removes a project folder; the protected projects are refused.
Mounted from app.py. Reads files only (never the engine), so it is cheap enough to call for every project."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Query

from bti.script.store import DocumentCorrupt, forget_lock, read_object, script_lock

from bti.library import projects as projects_mod

from .common import ApiError, forget_save_lock, read_json, save_lock, storyboard_approval, valid_pid
from bti.fsio import atomic_replace

DELETE_WAIT_S = 2.0          # how long DELETE waits for a save in flight before it answers 409


def project_meta(d: Path, strict: bool = False) -> dict:
    """project.json of a folder as a dict ({} when there is none). When the file is there but unreadable or not an object:
    `strict` raises DocumentCorrupt (409 `data_error: "project"` for the page); otherwise {} (used where the answer must not
    fail: the protected check of a delete, so that a damaged project can still be removed)."""
    try:
        return read_object(d / "project.json", "project") or {}
    except DocumentCorrupt:
        if strict:
            raise
        return {}


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
STATES = ("done", "current", "available", "locked", "not_built", "no_data", "waiting")     # `not_built` is kept for old clients; no step is in it now
# `waiting`: the step HAS output, but an earlier document is being edited (or redone) and is not approved again yet. The step still
# opens (read-only where acting would be wrong) and says what it waits for in `blocked_by`.

# the steps a step stands on, in pipeline order: its `blocked_by` is the first of them that is not done
DEPENDS_ON = {"voice": ("script",), "picks": ("script",), "edit": ("script", "voice", "picks"), "export": ("script", "voice", "picks", "edit")}

R_IMPORTED = "Dự án này được nhập từ bản dựng trước, chưa có dữ liệu cho bước này."
R_NEEDS_NARRATION = "Cần duyệt lời dẫn ở bước Kịch bản trước."
R_NO_STORYBOARD = "Chưa có storyboard. Xong hai bước Giọng đọc và Chọn hình để dựng bản nháp storyboard."
R_NO_STORYBOARD_VOICE = "Chưa có storyboard. Còn thiếu bước Giọng đọc để dựng bản nháp."
R_NO_STORYBOARD_PICKS = "Chưa có storyboard. Còn thiếu bước Chọn hình để dựng bản nháp."
R_NEEDS_APPROVED = "Cần duyệt storyboard ở bước Dựng hình trước khi xuất video."
R_NO_PROJECT = "Chọn một tác phẩm và tạo dự án trước."


def _step(i: int, sid: str, label: str, state: str, reason: str = "", detail: str = "", work: str | None = None) -> dict:
    """`work` is the stage package's own state (none|running|stale|done) for the steps that have one, so the stepper can say
    "Đang chạy" or "Cần làm lại" next to the step's state."""
    out = {"id": sid, "n": i + 1, "label": label, "state": state, "reason": reason, "detail": detail}
    if work is not None:
        out["work"] = work
    return out


def _stage_step(i: int, sid: str, label: str, st: dict, unlocked: bool, locked_reason: str) -> dict:
    """A step run by a stage package (voice, picks, export): done when the package says done, else open or locked."""
    work = st.get("state", "none")
    detail = str(st.get("detail") or "")
    if work == "done":
        return _step(i, sid, label, "done", detail=detail, work=work)
    if not unlocked:
        return _step(i, sid, label, "locked", locked_reason, detail=detail, work=work)
    return _step(i, sid, label, "available", detail=detail, work=work)


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
    from bti.script.store import load_narration, load_outline, narration_approval
    try:
        n, o = load_narration(d), load_outline(d)
    except (OSError, ValueError, DocumentCorrupt):
        return "available", "Tệp kịch bản không đọc được"
    na = narration_approval(n, o)         # the same function the stage and GET /narration use
    if na["approved"]:
        return "done", "Lời dẫn đã duyệt"
    if na["reason"] == "outline_changed":
        return "available", "Dàn ý đã đổi sau khi duyệt lời dẫn: duyệt lại lời dẫn"
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
        sa = storyboard_approval(read_json(f))      # the same function `infer_stage` uses
        if sa == "fresh":
            return "done", "Storyboard đã duyệt"
        if sa == "stale":
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


def _has_output(sid: str, sts: dict, has_sb: bool, outputs: list) -> bool:
    """Whether a step has made something the owner could lose sight of (a voice, picks, a storyboard, an export or a video file)."""
    if sid in ("voice", "picks"):
        st = sts[sid]
        return st.get("state") in ("done", "stale") or bool((st.get("counts") or {}).get("cached")) or bool(st.get("picked")) or bool(st.get("main_asset"))
    if sid == "edit":
        return has_sb
    if sid == "export":
        return sts["export"].get("state") in ("done", "stale") or bool(outputs)
    return False


def _mark_blocking(steps: list[dict], sts: dict, has_sb: bool, outputs: list) -> None:
    """Add `blocked_by` (the id of the first earlier step this one stands on that is not done, or None) and `has_output` to steps 3 to 6
    (fields are added, none renamed). A step with output that is blocked is `waiting` and never `done` or `locked`: its page stays
    open. A step without output that is blocked is `locked`."""
    by = {s["id"]: s for s in steps}
    for s in steps:
        sid = s["id"]
        if sid not in DEPENDS_ON or s["state"] == "no_data":
            continue
        blocker = next((d for d in DEPENDS_ON[sid] if by[d]["state"] not in ("done", "no_data")), None)
        out = _has_output(sid, sts, has_sb, outputs)
        s["blocked_by"], s["has_output"] = blocker, out
        if not blocker:
            continue
        label = by[blocker]["label"]
        if out and s["state"] in ("done", "locked", "available", "current"):
            s["state"] = "waiting"
            s["reason"] = "Chờ duyệt lại lời dẫn ở bước Kịch bản." if blocker == "script" else f"Chờ xong bước {label}."
        elif not out and s["state"] in ("available", "current"):
            s["state"] = "locked"
            s["reason"] = s["reason"] or f"Cần xong bước {label} trước."
        elif s["state"] == "locked" and not s["reason"]:
            s["reason"] = f"Cần xong bước {label} trước."


def compute(root: Path, pid: str) -> dict:
    from .library_api import stage_of
    d = root / pid
    has_project = (d / "project.json").is_file()
    pj = project_meta(d, strict=True) if has_project else {}
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
    sts = projects_mod.stage_states(d)
    script_st, script_det = _script_state(d) if not imported else ("no_data", "")
    narration_ok = script_st == "done"
    sb_state, sb_det = _storyboard_state(d)
    voice_done, picks_done = sts["voice"]["state"] == "done", sts["picks"]["state"] == "done"
    steps: list[dict] = []
    for i, (sid, label) in enumerate(STEPS):
        if sid in ("artwork", "script", "voice", "picks") and imported:
            steps.append(_step(i, sid, label, "no_data", R_IMPORTED))
        elif sid == "artwork":
            srcs = pj.get("sources")
            if srcs is not None and not isinstance(srcs, list):
                raise DocumentCorrupt("project.json is corrupt: sources must be a list", "project")
            n = len(srcs or [])
            steps.append(_step(i, sid, label, "done", detail=f"{n} nguồn sách" if n else "Đã chọn tác phẩm"))
        elif sid == "script":
            steps.append(_step(i, sid, label, script_st, detail=script_det))
        elif sid in ("voice", "picks"):
            # steps 3 and 4 both open when the narration is approved, in either order or at the same time
            steps.append(_stage_step(i, sid, label, sts[sid], narration_ok, R_NEEDS_NARRATION))
        elif sid == "edit":
            if has_sb:
                steps.append(_step(i, sid, label, sb_state, "", sb_det))
            elif voice_done and picks_done:
                dr = projects_mod._safe_state("bti.draft", d)           # the draft panel is what step 5 shows without a storyboard
                steps.append(_step(i, sid, label, "available", detail=str(dr.get("detail") or "Dựng bản nháp storyboard từ giọng đọc và hình đã chọn"),
                                   work=dr.get("state")))
            else:
                why = R_NO_STORYBOARD_VOICE if picks_done else R_NO_STORYBOARD_PICKS if voice_done else R_NO_STORYBOARD
                steps.append(_step(i, sid, label, "locked", why))
        else:  # export: opens when the storyboard approval is fresh; an old video file is shown as a detail
            st = dict(sts["export"])
            if st.get("state") == "none" and outputs:
                st["detail"] = f"Đã có {len(outputs)} tệp video dựng sẵn"
            steps.append(_stage_step(i, sid, label, st, sb_state == "done", R_NEEDS_APPROVED))

    _mark_blocking(steps, sts, has_sb, outputs)

    # the step the stage calls for: the first one that is neither done nor without data nor locked
    current = next((s["id"] for s in steps if s["state"] in ("available", "current", "not_built")), steps[-1]["id"])
    for s in steps:
        if s["id"] == current and s["state"] == "available":
            s["state"] = "current"
    return {"project": pid, "title": title or pid, "painting": _painting(d, pj), "stage": stage_of(d, sts),
            "imported": imported, "has_storyboard": has_sb, "protected": is_protected(d), "artwork_key": pj.get("artwork_key"), "current": current, "steps": steps,
            "outputs": outputs}


def make_router(projects_root: Path, *, script_jobs=None, preview_jobs=None, longjobs=None, on_delete=None) -> APIRouter:
    """`script_jobs` / `preview_jobs` / `longjobs`: the job registries (a project with a running job cannot be deleted);
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
        """Remove a project. It takes the project's script lock and its storyboard lock (in that order, see bti/script/store.py),
        each for at most 2 seconds: when a save holds one the answer is 409 and nothing is removed. Under both locks the folder is
        renamed away in one step (so no writer can find it, and the slug is free at once), then deleted."""
        if not valid_pid(pid):
            raise ApiError(404, "project not found")
        d = root / pid
        if d.is_dir() and not d.is_symlink():
            try:
                project_meta(d, strict=True)
            except DocumentCorrupt:
                # the server cannot tell whether this project is protected: nothing is removed
                raise ApiError(409, f"the project file of {pid!r} (project.json) is damaged, so the server cannot tell whether the "
                                    "project is protected; repair or remove the folder by hand", data_error="project",
                               code="project_file_damaged")
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
        sweep_trash(root)
        busy_msg = ("a save of this project is in progress; try again in a moment", "project_busy")
        sl, bl = script_lock(d), save_lock(d)
        if not sl.acquire(timeout=DELETE_WAIT_S):
            raise ApiError(409, busy_msg[0], code=busy_msg[1])
        trash = None
        try:
            if not bl.acquire(timeout=DELETE_WAIT_S):
                raise ApiError(409, busy_msg[0], code=busy_msg[1])
            try:
                if not d.is_dir():
                    raise ApiError(404, "project not found")
                busy = script_jobs.running(pid) if script_jobs is not None else None
                if busy is not None:
                    raise ApiError(409, "a model job is running for this project; cancel it first (POST /api/jobs/{id}/cancel)",
                                   job_id=busy.id)
                lj = longjobs.active(pid) if longjobs is not None else None
                if lj is not None:
                    raise ApiError(409, "a long job (voice, draft, export...) is running for this project; cancel it first "
                                        "(POST /api/longjobs/{id}/cancel)", code="longjob_running", job_id=lj["id"], kind=lj["kind"])
                if preview_jobs is not None and preview_jobs.running(pid):
                    raise ApiError(409, "a preview is being rendered for this project; wait for it to finish")
                trash = root / f".deleting-{pid}-{uuid.uuid4().hex[:8]}"
                try:
                    atomic_replace(d, trash)           # one atomic step: the project is gone for every other request
                except OSError as e:
                    trash = None
                    raise ApiError(409, f"the project folder could not be removed ({e.strerror or type(e).__name__})",
                                   code="project_busy")
            finally:
                bl.release()
        finally:
            sl.release()
        forget_lock(d)
        forget_save_lock(d)
        try:
            from bti.picks.doc import forget_lock as forget_picks_lock
            forget_picks_lock(d)
        except Exception:          # noqa: BLE001 - only frees one lock object
            pass
        if on_delete is not None:
            on_delete(pid)
        remove_tree(trash)
        return {"deleted": pid}

    return r


def remove_tree(path: Path | None) -> None:
    """Delete a folder that nobody can reach by a project id any more; try again when a writer still finishing adds a file."""
    if path is None:
        return
    for _ in range(5):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return


def sweep_trash(root: Path) -> None:
    """Folders left by a delete that could not finish removing its files (a name that is never a project id)."""
    try:
        for f in root.glob(".deleting-*"):
            if f.is_dir() and not f.is_symlink():
                remove_tree(f)
    except OSError:
        pass
