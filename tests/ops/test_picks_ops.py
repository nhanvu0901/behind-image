"""The picks operations, one by one: the normal case, every way the fields can be wrong (with the exact `fields[].path`), the scope,
and the import (with the fakes of the media tests: no network)."""
import copy
import urllib.error

import pytest
from ops_helpers import PD_ID, PID, paths, pk, pk_rev, picks, read_json, snapshot
from picks_helpers import FakeNet

from bti.media import api as media_api
from bti.media.sources.commons import CommonsSource
from bti.picks import doc as pdoc

B = "/api/projects/%s/picks" % PID


def untouched(client, resp, before):
    assert resp.status_code >= 400
    assert snapshot(client.pdir) == before


def add_video(client):
    """An asset `V` of kind video (its file exists) in picks.json."""
    d = pdoc.load(client.pdir)
    (client.pdir / "media" / "v_clip.mp4").write_bytes(b"not a real video")
    d["assets"]["V"] = {"file": "media/v_clip.mp4", "kind": "video", "title": "Clip", "artist": "", "year": "", "width": 640, "height": 360,
                        "credit": {"flag": None}, "regions": {}, "duration": 5.0}
    pdoc.save(client.pdir, d)


# ---------------------------------------------------------------- set_main
def test_set_main(client):
    r = pk(client, [{"op": "set_main", "asset": "B"}])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["applied"] == 1 and j["batch"] == "batch_0001" and j["dry_run"] is False
    assert [i for i in j["issues"] if i["level"] == "error"] == [] and {i["code"] for i in j["issues"]} == {"beat_no_pick"}      # warnings stay
    assert j["changes"] == [{"target": {"asset": "B"}, "time": None, "what": "Tranh chính: đổi sang hình “Test landscape”"}]
    assert picks(client)["main_asset"] == "B" and j["rev"] == pk_rev(client)


@pytest.mark.parametrize("op,code,where,allowed", [
    ({"op": "set_main"}, "invalid_field", ["ops[0].asset"], None),
    ({"op": "set_main", "asset": 5}, "invalid_field", ["ops[0].asset"], None),
    ({"op": "set_main", "asset": "not a key"}, "invalid_field", ["ops[0].asset"], None),
    ({"op": "set_main", "asset": "Z9"}, "unknown_asset", ["ops[0].asset"], ["A", "B", "C", "D"]),
    ({"op": "set_main", "asset": "$nothing"}, "unknown_ref", ["ops[0].asset"], []),
    ({"op": "set_main", "asset": "A", "extra": 1}, "invalid_field", ["ops[0].extra"], None),
])
def test_set_main_wrong_fields(client, op, code, where, allowed):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where and r.json()["op_index"] == 0
    assert r.json()["fix"] and r.json()["retry"] == "after_fix"
    if allowed is not None:
        assert r.json()["fields"][0]["allowed"] == allowed
    untouched(client, r, before)


def test_set_main_refuses_a_video(client):
    add_video(client)
    r = pk(client, [{"op": "set_main", "asset": "V"}])
    assert r.status_code == 422 and r.json()["code"] == "video_not_main" and paths(r) == ["ops[0].asset"]


