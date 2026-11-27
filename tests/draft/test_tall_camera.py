"""Tests for worker tallcam: filling-zoom floor, tall/wide oversized region travel, head-end framing, and CAM-03/cutaway defaults."""
from __future__ import annotations

import math

from bti.draft import camera as CAM
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing
from bti.media import contentbox as CB


def _arnolfini_asset():
    return {
        "width": 3840,
        "height": 5253,
        "regions": {
            "FULL_UPPER": {"x": 1920, "y": 1300, "rx": 1920, "ry": 1080, "label": "Upper band"},
            "FULL_MIDDLE": {"x": 1920, "y": 2600, "rx": 1920, "ry": 1080, "label": "Middle band"},
            "GREEN_SKIRT": {"x": 2923, "y": 2444, "rx": 660, "ry": 944, "label": "Green gown"},
            "FACES_HANDS": {"x": 1990, "y": 1630, "rx": 1230, "ry": 790, "label": "Both faces and joined hands"},
            "MAN_FIGURE": {"x": 1238, "y": 2662, "rx": 992, "ry": 2108, "label": "Standing man", "thing": "merchant standing on the left"},
            "MAN_HEAD": {"x": 1091, "y": 943, "rx": 438, "ry": 372, "label": "Man head"},
            "HUSBAND_FACE": {"x": 1040, "y": 1000, "rx": 330, "ry": 260, "label": "Husband face"},
            "WOMAN_FIGURE": {"x": 2926, "y": 3025, "rx": 912, "ry": 2111, "label": "Woman in green gown", "thing": "woman in green gown"},
            "WOMAN_HEAD": {"x": 3032, "y": 1266, "rx": 342, "ry": 365, "label": "Woman head"},
            "BED": {"x": 3304, "y": 2209, "rx": 536, "ry": 2209, "label": "Red bed"},
            "TABARD": {"x": 1108, "y": 2714, "rx": 844, "ry": 1414, "label": "Dark plum tabard"},
            "WINDOW": {"x": 324, "y": 1238, "rx": 162, "ry": 1238, "label": "Left window"},
            "MIRROR": {"x": 1939, "y": 1569, "rx": 306, "ry": 310, "label": "Mirror"},
        },
    }


def _eligius_asset():
    return {
        "width": 3469,
        "height": 4000,
        "content_box": {"x0": 100, "y0": 106, "x1": 3363, "y1": 3900, "how": "found"},
        "regions": {
            "SAINT": {"x": 2047, "y": 2240, "rx": 902, "ry": 960, "label": "Saint Eligius"},
            "SAINT_FACE": {"x": 1995, "y": 1700, "rx": 364, "ry": 420, "label": "Saint face"},
            "WOMAN": {"x": 763, "y": 1480, "rx": 659, "ry": 1000, "label": "Woman in gold"},
            "COUPLE": {"x": 1093, "y": 1720, "rx": 989, "ry": 1320, "label": "Young couple"},
            "SHELVES": {"x": 2758, "y": 1240, "rx": 538, "ry": 1080, "label": "Shelves"},
            "COUNTER": {"x": 1717, "y": 3320, "rx": 1648, "ry": 400, "label": "Counter"},
        },
    }


def _wide_asset():
    return {
        "width": 6000,
        "height": 2000,
        "regions": {
            "VENUS_FIGURE": {"x": 3200, "y": 1000, "rx": 2400, "ry": 750, "label": "Reclining Venus"},
            "VENUS_HEAD": {"x": 5000, "y": 650, "rx": 400, "ry": 320, "label": "Venus head"},
            "PROCESSION": {"x": 3000, "y": 1000, "rx": 2600, "ry": 600, "label": "Long procession"},
        },
    }


def _assert_all_filling_and_inside(keys, w, h, box=None):
    pbox = box if box is not None else (0.0, 0.0, float(w), float(h))
    for k in keys:
        cov = VC.coverage(k["cx"], k["cy"], k["zoom"], w, h)
        assert cov >= 0.99, (k, cov)
        assert CB.outside_share(pbox, k["cx"], k["cy"], k["zoom"]) <= CB.OFF_LIMIT, k


