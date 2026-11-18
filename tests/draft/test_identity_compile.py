"""The draft compiler gives every new video its channel identity (contract 2026-11-18, section 6, last paragraph): the style the project chose
(`identity.style` of the saved storyboard), else the style.json default, applied at the end, so no step by the owner or the agent is needed.
Edit by instruction never applies it, and its merge and scope rules are untouched. Real registry, real engine; nothing calls a model."""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from bti import identity as ID
from bti.draft import decompile as D
from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import clone_inputs, load_inputs, resolve_edit_scope
from bti.draft.workspace import read_out
from bti.engine import registry as R
from bti.engine.timing import Timing
from helpers import GOOD, clean_spec, shot, spec

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "arnolfini_live"


def default_style() -> str:
    cfg = ID.read(R.load_bundle("gae").style)
    if cfg is None:
        pytest.skip("style/gae/style.json has no identity block yet")
    return cfg.default_style


def specs_of(chapters=GOOD):
    return {c: clean_spec(s, c) for c, s in chapters.items()}


def techniques(doc):
    return [s["technique"] for s in doc["shots"]]


def save(proj: Path, doc: dict) -> None:
    (proj / "storyboard.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------------------------------------------------- the default
def test_a_new_video_gets_the_default_style_with_no_step(proj_title_card):
    inp = load_inputs(proj_title_card)
    res = compile_specs(inp, specs_of())                      # draws three frames of every shot, the identity shots included
    assert not res.errors, summary_text(res)
    want = default_style()
    cfg = ID.read(R.load_bundle("gae").style)
    sd = cfg.style(want)
    assert res.storyboard["identity"] == {"style": want} and res.identity["style"] == want and res.identity["skipped"] == []
    ts = techniques(res.storyboard)
    assert "X-CARD-01" not in ts and "X-CARD-02" not in ts
    assert ts.count(sd.brand) == 1 and ts.count(sd.mark) == 1
    brand = next(s for s in res.storyboard["shots"] if s["technique"] == sd.brand)
    mark = next(s for s in res.storyboard["shots"] if s["technique"] == sd.mark)
    assert brand["params"]["text"] == cfg.channel_name and brand["intent"] == "structure" and brand["source"] == "identity"
    assert mark["params"]["title"] == "1. The Mirror"
    first = res.storyboard["shots"][0]
    assert any(o["technique"] == sd.open for o in first["overlays"])
    label = next((o for s in res.storyboard["shots"] for o in s["overlays"] if sd.label_role and o["technique"] == sd.label_role), None)
    if sd.label_role:
        assert label["params"]["artist_year"] == "Some Painter, 1434"
    # the check that drew the frames saw the final document
    assert res.drawn and not [i for i in res.issues if i["level"] == "error"]


def test_the_old_cards_stay_when_identity_is_switched_off(proj_title_card):
    res = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False, identity=False)
    assert "identity" not in res.storyboard and res.identity is None
    assert "X-CARD-02" in techniques(res.storyboard) and "X-CARD-01" in techniques(res.storyboard)


def test_the_default_is_read_from_style_json_not_assumed(proj_title_card, monkeypatch):
    cfg = ID.read(R.load_bundle("gae").style)
    other = next(i for i in cfg.ids() if i != cfg.default_style)
    b = R.load_bundle("gae")
    monkeypatch.setitem(b.style["identity"], "default_style", other)
    res = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    assert res.storyboard["identity"] == {"style": other}
    assert cfg.style(other).mark in techniques(res.storyboard)


# ----------------------------------------------------------------------------------------------------------- the chosen style
def test_the_style_the_project_chose_is_kept_on_a_redraft(proj_title_card):
    cfg = ID.read(R.load_bundle("gae").style)
    chosen = next(i for i in cfg.ids() if i != cfg.default_style)
    inp = load_inputs(proj_title_card)
    res = compile_specs(inp, specs_of(), draw=False)
    again, _ = ID.apply_identity(res.storyboard, chosen, R.load_bundle("gae").style, Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]}), {"main_asset": "A"})
    save(proj_title_card, again)
    res2 = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    assert not res2.errors, summary_text(res2)
    assert res2.storyboard["identity"] == {"style": chosen}
    sd = cfg.style(chosen)
    assert sd.mark in techniques(res2.storyboard) and sd.brand in techniques(res2.storyboard)
    assert cfg.style(cfg.default_style).mark not in techniques(res2.storyboard)


def test_cards_keep_their_ids_on_a_redraft(proj_title_card):
    """The title slot and the chapter mark are cards: a re-draft hands their old ids back, it does not make new ones every time."""
    res = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    cards = {s["technique"]: s["id"] for s in res.storyboard["shots"] if s["intent"] == "structure"}
    save(proj_title_card, res.storyboard)
    res2 = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    assert {s["technique"]: s["id"] for s in res2.storyboard["shots"] if s["intent"] == "structure"} == cards
    assert [s["id"] for s in res2.storyboard["shots"]] == [s["id"] for s in res.storyboard["shots"]]


def test_a_locked_mark_is_not_made_again(proj_title_card):
    res = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    mark = next(s for s in res.storyboard["shots"] if s["intent"] == "structure" and s["technique"] == ID.read(R.load_bundle("gae").style).style(res.storyboard["identity"]["style"]).mark)
    mark["locked"] = True
    save(proj_title_card, res.storyboard)
    res2 = compile_specs(load_inputs(proj_title_card), specs_of(), draw=False)
    kept = next(s for s in res2.storyboard["shots"] if s["id"] == mark["id"])
    assert kept == mark
    assert [s["technique"] for s in res2.storyboard["shots"] if s["intent"] == "structure"].count(mark["technique"]) == 1