# ---------------------------------------------------------------- set_region / remove_region
def test_set_region_adds_and_replaces(client):
    r = pk(client, [{"op": "set_region", "asset": "A", "region": "MIRROR", "x": 700, "y": 420, "rx": 120, "ry": 100, "label": "Mirror"},
                    {"op": "set_region", "asset": "A", "region": "HEAD", "x": 610, "y": 390}])
    assert r.status_code == 200, r.text
    regs = picks(client)["assets"]["A"]["regions"]
    assert regs["MIRROR"] == {"x": 700, "y": 420, "rx": 120, "ry": 100, "label": "Mirror"}
    assert regs["HEAD"] == {"x": 610, "y": 390, "label": ""}                       # replaced: the old radii are gone
    assert [c["what"] for c in r.json()["changes"]] == ["Vùng MIRROR của hình “Test portrait”: đã đặt", "Vùng HEAD của hình “Test portrait”: đã đặt"]


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_region", "asset": "A", "region": "X"}, "invalid_field", ["ops[0].x", "ops[0].y"]),
    ({"op": "set_region", "asset": "A", "region": "X", "x": 5000, "y": 10}, "invalid_field", ["ops[0].x"]),
    ({"op": "set_region", "asset": "A", "region": "X", "x": 10, "y": -1}, "invalid_field", ["ops[0].y"]),
    ({"op": "set_region", "asset": "A", "region": "bad/name", "x": 10, "y": 10}, "invalid_field", ["ops[0].region"]),
    ({"op": "set_region", "asset": "A", "region": "X", "x": 10, "y": 10, "rx": 0}, "invalid_field", ["ops[0].rx"]),
    ({"op": "set_region", "asset": "A", "region": "X", "x": "10", "y": 10}, "invalid_field", ["ops[0].x"]),
    ({"op": "set_region", "asset": "A", "region": "X", "x": 10, "y": 10, "label": "x" * 81}, "invalid_field", ["ops[0].label"]),
    ({"op": "set_region", "asset": "Z9", "region": "X", "x": 10, "y": 10}, "unknown_asset", ["ops[0].asset"]),
])
def test_set_region_wrong_fields(client, op, code, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where
    untouched(client, r, before)


def test_remove_region(client):
    r = pk(client, [{"op": "remove_region", "asset": "A", "region": "HANDS"}])
    assert r.status_code == 200 and "HANDS" not in picks(client)["assets"]["A"]["regions"]
    assert r.json()["changes"][0]["what"] == "Vùng HANDS của hình “Test portrait”: đã bỏ"


def test_remove_region_wrong_fields(client):
    r = pk(client, [{"op": "remove_region", "asset": "A", "region": "NOPE"}])
    assert r.status_code == 422 and r.json()["code"] == "unknown_region" and paths(r) == ["ops[0].region"]
    assert r.json()["fields"][0]["allowed"] == ["HANDS", "HEAD"]
    assert pk(client, [{"op": "remove_region", "asset": "A"}]).json()["fields"][0]["path"] == "ops[0].region"


def test_remove_region_in_use_is_refused_by_the_validation_and_names_the_operation(client):
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_main", "asset": "B"}, {"op": "remove_region", "asset": "A", "region": "HEAD"}])      # b0001 shows A/HEAD
    j = r.json()
    assert r.status_code == 422 and j["code"] == "validation_failed", r.text
    assert j["issues"][0]["code"] == "unknown_region" and j["issues"][0]["beat"] == "b0001" and j["issues"][0]["op_index"] == 1
    assert j["op_index"] == 1 and j["fields"] == [{"path": "ops[1]", "problem": j["issues"][0]["message"]}]
    untouched(client, r, before)
    # the same batch with the line changed first is fine
    ok = pk(client, [{"op": "set_picks", "beat": "b0001", "items": [{"asset": "A"}]}, {"op": "remove_region", "asset": "A", "region": "HEAD"}])
    assert ok.status_code == 200, ok.text


# ---------------------------------------------------------------- set_picks
def test_set_picks(client):
    r = pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}, {"asset": "A", "region": "HEAD", "role": "context", "note": "n"}],
                     "reason": "Both show the room."}])
    assert r.status_code == 200, r.text
    b = picks(client)["beats"]["b0004"]
    assert b == {"items": [{"asset": "B", "region": None, "role": "detail", "note": ""},
                           {"asset": "A", "region": "HEAD", "role": "context", "note": "n"}], "status": "picked", "note": "Both show the room."}
    assert r.json()["changes"] == [{"target": {"beat": "b0004"}, "time": "0:42", "what": "Đoạn 4: thay 2 hình"}]


