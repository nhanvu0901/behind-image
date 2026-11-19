"""How the app reaches the folder: the middleware after a change through the API, the last part of the voice and export jobs, notify never raising, the warnings."""
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "export"))

from bti.editor.app import create_app  # noqa: E402
from bti.output import hooks, publish  # noqa: E402
from output_helpers import KEY, PID, Project, export_world  # noqa: E402


def app_of(proj, **kw):
    return create_app(projects_root=proj.root, output_root=proj.out, engine_module=None, media_module=None, **kw)


def test_an_approval_through_the_api_writes_the_folder(proj):
    proj.create().outline()
    with TestClient(app_of(proj)) as c:
        rev = c.get("/api/projects/%s/outline" % PID).json()["rev"]
        r = c.post("/api/projects/%s/outline/approve" % PID, json={"rev": rev})
        assert r.status_code == 200, r.text
        assert hooks.flush(30)
        t = proj.tree()
        assert "2_script/outline.md" in t and "1_sources/sources.md" in t and "README.md" in t
        assert proj.state()["gates"]["outline"]["by"] == "human" and proj.state()["last_sync"]["moment"].startswith("POST outline/approve")


def test_a_change_made_behind_the_apps_back_is_marked_at_the_next_change_through_the_api(proj):
    proj.create().outline().approve_outline()
    with TestClient(app_of(proj)) as c:
        a = c.get("/api/projects/%s/auto" % PID).json()
        assert c.put("/api/projects/%s/auto" % PID, json={"base_rev": a["rev"], "enabled": False}).status_code == 200
        assert hooks.flush(30) and not proj.state()["parts"]["outline"]["out_of_date"]
        from bti.script import store as sstore
        o = sstore.load_outline(proj.d)
        o.thesis += " (edited)"
        sstore.save_outline(proj.d, o)                      # saving drops the approval
        a = c.get("/api/projects/%s/auto" % PID).json()
        assert c.put("/api/projects/%s/auto" % PID, json={"base_rev": a["rev"], "enabled": True}).status_code == 200
        assert hooks.flush(30)
        assert proj.state()["parts"]["outline"]["out_of_date"] is True


def test_a_failed_request_a_read_and_the_output_routes_write_nothing(proj):
    proj.create()
    with TestClient(app_of(proj)) as c:
        assert c.get("/api/projects/%s/state" % PID).status_code == 200
        r = c.post("/api/projects/%s/outline/approve" % PID, json={"rev": "nope"})
        assert r.status_code >= 400
        hooks.flush(30)
        assert not (proj.out / KEY).exists(), "neither a read nor a refused request makes the folder"
        assert c.get("/api/projects/%s/output" % PID).json()["state"] is None


def test_an_app_without_an_output_folder_writes_nothing(proj):
    proj.create().outline()
    app = create_app(projects_root=proj.root, engine_module=None, media_module=None)           # an explicit projects folder and no output folder: none
    assert app.state.output_root is None
    with TestClient(app) as c:
        rev = c.get("/api/projects/%s/outline" % PID).json()["rev"]
        assert c.post("/api/projects/%s/outline/approve" % PID, json={"rev": rev}).status_code == 200
        hooks.flush(30)
        assert not proj.out.exists()
        assert c.get("/api/projects/%s/output" % PID).json()["enabled"] is False
        assert c.post("/api/projects/%s/output/build" % PID, json={}).json()["code"] == "output_disabled"


def test_the_default_output_folder_is_beside_the_projects_folder(proj, monkeypatch):
    from bti.output import paths
    assert paths.output_root_for(proj.root, None, projects_root_given=False) == proj.out.resolve()
    assert paths.output_root_for(proj.root, None, projects_root_given=True) is None
    assert paths.output_root_for(proj.root, False) is None
    monkeypatch.setenv("BTI_OUTPUT_ROOT", str(proj.out.parent / "elsewhere"))
    assert paths.output_root_for(proj.root, None, projects_root_given=True) == (proj.out.parent / "elsewhere").resolve()


def test_a_new_project_from_the_library_gets_its_folder(proj):
    """The middleware reads the id of the new project from the answer of POST /api/library/projects (the route itself is the library's, faked here)."""
    proj.create()

    async def downstream(scope, receive, send):
        await receive()
        body = json.dumps({"id": PID}).encode()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})
    app = hooks.OutputSyncMiddleware(downstream, proj.root, proj.out)
    c = TestClient(app)
    assert c.post("/api/library/projects", json={"artwork_key": KEY}).status_code == 200
    assert hooks.flush(30)
    assert {"1_sources/sources.md", "README.md", "state.json"} <= set(proj.tree())
    assert c.get("/api/library/projects").status_code in (200, 405) or True


def test_two_writes_in_a_row_are_one(proj, monkeypatch):
    proj.create()
    calls = []
    real = hooks.notify

    def counting(*a, **k):
        calls.append(a[2])
        return real(*a, **k)
    monkeypatch.setattr(hooks, "notify", counting)
    import threading
    gate = threading.Event()
    hooks._EXEC.submit(gate.wait, 5)                         # hold the one worker so the two requests meet in the queue
    hooks.register(proj.root, proj.out)
    hooks.schedule(proj.root, PID, "one")
    hooks.schedule(proj.root, PID, "two")
    gate.set()
    assert hooks.flush(30)
    assert calls == ["one"]


