"""The storyboard operations, one by one: the normal case, every way the fields can be wrong (with the exact `fields[].path`), the
scope and the lock. The fixture: ten shots, `s0006` locked with a locked overlay, starts at word 0, 22, 48, 62, 85, 110, 140, 168,
200, 226 (a word every 0.35 s from 0.4 s), the end at 90 s."""
import copy
import json

import pytest
from ops_helpers import paths, read_json, sb, shot, shots, snapshot, word_t

import bti.engine.api  # noqa: F401  - registers the renderers
from bti.engine import registry as R

BUNDLE = R.load_bundle("gae")


def vi(tid):
    return BUNDLE.spec(tid)["label_vi"]


def ids(client):
    return [s["id"] for s in shots(client)]


def refused(client, ops, status, code, where, **kw):
    """Send `ops`; they must be refused with `code`, naming exactly `where` as the wrong fields, and write nothing."""
    before = snapshot(client.pdir)
    r = sb(client, ops, **kw)
    assert r.status_code == status and r.json()["code"] == code, r.text
    assert paths(r) == where, r.text
    assert r.json()["fix"] and r.json()["retry"] in ("after_fix", "later", "no") and "detail" in r.json()
    assert snapshot(client.pdir) == before
    return r


def add_mask_asset(client):
    d = read_json(client.pdir / "storyboard.json")
    d["assets"]["M"] = {"file": "media/c_detail.png", "kind": "mask", "title": "Mask", "artist": "", "year": "", "width": 1000, "height": 1000,
                        "credit": {}, "regions": {}}
    (client.pdir / "storyboard.json").write_text(json.dumps(d, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- set_technique
def test_set_technique(client):
    before = copy.deepcopy(shot(client, "s0004"))
    r = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0004")
    assert s["technique"] == "CAM-03" and s["slots"] == {"image": {"asset": "B"}} and s["source"] == "agent"
    keys = s["params"]["camera"]
    assert len(keys) >= 2 and all("rel" in k["at"] for k in keys)                          # the engine's own defaults for CAM-03
    assert s["intent"] in BUNDLE.spec("CAM-03")["intents"]
    for k in ("id", "start", "overlays", "locked", "transition_in", "note"):
        assert s[k] == before[k]
    assert r.json()["changes"] == [{"target": {"shot": "s0004"}, "time": "0:22", "what": "Cảnh 4: đổi kỹ thuật sang " + vi("CAM-03")}]


def test_set_technique_takes_the_defaults_the_defaults_route_gives(client):
    sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}])
    t = client.get("/api/projects/ops1").json()["storyboard"]
    s = shot(client, "s0004")                                                                        # as saved (the page's copy has derived keys)
    ask = client.post("/api/projects/ops1/defaults", json={"technique": "CAM-03", "context": {
        "item": "shot", "shot_id": "s0004", "slots": {"image": {"asset": "B"}},
        "assets": {"B": {"width": 1600, "height": 1000, "title": "Test landscape", "artist": "Test", "year": "2026",
                         "regions": t["assets"]["B"]["regions"]}}, "canvas": t["canvas"],
        "camera": {"cx": 800, "cy": 500, "zoom": 1.08}}}).json()["params"]
    assert s["params"]["camera"] == ask["camera"] and s["params"]["shadow"] == ask["shadow"]


def test_set_technique_with_params_and_an_intent(client):
    r = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"shadow": False}, "intent": "reveal"}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0004")
    assert s["params"]["shadow"] is False and s["intent"] == "reveal"


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_technique", "shot": "s0004"}, "invalid_field", ["ops[0].technique"]),
    ({"op": "set_technique", "technique": "CAM-03"}, "invalid_field", ["ops[0].shot"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "NOPE-99"}, "unknown_technique", ["ops[0].technique"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "HI-01"}, "wrong_technique_kind", ["ops[0].technique"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "TR-01"}, "wrong_technique_kind", ["ops[0].technique"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"zzz": 1}}, "unknown_param", ["ops[0].params.zzz"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"zzz": None}}, "unknown_param", ["ops[0].params.zzz"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"shadow": "yes"}}, "invalid_field", ["ops[0].params.shadow"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"camera": []}}, "invalid_field", ["ops[0].params.camera"]),
    ({"op": "set_technique", "shot": "s0099", "technique": "CAM-03"}, "unknown_shot", ["ops[0].shot"]),
    ({"op": "set_technique", "shot": "$nope", "technique": "CAM-03"}, "unknown_ref", ["ops[0].shot"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "intent": "dance"}, "invalid_field", ["ops[0].intent"]),
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": []}, "invalid_field", ["ops[0].params"]),
    ({"op": "set_technique", "shot": 4, "technique": "CAM-03"}, "invalid_field", ["ops[0].shot"]),
])
def test_set_technique_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


def test_set_technique_lists_what_is_allowed(client):
    r = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "NOPE-99"}])
    assert "CAM-03" in r.json()["fields"][0]["allowed"] and "HI-01" not in r.json()["fields"][0]["allowed"]
    r = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03", "params": {"zzz": 1}}])
    assert r.json()["fields"][0]["allowed"] == ["camera", "shadow"]
    r = sb(client, [{"op": "set_technique", "shot": "s0099", "technique": "CAM-03"}])
    assert r.json()["fields"][0]["allowed"] == ["s%04d" % i for i in range(1, 11)]
    enum = next((t, p) for t in BUNDLE.techniques for p in t["params"] if p["type"] == "enum" and t["kind"] == "base" and BUNDLE.available(t["id"]))
    r = sb(client, [{"op": "set_technique", "shot": "s0004", "technique": enum[0]["id"], "params": {enum[1]["name"]: "no-such-value"}}])
    assert r.status_code == 422 and r.json()["fields"][0]["allowed"] == enum[1]["values"]


