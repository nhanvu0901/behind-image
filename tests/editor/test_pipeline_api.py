"""GET /api/projects/{pid}/pipeline (steps, states, reasons), GET /api/pipeline and DELETE /api/projects/{pid}.
Uses copies of projects/arnolfini-from-books (script project) and projects/demo_stub (imported: storyboard only)."""
import json
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.editor.app import create_app  # noqa: E402
from bti.editor.pipeline_api import STEPS  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402

SCRIPT_SRC = REPO / "projects" / "arnolfini-from-books"
IMPORTED_SRC = REPO / "projects" / "demo_stub"
pytestmark = pytest.mark.skipif(not (SCRIPT_SRC / "project.json").is_file() or not IMPORTED_SRC.is_dir(),
                                reason="sample projects are missing")
IDS = [s[0] for s in STEPS]


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    yield
    set_transport(None)


@pytest.fixture()
def c(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(SCRIPT_SRC, root / "arn", ignore=shutil.ignore_patterns("script", "cache", "history"))
    shutil.copytree(IMPORTED_SRC, root / "imp", ignore=shutil.ignore_patterns("cache", "history"))
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    with TestClient(app) as cl:
        cl.root = root
        yield cl


def steps(body):
    return {s["id"]: s for s in body["steps"]}


def wait_job(c, jid):
    end = time.time() + 20
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.03)
    raise AssertionError(j)


def test_steps_are_ordered_and_complete(c):
    for pid in ("arn", "imp"):
        body = c.get(f"/api/projects/{pid}/pipeline").json()
        assert [s["id"] for s in body["steps"]] == IDS
        assert [s["n"] for s in body["steps"]] == [1, 2, 3, 4, 5, 6]
        assert all(s["state"] in ("done", "current", "available", "locked", "no_data") for s in body["steps"])
        assert body["current"] in IDS and body["project"] == pid and body["protected"] is False


def test_new_project_lands_on_script(c):
    b = c.get("/api/projects/arn/pipeline").json()
    st = steps(b)
    assert b["imported"] is False and b["stage"] == "selected" and b["current"] == "script"
    assert st["artwork"]["state"] == "done"
    assert st["script"]["state"] == "current" and st["script"]["detail"] == "Chưa có dàn ý"
    # steps 3 and 4 wait for the approved narration; the export waits for an approved storyboard
    assert st["voice"]["state"] == "locked" and st["picks"]["state"] == "locked" and st["export"]["state"] == "locked"
    assert "lời dẫn" in st["voice"]["reason"] and "lời dẫn" in st["picks"]["reason"] and "duyệt storyboard" in st["export"]["reason"]
    assert st["edit"]["state"] == "locked" and "storyboard" in st["edit"]["reason"].lower()
    assert b["painting"]["title"] and b["artwork_key"]
    # every step that cannot be opened says why
    assert all(s["reason"] for s in b["steps"] if s["state"] in ("locked", "no_data"))


def test_imported_project_has_no_data_for_steps_1_to_4_and_edit_works(c):
    b = c.get("/api/projects/imp/pipeline").json()
    st = steps(b)
    assert b["imported"] is True and b["current"] == "edit" and b["stage"] in ("storyboard", "approved")
    for sid in ("artwork", "script", "voice", "picks"):
        assert st[sid]["state"] == "no_data" and "nhập từ bản dựng trước" in st[sid]["reason"]
    assert st["edit"]["state"] == "current" and st["edit"]["reason"] == ""
    assert st["export"]["state"] == "locked" and "duyệt storyboard" in st["export"]["reason"]      # not approved yet


