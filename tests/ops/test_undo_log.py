"""The change log and undo: order, limit, pruning at 200 (copies first), what a record holds, and undo of the newest batch, of an older
batch with nothing touched since, of an older batch with a conflict, of an undo, and after a save of the page in between."""
import copy
import json

import pytest
from ops_helpers import PD_ID, PID, paths, pk, pk_rev, picks, read_json, sb, sb_rev, shot, shots, snapshot

from bti.ops import log as oplog
from bti.picks import doc as pdoc
from bti.picks import service

B = "/api/projects/%s" % PID


def sbdoc(client):
    return read_json(client.pdir / "storyboard.json")


def changes(client, query=""):
    r = client.get(B + "/changes" + query)
    assert r.status_code == 200, r.text
    return r.json()["changes"]


def undo(client, kind, batch, *, rev=None, actor="human", **extra):
    body = {"base_rev": rev if rev is not None else (sb_rev(client) if kind == "sb" else pk_rev(client)), "actor": actor, **extra}
    return client.post(B + "/changes/%s/undo" % batch, json=body)


# ---------------------------------------------------------------- the log
def test_the_log_lists_the_newest_first_with_a_limit_and_a_filter(client):
    assert changes(client) == []
    for ops in ([{"op": "lock", "shot": "s0003"}], [{"op": "lock", "shot": "s0005"}], [{"op": "unlock", "shot": "s0003"}]):
        assert sb(client, ops).status_code == 200
    for beat in ("b0004", "b0005"):
        assert pk(client, [{"op": "skip_beat", "beat": beat}]).status_code == 200
    assert [r["batch"] for r in changes(client)] == ["batch_0005", "batch_0004", "batch_0003", "batch_0002", "batch_0001"]
    assert [r["batch"] for r in changes(client, "?doc=picks")] == ["batch_0005", "batch_0004"]
    assert [r["batch"] for r in changes(client, "?doc=storyboard")] == ["batch_0003", "batch_0002", "batch_0001"]
    assert [r["batch"] for r in changes(client, "?limit=2")] == ["batch_0005", "batch_0004"]
    assert [r["batch"] for r in changes(client, "?doc=storyboard&limit=1")] == ["batch_0003"]
    assert len(changes(client, "?limit=200")) == 5
    for bad in ("?doc=nope", "?limit=0", "?limit=201", "?limit=abc"):
        r = client.get(B + "/changes" + bad)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request" and r.json()["fix"], bad
    assert paths(client.get(B + "/changes?doc=nope")) == ["doc"] and paths(client.get(B + "/changes?limit=0")) == ["limit"]


def test_a_record_holds_what_was_sent_and_what_happened(client):
    ops = [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}, {"op": "split_shot", "shot": "s0002", "at": 12.0, "ref": "t"}]
    before_doc, rev_before = sbdoc(client), sb_rev(client)
    r = sb(client, ops, actor="agent:gemini-3.8-flash@high", note="Zoom slower, then cut the second shot.", scope={"shots": ["s0002", "s0004"]})
    assert r.status_code == 200, r.text
    rec, = changes(client)
    assert rec["batch"] == r.json()["batch"] == "batch_0001" and rec["doc"] == "storyboard"
    assert rec["actor"] == "agent:gemini-3.8-flash@high" and rec["note"] == "Zoom slower, then cut the second shot." and rec["time"]
    assert rec["ops"] == ops and rec["applied"] == 2 and rec["changes"] == r.json()["changes"] and rec["created"] == r.json()["created"]
    assert rec["rev_before"] == rev_before and rec["rev_after"] == r.json()["rev"] == sb_rev(client)
    assert rec["touched"] == ["shot:s0002", "shot:s0004", "shot:s0011"] and rec["undo_of"] is None and rec["scope"] == {"shots": ["s0002", "s0004"]}
    assert rec["copies"] is True and rec["undone_by"] is None and "before" not in rec and "after" not in rec
    folder = client.pdir / "changes"
    assert sorted(p.name for p in folder.iterdir()) == ["batch_0001.after.json", "batch_0001.before.json", "batch_0001.json"]
    assert read_json(folder / "batch_0001.before.json") == before_doc and read_json(folder / "batch_0001.after.json") == sbdoc(client)
    pr = pk(client, [{"op": "skip_beat", "beat": "b0004"}], actor="human")
    prec = changes(client, "?doc=picks")[0]
    assert prec["doc"] == "picks" and prec["touched"] == ["beat:b0004"] and prec["rev_after"] == pr.json()["rev"] and prec["actor"] == "human"