def test_an_agent_never_writes_a_mark_or_the_title_slot(proj_title_card):
    cfg = ID.read(R.load_bundle("gae").style)
    chapters = copy.deepcopy(GOOD)
    chapters["c02"]["shots"].insert(0, shot("b0004", 30, cfg.style(cfg.default_style).mark, slots={"image": {"asset": "A"}}, params={"title": "9. By hand"}))
    res = compile_specs(load_inputs(proj_title_card), specs_of(chapters), draw=False)
    assert not res.errors, summary_text(res)
    assert [i for i in res.issues if i["code"] == "card_written_by_agent" and i["level"] == "warn"]
    assert not [s for s in res.storyboard["shots"] if s["params"].get("title") == "9. By hand"]


# ----------------------------------------------------------------------------------------------------------- edit mode
def _arnolfini_with_identity(tmp_path, style_id):
    dst = tmp_path / "arnolfini-live"
    dst.mkdir()
    shutil.copyfile(FIXTURE_DIR / "timing.json", dst / "timing.json")
    sb = json.loads((FIXTURE_DIR / "storyboard.json").read_text(encoding="utf-8"))
    tm = json.loads((FIXTURE_DIR / "timing.json").read_text(encoding="utf-8"))
    out, rep = ID.apply_identity(sb, style_id, R.load_bundle("gae").style, Timing({"duration": tm["duration"], "words": tm["words"]}), {"main_asset": "arnolfini_portrait"})
    assert rep["skipped"] == []
    (dst / "storyboard.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return dst, out


def _edit_unchanged(dst, scope):
    """The edit mode with specs the agent left exactly as decompiled: nothing may change, nothing may be reported."""
    inp0 = load_inputs(dst, None, for_edit=True)
    es, sc, _ = resolve_edit_scope(inp0, scope)
    inp = clone_inputs(inp0, scope=sc, edit_shots=es)
    dec = D.decompile(inp, es)
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "out").mkdir()
        for c, v in dec.items():
            if c in inp.in_scope():
                (Path(td) / "out" / (c + ".json")).write_text(json.dumps(v["spec"]), encoding="utf-8")
        out = read_out(Path(td), inp.in_scope(), {**inp.picks["assets"], **((inp.current or {}).get("assets") or {})})
        return inp, compile_specs(inp, out.specs, regions=out.regions, spec_problems=out.problems, degrade=False, draw=False)


@pytest.mark.parametrize("style_id", ["raking", "dim"])
def test_edit_by_instruction_leaves_the_identity_alone(tmp_path, style_id):
    default_style()
    dst, saved = _arnolfini_with_identity(tmp_path, style_id)
    for scope in ({"all": True}, {"chapter": "c03"}, {"chapter": "c08"}, {"shots": ["s0016"]}):
        inp, res = _edit_unchanged(dst, scope)
        assert res.violations == [], (scope, [v["message"] for v in res.violations])
        assert res.identity is None
        assert res.storyboard["identity"] == {"style": style_id}, scope
        strip = lambda shots: json.loads(json.dumps(shots, sort_keys=True))        # noqa: E731
        assert strip(res.storyboard["shots"]) == strip(saved["shots"]), scope


# ----------------------------------------------------------------------------------------------------------- short silences
def _lead(proj, kind, seconds):
    """Chapter 2 of the synthetic project gets a lead of `kind` that lasts `seconds` and ends just before its first word."""
    t = json.loads((proj / "timing.json").read_text())
    end = round(t["words"][30]["s"] - 0.1, 3)
    t["chapters"][1]["lead"] = {"kind": kind, "start": round(end - seconds, 3), "end": end}
    t["chapters"][1]["card"] = kind != "plain"
    (proj / "timing.json").write_text(json.dumps(t))


def test_a_silence_too_short_for_the_style_leaves_the_old_card_and_no_error(proj):
    """The compiler places a chapter card from 1.0 s; the identity's mark needs 1.5 s: the old card stays (reported), nothing fails."""
    _lead(proj, "card", 1.2)
    res = compile_specs(load_inputs(proj), specs_of(), draw=False)
    assert not res.errors, summary_text(res)
    cards = [s for s in res.storyboard["shots"] if s["intent"] == "structure"]
    assert [c["technique"] for c in cards] == ["X-CARD-01"] and res.identity["style"] == default_style()
    assert [(x["reason"], x["what"], x["shot"]) for x in res.identity["skipped"] if x["what"] == "mark"] == [("too_short", "mark", cards[0]["id"])]
    assert not [i for i in res.issues if i["code"] == "element_too_short"]


def test_a_long_enough_silence_gives_the_mark_and_a_short_title_slot_stays_old(proj):
    _lead(proj, "title", 3.8)                                 # chapter card 2.8 s, title slot 1.0 s
    res = compile_specs(load_inputs(proj), specs_of(), draw=False)
    assert not res.errors, summary_text(res)
    cfg = ID.read(R.load_bundle("gae").style)
    sd = cfg.style(default_style())
    by = {s["technique"]: s for s in res.storyboard["shots"] if s["intent"] == "structure"}
    assert set(by) == {"X-CARD-02", sd.mark}                  # the 1.0 s title slot could not become the channel-name beat
    assert any(x["reason"] == "too_short" and x["what"] == "brand" for x in res.identity["skipped"])
    assert not [i for i in res.issues if i["code"] == "element_too_short"]
