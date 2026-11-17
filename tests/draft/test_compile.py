import copy
import json

import pytest

from bti.draft.compile import compile_specs, summary_text
from bti.draft.decompile import clean
from bti.draft.inputs import load_inputs
from bti.draft.providers import auto
from bti.engine.timing import Timing
from helpers import GOOD, clean_spec, shot, spec


def good(proj):
    inp = load_inputs(proj)
    return inp, {c: clean_spec(s, c) for c, s in GOOD.items()}


def times(inp, doc):
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    return [tm.resolve(s["start"]) for s in doc["shots"]]


def test_tiling_anchors_and_first_shot(proj):
    inp, specs = good(proj)
    res = compile_specs(inp, specs, draw=False)
    assert not res.errors, summary_text(res)
    ts = times(inp, res.storyboard)
    assert ts[0] == 0.0 and all(b > a for a, b in zip(ts, ts[1:]))
    for s in res.storyboard["shots"]:
        a = s["start"]
        if "w" in a:
            assert a["text"] == inp.timing["words"][a["w"]]["w"]
    assert res.storyboard["end"]["t"] == pytest.approx(inp.timing["duration"], abs=1e-3)
    assert res.storyboard["schema"] == "bti.storyboard/1" and all(s["source"] == "agent" and s["locked"] is False for s in res.storyboard["shots"])


def test_ids_are_unique_and_sequential(proj):
    inp, specs = good(proj)
    res = compile_specs(inp, specs, draw=False)
    ids = [s["id"] for s in res.storyboard["shots"]]
    assert len(set(ids)) == len(ids) and ids[0] == "s0001"


def test_chapter_card_sits_in_the_silence(proj):
    inp, specs = good(proj)
    res = compile_specs(inp, specs, draw=False)
    cards = [s for s in res.storyboard["shots"] if s["technique"] == "X-CARD-01"]
    assert len(cards) == 1 and cards[0]["params"]["title"] == "THE MIRROR"
    c2 = inp.timing["chapters"][1]
    assert cards[0]["start"]["t"] == pytest.approx(c2["start"] - 2.8, abs=0.01)
    ts = times(inp, res.storyboard)
    i = res.storyboard["shots"].index(cards[0])
    assert ts[i + 1] == pytest.approx(c2["start"], abs=0.01)           # the card ends where chapter 2 begins


