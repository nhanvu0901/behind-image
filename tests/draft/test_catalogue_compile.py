"""Worker catalogue (2026-11-20): what the compiler does with the catalogue's two decisions.

1. A technique that is hidden from the models (`offered: false`) is the error `technique_not_offered` in a draft or an edit turn, with what to use instead; a stored shot that
   already has it is never judged (the two finished videos use hidden techniques and must stay valid).
2. Rule 17: a picture that is not the painting is shown at its default fit. A camera the model wrote that shows it under 80% of that fit, or a small picture (long side under
   1000 px) past twice its size, is replaced by the default and the compiler says so (`outside_camera_refit`, a warning)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from bti.draft import decompile as D
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import load_inputs
from helpers import GOOD, _image, clean_spec, shot, spec

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))
import real_docs as RD  # noqa: E402


def good(proj):
    inp = load_inputs(proj)
    return inp, {c: clean_spec(s, c) for c, s in GOOD.items()}


def run(inp, specs, **kw):
    return compile_specs(inp, specs, draw=False, identity=False, **kw)


def codes(res, code):
    return [i for i in res.issues if i["code"] == code]


# ----------------------------------------------------------------------------------------------------------------- hidden techniques
def test_a_hidden_shot_technique_is_an_error_that_says_what_to_use_instead(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][0]["technique"] = "CAM-06"
    res = run(inp, specs)
    bad = codes(res, "technique_not_offered")
    assert len(bad) == 1 and bad[0]["level"] == "error" and bad[0]["chapter"] == "c01" and bad[0]["shot"] == 1 and bad[0]["field"] == "technique"
    assert "CAM-06" in bad[0]["message"] and "not one of the techniques you are offered" in bad[0]["message"] and "Use STATIC-01 or X-ANN-01 instead." in bad[0]["message"]
    assert res.errors and "ERROR technique_not_offered" in summary_text(res)


def test_a_replaced_technique_names_its_replacement_and_a_program_one_says_leave_it_out(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][0]["technique"] = "AN-04"
    specs["c01"]["shots"][2]["overlays"] = [{"technique": "ID-OPEN-01", "start_word": 22, "dur": 2.0, "params": {}}]
    msgs = {i["shot"]: i["message"] for i in codes(run(inp, specs), "technique_not_offered")}
    assert "Use MAP-01 instead." in msgs[1] and "Leave it out." in msgs[3] and "writes the opening" in msgs[3]


def test_a_hidden_overlay_is_an_error_and_is_left_out(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][0]["overlays"] = [{"technique": "X-HI-01", "start_word": 3, "dur": 2.0, "params": {"at": [400, 400], "rx": 100, "ry": 100}}]
    res = run(inp, specs)
    bad = codes(res, "technique_not_offered")
    assert len(bad) == 1 and bad[0]["shot"] == 1 and bad[0]["overlay"] == 1 and "Use HI-01 instead." in bad[0]["message"]
    assert not any(o["technique"] == "X-HI-01" for s in res.storyboard["shots"] for o in s["overlays"])


def test_a_hidden_transition_is_an_error(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][2]["transition_in"] = {"technique": "TR-02", "dur": 1.0}
    bad = codes(run(inp, specs), "technique_not_offered")
    assert len(bad) == 1 and bad[0]["shot"] == 3 and bad[0]["field"] == "transition_in.technique" and "Use LAY-01 instead." in bad[0]["message"]
    specs["c01"]["shots"][2]["transition_in"] = {"technique": "TR-01", "dur": 1.0}
    assert not codes(run(inp, specs), "technique_not_offered")


def test_the_offered_techniques_and_an_unknown_one_are_not_this_error(proj):
    inp, specs = good(proj)
    assert not codes(run(inp, specs), "technique_not_offered")
    specs["c01"]["shots"][0]["technique"] = "NOPE-99"
    res = run(inp, specs)
    assert not codes(res, "technique_not_offered") and res.errors, "an unknown id has its own refusal"


def test_the_proposal_run_replaces_a_shot_that_uses_a_hidden_technique_and_has_no_error_left(proj):
    inp, specs = good(proj)
    specs["c01"]["shots"][1]["technique"] = "CAM-06"
    specs["c01"]["shots"][1]["overlays"] = []
    res = run(inp, specs, degrade=True)         # the proposal run: what is refused is replaced (and listed in `degraded`), so that the document it writes validates
    assert "CAM-06" not in {s["technique"] for s in res.storyboard["shots"]} and any(i["code"] == "technique_not_offered" for i in res.degraded)
    assert not [i for i in res.issues if i["level"] == "error" and i["code"] != "technique_not_offered"], summary_text(res)


def stored(proj, hidden_on_shot=1):
    """The project with a saved storyboard whose shot number `hidden_on_shot` of chapter c01 uses a hidden technique; returns (inputs, specs of the saved shots, that shot's id)."""
    inp, specs = good(proj)
    res = run(inp, specs)
    sb = copy.deepcopy(res.storyboard)
    agent = [s for s in sb["shots"] if s["source"] == "agent" and s["technique"] != "X-CARD-01"]
    target = agent[hidden_on_shot]
    target["technique"] = "CAM-06"
    (proj / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    inp2 = load_inputs(proj)
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp2, None).items() if d["spec"]["shots"]}
    return inp2, saved, target["id"]


