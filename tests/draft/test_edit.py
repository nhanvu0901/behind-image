import copy
import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.draft import decompile as D
from bti.draft import run as R
from bti.draft import workspace as W
from bti.draft.compile import compile_specs
from bti.draft.guard import Guard
from bti.draft.inputs import DraftError, load_inputs
from bti.editor import draft_api
from bti.editor.common import ApiError
from bti.longjob import LongJobManager
from helpers import GOOD, clean_spec, make_synth_project
from test_agy import fake  # noqa: F401


@pytest.fixture()
def sb_proj(proj):
    """Synthetic project with an initial saved storyboard."""
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    res = compile_specs(inp, specs, draw=False)
    assert not res.errors
    # Lock the second shot (s0002)
    res.storyboard["shots"][1]["locked"] = True
    (proj / "storyboard.json").write_text(json.dumps(res.storyboard, indent=1), encoding="utf-8")
    return proj


@pytest.fixture()
def mgr(proj):
    return LongJobManager(projects_root=proj.parent)


def finish(mgr, rec, timeout=120):
    j = mgr.wait(rec, timeout=timeout)
    assert j is not None and j["state"] not in ("queued", "running", "waiting"), j
    return j


def gf(d):
    return Guard(d, extra=lambda: None, repo_root=d.parent)


def test_scope_resolution(sb_proj):
    inp = load_inputs(sb_proj)
    cur_shots = [s["id"] for s in inp.current["shots"]]
    assert len(cur_shots) >= 6
    s1, s2 = cur_shots[0], cur_shots[1]
    assert inp.current["shots"][1]["locked"] is True

    # 1. shots scope: s2 is locked so it must be excluded
    edit_shots, chapters, words = R.resolve_edit_scope(inp, {"shots": [s1, s2]})
    assert edit_shots == {s1}
    assert s2 not in edit_shots
    assert words == "1 shot đang chọn"
    assert chapters == ["c01"]

    # 2. chapter scope: c01
    edit_shots_c1, chapters_c1, words_c1 = R.resolve_edit_scope(inp, {"chapter": "c01"})
    assert s1 in edit_shots_c1
    assert s2 not in edit_shots_c1  # locked excluded
    assert words_c1 == "chương c01"
    assert chapters_c1 == ["c01"]

    # 3. all scope
    edit_shots_all, chapters_all, words_all = R.resolve_edit_scope(inp, {"all": True})
    assert s1 in edit_shots_all
    assert s2 not in edit_shots_all  # locked excluded
    assert len(edit_shots_all) == len(cur_shots) - 1
    assert words_all == "cả video"
    assert chapters_all == ["c01", "c02"]

    # 4. bad scope: only locked shot in shots list
    with pytest.raises(DraftError) as e:
        R.resolve_edit_scope(inp, {"shots": [s2]})
    assert e.value.code == "edit_bad_scope"

    # 5. bad scope: empty or invalid
    with pytest.raises(DraftError) as e:
        R.resolve_edit_scope(inp, {})
    assert e.value.code == "edit_bad_scope"

    with pytest.raises(DraftError) as e:
        R.resolve_edit_scope(inp, {"chapter": "c99"})
    assert e.value.code == "unknown_chapter"


def test_edit_refused_without_storyboard(proj, mgr):
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, instruction="sửa video", edit_scope={"all": True}, manager=mgr)
    assert e.value.code == "scope_needs_storyboard"


def test_auto_provider_refused_for_edit(sb_proj, mgr):
    with pytest.raises(DraftError) as e:
        R.start(sb_proj.name, sb_proj, provider="auto", instruction="sửa video", edit_scope={"all": True}, manager=mgr)
    assert e.value.code == "edit_needs_agy"


def test_thread_storage_lifecycle(sb_proj):
    turns = R.load_thread(sb_proj)
    assert turns == []

    # Append turns
    for i in range(55):
        R.append_turn(sb_proj, {
            "id": f"t_{i}",
            "at": "2026-11-17T12:00:00",
            "instruction": f"instruction {i}",
            "scope": {"kind": "all", "shots": None, "chapter": None},
            "scope_words": "cả video",
            "model": "gemini",
            "status": "running",
            "proposal_id": None,
            "notes": "",
            "conversation_id": None,
            "error": None,
            "accepted": None,
        })

    # Capped at 50
    turns = R.load_thread(sb_proj)
    assert len(turns) == 50
    assert turns[0]["id"] == "t_5"
    assert turns[-1]["id"] == "t_54"

    # Update turn
    R.update_turn(sb_proj, "t_54", status="done", notes="Updated notes")
    turns = R.load_thread(sb_proj)
    assert turns[-1]["status"] == "done"
    assert turns[-1]["notes"] == "Updated notes"

    # Clear thread
    R.clear_thread(sb_proj)
    assert R.load_thread(sb_proj) == []


