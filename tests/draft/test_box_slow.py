"""The slow path (an agent in a work folder) writes through the typed operations too (worker c2box): its compiled result becomes ONE batch of
`replace_range` operations (change log, actor, note, undo), after the three-way merge that keeps what the owner saved meanwhile.

`replace_ops` is tested on small documents; the rest runs through the routes on the synthetic project with the fake agy program."""
from __future__ import annotations

import copy
import json

import pytest

from bti.draft import boxops
from bti.draft.merge import locked_update
from bti.engine.timing import Timing
from bti.ops.timeline import Timeline
from test_edit_routes_e2e import Env, env, held, sb_proj, strip, why   # noqa: F401  (fixtures and helpers of the synthetic-project routes)
from test_agy import fake                                            # noqa: F401


# ----------------------------------------------------------------------------------------------------------- replace_ops, on small documents
def tl():
    words = [{"w": "w%d" % i, "s": float(i), "e": i + 0.5} for i in range(100)]
    return Timeline(Timing({"duration": 100.0, "words": words}))


def shot(sid, t, tech="CAM-01", **kw):
    s = {"id": sid, "start": {"t": float(t)}, "technique": tech, "intent": "explore", "slots": {"image": {"asset": "A"}}, "params": {},
         "overlays": [], "locked": False, "source": "import", "note": ""}
    s.update(kw)
    return s


def doc(*shots):
    return {"shots": list(shots), "end": {"t": 100.0}, "assets": {"A": {"regions": {}}}}


BASE = doc(shot("s1", 0), shot("s2", 10), shot("s3", 20), shot("s4", 30), shot("s5", 40))


def merged(**changes):
    d = copy.deepcopy(BASE)
    for sid, kw in changes.items():
        next(s for s in d["shots"] if s["id"] == sid).update(kw)
    return d


def test_identical_documents_need_no_operation():
    assert boxops.replace_ops(BASE, copy.deepcopy(BASE), tl()) == ([], [])


def test_one_changed_shot_is_one_replace_range_of_that_shot_and_keeps_the_others():
    ops, runs = boxops.replace_ops(BASE, merged(s3={"note": "slower"}), tl())
    assert len(ops) == 1 and ops[0]["op"] == "replace_range" and ops[0]["from_shot"] == ops[0]["to_shot"] == "s3"
    new = ops[0]["shots"]
    assert len(new) == 1 and "start" not in new[0] and new[0]["technique"] == "CAM-01" and new[0]["note"] == "slower"
    assert [s["id"] for s in runs[0][0]] == ["s3"]


def test_two_far_apart_changes_are_two_operations_and_two_neighbours_are_one():
    ops, _ = boxops.replace_ops(BASE, merged(s1={"note": "a"}, s4={"note": "b"}), tl())
    assert [(o["from_shot"], o["to_shot"]) for o in ops] == [("s1", "s1"), ("s4", "s4")]
    ops, _ = boxops.replace_ops(BASE, merged(s2={"note": "a"}, s3={"note": "b"}), tl())
    assert [(o["from_shot"], o["to_shot"]) for o in ops] == [("s2", "s3")] and len(ops[0]["shots"]) == 2
    assert ops[0]["shots"][1]["start"] == {"t": 20.0}


def test_a_removed_shot_makes_the_shot_before_longer_so_both_are_in_the_run():
    d = merged()
    d["shots"] = [s for s in d["shots"] if s["id"] != "s3"]
    ops, runs = boxops.replace_ops(BASE, d, tl())
    assert [(o["from_shot"], o["to_shot"]) for o in ops] == [("s2", "s3")]
    assert [s["id"] for s in runs[0][1]] == ["s2"] and len(ops[0]["shots"]) == 1


def test_an_added_shot_splits_the_shot_it_starts_in():
    d = merged()
    d["shots"].insert(3, shot("s9", 25, note="new"))
    ops, runs = boxops.replace_ops(BASE, d, tl())
    assert [(o["from_shot"], o["to_shot"]) for o in ops] == [("s3", "s3")]
    new = ops[0]["shots"]
    assert [n.get("start") for n in new] == [None, {"t": 25.0}] and new[1]["note"] == "new"


