import json
import pytest
from pathlib import Path

from tests.draft.helpers import make_synth_project, GOOD, clean_spec
from bti.draft.inputs import load_inputs, resolve_edit_scope, clone_inputs
from bti.draft.compile import compile_specs
from bti.draft.fastedit import fast_edit
from bti.script.providers import mock


@pytest.fixture
def synth_edit_setup(tmp_path):
    proj = make_synth_project(tmp_path / "proj")
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    res0 = compile_specs(inp, specs, draw=False)
    assert not res0.errors
    (proj / "storyboard.json").write_text(json.dumps(res0.storyboard, indent=1), encoding="utf-8")

    inp0 = load_inputs(proj, for_edit=True)
    first_shot_id = inp0.current["shots"][0]["id"]
    es, sc, words = resolve_edit_scope(inp0, {"shots": [first_shot_id]})
    inp_edit = clone_inputs(inp0, scope=sc, edit_shots=es)
    return inp_edit, first_shot_id


def test_fastedit_good_edit(synth_edit_setup):
    inp_edit, first_shot_id = synth_edit_setup
    good = {
        "result": "edit",
        "summary": "Đổi kỹ thuật máy quay sang zoom chậm",
        "shots": [{
            "id": first_shot_id,
            "beat": "b0001",
            "start_word": 0,
            "off": 0.0,
            "technique": "CAM-01",
            "intent": "explore",
            "slots": {"image": {"asset": "A"}},
            "params": {},
            "overlays": [],
            "note": "slow push in"
        }],
        "changes": [{"shot": first_shot_id, "what": "Đổi góc quay sang zoom từ từ"}]
    }

    mock.set_canned([json.dumps(good)])
    res = fast_edit(inp_edit, "zoom chậm hơn", model="mock")
    assert res.status == "applied"
    assert res.summary == "Đổi kỹ thuật máy quay sang zoom chậm"
    assert len(res.changes) == 1
    assert res.changes[0]["what"] == "Đổi góc quay sang zoom từ từ"
    assert res.storyboard is not None
    assert res.repair_used is False


def test_fastedit_cannot(synth_edit_setup):
    inp_edit, _ = synth_edit_setup
    cannot = {
        "result": "cannot",
        "reason": "Yêu cầu cần thêm tranh mới chưa có trong dự án",
        "summary": ""
    }

    mock.set_canned([json.dumps(cannot)])
    res = fast_edit(inp_edit, "thêm tranh mới của họa sĩ khác", model="mock")
    assert res.status == "cannot"
    assert res.reason == "Yêu cầu cần thêm tranh mới chưa có trong dự án"
    assert res.storyboard is None
    assert res.repair_used is False


def test_fastedit_escalate(synth_edit_setup):
    inp_edit, _ = synth_edit_setup
    escalate = {
        "result": "escalate",
        "reason": "Cần phóng to chi tiết nhẫn cưới chưa có vùng xác định",
        "summary": ""
    }

    mock.set_canned([json.dumps(escalate)])
    res = fast_edit(inp_edit, "zoom sát nhẫn cưới", model="mock")
    assert res.status == "escalate"
    assert res.reason == "Cần phóng to chi tiết nhẫn cưới chưa có vùng xác định"
    assert res.storyboard is None
    assert res.repair_used is False


def test_fastedit_broken_json(synth_edit_setup):
    inp_edit, _ = synth_edit_setup
    # Both initial and repair answer are broken JSON
    mock.set_canned(["Broken JSON {{{", "Still broken JSON }}}"])
    res = fast_edit(inp_edit, "sửa cảnh", model="mock", max_repairs=1)
    assert res.status == "failed"
    assert res.repair_used is True
    assert "JSON parse error" in res.reason


def test_fastedit_touches_shot_outside_scope(synth_edit_setup):
    inp_edit, first_shot_id = synth_edit_setup
    # The answer includes shot s0002 which is in the project but outside the scope {first_shot_id}
    other_shot_id = inp_edit.current["shots"][1]["id"]
    outside_scope = {
        "result": "edit",
        "summary": "Sửa hai cảnh",
        "shots": [
            {
                "id": first_shot_id,
                "beat": "b0001",
                "start_word": 0,
                "technique": "CAM-01",
                "intent": "explore",
                "slots": {"image": {"asset": "A"}},
                "params": {},
                "overlays": []
            },
            {
                "id": other_shot_id,
                "beat": "b0002",
                "start_word": 10,
                "technique": "CAM-02",
                "intent": "explore",
                "slots": {"image": {"asset": "A"}},
                "params": {},
                "overlays": []
            }
        ],
        "changes": [{"shot": first_shot_id, "what": "Sửa cảnh 1"}]
    }

    # Both tries return the outside-scope shot
    mock.set_canned([json.dumps(outside_scope), json.dumps(outside_scope)])
    res = fast_edit(inp_edit, "sửa cảnh", model="mock", max_repairs=1)
    assert res.status == "failed"
    assert res.repair_used is True
    assert any("outside the allowed edit scope" in iss for iss in res.issues)