def test_set_picks_replaces_all_and_keeps_the_note_without_a_reason(client):
    pk(client, [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "C"}], "reason": "why"}])
    pk(client, [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "D"}]}])
    assert picks(client)["beats"]["b0003"]["items"] == [{"asset": "D", "region": None, "role": "detail", "note": ""}]
    assert picks(client)["beats"]["b0003"]["note"] == "why"


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_picks", "beat": "b0004"}, "invalid_field", ["ops[0].items"]),
    ({"op": "set_picks", "beat": "b0004", "items": []}, "invalid_field", ["ops[0].items"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}] * 31}, "invalid_field", ["ops[0].items"]),
    ({"op": "set_picks", "beat": "b9999", "items": [{"asset": "A"}]}, "unknown_beat", ["ops[0].beat"]),
    ({"op": "set_picks", "beat": "line 4", "items": [{"asset": "A"}]}, "invalid_field", ["ops[0].beat"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}, {"asset": "Z9"}]}, "unknown_asset", ["ops[0].items[1].asset"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A", "region": "NOPE"}]}, "unknown_region", ["ops[0].items[0].region"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A", "role": "star"}]}, "invalid_field", ["ops[0].items[0].role"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"region": "HEAD"}]}, "invalid_field", ["ops[0].items[0].asset"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A", "extra": 1}]}, "invalid_field", ["ops[0].items[0].extra"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "reason": "x" * 401}, "invalid_field", ["ops[0].reason"]),
])
def test_set_picks_wrong_fields(client, op, code, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where
    untouched(client, r, before)


def test_unknown_beat_lists_the_beats(client):
    r = pk(client, [{"op": "skip_beat", "beat": "b0077"}])
    assert r.json()["fields"][0]["allowed"] == ["b0001", "b0002", "b0003", "b0004", "b0005", "b0006"]
    assert r.json()["fix"]


# ---------------------------------------------------------------- add_pick / remove_pick / skip_beat
def test_add_pick_last_and_at_a_position(client):
    r = pk(client, [{"op": "add_pick", "beat": "b0003", "asset": "C"},
                    {"op": "add_pick", "beat": "b0003", "asset": "D", "position": 0, "role": "compare", "note": "side by side"}])
    assert r.status_code == 200, r.text
    items = picks(client)["beats"]["b0003"]["items"]
    assert [i["asset"] for i in items] == ["D", "B", "C"] and items[0]["role"] == "compare" and items[0]["note"] == "side by side"
    assert [c["what"] for c in r.json()["changes"]] == ["Đoạn 3: thêm hình “Test detail”", "Đoạn 3: thêm hình “Test other work”"]
    fresh = pk(client, [{"op": "add_pick", "beat": "b0005", "asset": "A"}])
    assert picks(client)["beats"]["b0005"]["status"] == "picked" and fresh.json()["changes"][0]["time"] == "0:59"


@pytest.mark.parametrize("op,code,where", [
    ({"op": "add_pick", "beat": "b0003"}, "invalid_field", ["ops[0].asset"]),
    ({"op": "add_pick", "beat": "b0003", "asset": "Z9"}, "unknown_asset", ["ops[0].asset"]),
    ({"op": "add_pick", "beat": "b0003", "asset": "A", "region": "NOPE"}, "unknown_region", ["ops[0].region"]),
    ({"op": "add_pick", "beat": "b0003", "asset": "A", "position": 5}, "invalid_field", ["ops[0].position"]),
    ({"op": "add_pick", "beat": "b0003", "asset": "A", "position": -1}, "invalid_field", ["ops[0].position"]),
    ({"op": "add_pick", "beat": "b0033", "asset": "A"}, "unknown_beat", ["ops[0].beat"]),
])
def test_add_pick_wrong_fields(client, op, code, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where
    untouched(client, r, before)


def test_add_pick_stops_at_thirty(client):
    items = [{"asset": "A"}] * 30
    assert pk(client, [{"op": "set_picks", "beat": "b0004", "items": items}]).status_code == 200
    r = pk(client, [{"op": "add_pick", "beat": "b0004", "asset": "B"}])
    assert r.status_code == 422 and paths(r) == ["ops[0].beat"]


def test_remove_pick(client):
    pk(client, [{"op": "add_pick", "beat": "b0003", "asset": "C"}])
    r = pk(client, [{"op": "remove_pick", "beat": "b0003", "index": 0}])
    assert r.status_code == 200, r.text
    assert [i["asset"] for i in picks(client)["beats"]["b0003"]["items"]] == ["C"]
    assert r.json()["changes"][0]["what"] == "Đoạn 3: bỏ hình “Test landscape”"
    last = pk(client, [{"op": "remove_pick", "beat": "b0003", "index": 0}])
    assert picks(client)["beats"]["b0003"]["items"] == [] and picks(client)["beats"]["b0003"]["status"] == "todo" and last.status_code == 200


@pytest.mark.parametrize("op,code,where", [
    ({"op": "remove_pick", "beat": "b0001"}, "invalid_field", ["ops[0].index"]),
    ({"op": "remove_pick", "beat": "b0001", "index": 1}, "invalid_field", ["ops[0].index"]),
    ({"op": "remove_pick", "beat": "b0001", "index": -1}, "invalid_field", ["ops[0].index"]),
    ({"op": "remove_pick", "beat": "b0001", "index": "0"}, "invalid_field", ["ops[0].index"]),
    ({"op": "remove_pick", "beat": "b0004", "index": 0}, "invalid_field", ["ops[0].index"]),
    ({"op": "remove_pick", "beat": "b0044", "index": 0}, "unknown_beat", ["ops[0].beat"]),
])
def test_remove_pick_wrong_fields(client, op, code, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where
    untouched(client, r, before)


def test_skip_beat(client):
    r = pk(client, [{"op": "skip_beat", "beat": "b0003", "reason": "The main picture says it all."}])
    assert r.status_code == 200, r.text
    assert picks(client)["beats"]["b0003"] == {"items": [], "status": "skip", "note": "The main picture says it all."}
    assert r.json()["changes"] == [{"target": {"beat": "b0003"}, "time": "0:28", "what": "Đoạn 3: dùng lại tranh chính"}]


@pytest.mark.parametrize("op,code,where", [
    ({"op": "skip_beat"}, "invalid_field", ["ops[0].beat"]),
    ({"op": "skip_beat", "beat": "b0099"}, "unknown_beat", ["ops[0].beat"]),
    ({"op": "skip_beat", "beat": "b0003", "reason": 5}, "invalid_field", ["ops[0].reason"]),
])
def test_skip_beat_wrong_fields(client, op, code, where):
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code and paths(r) == where


# ---------------------------------------------------------------- scope (every operation of a line is refused outside it)
@pytest.mark.parametrize("op", [
    {"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}]},
    {"op": "add_pick", "beat": "b0004", "asset": "A"},
    {"op": "remove_pick", "beat": "b0001", "index": 0},
    {"op": "skip_beat", "beat": "b0004"},
])
def test_a_line_operation_outside_the_scope_refuses_the_batch(client, op):
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_picks", "beat": "b0003", "items": [{"asset": "C"}]}, op], scope={"beats": ["b0003"]})
    assert r.status_code == 422 and r.json()["code"] == "out_of_scope", r.text
    assert paths(r) == ["ops[1].beat"] and r.json()["op_index"] == 1
    untouched(client, r, before)


@pytest.mark.parametrize("op", [
    {"op": "set_main", "asset": "B"},
    {"op": "set_region", "asset": "A", "region": "X", "x": 1, "y": 1},
    {"op": "remove_region", "asset": "A", "region": "HANDS"},
    {"op": "import", "source": "commons", "source_id": PD_ID, "as_main": True},
])
def test_an_operation_on_the_whole_document_is_outside_any_scope(client, op):
    r = pk(client, [op], scope={"beats": ["b0003"]})
    assert r.status_code == 422 and r.json()["code"] == "out_of_scope" and paths(r) == ["ops[0]"], r.text


def test_scope_by_beats_and_by_chapters_lets_the_lines_inside_through(client):
    assert pk(client, [{"op": "skip_beat", "beat": "b0003"}], scope={"beats": ["b0003", "b0004"]}).status_code == 200
    assert pk(client, [{"op": "skip_beat", "beat": "b0004"}], scope={"chapters": ["c02"]}).status_code == 200      # c02: b0003 and b0004
    r = pk(client, [{"op": "skip_beat", "beat": "b0005"}], scope={"chapters": ["c02"]})
    assert r.status_code == 422 and r.json()["code"] == "out_of_scope"


def test_a_scope_that_names_nothing_real_is_an_invalid_request(client):
    r = pk(client, [{"op": "skip_beat", "beat": "b0003"}], scope={"beats": ["b9000"]})
    assert r.status_code == 422 and r.json()["code"] == "invalid_request" and paths(r) == ["scope.beats[0]"]
    assert r.json()["fields"][0]["allowed"][0] == "b0001"
    r = pk(client, [{"op": "skip_beat", "beat": "b0003"}], scope={"chapters": ["c99"]})
    assert paths(r) == ["scope.chapters[0]"] and r.json()["fields"][0]["allowed"] == ["c01", "c02", "c03"]
    r = pk(client, [{"op": "skip_beat", "beat": "b0003"}], scope={"shots": ["s0001"]})
    assert r.status_code == 422 and paths(r) == ["scope.shots"]


# ---------------------------------------------------------------- import (fake sources: no network)
def test_import_then_use_the_ref_in_the_same_batch(client):
    r = pk(client, [{"op": "import", "source": "commons", "source_id": PD_ID, "ref": "found"},
                    {"op": "set_picks", "beat": "b0004", "items": [{"asset": "$found"}, {"asset": "A"}]},
                    {"op": "set_region", "asset": "$found", "region": "MIRROR", "x": 100, "y": 100}])
    assert r.status_code == 200, r.text
    j = r.json()
    key = j["created"]["refs"]["found"]
    assert j["created"]["assets"] == [key] and key not in ("A", "B", "C", "D")
    d = picks(client)
    assert d["assets"][key]["credit"]["source"] == "commons" and (client.pdir / d["assets"][key]["file"]).is_file()
    assert d["beats"]["b0004"]["items"][0]["asset"] == key and "MIRROR" in d["assets"][key]["regions"]
    assert [c["what"] for c in j["changes"]] == ["Nhập hình từ Wikimedia Commons", "Đoạn 4: thay 2 hình", "Vùng MIRROR của hình vừa nhập: đã đặt"]
    assert j["changes"][0]["target"] == {"asset": key}


def test_import_as_main_and_twice(client):
    r = pk(client, [{"op": "import", "source": "commons", "source_id": PD_ID, "as_main": True}])
    key = r.json()["created"]["assets"][0]
    assert picks(client)["main_asset"] == key
    assert r.json()["changes"][0]["what"] == "Nhập hình từ Wikimedia Commons và đặt làm tranh chính"
    again = pk(client, [{"op": "import", "source": "commons", "source_id": PD_ID}])       # already in the project: nothing changes
    assert again.status_code == 200 and again.json()["batch"] is None and again.json()["changes"] == [] and again.json()["created"]["assets"] == []


def test_import_a_picture_of_the_books(client):
    r = pk(client, [{"op": "import", "source": "book", "source_id": "payne_gae/img/850", "ref": "pg"},
                    {"op": "add_pick", "beat": "b0005", "asset": "$pg"}])
    assert r.status_code == 200, r.text
    key = r.json()["created"]["refs"]["pg"]
    assert picks(client)["assets"][key]["credit"]["source"] == "book"
    assert r.json()["changes"][0]["what"] == "Nhập hình từ sách của dự án"


def test_a_picture_that_is_not_of_the_books_is_not_found(client):
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "import", "source": "book", "source_id": "payne_gae/page/99"}])
    assert r.status_code == 404 and r.json()["code"] == "not_found" and r.json()["op_index"] == 0 and r.json()["fix"]
    untouched(client, r, before)


def test_a_dry_run_downloads_nothing_and_says_what_a_real_run_says(client, sources):
    net, _ = sources
    ops = [{"op": "import", "source": "commons", "source_id": PD_ID, "ref": "found"}, {"op": "set_picks", "beat": "b0004", "items": [{"asset": "$found"}]}]
    before = snapshot(client.pdir)
    dry = pk(client, ops, dry_run=True)
    assert dry.status_code == 200, dry.text
    assert dry.json()["dry_run"] is True and dry.json()["batch"] is None and net.urls == []
    assert snapshot(client.pdir) == before
    assert dry.json()["changes"][0]["target"] == {"asset": None}
    real = pk(client, ops)
    assert real.status_code == 200 and net.urls
    key = real.json()["created"]["assets"][0]
    assert [(c["what"], c["time"]) for c in dry.json()["changes"]] == [(c["what"], c["time"]) for c in real.json()["changes"]]
    assert [c["target"] for c in real.json()["changes"]] == [{"asset": key}, {"beat": "b0004"}]


def test_a_failed_download_refuses_the_batch_before_any_write(client, monkeypatch):
    bad = FakeNet([("commons.wikimedia.org", urllib.error.URLError("down"))])
    monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=bad, sleep=lambda s: None))
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_main", "asset": "B"}, {"op": "import", "source": "commons", "source_id": PD_ID}])
    assert r.status_code == 503 and r.json()["code"] == "source_unreachable" and r.json()["retry"] == "later" and r.json()["op_index"] == 1
    untouched(client, r, before)


