"""KEY-01, NUM-01 and DOC-01 (labels as a key to parts of a picture, a big number with a comparison, a lit line of a document): contract
docs/design/2026-11-18-explainer-components.md sections 2 to 5. Pictures are measured, not looked at: every test draws frames of a flat grey picture
(so the base is exactly 120 everywhere and anything else is the overlay) and measures ink, brightness and positions in pixels."""
from __future__ import annotations

import copy
import json
import math
import socket
from pathlib import Path

import cv2
import numpy as np
import pytest

from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine.api import open_project
from bti.engine.techniques import explain_over as X
from conftest import REPO

GREY = 120
PIC_W, PIC_H = 3000, 2200
W, H = 1920, 1080
REGIONS = {
    "CENTRE": {"x": 1500, "y": 1100, "rx": 150, "ry": 100, "label": "Centre"},
    "A": {"x": 1100, "y": 800, "rx": 80, "ry": 60, "label": "Alpha"},
    "B": {"x": 1500, "y": 1100, "rx": 80, "ry": 60, "label": "Beta"},
    "WIDE": {"x": 1500, "y": 1100, "rx": 300, "ry": 80, "label": "Wide line"},
    "LOW": {"x": 1500, "y": 1600, "rx": 300, "ry": 80, "label": "Low line"},
    "UL": {"x": 1000, "y": 700, "rx": 200, "ry": 60, "label": "Upper left"},
    "LR": {"x": 2000, "y": 1500, "rx": 200, "ry": 60, "label": "Lower right"},
    "POINT": {"x": 1500, "y": 1100, "label": "A point"},
}
CENTRE_CAM = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}]


def spec(tid):
    return R.load_bundle("gae").spec(tid)


def param(tid, name):
    return next(p for p in spec(tid)["params"] if p["name"] == name)


def words(n=80, step=0.5):
    return [{"w": "w%d" % i, "s": round(i * step, 3), "e": round(i * step + 0.4, 3)} for i in range(n)]


def overlay(tid, params, start=0.0, dur=8.0, oid="o1"):
    return {"id": oid, "technique": tid, "intent": "point_at", "start": {"t": start}, "dur": dur, "params": params, "locked": False, "source": "agent", "note": ""}


def make_picture(kind):
    """The test picture: flat grey, or with its right (or bottom) half bright (220) and the other half dark (30), the split through the middle (1500, 1100)."""
    img = np.full((PIC_H, PIC_W, 3), GREY, np.uint8)
    if kind == "right":
        img[:, :PIC_W // 2], img[:, PIC_W // 2:] = 30, 220
    elif kind == "bottom":
        img[:PIC_H // 2], img[PIC_H // 2:] = 30, 220
    return img


def make_project(tmp_path, tid, params, camera=None, dur=8.0, shot_dur=10.0, name="lab", base="CAM-05", start=0.0, regions=None, picture="flat"):
    d = Path(tmp_path) / name
    (d / "media").mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / "media" / "pic.png"), make_picture(picture))
    asset = {"file": "media/pic.png", "kind": "image", "title": "Flat", "artist": "Nobody", "year": "1999", "width": PIC_W, "height": PIC_H,
             "credit": {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}, "regions": regions or REGIONS}
    shot = {"id": "s1", "start": {"t": 0.0}, "technique": base, "intent": "point_at", "slots": {"image": {"asset": "A"}}, "params": {"camera": camera or CENTRE_CAM},
            "transition_in": None, "overlays": [overlay(tid, params, start, dur)], "locked": False, "source": "agent", "note": ""}
    if base in ("X-CARD-01", "MAP-01"):
        shot["slots"], shot["params"] = {}, {}
    elif base == "STATE-01":                                  # compbase's two-state base: both slots hold the one picture, one camera over the whole frame
        shot["slots"], shot["params"] = {"a": {"asset": "A"}, "b": {"asset": "A"}}, {"camera": camera or CENTRE_CAM}
    sb = {"schema": "bti.storyboard/1", "project": name, "title": "t", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json", "audio": None,
          "assets": {"A": asset}, "shots": [shot], "end": {"t": shot_dur, "fade_s": 0}, "approvals": {"storyboard": None}}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    (d / "timing.json").write_text(json.dumps({"duration": shot_dur + 5, "words": words(), "beats": [], "chapters": []}), encoding="utf-8")
    return open_project(d)


def errors(p, sb=None):
    return [i for i in p.validate(sb) if i["level"] == "error"]


def frame(p, t, width=1920):
    return p.frame_at(t, width)


def gray(img):
    return img.astype(np.float32).mean(2)


def renderer(p):
    return p._scene().shots[0].overlays[0][1]


def view_at(p, t):
    return p._scene().shots[0].base.view(t)


def lab(text, ref, side="auto", at=1.0, style="italic"):
    return {"text": text, "ref": ref, "side": side, "at": at, "style": style}