def test_overlays_params_slots_and_anchors_go_into_the_operation():
    ov = {"id": "o1", "technique": "HI-01", "intent": "isolate", "start": {"w": 21, "off": 0.0, "text": "w21"}, "dur": 4.0,
          "params": {"at": "MIRROR"}, "locked": False, "source": "import", "note": ""}
    ops, _ = boxops.replace_ops(BASE, merged(s3={"overlays": [ov], "params": {"camera": [{"at": {"rel": 0}, "cx": 1, "cy": 1, "zoom": 1}]}}), tl())
    spec = ops[0]["shots"][0]
    assert spec["overlays"] == [{"technique": "HI-01", "start": {"w": 21, "off": 0.0, "text": "w21"}, "dur": 4.0, "params": {"at": "MIRROR"},
                                 "intent": "isolate"}]
    assert spec["params"]["camera"][0]["zoom"] == 1 and spec["slots"] == {"image": {"asset": "A"}}


def test_a_result_that_does_not_cover_the_time_is_a_plan_error_not_a_guess():
    d = merged()
    d["shots"][2]["start"] = {"t": 22.0}                                        # s3 starts later: s2 is longer, s3 is shorter: both in one run
    ops, _ = boxops.replace_ops(BASE, d, tl())
    assert [(o["from_shot"], o["to_shot"]) for o in ops] == [("s2", "s3")]
    d2 = merged()
    d2["shots"].insert(1, shot("s8", 5))
    d2["shots"][0]["start"] = {"t": 3.0}                                       # the first shot no longer starts where the video starts
    with pytest.raises(boxops.DeepPlanError):
        boxops.replace_ops(BASE, d2, tl())


def test_new_regions_are_those_the_saved_storyboard_lacks():
    cur = {"assets": {"A": {"regions": {"MIRROR": {"x": 1, "y": 1}}}, "B": {"regions": {}}}}
    res = {"assets": {"A": {"regions": {"MIRROR": {"x": 1, "y": 1}, "RING": {"x": 5, "y": 6}}}, "B": {"regions": {}}, "C": {"regions": {"Z": {"x": 0, "y": 0}}}}}
    assert boxops.new_regions(cur, res) == {"A": {"RING": {"x": 5, "y": 6}}}


# ----------------------------------------------------------------------------------------------------------- through the routes
def owner_note(env, sid, note):
    """The owner saves a note on one shot (the page's own save path: under the storyboard lock, with the history copy)."""
    def make(cur):
        d = copy.deepcopy(cur)
        next(s for s in d["shots"] if s["id"] == sid)["note"] = note
        return d, None
    locked_update(env.pdir, make)


def before_apply(monkeypatch, fn):
    """`fn()` runs once, right before the slow path's result is put on the storyboard: the owner saves while the agent worked."""
    real = boxops.apply_deep
    done = []

    def wrapped(*a, **k):
        if not done:
            done.append(1)
            fn()
        return real(*a, **k)

    monkeypatch.setattr(boxops, "apply_deep", wrapped)


def test_an_owner_save_of_another_shot_while_the_agent_worked_stays_and_undo_leaves_it(env, fake, monkeypatch):
    ids = env.content_ids("c01")
    other = env.content_ids("c02")[0]
    env.deep_cfg(fake.dir, {ids[0]: {"note": "agent note"}})
    before_apply(monkeypatch, lambda: owner_note(env, other, "owner note elsewhere"))

    job, turn = env.run_edit("sửa", chapter="c01", mode="deep")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "applied" and turn["batch"]
    now = {s["id"]: s for s in env.saved()["shots"]}
    assert now[other]["note"] == "owner note elsewhere"
    assert [s["note"] for s in now.values() if s["note"] == "agent note"] == ["agent note"]
    assert len(turn["changes"]) == 1                                                          # the owner's save is not the turn's change
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    now = {s["id"]: s for s in env.saved()["shots"]}
    assert now[other]["note"] == "owner note elsewhere" and ids[0] in now and now[ids[0]]["note"] != "agent note"


def test_a_shot_both_sides_changed_needs_a_choice_and_nothing_is_written(env, fake, monkeypatch):
    ids = env.content_ids("c01")
    env.deep_cfg(fake.dir, {ids[0]: {"note": "agent note"}})
    before_apply(monkeypatch, lambda: owner_note(env, ids[0], "owner note"))

    job, turn = env.run_edit("sửa", chapter="c01", mode="deep")

    assert job["state"] == "done", why(job)
    assert turn["status"] == "needs_choice" and turn["conflicts"] and not turn.get("batch")
    assert {s["id"]: s for s in env.saved()["shots"]}[ids[0]]["note"] == "owner note"
    assert env.client.get(env.u("/changes?doc=storyboard")).json()["changes"] == []