def test_a_technique_the_engine_cannot_draw_yet_is_refused(client, monkeypatch):
    monkeypatch.setitem(BUNDLE.by_id["CAM-03"]["engine"], "available", False)                       # the registry says it is not drawn yet
    r = refused(client, [{"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}], 422, "technique_unavailable", ["ops[0].technique"])
    assert "CAM-03" not in r.json()["fields"][0]["allowed"] and "CAM-01" in r.json()["fields"][0]["allowed"]
    refused(client, [{"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-03"}]}], 422, "technique_unavailable",
            ["ops[0].shots[0].technique"])


# ---------------------------------------------------------------- set_params
def test_set_params_on_a_shot(client):
    before = copy.deepcopy(shot(client, "s0004"))
    r = sb(client, [{"op": "set_params", "shot": "s0004", "params": {"shadow": False}}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0004")
    assert s["params"]["shadow"] is False and s["params"]["camera"] == before["params"]["camera"] and s["source"] == "agent"
    assert r.json()["changes"] == [{"target": {"shot": "s0004"}, "time": "0:22", "what": "Cảnh 4: đổi thiết lập shadow"}]


def test_set_params_on_an_overlay(client):
    r = sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 260, "ry": 240}}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0002")
    o = s["overlays"][0]
    assert (o["params"]["rx"], o["params"]["ry"], o["params"]["at"]) == (260, 240, "CENTRE") and o["source"] == "agent" and s["source"] == "import"
    assert r.json()["changes"] == [{"target": {"shot": "s0002", "overlay": "o1"}, "time": "0:08",
                                    "what": "Cảnh 2: đổi thiết lập rx, ry của lớp phủ " + vi("HI-01")}]


def test_a_null_parameter_returns_to_its_default(client):
    r = sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"floor": 0.6}},
                    {"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"floor": None, "ramp_in": 1.5}}])
    assert r.status_code == 200, r.text
    default = next(p["default"] for p in BUNDLE.spec("HI-01")["params"] if p["name"] == "floor")
    o = shot(client, "s0002")["overlays"][0]
    assert o["params"]["floor"] == default and o["params"]["ramp_in"] == 1.5


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_params", "shot": "s0002"}, "invalid_field", ["ops[0].params"]),
    ({"op": "set_params", "shot": "s0002", "params": {}}, "invalid_field", ["ops[0].params"]),
    ({"op": "set_params", "shot": "s0002", "params": "rx"}, "invalid_field", ["ops[0].params"]),
    ({"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"zzz": 1}}, "unknown_param", ["ops[0].params.zzz"]),
    ({"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 1}}, "invalid_field", ["ops[0].params.rx"]),
    ({"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": "wide"}}, "invalid_field", ["ops[0].params.rx"]),
    ({"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"at": "NOPE"}}, "unknown_region", ["ops[0].params.at"]),
    ({"op": "set_params", "shot": "s0002", "overlay": "o9", "params": {"rx": 90}}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "set_params", "shot": "s0003", "overlay": "o1", "params": {"rx": 90}}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "set_params", "shot": "s0099", "params": {"rx": 90}}, "unknown_shot", ["ops[0].shot"]),
])
def test_set_params_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


def test_set_params_names_the_regions_that_exist(client):
    r = sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"at": "NOPE"}}])
    assert r.json()["fields"][0]["allowed"] == ["CENTRE", "HANDS", "HEAD"]
    r = sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o9", "params": {"rx": 90}}])
    assert r.json()["fields"][0]["allowed"] == ["o1", "o2"]