def ink_boxes(img, dim, thr=30):
    """Bounding box (x0, y0, x1, y1) of the bright text pixels on a dimmed flat picture, None when there are none."""
    m = gray(img) > GREY * dim + thr
    ys, xs = np.where(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


# ================================================================================ the registry entries
IDS = ["KEY-01", "NUM-01", "DOC-01"]


def test_the_three_entries_are_the_last_of_the_registry_in_this_order_after_the_map():
    ids = [t["id"] for t in R.load_bundle("gae").techniques]
    assert ids[-4:] == ["MAP-01", "KEY-01", "NUM-01", "DOC-01"]
    assert len(ids) == 86


@pytest.mark.parametrize("tid", IDS)
def test_the_registry_entry_is_complete(tid):
    sp = spec(tid)
    assert sp["kind"] == "overlay" and sp["engine"]["available"] and sp["label_vi"] and len(sp["description"]) > 80 and len(sp["usage_rule"]) > 200
    assert sp["engine"]["impl"].startswith("bti.engine.techniques.explain_over.") and sp["engine"]["reason"] is None
    assert sp["timing"]["min_s"] and sp["timing"]["min_s"] < sp["timing"]["default_s"] < sp["timing"]["max_s"] and sp["timing"]["anchor"] == "word"
    assert all(R.check_problem(x, x["default"]) is None for x in sp["params"]), "every default passes its own check"
    for pd in sp["params"]:
        if pd["type"] == "number":
            assert pd["min"] is not None and pd["max"] is not None and pd["min"] <= pd["default"] <= pd["max"], pd["name"]
        if pd["type"] == "items":
            assert pd["min_items"] is not None and pd["max_items"] is not None and pd["default"]
            for fd in pd["fields"]:
                assert (fd["min"] is None) == (fd["max"] is None), (pd["name"], fd["name"])
                if fd["type"] in ("string",) and fd["pattern"]:
                    assert fd["pattern_hint"] and any(c in fd["pattern_hint"] for c in "ơưăâêôđ"), "the hint of a text field is Vietnamese"
        if pd["type"] in ("string", "text"):
            assert pd["pattern"] and pd["pattern_hint"]
    assert (REPO / "style/gae" / sp["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / sp["preview"]["thumb"]).stat().st_size > 1000
    assert sp["evidence"]


def test_each_usage_rule_gives_the_fields_in_one_line_and_says_which_sentence_it_serves():
    key, num, doc = (spec(t)["usage_rule"] for t in IDS)
    for word in ("`labels`", "`text`", "`ref`", "`side`", "`at`", "`style`", "NAMES", "ALWAYS", "at most five labels on screen at a time", "two shots"):
        assert word in key, word
    assert param("KEY-01", "leader")["values"] == ["none", "hairline", "auto"] and param("KEY-01", "leader")["default"] == "auto"
    for word in ("`rows`", "`label`", "`value`", "`units`", "`count`", "`caption`", "`source`", "STATES", "ALWAYS"):
        assert word in num, word
    for word in ("`lit`", "`ref`", "`box`", "`hold_s`", "`reading`", "`original`", "`reading_at`", "READS", "ALWAYS"):
        assert word in doc, word
    assert [x["name"] for x in spec("KEY-01")["slots"]] == ["image"] and spec("NUM-01")["slots"] == [] and [x["name"] for x in spec("DOC-01")["slots"]] == ["image"]


def test_the_default_data_is_the_mock_up_example_on_the_arnolfini_regions():
    d = {x["name"]: x["default"] for x in spec("KEY-01")["params"]}
    assert [(lb["text"], lb["ref"], lb["side"], lb["at"]) for lb in d["labels"]] == [("One candle, lit", "LIT", "w", 0.7), ("Latin inscription", "INSCR", "n", 1.6), ("Convex mirror", "MIRROR", "s", 2.5),
                                                                                    ("Amber beads", "AMBER", "w", 3.4), ("A brush", "BRUSH", "e", 4.3)]
    assert d["cap_pct"] == 2.4 and d["dim_picture_to"] == 0.78 and d["leader"] == "auto" and d["shadow"] is True
    d = {x["name"]: x["default"] for x in spec("NUM-01")["params"]}
    assert [(r["value"], r["count"], r["at"]) for r in d["rows"]] == [("600", 12, 1.0), ("2,000", 40, 2.9)] and d["cap_pct"] == 8 and d["dim_picture_to"] == 0.38 and d["align"] == "left"
    d = {x["name"]: x["default"] for x in spec("DOC-01")["params"]}
    assert d["lit"][0]["ref"] == "INSCR" and d["dim_to"] == 0.34 and d["reading"] == "Jan van Eyck was here. 1434" and d["reading_at"] == 2.4 and d["ramp_s"] == 0.7


# ================================================================================ validation of the lists
@pytest.mark.parametrize("value,code,words_", [
    ("x", "param_not_items", ["list"]),
    ([], "param_item_count", ["at least 1"]),
    ([lab("a", "A")] * 13, "param_item_count", ["at most 12"]),
    ([lab("ok", "A"), {"text": "", "ref": "A"}], "item_field_bad_form", ["item 2", "'text'"]),
    ([{"ref": "A"}], "item_field_missing", ["item 1", "'text'"]),
    ([{"text": "Beta"}], "item_field_missing", ["item 1 (Beta)", "'ref'"]),
    ([lab("x" * 61, "A")], "item_field_bad_form", ["'text'"]),
    ([lab("Alpha", "A", side="up")], "item_field_not_in_values", ["item 1 (Alpha)", "'side'", "auto, n, ne"]),
    ([lab("Alpha", "A", style="bold")], "item_field_not_in_values", ["'style'", "italic, regular, caps"]),
    ([lab("Alpha", "A", at=-1)], "item_field_below_min", ["'at'"]),
    ([lab("Alpha", "A", at=601)], "item_field_above_max", ["'at'"]),
    ([lab("Alpha", "A", at={"w": -1})], "item_field_bad_at", ["'at'"]),
    ([lab("Alpha", 5)], "item_field_bad_type", ["'ref'"]),
    ([lab("Alpha", "A"), lab("Beta", "B", at="soon")], "item_field_bad_at", ["item 2 (Beta)", "'at'"]),
    ([{"text": "Alpha", "ref": "A", "colour": "red"}], "item_unknown_field", ["'colour'"]),
])
def test_key_labels_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(param("KEY-01", "labels"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


@pytest.mark.parametrize("value,code,words_", [
    ([], "param_item_count", ["at least 1"]),
    ([{"value": "1", "units": ""}] * 5, "param_item_count", ["at most 4"]),
    ([{"label": "x"}], "item_field_missing", ["item 1 (x)", "'value'"]),
    ([{"value": ""}], "item_field_bad_form", ["'value'"]),
    ([{"value": "1" * 17}], "item_field_bad_form", ["'value'"]),
    ([{"value": "9", "units": "u" * 25}], "item_field_bad_form", ["'units'"]),
    ([{"value": "9", "label": "l" * 61}], "item_field_bad_form", ["'label'"]),
    ([{"value": "9", "count": -1}], "item_field_below_min", ["'count'"]),
    ([{"value": "9"}, {"value": "8", "label": "Eight", "count": 61}], "item_field_above_max", ["item 2 (Eight)", "'count'"]),
    ([{"value": "9", "count": "many"}], "item_field_bad_type", ["'count'"]),
    ([{"value": "9", "at": {"rel": 3}}], "item_field_bad_at", ["'at'"]),
])
def test_num_rows_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(param("NUM-01", "rows"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


@pytest.mark.parametrize("value,code,words_", [
    ([], "param_item_count", ["at least 1"]),
    ([{"ref": "A"}] * 7, "param_item_count", ["at most 6"]),
    ([{"box": "1, 2, 3"}], "item_field_bad_form", ["'box'", "bốn số"]),
    ([{"box": "a, b, c, d"}], "item_field_bad_form", ["'box'"]),
    ([{"ref": "A", "hold_s": -1}], "item_field_below_min", ["'hold_s'"]),
    ([{"ref": "A", "hold_s": 61}], "item_field_above_max", ["'hold_s'"]),
    ([{"ref": "A", "at": -0.5}], "item_field_below_min", ["'at'"]),
    ([{"ref": "A"}, {"ref": 7}], "item_field_bad_type", ["item 2", "'ref'"]),
])
def test_doc_lit_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(param("DOC-01", "lit"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


def test_items_that_are_fine_pass_and_fill_their_defaults():
    assert R.check_problem(param("KEY-01", "labels"), [{"text": "Alpha", "ref": "A"}, {"text": "B", "ref": [10, 20], "side": "nw", "at": {"t": 2.5}, "style": "caps"},
                                                       {"text": "C", "ref": "B", "at": {"w": 4, "off": -0.2, "text": "x"}}]) is None
    assert R.check_problem(param("NUM-01", "rows"), [{"value": "$450.3M"}, {"value": "2,000", "units": "pelts", "count": 40, "at": 2.9, "label": "L"}]) is None
    assert R.check_problem(param("DOC-01", "lit"), [{"ref": "A"}, {"box": "1750, 1240, 2690, 1540"}, {"ref": "A", "box": "1,2,3,4", "at": {"rel": 0.5}, "hold_s": 2}]) is None
    key = R.merged_params(spec("KEY-01"), {"labels": [{"text": "a\nb", "ref": "A"}]})
    assert key["labels"] == [{"text": "a b", "ref": "A", "side": "auto", "at": 1.0, "style": "italic"}]
    assert R.merged_params(spec("NUM-01"), {"rows": [{"value": "5"}]})["rows"] == [{"label": "", "value": "5", "units": "", "count": 0, "at": 1.0}]
    assert R.merged_params(spec("DOC-01"), {"lit": [{"ref": "A"}]})["lit"] == [{"ref": "A", "box": "", "at": 1.0, "hold_s": 0}]
    assert R.items_at_fields(spec("KEY-01")) == [("labels", ["at"])] and R.items_at_fields(spec("NUM-01")) == [("rows", ["at"])] and R.items_at_fields(spec("DOC-01")) == [("lit", ["at"])]


def test_the_rules_between_params_of_the_lit_lines(tmp_path):
    p = make_project(tmp_path, "DOC-01", {"lit": [{"ref": "WIDE"}]})
    sb = p.storyboard()

    def codes(lit, **params):
        d = copy.deepcopy(sb)
        d["shots"][0]["overlays"][0]["params"] = dict({"lit": lit}, **params)
        return [(i["code"], i["path"]) for i in errors(p, d)]
    path = "shots[0].overlays[0].params.lit"
    assert codes([{"ref": "WIDE"}]) == []
    assert codes([{"ref": "WIDE"}, {}]) == [("doc_lit_no_target", path)]
    assert codes([{"box": ""}]) == [("doc_lit_no_target", path)]
    assert codes([{"box": "100, 100, 50, 300"}]) == [("doc_bad_box", path)]
    assert codes([{"box": "100, 100, 300, 100"}]) == [("doc_bad_box", path)]
    assert codes([{"box": "100, 100, 400, 300"}]) == []
    assert codes([{"ref": "NOWHERE"}]) == [("region_undefined", "shots[0].overlays[0].params.lit[0].ref")]
    assert codes([{"ref": [100, 200]}]) == []
    bad = errors(p, {**copy.deepcopy(sb), "shots": [{**sb["shots"][0], "overlays": [overlay("DOC-01", {"lit": [{"ref": "WIDE"}, {"box": "5, 5, 1, 1"}]})]}]})
    assert "item 2" in bad[0]["message"] or bad[0]["args"]["index"] == 1


def test_an_unknown_region_of_a_label_is_an_error_naming_it(tmp_path):
    p = make_project(tmp_path, "KEY-01", {"labels": [lab("Alpha", "A"), lab("Ghost", "GHOST")]})
    e = errors(p)
    assert [(i["code"], i["path"]) for i in e] == [("region_undefined", "shots[0].overlays[0].params.labels[1].ref")]
    assert e[0]["args"]["region"] == "GHOST"
    assert errors(make_project(tmp_path, "KEY-01", {"labels": [lab("Alpha", "A"), lab("Point", [1200, 900])]}, name="ok")) == []


def test_a_word_anchor_in_an_at_lands_on_the_word(tmp_path):
    """`at` of a label may be a word anchor: the engine resolves it (word 6 starts at 3.0 s in the lab timing; the overlay starts at 1.0 s, so the label is due 2.0 s in)."""
    word = {"w": 6, "off": 0.0, "text": "w6"}
    p = make_project(tmp_path, "KEY-01", {"labels": [lab("Alpha", "A", "e", word)]}, start=1.0, dur=8.0)
    assert errors(p) == []
    assert p.resolve()["shots"][0]["overlays"][0]["params"]["labels"][0]["at"]["_t"] == pytest.approx(3.0)
    assert renderer(p).labels[0]["at"] == pytest.approx(2.0)
    zone = (slice(150, 330), slice(500, 1100))
    assert (gray(frame(p, 2.9))[zone] > GREY * 0.78 + 30).sum() == 0
    assert (gray(frame(p, 3.6))[zone] > GREY * 0.78 + 30).sum() > 150
    stale = copy.deepcopy(p.storyboard())
    stale["shots"][0]["overlays"][0]["params"]["labels"][0]["at"] = {"w": 6, "off": 0.0, "text": "zzz"}
    assert [i["code"] for i in errors(p, stale)] == ["item_anchor_stale"]
    gone = copy.deepcopy(p.storyboard())
    gone["shots"][0]["overlays"][0]["params"]["labels"][0]["at"] = {"w": 9999, "off": 0.0, "text": "x"}
    assert [i["code"] for i in errors(p, gone)] == ["item_anchor_invalid"]
    rel = copy.deepcopy(p.storyboard())
    rel["shots"][0]["overlays"][0]["params"]["labels"][0]["at"] = {"rel": 0.5}
    assert errors(p, rel) == [] and p.resolve(rel)["shots"][0]["overlays"][0]["params"]["labels"][0]["at"]["_t"] == pytest.approx(1.0 + 0.5 * 8.0)


def test_word_anchors_in_the_rows_and_the_lit_lines_land_on_their_words(tmp_path):
    """Word 6 starts at 3.0 s in the lab timing; the overlays start at 1.0 s, so an item on that word is due 2.0 s in."""
    word = {"w": 6, "off": 0.0, "text": "w6"}
    n = make_project(tmp_path, "NUM-01", {"rows": [row("Row", "600", "pelts", 0, word)], "caption": "", "source": ""}, start=1.0, dur=8.0, name="wn")
    assert errors(n) == [] and n.resolve()["shots"][0]["overlays"][0]["params"]["rows"][0]["at"]["_t"] == pytest.approx(3.0)
    assert renderer(n).rows[0]["at"] == pytest.approx(2.0)
    lx, lb = renderer(n).lay[0]["label_pos"]
    zone = (slice(int(lb) - 30, int(lb) + 12), slice(int(lx) - 4, int(lx) + 300))
    count = lambda p, t: int((gray(frame(p, t))[zone] > GREY * 0.38 + 30).sum())
    assert count(n, 2.9) == 0 and count(n, 3.6) > 50
    d = make_project(tmp_path, "DOC-01", {"lit": [{"ref": "WIDE", "at": word}], "reading": "", "original": ""}, start=1.0, dur=8.0, name="wd")
    assert errors(d) == [] and d.resolve()["shots"][0]["overlays"][0]["params"]["lit"][0]["at"]["_t"] == pytest.approx(3.0)
    assert renderer(d).wins[0]["at"] == pytest.approx(2.0)
    corner = lambda t: float(gray(frame(d, t))[20, 20])
    assert corner(2.9) == GREY and corner(3.9) < GREY * 0.7
    for p, tid, field in ((n, "NUM-01", "rows"), (d, "DOC-01", "lit")):
        stale = copy.deepcopy(p.storyboard())
        stale["shots"][0]["overlays"][0]["params"][field][0]["at"] = {"w": 6, "off": 0.0, "text": "zzz"}
        assert [i["code"] for i in errors(p, stale)] == ["item_anchor_stale"], tid


# ================================================================================ which base shots each overlay is valid on
def test_the_camera_overlays_are_valid_on_the_bases_that_show_a_picture_through_a_camera(tmp_path):
    for base in ("CAM-01", "CAM-02", "CAM-05", "STATIC-01", "X-LAY-01"):
        for tid, params in (("KEY-01", {"labels": [lab("Alpha", "A")]}), ("DOC-01", {"lit": [{"ref": "A"}]})):
            p = make_project(tmp_path, tid, params, base=base, name="b_%s_%s" % (tid[:3], base))
            bad = [i for i in errors(p) if i["code"] == "overlay_needs_camera"]
            assert bad == [], (tid, base)


@pytest.mark.parametrize("base", ["X-CARD-01", "MAP-01", "DIA-01"])
@pytest.mark.parametrize("tid,params", [("KEY-01", {"labels": [lab("Alpha", "A")]}), ("DOC-01", {"lit": [{"ref": "A"}]})])
def test_the_camera_overlays_are_refused_on_a_base_without_a_camera(tmp_path, base, tid, params):
    p = make_project(tmp_path, tid, params, base=base, name="c_%s" % base)
    sb = p.storyboard()
    sb["shots"][0]["technique"] = base
    sb["shots"][0]["slots"] = {} if base in ("X-CARD-01", "MAP-01") else sb["shots"][0]["slots"]
    sb["shots"][0]["params"] = {}
    bad = [i for i in errors(p, sb) if i["code"] == "overlay_needs_camera"]
    assert len(bad) == 1 and bad[0]["args"] == {"technique": tid, "base": base} and bad[0]["path"] == "shots[0].overlays[0].technique", (bad, base)


def test_the_number_is_valid_on_every_shot_with_or_without_a_picture(tmp_path):
    for base in ("CAM-05", "STATIC-01", "X-CARD-01", "MAP-01"):
        p = make_project(tmp_path, "NUM-01", {}, base=base, name="n_%s" % base)
        sb = p.storyboard()
        sb["shots"][0]["technique"] = base
        if base in ("X-CARD-01", "MAP-01"):
            sb["shots"][0]["slots"], sb["shots"][0]["params"] = {}, {}
        assert [i for i in errors(p, sb) if i["code"] == "overlay_needs_camera"] == [], base
        assert not [i for i in p.validate(sb) if i["code"] == "incomplete" and "overlays" in i["path"]], base


def test_a_picture_overlay_on_a_shot_that_has_no_image_is_incomplete_and_skipped(tmp_path):
    p = make_project(tmp_path, "KEY-01", {"labels": [lab("Alpha", "A")]}, base="X-CARD-01")
    sb = p.storyboard()
    sb["shots"][0]["technique"], sb["shots"][0]["slots"], sb["shots"][0]["params"] = "X-CARD-01", {}, {}
    assert any(i["code"] == "incomplete" and i["path"].endswith("overlays[0].slots") for i in p.validate(sb))


# ================================================================================ KEY-01
def key_project(tmp_path, labels, camera=None, name="key", dur=8.0, **params):
    return make_project(tmp_path, "KEY-01", dict({"labels": labels}, **params), camera=camera, dur=dur, name=name)


def test_each_label_appears_at_its_own_time_and_not_before(tmp_path):
    p = key_project(tmp_path, [lab("Alpha one", "A", "e", 1.0), lab("Beta two", "B", "e", 3.0)])
    dim = 0.78
    zone_a, zone_b = (slice(200, 290), slice(640, 1000)), (slice(500, 580), slice(1040, 1400))
    count = lambda t, z: int((gray(frame(p, t))[z] > GREY * dim + 30).sum())
    assert np.array_equal(frame(p, 0.2), np.full((H, W, 3), GREY, np.uint8)), "nothing is drawn before the dim starts (0.6 s)"
    assert count(0.95, zone_a) == 0 and count(0.95, zone_b) == 0, "no label before its time"
    assert count(1.6, zone_a) > 120 and count(1.6, zone_b) == 0
    assert count(2.9, zone_b) == 0
    assert count(3.6, zone_b) > 120 and count(3.6, zone_a) > 120
    mid_a = count(1.12, zone_a)
    assert 0 < mid_a < count(1.6, zone_a), "a label fades in"
    # the exact time of the first and the second frame of the fade: invisible at its time, there at +fade
    assert count(1.0, zone_a) == 0 and count(1.0 + 0.3, zone_a) > 100


def test_a_label_sits_on_the_stated_side_outside_the_ellipse_of_its_region(tmp_path):
    """Camera on the region (zoom 1): the ellipse is centred at (960, 540) with radii 150 and 100 px; every ink pixel of the label is outside it, on the stated side, and
    beside labels (e, w) are centred on the region's height, above and below ones on its middle."""
    cx, cy, rx, ry = 960, 540, 150, 100
    for side in ("n", "ne", "e", "se", "s", "sw", "w", "nw"):
        p = key_project(tmp_path, [lab("Convex mirror", "CENTRE", side, 0.5)], name="side_%s" % side)
        img = frame(p, 4.0)
        m = gray(img) > GREY * 0.78 + 30
        ys, xs = np.where(m)
        assert len(xs) > 150, side
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        inside = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 < 1.0
        assert not inside.any(), "%s: ink inside the ellipse" % side
        if "e" in side:
            assert x0 >= cx + rx * (0.7 if len(side) == 2 else 1.0) - 1, side
        if "w" in side:
            assert x1 <= cx - rx * (0.7 if len(side) == 2 else 1.0) + 1, side
        if "n" in side:
            assert y1 <= cy - ry * (0.7 if len(side) == 2 else 1.0) + 1, side
        if "s" in side:
            assert y0 >= cy + ry * (0.7 if len(side) == 2 else 1.0) - 1, side
        if side in ("e", "w"):
            assert abs((y0 + y1) / 2 - cy) < 16, side
        if side in ("n", "s"):
            assert abs((x0 + x1) / 2 - cx) < 6, side            # the ink of italic letters leans: its box is not exactly centred


def test_a_bare_point_gets_a_small_radius_and_a_region_without_radii_is_a_point(tmp_path):
    for ref in ([1500, 1100], "POINT"):
        p = key_project(tmp_path, [lab("Point label", ref, "e", 0.5)], name="pt")
        x0, y0, x1, y1 = ink_boxes(frame(p, 4.0), 0.78)
        assert 960 + X.POINT_R * H - 3 <= x0 <= 960 + X.POINT_R * H + X.LABEL_GAP * H + 4, (ref, x0)


CROWD = {"R%d" % i: {"x": x, "y": y, "rx": 70, "ry": 55, "label": "r"} for i, (x, y) in enumerate([(1500, 1100), (1580, 1130), (1420, 1150), (1500, 1220), (1500, 980), (1600, 1030), (1390, 1040), (1640, 1180)])}
CROWD_TEXTS = ["Convex mirror", "Latin inscription", "One candle, lit", "Amber beads", "A brush", "Joined hands", "Carved lion", "The little dog"]


def test_eight_labels_on_a_crowded_picture_never_touch_and_never_leave_the_frame(tmp_path):
    camera = [{"at": {"rel": 0.0}, "cx": 1350, "cy": 1000, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1750, "cy": 1200, "zoom": 1.5, "ease": "linear"}]
    labels = [lab(CROWD_TEXTS[i], "R%d" % i, "auto", 0.5 + 0.2 * i) for i in range(8)]
    p = make_project(tmp_path, "KEY-01", {"labels": labels, "leader": "none"}, camera=camera, regions=dict(REGIONS, **CROWD), name="crowd")      # no leader: the pixel check below counts every bright pixel
    assert errors(p) == []
    r = renderer(p)
    m = X.EDGE_MARGIN * H
    for tau in (2.5, 3.5, 4.5, 5.5, 6.5, 7.0):
        view = view_at(p, tau)
        pos = r.layout(view, tau)
        assert sorted(pos) == list(range(8)), (tau, sorted(pos))
        boxes = []
        for i, (left, base, vis) in sorted(pos.items()):
            a = r.arts[i]
            box = (left, base - a.cap, left + a.width, base + a.below)
            assert box[0] >= m - 0.5 and box[2] <= W - m + 0.5 and box[1] >= m - 0.5 and box[3] <= H - m + 0.5, (tau, i, box)
            boxes.append(box)
        for i in range(8):
            for j in range(i + 1, 8):
                assert not X._hit(boxes[i], boxes[j], 0.0), (tau, i, j, boxes[i], boxes[j])
        # the pixels agree with the boxes: every box holds ink and nothing else is drawn
        img = frame(p, tau)
        mask = gray(img) > GREY * 0.78 + 30
        covered = np.zeros_like(mask)
        for (x0, y0, x1, y1) in boxes:
            sl = (slice(max(int(y0) - 8, 0), int(y1) + 9), slice(max(int(x0) - 8, 0), int(x1) + 9))      # italic letters lean over the advance box by a few pixels
            assert mask[sl].sum() > 40, (tau, (x0, y0, x1, y1))
            covered[sl] = True
        assert not (mask & ~covered).any(), "ink outside every label box"


def test_the_labels_follow_the_camera_and_keep_their_size(tmp_path):
    """Two camera positions of one shot (a linear move of 400 source px right and 200 down over the 10 s of the shot, zoom 1): the label moves with the picture and does not change size."""
    cam = [{"at": {"rel": 0.0}, "cx": 1300, "cy": 1000, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1700, "cy": 1200, "zoom": 1.0, "ease": "linear"}]
    p = key_project(tmp_path, [lab("Convex mirror", "B", "e", 0.5)], camera=cam)
    b1, b2 = ink_boxes(frame(p, 2.0), 0.78), ink_boxes(frame(p, 6.0), 0.78)
    v1, v2 = view_at(p, 2.0), view_at(p, 6.0)                       # the camera keys are written over the shot (10 s), the overlay lasts 8 s
    assert (v2.cx - v1.cx, v2.cy - v1.cy) == pytest.approx((160, 80)) and v1.z == v2.z == 1.0
    assert (b2[0] - b1[0], b2[1] - b1[1]) in [(-160 + dx, -80 + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)], (b1, b2)
    assert abs((b2[2] - b2[0]) - (b1[2] - b1[0])) <= 1 and abs((b2[3] - b2[1]) - (b1[3] - b1[1])) <= 1, "the label keeps its size"


def test_the_label_keeps_its_size_when_the_camera_zooms(tmp_path):
    cam = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1500, "cy": 1100, "zoom": 1.5, "ease": "linear"}]
    p = key_project(tmp_path, [lab("Convex mirror", "CENTRE", "e", 0.5)], camera=cam)
    z = lambda t: view_at(p, t).z
    b1, b2 = ink_boxes(frame(p, 1.0), 0.78), ink_boxes(frame(p, 7.0), 0.78)
    assert abs((b2[2] - b2[0]) - (b1[2] - b1[0])) <= 1 and abs((b2[3] - b2[1]) - (b1[3] - b1[1])) <= 1
    assert (b2[0] - b1[0]) == pytest.approx(150 * (z(7.0) - z(1.0)), abs=2.5), "only the position follows: the label stays beside the growing ellipse"


def test_text_moves_smoothly_between_frames_at_sub_pixel_positions(tmp_path):
    """A label on a slowly moving camera moves by quarter pixels: the centroid of its ink moves by (nearly) the same amount every frame, not in whole-pixel jumps."""
    cam = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1580, "cy": 1100, "zoom": 1.0, "ease": "linear"}]
    p = key_project(tmp_path, [lab("Convex mirror", "CENTRE", "e", 0.0)], camera=cam, dur=8.0)
    xs = []
    for k in range(12):
        g = gray(frame(p, 3.0 + k / 30.0)) - GREY * 0.78
        ink = np.clip(g, 0, None)[:, 700:1400]                       # the weight of the ink, no threshold: the centroid follows the true position of the text
        xs.append(float((ink.sum(0) * (np.arange(700, 1400) + 0.5)).sum() / ink.sum()))
    steps = np.diff(xs)
    want = -80.0 / 300.0                                              # 80 px over the 10 s of the shot at 30 frames a second: 0.267 px a frame
    assert (steps < -0.03).all() and (steps > -0.8).all(), steps        # in whole pixels the steps would be 0 and 1
    assert xs[-1] - xs[0] == pytest.approx(11 * want, abs=0.35), "the quarter pixels add up to the true motion"


def test_the_picture_dims_from_before_the_first_label_until_the_end(tmp_path):
    p = key_project(tmp_path, [lab("Alpha", "A", "e", 2.0)], dur=8.0)
    far = lambda t: int(frame(p, t)[1060, 1900, 0])
    assert far(1.5) == GREY, "the dim starts 0.4 s before the first label (1.6 s)"
    assert far(1.9) == pytest.approx(GREY * (1 - 0.22 * (0.3 / 0.6)), abs=2)
    assert far(2.5) == pytest.approx(GREY * 0.78, abs=1)
    assert far(5.0) == pytest.approx(GREY * 0.78, abs=1)
    assert far(7.75) == pytest.approx(GREY - (GREY - GREY * 0.78) * 0.5, abs=2.5), "it leaves over the last 0.5 s, ending with the overlay"
    assert far(8.0) == GREY and far(9.0) == GREY, "nothing after the end"
    q = key_project(tmp_path, [lab("Alpha", "A", "e", 2.0)], name="dim9", dim_picture_to=1.0)
    assert int(frame(q, 5.0)[1060, 1900, 0]) == GREY, "dim_picture_to 1 leaves the picture as it is"
    q = key_project(tmp_path, [lab("Alpha", "A", "e", 2.0)], name="dim6", dim_picture_to=0.6)
    assert int(frame(q, 5.0)[1060, 1900, 0]) == pytest.approx(GREY * 0.6, abs=1)


def test_a_label_leaves_by_a_fade_that_ends_with_the_overlay(tmp_path):
    p = key_project(tmp_path, [lab("Alpha one", "A", "e", 1.0)], dur=6.0, leave_s=1.0)
    zone = (slice(200, 290), slice(640, 1000))
    n = lambda t: int((gray(frame(p, t))[zone] > 100 + 20).sum())
    assert n(4.9) > 100 and n(5.5) > 0 and n(5.5) < n(4.9) * 1.01 + 200
    assert n(5.99) < 5 and n(6.0) == 0 and n(7.0) == 0


def test_cap_height_and_style_of_the_text(tmp_path):
    """Capital H of 2.4 percent of the frame height (25.9 px); small capitals are 80 percent of it; the hairline leader adds pixels between the label and the region."""
    h = lambda style, **k: ink_boxes(frame(key_project(tmp_path, [lab("HHHH", "A", "e", 0.5, style)], name="st_" + style, **k), 4.0), 0.78)
    for style, share in (("italic", 1.0), ("regular", 1.0), ("caps", 0.8)):
        x0, y0, x1, y1 = h(style)
        assert (y1 - y0) == pytest.approx(0.024 * H * share, abs=2.2), (style, y1 - y0)
    x0, y0, x1, y1 = ink_boxes(frame(key_project(tmp_path, [lab("HHHH", "A", "e", 0.5)], name="cap3", cap_pct=3.0), 4.0), 0.78)
    assert (y1 - y0) == pytest.approx(0.03 * H, abs=2.2)


def test_the_hairline_leader_and_the_shadow_switch(tmp_path):
    none = frame(key_project(tmp_path, [lab("Alpha one", "A", "e", 0.5)], name="l0", leader="none"), 4.0)
    hair = frame(key_project(tmp_path, [lab("Alpha one", "A", "e", 0.5)], name="l1", leader="hairline"), 4.0)
    diff = (np.abs(hair.astype(int) - none.astype(int)).max(2) > 8)
    ys, xs = np.where(diff)
    assert len(xs) > 10, "a hairline is drawn"
    # A sits at (560, 240) on screen (camera 1500, 1100): its label is to the east, the line lies between the ellipse's edge and the label
    assert xs.min() >= 560 + 80 - 4 and xs.max() <= 560 + 80 + 40
    noshadow = frame(key_project(tmp_path, [lab("Alpha one", "A", "e", 0.5)], name="sh0", shadow=False), 4.0)
    shadow = frame(key_project(tmp_path, [lab("Alpha one", "A", "e", 0.5)], name="sh1"), 4.0)
    dark = lambda img: int((gray(img)[150:330, 600:1100] < GREY * 0.78 - 4).sum())
    assert dark(noshadow) == 0 and dark(shadow) > 100


def test_among_sides_that_are_equally_near_a_label_takes_the_one_with_the_darker_ground(tmp_path):
    """The default order of the sides is e first; with the right half of the picture bright and the left dark the label goes west (and north when the bottom is bright)."""
    labels = [lab("Convex mirror", "CENTRE", "auto", 0.5)]
    flat = make_project(tmp_path, "KEY-01", {"labels": labels, "leader": "none"}, name="gflat")
    assert renderer(flat).plan(view_at(flat, 3.0)) == {0: "e"}, "on a flat picture the order decides"
    right = make_project(tmp_path, "KEY-01", {"labels": labels, "leader": "none"}, name="gright", picture="right")
    assert renderer(right).plan(view_at(right, 3.0)) == {0: "w"}
    img = frame(right, 4.0)
    ys, xs = np.where(gray(img) > 200)
    assert len(xs) > 100 and xs.max() < 960 - 150, "and it is drawn on the dark side, west of the region"
    bottom = make_project(tmp_path, "KEY-01", {"labels": labels, "leader": "none"}, name="gbottom", picture="bottom")
    assert renderer(bottom).plan(view_at(bottom, 3.0)) == {0: "n"}
    fixed = make_project(tmp_path, "KEY-01", {"labels": [lab("Convex mirror", "CENTRE", "e", 0.5)], "leader": "none"}, name="gfixed", picture="right")
    assert renderer(fixed).plan(view_at(fixed, 3.0)) == {0: "e"}, "a side the author fixed is kept"
    lvl = X.ground_level(view_at(right, 3.0), (100, 100, 400, 140)), X.ground_level(view_at(right, 3.0), (1400, 100, 1700, 140)), X.ground_level(view_at(right, 3.0), (-900, 100, -600, 140))
    assert lvl[0] == pytest.approx(30 / 255, abs=0.01) and lvl[1] == pytest.approx(220 / 255, abs=0.01) and lvl[2] == 0.0, "dark, bright, and off the picture (the backdrop)"


def stacked(tmp_path, leader, name):
    """Three labels on one detail, all on its east side: the first sits beside it, the others are pushed down by the ones before."""
    labels = [lab("First one", "B", "e", 0.5), lab("Second one", "B", "e", 0.6), lab("Third one", "B", "e", 0.7)]
    return key_project(tmp_path, labels, name=name, leader=leader)


def test_a_displaced_label_has_a_leader_that_ends_at_its_detail_and_a_label_beside_its_detail_has_none(tmp_path):
    p = stacked(tmp_path, "auto", "lead_auto")
    r = renderer(p)
    view = view_at(p, 4.0)
    pos = r.layout(view, 4.0 - r.t0)
    sx, sy, rx, ry = X.anchor_of(r.ctx, view, "B")
    segs = [r.leader_segment(view, r.labels[i], r.arts[i], *pos[i][:2]) for i in range(3)]
    gap = [s[4] for s in segs]
    thr = [s[5] for s in segs]
    assert gap[0] == pytest.approx(X.LABEL_GAP * H, abs=1.0) and gap[0] < thr[0], "beside its detail: no line"
    assert gap[2] > thr[2] and gap[2] > gap[1] > gap[0], (gap, thr)
    for s in segs:
        px, py, ex, ey, _g, _t = s
        assert ((ex - sx) / rx) ** 2 + ((ey - sy) / ry) ** 2 == pytest.approx(1.0, abs=0.01), "the line ends on the edge of the detail's ellipse"
    box2 = (pos[2][0], pos[2][1] - r.arts[2].cap, pos[2][0] + r.arts[2].width, pos[2][1] + r.arts[2].below)
    assert box2[0] - 0.5 <= segs[2][0] <= box2[2] + 0.5 and box2[1] - 0.5 <= segs[2][1] <= box2[3] + 0.5, "and starts at the label's box"
    none = frame(stacked(tmp_path, "none", "lead_none"), 4.0)
    auto, hair = frame(p, 4.0), frame(stacked(tmp_path, "hairline", "lead_hair"), 4.0)
    diff = lambda a, b: np.abs(a.astype(int) - b.astype(int)).max(2) > 8
    d_auto, d_hair = diff(auto, none), diff(hair, none)
    px, py, ex, ey = segs[2][:4]
    near = lambda x0, y0, x1, y1, d: int(d[int(min(y0, y1)) - 3:int(max(y0, y1)) + 4, int(min(x0, x1)) - 3:int(max(x0, x1)) + 4].sum())
    assert near(px, py, ex, ey, d_auto) > 15, "the third label has its line"
    first = (slice(int(sy) - 14, int(sy) + 14), slice(int(sx + rx) - 2, int(sx + rx) + 18))
    assert d_auto[first].sum() == 0, "the first, beside its detail, has none"
    assert d_hair[first].sum() > 5 and d_hair.sum() > d_auto.sum(), "hairline draws a line for every label"
    assert d_auto.sum() > 0 and (diff(none, frame(stacked(tmp_path, "none", "lead_none2"), 4.0))).sum() == 0
    # the line fades with its label: half way through the fade of the third label (0.7 s .. 1.0 s) it is fainter than at full
    early = np.abs(frame(p, 0.7 + 0.15).astype(int) - frame(stacked(tmp_path, "none", "lead_none3"), 0.7 + 0.15).astype(int)).max()
    full = np.abs(auto.astype(int) - none.astype(int)).max()
    assert 0 < early < full
    # a label that is not displaced never gets one, whatever the mode: 'auto' equals 'none' for the labels of the default example
    one = lambda mode: frame(key_project(tmp_path, [lab("Alpha one", "A", "e", 0.5)], name="one_" + mode, leader=mode), 4.0)
    assert np.array_equal(one("auto"), one("none"))


ARNOLFINI_KEY_REGIONS = {"LIT": {"x": 1856, "y": 420, "rx": 215, "ry": 215}, "INSCR": {"x": 2220, "y": 1390, "rx": 420, "ry": 120}, "MIRROR": {"x": 2220, "y": 1790, "rx": 440, "ry": 440},
                         "AMBER": {"x": 1810, "y": 1650}, "BRUSH": {"x": 2700, "y": 1560}}


def test_the_default_example_has_no_leader_whatever_the_mode_says(tmp_path):
    """The mock-up's five labels, each beside its detail: `auto` draws nothing, so the default looks like the mock-up (no line)."""
    camera = [{"at": {"rel": 0.0}, "cx": 2220, "cy": 1410, "zoom": 0.5, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 2220, "cy": 1410, "zoom": 0.5, "ease": "linear"}]
    frames = {}
    for mode in ("auto", "none", "hairline"):
        p = make_project(tmp_path, "KEY-01", {"leader": mode}, camera=camera, regions=dict(REGIONS, **ARNOLFINI_KEY_REGIONS), name="def_" + mode)
        assert errors(p) == []
        frames[mode] = frame(p, 4.8)
    assert np.array_equal(frames["auto"], frames["none"]), "no label is displaced or in doubt: no line"
    assert not np.array_equal(frames["hairline"], frames["none"])


def test_a_label_that_lies_over_another_detail_gets_a_leader_to_its_own_detail(tmp_path):
    """Detail A (radius 80 x 60) has its label to the east, where the ellipse of detail X (120 x 80) is: a viewer could take the label for X's, so it is tied to A."""
    regions = dict(REGIONS, X={"x": 1700, "y": 1100, "rx": 120, "ry": 80, "label": "X"})
    labels = [lab("The first detail", "B", "e", 0.5), lab("The other detail", "X", "e", 0.6)]
    mk = lambda mode: make_project(tmp_path, "KEY-01", {"labels": labels, "leader": mode}, regions=regions, name="amb_" + mode)
    auto, none = mk("auto"), mk("none")
    r = renderer(auto)
    view = view_at(auto, 4.0)
    pos = r.layout(view, 4.0)
    anchors = {i: X.anchor_of(r.ctx, view, r.labels[i]["ref"]) for i in pos}
    box = lambda i: (pos[i][0], pos[i][1] - r.arts[i].cap, pos[i][0] + r.arts[i].width, pos[i][1] + r.arts[i].below)
    gap0 = r.leader_segment(view, r.labels[0], r.arts[0], *pos[0][:2])[4]
    assert r.crowded(0, box(0), gap0, anchors) == 1.0, "the first label lies over X's ellipse"
    gap1 = r.leader_segment(view, r.labels[1], r.arts[1], *pos[1][:2])[4]
    assert r.crowded(1, box(1), gap1, anchors) == 0.0, "the second is beside its own detail and far from the other"
    diff = np.abs(frame(auto, 4.0).astype(int) - frame(none, 4.0).astype(int)).max(2) > 8
    sx, sy, rx, ry = anchors[0]
    seg0 = r.leader_segment(view, r.labels[0], r.arts[0], *pos[0][:2])
    assert diff[int(sy) - 6:int(sy) + 6, int(sx + rx) - 2:int(sx + rx) + 18].sum() > 5, "a line from the label to the edge of A"
    assert seg0[4] == pytest.approx(X.LABEL_GAP * H, abs=1.0), "the label itself is where it always is"
    assert diff[:, int(anchors[1][0] + anchors[1][2]) - 2:].sum() == 0, "nothing near the second label"
    same = lambda a, b: np.array_equal(a, b)
    assert same(frame(mk("none"), 4.0), frame(none, 4.0))


def test_the_leader_follows_the_camera_and_its_strength_grows_from_zero_at_the_threshold(tmp_path):
    cam = [{"at": {"rel": 0.0}, "cx": 1300, "cy": 1000, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1700, "cy": 1200, "zoom": 1.0, "ease": "linear"}]
    labels = [lab("First one", "B", "e", 0.5), lab("Second one", "B", "e", 0.6), lab("Third one", "B", "e", 0.7)]
    p = key_project(tmp_path, labels, camera=cam, name="lead_cam")
    r = renderer(p)
    ends = []
    for t in (3.0, 6.0):
        view = view_at(p, t)
        pos = r.layout(view, t)
        ends.append((view, r.leader_segment(view, r.labels[2], r.arts[2], *pos[2][:2])))
    (v1, s1), (v2, s2) = ends
    assert (s2[2] - s1[2], s2[3] - s1[3]) == pytest.approx((-(v2.cx - v1.cx), -(v2.cy - v1.cy)), abs=0.5), "the end of the line moves with the picture"
    assert s2[4] == pytest.approx(s1[4], abs=0.5), "and the label keeps its distance from its detail"
    assert X.smooth(0.0) == 0.0 and X.smooth(1.0) == 1.0 and 0.0 < X.smooth(0.3) < X.smooth(0.7) < 1.0


def test_a_detail_that_leaves_the_frame_takes_its_label_with_it(tmp_path):
    cam = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 3300, "cy": 1100, "zoom": 1.0, "ease": "linear"}]
    p = key_project(tmp_path, [lab("Centre", "CENTRE", "e", 0.5)], camera=cam, dur=10.0, name="leaving")
    assert ink_boxes(frame(p, 1.0), 0.78) is not None
    near = ink_boxes(frame(p, 5.5), 0.78)                             # at 5.5 s the camera is at 2490: the region's centre is 30 px outside the frame: its label is fading with it
    assert near is not None
    gone = ink_boxes(frame(p, 6.5), 0.78)                             # at 6.5 s it is 210 px outside (more than 8 percent of the height): gone
    assert gone is None, gone
    assert ink_boxes(frame(p, 9.0), 0.78) is None, "the region is far left of the frame: no label"
    edge = key_project(tmp_path, [lab("Centre", "CENTRE", "e", 0.5)], camera=[dict(CENTRE_CAM[0], cx=1500 + 960), dict(CENTRE_CAM[1], cx=1500 + 960)], name="edge", dur=8.0)
    partly = ink_boxes(frame(edge, 4.0), 0.78)                        # the region's centre sits on the left edge of the frame: its label is there, held inside the frame
    assert partly is not None and partly[0] >= X.EDGE_MARGIN * H - 1


# ================================================================================ NUM-01
def num_project(tmp_path, rows, name="num", camera=None, **params):
    return make_project(tmp_path, "NUM-01", dict({"rows": rows}, **params), camera=camera, name=name)


def row(label, value, units="", count=0, at=1.0):
    return {"label": label, "value": value, "units": units, "count": count, "at": at}


def test_rows_and_their_parts_appear_at_their_times_and_not_before(tmp_path):
    p = num_project(tmp_path, [row("First", "600", "pelts", 0, 1.0), row("Second", "2,000", "pelts", 0, 3.0)])
    r = renderer(p)
    zones = []
    for ly in r.lay:
        (lx, lb), (vx, vb) = ly["label_pos"], ly["value_pos"]
        zones.append({"label": (slice(int(lb - 30), int(lb + 12)), slice(int(lx) - 4, int(lx) + 400)), "value": (slice(int(vb - 90), int(vb + 8)), slice(int(vx) - 4, int(vx) + 400)),
                      "units": (slice(int(vb - 40), int(vb + 8)), slice(int(ly["units_pos"][0]) - 4, int(ly["units_pos"][0]) + 120))})
    dim = 0.38
    count = lambda t, z: int((gray(frame(p, t))[z] > GREY * dim + 30).sum())
    for i, at in enumerate((1.0, 3.0)):
        z = zones[i]
        assert count(at - 0.05, z["label"]) == 0 and count(at - 0.05, z["value"]) == 0 and count(at - 0.05, z["units"]) == 0, "nothing of the row before its time"
        assert count(at + 0.2, z["label"]) > 50, "the label comes first (0.35 s)"
        assert count(at + 0.2, z["value"]) == 0, "the figure starts 0.25 s after the label starts"
        assert count(at + 0.7, z["value"]) > 800, "then the figure"
        assert count(at + 0.3, z["units"]) == 0 and count(at + 1.0, z["units"]) > 100, "then its units (0.4 s)"
    assert count(2.9, zones[1]["value"]) == 0 and count(2.9, zones[1]["label"]) == 0


def test_the_marks_of_a_row_appear_one_after_another_over_the_stated_time(tmp_path):
    n = 20
    p = num_project(tmp_path, [row("Row", "20", "", n, 1.0)], marks_s=1.1)
    marks = renderer(p).lay[0]["marks"]
    assert len(marks) == n
    r = renderer(p).lay[0]["mark_r"]
    assert r == pytest.approx(0.015 * H / 2, rel=1e-6)

    def lit(t):
        g = gray(frame(p, t))
        return [bool(g[int(round(cy)), int(round(cx))] > GREY * 0.38 + 0.5 * (0.92 * 240 - GREY * 0.38)) for cx, cy in marks]
    per = 1.1 / n
    prefix = []
    for k in range(-2, n + 4, 2):
        flags = lit(1.0 + 0.6 + k * per + 0.06)
        first_off = flags.index(False) if False in flags else n
        assert not any(flags[first_off:]), "a mark is on while an earlier one is off: %s" % flags
        prefix.append(first_off)
    assert prefix == sorted(prefix), prefix
    assert prefix[0] == 0 and prefix[-1] == n
    assert not any(lit(1.55)), "no mark before 0.6 s after the row's time"
    assert all(lit(1.0 + 0.6 + 1.1 + 0.2)), "all of them at the end"
    mid = sum(lit(1.0 + 0.6 + 0.55 + 0.03))
    assert n // 2 - 3 <= mid <= n // 2 + 3, mid
    # the next mark does not start before the one before it: the marks' times in the file are ordered along the row
    xs = [m[0] for m in marks[:20]]
    assert xs == sorted(xs) and len({round(m[1]) for m in marks}) == 1, "one line, left to right"
    q = num_project(tmp_path, [row("Row", "20", "", n, 1.0)], name="num_slow", marks_s=4.0)
    mid2 = sum(1 for (cx, cy) in marks if gray(frame(q, 1.0 + 0.6 + 2.0))[int(round(cy)), int(round(cx))] > GREY * 0.38 + 60)
    assert n // 2 - 3 <= mid2 <= n // 2 + 3, "marks_s stretches the run"


def test_forty_marks_make_two_lines_and_sixty_make_two_lines_of_thirty(tmp_path):
    for count, lines, per in ((12, 1, 20), (40, 2, 20), (41, 2, 30), (60, 2, 30)):
        r = renderer(num_project(tmp_path, [row("Row", "7", "", count, 1.0)], name="m%d" % count)).lay[0]
        assert len(r["marks"]) == count and len({round(m[1]) for m in r["marks"]}) == lines, count
        assert len({round(m[0]) for m in r["marks"]}) == min(count, per), count


def test_the_picture_is_dimmed_behind_the_rows(tmp_path):
    p = num_project(tmp_path, [row("First", "600", "pelts", 0, 2.0)])
    far = lambda t: int(frame(p, t)[1060, 1900, 0])
    assert far(1.0) == GREY, "the dim starts 0.8 s before the first row (1.2 s)"
    assert far(2.0) == pytest.approx(GREY * 0.38, abs=1.5), "and is complete 0.1 s before it"
    assert far(5.0) == pytest.approx(GREY * 0.38, abs=1)
    assert far(8.0) == GREY and far(9.0) == GREY
    q = num_project(tmp_path, [row("First", "600", "pelts", 0, 2.0)], name="num_dim", dim_picture_to=0.7)
    assert int(frame(q, 5.0)[1060, 1900, 0]) == pytest.approx(GREY * 0.7, abs=1)


def test_the_figure_is_as_high_as_cap_pct_says(tmp_path):
    for cap in (6.0, 8.0, 11.0, 14.0):
        p = num_project(tmp_path, [row("", "HHH", "", 0, 0.5)], name="cap%d" % cap, cap_pct=cap, caption="", source="")
        x0, y0, x1, y1 = ink_boxes(frame(p, 3.0), 0.38)
        assert (y1 - y0) == pytest.approx(cap / 100 * H, abs=2.5), (cap, y1 - y0)


def test_rows_are_stacked_in_order_inside_the_frame_for_one_to_four_rows(tmp_path):
    for n in (1, 2, 3, 4):
        rows = [row("Row %d" % (i + 1), "%d,000" % (i + 1), "pelts", 12 + 14 * i, 0.5 + 0.4 * i) for i in range(n)]
        for cap in (8.0, 14.0):
            p = num_project(tmp_path, rows, name="stack%d_%d" % (n, cap), cap_pct=cap, caption="each dot is fifty pelts", source="Source: a book")
            r = renderer(p)
            ys = []
            for ly in r.lay:
                ys += [ly["label_pos"][1], ly["value_pos"][1]] + [m[1] for m in ly["marks"]]
            assert ys == sorted(ys), (n, cap, "rows are in order, top to bottom")
            assert ys[0] > 0.06 * H and ys[-1] < 0.88 * H, (n, cap, ys[0], ys[-1])
            img = frame(p, 7.0 - 0.6)                                    # everything is there, nothing has left yet
            m = gray(img) > GREY * 0.38 + 30
            ysx, xsx = np.where(m)
            assert xsx.min() >= 0.05 * W and xsx.max() <= 0.97 * W and ysx.min() >= 0.05 * H and ysx.max() <= 0.97 * H, (n, cap)
    one = renderer(num_project(tmp_path, [row("Alone", "600", "pelts", 12, 1.0)], name="alone")).lay[0]
    assert 0.3 * H < one["value_pos"][1] < 0.6 * H, "one row alone is centred, not pushed to the top"


def test_four_rows_with_marks_are_scaled_to_fit_and_do_not_overlap(tmp_path):
    rows = [row("Row %d" % (i + 1), "%d" % (100 * (i + 1)), "u", 40, 0.5 + 0.4 * i) for i in range(4)]
    p = num_project(tmp_path, rows, name="four40", cap_pct=14.0)
    r = renderer(p)
    assert r.scale < 1.0 * 14 / 8, "everything was made smaller by one factor"
    bottoms = [ly["marks"][-1][1] for ly in r.lay]
    tops = [ly["label_pos"][1] for ly in r.lay]
    assert all(tops[i + 1] > bottoms[i] for i in range(3)), "no row runs into the next"


def test_align_right_mirrors_the_block_to_the_right_margin(tmp_path):
    rows = [row("Label", "2,000", "pelts", 10, 0.5)]
    left = frame(num_project(tmp_path, rows, name="al"), 4.0)
    right = frame(num_project(tmp_path, rows, name="ar", align="right"), 4.0)
    for img, side in ((left, "left"), (right, "right")):
        ys, xs = np.where(gray(img) > GREY * 0.38 + 30)
        assert ys.size > 500
        if side == "left":
            assert xs.min() >= 0.075 * W - 3 and xs.mean() < 0.35 * W
        else:
            assert xs.max() <= 0.925 * W + 3 and xs.max() >= 0.915 * W and xs.mean() > 0.65 * W


def test_the_caption_comes_with_the_first_marks_and_stays_to_the_end_and_the_source_with_the_first_figure(tmp_path):
    p = num_project(tmp_path, [row("A", "6", "", 12, 1.0), row("B", "20", "", 12, 2.0)], caption="each dot is fifty pelts", source="Source: Christie's")
    r = renderer(p)
    assert r.caption_at == pytest.approx(1.0 + 0.6), "it explains the marks: it comes when the first of them appear"
    cap_z, src_z = (slice(int(0.88 * H), int(0.915 * H)), slice(150, 900)), (slice(int(0.93 * H), int(0.965 * H)), slice(150, 900))
    count = lambda t, z: int((gray(frame(p, t))[z] > GREY * 0.38 + 14).sum())
    assert count(1.55, cap_z) == 0, "not before the first mark"
    assert 0 < count(1.85, cap_z) < count(2.3, cap_z), "it fades in over 0.5 s"
    assert count(2.3, cap_z) > 100 and count(4.0, cap_z) > 100 and count(7.0, cap_z) > 100, "and it stays: readable for the whole of the overlay"
    assert count(7.4, cap_z) > 100, "up to the moment the overlay starts to leave (7.5 s)"
    assert count(1.1, src_z) == 0 and count(1.9, src_z) > 100, "the source line comes with the first figure"
    q = num_project(tmp_path, [row("A", "6", "", 0, 1.0)], name="nocap", caption="", source="")
    assert q is not None and renderer(q).caption is None and renderer(q).source is None
    plain = renderer(num_project(tmp_path, [row("A", "6", "", 0, 1.0)], name="nomarks"))
    assert plain.caption_at == pytest.approx(1.0 + 0.75), "no marks at all: the caption follows the first figure"
    later = renderer(num_project(tmp_path, [row("A", "6", "", 0, 1.0), row("B", "20", "", 5, 2.5)], name="latemarks"))
    assert later.caption_at == pytest.approx(2.5 + 0.6), "the first row that has marks decides"


def test_the_units_are_at_the_secondary_level_and_no_smaller_than_the_label(tmp_path):
    p = num_project(tmp_path, [row("Label", "2,000", "pelts", 0, 1.0)], caption="", source="")
    ly = renderer(p).lay[0]
    ar = ly["ar"]
    assert X.BigNumber.UNITS_ALPHA == 0.72 and X.BigNumber.TEXT_ALPHA == 1.0
    assert ar["units"].cap >= ar["label"].cap - 0.01 and ar["units"].size >= ar["label"].size
    img = gray(frame(p, 3.0)) - GREY * 0.38
    (ux, ub), (lx, lb) = ly["units_pos"], ly["label_pos"]
    units = img[int(ub) - 40:int(ub) + 10, int(ux) - 4:int(ux + ar["units"].width) + 4]
    label = img[int(lb) - 40:int(lb) + 10, int(lx) - 4:int(lx + ar["label"].width) + 4]
    ratio = float(np.percentile(units, 99.5)) / float(np.percentile(label, 99.5))
    assert 0.62 <= ratio <= 0.82, ratio


def test_the_text_of_the_number_is_set_in_the_bundled_faces(tmp_path):
    r = renderer(num_project(tmp_path, [row("Label", "2,000", "pelts", 0, 1.0)]))
    ar = r.lay[0]["ar"]
    assert ar["value"].kind == "eb_medium" and ar["label"].kind == "eb_italic" and ar["units"].kind == "eb_italic"
    assert ar["value"].cap == pytest.approx(0.08 * H, abs=0.6)


# ================================================================================ DOC-01
def doc_project(tmp_path, lit, camera=None, name="doc", **params):
    base = {"reading": "", "original": ""}
    return make_project(tmp_path, "DOC-01", dict(base, lit=lit, **params), camera=camera, name=name)


def bright_box(img, dim_to=0.34):
    """Bounding box of the pixels above the half level between the dimmed and the lit grey."""
    m = gray(img) > GREY * (1 + dim_to) / 2
    ys, xs = np.where(m)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else None


def test_the_lit_window_is_brighter_than_its_surroundings_by_the_stated_ratio(tmp_path):
    for dim in (0.25, 0.34, 0.6):
        p = doc_project(tmp_path, [{"ref": "WIDE", "at": 0.5}], name="ratio%d" % int(dim * 100), dim_to=dim, pad_px=0)
        img = gray(frame(p, 3.0))
        inside, outside = img[540 - 40:540 + 40, 960 - 250:960 + 250], img[20:100, 20:200]
        assert inside.mean() == pytest.approx(GREY, abs=0.6) and outside.mean() == pytest.approx(GREY * dim, abs=0.8), dim
        assert inside.mean() / outside.mean() == pytest.approx(1 / dim, rel=0.025), dim


def test_the_edge_of_the_window_is_soft_and_has_no_outline(tmp_path):
    for edge in (0, 12, 40, 100):
        p = doc_project(tmp_path, [{"ref": "WIDE", "at": 0.5}], name="edge%d" % edge, edge_px=edge, pad_px=0)
        row_ = gray(frame(p, 3.0))[540]
        out, inn = GREY * 0.34, float(GREY)
        m = (row_ - out) / (inn - out)
        left = m[:960]                                                 # the left border of the window: rx 300 -> x = 660
        i10, i50, i90 = (int(np.argmax(left > q)) for q in (0.1, 0.5, 0.9))
        assert abs(i50 - 660) <= 1.5, (edge, i50)
        if edge == 0:
            assert i90 - i10 <= 2.5, "edge_px 0 is a clean border"
        else:
            assert 0.5 * edge <= (i90 - i10) <= 0.8 * edge + 1.5, (edge, i10, i90)
        assert m.max() <= 1.012 and m.min() >= -0.012, "no outline: the profile never goes above the lit grey or under the dimmed one"
        assert (np.diff(left) >= -1.01).all(), "monotone across the border"


def test_the_lit_window_follows_the_camera_and_scales_with_the_picture(tmp_path):
    cam = [{"at": {"rel": 0.0}, "cx": 1300, "cy": 1000, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1700, "cy": 1200, "zoom": 1.0, "ease": "linear"}]
    p = doc_project(tmp_path, [{"ref": "WIDE", "at": 0.5}], camera=cam, pad_px=0, edge_px=8)
    b1, b2 = bright_box(frame(p, 2.0)), bright_box(frame(p, 6.0))
    assert b1 is not None and b2 is not None
    v1, v2 = view_at(p, 2.0), view_at(p, 6.0)
    dx, dy = -(v2.cx - v1.cx) * v1.z, -(v2.cy - v1.cy) * v1.z
    assert (dx, dy) == pytest.approx((-160, -80))
    assert [b2[i] - b1[i] for i in range(4)] == pytest.approx([dx, dy, dx, dy], abs=2), (b1, b2)
    assert (b1[2] - b1[0], b1[3] - b1[1]) == pytest.approx((600, 160), abs=2) and (b2[2] - b2[0], b2[3] - b2[1]) == pytest.approx((600, 160), abs=2)
    zoom = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1500, "cy": 1100, "zoom": 1.5, "ease": "linear"}]
    q = doc_project(tmp_path, [{"ref": "WIDE", "at": 0.5}], camera=zoom, name="zoom", pad_px=40, edge_px=8)
    for t in (1.5, 6.0):
        z = view_at(q, t).z
        b = bright_box(frame(q, t))
        assert (b[2] - b[0], b[3] - b[1]) == pytest.approx((600 * z + 80, 160 * z + 80), abs=3), (t, z, b)


def test_the_padding_and_a_box_in_source_pixels(tmp_path):
    for pad in (0, 40, 120):
        p = doc_project(tmp_path, [{"ref": "WIDE", "at": 0.5}], name="pad%d" % pad, pad_px=pad, edge_px=6)
        b = bright_box(frame(p, 3.0))
        assert (b[2] - b[0], b[3] - b[1]) == pytest.approx((600 + 2 * pad, 160 + 2 * pad), abs=3), pad
    q = doc_project(tmp_path, [{"ref": "A", "box": "1250, 900, 1750, 1000", "at": 0.5}], name="box", pad_px=0, edge_px=6)
    b = bright_box(frame(q, 3.0))
    assert (b[2] - b[0], b[3] - b[1]) == pytest.approx((500, 100), abs=3), "the box wins over the region"
    assert (b[0] + b[2]) / 2 == pytest.approx(960, abs=2) and (b[1] + b[3]) / 2 == pytest.approx(540 - 150, abs=2)
    r = doc_project(tmp_path, [{"ref": "POINT", "at": 0.5}], name="pointwin", pad_px=0, edge_px=6)
    b = bright_box(frame(r, 3.0))
    assert (b[2] - b[0]) == pytest.approx(2 * 0.07 * PIC_W, abs=4) and (b[3] - b[1]) == pytest.approx(2 * 0.02 * PIC_W, abs=4), "a region without radii gets a default window"


def test_windows_light_one_after_another_and_the_dimming_stays_while_any_is_lit(tmp_path):
    p = doc_project(tmp_path, [{"ref": "UL", "at": 1.0, "hold_s": 0}, {"ref": "LR", "at": 3.0, "hold_s": 2.0}], name="seq", pad_px=0, edge_px=8)
    # UL is centred at screen (960 - 500, 540 - 400) = (460, 140); LR at (960 + 500, 540 + 400) = (1460, 940)
    inside = lambda img, cx, cy: float(img[cy - 5:cy + 5, cx - 100:cx + 100].mean())
    at = lambda t: gray(frame(p, t))
    lo, hi = GREY * 0.34, float(GREY)
    a, b = at(0.9), at(1.9)
    assert inside(a, 460, 140) == pytest.approx(GREY, abs=0.5), "nothing is dimmed before the first window"
    assert inside(b, 460, 140) == pytest.approx(hi, abs=1) and inside(b, 1460, 940) == pytest.approx(lo, abs=1), "the first window alone"
    c = at(3.35)                                                    # a crossfade: A falls (it ends when B rises) while B rises, the two share the dimming: both half way
    assert lo + 0.3 * (hi - lo) < inside(c, 460, 140) < lo + 0.8 * (hi - lo) and lo + 0.3 * (hi - lo) < inside(c, 1460, 940) < lo + 0.8 * (hi - lo)
    d = at(4.2)
    assert inside(d, 1460, 940) == pytest.approx(hi, abs=1) and inside(d, 460, 140) == pytest.approx(lo, abs=1), "the second window alone"
    e = at(5.35)                                                    # B has hold_s 2.0: it falls over 5.0 .. 5.7, alone, so the dimming falls with it: half way
    assert inside(e, 1460, 940) == pytest.approx(hi, abs=1) and inside(e, 460, 140) == pytest.approx(lo + 0.5 * (hi - lo), abs=2.5)
    e = at(6.5)                                                     # nothing is lit, nothing is dimmed
    assert inside(e, 1460, 940) == pytest.approx(GREY, abs=1) and inside(e, 460, 140) == pytest.approx(GREY, abs=1)
    f = at(7.9)
    assert abs(float(f[1060, 1900]) - GREY) < 25, "everything is back by the end"


def test_the_window_rises_and_falls_over_ramp_s(tmp_path):
    p = doc_project(tmp_path, [{"ref": "WIDE", "at": 1.0, "hold_s": 2.0}], name="ramp", ramp_s=1.0, pad_px=0)
    centre = lambda t: float(gray(frame(p, t))[540, 960])
    corner = lambda t: float(gray(frame(p, t))[20, 20])
    assert corner(0.9) == GREY and corner(1.5) == pytest.approx(GREY * (1 - 0.66 * 0.5), abs=1.5) and corner(2.1) == pytest.approx(GREY * 0.34, abs=1)
    assert centre(1.5) == pytest.approx(GREY, abs=1), "the window is lit all the time; only the surroundings dim"
    assert corner(3.0) == pytest.approx(GREY * 0.34, abs=1) and corner(3.5) == pytest.approx(GREY * (1 - 0.66 * 0.5), abs=1.5) and corner(4.1) == GREY


def test_the_reading_and_the_line_as_written_appear_at_reading_at(tmp_path):
    p = make_project(tmp_path, "DOC-01", {"lit": [{"ref": "WIDE", "at": 1.0}], "reading": "Jan van Eyck was here. 1434", "original": "Johannes de eyck fuit hic · 1434", "reading_at": 3.0})
    reading_z, original_z = (slice(int(0.76 * H), int(0.82 * H)), slice(300, 1620)), (slice(int(0.835 * H), int(0.885 * H)), slice(300, 1620))
    ink = lambda t, z: int((gray(frame(p, t))[z] > GREY * 0.34 + 30).sum())
    assert ink(2.9, reading_z) == 0 and ink(2.9, original_z) == 0
    assert 0 < ink(3.2, reading_z) < ink(3.6, reading_z) and ink(3.6, reading_z) > 600
    assert ink(3.3, original_z) == 0, "the original follows 0.4 s later"
    assert ink(4.0, original_z) > 200
    # italic reading, centred; the line as written in capitals, 70 percent
    x0, y0, x1, y1 = ink_boxes(frame(p, 5.0), 0.34, thr=40)
    assert abs((x0 + x1) / 2 - 960) < 40
    ro = renderer(p)
    assert ro.reading.kind == "eb_italic" and ro.original.text == "JOHANNES DE EYCK FUIT HIC · 1434" and ro.original.trk4 > 0


def test_reading_at_is_a_param_of_type_at_and_a_word_brings_the_reading_on_that_word(tmp_path):
    """`reading_at` is one moment (the parameter type `at`): seconds from the start of the overlay, or a word of the narration (word 6 starts at 3.0 s in the test timing;
    the overlay starts at 1.0 s, so the reading comes 2.0 s into it). It is resolved and checked the way a camera key's `at` is."""
    assert param("DOC-01", "reading_at")["type"] == "at" and R.at_params(spec("DOC-01")) == ["reading_at"]
    base = {"lit": [{"ref": "WIDE", "at": 0.5}], "reading": "Jan van Eyck was here. 1434", "original": "Johannes de eyck fuit hic · 1434"}
    word = {"w": 6, "off": 0.0, "text": "w6"}
    p = make_project(tmp_path, "DOC-01", dict(base, reading_at=word), start=1.0, dur=7.0)
    assert errors(p) == []
    assert p.resolve()["shots"][0]["overlays"][0]["params"]["reading_at"]["_t"] == pytest.approx(3.0)
    assert renderer(p).reading_at == pytest.approx(2.0)
    seconds = make_project(tmp_path, "DOC-01", dict(base, reading_at=2.0), start=1.0, dur=7.0, name="seconds")
    reading_z = (slice(int(0.76 * H), int(0.82 * H)), slice(300, 1620))
    ink = lambda t: int((gray(frame(p, t))[reading_z] > GREY * 0.34 + 30).sum())
    assert ink(2.9) == 0 and ink(4.0) > 600, "nothing before the word, the reading after it"
    for t in (2.9, 3.2, 3.6, 5.0):
        assert np.array_equal(frame(p, t), frame(seconds, t)), "a word and its time in seconds draw the same frame at %s" % t
    stale = copy.deepcopy(p.storyboard())
    stale["shots"][0]["overlays"][0]["params"]["reading_at"] = {"w": 6, "off": 0.0, "text": "zzz"}
    assert [(i["code"], i["path"]) for i in errors(p, stale)] == [("stale_anchor", "shots[0].overlays[0].params.reading_at")]
    gone = copy.deepcopy(p.storyboard())
    gone["shots"][0]["overlays"][0]["params"]["reading_at"] = {"w": 9999, "off": 0.0, "text": "x"}
    assert [i["code"] for i in errors(p, gone)] == ["anchor_invalid"]
    for bad, code in (("soon", "param_bad_at"), (-1, "param_below_min"), (601, "param_above_max")):
        d = copy.deepcopy(p.storyboard())
        d["shots"][0]["overlays"][0]["params"]["reading_at"] = bad
        assert [i["code"] for i in errors(p, d)] == [code], bad


def test_the_overlays_sit_on_a_two_state_base_and_follow_its_camera(tmp_path):
    """STATE-01 (the other checkout) draws its two pictures through ONE camera and provides `view()` of the picture in slot a, so KEY-01 and DOC-01 may sit on it. With a
    still camera the three overlays draw exactly what they draw on a CAM-05 shot (before, during and after a dissolve; the states are the same flat picture); with a moving
    camera, whose clock STATE-01 bends (it stands still through a dissolve), a label stays beside its detail where `view(t)` of the base puts it."""
    assert X.LabelsKey.check_base("STATE-01") is None and X.LitLine.check_base("STATE-01") is None
    still = [{"at": {"rel": 0.0}, "cx": 1400, "cy": 1000, "zoom": 0.8, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1400, "cy": 1000, "zoom": 0.8, "ease": "linear"}]
    key = {"labels": [lab("Alpha one", "A", "e", 1.0)]}
    doc = {"lit": [{"ref": "WIDE", "at": 0.5}], "reading": "", "original": ""}
    num = {"rows": [row("First", "600", "pelts", 0, 1.0)]}
    above_caption = slice(0, 900)                                   # the caption of the state is at the bottom left of the frame; the overlays are tested above it
    for tid, params, lit_px in (("KEY-01", key, GREY * 0.78 + 30), ("DOC-01", doc, GREY * 0.67), ("NUM-01", num, GREY * 0.78 + 30)):
        name = tid.lower().replace("-", "")
        on_state = make_project(tmp_path, tid, params, camera=still, name=name + "_state", base="STATE-01")
        on_cam = make_project(tmp_path, tid, params, camera=still, name=name + "_cam")
        assert errors(on_state) == [], tid
        for t in (1.5, 3.0, 4.5, 6.0):                              # the default holds are 1.5, 2.5 and 1.5 s with a dissolve of 1 s between them
            a, b = frame(on_state, t).astype(int)[above_caption], frame(on_cam, t).astype(int)[above_caption]
            assert np.abs(a - b).max() <= 2, (tid, t, int(np.abs(a - b).max()))
        assert int((gray(frame(on_state, 4.5))[above_caption] > lit_px).sum()) > 100, tid + ": the overlay is drawn on the two-state base"
    move = [{"at": {"rel": 0.0}, "cx": 1400, "cy": 1000, "zoom": 0.8, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1600, "cy": 1100, "zoom": 1.2, "ease": "linear"}]
    p = make_project(tmp_path, "KEY-01", key, camera=move, name="key_state_move", base="STATE-01")
    assert errors(p) == []
    for t in (2.0, 3.5, 5.0):
        v = view_at(p, t)
        sx, sy = (float(c) for c in v.to_screen(1100, 800))        # the region A of the lab picture, where the base puts it at this moment
        rows = slice(max(0, int(sy) - 60), int(sy) + 60)
        ys, xs = np.where(gray(frame(p, t))[rows] > GREY * 0.78 + 30)
        assert len(xs) > 100, t
        assert sx + 80 * v.z < xs.min() < sx + 80 * v.z + 60 and abs((ys.min() + ys.max()) / 2 + rows.start - sy) < 40, (t, sx, sy, int(xs.min()))


def test_the_text_goes_above_the_window_when_the_window_comes_down_into_its_place(tmp_path):
    p = make_project(tmp_path, "DOC-01", {"lit": [{"ref": "LOW", "at": 1.0}], "reading": "Below", "original": "", "reading_at": 2.0})
    up, down = (slice(int(0.12 * H), int(0.22 * H)), slice(500, 1420)), (slice(int(0.76 * H), int(0.83 * H)), slice(500, 1420))
    ink = lambda img, z: int((gray(img)[z] > GREY * 0.34 + 30).sum())
    # LOW is centred at screen (960, 540 + 500): its window reaches into the lower fifth, so the reading is placed above it (baseline at 17.8 percent)
    img = frame(p, 5.0)
    assert ink(img, up) > 150, "the reading is above"
    q = make_project(tmp_path, "DOC-01", {"lit": [{"ref": "WIDE", "at": 1.0}], "reading": "Below", "original": "", "reading_at": 2.0}, name="below")
    img = frame(q, 5.0)
    assert ink(img, up) == 0 and ink(img, down) > 150, "the window is in the middle: the reading is under it, where the mock-up has it"


def test_the_camera_may_move_in_on_the_line_while_the_window_follows(tmp_path):
    """The mock-up's shot: the camera eases in on the signature while its window is lit and the reading arrives."""
    cam = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1000, "zoom": 0.7, "ease": "inout_cubic"}, {"at": {"t": 3.0}, "cx": 1500, "cy": 1100, "zoom": 1.2, "ease": "linear"}]
    p = doc_project(tmp_path, [{"ref": "WIDE", "at": 1.0}], camera=cam, pad_px=20, edge_px=10)
    prev = None
    for t in (1.8, 2.2, 2.6, 3.0, 3.6):
        z, cx, cy = view_at(p, t).z, view_at(p, t).cx, view_at(p, t).cy
        b = bright_box(frame(p, t))
        want = (960 + (1200 - cx) * z - 20, 540 + (1020 - cy) * z - 20, 960 + (1800 - cx) * z + 20, 540 + (1180 - cy) * z + 20)
        assert b == pytest.approx(want, abs=3), (t, b, want)
        assert prev is None or b[2] - b[0] >= prev[2] - prev[0] - 1
        prev = b