def test_the_log_sits_next_to_history_and_history_is_still_pruned_by_the_page(client):
    for i in range(3):
        assert sb(client, [{"op": "lock" if i % 2 == 0 else "unlock", "shot": "s0003"}]).status_code == 200
    assert (client.pdir / "history").is_dir() and (client.pdir / "changes").is_dir()
    assert len(list((client.pdir / "history").glob("*.json"))) == 3                                  # the page's own copies, one per write
    assert not list((client.pdir / "history").glob("batch_*"))


# ---------------------------------------------------------------- undo: the newest batch
def test_undo_the_newest_batch(client):
    orig = sbdoc(client)
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}]).json()["batch"]
    assert sbdoc(client) != orig
    r = undo(client, "sb", b1, actor="human", note="I changed my mind")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["batch"] == "batch_0002" and j["undo_of"] == b1 and j["applied"] == 1 and j["dry_run"] is False and j["rev"] == sb_rev(client)
    assert j["changes"] == [{"target": {"shot": "s0003"}, "time": "0:17", "what": "Cảnh 3: trở lại như trước khi sửa"}]
    assert sbdoc(client) == orig
    rec = changes(client)[0]
    assert rec["batch"] == "batch_0002" and rec["undo_of"] == b1 and rec["ops"] == [{"op": "undo", "batch": b1}] and rec["note"] == "I changed my mind"
    assert rec["actor"] == "human" and rec["touched"] == ["shot:s0003"] and rec["doc"] == "storyboard"
    assert changes(client)[1]["undone_by"] == "batch_0002"


@pytest.mark.parametrize("op", [
    {"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "slots": {"image": {"asset": "C"}}},
                                                                                  {"technique": "STATIC-01", "start": {"w": 154}, "slots": {"image": {"asset": "B"}}}]},
    {"op": "merge_shots", "shots": ["s0002", "s0003", "s0004"]},
    {"op": "split_shot", "shot": "s0004", "at": 26.0},
    {"op": "move_boundary", "shot": "s0003", "to": 13.0},
    {"op": "remove_overlay", "shot": "s0002", "overlay": "o2"},
    {"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 100, "ry": 100}},
    {"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "C"},
], ids=lambda o: o["op"])
def test_undo_puts_every_kind_of_change_back_exactly(client, op):
    """Shots a batch removed come back in their place, shots it added go, and the file is as it was."""
    orig = sbdoc(client)
    b = sb(client, [op]).json()["batch"]
    assert sbdoc(client)["shots"] != orig["shots"]
    assert undo(client, "sb", b).status_code == 200
    assert sbdoc(client) == orig and [s["id"] for s in shots(client)] == [s["id"] for s in orig["shots"]]


def test_undo_restores_removed_neighbours_in_their_order_whatever_the_order_of_the_set(client):
    orig = sbdoc(client)
    b = sb(client, [{"op": "replace_range", "from_shot": "s0002", "to_shot": "s0005",
                     "shots": [{"technique": "STATIC-01", "slots": {"image": {"asset": "A"}}}]}]).json()["batch"]
    assert [s["id"] for s in shots(client)][:3] == ["s0001", "s0011", "s0006"]
    assert undo(client, "sb", b).status_code == 200 and sbdoc(client) == orig


# ---------------------------------------------------------------- undo: an older batch
def test_undo_an_older_batch_when_nothing_it_touched_changed_since(client):
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}]).json()["batch"]
    sb(client, [{"op": "set_technique", "shot": "s0007", "technique": "CAM-01"}])
    sb(client, [{"op": "set_params", "shot": "s0004", "params": {"shadow": False}}])
    r = undo(client, "sb", b1)
    assert r.status_code == 200, r.text
    assert shot(client, "s0003")["locked"] is False                                                  # put back
    assert shot(client, "s0007")["technique"] == "CAM-01" and shot(client, "s0004")["params"]["shadow"] is False      # the later batches stay
    assert r.json()["batch"] == "batch_0004"


