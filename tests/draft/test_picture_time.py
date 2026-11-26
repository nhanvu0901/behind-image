"""Tests for shot floor (2.5 s) and borrowed picture / MAP-01 minimum duration (3.0 s) in the draft compiler."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bti.draft.compile import compile_specs, summary_text
from bti.draft.inputs import load_inputs
from bti.engine.timing import Timing
from helpers import _image, clean_spec, shot, spec


def _make_multi_project(d: Path, *, lead_first: float = 0.4, beat2_start: float = 12.0, beat2_words: list[str] | None = None,
                        word_step: float = 0.5) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    _image(d / "media" / "a.jpg", 800, 1200)
    _image(d / "media" / "city.jpg", 640, 480, seed=2)
    _image(d / "media" / "fabric.jpg", 640, 480, seed=3)

    w_b1 = ["Before", "this", "scene", "we", "look", "inside", "the", "quiet", "room", "here."]
    w_b2 = beat2_words or [
        "Home", "was", "a", "trading", "port.",
        "The", "family", "came", "from", "another", "town", "and", "mixed", "trade", "with", "finance.",
        "They", "grew", "rich", "selling", "fine", "woven", "fabrics", "and", "precious", "objects.",
    ]
    w_b3 = ["Later", "on", "the", "painter", "signed", "the", "wooden", "panel", "above", "everything."]

    words = []
    t = lead_first
    for i, w in enumerate(w_b1):
        words.append({"w": w, "s": round(t, 3), "e": round(t + 0.4, 3)})
        t += 1.0
    b2_w0 = len(words)
    t = beat2_start
    for w in w_b2:
        words.append({"w": w, "s": round(t, 3), "e": round(t + max(0.2, word_step - 0.1), 3)})
        t += word_step
    b3_w0 = len(words)
    for w in w_b3:
        words.append({"w": w, "s": round(t, 3), "e": round(t + 0.4, 3)})
        t += 0.8

    beats = [
        {"id": "b0001", "chapter": "c01", "text": " ".join(w_b1), "start": words[0]["s"], "end": words[b2_w0]["s"], "w0": 0, "w1": b2_w0},
        {"id": "b0002", "chapter": "c01", "text": " ".join(w_b2), "start": words[b2_w0]["s"], "end": words[b3_w0]["s"], "w0": b2_w0, "w1": b3_w0},
        {"id": "b0003", "chapter": "c01", "text": " ".join(w_b3), "start": words[b3_w0]["s"], "end": round(words[-1]["e"] + 0.5, 3), "w0": b3_w0, "w1": len(words)},
    ]
    timing = {
        "duration": round(words[-1]["e"] + 0.5, 3),
        "words": words,
        "beats": beats,
        "chapters": [{"id": "c01", "name": "Origins", "start": 0.0, "end": round(words[-1]["e"] + 0.5, 3), "card": False}],
    }
    (d / "timing.json").write_text(json.dumps(timing), encoding="utf-8")

    picks = {
        "schema": "bti.picks/1",
        "main_asset": "A",
        "assets": {
            "A": {"file": "media/a.jpg", "kind": "image", "title": "Main Painting", "artist": "Painter", "year": "1434",
                  "width": 800, "height": 1200, "regions": {"ROOM": {"x": 400, "y": 500, "rx": 180, "ry": 180, "label": "Room"}}},
            "CITY": {"file": "media/city.jpg", "kind": "image", "title": "Port Map", "artist": "Cartographer", "year": "1570",
                     "width": 640, "height": 480},
            "FABRIC": {"file": "media/fabric.jpg", "kind": "image", "title": "Woven Silk", "artist": "Weaver", "year": "1450",
                       "width": 640, "height": 480},
        },
        "subjects": [
            {"id": "port", "kind": "place", "name": "trading port", "strip": False, "where": {"asset": "CITY"}},
            {"id": "route", "kind": "place", "name": "another town", "strip": False, "where": None},
            {"id": "silk", "kind": "thing", "name": "woven fabrics", "strip": False, "where": {"asset": "FABRIC"}},
        ],
        "beats": {
            "b0001": {"items": [{"asset": "A", "region": "ROOM", "role": "detail", "note": ""}], "kinds": ["detail"], "status": "picked"},
            "b0002": {
                "items": [
                    {"asset": "CITY", "region": None, "role": "context", "note": ""},
                    {"asset": "FABRIC", "region": None, "role": "context", "note": ""},
                ],
                "kinds": ["outside", "journey"],
                "about": [
                    {"id": "port", "words": "trading port"},
                    {"id": "route", "words": "another town"},
                    {"id": "silk", "words": "woven fabrics"},
                ],
                "status": "picked",
            },
            "b0003": {"items": [{"asset": "A", "region": "ROOM", "role": "detail", "note": ""}], "kinds": ["detail"], "status": "picked"},
        },
        "approval": {"approved": True},
    }
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    return d


def _shot_spans(inp, doc):
    tm = Timing({"duration": inp.timing["duration"], "words": inp.timing["words"]})
    ts = [tm.resolve(s["start"]) for s in doc["shots"]]
    end_t = tm.resolve(doc["end"])
    return [(s["id"], s["technique"], round(ts[i], 3), round((ts[i + 1] if i + 1 < len(ts) else end_t) - ts[i], 3)) for i, s in enumerate(doc["shots"])]


def test_agent_shot_floor_is_2_5s_while_opening_shot_keeps_1_6s(tmp_path):
    d = _make_multi_project(tmp_path, lead_first=1.95)          # opening shot s0000 = 1.95 - 0.35 = 1.60 s
    inp = load_inputs(d)
    # Shot 2 is an agent shot on main painting lasting 2.0 s (< 2.5 s) -> warns shot_short & pacing_short
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0001", 8, "STATIC-01", slots={"image": {"asset": "A"}}),
            shot("b0002", 10, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    res = compile_specs(inp, sp, draw=False)
    spans = _shot_spans(inp, res.storyboard)
    assert spans[0][0] == "s0000" and spans[0][3] == pytest.approx(1.6, abs=0.01)
    assert spans[2][3] == pytest.approx(2.05, abs=0.01)
    short_warns = [i for i in res.warnings if i["code"] == "shot_short"]
    assert len(short_warns) == 1 and short_warns[0]["args"]["shot"] == spans[2][0] and short_warns[0]["args"]["min"] == 2.5
    assert any(i["code"] == "pacing_short" for i in res.warnings)


def test_borrowed_picture_expands_back_to_sentence_start_from_previous_shot(tmp_path):
    # Main painting shot starts at 0.0 and runs past b0002 start (12.0 s) until word 13 (13.5 s);
    # CITY starts at word 13 (13.5 s) until word 16 (15.0 s) -> 1.5 s (1.6 s style flash!).
    # MAP-01 starts at word 16 (15.0 s) until word 27 (20.5 s) -> 5.5 s.
    # FABRIC starts at word 27 (20.5 s) until b0003 (25.0 s) -> 4.5 s.
    d = _make_multi_project(tmp_path, lead_first=0.4, beat2_start=12.0, word_step=0.5)
    inp = load_inputs(d)
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0002", 13, "X-LAY-01", slots={"image": {"asset": "CITY"}}),
            shot("b0002", 16, "MAP-01", slots={}, params={"places": [{"id": "a", "name": "Bruges", "lonlat": [3.2, 51.2]}, {"id": "b", "name": "Lucca", "lonlat": [10.5, 43.8]}], "route": [], "sea_names": False}),
            shot("b0002", 27, "X-LAY-01", slots={"image": {"asset": "FABRIC"}}),
            shot("b0003", 36, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    res = compile_specs(inp, sp, draw=False)
    assert not res.errors, summary_text(res)
    spans = _shot_spans(inp, res.storyboard)
    city = next(s for s in spans if s[1] == "X-LAY-01" and res.storyboard["shots"][spans.index(s)]["slots"]["image"]["asset"] == "CITY")
    assert city[2] == pytest.approx(12.0, abs=0.01)              # moved back to start of sentence ("Home was a trading port.")
    assert city[3] >= 3.0 - 1e-6
    assert spans[0][3] >= 2.5 - 1e-6                            # previous shot kept above the 2.5 s floor
    assert not any(i["code"] in ("outside_picture_brief", "outside_picture_dropped") for i in res.warnings)


def test_borrowed_picture_takes_time_from_after_when_previous_shot_is_locked(tmp_path):
    d = _make_multi_project(tmp_path, lead_first=0.4, beat2_start=12.0, word_step=0.5)
    inp = load_inputs(d)
    # Compile once to lock shot 1 up to 12.0 s, then put CITY at 12.0 for 1.5 s followed by a long shot
    base_sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0002", 10, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    sb0 = compile_specs(inp, base_sp, draw=False).storyboard
    sb0["shots"][0]["locked"] = True
    (d / "storyboard.json").write_text(json.dumps(sb0), encoding="utf-8")

    inp2 = load_inputs(d)
    sp2 = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0002", 10, "X-LAY-01", slots={"image": {"asset": "CITY"}}),
            shot("b0002", 13, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    res = compile_specs(inp2, sp2, draw=False)
    assert not res.errors, summary_text(res)
    spans = _shot_spans(inp2, res.storyboard)
    city = next(s for s in spans if s[1] == "X-LAY-01")
    assert city[2] == pytest.approx(12.0, abs=0.01)              # locked shot before could not shrink
    assert city[3] == pytest.approx(3.0, abs=0.02)               # borrowed 1.5 s from the shot after
    assert spans[2][3] >= 2.5 - 1e-6


def test_map_01_is_counted_and_line_too_short_drops_fewest_words_picture_with_warning(tmp_path):
    # b0002 is only 4.8 s (12 words * 0.4 s) — cannot hold two borrowed pictures at 3.0 s each
    short_words = ["Town", "here.", "Rich", "woven", "silk", "trade", "across", "many", "markets", "and", "guilds", "too."]
    d = _make_multi_project(tmp_path, lead_first=0.4, beat2_start=12.0, beat2_words=short_words, word_step=0.4)
    inp = load_inputs(d)
    # Adjust picks about so port has 2 words ("Town here.") and silk has 10 words
    picks = json.loads((d / "picks.json").read_text(encoding="utf-8"))
    picks["beats"]["b0002"]["about"] = [
        {"id": "port", "words": "Town here"},
        {"id": "silk", "words": "woven silk"},
    ]
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    inp = load_inputs(d)

    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0002", 10, "X-LAY-01", slots={"image": {"asset": "CITY"}}),
            shot("b0002", 14, "X-LAY-01", slots={"image": {"asset": "FABRIC"}}),
            shot("b0003", 22, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    res = compile_specs(inp, sp, draw=False)
    assert not res.errors, summary_text(res)
    dropped = [i for i in res.warnings if i["code"] == "outside_picture_dropped"]
    assert len(dropped) == 1 and dropped[0]["args"]["beat"] == "b0002"
    assets_kept = [s["slots"].get("image", {}).get("asset") for s in res.storyboard["shots"]]
    assert "CITY" not in assets_kept and "FABRIC" in assets_kept
    spans = _shot_spans(inp, res.storyboard)
    fab = next(s for s in spans if s[1] == "X-LAY-01")
    assert fab[3] >= 3.0 - 1e-6


def test_map_01_is_expanded_as_borrowed_shot(tmp_path):
    d = _make_multi_project(tmp_path, lead_first=0.4, beat2_start=12.0, word_step=0.5)
    inp = load_inputs(d)
    sp = {
        "c01": clean_spec(spec(
            "c01",
            shot("b0001", 0, "CAM-01", slots={"image": {"asset": "A", "region": "ROOM"}}),
            shot("b0002", 15, "MAP-01", slots={}, params={"places": [{"id": "a", "name": "Bruges", "lonlat": [3.2, 51.2]}, {"id": "b", "name": "Lucca", "lonlat": [10.5, 43.8]}], "route": [], "sea_names": False}),
            shot("b0002", 18, "CAM-01", slots={"image": {"asset": "A"}}),
        ), "c01")
    }
    res = compile_specs(inp, sp, draw=False)
    assert not res.errors, summary_text(res)
    spans = _shot_spans(inp, res.storyboard)
    mp = next(s for s in spans if s[1] == "MAP-01")
    assert mp[3] >= 3.0 - 1e-6
    assert not any(i["code"] == "outside_picture_brief" for i in res.warnings)
