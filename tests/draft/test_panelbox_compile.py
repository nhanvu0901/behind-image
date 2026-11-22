"""Worker panelbox (2026-11-20): the compiler keeps the camera on the painted surface of the main painting.

The main picture of the synthetic project is made a museum photograph: a black ground round the painting (the painted area is 60, 80 to 740, 1120 of 800 x 1200). The compiler finds the
box (`bti.media.contentbox`), keeps it in the storyboard's asset, makes its own defaults for the painting and not for the photograph, and moves or tightens any camera key of a shot on
the main painting that would show more than 1% of its frame outside the box, and says so. A locked shot, and a shot outside the scope of an edit, are never touched."""
from __future__ import annotations

import copy
import json

import pytest
from PIL import Image

from bti.draft import decompile as D
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import clone_inputs, load_inputs
from bti.media import contentbox as CB
from helpers import GOOD, clean_spec, shot, spec

PANEL = (60, 80, 740, 1120)


def ground(proj, panel=PANEL):
    """The main picture of the project becomes a photograph with a black ground (the synthetic gradient picture inside it)."""
    f = proj / "media" / "a.jpg"
    inner = Image.open(f).convert("RGB").resize((panel[2] - panel[0], panel[3] - panel[1]))
    im = Image.new("RGB", (800, 1200), (0, 0, 0))
    im.paste(inner, panel[:2])
    im.save(f, quality=95)
    return proj


@pytest.fixture()
def ringed(proj):
    return ground(proj)


def run(proj, specs=None, **kw):
    inp = load_inputs(proj)
    specs = specs or {c: clean_spec(s, c) for c, s in GOOD.items()}
    return inp, compile_specs(inp, specs, draw=False, identity=False, **kw)


def keys_of(sb, sid):
    return next(s for s in sb["shots"] if s["id"] == sid)["params"]["camera"]


def agent_shots(sb, asset="A"):
    return [s for s in sb["shots"] if s.get("source") == "agent" and (s.get("slots") or {}).get("image", {}).get("asset") == asset and (s.get("params") or {}).get("camera")]


def box_of(sb):
    return CB.box_of(sb["assets"]["A"])


def test_the_compiler_finds_the_box_and_keeps_it_in_the_storyboards_asset(ringed):
    assert "content_box" not in json.loads((ringed / "picks.json").read_text(encoding="utf-8"))["assets"]["A"], "a project made before the box existed"
    inp, res = run(ringed)
    cb = res.storyboard["assets"]["A"]["content_box"]
    assert cb["how"] == "found" and all(abs(cb[k] - v) <= 8 for k, v in zip(CB.FIELDS, PANEL)), cb
    assert "content_box" not in res.storyboard["assets"]["B"]


def test_a_picture_without_a_ground_band_gets_no_box_and_the_compile_is_as_it_was(proj):
    inp, res = run(proj)
    assert "content_box" not in res.storyboard["assets"]["A"]
    assert not [i for i in res.issues if i["code"] in ("frame_moved_into_painting", "frame_off_painting")]


def test_the_defaults_of_the_main_painting_are_made_for_the_painting_not_the_photograph(ringed, tmp_path):
    """A nearby start preserves the preceding frame, fitted to the painted area."""
    sp = {c: clean_spec(s, c) for c, s in GOOD.items()}
    sp["c01"]["shots"][1]["from"] = "whole"
    sp["c01"]["shots"][1]["overlays"] = []
    inp, res = run(ringed, sp)
    sid = next(s["id"] for s in res.storyboard["shots"] if s["technique"] == "CAM-05" and (s["slots"].get("image") or {}).get("asset") == "A")
    k0 = keys_of(res.storyboard, sid)[0]
    cb = res.storyboard["assets"]["A"]["content_box"]
    assert (k0["cx"], k0["cy"]) == ((cb["x0"] + cb["x1"]) / 2, (cb["y0"] + cb["y1"]) / 2) and abs(k0["cx"] - 400) <= 3 and abs(k0["cy"] - 600) <= 3
    assert k0["zoom"] > 0.955 * 1080 / (cb["y1"] - cb["y0"])
    from helpers import make_synth_project                                                     # the same project with no ground: file centre and the file's fit
    plain = make_synth_project(tmp_path / "plain")
    k1 = keys_of(run(plain, copy.deepcopy(sp))[1].storyboard, sid)[0]
    assert k1["zoom"] > 0.955 * 1080 / 1200
    assert k0["zoom"] > k1["zoom"]


