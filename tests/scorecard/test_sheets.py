from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from bti.scorecard.sheets import COLS, TILE_H, TILE_W, render_sheets, shot_sample_time


def test_shot_sample_time_prefers_first_mark_plus_1_3_else_midpoint():
    s_marked = {
        "id": "s1",
        "overlays": [
            {"technique": "AN-01", "_t0": 12.0},
            {"technique": "HI-01", "_t0": 15.0},
        ],
    }
    # 12.0 + 1.3 = 13.3 inside [10.0, 20.0]
    assert abs(shot_sample_time(s_marked, 10.0, 20.0) - 13.3) < 1e-6

    # clamped near end of shot
    assert abs(shot_sample_time(s_marked, 10.0, 12.5) - 12.45) < 1e-6

    # plain shot uses midpoint
    assert abs(shot_sample_time({"id": "s2"}, 10.0, 20.0) - 15.0) < 1e-6


def test_render_sheets_builds_5x4_grid_from_fake_engine(tmp_path: Path):
    pdir = tmp_path / "proj"
    pdir.mkdir()
    shots = [
        {
            "id": f"s{i+1:02d}",
            "_t0": float(i * 4),
            "_t1": float(i * 4 + 4),
            "technique": "CAM-01",
            "overlays": [{"technique": "AN-01", "_t0": float(i * 4 + 0.5)}] if i == 0 else [],
        }
        for i in range(22)
    ]

    class FakeEngine:
        def __init__(self):
            self.times: list[float] = []

        def resolve(self):
            return {"shots": shots}

        def frame_at(self, t: float, width: int = TILE_W):
            self.times.append(t)
            return np.full((TILE_H, TILE_W, 3), 90, dtype=np.uint8)

    eng = FakeEngine()
    out_dir = pdir / "scorecard" / "sheets"
    entries, source = render_sheets(pdir, out_dir, engine_project=eng, title="Sheet Demo")
    assert source == "engine"
    assert len(eng.times) == 22
    assert abs(eng.times[0] - 1.8) < 1e-6  # 0.5 + 1.3
    assert len(entries) == 2  # 20 + 2 shots
    assert entries[0]["name"] == "sheet_01.jpg"
    assert entries[0]["count"] == 20
    assert entries[1]["name"] == "sheet_02.jpg"
    assert entries[1]["count"] == 2

    img1 = Image.open(out_dir / "sheet_01.jpg")
    img2 = Image.open(out_dir / "sheet_02.jpg")
    assert img1.size[0] == COLS * TILE_W
    assert img1.size[1] > 4 * TILE_H
    assert img2.size[0] == COLS * TILE_W
    assert img2.size[1] < img1.size[1]


def test_render_sheets_falls_back_to_open_project(tmp_path: Path, monkeypatch):
    import bti.engine.api as engine_api

    pdir = tmp_path / "proj"
    pdir.mkdir()
    shots = [
        {"id": f"s{i+1:02d}", "_t0": float(i * 3), "_t1": float(i * 3 + 3), "technique": "CAM-01"}
        for i in range(5)
    ]
    (pdir / "timing.json").write_text(
        json.dumps({"duration": 15.0, "words": [{"w": f"w{i+1}", "s": float(i * 3), "e": float(i * 3 + 1)} for i in range(5)]}),
        encoding="utf-8",
    )

    class FakeEngine:
        def resolve(self):
            return {"shots": shots}

        def frame_at(self, t: float, width: int = TILE_W):
            return np.full((TILE_H, TILE_W, 3), 120, dtype=np.uint8)

    monkeypatch.setattr(engine_api, "open_project", lambda *a, **kw: FakeEngine())

    out_dir = pdir / "scorecard" / "sheets"
    entries, source = render_sheets(pdir, out_dir, title="Sheet Demo")
    assert source == "engine"
    assert len(entries) == 1
    assert entries[0]["count"] == 5
    assert (out_dir / "sheet_01.jpg").is_file()