def test_a_rate_limited_source_keeps_its_code_and_its_wait(client, monkeypatch):
    limited = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "180"}, None)
    net = FakeNet([("commons.wikimedia.org", limited)])
    monkeypatch.setitem(media_api._SOURCES, "commons", CommonsSource(opener=net, sleep=lambda s: None))
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_main", "asset": "B"}, {"op": "import", "source": "commons", "source_id": PD_ID}])
    j = r.json()
    assert r.status_code == 503 and j["code"] == "source_rate_limited" and j["retry_after"] == 180 and j["retry"] == "later" and j["op_index"] == 1
    assert j["fix"] and len(net.urls) == 1
    untouched(client, r, before)


@pytest.mark.parametrize("op,code,where", [
    ({"op": "import", "source": "flickr", "source_id": "1"}, "invalid_field", ["ops[0].source"]),
    ({"op": "import", "source": "commons"}, "invalid_field", ["ops[0].source_id"]),
    ({"op": "import", "source": "commons", "source_id": ""}, "invalid_field", ["ops[0].source_id"]),
    ({"op": "import", "source": "commons", "source_id": "x", "ref": "1bad"}, "invalid_field", ["ops[0].ref"]),
    ({"op": "import", "source": "commons", "source_id": "x", "as_main": "yes"}, "invalid_field", ["ops[0].as_main"]),
])
def test_import_wrong_fields(client, op, code, where, sources):
    net, _ = sources
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code and paths(r) == where and net.urls == []
    assert "commons" in r.json()["fields"][0].get("allowed", ["commons"]) or r.json()["fields"][0]["path"] != "ops[0].source"


