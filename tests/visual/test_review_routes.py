import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_visual_action_routers_start_jobs(tmp_path, monkeypatch):
    from bti.visual import edit, review
    from bti.editor.common import ApiError
    project = tmp_path / 'p1'; project.mkdir()
    app = FastAPI(); app.state.projects_root = tmp_path
    app.add_exception_handler(ApiError, lambda request, exc: __import__('fastapi').responses.JSONResponse({'code': exc.code}, status_code=exc.status))
    app.include_router(edit.router); app.include_router(review.router)
    monkeypatch.setattr(edit, 'start', lambda pid, pdir, **kw: {'id': 'edit-job'})
    monkeypatch.setattr(review, 'start', lambda pid, pdir, **kw: {'id': 'review-job'})
    client = TestClient(app)
    response = client.post('/api/projects/p1/visual/edit', json={'instruction': 'Change it', 'scope': {'all': True}})
    assert response.status_code == 200 and response.json()['job_id'] == 'edit-job'
    response = client.post('/api/projects/p1/visual/review', json={})
    assert response.status_code == 200 and response.json()['job_id'] == 'review-job'


@pytest.mark.parametrize("endpoint,body", [("edit", {"instruction": "x", "scope": {"all": True}}), ("review", {})])
def test_application_exposes_visual_action_routes(tmp_path, monkeypatch, endpoint, body):
    from bti.editor.app import create_app
    from bti.visual import edit, review
    (tmp_path / 'p1').mkdir()
    app = create_app(projects_root=tmp_path, engine_module=None, media_module=None, output_root=False)
    monkeypatch.setattr(edit, 'start', lambda *a, **k: {'id': 'edit-job'})
    monkeypatch.setattr(review, 'start', lambda *a, **k: {'id': 'review-job'})
    client = TestClient(app)
    assert client.post('/api/projects/p1/visual/' + endpoint, json=body).status_code == 200


def test_automatic_visual_review_disables_paid_search(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.visual import review, store
    from bti.draft import run
    from bti.picks.auto import session
    p = tmp_path / 'p1'; p.mkdir()
    (p / 'storyboard.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(store, 'load', lambda p: {'moments': []})
    monkeypatch.setattr(run, '_resolve', lambda *a: SimpleNamespace(model='fake', public=lambda: {}))
    monkeypatch.setattr(run, 'other_agent_job', lambda *a, **k: None)
    monkeypatch.setattr(session, 'check_installed', lambda *a: None)
    captured = {}
    monkeypatch.setattr(review, 'run_job', lambda *a, **kw: captured.update(kw))
    class Manager:
        def start(self, **kwargs):
            kwargs['parts'][0].run(None)
            return {'id': 'job'}
    review.start('p1', p, manager=Manager(), run_ok=True)
    assert captured['web'] == {'on': False, 'max': 0}
