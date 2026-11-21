import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bti.editor.common import ApiError
from bti.editor.voice_api import make_router
from bti.longjob.config import ServerConfig
from bti.longjob.fakes import FakeProbes
from bti.longjob.heavy import HeavySlot
from bti.longjob.manager import LongJobManager
from bti.voice import files
from conftest import needs_ffmpeg, write_project


@pytest.fixture()
def client(tmp_path, cfg):
    d = write_project(tmp_path, "vtest")
    write_project(tmp_path, "unap", approve=False)
    mgr = LongJobManager(heavy=HeavySlot(ServerConfig(), probes=FakeProbes()))        # in-process only: never the server's lock folder
    mgr.configure(projects_root=tmp_path)
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def _e(_, e):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)

    app.include_router(make_router(tmp_path, cfg=cfg, server={}, provider="fake", manager=mgr))
    c = TestClient(app)
    c.mgr, c.dir, c.root = mgr, d, tmp_path
    return c


def test_get_voice_before_anything(client):
    r = client.get("/api/projects/vtest/voice")
    assert r.status_code == 200
    d = r.json()
    assert d["state"] == "none" and d["approved"] and d["counts"]["missing"] == d["counts"]["total"] > 0
    assert d["chapters"][1]["card"] is True and d["estimate"]["parts"] >= 1
    assert d["chunks"][0]["text"].startswith("In 1434") and "fourteen thirty-four" in d["chunks"][0]["spoken"]


def test_unknown_and_unapproved(client):
    assert client.get("/api/projects/nope/voice").status_code == 404
    assert client.get("/api/projects/..%2Fx/voice").status_code in (404, 422)
    r = client.get("/api/projects/unap/voice")
    assert r.json()["state"] == "none" and "duyệt" in r.json()["detail"]
    r = client.post("/api/projects/unap/voice/generate", json={})
    assert r.status_code == 409 and r.json()["code"] == "narration_not_approved"


def test_settings_validation_and_save(client):
    r = client.put("/api/projects/vtest/voice/settings", json={"tempo": 1.1, "pad": False})
    assert r.status_code == 200 and r.json()["settings"] == {"tempo": 1.1, "pad": False}
    for bad in ({"tempo": 2.0}, {"tempo": "fast"}, {"tempo": True}, {"pad": "yes"}, {"pronounce": []}, {"pronounce": {"": "x"}}, {"pronounce": {"a": 3}}):
        r = client.put("/api/projects/vtest/voice/settings", json=bad)
        assert r.status_code == 422 and r.json()["code"].startswith("bad_"), bad
    r = client.put("/api/projects/vtest/voice/settings", json={"pronounce": {"  mirror ": "mir ror"}})
    assert r.json()["pronounce"] == {"mirror": "mir ror"}
    assert files.read_pronounce(client.dir) == {"mirror": "mir ror"}
    assert files.read_settings(client.dir)["tempo"] == 1.1          # untouched by the second save


def test_generate_validation(client):
    for body in ({"scope": "everything"}, {"scope": ["../x"]}, {"scope": "all", "reseed": ["zz"]}, {"scope": [1]}):
        r = client.post("/api/projects/vtest/voice/generate", json=body)
        assert r.status_code == 422 and r.json()["code"] == "bad_scope"


@needs_ffmpeg
def test_generate_serve_and_play(client):
    r = client.post("/api/projects/vtest/voice/generate", json={"scope": "changed"})
    assert r.status_code == 200
    rec = client.mgr.wait(r.json()["job_id"], 120)
    assert rec["state"] == "done"
    d = client.get("/api/projects/vtest/voice").json()
    assert d["state"] == "done" and d["timing"]["quality"] == "even" and d["mix"]["exists"]
    cid = d["chunks"][0]["id"]
    w = client.get(f"/api/projects/vtest/voice/chunks/{cid}.wav")
    assert w.status_code == 200 and w.content[:4] == b"RIFF"
    assert client.get("/api/projects/vtest/voice/chunks/000000000000.wav").status_code == 404
    assert client.get("/api/projects/vtest/voice/chunks/xyz.wav").status_code == 404
    m = client.get("/api/projects/vtest/voice/mix")
    assert m.status_code == 200 and len(m.content) > 1000


def test_mix_before_it_exists(client):
    r = client.get("/api/projects/vtest/voice/mix")
    assert r.status_code == 404 and r.json()["code"] == "no_voice"


def test_voice_state_function(client, cfg):
    from bti.voice import state
    s = state(client.dir)
    assert set(s) >= {"state", "detail"} and s["state"] in ("none", "running", "stale", "done")
    assert state(client.root / "does-not-exist")["state"] == "none"
