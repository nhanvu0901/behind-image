import copy

import pytest

from bti.engine import storyboard as SB
from conftest import base_storyboard


def issues_for(p, sb):
    return p.validate(sb)


def errors(issues):
    return [i for i in issues if i["level"] == "error"]


def find(issues, path_part, msg_part=""):
    return [i for i in issues if path_part in i["path"] and msg_part in i["message"]]


def test_base_storyboard_is_valid(tiny_project):
    assert errors(tiny_project.validate()) == []


def test_unknown_technique(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["technique"] = "CAM-99"
    e = find(tiny_project.validate(sb), "shots[0].technique", "unknown technique")
    assert e and e[0]["level"] == "error"


def test_unknown_overlay_technique(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["overlays"][0]["technique"] = "HI-99"
    assert find(tiny_project.validate(sb), "overlays[0].technique", "unknown technique")


def test_unknown_parameter(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["overlays"][0]["params"]["glow"] = 1
    e = find(tiny_project.validate(sb), "overlays[0].params.glow", "unknown parameter")
    assert e and e[0]["level"] == "error"
    sb = base_storyboard()
    sb["shots"][1]["params"]["colour"] = "red"
    assert find(tiny_project.validate(sb), "shots[1].params.colour", "unknown parameter")


def test_parameter_type_and_range(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["overlays"][0]["params"]["floor"] = 3
    sb["shots"][0]["overlays"][1]["params"]["color"] = "red"
    iss = tiny_project.validate(sb)
    assert find(iss, "params.floor", "<= 1")
    assert find(iss, "params.color", "#rrggbb")


def test_required_parameter_missing(tiny_project):
    sb = base_storyboard()
    del sb["shots"][0]["overlays"][0]["params"]["rx"]
    assert find(tiny_project.validate(sb), "params.rx", "required")


def test_overlay_outside_its_shot(tiny_project):
    sb = base_storyboard()
    o = sb["shots"][0]["overlays"][2]
    o["start"] = {"t": 5.0}                       # shot 0 spans 0 .. 6.0 (word 12 at 6.0): ends after the shot
    o["dur"] = 3.0
    iss = tiny_project.validate(sb)
    assert find(iss, "shots[0].overlays[2]", "ends outside its shot")
    o["start"] = {"t": 7.0}
    assert find(tiny_project.validate(sb), "overlays[2].start", "outside its shot")


def test_overlay_must_not_use_rel(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["overlays"][2]["start"] = {"rel": 0.2}
    assert find(tiny_project.validate(sb), "overlays[2].start", "rel")


def test_stale_anchor_text(tiny_project):
    sb = base_storyboard()
    sb["shots"][1]["start"]["text"] = "something else"
    e = find(tiny_project.validate(sb), "shots[1].start", "does not match")
    assert e and e[0]["level"] == "error"
    sb = base_storyboard()
    sb["shots"][0]["overlays"][0]["start"]["text"] = "zzz"
    assert find(tiny_project.validate(sb), "overlays[0].start", "does not match")
    sb = base_storyboard()
    sb["shots"][0]["params"]["camera"][1]["at"] = {"w": 5, "text": "wrong"}
    assert find(tiny_project.validate(sb), "params.camera[1].at", "does not match")


def test_shot_shorter_than_min(tiny_project):
    sb = base_storyboard()
    sb["shots"][1]["start"] = {"t": 5.9}
    sb["shots"][2]["start"] = {"t": 6.05}         # shot 1 lasts 0.15 s
    e = find(tiny_project.validate(sb), "shots[1]", "shorter than 0.2")
    assert e and e[0]["level"] == "error"
    sb["shots"][2]["start"] = {"t": 6.2}
    assert not find(tiny_project.validate(sb), "shots[1]", "shorter")


def test_shots_out_of_order_and_end(tiny_project):
    sb = base_storyboard()
    sb["shots"][2]["start"] = {"t": 3.0}
    assert find(tiny_project.validate(sb), "shots[2].start", "time order")
    sb = base_storyboard()
    sb["end"] = {"t": 8.0}
    assert find(tiny_project.validate(sb), "end", "not after")


def test_slots_and_assets(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["slots"] = {"image": {"asset": "NOPE"}}
    assert find(tiny_project.validate(sb), "slots.image.asset", "not defined")
    sb = base_storyboard()
    sb["shots"][0]["slots"] = {}
    assert find(tiny_project.validate(sb), "shots[0].slots", "required slot")
    sb = base_storyboard()
    sb["shots"][0]["slots"]["bogus"] = {"asset": "A"}
    assert find(tiny_project.validate(sb), "slots.bogus", "unknown slot")


def test_region_must_exist(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["overlays"][0]["params"]["at"] = "NOWHERE"
    assert find(tiny_project.validate(sb), "overlays[0].params.at", "not defined")


def test_camera_keys_must_increase(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["params"]["camera"][1]["at"] = {"rel": 0.0}
    assert find(tiny_project.validate(sb), "params.camera[1].at", "increasing")
    sb = base_storyboard()
    sb["shots"][0]["params"]["camera"][0]["ease"] = "wobble"
    assert find(tiny_project.validate(sb), "camera[0].ease", "unknown ease")


def test_unavailable_technique_is_an_error(tiny_project, monkeypatch):
    monkeypatch.setitem(tiny_project.bundle.spec("CMP-01")["engine"], "available", False)      # synthetic unavailable entry
    sb = base_storyboard()
    sb["shots"][2]["technique"] = "CMP-01"
    e = find(tiny_project.validate(sb), "shots[2].technique", "not available")
    assert e and e[0]["level"] == "error"


def test_technique_kind_must_match_position(tiny_project):
    sb = base_storyboard()
    sb["shots"][0]["technique"] = "HI-01"                     # overlay used as a shot
    assert find(tiny_project.validate(sb), "shots[0].technique", "needs kind base or card")
    sb = base_storyboard()
    sb["shots"][2]["transition_in"]["technique"] = "CAM-05"
    assert find(tiny_project.validate(sb), "transition_in.technique", "not a transition")


def test_transition_checks(tiny_project):
    sb = base_storyboard()
    sb["shots"][2]["transition_in"]["dur"] = 50
    assert find(tiny_project.validate(sb), "transition_in.dur", "longer than the shot")


def test_missing_asset_file(tiny_project):
    sb = base_storyboard()
    sb["assets"]["A"]["file"] = "media/missing.jpg"
    assert find(tiny_project.validate(sb), "assets.A.file", "does not exist")


def test_resolve_adds_derived_times(tiny_project):
    r = tiny_project.resolve()
    s0, s1, s2 = r["shots"]
    assert (s0["_t0"], s0["_t1"]) == (0.0, 6.0) and s1["_t0"] == 6.0 and s2["_t1"] == 19.0
    o = s0["overlays"][1]
    assert o["start"]["_t"] == pytest.approx(2.1) and o["_t1"] == pytest.approx(5.1)
    assert s0["params"]["camera"][1]["at"]["_t"] == 6.0
    assert "_t0" not in tiny_project.storyboard()["shots"][0]       # the saved document stays unresolved
