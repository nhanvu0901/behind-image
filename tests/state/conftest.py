"""Fixtures of the state and error tests: an app on a private projects folder, a mock agent (no model is ever called), a private
settings file. The patterns are those of tests/editor and tests/settings."""
import json
import os
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO, HERE, REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti import settings as S  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402

MOCK_AGENTS = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}],
               "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    """No real .env, no real keys, no model, no network, private settings and agent files."""
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(run / "settings.json"))
    monkeypatch.setenv("BTI_AGENTS_FILE", str(tmp_path / "agents.json"))
    (tmp_path / "agents.json").write_text(json.dumps({r: "mock" for r in S.ROLES}), encoding="utf-8")
    choices = tmp_path / "choices.json"
    choices.write_text(json.dumps(MOCK_AGENTS), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(choices))
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    from bti.picks import suggest
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)       # no paid call can start, whatever config/picks.json says
    yield
    set_transport(None)


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    return r


@pytest.fixture()
def make_client(root):
    """`make_client()` -> a TestClient on the projects folder; every client is closed at the end of the test."""
    opened = []

    def make(**kw):
        app = create_app(projects_root=root, engine_module=None, media_module=None, **kw)
        cl = TestClient(app, raise_server_exceptions=False)
        cl.__enter__()
        cl.root = root
        opened.append(cl)
        return cl
    yield make
    for cl in opened:
        cl.__exit__(None, None, None)


@pytest.fixture()
def client(make_client):
    return make_client()
