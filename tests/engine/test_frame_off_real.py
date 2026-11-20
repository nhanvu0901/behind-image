"""Worker panelbox (2026-11-20): `frame_off_painting` on the two finished videos (`fixtures/catalogue/`: the storyboard, timing and picks of St. Eligius and of the Arnolfini
portrait, copied read-only from the server's `output/` folder). The Met's photograph of the Eligius panel (3469 x 4000) has a black ground round the painted surface; the
fixture has no picture, so the main painting is made up with the same geometry (a flat panel at 100, 106 to 3363, 3900 on black), and the program finds the box in it as it did in
the real photograph (which this test was frozen from: on the server the real file gave the same fifty-nine shots and the box 100, 106, 3363, 3900).

Proved on the real files (worker panelbox, read-only on the server): the very issues the stored storyboard gave before, plus `frame_off_painting`, and nothing else."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

import real_docs as RD

import bti.engine.api  # noqa: F401
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.timing import Timing

BEFORE = json.loads((RD.FIX / "issues_before.json").read_text(encoding="utf-8"))
PANEL = (100, 106, 3363, 3900)


def project_with_ground(tmp_path, name="eligius"):
    d = RD.build_project(tmp_path, name)
    sb = RD.load(name)
    main = json.loads((RD.FIX / name / "picks.json").read_text(encoding="utf-8"))["main_asset"]
    a = sb["assets"][main]
    im = Image.new("RGB", (a["width"], a["height"]), (0, 0, 0))
    im.paste(Image.new("RGB", (PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]), (96, 90, 84)), PANEL[:2])
    im.save(d / a["file"], quality=60)
    return d


def issues(d):
    return SB.validate(json.loads((d / "storyboard.json").read_text(encoding="utf-8")), Timing.load(d / "timing.json"), R.load_bundle("gae"), d)


@pytest.fixture(scope="module")
def eligius(tmp_path_factory):
    d = project_with_ground(tmp_path_factory.mktemp("eligius"))
    return d, issues(d)


def test_the_storyboard_of_the_first_export_gives_the_same_issues_as_before_and_the_new_warning(eligius):
    d, now = eligius
    new = [i for i in now if i["code"] == "frame_off_painting"]
    rest = [{"level": i["level"], "code": i["code"], "path": i["path"], "message": i["message"], "args": i["args"]} for i in now if i["code"] != "frame_off_painting"]
    assert rest == BEFORE["eligius"], "the stored storyboard validates with the same issues apart from the new warning"
    assert len(new) == 59 and {i["level"] for i in new} == {"warn"}


def test_the_mirror_close_ups_the_owner_saw_are_the_worst(eligius):
    d, now = eligius
    got = {i["args"]["shot"]: i["args"] for i in now if i["code"] == "frame_off_painting"}
    sb = RD.load("eligius")
    tm = Timing.load(d / "timing.json")
    at = {s["id"]: tm.resolve(s["start"]) for s in sb["shots"]}
    mmss = lambda t: "%d:%02d" % (int(t // 60), int(t % 60))        # noqa: E731
    # 8:14 to 8:25, 8:53 to 9:08 and 11:29 of the first export (the owner's notes)
    for sid, when, lo in (("s0076", "8:14", 0.07), ("s0077", "8:19", 0.10), ("s0082", "8:53", 0.08), ("s0083", "9:01", 0.08), ("s0106", "11:29", 0.10)):
        assert mmss(at[sid]) == when and got[sid]["share"] >= lo, (sid, got.get(sid))
    severe = sorted(k for k, a in got.items() if a["share"] >= 0.10)
    assert severe == ["s0077", "s0078", "s0080", "s0084", "s0106"]
    assert all(a["box"][0] in range(95, 120) and a["box"][2] in range(3340, 3369) for a in got.values()), "the box the program found is the painted surface"


def test_a_key_that_holds_the_whole_painting_is_a_pull_back_and_is_not_flagged(eligius):
    """The pull back that ends the cold open (s0009, from 0:44) ends on the whole panel: its second key shows the ground round it and says nothing, its first key
    (the full width of the file, 3% of black at each side) is what is flagged."""
    from bti.media import contentbox as CB
    sb = RD.load("eligius")
    shot = next(s for s in sb["shots"] if s["id"] == "s0009")
    k0, k1 = shot["params"]["camera"][0], shot["params"]["camera"][-1]
    assert not CB.holds_whole(PANEL, k0["cx"], k0["cy"], k0["zoom"]) and CB.holds_whole(PANEL, k1["cx"], k1["cy"], k1["zoom"])
    assert CB.outside_share(PANEL, k1["cx"], k1["cy"], k1["zoom"]) == 0.0 and CB.outside_share(PANEL, k0["cx"], k0["cy"], k0["zoom"]) > CB.OFF_LIMIT
    d, now = eligius
    (row,) = [i for i in now if i["code"] == "frame_off_painting" and i["args"]["shot"] == "s0009"]
    assert row["args"]["key"] == 0


def test_the_arnolfini_storyboard_is_clean(tmp_path):
    d = RD.build_project(tmp_path, "arnolfini")
    rows = [i for i in issues(d) if i["code"] == "frame_off_painting"]
    assert rows == [], [(i["args"]["shot"], i["args"]["share"]) for i in rows]
