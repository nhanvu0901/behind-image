import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from bti.editor.common import ApiError
from bti.visual.api import router
from test_validation import valid, timing


def test_visual_routes_validate_and_check_revision(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "timing.json").write_text(json.dumps(timing()), encoding="utf-8")
    app = FastAPI()
    app.state.projects_root = tmp_path
    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return JSONResponse({"detail": exc.detail, **exc.extra}, status_code=exc.status)
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/api/projects/demo/visual").json()["visual"] is None
    body = {"visual": valid(), "base_rev": None, "actor": "agent:test"}
    saved = client.put("/api/projects/demo/visual", json=body)
    assert saved.status_code == 200
    assert saved.json()["visual"] == valid()
    assert client.put("/api/projects/demo/visual", json=body).status_code == 409
    body["base_rev"] = saved.json()["rev"]
    body["visual"]["moments"][0]["w1"] = 1
    refused = client.put("/api/projects/demo/visual", json=body)
    assert refused.status_code == 422
    assert refused.json()["issues"]
    assert client.get("/api/projects/demo/visual").json()["rev"] == saved.json()["rev"]


def test_editor_app_mounts_visual_routes(tmp_path):
    from bti.editor.app import create_app
    (tmp_path / "demo").mkdir()
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    client = TestClient(app)
    response = client.get("/api/projects/demo/visual")
    assert response.status_code == 200
    assert response.json()["visual"] is None
    (tmp_path / "demo" / "timing.json").write_text(json.dumps(timing()), encoding="utf-8")
    saved = client.put("/api/projects/demo/visual", json={"visual": valid(), "base_rev": None, "actor": "agent:test"})
    assert saved.status_code == 200
    assert client.get("/api/projects/demo/visual").json()["rev"] == saved.json()["rev"]


def test_review_notes_are_returned_without_refusing_a_save(tmp_path):
    from bti.editor.app import create_app
    project = tmp_path / "demo"
    project.mkdir()
    (project / "timing.json").write_text(json.dumps(timing()), encoding="utf-8")
    client = TestClient(create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False))
    doc = valid()
    doc["cast"][0].update(strip=True, term=True)
    result = client.put("/api/projects/demo/visual", json={"visual": doc, "base_rev": None, "actor": "agent:test"})
    assert result.status_code == 200
    assert any(i["rule"] == "V6" and i["level"] == "review" for i in result.json()["issues"])


def test_visual_plan_action_starts_long_job(tmp_path, monkeypatch):
    from bti.editor.app import create_app
    from bti.visual import job
    (tmp_path / 'demo').mkdir()
    calls = []
    def start(pid, pdir, **kwargs):
        calls.append((pid, pdir, kwargs))
        return {'id': '1234567890abcdef', 'meta': {'model': 'fake', 'agent': {}}}
    monkeypatch.setattr(job, 'start', start)
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    res = TestClient(app).post('/api/projects/demo/visual/plan', json={})
    assert res.status_code == 200 and res.json()['job_id'] == '1234567890abcdef'
    assert calls[0][0] == 'demo'


def test_visual_plan_is_listed_in_state_actions():
    from bti.editor.state_api import SPECS, BUILDERS
    spec = next(s for s in SPECS if s.id == 'visual.plan')
    assert spec.step == 'picks' and spec.path.endswith('/visual/plan') and spec.long_job
    assert 'visual.plan' in BUILDERS


def test_action_cost_mentions_web_when_owner_enabled_it(monkeypatch):
    from bti.editor.state_api import SPECS, cost_about
    from bti.picks import websettings
    monkeypatch.setattr(websettings, 'for_run', lambda: {'on': True, 'max': 7})
    spec = next(s for s in SPECS if s.id == 'visual.plan')
    assert '7 web searches' in cost_about(spec)


def test_visual_plan_can_be_taken_by_the_automatic_run():
    from bti.editor.state_api import RUN_MANUAL
    assert 'visual.plan' not in RUN_MANUAL


def test_agent_visual_plan_never_enables_paid_web(tmp_path, monkeypatch):
    from bti.editor.app import create_app
    from bti.visual import job
    (tmp_path / 'demo').mkdir()
    calls = []
    monkeypatch.setattr(job, 'start', lambda pid, pdir, **kw: calls.append(kw) or {'id': 'fake', 'meta': {}})
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    r = TestClient(app).post('/api/projects/demo/visual/plan', json={'actor': 'cli:test'})
    assert r.status_code == 200
    assert calls[0]['web']['on'] is False


def test_visual_edit_cost_discloses_enabled_web_search(monkeypatch):
    from bti.editor.state_api import SPEC, cost_about
    from bti.picks import websettings
    monkeypatch.setattr(websettings, 'for_run', lambda: {'on': True, 'max': 7})
    assert '7 web searches' in cost_about(SPEC['visual.edit'])


def test_visual_edit_holds_project_agent_slot():
    from bti.draft.run import other_agent_job
    class Manager:
        def active(self, pid, kind):
            return {'id': 'edit', 'kind': 'picks', 'meta': {'action': 'edit', 'visual_action': 'edit'}} if kind == 'picks' else None
    assert other_agent_job('p1', 'draft', Manager())['id'] == 'edit'


def test_public_review_action_has_one_identifier():
    from bti.editor.state_api import SPEC
    assert 'storyboard.review' in SPEC
    assert 'visual.review' not in SPEC
