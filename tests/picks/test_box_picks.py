"""The prompt box of step 4 ("Chọn hình") on typed picks operations, through the routes (worker c2box). The model is the mock provider.

The box can rearrange, add and remove pictures and regions the project already has, inside the narration lines the owner selected. It cannot
import: a request for a new picture, or that needs someone to look at a picture, is answered `escalate` and changes nothing."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

DRAFT_TESTS = Path(__file__).resolve().parents[1] / "draft"
if str(DRAFT_TESTS) not in sys.path:
    sys.path.insert(0, str(DRAFT_TESTS))

import box_helpers as BH  # noqa: E402
from box_helpers import ans, why  # noqa: E402
from bti.script.providers import mock  # noqa: E402

ASK = "dòng này cho xem cả bức tranh rồi khuôn mặt"


@pytest.fixture()
def box(tmp_path, monkeypatch):
    b = BH.make_box(tmp_path, monkeypatch)
    yield b
    BH.cleanup(b)


def beat(box, bid):
    return box.picks()["picks"]["beats"][bid]


SET = {"op": "set_picks", "beat": "b0003", "items": [{"asset": "A", "role": "main"}, {"asset": "A", "region": "HEAD", "role": "detail"}]}


def test_rearranging_existing_pictures_is_one_batch_with_the_request_as_its_note(box):
    rev0 = box.picks()["rev"]
    box.model([ans([SET], summary="Dòng này giờ cho xem cả bức tranh, rồi khuôn mặt.")])

    job, turn = box.run_picks_edit(ASK, ["b0003"])

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["doc"] == "picks" and turn["path"] == "fast"
    assert turn["summary"] == "Dòng này giờ cho xem cả bức tranh, rồi khuôn mặt."
    assert [(i["asset"], i.get("region")) for i in beat(box, "b0003")["items"]] == [("A", None), ("A", "HEAD")]
    log = box.changes("picks")
    assert len(log) == 1 and log[0]["batch"] == turn["batch"] and log[0]["note"] == ASK
    assert log[0]["actor"] == "agent:mock" and log[0]["scope"] == {"beats": ["b0003"]} and log[0]["rev_before"] == rev0
    assert turn["batch_changes"] and turn["batch_changes"][0]["what"].startswith("Đoạn 3:")
    assert turn["has_undo"] is True and turn["scope"]["beats"] == ["b0003"]
    assert not box.changes("storyboard")


def test_adding_and_removing_a_picture_of_a_line(box):
    box.model([ans([{"op": "add_pick", "beat": "b0001", "asset": "B", "role": "context"}, {"op": "remove_pick", "beat": "b0001", "index": 0}],
                   summary="Dòng đầu giờ chỉ cho xem hình phong cảnh.")])
    _, turn = box.run_picks_edit("dòng đầu chỉ cho xem hình phong cảnh", ["b0001"])
    assert turn["status"] == "applied"
    assert [i["asset"] for i in beat(box, "b0001")["items"]] == ["B"]
    assert len(turn["batch_changes"]) == 2


def test_a_request_for_a_new_picture_escalates_and_changes_nothing(box):
    raw = box.raw_bytes("picks.json")
    reason = "Dự án chưa có hình bản đồ Bruges, bạn cần tìm thêm hình ở cột Tìm hình."
    box.model([ans(status="escalate", reason=reason, summary="")])

    job, turn = box.run_picks_edit("thêm một tấm bản đồ Bruges", ["b0003"])

    assert job["state"] == "done" and turn["status"] == "escalate" and turn["reason"] == reason == turn["summary"]
    assert box.raw_bytes("picks.json") == raw and not box.changes()
    assert len(mock.CALLS) == 1


def test_import_is_not_offered_and_is_refused_when_the_model_sends_it_anyway(box):
    imp = {"op": "import", "source": "commons", "source_id": "File:Something.jpg"}
    box.model([ans([imp]), ans([imp])])
    raw = box.raw_bytes("picks.json")

    _, turn = box.run_picks_edit(ASK, ["b0003"])

    prompt = box.prompts()[0]
    assert "### import:" not in prompt and "### set_picks:" in prompt and "### skip_beat:" in prompt
    assert turn["status"] == "failed" and turn["error"] == "unknown_op"
    assert box.raw_bytes("picks.json") == raw
    assert '"allowed"' in box.prompts()[1] and "import" not in box.prompts()[1].split('"allowed"')[1].split("]")[0]


def test_the_main_picture_and_the_regions_are_only_offered_for_the_whole_video(box):
    box.model([ans(status="cannot", reason="Cần chọn cả video để đổi vùng.", summary="")])
    box.run_picks_edit("đổi vùng mặt", ["b0003"])
    scoped = box.prompts()[0]
    for name in ("set_main", "set_region", "remove_region"):
        assert "### %s:" % name not in scoped
    box.model([ans(status="cannot", reason="Cần chọn cả video để đổi vùng.", summary="")])
    box.run_picks_edit("đổi vùng mặt", all_=True)
    whole = box.prompts()[1]
    for name in ("set_main", "set_region", "remove_region"):
        assert "### %s:" % name in whole


def test_a_region_can_be_added_in_a_whole_video_box(box):
    reg = {"op": "set_region", "asset": "A", "region": "NECKLACE", "x": 600, "y": 700, "rx": 60, "ry": 60, "label": "chiếc vòng cổ"}
    box.model([ans([reg], summary="Đã thêm một vùng chiếc vòng cổ trên bức tranh chính.")])
    _, turn = box.run_picks_edit("thêm vùng chiếc vòng cổ", all_=True)
    assert turn["status"] == "applied"
    assert box.picks()["picks"]["assets"]["A"]["regions"]["NECKLACE"]["label"] == "chiếc vòng cổ"
    assert box.changes("picks")[0]["scope"] is None


def test_a_line_outside_the_selection_is_refused_twice_and_nothing_is_written(box):
    raw = box.raw_bytes("picks.json")
    other = {"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}]}
    box.model([ans([other]), ans([other])])

    job, turn = box.run_picks_edit(ASK, ["b0003"])

    assert job["state"] == "error" and turn["status"] == "failed" and turn["error"] == "out_of_scope"
    assert "chưa chọn" in turn["summary"] and turn["repairs"] == 1
    assert box.raw_bytes("picks.json") == raw and not box.changes()


def test_a_wrong_picture_is_repaired_on_the_second_try_with_the_servers_error_body(box):
    bad = {"op": "set_picks", "beat": "b0003", "items": [{"asset": "Z"}]}
    box.model([ans([bad]), ans([SET])])
    _, turn = box.run_picks_edit(ASK, ["b0003"])
    assert turn["status"] == "applied" and turn["repairs"] == 1
    repair = box.prompts()[1]
    assert '"code": "unknown_asset"' in repair and '"allowed"' in repair and "[REPAIR TURN]" in repair


def test_ops_that_change_nothing_end_as_no_change(box):
    box.model([ans([{"op": "set_main", "asset": "A"}])])                    # A is the main picture already
    raw = box.raw_bytes("picks.json")
    _, turn = box.run_picks_edit("tranh chính là bức A", all_=True)
    assert turn["status"] == "no_change" and not box.changes() and box.raw_bytes("picks.json") == raw


def test_undo_through_the_cards_route_and_the_conflict_of_a_later_change(box):
    before = box.picks()["picks"]["beats"]["b0003"]
    box.model([ans([SET])])
    _, turn = box.run_picks_edit(ASK, ["b0003"])

    r = box.picks_card_undo(turn)

    assert r.status_code == 200 and r.json()["status"] == "undone", r.text
    assert beat(box, "b0003") == before
    assert box.turn(turn["id"], picks=True)["status"] == "undone" and box.changes("picks")[0]["undo_of"] == turn["batch"]
    # a second turn, then the owner changes the same line by hand: the undo says why it cannot
    box.model([ans([SET])])
    _, turn2 = box.run_picks_edit(ASK, ["b0003"])
    rev = box.picks()["rev"]
    ok = box.client.post(box.u("/picks/ops"), json={"base_rev": rev, "actor": "human", "ops": [{"op": "skip_beat", "beat": "b0003"}]})
    assert ok.status_code == 200, ok.text
    raw = box.raw_bytes("picks.json")
    bad = box.picks_card_undo(turn2)
    assert bad.status_code == 409 and bad.json()["code"] == "undo_conflict" and bad.json()["fix"] and bad.json()["retry"] == "after_fix"
    assert box.raw_bytes("picks.json") == raw


def test_the_two_boxes_have_separate_threads(box):
    box.model([ans([SET]), ans([{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 260}}])])
    _, pt = box.run_picks_edit(ASK, ["b0003"])
    _, st = box.run_edit("làm vòng sáng to hơn", ["s0002"])
    assert [t["id"] for t in box.picks_thread()] == [pt["id"]] and [t["id"] for t in box.thread()] == [st["id"]]
    assert box.client.delete(box.u("/draft/thread")).status_code == 200
    assert [t["id"] for t in box.picks_thread()] == [pt["id"]] and box.thread() == []
    assert box.client.delete(box.u("/picks/edit/thread")).status_code == 200 and box.picks_thread() == []


def test_the_routes_refuse_with_code_fix_and_retry(box):
    r = box.post_picks_edit("   ", ["b0003"])
    assert r.status_code == 422 and r.json()["code"] == "edit_empty_instruction" and r.json()["fix"] and r.json()["retry"] == "after_fix"
    r = box.post_picks_edit(ASK)
    assert r.status_code == 422 and r.json()["code"] == "edit_bad_scope" and "beats" in r.json()["fix"]
    r = box.post_picks_edit(ASK, ["b9999"])
    assert r.status_code == 422 and r.json()["code"] == "edit_bad_scope"
    r = box.post_picks_edit(ASK, ["b0003"], base_rev="0" * 40)
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == box.picks()["rev"]
    r = box.client.post(box.u("/picks/edit/t_nothing/undo"), json={})
    assert r.status_code == 404 and r.json()["code"] == "turn_not_found"


def test_a_second_turn_while_one_runs_is_busy(box, monkeypatch):
    held = BH.HeldModel(monkeypatch)
    box.model([ans([SET])])
    r = box.post_picks_edit(ASK, ["b0003"])
    assert held.entered.wait(30)
    second = box.post_picks_edit(ASK, ["b0003"])
    assert second.status_code == 409 and second.json()["code"] == "busy"
    assert box.client.delete(box.u("/picks/edit/thread")).status_code == 409
    held.release.set()
    box.wait_job(r.json()["job_id"])


def test_the_briefing_holds_the_generated_schemas_and_only_the_scopes_lines(box):
    from bti.ops import registry
    box.model([ans(status="cannot", reason="Không làm được.", summary="")])
    box.run_picks_edit(ASK, ["b0003"])
    text = box.prompts()[0]
    import json
    for name in BH_allowed(registry):
        d = registry.defs("picks")[name]
        assert "### %s:" % name in text and json.dumps(d.example, ensure_ascii=False, separators=(",", ":")) in text
    in_scope = text.split("### The lines in scope")[1].split("### The line before")[0]
    assert '"id":"b0003"' in in_scope and '"id":"b0001"' not in in_scope and '"id":"b0004"' not in in_scope
    assert "before:" in text and "after:" in text                               # the neighbours, read only
    assert '"HEAD"' in text and "used_in" in text                               # the pictures with their regions and where each is used
    assert "Dòng 3 đang chọn" in text
    assert len(text) < 14000, len(text)


def BH_allowed(registry):
    from bti.draft import boxops
    return boxops.allowed_ops("picks")
