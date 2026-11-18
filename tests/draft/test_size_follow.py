"""Worker sizefollow: a draft never compiles from a picture size that disagrees with the stored file.

`load_inputs` reads `picks.json` raw from disk, so it corrects the picks' assets itself (`bti.media.assets.reconcile_sizes`: the
declared size becomes the stored size and the regions follow, in memory). The saved storyboard's own copy of the assets is NOT
rescaled: its camera keys and regions were written for the size it declares (the validator warns about it instead).
Fakes only: the synthetic project of `helpers.make_synth_project`, no network, no model."""
from __future__ import annotations

import copy
import json

from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import load_inputs
from helpers import GOOD, clean_spec

# the synthetic picture A is a 800 x 1200 file; its MIRROR region is at (400, 300) r 80. Declared at twice the size, as an old
# import of a large Commons picture was (the file is a scaled rendition, the record is the original's size).
DECLARED = (1600, 2400)
MIRROR_DECLARED = {"x": 800, "y": 600, "rx": 160, "ry": 160, "label": "Mirror"}


def declare_wrong(proj, key="A", size=DECLARED, regions=None):
    f = proj / "picks.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    a = raw["assets"][key]
    a["width"], a["height"] = size
    if regions is not None:
        a["regions"] = regions
    f.write_text(json.dumps(raw), encoding="utf-8")
    return raw


def compile_for(inp):
    res = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    assert not res.errors, summary_text(res)
    return res


def test_picks_declaring_another_size_than_the_file_are_corrected_in_the_inputs(proj):
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    a = load_inputs(proj).picks["assets"]["A"]
    assert (a["width"], a["height"]) == (800, 1200)                                      # the stored file's pixels
    assert a["regions"]["MIRROR"] == {"x": 400, "y": 300, "rx": 80, "ry": 80, "label": "Mirror"}   # scaled with the picture
    assert (a["original_width"], a["original_height"]) == DECLARED                        # what the record said is kept


def test_the_compiled_storyboard_carries_the_stored_size_and_the_scaled_regions(proj):
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    sb = compile_for(load_inputs(proj)).storyboard
    a = sb["assets"]["A"]
    assert (a["width"], a["height"]) == (800, 1200)
    assert a["regions"]["MIRROR"]["x"] == 400 and a["regions"]["MIRROR"]["y"] == 300 and a["regions"]["MIRROR"]["rx"] == 80
    assert (sb["assets"]["B"]["width"], sb["assets"]["B"]["height"]) == (600, 400)       # a picture that agrees is untouched


def test_a_draft_compiled_from_wrong_picks_equals_one_compiled_from_right_picks(proj, tmp_path):
    """The same project, once with the old wrong record and once written correctly: the same storyboard (no shot is placed by a
    size that is not the picture's)."""
    from helpers import make_synth_project
    good = make_synth_project(tmp_path / "projects" / "right")
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    a = compile_for(load_inputs(proj)).storyboard
    b = compile_for(load_inputs(good)).storyboard
    for k in ("A", "B"):
        for f in ("width", "height", "regions"):
            assert a["assets"][k].get(f) == b["assets"][k].get(f), (k, f)
    assert a["shots"] == b["shots"]


def test_reading_the_inputs_writes_nothing(proj):
    declare_wrong(proj)
    before = (proj / "picks.json").read_bytes()
    load_inputs(proj)
    assert (proj / "picks.json").read_bytes() == before


def test_loading_the_inputs_twice_gives_the_same_picks_and_hash(proj):
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    a, b = load_inputs(proj), load_inputs(proj)
    assert a.picks == b.picks and a.hashes() == b.hashes()


def test_a_missing_size_is_still_filled_in(proj):
    f = proj / "picks.json"
    raw = json.loads(f.read_text(encoding="utf-8"))
    del raw["assets"]["B"]["width"], raw["assets"]["B"]["height"]
    f.write_text(json.dumps(raw), encoding="utf-8")
    b = load_inputs(proj).picks["assets"]["B"]
    assert (b["width"], b["height"]) == (600, 400)