def test_edit_job_in_scope_change(sb_proj, mgr, fake):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    # Change note of first shot (s0001) in c01
    c1["shots"][0]["note"] = "slower push-in for mirror"
    c2 = decomp["c02"]["spec"]

    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": c2},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="zoom chậm hơn",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    assert "turn_id" in rec
    turn_id = rec["turn_id"]

    # Thread has running turn
    t0 = R.load_thread(sb_proj)[0]
    assert t0["id"] == turn_id and t0["status"] == "running"

    j = finish(mgr, rec)
    assert j["state"] == "done", (j.get("error"), j.get("log_tail"))

    # Proposal was written
    pid = j["result"]["proposal_id"]
    assert pid and pid.startswith("edit_")
    prop_file = sb_proj / "proposals" / (pid + ".json")
    assert prop_file.is_file()
    prop_doc = json.loads(prop_file.read_text(encoding="utf-8"))
    assert prop_doc["author"].startswith("agent:agy:")
    assert prop_doc["summary"] == "Fake agent summary"

    # Thread updated to done
    t_end = R.load_thread(sb_proj)[-1]
    assert t_end["id"] == turn_id
    assert t_end["status"] == "done"
    assert t_end["proposal_id"] == pid
    assert t_end["conversation_id"] == "conv-1"


def test_edit_job_scope_violation_refuses_proposal(sb_proj, mgr, fake):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    # Scope is only s0001, but fake changes s0003 (outside scope)
    c1["shots"][2]["technique"] = "STATIC-09"
    c2 = decomp["c02"]["spec"]

    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": c2},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="chỉ sửa shot 1",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    turn_id = rec["turn_id"]
    j = finish(mgr, rec)

    assert j["state"] == "error"
    assert j["error_code"] == "edit_outside_scope"

    # No proposal written
    props = list((sb_proj / "proposals").glob("edit_*.json"))
    assert props == []

    # Thread status is refused
    t_end = R.load_thread(sb_proj)[-1]
    assert t_end["id"] == turn_id
    assert t_end["status"] == "refused"
    assert t_end["error"] == "edit_outside_scope"


def test_edit_job_no_change_writes_no_proposal(sb_proj, mgr, fake):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    # Output identical decompiled specs without changes
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="trả lời câu hỏi",
                  edit_scope={"all": True}, manager=mgr, guard_factory=gf, python="python")
    turn_id = rec["turn_id"]
    j = finish(mgr, rec)

    assert j["state"] == "done"
    assert j["result"]["proposal_id"] is None
    assert j["result"]["no_change"] is True

    # No proposal written
    props = list((sb_proj / "proposals").glob("edit_*.json"))
    assert props == []

    # Thread status is no_change
    t_end = R.load_thread(sb_proj)[-1]
    assert t_end["id"] == turn_id
    assert t_end["status"] == "no_change"
    assert t_end["proposal_id"] is None
    assert t_end["notes"] == "Fake agent summary\n"


def test_followup_history_includes_prior_outcome(sb_proj, mgr, fake):
    # Set up previous turn with accepted proposal
    R.append_turn(sb_proj, {
        "id": "turn_prev",
        "at": "2026-11-17T12:00:00",
        "instruction": "lần 1 sửa camera",
        "scope": {"kind": "all", "shots": None, "chapter": None},
        "scope_words": "cả video",
        "model": "gemini",
        "status": "done",
        "proposal_id": "edit_1",
        "notes": "Đã chỉnh camera",
        "conversation_id": None,
        "error": None,
        "accepted": "applied",
    })

    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="nhanh hơn chút nữa",
                  edit_scope={"all": True}, followup=True, manager=mgr, guard_factory=gf, python="python")
    finish(mgr, rec)

    # Fresh session: agy should NOT receive stale --conversation
    last_call = fake.calls()[-1]
    assert "--conversation" not in last_call["argv"]

    # Thread records both turns cleanly
    turns = R.load_thread(sb_proj)
    assert len(turns) == 2
    assert turns[0]["id"] == "turn_prev"
    assert turns[1]["id"] == rec["turn_id"]


