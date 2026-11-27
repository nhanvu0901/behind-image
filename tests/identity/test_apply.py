"""The identity applier on the real Arnolfini storyboard (the draft tests' fixture): the five rules of the contract, section 6.
The style block is a FAKE one (conftest), so none of this depends on the registry entries of the `ID-*` techniques."""
from __future__ import annotations

import copy
import json

import pytest

from bti.identity import IdentityError, apply_identity, chosen_style, options, read
from bti.identity import titles as T


# ------------------------------------------------------------------------------------------------------------ helpers
def by_id(sb, sid):
    return next(s for s in sb["shots"] if s["id"] == sid)


def spans(sb, tm):
    t0 = [tm.resolve(s["start"]) for s in sb["shots"]]
    end = tm.resolve(sb["end"])
    return {s["id"]: (t0[i], t0[i + 1] if i + 1 < len(t0) else end) for i, s in enumerate(sb["shots"])}


def cam(shot, a, b, tm):
    """The camera of a shot as the engine builds it (anchors resolved against the shot), evaluated with the engine's own `Cam`."""
    from bti.engine.vfx import Cam
    return Cam([(tm.resolve(k["at"], a, b), k["cx"], k["cy"], k["zoom"], k.get("ease", "linear")) for k in shot["params"]["camera"]])


MARK_IDS = ["s0005", "s0015", "s0021", "s0030", "s0037", "s0044"]       # the six chapter cards of the fixture
TITLE_ID = "s0004"                                                      # its title card


def raking(sb, style, timing, meta=None):
    return apply_identity(sb, "raking", style, timing, meta or {})


def dim(sb, style, timing, meta=None):
    return apply_identity(sb, "dim", style, timing, meta or {})


# ------------------------------------------------------------------------------------------------------------ rule 3: chapter marks
def test_marks_are_numbered_in_order_in_title_case(sb, style, timing):
    out, rep = raking(sb, style, timing)
    titles = [by_id(out, i)["params"]["title"] for i in MARK_IDS]
    assert titles == ["1. The Merchant and His Brand", "2. The Woman in Green", "3. The Staged Interior", "4. The Alchemy of Light and Oil",
                      "5. Two Readings: Marriage Certificate or Symbolic Union", "6. The Borderland of Death: The Memorial Reading"]
    for i in MARK_IDS:
        s = by_id(out, i)
        assert s["technique"] == "ID-MARK-01" and s["intent"] == "structure" and s["source"] == "identity"
        assert set(s["params"]) == {"camera", "title"} and s["transition_in"] is None


def test_the_number_of_an_old_title_is_replaced_not_doubled(sb, style, timing):
    by_id(sb, "s0015")["params"]["title"] = "7. THE WOMAN IN GREEN"
    out, _ = raking(sb, style, timing)
    assert by_id(out, "s0015")["params"]["title"] == "2. The Woman in Green"


def test_non_ascii_letters_and_apostrophes_are_kept(sb, style, timing):
    by_id(sb, "s0005")["params"]["title"] = "DÜRER'S HANDS"
    by_id(sb, "s0015")["params"]["title"] = "L'ÉCOLE D'ATHÈNES"
    by_id(sb, "s0021")["params"]["title"] = "The Arnolfini's Wedding, Reconsidered"
    out, _ = raking(sb, style, timing)
    assert by_id(out, "s0005")["params"]["title"] == "1. Dürer's Hands"
    assert by_id(out, "s0015")["params"]["title"] == "2. L'École D'Athènes"
    assert by_id(out, "s0021")["params"]["title"] == "3. The Arnolfini's Wedding, Reconsidered"
    assert json.dumps(out, ensure_ascii=False).count("Dürer's") == 1