def test_wide_and_full_width_bands_fill_screen_without_black_bars():
    asset = _arnolfini_asset()
    z_cov = VC.cover_zoom(3840, 5253)
    for rname in ("FULL_UPPER", "FULL_MIDDLE", "GREEN_SKIRT", "FACES_HANDS"):
        cx, cy, z = VC.region_frame(asset["regions"][rname], 3840, 5253)
        assert z >= z_cov - 1e-6, (rname, z, z_cov)
        assert VC.coverage(cx, cy, z, 3840, 5253) >= 0.999
        for tid in ("CAM-01", "CAM-03", "CAM-05", "STATIC-01"):
            keys = CAM.build_main_camera(tid, rname, None, asset, None, None, 0.0, 6.0)
            _assert_all_filling_and_inside(keys, 3840, 5253)


def test_tall_person_regions_travel_from_head_end_at_filling_zoom():
    asset = _arnolfini_asset()
    # MAN_FIGURE should prefer MAN_HEAD over HUSBAND_FACE (keeps hat inside)
    head_match = VC.find_head_region("MAN_FIGURE", asset["regions"]["MAN_FIGURE"], asset["regions"])
    assert head_match is not None and head_match[0] == "MAN_HEAD"

    keys_man = CAM.build_main_camera("CAM-05", "MAN_FIGURE", None, asset, None, None, 0.0, 8.0)
    _assert_all_filling_and_inside(keys_man, 3840, 5253)
    assert keys_man[0]["cy"] < keys_man[-1]["cy"]
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["MAN_HEAD"]), keys_man[0]["cx"], keys_man[0]["cy"], keys_man[0]["zoom"])[0]
    assert CAM._travel_speed_fw(
        (keys_man[0]["cx"], keys_man[0]["cy"], keys_man[0]["zoom"]),
        (keys_man[-1]["cx"], keys_man[-1]["cy"], keys_man[-1]["zoom"]),
        8.0,
    ) <= CAM.MAX_TRAVEL_SPEED + 1e-4

    # WOMAN_FIGURE matches WOMAN_HEAD even though WOMAN_HEAD.y0 (901) is 13px above WOMAN_FIGURE.y0 (914)
    w_match = VC.find_head_region("WOMAN_FIGURE", asset["regions"]["WOMAN_FIGURE"], asset["regions"])
    assert w_match is not None and w_match[0] == "WOMAN_HEAD"
    keys_woman = CAM.build_main_camera("CAM-01", "WOMAN_FIGURE", None, asset, None, None, 0.0, 8.0)
    _assert_all_filling_and_inside(keys_woman, 3840, 5253)
    assert keys_woman[0]["cy"] < keys_woman[-1]["cy"]
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["WOMAN_HEAD"]), keys_woman[0]["cx"], keys_woman[0]["cy"], keys_woman[0]["zoom"])[0]


def test_non_person_and_no_head_tall_regions_travel_top_to_bottom():
    arn = _arnolfini_asset()
    for non_person in ("BED", "TABARD", "WINDOW"):
        assert VC.find_head_region(non_person, arn["regions"][non_person], arn["regions"]) is None
        keys = CAM.build_main_camera("CAM-05", non_person, None, arn, None, None, 0.0, 8.0)
        _assert_all_filling_and_inside(keys, 3840, 5253)
        assert keys[0]["cy"] < keys[-1]["cy"], (non_person, keys)

    el = _eligius_asset()
    box = (100.0, 106.0, 3363.0, 3900.0)
    assert VC.find_head_region("SAINT", el["regions"]["SAINT"], el["regions"])[0] == "SAINT_FACE"
    # Multi-person COUPLE has no head match and travels top-to-bottom within content_box
    assert VC.find_head_region("COUPLE", el["regions"]["COUPLE"], el["regions"]) is None
    for rname in ("SAINT", "WOMAN", "COUPLE", "SHELVES", "COUNTER"):
        keys = CAM.build_main_camera("CAM-05", rname, None, el, box, None, 0.0, 7.0)
        _assert_all_filling_and_inside(keys, 3469, 4000, box)
    keys_saint = CAM.build_main_camera("CAM-05", "SAINT", None, el, box, None, 0.0, 7.0)
    assert VC.box_inside_frame(VC.region_box(el["regions"]["SAINT_FACE"]), keys_saint[0]["cx"], keys_saint[0]["cy"], keys_saint[0]["zoom"])[0]