def test_fastedit_needs_one_repair_call(synth_edit_setup):
    inp_edit, first_shot_id = synth_edit_setup
    broken_initial = "I am an LLM, here is invalid JSON: { shot: broken"
    good_repair = {
        "result": "edit",
        "summary": "Đã sửa thành công sau lượt chỉnh sửa",
        "shots": [{
            "id": first_shot_id,
            "beat": "b0001",
            "start_word": 0,
            "technique": "CAM-01",
            "intent": "explore",
            "slots": {"image": {"asset": "A"}},
            "params": {},
            "overlays": []
        }],
        "changes": [{"shot": first_shot_id, "what": "Đổi góc quay"}]
    }

    mock.set_canned([broken_initial, json.dumps(good_repair)])
    res = fast_edit(inp_edit, "zoom chậm hơn", model="mock", max_repairs=1)
    assert res.status == "applied"
    assert res.repair_used is True
    assert res.summary == "Đã sửa thành công sau lượt chỉnh sửa"
    assert res.storyboard is not None


def test_fastedit_fails_after_repair(synth_edit_setup):
    inp_edit, first_shot_id = synth_edit_setup
    # Initial has empty shots list, repair also has empty shots list
    empty_shots = {
        "result": "edit",
        "summary": "Không có cảnh nào",
        "shots": [],
        "changes": []
    }

    mock.set_canned([json.dumps(empty_shots), json.dumps(empty_shots)])
    res = fast_edit(inp_edit, "zoom chậm hơn", model="mock", max_repairs=1)
    assert res.status == "failed"
    assert res.repair_used is True
    assert any("requires a non-empty list of 'shots'" in iss for iss in res.issues)


def test_the_draw_check_of_changed_shots_really_runs(synth_edit_setup):
    """It once imported DraftProject from the wrong module and the ImportError was swallowed: the check never ran."""
    import copy
    from bti.draft.fastedit import _draw_check_changed_shots
    inp_edit, first_shot_id = synth_edit_setup
    sb = copy.deepcopy(inp_edit.current)
    assert _draw_check_changed_shots(inp_edit, sb) == []                    # nothing changed: nothing to draw, nothing wrong
    sb["shots"][0]["note"] = "changed"
    assert _draw_check_changed_shots(inp_edit, sb) == []                    # a drawable change passes
    sb["assets"]["A"]["file"] = "media/does_not_exist.jpg"                  # a picture that is not there cannot be drawn
    issues = _draw_check_changed_shots(inp_edit, sb)
    assert issues and all(i["level"] == "error" for i in issues), issues


def test_the_draw_check_draws_only_what_the_edit_can_have_affected(synth_edit_setup):
    """Counts the frames drawn (no timing): a note change on one shot draws that shot only (and the transition into the next one)."""
    import copy
    from bti.draft.drawcheck import affected_shots, draw_changed
    inp_edit, first_id = synth_edit_setup
    cur = inp_edit.current
    ids = [s["id"] for s in cur["shots"]]
    assert len(ids) >= 5

    # nothing changed: no frame at all
    rep = draw_changed(inp_edit, copy.deepcopy(cur))
    assert rep.frames == [] and rep.shots == set()

    # one shot changed, same times: only its frames (3 plus overlay frames), and at most the transition into the next shot
    sb = copy.deepcopy(cur)
    sb["shots"][0]["note"] = "changed"
    rep = draw_changed(inp_edit, sb)
    assert rep.full == {first_id}
    assert rep.shots <= {ids[0], ids[1]}, rep.shots
    assert all(sid == ids[0] or path.endswith("transition_in") for sid, path, _ in rep.frames), rep.frames
    assert len(rep.frames) < len(ids), rep.frames                            # far fewer frames than a full check (3 per shot)

    # the start of shot 2 moves later: shot 1 (its end) and shot 2 are affected; shots 3 and later are not drawn
    sb = copy.deepcopy(cur)
    st = sb["shots"][1]["start"]
    assert "w" in st
    st["off"] = float(st.get("off") or 0.0) + 0.5
    full, trans = affected_shots(inp_edit, sb)
    assert full == {ids[0], ids[1]}, (full, trans)
    rep = draw_changed(inp_edit, sb)
    assert set(ids[3:]).isdisjoint(rep.shots), rep.shots
    assert {ids[0], ids[1]} <= rep.shots


def test_a_removed_and_added_shot_marks_the_neighbours_whose_times_moved(synth_edit_setup):
    import copy
    from bti.draft.drawcheck import affected_shots
    inp_edit, first_id = synth_edit_setup
    cur = inp_edit.current
    ids = [s["id"] for s in cur["shots"]]
    sb = copy.deepcopy(cur)
    del sb["shots"][1]                               # shot 1's range is now covered by the shot before it
    full, _ = affected_shots(inp_edit, sb)
    assert ids[0] in full and ids[1] not in full and set(ids[3:]).isdisjoint(full), full
