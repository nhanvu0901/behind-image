import copy
import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.draft import run as draft_run
from bti.draft.inputs import load_inputs
from bti.draft.merge import apply_direct_edit, compute_changes, merge_storyboard, undo_turn
from bti.draft.thread import (
    get_turn_storyboard,
    load_thread,
    save_thread,
    save_turn_storyboards,
    turns_dir,
    update_turn,
)
from bti.editor import draft_api
from bti.editor.app import create_app
from bti.editor.common import ApiError, compute_rev
from bti.longjob import LongJobManager
from bti.script.providers import mock as mock_provider
from helpers import GOOD, clean_spec, make_synth_project


@pytest.fixture()
def sb_proj(proj):
    """Synthetic project with initial saved storyboard."""
    from bti.draft.compile import compile_specs
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    res = compile_specs(inp, specs, draw=False)
    assert not res.errors
    (proj / "storyboard.json").write_text(json.dumps(res.storyboard, indent=1), encoding="utf-8")
    return proj


@pytest.fixture()
def app_client(sb_proj):
    from bti.longjob import manager as global_mgr
    global_mgr.configure(projects_root=sb_proj.parent)
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    return client, sb_proj


# -----------------------------------------------------------------------------
# 1. Direct apply: current equals base
# -----------------------------------------------------------------------------
def test_direct_apply_current_equals_base(sb_proj):
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    result_sb = copy.deepcopy(base_sb)
    s1 = result_sb["shots"][0]
    s1["note"] = "Updated note by agent"

    res = apply_direct_edit(
        sb_proj,
        "turn_001",
        base_sb=base_sb,
        result_sb=result_sb,
        scope_shot_ids={s1["id"]},
    )
    assert res["status"] == "applied"
    assert res["after_rev"] is not None
    assert len(res["changes"]) == 1
    assert res["changes"][0]["shot_id"] == s1["id"]
    assert res["changes"][0]["op"] == "changed"

    # Saved storyboard was updated with agent source
    saved = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved["shots"][0]["note"] == "Updated note by agent"
    assert saved["shots"][0]["source"] == "agent"

    # Before and after storyboards stored
    before_read = get_turn_storyboard(sb_proj, "turn_001", "before")
    after_read = get_turn_storyboard(sb_proj, "turn_001", "after")
    assert before_read is not None
    assert after_read is not None
    assert before_read["shots"][0].get("note") != "Updated note by agent"
    assert after_read["shots"][0]["note"] == "Updated note by agent"


# -----------------------------------------------------------------------------
# 2. Direct apply: manual save of another shot during job (merged)
# -----------------------------------------------------------------------------
def test_direct_apply_manual_save_other_shot_merged(sb_proj):
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert len(base_sb["shots"]) >= 3
    s1_id = base_sb["shots"][0]["id"]
    s3_id = base_sb["shots"][2]["id"]

    # Result modifies shot 1
    result_sb = copy.deepcopy(base_sb)
    result_sb["shots"][0]["note"] = "Agent edit on shot 1"

    # Current on disk modified shot 3 in the meantime
    current_sb = copy.deepcopy(base_sb)
    current_sb["shots"][2]["note"] = "User edit on shot 3"
    (sb_proj / "storyboard.json").write_text(json.dumps(current_sb, indent=1), encoding="utf-8")

    res = apply_direct_edit(
        sb_proj,
        "turn_merged_002",
        base_sb=base_sb,
        result_sb=result_sb,
        scope_shot_ids={s1_id},
    )
    assert res["status"] == "applied"

    # Disk must contain BOTH edits
    saved = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved["shots"][0]["note"] == "Agent edit on shot 1"
    assert saved["shots"][0]["source"] == "agent"
    assert saved["shots"][2]["note"] == "User edit on shot 3"