def test_short_shot_on_tall_region_holds_head_end():
    asset = _arnolfini_asset()
    # When even at minimum filling zoom (z_cov) the travel exceeds MAX_TRAVEL_SPEED, the shot holds the head end
    keys = CAM.build_main_camera("CAM-05", "MAN_FIGURE", None, asset, None, None, 0.0, 1.5)
    _assert_all_filling_and_inside(keys, 3840, 5253)
    assert abs(keys[-1]["cy"] - keys[0]["cy"]) < 5.0
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["MAN_HEAD"]), keys[0]["cx"], keys[0]["cy"], keys[0]["zoom"])[0]
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["MAN_HEAD"]), keys[-1]["cx"], keys[-1]["cy"], keys[-1]["zoom"])[0]

    # On a tall 3840x8000 scroll, a 2.5s shot cannot traverse the region within MAX_TRAVEL_SPEED and holds the head end
    scroll = {
        "width": 3840,
        "height": 8000,
        "regions": {
            "SCROLL_FIGURE": {"x": 1920, "y": 4000, "rx": 1200, "ry": 3200, "label": "Tall figure"},
            "SCROLL_HEAD": {"x": 1920, "y": 1200, "rx": 350, "ry": 350, "label": "Figure head"},
        },
    }
    keys_scroll = CAM.build_main_camera("CAM-05", "SCROLL_FIGURE", None, scroll, None, None, 0.0, 2.5)
    _assert_all_filling_and_inside(keys_scroll, 3840, 8000)
    assert abs(keys_scroll[-1]["cy"] - keys_scroll[0]["cy"]) < 5.0
    assert VC.box_inside_frame(VC.region_box(scroll["regions"]["SCROLL_HEAD"]), keys_scroll[-1]["cx"], keys_scroll[-1]["cy"], keys_scroll[-1]["zoom"])[0]


def test_wide_region_on_wide_painting_travels_from_head_end_or_left():
    wide = _wide_asset()
    # Head on the right -> starts on the right (VENUS_HEAD inside frame) and travels left
    keys_venus = CAM.build_main_camera("CAM-05", "VENUS_FIGURE", None, wide, None, None, 0.0, 7.0)
    _assert_all_filling_and_inside(keys_venus, 6000, 2000)
    assert keys_venus[0]["cx"] > keys_venus[-1]["cx"]
    assert VC.box_inside_frame(VC.region_box(wide["regions"]["VENUS_HEAD"]), keys_venus[0]["cx"], keys_venus[0]["cy"], keys_venus[0]["zoom"])[0]

    # Short shot (< distance / MAX_TRAVEL_SPEED) holds right (head) end
    keys_short = CAM.build_main_camera("CAM-05", "VENUS_FIGURE", None, wide, None, None, 0.0, 1.2)
    _assert_all_filling_and_inside(keys_short, 6000, 2000)
    assert abs(keys_short[-1]["cx"] - keys_short[0]["cx"]) < 5.0
    assert VC.box_inside_frame(VC.region_box(wide["regions"]["VENUS_HEAD"]), keys_short[-1]["cx"], keys_short[-1]["cy"], keys_short[-1]["zoom"])[0]

    # No head region -> defaults to left end and travels right
    keys_proc = CAM.build_main_camera("CAM-05", "PROCESSION", None, wide, None, None, 0.0, 8.0)
    _assert_all_filling_and_inside(keys_proc, 6000, 2000)
    assert keys_proc[0]["cx"] < keys_proc[-1]["cx"]


