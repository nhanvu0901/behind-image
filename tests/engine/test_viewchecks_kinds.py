"""Worker catalogue (2026-11-20): the viewer checks of what the `kinds` of a beat call for (`bti/engine/viewchecks.py`): `device_wrong_kind`, `device_too_little`,
`figure_on_wrong_picture`, `outside_on_painting`, `outside_picture_small`. Each is raised and not raised on made-up storyboards, and every one is silent on a beat that
has no `kinds` (a project made before the pictures step wrote them) and on a project with no picks.json at all.

The beats: six of 20 seconds (b0001 0-20 s ... b0006 100-120 s); the picks of a test say what each one is."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import words as make_words

import bti.engine.api  # noqa: F401  (registers the techniques)
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as VC
from bti.engine.timing import Timing

BUNDLE = R.load_bundle("gae")
NEW = {"device_wrong_kind", "device_too_little", "figure_on_wrong_picture", "outside_on_painting", "outside_picture_small"}


# ----------------------------------------------------------------------------------------------------------------- made-up documents
def asset(w, h, key="a", title="Test"):
    return {"file": "media/%s.jpg" % key, "kind": "image", "title": title, "artist": "Nobody", "year": "1999", "width": w, "height": h,
            "regions": {"FACE": {"x": w / 2, "y": h / 3, "rx": w / 10, "ry": w / 10, "label": "Face"}}}


def cam(*poses):
    n = len(poses)
    return [{"at": {"rel": round(i / (n - 1), 4)}, "cx": p[0], "cy": p[1], "zoom": p[2], "ease": "linear"} for i, p in enumerate(poses)]


def shot(i, t, tech="CAM-01", key="A", camera=None, overlays=None, params=None, slots=None):
    p = dict(params or {})
    if camera is not None:
        p["camera"] = camera
    return {"id": "s%d" % i, "start": {"t": t}, "technique": tech, "intent": "explore", "slots": slots if slots is not None else {"image": {"asset": key}},
            "params": p, "transition_in": None, "overlays": overlays or [], "locked": False, "source": "agent", "note": ""}


def overlay(oid, tech, t, dur, **params):
    return {"id": oid, "technique": tech, "intent": "isolate", "start": {"t": t}, "dur": dur, "params": params, "locked": False, "source": "agent", "note": ""}


def beats_of(n=6, each=20.0):
    return [{"id": "b%04d" % (k + 1), "chapter": "c01", "text": "t", "start": k * each, "end": (k + 1) * each, "w0": k * 50, "w1": (k + 1) * 50} for k in range(n)]


def picks_of(kinds=None, items=None, main="A", status=None):
    """`kinds`: {beat id: list}, `items`: {beat id: [(asset, role)]}; a beat with no `kinds` entry carries none."""
    beats = {}
    for b in beats_of():
        e = {"items": [{"asset": a, "region": None, "role": r, "note": ""} for a, r in (items or {}).get(b["id"], [("A", "detail")])], "status": (status or {}).get(b["id"], "picked"), "note": ""}
        if kinds and b["id"] in kinds:
            e["kinds"] = kinds[b["id"]]
        beats[b["id"]] = e
    return {"schema": "bti.picks/1", "main_asset": main, "assets": {}, "beats": beats, "approval": {"approved": True}}


def make(tmp_path, shots, *, picks="none", assets=None, end=120.0, each=20.0):
    d = tmp_path / "proj"
    (d / "media").mkdir(parents=True, exist_ok=True)
    from PIL import Image
    for k in ("a", "b", "c", "d"):
        Image.new("RGB", (64, 96), (120, 120, 120)).save(d / "media" / ("%s.jpg" % k))
    doc = {"schema": "bti.storyboard/1", "project": "proj", "style": "gae", "canvas": {"w": 1920, "h": 1080, "fps": 30}, "timing": "timing.json",
           "assets": assets or {"A": asset(1000, 1500, "a"), "B": asset(900, 700, "b", "An outside picture"), "C": asset(600, 400, "c", "A small engraving")},
           "shots": shots, "end": {"t": end}, "approvals": {"storyboard": None}}
    tm = Timing({"duration": end, "words": make_words(300, step=end / 300), "beats": beats_of(each=each)})
    pk = d / "picks.json"
    if picks == "none":
        if pk.exists():
            pk.unlink()
    else:
        pk.write_text(json.dumps(picks), encoding="utf-8")
    return doc, tm, d


def got(doc, tm, d, *names):
    out = [i for i in SB.validate(doc, tm, BUNDLE, d) if i["code"] in NEW]
    return [i for i in out if not names or i["code"] in names]


def codes(doc, tm, d):
    return sorted(i["code"] for i in got(doc, tm, d))


WIDE = cam((500, 750, 1.92), (500, 800, 1.92))


# ----------------------------------------------------------------------------------------------------------------- the fields of the codes
def test_the_new_codes_are_listed_hinted_and_warnings():
    assert NEW <= set(VC.CODES) and set(VC.CODES) == set(VC.HINTS)
    for code in NEW:
        assert code in SB.ISSUE_CODES and "(warning)" in VC.CODES[code] and "args:" in VC.CODES[code]


def test_every_issue_is_a_warning_with_args_and_a_hint_the_message_ends_with(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 40, "MAP-01", slots={}, params={"places": [{"id": "x", "name": "X", "lonlat": [3.2, 51.2]}]}), shot(3, 60, camera=WIDE)]
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0003": ["detail"]}))
    rows = got(doc, tm, d)
    assert {r["code"] for r in rows} == {"device_wrong_kind", "device_too_little"}
    for r in rows:
        assert r["level"] == "warn" and r["hint"] and r["message"].endswith(r["hint"]) and isinstance(r["args"], dict) and r["args"]["shot"] == "s2"


# ----------------------------------------------------------------------------------------------------------------- silence without kinds
DEVICE_SHOTS = [
    shot(1, 0, camera=WIDE),
    shot(2, 20, "MAP-01", slots={}, params={"places": [{"id": "x", "name": "X", "lonlat": [3.2, 51.2]}], "route": []}),
    shot(3, 40, "TIME-01", slots={}, params={"items": [{"date": 1425, "label": "a"}, {"date": 1426, "label": "b"}]}),
    shot(4, 60, camera=WIDE, overlays=[overlay("o1", "NUM-01", 61, 5, rows=[{"label": "x", "value": "3"}]), overlay("o2", "DOC-01", 66, 5, lit=[{"ref": "FACE"}]),
                                       overlay("o3", "KEY-01", 71, 5, labels=[{"text": "a", "ref": "FACE"}])]),
    shot(5, 80, "TREE-01", slots={}, params={"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]}),
    shot(6, 100, "LAY-01", slots={"left": {"asset": "A"}, "right": {"asset": "B"}}),
]


def test_a_project_with_no_picks_json_raises_nothing(tmp_path):
    doc, tm, d = make(tmp_path, DEVICE_SHOTS, picks="none")
    assert codes(doc, tm, d) == []


def test_a_project_whose_beats_carry_no_kinds_raises_nothing(tmp_path):
    doc, tm, d = make(tmp_path, DEVICE_SHOTS, picks=picks_of())
    assert codes(doc, tm, d) == []


def test_a_beat_without_kinds_is_not_judged_while_its_neighbour_is(tmp_path):
    doc, tm, d = make(tmp_path, DEVICE_SHOTS, picks=picks_of({"b0002": ["detail"]}))        # only the map's beat has kinds
    rows = got(doc, tm, d)
    assert {(r["code"], r["args"]["shot"]) for r in rows} == {("device_wrong_kind", "s2"), ("device_too_little", "s2")}


def test_unknown_words_are_no_kinds(tmp_path):
    doc, tm, d = make(tmp_path, DEVICE_SHOTS, picks=picks_of({"b0002": ["decoration"]}))
    assert codes(doc, tm, d) == []


# ----------------------------------------------------------------------------------------------------------------- device_wrong_kind
GOOD_PARAMS = {
    "MAP-01": {"places": [{"id": "x", "name": "X", "lonlat": [3.2, 51.2]}, {"id": "y", "name": "Y", "lonlat": [10.5, 43.8]}]},
    "TIME-01": {"items": [{"date": 1425, "label": "a"}, {"date": 1426, "label": "b"}, {"date": 1431, "label": "c"}]},
    "TREE-01": {"nodes": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}, {"id": "c", "name": "C"}]},
}
CASES = [  # technique, kind that calls for it, how it is placed
    ("MAP-01", "journey", "base"), ("TIME-01", "dates", "base"), ("TREE-01", "relations", "base"), ("LAY-01", "compare", "base"), ("X-CMP-01", "compare", "base"),
    ("NUM-01", "figure", "overlay"), ("DOC-01", "inscription", "overlay"), ("AN-03", "construction", "overlay"), ("AN-06", "construction", "overlay"),
]


def placed(tech, where, t=40.0):
    """A storyboard whose beat b0003 (40 to 60 s) holds the device: a base shot of its own, or an overlay on a wide shot of the painting."""
    if where == "base":
        slots = {"left": {"asset": "A"}, "right": {"asset": "B"}} if tech == "LAY-01" else {"anchor": {"asset": "A"}, "swap_1": {"asset": "B"}} if tech == "X-CMP-01" else {}
        return [shot(1, 0, camera=WIDE), shot(2, t, tech, slots=slots, params=GOOD_PARAMS.get(tech, {})), shot(3, 60, camera=WIDE)]
    params = {"NUM-01": {"rows": [{"label": "x", "value": "3"}]}, "DOC-01": {"lit": [{"ref": "FACE"}]}, "AN-03": {"vanishing_point": [500, 400]}, "AN-06": {}}[tech]
    return [shot(1, 0, camera=WIDE), shot(2, t, camera=WIDE, overlays=[overlay("o1", tech, t + 2, 6, **params)]), shot(3, 60, camera=WIDE)]


@pytest.mark.parametrize("tech,kind,where", CASES)
def test_a_device_on_a_line_that_does_not_call_for_it_is_flagged_and_on_one_that_does_it_is_not(tmp_path, tech, kind, where):
    doc, tm, d = make(tmp_path, placed(tech, where), picks=picks_of({"b0003": ["detail"]}))
    rows = got(doc, tm, d, "device_wrong_kind")
    assert [(r["args"]["technique"], r["args"]["shot"], r["args"]["needs"], r["args"]["kinds"], r["args"]["beats"]) for r in rows] == [(tech, "s2", [kind], ["detail"], ["b0003"])]
    assert (rows[0]["path"] == "shots[1]") == (where == "base") and (rows[0]["args"]["overlay"] == "o1") == (where == "overlay")
    ok_doc, ok_tm, ok_d = make(tmp_path / "ok", placed(tech, where), picks=picks_of({"b0003": [kind]}))
    assert got(ok_doc, ok_tm, ok_d, "device_wrong_kind") == []
    two_doc, two_tm, two_d = make(tmp_path / "two", placed(tech, where), picks=picks_of({"b0003": ["outside", kind]}))
    assert got(two_doc, two_tm, two_d, "device_wrong_kind") == []


def test_a_device_that_overlaps_two_beats_is_wrong_only_when_neither_calls_for_it(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 50, "MAP-01", slots={}, params=GOOD_PARAMS["MAP-01"]), shot(3, 70, camera=WIDE)]       # 10 s in b0003, 10 s in b0004
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0003": ["detail"], "b0004": ["journey"]}))
    assert got(doc, tm, d, "device_wrong_kind") == []
    doc, tm, d = make(tmp_path / "n", shots, picks=picks_of({"b0003": ["detail"], "b0004": ["whole"]}))
    assert [r["args"]["beats"] for r in got(doc, tm, d, "device_wrong_kind")] == [["b0003", "b0004"]]
    doc, tm, d = make(tmp_path / "half", shots, picks=picks_of({"b0003": ["detail"]}))           # b0004 has no kinds: not judged
    assert got(doc, tm, d, "device_wrong_kind") == []


def test_a_device_that_only_touches_a_beat_for_a_moment_does_not_belong_to_it(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 59.5, "MAP-01", slots={}, params=GOOD_PARAMS["MAP-01"]), shot(3, 80, camera=WIDE)]       # 0.5 s in b0003, 20 s in b0004
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0003": ["detail"], "b0004": ["journey"]}))
    assert got(doc, tm, d, "device_wrong_kind") == []


# ----------------------------------------------------------------------------------------------------------------- device_too_little
def test_a_map_needs_two_places_or_a_route(tmp_path):
    one = {"places": [{"id": "x", "name": "X", "lonlat": [3.2, 51.2]}], "route": []}
    for params, flagged in ((one, True), (GOOD_PARAMS["MAP-01"], False),
                            ({**one, "route": [{"from": "x", "to": "x", "via": ""}]}, False)):
        doc, tm, d = make(tmp_path / ("m%d" % len(json.dumps(params))), [shot(1, 0, camera=WIDE), shot(2, 40, "MAP-01", slots={}, params=params), shot(3, 60, camera=WIDE)], picks=picks_of({"b0003": ["journey"]}))
        rows = got(doc, tm, d, "device_too_little")
        assert bool(rows) is flagged, params
        if flagged:
            assert rows[0]["args"] == {"shot": "s2", "overlay": None, "technique": "MAP-01", "count": 1, "min": 2, "items": "places", "beats": ["b0003"]}


@pytest.mark.parametrize("tech,name,need,where", [("TIME-01", "items", 3, "base"), ("TREE-01", "nodes", 3, "base"), ("KEY-01", "labels", 3, "overlay")])
def test_a_time_axis_a_tree_and_a_key_need_three(tmp_path, tech, name, need, where):
    def doc_with(n, sub):
        if tech == "KEY-01":
            labels = [{"text": "l%d" % k, "ref": "FACE"} for k in range(n)]
            shots = [shot(1, 0, camera=WIDE), shot(2, 40, camera=WIDE, overlays=[overlay("o1", "KEY-01", 42, 6, labels=labels)]), shot(3, 60, camera=WIDE)]
        else:
            seq = [{"date": 1400 + 10 * k, "label": "x%d" % k} if tech == "TIME-01" else {"id": "n%d" % k, "name": "N%d" % k} for k in range(n)]
            shots = [shot(1, 0, camera=WIDE), shot(2, 40, tech, slots={}, params={name: seq}), shot(3, 60, camera=WIDE)]
        kinds = {"TIME-01": "dates", "TREE-01": "relations", "KEY-01": "detail"}[tech]
        return make(tmp_path / sub, shots, picks=picks_of({"b0003": [kinds]}))
    assert [r["args"]["count"] for r in got(*doc_with(need - 1, "few"), "device_too_little")] == [need - 1]
    assert got(*doc_with(need, "enough"), "device_too_little") == []


def test_too_little_is_judged_on_lines_that_carry_kinds_only(tmp_path):
    one = {"places": [{"id": "x", "name": "X", "lonlat": [3.2, 51.2]}], "route": []}
    doc, tm, d = make(tmp_path, [shot(1, 0, camera=WIDE), shot(2, 40, "MAP-01", slots={}, params=one), shot(3, 60, camera=WIDE)], picks=picks_of())
    assert got(doc, tm, d) == []


# ----------------------------------------------------------------------------------------------------------------- outside_on_painting
def outside_doc(tmp_path, shots, *, kinds=("outside",), items=None, status=None, picks=None):
    return make(tmp_path, shots, picks=picks if picks is not None else picks_of({"b0002": list(kinds)}, {"b0002": items if items is not None else [("A", "detail"), ("B", "context")]}, status=status))


def test_a_line_about_something_outside_that_stays_on_the_painting_is_flagged(tmp_path):
    doc, tm, d = outside_doc(tmp_path, [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 40, camera=WIDE)])
    rows = got(doc, tm, d, "outside_on_painting")
    assert [(r["args"]["beat"], r["args"]["assets"], r["args"]["seconds"], r["args"]["beat_seconds"], r["args"]["share"], r["args"]["shot"]) for r in rows] == [("b0002", ["B"], 0.0, 20.0, 0.0, "s2")]
    assert rows[0]["path"] == "shots[1]"


@pytest.mark.parametrize("seconds,flagged", [(8.0, True), (8.9, True), (9.0, False), (9.9, False), (14.0, False), (20.0, False)])
def test_the_outside_picture_must_be_on_screen_for_45_percent_of_a_beat_that_has_one_kind(tmp_path, seconds, flagged):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, "X-LAY-01", key="B"), shot(3, 20 + seconds, camera=WIDE)]
    if seconds >= 20:
        shots = [shot(1, 0, camera=WIDE), shot(2, 20, "X-LAY-01", key="B"), shot(3, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots)
    rows = got(doc, tm, d, "outside_on_painting")
    assert bool(rows) is flagged
    if flagged:
        assert rows[0]["args"]["limit"] == 0.45 and rows[0]["args"]["min_seconds"] == 3.5 and rows[0]["args"]["needed_seconds"] == 9.0
        assert "needs 45% of the line (9.0 seconds at the least)" in rows[0]["message"]


@pytest.mark.parametrize("seconds,flagged", [(4.0, True), (4.9, True), (5.0, False), (8.4, False)])
def test_a_beat_that_does_two_things_needs_the_outside_picture_for_a_quarter_of_it(tmp_path, seconds, flagged):
    """b0011 of the first run of the new rules (`detail`, `outside`): the picture came when the sentence reached the thing, 42% of the line, and that is right."""
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 20 + 20 - seconds, "X-LAY-01", key="B"), shot(4, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots, kinds=("detail", "outside"))
    rows = got(doc, tm, d, "outside_on_painting")
    assert bool(rows) is flagged
    if flagged:
        assert rows[0]["args"]["limit"] == 0.25 and rows[0]["args"]["needed_seconds"] == 5.0


def test_the_other_order_of_the_two_kinds_is_the_same_and_a_third_word_is_not_a_kind_the_check_knows(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 34, "X-LAY-01", key="B"), shot(4, 40, camera=WIDE)]       # 6 seconds of 20: 30%
    for kinds in (("outside", "detail"), ("whole", "outside"), ("outside", "journey")):
        doc, tm, d = outside_doc(tmp_path / "-".join(kinds), shots, kinds=kinds)
        assert got(doc, tm, d, "outside_on_painting") == [], kinds


@pytest.mark.parametrize("kinds,dur,share,need", [
    (["outside"], 20.0, 0.45, 9.0), (["detail", "outside"], 20.0, 0.25, 5.0), (["outside", "detail"], 14.1, 0.25, 3.525),
    (["outside"], 13.1, 0.45, 5.895), (["outside"], 7.0, 0.45, 3.5), (["detail", "outside"], 11.7, 0.25, 3.5), (["detail", "outside"], 8.0, 0.25, 3.5),
    (["outside"], 3.0, 0.45, 3.0), (["detail", "outside"], 2.0, 0.25, 2.0)])           # a beat shorter than 3.5 s needs the picture for all of it
def test_what_a_beat_needs_is_the_share_of_its_kinds_and_never_less_than_three_and_a_half_seconds(kinds, dur, share, need):
    s_, n_ = VC.outside_needed(kinds, dur)
    assert s_ == share and n_ == pytest.approx(need)


@pytest.mark.parametrize("kinds,seconds,flagged", [(("outside",), 3.5, True), (("outside",), 3.6, False), (("detail", "outside"), 3.4, True), (("detail", "outside"), 3.5, False)])
def test_a_short_beat_needs_the_picture_for_three_and_a_half_seconds_whatever_its_share(tmp_path, kinds, seconds, flagged):
    """Beats of 8 s (b0002 is 8-16 s): 45% is 3.6 s and 25% is 2 s, so the 3.5 s floor decides the second case."""
    shots = [shot(1, 0, camera=WIDE), shot(2, 8, "X-LAY-01", key="B"), shot(3, 8 + seconds, camera=WIDE), shot(4, 16, camera=WIDE)]
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0002": list(kinds)}, {"b0002": [("A", "detail"), ("B", "context")]}), each=8.0, end=48.0)
    assert bool(got(doc, tm, d, "outside_on_painting")) is flagged


def test_the_picture_in_a_panel_or_a_footage_slot_counts_as_on_screen(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, "LAY-01", slots={"left": {"asset": "A"}, "right": {"asset": "B"}}), shot(3, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots)
    assert got(doc, tm, d, "outside_on_painting") == []


def test_a_beat_whose_picture_was_not_found_stays_on_the_painting_without_a_warning(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots, items=[("A", "detail")])                                  # the plan's fallback only: nothing outside in the picks
    assert got(doc, tm, d, "outside_on_painting") == []
    doc, tm, d = outside_doc(tmp_path / "skip", shots, status={"b0002": "skip"})
    assert got(doc, tm, d, "outside_on_painting") == []


def test_only_a_line_of_kind_outside_is_judged_for_its_outside_picture(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots, kinds=("detail",))
    assert got(doc, tm, d, "outside_on_painting") == []
    doc, tm, d = outside_doc(tmp_path / "two", shots, kinds=("detail", "outside"))
    assert len(got(doc, tm, d, "outside_on_painting")) == 1


def test_a_map_or_a_compare_picture_of_a_line_is_not_its_outside_picture(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE), shot(3, 40, camera=WIDE)]
    doc, tm, d = outside_doc(tmp_path, shots, items=[("A", "detail"), ("B", "map"), ("C", "compare")])
    assert got(doc, tm, d, "outside_on_painting") == []


# ----------------------------------------------------------------------------------------------------------------- outside_picture_small
def small_doc(tmp_path, key, zoom, kinds=("outside",)):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, "X-LAY-01", key=key, camera=cam((450, 350, zoom), (450, 350, zoom))), shot(3, 40, camera=WIDE)]
    return make(tmp_path, shots, picks=picks_of({"b0002": list(kinds)}, {"b0002": [("A", "detail"), (key, "context")]}))


def test_the_default_fit_is_the_frames_height_or_width_and_a_small_picture_is_held_to_twice_its_size():
    assert VC.default_fit_zoom(900, 700) == pytest.approx(min(1920 / 900, 1080 / 700))
    assert VC.default_fit_zoom(2400, 1350) == pytest.approx(0.8) and VC.default_fit_zoom(1920, 2444) == pytest.approx(1080 / 2444)
    assert VC.default_fit_zoom(600, 400) == 2.0 and VC.default_fit_zoom(250, 334) == 2.0 and VC.default_fit_zoom(999, 999) == pytest.approx(1080 / 999)
    assert VC.outside_camera_problem([0.5, 0.6], 900, 700) == "small" and VC.outside_camera_problem([1.3, 1.6], 900, 700) is None
    assert VC.outside_camera_problem([1.0], 600, 400) == "small" and VC.outside_camera_problem([1.7, 2.0], 600, 400) is None
    assert VC.outside_camera_problem([1.7, 2.6], 600, 400) == "large" and VC.outside_camera_problem([3.5], 2400, 1350) is None
    assert VC.outside_camera_problem([], 900, 700) is None


@pytest.mark.parametrize("key,zoom,flagged", [("B", 0.3, True), ("B", 1.2, True), ("B", 1.26, False), ("B", 1.5, False), ("C", 1.2, True), ("C", 1.7, False)])
def test_an_outside_picture_drawn_under_80_percent_of_its_default_fit_is_flagged(tmp_path, key, zoom, flagged):
    doc, tm, d = small_doc(tmp_path, key, zoom)
    rows = got(doc, tm, d, "outside_picture_small")
    assert bool(rows) is flagged
    if flagged:
        a = rows[0]["args"]
        assert a["shot"] == "s2" and a["asset"] == key and a["zoom"] == zoom and a["limit"] == 0.8 and a["share"] < 0.8 and a["fit"] == round(VC.default_fit_zoom(*{"B": (900, 700), "C": (600, 400)}[key]), 3)


def test_the_painting_itself_and_a_line_without_kinds_are_never_judged_here(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, "X-LAY-01", key="A", camera=cam((500, 750, 0.3), (500, 750, 0.3))), shot(3, 40, camera=WIDE)]
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0002": ["outside"]}, {"b0002": [("A", "detail"), ("B", "context")]}))
    assert got(doc, tm, d, "outside_picture_small") == []                     # A is the painting
    doc, tm, d = small_doc(tmp_path / "nokinds", "B", 0.3, kinds=())
    assert got(doc, tm, d) == []


def test_an_outside_picture_in_a_panel_is_not_drawn_through_a_camera_param(tmp_path):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, "LAY-01", slots={"left": {"asset": "A"}, "right": {"asset": "B"}}), shot(3, 40, camera=WIDE)]
    doc, tm, d = make(tmp_path, shots, picks=picks_of({"b0002": ["compare"]}, {"b0002": [("A", "detail"), ("B", "compare")]}))
    assert got(doc, tm, d, "outside_picture_small") == []


# ----------------------------------------------------------------------------------------------------------------- figure_on_wrong_picture
def figure_doc(tmp_path, base_key, items, kinds=("figure",)):
    shots = [shot(1, 0, camera=WIDE), shot(2, 20, camera=WIDE, key=base_key, overlays=[overlay("o1", "NUM-01", 22, 6, rows=[{"label": "x", "value": "42"}])]), shot(3, 40, camera=WIDE)]
    return make(tmp_path, shots, picks=picks_of({"b0002": list(kinds)}, {"b0002": items}))


def test_a_figure_over_the_painting_when_the_picture_of_the_thing_counted_is_in_the_picks_is_flagged(tmp_path):
    doc, tm, d = figure_doc(tmp_path, "A", [("B", "context")])
    rows = got(doc, tm, d, "figure_on_wrong_picture")
    assert [(r["args"]["shot"], r["args"]["overlay"], r["args"]["asset"], r["args"]["assets"], r["args"]["beats"]) for r in rows] == [("s2", "o1", "A", ["B"], ["b0002"])]
    assert rows[0]["path"] == "shots[1].overlays[0]"


def test_a_figure_over_the_thing_counted_or_over_the_detail_of_a_figure_in_the_painting_is_not(tmp_path):
    doc, tm, d = figure_doc(tmp_path, "B", [("A", "detail"), ("B", "context")])
    assert got(doc, tm, d, "figure_on_wrong_picture") == []
    doc, tm, d = figure_doc(tmp_path / "in", "A", [("A", "detail")])                                      # the thing counted is in the painting
    assert got(doc, tm, d, "figure_on_wrong_picture") == []
    doc, tm, d = figure_doc(tmp_path / "none", "A", [("B", "context")], kinds=())                         # no kinds: silent
    assert got(doc, tm, d) == []
    doc, tm, d = figure_doc(tmp_path / "other", "A", [("B", "context")], kinds=("detail", "outside"))     # not a line of kind figure
    assert got(doc, tm, d, "figure_on_wrong_picture") == []


# ----------------------------------------------------------------------------------------------------------------- helpers
def test_outside_asset_keys_are_the_pictures_that_are_not_the_painting():
    pk = picks_of(items={"b0001": [("A", "main"), ("A", "detail")], "b0002": [("B", "context"), ("C", "map")], "b0003": [("D", "detail"), ("D", "context")], "b0004": [("E", "video")]})
    assert VC.outside_asset_keys(pk) == {"B", "C", "E"}, "D is also a detail of a line, so it is the painting"
    assert VC.outside_asset_keys({}) == set() and VC.outside_asset_keys(None) == set() and VC.outside_asset_keys({"beats": []}) == set()