# ================================================================================ everything that is not about one technique
@pytest.mark.parametrize("tid,params", [
    ("KEY-01", {"labels": [lab("Alpha", "A", "e", 1.0), lab("Beta", "B", "w", 2.0)]}),
    ("NUM-01", {"rows": [row("A", "600", "pelts", 12, 1.0), row("B", "2,000", "pelts", 40, 2.9)]}),
    ("DOC-01", {"lit": [{"ref": "WIDE", "at": 1.0}], "reading": "A reading", "original": "As written"})])
def test_the_same_frame_rendered_twice_and_out_of_order_is_identical(tmp_path, tid, params):
    p = make_project(tmp_path, tid, params, name="pure_" + tid[:3])
    ts = [4.5, 1.2, 7.7, 0.3, 3.1, 6.0, 2.2, 7.9]
    first = {t: frame(p, t) for t in ts}
    for t in reversed(ts):
        assert np.array_equal(frame(p, t), first[t]), (tid, t)
    q = make_project(tmp_path, tid, params, name="pure2_" + tid[:3])
    assert np.array_equal(frame(q, 3.1), first[3.1]), "a new project draws the same frame"


def bounds_cases(tid, pd):
    cases = []
    if pd["type"] == "number":
        cases = [pd["min"], pd["max"], pd["default"]]
    elif pd["type"] == "enum":
        cases = list(pd["values"])
    elif pd["type"] == "bool":
        cases = [True, False]
    elif pd["type"] in ("string", "text"):
        cases = ["", "x" * 40, pd["default"]]
        if pd["name"] == "value":
            cases = ["7"]
    elif pd["type"] == "items":
        for fd in pd["fields"]:
            if fd["type"] in ("number", "at"):
                for bound in (fd["min"], fd["max"]):
                    items = copy.deepcopy(pd["default"])
                    items[0][fd["name"]] = bound
                    cases.append(items)
            elif fd["type"] == "enum":
                for v in fd["values"]:
                    items = copy.deepcopy(pd["default"])
                    items[0][fd["name"]] = v
                    cases.append(items)
        cases.append(copy.deepcopy(pd["default"]))
        if pd["name"] == "labels":
            cases.append([dict(pd["default"][0], text="Label %d" % i, ref=["LIT", "INSCR", "MIRROR", "AMBER", "BRUSH", "HANDS"][i % 6], side="auto", at=0.2 * i) for i in range(12)])
        if pd["name"] == "rows":
            cases.append([dict(pd["default"][0], value="%d" % (i + 1), count=60, at=0.5 * i) for i in range(4)])
        if pd["name"] == "lit":
            cases.append([dict(pd["default"][0], ref=["INSCR", "MIRROR", "HANDS", "LIT", "AMBER", "BRUSH"][i], at=0.8 * i, hold_s=1.5 if i % 2 else 0) for i in range(6)])
    return cases


