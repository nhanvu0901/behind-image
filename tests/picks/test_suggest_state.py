"""The suggestion job (real long-job runner, fake provider), the paid-call guards, and state()."""
import pytest
from fastapi.testclient import TestClient
from picks_helpers import make_project, mount

from bti.editor import picks_api
from bti.editor.app import create_app
from bti.longjob import manager
from bti.picks import doc, state, suggest
from bti.picks.errors import PicksError

CAND = {"source": "commons", "source_id": "File:X.jpg", "title": "X", "thumb_url": "https://example.invalid/x.jpg", "page_url": "", "width": 2000,
        "height": 2000, "mime": "image/jpeg", "author": "a", "licence": "PD", "licence_ok": True, "licence_reason": "", "flag": None}
SUG = [{"what": "Another work", "kind": "artwork", "why": "same artist", "search_terms": ["a", "b"], "source_urls": ["https://wikipedia.org/x"],
        "candidates": [CAND]}]


@pytest.fixture
def env(root, proj):
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    app.state.picks_provider = suggest.FakeProvider(default=SUG)
    with TestClient(app) as c:
        c.pdir, c.u = proj, lambda t="": f"/api/projects/{proj.name}/picks{t}"
        yield c


def run(c, body):
    r = c.post(c.u("/suggest"), json=body)
    if r.status_code == 200:
        manager.wait(r.json()["job_id"], 20)
    return r


def test_confirm_is_required(env):
    for body in ({"beats": ["b0001"]}, {"beats": ["b0001"], "confirm_paid": "yes"}, {"beats": ["b0001"], "confirm_paid": False}):
        r = env.post(env.u("/suggest"), json=body)
        assert r.status_code == 422 and r.json()["code"] == "confirm_required"
    assert env.app.state.picks_provider.calls == []


def test_bad_beats(env):
    assert env.post(env.u("/suggest"), json={"beats": [], "confirm_paid": True}).status_code == 422
    assert env.post(env.u("/suggest"), json={"beats": ["b9999"], "confirm_paid": True}).status_code == 404
    assert env.post(env.u("/suggest"), json={"beats": [f"b{i:04d}" for i in range(50)], "confirm_paid": True}).status_code in (404, 422)


def test_job_stores_suggestions_and_resumes(env):
    r = run(env, {"beats": ["b0001", "b0002"], "confirm_paid": True})
    assert r.status_code == 200
    got = env.get(env.u("/suggestions")).json()["beats"]
    assert set(got) == {"b0001", "b0002"} and got["b0001"]["items"][0]["candidates"][0]["source_id"] == "File:X.jpg"
    prov = env.app.state.picks_provider
    assert prov.calls == ["b0001", "b0002"]
    run(env, {"beats": ["b0001", "b0003"], "confirm_paid": True})                 # b0001 is not asked again
    assert prov.calls == ["b0001", "b0002", "b0003"]
    run(env, {"beats": ["b0001"], "confirm_paid": True, "refresh": True})
    assert prov.calls[-1] == "b0001" and len(prov.calls) == 4
    assert not (env.pdir / "picks.json").exists()                                  # suggestions never touch the picks


def test_provider_failure_fails_the_job_with_a_sentence(env):
    env.app.state.picks_provider = suggest.FakeProvider(fail=PicksError(409, "x", "suggest_no_key"))
    r = env.post(env.u("/suggest"), json={"beats": ["b0001"], "confirm_paid": True})
    job = manager.wait(r.json()["job_id"], 20)
    assert job["state"] == "error" and job["error_code"] == "suggest_no_key" and "You.com" in job["error"]
    assert env.get(env.u("/suggestions")).json()["beats"] == {}


def test_provider_failure_reason_is_in_the_job_log(env):     # LR-002
    env.app.state.picks_provider = suggest.FakeProvider(fail=PicksError(502, "You.com call failed: HTTP 401", "suggest_failed"))
    r = env.post(env.u("/suggest"), json={"beats": ["b0001"], "confirm_paid": True})
    job = manager.wait(r.json()["job_id"], 20)
    assert any("HTTP 401" in str(x) for x in job["log_tail"])


def test_real_provider_is_off_unless_the_config_allows(env):
    env.app.state.picks_provider = None
    r = env.post(env.u("/suggest"), json={"beats": ["b0001"], "confirm_paid": True})
    assert r.status_code == 409 and r.json()["code"] == "suggest_off"
    assert env.get(env.u()).json()["suggest"]["available"] is False
    with pytest.raises(PicksError):
        suggest.YouComProvider().suggest({"id": "b1", "text": "t", "show": []}, {})


