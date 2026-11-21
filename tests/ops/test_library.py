"""The library on its own: no HTTP, no files written, the document passed in is never changed; and the small pieces it is made of
(the schema checker, the time helpers ported from the page)."""
import copy
import subprocess
import sys

import pytest
from ops_helpers import REPO, read_json, snapshot, timing_doc, word, word_t

import bti.engine.api as engine_api
from bti.engine.timing import Timing
from bti.ops import ERRORS, OpError, apply_ops, parse_request, schemacheck
from bti.ops.errors import SMALL, small
from bti.ops.facts import PicksFacts, StoryboardFacts
from bti.ops.timeline import Timeline, camera_lists, clean_word, fmt_time, jround
from bti.picks import doc as pdoc


def test_the_library_imports_no_http():
    code = ("import sys, bti.ops, bti.ops.runner, bti.ops.adapters, bti.ops.log, bti.ops.undo, bti.ops.doc\n"
            "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('fastapi', 'starlette', 'uvicorn', 'httpx'))\n"
            "assert not bad, bad\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-600:]


def test_apply_ops_to_picks_returns_a_new_document_and_touches_nothing(root, proj):
    doc = pdoc.load(proj)
    original = copy.deepcopy(doc)
    before = snapshot(proj)
    res = apply_ops("picks", doc, [{"op": "skip_beat", "beat": "b0004", "reason": "r"}, {"op": "set_main", "asset": "B"}],
                    PicksFacts.from_project(proj), actor="agent:test")
    assert doc == original and snapshot(proj) == before
    assert res.doc["main_asset"] == "B" and res.doc["beats"]["b0004"]["status"] == "skip" and res.applied == 2
    assert [c["what"] for c in res.changes] == ["Đoạn 4: dùng lại tranh chính", "Tranh chính: đổi sang hình “Test landscape”"]
    assert res.created == {"shots": [], "overlays": [], "assets": [], "refs": {}} and res.touched_by == {"beat:b0004": 0, "main": 1}


def test_apply_ops_to_a_storyboard_returns_a_new_document_and_touches_nothing(root, proj):
    doc = read_json(proj / "storyboard.json")
    original = copy.deepcopy(doc)
    before = snapshot(proj)
    project = engine_api.open_project(proj)
    res = apply_ops("storyboard", doc, [{"op": "lock", "shot": "s0003"}, {"op": "split_shot", "shot": "s0004", "at": 26.0}],
                    StoryboardFacts(proj, project, doc), actor="human")
    assert doc == original and snapshot(proj) == before
    assert [s["id"] for s in res.doc["shots"]][2:6] == ["s0003", "s0004", "s0011", "s0005"] and res.doc["shots"][2]["locked"] is True
    assert res.created["shots"] == ["s0011"] and not [i for i in res.issues if i["level"] == "error"]


def test_a_typed_error_comes_out_of_the_library(root, proj):
    doc = read_json(proj / "storyboard.json")
    facts = StoryboardFacts(proj, engine_api.open_project(proj), doc)
    with pytest.raises(OpError) as e:
        apply_ops("storyboard", doc, [{"op": "lock", "shot": "s0006"}], facts)
    assert e.value.code == "locked" and e.value.status == 409 and e.value.op_index == 0 and e.value.retry == "after_fix"
    body = e.value.body()
    assert set(body) >= {"code", "fix", "retry", "fields", "op_index"} and body["fields"][0]["path"] == "ops[0].shot"
    with pytest.raises(OpError) as e:
        parse_request({"base_rev": "x", "actor": "human", "ops": []})
    assert e.value.code == "invalid_request"


def test_every_error_code_can_be_built():
    for code in ERRORS:
        e = OpError(code, "A sentence.")
        assert e.body()["code"] == code and e.body()["fix"] and e.body()["retry"] in ("no", "after_fix", "later")
    assert OpError("stale_revision", "x", current_rev="abc").body()["current_rev"] == "abc"
    assert OpError("locked", "x", fix="Do this.", retry="later", status=418).body()["fix"] == "Do this."
    with pytest.raises(KeyError):
        OpError("no_such_code", "x")


def test_allowed_is_given_only_when_the_set_is_small():
    assert small(range(SMALL)) == list(range(SMALL)) and small(range(SMALL + 1)) is None


# ---------------------------------------------------------------- the schema checker
def test_the_schema_checker_understands_what_the_schemas_use():
    S = schemacheck
    schema = S.obj("x", ["a"], {"a": S.integer(minimum=1, maximum=3), "b": S.string(pattern=r"^b\d$", hint="b and a digit", max_length=2),
                                "c": S.array(S.string(enum=["u", "v"]), min_items=1, max_items=2), "d": S.number(exclusive_minimum=0, nullable=True),
                                "e": S.any_of(S.number(), S.plain_object({"t": S.number()}, ["t"]), title="seconds or an anchor"),
                                "f": S.boolean(), "g": S.free_object(min_properties=1)})
    ok = {"op": "x", "a": 2, "b": "b1", "c": ["u"], "d": None, "e": {"t": 1}, "f": True, "g": {"k": 1}}
    assert S.validate(schema, ok, "ops[0]") == []
    assert S.validate(schema, {**ok, "a": 2.0}, "ops[0]") == []                                      # a whole number written 2.0 is whole
    bad = {"op": "y", "a": 4, "b": "x", "c": ["w", "u", "u"], "d": 0, "e": "now", "f": 1, "g": {}, "h": 1}
    got = {f["path"]: f for f in S.validate(schema, bad, "ops[0]")}
    assert set(got) == {"ops[0].op", "ops[0].a", "ops[0].b", "ops[0].c", "ops[0].c[0]", "ops[0].d", "ops[0].e", "ops[0].f", "ops[0].g", "ops[0].h"}
    assert got["ops[0].a"]["problem"] == "must be at most 3" and "b and a digit" in got["ops[0].b"]["problem"]
    assert got["ops[0].c"]["problem"] == "must have at most 2 items" and got["ops[0].d"]["problem"] == "must be greater than 0"
    assert got["ops[0].e"]["problem"] == "must be seconds or an anchor" and got["ops[0].f"]["problem"] == "must be true or false"
    assert got["ops[0].h"]["allowed"] == ["a", "b", "c", "d", "e", "f", "g", "op"] and got["ops[0].op"]["allowed"] == ["x"]
    assert [f["path"] for f in S.validate(schema, {"op": "x", "a": True}, "ops[0]")] == ["ops[0].a"]       # a boolean is no number
    assert [f["path"] for f in S.validate(schema, {"op": "x", "a": float("nan")}, "ops[0]")] == ["ops[0].a"]
    assert [f["path"] for f in S.validate(schema, {"op": "x"}, "ops[3]")] == ["ops[3].a"]
    assert [f["path"] for f in S.validate(schema, {"op": "x", "a": 1, "c": ["u", 5]}, "ops[0]")] == ["ops[0].c[1]"]


# ---------------------------------------------------------------- the time helpers (the page's own rules, ported)
def timeline():
    return Timeline(Timing(timing_doc()))


def test_jround_rounds_halves_up_like_the_page():
    assert jround(2.5, 0) == 3 and jround(0.125, 2) == 0.13 and jround(1.0049999, 2) == 1.0 and jround(-0.5, 0) == 0


def test_fmt_time():
    assert [fmt_time(t) for t in (None, 0, 8.1, 59.9, 60, 102.4, 3599, 3600, 3725)] == [None, "0:00", "0:08", "0:59", "1:00", "1:42", "59:59", "1:00:00", "1:02:05"]


def test_clean_word_keeps_letters_digits_apostrophe_and_hyphen():
    assert clean_word("“Don't-stop,”") == "Don't-stop" and clean_word("...") == "..." and clean_word("école!") == "école" and clean_word(None) == ""


def test_anchor_from_time_snaps_to_a_word_start_within_a_third_of_a_second():
    t = timeline()
    assert t.anchor_from_time(word_t(10) + 0.1) == {"w": 10, "off": 0, "text": word(10)}
    assert t.anchor_from_time(word_t(10) + 0.34) == {"w": 11, "off": 0, "text": word(11)}                # the next word starts 0.01 s later
    assert t.anchor_from_time(word_t(249) + 0.34) == {"w": 249, "off": 0, "text": word(249)}
    assert t.anchor_from_time(word_t(249) + 0.4) == {"t": jround(word_t(249) + 0.4)}                    # farther than 0.35 s from every word: free
    assert t.anchor_from_time(100.0) == {"t": 100.0}                                                 # after the last word: free
    assert t.anchor_from_time(word_t(10) + 0.1, snap=False) == {"t": jround(word_t(10) + 0.1)}
    assert t.anchor_from_time(-5) == {"t": 0.0}                                                      # 0.4 s from the first word: free, never negative


def test_parse_anchor():
    t = timeline()
    assert t.parse_anchor({"w": 5}) == ({"w": 5, "off": 0, "text": word(5)}, None)
    assert t.parse_anchor({"w": 5, "off": 0.25, "text": word(5)}) == ({"w": 5, "off": 0.25, "text": word(5)}, None)
    assert t.parse_anchor({"t": 3}) == ({"t": 3.0}, None)
    for bad in ({}, {"w": -1}, {"w": 999}, {"w": 1.5}, {"w": True}, {"w": 5, "text": "other"}, {"w": 5, "off": "x"}, {"t": -1}, {"t": "3"}, "w5", None):
        got, problem = t.parse_anchor(bad)
        assert got is None and problem, bad


def test_spans_are_where_a_shot_starts_to_where_the_next_one_starts():
    t = timeline()
    doc = {"shots": [{"start": {"t": 0.0}}, {"start": {"w": 10, "off": 0, "text": word(10)}}, {"start": {"t": 50}}], "end": {"t": 90}}
    assert t.spans(doc) == [(0.0, word_t(10)), (word_t(10), 50.0), (50.0, 90.0)]
    assert t.spans({"shots": [{"start": {"w": 9999}}], "end": {"t": 9}}) == [(None, 9.0)]


def test_rescale_rel_keeps_every_pose_at_the_same_absolute_time():
    keys = [{"at": {"rel": 0.0}, "cx": 1, "cy": 1, "zoom": 1}, {"at": {"rel": 0.5}, "cx": 1, "cy": 1, "zoom": 2}, {"at": {"w": 3}, "cx": 1, "cy": 1, "zoom": 3}]
    out = Timeline.rescale_rel(keys, 10.0, 20.0)
    assert [k["at"] for k in out] == [{"rel": 0.0}, {"rel": 0.25}, {"w": 3}] and keys[1]["at"] == {"rel": 0.5}


def test_crop_camera_is_continuous_at_the_cut_and_keeps_the_keys_inside():
    t = timeline()
    keys = [{"at": {"rel": 0.0}, "cx": 0, "cy": 0, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 0.5}, "cx": 100, "cy": 0, "zoom": 2.0, "ease": "in_quad"},
            {"at": {"rel": 1.0}, "cx": 200, "cy": 100, "zoom": 4.0, "ease": "linear"}]
    t0, t1, cut = 10.0, 20.0, 12.0                                                                   # the cut is at rel 0.2
    first = t.crop_camera(keys, t0, cut, t0, t1)
    second = t.crop_camera(keys, cut, t1, t0, t1)
    assert [k["at"] for k in first] == [{"rel": 0}, {"rel": 1}] and [k["at"] for k in second] == [{"rel": 0}, {"rel": 0.375}, {"rel": 1}]
    assert (first[-1]["cx"], first[-1]["cy"], first[-1]["zoom"]) == (second[0]["cx"], second[0]["cy"], second[0]["zoom"])
    assert first[-1]["cx"] == pytest.approx(40.0, abs=0.01) and first[-1]["zoom"] == pytest.approx(2 ** 0.4, abs=1e-4)   # 40 % of the way to key 2, zoom in log space
    assert first[0]["zoom"] == 1.0 and second[-1]["zoom"] == 4.0
    assert t.crop_camera([{"at": {"w": 999}, "cx": 1, "cy": 1, "zoom": 1}], 0, 1, 0, 2) == [{"at": {"w": 999}, "cx": 1, "cy": 1, "zoom": 1}]


