"""The applier against the REAL registry and style.json (the `ID-*` techniques and the `identity` block written by the engine side):
what it writes validates, every technique it names exists with the right kind and slot, and the compiled documents carry no error."""
from __future__ import annotations

import pytest

from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import techniques  # noqa: F401  (registers every renderer)
from bti.identity import apply_identity, options, read


@pytest.fixture(scope="module")
def bundle():
    b = R.load_bundle("gae")
    if read(b.style) is None:
        pytest.skip("style/gae/style.json has no identity block yet")
    return b


def test_the_block_names_techniques_of_the_right_kind(bundle):
    cfg = read(bundle.style)
    assert cfg.channel_name == "RAKING LIGHT" and cfg.default_style in cfg.ids() and set(cfg.ids()) >= {"raking", "dim"}
    for sd in cfg.styles.values():
        for role, kind in (("open", "overlay"), ("label", "overlay"), ("brand", "base"), ("mark", "base")):
            tid = sd.technique(role)
            if tid is None:
                assert role == "label"                              # only the `dim` opening writes the title itself
                continue
            spec = bundle.spec(tid)
            assert spec is not None and spec["kind"] == kind and bundle.available(tid), (sd.id, role, tid)
            if role in ("brand", "mark"):
                assert "structure" in spec["intents"] and [s["name"] for s in spec["slots"]] == ["image"]
                assert "camera" in {p["name"] for p in spec["params"]}
        if sd.transition:
            assert bundle.spec(sd.transition["technique"])["kind"] == "transition"
    assert [o["label"] for o in options(bundle.style)] == [bundle.style["identity"]["styles"][i]["label_vi"] for i in cfg.ids()]


@pytest.mark.parametrize("style_id", ["raking", "dim"])
def test_the_applied_storyboard_validates_with_no_error(bundle, sb, timing, tm, style_id):
    out, rep = apply_identity(sb, style_id, bundle.style, timing, {"main_asset": "arnolfini_portrait"}, defaults=bundle.param_defaults)
    got = SB.validate(out, tm, bundle)
    assert [i for i in got if i["level"] == "error"] == [], [i for i in got if i["level"] == "error"][:3]
    assert not [i for i in got if i["code"] in ("identity_technique_mismatch", "unknown_source", "identity_style_unknown")]
    assert rep["skipped"] == [] and len(rep["changed"]) == 8


def test_a_style_chosen_over_an_old_video_warns_until_it_is_applied(bundle, sb, timing, tm):
    old = dict(sb, identity={"style": "dim"})
    warns = [i for i in SB.validate(old, tm, bundle) if i["code"] == "identity_technique_mismatch"]
    assert len(warns) == 7
    out, _ = apply_identity(old, "dim", bundle.style, timing, {})
    assert not [i for i in SB.validate(out, tm, bundle) if i["code"] == "identity_technique_mismatch"]


def test_the_old_look_is_still_valid_and_drawable_by_name(bundle, sb, tm):
    assert "identity" not in sb
    assert [i for i in SB.validate(sb, tm, bundle) if i["level"] == "error"] == []


@pytest.mark.parametrize("style_id", ["raking", "dim"])
def test_what_is_written_carries_every_registry_param_like_the_compilers_shots(bundle, sb, timing, style_id):
    """So that a later edit which rebuilds a shot (and fills the defaults) does not "change" the identity's overlays and cards."""
    out, _ = apply_identity(sb, style_id, bundle.style, timing, {"main_asset": "arnolfini_portrait"}, defaults=bundle.param_defaults)
    cfg = read(bundle.style)
    sd = cfg.style(style_id)
    seen = 0
    for s in out["shots"]:
        for o in s["overlays"]:
            if o["technique"] in (sd.open, sd.label_role):
                assert set(o["params"]) == {p["name"] for p in bundle.spec(o["technique"])["params"]}, o["technique"]
                seen += 1
        if s["technique"] in (sd.brand, sd.mark):
            assert set(s["params"]) == {p["name"] for p in bundle.spec(s["technique"])["params"]}, s["technique"]
            seen += 1
    assert seen == 1 + (1 if sd.label_role else 0) + 1 + 6
    again, rep = apply_identity(out, style_id, bundle.style, timing, {"main_asset": "arnolfini_portrait"}, defaults=bundle.param_defaults)
    assert rep["changed"] == [] and again == out


@pytest.mark.parametrize("style_id", ["raking", "dim"])
@pytest.mark.parametrize("card_s", [0.4, 1.0, 1.49, 1.5, 2.0, 2.8])
def test_the_applier_never_makes_an_element_the_engine_refuses(bundle, sb, timing, tm, style_id, card_s):
    """Every chapter card of the fixture is cut to `card_s` seconds: those under the floor stay old cards (reported `too_short`), the
    others become marks; the document never carries `element_too_short`, whatever the lengths."""
    cards = [i for i, s in enumerate(sb["shots"]) if s["intent"] == "structure"]
    for i in cards:
        sb["shots"][i + 1]["start"] = {"t": sb["shots"][i]["start"]["t"] + card_s}
    out, rep = apply_identity(sb, style_id, bundle.style, timing, {"main_asset": "arnolfini_portrait"}, defaults=bundle.param_defaults)
    got = SB.validate(out, tm, bundle)
    assert not [i for i in got if i["code"] == "element_too_short"], [i for i in got if i["code"] == "element_too_short"][:2]
    floor = read(bundle.style).min_element_s
    kept_old = [s for s in out["shots"] if s["intent"] == "structure" and s["technique"] in ("X-CARD-01", "X-CARD-02")]
    if card_s < floor - 1e-9:
        assert len(kept_old) == len(cards) and {x["reason"] for x in rep["skipped"] if x["what"] in ("mark", "brand")} == {"too_short"}
    else:
        assert not kept_old
    for s in out["shots"]:
        for o in s["overlays"]:
            if o["technique"] in (read(bundle.style).style(style_id).open, read(bundle.style).style(style_id).label_role):
                assert o["dur"] >= 3.0 - 1e-6
