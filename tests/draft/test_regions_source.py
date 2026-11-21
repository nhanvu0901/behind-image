"""Worker regionsrc: a full draft takes its regions from the pictures step (picks.json), not from the storyboard saved before.

The saved storyboard's copy of an asset used to replace the picks' asset, so a draft written over an older storyboard compiled its camera and its
spotlight from the OLD loose boxes and showed the model the same boxes, while the pictures step (`picks.tighten`) had just measured tight ones.
Now (`bti.draft.assetmerge`): a full draft (`edit_shots is None`) takes every region the picks hold, each whole, replacing the saved region of the same name;
a region only the saved storyboard has is kept; an edit keeps the saved asset as it is. Fakes only: the synthetic project of `helpers.make_synth_project`."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bti.draft import assetmerge as AM
from bti.draft import decompile as D
from bti.draft import workspace as W
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import clone_inputs, load_inputs
from bti.draft.providers import auto
from bti.engine import viewchecks as VC
from helpers import GOOD, clean_spec

REPO = Path(__file__).resolve().parents[2]

LOOSE = {"x": 600, "y": 500, "rx": 300, "ry": 360, "label": "The loose mirror box of the old storyboard"}
TIGHT = {"x": 400, "y": 300, "rx": 40, "ry": 50, "label": "Mirror", "tight": True, "thing": "convex mirror", "rough": False}
RING = {"x": 300, "y": 900, "rx": 60, "ry": 60, "label": "Ring added on the storyboard"}


def specs():
    return {c: clean_spec(s, c) for c, s in GOOD.items()}


def compile_(inp):
    res = compile_specs(inp, specs(), draw=False, identity=False)
    assert not res.errors, summary_text(res)
    return res


def set_picks_mirror(proj, region):
    f = proj / "picks.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    raw["assets"]["A"]["regions"]["MIRROR"] = copy.deepcopy(region)
    f.write_text(json.dumps(raw), encoding="utf-8")


def save_old_storyboard(proj):
    """A storyboard compiled from the OLD picks (the loose MIRROR box), with a region only the storyboard has; then the pictures step measures a tight MIRROR."""
    set_picks_mirror(proj, LOOSE)
    sb = copy.deepcopy(compile_(load_inputs(proj)).storyboard)
    sb["assets"]["A"]["regions"]["RING"] = copy.deepcopy(RING)
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    set_picks_mirror(proj, TIGHT)
    return sb


def mirror_shot(sb):
    return next(s for s in sb["shots"] if s.get("source") == "agent" and (s.get("slots") or {}).get("image", {}).get("region") == "MIRROR" and s["technique"] == "CAM-05")


# ------------------------------------------------------------------------------------------------------------------- the rule itself
def test_the_rule_on_assets_full_draft_and_edit():
    picks = {"A": {"file": "a.jpg", "kind": "image", "width": 800, "height": 1200, "regions": {"MIRROR": dict(TIGHT), "NEW": {"x": 1, "y": 2, "rx": 3, "ry": 4, "label": "n"}}}}
    saved = {"A": {"file": "old.jpg", "kind": "image", "width": 800, "height": 1200, "title": "kept", "regions": {"MIRROR": dict(LOOSE), "RING": dict(RING)}},
             "ONLY": {"file": "only.jpg", "kind": "image", "width": 10, "height": 10, "regions": {"X": {"x": 1, "y": 1, "label": "x"}}}}
    full = AM.merged_assets(picks, saved, edit=False)
    assert full["A"]["regions"]["MIRROR"] == TIGHT                                   # whole: the box and `tight`, `thing`, `rough`, `label`
    assert full["A"]["regions"]["NEW"]["label"] == "n" and full["A"]["regions"]["RING"] == RING          # added by the picks; only on the storyboard: kept
    assert full["A"]["file"] == "a.jpg" and full["A"]["title"] == "kept"             # the facts of the file from the picks, the rest of the saved copy kept
    assert list(full["A"]["regions"]) == ["MIRROR", "NEW", "RING"]                   # the picks' regions first
    assert full["ONLY"] == saved["ONLY"]
    edit = AM.merged_assets(picks, saved, edit=True)
    assert edit["A"]["regions"] == {"MIRROR": LOOSE, "RING": RING}                   # an edit: the saved asset as it is (the file's facts apart)
    assert AM.merged_assets(picks, None, edit=False) == picks and AM.merged_assets(None, None, edit=False) == {}
    picks["A"]["regions"]["MIRROR"]["x"] = 999                                       # a copy: nothing is shared with the inputs
    assert full["A"]["regions"]["MIRROR"]["x"] == 400


# ------------------------------------------------------------------------------------------------------------------- the compiler
def test_a_full_draft_over_a_saved_storyboard_compiles_from_the_picks_region(proj):
    save_old_storyboard(proj)
    inp = load_inputs(proj)
    assert inp.current["assets"]["A"]["regions"]["MIRROR"] == LOOSE and inp.picks["assets"]["A"]["regions"]["MIRROR"] == TIGHT
    res = compile_(inp)
    a = res.storyboard["assets"]["A"]
    assert a["regions"]["MIRROR"] == TIGHT                                           # the storyboard that is written carries the picks' region, whole
    assert a["regions"]["RING"] == RING                                              # a region only the saved storyboard has is kept
    shot = mirror_shot(res.storyboard)
    end = shot["params"]["camera"][-1]
    want = VC.region_frame(TIGHT, 800, 1200, a.get("content_box") and (a["content_box"]["x0"], a["content_box"]["y0"], a["content_box"]["x1"], a["content_box"]["y1"]))
    assert (end["cx"], end["cy"]) == pytest.approx(want[:2], abs=0.05) and end["zoom"] == pytest.approx(want[2], abs=1e-4)
    assert (end["cx"], end["cy"]) == (400.0, 300.0) and end["zoom"] > VC.region_frame(LOOSE, 800, 1200)[2]          # on the tight box, closer than the loose one made it
    hi = next(o for o in shot["overlays"] if o["technique"] == "HI-01")
    assert hi["params"]["at"] == "MIRROR"
    assert not [i for i in res.issues if i["code"] in ("camera_off_region", "thing_arrives_late")], summary_text(res)


def test_the_spotlight_is_sized_from_the_picks_box(proj):
    """The spotlight's default size comes from the region: the tight box of the picks, not the loose one of the saved storyboard."""
    def light(sb):
        return next(o for o in mirror_shot(sb)["overlays"] if o["technique"] == "HI-01")["params"]
    set_picks_mirror(proj, LOOSE)
    loose = light(compile_(load_inputs(proj)).storyboard)
    set_picks_mirror(proj, TIGHT)
    tight = light(compile_(load_inputs(proj)).storyboard)                            # no storyboard yet
    assert tight != loose, (tight, loose)                                            # the two boxes give two different lights
    save_old_storyboard(proj)                                                        # the saved storyboard knows the loose box
    assert light(compile_(load_inputs(proj)).storyboard) == tight                    # over it: the same light as with no storyboard


