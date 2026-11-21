"""The prompt box of step 5 on typed operations, end to end through the routes (worker c2box). The model is the mock provider with canned answers.

What the owner relies on: a small request is one batch in the change log with the request as its note, the card carries the batch's own
sentences and its undo, a refusal reads as a plain sentence and writes nothing, `cannot` and `escalate` change nothing, and nothing outside the
selection is ever touched."""
from __future__ import annotations

import json

import pytest

from box_helpers import CAM, HeldModel, ans, set_ring, strip, why
from bti.script.providers import mock

SCOPE = ["s0002"]
ASK = "làm vòng sáng ở cảnh này to hơn"


def test_a_normal_answer_is_one_batch_with_the_request_as_its_note(box):
    before = box.saved()
    rev0 = box.sb_rev()
    box.model([ans([set_ring()])])

    job, turn = box.run_edit(ASK, SCOPE)

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["doc"] == "storyboard" and turn["path"] == "fast"
    assert turn["summary"] == "Vòng sáng ở cảnh này to hơn." and turn["summary_source"] == "model"
    logged = box.changes("storyboard")
    assert len(logged) == 1
    rec = logged[0]
    assert rec["batch"] == turn["batch"] and rec["note"] == ASK
    assert rec["actor"] == "agent:mock" and rec["scope"] == {"shots": SCOPE} and rec["rev_before"] == rev0
    assert [c["what"] for c in rec["changes"]] == [c["what"] for c in turn["batch_changes"]]
    assert all(" " in c["what"] and "s0002" not in c["what"] for c in turn["batch_changes"])          # a sentence for a person, no id
    assert turn["before_rev"] == rev0 and turn["after_rev"] == box.sb_rev() != rev0
    after = box.saved()
    assert box.shot("s0002", after)["overlays"][0]["params"]["rx"] == 260
    assert box.shot("s0002", after)["overlays"][0]["source"] == "agent"
    # nothing else of the document moved
    assert [s for s in after["shots"] if s["id"] != "s0002"] == [s for s in before["shots"] if s["id"] != "s0002"]
    assert turn["has_undo"] is True


def test_the_card_shows_the_batch_sentences_for_the_changed_shot_only(box):
    """Defect of the earlier probe (13.4 open point 1): existing overlays of a returned shot were reported as changed when the request did not
    touch them. Now the card lists what the batch changed: one shot, its sentence, and the other overlay is byte-identical."""
    before = box.saved()
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)
    assert [c["shot_id"] for c in turn["changes"]] == ["s0002"] and turn["changes"][0]["op"] == "changed"
    assert turn["changes"][0]["facts"] == [c["what"] for c in turn["batch_changes"]]
    assert len(turn["batch_changes"]) == 1 and "lớp phủ" in turn["batch_changes"][0]["what"]
    o2_before = box.shot("s0002", before)["overlays"][1]
    assert box.shot("s0002")["overlays"][1] == o2_before


def test_an_answer_with_a_wrong_operation_is_repaired_on_the_second_try(box):
    box.model([ans([{"op": "make_it_pretty", "shot": "s0002"}]), ans([set_ring()])])

    _, turn = box.run_edit(ASK, SCOPE)

    assert turn["status"] == "applied" and turn["repairs"] == 1
    first, second = box.prompts()[0], box.prompts()[1]
    assert "[REPAIR TURN]" not in first and "[REPAIR TURN]" in second
    assert '"code": "unknown_op"' in second and '"fix"' in second and "make_it_pretty" in second     # the server's own error body
    assert len(box.changes()) == 1 and box.shot("s0002")["overlays"][0]["params"]["rx"] == 260