def test_every_camera_key_of_every_shot_on_the_main_painting_is_inside_the_box_after_the_compile(ringed):
    inp, res = run(ringed)
    box = box_of(res.storyboard)
    shots = agent_shots(res.storyboard)
    assert shots
    for s in shots:
        for k in s["params"]["camera"]:
            assert CB.outside_share(box, k["cx"], k["cy"], k["zoom"]) <= CB.OFF_LIMIT, (s["id"], k)
    assert not [i for i in res.issues if i["code"] == "frame_off_painting"], summary_text(res)


def _edit_carried_camera(ringed, past):
    inp, res = run(ringed)
    sb = copy.deepcopy(res.storyboard)
    cams = [s for s in sb["shots"] if s.get("source") == "agent" and s["params"].get("camera") and (s["slots"].get("image") or {}).get("asset") == "A"]
    victim = cams[2]
    victim["params"]["camera"] = copy.deepcopy(past)
    inp2, saved = edit_inputs(ringed, sb, {victim["id"]})
    # Edit note (leaving carried-over camera untouched so fit_to_box still clamps it on recompilation)
    for d in saved.values():
        for sh in d["shots"]:
            if sh.get("id") == victim["id"]:
                sh["note"] = "edited"
    return victim["id"], compile_specs(inp2, saved, draw=False, identity=False)


def test_a_camera_the_model_wrote_past_the_edge_is_moved_back_and_the_warning_says_what_was_done(ringed):
    past = [{"at": {"rel": 0.0}, "cx": 700, "cy": 600, "zoom": 3.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 790, "cy": 600, "zoom": 4.0, "ease": "linear"}]
    vid, res = _edit_carried_camera(ringed, past)
    (w,) = [i for i in res.issues if i["code"] == "frame_moved_into_painting"]
    assert w["level"] == "warn" and w["field"] == "params.camera"
    assert "painted area of the main painting" in w["message"]
    assert "key 1 showed" in w["message"] and "key 2 showed" in w["message"] and "inside" in w["message"]
    s = next(s for s in res.storyboard["shots"] if s["id"] == vid)
    k0, k1 = s["params"]["camera"]
    box = box_of(res.storyboard)
    assert k0["zoom"] == 3.0 and k1["zoom"] == 4.0, "the zoom is changed only when the frame is wider than the painting: here it is not"
    assert k0["cx"] == pytest.approx(box[2] - 1920 / 3.0 / 2, abs=0.01) and k1["cx"] == pytest.approx(box[2] - 1920 / 4.0 / 2, abs=0.01)
    assert k0["cy"] == 600 and k1["cy"] == 600, "the centre moves along the axis that was wrong only"
    assert not [i for i in res.issues if i["code"] == "frame_off_painting"]


def test_a_frame_wider_than_the_painting_is_tightened_by_no_more_than_it_must(ringed):
    """The full width of the file (800 px, zoom 2.4) is 60 px of black at each side: the zoom goes to the width of the painting."""
    past = [{"at": {"rel": 0.0}, "cx": 400, "cy": 300, "zoom": 2.4, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 400, "cy": 900, "zoom": 2.4, "ease": "linear"}]
    vid, res = _edit_carried_camera(ringed, past)
    cb = res.storyboard["assets"]["A"]["content_box"]
    width = cb["x1"] - cb["x0"]
    s = next(s for s in res.storyboard["shots"] if s["id"] == vid)
    assert s["params"]["camera"][0]["zoom"] == pytest.approx(1920 / width, abs=2e-5) and s["params"]["camera"][0]["cx"] == pytest.approx((cb["x0"] + cb["x1"]) / 2, abs=1.0)