def test_real_provider_maps_research_without_a_call(monkeypatch):
    from bti.media import research
    monkeypatch.setattr(suggest, "live_allowed", lambda: True)
    seen = {}

    def fake_vr(text, ctx, client=None, live=False, **kw):
        seen.update(text=text, live=live, client=client)
        return [{"what": "W", "kind": "artwork", "why": "", "search_terms": ["w"], "source_urls": []}]
    monkeypatch.setattr(research, "visual_research", fake_vr)
    monkeypatch.setattr(research, "resolve_suggestion", lambda s, **k: [CAND] * 20)
    out = suggest.YouComProvider(limit_candidates=3).suggest({"id": "b1", "text": "hello", "show": []}, {"title": "T"})
    assert seen["live"] is True and out[0]["what"] == "W" and len(out[0]["candidates"]) == 3

    def disabled(*a, **k):
        raise research.LiveCallDisabled("no key")
    monkeypatch.setattr(research, "visual_research", disabled)
    with pytest.raises(PicksError) as e:
        suggest.YouComProvider().suggest({"id": "b1", "text": "t", "show": []}, {})
    assert e.value.code == "suggest_no_key"


def test_settings_default_and_file(tmp_path, monkeypatch):
    monkeypatch.setattr(suggest, "REPO_ROOT", tmp_path)
    assert suggest.settings() == {"suggest": "youcom"}
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "picks.json").write_text('{"suggest": "off"}')
    assert suggest.settings() == {"suggest": "off"}
    (tmp_path / "config" / "picks.json").write_text("{bad")
    assert suggest.settings() == {"suggest": "youcom"}


# ------------------------------------------------------------------ state()
def _doc_with_main(d, beats):
    (d / "media").mkdir(exist_ok=True)
    (d / "media" / "a.jpg").write_bytes(b"x")
    a = {"file": "media/a.jpg", "kind": "image", "title": "A", "artist": "", "year": "", "width": 100, "height": 100,
         "credit": {"source": "u", "source_url": "", "author": "", "licence": "PD", "flag": None}, "regions": {}}
    return {"main_asset": "A", "assets": {"A": a},
            "beats": {b: {"items": [{"asset": "A", "region": None, "role": "main", "note": ""}], "status": "picked", "note": ""} for b in beats}}


def test_state_progression(root):
    from picks_helpers import beat_ids
    from bti.script import store
    root.mkdir()
    d = make_project(root, "st1")
    assert state(d)["state"] == "none" and "Chưa" in state(d)["detail"]
    ids = beat_ids(d)
    with doc.Held(d):
        doc.save(d, {**doc.empty(), "assets": {}, "beats": {}})
    assert state(d)["detail"] == "Chưa chọn tranh chính."
    with doc.Held(d):
        rev = doc.save(d, _doc_with_main(d, ids[:2]))
    s = state(d)
    assert s["state"] == "none" and s["picked"] == 2 and s["beats"] == 6 and "2/6" in s["detail"]
    with doc.Held(d):
        doc.stamp_approval(d, rev, store.load_narration(d).rev())
    assert state(d)["state"] == "done"
    n = store.load_narration(d)
    n.chapters[0].beats[0].text += " Changed."
    store.save_narration(d, n)
    s = state(d)
    assert s["state"] == "stale" and s["reason"] == "narration_changed"


def test_state_never_raises_on_damage(root):
    root.mkdir()
    d = make_project(root, "st2")
    (d / "picks.json").write_text("{broken")
    s = state(d)
    assert s["state"] == "none" and "hỏng" in s["detail"]


def test_state_running_reads_the_runner(root, monkeypatch):
    root.mkdir()
    d = make_project(root, "st3")
    monkeypatch.setattr(manager, "active", lambda pid, kind=None: {"id": "j1"} if (pid == "st3" and kind == "picks") else None)
    assert state(d)["state"] == "running"


@pytest.mark.parametrize("status,error,code", [(401, "HTTP 401", "suggest_key_refused"), (403, "HTTP 403", "suggest_key_refused"),
                                               (402, "HTTP 402", "suggest_quota"), (429, "HTTP 429", "suggest_quota"),
                                               (None, "request failed: TimeoutError", "suggest_timeout"),
                                               (422, "HTTP 422", "suggest_bad_answer"), (None, "response was not valid JSON", "suggest_bad_answer"),
                                               (500, "HTTP 500", "suggest_failed"), (None, "request failed: URLError", "suggest_failed")])
def test_you_com_failures_get_a_code_by_kind_and_the_key_stays_out(monkeypatch, status, error, code):     # LR-002
    from bti.media import research
    from bti.media.youcom import RawCall
    monkeypatch.setattr(suggest, "live_allowed", lambda: True)
    from bti.script import env as script_env
    monkeypatch.setattr(script_env, "get_key", lambda n: "sekrit-key")
    monkeypatch.setattr("bti.media.youcom.YouComClient.research",
                        lambda self, *a, **k: RawCall(api="research", payload={}, error=error, status_code=status,
                                                      response_text='{"message":"bad sekrit-key here"}'))
    with pytest.raises(PicksError) as e:
        suggest.YouComProvider().suggest({"id": "b1", "text": "t", "show": []}, {"title": "T"})
    assert e.value.code == code and "sekrit-key" not in e.value.detail
    assert code in suggest.PART_ERRORS and "***" in e.value.detail or status is None
