"""The new channel-name beat `ID-BRAND-03` in the identity applier, and the video's title (worker introflow).

    * the style block names `ID-BRAND-03` for `raking`, with the nominal numbers of the new opening, and lists `ID-BRAND-01` as an EARLIER FORM of the style
      (`earlier`): a storyboard made before the change is not reported as another style's;
    * `apply_identity` writes `text`, `title` and `subtitle` on a beat whose technique has the params, from `identity.video_title` (or the painting's own
      title), keeps `identity.video_title`, and gives the same document when it is applied twice;
    * the validator accepts `identity.video_title` (a string).

The style block is a copy of the real one with the numbers written out and the registry's answer is a stub: no registry entry, no renderer."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bti import identity as ID
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import techniques  # noqa: F401  (registers every renderer: `available` needs them)
from bti.engine.timing import Timing
from bti.identity import apply_identity, is_mismatch, read, with_video_title
from conftest import FAKE_STYLE

NEW_STYLE = copy.deepcopy(FAKE_STYLE)
NEW_STYLE["identity"]["styles"]["raking"].update({
    "brand": "ID-BRAND-03", "earlier": {"brand": ["ID-BRAND-01"]},
    "nominal": {"open": {"start_s": 0.0, "dur_s": 3.6}, "label": {"start_s": 1.2, "dur_s": 3.8}, "brand": {"dur_s": 9.1}, "mark": {"dur_s": 3.2}}})


def defaults(tid):
    """What the registry would give: the params of the technique (the contract of ID-BRAND-03: camera, text, title, subtitle)."""
    base = {"camera": None, "shadow": True}
    if tid == "ID-BRAND-03":
        return {**base, "text": "RAKING LIGHT", "title": "", "subtitle": ""}
    if tid == "ID-BRAND-01":
        return {**base, "text": "RAKING LIGHT"}
    return {}


@pytest.fixture()
def style():
    return copy.deepcopy(NEW_STYLE)


def by_id(sb, sid):
    return next(s for s in sb["shots"] if s["id"] == sid)


def beat(sb):
    return next(s for s in sb["shots"] if s["technique"] == "ID-BRAND-03")


def raking(sb, style, timing, **kw):
    return apply_identity(sb, "raking", style, timing, {"main_asset": "arnolfini_portrait"}, defaults=defaults, **kw)


# ----------------------------------------------------------------------------------------------------------------- the block
def test_the_block_reads_the_new_beat_the_numbers_and_the_earlier_form(style):
    cfg = read(style)
    sd = cfg.style("raking")
    assert sd.brand == "ID-BRAND-03" and sd.earlier == {"brand": ("ID-BRAND-01",)} and sd.own("brand") == {"ID-BRAND-03", "ID-BRAND-01"}
    assert (sd.start_s["open"], sd.dur_s["open"], sd.start_s["label"], sd.dur_s["label"], sd.dur_s["brand"], sd.dur_s["mark"]) == (0.0, 3.6, 1.2, 3.8, 9.1, 3.2)
    assert cfg.style("dim").earlier == {}


def test_the_real_style_json_has_the_same_block():
    real = json.loads((Path(__file__).resolve().parents[2] / "style" / "gae" / "style.json").read_text(encoding="utf-8"))
    sd = read(real).style("raking")
    assert sd.brand == "ID-BRAND-03" and sd.earlier == {"brand": ("ID-BRAND-01",)}
    assert (sd.start_s["open"], sd.dur_s["open"], sd.start_s["label"], sd.dur_s["label"], sd.dur_s["brand"], sd.dur_s["mark"]) == (0.0, 1.35, 0.3, 7.7, 9.1, 3.2)
    assert sd.cross_cut == {"label": True}
    assert read(real).style("dim").brand == "ID-BRAND-02" and read(real).style("dim").dur_s["open"] == 5.0           # dim is left as it is


def test_the_earlier_form_is_not_a_mismatch_and_another_styles_technique_is(style):
    cfg = read(style)
    assert not is_mismatch(cfg, "raking", "ID-BRAND-01") and not is_mismatch(cfg, "raking", "ID-BRAND-03") and not is_mismatch(cfg, "raking", "ID-MARK-01")
    assert is_mismatch(cfg, "raking", "ID-BRAND-02") and is_mismatch(cfg, "raking", "ID-MARK-02") and is_mismatch(cfg, "raking", "X-CARD-02")
    assert is_mismatch(cfg, "dim", "ID-BRAND-01") and is_mismatch(cfg, "dim", "ID-BRAND-03")                  # the earlier form belongs to raking only


def test_a_stored_storyboard_with_the_earlier_beat_gets_no_mismatch_warning(sb, timing, style):
    b = R.StyleBundle("gae")
    b.style = dict(b.style, identity=copy.deepcopy(style["identity"]))
    tm = Timing({"duration": timing["duration"], "words": timing["words"]})
    sb["identity"] = {"style": "raking"}
    for s in sb["shots"]:
        if s["intent"] == "structure":
            s["technique"] = {"X-CARD-02": "ID-BRAND-01", "X-CARD-01": "ID-MARK-01"}[s["technique"]]
    got = [i for i in SB.validate(sb, tm, b) if i["code"] in ("identity_technique_mismatch", "unknown_source", "identity_style_unknown")]
    assert got == []
    by_id(sb, "s0004")["technique"] = "ID-BRAND-02"                      # the other style's beat is still reported
    assert [i["args"]["technique"] for i in SB.validate(sb, tm, b) if i["code"] == "identity_technique_mismatch"] == ["ID-BRAND-02"]


# ----------------------------------------------------------------------------------------------------------------- the texts
def test_the_beat_has_the_video_title_and_a_small_line_with_the_painting_and_the_artist(sb, timing, style):
    sb["identity"] = {"style": "raking", "video_title": "  The Mirror\nThat Remembers "}
    out, rep = raking(sb, style, timing)
    p = beat(out)["params"]
    assert beat(out)["id"] == "s0004" and p["text"] == "RAKING LIGHT"
    assert p["title"] == "The Mirror That Remembers"
    first_label = next(o for s in out["shots"] for o in s["overlays"] if o["technique"] == "ID-LABEL-01")
    assert p["subtitle"] == "%s · %s" % (first_label["params"]["title"], first_label["params"]["artist_year"])      # the same words the label uses
    assert out["identity"] == {"style": "raking", "video_title": "  The Mirror\nThat Remembers "}                      # the title is kept as it was written


def test_without_a_video_title_the_title_is_the_painting_and_the_line_below_is_artist_and_year(sb, timing, style):
    out, _ = raking(sb, style, timing)
    p = beat(out)["params"]
    label = next(o for s in out["shots"] for o in s["overlays"] if o["technique"] == "ID-LABEL-01")["params"]
    assert p["title"] == label["title"] and p["subtitle"] == label["artist_year"] and p["text"] == "RAKING LIGHT"
    assert out["identity"] == {"style": "raking"}


def test_a_beat_whose_technique_has_no_such_params_is_written_as_before(sb, timing, style):
    out, _ = apply_identity(sb, "raking", style, timing, {"main_asset": "arnolfini_portrait"}, defaults=lambda tid: {"camera": None, "text": "X"} if tid == "ID-BRAND-03" else {})
    assert set(beat(out)["params"]) == {"camera", "text"}
    out, _ = apply_identity(sb, "raking", style, timing, {"main_asset": "arnolfini_portrait"})            # no registry at all
    assert set(beat(out)["params"]) == {"camera", "text"}


def test_applying_twice_gives_the_same_document_with_the_title(sb, timing, style):
    sb["identity"] = {"style": "raking", "video_title": "The Mirror That Remembers"}
    once, _ = raking(sb, style, timing)
    twice, rep = raking(once, style, timing)
    assert json.dumps(twice, sort_keys=True) == json.dumps(once, sort_keys=True) and rep["changed"] == []
    again, _ = raking(with_video_title(once, "Another Title"), style, timing)
    assert beat(again)["params"]["title"] == "Another Title" and beat(again)["params"]["subtitle"] == beat(once)["params"]["subtitle"]
    assert again["identity"] == {"style": "raking", "video_title": "Another Title"}
    gone, _ = raking(with_video_title(again, ""), style, timing)
    assert "video_title" not in gone["identity"] and beat(gone)["params"]["title"] == beat(once)["params"]["subtitle"].split(" · ")[0]


def test_with_video_title_sets_changes_and_removes_it_in_place_without_changing_the_input(sb):
    snap = json.dumps(sb, sort_keys=True)
    a = with_video_title(sb, "A Title")
    assert a["identity"] == {"video_title": "A Title"} and json.dumps(sb, sort_keys=True) == snap
    keys = list(a)
    assert keys.index("identity") == keys.index("style") + 1                       # right after `style`, where the applier puts it
    b = with_video_title({**a, "identity": {"style": "raking", "video_title": "A Title"}}, "")
    assert b["identity"] == {"style": "raking"} and with_video_title(sb, None) == sb and "identity" not in with_video_title(sb, "")
    assert ID.video_title_of(a) == "A Title" and ID.video_title_of(sb) is None and ID.video_title_of({"identity": {"video_title": "  "}}) is None


# ------------------------------------------------------------------------------------------------------------- the nominal numbers
def test_the_opening_and_the_label_sit_on_the_first_shot_with_the_new_numbers(sb, timing, style):
    tm = Timing({"duration": timing["duration"], "words": timing["words"]})
    out, rep = raking(sb, style, timing)
    first = out["shots"][0]
    op = next(o for o in first["overlays"] if o["technique"] == "ID-OPEN-01")
    lab = next(o for o in first["overlays"] if o["technique"] == "ID-LABEL-01")
    assert tm.resolve(op["start"]) == pytest.approx(0.0, abs=1e-3) and op["dur"] == pytest.approx(3.6, abs=1e-3)
    assert tm.resolve(lab["start"]) == pytest.approx(1.2, abs=1e-3) and lab["dur"] == pytest.approx(3.8, abs=1e-3)


def test_the_validator_accepts_the_video_title_and_wants_a_string(sb, timing, style):
    b = R.StyleBundle("gae")
    b.style = dict(b.style, identity=copy.deepcopy(style["identity"]))
    tm = Timing({"duration": timing["duration"], "words": timing["words"]})
    for ok in ({"style": "raking", "video_title": "A title"}, {"style": "raking", "video_title": None}, {"style": "raking"}):
        sb["identity"] = ok
        assert not [i for i in SB.validate(sb, tm, b) if i["path"].startswith("identity")], ok
    sb["identity"] = {"style": "raking", "video_title": 5}
    got = [i for i in SB.validate(sb, tm, b) if i["path"] == "identity.video_title"]
    assert len(got) == 1 and got[0]["level"] == "error" and got[0]["code"] == "not_a_string"