def test_a_key_that_holds_the_whole_painting_is_left_alone(ringed):
    whole = [{"at": {"rel": 0.0}, "cx": 400, "cy": 600, "zoom": 0.9, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 400, "cy": 600, "zoom": 0.95, "ease": "linear"}]
    vid, res = _edit_carried_camera(ringed, whole)
    assert not [i for i in res.issues if i["code"] == "frame_moved_into_painting"]
    s = next(s for s in res.storyboard["shots"] if s["id"] == vid)
    assert [(k["cx"], k["cy"], k["zoom"]) for k in s["params"]["camera"]] == [(400, 600, 0.9), (400, 600, 0.95)]


def test_a_locked_shot_is_copied_through_untouched_and_the_validator_still_flags_it(ringed):
    inp, res = run(ringed)
    sb = copy.deepcopy(res.storyboard)
    victim = next(s for s in sb["shots"] if s.get("source") == "agent" and s["params"].get("camera") and (s["slots"].get("image") or {}).get("asset") == "A")
    off = [{"at": {"rel": 0.0}, "cx": 700, "cy": 600, "zoom": 2.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 790, "cy": 600, "zoom": 2.5, "ease": "linear"}]
    victim["params"]["camera"], victim["locked"] = off, True
    (ringed / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    inp2 = load_inputs(ringed)
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp2, None).items() if d["spec"]["shots"]}
    res2 = compile_specs(inp2, saved, draw=False, identity=False)
    got = next(s for s in res2.storyboard["shots"] if s["id"] == victim["id"])
    assert got["locked"] and [(k["cx"], k["cy"], k["zoom"]) for k in got["params"]["camera"]] == [(700, 600, 2.0), (790, 600, 2.5)]
    assert [i["shot"] for i in res2.issues if i["code"] == "frame_off_painting"], "the check still judges a locked shot: the person who locked it can see the warning"
    assert not [i for i in res2.issues if i["code"] == "frame_moved_into_painting" and victim["id"] in i["message"]]


def test_in_an_edit_only_the_shots_of_the_scope_are_corrected(ringed):
    """A shot outside the scope of an edit is kept exactly (a change outside the scope is a violation, and an acceptable result has none)."""
    inp, res = run(ringed)
    sb = copy.deepcopy(res.storyboard)
    cams = [s for s in sb["shots"] if s.get("source") == "agent" and s["params"].get("camera") and (s["slots"].get("image") or {}).get("asset") == "A"]
    a, b = cams[0], cams[1]
    off = [{"at": {"rel": 0.0}, "cx": 700, "cy": 600, "zoom": 2.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 790, "cy": 600, "zoom": 2.5, "ease": "linear"}]
    a["params"]["camera"], b["params"]["camera"] = copy.deepcopy(off), copy.deepcopy(off)
    (ringed / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    inp2 = load_inputs(ringed)
    inp2 = clone_inputs(inp2, edit_shots={b["id"]}, scope=D.chapters_of_shots(inp2, {a["id"], b["id"]}))
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp2, {b["id"]}).items() if d["spec"]["shots"]}
    res2 = compile_specs(inp2, saved, draw=False, identity=False)
    got = {s["id"]: s for s in res2.storyboard["shots"]}
    assert [(k["cx"], k["cy"], k["zoom"]) for k in got[a["id"]]["params"]["camera"]] == [(700, 600, 2.0), (790, 600, 2.5)], "outside the scope: as it was"
    assert got[b["id"]]["params"]["camera"][0]["cx"] < 700 and CB.outside_share(box_of(res2.storyboard), *[got[b["id"]]["params"]["camera"][0][f] for f in ("cx", "cy", "zoom")]) == 0.0
    assert res2.violations == [], res2.violations


