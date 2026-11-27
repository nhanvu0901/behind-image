import json
from pathlib import Path
from shutil import copyfile

from fastapi.testclient import TestClient
from bti.editor.app import create_app


def test_compose_action_saves_and_retains_history(tmp_path):
    root = Path(__file__).parents[1] / "visual" / "fixtures" / "landscape"
    project = tmp_path / "demo"
    project.mkdir()
    (project / "media").mkdir()
    for name in ("visual.json", "timing.json", "picks.json"):
        copyfile(root / name, project / name)
    copyfile(root / "media" / "painting.png", project / "media" / "painting.png")
    client = TestClient(create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False))
    result = client.post("/api/projects/demo/storyboard/compose", json={"base_rev": None})
    assert result.status_code == 200, result.text
    first = json.loads((project / "storyboard.json").read_text(encoding="utf-8"))
    assert first["shots"]
    from bti.editor.common import compute_rev
    assert result.json()["rev"] == compute_rev(first)
    assert client.post("/api/projects/demo/storyboard/compose", json={"base_rev": "stale"}).status_code == 409
    visual = json.loads((project / "visual.json").read_text(encoding="utf-8"))
    visual["moments"][0]["show"] = {"whole": True}
    (project / "visual.json").write_text(json.dumps(visual), encoding="utf-8")
    assert client.post("/api/projects/demo/storyboard/compose", json={"base_rev": result.json()["rev"]}).status_code == 200
    assert list((project / "history").glob("*.json"))


def test_action_is_only_listed_with_a_visual_document(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({"id": "demo", "title": "Demo"}), encoding="utf-8")
    client = TestClient(create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False))
    def ids():
        return [row["id"] for row in client.get("/api/projects/demo/state").json()["next_actions"]]
    assert "storyboard.compose" not in ids()
    (project / "visual.json").write_text('{}', encoding="utf-8")
    assert "storyboard.compose" in ids()
    actions = client.get("/api/projects/demo/state").json()["next_actions"]
    action = next(row for row in actions if row["id"] == "storyboard.compose")
    assert not action["ready"]
    assert {"timing", "main_asset"} <= set(action["needs"])
