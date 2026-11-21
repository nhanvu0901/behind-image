"""The routes of the prompt boxes next to the older ones (worker c2box): what the page of today still sends keeps working, a turn made before the typed
operations keeps its own undo, the two threads do not mix, and the new page files are served."""
from __future__ import annotations

import copy
import sys
import time
from pathlib import Path

import pytest

DRAFT_TESTS = Path(__file__).resolve().parents[1] / "draft"
if str(DRAFT_TESTS) not in sys.path:
    sys.path.insert(0, str(DRAFT_TESTS))

import box_helpers as BH  # noqa: E402
from box_helpers import ans, set_ring  # noqa: E402


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = BH.make_box(tmp_path, monkeypatch)
    yield b
    BH.cleanup(b)


def test_the_page_files_of_the_boxes_and_the_list_of_changes_are_served(box):
    for f in ("promptedit.js", "changeslist.js", "changeslogic.js", "editlogic.js", "labels.js", "errmsg.js"):
        r = box.client.get("/js/" + f)
        assert r.status_code == 200 and "export" in r.text, f
    assert "BOX_LABELS" in box.client.get("/js/labels.js").text and "boxErrorText" in box.client.get("/js/errmsg.js").text


def test_the_body_the_page_sends_today_still_starts_an_edit(box):
    """POST /draft/edit with instruction, scope, mode auto and base_rev: the page of step 5 as it is."""
    box.model([ans([set_ring()])])
    r = box.client.post(box.u("/draft/edit"), json={"instruction": "làm vòng sáng to hơn", "scope": {"shots": ["s0002"]}, "mode": "auto", "base_rev": box.sb_rev()})
    assert r.status_code == 200 and set(r.json()) >= {"job_id", "turn_id", "model", "agent"}, r.text
    assert box.wait_job(r.json()["job_id"])["state"] == "done"
    t = box.turn(r.json()["turn_id"])
    assert t["status"] == "applied" and t["path"] == "fast" and t["scope_words"] == "1 cảnh đang chọn"


def test_a_stale_base_rev_is_refused_with_the_current_one(box):
    r = box.client.post(box.u("/draft/edit"), json={"instruction": "x", "scope": {"shots": ["s0002"]}, "mode": "fast", "base_rev": "0" * 40})
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == box.sb_rev() and r.json()["fix"]


def test_a_turn_made_before_the_typed_operations_keeps_its_own_undo(box):
    """No batch on the turn: the older mechanism (the stored storyboards of the turn) still undoes it."""
    from bti.draft.merge import locked_update
    from bti.draft.thread import append_turn, save_turn_storyboards
    before = box.saved()
    after = copy.deepcopy(before)
    next(s for s in after["shots"] if s["id"] == "s0003")["note"] = "changed by an old turn"

    def make(cur):
        d = copy.deepcopy(cur)
        next(s for s in d["shots"] if s["id"] == "s0003")["note"] = "changed by an old turn"
        return d, None
    locked_update(box.pdir, make)
    save_turn_storyboards(box.pdir, "t_old", before, box.saved())
    append_turn(box.pdir, {"id": "t_old", "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "instruction": "old", "status": "applied", "summary": "Đã sửa.",
                           "scope": {"kind": "shots", "shots": ["s0003"]}, "changes": [{"shot_id": "s0003", "op": "changed", "what": "x"}], "path": "fast"})
    t = box.turn("t_old")
    assert t["batch"] is None and t["has_undo"] is True and t["doc"] == "storyboard"
    r = box.client.post(box.u("/draft/edit/t_old/undo"), json={})
    assert r.status_code == 200 and r.json()["status"] == "undone", r.text
    assert box.shot("s0003")["note"] == next(s for s in before["shots"] if s["id"] == "s0003")["note"]
    assert not box.changes()                                      # the older undo is not in the change log


def test_a_turn_without_a_stored_copy_says_undo_unavailable_as_before(box):
    from bti.draft.thread import append_turn
    append_turn(box.pdir, {"id": "t_lost", "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "instruction": "old", "status": "applied", "summary": "x",
                           "scope": {"kind": "all"}, "changes": [], "path": "fast"})
    r = box.client.post(box.u("/draft/edit/t_lost/undo"), json={})
    assert r.status_code == 410 and r.json()["code"] == "undo_unavailable" and r.json()["fix"]


def test_the_two_threads_do_not_mix_and_a_turn_belongs_to_one_box(box):
    box.model([ans([set_ring()]), ans([{"op": "skip_beat", "beat": "b0003"}], summary="Dòng này giờ cho xem tranh chính.")])
    _, st = box.run_edit("làm vòng sáng to hơn", ["s0002"])
    _, pt = box.run_picks_edit("dòng này dùng lại tranh chính", ["b0003"])
    assert st["doc"] == "storyboard" and pt["doc"] == "picks"
    assert [t["id"] for t in box.thread()] == [st["id"]] and [t["id"] for t in box.picks_thread()] == [pt["id"]]
    assert box.client.post(box.u("/picks/edit/%s/undo" % st["id"]), json={}).status_code == 404       # a storyboard turn is not found by the pictures' box
    assert box.picks()["picks"]["beats"]["b0003"]["status"] == "skip"
    assert box.client.post(box.u("/picks/edit/%s/undo" % pt["id"]), json={}).status_code == 200


def test_the_thread_marks_a_batch_undone_from_the_list_of_changes_for_both_boxes(box):
    box.model([ans([{"op": "skip_beat", "beat": "b0003"}], summary="Dòng này giờ cho xem tranh chính.")])
    _, pt = box.run_picks_edit("dòng này dùng lại tranh chính", ["b0003"])
    r = box.client.post(box.u("/changes/%s/undo" % pt["batch"]), json={"base_rev": box.picks()["rev"], "actor": "human"})
    assert r.status_code == 200, r.text
    t = box.turn(pt["id"], picks=True)
    assert t["status"] == "undone" and t["has_undo"] is False