def test_a_box_a_person_set_in_the_picks_wins_over_the_finding_and_reaches_the_storyboard(ringed):
    picks = json.loads((ringed / "picks.json").read_text(encoding="utf-8"))
    picks["assets"]["A"]["content_box"] = {"x0": 0, "y0": 0, "x1": 800, "y1": 1200, "how": "set"}
    (ringed / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    inp, res = run(ringed)
    assert res.storyboard["assets"]["A"]["content_box"] == {"x0": 0, "y0": 0, "x1": 800, "y1": 1200, "how": "set"}
    assert not [i for i in res.issues if i["code"] == "frame_moved_into_painting"], "the whole picture is the painted area"


def test_the_box_follows_its_picture_when_the_declared_size_was_wrong(ringed):
    """The picks said 400 x 600 for a file that is 800 x 1200: the size step corrects the size and scales the box with the regions."""
    picks = json.loads((ringed / "picks.json").read_text(encoding="utf-8"))
    a = picks["assets"]["A"]
    a["width"], a["height"] = 400, 600
    a["regions"] = {"MIRROR": {"x": 200, "y": 150, "rx": 40, "ry": 40, "label": "Mirror"}}
    a["content_box"] = {"x0": 30, "y0": 40, "x1": 370, "y1": 560, "how": "found"}
    (ringed / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    inp = load_inputs(ringed)
    cb = inp.picks["assets"]["A"]["content_box"]
    assert (cb["x0"], cb["y0"], cb["x1"], cb["y1"]) == (60, 80, 740, 1120) and (inp.picks["assets"]["A"]["width"], inp.picks["assets"]["A"]["height"]) == (800, 1200)


# ----------------------------------------------------------------------------------------------------------------- the opening shot
def opening_of(proj, **kw):
    from intro_helpers import intro_timing, make_project, specs
    inp = load_inputs(make_project(proj, intro_timing()) if not (proj / "timing.json").exists() else proj)
    res = compile_specs(inp, specs(), draw=False, identity=False, **kw)
    return res, next(s for s in res.storyboard["shots"] if s["id"] == "s0000")


def test_the_opening_shot_fits_and_centres_the_painted_area_not_the_file(tmp_path):
    from intro_helpers import intro_timing, make_project
    proj = ground(make_project(tmp_path, intro_timing(), "ring"))
    res, op = opening_of(proj)
    cb = res.storyboard["assets"]["A"]["content_box"]
    box = tuple(float(cb[k]) for k in CB.FIELDS)
    k0, k1 = op["params"]["camera"]
    assert (k0["cx"], k0["cy"]) == ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) and (k1["cx"], k1["cy"]) == (k0["cx"], k0["cy"])
    assert k0["zoom"] == pytest.approx(min(0.955 * 1080 / (box[3] - box[1]), 0.955 * 1920 / (box[2] - box[0])), abs=2e-5)
    assert CB.holds_whole(box, k0["cx"], k0["cy"], k0["zoom"]) and CB.holds_whole(box, k1["cx"], k1["cy"], k1["zoom"])
    assert k1["zoom"] <= min(1080 / (box[3] - box[1]), 1920 / (box[2] - box[0])) + 1e-6, "the push never puts an edge of the painting outside the frame"
    assert not [i for i in res.issues if i["code"] in ("frame_off_painting", "frame_moved_into_painting") and "s0000" in i["message"]]


def test_the_opening_shot_of_a_painting_with_no_ground_is_what_it_was(tmp_path):
    from intro_helpers import intro_timing, make_project
    proj = make_project(tmp_path, intro_timing(), "plain")
    res, op = opening_of(proj)
    k0 = op["params"]["camera"][0]
    assert (k0["cx"], k0["cy"]) == (400.0, 600.0) and k0["zoom"] == pytest.approx(0.955 * 1080 / 1200, abs=2e-5)
    assert "content_box" not in res.storyboard["assets"]["A"]


def test_zones_whole_camera_with_and_without_a_box():
    from bti.draft import zones as Z
    plain = Z.whole_camera(800, 1200, {"w": 1920, "h": 1080}, 95.5)
    assert [(k["cx"], k["cy"]) for k in plain] == [(400.0, 600.0)] * 2 and plain[0]["zoom"] == pytest.approx(0.955 * 1080 / 1200, abs=2e-5)
    boxed = Z.whole_camera(800, 1200, {"w": 1920, "h": 1080}, 95.5, (60, 80, 740, 1120))
    assert [(k["cx"], k["cy"]) for k in boxed] == [(400.0, 600.0)] * 2 and boxed[0]["zoom"] == pytest.approx(0.955 * 1080 / 1040, abs=2e-5)
    assert boxed[1]["zoom"] <= 1080 / 1040 + 1e-6
    off = Z.whole_camera(800, 1200, {"w": 1920, "h": 1080}, 95.5, (0, 0, 400, 1200))
    assert off[0]["cx"] == 200.0 and off[0]["cy"] == 600.0, "a box that is not centred centres the frame on the box"
    assert Z.whole_camera(800, 1200, None, 95.5, (500, 0, 100, 1200)) == Z.whole_camera(800, 1200, None, 95.5), "a box that is not a box is ignored"
    assert Z.whole_camera(800, 1200, None, 95.5, (0, 0, 2000, 1200)) == Z.whole_camera(800, 1200, None, 95.5), "so is one outside the picture"
    shot = Z.opening_shot("A", {"width": 800, "height": 1200, "content_box": {"x0": 60, "y0": 80, "x1": 740, "y1": 1120, "how": "found"}}, None, 95.5, {"shadow": True})
    assert shot["params"]["camera"] == boxed and shot["params"]["shadow"] is True


# ----------------------------------------------------------------------------------------------------------------- an edit hands every asset back as it was
def edit_inputs(proj, sb, shot_ids):
    (proj / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    inp = load_inputs(proj)
    inp = clone_inputs(inp, edit_shots=set(shot_ids), scope=D.chapters_of_shots(inp, set(shot_ids)))
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp, set(shot_ids)).items() if d["spec"]["shots"]}
    return inp, saved


