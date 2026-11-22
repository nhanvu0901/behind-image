"""Tests for worker idfix check `strip_without_light`: X-ANN-01 for non-cast things needs a light unless region > 60% of frame."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from bti.auto_run import checks as auto_checks
from bti.draft import compile as draft_compile
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as V
from bti.engine.timing import Timing

from test_box_camera_checks import _base_project


def _shot(sid: str, t0: float, *, asset: str = "MAIN", region: str | None = "CHAIR", zoom: float = 0.52,
          strip_text: str | None = "The Chair", strip_span: tuple[float, float] = (1.0, 4.0),
          lights: list[dict] | None = None, intent: str = "point_at", camera: list | None = None):
    ovs = list(lights or [])
    if strip_text is not None:
        ovs.append({
            "id": "ov_strip",
            "technique": "X-ANN-01",
            "start": {"t": strip_span[0]},
            "dur": strip_span[1] - strip_span[0],
            "params": {"text": strip_text},
        })
    slots = {"image": {"asset": asset}}
    if region:
        slots["image"]["region"] = region
    if camera is None:
        camera = [
            {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": zoom, "ease": "linear"},
            {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": zoom, "ease": "linear"},
        ]
    return {
        "id": sid, "start": {"t": t0}, "technique": "CAM-05", "intent": intent,
        "slots": slots, "params": {"camera": camera}, "overlays": ovs,
        "locked": False, "source": "agent", "note": "",
    }


def _setup(tmp_path: Path, *, names=None, extra_regions=None):
    d, sb, tm, bundle = _base_project(tmp_path)
    picks = json.loads((d / "picks.json").read_text(encoding="utf-8"))
    if extra_regions:
        picks["assets"]["MAIN"]["regions"].update(extra_regions)
        sb["assets"]["MAIN"]["regions"].update(extra_regions)
    if names is not None:
        picks["names"] = names
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    return d, sb, tm, bundle


def test_thing_strip_warns_without_light_and_clears_with_overlapping_light(tmp_path):
    d, sb, tm, bundle = _setup(tmp_path, names=[{"name": "Giovanni Arnolfini", "also": ["Giovanni"], "line": "b0002", "where": {"region": "WOMAN"}}])
    # CHAIR is 538x736 -> at zoom 1.0 (frame 1920x1080), CHAIR is 28% x 68%... wait use tight zoom 0.45 so CHAIR is 12.6% x 30.7% <= 60%
    sb["shots"] = [_shot("s0001", 0.0, region="CHAIR", zoom=0.45, strip_text="The Oak Chair")]
    warns = [i for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"]
    assert len(warns) == 1 and warns[0]["level"] == "warn"
    assert warns[0]["args"]["shot"] == "s0001" and warns[0]["args"]["text"] == "The Oak Chair"
    assert warns[0]["args"]["region"] == "CHAIR" and warns[0]["args"]["min_share"] == 0.6

    # Overlapping HI-01, X-HI-01, or AN-01 clears it.
    for tech in ("HI-01", "X-HI-01", "AN-01"):
        light = {"id": "ov_l", "technique": tech, "start": {"t": 1.5}, "dur": 2.0, "params": {"at": "CHAIR"}}
        sb["shots"] = [_shot("s0001", 0.0, region="CHAIR", zoom=0.45, strip_text="The Oak Chair", lights=[light])]
        assert [i for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"] == []

    # Light in same shot that does NOT overlap strip span, or light in a different shot, still warns.
    non_ov = {"id": "ov_l", "technique": "HI-01", "start": {"t": 4.2}, "dur": 1.0, "params": {"at": "CHAIR"}}
    sb["shots"] = [
        _shot("s0001", 0.0, region="CHAIR", zoom=0.45, strip_text="The Oak Chair", strip_span=(1.0, 3.0), lights=[non_ov]),
        _shot("s0002", 6.0, region="WOMAN", zoom=1.0, strip_text=None, lights=[{"id": "ov2", "technique": "HI-01", "start": {"t": 6.5}, "dur": 3.0, "params": {"at": "WOMAN"}}]),
    ]
    assert [i["args"]["shot"] for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"] == ["s0001"]


def test_cast_names_and_aliases_exempt_while_non_cast_substrings_warn(tmp_path):
    names = [
        {"name": "Giovanni Arnolfini", "also": ["Giovanni"], "line": "b0001", "where": {"region": "WOMAN"}},
        {"name": "Saint Martha", "also": [], "line": "b0002", "where": {"region": "WOMAN"}},
    ]
    d, sb, tm, bundle = _setup(tmp_path, names=names)
    sb["shots"] = [
        _shot("s0001", 0.0, region="WOMAN", zoom=1.0, strip_text="Giovanni Arnolfini", strip_span=(0.5, 2.5)),
        _shot("s0002", 3.0, region="WOMAN", zoom=1.0, strip_text="GIOVANNI", strip_span=(3.5, 5.5)),
        _shot("s0003", 6.0, region="WOMAN", zoom=1.0, strip_text="Saint Martha?", strip_span=(6.5, 8.5)),
        _shot("s0004", 9.0, region="CHAIR", zoom=0.45, strip_text="Arnolfini House", strip_span=(9.5, 11.5)),  # "Arnolfini" alone is not cast name/also!
    ]
    got = [i["args"]["shot"] for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"]
    assert got == ["s0004"]


def test_large_region_over_60pct_exempt_and_thin_or_clipped_caught(tmp_path):
    extra = {
        # Large region 1600x900 -> at z=1.0 (1920x1080), 83.3% W x 83.3% H
        "BIG_BED": {"x": 1920, "y": 2500, "rx": 800, "ry": 450, "label": "Big bed"},
        # Huge region larger than 1920x1080 frame at z=1.0 -> clipped to 100% W x 100% H
        "HUGE_WALL": {"x": 1920, "y": 2500, "rx": 1800, "ry": 2000, "label": "Huge wall"},
        # Tall thin strip like SETTLE_CUSHION: 588x1288 -> at z=0.51 (3765x2118), 15.6% W x 60.8% H -> thin (<20% W)!
        "SETTLE_CUSHION": {"x": 2010, "y": 2592, "rx": 294, "ry": 644, "label": "Settle"},
    }
    d, sb, tm, bundle = _setup(tmp_path, names=[], extra_regions=extra)
    # 1. BIG_BED centered at z=1.0 -> >60% -> exempt
    # 2. HUGE_WALL larger than frame -> clipped to 1.0 -> exempt
    # 3. BIG_BED pushed mostly off-frame (cx=3000 -> intersection width only 120px = 6.25% <= 60%) -> caught!
    # 4. SETTLE_CUSHION (15.6% W x 60.8% H) -> thin guard catches it!
    sb["shots"] = [
        _shot("s0001", 0.0, region="BIG_BED", zoom=1.0, strip_text="The Red Bed", strip_span=(0.5, 2.5),
              camera=[{"at": {"rel": 0.0}, "cx": 1920, "cy": 2500, "zoom": 1.0, "ease": "linear"},
                      {"at": {"rel": 1.0}, "cx": 1920, "cy": 2500, "zoom": 1.0, "ease": "linear"}]),
        _shot("s0002", 3.0, region="HUGE_WALL", zoom=1.0, strip_text="Back Wall", strip_span=(3.5, 5.5),
              camera=[{"at": {"rel": 0.0}, "cx": 1920, "cy": 2500, "zoom": 1.0, "ease": "linear"},
                      {"at": {"rel": 1.0}, "cx": 1920, "cy": 2500, "zoom": 1.0, "ease": "linear"}]),
        _shot("s0003", 6.0, region="BIG_BED", zoom=1.0, strip_text="Side of Bed", strip_span=(6.5, 8.5),
              camera=[{"at": {"rel": 0.0}, "cx": 3560, "cy": 2500, "zoom": 1.0, "ease": "linear"},
                      {"at": {"rel": 1.0}, "cx": 3560, "cy": 2500, "zoom": 1.0, "ease": "linear"}]),
        _shot("s0004", 9.0, region="SETTLE_CUSHION", zoom=0.50985, strip_text="Settle", strip_span=(9.5, 11.5),
              camera=[{"at": {"rel": 0.0}, "cx": 1965.3, "cy": 2592.0, "zoom": 0.50985, "ease": "linear"},
                      {"at": {"rel": 1.0}, "cx": 1965.3, "cy": 2592.0, "zoom": 0.50985, "ease": "linear"}]),
    ]
    got = [i["args"]["shot"] for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"]
    assert got == ["s0001", "s0002", "s0003", "s0004"]


def test_outside_picture_and_missing_cast_list_behavior(tmp_path):
    # Borrowed picture never triggers strip_without_light; missing `names` skips checking; `"names": []` IS checked.
    d, sb, tm, bundle = _setup(tmp_path, names=None)
    sb["assets"]["OTHER"] = {"file": "other.jpg", "kind": "image", "width": 800, "height": 600}
    sb["shots"] = [
        _shot("s0001", 0.0, region="CHAIR", zoom=0.45, strip_text="Chair"),
        _shot("s0002", 6.0, asset="OTHER", region=None, zoom=1.0, strip_text="Context Work", strip_span=(6.5, 8.5),
              camera=[{"at": {"rel": 0.0}, "cx": 400, "cy": 300, "zoom": 1.0, "ease": "linear"},
                      {"at": {"rel": 1.0}, "cx": 400, "cy": 300, "zoom": 1.0, "ease": "linear"}]),
    ]
    assert [i for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"] == []

    pk = json.loads((d / "picks.json").read_text(encoding="utf-8"))
    pk["names"] = []
    (d / "picks.json").write_text(json.dumps(pk), encoding="utf-8")
    assert [i["args"]["shot"] for i in SB.validate(sb, tm, bundle, d) if i["code"] == "strip_without_light"] == ["s0001"]


def test_namefirst_fixture_real_settle_and_stored_arnolfini_clean():
    folder = Path(__file__).parent / "fixtures" / "namefirst"
    sb = json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))
    tm = Timing.load(folder / "timing.json")
    bundle = R.load_bundle("gae")
    starts = [tm.resolve(s["start"]) for s in sb["shots"]]
    end = tm.resolve(sb["end"])

    # In tests/engine/fixtures/namefirst, s0040 already has manual o4 HI-01 -> only s0030 ("Tabard") warns.
    issues_as_is = V.check(sb, tm, bundle, folder, starts, end, lambda *_: None)
    assert [i["args"]["shot"] for i in issues_as_is if i["code"] == "strip_without_light"] == ["s0030", "s0049", "s0074"]

    # Removing manual o4 HI-01 from s0040 catches Settle (`SETTLE_CUSHION`, 15.6% x 60.8%) too!
    sb_no_o4 = copy.deepcopy(sb)
    for s in sb_no_o4["shots"]:
        if s.get("id") == "s0040":
            s["overlays"] = [o for o in s["overlays"] if o.get("technique") != "HI-01"]
    issues_no_o4 = V.check(sb_no_o4, tm, bundle, folder, starts, end, lambda *_: None)
    assert [(i["args"]["shot"], i["args"]["text"]) for i in issues_no_o4 if i["code"] == "strip_without_light"] == [
        ("s0030", "Tabard"), ("s0040", "Settle"), ("s0049", "Crown glass"), ("s0074", "Pattens")
    ]

    # Stored legacy Arnolfini without picks.names produces zero false strip_without_light warnings.
    cat_arn = Path(__file__).parent / "fixtures" / "catalogue" / "arnolfini"
    cat_sb = json.loads((cat_arn / "storyboard.json").read_text(encoding="utf-8"))
    cat_tm = Timing.load(cat_arn / "timing.json")
    cat_starts = [cat_tm.resolve(s["start"]) for s in cat_sb["shots"]]
    cat_end = cat_tm.resolve(cat_sb["end"])
    assert [i for i in V.check(cat_sb, cat_tm, bundle, cat_arn, cat_starts, cat_end, lambda *_: None) if i["code"] == "strip_without_light"] == []


def test_auto_run_stops_summary_prioritizes_and_docs_present():
    assert "strip_without_light" in auto_checks.STOPS["storyboard"]
    verdict = auto_checks.judge("storyboard", [{"level": "warn", "code": "strip_without_light", "shot": "s0040", "message": "Settle unlit"}])
    assert len(verdict["stopping"]) == 1 and verdict["stopping"][0]["code"] == "strip_without_light"
    assert verdict["stopping"][0]["why"] == auto_checks.STOPS["storyboard"]["strip_without_light"][0]

    res = draft_compile.CompileResult(
        {"shots": []},
        [{"level": "warn", "code": "shot_short", "message": "short1"},
         {"level": "warn", "code": "shot_short", "message": "short2"},
         {"level": "warn", "code": "strip_without_light", "message": "unlit settle"}],
        [], [], {}, False,
    )
    txt = draft_compile.summary_text(res, limit=1)
    assert "warning strip_without_light: unlit settle" in txt

    repo = Path(__file__).resolve().parents[2]
    task = (repo / "skills" / "storyboard_draft" / "TASK.template.md").read_text(encoding="utf-8")
    assert len(task) < 35_500 and "strip_without_light" in task and "of any size" in task
    techs = json.loads((repo / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))
    xann = next(t for t in techs["techniques"] if t["id"] == "X-ANN-01")
    assert "regardless of its size" in xann["needs"]