@pytest.mark.parametrize("tid", IDS)
def test_every_param_at_its_bounds_validates_and_draws(tmp_path, tid):
    """Every number at its min and max, every enum value, every bool, and the extremes of every field of every list: validates and draws, on the Arnolfini regions of the
    default data (a picture with those regions is the example the default data is written for)."""
    reg = json.loads((REPO / "tests/engine" / "arnolfini_regions.json").read_text(encoding="utf-8")) if (REPO / "tests/engine/arnolfini_regions.json").exists() else None
    regions = reg or dict(REGIONS, LIT={"x": 1856, "y": 420, "rx": 215, "ry": 215}, INSCR={"x": 2220, "y": 1390, "rx": 420, "ry": 120}, MIRROR={"x": 2220, "y": 1790, "rx": 440, "ry": 440},
                          AMBER={"x": 1810, "y": 1650}, BRUSH={"x": 2700, "y": 1560}, HANDS={"x": 2420, "y": 2540, "rx": 360, "ry": 270})
    camera = [{"at": {"rel": 0.0}, "cx": 1500, "cy": 1100, "zoom": 0.9, "ease": "linear"}, {"at": {"rel": 1.0}, "cx": 1500, "cy": 1100, "zoom": 1.0, "ease": "linear"}]
    p = make_project(tmp_path, tid, {}, camera=camera, regions=regions, name="bounds_" + tid[:3])
    sb = p.storyboard()
    n = 0
    for pd in spec(tid)["params"]:
        for v in bounds_cases(tid, pd):
            d = copy.deepcopy(sb)
            d["shots"][0]["overlays"][0]["params"] = {pd["name"]: v}
            assert errors(p, d) == [], (pd["name"], str(v)[:80], errors(p, d)[:2])
            p.use_draft(d)
            try:
                for t in (0.2, 2.5, 4.0, 7.4):
                    img = p.frame_at(t, 320)
                    assert img.shape == (180, 320, 3)
                n += 1
            finally:
                p.use_draft(None)
    assert n > 25