# ---------------------------------------------------------------- refs
def test_a_ref_that_was_not_defined_or_is_defined_twice(client):
    r = pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "$later"}]}])
    assert r.status_code == 422 and r.json()["code"] == "unknown_ref" and paths(r) == ["ops[0].items[0].asset"]
    two = pk(client, [{"op": "import", "source": "commons", "source_id": PD_ID, "ref": "x"},
                      {"op": "import", "source": "met", "source_id": "436535", "ref": "x"}], dry_run=True)
    assert two.status_code == 422 and two.json()["code"] == "duplicate_ref" and paths(two) == ["ops[1].ref"]


# ---------------------------------------------------------------- the document the ops leave
def test_a_batch_writes_the_picks_like_the_page_does(client):
    """Approval dropped, previous file kept as picks.prev.json, no op leaves a document the strict check refuses."""
    from bti.picks import service
    ap = service.approve(client.pdir, pk_rev(client))
    assert ap["approved"] is True
    r = pk(client, [{"op": "skip_beat", "beat": "b0004"}])
    assert r.status_code == 200
    p = client.get(B).json()
    assert p["approved"] is False and read_json(client.pdir / "picks.json")["approval"] == {"approved": False, "sha1": None, "approved_at": None}
    assert (client.pdir / "picks.prev.json").is_file()
    assert pdoc.doc_problem(read_json(client.pdir / "picks.json")) is None
    assert copy.deepcopy(p["issues"]) == [i for i in p["issues"] if i["level"] != "error"]


