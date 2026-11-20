"""Worker catalogue (2026-11-20): the two finished videos (`christus-st-eligius`, `eyck-the-arnolfini-portrait`; their storyboard, timing and picks are copied read-only from the
server's `output/` folder to `fixtures/catalogue/`) use techniques the catalogue now hides. They must stay valid and draw as before: `validate` gives the very issues it
gave before the catalogue pass (`fixtures/catalogue/issues_before.json`, taken from the unchanged code), and none of the new checks says anything on them, because no beat of
their picks carries `kinds`. With the `kinds` of the St. Eligius lines written by hand the checks flag what the owner found by eye."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import real_docs as RD

from bti.engine import registry as R
from bti.engine import viewchecks as VC

BUNDLE = R.load_bundle("gae")
BEFORE = json.loads((RD.FIX / "issues_before.json").read_text(encoding="utf-8"))


def techniques_of(name):
    sb = RD.load(name)
    used = set()
    for s in sb["shots"]:
        used.add(s["technique"])
        used |= {o["technique"] for o in s.get("overlays") or []}
        if isinstance(s.get("transition_in"), dict):
            used.add(s["transition_in"].get("technique"))
    return used


@pytest.mark.parametrize("name", sorted(RD.KEYS))
def test_a_finished_video_uses_techniques_the_catalogue_hides_and_still_validates_with_the_same_issues(tmp_path, name):
    hidden = {t for t in techniques_of(name) if t and not BUNDLE.offered(t)}
    assert hidden, "the point of the proof: %s uses hidden techniques" % name
    now = RD.issues_of(name, tmp_path)
    assert now == BEFORE[name], "validate() of the stored storyboard changed"
    assert not [i for i in now if i["level"] == "error"] and {i["code"] for i in now} <= {"audio_missing", "project_name_differs"}


def test_the_hidden_techniques_the_two_videos_use(tmp_path):
    used = {n: {t for t in techniques_of(n) if t and not BUNDLE.offered(t)} for n in RD.KEYS}
    assert "STATIC-04" in used["arnolfini"] and "X-HI-01" in used["arnolfini"]
    assert used["eligius"] and used["eligius"] <= {"ID-BRAND-01", "ID-MARK-01", "ID-OPEN-01", "ID-LABEL-01"}, "St. Eligius: only what the program writes"


@pytest.mark.parametrize("name", sorted(RD.KEYS))
def test_the_new_checks_say_nothing_on_a_video_whose_picks_have_no_kinds(tmp_path, name):
    d = RD.build_project(tmp_path, name)
    assert not any("kinds" in e for e in json.loads((d / "picks.json").read_text(encoding="utf-8"))["beats"].values())
    assert RD.flagged(name, tmp_path / "again", {}) == []


def test_with_the_kinds_of_the_lines_written_by_hand_the_checks_flag_the_three_one_place_maps(tmp_path):
    rows = RD.flagged("eligius", tmp_path, RD.ELIGIUS_KINDS)
    assert sorted((r["code"], r["args"]["shot"], tuple(r["args"]["beats"])) for r in rows) == sorted(
        [("device_wrong_kind", "s0024", ("b0011",)), ("device_too_little", "s0024", ("b0011",)),                    # 2:26 "born at Limoges"
         ("device_wrong_kind", "s0054", ("b0027",)), ("device_too_little", "s0054", ("b0027",)),                    # 5:36 Bruges
         ("device_wrong_kind", "s0102", ("b0055",)), ("device_too_little", "s0102", ("b0055",))])                   # 11:04 Switzerland
    assert {r["level"] for r in rows} == {"warn"}


def test_the_maps_that_tie_two_places_are_not_flagged(tmp_path):
    flagged_shots = {r["args"]["shot"] for r in RD.flagged("eligius", tmp_path, RD.ELIGIUS_KINDS)}
    assert "s0018" not in flagged_shots, "Lübeck to Bruges (b0008) is a journey with a route"
    assert "s0029" not in flagged_shots, "Noyon and Bruges (b0014) are two places tied by a diocese"
    assert "s0107" not in flagged_shots, "Bruges to Antwerp (b0057) is a journey with a route"
    assert "s0092" not in flagged_shots, "the time axis of b0049 has three dates"


def test_the_figure_over_the_saint_is_flagged_once_the_picture_of_the_thing_counted_is_in_the_picks(tmp_path):
    rows = RD.flagged("eligius", tmp_path, RD.ELIGIUS_KINDS, {"b0028": [RD.CARAVEL_PICTURE]})
    fig = [r for r in rows if r["code"] == "figure_on_wrong_picture"]
    assert len(fig) == 1 and fig[0]["args"]["shot"] == "s0056" and fig[0]["args"]["overlay"] == "o1" and fig[0]["args"]["assets"] == ["caravel_view"]
    assert fig[0]["args"]["asset"] == "goldsmith_his_shop_3bc1"
    assert len(rows) == 7 and not [r for r in rows if r["code"] in ("outside_on_painting", "outside_picture_small")]


def test_every_line_of_the_narration_has_hand_made_kinds_from_the_known_words():
    tm = json.loads(RD.timing_path("eligius").read_text(encoding="utf-8"))
    assert sorted(RD.ELIGIUS_KINDS) == sorted(b["id"] for b in tm["beats"]) and len(tm["beats"]) == 61
    assert all(1 <= len(v) <= 2 and set(v) <= set(VC.KINDS) for v in RD.ELIGIUS_KINDS.values())
