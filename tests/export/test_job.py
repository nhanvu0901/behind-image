import json

import pytest

from bti.export import plan, run
from bti.export.errors import ExportError

from conftest import approve, real_timeline


def specs_of(project, settings):
    starts, end = real_timeline(project)
    return plan.plan_parts(starts, end, settings.fps, settings.part_seconds)


def test_full_export_writes_every_file_and_a_manifest(patch_run, project, settings, manager, fake_tools):
    job = run.start(project, settings=settings)
    assert job["state"] == "done", job.get("error")
    specs = specs_of(project, settings)
    assert [p["key"] for p in job["parts"]] == ["prepare"] + ["render-%d" % (i + 1) for i in range(len(specs))] + ["join", "mux", "finish"]
    edir = project / "export"
    assert sorted(f.name for f in edir.iterdir()) == ["arnolfini.mp4", "arnolfini.srt", "chapters.txt", "description.txt", "export.json"]
    m = run.read_manifest(project)
    assert m["frames"] == 24625 and m["duration"] == 820.833 and m["fps"] == 30 and m["chapters"] == 8
    assert m["cues"] == (edir / "arnolfini.srt").read_text(encoding="utf-8").count("-->") > 100
    assert m["cue_problems"] == []
    assert m["report_status"] == "ok", [i for i in m["report"] if i["status"] != "ok"]
    assert len(m["parts"]) == len(specs)
    assert "Subtitles available" in (edir / "description.txt").read_text(encoding="utf-8")
    assert len(fake_tools.calls("engine")) == len(specs)
    assert run.state(project, manager)["state"] == "done"


def test_the_mux_command_has_no_video_filter_and_a_soft_track(patch_run, project, settings, fake_tools):
    run.start(project, settings=settings)
    cmds = [c["argv"] for c in fake_tools.calls("ffmpeg")]
    assert cmds
    for argv in cmds:
        s = " ".join(argv)
        assert "-vf" not in s and "subtitles=" not in s and "-filter_complex" not in s and "ass=" not in s
    mux = next(a for a in cmds if "mov_text" in a)
    assert mux[mux.index("-c:v") + 1] == "copy"


def test_resume_renders_only_the_missing_parts(patch_run, project, settings, manager, fake_tools):
    specs = specs_of(project, settings)
    assert len(specs) >= 3
    fake_tools.env["FAKE_FAIL_T0"] = "%.6f" % specs[1].t0
    job = run.start(project, settings=settings)
    assert job["state"] == "error" and job["error_code"] == "render_failed"
    assert run.read_manifest(project) is None
    assert run.state(project, manager)["state"] == "none"
    assert not list((project / "cache" / "export" / "parts").glob("*.partial*"))
    before = len(fake_tools.calls("engine"))
    del fake_tools.env["FAKE_FAIL_T0"]
    job = run.start(project, settings=settings)
    assert job["state"] == "done"
    assert len(fake_tools.calls("engine")) - before == len(specs) - 1
    assert job["parts"][1].get("skipped") is True


def test_plan_counts_parts_that_already_exist(patch_run, project, settings):
    p0 = run.plan_for(project, settings)
    assert p0["parts_done"] == 0 and p0["frames"] == 24625 and p0["estimate_seconds"] > 0
    run.start(project, settings=settings)
    p1 = run.plan_for(project, settings)
    assert p1["parts_done"] == p1["parts"] and p1["estimate_seconds"] == 0


def test_frame_count_mismatch_stops_the_job(patch_run, project, settings, fake_tools):
    fake_tools.env["FAKE_SHORT"] = "1"
    job = run.start(project, settings=settings)
    assert job["state"] == "error" and job["error_code"] == "frames_mismatch"
    assert not (project / "export").exists() or not list((project / "export").glob("*.mp4"))


def test_cancel_leaves_no_export(patch_run, project, settings, fake_tools, monkeypatch):
    from fakelongjob import FakeManager
    mgr = FakeManager(cancel_after_part=1)
    monkeypatch.setattr(run, "get_manager", lambda: mgr)
    job = run.start(project, settings=settings)
    assert job["state"] == "cancelled"
    assert fake_tools.calls("engine") == []
    assert run.read_manifest(project) is None