def shots_of(saved, sid):
    return [s for sp in saved.values() for s in sp["shots"] if s.get("id") == sid]


def test_a_stored_shot_that_uses_a_hidden_technique_is_never_judged_even_when_it_is_changed(proj):
    inp, saved, sid = stored(proj)
    (hit,) = shots_of(saved, sid)
    assert hit["technique"] == "CAM-06"
    assert not codes(run(inp, copy.deepcopy(saved)), "technique_not_offered"), "copied unchanged"
    changed = copy.deepcopy(saved)
    (c_hit,) = shots_of(changed, sid)
    c_hit["note"] = "a new reason"                          # a shot that is not copied verbatim is built again
    c_hit["params"] = {"shadow": False}
    res = run(inp, changed)
    assert not codes(res, "technique_not_offered"), summary_text(res)
    assert "CAM-06" in {s["technique"] for s in res.storyboard["shots"]}


def test_a_new_shot_or_a_new_technique_on_a_stored_shot_is_judged(proj):
    inp, saved, sid = stored(proj)
    other = copy.deepcopy(saved)
    (o_hit,) = shots_of(other, sid)
    o_hit["technique"] = "STATIC-04"                        # another hidden technique on the same shot
    assert len(codes(run(inp, other), "technique_not_offered")) == 1
    new = copy.deepcopy(saved)
    ch = next(c for c, sp in new.items() if any(s.get("id") == sid for s in sp["shots"]))
    extra = dict(shot("b0001", 1, "CAM-06"), _n=99)
    new[ch]["shots"].append(extra)
    assert any(i["shot"] == 99 for i in codes(run(inp, new), "technique_not_offered"))


def test_a_stored_overlay_that_is_hidden_is_kept_and_a_new_one_is_refused(proj):
    inp, specs = good(proj)
    res = run(inp, specs)
    sb = copy.deepcopy(res.storyboard)
    first = next(s for s in sb["shots"] if s["source"] == "agent")
    first["overlays"].append({"id": "o9", "technique": "X-HI-01", "intent": "isolate", "start": {"w": 3, "off": 0.0, "text": "w3"}, "dur": 2.0,
                              "params": {"at": [400, 400], "rx": 100, "ry": 100}, "locked": False, "source": "agent", "note": ""})
    (proj / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    inp2 = load_inputs(proj)
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp2, None).items() if d["spec"]["shots"]}
    sh = next(s for sp in saved.values() for s in sp["shots"] if s.get("id") == first["id"])
    assert any(o["technique"] == "X-HI-01" for o in sh["overlays"])
    sh["note"] = "changed so that the shot is built again"
    assert not codes(run(inp2, saved), "technique_not_offered")
    sh["overlays"].append({"technique": "AN-02", "start_word": 6, "dur": 1.5, "params": {}})
    assert len(codes(run(inp2, saved), "technique_not_offered")) == 1, "another hidden overlay is new"


