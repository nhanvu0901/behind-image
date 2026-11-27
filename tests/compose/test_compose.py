import json
from pathlib import Path

from bti.compose import compose
from bti.engine import registry
from bti.engine import storyboard
from bti.engine.timing import Timing


def fixture(name):
    root = Path(__file__).parents[1] / "visual" / "fixtures" / name
    return tuple(json.loads((root / (part + ".json")).read_text(encoding="utf-8"))
                 for part in ("visual", "timing", "picks"))


def test_landscape_is_deterministic_and_engine_valid():
    visual, timing, picks = fixture("landscape")
    first, notes = compose(visual, timing, picks, {"id": "gae"})
    second, other_notes = compose(visual, timing, picks, {"id": "gae"})
    assert first == second and notes == other_notes
    assert json.dumps(first, ensure_ascii=False).encode() == json.dumps(second, ensure_ascii=False).encode()
    issues = storyboard.validate(first, Timing(timing), registry.load_bundle("gae"))
    assert not [issue for issue in issues if issue["level"] == "error"]
    assert all(shot.get("moment") for shot in first["shots"])


def test_intro_and_picture_caption_are_only_sourced_from_script_and_pool():
    visual, timing, picks = fixture("landscape")
    visual["moments"] = visual["moments"][:2]
    timing["duration"] = 9.0
    for word in timing["words"][5:]:
        word["s"] += 1.5
        word["e"] += 1.5
    visual["cast"][0].update(kind="place", name="Village", strip=True, sub="by the water")
    visual["moments"][0]["say"] = [{"intro": "village", "word": 1}]
    picks["assets"]["B"] = {"kind": "image", "file": "b.png", "width": 400, "height": 300, "caption": "A river view"}
    visual["moments"][1]["show"] = {"picture": "B"}
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert sb["shots"][0]["overlays"][0]["params"]["text"] == "Village"
    assert sb["shots"][0]["overlays"][0]["params"]["pop_in_s"] == 0
    assert sb["shots"][0]["overlays"][0]["params"]["fade_out_s"] == 0
    assert sb["shots"][1]["overlays"][0]["params"]["title"] == "A river view"
    issues = storyboard.validate(sb, Timing(timing), registry.load_bundle("gae"))
    assert not [issue for issue in issues if issue["level"] == "error"]


def test_unresolved_map_uses_declared_fallback_and_notes():
    visual, timing, picks = fixture("landscape")
    visual["moments"][0]["show"] = {"map": {"places": ["A", "B"]}, "else": {"region": "VILLAGE"}}
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert sb["shots"][0]["slots"]["image"]["region"] == "VILLAGE"
    assert any(n["moment"] == "m0001" and n["rule"] == "C7" for n in notes)


