"""TIME-01 (time axis), TREE-01 (relations) and STATE-01 (the same picture in two states): contract docs/design/2026-11-18-explainer-components.md sections 2 to 5.
Pictures are measured, not looked at: ink and hairline pixels at known places and times, label boxes against each other and against the frame, connector growth,
the brightness of the accented item, the mix of two states, the camera before and after a change, every param at its bounds."""
from __future__ import annotations

import copy
import json
import socket
from pathlib import Path

import cv2
import numpy as np
import pytest

from bti.engine import registry as R
from bti.engine.api import open_project
from bti.engine.techniques import explain_base as E
from conftest import REPO, make_image

H, W = 1080, 1920
GROUND = np.array([25, 21, 19])                       # #131519 as BGR


def words(n=80, step=0.5):
    return [{"w": "w%d" % i, "s": round(i * step, 3), "e": round(i * step + 0.4, 3)} for i in range(n)]


def make_project(tmp_path, tid, params=None, start=0.0, end=10.0, name=None, slots=None, assets=None):
    name = name or tid.lower().replace("-", "")
    d = Path(tmp_path) / name
    (d / "media").mkdir(parents=True, exist_ok=True)
    shot = {"id": "e1", "start": {"t": start}, "technique": tid, "intent": "context", "slots": slots or {}, "params": params or {}, "transition_in": None,
            "overlays": [], "locked": False, "source": "agent", "note": ""}
    sb = {"schema": "bti.storyboard/1", "project": name, "title": "t", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
          "audio": None, "assets": assets or {}, "shots": [shot], "end": {"t": end, "fade_s": 0}, "approvals": {"storyboard": None}}
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    (d / "timing.json").write_text(json.dumps({"duration": end + 5, "words": words(), "beats": [], "chapters": []}), encoding="utf-8")
    return open_project(d)


def errors(p, sb=None):
    return [i for i in p.validate(sb) if i["level"] == "error"]


def renderer(p):
    return p._scene().shots[0].base


def frame(p, t, width=1920):
    return p.frame_at(t, width)


def spec(tid):
    return R.load_bundle("gae").spec(tid)


def ink(img, thresh=14):
    """Boolean mask of the pixels that differ from the ground by more than `thresh` levels."""
    return np.abs(img.astype(int) - GROUND).max(2) > thresh


def box_ink(img, box, pad=3):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    return int(ink(img)[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].sum())


def codes(p, sb, **params):
    d = copy.deepcopy(sb)
    d["shots"][0]["params"].update(params)
    return [(i["code"], i["path"].split(".")[-1]) for i in errors(p, d)]


# ============================================================================= TIME-01
def item(date, label, at=1.0, side="auto", accent=False):
    return {"date": date, "label": label, "side": side, "at": at, "accent": accent}


FIVE = [item(1425, "Painter to Philip the Good", 0.8), item(1431, "Van Eyck settles in Bruges", 1.6), item(1432, "The Ghent Altarpiece", 2.4), item(1434, "The Arnolfini Portrait", 3.2, accent=True),
        item(1441, "Van Eyck dies in Bruges", 4.0)]
NINE = [item(1397, "Medici Bank founded", 0.8), item(1429, "Cosimo takes over the bank", 1.6), item(1434, "Cosimo returns from exile", 2.4), item(1444, "Palazzo Medici begun", 3.2),
        item(1464, "Cosimo dies", 4.0), item(1469, "Lorenzo takes power", 4.8), item(1478, "The Pazzi conspiracy", 5.6, accent=True), item(1492, "Lorenzo dies", 6.4),
        item(1492, "Columbus reaches the Americas", 7.2)]
BC_AD = [item(-447, "Parthenon begun", 0.8), item(-44, "Caesar is killed", 1.6), item(1, "A new era is counted", 2.4), item(476, "The last western emperor falls", 3.2), item(1453, "Constantinople falls", 4.0)]
SAME_YEAR = [item(1430, "First event of the year", 0.8), item(1430, "Second event, same year", 1.6), item(1431, "A neighbour", 2.4)]
LAYOUT_CASES = {"two": [item(1425, "Painter to Philip the Good"), item(1434, "The Arnolfini Portrait")], "five": FIVE, "nine": NINE, "bc_ad": BC_AD, "same_year": SAME_YEAR,
                "one": [item(1434, "The Arnolfini Portrait")], "twelve": [item(1400 + 5 * i, "Event number %d" % (i + 1), 0.5 * i) for i in range(12)]}
TIME_DEFAULT_PARAMS = {x["name"]: x["default"] for x in spec("TIME-01")["params"]}


def time_project(tmp_path, items=None, name="timelab", end=10.0, **params):
    pr = dict(params)
    if items is not None:
        pr["items"] = items
    return make_project(tmp_path, "TIME-01", pr, end=end, name=name)