def test_title_case_rules():
    assert T.title_case("THE MERCHANT AND HIS BRAND") == "The Merchant and His Brand"
    assert T.title_case("a tale of two cities") == "A Tale of Two Cities"
    assert T.title_case("the mirror in the doorway") == "The Mirror in the Doorway"       # small words go down, the first one does not
    assert T.title_case("ARNOLFINI'S ROOM") == "Arnolfini's Room"                           # not "Arnolfini'S"
    assert T.title_case("SELF-PORTRAIT AT THE EASEL") == "Self-Portrait at the Easel"
    # the small words: a an the and or nor but for yet so of in on to at by as vs via per with from into
    assert T.title_case("TWO READINGS: MARRIAGE CERTIFICATE OR SYMBOLIC UNION") == "Two Readings: Marriage Certificate or Symbolic Union"
    assert T.title_case("PAINTER VS PATRON, FROM THE NORTH INTO LIGHT") == "Painter vs Patron, from the North into Light"
    assert T.title_case("art as power, with or without a patron") == "Art as Power, with or Without a Patron"
    # ... except as the first or the last word, or right after a colon
    assert T.title_case("WHAT IT IS ALL ABOUT") == "What It Is All About"
    assert T.title_case("THE THING TO LOOK AT") == "The Thing to Look At"
    assert T.title_case("WHAT IS IT FOR") == "What Is It For"
    assert T.title_case("THE MIRROR: THE END") == "The Mirror: The End"
    assert T.title_case("THE MIRROR: A STUDY IN GREEN") == "The Mirror: A Study in Green"
    assert T.title_case("BY THE WAY") == "By the Way"
    for t in ("THE FACE-TO-FACE", "L'ÉCOLE D'ATHÈNES", "Van Eyck's Mirror", "the end of the line", "WHAT IS IT FOR", "THE MIRROR: A STUDY IN GREEN"):
        assert T.title_case(T.title_case(t)) == T.title_case(t)
    assert T.strip_number("5. The Mirror") == "The Mirror" and T.strip_number("1434 Portrait") == "1434 Portrait"
    assert T.mark_title(5, "THE MIRROR") == "5. The Mirror" and T.mark_title(2, "9) the room") == "2. The Room"
    assert T.name_case("JAN VAN EYCK") == "Jan van Eyck"


def test_a_mark_flows_into_the_next_shot_on_resolved_numbers(sb, style, timing, tm):
    """When the next shot fills the screen, the mark ends on its first key and starts 4 % wider (still filling the screen).
    When the next shot does NOT fill the screen (whole painting or half-way pose), the mark uses a width-filling band instead."""
    from bti.media import contentbox as CB

    out, _ = raking(sb, style, timing)
    sp = spans(out, tm)
    a_info = out["assets"]["arnolfini_portrait"]
    w, h = float(a_info["width"]), float(a_info["height"])
    z_cover = round(1920.0 / w, 5)
    flowed = 0
    banded = 0
    for i in MARK_IDS:
        mark = by_id(out, i)
        j = out["shots"].index(mark) + 1
        nxt = out["shots"][j]
        assert nxt["intent"] != "structure" and nxt["params"].get("camera")
        assert mark["slots"]["image"]["asset"] == nxt["slots"]["image"]["asset"]
        a = cam(mark, *sp[i], tm)
        b = cam(nxt, *sp[nxt["id"]], tm)
        first = a.at(sp[i][0])
        end_of_mark = a.at(sp[i][1])
        start_of_next = b.at(sp[nxt["id"]][0])
        assert first[2] >= z_cover - 1e-5 and end_of_mark[2] >= z_cover - 1e-5
        assert CB.outside_share((0.0, 0.0, w, h), *first) <= CB.OFF_LIMIT + 1e-9
        assert CB.outside_share((0.0, 0.0, w, h), *end_of_mark) <= CB.OFF_LIMIT + 1e-9
        if start_of_next[2] >= z_cover - 1e-5:
            assert end_of_mark == pytest.approx(start_of_next, abs=1e-9), (i, end_of_mark, start_of_next)
            assert end_of_mark[2] / first[2] == pytest.approx(1.04, rel=1e-3)
            flowed += 1
        else:
            assert end_of_mark[2] / first[2] == pytest.approx(1.03, rel=1e-3)
            banded += 1
    assert flowed == 4 and banded == 2


