import json
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.draft import run as R
from bti.draft.inputs import DraftError, load_inputs
from bti.draft.thread import load_thread
from bti.editor import draft_api
from bti.editor.common import ApiError
from bti.longjob import LongJobManager, Busy
from helpers import GOOD, clean_spec, make_synth_project


@pytest.fixture()
def sb_proj(proj):
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    from bti.draft.compile import compile_specs
    res = compile_specs(inp, specs, draw=False)
    assert not res.errors
    (proj / "storyboard.json").write_text(json.dumps(res.storyboard, indent=1), encoding="utf-8")
    return proj


def test_e9_order_of_checks_validates_before_find_agy(sb_proj, monkeypatch):
    """E9: Request validation (instruction, scope, model, storyboard) occurs BEFORE looking for agy."""
    # Simulate machine without agy
    import bti.draft.providers.agy as agy_mod
    monkeypatch.setattr(agy_mod, "find_agy", lambda: None)

    app = FastAPI()
    app.state.projects_root = sb_proj.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    app.include_router(draft_api.router)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    # 1. Empty instruction rejected with edit_empty_instruction (422), not agy_missing
    r1 = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "", "scope": {"all": True}})
    assert r1.status_code == 422
    assert r1.json()["code"] == "edit_empty_instruction"

    # 2. Bad scope rejected with edit_bad_scope (422), not agy_missing
    r2 = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "sửa", "scope": {}})
    assert r2.status_code == 422
    assert r2.json()["code"] == "edit_bad_scope"

    # 3. Bad model rejected with bad_model (422), not agy_missing
    r3 = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "sửa", "scope": {"all": True}, "model": 12345})
    assert r3.status_code == 422
    assert r3.json()["code"] == "bad_model"

    # 4. Scope needs storyboard on project without storyboard rejected with 409 scope_needs_storyboard, not agy_missing
    no_sb_proj = make_synth_project(sb_proj.parent / "nosb_e9")
    r4 = client.post(f"/api/projects/nosb_e9/draft/edit", json={"instruction": "sửa", "scope": {"all": True}})
    assert r4.status_code == 409
    assert r4.json()["code"] == "scope_needs_storyboard"


def test_e12_separate_last_run_for_draft_and_edit(sb_proj, tmp_path):
    """E12: Edit jobs write last_run_edit.json, never overwriting draft's last_run.json."""
    cache = sb_proj / "cache" / "draft"
    cache.mkdir(parents=True, exist_ok=True)

    # Simulate existing draft last_run
    draft_last = {"id": "run_draft_001", "provider": "auto", "model": "gemini", "at": "2026-11-17T10:00:00", "n_shots": 93}
    (cache / "last_run.json").write_text(json.dumps(draft_last), encoding="utf-8")

    # Run _write_last_edit simulating edit job completion
    R._write_last_edit(sb_proj, turn_id="t_edit_001", status="done", changes=2)

    # 1. Draft last_run remains untouched
    assert R.last_run(sb_proj) == draft_last
    cur_draft_last = json.loads((cache / "last_run.json").read_text(encoding="utf-8"))
    assert cur_draft_last["id"] == "run_draft_001"
    assert cur_draft_last["n_shots"] == 93

    # 2. Edit last_run is written to last_run_edit.json
    edit_last = R.last_run_edit(sb_proj)
    assert edit_last is not None
    assert edit_last["turn_id"] == "t_edit_001"
    assert edit_last["status"] == "done"
    assert edit_last["changes"] == 2


def test_e13_turn_recorded_before_job_start(sb_proj):
    """E13: Turn is recorded in thread before longjob start."""
    mgr = LongJobManager(projects_root=sb_proj.parent)

    # If start succeeds, turn is already in thread
    rec = R.start(sb_proj.name, sb_proj, instruction="kiểm tra thứ tự ghi",
                  edit_scope={"shots": ["s0001"]}, mode="deep", manager=mgr)
    turns = load_thread(sb_proj)
    assert len(turns) == 1
    assert turns[0]["id"] == rec["turn_id"]
    assert turns[0]["instruction"] == "kiểm tra thứ tự ghi"
    assert turns[0]["status"] == "running"
    assert turns[0]["job_id"] == rec["id"]