def test_a_dry_run_refusal_goes_back_to_the_model_with_code_fix_and_fields(box):
    bad = {"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"no_such_param": 1}}
    box.model([ans([bad]), ans([set_ring()])])

    _, turn = box.run_edit(ASK, SCOPE)

    assert turn["status"] == "applied" and turn["repairs"] == 1
    repair = box.prompts()[1]
    assert '"code": "unknown_param"' in repair and '"path": "ops[0].params.no_such_param"' in repair and '"allowed"' in repair


def test_refused_twice_ends_failed_with_a_plain_sentence_and_nothing_is_written(box):
    raw = box.raw_bytes()
    outside = {"op": "set_params", "shot": "s0004", "overlay": "o1", "params": {"size_px": 30}}       # a shot the owner did not select
    box.model([ans([outside]), ans([outside])])

    job, turn = box.run_edit(ASK, SCOPE)

    assert job["state"] == "error" and job["error_code"] == "out_of_scope"
    assert turn["status"] == "failed" and turn["error"] == "out_of_scope" and turn["repairs"] == 1
    assert "chưa chọn" in turn["summary"] and not any(w in turn["summary"] for w in ("out_of_scope", "s0004", "scope"))
    assert box.raw_bytes() == raw and not box.changes()


def test_a_locked_shot_is_refused_by_the_server_and_named_by_its_number(box):
    raw = box.raw_bytes()
    locked = {"op": "set_params", "shot": "s0006", "params": {"zoom": 1.0}}
    box.model([ans([locked]), ans([locked])])

    _, turn = box.run_edit(ASK, ["s0005", "s0006"])

    assert turn["status"] == "failed" and turn["error"] == "locked"
    assert "Cảnh 6 đang khóa" in turn["summary"]
    assert box.raw_bytes() == raw and not box.changes()
    assert "locked" in box.prompts()[1] and '"code": "locked"' in box.prompts()[1]


def test_the_box_does_not_offer_or_accept_lock_unlock_or_replace_range(box):
    box.model([ans([{"op": "unlock", "shot": "s0006"}]), ans([{"op": "unlock", "shot": "s0006"}])])
    _, turn = box.run_edit(ASK, ["s0005", "s0006"])
    prompt = box.prompts()[0]
    for name in ("lock", "unlock", "replace_range"):
        assert "### %s:" % name not in prompt
    assert turn["status"] == "failed" and turn["error"] == "unknown_op"
    assert box.shot("s0006")["locked"] is True


def test_cannot_changes_nothing_and_its_reason_reaches_the_turn(box):
    raw = box.raw_bytes()
    reason = "Cần một bức tranh mới, dự án chưa có. Hãy chọn tranh ở bước Chọn hình."
    box.model([ans(status="cannot", reason=reason, summary="")])

    job, turn = box.run_edit("đổi sang tranh khác", SCOPE)

    assert job["state"] == "done" and turn["status"] == "no_change" and turn["path"] == "fast"
    assert turn["summary"] == reason and turn["reason"] == reason
    assert box.raw_bytes() == raw and not box.changes()


def test_a_cannot_with_an_english_reason_is_sent_back_once_and_never_shown_in_english(box):
    """Defect of the earlier probe (13.4 open point 2): the model's reason was English, the owner got a fixed sentence that told him nothing."""
    english = "Select the next shot too: the length of a shot is where the next one starts."
    good = "Cần chọn thêm cảnh sau, vì độ dài của một cảnh là đến chỗ cảnh sau bắt đầu."
    box.model([ans(status="cannot", reason=english, summary=""), ans(status="cannot", reason=good, summary="")])

    _, turn = box.run_edit("cho cảnh này dài hơn một giây", SCOPE)

    assert turn["status"] == "no_change" and turn["reason"] == good == turn["summary"]
    assert "`reason`" in box.prompts()[1] and english not in turn["summary"]


def test_a_reason_that_stays_english_is_replaced_by_a_fixed_sentence_and_kept_under_details(box):
    english = "Select the next shot too."
    box.model([ans(status="cannot", reason=english, summary=""), ans(status="cannot", reason=english, summary="")])

    _, turn = box.run_edit("cho cảnh này dài hơn một giây", SCOPE)

    assert turn["status"] == "no_change" and turn["summary"] and any(ch in turn["summary"] for ch in "ăâêôơưđ")
    assert english not in turn["summary"] and english in turn["notes"]


def test_an_owner_who_writes_english_gets_english_sentences(box):
    box.model([ans([set_ring()], summary="The ring of light around the middle is bigger now.")])
    _, turn = box.run_edit("make the ring around the middle bigger", SCOPE)
    assert turn["status"] == "applied" and turn["summary"].startswith("The ring of light") and turn["summary_source"] == "model"
    assert "English" in box.prompts()[0].split("## The request")[0]


def test_an_english_summary_for_a_vietnamese_owner_is_replaced_by_the_batch_sentence(box):
    """Defect of the earlier probe (13.4 open point 3): the model's own sentence was never fit to show. The summary the owner reads is always
    Vietnamese: the model's when it passes the check, else the server's, made from the batch's first sentence."""
    box.model([ans([set_ring()], summary="The ring is bigger now.")])
    _, turn = box.run_edit(ASK, SCOPE)
    assert turn["status"] == "applied" and turn["summary_source"] == "code"
    assert turn["summary"] == turn["batch_changes"][0]["what"] and "Cảnh 2" in turn["summary"]
    assert turn["repairs"] == 0                       # a sentence is not worth a second call: the batch's sentences say what changed


def test_escalate_offers_the_slow_path_and_changes_nothing(box):
    raw = box.raw_bytes()
    reason = "Chi tiết này chưa có vùng nào trên tranh, cần bước xem tranh kỹ hơn."
    box.model([ans(status="escalate", reason=reason, summary="")])

    job, turn = box.run_edit("zoom vào chiếc nhẫn", SCOPE, mode="auto")

    assert job["state"] == "done" and turn["status"] == "escalate" and turn["path"] == "fast" and turn["escalated"] is False
    assert turn["reason"] == reason == turn["summary"]
    assert box.raw_bytes() == raw and not box.changes()
    assert len(mock.CALLS) == 1                       # the slow path is the owner's button, never started by itself


def test_a_save_of_another_shot_while_the_model_thinks_is_kept_and_the_batch_still_applies(box, monkeypatch):
    held = HeldModel(monkeypatch)
    box.model([ans([set_ring()])])
    r = box.post_edit(ASK, SCOPE)
    assert held.entered.wait(30)
    st = box.sb()
    sb = strip(st["storyboard"])
    box.shot("s0009", sb)["note"] = "the owner wrote this meanwhile"
    put = box.client.put(box.u("/storyboard"), json={"storyboard": sb, "base_rev": st["rev"]})
    assert put.status_code == 200, put.text
    held.release.set()
    job = box.wait_job(r.json()["job_id"])

    turn = box.turn(r.json()["turn_id"])
    assert job["state"] == "done" and turn["status"] == "applied"
    now = box.saved()
    assert box.shot("s0009", now)["note"] == "the owner wrote this meanwhile" and box.shot("s0002", now)["overlays"][0]["params"]["rx"] == 260


def test_a_change_of_the_selected_shot_while_the_model_thinks_fails_saying_the_storyboard_changed(box, monkeypatch):
    held = HeldModel(monkeypatch)
    box.model([ans([set_ring()])])
    r = box.post_edit(ASK, SCOPE)
    assert held.entered.wait(30)
    st = box.sb()
    sb = strip(st["storyboard"])
    box.shot("s0002", sb)["note"] = "the owner changed this very shot"
    assert box.client.put(box.u("/storyboard"), json={"storyboard": sb, "base_rev": st["rev"]}).status_code == 200
    held.release.set()
    box.wait_job(r.json()["job_id"])

    turn = box.turn(r.json()["turn_id"])
    assert turn["status"] == "failed" and turn["error"] == "stale_revision" and "đã đổi" in turn["summary"]
    assert not box.changes() and box.shot("s0002")["overlays"][0]["params"]["rx"] == 200


def _inject_after_dry_run(monkeypatch, box, mutate):
    """After the dry run of the batch, `mutate(backend)` changes the storyboard: a save between the dry run and the write."""
    from bti.draft import boxops
    real = boxops.Backend.run
    done = []

    def run(self, kind, body):
        out = real(self, kind, body)
        if body.get("dry_run") and not done:
            done.append(1)
            mutate(self)
        return out

    monkeypatch.setattr(boxops.Backend, "run", run)


def test_a_stale_revision_between_the_dry_run_and_the_write_is_retried_when_the_scope_did_not_change(box, monkeypatch):
    def other_shot(backend):
        doc, rev = backend.read("storyboard")
        backend.run("storyboard", {"base_rev": rev, "actor": "human", "ops": [{"op": "add_overlay", "shot": "s0004", "technique": "HI-01",
                                                                                "params": {"at": "CENTRE", "rx": 220, "ry": 220}, "start": {"w": 70}, "dur": 4}]})

    _inject_after_dry_run(monkeypatch, box, other_shot)
    box.model([ans([set_ring()])])

    _, turn = box.run_edit(ASK, SCOPE)

    assert turn["status"] == "applied"
    assert len(box.changes("storyboard")) == 2 and box.shot("s0002")["overlays"][0]["params"]["rx"] == 260
    assert turn["before_rev"] != turn["after_rev"]


def test_a_stale_revision_between_the_dry_run_and_the_write_fails_when_the_scope_changed(box, monkeypatch):
    def same_shot(backend):
        doc, rev = backend.read("storyboard")
        backend.run("storyboard", {"base_rev": rev, "actor": "human", "ops": [{"op": "set_overlay", "shot": "s0002", "overlay": "o2", "dur": 2.5}]})

    _inject_after_dry_run(monkeypatch, box, same_shot)
    box.model([ans([set_ring()])])

    _, turn = box.run_edit(ASK, SCOPE)

    assert turn["status"] == "failed" and turn["error"] == "stale_revision" and "đã đổi" in turn["summary"]
    assert box.shot("s0002")["overlays"][0]["params"]["rx"] == 200 and len(box.changes("storyboard")) == 1      # only the owner's own batch


def test_undo_through_the_cards_route_puts_the_storyboard_back(box):
    before = box.saved()
    rev0 = box.sb_rev()
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)

    r = box.card_undo(turn)

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "undone" and r.json()["rev"] == box.sb_rev() == rev0
    assert box.saved() == before
    assert box.turn(turn["id"])["status"] == "undone"
    log = box.changes("storyboard")
    assert log[0]["undo_of"] == turn["batch"] and log[0]["actor"] == "human"
    assert box.card_undo(box.turn(turn["id"])).status_code == 409                # already undone


