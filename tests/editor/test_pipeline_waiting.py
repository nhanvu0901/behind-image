"""SU-003 / SU-008: a step that already has output is never hidden behind the locked page. `waiting` + `blocked_by` + `has_output`."""
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.editor import pipeline_api as pa  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.library import projects as projects_mod  # noqa: E402


def mk(states, **extra):
    """Steps as compute() builds them before marking: {id: state}."""
    out = []
    for i, (sid, label) in enumerate(pa.STEPS):
        out.append(pa._step(i, sid, label, states.get(sid, "locked"), "r" if states.get(sid, "locked") == "locked" else ""))
    return out


def by(steps):
    return {s["id"]: s for s in steps}


def sts(voice="none", picks="none", export="none", **extra):
    return {"voice": {"state": voice, **extra.get("voice", {})}, "picks": {"state": picks, **extra.get("picks", {})}, "export": {"state": export}}


def test_everything_made_and_the_narration_edited_gives_waiting_steps_not_done_or_locked():
    steps = mk({"artwork": "done", "script": "current", "voice": "locked", "picks": "locked", "edit": "done", "export": "done"})
    pa._mark_blocking(steps, sts(voice="stale", picks="stale", export="done"), True, [])
    s = by(steps)
    for sid in ("voice", "picks", "edit", "export"):
        assert s[sid]["state"] == "waiting" and s[sid]["blocked_by"] == "script" and s[sid]["has_output"] is True, sid
    assert s["script"].get("blocked_by") is None


def test_a_locked_step_without_output_names_the_step_to_do_first():
    steps = mk({"artwork": "done", "script": "current", "voice": "locked", "picks": "locked", "edit": "locked", "export": "locked"})
    pa._mark_blocking(steps, sts(), False, [])
    s = by(steps)
    assert [s[x]["state"] for x in ("voice", "picks", "edit", "export")] == ["locked"] * 4
    assert [s[x]["blocked_by"] for x in ("voice", "picks", "edit", "export")] == ["script"] * 4
    assert [s[x]["has_output"] for x in ("voice", "picks", "edit", "export")] == [False] * 4


def test_edit_and_export_name_the_first_unfinished_step_before_them():
    steps = mk({"artwork": "done", "script": "done", "voice": "done", "picks": "current", "edit": "locked", "export": "locked"})
    pa._mark_blocking(steps, sts(voice="done", picks="none"), False, [])
    s = by(steps)
    assert s["edit"]["blocked_by"] == "picks" and s["export"]["blocked_by"] == "picks" and s["voice"]["blocked_by"] is None


def test_voice_stale_after_approval_makes_the_storyboard_and_export_wait_on_the_voice():
    steps = mk({"artwork": "done", "script": "done", "voice": "available", "picks": "done", "edit": "done", "export": "done"})
    pa._mark_blocking(steps, sts(voice="stale", picks="done", export="done"), True, [])
    s = by(steps)
    assert s["voice"]["state"] == "available" and s["voice"]["blocked_by"] is None
    assert s["edit"]["state"] == "waiting" and s["edit"]["blocked_by"] == "voice"
    assert s["export"]["state"] == "waiting" and s["export"]["blocked_by"] == "voice"


def test_a_finished_project_has_no_blockers():
    steps = mk({"artwork": "done", "script": "done", "voice": "done", "picks": "done", "edit": "done", "export": "done"})
    pa._mark_blocking(steps, sts(voice="done", picks="done", export="done"), True, [])
    assert all(s.get("blocked_by") is None and s["state"] == "done" for s in steps[1:])


def test_imported_steps_without_data_are_not_blockers():
    steps = mk({"artwork": "no_data", "script": "no_data", "voice": "no_data", "picks": "no_data", "edit": "available", "export": "locked"})
    pa._mark_blocking(steps, sts(), True, [])
    s = by(steps)
    assert s["edit"]["blocked_by"] is None and s["edit"]["state"] == "available"
    assert s["export"]["blocked_by"] == "edit" and s["export"]["state"] == "locked" and s["export"]["has_output"] is False
    assert "voice" in s and s["voice"]["state"] == "no_data" and "blocked_by" not in s["voice"]


def test_an_old_video_file_counts_as_output_of_the_export_step():
    steps = mk({"artwork": "done", "script": "done", "voice": "done", "picks": "done", "edit": "available", "export": "locked"})
    pa._mark_blocking(steps, sts(voice="done", picks="done"), True, [{"path": "render/x.mp4"}])
    assert by(steps)["export"]["state"] == "waiting" and by(steps)["export"]["blocked_by"] == "edit"


def test_every_step_keeps_the_old_fields():
    steps = mk({"artwork": "done", "script": "current", "voice": "locked", "picks": "locked", "edit": "locked", "export": "locked"})
    pa._mark_blocking(steps, sts(), False, [])
    for s in steps:
        assert {"id", "n", "label", "state", "reason", "detail"} <= set(s)
    assert "waiting" in pa.STATES


def test_compute_marks_the_voice_waiting_when_the_narration_is_edited_after_it(tmp_path, monkeypatch):
    src = REPO / "projects" / "arnolfini-from-books"
    if not (src / "project.json").is_file():
        pytest.skip("sample project is missing")
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(src, root / "arn", ignore=shutil.ignore_patterns("script", "cache", "history"))
    monkeypatch.setattr(projects_mod, "stage_states", lambda d: {"voice": {"state": "stale", "detail": "x", "counts": {"cached": 12}},
                                                                 "picks": {"state": "none", "detail": ""}, "export": {"state": "none", "detail": ""}})
    b = pa.compute(root, "arn")
    s = by(b["steps"])
    assert s["script"]["state"] in ("current", "available")             # the narration is not approved
    assert s["voice"]["state"] == "waiting" and s["voice"]["blocked_by"] == "script" and s["voice"]["has_output"] is True
    assert s["picks"]["state"] == "locked" and s["picks"]["blocked_by"] == "script" and s["picks"]["has_output"] is False
    assert b["current"] == "script"