# -----------------------------------------------------------------------------
# 3. Direct apply: manual save of shot result touches -> needs_choice (resolve)
# -----------------------------------------------------------------------------
def test_direct_apply_manual_save_conflict_and_resolve(app_client):
    client, sb_proj = app_client
    pid = sb_proj.name
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    s1_id = base_sb["shots"][0]["id"]

    # Agent result modifies shot 1
    result_sb = copy.deepcopy(base_sb)
    result_sb["shots"][0]["note"] = "Agent edit on shot 1"

    # User simultaneously modified shot 1 on disk
    current_sb = copy.deepcopy(base_sb)
    current_sb["shots"][0]["note"] = "User edit on shot 1"
    (sb_proj / "storyboard.json").write_text(json.dumps(current_sb, indent=1), encoding="utf-8")

    # Apply detects conflict -> needs_choice
    res = apply_direct_edit(
        sb_proj,
        "turn_conflict_003",
        base_sb=base_sb,
        result_sb=result_sb,
        scope_shot_ids={s1_id},
    )
    assert res["status"] == "needs_choice"
    assert len(res["conflicts"]) > 0

    # Current storyboard on disk is UNTOUCHED
    saved = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved["shots"][0]["note"] == "User edit on shot 1"

    # Record turn as needs_choice in thread
    turn = {
        "id": "turn_conflict_003",
        "at": "2026-11-18T00:00:00",
        "instruction": "sửa cảnh 1",
        "scope": {"kind": "shots", "shots": [s1_id]},
        "scope_words": "1 cảnh",
        "model": "gemini-3.8-flash",
        "base_rev": compute_rev(base_sb),
        "status": "needs_choice",
        "changes": res["changes"],
    }
    save_thread(sb_proj, [turn])

    # 3a. Resolve with discard
    r_disc = client.post(f"/api/projects/{pid}/draft/edit/turn_conflict_003/resolve", json={"action": "discard"})
    assert r_disc.status_code == 200
    assert r_disc.json()["status"] == "cancelled"
    turns = load_thread(sb_proj)
    assert turns[0]["status"] == "cancelled"
    assert json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))["shots"][0]["note"] == "User edit on shot 1"

    # Reset turn to needs_choice to test overwrite
    update_turn(sb_proj, "turn_conflict_003", status="needs_choice")

    # 3b. Resolve with overwrite
    r_over = client.post(f"/api/projects/{pid}/draft/edit/turn_conflict_003/resolve", json={"action": "overwrite"})
    assert r_over.status_code == 200
    assert r_over.json()["status"] == "applied"
    turns = load_thread(sb_proj)
    assert turns[0]["status"] == "applied"
    # Storyboard overwritten with agent result
    saved_after = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved_after["shots"][0]["note"] == "Agent edit on shot 1"


# -----------------------------------------------------------------------------
# 4. Undo clean
# -----------------------------------------------------------------------------
def test_undo_clean(app_client):
    client, sb_proj = app_client
    pid = sb_proj.name
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    s1_id = base_sb["shots"][0]["id"]

    result_sb = copy.deepcopy(base_sb)
    result_sb["shots"][0]["note"] = "Agent note for undo test"

    res = apply_direct_edit(
        sb_proj,
        "turn_undo_004",
        base_sb=base_sb,
        result_sb=result_sb,
        scope_shot_ids={s1_id},
    )
    assert res["status"] == "applied"

    turn = {
        "id": "turn_undo_004",
        "at": "2026-11-18T00:00:00",
        "instruction": "sửa để undo",
        "scope": {"kind": "shots", "shots": [s1_id]},
        "scope_words": "1 cảnh",
        "model": "gemini-3.8-flash",
        "base_rev": compute_rev(base_sb),
        "after_rev": res["after_rev"],
        "status": "applied",
        "changes": res["changes"],
    }
    save_thread(sb_proj, [turn])

    # Call undo
    r_undo = client.post(f"/api/projects/{pid}/draft/edit/turn_undo_004/undo", json={})
    assert r_undo.status_code == 200
    assert r_undo.json()["status"] == "undone"

    # Restored to original base_sb
    saved = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved["shots"][0].get("note") != "Agent note for undo test"
    assert saved["shots"][0].get("note") == base_sb["shots"][0].get("note")

    turns = load_thread(sb_proj)
    assert turns[0]["status"] == "undone"


