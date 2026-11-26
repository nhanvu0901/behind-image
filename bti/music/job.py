"""A model job that selects and places music, serialized with the title agent."""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from bti.draft import run as draft_run
from bti.draft.inputs import DraftError
from bti.picks.auto import session
from bti.script.brief import REPO_ROOT
from . import helper, inputs, store
from .document import MusicError

# The existing title job family participates in the project's existing agent lock.
# A distinct action in meta identifies the job without changing draft/picks code.
KIND = "title"
ROLE = "music"
LIMITS = session.Limits(minutes=10, steps=40, repairs=1)
WORK_ROOT = REPO_ROOT / "run" / "music-work"


def _refuse(code, detail, retry="after_fix"):
    exc = MusicError(detail)
    exc.code, exc.retry = code, retry
    return exc


def _workspace(data):
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="music-", dir=WORK_ROOT))
    (root / "inputs").mkdir()
    (root / "out").mkdir()
    (root / "inputs" / "context.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    task = (REPO_ROOT / "skills" / "music" / "TASK.template.md").read_text(encoding="utf-8")
    (root / "TASK.md").write_text(task, encoding="utf-8")
    if os.name == "nt":
        (root / "check.cmd").write_text('@echo off\r\nset "PYTHONPATH=%s"\r\n"%s" -m bti.music.helper check\r\n' % (REPO_ROOT, sys.executable), encoding="utf-8")
    else:
        f = root / "check"
        f.write_text("#!/bin/sh\nPYTHONPATH='%s' exec '%s' -m bti.music.helper check\n" % (str(REPO_ROOT).replace("'", "'\\''"), sys.executable.replace("'", "'\\''")), encoding="utf-8")
        f.chmod(f.stat().st_mode | stat.S_IXUSR)
    return root


def start(pid, pdir, *, actor=None, model=None, by_run=False, manager=None, **seams):
    pdir = Path(pdir)
    if model is not None and (not isinstance(model, str) or draft_run._bad_model_name(model)):
        raise _refuse("bad_model", "the model name is invalid")
    data = inputs.load(pdir)
    base_rev = store.revision(store.read(pdir))
    resolved = draft_run._resolve(pdir, ROLE, model)
    try:
        session.check_installed(resolved.model)
    except DraftError as exc:
        raise _refuse(exc.code, exc.message) from exc
    if manager is None:
        from bti.longjob import manager
    other = draft_run.other_agent_job(pid, "music", manager, run_ok=by_run)
    if other:
        err = _refuse("agent_job_running", "another agent is working on this project", "later")
        err.job_id = other.get("id")
        raise err
    from bti.longjob import Part, PartError
    from bti.engine.timing import Timing

    def run(ctx):
        if ctx.cancelled():
            return None
        root = _workspace(data)
        ctx.progress(0.02, "Đã chuẩn bị dữ liệu chọn nhạc.")
        try:
            result = session.run_session(root, model=resolved.model, project_dir=pdir, ctx=ctx, label="Chọn nhạc", limits=LIMITS,
                                         check_fn=lambda: helper.run_check(root).problems(), python=seams.get("python"),
                                         guard_factory=seams.get("guard_factory"), allow=session.allow_rules(helpers=("check",)))
        except DraftError as exc:
            raise PartError(exc.code, session.refuse_text(exc)) from exc
        if result.status == "cancelled" or ctx.cancelled():
            return None
        report = helper.run_check(root)
        if result.status != "ok" or not report.ok:
            raise PartError(getattr(result, "code", None) or "music_no_output", getattr(result, "message", "") or report.text())
        try:
            current = inputs.load(pdir)
        except MusicError as exc:
            raise PartError("stale_revision", "Dữ liệu dựng nhạc đã thay đổi. Hãy chọn nhạc lại.") from exc
        if any(current[key] != data[key] for key in ("storyboard", "timing", "painting", "library")):
            raise PartError("stale_revision", "Dữ liệu dựng nhạc đã thay đổi. Hãy chọn nhạc lại.")
        try:
            doc = store.set_document(pdir, report.value, current["library"], Timing(current["timing"]), current["duration"],
                                     landmarks=current["landmarks"], base_rev=base_rev)
        except MusicError as exc:
            raise PartError(exc.code, exc.detail) from exc
        ctx.progress(1.0, "Đã chọn nhạc.")
        return {"cues": len(doc["cues"]), "agent": resolved.public()}

    try:
        return manager.start(kind=KIND, pid=pid, project_dir=pdir, parts=[Part(key="music", title="Chọn nhạc", run=run, est_seconds=90)],
                             meta={"action": "music", "model": resolved.model, "agent": resolved.public(), "requested_by": actor})
    except Exception as exc:
        if type(exc).__name__ == "Busy":
            raise _refuse("agent_job_running", "another agent is working on this project", "later") from exc
        raise
