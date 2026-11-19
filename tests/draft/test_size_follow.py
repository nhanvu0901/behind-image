"""Worker sizefollow: a draft never compiles from a picture size that disagrees with the stored file.

`load_inputs` reads `picks.json` raw from disk, so it corrects the picks' assets itself (`bti.media.assets.reconcile_sizes`: the
declared size becomes the stored size and the regions follow, in memory). The saved storyboard's own copy of the assets is NOT
rescaled when it is LOADED (`inputs.current`): its camera keys were written for the size it declares (the validator warns about it). The
compiler no longer lets that copy keep the file's facts (followups item 4): they come from the picks, the regions follow the new size.
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


def add_storyboard_side_facts(proj):
    """What a person or an agent added to the saved storyboard's copy of A, in the space that copy declares (DECLARED), plus a stale
    size of the source that the picks do not carry."""
    f = proj / "storyboard.json"
    sb = json.loads(f.read_text(encoding="utf-8"))
    a = sb["assets"]["A"]
    a["regions"]["RING"] = {"x": 1000, "y": 1800, "rx": 100, "ry": 100, "label": "Ring"}
    a["title"] = "A title the owner typed on the storyboard"
    a["note"] = "a field only the storyboard side has"
    a["original_width"], a["original_height"] = 9999, 9999
    sb["assets"]["ONLY"] = {**copy.deepcopy(sb["assets"]["B"]), "title": "a picture only the storyboard has"}
    f.write_text(json.dumps(sb, indent=1), encoding="utf-8")
    return sb


def test_a_redraft_takes_the_facts_of_the_file_from_the_picks(proj):
    """followups item 4. `compile._merge_assets` used to let the saved storyboard's copy replace the picks' asset as a whole, so a
    storyboard drafted before a size correction kept the wrong size for ever (and `asset_size_mismatch` never cleared). The facts of the
    stored file (`FILE_FACTS`: file, kind, width, height, original_width, original_height, duration) now always come from the picks."""
    saved_with_wrong_size(proj)
    add_storyboard_side_facts(proj)
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    pick = load_inputs(proj).picks["assets"]["A"]
    for chapters in (None, ["c01"]):
        a = compile_for(load_inputs(proj, chapters)).storyboard["assets"]["A"]
        assert (a["width"], a["height"]) == (800, 1200)
        assert (a["original_width"], a["original_height"]) == DECLARED                  # the picks' record of the source, not the stale 9999
        assert a["file"] == pick["file"] and a["kind"] == pick["kind"]


def test_what_the_storyboard_side_added_is_kept_and_its_regions_follow_the_new_size(proj):
    saved_with_wrong_size(proj)
    add_storyboard_side_facts(proj)
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    sb = compile_for(load_inputs(proj)).storyboard
    a = sb["assets"]["A"]
    assert a["regions"]["MIRROR"] == {"x": 400, "y": 300, "rx": 80, "ry": 80, "label": "Mirror"}        # scaled as `reconcile_sizes` scales
    assert a["regions"]["RING"] == {"x": 500, "y": 900, "rx": 50, "ry": 50, "label": "Ring"}            # added on the storyboard in the old space
    assert a["title"] == "A title the owner typed on the storyboard" and a["note"] == "a field only the storyboard side has"
    only = sb["assets"]["ONLY"]
    assert only["title"] == "a picture only the storyboard has" and (only["width"], only["height"]) == (600, 400)    # not in the picks: its own record
    assert (sb["assets"]["B"]["width"], sb["assets"]["B"]["height"]) == (600, 400)                      # a picture that agrees is untouched


def test_regions_of_a_picture_whose_size_already_agrees_are_not_scaled(proj):
    sb = compile_for(load_inputs(proj)).storyboard                                       # picks right, storyboard saved right
    (proj / "storyboard.json").write_text(json.dumps(sb, indent=1), encoding="utf-8")
    a = compile_for(load_inputs(proj)).storyboard["assets"]["A"]
    assert (a["width"], a["height"]) == (800, 1200) and a["regions"]["MIRROR"] == sb["assets"]["A"]["regions"]["MIRROR"]


def test_drafting_again_clears_the_size_warning(proj, tmp_path):
    """The advice of the page's sentence ("Dựng nháp lại để cập nhật kích thước hình.") is true: the saved storyboard warns, a draft job
    (whole video, then the accepted proposal saved as the storyboard) no longer carries the wrong size, and the warning is gone."""
    from bti.draft import run as R
    from bti.engine.api import open_project
    from bti.longjob import LongJobManager
    saved_with_wrong_size(proj)
    declare_wrong(proj, regions={"MIRROR": dict(MIRROR_DECLARED)})
    warn = lambda: [i for i in open_project(proj).validate() if i.get("code") == "asset_size_mismatch"]      # noqa: E731
    assert [i["args"]["asset"] for i in warn()] == ["A"]
    mgr = LongJobManager(projects_root=proj.parent)
    j = mgr.wait(R.start(proj.name, proj, provider="auto", manager=mgr), timeout=120)
    assert j is not None and j["state"] == "done", j
    doc = json.loads((proj / "proposals" / (j["result"]["proposal_id"] + ".json")).read_text(encoding="utf-8"))
    a = doc["storyboard"]["assets"]["A"]
    assert (a["width"], a["height"]) == (800, 1200) and a["regions"]["MIRROR"]["x"] == 400
    (proj / "storyboard.json").write_text(json.dumps(doc["storyboard"], indent=1), encoding="utf-8")        # what "Áp dụng" saves
    assert warn() == []
