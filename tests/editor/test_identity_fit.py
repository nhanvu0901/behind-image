"""Integration tests for Defect A: identity/title/retime/draft keep all shots inside painted surface with and without content_box."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from bti.draft.compile import compile_specs
from bti.draft.inputs import DraftInputs, normalize_timing
from bti.draft.spec import shape_problems
from bti.editor.app import create_app
from bti.engine import registry as R
from bti.engine import storyboard as SB
from bti.engine import viewchecks as V
from bti.engine.timing import Timing
from bti.title import apply as tapply


def _make_fit_project(root: Path, pid: str, *, with_content_box: bool) -> dict:
    d = root / pid
    (d / "images").mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (3840, 5253), (140, 110, 85))
    if with_content_box:
        matte = Image.new("RGB", (3840, 5253), (4, 4, 4))
        matte.paste(img.crop((384, 525, 3456, 4728)), (384, 525))
        img = matte
    img.save(d / "images" / "main.jpg", quality=80)

    # Lead 2.0s (triggers raking opening), chap1 2..10s, silence gap 10..14s (card sits cleanly), chap2 14..24s.
    words = []
    for i in range(6):
        s = round(2.0 + i * 1.2, 2)
        words.append({"w": f"a{i}", "s": s, "e": round(s + 0.5, 2)})
    for i in range(8):
        s = round(14.0 + i * 1.2, 2)
        words.append({"w": f"b{i}", "s": s, "e": round(s + 0.5, 2)})
    timing = normalize_timing({
        "duration": 24.0,
        "words": words,
        "beats": [
            {"id": "b0001", "chapter": "c01", "text": "a0 a1 a2 a3 a4 a5", "start": 2.0, "end": 9.8, "w0": 0, "w1": 6},
            {"id": "b0002", "chapter": "c02", "text": "b0 b1 b2 b3 b4 b5 b6 b7", "start": 14.0, "end": 23.8, "w0": 6, "w1": 14},
        ],
        "chapters": [
            {"id": "c01", "name": "INTRO", "title": "Intro", "role": "cold_open", "start": 2.0, "end": 10.0, "card": False},
            {"id": "c02", "name": "MIRROR", "title": "The Mirror", "role": "chapter", "start": 14.0, "end": 24.0,
             "card": True, "lead": {"kind": "card", "start": 10.0, "end": 14.0}},
        ],
    })
    (d / "timing.json").write_text(json.dumps(timing), encoding="utf-8")

    asset = {"file": "images/main.jpg", "kind": "image", "width": 3840, "height": 5253,
             "title": "Test Painting", "artist": "Van Eyck", "year": "1434",
             "regions": {"MIRROR": {"x": 1920, "y": 2626.5, "rx": 240, "ry": 240, "label": "Mirror"}}}
    if with_content_box:
        asset["content_box"] = [0.1, 0.1, 0.9, 0.9]
        # Inside [384..3456] (w=3072): zoom=0.63 gives vw=3047.6 (inside), while z/1.04=0.60577 gives vw=3169.5 (extends outside!)
        edge_zoom = 0.63
    else:
        # Whole file [0..3840]: zoom=0.51 gives vw=3764.7 (inside), while z/1.04=0.49038 gives vw=3915.3 (extends outside!)
        edge_zoom = 0.51

    picks = {"schema": "bti.picks/1", "main_asset": "MAIN", "assets": {"MAIN": asset},
             "beats": {"b0001": {"items": [{"asset": "MAIN", "role": "main"}], "kinds": ["detail"]},
                       "b0002": {"items": [{"asset": "MAIN", "region": "MIRROR", "role": "detail"}], "kinds": ["detail"]}}}
    (d / "picks.json").write_text(json.dumps(picks), encoding="utf-8")
    (d / "project.json").write_text(json.dumps({"id": pid, "title": "Test Painting", "artist": "Van Eyck", "year": "1434"}), encoding="utf-8")

    sb = {
        "schema": "bti.storyboard/1",
        "project": pid,
        "style": "gae",
        "identity": {"style": "raking"},
        "canvas": {"w": 1920, "h": 1080, "fps": 30},
        "assets": {"MAIN": copy.deepcopy(asset)},
        "shots": [
            {"id": "s0000", "start": {"t": 0.0}, "technique": "STATIC-01", "intent": "establish",
             "slots": {"image": {"asset": "MAIN"}}, "params": {}, "overlays": [], "locked": False, "source": "agent", "note": ""},
            {"id": "s0001", "start": {"w": 0, "off": -0.35, "text": "a0"}, "technique": "CAM-05", "intent": "explore",
             "slots": {"image": {"asset": "MAIN"}},
             "params": {"camera": [
                 {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": edge_zoom, "ease": "linear"},
                 {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": edge_zoom + 0.05, "ease": "linear"},
             ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
            {"id": "s0002", "start": {"t": 11.5}, "technique": "X-CARD-01", "intent": "structure",
             "slots": {"title": {"text": "The Mirror"}}, "params": {"title": "The Mirror"},
             "overlays": [], "locked": False, "source": "agent", "note": ""},
            {"id": "s0003", "start": {"w": 6, "off": 0.0, "text": "b0"}, "technique": "CAM-05", "intent": "point_at",
             "slots": {"image": {"asset": "MAIN", "region": "MIRROR"}},
             "params": {"camera": [
                 {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": edge_zoom, "ease": "linear"},
                 {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": 1.2, "ease": "linear"},
             ]}, "overlays": [], "locked": False, "source": "agent", "note": ""},
        ],
        "end": {"t": 24.0},
    }
    (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
    return {"timing": timing, "picks": picks, "edge_zoom": edge_zoom}


def _off_painting_issues(d: Path) -> list[dict]:
    sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
    tm = Timing.load(d / "timing.json")
    issues = SB.validate(sb, tm, R.load_bundle("gae"), d)
    return [i for i in issues if i["code"] == "frame_off_painting"]


@pytest.mark.parametrize("with_content_box", [False, True])
def test_all_identity_paths_stay_inside_painted_surface(tmp_path, with_content_box):
    pid = f"fit_{'box' if with_content_box else 'whole'}"
    info = _make_fit_project(tmp_path, pid, with_content_box=with_content_box)
    d = tmp_path / pid

    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None)
    with TestClient(app) as client:
        # 1. identity.set (raking, then dim)
        for sid in ("raking", "dim"):
            rev = client.get(f"/api/projects/{pid}").json()["rev"]
            r = client.put(f"/api/projects/{pid}/identity", json={"style": sid, "base_rev": rev})
            assert r.status_code == 200, r.text
            assert _off_painting_issues(d) == []

        # Back to raking (uses marks with 1.04x wider pull-in)
        rev = client.get(f"/api/projects/{pid}").json()["rev"]
        assert client.put(f"/api/projects/{pid}/identity", json={"style": "raking", "base_rev": rev}).status_code == 200
        assert _off_painting_issues(d) == []

        # 2. title.set
        tget = client.get(f"/api/projects/{pid}/title").json()
        r = client.put(f"/api/projects/{pid}/title", json={"base_rev": tget["rev"], "text": "A Clean Painting Title"})
        assert r.status_code == 200, r.text
        assert _off_painting_issues(d) == []

        # 3. title.apply.apply_to_storyboard (called by title.generate job)
        out = tapply.apply_to_storyboard(d, "Another Agent Generated Title")
        assert out is not None and not out.get("error")
        assert _off_painting_issues(d) == []

        # 4. storyboard.retime (simulate card slightly off-voice and let retime re-apply identity)
        sb = json.loads((d / "storyboard.json").read_text(encoding="utf-8"))
        for s in sb["shots"]:
            if s.get("intent") == "structure":
                s["start"] = {"t": 10.2}
                break
        (d / "storyboard.json").write_text(json.dumps(sb), encoding="utf-8")
        rev = client.get(f"/api/projects/{pid}").json()["rev"]
        r = client.post(f"/api/projects/{pid}/storyboard/retime", json={"base_rev": rev, "actor": "cli:test"})
        assert r.status_code == 200, r.text
        assert _off_painting_issues(d) == []

    # 5. full draft compile
    c1, e1 = shape_problems({"schema": "bti.draft/1", "chapter": "c01", "shots": [
        {"beat": "b0001", "start_word": 0, "technique": "CAM-05", "intent": "explore",
         "slots": {"image": {"asset": "MAIN"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": info["edge_zoom"], "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": info["edge_zoom"] + 0.05, "ease": "linear"},
         ]}, "note": "intro"},
    ]}, "c01")
    c2, e2 = shape_problems({"schema": "bti.draft/1", "chapter": "c02", "shots": [
        {"beat": "b0002", "start_word": 6, "technique": "CAM-05", "intent": "point_at",
         "slots": {"image": {"asset": "MAIN", "region": "MIRROR"}},
         "params": {"camera": [
             {"at": {"rel": 0.0}, "cx": 1920, "cy": 2626.5, "zoom": info["edge_zoom"], "ease": "linear"},
             {"at": {"rel": 1.0}, "cx": 1920, "cy": 2626.5, "zoom": 1.2, "ease": "linear"},
         ]}, "note": "mirror"},
    ]}, "c02")
    assert not e1 and not e2
    inp = DraftInputs(timing=info["timing"], picks=info["picks"], title="Test Painting", style="gae", project_dir=d)
    res = compile_specs(inp, {"c01": c1, "c02": c2}, draw=False)
    tm = Timing.load(d / "timing.json")
    issues = V.check(res.storyboard, tm, R.load_bundle("gae"), d, [tm.resolve(s["start"]) for s in res.storyboard["shots"]], tm.resolve(res.storyboard["end"]), lambda *_: None)
    assert [i for i in issues if i["code"] == "frame_off_painting"] == []