def test_a_mark_before_a_shot_with_no_camera_uses_a_width_filling_band(sb, style, timing, tm):
    nxt = by_id(sb, "s0016")                      # the shot after chapter card s0015
    nxt["params"].pop("camera")
    out, _ = raking(sb, style, timing)
    mark = by_id(out, "s0015")
    assert mark["slots"]["image"]["asset"] == "arnolfini_portrait"            # the picture of the first shot of the video
    k0, k1 = mark["params"]["camera"]
    z = 0.43776                                                               # ceil(1920 / 4386 * 1e5) / 1e5: width-filling
    assert (k0["cx"], k0["cy"], k0["zoom"]) == (2193.0, 3000.0, z)
    assert k1["zoom"] == round(z * 1.03, 5) and k1["at"] == {"rel": 1.0} and k0["at"] == {"rel": 0.0}


def test_dim_sets_the_entry_dissolve_and_raking_clears_it(sb, style, timing):
    d, _ = dim(sb, style, timing)
    for i in MARK_IDS:
        s = by_id(d, i)
        assert s["technique"] == "ID-MARK-02" and s["transition_in"] == {"technique": "TR-01", "dur": 0.75, "params": {}}
    r, _ = raking(d, style, timing)
    assert all(by_id(r, i)["transition_in"] is None and by_id(r, i)["technique"] == "ID-MARK-01" for i in MARK_IDS)


def test_a_transition_is_never_longer_than_the_mark(sb, style, timing):
    style["identity"]["styles"]["dim"]["mark_transition"]["dur"] = 3.0
    by_id(sb, "s0016")["start"] = {"t": 195.61 + 1.6}              # the chapter card s0015 now lasts 1.6 s
    out, _ = dim(sb, style, timing)
    assert by_id(out, "s0015")["technique"] == "ID-MARK-02" and by_id(out, "s0015")["transition_in"]["dur"] == pytest.approx(1.55)
    by_id(sb, "s0016")["start"] = {"t": 195.61 + 0.7}              # under 1.5 s: too short for the new style, left as it is
    out2, rep = dim(sb, style, timing)
    assert any(x["shot"] == "s0015" and x["reason"] == "too_short" for x in rep["skipped"])
    assert by_id(out2, "s0015")["technique"] == "X-CARD-01"
    assert by_id(out2, "s0021")["params"]["title"] == "3. The Staged Interior"          # it still counts in the numbering


# ------------------------------------------------------------------------------------------------------------ rule 2: the title slot
def test_the_title_slot_becomes_the_channel_name_beat_filling_the_screen(sb, style, timing, tm):
    # s0060 ends on the whole painting (0.1719, not filling), so the beat uses a width-filling band instead of pillarboxed whole.
    out, rep = raking(sb, style, timing)
    s = by_id(out, TITLE_ID)
    assert s["technique"] == "ID-BRAND-01" and s["params"]["text"] == "RAKING LIGHT" and s["slots"] == {"image": {"asset": "arnolfini_portrait"}}
    k0, k1 = s["params"]["camera"]
    z = 0.43776
    assert (k0["cx"], k0["cy"], k0["zoom"]) == (2193.0, 3000.0, z)
    assert k1["zoom"] == round(z * 1.03, 5) and (k1["cx"], k1["cy"]) == (2193.0, 3000.0)
    assert s["intent"] == "structure" and s["note"] == "title card" and s["start"] == by_id(sb, TITLE_ID)["start"]
    assert not [x for x in rep["skipped"] if x["what"] == "brand"]
    d, _ = dim(sb, style, timing)
    assert by_id(d, TITLE_ID)["technique"] == "ID-BRAND-02"

    # When the previous shot ends on a screen-filling pose, the beat continues from that pose with a 3 % push.
    sb_fill = copy.deepcopy(sb)
    by_id(sb_fill, "s0060")["params"]["camera"][-1] = {"at": {"rel": 1.0}, "cx": 2193.0, "cy": 2400.0, "zoom": 0.60, "ease": "linear"}
    out2, _ = raking(sb_fill, style, timing)
    k0_f, k1_f = by_id(out2, TITLE_ID)["params"]["camera"]
    assert (k0_f["cx"], k0_f["cy"], k0_f["zoom"]) == (2193.0, 2400.0, 0.60)
    assert k1_f["zoom"] == round(0.60 * 1.03, 5) and (k1_f["cx"], k1_f["cy"]) == (2193.0, 2400.0)