def test_not_approved_and_stale_approval_and_missing_inputs(patch_run, project, settings):
    sb = json.loads((project / "storyboard.json").read_text())
    sb["title"] = "Changed"
    (project / "storyboard.json").write_text(json.dumps(sb))
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "approval_stale"
    sb["approvals"] = {"storyboard": None}
    (project / "storyboard.json").write_text(json.dumps(sb))
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "not_approved"
    approve(project)
    (project / "audio" / "mix.m4a").unlink()
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "no_audio"
    (project / "audio" / "mix.m4a").write_text("{}")
    (project / "timing.json").unlink()
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "no_timing"
    (project / "storyboard.json").unlink()
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "no_storyboard"


def test_a_second_start_while_running_is_busy(patch_run, project, settings, manager):
    manager.running.add(("arnolfini", "export"))
    with pytest.raises(ExportError) as e:
        run.start(project, settings=settings)
    assert e.value.code == "busy"


def test_state_goes_stale_when_the_storyboard_or_audio_or_files_change(patch_run, project, settings, manager):
    run.start(project, settings=settings)
    assert run.state(project, manager)["state"] == "done"
    audio = project / "audio" / "mix.m4a"
    audio.write_text(json.dumps({"kind": "audio", "codec": "aac", "duration": 820.8333, "x": 1}))
    s = run.state(project, manager)
    assert s["state"] == "stale" and s["reason"] == "audio"
    run.start(project, settings=settings)
    assert run.state(project, manager)["state"] == "done"
    sb = json.loads((project / "storyboard.json").read_text())
    sb["title"] = "New title"
    (project / "storyboard.json").write_text(json.dumps(sb))
    assert run.state(project, manager)["reason"] == "storyboard"
    approve(project)
    run.start(project, settings=settings)
    assert run.state(project, manager)["state"] == "done"
    (project / "export" / "arnolfini.srt").unlink()
    assert run.state(project, manager)["reason"] == "files"


def test_state_running_when_the_manager_has_an_active_job(project):
    class M:
        def active(self, pid, kind=None):
            return {"id": "j1"} if kind == "export" else None
    assert run.state(project, M())["state"] == "running"


def test_a_new_export_of_a_new_revision_removes_old_parts(patch_run, project, settings):
    run.start(project, settings=settings)
    parts = project / "cache" / "export" / "parts"
    old = set(p.name for p in parts.glob("*.mp4"))
    sb = json.loads((project / "storyboard.json").read_text())
    sb["title"] = "Another"
    (project / "storyboard.json").write_text(json.dumps(sb))
    approve(project)
    run.start(project, settings=settings)
    new = set(p.name for p in parts.glob("*.mp4"))
    assert new and not (old & new)


def test_a_project_deleted_during_the_export_is_not_brought_back(patch_run, project, settings, monkeypatch):
    import shutil
    orig = run.render.join_parts

    def join_then_delete(*a, **k):
        r = orig(*a, **k)
        shutil.rmtree(project)
        return r
    monkeypatch.setattr(run.render, "join_parts", join_then_delete)
    job = run.start(project, settings=settings)
    assert job["state"] == "error"
    assert not project.exists()


def test_the_real_engine_timeline_matches_the_storyboard(project):
    starts, end = run.engine_timeline(project, "rev-x")
    assert end == pytest.approx(820.8333) and starts[0] == 0.0 and len(starts) == 82


def test_audio_length_mismatch_fails_the_card(patch_run, project, settings):
    (project / "audio" / "mix.m4a").write_text(json.dumps({"kind": "audio", "codec": "aac", "duration": 800.0}))
    approve(project)
    run.start(project, settings=settings)
    item = {i["key"]: i for i in run.read_manifest(project)["report"]}["audio_length"]
    assert item["status"] == "fail" and item["value"] == 800.0 and item["expected"] == 820.83
