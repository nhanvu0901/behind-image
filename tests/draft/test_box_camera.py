"""Tests for worker boxcam: one frame rule, model spec (`region`, `from`, refused `params.camera`), 5 camera moves,
early arrival, no-race rule, 3 keys through `storyboard.retime` + tempo change, helpers, and stored storyboards."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bti.draft import camera as CAM
from bti.draft import decompile as D
from bti.draft import retime as RT
from bti.draft import spec as S
from bti.draft import workspace as W
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import DraftInputs, clone_inputs, load_inputs
from bti.draft.providers import auto
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing
from bti.media import contentbox as CB
from helpers import GOOD, _image, clean_spec, shot, spec

REPO = Path(__file__).resolve().parents[2]


# ----------------------------------------------------------------------------------------------------------------- 1. Frame rule
def test_frame_rule_large_small_edge_small_picture_and_extra_fields():
    w, h = 3840.0, 5253.0
    # Large region (1200 x 1200): height limit reached first -> 62% of frame height (1080), frame narrower than painting width
    big = {"x": 2000.0, "y": 2500.0, "rx": 600.0, "ry": 600.0}
    cx, cy, z = VC.region_frame(big, w, h)
    assert (cx, cy) == (2000.0, 2500.0)
    assert z == pytest.approx(VC.FRAME_FILL * 1080.0 / 1200.0, abs=1e-4)
    info_big = VC.region_frame_info(big, w, h)
    assert info_big["height_share"] == pytest.approx(VC.FRAME_FILL, abs=1e-3) and info_big["needs_spotlight"] is False

    # Tight small carved-woman region: capped at SHARP_ZOOM (2.0), stays < 40% of width & height -> HI-01 takes over
    woman = {"x": 2472.0, "y": 1041.5, "rx": 47.0, "ry": 107.5, "tight": True, "thing": "carved woman", "rough": False}
    info_w = VC.region_frame_info(woman, w, h)
    assert info_w["zoom"] == pytest.approx(VC.SHARP_ZOOM, abs=1e-4)
    assert info_w["width_share"] < VC.SMALL_ON_SCREEN and info_w["height_share"] < VC.SMALL_ON_SCREEN
    assert info_w["needs_spotlight"] is True

    # Region at edge of painted surface (`content_box`): kept inside box and holds the region
    box = (60.0, 80.0, 740.0, 1120.0)
    edge = {"x": 100.0, "y": 120.0, "rx": 40.0, "ry": 40.0}
    ex, ey, ez = VC.region_frame(edge, 800.0, 1200.0, box)
    assert CB.outside_share(box, ex, ey, ez) <= CB.OFF_LIMIT
    assert VC.box_inside_frame(VC.region_box(edge), ex, ey, ez)[0]
    assert ez <= VC.SHARP_ZOOM

    # Small stored picture (< 1000 px long side): held to SMALL_PICTURE_MAX_ZOOM (2.0) even with larger sharp_zoom
    small_reg = {"x": 300.0, "y": 200.0, "rx": 30.0, "ry": 30.0}
    sx, sy, sz = VC.region_frame(small_reg, 600.0, 400.0, sharp_zoom=3.0)
    assert sz <= VC.SMALL_PICTURE_MAX_ZOOM + 1e-6


def test_small_picture_end_frame_keeps_room_for_the_beats_drift():
    """800 x 1200 picture: the tight fit of a region would pass the sharp limit, so the frame stays in the matte band WITH room: the 3 % drift the identity gives
    the channel-name beat after it (`BRAND_PUSH`) must not leave the band (the compiler would tighten it past the limit, and a retime would put it back)."""
    reg = {"x": 400.0, "y": 300.0, "rx": 60.0, "ry": 60.0, "label": "Mirror"}
    box = (0.0, 0.0, 800.0, 1200.0)
    cx, cy, z = VC.region_frame(reg, 800.0, 1200.0, box)
    assert z <= VC.SMALL_PICTURE_MAX_ZOOM
    for push in (1.0, 1.03, 1.04):
        assert CB.outside_share(box, cx, cy, z * push) <= CB.OFF_LIMIT, push
    assert VC.box_inside_frame(VC.region_box(reg), cx, cy, z)[0]


def test_extra_region_fields_pass_through_spec_and_workspace(proj, tmp_path):
    p = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    p["assets"]["A"]["regions"]["MIRROR"].update({"tight": True, "thing": "round mirror", "rough": False})
    (proj / "picks.json").write_text(json.dumps(p), encoding="utf-8")
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    assets_in = json.loads((ws.root / "inputs" / "assets.json").read_text(encoding="utf-8"))
    m = assets_in["assets"]["A"]["regions"]["MIRROR"]
    assert m["tight"] is True and m["thing"] == "round mirror" and m["rough"] is False

    clean, probs = S.regions_problems(
        {"A": {"CARVING": {"x": 200, "y": 300, "rx": 40, "ry": 60, "label": "Carving", "tight": True, "thing": "carving"}}},
        load_inputs(proj).picks["assets"],
    )
    assert not [x for x in probs if x["level"] == "error"]
    assert clean["A"]["CARVING"]["tight"] is True and clean["A"]["CARVING"]["thing"] == "carving"


# ----------------------------------------------------------------------------------------------------------------- 2. `from` and `params.camera`
def _add_two_regions(proj):
    p = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    p["assets"]["A"]["regions"].update({
        "DOG": {"x": 260, "y": 980, "rx": 60, "ry": 60, "label": "Dog"},
        "HANDS": {"x": 400, "y": 600, "rx": 70, "ry": 70, "label": "Joined hands"},
    })
    (proj / "picks.json").write_text(json.dumps(p), encoding="utf-8")


def test_from_previous_whole_region_absent_and_cutaway_reset(proj):
    _add_two_regions(proj)
    inp = load_inputs(proj)
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-05", slots={"image": {"asset": "A", "region": "DOG"}}),                         # no previous main shot -> whole
            shot("b0002", 10, "CAM-05", slots={"image": {"asset": "A", "region": "MIRROR"}}),                      # omitted `from` -> previous (DOG end)
            shot("b0003", 20, "CAM-05", **{"from": "whole"}, slots={"image": {"asset": "A", "region": "HANDS"}}),  # explicit "whole"
        ), "c01"),
        "c02": clean_spec(spec(
            "c02",
            shot("b0004", 30, "X-LAY-01", slots={"image": {"asset": "B"}}),                                        # cutaway resets prev_main_frame
            shot("b0005", 40, "CAM-05", slots={"image": {"asset": "A", "region": "DOG"}}),                         # after cutaway: starts on whole
            shot("b0006", 50, "CAM-05", **{"from": "MIRROR"}, slots={"image": {"asset": "A", "region": "HANDS"}}), # explicit region
        ), "c02"),
    }
    res = compile_specs(inp, sp, draw=False, identity=False)
    assert not res.errors, summary_text(res)
    sh = [s for s in res.storyboard["shots"] if s.get("source") == "agent" and s.get("technique") != "X-CARD-01"]
    whole_pose = VC.whole_painting_frame(800, 1200)
    dog_end = VC.region_frame(inp.picks["assets"]["A"]["regions"]["DOG"], 800, 1200)
    mirror_end = VC.region_frame(inp.picks["assets"]["A"]["regions"]["MIRROR"], 800, 1200)
    # Shot 0 starts on whole, ends on DOG
    assert sh[0]["params"]["camera"][0]["zoom"] == pytest.approx(whole_pose[2], abs=1e-4)
    # Shot 1 (from omitted -> previous) starts where shot 0 ended (DOG)
    assert (sh[1]["params"]["camera"][0]["cx"], sh[1]["params"]["camera"][0]["cy"]) == (sh[0]["params"]["camera"][-1]["cx"], sh[0]["params"]["camera"][-1]["cy"])
    assert sh[1]["params"]["camera"][0]["cy"] == pytest.approx(dog_end[1], abs=5.0)
    # Shot 2 (from="whole") starts on whole even though shot 1 was main painting
    assert sh[2]["params"]["camera"][0]["zoom"] == pytest.approx(whole_pose[2], abs=1e-4)
    # Shot 4 (after cutaway shot 3 on B) resets to whole
    assert sh[4]["params"]["camera"][0]["zoom"] == pytest.approx(whole_pose[2], abs=1e-4)
    # Shot 5 (from="MIRROR") starts at MIRROR frame
    assert (sh[5]["params"]["camera"][0]["cx"], sh[5]["params"]["camera"][0]["cy"]) == pytest.approx(mirror_end[:2], abs=1.0)


def test_unknown_from_region_is_refused(proj):
    inp = load_inputs(proj)
    sp = {c: clean_spec(s, c) for c, s in GOOD.items()}
    sp["c01"]["shots"][1]["from"] = "NO_SUCH_SPOT"
    res = compile_specs(inp, sp, draw=False, identity=False)
    assert any(i["code"] == "from_unknown_region" and i["field"] == "from" for i in res.errors)


def test_params_camera_refused_on_main_painting_and_accepted_on_other_picture(proj):
    inp = load_inputs(proj)
    sp = {c: clean_spec(s, c) for c, s in GOOD.items()}
    sp["c01"]["shots"][0]["params"] = {"camera": [
        {"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.9, "ease": "linear"},
        {"at": {"rel": 1.0}, "cx": 400, "cy": 500, "zoom": 1.1, "ease": "linear"},
    ]}
    # Valid range on outside image B is accepted
    sp["c02"]["shots"][0]["params"] = {"camera": [
        {"at": {"rel": 0.0}, "cx": 300, "cy": 200, "zoom": 1.7, "ease": "linear"},
        {"at": {"rel": 1.0}, "cx": 300, "cy": 200, "zoom": 1.9, "ease": "linear"},
    ]}
    res = compile_specs(inp, sp, draw=False, identity=False)
    bad = [i for i in res.errors if i["code"] == "camera_not_allowed"]
    assert len(bad) == 1 and bad[0]["chapter"] == "c01" and bad[0]["shot"] == 1 and bad[0]["field"] == "params.camera"
    assert "out/regions.json" in bad[0]["message"] and "./crop" in bad[0]["message"]
    b_shot = next(s for s in res.storyboard["shots"] if (s.get("slots") or {}).get("image", {}).get("asset") == "B")
    assert [k["zoom"] for k in b_shot["params"]["camera"]] == [1.7, 1.9]


# ----------------------------------------------------------------------------------------------------------------- 3. Moves, early arrival, no race
def test_all_five_offered_camera_techniques_and_early_arrival(proj):
    inp = load_inputs(proj)
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "STATIC-01", slots={"image": {"asset": "A"}}),
            shot("b0002", 10, "CAM-05", **{"from": "whole"}, slots={"image": {"asset": "A", "region": "MIRROR"}},
                 overlays=[{"technique": "HI-01", "start_word": 16, "dur": 2.0, "params": {"at": "MIRROR"}}]),
            shot("b0003", 20, "CAM-03", **{"from": "MIRROR"}, slots={"image": {"asset": "A"}}),
        ), "c01"),
        "c02": clean_spec(spec(
            "c02",
            shot("b0004", 30, "CAM-04", slots={"image": {"asset": "A", "region": "MIRROR"}}),
            shot("b0005", 40, "CAM-01", slots={"image": {"asset": "A", "region": "MIRROR"}}),
            shot("b0006", 50, "CAM-05", **{"from": "whole"}, slots={"image": {"asset": "A", "region": "MIRROR"}}),  # no overlay -> 45%
        ), "c02"),
    }
    res = compile_specs(inp, sp, draw=False, identity=False)
    assert not res.errors, summary_text(res)
    assert not [i for i in res.issues if i["code"] in ("camera_off_region", "thing_arrives_late", "frame_off_painting")], summary_text(res)

    sh = [s for s in res.storyboard["shots"] if s.get("source") == "agent" and s.get("technique") != "X-CARD-01"]
    starts = [tm.resolve(s["start"]) for s in res.storyboard["shots"]]
    ends = starts[1:] + [tm.resolve(res.storyboard["end"])]
    by_sid = {s["id"]: (s, a, b) for s, a, b in zip(res.storyboard["shots"], starts, ends)}

    # With spotlight starting at w16 -> arrives at <= w16 - 0.3s using 3 keys
    s_hi, a_hi, b_hi = by_sid[sh[1]["id"]]
    cams_hi = s_hi["params"]["camera"]
    assert len(cams_hi) == 3 and cams_hi[0]["ease"] == "inout_cubic"
    t_arr_hi = a_hi + cams_hi[1]["at"]["rel"] * (b_hi - a_hi)
    assert t_arr_hi <= tm.word_start(16) - 0.30 + 0.02

    # A repeated region holds the previous shot even with an explicit from="whole".
    cams_no = sh[5]["params"]["camera"]
    previous = sh[4]["params"]["camera"][-1]
    assert all(tuple(k[f] for f in ("cx", "cy", "zoom")) == tuple(previous[f] for f in ("cx", "cy", "zoom")) for k in cams_no)

    # Pull-back CAM-03 ends at whole-painting zoom (wider than start)
    s_pull = by_sid[sh[2]["id"]][0]
    assert s_pull["params"]["camera"][0]["zoom"] > s_pull["params"]["camera"][-1]["zoom"]


def test_no_race_fallback_when_travel_exceeds_speed_limit():
    asset = {
        "width": 3840, "height": 5253,
        "regions": {
            "GARGOYLE": {"x": 2240.0, "y": 2025.0, "rx": 47.0, "ry": 76.0, "label": "Gargoyles"},
            "WOMAN": {"x": 2472.0, "y": 1041.5, "rx": 47.0, "ry": 107.5, "label": "Carved woman"},
        },
    }
    garg_pose = VC.region_frame(asset["regions"]["GARGOYLE"], 3840, 5253)
    # 1010 px distance (~1.05 fw at zoom 2.0) over 4.5s shot (arriving by 45% = 2.02s -> 0.52 fw/s > MAX_TRAVEL_SPEED 0.35 fw/s)
    keys = CAM.build_main_camera("CAM-05", "WOMAN", "previous", asset, None, garg_pose, 0.0, 4.5)
    assert len(keys) == 2
    assert keys[0]["cx"] == pytest.approx(2472.0, abs=0.5) and keys[0]["cy"] == pytest.approx(1041.5, abs=0.5)
    assert keys[0]["zoom"] < keys[-1]["zoom"] <= VC.SHARP_ZOOM
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["WOMAN"]), keys[0]["cx"], keys[0]["cy"], keys[0]["zoom"])[0]


def test_zoom_rate_limit_both_directions():
    import math
    asset = {
        "width": 3840, "height": 5253,
        "regions": {
            "WOMAN": {"x": 2472.0, "y": 1041.5, "rx": 47.0, "ry": 107.5, "label": "Carved woman"},
            "COUPLE": {"x": 1920.0, "y": 2626.5, "rx": 800.0, "ry": 1000.0, "label": "The couple"},
        },
    }
    whole = VC.whole_painting_frame(3840, 5253)
    woman_pose = VC.region_frame(asset["regions"]["WOMAN"], 3840, 5253)

    # 1a. Zoom-in exceeding ZOOM_RATE_MAX (1.0 oct/s): whole (0.1963) -> WOMAN (2.0) in 4.51 s (t_arr=2.03 s -> 1.65 oct/s, sideways 0.27 fw/s <= 0.35)
    keys_in_fast = CAM.build_main_camera("CAM-05", "WOMAN", "whole", asset, None, None, 0.0, 4.51)
    assert len(keys_in_fast) == 2
    assert keys_in_fast[0]["cx"] == pytest.approx(woman_pose[0], abs=0.5) and keys_in_fast[0]["cy"] == pytest.approx(woman_pose[1], abs=0.5)
    assert keys_in_fast[0]["zoom"] < keys_in_fast[-1]["zoom"] <= VC.SHARP_ZOOM
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["WOMAN"]), keys_in_fast[0]["cx"], keys_in_fast[0]["cy"], keys_in_fast[0]["zoom"])[0]

    # 1b. Zoom-in within ZOOM_RATE_MAX: same whole -> WOMAN over 8.5 s (t_arr=3.825 s -> 0.876 oct/s <= 1.0, sideways 0.14 fw/s <= 0.35) travels in 3 keys
    keys_in_ok = CAM.build_main_camera("CAM-05", "WOMAN", "whole", asset, None, None, 0.0, 8.5)
    assert len(keys_in_ok) == 3
    assert keys_in_ok[0]["zoom"] == pytest.approx(whole[2], abs=1e-4)
    assert keys_in_ok[1]["at"]["rel"] <= 0.45 + 1e-4

    # 2. Zoom-out via CAM-05 exceeding ZOOM_RATE_MAX: WOMAN (2.0) -> COUPLE (filling zoom 0.50) in 3.5 s (t_arr=1.575 s -> 1.27 oct/s) cuts to COUPLE without black bars
    couple_pose = VC.region_frame(asset["regions"]["COUPLE"], 3840, 5253)
    assert couple_pose[2] == pytest.approx(VC.cover_zoom(3840, 5253), abs=1e-4)
    keys_out_fast = CAM.build_main_camera("CAM-05", "COUPLE", "WOMAN", asset, None, woman_pose, 0.0, 3.5)
    assert len(keys_out_fast) == 2
    assert keys_out_fast[0]["cx"] == pytest.approx(couple_pose[0], abs=0.5) and keys_out_fast[0]["cy"] == pytest.approx(couple_pose[1], abs=0.5)
    assert keys_out_fast[0]["zoom"] == pytest.approx(couple_pose[2], abs=1e-4)
    assert keys_out_fast[-1]["zoom"] >= couple_pose[2] - 1e-4

    # 3a. CAM-03 pulling back to whole painting over 2.0 s: full jump (2.0 -> 0.1963) would be 1.67 oct/s, so it starts nearer and stays <= ZOOM_RATE_MAX
    keys_pull_2s = CAM.build_main_camera("CAM-03", None, "WOMAN", asset, None, woman_pose, 0.0, 2.0)
    assert len(keys_pull_2s) == 2
    assert whole[2] < keys_pull_2s[0]["zoom"] < woman_pose[2]
    assert keys_pull_2s[-1]["zoom"] == pytest.approx(whole[2], abs=1e-4)
    rate_2s = abs(math.log2(keys_pull_2s[-1]["zoom"] / keys_pull_2s[0]["zoom"])) / 2.0
    assert rate_2s <= CAM.ZOOM_RATE_MAX + 1e-6
    assert CB.outside_share((0.0, 0.0, 3840.0, 5253.0), keys_pull_2s[0]["cx"], keys_pull_2s[0]["cy"], keys_pull_2s[0]["zoom"]) <= CB.OFF_LIMIT

    # 3b. CAM-03 pull-back over 1.2 s (near MATTE_RATIO band): still obeys ZOOM_RATE_MAX and stays inside painted box
    keys_pull_12s = CAM.build_main_camera("CAM-03", None, "WOMAN", asset, None, woman_pose, 0.0, 1.2)
    rate_12s = abs(math.log2(keys_pull_12s[-1]["zoom"] / keys_pull_12s[0]["zoom"])) / 1.2
    assert rate_12s <= CAM.ZOOM_RATE_MAX + 1e-6
    assert CB.outside_share((0.0, 0.0, 3840.0, 5253.0), keys_pull_12s[0]["cx"], keys_pull_12s[0]["cy"], keys_pull_12s[0]["zoom"]) <= CB.OFF_LIMIT

    # 3c. CAM-03 pull-back over 6.0 s (0.56 oct/s <= 1.0): keeps full start pose at WOMAN zoom 2.0
    keys_pull_6s = CAM.build_main_camera("CAM-03", None, "WOMAN", asset, None, woman_pose, 0.0, 6.0)
    assert keys_pull_6s[0]["zoom"] == pytest.approx(woman_pose[2], abs=1e-4)

    # 4. CAM-03 pulling back to a wider region (COUPLE) faster than ZOOM_RATE_MAX falls back to gentle pull on COUPLE
    keys_pull_reg_fast = CAM.build_main_camera("CAM-03", "COUPLE", "WOMAN", asset, None, woman_pose, 0.0, 3.5)
    assert len(keys_pull_reg_fast) == 2
    assert keys_pull_reg_fast[0]["zoom"] == pytest.approx(couple_pose[2] * 1.08, abs=1e-2)
    assert keys_pull_reg_fast[-1]["zoom"] == pytest.approx(couple_pose[2], abs=1e-4)


def test_zoom_rate_limit_alone_with_no_sideways_way_in_both_directions():
    """Only the zoom rate decides here: the previous frame and the end frame have the same centre, so the sideways limit never fires."""
    import math
    cx, cy = 2400.0, 3250.0
    asset = {
        "width": 4800, "height": 6500,
        "regions": {
            "COUPLE": {"x": cx, "y": cy, "rx": 900.0, "ry": 720.0, "label": "The couple"},        # wide end frame (filling zoom ~0.465)
            "FACE": {"x": cx, "y": cy, "rx": 47.0, "ry": 60.0, "label": "A small thing"},          # tight end frame (zoom 2.0, the sharp limit)
        },
    }
    wide = VC.region_frame(asset["regions"]["COUPLE"], 4800, 6500)
    tight = VC.region_frame(asset["regions"]["FACE"], 4800, 6500)
    assert (wide[0], wide[1]) == (cx, cy) and (tight[0], tight[1]) == (cx, cy)
    octaves = abs(math.log2(tight[2] / wide[2]))
    assert octaves > 2.0

    # in (wide -> tight): 3.5 s is too short (arrival at 45% = 1.575 s -> ~1.34 octaves/s): no travel, a start a little wider on the end region
    fast_in = CAM.build_main_camera("CAM-05", "FACE", "previous", asset, None, wide, 0.0, 3.5)
    assert len(fast_in) == 2 and fast_in[0]["zoom"] < fast_in[-1]["zoom"]
    assert fast_in[-1]["zoom"] / fast_in[0]["zoom"] < 1.2 and fast_in[0]["zoom"] > wide[2] * 3.0
    # the same move over 8 s (arrival at 3.6 s -> under 1 octave/s): it travels, with three keys, and the travel stays within the limit
    slow_in = CAM.build_main_camera("CAM-05", "FACE", "previous", asset, None, wide, 0.0, 8.0)
    assert len(slow_in) == 3 and slow_in[0]["zoom"] == pytest.approx(wide[2], abs=1e-4)
    assert abs(math.log2(slow_in[1]["zoom"] / slow_in[0]["zoom"])) / (slow_in[1]["at"]["rel"] * 8.0) <= CAM.ZOOM_RATE_MAX + 1e-6

    # out (tight -> wide): the same, the other way; the fallback cuts to the wide end region and pushes in a little (it never pulls back across the whole way)
    fast_out = CAM.build_main_camera("CAM-05", "COUPLE", "previous", asset, None, tight, 0.0, 3.5)
    assert len(fast_out) == 2 and fast_out[0]["zoom"] < fast_out[-1]["zoom"] and fast_out[-1]["zoom"] / fast_out[0]["zoom"] < 1.2
    assert fast_out[-1]["zoom"] == pytest.approx(wide[2], abs=1e-4) and fast_out[0]["zoom"] < tight[2] / 3.0
    slow_out = CAM.build_main_camera("CAM-05", "COUPLE", "previous", asset, None, tight, 0.0, 8.0)
    assert len(slow_out) == 3 and slow_out[0]["zoom"] == pytest.approx(tight[2], abs=1e-4)
    assert abs(math.log2(slow_out[1]["zoom"] / slow_out[0]["zoom"])) / (slow_out[1]["at"]["rel"] * 8.0) <= CAM.ZOOM_RATE_MAX + 1e-6

    # the same limit through CAM-01 (from a region) and CAM-03 (pull back to a wider region)
    assert len(CAM.build_main_camera("CAM-01", "FACE", "COUPLE", asset, None, None, 0.0, 3.5)) == 2
    assert len(CAM.build_main_camera("CAM-03", "COUPLE", "FACE", asset, None, None, 0.0, 3.5)) == 2
    assert len(CAM.build_main_camera("CAM-03", "COUPLE", "FACE", asset, None, None, 0.0, 8.0)) == 3


def test_pull_back_over_a_very_long_shot_does_not_overflow_the_zoom_rate_power():
    asset = {"width": 3840, "height": 5253, "regions": {"WOMAN": {"x": 2472.0, "y": 1041.5, "rx": 47.0, "ry": 107.5, "label": "Carved woman"}}}
    woman_pose = VC.region_frame(asset["regions"]["WOMAN"], 3840, 5253)
    keys = CAM.build_main_camera("CAM-03", None, "WOMAN", asset, None, woman_pose, 0.0, 5000.0)
    assert len(keys) == 2 and keys[0]["zoom"] == pytest.approx(woman_pose[2], abs=1e-4)          # far under the rate limit: the whole way is allowed


def test_a_stored_storyboard_with_hand_written_camera_numbers_still_validates(proj):
    """The page, the typed operations and the engine are untouched: a stored shot on the main painting with round numbers a model wrote still validates
    (no error); the only new thing is what the two checks say about it, as warnings."""
    inp = load_inputs(proj)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    sb = copy.deepcopy(res.storyboard)
    victim = next(s for s in sb["shots"] if s.get("source") == "agent" and (s.get("slots") or {}).get("image", {}).get("asset") == "A" and (s.get("params") or {}).get("camera"))
    victim["params"]["camera"] = [{"at": {"rel": 0.0}, "cx": 300, "cy": 700, "zoom": 1.0, "ease": "linear"},
                                  {"at": {"rel": 1.0}, "cx": 420, "cy": 560, "zoom": 1.4, "ease": "linear"}]
    victim["slots"]["image"]["region"] = "MIRROR"
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    issues = SB.validate(sb, tm, R.load_bundle("gae"), inp.project_dir)
    assert not [i for i in issues if i["level"] == "error"], issues
    assert {i["code"] for i in issues if i["level"] != "error"} <= {"camera_off_region", "thing_arrives_late", "frame_off_painting", "small_detail_not_lit"} | {i["code"] for i in res.warnings}


# ----------------------------------------------------------------------------------------------------------------- 4. Retime & Tempo Change
def test_three_keys_survive_retime_and_tempo_change(tmp_path):
    from intro_helpers import intro_timing, make_project
    tm0 = intro_timing(lead=5.0, title=10.2, spacing=0.5)
    pdir = make_project(tmp_path, tm0)
    inp = load_inputs(pdir)
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A"}}),
            shot("b0002", 10, "CAM-05", **{"from": "whole"}, slots={"image": {"asset": "A", "region": "MIRROR"}}),
        ), "c01"),
        "c02": clean_spec(spec(
            "c02",
            shot("b0003", 20, "CAM-03", **{"from": "MIRROR"}, slots={"image": {"asset": "A"}}),
            shot("b0004", 30, "X-LAY-01", slots={"image": {"asset": "B"}}),
        ), "c02"),
        "c03": clean_spec(spec(
            "c03",
            shot("b0005", 40, "STATIC-01", slots={"image": {"asset": "A"}}),
            shot("b0006", 50, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c03"),
    }
    res = compile_specs(inp, sp, draw=False)
    sb = res.storyboard
    three_id = next(s["id"] for s in sb["shots"] if s.get("technique") == "CAM-05" and len((s.get("params") or {}).get("camera") or []) == 3)

    # Apply 0.8x faster (with shorter lead -> removes opening shot) and 1.25x slower tempo + longer lead
    for lead_val, title_val, spacing in ((1.0, 6.0, 0.4), (6.0, 12.0, 0.625)):
        new_timing = intro_timing(lead=lead_val, title=title_val, spacing=spacing)
        style = R.load_bundle("gae").style
        retimed, rep = RT.retime(sb, new_timing, style, meta={"main_asset": "A"}, defaults=R.load_bundle("gae").param_defaults)
        assert not rep["left"], rep["left"]
        assert RT.off_voice(retimed, new_timing, style, meta={"main_asset": "A"}) == []
        s_after = next(s for s in retimed["shots"] if s["id"] == three_id)
        cams = s_after["params"]["camera"]
        assert [k["at"]["rel"] for k in cams] == sorted([k["at"]["rel"] for k in cams]) and len(cams) == 3
        issues = SB.validate(retimed, Timing(new_timing), R.load_bundle("gae"), pdir)
        assert not [i for i in issues if i["level"] == "error"], issues


# ----------------------------------------------------------------------------------------------------------------- 5. Helpers
def test_helpers_show_computed_end_frame(proj, tmp_path):
    inp = load_inputs(proj)
    ws = W.build(inp, root=tmp_path / "ws")
    for cid, sp in auto.draft(inp).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")}
    env["PYTHONPATH"] = str(REPO)

    r_def = subprocess.run([sys.executable, "-m", "bti.draft.defaults", "CAM-05", "--asset", "A", "--region", "MIRROR", "--from", "whole"],
                           cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r_def.returncode == 0 and "compiler end frame:" in r_def.stdout and "never params.camera" in r_def.stdout, r_def.stdout + r_def.stderr

    r_crop = subprocess.run([sys.executable, "-m", "bti.draft.crop", "--region", "MIRROR", "-o", "look/crop.jpg"],
                            cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r_crop.returncode == 0 and "compiler end frame:" in r_crop.stdout and (ws.root / "look" / "crop.jpg").is_file(), r_crop.stdout + r_crop.stderr

    r_still = subprocess.run([sys.executable, "-m", "bti.draft.still", "--shot", "c01:2", "-o", "look/s2.jpg", "--width", "320"],
                             cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r_still.returncode == 0 and "frame centre" in r_still.stdout and "zoom" in r_still.stdout, r_still.stdout + r_still.stderr


# ----------------------------------------------------------------------------------------------------------------- 6. picks.tighten join2
@pytest.mark.parametrize("action,blocks", [("auto", True), ("tighten", True), ("search", False)])
def test_other_agent_job_covers_picks_auto_and_tighten(action, blocks):
    from bti.draft import run as R
    from bti.draft.inputs import DraftError

    class FakeMgr:
        def active(self, pid, kind):
            return {"id": "j1", "kind": "picks", "meta": {"action": action}} if kind == "picks" else None

    mgr = FakeMgr()
    got = R.other_agent_job("p1", "draft", manager=mgr)
    if blocks:
        assert got and got["id"] == "j1"
        with pytest.raises(DraftError) as exc:
            R.refuse_while_agent_busy("p1", manager=mgr)
        assert exc.value.code == "agent_job_running"
    else:
        assert got is None
        R.refuse_while_agent_busy("p1", manager=mgr)