# ---------------------------------------------------------------- set_slot
def test_set_slot_changes_the_picture_and_fits_the_camera(client):
    before = copy.deepcopy(shot(client, "s0004"))
    r = sb(client, [{"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "C"}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0004")
    assert s["slots"] == {"image": {"asset": "C"}} and s["source"] == "agent"
    assert s["params"]["camera"] != before["params"]["camera"] and len(s["params"]["camera"]) == 2          # keys in the new picture's pixels
    assert r.json()["changes"] == [{"target": {"shot": "s0004"}, "time": "0:22", "what": "Cảnh 4: đổi ô image sang hình “Test detail”"}]


def test_set_slot_on_an_overlay_and_clearing_a_slot(client):
    r = sb(client, [{"op": "set_slot", "shot": "s0002", "overlay": "o1", "slot": "image", "asset": "B"},
                    {"op": "set_slot", "shot": "s0005", "slot": "right", "asset": None}])
    assert r.status_code == 200, r.text
    assert shot(client, "s0002")["overlays"][0]["slots"] == {"image": {"asset": "B"}}
    assert shot(client, "s0005")["slots"] == {"left": {"asset": "A"}}
    assert [c["what"] for c in r.json()["changes"]] == ["Cảnh 2: đổi ô image của lớp phủ %s sang hình “Test landscape”" % vi("HI-01"),
                                                         "Cảnh 5: bỏ hình ở ô right"]
    assert any(i["code"] == "incomplete" for i in r.json()["issues"])                       # a warning stays; it is no error


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_slot", "shot": "s0004", "slot": "image"}, "invalid_field", ["ops[0].asset"]),
    ({"op": "set_slot", "shot": "s0004", "asset": "C"}, "invalid_field", ["ops[0].slot"]),
    ({"op": "set_slot", "shot": "s0004", "slot": "image", "asset": 3}, "invalid_field", ["ops[0].asset"]),
    ({"op": "set_slot", "shot": "s0004", "slot": "zzz", "asset": "C"}, "unknown_slot", ["ops[0].slot"]),
    ({"op": "set_slot", "shot": "s0004", "slot": "zzz", "asset": None}, "unknown_slot", ["ops[0].slot"]),
    ({"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "Z9"}, "unknown_asset", ["ops[0].asset"]),
    ({"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "M"}, "slot_kind_mismatch", ["ops[0].asset"]),
    ({"op": "set_slot", "shot": "s0002", "overlay": "o7", "slot": "image", "asset": "C"}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "set_slot", "shot": "s0044", "slot": "image", "asset": "C"}, "unknown_shot", ["ops[0].shot"]),
])
def test_set_slot_wrong_fields(client, op, code, where):
    add_mask_asset(client)
    r = refused(client, [op], 422, code, where)
    if code == "slot_kind_mismatch":
        assert r.json()["fields"][0]["allowed"] == ["image"]
    if code == "unknown_slot":
        assert r.json()["fields"][0]["allowed"] == ["image"]
    if code == "unknown_asset":
        assert r.json()["fields"][0]["allowed"] == ["A", "B", "C", "D", "M"]


# ---------------------------------------------------------------- add_overlay / set_overlay / remove_overlay
def test_add_overlay(client):
    r = sb(client, [{"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 220, "ry": 220},
                     "start": {"w": 70}, "dur": 4, "ref": "ring"}])
    assert r.status_code == 200, r.text
    o = shot(client, "s0004")["overlays"][1]
    assert o["id"] == "o3" and o["technique"] == "HI-01" and o["dur"] == 4.0 and o["start"] == {"w": 70, "off": 0, "text": "word70"}
    assert o["params"]["at"] == "CENTRE" and o["params"]["rx"] == 220 and o["params"]["floor"] == 0.2          # defaults for the rest
    assert o["source"] == "agent" and o["locked"] is False and o["intent"] in BUNDLE.spec("HI-01")["intents"]
    j = r.json()
    assert j["created"]["overlays"] == [{"shot": "s0004", "overlay": "o3"}] and j["created"]["refs"] == {"ring": "o3"}
    assert j["changes"] == [{"target": {"shot": "s0004", "overlay": "o3"}, "time": "0:22",
                             "what": "Cảnh 4: thêm lớp phủ %s ở vùng Centre" % vi("HI-01")}]


def test_add_overlay_defaults_and_a_ref_used_later(client):
    r = sb(client, [{"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 100, "ry": 100}, "ref": "ring"},
                    {"op": "set_overlay", "shot": "s0004", "overlay": "$ring", "dur": 2.0}])
    assert r.status_code == 200, r.text
    o = shot(client, "s0004")["overlays"][1]
    assert o["start"] == shot(client, "s0004")["start"] and o["dur"] == 2.0
    e = sb(client, [{"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 100, "ry": 100},
                     "start": {"w": 66}, "end": {"w": 72}}])
    assert e.status_code == 200 and "end" in shot(client, "s0004")["overlays"][-1] and "dur" not in shot(client, "s0004")["overlays"][-1]


def test_add_overlay_lasts_three_seconds_or_what_is_left(client):
    sb(client, [{"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "CENTRE", "rx": 100, "ry": 100},
                 "start": {"t": 29.0}}])
    assert shot(client, "s0004")["overlays"][-1]["dur"] == 1.15                                      # the shot ends at 30.15 s


@pytest.mark.parametrize("op,code,where", [
    ({"op": "add_overlay", "shot": "s0004"}, "invalid_field", ["ops[0].technique"]),
    ({"op": "add_overlay", "technique": "HI-01"}, "invalid_field", ["ops[0].shot"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "CAM-01"}, "wrong_technique_kind", ["ops[0].technique"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "NOPE-99"}, "unknown_technique", ["ops[0].technique"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "start": {"w": 10}}, "invalid_field", ["ops[0].start"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "start": {"w": 9999}}, "invalid_field", ["ops[0].start"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "start": {"w": 70, "text": "wrong"}}, "invalid_field", ["ops[0].start"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "start": {}}, "invalid_field", ["ops[0].start"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "dur": 60}, "invalid_field", ["ops[0].dur"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "dur": 0}, "invalid_field", ["ops[0].dur"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "dur": 2, "end": {"w": 70}}, "invalid_field", ["ops[0].end"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "start": {"w": 66}, "end": {"w": 90}}, "invalid_field", ["ops[0].end"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"at": "NOPE"}}, "unknown_region", ["ops[0].params.at"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"zzz": 1}}, "unknown_param", ["ops[0].params.zzz"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "params": {"rx": -4}}, "invalid_field", ["ops[0].params.rx"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "slots": {"zzz": {"asset": "A"}}}, "unknown_slot", ["ops[0].slots.zzz"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "slots": {"image": {"asset": "Z9"}}}, "unknown_asset", ["ops[0].slots.image.asset"]),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01", "intent": "dance"}, "invalid_field", ["ops[0].intent"]),
    ({"op": "add_overlay", "shot": "s0099", "technique": "HI-01"}, "unknown_shot", ["ops[0].shot"]),
])
def test_add_overlay_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


def test_set_overlay(client):
    r = sb(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": 3.5, "note": "ring"}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0002")
    assert s["overlays"][0]["dur"] == 3.5 and s["overlays"][0]["note"] == "ring" and s["overlays"][0]["source"] == "agent"
    assert r.json()["changes"] == [{"target": {"shot": "s0002", "overlay": "o1"}, "time": "0:08", "what": "Cảnh 2: sửa lớp phủ " + vi("HI-01")}]


def test_set_overlay_start_end_and_open_end(client):
    assert sb(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o1", "start": {"w": 30}}]).status_code == 200
    o = shot(client, "s0002")["overlays"][0]
    assert o["start"] == {"w": 30, "off": 0, "text": "word30"} and o["dur"] == 5.0
    assert sb(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o1", "end": {"w": 40}}]).status_code == 200
    o = shot(client, "s0002")["overlays"][0]
    assert o["end"] == {"w": 40, "off": 0, "text": "word40"} and "dur" not in o
    assert sb(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o1", "end": None, "dur": None}]).status_code == 200
    o = shot(client, "s0002")["overlays"][0]
    assert "end" not in o and "dur" not in o                                                         # it runs to the end of the shot


def test_set_overlay_technique_takes_new_defaults(client):
    new = next(t["id"] for t in BUNDLE.techniques if t["kind"] == "overlay" and BUNDLE.available(t["id"]) and t["id"] not in ("HI-01", "AN-01"))
    r = sb(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o2", "technique": new}])
    assert r.status_code == 200, r.text
    o = shot(client, "s0002")["overlays"][1]
    assert o["technique"] == new and set(o["params"]) <= {p["name"] for p in BUNDLE.spec(new)["params"]} and o["intent"] in BUNDLE.spec(new)["intents"]


@pytest.mark.parametrize("op,code,where", [
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1"}, "invalid_field", ["ops[0]"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "start": {"w": 10}}, "invalid_field", ["ops[0].start"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": 20}, "invalid_field", ["ops[0].dur"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": -1}, "invalid_field", ["ops[0].dur"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": 2, "end": {"w": 40}}, "invalid_field", ["ops[0].end"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "end": {"w": 90}}, "invalid_field", ["ops[0].end"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "technique": "CAM-01"}, "wrong_technique_kind", ["ops[0].technique"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o1", "technique": "NOPE-99"}, "unknown_technique", ["ops[0].technique"]),
    ({"op": "set_overlay", "shot": "s0002", "overlay": "o9", "dur": 2}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "set_overlay", "shot": "s0002", "dur": 2}, "invalid_field", ["ops[0].overlay"]),
    ({"op": "set_overlay", "shot": "s0099", "overlay": "o1", "dur": 2}, "unknown_shot", ["ops[0].shot"]),
])
def test_set_overlay_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


def test_remove_overlay(client):
    r = sb(client, [{"op": "remove_overlay", "shot": "s0002", "overlay": "o2"}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0002")
    assert [o["id"] for o in s["overlays"]] == ["o1"] and s["source"] == "agent"
    assert r.json()["changes"] == [{"target": {"shot": "s0002", "overlay": "o2"}, "time": "0:08", "what": "Cảnh 2: bỏ lớp phủ " + vi("AN-01")}]


@pytest.mark.parametrize("op,code,where", [
    ({"op": "remove_overlay", "shot": "s0002"}, "invalid_field", ["ops[0].overlay"]),
    ({"op": "remove_overlay", "shot": "s0002", "overlay": "o3"}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "remove_overlay", "shot": "s0099", "overlay": "o1"}, "unknown_shot", ["ops[0].shot"]),
])
def test_remove_overlay_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


# ---------------------------------------------------------------- split_shot
def test_split_shot(client):
    before = copy.deepcopy(shot(client, "s0004"))
    r = sb(client, [{"op": "split_shot", "shot": "s0004", "at": 26.0, "ref": "second_half"}])
    assert r.status_code == 200, r.text
    assert ids(client) == ["s0001", "s0002", "s0003", "s0004", "s0011", "s0005", "s0006", "s0007", "s0008", "s0009", "s0010"]
    a, b = shot(client, "s0004"), shot(client, "s0011")
    assert b["start"] == {"w": 73, "off": 0, "text": "word73"} and a["start"] == before["start"]
    assert b["technique"] == "CAM-01" and b["slots"] == before["slots"] and b["transition_in"] is None and b["locked"] is False
    assert a["source"] == b["source"] == "agent" and b["overlays"] == []
    # the picture is continuous across the cut: each half keeps the pose it had
    ka, kb = a["params"]["camera"], b["params"]["camera"]
    assert ka[0]["at"] == {"rel": 0} and ka[-1]["at"] == {"rel": 1} and kb[0]["at"] == {"rel": 0} and kb[-1]["at"] == {"rel": 1}
    pose = lambda k: (k["cx"], k["cy"], k["zoom"])                                                   # noqa: E731
    assert pose(ka[-1]) == pose(kb[0]) and 400 < ka[-1]["cy"] < 500 and 1.08 < ka[-1]["zoom"] < 1.296
    assert pose(ka[0]) == pose(before["params"]["camera"][0]) and pose(kb[-1]) == pose(before["params"]["camera"][-1])
    # the overlay that crosses the cut is shortened to the cut (23.15 s to 25.95 s)
    assert a["overlays"][0]["dur"] == pytest.approx(25.95 - word_t(65), abs=1e-6) and a["overlays"][0]["source"] == "agent"
    assert r.json()["created"] == {"shots": ["s0011"], "overlays": [], "assets": [], "refs": {"second_half": "s0011"}}
    assert r.json()["changes"] == [{"target": {"shot": "s0004"}, "time": "0:22", "what": "Cảnh 4: tách thành hai cảnh tại 0:25"}]


def test_split_moves_the_overlays_that_start_after_the_cut(client):
    r = sb(client, [{"op": "split_shot", "shot": "s0002", "at": 12.0}])                              # o1 starts at 10.2 s, o2 at 12.3 s
    assert r.status_code == 200, r.text
    a, b = shot(client, "s0002"), shot(client, "s0011")
    assert [o["id"] for o in a["overlays"]] == ["o1"] and [o["id"] for o in b["overlays"]] == ["o2"]
    assert a["overlays"][0]["dur"] == pytest.approx(word_t(33) - word_t(28), abs=1e-6)
    assert b["overlays"][0]["start"] == {"w": 34, "off": 0.0, "text": "word34"} and b["overlays"][0]["dur"] == 3.0


def test_split_at_an_anchor_or_at_the_exact_time(client):
    assert sb(client, [{"op": "split_shot", "shot": "s0004", "at": {"w": 73}}]).status_code == 200
    assert shot(client, "s0011")["start"] == {"w": 73, "off": 0, "text": "word73"}
    assert sb(client, [{"op": "split_shot", "shot": "s0005", "at": 33.0, "snap": False}]).status_code == 200
    assert shot(client, "s0012")["start"] == {"t": 33.0}


@pytest.mark.parametrize("op,code,where", [
    ({"op": "split_shot", "shot": "s0004"}, "invalid_field", ["ops[0].at"]),
    ({"op": "split_shot", "at": 26}, "invalid_field", ["ops[0].shot"]),
    ({"op": "split_shot", "shot": "s0004", "at": 5.0}, "shot_too_short", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": 22.2}, "shot_too_short", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": 30.1}, "shot_too_short", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": {"w": 9999}}, "invalid_field", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": {"t": 99}}, "shot_too_short", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": "now"}, "invalid_field", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": -3}, "invalid_field", ["ops[0].at"]),
    ({"op": "split_shot", "shot": "s0004", "at": 26, "snap": "no"}, "invalid_field", ["ops[0].snap"]),
    ({"op": "split_shot", "shot": "s0099", "at": 26}, "unknown_shot", ["ops[0].shot"]),
])
def test_split_shot_wrong_fields(client, op, code, where):
    r = refused(client, [op], 422, code, where)
    if code == "shot_too_short":
        assert "choose a time between 22.30 and 29.95 s" in r.json()["fields"][0]["problem"]


def test_a_ref_made_by_a_split_names_the_new_shot_later(client):
    r = sb(client, [{"op": "split_shot", "shot": "s0004", "at": 26.0, "ref": "tail"},
                    {"op": "set_params", "shot": "$tail", "params": {"shadow": False}}])
    assert r.status_code == 200, r.text
    assert shot(client, "s0011")["params"]["shadow"] is False and shot(client, "s0004")["params"].get("shadow") != False   # noqa: E712


# ---------------------------------------------------------------- merge_shots
def test_merge_shots(client):
    r = sb(client, [{"op": "merge_shots", "shots": ["s0007", "s0008"]}])
    assert r.status_code == 200, r.text
    assert ids(client) == ["s0001", "s0002", "s0003", "s0004", "s0005", "s0006", "s0007", "s0009", "s0010"]
    m = shot(client, "s0007")
    keys = m["params"]["camera"]
    assert keys[0]["at"] == {"rel": 0.0} and keys[1]["at"] == {"rel": pytest.approx(9.8 / 21.0, abs=1e-4)}          # its poses keep their time
    assert m["technique"] == "CAM-03" and m["source"] == "agent"
    assert r.json()["changes"] == [{"target": {"shot": "s0007"}, "time": "0:49", "what": "Cảnh 7: gộp với cảnh 8"}]


def test_merge_three_shots_takes_every_overlay_and_gives_a_duplicate_id_a_fresh_one(client):
    r = sb(client, [{"op": "merge_shots", "shots": ["s0002", "s0003", "s0004"]}])
    assert r.status_code == 200, r.text
    m = shot(client, "s0002")
    assert [o["id"] for o in m["overlays"]] == ["o1", "o2", "o3"] and m["overlays"][2]["technique"] == "STATIC-02"    # s0004's "o1" is renamed
    assert "s0003" not in ids(client) and "s0004" not in ids(client)
    assert r.json()["changes"][0]["what"] == "Cảnh 2: gộp với cảnh 3, 4"


@pytest.mark.parametrize("op,code,where", [
    ({"op": "merge_shots"}, "invalid_field", ["ops[0].shots"]),
    ({"op": "merge_shots", "shots": ["s0007"]}, "invalid_field", ["ops[0].shots"]),
    ({"op": "merge_shots", "shots": "s0007"}, "invalid_field", ["ops[0].shots"]),
    ({"op": "merge_shots", "shots": ["s0007", "s0099"]}, "unknown_shot", ["ops[0].shots[1]"]),
    ({"op": "merge_shots", "shots": ["s0007", "s0009"]}, "not_consecutive", ["ops[0].shots[1]"]),
    ({"op": "merge_shots", "shots": ["s0008", "s0007"]}, "not_consecutive", ["ops[0].shots[1]"]),
    ({"op": "merge_shots", "shots": ["s0007", "s0007"]}, "not_consecutive", ["ops[0].shots"]),
    ({"op": "merge_shots", "shots": ["s0007", 8]}, "invalid_field", ["ops[0].shots[1]"]),
])
def test_merge_shots_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


# ---------------------------------------------------------------- move_boundary
def test_move_boundary(client):
    r = sb(client, [{"op": "move_boundary", "shot": "s0004", "to": 20.0}])
    assert r.status_code == 200, r.text
    assert shot(client, "s0004")["start"] == {"w": 56, "off": 0, "text": "word56"} and shot(client, "s0003")["start"]["w"] == 48
    assert shot(client, "s0004")["source"] == "agent"
    assert r.json()["changes"] == [{"target": {"shot": "s0004"}, "time": "0:20", "what": "Cảnh 4: dời điểm cắt từ 0:22 sang 0:20"}]


def test_move_boundary_fits_the_overlays_of_both_shots(client):
    r = sb(client, [{"op": "move_boundary", "shot": "s0003", "to": 13.0}])                  # s0002 now ends at 13.0 s: o1 (10.2-15.2), o2 (12.3-15.3)
    assert r.status_code == 200, r.text
    o1, o2 = shot(client, "s0002")["overlays"]
    assert o1["dur"] == pytest.approx(13.0 - word_t(28), abs=1e-6) and o2["dur"] == pytest.approx(13.0 - word_t(34), abs=1e-6)
    assert o1["source"] == o2["source"] == "agent"
    r = sb(client, [{"op": "move_boundary", "shot": "s0004", "to": 25.0}])                  # s0004 now starts at 24.9 s: its overlay (23.15 s) moves in
    assert r.status_code == 200, r.text
    o = shot(client, "s0004")["overlays"][0]
    assert o["start"] == {"w": 70, "off": 0, "text": "word70"} and o["dur"] == pytest.approx(30.15 - word_t(70), abs=1e-6)


@pytest.mark.parametrize("op,code,where", [
    ({"op": "move_boundary", "shot": "s0004"}, "invalid_field", ["ops[0].to"]),
    ({"op": "move_boundary", "to": 20}, "invalid_field", ["ops[0].shot"]),
    ({"op": "move_boundary", "shot": "s0001", "to": 3}, "invalid_field", ["ops[0].shot"]),
    ({"op": "move_boundary", "shot": "s0004", "to": 5.0}, "shot_too_short", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0004", "to": 30.1}, "shot_too_short", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0004", "to": {"t": 99}}, "shot_too_short", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0004", "to": {"w": 9999}}, "invalid_field", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0004", "to": -2}, "invalid_field", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0004", "to": "later"}, "invalid_field", ["ops[0].to"]),
    ({"op": "move_boundary", "shot": "s0099", "to": 20}, "unknown_shot", ["ops[0].shot"]),
])
def test_move_boundary_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


# ---------------------------------------------------------------- replace_range
EXAMPLE_RANGE = {"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008",
                 "shots": [{"technique": "CAM-01", "intent": "explore", "slots": {"image": {"asset": "C"}}, "ref": "first"},
                           {"technique": "STATIC-01", "start": {"w": 154}, "slots": {"image": {"asset": "B"}}}]}


def test_replace_range(client):
    before = {s["id"]: copy.deepcopy(s) for s in shots(client)}
    r = sb(client, [copy.deepcopy(EXAMPLE_RANGE)])
    assert r.status_code == 200, r.text
    assert ids(client) == ["s0001", "s0002", "s0003", "s0004", "s0005", "s0006", "s0011", "s0012", "s0009", "s0010"]
    a, b = shot(client, "s0011"), shot(client, "s0012")
    assert a["start"] == before["s0007"]["start"] and b["start"] == {"w": 154, "off": 0, "text": "word154"}      # the span is covered exactly
    assert (a["technique"], a["slots"], a["intent"]) == ("CAM-01", {"image": {"asset": "C"}}, "explore") and a["source"] == "agent"
    assert b["technique"] == "STATIC-01" and b["slots"] == {"image": {"asset": "B"}} and b["locked"] is False and b["overlays"] == []
    for sid in ("s0001", "s0002", "s0003", "s0004", "s0005", "s0006", "s0009", "s0010"):
        assert shot(client, sid) == before[sid]                                                      # nothing else moved
    assert r.json()["created"]["shots"] == ["s0011", "s0012"] and r.json()["created"]["refs"] == {"first": "s0011"}
    assert r.json()["changes"] == [{"target": {"shot": "s0011"}, "time": "0:49", "what": "Cảnh 7–8: thay bằng 2 cảnh mới"}]


def test_replace_range_with_overlays_and_inherited_slots(client):
    r = sb(client, [{"op": "replace_range", "from_shot": "s0004", "to_shot": "s0004", "shots": [
        {"technique": "CAM-03", "overlays": [{"technique": "HI-01", "params": {"at": "CENTRE", "rx": 150, "ry": 150}, "dur": 2}]}]}])
    assert r.status_code == 200, r.text
    s = shot(client, "s0011")
    assert s["slots"] == {"image": {"asset": "B"}} and s["start"] == {"w": 62, "off": 0.0, "text": "word62"}         # slots carried from the replaced shot
    assert s["overlays"][0]["id"] == "o3" and s["overlays"][0]["params"]["at"] == "CENTRE"
    assert r.json()["created"]["overlays"] == [{"shot": "s0011", "overlay": "o3"}]
    assert r.json()["changes"][0]["what"] == "Cảnh 4: thay bằng 1 cảnh mới"


@pytest.mark.parametrize("op,code,where", [
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008"}, "invalid_field", ["ops[0].shots"]),
    ({"op": "replace_range", "from_shot": "s0007", "shots": [{"technique": "CAM-01"}]}, "invalid_field", ["ops[0].to_shot"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": []}, "invalid_field", ["ops[0].shots"]),
    ({"op": "replace_range", "from_shot": "s0008", "to_shot": "s0007", "shots": [{"technique": "CAM-01"}]}, "not_consecutive", ["ops[0].to_shot"]),
    ({"op": "replace_range", "from_shot": "s0099", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}]}, "unknown_shot", ["ops[0].from_shot"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "start": {"w": 141}}]}, "span_mismatch",
     ["ops[0].shots[0].start"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}, {"technique": "CAM-03"}]},
     "invalid_field", ["ops[0].shots[1].start"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}, {"technique": "CAM-03", "start": {"w": 139}}]},
     "span_mismatch", ["ops[0].shots[1].start"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}, {"technique": "CAM-03", "start": {"w": 200}}]},
     "span_mismatch", ["ops[0].shots[1].start"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}, {"technique": "CAM-03", "start": {"w": 141}},
                                                                                 {"technique": "CAM-03", "start": {"t": 49.75}}]},
     "span_mismatch", ["ops[0].shots[2].start"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01"}, {"technique": "CAM-03", "start": {"t": 49.5}}]},
     "shot_too_short", ["ops[0].shots[0]"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "NOPE-99"}]}, "unknown_technique", ["ops[0].shots[0].technique"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "HI-01"}]}, "wrong_technique_kind",
     ["ops[0].shots[0].technique"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "slots": {"image": {"asset": "Z9"}}}]},
     "unknown_asset", ["ops[0].shots[0].slots.image.asset"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "params": {"zzz": 1}}]}, "unknown_param",
     ["ops[0].shots[0].params.zzz"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "overlays": [{"technique": "HI-01", "dur": 99}]}]},
     "invalid_field", ["ops[0].shots[0].overlays[0].dur"]),
    ({"op": "replace_range", "from_shot": "s0007", "to_shot": "s0008", "shots": [{"technique": "CAM-01", "extra": 1}]}, "invalid_field",
     ["ops[0].shots[0].extra"]),
])
def test_replace_range_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