def test_a_picks_project_without_a_picks_file_takes_its_first_batch(client):
    (client.pdir / "picks.json").unlink()
    (client.pdir / "picks.prev.json").unlink(missing_ok=True)
    r = pk(client, [{"op": "skip_beat", "beat": "b0001"}])
    assert r.status_code == 200 and picks(client)["beats"]["b0001"]["status"] == "skip"


# ---------------------------------------------------------------- kinds and missing of a line (worker linekinds)
KINDS = ["outside", "figure"]
MISSING = [{"what": "Noyon Cathedral", "code": "agent_none"}]


def set_known(client, beat="b0004", **more):
    r = pk(client, [{"op": "set_picks", "beat": beat, "items": [{"asset": "A"}], "reason": "Tranh chính.", "kinds": KINDS, "missing": MISSING, **more}])
    assert r.status_code == 200, r.text
    return r


def test_set_picks_writes_kinds_and_missing_and_the_document_keeps_them(client):
    set_known(client)
    b = picks(client)["beats"]["b0004"]
    assert b["kinds"] == KINDS and b["missing"] == MISSING and b["status"] == "picked" and b["items"][0]["asset"] == "A"
    assert pdoc.load(client.pdir)["beats"]["b0004"]["kinds"] == KINDS


def test_a_later_edit_of_the_pictures_keeps_kinds_and_missing_unless_it_sends_new_ones(client):
    set_known(client)
    pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}]}])                              # an edit of the items
    pk(client, [{"op": "add_pick", "beat": "b0004", "asset": "C"}])
    pk(client, [{"op": "remove_pick", "beat": "b0004", "index": 0}])
    b = picks(client)["beats"]["b0004"]
    assert [i["asset"] for i in b["items"]] == ["C"] and b["kinds"] == KINDS and b["missing"] == MISSING
    pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "D"}], "kinds": ["detail"]}])         # new kinds: replaced; missing stays
    b = picks(client)["beats"]["b0004"]
    assert b["kinds"] == ["detail"] and b["missing"] == MISSING
    pk(client, [{"op": "skip_beat", "beat": "b0004"}])                                                         # skip keeps them too
    b = picks(client)["beats"]["b0004"]
    assert b["status"] == "skip" and b["items"] == [] and b["kinds"] == ["detail"] and b["missing"] == MISSING
    pk(client, [{"op": "skip_beat", "beat": "b0005", "kinds": ["idea"], "reason": "Cùng ý."}])                 # skip_beat takes kinds
    assert picks(client)["beats"]["b0005"]["kinds"] == ["idea"] and "missing" not in picks(client)["beats"]["b0005"]