@pytest.mark.parametrize("tid,params", [("KEY-01", {}), ("NUM-01", {}), ("DOC-01", {})])
def test_an_element_shorter_than_its_minimum_is_an_error(tmp_path, tid, params):
    minimum = spec(tid)["timing"]["min_s"]
    short = make_project(tmp_path, tid, params, dur=minimum - 0.5, name="short_" + tid[:3])
    e = [i for i in errors(short) if i["code"] == "element_too_short"]
    assert len(e) == 1 and e[0]["args"]["technique"] == tid and e[0]["args"]["min"] == minimum and e[0]["args"]["got"] == pytest.approx(minimum - 0.5)
    ok = make_project(tmp_path, tid, params, dur=minimum, name="ok_" + tid[:3])
    assert [i for i in errors(ok) if i["code"] == "element_too_short"] == []


@pytest.mark.parametrize("tid", IDS)
def test_no_socket_is_opened_while_the_overlay_is_drawn(tmp_path, monkeypatch, tid):
    p = make_project(tmp_path, tid, {}, name="sock_" + tid[:3], regions=dict(REGIONS, LIT=REGIONS["A"], INSCR=REGIONS["WIDE"], MIRROR=REGIONS["B"], AMBER=REGIONS["POINT"], BRUSH=REGIONS["POINT"]))

    def forbid(*a, **k):
        raise AssertionError("a socket was opened while %s drew a frame" % tid)
    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    for t in (0.2, 3.0, 6.0):
        assert p.frame_at(t, 480).shape == (270, 480, 3)


