"""Fixtures of the `bti` command tests (worker c5cli): the app in the test process on a private projects folder, a transport that talks to it
without a network, a scripted transport for the answers a real app does not give on demand, and one real local port to prove the HTTP path.
No model, no voice, no render, no paid service and no download is ever started: the starters of the heavy stages are stood in for, the way
tests/state does. The patterns are those of tests/state and tests/ops."""
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
for p in (REPO, HERE, REPO / "tests" / "state", REPO / "tests" / "ops", REPO / "tests" / "picks", REPO / "tests" / "script"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from bti import settings as S  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import mock as mock_mod, set_transport  # noqa: E402
from cli_helpers import AppTransport, run_bti  # noqa: E402

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


class Calls:
    """What the stood-in starters were asked (a test proves that a refused command never reached them)."""

    def __init__(self):
        self.voice, self.draft, self.export, self.search = [], [], [], []


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Nothing heavy or paid starts: the starters of the voice, the draft, the export and the preview, and the picture search, answer at once."""
    import bti.draft.run as draft_run
    import bti.editor.jobs as jobs_mod
    import bti.export.run as export_run
    import bti.voice.run as voice_run
    from bti.picks import service
    calls = Calls()

    def voice(*a, **k):
        calls.voice.append(k)
        return {"id": "fakevoicejob"}

    def draft(*a, **k):
        calls.draft.append(k)
        return {"id": "fakedraftjob", "meta": {}}

    def export(*a, **k):
        calls.export.append(k)
        return {"id": "fakeexportjob"}

    def search(*a, **k):
        calls.search.append((a, k))
        return {"items": [{"source": "commons", "source_id": "x1", "title": "A picture"}], "errors": []}
    monkeypatch.setattr(voice_run, "start", voice)
    monkeypatch.setattr(draft_run, "start", draft)
    monkeypatch.setattr(export_run, "start", export)
    monkeypatch.setattr(jobs_mod, "render_preview", lambda *a, **k: "/api/projects/x/files/cache/previews/p.mp4")
    monkeypatch.setattr(service, "search", search)
    return calls


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "projects"
    r.mkdir()
    return r


@pytest.fixture()
def make_client(root):
    """`make_client(**kw)` -> a TestClient on the projects folder; every client is closed at the end of the test."""
    opened = []

    def make(**kw):
        kw.setdefault("engine_module", None)
        kw.setdefault("media_module", None)
        app = create_app(projects_root=root, **kw)
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


@pytest.fixture()
def bti(client):
    """`bti(*argv)` -> Result, against the app of `client`."""
    t = AppTransport(client)

    def run(*argv, **kw):
        return run_bti(t, *argv, **kw)
    run.transport = t
    run.client = client
    return run


# ------------------------------------------------------------------------------------------------------------------- one real port
@pytest.fixture()
def live(root):
    """The app on a real local port (an ephemeral one, never 8550 or 8560): proves the HTTP path of the command. -> (url, stop)."""
    import uvicorn
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port not in (8550, 8560)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    end = time.time() + 20
    while not server.started and time.time() < end:
        time.sleep(0.05)
    assert server.started, "the test server did not start"
    state = {"stopped": False}

    def stop():
        if not state["stopped"]:
            state["stopped"] = True
            server.should_exit = True
            t.join(15)
    yield "http://127.0.0.1:%d" % port, stop
    stop()
