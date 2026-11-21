"""Tests for worker boxcam viewer checks: `camera_off_region` and `thing_arrives_late` in `bti/engine/viewchecks.py`."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.timing import Timing


def _base_project(tmp_path: Path):
    from PIL import Image
    d = tmp_path / "p"
    d.mkdir()
    Image.new("RGB", (3840, 5253), (90, 85, 80)).save(d / "main.jpg", quality=80)
    Image.new("RGB", (800, 600), (60, 70, 80)).save(d / "other.jpg", quality=80)
    words = [{"w": "w%d" % i, "s": round(i * 0.5, 2), "e": round(i * 0.5 + 0.4, 2)} for i in range(24)]
    timing = {
        "duration": 12.0,
        "words": words,
        "beats": [
            {"id": "b0001", "chapter": "c01", "text": "w0..w11", "start": 0.0, "end": 5.9, "w0": 0, "w1": 12},
            {"id": "b0002", "chapter": "c01", "text": "w12..w23", "start": 6.0, "end": 11.9, "w0": 12, "w1": 24},
        ],
        "chapters": [{"id": "c01", "name": "One", "start": 0.0, "end": 11.9, "card": False}],
    }
    picks = {
        "schema": "bti.picks/1",
        "main_asset": "MAIN",
        "assets": {"MAIN": {"file": "main.jpg", "kind": "image", "width": 3840, "height": 5253,
                            "regions": {
                                "WOMAN": {"x": 2472, "y": 1041.5, "rx": 47, "ry": 107.5, "label": "Woman"},
                                "CHAIR": {"x": 2496, "y": 1261, "rx": 269, "ry": 368, "label": "Chair"},
                                "EDGE": {"x": 60, "y": 100, "rx": 60, "ry": 80, "label": "Edge"},
                            }}},
        "beats": {
            "b0001": {"items": [{"asset": "MAIN", "region": "CHAIR", "role": "detail"}], "kinds": ["detail"]},
            "b0002": {"items": [{"asset": "MAIN", "region": "WOMAN", "role": "detail"}], "kinds": ["detail"]},
        },
    }
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    sb = {
        "schema": "bti.storyboard/1",
        "project": d.name,
        "style": "gae",
        "canvas": {"w": 1920, "h": 1080, "fps": 30},
        "assets": copy.deepcopy(picks["assets"]),
        "shots": [],
        "end": {"t": 12.0},
    }
    return d, sb, Timing(timing), R.load_bundle("gae")


def test_camera_off_region_and_thing_arrives_late_fire_and_clear(tmp_path):
    d, sb, tm, bundle = _base_project(tmp_path)
    # s0001 (0..6s, beat b0001 CHAIR): ends at (2480, 1300, z=1.5) -> clips top of CHAIR (`y0=893`, frame `fy0=940`, 47px miss) AND never wholly inside!
    # s0002 (6..12s, beat b0002 WOMAN): arrives at t=8.0 (33% -> inside for 4.0s >= 2.0s!) and holds cleanly -> NO warning!
    sb["shots"] = [
        {"id": "s0001", "start": {"t": 0.0}, "technique": "CAM-05", "intent": "point_at",
         "slots": {"image": {"asset": "MAIN", "region": "CHAIR"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 2300, "cy": 1900, "zoom": 1.0, "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 2480, "cy": 1300, "zoom": 1.5, "ease": "linear"},
         ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
        {"id": "s0002", "start": {"t": 6.0}, "technique": "CAM-05", "intent": "point_at",
         "slots": {"image": {"asset": "MAIN", "region": "WOMAN"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626, "zoom": 0.2, "ease": "inout_cubic"},
             {"at": {"rel": 0.35}, "cx": 2472, "cy": 1041.5, "zoom": 1.9, "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 2472, "cy": 1041.5, "zoom": 2.0, "ease": "linear"},
         ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
    ]
    issues = SB.validate(sb, tm, bundle, d)
    off = [i for i in issues if i["code"] == "camera_off_region"]
    late = [i for i in issues if i["code"] == "thing_arrives_late"]
    assert [i["args"]["shot"] for i in off] == ["s0001"] and off[0]["level"] == "warn"
    assert off[0]["args"]["miss_px"] > 40
    assert [i["args"]["shot"] for i in late] == ["s0001"] and late[0]["level"] == "warn"

    # When slot.region is absent, falls back to beat detail pick (still fires on b0001)
    sb["shots"][0]["slots"]["image"].pop("region")
    issues2 = SB.validate(sb, tm, bundle, d)
    assert [i["args"]["shot"] for i in issues2 if i["code"] == "camera_off_region"] == ["s0001"]


def test_late_threshold_and_edge_tolerance_and_no_kinds_silence(tmp_path):
    d, sb, tm, bundle = _base_project(tmp_path)
    # 3.0 s shot (0..3s) arriving at rel=0.8 (only 0.6s inside = 20% < 2.0s AND < 55%) -> late fires!
    # Edge-touching region EDGE `(0..120, 20..180)` with 0.5 px rounding -> within REGION_IN_TOL_PX (1.0) -> camera_off_region silent!
    sb["shots"] = [
        {"id": "s0001", "start": {"t": 0.0}, "technique": "CAM-05", "intent": "point_at",
         "slots": {"image": {"asset": "MAIN", "region": "WOMAN"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 1500, "cy": 2500, "zoom": 2.0, "ease": "linear"},
             {"at": {"rel": 0.85}, "cx": 2472, "cy": 1041.5, "zoom": 2.0, "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 2472, "cy": 1041.5, "zoom": 2.0, "ease": "linear"},
         ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
        {"id": "s0002", "start": {"t": 3.0}, "technique": "CAM-01", "intent": "point_at",
         "slots": {"image": {"asset": "MAIN", "region": "EDGE"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 480.3, "cy": 270.0, "zoom": 2.0, "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 480.3, "cy": 270.0, "zoom": 2.0, "ease": "linear"},
         ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
    ]
    issues = SB.validate(sb, tm, bundle, d)
    assert [i["args"]["shot"] for i in issues if i["code"] == "thing_arrives_late"] == ["s0001"]
    assert not [i for i in issues if i["code"] == "camera_off_region"]

    # When neither shot has slot.region nor picks have kinds, both checks stay silent
    pk = json.loads((d / "picks.json").read_text(encoding="utf-8"))
    for v in pk["beats"].values():
        v.pop("kinds", None)
    (d / "picks.json").write_text(json.dumps(pk), encoding="utf-8")
    for s in sb["shots"]:
        s["slots"]["image"].pop("region", None)
    issues3 = SB.validate(sb, tm, bundle, d)
    assert not [i for i in issues3 if i["code"] in ("camera_off_region", "thing_arrives_late")]