def test_an_older_batch_with_a_conflict_names_what_changed_and_the_batches_that_did_it(client):
    b1 = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}]).json()["batch"]
    b2 = sb(client, [{"op": "set_params", "shot": "s0004", "params": {"shadow": False}}, {"op": "lock", "shot": "s0003"}]).json()["batch"]
    before = snapshot(client.pdir)
    r = undo(client, "sb", b1)
    j = r.json()
    assert r.status_code == 409 and j["code"] == "undo_conflict" and j["retry"] == "after_fix" and j["fix"], r.text
    assert j["conflicts"] == [{"thing": {"shot": "s0004"}, "key": "shot:s0004", "batches": [b2]}]
    assert "s0004" in j["detail"] and b1 in j["detail"]
    assert snapshot(client.pdir) == before
    # newest first is the way out
    assert undo(client, "sb", b2).status_code == 200
    assert undo(client, "sb", b1).status_code == 200
    assert shot(client, "s0004")["technique"] == "CAM-01" and shot(client, "s0003")["locked"] is False


def test_a_conflict_on_one_shot_of_several_refuses_the_whole_undo(client):
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}, {"op": "lock", "shot": "s0005"}]).json()["batch"]
    sb(client, [{"op": "unlock", "shot": "s0005"}])
    before = snapshot(client.pdir)
    r = undo(client, "sb", b1)
    assert r.status_code == 409 and [c["key"] for c in r.json()["conflicts"]] == ["shot:s0005"]
    assert snapshot(client.pdir) == before and shot(client, "s0003")["locked"] is True


def test_undo_of_an_undo(client):
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}]).json()["batch"]
    after_b1 = sbdoc(client)
    u = undo(client, "sb", b1).json()["batch"]
    assert shot(client, "s0003")["locked"] is False
    uu = undo(client, "sb", u)
    assert uu.status_code == 200, uu.text
    assert uu.json()["undo_of"] == u and uu.json()["batch"] == "batch_0003"
    assert sbdoc(client) == after_b1 and shot(client, "s0003")["locked"] is True
    again = undo(client, "sb", b1)                                                                   # b1 was undone and then redone: undoing it again works
    assert again.status_code == 200 and shot(client, "s0003")["locked"] is False


def test_a_batch_that_was_undone_cannot_be_undone_again(client):
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}]).json()["batch"]
    undo(client, "sb", b1)
    r = undo(client, "sb", b1)
    assert r.status_code == 409 and r.json()["code"] == "undo_conflict" and r.json()["conflicts"][0]["batches"] == ["batch_0002"]


# ---------------------------------------------------------------- undo and the page
def put_page(client, edit):
    page = client.get(B).json()
    doc = copy.deepcopy(page["storyboard"])
    edit(doc)
    r = client.put(B + "/storyboard", json={"storyboard": doc, "base_rev": page["rev"]})
    assert r.status_code == 200, r.text
    return r


def test_undo_after_a_save_of_the_page_in_between_keeps_the_page_edit(client):
    b1 = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}]).json()["batch"]
    put_page(client, lambda d: d["shots"][4].__setitem__("note", "written by the page"))               # s0005: not touched by the batch; not logged
    assert len(changes(client)) == 1
    r = undo(client, "sb", b1)
    assert r.status_code == 200, r.text
    assert shot(client, "s0004")["technique"] == "CAM-01" and shot(client, "s0005")["note"] == "written by the page"


def test_undo_after_the_page_changed_what_the_batch_touched_is_a_conflict_with_no_batch_named(client):
    b1 = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}]).json()["batch"]
    put_page(client, lambda d: d["shots"][3].__setitem__("note", "the page edited this shot too"))
    before = snapshot(client.pdir)
    r = undo(client, "sb", b1)
    assert r.status_code == 409 and r.json()["conflicts"] == [{"thing": {"shot": "s0004"}, "key": "shot:s0004", "batches": []}]
    assert snapshot(client.pdir) == before


