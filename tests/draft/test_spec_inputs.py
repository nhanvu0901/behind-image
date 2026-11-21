import json

import pytest

from bti.draft import spec as S
from bti.draft.inputs import DraftError, load_inputs, normalize_timing
from helpers import GOOD, shot, spec, synth_timing


def test_good_spec_has_no_problem():
    for cid, sp in GOOD.items():
        clean, probs = S.shape_problems(sp, cid)
        assert probs == [] and len(clean["shots"]) == len(sp["shots"])


@pytest.mark.parametrize("bad,code", [
    (shot("b1", -1), "shot_start_word"), (shot("b1", "3"), "shot_start_word"), ({"start_word": 1, "technique": "CAM-01"}, "shot_beat"),
    (shot("b1", 1, slots={"image": "A"}), "shot_slots"), (shot("b1", 1, params=[1]), "shot_params"),
    (shot("b1", 1, overlays=[{"technique": "HI-01"}]), "overlay_start_word")])
def test_bad_shapes_name_chapter_and_shot_and_are_dropped(bad, code):
    clean, probs = S.shape_problems(spec("c01", shot("b0001", 0), bad), "c01")
    errs = [p for p in probs if p["level"] == "error"]
    assert errs and errs[0]["code"] == code
    assert errs[0]["message"].startswith("chapter c01, shot 2")
    if not code.startswith("overlay"):
        assert len(clean["shots"]) == 1


def test_unknown_keys_are_warnings_and_not_an_object_is_an_error():
    s = shot("b0001", 0)
    s["colour"] = "red"
    _, probs = S.shape_problems(spec("c01", s), "c01")
    assert [p["code"] for p in probs] == ["shot_unknown_key"] and probs[0]["level"] == "warn"
    assert S.shape_problems([], "c01")[1][0]["code"] == "spec_not_object"
    assert S.shape_problems({"schema": "bti.draft/1", "chapter": "c01", "shots": []}, "c01")[1][0]["code"] == "spec_no_shots"


def test_load_spec_reports_missing_and_bad_json(tmp_path):
    assert S.load_spec(tmp_path / "c01.json", "c01")[1][0]["code"] == "spec_missing"
    (tmp_path / "c01.json").write_text("{nope", encoding="utf-8")
    assert S.load_spec(tmp_path / "c01.json", "c01")[1][0]["code"] == "spec_json"


def test_regions_are_checked_in_source_pixels():
    assets = {"A": {"width": 800, "height": 1200}}
    clean, probs = S.regions_problems({"A": {"EYE": {"x": 100, "y": 200, "rx": 10, "ry": 10, "label": "Eye"}, "BAD": {"x": 5000, "y": 1}}, "Z": {}}, assets)
    assert list(clean["A"]) == ["EYE"] and {p["code"] for p in probs} == {"region_outside", "regions_asset"}


def test_normalize_timing_makes_ids_and_ranges():
    raw = synth_timing()
    for b in raw["beats"]:
        b.pop("id")
        b["chapter"] = "Intro" if b["w0"] < 30 else "The mirror"
    for c in raw["chapters"]:
        c.pop("id")
    t = normalize_timing(raw)
    assert [c["id"] for c in t["chapters"]] == ["c01", "c02"] and t["beats"][0]["id"] == "b0001" and t["beats"][5]["chapter"] == "c02"
    assert t["chapters"][1]["card"] is True and (t["chapters"][0]["w0"], t["chapters"][0]["w1"]) == (0, 30)


def test_normalize_timing_refuses_bad_ranges():
    raw = synth_timing()
    raw["beats"][0]["w1"] = 999
    with pytest.raises(DraftError) as e:
        normalize_timing(raw)
    assert e.value.code == "timing_shape"


def test_load_inputs(proj):
    inp = load_inputs(proj)
    assert inp.chapter_ids() == ["c01", "c02"] and inp.current is None and inp.picks["main_asset"] == "A"
    assert inp.hashes()["timing"] and inp.title == proj.name
    with pytest.raises(DraftError) as e:
        load_inputs(proj, ["c01"])
    assert e.value.code == "scope_needs_storyboard"
    with pytest.raises(DraftError) as e:
        load_inputs(proj, ["zz"])
    assert e.value.code == "unknown_chapter"


def test_load_inputs_needs_main_asset(proj):
    p = json.loads((proj / "picks.json").read_text())
    p["main_asset"] = "nope"
    (proj / "picks.json").write_text(json.dumps(p))
    with pytest.raises(DraftError) as e:
        load_inputs(proj)
    assert e.value.code == "picks_no_main"