# ---------------------------------------------------------------- lock / unlock
def test_lock_and_unlock(client):
    r = sb(client, [{"op": "lock", "shot": "s0003"}])
    assert r.status_code == 200, r.text
    assert shot(client, "s0003")["locked"] is True and shot(client, "s0003")["source"] == "import"                   # a lock is not an edit
    assert r.json()["changes"] == [{"target": {"shot": "s0003"}, "time": "0:17", "what": "Cảnh 3: đã khóa"}]
    u = sb(client, [{"op": "unlock", "shot": "s0003"}])
    assert u.status_code == 200 and shot(client, "s0003")["locked"] is False
    assert u.json()["changes"][0]["what"] == "Cảnh 3: đã mở khóa"


def test_lock_and_unlock_an_overlay(client):
    r = sb(client, [{"op": "lock", "shot": "s0002", "overlay": "o1"}])
    assert r.status_code == 200 and shot(client, "s0002")["overlays"][0]["locked"] is True and shot(client, "s0002")["locked"] is False
    assert r.json()["changes"][0]["what"] == "Cảnh 2: đã khóa lớp phủ " + vi("HI-01")
    refused(client, [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 90}}], 409, "locked", ["ops[0].overlay"])
    refused(client, [{"op": "remove_overlay", "shot": "s0002", "overlay": "o1"}], 409, "locked", ["ops[0].overlay"])
    refused(client, [{"op": "set_overlay", "shot": "s0002", "overlay": "o1", "dur": 2}], 409, "locked", ["ops[0].overlay"])
    refused(client, [{"op": "lock", "shot": "s0002", "overlay": "o1"}], 409, "locked", ["ops[0].overlay"])
    assert sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o2", "params": {"radius": 150}}]).status_code == 200           # o2 is free
    assert sb(client, [{"op": "unlock", "shot": "s0002", "overlay": "o1"}]).status_code == 200
    assert sb(client, [{"op": "set_params", "shot": "s0002", "overlay": "o1", "params": {"rx": 90}}]).status_code == 200