def test_a_missing_or_unreadable_file_leaves_the_declared_size(proj):
    declare_wrong(proj, "B", (1200, 800))
    (proj / "media" / "b.jpg").write_bytes(b"not an image")
    b = load_inputs(proj).picks["assets"]["B"]
    assert (b["width"], b["height"]) == (1200, 800)
    (proj / "media" / "b.jpg").unlink()
    b = load_inputs(proj).picks["assets"]["B"]
    assert (b["width"], b["height"]) == (1200, 800)


# ------------------------------------------------------------------------------------------- the saved storyboard
def saved_with_wrong_size(proj):
    """A storyboard compiled from the right picks, then written the way an old import left it: A declared at DECLARED, with its
    region in that space."""
    res = compile_for(load_inputs(proj))
    sb = copy.deepcopy(res.storyboard)
    sb["assets"]["A"]["width"], sb["assets"]["A"]["height"] = DECLARED
    sb["assets"]["A"]["regions"]["MIRROR"] = dict(MIRROR_DECLARED)
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    return sb


def test_the_saved_storyboards_own_assets_are_not_rescaled(proj):
    saved = saved_with_wrong_size(proj)
    inp = load_inputs(proj)
    a = inp.current["assets"]["A"]
    assert (a["width"], a["height"]) == DECLARED and a["regions"]["MIRROR"] == MIRROR_DECLARED       # camera keys were written for this size
    assert inp.current["shots"] == saved["shots"]
    assert "original_width" not in a


def test_the_picks_are_corrected_even_when_a_storyboard_exists(proj):
    saved_with_wrong_size(proj)
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    inp = load_inputs(proj)
    assert (inp.picks["assets"]["A"]["width"], inp.picks["assets"]["A"]["height"]) == (800, 1200)
    assert (inp.current["assets"]["A"]["width"], inp.current["assets"]["A"]["height"]) == DECLARED


def test_picks_taken_from_the_storyboard_stay_the_storyboards_own_copy(proj):
    """Editing with no usable picks.json: the picks are a copy of the storyboard's assets and must agree with it, or the agent would
    be shown one size while the compiler used another."""
    saved_with_wrong_size(proj)
    (proj / "picks.json").unlink()
    inp = load_inputs(proj, for_edit=True)
    a = inp.picks["assets"]["A"]
    assert (a["width"], a["height"]) == DECLARED and a["regions"]["MIRROR"] == MIRROR_DECLARED
    assert inp.picks["assets"]["A"] == inp.current["assets"]["A"]


def test_the_validator_names_the_picture_a_stale_storyboard_still_carries(proj):
    """The way the owner learns of it: the storyboard keeps the declared size, so its validation warns."""
    from bti.engine.api import open_project
    saved_with_wrong_size(proj)
    got = [i for i in open_project(proj).validate() if i.get("code") == "asset_size_mismatch"]
    assert [i["args"]["asset"] for i in got] == ["A"] and got[0]["args"]["stored_width"] == 800


def test_a_redraft_still_carries_the_saved_storyboards_asset_size_today(proj):
    """Documents the present behaviour, not a wish: `compile._merge_assets` lets the saved storyboard's own copy of an asset override
    the picks' one, so a re-draft (whole or one chapter) over a storyboard that carries a wrong size keeps that size and the
    `asset_size_mismatch` warning stays. This is why the page's sentence for the warning does not tell the owner to re-draft. When
    the compiler learns to take the stored size for such an asset, this test fails: then add that advice to the sentence
    (sbissues.js `asset_size_mismatch`) and flip this test."""
    saved_with_wrong_size(proj)
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    for chapters in (None, ["c01"]):
        a = compile_for(load_inputs(proj, chapters)).storyboard["assets"]["A"]
        assert (a["width"], a["height"]) == DECLARED