def test_an_undo_of_a_change_made_since_says_undo_conflict_and_changes_nothing(box):
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)
    rev = box.sb_rev()
    ok = box.client.post(box.u("/storyboard/ops"), json={"base_rev": rev, "actor": "human",
                                                        "ops": [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 300, "ry": 300}}]})
    assert ok.status_code == 200, ok.text
    raw = box.raw_bytes()

    r = box.card_undo(turn)

    assert r.status_code == 409 and r.json()["code"] == "undo_conflict" and r.json()["fix"] and r.json()["retry"] == "after_fix"
    assert box.raw_bytes() == raw and box.turn(turn["id"])["status"] == "applied"


def test_an_undo_whose_copies_are_gone_says_undo_unavailable_and_the_card_knows(box):
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)
    (box.log_dir() / ("%s.before.json" % turn["batch"])).unlink()
    (box.log_dir() / ("%s.after.json" % turn["batch"])).unlink()
    rec = json.loads((box.log_dir() / ("%s.json" % turn["batch"])).read_text(encoding="utf-8"))
    rec["copies"] = False
    (box.log_dir() / ("%s.json" % turn["batch"])).write_text(json.dumps(rec), encoding="utf-8")

    assert box.turn(turn["id"])["has_undo"] is False
    r = box.card_undo(turn)
    assert r.status_code == 409 and r.json()["code"] == "undo_unavailable"