def test_title_card_only_when_the_silence_is_long(proj_title_card, proj):
    inp = load_inputs(proj_title_card)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert [s["technique"] for s in res.storyboard["shots"]].count("X-CARD-02") == 1
    assert not res.errors, summary_text(res)
    res2 = compile_specs(load_inputs(proj), {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert "X-CARD-02" not in [s["technique"] for s in res2.storyboard["shots"]]


def test_defaults_are_filled_and_regions_aimed(proj):
    inp, specs = good(proj)
    res = compile_specs(inp, specs, draw=False)
    s = res.storyboard["shots"][1]
    assert s["technique"] == "CAM-05" and s["slots"]["image"]["asset"] == "A"
    cam = s["params"]["camera"]
    assert len(cam) == 2 and (cam[-1]["cx"], cam[-1]["cy"]) == (400.0, 300.0) and cam[-1]["zoom"] > cam[0]["zoom"]
    ov = s["overlays"][0]
    assert ov["id"] == "o1" and ov["params"]["at"] == "MIRROR" and ov["params"]["rx"] == 80 and ov["dur"] > 0
    assert ov["start"]["text"] == "w12"


def test_missing_image_slot_uses_the_pick_then_the_main_painting(proj):
    inp = load_inputs(proj)
    sp = {"c01": clean_spec(spec("c01", shot("b0001", 0, slots={}), shot("b0002", 10, slots={}), shot("b0003", 20, slots={})), "c01"), "c02": clean_spec(GOOD["c02"], "c02")}
    res = compile_specs(inp, sp, draw=False)
    sh = res.storyboard["shots"]
    assert sh[0]["slots"]["image"]["asset"] == "A" and sh[1]["slots"]["image"]["asset"] == "A"
    assert sh[1]["params"]["camera"][-1]["cx"] == 400.0           # b0002's pick has the MIRROR region


def test_every_issue_names_chapter_and_shot(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][1]["technique"] = "NOPE-9"
    specs["c02"]["shots"][0]["slots"]["image"]["asset"] = "ZZ"
    res = compile_specs(inp, specs, draw=False)
    errs = {(i["chapter"], i["shot"]): i for i in res.errors}
    assert ("c01", 2) in errs and ("c02", 1) in errs
    assert errs[("c01", 2)]["engine_code"] == "unknown_technique" and errs[("c02", 1)]["engine_code"] == "asset_undefined"
    assert all(i["message"].startswith("chapter c0") for i in res.errors)
    assert errs[("c02", 1)]["field"] == "slots.image.asset"
    assert "chapter c01, shot 2" in summary_text(res)


def test_spec_problems_beat_and_order(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][1]["beat"] = "b0005"
    specs["c02"]["shots"].append(dict(copy.deepcopy(specs["c02"]["shots"][1]), _n=4))
    res = compile_specs(inp, specs, draw=False)
    codes = {i["code"] for i in res.errors}
    assert "beat_other_chapter" in codes and "shot_order" in codes


def test_first_shot_is_moved_to_the_chapter_start(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][0]["start_word"] = 3
    res = compile_specs(inp, specs, draw=False)
    assert "chapter_start_moved" in {i["code"] for i in res.issues}
    assert times(inp, res.storyboard)[0] == 0.0


def test_overlay_is_clamped_and_outside_overlay_is_reported(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][1]["overlays"][0]["end_word"] = 28           # far beyond the shot
    specs["c01"]["shots"][2]["overlays"] = [{"technique": "HI-01", "start_word": 5, "params": {"at": "MIRROR"}}]
    res = compile_specs(inp, specs, draw=False)
    sh = res.storyboard["shots"]
    ts = times(inp, res.storyboard)
    o = sh[1]["overlays"][0]
    tm = Timing({"duration": 100, "words": inp.timing["words"]})
    assert tm.resolve(o["start"]) + o["dur"] <= ts[2] + 1e-6
    assert any(i["code"] == "overlay_outside_shot" and i["shot"] == 3 and i["overlay"] == 1 for i in res.errors)
    assert sh[2]["overlays"] == []


def test_narration_on_screen_is_refused(proj):
    inp, specs = good(proj)
    text = " ".join(w["w"] for w in inp.timing["words"][12:18])
    specs["c01"]["shots"][1]["overlays"].append({"technique": "X-ANN-01", "start_word": 13, "dur": 2.0, "params": {"text": text}})
    res = compile_specs(inp, specs, draw=False)
    bad = [i for i in res.errors if i["code"] == "narration_on_screen"]
    assert bad and bad[0]["chapter"] == "c01" and bad[0]["shot"] == 2 and bad[0]["overlay"] == 2
    assert len(res.storyboard["shots"][1]["overlays"]) == 1


def test_short_label_is_fine(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][1]["overlays"].append({"technique": "X-ANN-01", "start_word": 13, "dur": 2.0, "params": {"text": "Mirror"}})
    assert not [i for i in compile_specs(inp, specs, draw=False).errors]


def test_shorts_only_technique_is_an_error(proj):
    inp, specs = good(proj)
    specs["c02"]["shots"][1]["technique"] = "SHORT-02"
    res = compile_specs(inp, specs, draw=False)
    assert any(i["code"] == "shorts_only_technique" and i["shot"] == 2 for i in res.errors)


def test_pacing_warnings(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"].insert(1, dict(shot("b0001", 1), _n=9))          # a 0.5 s shot
    res = compile_specs(inp, specs, draw=False)
    assert any(i["code"] == "pacing_short" for i in res.warnings)


def test_draw_check_passes_on_synthetic_project(proj):
    inp, specs = good(proj)
    res = compile_specs(inp, specs, draw=True)
    assert res.drawn and not res.errors, summary_text(res)


def test_degrade_replaces_a_broken_shot_and_fills_a_missing_chapter(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][2]["params"] = {"camera": [{"at": {"rel": 0.0}, "cx": 1, "cy": 1, "zoom": -5}]}
    del specs["c02"]
    plain = compile_specs(inp, specs, draw=False)
    assert plain.errors
    res = compile_specs(inp, specs, draw=False, degrade=True)
    assert not res.errors, summary_text(res)
    assert res.degraded and "chapter_filled_by_auto" in {i["code"] for i in res.issues}
    assert any(o["chapter"] == "c02" for o in res.origin)


def test_locked_shots_pass_through_untouched_and_ids_are_kept(proj):
    inp, specs = good(proj)
    first = compile_specs(inp, specs, draw=False).storyboard
    cur = copy.deepcopy(first)
    cur["shots"][2]["locked"] = True
    cur["shots"][2]["note"] = "owner kept this"
    cur["shots"][2]["source"] = "human"
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    inp2 = load_inputs(proj)
    specs2 = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs2["c01"]["shots"][2]["technique"] = "STATIC-01"                    # the agent "changes" the locked shot
    res = compile_specs(inp2, specs2, draw=False)
    new = {s["id"]: s for s in res.storyboard["shots"]}
    assert clean(new[cur["shots"][2]["id"]]) == clean(cur["shots"][2])
    assert [s["id"] for s in res.storyboard["shots"]] == [s["id"] for s in cur["shots"]]       # same words, same ids
    res3 = compile_specs(inp2, dict(specs2, c02=clean_spec(spec("c02", shot("b0004", 30), shot("b0005", 40), shot("b0005", 45, "CAM-03"), shot("b0006", 50)), "c02")), draw=False)
    ids = [s["id"] for s in res3.storyboard["shots"]]
    assert max(int(i[1:]) for i in ids) > max(int(s["id"][1:]) for s in cur["shots"])          # a new shot gets a new id


def test_new_ids_never_reuse_reserved_ones(proj):
    inp, specs = good(proj)
    inp.reserved_ids = ["s0020"]
    res = compile_specs(inp, specs, draw=False)
    assert min(int(s["id"][1:]) for s in res.storyboard["shots"]) == 21


def test_assets_merge_storyboard_wins_and_regions_are_added(proj):
    inp, specs = good(proj)
    cur = compile_specs(inp, specs, draw=False).storyboard
    cur["assets"]["A"]["regions"]["MIRROR"]["rx"] = 123
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    inp2 = load_inputs(proj)
    regions = {"A": {"NEWSPOT": {"x": 10, "y": 20, "rx": 5, "ry": 5, "label": "New"}, "MIRROR": {"x": 1, "y": 1, "label": "x"}}}
    res = compile_specs(inp2, specs, regions=regions, draw=False)
    r = res.storyboard["assets"]["A"]["regions"]
    assert r["MIRROR"]["rx"] == 123 and r["NEWSPOT"]["x"] == 10
    assert any(i["code"] == "region_exists" for i in res.warnings)


def test_partial_redraft_keeps_other_chapters(proj):
    inp, specs = good(proj)
    cur = compile_specs(inp, specs, draw=False).storyboard
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    inp2 = load_inputs(proj, ["c01"])
    specs2 = {"c01": clean_spec(spec("c01", shot("b0001", 0, "CAM-03"), shot("b0002", 10), shot("b0003", 20)), "c01")}
    res = compile_specs(inp2, specs2, draw=False)
    assert not res.errors, summary_text(res)
    old_c2 = [s for s in cur["shots"] if s["start"].get("w", 0) >= 30 or s["technique"] == "X-CARD-01"]
    new_c2 = [s for s in res.storyboard["shots"] if s["start"].get("w", 0) >= 30 or s["technique"] == "X-CARD-01"]
    assert [clean(s) for s in new_c2] == [clean(s) for s in old_c2]
    assert res.storyboard["shots"][0]["technique"] == "CAM-03"


def test_auto_specs_compile_clean_with_draw(proj):
    inp = load_inputs(proj)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in auto.draft(inp).items()}, draw=True)
    assert not res.errors, summary_text(res)


def _shift_timing(proj, by, leads):
    t = json.loads((proj / "timing.json").read_text())
    for w in t["words"]:
        w["s"], w["e"] = round(w["s"] + by, 3), round(w["e"] + by, 3)
    for b in t["beats"]:
        b["start"], b["end"] = round(b["start"] + by, 3), round(b["end"] + by, 3)
    for i, c in enumerate(t["chapters"]):
        if i:
            c["start"] = round(c["start"] + by, 3)
        c["end"] = round(c["end"] + by, 3)
        if leads.get(c["id"]):
            c["lead"] = leads[c["id"]]
    t["duration"] += by
    (proj / "timing.json").write_text(json.dumps(t))


def test_cards_are_placed_from_the_lead_of_the_timing(proj):
    t = json.loads((proj / "timing.json").read_text())
    w30 = t["words"][30]["s"]
    c1_end = t["chapters"][0]["end"]
    t["chapters"][1]["lead"] = {"kind": "card", "start": round(c1_end + 0.2, 3), "end": round(w30 - 0.1, 3)}
    t["chapters"][1]["card"] = False                      # the lead decides, not the flag
    (proj / "timing.json").write_text(json.dumps(t))
    inp = load_inputs(proj)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert not res.errors, summary_text(res)
    lead_end = round(w30 - 0.1, 3)
    cards = [s for s in res.storyboard["shots"] if s["technique"] == "X-CARD-01"]
    assert len(cards) == 1 and cards[0]["start"]["t"] == pytest.approx(lead_end - 2.8, abs=0.01)
    ts = times(inp, res.storyboard)
    i = res.storyboard["shots"].index(cards[0])
    assert ts[i + 1] == pytest.approx(lead_end, abs=0.01)


def test_title_lead_at_the_very_start_gives_a_title_card_first(proj):
    _shift_timing(proj, 6.0, {"c01": {"kind": "title", "start": 0.0, "end": 6.4}})
    inp = load_inputs(proj)
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert not res.errors, summary_text(res)
    sh = res.storyboard["shots"]
    assert sh[0]["technique"] == "X-CARD-02" and sh[0]["start"]["t"] == 0.0
    assert times(inp, res.storyboard)[1] == pytest.approx(6.4, abs=0.01)


def test_plain_lead_places_no_card(proj):
    t = json.loads((proj / "timing.json").read_text())
    t["chapters"][1]["lead"] = {"kind": "plain", "start": t["chapters"][0]["end"], "end": round(t["words"][30]["s"] - 0.1, 3)}
    t["chapters"][1]["card"] = False
    (proj / "timing.json").write_text(json.dumps(t))
    res = compile_specs(load_inputs(proj), {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    assert not [s for s in res.storyboard["shots"] if s["technique"].startswith("X-CARD")]


def test_a_locked_card_is_never_regenerated(proj):
    inp, specs = good(proj)
    cur = compile_specs(inp, specs, draw=False).storyboard
    card = next(s for s in cur["shots"] if s["technique"] == "X-CARD-01")
    card["locked"] = True
    card["params"]["title"] = "OWNER TITLE"
    (proj / "storyboard.json").write_text(json.dumps(cur), encoding="utf-8")
    res = compile_specs(load_inputs(proj), {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False)
    cards = [s for s in res.storyboard["shots"] if s["technique"] == "X-CARD-01"]
    assert len(cards) == 1 and clean(cards[0]) == clean(card)