def test_whole_painting_only_when_requested_and_pullback_ends_filling():
    asset = _arnolfini_asset()
    whole = VC.whole_painting_frame(3840, 5253)
    mirror = VC.region_frame(asset["regions"]["MIRROR"], 3840, 5253)

    # Cutaway reset (prev_frame=None, from=None) on a region must start at a filling zoom, never whole
    keys_cut = CAM.build_main_camera("CAM-05", "MIRROR", None, asset, None, None, 0.0, 6.0)
    assert keys_cut[0]["zoom"] >= VC.cover_zoom(3840, 5253) - 1e-6

    # Explicit from="whole" still starts on whole
    keys_whole = CAM.build_main_camera("CAM-05", "MIRROR", "whole", asset, None, None, 0.0, 8.5)
    assert keys_whole[0]["zoom"] == whole[2]

    # CAM-03 pull-back to a named region ends filling; CAM-03 with region=None ends at whole
    keys_pull_reg = CAM.build_main_camera("CAM-03", "FULL_UPPER", None, asset, None, mirror, 0.0, 6.0)
    _assert_all_filling_and_inside(keys_pull_reg, 3840, 5253)
    keys_pull_whole = CAM.build_main_camera("CAM-03", None, None, asset, None, mirror, 0.0, 6.0)
    assert keys_pull_whole[-1]["zoom"] == whole[2]


def test_continuity_naming_arrival_and_no_feet_collapse():
    asset = _arnolfini_asset()
    tm = Timing({"duration": 10.0, "words": [{"w": f"w{i}", "s": i * 0.5, "e": i * 0.5 + 0.4} for i in range(20)]})
    # Naming strip at word 8 (4.0s): head must stay inside frame at 4.0s
    ovs = [{"technique": "X-ANN-01", "start": {"w": 8}, "dur": 3.0, "params": {"text": "Giovanni Arnolfini"}}]
    keys_name = CAM.build_main_camera("CAM-05", "MAN_FIGURE", "whole", asset, None, None, 0.0, 9.0, overlays=ovs, tm=tm)
    pose_at_4s = VC.camera_at([(k["at"]["rel"] * 9.0, k["cx"], k["cy"], k["zoom"], k.get("ease", "linear")) for k in keys_name], 4.0)
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["MAN_HEAD"]), *pose_at_4s)[0]

    # If previous frame happened to sit near the feet/tail of MAN_FIGURE, travel from head to feet is NOT collapsed onto feet
    travel_ref = VC.region_travel_frames(asset["regions"]["MAN_FIGURE"], 3840, 5253, regions=asset["regions"], region_name="MAN_FIGURE", dur=8.0, max_speed=CAM.MAX_TRAVEL_SPEED)
    tail_frame = travel_ref["tail"]
    keys_from_tail = CAM.build_main_camera("CAM-05", "MAN_FIGURE", None, asset, None, tail_frame, 0.0, 8.0, prev_region="DOG")
    assert len(keys_from_tail) == 3
    assert keys_from_tail[1]["cy"] < tail_frame[1] - 1000.0
    assert VC.box_inside_frame(VC.region_box(asset["regions"]["MAN_HEAD"]), keys_from_tail[1]["cx"], keys_from_tail[1]["cy"], keys_from_tail[1]["zoom"])[0]

    # Same region keeps previous frame verbatim
    keys_same = CAM.build_main_camera("CAM-05", "MAN_FIGURE", None, asset, None, tail_frame, 0.0, 8.0, prev_region="MAN_FIGURE")
    assert len(keys_same) == 2 and all(math.isclose(k["cy"], tail_frame[1], abs_tol=0.1) for k in keys_same)