def test_a_project_with_no_storyboard_is_as_before(proj):
    set_picks_mirror(proj, TIGHT)
    inp = load_inputs(proj)
    assert inp.current is None
    res = compile_(inp)
    assert res.storyboard["assets"]["A"]["regions"] == {"MIRROR": TIGHT}
    saved_first = copy.deepcopy(res.storyboard)
    (proj / "storyboard.json").write_text(json.dumps(saved_first), encoding="utf-8")
    again = compile_(load_inputs(proj)).storyboard                                   # picks and storyboard agree: nothing moves
    assert again["assets"]["A"]["regions"] == saved_first["assets"]["A"]["regions"]


def test_an_edit_over_the_same_project_keeps_the_saved_region(proj):
    sb = save_old_storyboard(proj)
    victim = mirror_shot(sb)
    inp = clone_inputs(load_inputs(proj), edit_shots={victim["id"]}, scope=D.chapters_of_shots(load_inputs(proj), {victim["id"]}))
    saved = {c: clean_spec(d["spec"], c) for c, d in D.decompile(inp, {victim["id"]}).items() if d["spec"]["shots"]}
    res = compile_specs(inp, saved, draw=False, identity=False)
    assert res.violations == [], res.violations
    a = res.storyboard["assets"]["A"]
    assert a["regions"]["MIRROR"] == LOOSE and a["regions"]["RING"] == RING          # the saved asset as it is: the shots outside the scope come back identical
    for s in res.storyboard["shots"]:
        if s["id"] != victim["id"]:
            assert s == next(o for o in sb["shots"] if o["id"] == s["id"]), s["id"]


def test_the_models_regions_json_still_never_overwrites_a_name(proj):
    save_old_storyboard(proj)
    inp = load_inputs(proj)
    regions = {"A": {"MIRROR": {"x": 100, "y": 100, "rx": 10, "ry": 10, "label": "model"}, "SHELF": {"x": 700, "y": 1000, "rx": 30, "ry": 30, "label": "Shelf"}}}
    res = compile_specs(inp, specs(), regions=regions, draw=False, identity=False)
    a = res.storyboard["assets"]["A"]
    assert a["regions"]["MIRROR"] == TIGHT and a["regions"]["SHELF"]["label"] == "Shelf"
    assert [i for i in res.issues if i["code"] == "region_exists"]