def test_points_only_mark_small_non_person_targets():
    visual, timing, picks = fixture("landscape")
    visual["moments"][0]["show"] = {"whole": True}
    visual["moments"][0]["say"] = [{"point": [{"region": "VILLAGE", "word": 0}]}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert sb["shots"][0]["overlays"][0]["technique"] == "HI-01"
    assert sb["shots"][0]["overlays"][0]["params"]["floor"] >= 0.6
    visual["cast"][0]["kind"] = "person"
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert not any(o["technique"] in ("HI-01", "AN-01") for o in sb["shots"][0]["overlays"])
    assert any(n["rule"] == "C6" for n in notes)


def test_devices_follow_intent_without_sample_data():
    visual, timing, picks = fixture("landscape")
    visual["moments"][0]["say"] = [{"read": {"region": "VILLAGE", "text": "a written phrase"}},
                                    {"number": {"text": "12", "of": "houses"}}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    overlays = {ov["technique"]: ov for ov in sb["shots"][0]["overlays"]}
    assert overlays["DOC-01"]["params"]["reading"] == "a written phrase"
    assert overlays["DOC-01"]["params"]["original"] == ""
    assert overlays["NUM-01"]["params"]["rows"][0]["value"] == "12"
    issues = storyboard.validate(sb, Timing(timing), registry.load_bundle("gae"))
    assert not [issue for issue in issues if issue["level"] == "error"]


def test_recompose_preserves_locked_shot_exactly():
    visual, timing, picks = fixture("landscape")
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    locked = sb["shots"][1]
    locked["locked"] = True
    locked["note"] = "owner edit"
    again, _ = compose(visual, timing, picks, {"id": "gae"}, sb)
    assert next(s for s in again["shots"] if s.get("moment") == locked["moment"]) == locked


def test_identity_is_applied_without_changing_locked_shots():
    visual, timing, picks = fixture("landscape")
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    assert sb.get("identity", {}).get("style")
    sb["shots"][0]["locked"] = True
    kept = sb["shots"][0].copy()
    recomposed, _ = compose(visual, timing, picks, {"id": "gae"}, sb)
    assert recomposed["shots"][0] == kept


def test_opening_uses_entire_painting_when_voice_has_lead():
    visual, timing, picks = fixture("landscape")
    for word in timing["words"]:
        word["s"] += 3
        word["e"] += 3
    timing["duration"] += 3
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    assert sb["shots"][0]["id"] == "s0000"
    assert sb["shots"][0]["start"] == {"t": 0.0}
    assert sb["shots"][1]["start"]["t"] < timing["words"][0]["s"]


def test_chapter_lead_becomes_identity_mark():
    visual, timing, picks = fixture("landscape")
    for word in timing["words"][25:]:
        word["s"] += 3
        word["e"] += 3
    timing["duration"] += 3
    for beat in timing["beats"]:
        beat["chapter"] = "c1" if beat["w0"] < 25 else "c2"
    timing["chapters"] = [{"id": "c1", "name": "One"},
                          {"id": "c2", "name": "Two", "lead": {"kind": "card", "start": 12.5, "end": 15.5}}]
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    assert any(shot["technique"].startswith("ID-MARK-") for shot in sb["shots"])


def test_generated_shape_valid_forms_have_no_engine_errors():
    import random
    rng = random.Random(42)
    forms = ["whole", "region", "picture", "pair", "map", "number", "point", "read", "labels"]
    for run in range(45):
        visual, timing, picks = fixture("landscape")
        for key in ("B", "C"):
            picks["assets"][key] = {"file": key + ".png", "kind": "image", "width": 400,
                                     "height": 300, "caption": "Recorded artwork"}
        for moment in visual["moments"]:
            form = rng.choice(forms)
            if form == "whole":
                moment["show"] = {"whole": True}
            elif form == "picture":
                moment["show"] = {"picture": "B"}
            elif form == "pair":
                moment["show"] = {"pair": [{"picture": "B"}, {"picture": "C"}]}
            elif form == "map":
                moment["show"] = {"map": {"places": ["A", "B"]}, "else": {"whole": True}}
            elif form == "number":
                moment["say"] = [{"number": {"text": "12", "of": "houses"}}]
            elif form == "point":
                moment["say"] = [{"point": [{"region": "VILLAGE", "word": moment["w0"]}]}]
            elif form == "read":
                moment["say"] = [{"read": {"region": "VILLAGE", "text": "Written words"}}]
            elif form == "labels":
                moment["say"] = [{"labels": [{"region": name, "text": name.title()} for name in ("VILLAGE", "RIVER", "BRIDGE")]}]
        sb, _ = compose(visual, timing, picks, {"id": "gae"})
        issues = storyboard.validate(sb, Timing(timing), registry.load_bundle("gae"))
        assert not [issue for issue in issues if issue["level"] == "error"], (run, issues)


def test_map_uses_osm_pool_record_coordinates():
    visual, timing, picks = fixture("landscape")
    picks["assets"]["map"] = {"file": "map.png", "kind": "image", "width": 400, "height": 300,
                               "title": "Map of Oslo", "credit": {"source": "osm", "source_url": "https://www.openstreetmap.org/#map=12/59.9133/10.7390"}}
    visual["moments"][0]["show"] = {"map": {"places": ["Oslo", "Bergen"], "picture": "map"}, "else": {"whole": True}}
    timing["words"][5]["s"] = 3.1
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    map_shot = next(s for s in sb["shots"] if s.get("moment") == "m0001")
    assert map_shot["technique"] == "MAP-01"
    assert map_shot["params"]["places"][0]["lonlat"] == [10.739, 59.9133]
    assert any(n["rule"] == "C7" for n in notes)


def test_module_cli_writes_requested_output(tmp_path):
    import subprocess
    import sys
    fixture_dir = Path(__file__).parents[1] / "visual" / "fixtures" / "landscape"
    output = tmp_path / "storyboard.json"
    run = subprocess.run([sys.executable, "-m", "bti.compose", str(fixture_dir), "--out", str(output)],
                         capture_output=True, text=True, check=True)
    assert not run.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["schema"] == "bti.storyboard/1"


def test_missing_label_region_is_noted_without_engine_error():
    visual, timing, picks = fixture("landscape")
    visual["moments"][0]["say"] = [{"labels": [{"region": region, "text": region} for region in ("MISSING", "RIVER", "BRIDGE")]}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert any(n["rule"] == "C7" and "MISSING" in n["what"] for n in notes)
    issues = storyboard.validate(sb, Timing(timing), registry.load_bundle("gae"))
    assert not [i for i in issues if i["level"] == "error"]


def test_strip_omits_repeated_name_from_subtitle_with_note():
    visual, timing, picks = fixture("landscape")
    subject = visual["cast"][0]
    subject.update(kind="place", name="Village", sub="the village by the river", strip=True)
    visual["moments"][0]["say"] = [{"intro": "village", "word": 0}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    strip = next(o for o in sb["shots"][0]["overlays"] if o["technique"] == "X-ANN-01")
    assert "village" not in strip["params"]["sub"].lower()
    assert any(n["rule"] == "C4" for n in notes)


def test_single_short_program_omits_device_with_note_and_validates():
    visual, timing, picks = fixture("landscape")
    visual["moments"] = visual["moments"][:1]
    visual["moments"][0]["say"] = [{"number": {"text": "12", "of": "houses"}}]
    timing["duration"] = 2.5
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert any(n["rule"] == "C8" and "NUM-01" in n["what"] for n in notes)
    issues = storyboard.validate(sb, Timing(timing), registry.load_bundle("gae"))
    assert not [i for i in issues if i["level"] == "error"]


def test_still_life_fixture_is_engine_valid_and_repeatable():
    visual, timing, picks = fixture("still_life")
    first, notes = compose(visual, timing, picks, {"id": "gae"})
    assert (first, notes) == compose(visual, timing, picks, {"id": "gae"})
    issues = storyboard.validate(first, Timing(timing), registry.load_bundle("gae"))
    assert not [i for i in issues if i["level"] == "error"]


def test_late_name_gets_room_without_repeating_it_early():
    visual, timing, picks = fixture("landscape")
    member = visual["cast"][0]
    member.update(kind="person", name="A Person", strip=True, sub="")
    visual["moments"][0]["say"] = [{"intro": member["id"], "word": 4}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    shot = next(s for s in sb["shots"] if s.get("moment") == "m0001")
    strip = next(o for o in shot["overlays"] if o["technique"] == "X-ANN-01")
    assert strip["start"]["t"] == timing["words"][4]["s"]
    assert strip["dur"] >= 1.5
    assert any(n["rule"] == "C4" for n in notes)


def test_locked_start_near_cut_does_not_create_a_flash():
    visual, timing, picks = fixture("landscape")
    first, _ = compose(visual, timing, picks, {"id": "gae"})
    first["shots"][1]["start"] = {"t": 2.9}
    first["shots"][1]["locked"] = True
    locked = first["shots"][1].copy()
    result, notes = compose(visual, timing, picks, {"id": "gae"}, first)
    assert locked in result["shots"]
    spans = [Timing(timing).resolve(s["start"]) for s in result["shots"]] + [timing["duration"]]
    assert all(b - a >= 2.5 - 1e-6 for a, b in zip(spans, spans[1:]) if b != 5.0)
    assert any(n["rule"] == "C8" for n in notes)


def test_caption_comes_from_pool_after_recompose():
    visual, timing, picks = fixture("landscape")
    picks["assets"]["B"] = {"kind": "image", "file": "b.png", "width": 400, "height": 300, "caption": "Pool caption"}
    visual["moments"][1]["show"] = {"picture": "B"}
    visual["moments"][2]["show"] = {"picture": "B"}
    first, _ = compose(visual, timing, picks, {"id": "gae"})
    first["assets"]["B"].pop("caption", None)
    second, _ = compose(visual, timing, picks, {"id": "gae"}, first)
    picture = next(s for s in second["shots"] if s.get("moment") == "m0002")
    assert any(o["technique"] == "X-ANN-02" and o["params"]["title"] == "Pool caption" for o in picture["overlays"])


def test_region_shots_of_low_resolution_fixture_fill_the_frame():
    visual, timing, picks = fixture("landscape")
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    for shot in sb["shots"]:
        slot = shot.get("slots", {}).get("image", {})
        if slot.get("region"):
            for key in shot["params"]["camera"]:
                assert key["zoom"] * 400 >= 1920 - 0.1
                assert key["zoom"] * 300 >= 1080 - 0.1


def test_point_inside_person_box_is_not_marked():
    visual, timing, picks = fixture("landscape")
    regions = picks["assets"]["A"]["regions"]
    regions["FIGURE"] = {"x": 200, "y": 150, "rx": 170, "ry": 125}
    regions["BOOK"] = {"x": 200, "y": 150, "rx": 5, "ry": 5}
    visual["cast"].append({"id": "person", "kind": "person", "name": "A person", "also": [], "strip": False, "sub": "", "shown_by": [{"region": "FIGURE"}]})
    visual["moments"][0]["show"] = {"whole": True}
    visual["moments"][0]["say"] = [{"point": [{"region": "BOOK", "word": 0}]}]
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    assert not any(o["technique"] == "HI-01" for o in sb["shots"][0]["overlays"])


def test_point_partially_overlapping_person_is_not_assumed_person():
    visual, timing, picks = fixture("landscape")
    regions = picks["assets"]["A"]["regions"]
    regions["HEAD"] = {"x": 150, "y": 150, "rx": 12, "ry": 12}
    regions["BAND"] = {"x": 170, "y": 150, "rx": 12, "ry": 12}
    visual["cast"].append({"id": "p", "kind": "person", "name": "A person", "also": [], "strip": False, "sub": "", "shown_by": [{"region": "HEAD"}]})
    visual["moments"][0]["show"] = {"whole": True}
    visual["moments"][0]["say"] = [{"point": [{"region": "BAND", "word": 0}]}]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    assert any(o["technique"] == "HI-01" for o in sb["shots"][0]["overlays"])


def test_pair_uses_simultaneous_panels_and_captions():
    visual, timing, picks = fixture("landscape")
    for key in ("B", "C"):
        picks["assets"][key] = {"file": key + ".png", "kind": "image", "width": 400, "height": 300, "caption": key + " caption"}
    visual["moments"][0]["show"] = {"pair": [{"picture": "B"}, {"picture": "C"}]}
    visual["moments"][1]["show"] = visual["moments"][0]["show"]
    sb, notes = compose(visual, timing, picks, {"id": "gae"})
    shot = next(s for s in sb["shots"] if s.get("moment") == "m0001")
    assert shot["params"]["entrance"] == "together"
    assert shot["params"]["caption_left"] == "B caption"
    assert shot["params"]["caption_right"] == "C caption"


def test_caption_remains_fully_visible_through_borrowed_shot():
    visual, timing, picks = fixture("landscape")
    picks["assets"]["B"] = {"kind": "image", "file": "b.png", "width": 400, "height": 300, "caption": "A caption"}
    visual["moments"][1]["show"] = {"picture": "B"}
    visual["moments"][2]["show"] = {"picture": "B"}
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    shot = next(s for s in sb["shots"] if s.get("moment") == "m0002")
    caption = next(o for o in shot["overlays"] if o["technique"] == "X-ANN-02")
    assert caption["params"]["pop_in_s"] == 0
    assert caption["params"]["fade_out_s"] == 0


def test_filled_fixture_cameras_still_target_distinct_regions():
    visual, timing, picks = fixture("landscape")
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    village = next(s for s in sb["shots"] if s.get("moment") == "m0001")
    hill = next(s for s in sb["shots"] if s.get("moment") == "m0006")
    assert village["params"]["camera"][-1]["cy"] != hill["params"]["camera"][-1]["cy"]


def test_borrowed_picture_before_chapter_mark_keeps_its_floor():
    visual, timing, picks = fixture("landscape")
    for word in timing["words"][25:]:
        word["s"] += 3
        word["e"] += 3
    timing["duration"] += 3
    for beat in timing["beats"]:
        beat["chapter"] = "c1" if beat["w0"] < 25 else "c2"
    timing["chapters"] = [{"id": "c1", "name": "One"}, {"id": "c2", "name": "Two", "lead": {"kind": "card", "start": 12.5, "end": 15.5}}]
    picks["assets"]["B"] = {"file": "b.png", "kind": "image", "width": 400, "height": 300, "caption": "A painting"}
    visual["moments"][4]["show"] = {"picture": "B"}
    sb, _ = compose(visual, timing, picks, {"id": "gae"})
    tm = Timing(timing)
    times = [tm.resolve(s["start"]) for s in sb["shots"]] + [timing["duration"]]
    picture_index = next(i for i,s in enumerate(sb["shots"]) if s.get("slots", {}).get("image", {}).get("asset") == "B")
    assert times[picture_index + 1] - times[picture_index] >= 3.0 - 1e-6


def test_person_like_region_name_alone_does_not_block_a_mark():
    visual, timing, picks = fixture('landscape')
    picks['assets']['A']['regions']['HAND'] = {'x': 200, 'y': 150, 'rx': 5, 'ry': 5}
    visual['moments'][0]['show'] = {'whole': True}
    visual['moments'][0]['say'] = [{'point': [{'region': 'HAND', 'word': 0}]}]
    sb, _ = compose(visual, timing, picks, {'id': 'gae'})
    assert any(o['technique'] == 'HI-01' for o in sb['shots'][0]['overlays'])