# ----------------------------------------------------------------------------------------------------------------- the real finished videos
@pytest.mark.parametrize("name", sorted(RD.KEYS))
def test_a_redraft_that_copies_the_stored_shots_of_a_real_video_is_never_judged_by_the_catalogue(tmp_path, name):
    d = RD.build_project(tmp_path, name)
    inp = load_inputs(d)
    saved = {c: clean_spec(x["spec"], c) for c, x in D.decompile(inp, None).items() if x["spec"]["shots"]}
    used = {s["technique"] for sp in saved.values() for s in sp["shots"]} | {o["technique"] for sp in saved.values() for s in sp["shots"] for o in s["overlays"]}
    hidden = {t for t in used if not inp_bundle(inp).offered(t)}
    assert hidden or name == "eligius", "the copy carries the hidden techniques of the stored video"
    res = compile_specs(inp, saved, draw=False, identity=True)
    assert not codes(res, "technique_not_offered"), [i["message"] for i in codes(res, "technique_not_offered")][:3]
    assert not [i for i in res.errors if i["code"] in ("technique_not_offered", "outside_camera_refit")], summary_text(res)[:600]


def inp_bundle(inp):
    from bti.engine import registry as R
    return R.load_bundle(inp.style)


# ----------------------------------------------------------------------------------------------------------------- rule 17: an outside picture at its default fit
def cam(z0, z1, cx=300, cy=200):
    return [{"at": {"rel": 0.0}, "cx": cx, "cy": cy, "zoom": z0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": cx, "cy": cy, "zoom": z1, "ease": "linear"}]


def with_big_outside(proj):
    """Asset C (3000 x 2000, an outside picture of b0005) beside B (600 x 400, an outside picture of b0004)."""
    _image(proj / "media" / "c.jpg", 3000, 2000, seed=3)
    pk = json.loads((proj / "picks.json").read_text(encoding="utf-8"))
    pk["assets"]["C"] = {"file": "media/c.jpg", "kind": "image", "title": "A large print", "artist": "An Etcher", "year": "1500", "width": 3000, "height": 2000}
    pk["beats"]["b0005"] = {"items": [{"asset": "C", "region": None, "role": "context", "note": ""}], "status": "picked"}
    (proj / "picks.json").write_text(json.dumps(pk), encoding="utf-8")


def build(proj, key, params, beat="b0004", sw=30, tid="X-LAY-01"):
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs["c02"]["shots"][0] = dict(shot(beat, sw, tid, slots={"image": {"asset": key}}, params=params), _n=1)
    res = run(inp, specs)
    s = next(x for x in res.storyboard["shots"] if x["technique"] == tid and x["slots"]["image"]["asset"] == key)
    return res, s


def zooms(s):
    return [k["zoom"] for k in s["params"]["camera"]]


def test_a_camera_that_shows_a_large_outside_picture_under_80_percent_of_its_fit_is_replaced_and_the_compiler_says_so(proj):
    with_big_outside(proj)
    res, s = build(proj, "C", {"camera": cam(0.2, 0.25, 1500, 1000)}, beat="b0005", sw=40)
    fit = min(1920 / 3000, 1080 / 2000)
    assert zooms(s) == [pytest.approx(0.94 * 1080 / 2000, abs=1e-4), pytest.approx(0.94 * 1080 / 2000 * 1.06, abs=1e-4)] and min(zooms(s)) >= 0.8 * fit
    (w,) = codes(res, "outside_camera_refit")
    assert w["level"] == "warn" and w["chapter"] == "c02" and w["field"] == "params.camera" and "under 80% of that fit" in w["message"] and "default camera back" in w["message"]
    assert not res.errors, summary_text(res)


def test_a_camera_at_or_above_the_fit_of_an_outside_picture_is_left_alone(proj):
    with_big_outside(proj)
    res, s = build(proj, "C", {"camera": cam(0.44, 0.6, 1500, 1000)}, beat="b0005", sw=40)
    assert zooms(s) == [0.44, 0.6] and not codes(res, "outside_camera_refit")


def test_no_camera_means_the_default_fit_and_no_message(proj):
    with_big_outside(proj)
    res, s = build(proj, "C", {}, beat="b0005", sw=40)
    assert zooms(s)[0] == pytest.approx(0.94 * 1080 / 2000, abs=1e-4) and not codes(res, "outside_camera_refit")


def test_a_small_outside_picture_is_never_enlarged_beyond_twice_its_size(proj):
    res, s = build(proj, "B", {})                                          # B is 600 x 400: the engine's default would be 2.54
    assert max(zooms(s)) == 2.0 and min(zooms(s)) >= 1.6 and not codes(res, "outside_camera_refit"), "the default is held to twice the size, silently"
    res, s = build(proj, "B", {"camera": cam(3.0, 3.5, 300, 200)})
    assert max(zooms(s)) <= 2.0 and min(zooms(s)) >= 1.6 and len(codes(res, "outside_camera_refit")) == 1 and "past twice its size" in codes(res, "outside_camera_refit")[0]["message"]
    res, s = build(proj, "B", {"camera": cam(0.3, 0.3, 300, 200)})
    assert min(zooms(s)) >= 1.6 and "under 80% of that fit" in codes(res, "outside_camera_refit")[0]["message"]
    res, s = build(proj, "B", {"camera": cam(1.7, 1.9, 300, 200)})
    assert zooms(s) == [1.7, 1.9] and not codes(res, "outside_camera_refit")


def test_the_main_painting_is_never_refitted(proj):
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs["c01"]["shots"][0] = dict(shot("b0001", 0, "CAM-01", params={"camera": cam(0.2, 0.25, 400, 600)}), _n=1)
    res = run(inp, specs)
    assert codes(res, "camera_not_allowed") and not codes(res, "outside_camera_refit")


def test_a_technique_without_a_camera_is_not_touched(proj):
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs["c02"]["shots"][0] = dict(shot("b0004", 30, "LAY-01", slots={"left": {"asset": "A"}, "right": {"asset": "B"}}), _n=1)
    res = run(inp, specs)
    assert not codes(res, "outside_camera_refit") and not res.errors


# ----------------------------------------------------------------------------------------------------------------- a detail beside another work
def panel_shot(tid, slots, params=None):
    return dict(shot("b0004", 30, tid, slots=slots, params=params or {}), _n=1)


def compiled(proj, sh):
    inp = load_inputs(proj)
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs["c02"]["shots"][0] = sh
    res = run(inp, specs)
    return res, next(x for x in res.storyboard["shots"] if x["technique"] == sh["technique"])


def test_lay_01_frames_the_region_of_the_painting_in_its_panel(proj):
    res, s = compiled(proj, panel_shot("LAY-01", {"left": {"asset": "A", "region": "MIRROR"}, "right": {"asset": "B"}}))
    left = s["params"]["camera_left"]
    assert [k["cx"] for k in left] == [400, 400] and [k["cy"] for k in left] == [300, 300] and left[0]["zoom"] == pytest.approx(min(0.8 * 900 / 160, 0.8 * 740 / 160), abs=1e-3)
    assert not res.errors, summary_text(res)


def test_a_panel_without_a_region_keeps_the_whole_picture_and_the_models_own_camera_wins(proj):
    _, s = compiled(proj, panel_shot("LAY-01", {"left": {"asset": "A"}, "right": {"asset": "B"}}))
    assert s["params"]["camera_left"][0]["zoom"] == pytest.approx(0.94 * 740 / 1200, abs=1e-3)
    own = [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 400, "cy": 600, "zoom": 0.7, "ease": "linear"}]
    _, s = compiled(proj, panel_shot("LAY-01", {"left": {"asset": "A", "region": "MIRROR"}, "right": {"asset": "B"}}, {"camera_left": own}))
    assert [k["zoom"] for k in s["params"]["camera_left"]] == [0.7, 0.7]


def test_x_cmp_01_frames_the_region_of_its_anchor(proj):
    res, s = compiled(proj, panel_shot("X-CMP-01", {"anchor": {"asset": "A", "region": "MIRROR"}, "swap_1": {"asset": "B"}}))
    cam = s["params"]["camera_anchor"]
    assert [k["cx"] for k in cam] == [400, 400] and cam[0]["zoom"] > 3.0 and not res.errors, summary_text(res)
