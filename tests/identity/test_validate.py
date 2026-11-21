"""The `identity` field of the storyboard and its two issues (storyboard.validate). The style block is a fake one put on a fresh bundle
(never on the cached one), so these tests do not depend on the registry entries of the `ID-*` techniques."""
from __future__ import annotations

import copy

import pytest

from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import techniques  # noqa: F401  (registers every renderer: `available` needs them)
from bti.engine.timing import Timing
from conftest import FAKE_STYLE


@pytest.fixture()
def bundle():
    b = R.StyleBundle("gae")                                    # a fresh instance: the cached bundle of the process is never touched
    b.style = dict(b.style, identity=copy.deepcopy(FAKE_STYLE["identity"]))
    return b


@pytest.fixture()
def tmg(timing):
    return Timing({"duration": timing["duration"], "words": timing["words"]})


def issues(sb, tmg, bundle, code):
    return [i for i in SB.validate(sb, tmg, bundle) if i.get("code") == code]


def test_an_old_storyboard_without_the_field_has_no_identity_issue(sb, tmg, bundle):
    assert "identity" not in sb
    got = SB.validate(sb, tmg, bundle)
    assert not [i for i in got if str(i.get("code", "")).startswith("identity_")]
    assert not [i for i in got if i["level"] == "error"]
    sb["identity"] = None                                       # null is the same as absent
    assert not issues(sb, tmg, bundle, "identity_style_unknown")


@pytest.mark.parametrize("bad", ["sepia", "", None, 3, ["raking"], "RAKING"])
def test_an_unknown_style_is_an_error_that_names_the_choices(sb, tmg, bundle, bad):
    sb["identity"] = {"style": bad}
    got = issues(sb, tmg, bundle, "identity_style_unknown")
    assert len(got) == 1 and got[0]["level"] == "error" and got[0]["path"] == "identity.style"
    assert got[0]["args"]["allowed"] == ["raking", "dim"]
    assert "raking" in got[0]["message"] and "dim" in got[0]["message"]


@pytest.mark.parametrize("bad", ["raking", ["raking"], 5, {}])
def test_identity_must_be_an_object_with_a_style(sb, tmg, bundle, bad):
    sb["identity"] = bad
    got = issues(sb, tmg, bundle, "identity_style_unknown")
    assert len(got) == 1 and got[0]["level"] == "error" and got[0]["path"] in ("identity", "identity.style")


def test_a_style_without_an_identity_block_refuses_the_field(sb, tmg):
    b = R.StyleBundle("gae")
    b.style = {k: v for k, v in b.style.items() if k != "identity"}
    sb["identity"] = {"style": "raking"}
    got = issues(sb, tmg, b, "identity_style_unknown")
    assert len(got) == 1 and got[0]["args"]["allowed"] == []


def test_a_listed_style_is_accepted(sb, tmg, bundle):
    sb["identity"] = {"style": "dim"}
    assert not issues(sb, tmg, bundle, "identity_style_unknown")


def test_old_cards_in_a_video_with_a_chosen_style_are_warnings(sb, tmg, bundle):
    sb["identity"] = {"style": "raking"}
    got = issues(sb, tmg, bundle, "identity_technique_mismatch")
    # the fixture has one old title card and six old chapter cards
    assert len(got) == 7 and all(i["level"] == "warn" for i in got)
    by = {i["args"]["shot"]: i for i in got}
    assert by["s0004"]["args"] == {"shot": "s0004", "technique": "X-CARD-02", "style": "raking", "wanted": "ID-BRAND-01"}
    assert by["s0005"]["args"]["wanted"] == "ID-MARK-01" and by["s0005"]["path"] == "shots[9].technique"


def test_a_shot_of_the_other_style_is_a_warning_too(sb, tmg, bundle):
    sb["identity"] = {"style": "dim"}
    for s in sb["shots"]:
        if s["technique"] == "X-CARD-01":
            s["technique"] = "ID-MARK-01"
    got = issues(sb, tmg, bundle, "identity_technique_mismatch")
    marks = [i for i in got if i["args"]["technique"] == "ID-MARK-01"]
    assert len(marks) == 6 and all(i["args"]["wanted"] == "ID-MARK-02" for i in marks)


