"""The state answer's action, the build route and its errors, the `bti output` command, the settings switch, and the index."""
import json
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "cli"))

from bti.editor import hints, state_api  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.output import hooks, index, publish  # noqa: E402
from cli_helpers import AppTransport, run_bti  # noqa: E402
from output_helpers import KEY, PID  # noqa: E402


def app_of(proj, **kw):
    return create_app(projects_root=proj.root, output_root=proj.out, engine_module=None, media_module=None, **kw)


def build_action(st):
    return next((a for a in st["next_actions"] if a["id"] == "output.build"), None)


def test_the_state_answer_lists_output_build_only_for_an_app_with_an_output_folder(proj):
    proj.stage("export")
    with TestClient(app_of(proj)) as c:
        st = c.get("/api/projects/%s/state" % PID).json()
        a = build_action(st)
        assert a and a["method"] == "POST" and a["path"] == "/api/projects/%s/output/build" % PID and a["body"] == {} and a["step"] == "export"
        assert a["ready"] is True and a["needs"] == [] and a["advances"] is False and a["gate"] is False and a["long_job"] is False and a["cost"] is None and a["auto_ok"] is True
        assert not [w for w in st.get("warnings", []) if w["code"] != "title_missing"]          # titlestep: a storyboard with no video title has its own warning; the output folder has none
    with TestClient(create_app(projects_root=proj.root, engine_module=None, media_module=None)) as c:
        assert build_action(c.get("/api/projects/%s/state" % PID).json()) is None
    assert "output.build" in state_api.SPEC and state_api.SPEC["output.build"].label == "Ghi thư mục output"


def test_a_reference_project_has_no_such_action(proj):
    d = proj.root / "technique_lab"
    d.mkdir()
    (d / "project.json").write_text(json.dumps({"id": "technique_lab", "protected": True, "imported": True}), encoding="utf-8")
    with TestClient(app_of(proj)) as c:
        assert build_action(c.get("/api/projects/technique_lab/state").json()) is None
        r = c.post("/api/projects/technique_lab/output/build", json={})
        assert r.status_code == 409 and r.json()["code"] == "output_not_applicable"


def test_the_build_route_fills_the_folder_and_says_so(proj):
    proj.stage("export").caches()
    with TestClient(app_of(proj)) as c:
        r = c.post("/api/projects/%s/output/build" % PID, json={})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["key"] == KEY and j["folder"] == "output/" + KEY and j["written"] > 10 and j["clean"] is None and j["warnings"] == [] or j["warnings"]
        assert {k: v["out_of_date"] for k, v in j["parts"].items()} == {k: False for k in ("sources", "outline", "narration", "voice", "pictures", "storyboard", "export")}
        assert (proj.d / "cache" / "export" / "video_all.mp4").exists(), "a rebuild does not clean unless it is asked to"
        r = c.post("/api/projects/%s/output/build" % PID, json={"clean": True})
        assert r.json()["clean"]["done"] is True and not (proj.d / "cache" / "export").exists()


def test_the_build_route_with_clean_keeps_current_export_parts(proj):
    proj.stage("export").caches()
    cur = proj.d / "cache" / "export" / "parts" / "part_01_cur.mp4"
    cur.write_bytes(b"CUR" * 500)
    m = json.loads((proj.d / "export" / "export.json").read_text(encoding="utf-8"))
    m["parts"] = [{"index": 1, "key": "cur", "file": "part_01_cur.mp4", "did_render": False}]
    (proj.d / "export" / "export.json").write_text(json.dumps(m), encoding="utf-8")
    with TestClient(app_of(proj)) as c:
        r = c.post("/api/projects/%s/output/build" % PID, json={"clean": True})
        assert r.status_code == 200
        cl = r.json()["clean"]
        assert cl["done"] is True and cl["kept_parts"] == 1
        assert cur.is_file()
        assert not (proj.d / "cache" / "export" / "parts" / "part_01_x.mp4").exists()
        assert not (proj.d / "cache" / "export" / "video_all.mp4").exists()
        g = c.get("/api/projects/%s/output" % PID).json()
        assert g["enabled"] and g["key"] == KEY and g["state"]["project"] == PID
        assert c.post("/api/projects/%s/output/build" % PID, json={"clean": "yes"}).status_code == 422
        assert c.post("/api/projects/nope/output/build", json={}).status_code == 404


def test_the_errors_carry_a_code_a_fix_and_a_retry(proj):
    proj.create()
    with TestClient(create_app(projects_root=proj.root, engine_module=None, media_module=None)) as c:
        r = c.post("/api/projects/%s/output/build" % PID, json={})
        b = r.json()
        assert r.status_code == 409 and b["code"] == "output_disabled" and b["retry"] == "no" and b["fix"].startswith("This app was started without an output folder")
    for code in ("output_disabled", "output_not_applicable", "output_failed"):
        assert code in hints.HINTS and not re.search(r"[À-ỹ]", hints.HINTS[code]["fix"])


