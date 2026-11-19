"""Fixtures of the automatic-run tests (worker c6auto): the app in the test process on a private projects folder, a mock agent, the fake pipeline of
`run_helpers.World` (real long jobs with quick parts, nothing heavy or paid), and the run's own transport pointed at the app without a network. The patterns are
those of tests/cli and tests/state. No model, no voice, no render, no paid service and no download is ever started."""
import json
import os
import socket
import sys
import threading
import time
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
from run_helpers import AppTransport, World  # noqa: E402

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
    monkeypatch.delenv("BTI_URL", raising=False)
    monkeypatch.delenv("BTI_ACTOR", raising=False)
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    from bti.picks import suggest
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)       # no paid call can start, whatever config/picks.json says
    yield
    set_transport(None)


@pytest.fixture(autouse=True)
def _jobs_of_one_test_only():
    """The long-job runner of the process is one object: a job of an earlier test (every test uses the project `arn`) must not be seen by the next."""
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
    """`make_client()` -> a TestClient on the projects folder whose automatic runs call this very app without a network, with quick polling."""
    opened = []

    def make(**kw):
        app = create_app(projects_root=root, engine_module=None, media_module=None, **kw)
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
    return World(client, monkeypatch)


@pytest.fixture()
def live(root):
    """The app on a real local port (an ephemeral one, never 8550 or 8560) with NO test transport: the run calls the app over HTTP at the address it was reached at, the way it does
    in production. -> an httpx client with `.root`, bound to that port."""
    import httpx
    import uvicorn
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port not in (8550, 8560)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    app.state.auto_options = {"poll": 0.05}
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    end = time.time() + 20
    while not server.started and time.time() < end:
        time.sleep(0.05)
    assert server.started, "the test server did not start"
    c = httpx.Client(base_url="http://127.0.0.1:%d" % port, timeout=60)
    c.root = root
    yield c
    c.close()
    server.should_exit = True
    th.join(15)