def test_the_draw_check_and_the_default_params_of_each_technique_pass(tmp_path):
    regions = dict(REGIONS, LIT=REGIONS["A"], INSCR=REGIONS["WIDE"], MIRROR=REGIONS["B"], AMBER=REGIONS["POINT"], BRUSH=REGIONS["POINT"])
    for tid in IDS:
        p = make_project(tmp_path, tid, {}, regions=regions, name="dc_" + tid[:3])
        assert p.draw_check() == [], tid
        d = p.default_params(tid, {})
        assert d == {x["name"]: x["default"] for x in spec(tid)["params"]}
        d2 = p.default_params(tid, {"asset": {"key": "A", "w": PIC_W, "h": PIC_H, "regions": {"MOUTH": {"x": 5, "y": 5, "rx": 40, "ry": 10, "label": "Mouth"}, "EYE": {"x": 9, "y": 9, "label": "An eye"}}}})
        sb = p.storyboard()
        sb["shots"][0]["overlays"][0]["params"] = d2
        assert [i for i in errors(p, sb) if i["code"] != "region_undefined"] == [], tid
    k = make_project(tmp_path, "KEY-01", {}, regions=regions, name="dk").default_params("KEY-01", {"asset": {"regions": {"MOUTH": {"x": 5, "y": 5, "rx": 40, "ry": 10, "label": "Mouth"}}}})
    assert [(x["text"], x["ref"]) for x in k["labels"]] == [("Mouth", "MOUTH")], "the default labels follow the regions of the picture when it has not the Arnolfini ones"
    dd = make_project(tmp_path, "DOC-01", {}, regions=regions, name="dd").default_params("DOC-01", {"asset": {"regions": {"EYE": {"x": 9, "y": 9, "rx": 20, "ry": 20}, "SIGN": {"x": 5, "y": 5, "rx": 80, "ry": 10}}}})
    assert dd["lit"][0]["ref"] == "SIGN", "the widest region is the line"