def test_script_progress_moves_the_current_step(c):
    P = "/api/projects/arn"
    jid = c.post(P + "/outline/generate", json={"model": "mock"}).json()["job_id"]
    assert wait_job(c, jid)["state"] == "done"
    st = steps(c.get(P + "/pipeline").json())
    assert st["script"]["state"] == "current" and "chưa duyệt" in st["script"]["detail"]
    o = c.get(P + "/outline").json()
    assert c.post(P + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    b = c.get(P + "/pipeline").json()
    assert b["stage"] == "outlined" and b["current"] == "script" and "Dàn ý đã duyệt" in steps(b)["script"]["detail"]
    jid = c.post(P + "/narration/generate", json={"model": "mock"}).json()["job_id"]
    assert wait_job(c, jid)["state"] == "done"
    n = c.get(P + "/narration").json()
    assert c.post(P + "/narration/approve", json={"rev": n["rev"]}).status_code == 200
    b = c.get(P + "/pipeline").json()
    st = steps(b)
    assert b["stage"] == "script" and st["script"]["state"] == "done"
    assert b["current"] == "voice"            # the stage calls for the voice step; the picks step is open beside it
    assert st["voice"]["state"] == "current" and st["picks"]["state"] == "available" and st["edit"]["state"] == "locked"
    # editing the narration after the approval makes the approval stale: the script step is open again
    doc = n["narration"]
    doc["chapters"][0]["beats"][0]["text"] += " Once more."
    cur = c.get(P + "/narration").json()["rev"]
    assert c.put(P + "/narration", json={"narration": doc, "base_rev": cur}).status_code == 200
    b = c.get(P + "/pipeline").json()
    assert steps(b)["script"]["state"] == "current" and b["current"] == "script"


def test_storyboard_state_follows_approval(c):
    P = "/api/projects/imp"
    assert steps(c.get(P + "/pipeline").json())["edit"]["detail"] == "Storyboard chưa duyệt"
    rev = c.get(P).json()["rev"]
    assert c.post(P + "/approve", json={"rev": rev}).status_code == 200
    b = c.get(P + "/pipeline").json()
    assert steps(b)["edit"]["state"] == "done" and b["current"] == "export"
    sb = c.get(P).json()["storyboard"]
    sb["shots"][0]["note"] = "changed after approval"
    assert c.put(P + "/storyboard", json={"storyboard": sb, "base_rev": rev}).status_code == 200
    b = c.get(P + "/pipeline").json()
    assert steps(b)["edit"]["state"] == "current" and "Duyệt cũ" in steps(b)["edit"]["detail"] and b["current"] == "edit"


def test_export_step_shows_rendered_files(c):
    d = c.root / "imp"
    assert c.get("/api/projects/imp/pipeline").json()["outputs"] == []
    (d / "render").mkdir()
    (d / "render" / "final.mp4").write_bytes(b"x" * 2048)
    b = c.get("/api/projects/imp/pipeline").json()
    assert b["outputs"] == [{"path": "render/final.mp4", "size": 2048, "url": "/api/projects/imp/files/render/final.mp4"}]
    # an old video file is output: the export step opens (waiting on the storyboard), it is not the locked page
    assert steps(b)["export"]["state"] == "waiting" and steps(b)["export"]["blocked_by"] == "edit" and "1 tệp" in steps(b)["export"]["detail"]
    assert c.get(b["outputs"][0]["url"]).status_code == 200
    assert b["stage"] == "rendered"


def test_unknown_or_invalid_project(c):
    assert c.get("/api/projects/nope/pipeline").status_code == 404
    assert c.get("/api/projects/..%2f..%2fx/pipeline").status_code in (404, 422)
    assert c.get("/api/projects/Bad_ID/pipeline").status_code == 404


def test_template_without_project(c):
    b = c.get("/api/pipeline").json()
    assert b["project"] is None and [s["id"] for s in b["steps"]] == IDS and b["current"] == "artwork"
    st = steps(b)
    assert st["artwork"]["state"] == "current"
    assert all(st[i]["state"] == "locked" and st[i]["reason"] for i in IDS[1:])


# ---------------------------------------------------------------- delete
def test_delete_needs_the_typed_id(c):
    assert c.delete("/api/projects/arn").status_code == 422
    assert c.delete("/api/projects/arn", params={"confirm": "arnolfini"}).status_code == 422
    assert c.delete("/api/projects/arn", params={"confirm": ""}).status_code == 422
    assert (c.root / "arn").is_dir()
    r = c.delete("/api/projects/arn", params={"confirm": "arn"})
    assert r.status_code == 200 and r.json() == {"deleted": "arn"}
    assert not (c.root / "arn").exists() and (c.root / "imp").is_dir()
    assert c.get("/api/projects/arn/pipeline").status_code == 404
    assert c.delete("/api/projects/arn", params={"confirm": "arn"}).status_code == 404
    assert "arn" not in [p["id"] for p in c.get("/api/projects").json()]


def _protect(c, pid, flag=True):
    (c.root / pid).mkdir()
    (c.root / pid / "storyboard.json").write_text("{}")
    (c.root / pid / "project.json").write_text(json.dumps({"id": pid, "protected": flag, "imported": True}))


def test_protected_flag_in_project_json_blocks_delete(c):
    _protect(c, "refproj")
    r = c.delete("/api/projects/refproj", params={"confirm": "refproj"})
    assert r.status_code == 403 and r.json()["protected"] is True
    assert (c.root / "refproj" / "storyboard.json").is_file()
    assert c.get("/api/projects/refproj/pipeline").json()["protected"] is True


def test_unflagged_project_with_a_lab_name_is_deletable(c):
    """Owner decision: only `"protected": true` protects; lab_*, demo_* and arnolfini_edit are ordinary projects."""
    _protect(c, "lab_x", flag=False)
    assert c.delete("/api/projects/lab_x", params={"confirm": "lab_x"}).status_code == 200
    assert not (c.root / "lab_x").exists()


def test_the_two_owner_projects_carry_the_flag():
    for pid in ("arnolfini", "technique_lab"):
        assert json.loads((REPO / "projects" / pid / "project.json").read_text())["protected"] is True


@pytest.mark.parametrize("pid", ["..", "../x", "%2e%2e", "a/b", "UPPER", ".hidden", "x" * 80])
def test_delete_path_validation(c, pid, tmp_path):
    keep = tmp_path / "outside.txt"
    keep.write_text("keep")
    r = c.delete(f"/api/projects/{pid}", params={"confirm": pid})
    assert r.status_code in (404, 405, 422)
    assert keep.is_file() and (c.root / "arn").is_dir() and (c.root / "imp").is_dir()


def test_delete_refuses_a_symlinked_project(c, tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / "keep.txt").write_text("keep")
    (c.root / "link").symlink_to(target, target_is_directory=True)
    r = c.delete("/api/projects/link", params={"confirm": "link"})
    assert r.status_code == 409
    assert (target / "keep.txt").is_file() and (c.root / "link").is_symlink()
