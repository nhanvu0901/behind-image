"""Fixtures of the title tests (worker titlestep): the app in the test process on a private projects folder, a mock agent for the other steps, a fake title agent that
writes prepared answers into its work folder the way a real one would, and the fake pipeline of tests/auto (`run_helpers.World`) for the test of the automatic run. The patterns
are those of tests/auto and tests/state. No model, no program, no network is ever started."""
import json
import os
import sys
import time
from pathlib import Path

os.environ["BTI_NO_REAL_MODELS"] = "1"

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for p in (REPO, HERE, REPO / "tests" / "auto", REPO / "tests" / "state", REPO / "tests" / "cli", REPO / "tests" / "picks", REPO / "tests" / "script", REPO / "tests" / "editor"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti import settings as S  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402

MOCK_AGENTS = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}],
               "steps": {"script": ["script.outline", "script.narration", "script.title"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


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
    monkeypatch.delenv("BTI_URL", raising=False)
    monkeypatch.delenv("BTI_ACTOR", raising=False)
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    from bti.picks import suggest
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)
    yield
    set_transport(None)


@pytest.fixture(autouse=True)
def _work_folders_in_the_test_folder(tmp_path, monkeypatch):
    """The agent's work folders (and `clean_old`) live in the test's own temp folder, never in the system's."""
    import tempfile
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    yield


@pytest.fixture(autouse=True)
def _jobs_of_one_test_only():
    """The long-job runner of the process is one object: a job of an earlier test must not be seen by the next."""
    from bti.longjob import manager

    def forget():
        with manager._lock:
            live = [j for j in manager._jobs.values() if j.state in ("queued", "waiting", "running")]
        for j in live:
            j.cancel.set()
        end = time.time() + 5
        while time.time() < end and any(j.state in ("queued", "waiting", "running") for j in live):
            time.sleep(0.02)
        with manager._lock:
            manager._jobs.clear()
    forget()
    yield
    forget()


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    return r


@pytest.fixture()
def make_client(root):
    """`make_client(**kw)` -> a TestClient on the projects folder whose automatic runs call this very app without a network, with quick polling."""
    from run_helpers import AppTransport
    opened = []

    def make(**kw):
        app = create_app(projects_root=root, engine_module=kw.pop("engine_module", None), media_module=None, **kw)
        cl = TestClient(app, raise_server_exceptions=False)
        cl.__enter__()
        cl.root = root
        cl.transport = AppTransport(cl)
        app.state.auto_transport = lambda: cl.transport
        app.state.auto_options = {"poll": 0.02, "slice_seconds": 60.0, "max_hours": 0.2}
        opened.append(cl)
        return cl
    yield make
    for cl in opened:
        cl.__exit__(None, None, None)


@pytest.fixture()
def client(make_client):
    return make_client()


@pytest.fixture()
def world(client, monkeypatch):
    from run_helpers import World
    return World(client, monkeypatch)
