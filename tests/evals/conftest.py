"""Fixtures of the bench tests (worker c6auto): the app in the test process with the mock agent (no model, no network), a private samples root with copies of the
reference projects, and a transport that talks to the app without a network. The agents are the fakes the test launchers use; nothing is ever paid for."""
import json
import os
import shutil
import sys
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO, HERE, REPO / "tests" / "state", REPO / "tests" / "cli", REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti import settings as S  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402
from cli_helpers import AppTransport  # noqa: E402

MOCK_AGENTS = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}, {"id": "opus", "label": "Opus giả", "model": "mock"}],
               "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
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
    monkeypatch.delenv("BTI_URL", raising=False)
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    from bti.picks import suggest
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)
    yield
    set_transport(None)


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    return r


@pytest.fixture()
def samples(tmp_path):
    """A samples root with copies of the two reference projects of the repository (the bench reads them and must never write into them)."""
    s = tmp_path / "samples"
    s.mkdir()
    for name in ("arnolfini-from-books", "arnolfini"):
        shutil.copytree(REPO / "projects" / name, s / name)
    return s


@pytest.fixture()
def client(root):
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    cl = TestClient(app, raise_server_exceptions=False)
    cl.__enter__()
    cl.root = root
    yield cl
    cl.__exit__(None, None, None)


@pytest.fixture()
def transport(client):
    return AppTransport(client)