def test_overwrite_after_a_conflict_is_one_batch_that_keeps_the_owners_other_changes(env, fake, monkeypatch):
    ids = env.content_ids("c01")
    other = env.content_ids("c02")[0]
    env.deep_cfg(fake.dir, {ids[0]: {"note": "agent note"}})
    before_apply(monkeypatch, lambda: owner_note(env, ids[0], "owner note"))
    _, turn = env.run_edit("sửa", chapter="c01", mode="deep")
    assert turn["status"] == "needs_choice"
    owner_note(env, other, "owner note on another shot, while the turn waited")

    r = env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "overwrite"})

    assert r.status_code == 200 and r.json()["status"] == "applied", r.text
    t = env.turn(turn["id"])
    assert t["status"] == "applied" and t["batch"] and t["has_undo"] is True
    now = {s["id"]: s for s in env.saved()["shots"]}
    assert any(s["note"] == "agent note" for s in now.values()) and now[other]["note"] == "owner note on another shot, while the turn waited"
    log = env.client.get(env.u("/changes?doc=storyboard")).json()["changes"]
    assert len(log) == 1 and [o["op"] for o in log[0]["ops"]] == ["replace_range"] and log[0]["batch"] == t["batch"]
    r = env.client.post(env.u("/draft/edit/%s/undo" % turn["id"]), json={})
    assert r.status_code == 200, r.text
    now = {s["id"]: s for s in env.saved()["shots"]}
    assert now[other]["note"] == "owner note on another shot, while the turn waited" and now[ids[0]]["note"] == "owner note"


def test_discard_after_a_conflict_changes_nothing(env, fake, monkeypatch):
    ids = env.content_ids("c01")
    env.deep_cfg(fake.dir, {ids[0]: {"note": "agent note"}})
    before_apply(monkeypatch, lambda: owner_note(env, ids[0], "owner note"))
    _, turn = env.run_edit("sửa", chapter="c01", mode="deep")
    rev = env.rev()
    r = env.client.post(env.u("/draft/edit/%s/resolve" % turn["id"]), json={"action": "discard"})
    assert r.status_code == 200 and env.turn(turn["id"])["status"] == "cancelled" and env.rev() == rev


def test_the_button_of_an_escalated_turn_starts_the_slow_path_with_the_same_request(env, fake):
    """`escalate` never starts the slow path by itself: the card offers it, the owner presses, and the page sends the same instruction and scope
    with mode deep. The slow path then states its limits."""
    ids = env.content_ids("c01")
    reason = "Chi tiết này chưa có vùng nào trên tranh, cần bước xem tranh kỹ hơn."
    boxops_answer = json.dumps({"status": "escalate", "summary": "", "reason": reason, "ops": []}, ensure_ascii=False)
    from bti.script.providers import mock
    mock.set_canned([boxops_answer])
    _, t1 = env.run_edit("zoom vào chiếc nhẫn", ids[:1], mode="auto")
    assert t1["status"] == "escalate" and t1["reason"] == reason and fake.calls() == []

    env.deep_cfg(fake.dir, {ids[0]: {"note": "close on the ring"}})
    job, t2 = env.run_edit(t1["instruction"], t1["scope"]["shots"], mode="deep")
    assert job["state"] == "done", why(job)
    assert t2["status"] == "applied" and t2["path"] == "deep" and t2["batch"] and t2["limits"]["minutes"] == 30 and len(fake.calls()) == 1


def test_a_slow_result_the_operations_refuse_fails_the_turn_with_a_sentence_and_writes_nothing(env, fake, monkeypatch):
    from bti.ops.errors import OpError
    ids = env.content_ids("c01")
    env.deep_cfg(fake.dir, {ids[0]: {"note": "x"}})
    rev = env.rev()

    def refuse(*a, **k):
        raise OpError("out_of_scope", "ops[0].from_shot: shot s9 is outside the scope of this batch")
    monkeypatch.setattr(boxops, "apply_deep", refuse)

    job, turn = env.run_edit("sửa", chapter="c01", mode="deep")

    assert job["state"] == "error" and turn["status"] == "failed" and turn["error"] == "out_of_scope"
    assert "chưa chọn" in turn["summary"] and env.rev() == rev
