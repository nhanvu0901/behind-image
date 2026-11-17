"""Phase 2 wiring: the stage routers answer, the steps and the stage follow each stage's state(), the first draft is adopted
by `apply`, a project with a long job cannot be deleted, and projects without voice or picks work as before."""
import copy
import json
import shutil
import threading
import time

import pytest
from fastapi.testclient import TestClient

from editor_helpers import PID, REPO, editable  # noqa: F401

from bti.editor.app import create_app
from bti.library import projects as libprojects
from bti.longjob import Part, manager

P = f"/api/projects/{PID}"
SCRIPT_SRC = REPO / "projects" / "arnolfini-from-books"


@pytest.fixture()
def mk(root):
    """An app on the copied demo project; engine_module None = the stub engine, "real" = bti.engine."""
    def make(engine="stub"):
        mod = None
        if engine == "real":
            pytest.importorskip("cv2")
            mod = pytest.importorskip("bti.engine.api")
        app = create_app(projects_root=root, engine_module=mod, media_module=None)
        return TestClient(app)
    return make


# ---------------------------------------------------------------- 1. the routes answer

STAGE_ROUTES = {
    ("GET", "/api/longjobs/{job_id}"), ("POST", "/api/longjobs/{job_id}/cancel"), ("GET", "/api/projects/{pid}/longjobs"),
    ("GET", "/api/projects/{pid}/voice"), ("POST", "/api/projects/{pid}/voice/generate"), ("PUT", "/api/projects/{pid}/voice/settings"),
    ("GET", "/api/projects/{pid}/voice/chunks/{cid}.wav"), ("GET", "/api/projects/{pid}/voice/mix"),
    ("GET", "/api/projects/{pid}/picks"), ("PUT", "/api/projects/{pid}/picks"), ("POST", "/api/projects/{pid}/picks/approve"),
    ("POST", "/api/projects/{pid}/picks/search"), ("POST", "/api/projects/{pid}/picks/import"),
    ("GET", "/api/projects/{pid}/picks/book-images"), ("POST", "/api/projects/{pid}/picks/import-book-image"),
    ("POST", "/api/projects/{pid}/picks/upload"), ("PUT", "/api/projects/{pid}/picks/assets/{key}/regions"),
    ("POST", "/api/projects/{pid}/picks/suggest"), ("GET", "/api/projects/{pid}/picks/suggestions"),
    ("GET", "/api/projects/{pid}/draft"), ("GET", "/api/projects/{pid}/draft/models"), ("POST", "/api/projects/{pid}/draft/start"),
    ("GET", "/api/projects/{pid}/export"), ("POST", "/api/projects/{pid}/export/start"),
}


def test_every_stage_route_is_registered_and_answers_something_other_than_the_page(client):
    app = client.app

    def flat(routes):
        for r in routes:       # newer FastAPI keeps an included router as one object that holds its own routes
            inner = getattr(getattr(r, "original_router", None), "routes", None)
            yield from flat(inner) if inner is not None else [r]

    have = {(m, r.path) for r in flat(app.routes) for m in getattr(r, "methods", ()) if m in ("GET", "POST", "PUT")}
    missing = STAGE_ROUTES - have
    assert not missing, sorted(missing)
    # the catch-all is the LAST route: a stage router included after it would never answer a GET
    assert getattr(app.routes[-1], "path", "") == "/{path:path}"
    for method, path in sorted(STAGE_ROUTES):
        url = (path.replace("{pid}", PID).replace("{job_id}", "0123456789abcdef").replace("{cid}", "0123456789ab")
               .replace("{key}", "A"))
        r = client.request(method, url, json={} if method != "GET" else None)
        ctype = r.headers.get("content-type", "")
        assert "text/html" not in ctype, (method, path)
        assert r.status_code != 405, (method, path)           # 405 = only the GET catch-all matched the path
        if method == "GET" and r.status_code == 404:
            assert r.json().get("detail") != "not found", (method, path)      # the catch-all's own 404


def test_longjob_routes_work_through_the_app(client, root):
    go = threading.Event()
    job = manager.start("wiring", PID, root / PID, [Part("a", "A", lambda c: go.wait(10))])
    try:
        assert client.get(f"/api/longjobs/{job['id']}").json()["state"] in ("queued", "running")
        assert [j["id"] for j in client.get(f"{P}/longjobs", params={"kind": "wiring"}).json()["items"]] == [job["id"]]
    finally:
        go.set()
        manager.wait(job)


# ---------------------------------------------------------------- 2. steps and stage

def fake_states(monkeypatch, voice="none", picks="none", export="none"):
    def f(d):
        return {k: {"state": v, "detail": f"{k} {v}"} for k, v in (("voice", voice), ("picks", picks), ("export", export))}
    monkeypatch.setattr(libprojects, "stage_states", f)