def test_an_empty_list_takes_kinds_or_missing_away(client):
    set_known(client)
    pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}], "missing": []}])
    b = picks(client)["beats"]["b0004"]
    assert "missing" not in b and b["kinds"] == KINDS
    pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}], "kinds": []}])
    assert "kinds" not in picks(client)["beats"]["b0004"]


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "kinds": ["picture"]}, "invalid_field", ["ops[0].kinds[0]"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "kinds": ["detail", "whole", "idea"]}, "invalid_field", ["ops[0].kinds"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "kinds": ["detail", "detail"]}, "invalid_field", ["ops[0].kinds"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "kinds": "outside"}, "invalid_field", ["ops[0].kinds"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "missing": [{"what": "x"}]}, "invalid_field", ["ops[0].missing[0].code"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "missing": [{"what": "x", "code": "Bad Code"}]}, "invalid_field", ["ops[0].missing[0].code"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "missing": [{"what": "x", "code": "a", "extra": 1}]}, "invalid_field", ["ops[0].missing[0].extra"]),
    ({"op": "set_picks", "beat": "b0004", "items": [{"asset": "A"}], "missing": [{"what": "x", "code": "a"}] * 11}, "invalid_field", ["ops[0].missing"]),
    ({"op": "skip_beat", "beat": "b0004", "kinds": ["nothing"]}, "invalid_field", ["ops[0].kinds[0]"]),
])
def test_kinds_and_missing_wrong_fields(client, op, code, where):
    before = snapshot(client.pdir)
    r = pk(client, [op])
    assert r.status_code == 422 and r.json()["code"] == code, r.text
    assert paths(r) == where
    untouched(client, r, before)


def test_the_schema_of_the_operation_lists_the_eleven_words_and_the_two_fields(client):
    for name in ("set_picks", "skip_beat"):
        sch = client.get("/api/ops/schema").json()["picks"][name]["schema"]
        assert set(sch["properties"]["kinds"]["items"]["enum"]) == set(pdoc.LINE_KINDS) and sch["properties"]["kinds"]["maxItems"] == 2
        assert sch["properties"]["missing"]["items"]["required"] == ["what", "code"] and "kinds" not in sch["required"]


def test_undo_gives_kinds_and_missing_back(client):
    r1 = set_known(client)
    r2 = pk(client, [{"op": "set_picks", "beat": "b0004", "items": [{"asset": "B"}], "kinds": ["detail"], "missing": []}])
    assert picks(client)["beats"]["b0004"]["kinds"] == ["detail"]
    out = client.post("/api/projects/%s/changes/%s/undo" % (PID, r2.json()["batch"]), json={"base_rev": pk_rev(client), "actor": "human"})
    assert out.status_code == 200, out.text
    b = picks(client)["beats"]["b0004"]
    assert b["kinds"] == KINDS and b["missing"] == MISSING and [i["asset"] for i in b["items"]] == ["A"]
    out = client.post("/api/projects/%s/changes/%s/undo" % (PID, r1.json()["batch"]), json={"base_rev": pk_rev(client), "actor": "human"})
    assert out.status_code == 200, out.text
    assert "b0004" not in picks(client)["beats"]                                                              # the line did not exist before the first batch


def test_a_save_of_the_page_keeps_what_the_agent_knows_of_a_line_unless_it_sends_new_ones(client):
    set_known(client)
    page = client.get("/api/projects/%s/picks" % PID).json()
    body = page["picks"]
    for key in ("kinds", "missing"):                                                                          # a page that does not know the fields sends none
        body["beats"]["b0004"].pop(key, None)
    r = client.put("/api/projects/%s/picks" % PID, json={"picks": body, "base_rev": page["rev"]})
    assert r.status_code == 200, r.text
    b = picks(client)["beats"]["b0004"]
    assert b["kinds"] == KINDS and b["missing"] == MISSING
    page = client.get("/api/projects/%s/picks" % PID).json()
    body = page["picks"]
    body["beats"]["b0004"]["kinds"] = ["detail"]
    body["beats"]["b0004"]["missing"] = []
    r = client.put("/api/projects/%s/picks" % PID, json={"picks": body, "base_rev": page["rev"]})
    b = picks(client)["beats"]["b0004"]
    assert r.status_code == 200 and b["kinds"] == ["detail"] and "missing" not in b
    page = client.get("/api/projects/%s/picks" % PID).json()
    page["picks"]["beats"]["b0004"]["kinds"] = ["nonsense"]
    r = client.put("/api/projects/%s/picks" % PID, json={"picks": page["picks"], "base_rev": page["rev"]})
    assert r.status_code == 422 and "kinds" in r.text


