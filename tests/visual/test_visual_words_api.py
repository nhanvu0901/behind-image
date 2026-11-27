"""Tests for the read-only visual words route."""
import json
from fastapi.testclient import TestClient

from bti.editor.app import create_app


def test_visual_words_missing_timing_returns_empty(tmp_path):
    (tmp_path / "demo").mkdir()
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    res = TestClient(app).get("/api/projects/demo/visual/words")
    assert res.status_code == 200
    assert res.json() == {"present": False, "words": [], "beats": [], "chapters": [], "duration": None}


def test_visual_words_returns_words_beats_and_chapters(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    timing = {
        "duration": 6.0,
        "words": [{"w": "In", "s": 0.0, "e": 0.5}, {"w": "1434", "s": 0.5, "e": 1.2}],
        "beats": [{"id": "b0001", "w0": 0, "w1": 2, "s": 0.0, "e": 1.2}],
        "chapters": [{"id": "c01", "name": "Mở đầu", "w0": 0, "w1": 2}],
    }
    (project / "timing.json").write_text(json.dumps(timing), encoding="utf-8")
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    res = TestClient(app).get("/api/projects/demo/visual/words")
    assert res.status_code == 200
    data = res.json()
    assert data["present"] is True
    assert data["duration"] == 6.0
    assert len(data["words"]) == 2
    assert data["beats"][0]["id"] == "b0001"
    assert data["chapters"][0]["name"] == "Mở đầu"


def test_visual_words_unknown_project_is_404(tmp_path):
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    res = TestClient(app).get("/api/projects/missing/visual/words")
    assert res.status_code == 404