@pytest.fixture()
def book_client(tmp_path):
    if not (SCRIPT_SRC / "project.json").is_file():
        pytest.skip("sample project missing")
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(SCRIPT_SRC, root / "book", ignore=shutil.ignore_patterns("cache", "history"))
    with TestClient(create_app(projects_root=root, engine_module=None, media_module=None)) as c:
        c.root = root
        yield c


def approve_narration(monkeypatch):
    """The narration counts as approved (the script step has its own tests; here only the steps after it are under test)."""
    import bti.editor.pipeline_api as pa
    monkeypatch.setattr(pa, "_script_state", lambda d: ("done", "Lời dẫn đã duyệt"))


def steps(b):
    return {s["id"]: s for s in b["steps"]}


def test_step_matrix_for_a_book_project(book_client, monkeypatch):
    c = book_client
    approve_narration(monkeypatch)

    def get():
        return c.get("/api/projects/book/pipeline").json()

    fake_states(monkeypatch)
    b = get()
    st = steps(b)
    assert st["voice"]["state"] == "current" and st["picks"]["state"] == "available" and st["edit"]["state"] == "locked"
    assert b["current"] == "voice" and st["voice"]["work"] == "none"
    fake_states(monkeypatch, voice="done")
    b = get()
    assert steps(b)["voice"]["state"] == "done" and b["current"] == "picks" and b["stage"] == "voiced"
    assert "Chọn hình" in steps(b)["edit"]["reason"] and "Giọng đọc" not in steps(b)["edit"]["reason"].replace("Còn thiếu bước Chọn hình", "")
    fake_states(monkeypatch, picks="done")
    b = get()
    assert b["current"] == "voice" and "Giọng đọc" in steps(b)["edit"]["reason"] and b["stage"] in ("selected", "script")      # picks alone: voice is not done, so no `picked`
    fake_states(monkeypatch, voice="done", picks="done")
    b = get()
    assert steps(b)["edit"]["state"] == "current" and b["current"] == "edit" and b["stage"] == "picked"
    fake_states(monkeypatch, voice="running", picks="stale")
    b = get()
    assert steps(b)["voice"]["state"] == "current" and steps(b)["voice"]["work"] == "running" and steps(b)["picks"]["work"] == "stale"
    # the home list and the pipeline agree on the stage
    fake_states(monkeypatch, voice="done", picks="done")
    row = next(r for r in c.get("/api/projects").json() if r["id"] == "book")
    assert row["stage"] == get()["stage"] == "picked"


def test_narration_not_approved_locks_steps_3_and_4(book_client, monkeypatch):
    fake_states(monkeypatch, voice="done", picks="done")
    st = steps(book_client.get("/api/projects/book/pipeline").json())
    # a step that has output is never hidden behind the locked page: it waits on the script step and still opens
    assert st["voice"]["state"] == "waiting" and st["voice"]["blocked_by"] == "script" and st["voice"]["has_output"] is True
    fake_states(monkeypatch)
    st = steps(book_client.get("/api/projects/book/pipeline").json())
    assert st["voice"]["state"] == "locked" and st["picks"]["state"] == "locked" and "lời dẫn" in st["voice"]["reason"]


def test_storyboard_export_and_rendered_stage(book_client, monkeypatch):
    c = book_client
    approve_narration(monkeypatch)
    d = c.root / "book"
    sb = json.loads((REPO / "projects" / PID / "storyboard.json").read_text())
    (d / "storyboard.json").write_text(json.dumps(sb))
    fake_states(monkeypatch, voice="done", picks="done")
    b = c.get("/api/projects/book/pipeline").json()
    assert steps(b)["edit"]["state"] in ("current", "done") and steps(b)["export"]["state"] == "locked" and b["stage"] == "storyboard"
    from bti.editor.common import compute_rev
    sb["approvals"] = {"storyboard": {"rev": compute_rev(sb), "at": "2026-01-01T00:00:00"}}
    (d / "storyboard.json").write_text(json.dumps(sb))
    b = c.get("/api/projects/book/pipeline").json()
    if steps(b)["edit"]["state"] == "done":
        assert steps(b)["export"]["state"] in ("available", "current") and b["stage"] == "approved" and b["current"] == "export"
        fake_states(monkeypatch, voice="done", picks="done", export="done")
        b = c.get("/api/projects/book/pipeline").json()
        assert steps(b)["export"]["state"] == "done" and b["stage"] == "rendered"


def test_projects_without_voice_or_picks_work_as_before(client):
    """The imported `demo_stub`: steps 1 to 4 have no data, the editor works, export opens after approval, the stage is from the files."""
    b = client.get(f"{P}/pipeline").json()
    st = steps(b)
    assert b["imported"] is True and b["current"] == "edit"
    assert all(st[i]["state"] == "no_data" for i in ("artwork", "script", "voice", "picks"))
    assert st["edit"]["state"] == "current" and st["export"]["state"] == "locked"
    assert b["stage"] in ("storyboard", "approved")
    rev = client.get(P).json()["rev"]
    assert client.post(f"{P}/approve", json={"rev": rev}).status_code == 200
    b = client.get(f"{P}/pipeline").json()
    assert steps(b)["export"]["state"] in ("available", "current") and b["stage"] == "approved"      # the stage calls for the export