def test_unlocking_what_is_not_locked_changes_nothing(client):
    r = sb(client, [{"op": "unlock", "shot": "s0003"}])
    assert r.status_code == 200 and r.json()["batch"] is None and r.json()["changes"] == [] and r.json()["applied"] == 1


@pytest.mark.parametrize("op,code,where", [
    ({"op": "lock"}, "invalid_field", ["ops[0].shot"]),
    ({"op": "lock", "shot": "s0099"}, "unknown_shot", ["ops[0].shot"]),
    ({"op": "lock", "shot": "s0002", "overlay": "o9"}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "unlock", "shot": "s0099"}, "unknown_shot", ["ops[0].shot"]),
    ({"op": "unlock", "shot": "s0002", "overlay": "o9"}, "unknown_overlay", ["ops[0].overlay"]),
    ({"op": "unlock", "shot": "s0002", "overlay": 1}, "invalid_field", ["ops[0].overlay"]),
])
def test_lock_wrong_fields(client, op, code, where):
    refused(client, [op], 422, code, where)


# ---------------------------------------------------------------- a locked shot refuses everything but unlock, whoever sends it
LOCKED = [
    ({"op": "set_technique", "shot": "s0006", "technique": "CAM-03"}, "ops[0].shot"),
    ({"op": "set_params", "shot": "s0006", "params": {"shadow": False}}, "ops[0].shot"),
    ({"op": "set_slot", "shot": "s0006", "slot": "image", "asset": "A"}, "ops[0].shot"),
    ({"op": "add_overlay", "shot": "s0006", "technique": "HI-01"}, "ops[0].shot"),
    ({"op": "set_overlay", "shot": "s0006", "overlay": "o1", "dur": 2}, "ops[0].shot"),
    ({"op": "remove_overlay", "shot": "s0006", "overlay": "o1"}, "ops[0].shot"),
    ({"op": "split_shot", "shot": "s0006", "at": 42}, "ops[0].shot"),
    ({"op": "merge_shots", "shots": ["s0005", "s0006"]}, "ops[0].shots[1]"),
    ({"op": "merge_shots", "shots": ["s0006", "s0007"]}, "ops[0].shots[0]"),
    ({"op": "move_boundary", "shot": "s0006", "to": 40}, "ops[0].shot"),
    ({"op": "move_boundary", "shot": "s0007", "to": 52}, "ops[0].shot"),
    ({"op": "replace_range", "from_shot": "s0005", "to_shot": "s0007", "shots": [{"technique": "CAM-01"}]}, "ops[0].from_shot"),
    ({"op": "lock", "shot": "s0006"}, "ops[0].shot"),
]