def test_undo_with_a_stale_revision_or_an_unknown_batch_or_a_bad_body(client):
    b1 = sb(client, [{"op": "lock", "shot": "s0003"}]).json()["batch"]
    old = sb_rev(client)
    sb(client, [{"op": "lock", "shot": "s0005"}])
    r = undo(client, "sb", b1, rev=old)
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == sb_rev(client)
    for batch in ("batch_9999", "nope", "batch_1"):
        r = undo(client, "sb", batch)
        assert r.status_code == 404 and r.json()["code"] == "batch_not_found" and r.json()["retry"] == "no" and r.json()["fix"], batch
    for body in ({}, {"base_rev": sb_rev(client)}, {"actor": "human"}, {"base_rev": "x", "actor": "robot"}, {"base_rev": "x", "actor": "human", "x": 1}, []):
        r = client.post(B + "/changes/%s/undo" % b1, json=body)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request", body
    assert client.post(B + "/changes/%s/undo" % b1, json={"base_rev": "x", "actor": "human", "note": 5}).json()["fields"][0]["path"] == "note"


# ---------------------------------------------------------------- undo: the picks
def test_undo_a_picks_batch_including_an_import(client):
    orig = picks(client)
    b = pk(client, [{"op": "import", "source": "commons", "source_id": PD_ID, "ref": "found", "as_main": True},
                    {"op": "set_picks", "beat": "b0004", "items": [{"asset": "$found"}]},
                    {"op": "set_region", "asset": "A", "region": "MIRROR", "x": 5, "y": 5}]).json()
    assert picks(client) != orig and b["batch"] == "batch_0001"
    key = b["created"]["refs"]["found"]
    r = undo(client, "pk", b["batch"])
    assert r.status_code == 200, r.text
    assert picks(client) == orig and key not in picks(client)["assets"]
    whats = [c["what"] for c in r.json()["changes"]]
    assert any(w.startswith("Đã bỏ hình ") and w.endswith(" khỏi dự án (do lô được hoàn tác nhập)") for w in whats), whats
    assert "Đoạn 4: trở lại như trước khi sửa" in whats and any(w.startswith("Tranh chính: trở lại") for w in whats)
    assert any(w.startswith("Vùng của hình “Test portrait”: trở lại") for w in whats), whats
    assert undo(client, "pk", r.json()["batch"]).status_code == 200                                 # and the undo can be undone: the picture is back
    assert key in picks(client)["assets"] and picks(client)["main_asset"] == key


def test_undo_gives_back_an_approval_when_the_content_is_exactly_what_was_approved(client):
    service.approve(client.pdir, pk_rev(client))
    assert client.get(B + "/picks").json()["approved"] is True
    b = pk(client, [{"op": "skip_beat", "beat": "b0004"}]).json()["batch"]
    assert client.get(B + "/picks").json()["approved"] is False
    assert undo(client, "pk", b).status_code == 200
    p = client.get(B + "/picks").json()
    assert p["approved"] is True and p["approval_reason"] is None


def put_picks_page(client, edit):
    page = client.get(B + "/picks").json()
    doc = copy.deepcopy(page["picks"])
    edit(doc)
    r = client.put(B + "/picks", json={"picks": doc, "base_rev": page["rev"]})
    assert r.status_code == 200, r.text


def test_a_picks_conflict_after_a_page_save(client):
    b = pk(client, [{"op": "skip_beat", "beat": "b0004"}]).json()["batch"]
    put_picks_page(client, lambda d: d["beats"].__setitem__(
        "b0004", {"items": [{"asset": "A", "region": None, "role": "detail", "note": ""}], "status": "picked", "note": "page"}))
    r = undo(client, "pk", b)
    assert r.status_code == 409 and r.json()["conflicts"] == [{"thing": {"beat": "b0004"}, "key": "beat:b0004", "batches": []}]


def test_a_page_save_of_something_else_does_not_stop_a_picks_undo(client):
    other = pk(client, [{"op": "skip_beat", "beat": "b0005"}]).json()["batch"]
    put_picks_page(client, lambda d: d.__setitem__("main_asset", "B"))                                # not what the batch touched
    assert undo(client, "pk", other).status_code == 200
    assert picks(client)["main_asset"] == "B" and "b0005" not in picks(client)["beats"]


