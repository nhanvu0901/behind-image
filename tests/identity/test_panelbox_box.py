"""Worker panelbox (2026-11-20): the identity applier keeps the camera of what it writes on the painted area of the main painting (`content_box` of its asset): the whole-painting
fit of the channel-name beat and of a chapter mark that has no picture of its own to flow into fits and centres the box, not the file, and the keys it writes for the main painting
(the beat's, a mark's, which starts 4% wider than the shot it flows into) are moved or tightened when they would show more than 1% of the frame outside the box."""
from __future__ import annotations

import copy
import json

import pytest

from bti.identity.apply import _Applier
from bti.media import contentbox as CB

from test_apply import MARK_IDS, TITLE_ID, by_id, raking

MAIN = "arnolfini_portrait"


def with_box(sb, fractions=(0.14, 0.06, 0.86, 0.95), how="found"):
    out = copy.deepcopy(sb)
    a = out["assets"][MAIN]
    w, h = a["width"], a["height"]
    box = (w * fractions[0], h * fractions[1], w * fractions[2], h * fractions[3])
    a["content_box"] = CB.record(box, how)
    return out, tuple(float(a["content_box"][k]) for k in CB.FIELDS)


def keys(shot):
    return [(k["cx"], k["cy"], k["zoom"]) for k in shot["params"]["camera"]]


def test_the_whole_keys_fit_and_centre_the_painted_area_and_are_what_they_were_without_a_box(sb, style, timing):
    a = sb["assets"][MAIN]
    app = _Applier(copy.deepcopy(sb), "raking", style, timing, {"main_asset": MAIN})
    plain = app.whole_keys(MAIN)
    w, h = float(a["width"]), float(a["height"])
    z = 95.5 / 100 * 1080 / h
    assert [(k["cx"], k["cy"], k["zoom"]) for k in plain] == [(round(w / 2, 2), round(h / 2, 2), round(z, 5)), (round(w / 2, 2), round(h / 2, 2), round(z * 1.03, 5))]
    boxed, box = with_box(sb)
    app = _Applier(copy.deepcopy(boxed), "raking", style, timing, {"main_asset": MAIN})
    k0, k1 = app.whole_keys(MAIN)
    zb = 95.5 / 100 * 1080 / (box[3] - box[1])
    assert (k0["cx"], k0["cy"]) == (round((box[0] + box[2]) / 2, 2), round((box[1] + box[3]) / 2, 2)) and k0["zoom"] == pytest.approx(zb, abs=2e-5)
    assert k1["zoom"] == pytest.approx(zb * 1.03, abs=2e-5) and zb > z
    assert CB.holds_whole(box, k0["cx"], k0["cy"], k0["zoom"]) and CB.holds_whole(box, k1["cx"], k1["cy"], k1["zoom"]), "the push of 3% keeps the painting whole"


def test_the_box_of_another_picture_is_not_used_and_a_box_that_is_not_usable_is_not_a_box(sb, style, timing):
    boxed, _ = with_box(sb)
    boxed["assets"]["other"] = {**boxed["assets"][MAIN], "content_box": {"x0": 1, "y0": 1, "x1": 50, "y1": 50, "how": "found"}}
    app = _Applier(boxed, "raking", style, timing, {"main_asset": MAIN})
    assert app.box_of("other") is None
    bad = copy.deepcopy(sb)
    bad["assets"][MAIN]["content_box"] = {"x0": 500, "y0": 0, "x1": 100, "y1": 100}
    assert _Applier(bad, "raking", style, timing, {"main_asset": MAIN}).box_of(MAIN) is None


