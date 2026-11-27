from fastapi.testclient import TestClient

from bti.editor.app import create_app


def test_get_music_reports_document_and_missing_project(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "p").mkdir()
    app = create_app(projects_root=projects, engine_module=None, media_module=None)
    client = TestClient(app)
    response = client.get("/api/projects/p/music")
    assert response.status_code == 200
    assert response.json()["music"] is None
    assert client.get("/api/projects/missing/music").status_code == 404


def test_music_view_resolves_cues_and_serves_recordings(tmp_path, monkeypatch):
    import json
    from bti.music import library
    projects, lib = tmp_path / "projects", tmp_path / "music"
    project = projects / "p"
    project.mkdir(parents=True)
    lib.mkdir()
    (lib / "piece.opus").write_bytes(b"recording")
    (lib / "library.json").write_text(json.dumps([{"id": "one", "file": "piece.opus", "duration": 60, "title": "Piece", "composer": "Composer", "license": "CC0", "credit": "Credit"}]))
    monkeypatch.setattr(library, "directory", lambda: lib)
    (project / "storyboard.json").write_text(json.dumps({"end": {"t": 10}, "shots": []}))
    (project / "timing.json").write_text(json.dumps({"duration": 10, "words": [{"w": "hello", "s": 1, "e": 2}], "chapters": []}))
    cue = {"recording": "one", "start": {"w": 0}, "end": {"t": 5}, "offset": 0, "level": "normal",
           "fade_in": 1, "fade_out": 1, "role": "bed", "why": "Quiet."}
    (project / "music.json").write_text(json.dumps({"cues": [cue]}))
    client = TestClient(create_app(projects_root=projects, engine_module=None, media_module=None))
    response = client.get("/api/projects/p/music")
    assert response.status_code == 200
    row = response.json()["cues"][0]
    assert (row["start"], row["end"], row["title"], row["composer"], row["role"]) == (1, 5, "Piece", "Composer", "bed")
    assert client.get(row["audio_url"]).content == b"recording"
    assert client.get("/api/projects/p/music/recordings/missing").status_code == 404