# ---------------------------------------------------------------- 5. the first draft is adopted

def put_first_draft(root, mutate=None):
    d = root / PID
    for old in (d / "proposals").glob("*.json"):
        old.unlink()
    sb = json.loads((d / "storyboard.json").read_text())
    sb.pop("approvals", None)
    for s in sb["shots"]:
        s["source"], s["locked"] = "import", True            # must be overwritten by the adoption
    if mutate:
        mutate(sb)
    (d / "proposals").mkdir(exist_ok=True)
    (d / "proposals" / "draft_1.json").write_text(json.dumps({"id": "draft_1", "created_at": "2026-01-01T00:00:00", "author": "agent:auto",
                                                              "summary": "first draft", "base_rev": None, "storyboard": sb,
                                                              "issues_left": [{"x": 1}]}))
    (d / "storyboard.json").unlink()
    return sb


@pytest.mark.parametrize("engine", ["stub", "real"])
def test_apply_adopts_the_first_draft(mk, root, engine):
    sb = put_first_draft(root)
    c = mk(engine)
    lst = c.get(f"{P}/proposals").json()["items"]
    assert [p["id"] for p in lst] == ["draft_1"] and lst[0]["n_changes"] > 0 and lst[0]["n_issues_left"] == 1
    g = c.get(f"{P}/proposals/draft_1").json()
    assert g["proposal"]["stale"] is False and g["proposal"]["first"] is True and g["changes"]
    r = c.post(f"{P}/proposals/draft_1/apply", json={"accept": "all"})
    assert r.status_code == 200, r.text
    saved = json.loads((root / PID / "storyboard.json").read_text())
    assert [s["id"] for s in saved["shots"]] == [s["id"] for s in sb["shots"]]
    assert all(s["source"] == "agent" and s["locked"] is False for s in saved["shots"])
    assert all(o["source"] == "agent" for s in saved["shots"] for o in s.get("overlays", []))
    assert saved["approvals"] == {"storyboard": None} and saved["canvas"] == sb["canvas"]
    assert r.json()["rev"] and not [i for i in r.json()["issues"] if i["level"] == "error"]
    assert c.get(P).status_code == 200                              # the editor opens it
    assert c.get(f"{P}/pipeline").json()["steps"][4]["state"] == "current"


def test_partial_accept_without_a_storyboard_is_refused(mk, root):
    put_first_draft(root)
    c = mk()
    r = c.post(f"{P}/proposals/draft_1/apply", json={"accept": ["shot.s0001"]})
    assert r.status_code == 422 and r.json()["code"] == "accept_all_required"
    assert c.post(f"{P}/proposals/draft_1/apply", json={}).json()["code"] == "accept_all_required"
    assert not (root / PID / "storyboard.json").exists()


def test_an_invalid_first_draft_is_not_adopted(mk, root):
    def bad(sb):
        sb["shots"][0]["technique"] = "NOPE-99"
    put_first_draft(root, bad)
    c = mk("real")
    r = c.post(f"{P}/proposals/draft_1/apply", json={"accept": "all"})
    assert r.status_code == 422 and r.json()["issues"]
    assert not (root / PID / "storyboard.json").exists()          # nothing stays on disk
    assert c.get(P).status_code == 404


def test_apply_on_a_project_with_a_storyboard_is_unchanged(client):
    r = client.post(f"{P}/proposals/p_demo_001/apply", json={"accept": ["shot.s0002"]})
    assert r.status_code == 200 and r.json()["applied"] == ["shot.s0002"]


# ---------------------------------------------------------------- 6. delete is refused while a long job runs

def test_delete_is_refused_while_a_long_job_runs(client, root):
    go = threading.Event()
    job = manager.start("wiring", PID, root / PID, [Part("a", "A", lambda c: go.wait(10))])
    try:
        # demo_stub is protected? use a copy under another id
        shutil.copytree(root / PID, root / "copy1", ignore=shutil.ignore_patterns("cache"))
        job2 = manager.start("wiring", "copy1", root / "copy1", [Part("a", "A", lambda c: go.wait(10))])
        r = client.delete("/api/projects/copy1", params={"confirm": "copy1"})
        assert r.status_code == 409 and r.json()["code"] == "longjob_running" and r.json()["job_id"] == job2["id"]
        assert (root / "copy1").is_dir()
        go.set()
        manager.wait(job2)
        manager.wait(job)
        assert client.delete("/api/projects/copy1", params={"confirm": "copy1"}).status_code == 200
    finally:
        go.set()