def test_no_title_slot_is_reported_and_the_rest_is_still_done(sb, style, timing):
    sb["shots"] = [s for s in sb["shots"] if s["id"] != TITLE_ID]
    out, rep = raking(sb, style, timing)
    assert {"shot": None, "reason": "no_title_slot", "what": "brand"} == {k: rep["skipped"][0][k] for k in ("shot", "reason", "what")}
    assert [s["technique"] for s in out["shots"] if s["intent"] == "structure"] == ["ID-MARK-01"] * 6
    assert out["identity"] == {"style": "raking"}


def test_a_second_title_card_is_left_alone(sb, style, timing):
    extra = copy.deepcopy(by_id(sb, TITLE_ID))
    extra["id"], extra["start"] = "s9999", {"t": 700.0}
    sb["shots"].insert(sb["shots"].index(by_id(sb, "s0045")), extra)
    out, rep = raking(sb, style, timing)
    assert by_id(out, "s9999")["technique"] == "X-CARD-02"
    assert any(x["shot"] == "s9999" and x["reason"] == "extra_title" for x in rep["skipped"])


# ------------------------------------------------------------------------------------------------------------ rule 1: the opening
def test_raking_opening_overlay_and_label_on_the_first_shot(sb, style, timing, tm):
    out, rep = raking(sb, style, timing)
    first = out["shots"][0]
    a, b = spans(out, tm)[first["id"]]
    ov = {o["technique"]: o for o in first["overlays"] if o["technique"].startswith("ID-")}
    assert set(ov) == {"ID-OPEN-01", "ID-LABEL-01"}
    o = ov["ID-OPEN-01"]
    assert tm.resolve(o["start"]) == a == 0.0 and o["dur"] == pytest.approx(b - a, abs=1e-3) and o["params"] == {}
    assert o["source"] == "agent" and o["locked"] is False             # the compiler's word for "a program wrote it"
    lab = ov["ID-LABEL-01"]
    t0 = tm.resolve(lab["start"])
    assert lab["params"] == {"title": "The Arnolfini Portrait", "artist_year": "Jan van Eyck, 1434"}
    assert a <= t0 and t0 + lab["dur"] <= b + 1e-6 and lab["dur"] >= 3.0 - 1e-6            # the shot ends at 8.71 s: the start moved earlier to keep 3 s
    assert first["source"] == "agent"                                                       # the author's shot stays the author's
    assert "s0001" in rep["changed"]
    kept = [o["technique"] for o in first["overlays"] if not o["technique"].startswith("ID-")]
    assert kept == ["HI-01", "X-ANN-01"]                                                   # the shot's own overlays are untouched
    assert len({o["id"] for o in first["overlays"]}) == len(first["overlays"])


def test_dim_opening_is_one_overlay_that_carries_the_title(sb, style, timing, tm):
    out, _ = dim(sb, style, timing)
    first = out["shots"][0]
    ids = [o for o in first["overlays"] if o["technique"].startswith("ID-")]
    assert [o["technique"] for o in ids] == ["ID-OPEN-02"]
    assert ids[0]["params"] == {"title": "The Arnolfini Portrait", "sub": "JAN VAN EYCK · 1434"}
    a, b = spans(out, tm)["s0001"]
    t0 = tm.resolve(ids[0]["start"])
    assert a <= t0 and t0 + ids[0]["dur"] <= b + 1e-6 and ids[0]["dur"] >= 3.0 - 1e-6


