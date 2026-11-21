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
    assert sorted(f.name for f in edir.iterdir()) == ["arnolfini.mp4", "chapters.txt", "description.txt", "export.json"]
    assert not list((project / "cache" / "export").glob("*.srt"))
    m = run.read_manifest(project)
    assert m["frames"] == 24625 and m["duration"] == 820.833 and m["fps"] == 30 and m["chapters"] == 8
    assert m["report_status"] == "ok", [i for i in m["report"] if i["status"] != "ok"]
    assert len(m["parts"]) == len(specs)
    assert "Subtitles available" not in (edir / "description.txt").read_text(encoding="utf-8")
    assert len(fake_tools.calls("engine")) == len(specs)
    assert run.state(project, manager)["state"] == "done"


def test_the_mux_command_has_no_video_filter_or_subtitle_track(patch_run, project, settings, fake_tools):
    run.start(project, settings=settings)
    cmds = [c["argv"] for c in fake_tools.calls("ffmpeg")]
    assert cmds
    for argv in cmds:
        s = " ".join(argv)
        assert "-vf" not in s and "subtitles=" not in s and "-filter_complex" not in s and "ass=" not in s
    mux = next(a for a in cmds if "-map_chapters" in a)
    assert "-c:s" not in mux and not any(x.endswith(":s:0") for x in mux)
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
    (project / "export" / "chapters.txt").unlink()
    assert run.state(project, manager)["reason"] == "files"


def test_state_running_when_the_manager_has_an_active_job(project):
    class M:
        def active(self, pid, kind=None):
            return {"id": "j1"} if kind == "export" else None
    assert run.state(project, M())["state"] == "running"


def test_a_new_export_of_a_new_revision_reuses_unchanged_parts_and_removes_stale_ones(patch_run, project, settings, fake_tools):
    specs = specs_of(project, settings)
    job1 = run.start(project, settings=settings)
    assert job1["state"] == "done"
    assert job1["result"]["parts_total"] == len(specs)
    assert job1["result"]["parts_rendered"] == len(specs)
    assert job1["result"]["parts_reused"] == 0
    parts = project / "cache" / "export" / "parts"
    old_list = sorted(parts.glob("*.mp4"))
    assert len(old_list) == len(specs)

    # Pure non-visual edit (title): every part key matches and 0 parts re-render.
    sb = json.loads((project / "storyboard.json").read_text())
    sb["title"] = "Another"
    (project / "storyboard.json").write_text(json.dumps(sb))
    approve(project)
    calls_before = len(fake_tools.calls("engine"))
    job2 = run.start(project, settings=settings)
    assert job2["state"] == "done"
    assert len(fake_tools.calls("engine")) == calls_before
    assert job2["result"]["parts_rendered"] == 0
    assert job2["result"]["parts_reused"] == len(specs)
    assert sorted(parts.glob("*.mp4")) == old_list

    # Edit a single visual parameter in shot s0005: only its part (and any overlap) re-renders; all others are reused.
    sb = json.loads((project / "storyboard.json").read_text())
    target_shot = next(s for s in sb["shots"] if s["id"] == "s0005")
    t_shot = float(target_shot["start"]["_t"] if isinstance(target_shot["start"], dict) and "_t" in target_shot["start"] else target_shot["start"].get("t", 0.0) if isinstance(target_shot["start"], dict) else 0.0)
    if "w" in target_shot["start"]:
        tm = json.loads((project / "timing.json").read_text())
        t_shot = float(tm["words"][target_shot["start"]["w"]]["s"]) + float(target_shot["start"].get("off", 0.0) or 0.0)
    target_shot["overlays"] = [{"id": "o_test", "technique": "X-ANN-01", "start": {"t": t_shot + 0.1}, "dur": 1.0, "params": {"text": "Changed annotation"}}]
    (project / "storyboard.json").write_text(json.dumps(sb))
    approve(project)

    p_plan = run.plan_for(project, settings)
    assert 1 <= p_plan["parts_to_render"] <= 2 and p_plan["parts_reused"] == len(specs) - p_plan["parts_to_render"]

    calls_before = len(fake_tools.calls("engine"))
    job3 = run.start(project, settings=settings)
    assert job3["state"] == "done"
    assert len(fake_tools.calls("engine")) - calls_before == p_plan["parts_to_render"]
    assert job3["result"]["parts_rendered"] == p_plan["parts_to_render"]
    assert job3["result"]["parts_reused"] == p_plan["parts_reused"]
    new_list = sorted(parts.glob("*.mp4"))
    assert len(new_list) == len(specs)
    kept = set(p.name for p in old_list) & set(p.name for p in new_list)
    replaced = set(p.name for p in old_list) - set(p.name for p in new_list)
    assert len(kept) == len(specs) - p_plan["parts_to_render"]
    assert len(replaced) == p_plan["parts_to_render"]


def test_global_style_change_rerenders_all_parts(patch_run, project, settings, fake_tools, monkeypatch):
    from bti.export import partkey
    specs = specs_of(project, settings)
    run.start(project, settings=settings)
    parts = project / "cache" / "export" / "parts"
    old_names = {p.name for p in parts.glob("*.mp4")}

    monkeypatch.setattr(partkey, "style_signature", lambda sid, style_root=None: "v2-" + str(sid))
    calls_before = len(fake_tools.calls("engine"))
    job = run.start(project, settings=settings)
    assert job["state"] == "done"
    assert len(fake_tools.calls("engine")) - calls_before == len(specs)
    assert job["result"]["parts_rendered"] == len(specs) and job["result"]["parts_reused"] == 0
    new_names = {p.name for p in parts.glob("*.mp4")}
    assert len(new_names) == len(specs) and not (old_names & new_names)


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
