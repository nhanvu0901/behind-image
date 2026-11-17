import json
import time

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti.editor import draft_api
from bti.editor.common import ApiError
from bti.longjob import manager


@pytest.fixture()
def client(proj):
    app = FastAPI()
    app.state.projects_root = proj.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)
    app.include_router(draft_api.router)
    return TestClient(app, raise_server_exceptions=False)


def test_get_draft(client, proj):
    r = client.get("/api/projects/%s/draft" % proj.name)
    assert r.status_code == 200
    d = r.json()
    assert d["ready"]["ok"] is True and d["state"]["state"] == "none" and d["default_model"] == "gemini-pro-orchestrator-g1-pro"
    assert d["providers"] == ["agy", "auto"]
    assert client.get("/api/projects/nope/draft").status_code == 404


def test_start_validates_the_body(client, proj):
    u = "/api/projects/%s/draft/start" % proj.name
    assert client.post(u, json={"provider": "x"}).json()["code"] == "bad_provider"
    assert client.post(u, json={"provider": "auto", "chapters": "c01"}).json()["code"] == "bad_chapters"
    r = client.post(u, json={"provider": "auto", "chapters": ["c01"]})
    assert r.status_code == 409 and r.json()["code"] == "scope_needs_storyboard"


def test_start_auto_and_poll_the_job(client, proj):
    r = client.post("/api/projects/%s/draft/start" % proj.name, json={"provider": "auto"})
    assert r.status_code == 200, r.text
    jid = r.json()["job_id"]
    j = manager.wait(jid, timeout=120)
    assert j["state"] == "done"
    d = client.get("/api/projects/%s/draft" % proj.name).json()
    assert d["state"]["state"] == "done" and d["last_run"]["status"] == "done"


def test_not_ready_is_409(client, proj):
    p = json.loads((proj / "picks.json").read_text())
    p["approval"] = {"approved": False}
    (proj / "picks.json").write_text(json.dumps(p))
    r = client.post("/api/projects/%s/draft/start" % proj.name, json={"provider": "auto"})
    assert r.status_code == 409 and r.json()["code"] == "draft_not_ready"