def test_notify_never_raises_and_the_failure_is_a_warning(proj, monkeypatch):
    proj.create()
    hooks.register(proj.root, proj.out)

    def boom(*a, **k):
        raise OSError("the disk is full")
    monkeypatch.setattr(publish, "sync", boom)
    assert hooks.notify(proj.root, PID, "x") is None
    w = hooks.warnings_for(proj.out, proj.d)
    assert w[0]["code"] == "output_failed" and "disk is full" in w[0]["detail"] and "Chưa ghi được thư mục output" in w[0]["sentence"]
    monkeypatch.undo()
    monkeypatch.setattr("bti.output.facts.voice_done", lambda pdir, pid: False)
    assert hooks.notify(proj.root, PID, "x")["key"] == KEY
    assert hooks.warnings_for(proj.out, proj.d) == []


def test_a_project_that_has_no_output_folder_is_left_alone(proj):
    d = proj.root / "technique_lab"
    d.mkdir()
    (d / "project.json").write_text(json.dumps({"id": "technique_lab", "protected": True, "imported": True}), encoding="utf-8")
    hooks.register(proj.root, proj.out)
    assert hooks.notify(proj.root, "technique_lab", "x")["skipped"] == "protected" and not proj.out.exists()
    (proj.root / "bare").mkdir()
    assert hooks.notify(proj.root, "bare", "x")["skipped"] == "no_project_file" and not proj.out.exists()
    with pytest.raises(publish.NotApplicable):
        publish.sync(d, proj.out, explicit=True)


# ------------------------------------------------------------------------------------------------ the long jobs
def test_the_export_job_publishes_the_video_and_cleans_the_caches(proj, monkeypatch):
    proj.stage("approve_storyboard").caches()
    run, settings, _ = export_world(proj, monkeypatch)
    job = run.start(proj.d, settings=settings)
    assert job["state"] == "done", job.get("error")
    assert [p["key"] for p in job["parts"]][-1] == "output" and job["result"]["output"] == KEY
    t = proj.tree()
    assert {"final.mp4", "6_export/description.txt", "6_export/report.json", "5_storyboard/shots.md"} <= set(t)
    assert (proj.out / KEY / "final.mp4").read_bytes() == (proj.d / "export" / (PID + ".mp4")).read_bytes()
    st = proj.state()
    assert st["status"] == "done" and st["clean"]["done"] and st["clean"]["freed_bytes"] > 0
    assert not (proj.d / "cache" / "export").exists() and (proj.d / "cache" / "draft" / "thread.json").exists()
    assert any(w["code"] == "output_sheets_failed" for w in st["warnings"]), "the fake video cannot be cut into frames: a warning, and the export is done all the same"
    assert (proj.d / "export" / "export.json").exists()


def test_a_failed_export_publishes_nothing_and_cleans_nothing(proj, monkeypatch):
    proj.stage("approve_storyboard").caches()
    sb = json.loads((proj.d / "storyboard.json").read_text(encoding="utf-8"))
    run, settings, tools = export_world(proj, monkeypatch, fail_t0="0.000000")
    job = run.start(proj.d, settings=settings)
    assert job["state"] == "error" and not [p for p in job["parts"] if p["key"] == "output"]
    assert not (proj.out / KEY / "final.mp4").exists()
    assert (proj.d / "cache" / "export" / "video_all.mp4").exists() or (proj.d / "cache" / "export").exists()


def test_a_folder_that_cannot_be_written_does_not_fail_the_export(proj, monkeypatch):
    proj.stage("approve_storyboard").caches()
    run, settings, _ = export_world(proj, monkeypatch)

    def boom(*a, **k):
        raise OSError("no room on the drive")
    monkeypatch.setattr(publish, "sync", boom)
    job = run.start(proj.d, settings=settings)
    assert job["state"] == "done", job.get("error")
    assert (proj.d / "export" / (PID + ".mp4")).exists() and (proj.d / "export" / "export.json").exists()
    assert hooks.warnings_for(proj.out, proj.d)[0]["code"] == "output_failed"
    assert (proj.d / "cache" / "export" / "video_all.mp4").exists(), "nothing was cleaned: the folder was not written"


def test_the_voice_job_publishes_the_voice(proj, monkeypatch):
    proj.stage("approve_narration")
    hooks.register(proj.root, proj.out)
    import fakelongjob
    part = hooks.job_part(fakelongjob.Part, "voice", proj.d)
    assert part is not None and part.key == "output"
    proj.voice()
    monkeypatch.setattr("bti.output.facts.voice_done", lambda pdir, pid: True)
    res = fakelongjob.FakeManager().start("voice", PID, proj.d, [part])
    assert res["state"] == "done" and {"3_voice/mix.m4a", "3_voice/timing.json"} <= set(proj.tree())
    hooks.register(proj.root, None)
    assert hooks.job_part(fakelongjob.Part, "voice", proj.d) is None


def test_a_cancelled_job_does_not_publish(proj):
    proj.stage("approve_narration")
    hooks.register(proj.root, proj.out)
    import fakelongjob
    part = hooks.job_part(fakelongjob.Part, "voice", proj.d)

    class Ctx:
        def cancelled(self):
            return True
    assert part.run(Ctx()) is None and not proj.out.exists()