def test_a_long_first_shot_keeps_the_nominal_start(sb, style, timing, tm):
    """With a shot that is long enough, the opening starts where the contract puts it (label 6.2 s, dim opening 7.0 s)."""
    sb["shots"] = [s for s in sb["shots"] if s["id"] not in ("s0056", "s0057")]        # the first shot now lasts until 26 s
    r, _ = raking(sb, style, timing)
    d, _ = dim(sb, style, timing)
    lab = next(o for o in r["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")
    assert tm.resolve(lab["start"]) == pytest.approx(6.2, abs=1e-3) and lab["dur"] == pytest.approx(4.5, abs=1e-3)
    op = next(o for o in d["shots"][0]["overlays"] if o["technique"] == "ID-OPEN-02")
    assert tm.resolve(op["start"]) == pytest.approx(7.0, abs=1e-3) and op["dur"] == pytest.approx(5.0, abs=1e-3)


def test_first_shot_shorter_than_three_seconds(sb, style, timing, tm):
    sb["shots"][1]["start"] = {"t": 2.0}                       # the first shot now lasts 2 s: the opening cannot sit on it
    out, rep = raking(sb, style, timing)
    assert any(x["what"] == "open" and x["reason"] == "no_room" and x["shot"] == "s0001" for x in rep["skipped"])
    assert not [o for o in out["shots"][0]["overlays"] if o["technique"] == "ID-OPEN-01"]
    lab = next(o for s in out["shots"] for o in s["overlays"] if o["technique"] == "ID-LABEL-01")       # the label is on the shot that is on screen at 6.2 s
    assert tm.resolve(lab["start"]) >= 2.0
    assert [s["id"] for s in out["shots"] if any(o["technique"] == "ID-LABEL-01" for o in s["overlays"])] == [sb["shots"][1]["id"]]


def test_the_opening_never_sits_on_a_card(sb, style, timing, tm):
    sb["shots"][1]["start"] = {"t": 5.0}                     # the shot on screen at 6.2 s is now a card ...
    sb["shots"][1]["intent"], sb["shots"][1]["technique"] = "structure", "X-CARD-01"
    sb["shots"][1]["params"] = {"title": "A CARD"}
    out, rep = raking(sb, style, timing)
    lab = next(o for s in out["shots"] for o in s["overlays"] if o["technique"] == "ID-LABEL-01")
    assert [s["id"] for s in out["shots"] if any(o is lab for o in s["overlays"])] == ["s0001"]      # ... so the label goes to the shot before it
    a, b = spans(out, tm)["s0001"]
    t0 = tm.resolve(lab["start"])
    assert a <= t0 and t0 + lab["dur"] <= b + 1e-6 and lab["dur"] == pytest.approx(4.5, abs=1e-3) and t0 == pytest.approx(0.5, abs=1e-3)


def test_opening_overlays_of_the_other_style_are_removed_everywhere(sb, style, timing):
    stray = {"id": "o77", "technique": "ID-LABEL-01", "intent": "structure", "start": {"t": 100.0}, "dur": 3.0, "params": {"title": "x", "artist_year": "y"},
             "slots": {}, "locked": False, "source": "agent", "note": ""}
    by_id(sb, "s0062")["overlays"].append(stray)
    out, _ = dim(sb, style, timing)
    all_ov = [o["technique"] for s in out["shots"] for o in s["overlays"]]
    assert "ID-LABEL-01" not in all_ov and all_ov.count("ID-OPEN-02") == 1


# ------------------------------------------------------------------------------------------------------------ rule 4: ids, locks, sources
def test_id_start_intent_note_locked_survive(sb, style, timing):
    out, _ = raking(sb, style, timing)
    for a, b in zip(sb["shots"], out["shots"]):
        for k in ("id", "start", "intent", "note", "locked"):
            assert a[k] == b[k], (a["id"], k)
    assert [s["id"] for s in out["shots"]] == [s["id"] for s in sb["shots"]]


def test_locked_shots_are_not_changed_and_are_listed(sb, style, timing):
    by_id(sb, TITLE_ID)["locked"] = True
    by_id(sb, "s0015")["locked"] = True
    first = by_id(sb, "s0001")
    first["locked"] = True
    out, rep = raking(sb, style, timing)
    for sid in (TITLE_ID, "s0015", "s0001"):
        assert json.dumps(by_id(out, sid), sort_keys=True) == json.dumps(by_id(sb, sid), sort_keys=True)
    got = {(x["shot"], x["what"]) for x in rep["skipped"] if x["reason"] == "locked"}
    assert {(TITLE_ID, "brand"), ("s0015", "mark"), ("s0001", "open"), ("s0001", "label")} <= got
    assert by_id(out, "s0021")["params"]["title"] == "3. The Staged Interior"          # a locked card still counts in the numbering
    assert "s0015" not in rep["changed"] and "s0021" in rep["changed"]


def test_a_locked_shot_keeps_an_old_opening_overlay(sb, style, timing):
    s = by_id(sb, "s0062")
    s["locked"] = True
    s["overlays"].append({"id": "o88", "technique": "ID-OPEN-01", "intent": "structure", "start": {"t": 100.0}, "dur": 3.0, "params": {}, "slots": {},
                          "locked": False, "source": "identity", "note": ""})
    out, rep = dim(sb, style, timing)
    assert any(o["id"] == "o88" for o in by_id(out, "s0062")["overlays"])
    assert any(x["shot"] == "s0062" and x["reason"] == "locked" for x in rep["skipped"])


def test_changed_shots_get_the_identity_source_and_untouched_shots_do_not(sb, style, timing):
    out, rep = raking(sb, style, timing)
    for sid in [TITLE_ID] + MARK_IDS:
        assert by_id(out, sid)["source"] == "identity"
    untouched = [s for s in out["shots"] if s["id"] not in rep["changed"]]
    assert len(untouched) > 80 and all(json.dumps(by_id(sb, s["id"]), sort_keys=True) == json.dumps(s, sort_keys=True) for s in untouched)
    assert set(rep["changed"]) == {"s0001", TITLE_ID, *MARK_IDS}


def test_the_input_is_not_changed(sb, style, timing):
    before = copy.deepcopy(sb)
    raking(sb, style, timing)
    assert sb == before


def test_derived_keys_are_not_carried(sb, style, timing):
    sb["shots"][0]["_t0"] = 0.0
    out, _ = raking(sb, style, timing)
    assert "_t0" not in out["shots"][0]


# ------------------------------------------------------------------------------------------------------------ rule 5: idempotence, round trip
def test_the_same_style_twice_is_byte_identical(sb, style, timing):
    for fn in (raking, dim):
        once, _ = fn(sb, style, timing)
        twice, rep = fn(once, style, timing)
        assert json.dumps(once, ensure_ascii=False) == json.dumps(twice, ensure_ascii=False)
        assert rep["changed"] == [] and rep["skipped"] == []


def test_raking_dim_raking_is_raking(sb, style, timing):
    once, _ = raking(sb, style, timing)
    d, _ = dim(once, style, timing)
    again, _ = raking(d, style, timing)
    assert json.dumps(once, ensure_ascii=False) == json.dumps(again, ensure_ascii=False)
    dd, _ = dim(sb, style, timing)
    back, _ = dim(again, style, timing)
    assert json.dumps(dd, ensure_ascii=False) == json.dumps(back, ensure_ascii=False)


def test_the_style_is_stored_with_the_video(sb, style, timing):
    out, _ = raking(sb, style, timing)
    assert out["identity"] == {"style": "raking"} and "identity" not in sb
    assert list(out)[list(out).index("style") + 1] == "identity"
    d, _ = dim(out, style, timing)
    assert d["identity"] == {"style": "dim"}
    assert chosen_style(d, style) == "dim" and chosen_style(sb, style) is None and chosen_style({"identity": {"style": "nope"}}, style) is None


# ------------------------------------------------------------------------------------------------------------ the project's words
def test_the_text_comes_from_the_old_title_card_then_from_the_project(sb, style, timing):
    card = by_id(sb, TITLE_ID)
    card["params"].update(title="THE ARNOLFINI WEDDING", artist="JAN VAN EYCK", year="1434")
    out, _ = raking(sb, style, timing)
    lab = next(o for o in out["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")
    assert lab["params"] == {"title": "The Arnolfini Wedding", "artist_year": "Jan van Eyck, 1434"}
    # a second application has no old card: the project's own title and the main picture's artist and year are used
    sb2 = copy.deepcopy(sb)
    sb2["shots"] = [s for s in sb2["shots"] if s["id"] != TITLE_ID]
    sb2["title"] = "The Arnolfini Portrait"
    out2, _ = raking(sb2, style, timing, {"main_asset": "arnolfini_portrait"})
    lab2 = next(o for o in out2["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")
    assert lab2["params"] == {"title": "The Arnolfini Portrait", "artist_year": "Jan van Eyck, 1434"}
    out3, _ = raking(sb2, style, timing, {"main_asset": "arnolfini_portrait", "title": "Meta Title", "artist": "A. Person", "year": "1999"})
    assert next(o for o in out3["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")["params"]["title"] == "Meta Title"


def test_the_words_of_an_earlier_application_are_kept_not_taken_from_the_project_again(sb, style, timing):
    """A second application has no old title card: it reads the opening words back, so an owner's edit of them is not lost and the same
    style twice stays byte-identical even when the card's words were not the project's."""
    by_id(sb, TITLE_ID)["params"].update(title="THE WEDDING OF GIOVANNI", artist="JAN VAN EYCK", year="1435")
    out, _ = raking(sb, style, timing)
    again, rep = raking(out, style, timing)
    assert rep["changed"] == [] and json.dumps(out) == json.dumps(again)
    lab = next(o for o in out["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")
    assert lab["params"] == {"title": "The Wedding of Giovanni", "artist_year": "Jan van Eyck, 1435"}
    lab["params"]["title"] = "An Owner's Title"                                      # the owner edits the label by hand
    d, _ = dim(out, style, timing)
    op = next(o for o in d["shots"][0]["overlays"] if o["technique"] == "ID-OPEN-02")
    assert op["params"] == {"title": "An Owner's Title", "sub": "JAN VAN EYCK · 1435"}
    back, _ = raking(d, style, timing)
    assert next(o for o in back["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")["params"] == {"title": "An Owner's Title", "artist_year": "Jan van Eyck, 1435"}


def test_a_capitals_artist_that_the_project_does_not_know_gets_name_case(sb, style, timing):
    by_id(sb, TITLE_ID)["params"].update(artist="LEONARDO DA VINCI", year="C. 1503")
    out, _ = dim(sb, style, timing)
    op = next(o for o in out["shots"][0]["overlays"] if o["technique"] == "ID-OPEN-02")
    assert op["params"]["sub"] == "LEONARDO DA VINCI · C. 1503"
    out2, _ = raking(sb, style, timing)
    lab = next(o for o in out2["shots"][0]["overlays"] if o["technique"] == "ID-LABEL-01")
    assert lab["params"]["artist_year"] == "Leonardo da Vinci, C. 1503"


# ------------------------------------------------------------------------------------------------------------ errors and the block
def test_unknown_style_and_missing_block(sb, style, timing):
    with pytest.raises(IdentityError) as e:
        apply_identity(sb, "sepia", style, timing)
    assert e.value.code == "unknown_style" and e.value.extra["allowed"] == ["raking", "dim"]
    with pytest.raises(IdentityError) as e2:
        apply_identity(sb, "raking", {"matte": {}}, timing)
    assert e2.value.code == "no_identity_block"


def test_the_block_is_read_not_assumed(style):
    cfg = read(style)
    assert cfg.channel_name == "RAKING LIGHT" and cfg.default_style == "raking" and cfg.ids() == ["raking", "dim"]
    assert options(style) == [{"id": "raking", "label": "Vệt sáng quét"}, {"id": "dim", "label": "Tối lại, hiện tên"}]
    assert cfg.style("dim").transition == {"technique": "TR-01", "dur": 0.75} and cfg.style("raking").transition is None
    assert cfg.style("dim").technique("label") is None and cfg.style("raking").technique("label") == "ID-LABEL-01"
    assert cfg.fit_pct == 95.5
    # a block with other ids and wrapped values: nothing is taken from constants
    other = {"identity": {"channel_name": {"value": "OTHER NAME", "source": "x"}, "default_style": {"value": "b"},
                          "styles": {"a": {"label_vi": "A", "open": "O-A", "brand": "B-A", "mark": "M-A"}, "b": {"label_vi": "B", "open": "O-B", "brand": "B-B", "mark": "M-B"}}}}
    c2 = read(other)
    assert c2.channel_name == "OTHER NAME" and c2.default_style == "b" and [o["id"] for o in c2.options()] == ["a", "b"]
    assert read({"identity": {}}) is None and read({}) is None and read(None) is None


def test_another_channel_name_and_other_techniques_are_used_as_given(sb, style, timing):
    style["identity"]["channel_name"] = "OTHER NAME"
    style["identity"]["styles"]["raking"]["mark"] = "ID-MARK-77"
    out, _ = raking(sb, style, timing)
    assert by_id(out, TITLE_ID)["params"]["text"] == "OTHER NAME" and by_id(out, "s0015")["technique"] == "ID-MARK-77"
    again, rep = raking(out, style, timing)
    assert rep["changed"] == []