def test_shots_of_the_chosen_style_and_other_structure_shots_are_not_warned(sb, tmg, bundle):
    sb["identity"] = {"style": "raking"}
    for s in sb["shots"]:
        if s["intent"] == "structure":
            s["technique"] = {"X-CARD-02": "ID-BRAND-01", "X-CARD-01": "ID-MARK-01"}[s["technique"]]
    sb["shots"][-1]["intent"] = "structure"                      # a credit card or anything else that is not part of the identity
    sb["shots"][-1]["technique"] = "X-CARD-03"
    assert not issues(sb, tmg, bundle, "identity_technique_mismatch")


def test_the_identity_source_is_a_known_source(sb, tmg, bundle):
    sb["shots"][0]["source"] = "identity"
    assert not issues(sb, tmg, bundle, "unknown_source")
    sb["shots"][0]["source"] = "someone"
    assert issues(sb, tmg, bundle, "unknown_source")


def test_every_code_the_check_emits_is_listed():
    assert {"identity_style_unknown", "identity_technique_mismatch"} <= set(SB.ISSUE_CODES)


# ------------------------------------------------------------------------------------------------------------ element_too_short
def _mark_of_length(sb, seconds):
    """The fixture's chapter card s0005 as an `ID-MARK-01` that lasts `seconds` (the next shot starts that much after it)."""
    i = next(k for k, s in enumerate(sb["shots"]) if s["id"] == "s0005")
    card = sb["shots"][i]
    card["technique"], card["params"], card["slots"] = "ID-MARK-01", {"title": "1. A Mark"}, {"image": {"asset": "arnolfini_portrait"}}
    sb["shots"][i + 1]["start"] = {"t": card["start"]["t"] + seconds}
    return i


def test_a_shot_of_the_identity_shorter_than_the_registry_floor_is_an_error(sb, tmg, bundle):
    i = _mark_of_length(sb, 1.0)
    got = issues(sb, tmg, bundle, "element_too_short")
    assert len(got) == 1 and got[0]["level"] == "error" and got[0]["path"] == "shots[%d]" % i
    assert got[0]["args"]["technique"] == "ID-MARK-01" and got[0]["args"]["min"] == bundle.spec("ID-MARK-01")["timing"]["min_s"] == 1.5
    assert got[0]["args"]["got"] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize("seconds", [1.5, 1.6, 2.8])
def test_at_the_floor_or_above_it_is_fine(sb, tmg, bundle, seconds):
    _mark_of_length(sb, seconds)
    assert not issues(sb, tmg, bundle, "element_too_short")


def test_the_floor_is_read_from_the_registry_not_written_down(sb, tmg, bundle):
    bundle.by_id["ID-MARK-01"]["timing"] = dict(bundle.by_id["ID-MARK-01"]["timing"], min_s=2.0)
    _mark_of_length(sb, 1.8)
    got = issues(sb, tmg, bundle, "element_too_short")
    assert len(got) == 1 and got[0]["args"]["min"] == 2.0


def test_an_overlay_of_the_identity_shorter_than_the_floor_is_an_error(sb, tmg, bundle):
    first = sb["shots"][0]
    for dur, expect in ((1.0, 1), (1.5, 0), (4.0, 0)):
        first["overlays"] = [o for o in first["overlays"] if not o["technique"].startswith("ID-")]
        first["overlays"].append({"id": "o9", "technique": "ID-OPEN-01", "intent": "structure", "start": {"t": 0.5}, "dur": dur, "params": {}, "slots": {},
                                  "locked": False, "source": "agent", "note": ""})
        got = issues(sb, tmg, bundle, "element_too_short")
        assert len(got) == expect, (dur, got)
        if expect:
            assert got[0]["path"] == "shots[0].overlays[%d]" % (len(first["overlays"]) - 1) and got[0]["args"]["got"] == pytest.approx(1.0)


def test_other_techniques_have_no_such_floor(sb, tmg, bundle):
    i = next(k for k, s in enumerate(sb["shots"]) if s["id"] == "s0005")
    sb["shots"][i + 1]["start"] = {"t": sb["shots"][i]["start"]["t"] + 0.5}            # an old card (X-CARD-01) of half a second
    assert not issues(sb, tmg, bundle, "element_too_short")


def test_the_new_code_is_listed():
    assert "element_too_short" in SB.ISSUE_CODES