@pytest.mark.parametrize("op,where", LOCKED, ids=[o["op"] + ("-" + o.get("shot", "") if o["op"] in ("move_boundary",) else "") for o, _ in LOCKED])
@pytest.mark.parametrize("actor", ["human", "agent:some-model", "cli:bti"])
def test_a_locked_shot_refuses_every_operation_but_unlock(client, op, where, actor):
    r = refused(client, [op], 409, "locked", [where], actor=actor)
    assert r.json()["op_index"] == 0 and "unlock" in r.json()["fix"] and r.json()["retry"] == "after_fix"


def test_unlock_is_accepted_on_a_locked_shot_and_then_everything_is(client):
    r = sb(client, [{"op": "unlock", "shot": "s0006"}, {"op": "set_params", "shot": "s0006", "params": {"shadow": False}}])
    assert r.status_code == 200, r.text
    assert shot(client, "s0006")["locked"] is False and shot(client, "s0006")["params"]["shadow"] is False
    refused(client, [{"op": "remove_overlay", "shot": "s0006", "overlay": "o1"}], 409, "locked", ["ops[0].overlay"])           # its overlay stays locked
    assert sb(client, [{"op": "unlock", "shot": "s0006", "overlay": "o1"}, {"op": "remove_overlay", "shot": "s0006", "overlay": "o1"}]).status_code == 200