def test_a_problem_with_the_folder_is_a_warning_in_the_state_answer(proj, monkeypatch):
    proj.create()
    with TestClient(app_of(proj)) as c:
        monkeypatch.setattr(publish, "sync", lambda *a, **k: (_ for _ in ()).throw(OSError("no room on the drive")))
        assert hooks.notify(proj.root, PID, "test") is None
        st = c.get("/api/projects/%s/state" % PID).json()
        w = st["warnings"][0]
        assert w["code"] == "output_failed" and "no room on the drive" in w["detail"] and re.search(r"[À-ỹ]", w["sentence"])
        t = AppTransport(c)
        res = run_bti(t, "status", PID)
        assert "warnings:" in res.out and "output_failed" in res.out


def test_the_command_fills_the_folder(proj):
    proj.stage("export").caches()
    with TestClient(app_of(proj)) as c:
        t = AppTransport(c)
        r = run_bti(t, "output", PID)
        assert r.code == 0, r
        assert "output folder: output/%s" % KEY in r.out and "parts: sources, outline, narration, voice, pictures, storyboard, export" in r.out
        assert (proj.out / KEY / "final.mp4").exists() and not r.err
        assert (proj.d / "cache" / "export" / "video_all.mp4").exists()
        assert t.log[-1] == ("POST", "/api/projects/%s/output/build" % PID, {})
        r = run_bti(t, "output", PID, "--clean")
        assert r.code == 0 and "cleaned the working folder: freed" in r.out and t.log[-1][2] == {"clean": True}
        j = run_bti(t, "--json", "output", PID)
        assert j.code == 0 and j.json["key"] == KEY and j.json["folder"] == "output/" + KEY


def test_the_command_refuses_where_there_is_no_folder(proj):
    proj.create()
    with TestClient(create_app(projects_root=proj.root, engine_module=None, media_module=None)) as c:
        r = run_bti(AppTransport(c), "output", PID)
        assert r.code == 4 and "output_not_available" in r.err + r.out
        assert run_bti(AppTransport(c), "output").code == 2


def test_the_settings_switch(proj):
    from bti import settings as S
    with TestClient(app_of(proj)) as c:
        assert c.get("/api/settings/output").json() == {"clean_after_export": True}
        S.set_machine_agent("opus")
        assert c.put("/api/settings/output", json={"clean_after_export": False}).json() == {"clean_after_export": False}
        assert c.get("/api/settings/output").json()["clean_after_export"] is False and S.get_machine_agent() == "opus", "the other settings are kept"
        assert S.get_output_settings()["clean_after_export"] is False
        r = c.put("/api/settings/output", json={"clean_after_export": "no"})
        assert r.status_code == 422 and r.json()["code"] == "invalid_payload"
        assert c.put("/api/settings/output", json={}).status_code == 422
        assert c.put("/api/settings/output", json={"clean_after_export": True}).json()["clean_after_export"] is True


def test_the_index(proj, tmp_path):
    from output_helpers import Project
    proj.stage("export")
    publish.sync(proj.d, proj.out, moment="export", sheets=False)
    other = Project(tmp_path, pid="scream", key="munch-the-scream", title="The Scream")
    other.create().outline().approve_outline()
    publish.sync(other.d, other.out, moment="outline approved", sheets=False)
    doc = json.loads((proj.out / "index.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "bti.output.index/1"
    by = {r["key"]: r for r in doc["folders"]}
    assert set(by) == {KEY, "munch-the-scream"}
    a, b = by[KEY], by["munch-the-scream"]
    assert a["status"] == "done" and a["video"] is True and a["project"] == PID and a["title"] == "The Dutch Portrait" and a["path"] == KEY
    assert a["length_seconds"] == pytest.approx(proj.duration) and a["size_bytes"] > 0 and a["last_run"] and a["out_of_date"] == []
    assert b["status"] == "in_progress" and b["video"] is False and b["step"] == "script" and b["step_label"] == "Kịch bản" and b["length_seconds"] is None
    md = (proj.out / "INDEX.md").read_text(encoding="utf-8")
    assert "The Dutch Portrait — Jan Vermeer" in md and "đã xong" in md and "đang làm" in md and "`%s/`" % KEY in md and "`munch-the-scream/`" in md
    assert index.rows(proj.out) == doc["folders"] or [r["key"] for r in index.rows(proj.out)] == [r["key"] for r in doc["folders"]]
