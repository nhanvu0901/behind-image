"""The new opening of every video and "fit the storyboard to the voice again" (worker introflow).

    * `bti.draft.zones`: the opening shot (the whole painting before the first word), the length of the channel-name beat, the placement of the cards;
    * the compiler writes the opening shot and the beat; `apply_identity` puts the opening on it and the three texts on the beat;
    * `off_voice` / `retime` (`bti.draft.retime`): what does not sit where the voice puts it, and putting it right, with the real engine's validator.

The timing is built the way the voice code builds it (a lead before the first word, the title silence and the 3.2 s of a card before the chapters that
have one: `tests/voice/test_intro_silences.py` proves the voice itself). The registry may not know `ID-BRAND-03` yet (the renderer is built by another
worker): the fixture `brand03` adds it for the test when it is missing (a copy of the entry of `ID-BRAND-01` with the contract's three texts) and takes it
away again; once the real entry exists it does nothing."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bti import identity as ID
from bti.draft import retime as RT
from bti.draft import zones as Z
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import load_inputs, normalize_timing
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.timing import Timing
from intro_helpers import CARD, CARD_LEN, SPECS, brand03, compiled, intro_timing, make_project, specs, style_doc  # noqa: F401  (brand03 is a fixture)


def times(sb: dict, timing: dict):
    tm = Timing({"duration": timing["duration"], "words": timing["words"]})
    t0 = [tm.resolve(s["start"]) for s in sb["shots"]]
    return tm, t0, [*t0[1:], tm.resolve(sb["end"])]


def by_technique(sb, prefix):
    return [s for s in sb["shots"] if s["technique"].startswith(prefix)]


def word_anchored(sb):
    return {s["id"]: s for s in sb["shots"] if isinstance(s.get("start"), dict) and "w" in s["start"]}


# ----------------------------------------------------------------------------------------------------------------- zones (pure)
def test_the_opening_exists_when_the_first_word_starts_at_3_3_s_or_later_and_the_video_starts_with_a_cold_open():
    t = normalize_timing(intro_timing(5.0))
    assert Z.opening_span(t["chapters"], t["words"]) == {"start": 0.0, "dur": pytest.approx(4.65)}
    for lead, has in ((0.35, False), (3.29, False), (3.3, True), (3.4, True), (15.0, True)):
        t = normalize_timing(intro_timing(lead))
        assert (Z.opening_span(t["chapters"], t["words"]) is not None) is has, lead
    t = normalize_timing(intro_timing(5.0))
    t["chapters"][0]["lead"]["kind"] = "title"                      # a video with no cold open starts with the beat: no opening shot
    assert Z.opening_span(t["chapters"], t["words"]) is None


def test_the_beat_is_9_1_s_with_the_new_silences_5_4_s_with_the_old_and_starts_1_5_s_after_the_last_word():
    t = normalize_timing(intro_timing(5.0, 10.2))
    p = Z.place(t["chapters"], t["words"], 9.1)["chapters"][1]
    last_word_end = t["chapters"][0]["end"]
    assert p["title"]["dur"] == pytest.approx(9.1) and p["title"]["start"] == pytest.approx(last_word_end + 1.5)
    assert p["card"]["dur"] == pytest.approx(2.8) and p["card"]["start"] + 2.8 == pytest.approx(p["gap"][1]) and p["title"]["start"] + 9.1 == pytest.approx(p["card"]["start"])
    t = normalize_timing(intro_timing(0.35, 6.2))
    p = Z.place(t["chapters"], t["words"], 9.1)["chapters"][1]
    assert p["title"]["dur"] == pytest.approx(5.4) and p["title"]["start"] == pytest.approx(t["chapters"][0]["end"] + 1.2)
    # a style with no nominal beat: the old 2.9 s
    assert Z.place(t["chapters"], t["words"], Z.brand_length(None, None))["chapters"][1]["title"]["dur"] == pytest.approx(2.9)
    # not enough room for the breath: the old rule min(B, gap - card)
    assert Z.title_length(9.1, 4.5, 2.8) == pytest.approx(1.7) and Z.title_length(9.1, 3.9, 2.8) == pytest.approx(1.1) and Z.title_length(9.1, 9.0, 0.0) == pytest.approx(7.8)


@pytest.mark.parametrize("w,h", [(800, 1200), (3840, 5253), (5000, 800), (1920, 1080), (1000, 1000), (300, 4000)])
def test_the_whole_painting_is_inside_the_frame_in_both_camera_keys(w, h):
    cam = Z.whole_camera(w, h, {"w": 1920, "h": 1080}, 95.5)
    assert [k["at"] for k in cam] == [{"rel": 0.0}, {"rel": 1.0}] and cam[0]["cx"] == w / 2 and cam[0]["cy"] == h / 2
    for k in cam:
        assert w * k["zoom"] <= 1920 + 1e-6 and h * k["zoom"] <= 1080 + 1e-6, (w, h, k)          # no edge of the painting outside the frame
        assert k["cx"] == cam[0]["cx"] and k["cy"] == cam[0]["cy"]
    assert 1.0 <= cam[1]["zoom"] / cam[0]["zoom"] <= 1.03 + 1e-4                                   # a push of at most 3 %
    assert cam[0]["zoom"] == pytest.approx(min(0.955 * 1080 / h, 0.955 * 1920 / w), abs=1e-5)     # the smaller of fit-by-height and fit-by-width
    assert Z.whole_camera(None, 100, None) is None and Z.whole_camera(0, 100, None) is None


def test_a_painting_that_already_fills_the_frame_is_never_pushed_out_of_it():
    cam = Z.whole_camera(1920, 1080, {"w": 1920, "h": 1080}, 100.0)
    assert cam[0]["zoom"] == 1.0 and cam[1]["zoom"] == 1.0            # at 100 % there is no room for a push: the edges stay on the frame


# --------------------------------------------------------------------------------------------------------- the compiler writes it
def test_a_full_compile_writes_the_opening_shot_the_beat_and_the_cards(tmp_path, brand03):
    timing = intro_timing(5.0, 10.2)
    res = compiled(make_project(tmp_path, timing))
    sb = res.storyboard
    tm, t0, t1 = times(sb, timing)
    first = sb["shots"][0]
    # the opening shot: from 0 to 0.35 s before the first word, the whole main painting, no overlays but the opening's own
    assert first["id"] == Z.OPENING_ID == "s0000" and first["technique"] == "CAM-01" and first["start"] == {"t": 0.0}
    assert first["slots"] == {"image": {"asset": "A"}} and first["intent"] == "establish" and first["locked"] is False and first["note"] == Z.OPENING_NOTE
    assert (t0[0], t1[0]) == (0.0, pytest.approx(5.0 - 0.35))
    cam = first["params"]["camera"]
    for k in cam:
        assert 800 * k["zoom"] <= 1920 and 1200 * k["zoom"] <= 1080
    assert [o["technique"] for o in first["overlays"]] == ["ID-OPEN-01", "ID-LABEL-01"]
    assert tm.resolve(first["overlays"][0]["start"]) == pytest.approx(0.0) and first["overlays"][0]["dur"] == pytest.approx(3.6)
    assert tm.resolve(first["overlays"][1]["start"]) == pytest.approx(1.2, abs=1e-3) and first["overlays"][1]["dur"] == pytest.approx(5.0 - 0.35 - 1.2, abs=1e-3)
    # the model's first shot starts 0.35 s before the first word
    second = sb["shots"][1]
    assert second["start"] == {"w": 0, "off": -0.35, "text": "w0"} and second["id"] != "s0000" and not [o for o in second["overlays"] if o["technique"].startswith("ID-")]
    # the beat: 9.1 s, 1.5 s after the last word of the cold open, with the three texts; the card ends where the silence ends
    beat = by_technique(sb, "ID-BRAND")[0]
    i = sb["shots"].index(beat)
    assert beat["technique"] == "ID-BRAND-03" and t1[i] - t0[i] == pytest.approx(9.1) and t0[i] == pytest.approx(timing["chapters"][0]["end"] + 1.5, abs=1e-3)
    assert beat["params"]["text"] == "RAKING LIGHT" and beat["params"]["title"] == "Intro" and beat["params"]["subtitle"] == "Some Painter, 1434"       # no video title: the painting's title (the project's, "intro" here) and artist, year
    marks = by_technique(sb, "ID-MARK")
    assert len(marks) == 2
    for m, c in zip(marks, timing["chapters"][1:]):
        j = sb["shots"].index(m)
        assert t0[j] == pytest.approx(c["card_start"], abs=1e-3) and t1[j] == pytest.approx(c["card_end"], abs=1e-3)
    assert sb["identity"] == {"style": "raking"} and sb["end"] == {"t": timing["duration"]}
    assert RT.off_voice(sb, timing, style_doc()) == []            # exactly where the voice puts it


def test_the_beat_has_the_video_title_when_the_storyboard_has_one(tmp_path, brand03):
    timing = intro_timing()
    proj = make_project(tmp_path, timing)
    first = compiled(proj).storyboard
    first["identity"]["video_title"] = "The Mirror That Remembers"
    (proj / "storyboard.json").write_text(json.dumps(first), encoding="utf-8")
    again = compiled(proj).storyboard                              # a full compile keeps the title: it belongs to the project
    beat = by_technique(again, "ID-BRAND")[0]
    assert again["identity"] == {"style": "raking", "video_title": "The Mirror That Remembers"}
    assert beat["params"]["title"] == "The Mirror That Remembers" and beat["params"]["subtitle"] == "Intro · Some Painter, 1434"


def test_a_late_first_word_is_the_only_case_with_an_opening_shot(tmp_path, brand03):
    res = compiled(make_project(tmp_path, intro_timing(1.0, 6.2)))
    sb = res.storyboard
    assert sb["shots"][0]["id"] != "s0000" and sb["shots"][0]["start"] == {"w": 0, "off": -1.0, "text": "w0"}      # as today: the model's first shot starts at 0
    assert [s["id"] for s in sb["shots"]].count("s0000") == 0
    assert RT.off_voice(sb, intro_timing(1.0, 6.2), style_doc()) == []


def test_the_old_silences_give_a_5_4_s_beat(tmp_path, brand03):
    timing = intro_timing(0.35, 6.2)
    sb = compiled(make_project(tmp_path, timing)).storyboard
    tm, t0, t1 = times(sb, timing)
    i = sb["shots"].index(by_technique(sb, "ID-BRAND")[0])
    assert t1[i] - t0[i] == pytest.approx(5.4)
    assert RT.off_voice(sb, timing, style_doc()) == []


def test_the_opening_shot_survives_an_edit_mode_compile(tmp_path, brand03):
    from bti.draft import decompile as D
    from bti.draft.inputs import clone_inputs, resolve_edit_scope
    from bti.draft.workspace import read_out
    import tempfile
    timing = intro_timing()
    proj = make_project(tmp_path, timing)
    saved = compiled(proj).storyboard
    saved["identity"]["video_title"] = "The Mirror That Remembers"
    (proj / "storyboard.json").write_text(json.dumps(saved), encoding="utf-8")
    inp0 = load_inputs(proj, None, for_edit=True)
    es, sc, _ = resolve_edit_scope(inp0, {"all": True})
    inp = clone_inputs(inp0, scope=sc, edit_shots=es)
    dec = D.decompile(inp, es)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "out").mkdir()
        for c, v in dec.items():
            if c in inp.in_scope():
                (Path(td) / "out" / (c + ".json")).write_text(json.dumps(v["spec"]), encoding="utf-8")
        out = read_out(Path(td), inp.in_scope(), {**inp.picks["assets"], **((inp.current or {}).get("assets") or {})})
        res = compile_specs(inp, out.specs, regions=out.regions, spec_problems=out.problems, degrade=False, draw=False)
    assert res.violations == [], [v["message"] for v in res.violations]
    assert json.loads(json.dumps(res.storyboard["shots"], sort_keys=True)) == json.loads(json.dumps(saved["shots"], sort_keys=True))
    assert res.storyboard["shots"][0]["id"] == "s0000"
    assert res.storyboard["identity"] == {"style": "raking", "video_title": "The Mirror That Remembers"}         # an edit keeps the video's title


def test_a_full_recompile_of_a_saved_storyboard_keeps_the_reserved_id_for_the_opening_only(tmp_path, brand03):
    timing = intro_timing()
    proj = make_project(tmp_path, timing)
    saved = compiled(proj).storyboard
    (proj / "storyboard.json").write_text(json.dumps(saved), encoding="utf-8")
    again = compiled(proj).storyboard
    ids = [s["id"] for s in again["shots"]]
    assert ids.count("s0000") == 1 and ids[0] == "s0000" and len(set(ids)) == len(ids)
    assert [s["id"] for s in saved["shots"]] == ids


# ------------------------------------------------------------------------------------------- off_voice and retime, the voice made again
def test_a_storyboard_made_for_a_voice_is_off_after_the_voice_is_assembled_again_and_retime_puts_it_right(tmp_path, brand03):
    old_t = intro_timing(5.0, 10.2)
    sb = compiled(make_project(tmp_path, old_t)).storyboard
    new_t = intro_timing(7.0, 12.0)                              # another lead and another title silence: every word moves
    off = RT.off_voice(sb, new_t, style_doc())
    codes = {p["code"] for p in off}
    assert {"title_off", "card_off", "end_off"} <= codes and "card_count" not in codes
    assert all(p["repair"] for p in off)
    out, rep = RT.retime(sb, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert RT.off_voice(out, new_t, style_doc()) == [] and rep["left"] == []
    # every shot anchored to a word is untouched, byte for byte (the opening shot only moves its overlays, which are the program's)
    for sid, s in word_anchored(sb).items():
        assert json.dumps(next(x for x in out["shots"] if x["id"] == sid), sort_keys=True) == json.dumps(s, sort_keys=True), sid
    # the beat is 9.1 s again, 1.5 s after the last word; the marks end where their silence ends; the video ends with the voice
    tm, t0, t1 = times(out, new_t)
    i = out["shots"].index(by_technique(out, "ID-BRAND")[0])
    assert t1[i] - t0[i] == pytest.approx(9.1, abs=1e-3)                    # min(9.1, 12.0 + 3.2 - 2.8 - 1.2): the nominal length
    assert t0[i] == pytest.approx(new_t["chapters"][0]["end"] + 1.5 + (12.0 - 10.2), abs=1e-3)      # the silence is 1.8 s longer: the beat starts 1.8 s later
    assert out["end"] == {"t": new_t["duration"]}
    assert [m["start"] for m in by_technique(out, "ID-MARK")] == [{"t": round(c["card_start"], 3)} for c in new_t["chapters"][1:]]
    assert out["shots"][0]["id"] == "s0000" and tm.resolve(out["shots"][1]["start"]) == pytest.approx(7.0 - 0.35)
    # no stale anchor, and the engine's validator finds no error
    assert [a for s in out["shots"] for a in [s["start"]] + [o["start"] for o in s["overlays"]] if tm.stale(a)] == []
    assert [i for i in SB.validate(out, tm, brand03) if i["level"] == "error"] == []
    # the same call twice changes nothing the second time
    again, rep2 = RT.retime(out, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert json.dumps(again, sort_keys=True) == json.dumps(out, sort_keys=True) and not rep2["moved"] and not rep2["inserted"] and rep2["end"] is None


def test_the_input_of_retime_is_never_changed(tmp_path, brand03):
    sb = compiled(make_project(tmp_path, intro_timing())).storyboard
    snap = json.dumps(sb, sort_keys=True)
    RT.retime(sb, intro_timing(8.0, 11.0), style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert json.dumps(sb, sort_keys=True) == snap


def test_an_old_layout_storyboard_is_clean_and_retime_after_a_lead_of_5_s_inserts_the_opening_shot(tmp_path, brand03):
    """Every video made so far: a lead of 0.35 s, a 2.9 s beat with ID-BRAND-01 under the style raking, the opening overlays on the first shot."""
    old_t = intro_timing(0.35, 6.2)
    sb = compiled(make_project(tmp_path, old_t)).storyboard
    tm, t0, t1 = times(sb, old_t)
    # make it the old form: the beat of 2.9 s with ID-BRAND-01 (the params of that technique), the old opening overlays (9 s and 4.5 s) on the first shot
    i = sb["shots"].index(by_technique(sb, "ID-BRAND")[0])
    beat = sb["shots"][i]
    beat["technique"], beat["start"] = "ID-BRAND-01", {"t": round(t1[i] - 2.9, 3)}
    for k in ("title", "subtitle"):
        beat["params"].pop(k, None)
    first = sb["shots"][0]
    for o in first["overlays"]:
        o["dur"] = 9.0 if o["technique"] == "ID-OPEN-01" else 4.5
    assert RT.off_voice(sb, old_t, style_doc()) == []                      # the length of the beat inside its silence is not a problem
    assert not [x for x in SB.validate(sb, tm, brand03) if x["code"] == "identity_technique_mismatch"]      # ID-BRAND-01 under raking is the earlier form of the style
    new_t = intro_timing(5.0, 10.2)                                        # the voice is assembled again with the new silences
    codes = [p["code"] for p in RT.off_voice(sb, new_t, style_doc())]
    assert "first_shot_late" in codes and "opening_missing" in codes and "title_off" in codes and "card_off" in codes and "end_off" in codes
    out, rep = RT.retime(sb, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert rep["inserted"] == ["s0000"] and out["shots"][0]["id"] == "s0000" and out["shots"][0]["start"] == {"t": 0.0}
    assert RT.off_voice(out, new_t, style_doc()) == [] and rep["left"] == []
    ov = [o["technique"] for o in out["shots"][0]["overlays"]]
    assert ov == ["ID-OPEN-01", "ID-LABEL-01"]                             # the opening overlays moved onto the opening shot ...
    assert not [o for o in out["shots"][1]["overlays"] if o["technique"].startswith("ID-")]       # ... and left the model's first shot
    assert out["shots"][1]["start"] == {"w": 0, "off": -0.35, "text": "w0"}
    assert by_technique(out, "ID-BRAND")[0]["technique"] == "ID-BRAND-03" and by_technique(out, "ID-BRAND")[0]["params"]["subtitle"] == "Some Painter, 1434"
    tm2, a, b = times(out, new_t)
    k = out["shots"].index(by_technique(out, "ID-BRAND")[0])
    assert b[k] - a[k] == pytest.approx(9.1, abs=1e-3)
    assert [i for i in SB.validate(out, tm2, brand03) if i["level"] == "error"] == []


def test_retime_takes_the_opening_shot_out_when_the_first_word_starts_early_again(tmp_path, brand03):
    old_t = intro_timing(5.0, 10.2)
    sb = compiled(make_project(tmp_path, old_t)).storyboard
    new_t = intro_timing(1.0, 10.2)
    assert [p["code"] for p in RT.off_voice(sb, new_t, style_doc()) if p["code"].startswith("opening")] == ["opening_extra"]
    out, rep = RT.retime(sb, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert rep["removed"] == ["s0000"] and "s0000" not in [s["id"] for s in out["shots"]]
    tm, t0, t1 = times(out, new_t)
    assert t0[0] == 0.0 and out["shots"][0]["start"] == {"w": 0, "off": -1.0, "text": "w0"}          # the next shot now starts at 0
    assert RT.off_voice(out, new_t, style_doc()) == [] and [i for i in SB.validate(out, tm, brand03) if i["level"] == "error"] == []
    assert any(o["technique"] == "ID-OPEN-01" for o in out["shots"][0]["overlays"])               # the opening overlay is back on the first shot


def test_a_locked_card_is_left_and_reported_and_a_wrong_number_of_cards_is_reported_never_repaired(tmp_path, brand03):
    old_t = intro_timing()
    sb = compiled(make_project(tmp_path, old_t)).storyboard
    new_t = intro_timing(6.0, 11.0)
    locked = copy.deepcopy(sb)
    m = by_technique(locked, "ID-MARK")[0]
    m["locked"] = True
    out, rep = RT.retime(locked, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert next(s for s in out["shots"] if s["id"] == m["id"])["start"] == m["start"]                  # left as it is ...
    assert [(p["code"], p["shot"], p["locked"]) for p in rep["left"] if p["locked"]] == [("card_off", m["id"], True)]             # ... and reported
    fewer = copy.deepcopy(sb)
    fewer["shots"] = [s for s in fewer["shots"] if s["id"] != by_technique(fewer, "ID-MARK")[1]["id"]]
    off = RT.off_voice(fewer, new_t, style_doc())
    assert [p for p in off if p["code"] == "card_count"] and not [p for p in off if p["code"] == "card_count"][0]["repair"]
    out2, rep2 = RT.retime(fewer, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert [p["code"] for p in rep2["left"] if p["code"] == "card_count"] == ["card_count"]
    assert len(by_technique(out2, "ID-MARK")) == 1 and by_technique(out2, "ID-MARK")[0]["start"] == by_technique(fewer, "ID-MARK")[0]["start"]      # not one card moved


def test_the_title_slot_of_an_old_look_storyboard_is_judged_by_the_old_cards(tmp_path, brand03):
    old_t = intro_timing(0.35, 6.2)
    sb = compiled(make_project(tmp_path, old_t), identity=False).storyboard
    assert "identity" not in sb and {s["technique"] for s in sb["shots"] if s["intent"] == "structure"} == {"X-CARD-01", "X-CARD-02"}
    assert RT.off_voice(sb, old_t, style_doc()) == []
    new_t = intro_timing(0.35, 8.0)
    assert {p["code"] for p in RT.off_voice(sb, new_t, style_doc())} >= {"title_off", "card_off", "end_off"}
    out, rep = RT.retime(sb, new_t, style_doc(), {"main_asset": "A"}, brand03.param_defaults)
    assert RT.off_voice(out, new_t, style_doc()) == [] and rep["identity"] is None and "identity" not in out        # no identity style chosen: none is applied


def test_without_a_size_for_the_main_painting_the_opening_cannot_be_written_and_is_reported(tmp_path, brand03):
    sb = compiled(make_project(tmp_path, intro_timing(5.0))).storyboard
    broken = copy.deepcopy(sb)
    broken["shots"] = broken["shots"][1:]                                   # the opening is gone and the first shot starts at 4.65 s
    for a in broken["assets"].values():
        a.pop("width", None)
        a.pop("height", None)
    off = RT.off_voice(broken, intro_timing(5.0), style_doc())
    assert [p["code"] for p in off if p["code"].startswith("opening")] == ["opening_missing"] and not [p for p in off if p["code"] == "opening_missing"][0]["repair"]


def test_the_engine_draws_the_opening_shot_with_its_overlays_and_the_new_beat(tmp_path, brand03):
    """The draw check takes frames across every shot and overlay of the compiled document: the opening shot (the whole painting, the opening overlay and the
    label on it) and the beat are drawn without an error."""
    res = compile_specs(load_inputs(make_project(tmp_path, intro_timing(5.0, 10.2))), specs(), draw=True)
    assert res.drawn and not res.errors, summary_text(res)
    assert res.storyboard["shots"][0]["id"] == "s0000"
