"""Batches as a whole: the envelope, all or nothing, the dry run, revisions and races, the lock, the validation, the approvals, the
document a batch leaves (history/ and the approvals record)."""
import copy
import json
import threading

import pytest
from fastapi.testclient import TestClient
from ops_helpers import PID, paths, pk, pk_rev, read_json, sb, sb_rev, shot, shots, snapshot

from bti.ops import registry

LOCK = {"op": "lock", "shot": "s0003"}
B = "/api/projects/%s" % PID


# ---------------------------------------------------------------- the envelope
@pytest.mark.parametrize("body,where", [
    ({"actor": "human", "ops": [LOCK]}, ["base_rev"]),
    ({"base_rev": "", "actor": "human", "ops": [LOCK]}, ["base_rev"]),
    ({"base_rev": 5, "actor": "human", "ops": [LOCK]}, ["base_rev"]),
    ({"base_rev": "x", "ops": [LOCK]}, ["actor"]),
    ({"base_rev": "x", "actor": "robot", "ops": [LOCK]}, ["actor"]),
    ({"base_rev": "x", "actor": "agent:", "ops": [LOCK]}, ["actor"]),
    ({"base_rev": "x", "actor": "cli:", "ops": [LOCK]}, ["actor"]),
    ({"base_rev": "x", "actor": "agent:a b", "ops": [LOCK]}, ["actor"]),
    ({"base_rev": "x", "actor": "human"}, ["ops"]),
    ({"base_rev": "x", "actor": "human", "ops": []}, ["ops"]),
    ({"base_rev": "x", "actor": "human", "ops": "lock"}, ["ops"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK] * 201}, ["ops"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "dry_run": "yes"}, ["dry_run"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": {}}, ["scope"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": {"shots": []}}, ["scope.shots"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": {"shots": [3]}}, ["scope.shots"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": {"stills": ["s1"]}}, ["scope"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": {"shots": ["s0001"], "beats": ["b0001"]}}, ["scope"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "scope": "all"}, ["scope"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "note": 5}, ["note"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "note": "n" * 2001}, ["note"]),
    ({"base_rev": "x", "actor": "human", "ops": [LOCK], "extra": 1}, ["extra"]),
    ({}, ["base_rev", "actor", "ops"]),
])
def test_the_envelope_is_checked(client, body, where):
    for url in (client.sb, client.pk):
        before = snapshot(client.pdir)
        r = client.post(url, json=body)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request", r.text
        assert paths(r) == where and r.json()["fix"] and r.json()["retry"] == "after_fix"
        assert snapshot(client.pdir) == before


def test_a_character_that_cannot_be_stored_is_refused(client):
    raw = b'{"base_rev": "x", "actor": "human", "ops": [{"op": "lock", "shot": "s0003"}], "note": "a\\ud800b"}'
    before = snapshot(client.pdir)
    for url in (client.sb, client.pk):
        r = client.post(url, content=raw, headers={"content-type": "application/json"})
        assert r.status_code == 422 and r.json()["code"] == "invalid_request" and paths(r) == [""], r.text
    assert snapshot(client.pdir) == before


def test_the_body_must_be_json_and_an_object(client):
    for url in (client.sb, client.pk):
        for r in (client.post(url, json=[1, 2]), client.post(url, content=b"{nope", headers={"content-type": "application/json"}),
                  client.post(url, content=b"", headers={"content-type": "application/json"})):
            assert r.status_code == 422 and r.json()["code"] == "invalid_request" and r.json()["fix"], r.text


def test_the_actor_forms(client):
    for actor in ("human", "agent:gemini-3.8-flash@high", "agent:claude:opus-5.5@high", "cli:bti"):
        assert sb(client, [{"op": "unlock", "shot": "s0003"}], actor=actor).status_code == 200, actor
    r = sb(client, [LOCK], actor="somebody")
    assert r.json()["fields"][0]["allowed"] == ["human", "agent:<model id>", "cli:<name>"]


def test_an_unknown_project_and_a_project_without_a_storyboard(client):
    r = client.post("/api/projects/nope/storyboard/ops", json={"base_rev": "x", "actor": "human", "ops": [LOCK]})
    assert r.status_code == 404 and r.json()["code"] == "project_not_found" and r.json()["fix"] and r.json()["retry"] == "no"
    (client.root / "nosb").mkdir()
    (client.root / "nosb" / "project.json").write_text("{}", encoding="utf-8")
    r = client.post("/api/projects/nosb/storyboard/ops", json={"base_rev": "x", "actor": "human", "ops": [LOCK]})
    assert r.status_code == 404 and r.json()["code"] == "storyboard_not_found" and r.json()["fix"]
    assert client.get("/api/projects/nope/changes").json()["code"] == "project_not_found"


def test_an_unknown_operation_lists_the_names(client):
    r = sb(client, [{"op": "teleport", "shot": "s0003"}])
    assert r.status_code == 422 and r.json()["code"] == "unknown_op" and paths(r) == ["ops[0].op"] and r.json()["op_index"] == 0
    assert r.json()["fields"][0]["allowed"] == registry.names("storyboard")
    r = sb(client, [LOCK, {"op": "set_main", "asset": "A"}])                                      # a picks operation on the storyboard
    assert r.json()["code"] == "unknown_op" and paths(r) == ["ops[1].op"] and r.json()["op_index"] == 1
    r = pk(client, [{"op": "lock", "shot": "s0003"}])
    assert r.json()["code"] == "unknown_op" and r.json()["fields"][0]["allowed"] == registry.names("picks")
    assert paths(sb(client, [{"shot": "s0003"}])) == ["ops[0].op"] and paths(sb(client, ["lock"])) == ["ops[0]"]


def test_every_wrong_field_of_every_operation_is_listed_at_once(client):
    r = sb(client, [{"op": "lock", "shot": 5}, {"op": "split_shot", "shot": "s0004"}, {"op": "lock", "shot": "s0003", "x": 1}])
    assert r.json()["code"] == "invalid_field" and paths(r) == ["ops[0].shot", "ops[1].at", "ops[2].x"] and r.json()["op_index"] == 0
    assert r.json()["fields"][2]["allowed"] == ["op", "overlay", "shot"]


def test_two_hundred_operations_in_one_batch(client):
    ops = [{"op": "set_params", "shot": "s0004", "params": {"shadow": i % 2 == 0}} for i in range(200)]
    r = sb(client, ops)
    assert r.status_code == 200, r.text
    assert r.json()["applied"] == 200 and len(r.json()["changes"]) == 200 and shot(client, "s0004")["params"]["shadow"] is False


# ---------------------------------------------------------------- all or nothing, dry run
def test_a_batch_whose_last_operation_is_wrong_leaves_the_files_byte_identical(client):
    ops = [LOCK, {"op": "set_params", "shot": "s0004", "params": {"shadow": False}}, {"op": "split_shot", "shot": "s0005", "at": 33.0},
           {"op": "set_technique", "shot": "s0007", "technique": "NOPE-99"}]
    before = snapshot(client.pdir)
    r = sb(client, ops)
    assert r.status_code == 422 and r.json()["code"] == "unknown_technique" and r.json()["op_index"] == 3
    assert snapshot(client.pdir) == before
    assert not (client.pdir / "changes").exists() and not (client.pdir / "history").exists()
    ops = [{"op": "set_main", "asset": "B"}, {"op": "skip_beat", "beat": "b0004"}, {"op": "add_pick", "beat": "b0003", "asset": "Z9"}]
    before = snapshot(client.pdir)
    r = pk(client, ops)
    assert r.status_code == 422 and r.json()["code"] == "unknown_asset" and r.json()["op_index"] == 2
    assert snapshot(client.pdir) == before


def test_a_later_operation_sees_what_the_earlier_ones_did(client):
    r = sb(client, [{"op": "lock", "shot": "s0003"}, {"op": "set_params", "shot": "s0003", "params": {"title": "NEW"}}])
    assert r.status_code == 409 and r.json()["code"] == "locked" and r.json()["op_index"] == 1
    r = sb(client, [{"op": "split_shot", "shot": "s0004", "at": 26.0}, {"op": "merge_shots", "shots": ["s0004", "s0011"]}])      # split, then merge it back
    assert r.status_code == 200, r.text
    assert [s["id"] for s in shots(client)].count("s0011") == 0 and len(shots(client)) == 10


def test_a_dry_run_writes_nothing_and_says_what_a_real_run_says(client):
    ops = [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"},
           {"op": "split_shot", "shot": "s0002", "at": 12.0, "ref": "t"},
           {"op": "set_params", "shot": "$t", "params": {"shadow": False}},
           {"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 100, "ry": 100}, "ref": "ring"},
           {"op": "set_overlay", "shot": "s0004", "overlay": "$ring", "dur": 2},
           {"op": "merge_shots", "shots": ["s0007", "s0008"]},
           {"op": "move_boundary", "shot": "s0003", "to": 13.0}]
    rev = sb_rev(client)
    before = snapshot(client.pdir)
    dry = sb(client, ops, dry_run=True)
    assert dry.status_code == 200, dry.text
    d = dry.json()
    assert d["dry_run"] is True and d["batch"] is None and d["rev"] == rev and d["applied"] == 7
    assert snapshot(client.pdir) == before and sb_rev(client) == rev                              # the files are byte-identical
    real = sb(client, ops)
    assert real.status_code == 200, real.text
    r = real.json()
    assert d["changes"] == r["changes"] and d["created"] == r["created"] and d["issues"] == r["issues"]
    assert r["dry_run"] is False and r["batch"] == "batch_0001" and r["rev"] != rev and len(r["changes"]) == 7
    assert r["created"]["shots"] == ["s0011"] and r["created"]["overlays"] == [{"shot": "s0004", "overlay": "o3"}]


def test_a_dry_run_of_picks_says_what_a_real_run_says(client):
    ops = [{"op": "set_main", "asset": "B"}, {"op": "set_picks", "beat": "b0004", "items": [{"asset": "A", "region": "HEAD"}], "reason": "x"},
           {"op": "set_region", "asset": "B", "region": "R", "x": 10, "y": 10}, {"op": "remove_pick", "beat": "b0001", "index": 0}]
    before = snapshot(client.pdir)
    dry = pk(client, ops, dry_run=True)
    assert dry.status_code == 200 and dry.json()["batch"] is None and snapshot(client.pdir) == before
    real = pk(client, ops)
    assert dry.json()["changes"] == real.json()["changes"] and dry.json()["issues"] == real.json()["issues"]
    assert real.json()["batch"] == "batch_0001"


def test_a_dry_run_refuses_what_a_real_run_refuses(client):
    before = snapshot(client.pdir)
    r = sb(client, [{"op": "set_slot", "shot": "s0002", "slot": "image", "asset": "C"}], dry_run=True)
    assert r.status_code == 422 and r.json()["code"] == "validation_failed"
    r = sb(client, [{"op": "lock", "shot": "s0006"}], dry_run=True)
    assert r.status_code == 409 and r.json()["code"] == "locked"
    assert snapshot(client.pdir) == before


def test_a_batch_that_changes_nothing_writes_and_logs_nothing(client):
    before = snapshot(client.pdir)
    rev = pk_rev(client)
    r = pk(client, [{"op": "set_main", "asset": "A"}])                                               # A is the main picture already
    assert r.status_code == 200 and r.json()["batch"] is None and r.json()["changes"] == [] and r.json()["rev"] == rev and r.json()["applied"] == 1
    rev = sb_rev(client)
    r = sb(client, [LOCK, {"op": "unlock", "shot": "s0003"}])                                        # locked and unlocked again: the document is as it was
    assert r.status_code == 200 and r.json()["batch"] is None and r.json()["rev"] == rev and r.json()["applied"] == 2
    assert [c["what"] for c in r.json()["changes"]] == ["Cảnh 3: đã khóa", "Cảnh 3: đã mở khóa"]    # each operation did change something when it ran
    assert snapshot(client.pdir) == before and client.get(B + "/changes").json()["changes"] == []


# ---------------------------------------------------------------- revisions and races
def test_a_batch_for_another_revision_is_refused_with_the_current_one(client):
    old = sb_rev(client)
    assert sb(client, [LOCK]).status_code == 200
    now = sb_rev(client)
    before = snapshot(client.pdir)
    r = sb(client, [{"op": "lock", "shot": "s0005"}], rev=old)
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == now
    assert r.json()["fix"] and r.json()["retry"] == "after_fix" and snapshot(client.pdir) == before
    assert sb(client, [LOCK], rev="deadbeef").status_code == 409
    old_pk = pk_rev(client)
    assert pk(client, [{"op": "skip_beat", "beat": "b0004"}]).status_code == 200
    r = pk(client, [{"op": "skip_beat", "beat": "b0005"}], rev=old_pk)
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == pk_rev(client)


@pytest.mark.parametrize("kind,first,second", [
    ("sb", {"op": "lock", "shot": "s0003"}, {"op": "lock", "shot": "s0005"}),
    ("pk", {"op": "skip_beat", "beat": "b0004"}, {"op": "skip_beat", "beat": "b0005"}),
])
def test_two_batches_racing_one_wins_the_other_gets_stale_revision(client, kind, first, second):
    url = client.sb if kind == "sb" else client.pk
    for _ in range(4):
        rev = sb_rev(client) if kind == "sb" else pk_rev(client)
        out = []
        barrier = threading.Barrier(2)

        def go(op):
            c = TestClient(client.app, raise_server_exceptions=False)
            barrier.wait()
            out.append(c.post(url, json={"base_rev": rev, "actor": "human", "ops": [op]}))
        ts = [threading.Thread(target=go, args=(o,)) for o in (first, second)]
        [t.start() for t in ts]
        [t.join(60) for t in ts]
        assert sorted(r.status_code for r in out) == [200, 409], [r.text for r in out]
        loser = next(r for r in out if r.status_code == 409)
        assert loser.json()["code"] == "stale_revision"
        # undo the winner so that the next round starts from a fresh state with both operations possible again
        won = next(r for r in out if r.status_code == 200).json()["batch"]
        newest = sb_rev(client) if kind == "sb" else pk_rev(client)
        assert client.post(B + "/changes/%s/undo" % won, json={"base_rev": newest, "actor": "human"}).status_code == 200
    assert len(client.get(B + "/changes").json()["changes"]) == 8                                   # four winners and four undos, nothing else


def test_a_batch_takes_the_lock_of_the_page_saves(client):
    from bti.editor.common import save_lock
    from bti.picks.doc import picks_lock
    for kind, lock in (("sb", save_lock(client.pdir)), ("pk", picks_lock(client.pdir))):
        rev = sb_rev(client) if kind == "sb" else pk_rev(client)
        url = client.sb if kind == "sb" else client.pk
        op = {"op": "lock", "shot": "s0003"} if kind == "sb" else {"op": "skip_beat", "beat": "b0004"}
        box = {}

        def go():
            box["r"] = TestClient(client.app).post(url, json={"base_rev": rev, "actor": "human", "ops": [op]})
        before = snapshot(client.pdir)
        with lock:
            t = threading.Thread(target=go)
            t.start()
            t.join(0.7)
            assert t.is_alive(), "the batch did not wait for the lock a page save takes"
            assert snapshot(client.pdir) == before
        t.join(30)
        assert box["r"].status_code == 200, box["r"].text


def test_a_stale_page_save_is_refused_after_a_batch(client):
    page = client.get(B).json()
    assert sb(client, [LOCK]).status_code == 200
    r = client.put(B + "/storyboard", json={"storyboard": page["storyboard"], "base_rev": page["rev"]})
    assert r.status_code == 409 and shot(client, "s0003")["locked"] is True


# ---------------------------------------------------------------- validation
def test_validation_refuses_a_batch_that_would_make_the_storyboard_invalid(client):
    before = snapshot(client.pdir)
    r = sb(client, [{"op": "lock", "shot": "s0003"}, {"op": "set_slot", "shot": "s0002", "slot": "image", "asset": "C"}])     # its overlays aim at CENTRE
    j = r.json()
    assert r.status_code == 422 and j["code"] == "validation_failed", r.text
    assert {i["code"] for i in j["issues"]} == {"region_undefined"} and all(i["op_index"] == 1 for i in j["issues"])
    assert j["op_index"] == 1 and j["fields"][0]["path"] == "ops[1]" and "CENTRE" in j["fields"][0]["problem"]
    assert j["fix"] and j["retry"] == "after_fix"
    assert snapshot(client.pdir) == before
    ok = sb(client, [{"op": "set_slot", "shot": "s0002", "slot": "image", "asset": "B"}])                                      # B has a CENTRE too
    assert ok.status_code == 200, ok.text


def test_a_problem_that_was_already_there_does_not_block_a_batch(client):
    d = read_json(client.pdir / "storyboard.json")
    d["assets"]["D"]["file"] = "media/gone.png"                                                      # an error that is already in the document
    (client.pdir / "storyboard.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    state = client.get(B).json()
    assert [i["code"] for i in state["issues"] if i["level"] == "error"] == ["asset_file_missing"]
    r = sb(client, [LOCK])
    assert r.status_code == 200, r.text
    assert [i["code"] for i in r.json()["issues"] if i["level"] == "error"] == ["asset_file_missing"]       # it stays in the issues
    assert shot(client, "s0003")["locked"] is True
    r = sb(client, [{"op": "set_slot", "shot": "s0002", "slot": "image", "asset": "C"}])              # a NEW error still refuses it, and only the new one is listed
    assert r.status_code == 422 and {i["code"] for i in r.json()["issues"]} == {"region_undefined"}


def test_a_batch_with_a_new_error_next_to_an_old_one_of_the_same_code_in_another_place_is_refused(client):
    d = read_json(client.pdir / "storyboard.json")
    d["shots"][1]["overlays"][0]["params"]["at"] = "GONE"                                            # region_undefined on s0002/o1 already
    (client.pdir / "storyboard.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    assert sb(client, [LOCK]).status_code == 200                                                     # the old one does not block
    r = sb(client, [{"op": "set_slot", "shot": "s0002", "slot": "image", "asset": "D"}])             # o2 (at CENTRE) now has a region problem of its own
    assert r.status_code == 422 and r.json()["code"] == "validation_failed", r.text
    assert [i["path"] for i in r.json()["issues"]] == ["shots[1].overlays[1].params.at"]             # only the new one; the old one (o1) is not listed


def test_picks_validation_refuses_only_new_errors(client):
    d = read_json(client.pdir / "picks.json")
    d["assets"]["B"]["file"] = "media/gone.png"                                                      # an existing error: asset_file_missing
    (client.pdir / "picks.json").write_text(json.dumps(d), encoding="utf-8")
    r = pk(client, [{"op": "skip_beat", "beat": "b0004"}])
    assert r.status_code == 200 and "asset_file_missing" in [i["code"] for i in r.json()["issues"]]


# ---------------------------------------------------------------- the document a batch leaves
def test_a_batch_saves_the_storyboard_like_the_page_does(client):
    from bti.editor.common import compute_rev, storyboard_approval
    d = read_json(client.pdir / "storyboard.json")
    d["approvals"] = {"storyboard": {"rev": compute_rev(d), "approved_at": "2026-11-18T09:00:00"}}
    (client.pdir / "storyboard.json").write_text(json.dumps(d, indent=1), encoding="utf-8")
    assert storyboard_approval(read_json(client.pdir / "storyboard.json")) == "fresh"
    assert not (client.pdir / "history").exists()
    r = sb(client, [LOCK])
    assert r.status_code == 200
    after = read_json(client.pdir / "storyboard.json")
    assert after["approvals"] == d["approvals"]                                                      # the record is kept as the page's PUT keeps it
    assert storyboard_approval(after) == "stale"                                                     # ... and it no longer stands
    assert r.json()["rev"] == compute_rev(after) == sb_rev(client)
    copies = list((client.pdir / "history").glob("*.json"))                                          # the previous file went to history/
    assert len(copies) == 1 and read_json(copies[0]) == d
    assert after["shots"][2]["locked"] is True and after["schema"] == "bti.storyboard/1"


def test_the_restore_route_still_brings_back_a_copy_of_history(client):
    assert sb(client, [LOCK]).status_code == 200
    assert sb(client, [{"op": "unlock", "shot": "s0003"}]).status_code == 200
    (client.pdir / "storyboard.json").write_text("{broken", encoding="utf-8")
    r = client.post(B + "/storyboard/restore", json={})
    assert r.status_code == 200 and r.json()["restored_from"].endswith(".json"), r.text
    assert read_json(client.pdir / "storyboard.json")["shots"][2]["locked"] is True                  # the newest good copy: the file after the first batch


def test_the_response_revision_is_the_revision_the_page_reads(client):
    r = sb(client, [LOCK])
    assert r.json()["rev"] == sb_rev(client)
    r = pk(client, [{"op": "skip_beat", "beat": "b0004"}])
    assert r.json()["rev"] == pk_rev(client)
    assert copy.deepcopy(r.json()["created"]) == {"shots": [], "overlays": [], "assets": [], "refs": {}}


def test_a_damaged_file_of_the_project_is_a_typed_error(client):
    rev, prev = sb_rev(client), pk_rev(client)
    (client.pdir / "timing.json").unlink()                                                            # the engine cannot place anything in time
    r = sb(client, [LOCK], rev=rev)
    assert r.status_code == 409 and r.json()["code"] == "document_corrupt" and r.json()["fix"] and r.json()["retry"] == "after_fix", r.text
    assert r.json()["data_error"] == "timing"
    (client.pdir / "picks.json").write_text("{broken", encoding="utf-8")
    r = pk(client, [{"op": "skip_beat", "beat": "b0004"}], rev=prev)
    assert r.status_code == 409 and r.json()["code"] == "document_corrupt" and r.json()["fix"], r.text