# -----------------------------------------------------------------------------
# 5. Undo conflict and force
# -----------------------------------------------------------------------------
def test_undo_conflict_and_force(app_client):
    client, sb_proj = app_client
    pid = sb_proj.name
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    s1_id = base_sb["shots"][0]["id"]

    result_sb = copy.deepcopy(base_sb)
    result_sb["shots"][0]["note"] = "Agent note v1"

    res = apply_direct_edit(
        sb_proj,
        "turn_undo_005",
        base_sb=base_sb,
        result_sb=result_sb,
        scope_shot_ids={s1_id},
    )
    assert res["status"] == "applied"

    turn = {
        "id": "turn_undo_005",
        "at": "2026-11-18T00:00:00",
        "instruction": "sửa v1",
        "scope": {"kind": "shots", "shots": [s1_id]},
        "scope_words": "1 cảnh",
        "model": "gemini-3.8-flash",
        "base_rev": compute_rev(base_sb),
        "after_rev": res["after_rev"],
        "status": "applied",
        "changes": res["changes"],
    }
    save_thread(sb_proj, [turn])

    # User modifies shot 1 again after the turn
    current_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    current_sb["shots"][0]["note"] = "User edited shot 1 after turn"
    (sb_proj / "storyboard.json").write_text(json.dumps(current_sb, indent=1), encoding="utf-8")

    # Undo without force fails with 409 undo_conflict
    r_undo = client.post(f"/api/projects/{pid}/draft/edit/turn_undo_005/undo", json={})
    assert r_undo.status_code == 409
    assert r_undo.json()["code"] == "undo_conflict"
    assert s1_id in r_undo.json()["conflicts"]

    # Undo WITH force succeeds
    r_force = client.post(f"/api/projects/{pid}/draft/edit/turn_undo_005/undo", json={"force": True})
    assert r_force.status_code == 200
    assert r_force.json()["status"] == "undone"

    # Restored to original
    saved = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved["shots"][0].get("note") == base_sb["shots"][0].get("note")


# -----------------------------------------------------------------------------
# 6. Turn storyboards pruning (20 limit) and has_undo
# -----------------------------------------------------------------------------
def test_turn_storyboards_pruning_and_has_undo(app_client):
    client, sb_proj = app_client
    pid = sb_proj.name
    sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))

    turns = []
    # Create 25 turns
    for i in range(25):
        tid = f"t_20261118_000000_{i:03d}"
        save_turn_storyboards(sb_proj, tid, sb, sb)
        turns.append({
            "id": tid,
            "at": "2026-11-18T00:00:00",
            "instruction": f"turn {i}",
            "scope": {"kind": "all"},
            "scope_words": "cả video",
            "model": "gemini-3.8-flash",
            "status": "applied",
            "changes": [],
        })
    save_thread(sb_proj, turns)

    # Check directory count: exactly 20
    t_dirs = sorted([d.name for d in turns_dir(sb_proj).iterdir() if d.is_dir()])
    assert len(t_dirs) == 20
    # Oldest 5 (000 to 004) were pruned
    assert "t_20261118_000000_000" not in t_dirs
    assert "t_20261118_000000_024" in t_dirs

    loaded = load_thread(sb_proj)
    # Turn 0 lost undo
    t0 = next(t for t in loaded if t["id"] == "t_20261118_000000_000")
    assert t0["has_undo"] is False

    # Turn 24 has undo
    t24 = next(t for t in loaded if t["id"] == "t_20261118_000000_024")
    assert t24["has_undo"] is True

    # Attempting undo on pruned turn returns 410 undo_unavailable
    r = client.post(f"/api/projects/{pid}/draft/edit/t_20261118_000000_000/undo", json={})
    assert r.status_code == 410
    assert r.json()["code"] == "undo_unavailable"


# -----------------------------------------------------------------------------
# 7. Frame route for before and after
# -----------------------------------------------------------------------------
def test_frame_route_before_after(app_client):
    client, sb_proj = app_client
    pid = sb_proj.name
    base_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    s1_id = base_sb["shots"][0]["id"]

    result_sb = copy.deepcopy(base_sb)
    result_sb["shots"][0]["note"] = "Different frame state"

    tid = "turn_frames_007"
    save_turn_storyboards(sb_proj, tid, base_sb, result_sb)

    # Before frame
    r_before = client.get(f"/api/projects/{pid}/draft/edit/{tid}/frames/{s1_id}/before.jpg")
    assert r_before.status_code == 200
    assert r_before.headers["content-type"] == "image/jpeg"
    assert r_before.content.startswith(b"\xff\xd8")  # JPEG SOI header

    # After frame
    r_after = client.get(f"/api/projects/{pid}/draft/edit/{tid}/frames/{s1_id}/after.jpg")
    assert r_after.status_code == 200
    assert r_after.headers["content-type"] == "image/jpeg"
    assert r_after.content.startswith(b"\xff\xd8")

    # Invalid when
    r_bad = client.get(f"/api/projects/{pid}/draft/edit/{tid}/frames/{s1_id}/middle.jpg")
    assert r_bad.status_code == 404

    # Non-existent shot
    r_no_shot = client.get(f"/api/projects/{pid}/draft/edit/{tid}/frames/non_existent_shot/before.jpg")
    assert r_no_shot.status_code == 404