# ------------------------------------------------------------------------------------------------------------------- the work folder and the helpers
def test_the_work_folder_shows_the_model_the_regions_the_compiler_will_use(proj, tmp_path):
    save_old_storyboard(proj)
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    shown = json.loads((ws.root / "inputs" / "assets.json").read_text(encoding="utf-8"))["assets"]["A"]["regions"]
    assert shown["MIRROR"] == TIGHT and shown["MIRROR"]["tight"] is True and shown["MIRROR"]["thing"] == "convex mirror"       # `tight` and `thing` pass through
    assert shown["RING"] == RING
    helper = json.loads((ws.root / "inputs" / "compile_input.json").read_text(encoding="utf-8"))
    assert helper["picks"]["assets"]["A"]["regions"]["MIRROR"] == TIGHT and helper["current"]["assets"]["A"]["regions"]["MIRROR"] == TIGHT
    # what `./check` compiles is what the real compile makes
    for cid, sp in auto.draft(load_inputs(proj)).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    out, _ = W.workspace_compile(ws.root, draw=False)
    assert out.storyboard["assets"]["A"]["regions"]["MIRROR"] == TIGHT and out.storyboard["assets"]["A"]["regions"]["RING"] == RING


def test_the_work_folder_of_an_edit_shows_the_saved_regions(proj, tmp_path):
    sb = save_old_storyboard(proj)
    victim = mirror_shot(sb)
    inp = load_inputs(proj)
    inp = clone_inputs(inp, edit_shots={victim["id"]}, scope=D.chapters_of_shots(inp, {victim["id"]}))
    ws = W.build(inp, root=tmp_path / "ws", instruction="make it slower")
    shown = json.loads((ws.root / "inputs" / "assets.json").read_text(encoding="utf-8"))["assets"]["A"]["regions"]
    assert shown["MIRROR"] == LOOSE and shown["RING"] == RING


def test_the_helpers_see_the_same_regions(proj, tmp_path):
    save_old_storyboard(proj)
    ws = W.build(load_inputs(proj), root=tmp_path / "ws")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "USERPROFILE")}
    env["PYTHONPATH"] = str(REPO)
    r = subprocess.run([sys.executable, "-m", "bti.draft.defaults", "CAM-05", "--asset", "A", "--region", "MIRROR", "--from", "whole"],
                       cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    want = VC.region_frame_info(TIGHT, 800, 1200)
    assert "compiler end frame: centre (400.0, 300.0) zoom %.4f" % want["zoom"] in r.stdout, r.stdout
    r2 = subprocess.run([sys.executable, "-m", "bti.draft.crop", "--region", "MIRROR", "-o", "look/crop.jpg"],
                        cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r2.returncode == 0 and "compiler end frame: centre (400.0, 300.0)" in r2.stdout, r2.stdout + r2.stderr
    for cid, sp in auto.draft(load_inputs(proj)).items():
        (ws.root / "out" / (cid + ".json")).write_text(json.dumps(sp), encoding="utf-8")
    r3 = subprocess.run([sys.executable, "-m", "bti.draft.still", "--shot", "c01:2", "-o", "look/s2.jpg", "--width", "320"],
                        cwd=str(ws.root), env=env, capture_output=True, text=True, timeout=120)
    assert r3.returncode == 0, r3.stdout + r3.stderr


# ------------------------------------------------------------------------------------------------------------------- a locked shot
def test_a_locked_shot_keeps_its_camera_numbers_and_its_overlay_follows_the_new_box_at_render(proj):
    """A locked shot is copied through as it is: its camera numbers (written for the loose box) stay. Its spotlight names the region, which the engine reads from
    the assets of the storyboard at render: it now lights the picks' tight box. The owner unlocks the shot to have both redone."""
    sb = save_old_storyboard(proj)
    locked = mirror_shot(sb)
    old_cam = copy.deepcopy(locked["params"]["camera"])
    for s in sb["shots"]:
        if s["id"] == locked["id"]:
            s["locked"] = True
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    res = compile_(load_inputs(proj))
    kept = next(s for s in res.storyboard["shots"] if s["id"] == locked["id"])
    assert kept["locked"] is True and kept["params"]["camera"] == old_cam
    assert [o["params"]["at"] for o in kept["overlays"] if o["technique"] == "HI-01"] == ["MIRROR"]
    assert res.storyboard["assets"]["A"]["regions"]["MIRROR"] == TIGHT