def test_followup_without_conv_id_copies_history(sb_proj, tmp_path):
    # Previous turn with no conversation_id
    R.append_turn(sb_proj, {
        "id": "turn_prev",
        "at": "2026-11-17T12:00:00",
        "instruction": "zoom chậm lại",
        "scope": {"kind": "all", "shots": None, "chapter": None},
        "scope_words": "cả video",
        "model": "gemini",
        "status": "done",
        "proposal_id": "edit_123",
        "notes": "Đã chỉnh camera zoom",
        "conversation_id": None,
        "error": None,
        "accepted": "applied",
    })

    turns = R.load_thread(sb_proj)
    history = R.format_previous_exchanges(turns)
    assert "# Previous exchanges" in history
    assert "zoom chậm lại" in history
    assert "Đã chỉnh camera zoom" in history
    assert "APPLIED" in history

    inp = load_inputs(sb_proj)
    ws = W.build(inp, instruction="thêm vòng sáng", scope_words="cả video", history=history, root=tmp_path / "ws_hist")
    instr_text = (ws.root / "INSTRUCTION.md").read_text(encoding="utf-8")
    assert "# Previous exchanges" in instr_text
    assert "zoom chậm lại" in instr_text
    assert "thêm vòng sáng" in instr_text
    assert "APPLIED" in instr_text


def test_edit_api_routes(sb_proj, mgr, fake):
    app = FastAPI()
    app.state.projects_root = sb_proj.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    app.include_router(draft_api.router)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    # 1. Validation checks
    # empty instruction
    r = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "", "scope": {"all": True}})
    assert r.status_code == 422 and r.json()["code"] == "edit_empty_instruction"

    # bad scope
    r = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "sửa", "scope": {}})
    assert r.status_code == 422 and r.json()["code"] == "edit_bad_scope"

    # 2. Scope needs storyboard on project without storyboard
    no_sb_proj = make_synth_project(sb_proj.parent / "nosb")
    r_nosb = client.post(f"/api/projects/nosb/draft/edit", json={"instruction": "sửa", "scope": {"all": True}})
    assert r_nosb.status_code == 409 and r_nosb.json()["code"] == "scope_needs_storyboard"

    # 3. Successful POST /draft/edit
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    r = client.post(f"/api/projects/{pid}/draft/edit", json={
        "instruction": "sửa qua api",
        "scope": {"all": True},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body and "turn_id" in body

    from bti.longjob import manager as global_mgr
    j = global_mgr.wait(body["job_id"], timeout=120)
    assert j is not None and j["state"] == "done"

    # 4. GET /draft/thread
    r_th = client.get(f"/api/projects/{pid}/draft/thread")
    assert r_th.status_code == 200
    th_body = r_th.json()
    assert "turns" in th_body
    assert any(t["id"] == body["turn_id"] for t in th_body["turns"])

    # 5. DELETE /draft/thread
    r_del = client.delete(f"/api/projects/{pid}/draft/thread")
    assert r_del.status_code == 200 and r_del.json()["ok"] is True
    r_th2 = client.get(f"/api/projects/{pid}/draft/thread")
    assert r_th2.json()["turns"] == []

    # 6. Ambiguous scope rejected
    r_amb = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "sửa", "scope": {"shots": ["s0001"], "chapter": "c01"}})
    assert r_amb.status_code == 422 and r_amb.json()["code"] == "edit_bad_scope"

    # 7. Stale base_rev rejected
    r_stale = client.post(f"/api/projects/{pid}/draft/edit", json={"instruction": "sửa", "scope": {"all": True}, "base_rev": "stale-12345"})
    assert r_stale.status_code == 409 and r_stale.json()["code"] == "stale_revision"