def test_validate_accepts_only_what_the_overlays_can_draw(tmp_path):
    """The rule of the registry (R2B-012) for the three overlays, run here because the full sweep is a slow test: every odd value of every param (wrong but well typed,
    extreme, empty, degenerate) is either refused by `validate` or drawn."""
    from test_validate_draw_sweep import odd_values
    regions = dict(REGIONS, LIT=REGIONS["A"], INSCR=REGIONS["WIDE"], MIRROR=REGIONS["B"], AMBER=REGIONS["POINT"], BRUSH=REGIONS["POINT"])
    for tid in IDS:
        p = make_project(tmp_path, tid, {}, regions=regions, name="odd_" + tid[:3])
        sb = p.storyboard()
        holes, drawn = [], 0
        for pd in spec(tid)["params"]:
            for v in odd_values(pd, pd["default"], [], None):
                d = copy.deepcopy(sb)
                d["shots"][0]["overlays"][0]["params"] = {pd["name"]: v}
                if errors(p, d):
                    continue
                p.use_draft(d)
                try:
                    p.frame_at(4.0, 160)
                    drawn += 1
                except Exception as e:      # noqa: BLE001
                    holes.append((tid, pd["name"], str(v)[:60], "%s: %s" % (type(e).__name__, str(e)[:100])))
                finally:
                    p.use_draft(None)
        assert not holes, holes[:6]
        assert drawn >= 5, (tid, drawn)


def test_a_frame_costs_what_the_other_overlays_cost(tmp_path):
    """A guard against a slow path (the milliseconds per frame are in docs/qa/FIX_comp_over.md): a warm 1920 px frame under 0.4 s each."""
    import time
    regions = dict(REGIONS, LIT=REGIONS["A"], INSCR=REGIONS["WIDE"], MIRROR=REGIONS["B"], AMBER=REGIONS["POINT"], BRUSH=REGIONS["POINT"])
    for tid in IDS:
        p = make_project(tmp_path, tid, {}, regions=regions, name="cost_" + tid[:3])
        frame(p, 5.0)
        t0 = time.perf_counter()
        for t in (4.0, 4.3, 6.0, 6.3):
            frame(p, t)
        assert (time.perf_counter() - t0) / 4 < 0.4, tid


def test_key_late_saved_labels_are_planned_earlier_when_rendered(tmp_path):
    p = key_project(tmp_path, [lab('First', 'A', at=5.4), lab('Second', 'B', at=6.2)], dur=7.0)
    r = renderer(p)
    assert [lb['at'] for lb in r.labels] == pytest.approx([4.45, 4.7])