# ---------------------------------------------------------------- out of scope
SCOPED = [
    ({"op": "set_technique", "shot": "s0004", "technique": "CAM-03"}, "ops[0].shot"),
    ({"op": "set_params", "shot": "s0004", "params": {"shadow": False}}, "ops[0].shot"),
    ({"op": "set_slot", "shot": "s0004", "slot": "image", "asset": "C"}, "ops[0].shot"),
    ({"op": "add_overlay", "shot": "s0004", "technique": "HI-01"}, "ops[0].shot"),
    ({"op": "set_overlay", "shot": "s0004", "overlay": "o1", "dur": 2}, "ops[0].shot"),
    ({"op": "remove_overlay", "shot": "s0004", "overlay": "o1"}, "ops[0].shot"),
    ({"op": "split_shot", "shot": "s0004", "at": 26}, "ops[0].shot"),
    ({"op": "merge_shots", "shots": ["s0004", "s0005"]}, "ops[0].shots[0]"),
    ({"op": "move_boundary", "shot": "s0004", "to": 25}, "ops[0].shot"),
    ({"op": "replace_range", "from_shot": "s0004", "to_shot": "s0005", "shots": [{"technique": "CAM-01"}]}, "ops[0].from_shot"),
    ({"op": "lock", "shot": "s0004"}, "ops[0].shot"),
    ({"op": "unlock", "shot": "s0004"}, "ops[0].shot"),
]