def test_locked_overlay_violation(sb_proj):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    cur = copy.deepcopy(inp.current)
    # Add a locked overlay to s0001
    cur["shots"][0]["overlays"] = [{
        "id": "ov_lock_1",
        "technique": "STATIC-09",
        "locked": True,
        "start": {"w": 0, "off": 0.0},
        "dur": 2.0,
    }]
    (sb_proj / "storyboard.json").write_text(json.dumps(cur, indent=1), encoding="utf-8")
    inp = load_inputs(sb_proj)

    # 1. New document removes the locked overlay
    new_doc_removed = copy.deepcopy(cur)
    new_doc_removed["shots"][0]["overlays"] = []
    v1 = D.scope_violations(inp, new_doc_removed, scope_ids={"s0001"})
    assert any(p["code"] == "edit_locked_changed" and "locked overlay ov_lock_1 was removed" in p["message"] for p in v1)

    # 2. New document changes the locked overlay technique
    new_doc_changed = copy.deepcopy(cur)
    new_doc_changed["shots"][0]["overlays"][0]["technique"] = "PAN-01"
    v2 = D.scope_violations(inp, new_doc_changed, scope_ids={"s0001"})
    assert any(p["code"] == "edit_locked_changed" and "locked overlay ov_lock_1 was changed" in p["message"] for p in v2)


def test_proposal_apply_acceptance_tracking(sb_proj, mgr, fake):
    from bti.editor.app import create_app
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    c1["shots"][0]["note"] = "accepted change test"
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa note",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    finish(mgr, rec)

    turns = R.load_thread(sb_proj)
    turn = turns[-1]
    prop_id = turn["proposal_id"]
    assert prop_id is not None
    assert turn["accepted"] is None

    # Apply the proposal
    r_apply = client.post(f"/api/projects/{pid}/proposals/{prop_id}/apply", json={"accept": "all"})
    assert r_apply.status_code == 200, r_apply.text

    # Verify thread records acceptance
    turns_after = R.load_thread(sb_proj)
    turn_after = turns_after[-1]
    assert turn_after["id"] == turn["id"]
    assert turn_after["accepted"] == "applied"
    assert turn_after["accepted_at"] is not None