def test_set_region_with_tight_thing_and_rough_roundtrips_and_undoes(client):
    r = pk(client, [{
        "op": "set_region", "asset": "A", "region": "MIRROR",
        "x": 700, "y": 420, "rx": 90, "ry": 110, "label": "Tấm gương",
        "tight": True, "thing": "convex mirror on back wall", "rough": [540, 260, 860, 580],
    }])
    assert r.status_code == 200, r.text
    reg = picks(client)["assets"]["A"]["regions"]["MIRROR"]
    assert reg == {
        "x": 700, "y": 420, "rx": 90, "ry": 110, "label": "Tấm gương",
        "tight": True, "thing": "convex mirror on back wall", "rough": [540, 260, 860, 580],
    }
    undo = client.post("/api/projects/%s/changes/%s/undo" % (PID, r.json()["batch"]), json={"base_rev": pk_rev(client), "actor": "human"})
    assert undo.status_code == 200 and "MIRROR" not in picks(client)["assets"]["A"]["regions"]
    # Without the new fields: unchanged legacy shape
    r2 = pk(client, [{"op": "set_region", "asset": "A", "region": "LEGACY", "x": 200, "y": 200, "rx": 50, "ry": 50, "label": "Cũ"}])
    assert r2.status_code == 200 and picks(client)["assets"]["A"]["regions"]["LEGACY"] == {"x": 200, "y": 200, "rx": 50, "ry": 50, "label": "Cũ"}


@pytest.mark.parametrize("extra,where", [
    ({"tight": "yes"}, ["ops[0].tight"]),
    ({"thing": 123}, ["ops[0].thing"]),
    ({"rough": [10, 20, 30]}, ["ops[0].rough"]),
    ({"rough": [100, 100, 50, 200]}, ["ops[0].rough"]),
    ({"rough": [0, 0, 5000, 200]}, ["ops[0].rough"]),
])
def test_set_region_rejects_bad_tight_thing_and_rough(client, extra, where):
    before = snapshot(client.pdir)
    r = pk(client, [{"op": "set_region", "asset": "A", "region": "BAD", "x": 200, "y": 200, "rx": 40, "ry": 40, **extra}])
    assert r.status_code == 422 and paths(r) == where
    untouched(client, r, before)


def test_subject_table_and_line_about_are_logged_and_undoable(client):
    subjects = [
        {"id": "sitter", "kind": "person", "name": "Sitter", "also": ["the merchant"], "strip": True, "where": {"region": "HEAD"}},
        {"id": "scroll", "kind": "text", "name": "The Charter", "strip": False, "where": None},
        {"id": "patron", "kind": "person", "name": "Patron", "strip": True, "where": {"asset": "B"}},
    ]
    response = pk(client, [{"op": "set_subjects", "subjects": subjects},
                           {"op": "set_about", "beat": "b0001", "about": [{"id": "sitter", "words": "the sitter"}]}])
    assert response.status_code == 200, response.text
    assert picks(client)["subjects"] == subjects
    assert picks(client)["beats"]["b0001"]["about"] == [{"id": "sitter", "words": "the sitter"}]
    undo = client.post("/api/projects/%s/changes/%s/undo" % (PID, response.json()["batch"]),
                       json={"base_rev": pk_rev(client), "actor": "human"})
    assert undo.status_code == 200, undo.text
    after_undo = picks(client)
    assert "subjects" not in after_undo
    assert "about" not in after_undo["beats"]["b0001"]


def test_set_subjects_and_set_about_reject_invalid_strips_and_blank_fields(client):
    assert pk(client, [{"op": "set_subjects", "subjects": [
        {"id": "s1", "kind": "person", "name": "Ada", "strip": True, "where": {"region": "HEAD"}},
    ]}]).status_code == 200
    before = snapshot(client.pdir)
    for bad_op in (
        {"op": "set_subjects", "subjects": [{"id": "i1", "kind": "idea", "name": "faith", "strip": True, "where": None}]},
        {"op": "set_subjects", "subjects": [{"id": "t1", "kind": "text", "name": "Bible", "strip": True, "where": None}]},
        {"op": "set_subjects", "subjects": [{"id": "p1", "kind": "person", "name": "   ", "strip": False, "where": None}]},
        {"op": "set_subjects", "subjects": [{"id": "p2", "kind": "person", "name": "Ada", "also": ["   "], "strip": True, "where": None}]},
        {"op": "set_about", "beat": "b0001", "about": [{"id": "s1", "words": "   "}]},
    ):
        r = pk(client, [bad_op])
        assert r.status_code == 422, (bad_op, r.text)
        untouched(client, r, before)


def test_set_and_clear_picture_caption(client):
    r = pk(client, [{'op': 'set_caption', 'asset': 'B', 'caption': 'Silk damask, Italy, about 1500'}])
    assert r.status_code == 200, r.text
    assert picks(client)['assets']['B']['caption'] == 'Silk damask, Italy, about 1500'
    r = pk(client, [{'op': 'set_caption', 'asset': 'B', 'caption': ''}])
    assert r.status_code == 200, r.text
    assert 'caption' not in picks(client)['assets']['B']