@pytest.mark.parametrize("op,where", SCOPED, ids=[o["op"] for o, _ in SCOPED])
def test_an_operation_outside_the_scope_refuses_the_whole_batch(client, op, where):
    ok = {"op": "set_params", "shot": "s0002", "params": {"shadow": False}}                          # inside the scope: must not be applied either
    before = snapshot(client.pdir)
    r = sb(client, [ok, op], scope={"shots": ["s0002"]})
    assert r.status_code == 422 and r.json()["code"] == "out_of_scope" and r.json()["op_index"] == 1, r.text
    assert paths(r) == [where.replace("ops[0]", "ops[1]")]
    assert snapshot(client.pdir) == before


def test_scope_by_chapter_and_by_beat(client):
    # the chapter "THE ROOM" (c02) holds the shots that start from 28.4 s to 59.85 s: s0005, s0006, s0007, s0008
    assert sb(client, [{"op": "lock", "shot": "s0007"}], scope={"chapters": ["c02"]}).status_code == 200
    r = refused(client, [{"op": "lock", "shot": "s0004"}], 422, "out_of_scope", ["ops[0].shot"], scope={"chapters": ["c02"]})
    assert r.json()["fields"][0]["allowed"] == ["s0005", "s0006", "s0007", "s0008"]
    # the beat b0003 (28.4 s to 42.6 s) holds s0005 and s0006
    assert sb(client, [{"op": "lock", "shot": "s0005"}], scope={"beats": ["b0003"]}).status_code == 200
    refused(client, [{"op": "lock", "shot": "s0007"}], 422, "out_of_scope", ["ops[0].shot"], scope={"beats": ["b0003"]})


def test_a_shot_made_in_a_scope_is_in_the_scope(client):
    r = sb(client, [{"op": "split_shot", "shot": "s0004", "at": 26.0, "ref": "tail"}, {"op": "set_params", "shot": "$tail", "params": {"shadow": False}}],
           scope={"shots": ["s0004"]})
    assert r.status_code == 200, r.text
    r = sb(client, [{"op": "replace_range", "from_shot": "s0009", "to_shot": "s0009", "shots": [{"technique": "STATIC-01", "ref": "n"}]},
                    {"op": "set_params", "shot": "$n", "params": {"shadow": False}}], scope={"shots": ["s0009"]})
    assert r.status_code == 200, r.text
    assert shot(client, "s0011")["params"]["shadow"] is False


def test_a_scope_that_names_nothing_real_is_an_invalid_request(client):
    r = refused(client, [{"op": "lock", "shot": "s0003"}], 422, "invalid_request", ["scope.shots[0]"], scope={"shots": ["s0777"]})
    assert r.json()["fields"][0]["allowed"] == ["s%04d" % i for i in range(1, 11)]
    refused(client, [{"op": "lock", "shot": "s0003"}], 422, "invalid_request", ["scope.chapters[0]"], scope={"chapters": ["c77"]})
    refused(client, [{"op": "lock", "shot": "s0003"}], 422, "invalid_request", ["scope.beats[0]"], scope={"beats": ["b0777"]})


# ---------------------------------------------------------------- who wrote it
@pytest.mark.parametrize("actor,source", [("human", "human"), ("agent:gemini-3.8-flash", "agent"), ("cli:bti", "agent")])
def test_the_actor_decides_the_source_of_what_a_batch_writes(client, actor, source):
    r = sb(client, [{"op": "set_params", "shot": "s0004", "params": {"shadow": False}}], actor=actor)
    assert r.status_code == 200 and shot(client, "s0004")["source"] == source