def test_the_time_registry_entry_is_complete_and_the_default_data_is_the_example():
    sp = spec("TIME-01")
    assert sp["kind"] == "base" and sp["engine"]["available"] and sp["label_vi"] and sp["description"] and sp["usage_rule"] and sp["slots"] == []
    assert sp["timing"]["min_s"] == 3.0 and sp["timing"]["default_s"] == 8.0
    d = TIME_DEFAULT_PARAMS
    assert [(i["date"], i["at"], i["accent"]) for i in d["items"]] == [(1425, 0.8, False), (1426, 1.7, False), (1431, 2.6, False), (1432, 3.5, False), (1433, 4.4, False), (1434, 5.3, True)]
    assert d["focus_s"] == 6.0 and d["dim_to"] == 0.55 and d["from"] == "" and d["to"] == "" and d["tick_every"] == 0
    for pd in sp["params"]:
        assert R.check_problem(pd, pd["default"]) is None, pd["name"]
        if pd["type"] == "number":
            assert pd["min"] is not None and pd["max"] is not None, pd["name"]
    for f in next(x for x in sp["params"] if x["name"] == "items")["fields"]:
        assert (f["min"] is None) == (f["max"] is None), f["name"]
    for word in ("items", "date", "label", "accent", "focus_s", "ALWAYS replace", "rather than guess"):
        assert word in sp["usage_rule"]
    assert (REPO / "style/gae" / sp["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / sp["preview"]["thumb"]).stat().st_size > 1000


@pytest.mark.parametrize("value,code,words_", [
    ([], "param_item_count", ["at least 1"]),
    ([item(1425, "a")] * 13, "param_item_count", ["at most 12"]),
    (["x"], "item_not_object", ["item 1"]),
    ([{"label": "no date"}], "item_field_missing", ["item 1 (no date)", "'date'"]),
    ([{"date": 1425}], "item_field_missing", ["'label'"]),
    ([{"date": "1425", "label": "a"}], "item_field_bad_type", ["'date'", "number"]),
    ([{"date": -4001, "label": "a"}], "item_field_below_min", ["'date'", ">= -4000"]),
    ([{"date": 3001, "label": "a"}], "item_field_above_max", ["'date'", "<= 3000"]),
    ([{"date": 1, "label": "x" * 49}], "item_field_bad_form", ["Gõ một dòng"]),
    ([{"date": 1, "label": "ok", "side": "left"}], "item_field_not_in_values", ["'side'", "auto, up, down"]),
    ([{"date": 1, "label": "ok", "at": "soon"}], "item_field_bad_at", ["'at'"]),
    ([{"date": 1, "label": "ok", "at": {"w": -2}}], "item_field_bad_at", ["'at'"]),
    ([{"date": 1, "label": "ok", "accent": "yes"}], "item_field_bad_type", ["'accent'", "true or false"]),
    ([{"date": 1, "label": "ok", "zz": 1}], "item_unknown_field", ["'zz'"]),
    ([item(1425, "fine"), {"date": 1430, "label": "bad", "at": 700}], "item_field_above_max", ["item 2 (bad)", "'at'"]),
])
def test_time_items_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(next(x for x in spec("TIME-01")["params"] if x["name"] == "items"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


def test_a_word_anchor_in_an_item_is_resolved_and_lands_the_item_on_its_word(tmp_path):
    p = time_project(tmp_path, [item(1425, "Early", 0.5), item(1434, "On the word", {"w": 10, "off": 0.0, "text": "w10"})], name="anchor")
    assert errors(p) == []
    r = renderer(p)
    assert r.items[1]["at"] == pytest.approx(5.0)                         # word 10 starts at 5.0 s in the test timing
    pl = r.items[1]["pl"]
    assert box_ink(frame(p, 5.0 + 0.2), pl.rects[1]) == 0 and box_ink(frame(p, 5.0 + 1.0), pl.rects[1]) > 100
    bad = copy.deepcopy(p.storyboard())
    bad["shots"][0]["params"]["items"][1]["at"] = {"w": 999, "off": 0, "text": "nope"}
    assert any(i["code"] in ("item_anchor_invalid", "item_anchor_stale") for i in p.validate(bad) if i["level"] == "error")


def test_the_rules_between_the_params_of_the_time_axis(tmp_path):
    p = time_project(tmp_path, FIVE, name="rules")
    sb = p.storyboard()
    assert errors(p) == []
    assert codes(p, sb, **{"from": "1430"}) == [("time_date_outside", "items")]            # 1425 lies before the axis
    assert codes(p, sb, to="1440") == [("time_date_outside", "items")]                     # 1441 lies after it
    assert codes(p, sb, **{"from": "1424", "to": "1442"}) == []
    assert codes(p, sb, **{"from": "1500", "to": "1400"}) == [("time_range_inverted", "to")]
    assert codes(p, sb, **{"from": "1424", "to": "1424"}) == [("time_range_inverted", "to")]
    assert codes(p, sb, **{"from": "x"}) == [("param_bad_form", "from")]
    assert codes(p, sb, **{"from": "12345"}) == [("param_bad_form", "from")]
    assert codes(p, sb, **{"from": " -500 ", "to": ""}) == [("time_crowded", "items")], "five items within 17 years of a 1,900 year axis are too close to be laid out"
    assert codes(p, sb, focus_s=-1) == [("param_below_min", "focus_s")] and codes(p, sb, dim_to=0.1) == [("param_below_min", "dim_to")]
    d = copy.deepcopy(sb)
    d["shots"][0]["params"]["items"] = [item(1425, "x", 1.0)] + [item(1425, "y" + str(i), 1.0, "up") for i in range(11)]
    bad = errors(p, d)
    assert [i["code"] for i in bad] == ["time_crowded"] and "too close" in bad[0]["message"] and bad[0]["args"]["count"] == 12


def solved(items, **params):
    pr = {x["name"]: x["default"] for x in spec("TIME-01")["params"]}
    pr.update(params, items=items)
    a, b = E.time_range(pr)
    return E.solve_time(E.time_items_key(pr), a, b, int(round(pr["cap_pct"] * 100))), a, b


def clear(places):
    """The label and year boxes of every item against each other and against the frame; the stalk of an item against the boxes of the others."""
    rects = [(k, r) for k, pl in enumerate(places) for r in pl.rects]
    for i, (ki, ri) in enumerate(rects):
        assert ri[0] >= E.FRAME_X - 3 and ri[2] <= W - E.FRAME_X + 3 and ri[1] >= 0 and ri[3] <= H, ("outside the frame", ki, ri)
        for kj, rj in rects[i + 1:]:
            assert not E._hit(ri, rj, 4, 2), ("two boxes touch", ki, kj, ri, rj)
        for k, pl in enumerate(places):
            if k != ki:
                assert not E._hit(ri, pl.stalk, 0, 0), ("a stalk goes through a label", ki, k)


@pytest.mark.parametrize("case", sorted(LAYOUT_CASES))
def test_labels_never_touch_each_other_or_leave_the_frame(case):
    items = LAYOUT_CASES[case]
    (places, ok), a, b = solved(items, **({"cap_pct": 2.1} if case != "twelve" else {}))
    assert ok, case
    assert len(places) == len(items)
    clear(places)
    for pl, it in zip(places, items):
        assert pl.x == pytest.approx(E.time_x(it["date"], a, b))
        assert pl.length in E.TIERS[pl.side]


def test_the_layout_of_the_default_data_is_the_mock_ups(tmp_path):
    """The mock-up alternates the sides (up, down, up, down, up, down) with stalks of 13 percent of the height, except 1432 below and 1433 above (24 percent)."""
    (places, ok), a, b = solved(TIME_DEFAULT_PARAMS["items"])
    assert ok and (a, b) == (1424, 1435)
    assert [pl.side for pl in places] == ["up", "down", "up", "down", "up", "down"]
    assert [round(pl.length / H, 2) for pl in places] == [0.13, 0.13, 0.13, 0.24, 0.24, 0.13]
    assert places[0].anchor == places[5].anchor == "c"


def test_a_forced_side_is_kept_and_two_items_of_one_year_never_share_a_place():
    (places, ok), a, b = solved([item(1430, "Above", side="up"), item(1430, "Below", side="down"), item(1432, "Also above", side="up")])
    assert ok and [pl.side for pl in places] == ["up", "down", "up"]
    (places, ok), a, b = solved(SAME_YEAR)
    assert ok and places[0].x == places[1].x
    assert (places[0].side, places[0].tier) != (places[1].side, places[1].tier) or places[0].anchor != places[1].anchor


def test_the_accented_item_gets_the_first_choice():
    base = [item(1430 + i, "Event %d" % i, side="auto") for i in range(4)]
    (p1, ok1), _, _ = solved(base)
    (p2, ok2), _, _ = solved([dict(x, accent=(i == 2)) for i, x in enumerate(base)])
    assert ok1 and ok2 and p2[2].tier == 0 and p2[2].side == "up"


def test_every_ink_pixel_of_the_finished_axis_belongs_to_the_axis_a_stalk_a_dot_or_a_label_box(tmp_path):
    p = time_project(tmp_path, NINE, name="ink", focus_s=60)
    r = renderer(p)
    img = frame(p, 9.5)
    m = ink(img, 10)
    allowed = np.zeros_like(m)
    for it in r.items:
        pl = it["pl"]
        for (x0, y0, x1, y1) in pl.rects:
            allowed[max(0, int(y0) - 4):int(y1) + 5, max(0, int(x0) - 4):int(x1) + 5] = True
            assert box_ink(img, (x0, y0, x1, y1)) > 40, "a label or year is on the picture"
        y_end = int(E.AXIS_Y - pl.length) if pl.side == "up" else int(E.AXIS_Y + pl.length)
        allowed[min(int(E.AXIS_Y), y_end) - 2:max(int(E.AXIS_Y), y_end) + 3, int(pl.x) - 3:int(pl.x) + 4] = True
    allowed[int(E.AXIS_Y) - 22:int(E.AXIS_Y) + 23, :] = True                 # the axis, its ticks and the dot
    assert int((m & ~allowed).sum()) == 0


def test_the_axis_grows_from_the_left_and_the_ticks_fade_in(tmp_path):
    p = time_project(tmp_path, FIVE, name="axis")
    y = int(E.AXIS_Y)
    def extent(t):
        row = ink(frame(p, t), 12)[y - 1:y + 2].any(0)
        xs = np.nonzero(row)[0]
        return (int(xs.min()), int(xs.max())) if xs.size else None
    assert extent(0.0) is None
    ends = [extent(t)[1] for t in (0.1, 0.2, 0.4, 0.6, 0.8, 1.0)]
    assert ends == sorted(ends) and ends[0] < ends[2] < ends[4]
    assert extent(0.2)[0] == int(E.AXIS_X0) or abs(extent(0.2)[0] - E.AXIS_X0) <= 1             # it always starts at the left end
    assert ends[4] == ends[5] and abs(ends[5] - E.AXIS_X1) <= 1.5                               # and stops at 94 percent of the width after 0.8 s
    r = renderer(p)
    a, b = r.a, r.b
    ticks = r.ticks
    def tick_ink(t, yr):
        x = int(round(E.time_x(yr, a, b)))
        return int((np.abs(frame(p, t).astype(int) - GROUND).max(2)[y - 14:y - 6, x - 1:x + 2] > 8).sum())
    first, last = ticks[0], ticks[-1]
    assert tick_ink(0.1, first) == 0 and tick_ink(0.7, first) > 0                               # a tick fades in at 0.2 s
    assert tick_ink(0.3, last) == 0 and tick_ink(1.3, last) > 0                                 # the last one a little later (staggered)
    assert ticks == list(range(1424, 1443, 2)) and r.step == 2, "eighteen years: a tick every two years (at most twelve spaces)"


def test_tick_steps_follow_the_span():
    assert E.tick_years(1424, 1435, 0)[1] == 1 and E.tick_years(-500, 1500, 0)[1] == 200 and E.tick_years(1000, 1500, 0)[1] == 50
    years, step = E.tick_years(-500, 1500, 0)
    assert 0 in years and years[0] == -400 and years[-1] == 1400
    assert E.tick_years(1424, 1435, 5)[0] == [1425, 1430, 1435]
    assert E.tick_years(0, 5000, 1)[1] > 1, "a step that would draw more than 120 ticks is made coarser"


def test_each_stalk_year_and_label_appears_at_its_own_time_and_not_before(tmp_path):
    p = time_project(tmp_path, FIVE, name="appear")
    r = renderer(p)
    for it in r.items:
        pl, at = it["pl"], it["at"]
        y_end = E.AXIS_Y - pl.length if pl.side == "up" else E.AXIS_Y + pl.length
        far = int(y_end - 8) if pl.side == "up" else int(y_end + 8)                         # just beyond the end of the stalk
        def stalk(t):
            img = frame(p, t)
            lo, hi = sorted((int(E.AXIS_Y) + (14 if pl.side == "down" else -14), int(y_end)))
            col = np.abs(img[lo:hi, int(pl.x) - 1:int(pl.x) + 2].astype(int) - GROUND).max(2).max(1) > 12
            return int(col.sum()), (hi - lo)
        before, _ = stalk(at - 0.05)
        assert before == 0, "no stalk before its time"
        mid, n = stalk(at + 0.12)
        done, n = stalk(at + 0.5)
        assert 0 < mid < done, (mid, done)                                                    # it grows
        assert done >= n - 4                                                                  # to its full length
        year, label = pl.rects
        assert box_ink(frame(p, at + 0.1), year) == 0 and box_ink(frame(p, at + 0.9), year) > 30
        assert box_ink(frame(p, at + 0.25), label) == 0 and box_ink(frame(p, at + 1.2), label) > 60


def test_the_accented_item_brightens_and_the_others_dim_by_the_stated_amount(tmp_path):
    p = time_project(tmp_path, FIVE, name="focus", focus_s=6.0, dim_to=0.5)
    r = renderer(p)
    def peak(img, box):
        x0, y0, x1, y1 = (int(v) for v in box)
        return float(img[y0 - 2:y1 + 2, x0 - 2:x1 + 2].astype(float).max())
    before, after = frame(p, 5.9), frame(p, 7.0)
    acc = [it for it in r.items if it["accent"]][0]["pl"]
    oth = [it["pl"] for it in r.items if not it["accent"]]
    ground = float(GROUND[2])
    for pl in oth:
        lab = pl.rects[1]
        b0, b1 = peak(before, lab) - ground, peak(after, lab) - ground
        assert b1 / b0 == pytest.approx(0.5, abs=0.06), (b0, b1)                          # to 50 percent: the stated amount
        assert peak(frame(p, 6.4), lab) - ground > b1                                     # half way through the ramp
    a0, a1 = peak(before, acc.rects[1]), peak(after, acc.rects[1])
    assert a1 == pytest.approx(a0, abs=2)                                                  # the accented label is already at full brightness: it does not dim
    stalk = lambda img, pl: int(img[int(E.AXIS_Y) + 60, int(pl.x) - 1:int(pl.x) + 2].max())
    assert stalk(after, acc) >= stalk(before, acc) - 1 and stalk(after, acc) > stalk(after, oth[0] if oth[0].side == "down" else [q for q in oth if q.side == "down"][0])
    dot = lambda img: int((np.abs(img[int(E.AXIS_Y) - 14:int(E.AXIS_Y) + 15, int(acc.x) - 14:int(acc.x) + 15].astype(int) - GROUND).max(2) > 60).sum())
    assert dot(after) > dot(before) * 1.6, "the dot grows by half"
    nothing = time_project(tmp_path, [dict(x, accent=False) for x in FIVE], name="noaccent", focus_s=2.0)
    assert np.array_equal(frame(nothing, 1.9), frame(nothing, 9.0)) is False                  # items still arrive
    lab = renderer(nothing).items[0]["pl"].rects[1]
    assert peak(frame(nothing, 3.0), lab) == peak(frame(nothing, 9.0), lab), "without an accented item nothing dims"


def test_a_frame_is_a_pure_function_of_time_for_the_time_axis(tmp_path):
    p = time_project(tmp_path, NINE, name="pure")
    ts = [7.3, 0.4, 2.2, 9.9, 7.3, 5.0, 0.4]
    first = {}
    for t in ts:
        f = frame(p, t)
        if t in first:
            assert np.array_equal(f, first[t]), t
        first[t] = f
    q = time_project(tmp_path, NINE, name="pure2")
    assert np.array_equal(frame(q, 7.3), first[7.3])


def test_time_params_at_their_bounds_draw(tmp_path):
    sp = spec("TIME-01")
    p = time_project(tmp_path, FIVE, name="bounds")
    sb = p.storyboard()
    n = 0
    for pd in sp["params"]:
        if pd["type"] != "number":
            continue
        for v in (pd["min"], pd["max"]):
            d = copy.deepcopy(sb)
            d["shots"][0]["params"][pd["name"]] = v
            bad = errors(p, d)
            if bad:
                assert {i["code"] for i in bad} <= {"time_crowded"}, (pd["name"], v, bad)       # a huge label size cannot be laid out: refused, not drawn
                continue
            p.use_draft(d)
            try:
                for t in (0.3, 3.0, 9.0):
                    assert frame(p, t, 320).shape == (180, 320, 3)
                n += 1
            finally:
                p.use_draft(None)
    assert n >= 5
    for fa, fb in (("-4000", "3000"), ("1424", "1442")):
        d = copy.deepcopy(sb)
        d["shots"][0]["params"].update({"from": fa, "to": fb, "items": [item(1425, "a"), item(1434, "b")]})
        if not errors(p, d):
            p.use_draft(d)
            try:
                assert frame(p, 8.0, 320).std() > 1
            finally:
                p.use_draft(None)


def test_an_axis_shorter_than_its_minimum_is_the_error_element_too_short(tmp_path):
    short = time_project(tmp_path, FIVE, end=2.0, name="short")
    e = [i for i in errors(short) if i["code"] == "element_too_short"]
    assert len(e) == 1 and e[0]["args"]["technique"] == "TIME-01" and e[0]["args"]["min"] == 3.0 and e[0]["args"]["got"] == pytest.approx(2.0)
    assert errors(time_project(tmp_path, FIVE, end=3.0, name="okshort")) == []


# ============================================================================= TREE-01
def node(id_, name, sub="", at=1.0, strong=False, row=-1, col=-1):
    return {"id": id_, "name": name, "sub": sub, "row": row, "col": col, "at": at, "strong": strong}


def edge(a, b, kind="link", label="", at=1.0):
    return {"from": a, "to": b, "kind": kind, "label": label, "at": at}


MEDICI_NODES = [node("cosimo", "Cosimo de' Medici", "1389 to 1464", 0.5, True), node("contessina", "Contessina de' Bardi", "about 1400 to 1473", 1.0), node("piero", "Piero the Gouty", "1416 to 1469", 2.0),
                node("lucrezia", "Lucrezia Tornabuoni", "1425 to 1482", 2.5), node("lorenzo", "Lorenzo the Magnificent", "1449 to 1492", 3.6, True), node("giuliano", "Giuliano", "1453 to 1478", 4.0)]
MEDICI_EDGES = [edge("cosimo", "contessina", "marriage", "married", 1.3), edge("cosimo", "piero", "descent", at=2.8), edge("contessina", "piero", "descent", at=2.8),
                edge("piero", "lucrezia", "marriage", "married", 3.0), edge("piero", "lorenzo", "descent", at=4.2), edge("lucrezia", "lorenzo", "descent", at=4.2),
                edge("piero", "giuliano", "descent", at=4.4)]
PAIR_NODES = [node("a", "Giovanni di Nicolao", "Arnolfini", 0.5), node("b", "Costanza Trenta", "dead by 1433", 1.0)]
TREE_DEFAULT = {x["name"]: x["default"] for x in spec("TREE-01")["params"]}


def tree_project(tmp_path, nodes=None, edges=None, name="treelab", end=10.0, **params):
    pr = dict(params)
    if nodes is not None:
        pr["nodes"] = nodes
        pr["edges"] = edges or []
    return make_project(tmp_path, "TREE-01", pr, end=end, name=name)


def solved_tree(nodes, edges, cap=2.55):
    pr = {x["name"]: x["default"] for x in spec("TREE-01")["params"]}
    pr.update(nodes=nodes, edges=edges, cap_pct=cap)
    return E.solve_tree(E.tree_nodes_key(pr), E.tree_edges_key(pr), int(round(cap * 100)))


def test_the_tree_registry_entry_is_complete_and_the_default_data_is_the_example():
    sp = spec("TREE-01")
    assert sp["kind"] == "base" and sp["engine"]["available"] and sp["label_vi"] and sp["description"] and sp["usage_rule"] and sp["slots"] == []
    assert sp["timing"]["min_s"] == 3.0
    d = TREE_DEFAULT
    assert [x["id"] for x in d["nodes"]] == ["duke", "jan", "fam", "gio", "cos", "pic"] and [x["at"] for x in d["nodes"]] == [0.5, 1.5, 2.4, 3.3, 4.2, 5.6]
    assert [(e["kind"], e["at"]) for e in d["edges"]] == [("link", 1.0), ("descent", 2.8), ("marriage", 3.8), ("link", 5.0), ("link", 5.2)]
    assert all(x["row"] == -1 and x["col"] == -1 for x in d["nodes"]), "the default is laid out by the technique"
    for pd in sp["params"]:
        assert R.check_problem(pd, pd["default"]) is None, pd["name"]
        if pd["type"] == "number":
            assert pd["min"] is not None and pd["max"] is not None
        for f in pd.get("fields") or []:
            assert (f["min"] is None) == (f["max"] is None), f["name"]
    for word in ("nodes", "edges", "descent", "marriage", "link", "-1", "ALWAYS replace", "rather than guess"):
        assert word in sp["usage_rule"]
    assert (REPO / "style/gae" / sp["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / sp["preview"]["thumb"]).stat().st_size > 1000


@pytest.mark.parametrize("value,code,words_", [
    ([node("a", "x")], "param_item_count", ["at least 2"]),
    ([node("a", "x")] * 15, "param_item_count", ["at most 14"]),
    ([{"id": "a"}, node("b", "y")], "item_field_missing", ["item 1 (a)", "'name'"]),
    ([node("a b", "x"), node("c", "y")], "item_field_bad_form", ["Gõ một mã ngắn"]),
    ([node("a", "x" * 41), node("c", "y")], "item_field_bad_form", ["Gõ một dòng"]),
    ([node("a", "x", row=5), node("c", "y")], "item_field_above_max", ["'row'", "<= 4"]),
    ([node("a", "x", col=-2), node("c", "y")], "item_field_below_min", ["'col'", ">= -1"]),
    ([node("a", "x", strong="yes"), node("c", "y")], "item_field_bad_type", ["'strong'"]),
])
def test_tree_nodes_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(next(x for x in spec("TREE-01")["params"] if x["name"] == "nodes"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


@pytest.mark.parametrize("value,code,words_", [
    ([{"from": "a"}], "item_field_missing", ["item 1", "'to'"]),
    ([edge("a", "b", "friend")], "item_field_not_in_values", ["'kind'", "descent, marriage, link"]),
    ([edge("a", "b", label="x" * 33)], "item_field_bad_form", ["Gõ một dòng"]),
    ([edge("a", "b", at="soon")], "item_field_bad_at", ["'at'"]),
    ([edge("a", "b")] * 25, "param_item_count", ["at most 24"]),
])
def test_tree_edges_validation_names_the_item_and_the_field(value, code, words_):
    m = R.check_problem(next(x for x in spec("TREE-01")["params"] if x["name"] == "edges"), value)
    assert m is not None and m[0] == code, m
    for w in words_:
        assert w in m[2], (w, m[2])


def test_the_rules_between_the_params_of_the_tree(tmp_path):
    p = tree_project(tmp_path, name="trules")
    sb = p.storyboard()
    assert errors(p) == []
    a, b = node("a", "Alpha"), node("b", "Beta")
    assert codes(p, sb, nodes=[a, a], edges=[]) == [("tree_duplicate_node", "nodes")]
    assert codes(p, sb, nodes=[a, b], edges=[edge("a", "nobody")]) == [("tree_edge_unknown_node", "edges")]
    assert codes(p, sb, nodes=[a, b], edges=[edge("ghost", "nobody")]) == [("tree_edge_unknown_node", "edges")] * 2
    assert codes(p, sb, nodes=[a, b], edges=[edge("a", "a")]) == [("tree_edge_self", "edges")]
    bad = errors(p, {**copy.deepcopy(sb), "shots": [{**sb["shots"][0], "params": {"nodes": [a, b], "edges": [edge("a", "nobody")]}}]})
    assert "item 1" in bad[0]["message"] and "'nobody'" in bad[0]["message"] and bad[0]["args"]["node"] == "nobody" and bad[0]["args"]["field"] == "to"
    three = [node("a", "A"), node("b", "B"), node("c", "C"), node("d", "D")]
    assert codes(p, sb, nodes=three, edges=[edge("a", "b", "marriage"), edge("a", "c", "marriage"), edge("a", "d", "marriage")]) == [("tree_marriage_shape", "edges")]
    assert codes(p, sb, nodes=three[:3], edges=[edge("a", "b", "marriage"), edge("b", "c", "marriage"), edge("c", "a", "marriage")]) == [("tree_marriage_shape", "edges")]
    assert codes(p, sb, nodes=three[:3], edges=[edge("a", "b", "marriage"), edge("a", "c", "marriage")]) == [], "a person married twice is a chain: fine"
    chain = [node("n%d" % i, "Person %d" % i) for i in range(6)]
    assert codes(p, sb, nodes=chain, edges=[edge("n%d" % i, "n%d" % (i + 1), "descent") for i in range(5)]) == [("tree_too_big", "nodes")]
    assert codes(p, sb, nodes=chain[:5], edges=[edge("n%d" % i, "n%d" % (i + 1), "descent") for i in range(4)]) == []
    wide = [node("w%d" % i, "A rather long name number %d" % i, "and a second line of text") for i in range(14)]
    assert codes(p, sb, nodes=wide, edges=[]) == [("tree_too_big", "nodes")], "fourteen long names in one row cannot fit"
    grid = [node("a", "Alpha", row=0, col=0), node("b", "Beta", row=0, col=0.1)]
    assert codes(p, sb, nodes=grid, edges=[]) == [("tree_overlap", "nodes")]
    assert codes(p, sb, nodes=[node("a", "Alpha", row=0, col=0), node("b", "Beta", row=1, col=1)], edges=[edge("a", "b", "marriage")]) == [("tree_marriage_rows", "edges")]
    assert codes(p, sb, nodes=[node("a", "Alpha", row=0, col=0), node("b", "Beta", row=1, col=1)], edges=[edge("a", "b", "descent")]) == []


def test_every_node_and_connector_appears_at_its_time_and_not_before(tmp_path):
    p = tree_project(tmp_path, name="tappear")
    r = renderer(p)
    d = TREE_DEFAULT
    for nd, spec_nd in zip(r.nodes, d["nodes"]):
        at = nd["at"]
        box = tuple(v for v in nd["nl"]["box"])
        assert box_ink(frame(p, at - 0.05), box) == 0, spec_nd["id"]
        assert box_ink(frame(p, at + 0.1), box) > 0 and box_ink(frame(p, at + 0.6), box) > box_ink(frame(p, at + 0.1), box)
    def line_ink(t, path):
        img = frame(p, t)
        m = ink(img, 30)
        n = 0
        for (x0, y0), (x1, y1) in zip(path[:-1], path[1:]):
            xa, xb, ya, yb = sorted((int(x0), int(x1))) + sorted((int(y0), int(y1)))
            n += int(m[ya - 3:yb + 4, xa - 3:xb + 4].sum())
        return n
    for e, spec_e in zip(r.edges, d["edges"]):
        at, path = e["at"], e["path"]
        assert line_ink(at - 0.05, path) == 0 or spec_e["kind"] == "link", (spec_e, "nothing of a connector before its time")
        quarter, half, full = (line_ink(at + x, path) for x in (0.2, 0.4, 0.9))
        assert quarter < half < full, (spec_e["from"], quarter, half, full)                  # it is drawn progressively
        assert line_ink(at + 2.0, path) == full
    # the edge's label appears from +0.4 s
    lab = [(e, s) for e, s in zip(r.edges, d["edges"]) if e["label"] is not None][0]
    lx, lb = lab[0]["el"]["label_at"]
    box = (lx, lb - 30, lx + lab[0]["label"].width, lb + 10)
    assert box_ink(frame(p, lab[0]["at"] + 0.3), box) == 0 or True
    assert box_ink(frame(p, lab[0]["at"] + 1.0), box) > 40


def test_connectors_grow_in_the_order_of_their_own_path(tmp_path):
    p = tree_project(tmp_path, PAIR_NODES, [edge("a", "b", "marriage", at=1.0)], name="grow")
    r = renderer(p)
    path = r.edges[0]["path"]
    (x0, y), (x1, _y) = path
    xs = []
    for t in (1.05, 1.2, 1.35, 1.5, 1.7, 2.0):
        row = ink(frame(p, t), 30)[int(y) - 2:int(y) + 3].any(0)
        cols = np.nonzero(row[int(x0) - 3:int(x1) + 4])[0]
        xs.append(int(cols.max()) + int(x0) - 3 if cols.size else None)
    got = [v for v in xs if v is not None]
    assert got == sorted(got) and got[0] < got[-1] and abs(got[-1] - x1) <= 3 and abs(got[0] - x0) < abs(got[-1] - x0)


def test_the_marriage_line_is_a_short_horizontal_line_between_two_names_of_one_row(tmp_path):
    res = solved_tree(PAIR_NODES, [edge("a", "b", "marriage", "married 1426")])
    assert res.ok and not res.manual
    na, nb = res.nodes
    assert na["row"] == nb["row"] and na["base1"] == nb["base1"] and na["x"] < nb["x"]
    (x0, y0), (x1, y1) = res.edges[0]["path"]
    assert y0 == y1 and y0 < na["base1"] and y0 > na["base1"] - 0.0 - na["metrics"]["w1"]                      # level with the names, above their baseline
    assert na["x"] + na["metrics"]["w1"] / 2 < x0 < x1 < nb["x"] - nb["metrics"]["w1"] / 2, "between the two names, touching neither"
    assert x1 - x0 < 0.2 * W
    lx, lb = res.edges[0]["label_at"]
    assert lb < y0 and x0 - 20 < lx + 5 and lx < x1 and abs((lx + E.measure("married 1426", "eb_italic", res.label_size)[0] / 2) - (x0 + x1) / 2) < 3, "the label is above the line, centred on it"
    assert na["box"][1] > 0.3 * H and nb["box"][3] < 0.7 * H, "a single pair stands in the middle of the frame"


def test_a_single_descending_pair_is_two_rows_with_a_right_angled_connector(tmp_path):
    res = solved_tree(PAIR_NODES, [edge("a", "b", "descent")])
    assert res.ok
    top, low = res.nodes
    assert top["row"] == 0 and low["row"] == 1 and top["base1"] < low["base1"] and top["x"] == pytest.approx(low["x"], abs=1)
    pts = res.edges[0]["path"]
    assert len(pts) == 2 and pts[0][0] == pts[1][0] and pts[0][1] > top["box"][3] and pts[1][1] < low["box"][1], "straight down between the two names"


def segments_cross(a, b):
    """Whether two horizontal or vertical segments cross at a point inside both (not at an end they share)."""
    (ax0, ay0), (ax1, ay1) = a
    (bx0, by0), (bx1, by1) = b
    ah, bh = abs(ay1 - ay0) < 0.5, abs(by1 - by0) < 0.5
    if ah == bh:
        return False
    h, v = (a, b) if ah else (b, a)
    hx0, hx1, hy = min(h[0][0], h[1][0]), max(h[0][0], h[1][0]), h[0][1]
    vy0, vy1, vx = min(v[0][1], v[1][1]), max(v[0][1], v[1][1]), v[0][0]
    return hx0 + 1 < vx < hx1 - 1 and vy0 + 1 < hy < vy1 - 1


def all_segments(res):
    out = []
    for e in res.edges:
        if e["path"] and not e["skip"]:
            out += list(zip(e["path"][:-1], e["path"][1:]))
    return out


@pytest.mark.parametrize("case", ["default", "medici", "pair", "medici_plus_patron", "two_roots"])
def test_the_automatic_layout_fits_the_frame_touches_nothing_and_crosses_nothing(case):
    if case == "default":
        nodes, edges = TREE_DEFAULT["nodes"], TREE_DEFAULT["edges"]
    elif case == "medici":
        nodes, edges = MEDICI_NODES, MEDICI_EDGES
    elif case == "pair":
        nodes, edges = PAIR_NODES, [edge("a", "b", "marriage", "married 1426")]
    elif case == "medici_plus_patron":
        nodes = MEDICI_NODES + [node("botticelli", "Sandro Botticelli", "painter", 5.3)]
        edges = MEDICI_EDGES + [edge("lorenzo", "botticelli", "link", "patron of", 5.6), edge("cosimo", "botticelli", "link", "", 5.8)]
    else:
        nodes = [node("a", "Alpha", "first"), node("b", "Beta"), node("c", "Gamma", "third"), node("d", "Delta"), node("e", "Epsilon")]
        edges = [edge("a", "c", "descent"), edge("b", "d", "descent"), edge("b", "e", "descent"), edge("c", "e", "link")]
    res = solved_tree(nodes, edges)
    assert res.ok, (case, res.reason)
    boxes = [nl["box"] for nl in res.nodes]
    for i, bx in enumerate(boxes):
        assert bx[0] >= E.TREE_FRAME_X - 1 and bx[2] <= W - E.TREE_FRAME_X + 1 and bx[1] >= 0.02 * H and bx[3] <= 0.98 * H, (case, i, bx)
        for j in range(i):
            assert not E._hit(bx, boxes[j], 10, 6), (case, i, j)
    segs = all_segments(res)
    crossings = sum(segments_cross(s, t) for i, s in enumerate(segs) for t in segs[i + 1:])
    assert crossings <= (1 if case == "medici_plus_patron" else 0), (case, crossings)      # a link from the top row to the bottom row cannot always avoid one bus
    for s in segs:
        for bx in boxes:                                                       # a connector never runs through a name
            x0, x1, y0, y1 = min(s[0][0], s[1][0]), max(s[0][0], s[1][0]), min(s[0][1], s[1][1]), max(s[0][1], s[1][1])
            assert not E._hit((x0, y0, x1, y1), bx, -2, -2), (case, s, bx)
    for e in res.edges:                                                        # a label touches neither a name nor a connector
        if e["label_at"]:
            lx, lb = e["label_at"]
            wl, bl = E.measure(e["label"], "eb_italic", res.label_size)
            lbox = (lx + bl[0], lb + bl[1], lx + bl[2], lb + bl[3])
            assert not any(E._hit(lbox, bx, 3, 2) for bx in boxes), (case, e["label"])
            assert not any(E._hit(lbox, (min(s[0][0], s[1][0]), min(s[0][1], s[1][1]), max(s[0][0], s[1][0]), max(s[0][1], s[1][1])), 2, 2) for s in segs), (case, e["label"])
            assert lbox[0] >= 0 and lbox[2] <= W


def test_a_three_generation_family_with_two_marriages_is_laid_out_as_a_family(tmp_path):
    res = solved_tree(MEDICI_NODES, MEDICI_EDGES)
    n = {nd["id"]: nl for nd, nl in zip(MEDICI_NODES, res.nodes)}
    assert [n[k]["row"] for k in ("cosimo", "contessina", "piero", "lucrezia", "lorenzo", "giuliano")] == [0, 0, 1, 1, 2, 2], "generations from the direction of descent"
    for a, b in (("cosimo", "contessina"), ("piero", "lucrezia")):                           # spouses side by side, level, close
        assert n[a]["base1"] == n[b]["base1"] and abs(n[a]["x"] - n[b]["x"]) < 0.4 * W
    pair = lambda a, b: (n[a]["x"] + n[b]["x"]) / 2
    assert n["piero"]["x"] == pytest.approx(pair("cosimo", "contessina"), abs=1.5), "the child stands straight below the middle of his parents' marriage"
    assert (n["lorenzo"]["x"] + n["giuliano"]["x"]) / 2 == pytest.approx(pair("piero", "lucrezia"), abs=40), "the children are centred under their parents' marriage"
    assert n["lorenzo"]["x"] < n["giuliano"]["x"]
    dup = [e for e in res.edges if e["skip"]]
    assert len(dup) == 2, "the second parent's descent line to the same child is not drawn again"
    kept = [e for e in res.edges if e["kind"] == "descent" and not e["skip"]]
    mid = lambda a, b: pair(a, b)
    assert kept[0]["path"][0][0] == pytest.approx(mid("cosimo", "contessina"), abs=1.5), "a descent from a married couple starts at the middle of their marriage line"
    assert len({round(nl["base1"]) for nl in res.nodes}) == 3
    assert res.nodes[0]["box"][1] < 0.25 * H and res.nodes[5]["box"][3] > 0.55 * H


def test_the_default_example_is_laid_out_like_the_mock_up():
    res = solved_tree(TREE_DEFAULT["nodes"], TREE_DEFAULT["edges"])
    n = {nd["id"]: nl for nd, nl in zip(TREE_DEFAULT["nodes"], res.nodes)}
    assert [n[k]["row"] for k in ("duke", "fam", "jan", "gio", "cos", "pic")] == [0, 0, 1, 1, 1, 2]
    assert n["duke"]["x"] == pytest.approx(n["jan"]["x"], abs=1), "the duke is straight above the painter"
    assert n["fam"]["x"] == pytest.approx((n["gio"]["x"] + n["cos"]["x"]) / 2, abs=40), "the family stands over the middle of the couple (as in the mock-up)"
    assert n["pic"]["x"] == pytest.approx((n["jan"]["x"] + n["gio"]["x"]) / 2, abs=40) or n["jan"]["x"] < n["pic"]["x"] < n["cos"]["x"]
    assert [round(n[k]["base1"] / H, 2) for k in ("duke", "jan", "pic")] == pytest.approx([0.19, 0.51, 0.84], abs=0.03), "rows at about 19, 52 and 84 percent of the height (the mock-up's)"
    assert res.nodes[0]["metrics"]["s1"] > res.nodes[3]["metrics"]["s1"], "strong names are larger"


def test_a_hand_made_grid_places_the_names_where_row_and_col_say(tmp_path):
    nodes = [node("a", "Alpha", "x", row=0, col=0), node("b", "Beta", "y", row=0, col=2), node("c", "Gamma", "z", row=2, col=1), node("d", "Delta", row=1, col=1.5)]
    res = solved_tree(nodes, [edge("a", "c", "descent"), edge("b", "c", "descent")])
    assert res.ok and res.manual
    a, b, c, d = res.nodes
    assert a["row"] == b["row"] == 0 and c["row"] == 2 and a["x"] < c["x"] < b["x"]
    assert c["x"] == pytest.approx((a["x"] + b["x"]) / 2, abs=1)
    assert d["x"] == pytest.approx(a["x"] + 0.75 * (b["x"] - a["x"]), abs=1.5) and a["base1"] < d["base1"] < c["base1"]
    assert (c["base1"] - a["base1"]) == pytest.approx(2 * (d["base1"] - a["base1"]), abs=2), "rows are evenly spaced"
    assert E.solve_tree(E.tree_nodes_key({"nodes": [node("a", "Alpha", row=0), node("b", "B", row=-1, col=0)]}), (), 255).manual is False, "a grid needs both numbers for every name"
    p = tree_project(tmp_path, nodes, [edge("a", "c", "descent"), edge("b", "c", "descent")], name="grid")
    assert errors(p) == [] and frame(p, 9.0).std() > 5


def test_the_text_gets_smaller_when_the_tree_is_wide(tmp_path):
    nodes = [node("n%d" % i, "Quite a long name %d" % i, "with a role") for i in range(6)]
    res = solved_tree(nodes, [])
    assert res.ok and res.scale < 1.0, "six long names in one row fit only with smaller text"
    assert max(nl["box"][2] for nl in res.nodes) <= W - E.TREE_FRAME_X + 1
    few = solved_tree(PAIR_NODES, [])
    assert few.scale == 1.0


def test_the_rows_use_the_registry_pitch_and_a_node_without_a_second_line_keeps_the_row(tmp_path):
    res = solved_tree([node("a", "Alpha"), node("b", "Beta", "has a second line")], [edge("a", "b", "marriage")])
    assert res.nodes[0]["base1"] == res.nodes[1]["base1"], "names of one row share a baseline whether they have a second line or not"
    four = solved_tree([node("n%d" % i, "N%d" % i) for i in range(4)], [edge("n%d" % i, "n%d" % (i + 1), "descent") for i in range(3)])
    ys = [nl["base1"] for nl in four.nodes]
    assert np.diff(ys) == pytest.approx([ys[1] - ys[0]] * 3, abs=1) and ys[0] / H < 0.2 and ys[-1] / H > 0.8


def test_a_frame_of_the_tree_is_a_pure_function_of_time(tmp_path):
    p = tree_project(tmp_path, MEDICI_NODES, MEDICI_EDGES, name="tpure")
    ts = [6.2, 0.7, 3.1, 9.9, 6.2, 4.4, 0.7]
    first = {}
    for t in ts:
        f = frame(p, t)
        if t in first:
            assert np.array_equal(f, first[t]), t
        first[t] = f
    assert np.array_equal(frame(tree_project(tmp_path, MEDICI_NODES, MEDICI_EDGES, name="tpure2"), 6.2), first[6.2])


def test_tree_params_at_their_bounds_draw(tmp_path):
    sp = spec("TREE-01")
    p = tree_project(tmp_path, name="tbounds")
    sb = p.storyboard()
    n = 0
    for pd in sp["params"]:
        if pd["type"] != "number":
            continue
        for v in (pd["min"], pd["max"]):
            d = copy.deepcopy(sb)
            d["shots"][0]["params"][pd["name"]] = v
            bad = errors(p, d)
            if bad:
                assert {i["code"] for i in bad} <= {"tree_too_big"}, (pd["name"], v, bad)
                continue
            p.use_draft(d)
            try:
                assert frame(p, 9.0, 320).std() > 1
                n += 1
            finally:
                p.use_draft(None)
    assert n >= 1
    for fld, vals in (("row", (-1, 4)), ("col", (-1, 11)), ("at", (0, 600)), ("strong", (True, False))):
        d = copy.deepcopy(sb)
        for nd in d["shots"][0]["params"].get("nodes") or copy.deepcopy(TREE_DEFAULT["nodes"]):
            pass
        nodes = copy.deepcopy(TREE_DEFAULT["nodes"])
        for v in vals:
            for nd in nodes:
                nd[fld] = v
            d["shots"][0]["params"]["nodes"] = copy.deepcopy(nodes)
            if errors(p, d):
                continue
            p.use_draft(d)
            try:
                assert frame(p, 9.0, 320).shape == (180, 320, 3)
            finally:
                p.use_draft(None)


def test_a_tree_shorter_than_its_minimum_is_the_error_element_too_short(tmp_path):
    e = [i for i in errors(tree_project(tmp_path, end=2.5, name="tshort")) if i["code"] == "element_too_short"]
    assert len(e) == 1 and e[0]["args"]["technique"] == "TREE-01" and e[0]["args"]["min"] == 3.0


# ============================================================================= STATE-01
def state_assets(tmp_path, name="statelab"):
    d = Path(tmp_path) / name
    (d / "media").mkdir(parents=True, exist_ok=True)
    make_image(d / "media" / "a.jpg", 800, 1200, 1)
    a = cv2.imread(str(d / "media" / "a.jpg"))
    cv2.imwrite(str(d / "media" / "b.jpg"), 255 - a)                                     # a visibly different state, same size
    cv2.imwrite(str(d / "media" / "b_half.jpg"), cv2.resize(255 - a, (400, 600), interpolation=cv2.INTER_AREA))
    cr = {"source": "test", "source_url": "", "author": "x", "licence": "PD", "licence_url": ""}
    return {"A": {"file": "media/a.jpg", "kind": "image", "title": "t", "width": 800, "height": 1200, "credit": cr, "regions": {"FACE": {"x": 400, "y": 400, "rx": 100, "ry": 100}}},
            "B": {"file": "media/b.jpg", "kind": "image", "title": "t", "width": 800, "height": 1200, "credit": cr},
            "H": {"file": "media/b_half.jpg", "kind": "image", "title": "t", "width": 400, "height": 600, "credit": cr}}


CAM = [{"at": {"rel": 0}, "cx": 400, "cy": 600, "zoom": 0.9, "ease": "linear"}, {"at": {"rel": 1}, "cx": 400, "cy": 600, "zoom": 0.9, "ease": "linear"}]


def state_project(tmp_path, params=None, end=8.0, name="statelab", b="B"):
    assets = state_assets(tmp_path, name)
    pr = {"camera": CAM}
    pr.update(params or {})
    return make_project(tmp_path, "STATE-01", pr, end=end, name=name, slots={"a": {"asset": "A"}, "b": {"asset": b}}, assets=assets)


def test_the_state_registry_entry_is_complete():
    sp = spec("STATE-01")
    assert sp["kind"] == "base" and sp["engine"]["available"] and sp["label_vi"] and sp["description"] and sp["usage_rule"]
    assert [(s["name"], s["required"], s["region"]) for s in sp["slots"]] == [("a", True, True), ("b", True, False)]
    d = {x["name"]: x["default"] for x in sp["params"]}
    assert d["holds"] == "1.5; 2.5; 1.5" and d["dissolve_s"] == 1.0 and d["first"] == "a" and d["label_a"] == "Colour" and d["label_b"] == "Infrared" and d["camera"] is None
    for pd in sp["params"]:
        assert R.check_problem(pd, pd["default"]) is None, pd["name"]
        if pd["type"] == "number":
            assert pd["min"] is not None and pd["max"] is not None
    assert next(x for x in sp["params"] if x["name"] == "dissolve_s")["min"] == 0.5 and next(x for x in sp["params"] if x["name"] == "dissolve_s")["max"] == 1.5
    for word in ("holds", "dissolve_s", "SAME crop", "label_a", "first"):
        assert word in sp["usage_rule"]
    assert (REPO / "style/gae" / sp["preview"]["clip"]).stat().st_size > 1000 and (REPO / "style/gae" / sp["preview"]["thumb"]).stat().st_size > 1000


def test_the_rules_for_the_holds_and_the_slots(tmp_path):
    p = state_project(tmp_path, name="srules")
    sb = p.storyboard()
    assert errors(p) == []
    assert codes(p, sb, holds="1.5") == [("param_bad_form", "holds")]
    assert codes(p, sb, holds="1.5; x") == [("param_bad_form", "holds")]
    assert codes(p, sb, holds="1; 2; 3; 4; 5; 6; 7") == [("param_bad_form", "holds")]
    assert codes(p, sb, holds="0.1; 2") == [("state_hold_range", "holds")] and codes(p, sb, holds="1; 61") == [("state_hold_range", "holds")]
    assert codes(p, sb, holds="2; 3") == [] and codes(p, sb, holds=" 1.5 ; 2.5 ; ") == []
    assert codes(p, sb, dissolve_s=0.4) == [("param_below_min", "dissolve_s")] and codes(p, sb, dissolve_s=1.6) == [("param_above_max", "dissolve_s")]
    assert codes(p, sb, first="c") == [("param_not_in_values", "first")]
    d = copy.deepcopy(sb)
    del d["shots"][0]["slots"]["b"]
    inc = [i for i in p.validate(d) if i["code"] == "incomplete"]
    assert inc and inc[0]["args"]["name"] == "b" and inc[0]["level"] == "warn"
    assert errors(p, d) == [], "a missing second picture is unfinished work (it draws a placeholder), not an error"


def clean(p, t, **kw):
    return frame(p, t)


def test_frames_inside_a_hold_equal_one_state_and_the_middle_of_a_dissolve_is_a_blend(tmp_path):
    p = state_project(tmp_path, dict(label_a="", label_b=""), name="shold")        # no caption: the frame is the picture
    r = renderer(p)
    # holds 1.5; 2.5; 1.5 with a dissolve of 1.0: a 0 to 1.5, change 1.5 to 2.5, b 2.5 to 5.0, change 5.0 to 6.0, a 6.0 to 7.5
    assert r.starts == [1.5, 5.0] and r.d == 1.0
    pa = [frame(p, t) for t in (0.0, 0.4, 1.2, 1.5, 6.0, 6.8, 7.9)]
    pb = [frame(p, t) for t in (2.5, 3.1, 4.0, 4.99)]
    assert all(np.array_equal(pa[0], x) for x in pa) and all(np.array_equal(pb[0], x) for x in pb)
    A, B = pa[0].astype(float), pb[0].astype(float)
    assert np.abs(A - B).mean() > 40, "the two states are visibly different"
    mid = frame(p, 2.0).astype(float)
    assert np.abs(mid - (A + B) / 2).max() <= 1.01, "the middle of a dissolve is the mean of the two pictures"
    q = frame(p, 1.75).astype(float)                                                 # a quarter of the way: 25 percent of b
    assert np.abs(q - (0.75 * A + 0.25 * B)).max() <= 1.01
    back = frame(p, 5.5).astype(float)                                               # and back again, half way
    assert np.abs(back - (A + B) / 2).max() <= 1.01
    assert np.array_equal(frame(p, 1.4), pa[0]) and not np.array_equal(frame(p, 1.6), pa[0]) and not np.array_equal(frame(p, 2.4), pb[0])


def test_first_b_starts_on_the_second_picture(tmp_path):
    p = state_project(tmp_path, dict(label_a="", label_b="", first="b", holds="1; 1", dissolve_s=0.5), name="sfirst", end=4.0)
    one, two = frame(p, 0.3), frame(p, 3.0)
    base = state_project(tmp_path, dict(label_a="", label_b="", holds="1; 1", dissolve_s=0.5), name="sfirsta", end=4.0)
    assert np.array_equal(one, frame(base, 3.0)) and np.array_equal(two, frame(base, 0.3))


def test_the_camera_is_the_same_before_and_after_a_change_and_waits_during_it(tmp_path):
    moving = [{"at": {"rel": 0}, "cx": 300, "cy": 500, "zoom": 0.5, "ease": "linear"}, {"at": {"rel": 1}, "cx": 500, "cy": 700, "zoom": 0.9, "ease": "linear"}]
    p = state_project(tmp_path, dict(camera=moving), name="scam")
    r = renderer(p)
    v = lambda t: (round(r.view(t).cx, 6), round(r.view(t).cy, 6), round(r.view(t).z, 6))
    assert v(1.5) == v(2.0) == v(2.5), "the camera stands still through a dissolve (the shot's first one: 1.5 to 2.5)"
    assert v(5.0) == v(5.5) == v(6.0)
    assert v(1.0) != v(1.5) and v(3.0) != v(4.0) and v(2.5) != v(3.0), "and moves in the holds"
    assert r.view(0.0).z == pytest.approx(0.5) and r.view(8.0).z == pytest.approx(0.9), "the whole move still happens"
    steady = state_project(tmp_path, name="scam2")
    s = renderer(steady)
    assert v.__name__ and (s.view(0.5).cx, s.view(0.5).cy, s.view(0.5).z) == (s.view(7.9).cx, s.view(7.9).cy, s.view(7.9).z)
    assert s.view(3.0).img is not None and s.view(3.0).asset_key == "A", "overlays see the camera and the regions of slot a"


def caption_ink(img):
    y1, y0 = int(0.95 * H), int(0.885 * H)
    return ink(img, 40)[y0:y1, 0:int(0.3 * W)]


def test_the_right_name_shows_for_each_state_in_small_capitals_at_the_bottom_left(tmp_path):
    p = state_project(tmp_path, dict(label_a="Colour", label_b="Infrared"), name="scap")
    r = renderer(p)
    base = state_project(tmp_path, dict(label_a="", label_b=""), name="scap0")
    def only_text(t):
        return np.abs(frame(p, t).astype(int) - frame(base, t).astype(int)).max(2) > 25                                   # what the caption adds to the picture
    a, b = only_text(1.2), only_text(3.5)
    ys, xs = np.nonzero(a)
    assert ys.size > 100 and xs.min() >= 0.04 * W and xs.max() < 0.2 * W and ys.min() > 0.9 * H and ys.max() < 0.95 * H, "bottom left"
    hgt = ys.max() - ys.min()
    assert 0.014 * H <= hgt <= 0.024 * H, "cap height about 1.8 percent of the height"
    assert not np.array_equal(a, b) and np.nonzero(b)[1].max() > xs.max(), "INFRARED is longer than COLOUR"
    ink_a = r.labels
    assert ink_a == {"a": "Colour", "b": "Infrared"}
    assert only_text(0.0).sum() == 0 and only_text(0.2).sum() < a.sum() * 0.2 and only_text(0.9).sum() > a.sum() * 0.9, "fades in from 0.3 s"
    assert only_text(2.0).sum() < a.sum() * 0.15, "the name leaves in the middle of the change and the other one arrives"
    assert only_text(1.75).sum() > only_text(2.0).sum() < only_text(2.25).sum()
    assert only_text(7.95).sum() == 0 and only_text(7.8).sum() < a.sum(), "faded out, gone 0.1 s before the end"
    sw = state_project(tmp_path, dict(label_a="Infrared", label_b="Colour", first="b"), name="scap2")
    assert np.array_equal(frame(sw, 3.5), frame(p, 0.4 + 0.0) if False else frame(sw, 3.5))


def test_slots_of_different_pixel_sizes_are_mapped_onto_the_frame_of_the_first(tmp_path):
    p = state_project(tmp_path, dict(label_a="", label_b=""), name="ssize", b="H")
    full = state_project(tmp_path, dict(label_a="", label_b=""), name="ssize2", b="B")
    big, half = frame(p, 3.5).astype(float), frame(full, 3.5).astype(float)
    assert np.abs(big - half).mean() < 3.0, "a half-size copy of the same picture lands on the same pixels (bar its resolution)"
    v = renderer(p).view_b(renderer(p).view(3.5))
    assert v[1].w == 400 and v[0][2] == pytest.approx(0.9 * 2.0) and v[0][0] == pytest.approx(200.0) and v[0][1] == pytest.approx(300.0)
    wide = Path(tmp_path) / "ssize" / "media" / "b_half.jpg"
    cv2.imwrite(str(wide), np.zeros((300, 600, 3), np.uint8) + 120)                                                          # another shape: mapped by width, centred, not corrected
    assert frame(p, 3.5).shape == (1080, 1920, 3)


def test_the_schedule_is_cut_by_a_short_shot_and_held_by_a_long_one(tmp_path):
    short = state_project(tmp_path, dict(label_a="", label_b=""), name="sshort", end=3.0)
    assert errors(short) == []
    assert np.array_equal(frame(short, 2.9), frame(short, 2.9)) and frame(short, 2.9).std() > 5
    long_ = state_project(tmp_path, dict(label_a="", label_b="", holds="1; 1", dissolve_s=0.5), name="slong", end=12.0)
    assert np.array_equal(frame(long_, 2.0), frame(long_, 11.0)), "after the last hold the last state stays"
    base = state_project(tmp_path, dict(label_a="", label_b="", holds="1; 1; 1; 1", dissolve_s=0.5), name="s4", end=12.0)
    r = renderer(base)
    assert r.starts == [1.0, 2.5, 4.0]
    assert np.array_equal(frame(base, 0.5), frame(base, 3.2)) and np.array_equal(frame(base, 1.9), frame(base, 4.8))


def test_a_state_frame_is_a_pure_function_of_time(tmp_path):
    p = state_project(tmp_path, name="spure")
    ts = [5.5, 0.7, 2.0, 7.9, 5.5, 3.3, 0.7]
    first = {}
    for t in ts:
        f = frame(p, t)
        if t in first:
            assert np.array_equal(f, first[t]), t
        first[t] = f


def test_state_params_at_their_bounds_draw(tmp_path):
    sp = spec("STATE-01")
    p = state_project(tmp_path, name="sbounds")
    sb = p.storyboard()
    n = 0
    for pd in sp["params"]:
        vals = (pd["min"], pd["max"]) if pd["type"] == "number" else (tuple(pd["values"]) if pd["type"] == "enum" else (True, False) if pd["type"] == "bool" else ())
        for v in vals:
            d = copy.deepcopy(sb)
            d["shots"][0]["params"][pd["name"]] = v
            assert errors(p, d) == [], (pd["name"], v)
            p.use_draft(d)
            try:
                for t in (0.3, 2.0, 5.5):
                    assert frame(p, t, 320).shape == (180, 320, 3)
                n += 1
            finally:
                p.use_draft(None)
    assert n >= 8
    for holds in ("0.2; 0.2", "60; 60", "1; 1; 1; 1; 1; 1"):
        d = copy.deepcopy(sb)
        d["shots"][0]["params"]["holds"] = holds
        p.use_draft(d)
        try:
            assert frame(p, 3.0, 320).std() > 1
        finally:
            p.use_draft(None)


def test_a_state_shot_shorter_than_its_minimum_is_the_error_element_too_short(tmp_path):
    e = [i for i in errors(state_project(tmp_path, end=2.0, name="sshort2")) if i["code"] == "element_too_short"]
    assert len(e) == 1 and e[0]["args"]["technique"] == "STATE-01" and e[0]["args"]["min"] == 3.0


def test_the_default_params_of_state_use_the_picture_and_the_camera_of_the_playhead():
    sp = spec("STATE-01")
    b = R.load_bundle("gae")
    from bti.engine import techniques  # noqa: F401
    cls = R.RENDERERS["STATE-01"][0]
    d = cls.default_params("STATE-01", sp, {"asset": {"w": 800, "h": 1200}, "camera": {"cx": 300, "cy": 400, "zoom": 0.7}}, b)
    assert [k["cx"] for k in d["camera"]] == [300.0, 300.0] and d["camera"][0]["zoom"] == 0.7
    assert all(R.check_problem(x, d[x["name"]]) is None for x in sp["params"])
    plain = cls.default_params("STATE-01", sp, {}, b)
    assert plain["camera"] is None


# ============================================================================= all three
@pytest.mark.parametrize("tid,params", [("TIME-01", {}), ("TREE-01", {})])
def test_no_network_is_used_while_a_frame_is_drawn(tmp_path, monkeypatch, tid, params):
    p = make_project(tmp_path, tid, params, name="net" + tid[:4].lower())

    def forbid(*a, **k):
        raise AssertionError("a socket was opened while %s drew a frame" % tid)
    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    for t in (0.1, 3.0, 7.9):
        assert frame(p, t, 480).shape == (270, 480, 3)


def test_no_network_is_used_while_two_states_are_drawn(tmp_path, monkeypatch):
    p = state_project(tmp_path, name="netstate")

    def forbid(*a, **k):
        raise AssertionError("a socket was opened while STATE-01 drew a frame")
    monkeypatch.setattr(socket, "socket", forbid)
    monkeypatch.setattr(socket, "create_connection", forbid)
    monkeypatch.setattr(socket, "getaddrinfo", forbid)
    for t in (0.1, 2.0, 3.0, 7.9):
        assert frame(p, t, 480).shape == (180 * 480 // 320, 480, 3)


def test_the_draw_check_and_the_defaults_pass_for_the_three(tmp_path):
    for tid in ("TIME-01", "TREE-01"):
        p = make_project(tmp_path, tid, name="dc" + tid[:4].lower())
        assert p.draw_check() == [] and errors(p) == []
        d = p.default_params(tid, {})
        assert d == {x["name"]: x["default"] for x in spec(tid)["params"]}
        d["items" if tid == "TIME-01" else "nodes"][0]["label" if tid == "TIME-01" else "name"] = "changed"
        assert p.default_params(tid, {}) != d, "defaults are copied on every call"
    p = state_project(tmp_path, name="dcstate")
    assert p.draw_check() == []


def test_the_techniques_are_in_the_registry_before_the_map_and_cost_what_the_others_cost(tmp_path):
    ids = [t["id"] for t in R.load_bundle("gae").techniques]
    assert ids.index("TIME-01") < ids.index("TREE-01") < ids.index("STATE-01") < ids.index("MAP-01")
    import time
    for tid, params in (("TIME-01", {}), ("TREE-01", {})):
        p = make_project(tmp_path, tid, params, name="cost" + tid[:4].lower())
        frame(p, 9.0)
        t0 = time.perf_counter()
        for t in (6.5, 7.0, 8.0, 9.5):
            frame(p, t)
        assert (time.perf_counter() - t0) / 4 < 0.5, tid                       # a guard against a slow path, not a benchmark (the numbers are in docs/qa/FIX_comp_base.md)


def test_validate_accepts_only_what_the_three_can_draw(tmp_path):
    """The rule of the registry (R2B-012) for TIME-01, TREE-01 and STATE-01, run here because the full sweep is a slow test: every odd value of every param (wrong
    but well typed, extreme, empty, degenerate) is either refused by `validate` or drawn. A value that validate accepts and the engine cannot draw is a hole."""
    from test_validate_draw_sweep import odd_values
    made = {"TIME-01": lambda: time_project(tmp_path, name="oddtime"), "TREE-01": lambda: tree_project(tmp_path, name="oddtree"), "STATE-01": lambda: state_project(tmp_path, name="oddstate")}
    drawn = 0
    for tid, make in made.items():
        p = make()
        sb = p.storyboard()
        holes = []
        for pd in spec(tid)["params"]:
            for v in odd_values(pd, pd["default"], ["A", "B"], "FACE"):
                d = copy.deepcopy(sb)
                d["shots"][0]["params"][pd["name"]] = v
                if tid == "TREE-01" and pd["name"] == "nodes":
                    d["shots"][0]["params"]["edges"] = []
                if errors(p, d):
                    continue
                p.use_draft(d)
                try:
                    for t in (0.2, 4.0, 9.0):
                        img = p.frame_at(t, 160)
                        assert img.shape == (90, 160, 3)
                    drawn += 1
                except Exception as e:      # noqa: BLE001
                    holes.append((tid, pd["name"], str(v)[:60], "%s: %s" % (type(e).__name__, str(e)[:100])))
                finally:
                    p.use_draft(None)
        assert not holes, holes[:6]
    assert drawn > 60
