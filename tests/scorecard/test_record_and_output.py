from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

import bti.engine.api as engine_api
from bti.editor.app import create_app
from bti.output import publish
from bti.scorecard import make_for_project


def _make_demo_project(root: Path, pid: str = "demo_sc") -> Path:
    pdir = root / pid
    (pdir / "assets").mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1920, 1080), (40, 50, 60)).save(pdir / "assets" / "main.png")
    (pdir / "project.json").write_text(
        json.dumps({"id": pid, "title": "Demo Scorecard", "artwork": {"key": "demo_key", "title": "Demo"}}),
        encoding="utf-8",
    )
    (pdir / "timing.json").write_text(
        json.dumps(
            {
                "duration": 20.0,
                "words": [
                    {"w": "Hello", "s": 0.0, "e": 1.0},
                    {"w": "world", "s": 10.0, "e": 11.0},
                ],
            }
        ),
        encoding="utf-8",
    )
    (pdir / "storyboard.json").write_text(
        json.dumps(
            {
                "schema": "bti.storyboard/1",
                "title": "Demo Scorecard",
                "timing": "timing.json",
                "end": {"t": 20.0},
                "assets": {"painting": {"file": "assets/main.png", "width": 1920, "height": 1080, "regions": {}}},
                "shots": [
                    {"id": "s01", "start": {"t": 0.0}, "technique": "CAM-01", "slots": {"image": {"asset": "painting"}}},
                    {"id": "s02", "start": {"t": 10.0}, "technique": "CAM-01", "slots": {"image": {"asset": "painting"}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    return pdir


def _install_fake_engine(monkeypatch) -> None:
    class FakeEngine:
        def resolve(self):
            return {
                "shots": [
                    {"id": "s01", "_t0": 0.0, "_t1": 10.0, "technique": "CAM-01"},
                    {"id": "s02", "_t0": 10.0, "_t1": 20.0, "technique": "CAM-01"},
                ]
            }

        def frame_at(self, t: float, width: int = 480):
            return np.full((270, 480, 3), 50, dtype=np.uint8)

    monkeypatch.setattr(engine_api, "open_project", lambda *a, **kw: FakeEngine())


def test_make_record_and_publish_7_quality(tmp_path: Path, monkeypatch):
    _install_fake_engine(monkeypatch)
    pdir = _make_demo_project(tmp_path / "projects")
    out_root = tmp_path / "output"

    res = make_for_project(pdir, sheets=True)
    sdir = pdir / "scorecard"
    assert (sdir / "scorecard.json").is_file()
    assert (sdir / "scorecard.md").is_file()
    assert (sdir / "record.json").is_file()
    assert (sdir / "record.md").is_file()
    assert (sdir / "sheets" / "sheet_01.jpg").is_file()
    assert "owner_comments" in res["record"] or "Nhận xét" in (sdir / "record.md").read_text(encoding="utf-8")

    # Sync output folder and verify 7_quality/ receives the files
    sync_res = publish.sync(pdir, output_root=out_root)
    qdir = Path(sync_res["folder"]) / "7_quality"
    assert (qdir / "scorecard.json").is_file()
    assert (qdir / "scorecard.md").is_file()
    assert (qdir / "record.json").is_file()
    assert (qdir / "record.md").is_file()
    assert (qdir / "sheets" / "sheet_01.jpg").is_file()


def test_editor_scorecard_routes_and_state_action(tmp_path: Path, monkeypatch):
    _install_fake_engine(monkeypatch)
    root = tmp_path / "projects"
    _make_demo_project(root, "demo_sc")
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    with TestClient(app) as client:
        st0 = client.get("/api/projects/demo_sc/state")
        assert st0.status_code == 200
        acts = {a["id"]: a for a in (st0.json().get("next_actions") or []) if isinstance(a, dict) and "id" in a}
        assert "scorecard.make" in acts
        assert acts["scorecard.make"]["method"] == "POST"
        assert acts["scorecard.make"]["path"] == "/api/projects/demo_sc/scorecard/make"
        assert acts["scorecard.make"]["ready"] is True

        g0 = client.get("/api/projects/demo_sc/scorecard")
        assert g0.status_code == 200
        assert g0.json()["exists"] is False
        assert g0.json()["ready"] is True

        m1 = client.post("/api/projects/demo_sc/scorecard/make", json={"sheets": True})
        assert m1.status_code == 200
        body = m1.json()
        assert body["exists"] is True
        assert len(body["scorecard"]["metrics"]) == 12
        assert len(body["sheets"]) == 1

        sheet_resp = client.get(body["sheets"][0]["url"])
        assert sheet_resp.status_code == 200
        assert sheet_resp.headers["content-type"].startswith("image/jpeg")