def test_camera_lists_finds_every_key_list():
    keys = [{"at": {"rel": 0}, "zoom": 1}]
    assert [n for n, _ in camera_lists({"camera": keys, "camera_left": keys, "shadow": True, "xs": [1, 2], "empty": []})] == ["camera", "camera_left"]


def test_fit_overlay_shifts_in_or_shortens_like_the_page():
    t = timeline()
    ov = {"start": {"w": 10, "off": 0, "text": word(10)}, "dur": 4.0}                                # 3.9 s to 7.9 s
    span = t.overlay_span(ov, 0.0, 20.0)
    assert span == (word_t(10), word_t(10) + 4.0)
    t.fit_overlay(ov, 0.0, 6.0, span)                                                                # the shot now ends at 6 s: shortened
    assert ov["dur"] == pytest.approx(6.0 - word_t(10), abs=1e-6) and ov["start"]["w"] == 10
    late = {"start": {"t": 2.0}, "dur": 3.0}
    t.fit_overlay(late, 5.0, 9.0, t.overlay_span(late, 0.0, 9.0))                                    # the shot now starts at 5 s: shifted in
    assert late["start"] in ({"t": 5.0}, {"w": 13, "off": 0, "text": word(13)}) and late["dur"] <= 4.0 + 1e-9