def test_a_batch_undone_from_the_list_of_changes_shows_as_undone_on_the_card(box):
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)
    r = box.client.post(box.u("/changes/%s/undo" % turn["batch"]), json={"base_rev": box.sb_rev(), "actor": "human"})
    assert r.status_code == 200, r.text
    t = box.turn(turn["id"])
    assert t["status"] == "undone" and t["has_undo"] is False


def test_the_frames_of_the_card_come_from_the_change_log_copies(box):
    box.model([ans([set_ring()])])
    _, turn = box.run_edit(ASK, SCOPE)
    for when in ("before", "after"):
        r = box.client.get(box.u("/draft/edit/%s/frames/s0002/%s.jpg" % (turn["id"], when)))
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 500, (when, r.text[:200])


def test_a_whole_chapter_scope_is_the_shots_of_that_chapter_and_nothing_else(box):
    box.model([ans([set_ring()])])
    r = box.post_edit(ASK, chapter="c01", mode="fast")
    assert r.status_code == 200, r.text
    box.wait_job(r.json()["job_id"])
    rec = box.changes("storyboard")[0]
    assert rec["scope"]["shots"] and "s0001" in rec["scope"]["shots"] and "s0010" not in rec["scope"]["shots"]


def test_an_overlay_dur_slightly_past_shot_end_is_cut_on_first_try(box):
    # s0002 spans word22 (8.10 s) to word48 (17.20 s); word28 starts at 10.20 s (7.00 s remaining)
    op = {"op": "add_overlay", "shot": "s0002", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 120, "ry": 120},
          "start": {"w": 28}, "dur": 7.03}
    box.model([ans([op], summary="Đã thêm vùng sáng đến hết cảnh.")])
    job, turn = box.run_edit("rọi sáng vùng giữa đến hết cảnh", SCOPE)
    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["repairs"] == 0
    assert box.shot("s0002")["overlays"][-1]["dur"] == pytest.approx(7.0, abs=1e-6)
    assert "cắt đến hết cảnh" in turn["batch_changes"][0]["what"]
