"""Unit tests for the Variant B ID-BRAND-04 channel ident default, rest-region selection, and style preservation."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from bti import identity as ID
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import techniques  # noqa: F401
from bti.engine.timing import Timing

REPO = Path(__file__).resolve().parents[2]


def _make_picks(*, last_item=None, subjects=None, beat_about=None):
    regions = {
        "DOORWAY": {"x": 800, "y": 500, "rx": 60, "ry": 90, "tight": False},
        "MIRROR_TIGHT": {"x": 960, "y": 600, "rx": 70, "ry": 70, "tight": True},
        "DOG_LOOSE": {"x": 960, "y": 900, "rx": 120, "ry": 120, "tight": False},
    }
    beats = {
        "b0001": {"items": [{"asset": "main_pic", "region": None, "role": "main"}]},
        "b0002": {"items": ([last_item] if last_item else [{"asset": "main_pic", "region": None, "role": "main"}])},
    }
    for bid, about in (beat_about or {}).items():
        beats.setdefault(bid, {"items": []})["about"] = about
    return {
        "schema": "bti.picks/1",
        "main_asset": "main_pic",
        "subjects": subjects or [],
        "assets": {
            "main_pic": {"kind": "image", "file": "main.jpg", "title": "The Main Work", "artist": "Master Painter", "year": "1434",
                         "width": 1920, "height": 1440, "regions": regions},
            "outside_pic": {"kind": "image", "file": "outside.jpg", "title": "Portrait", "artist": "Other", "year": "1440",
                            "width": 1000, "height": 1200, "regions": {"FACE": {"x": 500, "y": 400, "rx": 80, "ry": 80, "tight": True}}},
        },
        "beats": beats,
    }


def _cold_timing():
    return {
        "duration": 90.0,
        "words": [{"w": "hello", "s": 5.0, "e": 5.5}, {"w": "world", "s": 10.0, "e": 10.5}],
        "beats": [
            {"id": "b0001", "chapter": "c01", "w0": 0, "w1": 0, "start": 5.0, "end": 8.0},
            {"id": "b0002", "chapter": "c01", "w0": 1, "w1": 1, "start": 8.0, "end": 12.0},
            {"id": "b0003", "chapter": "c02", "w0": 1, "w1": 1, "start": 25.0, "end": 35.0},
        ],
        "chapters": [
            {"id": "c01", "start": 5.0, "end": 12.0, "w0": 0, "w1": 1},
            {"id": "c02", "start": 25.0, "end": 35.0, "w0": 1, "w1": 1},
        ],
    }


def test_choose_rest_region_all_three_rules():
    tm = _cold_timing()
    # Rule 1: cold open's final sentence line picks a region of main_pic -> chosen directly (even if tight is False).
    p1 = _make_picks(last_item={"asset": "main_pic", "region": "DOORWAY", "role": "detail"})
    assert ID.choose_rest_region(tm, p1, "main_pic") == "DOORWAY"

    # Rule 2: final beat shows outside asset (or whole main painting), fall back to first cold-open person/thing subject with tight: true.
    p2 = _make_picks(
        last_item={"asset": "outside_pic", "region": "FACE", "role": "outside"},
        subjects=[
            {"id": "s_place", "kind": "place", "name": "Bruges", "strip": False, "where": {"region": "MIRROR_TIGHT"}},
            {"id": "s_loose", "kind": "thing", "name": "Terrier", "strip": True, "where": {"region": "DOG_LOOSE"}},
            {"id": "s_mirror", "kind": "thing", "name": "Mirror", "strip": True, "where": {"region": "MIRROR_TIGHT"}},
        ],
        beat_about={
            "b0001": [{"id": "s_place", "words": "Bruges"}, {"id": "s_loose", "words": "dog"}, {"id": "s_mirror", "words": "mirror"}],
        },
    )
    assert ID.choose_rest_region(tm, p2, "main_pic") == "MIRROR_TIGHT"

    # Rule 3: neither final-beat region on main painting nor tight person/thing subject -> None (centre rest).
    p3 = _make_picks(
        last_item={"asset": "main_pic", "region": None, "role": "main"},
        subjects=[{"id": "s_loose", "kind": "person", "name": "Patron", "strip": True, "where": {"region": "DOG_LOOSE"}}],
        beat_about={"b0001": [{"id": "s_loose", "words": "Patron"}]},
    )
    assert ID.choose_rest_region(tm, p3, "main_pic") is None


def test_choose_rest_region_handles_subject_where_list():
    tm = _cold_timing()
    # Subject `where` as a list (standard picks schema): skips non-main / loose places and picks the first tight main region.
    picks = _make_picks(
        last_item={"asset": "main_pic", "region": None, "role": "main"},
        subjects=[
            {
                "id": "s_multi",
                "kind": "person",
                "name": "Christ",
                "strip": True,
                "where": [
                    {"asset": "outside_pic", "region": "FACE"},
                    {"region": "DOG_LOOSE"},
                    {"region": "MIRROR_TIGHT"},
                ],
            },
        ],
        beat_about={"b0001": [{"id": "s_multi", "words": "Christ"}]},
    )
    assert ID.choose_rest_region(tm, picks, "main_pic") == "MIRROR_TIGHT"


def test_ident_and_marks_never_sit_on_halfway_pose_and_always_fill_screen(sb, timing):
    b = R.load_bundle("gae")
    picks = _make_picks(last_item={"asset": "main_pic", "region": "MIRROR_TIGHT", "role": "detail"})
    tm_data = copy.deepcopy(timing)
    tm_data["chapters"] = [{"id": "c01", "start": 0.0, "end": 4.0}, {"id": "c02", "start": 10.0, "end": 40.0}]
    tm_data["beats"] = [{"id": "b0001", "chapter": "c01", "start": 0.5, "end": 2.0},
                        {"id": "b0002", "chapter": "c01", "start": 2.0, "end": 4.0}]
    tm = Timing(tm_data)
    # Upright painting 3840x5253: z_cover = 0.50; opening shot is 0.19634; previous shot ends at halfway z=0.31.
    main_w, main_h = 3840.0, 5253.0
    sb["assets"]["main_pic"] = {
        "kind": "image", "file": "main.jpg", "title": "The Arnolfini Portrait", "artist": "Jan van Eyck", "year": "1434",
        "width": int(main_w), "height": int(main_h),
        "regions": {"MIRROR_TIGHT": {"x": 1940, "y": 1558, "rx": 25, "ry": 50, "tight": True}},
    }
    for s in sb["shots"]:
        s["overlays"] = [o for o in s.get("overlays") or [] if not o.get("technique", "").startswith("ID-")]
    sb["shots"][0]["slots"] = {"image": {"asset": "main_pic"}}
    sb["shots"][0]["params"]["camera"] = [
        {"at": {"rel": 0.0}, "cx": 1920.0, "cy": 2626.5, "zoom": 0.19634, "ease": "linear"},
        {"at": {"rel": 1.0}, "cx": 1920.0, "cy": 2626.5, "zoom": 0.19634, "ease": "linear"},
    ]
    # Shot before brand ends at halfway z=0.31; shots after marks include halfway z=0.31 and filling z=0.70.
    brand_idx = next(i for i, s in enumerate(sb["shots"]) if s["technique"] in ("X-CARD-02",) or s["technique"].startswith("ID-BRAND-"))
    sb["shots"][brand_idx - 1]["slots"] = {"image": {"asset": "main_pic"}}
    sb["shots"][brand_idx - 1]["params"]["camera"] = [
        {"at": {"rel": 0.0}, "cx": 1920.0, "cy": 1741.94, "zoom": 0.31, "ease": "linear"},
        {"at": {"rel": 1.0}, "cx": 1920.0, "cy": 1741.94, "zoom": 0.31, "ease": "linear"},
    ]
    for s in sb["shots"]:
        if s["intent"] != "structure" and (s.get("slots") or {}).get("image", {}).get("asset") == "arnolfini_portrait":
            s["slots"]["image"]["asset"] = "main_pic"
    for k in range(brand_idx + 1, len(sb["shots"])):
        if sb["shots"][k]["intent"] == "structure":
            nxt = sb["shots"][k + 1]
            nxt["slots"] = {"image": {"asset": "main_pic"}}
            nxt["params"]["camera"] = [
                {"at": {"rel": 0.0}, "cx": 1920.0, "cy": 3511.06, "zoom": 0.31, "ease": "linear"},
                {"at": {"rel": 1.0}, "cx": 1920.0, "cy": 1741.94, "zoom": 0.31, "ease": "linear"},
            ]
            break

    out, _ = ID.apply_identity(sb, "raking", b.style, tm, {"main_asset": "main_pic", "picks": picks}, defaults=b.param_defaults)
    for s in out["shots"]:
        if s["intent"] != "structure":
            continue
        cam = s["params"]["camera"]
        for key in cam:
            vw, vh = 1920.0 / key["zoom"], 1080.0 / key["zoom"]
            cov_w = max(0.0, min(main_w, key["cx"] + vw / 2.0) - max(0.0, key["cx"] - vw / 2.0)) / vw
            cov_h = max(0.0, min(main_h, key["cy"] + vh / 2.0) - max(0.0, key["cy"] - vh / 2.0)) / vh
            assert cov_w >= 0.99 and cov_h >= 0.99, (s["id"], s["technique"], key, cov_w, cov_h)
            assert key["zoom"] >= 0.50 - 1e-5, (s["id"], key)


def test_default_raking_applies_brand04_variant_b_with_texts_and_preserves_dim(sb, timing):
    b = R.load_bundle("gae")
    picks = _make_picks(last_item={"asset": "main_pic", "region": "DOORWAY", "role": "detail"})
    tm_data = copy.deepcopy(timing)
    tm_data["chapters"] = [{"id": "c01", "start": 0.0, "end": 4.0}, {"id": "c02", "start": 10.0, "end": 40.0}]
    tm_data["beats"] = [{"id": "b0001", "chapter": "c01", "start": 0.5, "end": 2.0},
                        {"id": "b0002", "chapter": "c01", "start": 2.0, "end": 4.0}]
    tm = Timing(tm_data)
    sb["assets"] = {**sb.get("assets", {}), "main_pic": copy.deepcopy(picks["assets"]["main_pic"])}
    for s in sb["shots"]:
        s["overlays"] = [o for o in s.get("overlays") or [] if not o.get("technique", "").startswith("ID-")]
    sb["shots"][1]["slots"] = {"image": {"asset": "main_pic"}}
    sb["identity"] = {"style": "raking", "video_title": "The Question in the Reflection"}

    out, _ = ID.apply_identity(sb, "raking", b.style, tm, {"main_asset": "main_pic", "picks": picks}, defaults=b.param_defaults)
    beat = next(s for s in out["shots"] if s["intent"] == "structure" and s["technique"].startswith("ID-BRAND-"))
    assert beat["technique"] == "ID-BRAND-04"
    assert beat["params"]["variant"] == "B"
    assert beat["params"]["region"] == "DOORWAY"
    assert beat["params"]["text"] == "RAKING LIGHT"
    assert beat["params"]["title"] == "The Question in the Reflection"
    assert beat["params"]["subtitle"] == "The Arnolfini Portrait · Jan van Eyck, 1434"
    assert not [i for i in SB.validate(out, tm, b) if i["level"] == "error"]

    # Switching to dim keeps dim untouched; switching back restores ID-BRAND-04 variant B.
    dimmed, _ = ID.apply_identity(out, "dim", b.style, tm, {"main_asset": "main_pic", "picks": picks}, defaults=b.param_defaults)
    dim_beat = next(s for s in dimmed["shots"] if s["id"] == beat["id"])
    assert dim_beat["technique"] == "ID-BRAND-02" and dimmed["identity"]["style"] == "dim"
    # Manual A/C choice on ID-BRAND-04 survives a subsequent raking re-apply (e.g. title update).
    tuned = copy.deepcopy(out)
    next(s for s in tuned["shots"] if s["id"] == beat["id"])["params"]["variant"] = "C"
    reapplied, _ = ID.apply_identity(ID.with_video_title(tuned, "Updated Title"), "raking", b.style, tm,
                                     {"main_asset": "main_pic", "picks": picks}, defaults=b.param_defaults)
    assert next(s for s in reapplied["shots"] if s["id"] == beat["id"])["params"]["variant"] == "C"

    # Stored storyboards still holding ID-BRAND-01 or ID-BRAND-03 under `raking` emit no mismatch warnings.
    for earlier_tid in ("ID-BRAND-01", "ID-BRAND-03"):
        legacy = copy.deepcopy(out)
        leg_beat = next(s for s in legacy["shots"] if s["id"] == beat["id"])
        leg_beat["technique"] = earlier_tid
        leg_beat["params"] = b.param_defaults(earlier_tid)
        if earlier_tid == "ID-BRAND-03":
            leg_beat["params"].update({"title": "A", "subtitle": "B"})
        mismatches = [i for i in SB.validate(legacy, tm, b) if i["code"] == "identity_technique_mismatch"]
        assert mismatches == []

    # viewchecks readability & placeholder hygiene on ID-BRAND-04: normal texts emit zero issues; placeholder flags caption_placeholder.
    assert [i for i in SB.validate(out, tm, b) if i["code"] == "caption_placeholder"] == []
    bad = copy.deepcopy(out)
    next(s for s in bad["shots"] if s["id"] == beat["id"])["params"]["title"] = "TBD"
    assert any(i["code"] == "caption_placeholder" for i in SB.validate(bad, tm, b))