def test_undo_of_a_picks_conflict_with_a_later_batch(client):
    b1 = pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}]}]).json()["batch"]
    b2 = pk(client, [{"op": "add_pick", "beat": "b0004", "asset": "C"}]).json()["batch"]
    r = undo(client, "pk", b1)
    assert r.status_code == 409 and r.json()["conflicts"] == [{"thing": {"beat": "b0004"}, "key": "beat:b0004", "batches": [b2]}]
    assert undo(client, "pk", b2).status_code == 200 and undo(client, "pk", b1).status_code == 200
    assert "b0004" not in picks(client)["beats"]


# ---------------------------------------------------------------- pruning (the logic, with a fast writer: durability is not what is tested)
@pytest.fixture
def fast_log(monkeypatch):
    def write(path, data, levels=1):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(oplog.sstore, "write_json_atomic", write)


def record(doc="picks"):
    return {"doc": doc, "time": "t", "actor": "human", "note": "", "ops": [], "applied": 1, "changes": [], "created": {}, "rev_before": "a",
            "rev_after": "b", "touched": [], "undo_of": None, "scope": None}


def test_the_log_keeps_the_newest_200_records_and_the_copies_of_the_newest_50(tmp_path, fast_log):
    log = oplog.ChangeLog(tmp_path)
    for i in range(205):
        assert log.write(record(), {"n": i}, {"n": i + 1}) == "batch_%04d" % (i + 1)
    assert log.numbers() == list(range(6, 206))                                                       # the oldest five records are gone
    recs = log.records("picks")
    assert len(recs) == 200 and recs[0]["batch"] == "batch_0006" and recs[-1]["batch"] == "batch_0205"
    with_copies = [r["batch"] for r in recs if r["copies"]]
    assert with_copies == ["batch_%04d" % n for n in range(156, 206)]                                # 50 copies, the newest
    assert sorted(p.name for p in (tmp_path / "changes").glob("*.before.json")) == ["%s.before.json" % b for b in with_copies]
    assert log.copies("batch_0205") == ({"n": 204}, {"n": 205}) and log.copies("batch_0100") is None and log.get("batch_0005") is None


def test_each_document_has_its_own_200(tmp_path, fast_log):
    log = oplog.ChangeLog(tmp_path)
    for i in range(3):
        log.write(record("storyboard"), {}, {})
    for i in range(203):
        log.write(record("picks"), {}, {})
    assert len(log.records("storyboard")) == 3 and len(log.records("picks")) == 200
    assert [r["batch"] for r in log.list("storyboard", 10)] == ["batch_0003", "batch_0002", "batch_0001"]
    assert [r["batch"] for r in log.list(None, 2)] == ["batch_0206", "batch_0205"]


def test_a_copy_without_a_record_is_removed_by_the_next_prune(tmp_path, fast_log):
    log = oplog.ChangeLog(tmp_path)
    log.write(record(), {}, {})
    (tmp_path / "changes" / "batch_0077.before.json").write_text("{}", encoding="utf-8")            # a crash between the copy and the record
    log.write(record(), {}, {})
    assert not (tmp_path / "changes" / "batch_0077.before.json").exists()


def test_a_record_whose_copies_were_pruned_is_listed_but_cannot_be_undone(client, fast_log):
    log = oplog.ChangeLog(client.pdir)
    for i in range(55):
        log.write({**record(), "rev_before": "x", "rev_after": "y"}, {}, {})
    listed = changes(client, "?doc=picks&limit=200")
    assert len(listed) == 55 and [r["copies"] for r in listed][:50] == [True] * 50 and [r["copies"] for r in listed][50:] == [False] * 5
    r = undo(client, "pk", "batch_0001")
    assert r.status_code == 409 and r.json()["code"] == "undo_unavailable" and r.json()["retry"] == "no" and r.json()["fix"]
    assert pdoc.doc_problem(picks(client)) is None


def test_the_ids_never_go_backwards_after_pruning(tmp_path, fast_log):
    log = oplog.ChangeLog(tmp_path)
    for i in range(202):
        log.write(record(), {}, {})
    assert log.write(record(), {}, {}) == "batch_0203"