def test_stale_edit_proposal_rejected_when_storyboard_modified(sb_proj, mgr, fake):
    from bti.editor.app import create_app
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    c1["shots"][0]["note"] = "change before stale"
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    finish(mgr, rec)
    prop_id = R.load_thread(sb_proj)[-1]["proposal_id"]

    # Now modify storyboard on disk behind the proposal's back
    sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    sb["shots"][0]["technique"] = "STATIC-09"
    (sb_proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")

    # Client sends standard apply ({accept: "all"}, without base_rev)
    r_apply = client.post(f"/api/projects/{pid}/proposals/{prop_id}/apply", json={"accept": "all"})
    assert r_apply.status_code == 409
    assert r_apply.json().get("code") == "stale"

    # Saved modification is preserved intact
    cur_sb = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert cur_sb["shots"][0]["technique"] == "STATIC-09"


def test_stale_edit_proposal_rejected_when_timing_changed(sb_proj, mgr, fake):
    from bti.editor.app import create_app
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    c1["shots"][0]["note"] = "change with timing"
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    finish(mgr, rec)
    prop_id = R.load_thread(sb_proj)[-1]["proposal_id"]

    # Change timing file while storyboard is untouched
    tm = json.loads((sb_proj / "timing.json").read_text(encoding="utf-8"))
    tm["words"][0]["w"] = "ChangedFirstWord"
    (sb_proj / "timing.json").write_text(json.dumps(tm, indent=1), encoding="utf-8")

    # Apply attempt should be refused because timing changed
    r_apply = client.post(f"/api/projects/{pid}/proposals/{prop_id}/apply", json={"accept": "all"})
    assert r_apply.status_code == 409
    assert r_apply.json().get("code") == "stale"


def test_effective_boundary_violations(sb_proj):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    cur = copy.deepcopy(inp.current)
    # cur has shots s0001 (start 0), s0002 (locked), s0003, ...
    # 1. Shifting in-scope shot s0003 start affects effective duration of out-of-scope neighbor
    new_doc_shift = copy.deepcopy(cur)
    # s0003 start is word 2, shift it forward to word 3
    new_doc_shift["shots"][2]["start"] = {"w": 3, "off": 0.0}
    v_shift = D.scope_violations(inp, new_doc_shift, scope_ids={"s0003"})
    assert any(p["code"] in ("edit_outside_scope", "edit_locked_changed") and "effective" in p["message"] for p in v_shift)

    # 2. Removing in-scope shot s0003 expands duration of out-of-scope s0002
    new_doc_remove = copy.deepcopy(cur)
    del new_doc_remove["shots"][2]
    v_remove = D.scope_violations(inp, new_doc_remove, scope_ids={"s0003"})
    assert any(p["code"] in ("edit_outside_scope", "edit_locked_changed") and "effective" in p["message"] for p in v_remove)

    # 3. Legal split: splitting s0001 into two shots within its own span preserves neighbor boundaries
    from bti.engine.timing import Timing
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    res_s = D.resolve_shots(cur, tm, inp.timing["duration"])
    s1_t0, s1_t1 = res_s[0]["t0"], res_s[0]["t1"]
    split_w = (cur["shots"][0]["start"]["w"] + cur["shots"][1]["start"]["w"]) // 2
    if split_w <= cur["shots"][0]["start"]["w"]:
        split_w = cur["shots"][0]["start"]["w"]
        split_start = {"w": split_w, "off": 0.5}
    else:
        split_start = {"w": split_w, "off": 0.0}
    new_doc_split = copy.deepcopy(cur)
    shot_b = copy.deepcopy(cur["shots"][0])
    shot_b["id"] = "s0001_bis"
    shot_b["start"] = split_start
    new_doc_split["shots"].insert(1, shot_b)
    v_split = D.scope_violations(inp, new_doc_split, scope_ids={"s0001"})
    # Split within span has zero boundary violations
    assert v_split == []


def test_edit_job_with_absent_picks_json(sb_proj, mgr, fake):
    # Remove picks.json
    (sb_proj / "picks.json").unlink(missing_ok=True)
    assert not (sb_proj / "picks.json").exists()

    inp = load_inputs(sb_proj, for_edit=True)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    c1["shots"][0]["note"] = "absent picks test"
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa không cần picks.json",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "done"
    assert j["result"]["proposal_id"] is not None


def test_edit_job_with_unapproved_picks_json(sb_proj, mgr, fake):
    # Set picks.json approval to False
    pdoc = json.loads((sb_proj / "picks.json").read_text(encoding="utf-8"))
    pdoc["approval"] = {"approved": False}
    (sb_proj / "picks.json").write_text(json.dumps(pdoc, indent=1), encoding="utf-8")

    inp = load_inputs(sb_proj, for_edit=True)
    decomp = D.decompile(inp)
    c1 = decomp["c01"]["spec"]
    c1["shots"][0]["note"] = "unapproved picks test"
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": c1, "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa với picks chưa duyệt",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "done"
    assert j["result"]["proposal_id"] is not None


def test_busy_leaves_no_dangling_turn(sb_proj, mgr, fake):
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec1 = R.start(sb_proj.name, sb_proj, provider="agy", instruction="job 1",
                   edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    assert rec1.get("id") or rec1.get("job_id")

    # Immediate second start while job1 is running raises Busy
    from bti.longjob import Busy
    with pytest.raises(Busy):
        R.start(sb_proj.name, sb_proj, provider="agy", instruction="job 2",
                edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")

    # Thread has ONLY the turn from job 1, not job 2
    turns = R.load_thread(sb_proj)
    assert len(turns) == 1
    assert turns[0]["id"] == rec1["turn_id"]
    finish(mgr, rec1)


def test_notes_only_response_handled_as_no_change(sb_proj, mgr, fake):
    # Fake writes ONLY notes.md in out/, no chapter specs
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {},  # empty specs
        "notes": "Fake agent summary\n",
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="có nên đổi góc máy không?",
                  edit_scope={"all": True}, manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "done"
    assert j["result"]["no_change"] is True
    assert j["result"]["proposal_id"] is None
    assert "Fake agent summary" in j["result"]["notes"]

    turn = R.load_thread(sb_proj)[-1]
    assert turn["id"] == rec["turn_id"]
    assert turn["status"] == "no_change"
    assert turn["proposal_id"] is None
    assert "Fake agent summary" in turn["notes"]


def test_delete_thread_rejected_when_job_active(sb_proj, fake):
    from bti.editor.app import create_app
    from bti.longjob import manager as global_mgr
    global_mgr.configure(projects_root=sb_proj.parent)
    app = create_app(projects_root=sb_proj.parent)
    client = TestClient(app, raise_server_exceptions=False)
    pid = sb_proj.name

    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa",
                  edit_scope={"shots": ["s0001"]}, manager=global_mgr, guard_factory=gf, python="python")

    # Attempt delete while job is running -> 409
    r_del = client.delete(f"/api/projects/{pid}/draft/thread")
    assert r_del.status_code == 409

    finish(global_mgr, rec)
    # After completion, delete succeeds
    r_del_ok = client.delete(f"/api/projects/{pid}/draft/thread")
    assert r_del_ok.status_code == 200


def test_early_cancel_reconciled(sb_proj, mgr, fake):
    from bti.draft.thread import reconcile_thread
    inp = load_inputs(sb_proj)
    decomp = D.decompile(inp)
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": decomp["c01"]["spec"], "c02": decomp["c02"]["spec"]},
        "victim": str(victim),
    }), encoding="utf-8")

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa cancel sớm",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")

    # Cancel immediately
    mgr.cancel(rec["id"])
    j = finish(mgr, rec)
    assert j["state"] == "cancelled"

    # Reconcile turns
    turns = reconcile_thread(sb_proj, manager=mgr)
    matching = [t for t in turns if t["id"] == rec["turn_id"]]
    assert len(matching) == 1
    turn = matching[0]
    assert turn["status"] in ("error", "cancelled")
    assert turn["error"] == "cancelled"