def test_an_edit_of_a_storyboard_made_before_the_box_existed_adds_no_box_to_the_asset_and_still_corrects_the_shots_it_changes(ringed):
    """`decompile.scope_violations` refuses an edit that changes an asset record: the box is found in the file for the frames and is not written."""
    inp, res = run(ringed)
    sb = copy.deepcopy(res.storyboard)
    sb["assets"]["A"].pop("content_box")                                  # as a storyboard saved before this change
    cams = [s for s in sb["shots"] if s.get("source") == "agent" and s["params"].get("camera") and (s["slots"].get("image") or {}).get("asset") == "A"]
    a, b = cams[0], cams[1]
    off = [{"at": {"rel": 0.0}, "cx": 700, "cy": 600, "zoom": 3.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 790, "cy": 600, "zoom": 4.0, "ease": "linear"}]
    a["params"]["camera"], b["params"]["camera"] = copy.deepcopy(off), copy.deepcopy(off)
    inp2, saved = edit_inputs(ringed, sb, {b["id"]})
    res2 = compile_specs(inp2, saved, draw=False, identity=False)
    assert res2.violations == [] and not res2.errors, summary_text(res2)
    assert "content_box" not in res2.storyboard["assets"]["A"], "the asset came back as it was"
    got = {s["id"]: s for s in res2.storyboard["shots"]}
    assert [(k["cx"], k["zoom"]) for k in got[a["id"]]["params"]["camera"]] == [(700, 3.0), (790, 4.0)], "outside the scope: as it was"
    k0 = got[b["id"]]["params"]["camera"][0]
    assert k0["cx"] < 700 and k0["zoom"] == 3.0, "inside the scope: moved back, by the box that was found in the file"
    assert [i["shot"] for i in res2.issues if i["code"] == "frame_moved_into_painting"] and not [i for i in res2.issues if i["code"] == "frame_off_painting" and b["id"] in i["message"]]


def test_an_edit_keeps_the_saved_box_even_when_the_picks_say_another_a_draft_takes_the_picks(ringed):
    inp, res = run(ringed)
    sb = copy.deepcopy(res.storyboard)
    saved_box = dict(sb["assets"]["A"]["content_box"])
    picks = json.loads((ringed / "picks.json").read_text(encoding="utf-8"))
    picks["assets"]["A"]["content_box"] = {"x0": 0, "y0": 0, "x1": 800, "y1": 1200, "how": "set"}
    (ringed / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    target = next(s for s in sb["shots"] if s.get("source") == "agent" and s["params"].get("camera"))
    inp2, saved = edit_inputs(ringed, sb, {target["id"]})
    res2 = compile_specs(inp2, saved, draw=False, identity=False)
    assert res2.violations == [] and res2.storyboard["assets"]["A"]["content_box"] == saved_box
    inp3 = load_inputs(ringed)
    res3 = compile_specs(inp3, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    assert res3.storyboard["assets"]["A"]["content_box"]["how"] == "set"
