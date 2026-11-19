import json
import pytest
from starlette.testclient import TestClient

from bti.editor.app import create_app
from bti.settings import (
    ROLES,
    AGENTIC_ROLES,
    ROLE_LABELS,
    DEFAULT_MODEL,
    model_for,
    get_model_settings,
    save_model_settings,
    SettingsError,
)


@pytest.fixture
def clean_settings(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    settings_file = run_dir / "settings.json"
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(settings_file))
    return settings_file


@pytest.fixture
def client(clean_settings, tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    app = create_app(projects_dir)
    return TestClient(app)


def test_model_for_defaults(clean_settings):
    for r in ROLES:
        assert model_for(r) == "agy:gemini-3.8-flash-high"


def test_user_settings_override(clean_settings):
    clean_settings.write_text(json.dumps({
        "models": {"script.outline": "mock"}
    }))
    assert model_for("script.outline") == "mock"
    assert model_for("script.narration") == "agy:gemini-3.8-flash-high"


def test_get_settings_api(client):
    res = client.get("/api/settings/models")
    assert res.status_code == 200
    data = res.json()
    assert "roles" in data
    assert "models" in data
    roles = {r["role"]: r for r in data["roles"]}
    assert len(roles) == 6
    for r in ROLES:
        assert r in roles
        assert roles[r]["label"] == ROLE_LABELS[r]
        assert roles[r]["value"] == "agy:gemini-3.8-flash-high"
        assert roles[r]["source"] == "default"


def test_put_settings_api_success(client, clean_settings):
    res = client.put("/api/settings/models", json={"script.outline": "mock"})
    assert res.status_code == 200
    assert model_for("script.outline") == "mock"

    res2 = client.get("/api/settings/models")
    assert res2.status_code == 200
    roles = {r["role"]: r for r in res2.json()["roles"]}
    assert roles["script.outline"]["value"] == "mock"
    assert roles["script.outline"]["source"] == "setting"


def test_put_settings_unknown_role(client):
    res = client.put("/api/settings/models", json={"invalid.role": "mock"})
    assert res.status_code == 422
    assert res.json().get("code") == "unknown_role"


def test_put_settings_unknown_model(client):
    res = client.put("/api/settings/models", json={"script.outline": "nonexistent-model-xyz"})
    assert res.status_code == 422
    assert res.json().get("code") == "unknown_model"


def test_put_settings_agentic_requires_agy(client):
    res = client.put("/api/settings/models", json={"draft": "mock"})
    assert res.status_code == 422
    assert res.json().get("code") == "agentic_role_needs_agy"


def test_put_settings_agentic_accepts_the_claude_code_family(client):
    """worker claudeprov: the roles that need an agent accept `claude:<model>@<effort>` next to `agy:<slug>`."""
    for role in AGENTIC_ROLES:
        res = client.put("/api/settings/models", json={role: "claude:claude-opus-5-5@high"})
        assert res.status_code == 200, res.text
        assert model_for(role) == "claude:claude-opus-5-5@high"
    res = client.get("/api/settings/models")
    roles = {r["role"]: r for r in res.json()["roles"]}
    assert roles["draft"]["value"] == "claude:claude-opus-5-5@high" and roles["draft"]["in_available"] is True      # the tracked entry is listed
    assert roles["draft"]["agentic"] is True
    claude = [m for m in res.json()["models"] if m["provider"] == "claudecode"]
    assert [m["id"] for m in claude] == ["claude:claude-opus-5-5@high"] and claude[0]["label"] == "Claude Code: Opus 5.5 High"
    assert claude[0]["enabled"] is False and claude[0]["claude"]["ok"] is False        # no real program in a test: listed, with a reason, never run


def test_put_settings_claude_family_is_checked_in_one_place(client):
    for bad in ("claude:claude-opus-5-5", "claude:x@ultra", "claude:@high", "claude:a b@high"):
        res = client.put("/api/settings/models", json={"draft": bad})
        assert res.status_code == 422 and res.json().get("code") == "agentic_role_needs_agy", bad
    res = client.put("/api/settings/models", json={"script.outline": "claude:claude-sonnet-4-5@medium"})            # a well-formed id of the family, not tracked
    assert res.status_code == 200 and model_for("script.outline") == "claude:claude-sonnet-4-5@medium"
    res = client.put("/api/settings/models", json={"script.outline": "claude:x@ultra"})
    assert res.status_code == 422 and res.json().get("code") == "unknown_model"
    res = client.put("/api/settings/models", json={"draft": "mock"})                                                  # the old refusal stays
    assert res.status_code == 422 and res.json().get("code") == "agentic_role_needs_agy"