def test_the_keys_a_mark_or_the_beat_get_never_show_more_than_one_per_cent_outside_the_box(sb, style, timing):
    boxed, box = with_box(sb, (0.2, 0.1, 0.8, 0.9))                # a ground a fifth wide at each side: the cameras of the fixture were made for the whole file
    out, rep = raking(boxed, style, timing, {"main_asset": MAIN})
    plain, _ = raking(sb, style, timing, {"main_asset": MAIN})
    changed = 0
    for sid in MARK_IDS + [TITLE_ID]:
        s = by_id(out, sid)
        if (s.get("slots") or {}).get("image", {}).get("asset") != MAIN:
            continue
        for k in s["params"]["camera"]:
            assert CB.outside_share(box, k["cx"], k["cy"], k["zoom"]) <= CB.OFF_LIMIT + 1e-9, (sid, k)
        changed += keys(s) != keys(by_id(plain, sid))
    assert changed, "at least one of them was moved or tightened (the fixture's cameras go past this box)"


def test_a_key_that_is_inside_comes_back_as_it_was_not_even_its_number_type_changes(sb, style, timing):
    boxed, box = with_box(sb)
    app = _Applier(copy.deepcopy(boxed), "raking", style, timing, {"main_asset": MAIN})
    inside = [{"at": {"rel": 0.0}, "cx": (box[0] + box[2]) / 2, "cy": (box[1] + box[3]) / 2, "zoom": 1, "ease": "linear"}]
    assert app.in_box(MAIN, inside) == inside and app.in_box(MAIN, inside)[0]["zoom"] == 1 and isinstance(app.in_box(MAIN, inside)[0]["zoom"], int)
    other = [{"at": {"rel": 0.0}, "cx": 0, "cy": 0, "zoom": 5.0, "ease": "linear"}]
    assert app.in_box("not_the_main_painting", other) == other and app.in_box(MAIN, None) is None and app.in_box(MAIN, []) == []


def test_applying_twice_gives_the_same_document_with_a_box_too(sb, style, timing):
    boxed, _ = with_box(sb, (0.2, 0.1, 0.8, 0.9))
    once, _ = raking(boxed, style, timing, {"main_asset": MAIN})
    twice, _ = raking(once, style, timing, {"main_asset": MAIN})
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_a_storyboard_with_no_box_gets_keys_that_are_not_touched_the_numbers_of_the_contract_are_the_existing_tests(sb, style, timing):
    """No `content_box` in the assets: `in_box` hands the keys back as the very same list, so everything the applier wrote before is written again (test_apply.py proves the numbers)."""
    app = _Applier(copy.deepcopy(sb), "raking", style, timing, {"main_asset": MAIN})
    wide = [{"at": {"rel": 0.0}, "cx": 0, "cy": 0, "zoom": 9.0, "ease": "linear"}]
    assert app.box_of(MAIN) is None and app.in_box(MAIN, wide) is wide


def test_fit_camera_to_box_shared_helper_unit(sb, tmp_path):
    from PIL import Image
    from bti import identity as ID
    from bti.media import contentbox as CB

    sample = [{"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": 0.49},
              {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": 0.51}]
    snap = json.loads(json.dumps(sample))
    assert ID.fit_camera_to_box(None, sample) == (sample, [])
    assert ID.fit_camera_to_box({}, None) == (None, [])
    assert ID.fit_camera_to_box({"kind": "image", "width": 3840, "height": 5253}, sample) == (sample, [])

    # Whole-file painting on disk without content_box: project_dir lets it find (0, 0, w, h) and clamp key 0 without mutating input.
    p = tmp_path / "paint.jpg"
    Image.new("RGB", (3840, 5253), (120, 95, 70)).save(p, quality=85)
    asset = {"file": "paint.jpg", "kind": "image", "width": 3840, "height": 5253}
    fitted, moved = ID.fit_camera_to_box(asset, sample, tmp_path)
    assert len(moved) == 1 and moved[0]["index"] == 0 and moved[0]["share"] > 0.01
    assert sample == snap
    assert CB.outside_share((0, 0, 3840, 5253), fitted[0]["cx"], fitted[0]["cy"], fitted[0]["zoom"]) <= 0.01

    # Stored content_box works without project_dir, and a full-painting pull-back stays untouched.
    boxed = {**asset, "content_box": [0.1, 0.1, 0.9, 0.9]}
    pullback = [{"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": 0.2}]
    assert ID.fit_camera_to_box(boxed, pullback) == (pullback, [])