def test_persisted_interrupted_turn_reconciled(sb_proj):
    from bti.draft.thread import append_turn, reconcile_thread
    from bti.longjob.manager import LongJobManager

    # Simulate an active job record persisted before server restart
    fake_jid = "0123456789abcdef"
    fake_turn_id = "turn_interrupted_001"
    jobs_f = sb_proj / "cache" / "longjobs" / f"{fake_jid}.json"
    jobs_f.parent.mkdir(parents=True, exist_ok=True)
    jobs_f.write_text(json.dumps({
        "id": fake_jid,
        "pid": sb_proj.name,
        "kind": "draft",
        "state": "running",
        "created": 1000.0,
    }), encoding="utf-8")

    # Append a turn referencing this job
    append_turn(sb_proj, {
        "id": fake_turn_id,
        "at": "2026-11-17T12:00:00Z",
        "instruction": "lệnh dang dở trước restart",
        "scope": {"kind": "all"},
        "scope_words": "cả video",
        "model": "gemini-3.8-flash",
        "base_rev": "rev1",
        "status": "running",
        "job_id": fake_jid,
        "proposal_id": None,
        "notes": "",
        "error": None,
    })

    # A new manager simulating restart reads disk: marks interrupted
    fresh_mgr = LongJobManager(projects_root=sb_proj.parent)
    rec = fresh_mgr.get(fake_jid)
    assert rec["state"] == "interrupted"

    # reconcile_thread updates running turn to terminal state (error with interrupted)
    turns = reconcile_thread(sb_proj, manager=fresh_mgr)
    matching = [t for t in turns if t["id"] == fake_turn_id]
    assert len(matching) == 1
    turn = matching[0]
    assert turn["status"] != "running"
    assert turn["status"] == "error"
    assert turn["error"] == "interrupted"


def test_malformed_spec_with_notes_rejected_as_error(sb_proj, mgr, fake):
    # Fake writes empty/malformed shots in c01.json alongside notes.md
    # read_out returns specs={} and problems=['spec_no_shots']
    victim = sb_proj / "timing.json"
    (fake.dir / "cfg.json").write_text(json.dumps({
        "specs": {"c01": {"schema": "bti-draft/1", "chapter": "c01", "shots": []}},
        "notes": "Fake agent summary\n",
        "victim": str(victim),
    }), encoding="utf-8")

    saved_before = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))

    rec = R.start(sb_proj.name, sb_proj, provider="agy", instruction="sửa shot với spec lỗi",
                  edit_scope={"shots": ["s0001"]}, manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "error"
    assert j["error_code"] == "compile_error"
    assert "proposal_id" not in (j.get("result") or {})

    # Saved storyboard must remain completely unchanged
    saved_after = json.loads((sb_proj / "storyboard.json").read_text(encoding="utf-8"))
    assert saved_before == saved_after

    # Turn recorded as error (compile_error), never swallowed as no_change
    turn = R.load_thread(sb_proj)[-1]
    assert turn["id"] == rec["turn_id"]
    assert turn["status"] == "error"
    assert turn["error"] == "compile_error"
    assert turn["proposal_id"] is None



