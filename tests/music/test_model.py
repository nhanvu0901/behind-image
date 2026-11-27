import json

from fastapi.testclient import TestClient

from bti.editor.app import create_app
from bti.music import library
from bti.music.inputs import pauses


def test_pauses_are_derived_from_word_end_and_next_start():
    words = [{"w": "a", "s": 0.2, "e": 0.7}, {"w": "b", "s": 2.0, "e": 2.4},
             {"w": "c", "s": 3.0, "e": 3.2}, {"w": "d", "s": 5.0, "e": 5.2}]
    assert pauses(words) == [{"start": 0.7, "end": 2.0, "duration": 1.3}, {"start": 3.2, "end": 5.0, "duration": 1.8}]


def test_set_and_clear_music_require_validated_current_revision(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    project = root / "p"
    project.mkdir(parents=True)
    (project / "storyboard.json").write_text(json.dumps({"end": {"t": 10}, "shots": []}))
    (project / "timing.json").write_text(json.dumps({"duration": 10, "words": [{"w": "hello", "s": 0, "e": 1}], "chapters": []}))
    lib = tmp_path / "music"
    lib.mkdir()
    (lib / "library.json").write_text(json.dumps([{"id": "one", "duration": 60}]))
    monkeypatch.setattr(library, "directory", lambda: lib)
    client = TestClient(create_app(projects_root=root, engine_module=None, media_module=None))
    url = "/api/projects/p/music"
    rev = client.get(url).json()["rev"]
    doc = {"cues": [{"recording": "one", "start": {"t": 0}, "end": {"t": 5}, "offset": 0, "level": "normal",
                     "fade_in": 1, "fade_out": 1, "role": "bed", "why": "Quiet opening."}]}
    response = client.put(url, json={"base_rev": rev, "music": doc})
    assert response.status_code == 200, response.text
    assert client.get(url).json()["music"]["cues"] == doc["cues"]
    assert client.put(url, json={"base_rev": rev, "music": doc}).status_code == 409
    rev = client.get(url).json()["rev"]
    assert client.post(url + "/clear", json={"base_rev": rev}).status_code == 200
    assert client.get(url).json()["music"] is None


def test_agent_writes_valid_music_and_receives_timed_inputs(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.music import job, store
    from bti.picks.auto import session
    from bti.draft import run as draft

    project = tmp_path / "p"
    project.mkdir()
    monkeypatch.setattr(job, "WORK_ROOT", tmp_path / "work")
    (project / "storyboard.json").write_text(json.dumps({"end": {"t": 10}, "shots": []}))
    timing = {"duration": 10, "words": [{"w": "hello", "s": 0, "e": 1}, {"w": "world", "s": 3, "e": 4}],
              "beats": [{"id": "b1", "chapter": "c1", "text": "hello world", "start": 0, "end": 4}],
              "chapters": [{"id": "c1", "name": "Opening", "start": 0, "end": 10}]}
    (project / "timing.json").write_text(json.dumps(timing))
    (project / "project.json").write_text(json.dumps({"title": "Landscape", "artist": "Painter", "year": "1850", "place": "France"}))
    lib = tmp_path / "music"
    lib.mkdir()
    (lib / "library.json").write_text(json.dumps([{"id": "one", "duration": 60, "title": "Piece", "forces": "solo piano"}]))
    monkeypatch.setattr(library, "directory", lambda: lib)
    resolved = SimpleNamespace(model="mock", public=lambda: {"id": "fake", "model": "mock"})
    monkeypatch.setattr(draft, "_resolve", lambda p, role, model: resolved)
    monkeypatch.setattr(session, "check_installed", lambda model: None)
    seen = {}
    cue = {"recording": "one", "start": {"t": 0}, "end": {"t": 5}, "offset": 0, "level": "normal",
           "fade_in": 1, "fade_out": 1, "role": "bed", "why": "Quiet opening."}
    def fake_session(root, **kwargs):
        data = json.loads((root / "inputs" / "context.json").read_text(encoding="utf-8"))
        seen.update(data)
        (root / "out" / "music.json").write_text(json.dumps({"cues": [cue]}), encoding="utf-8")
        assert kwargs["check_fn"]() is None
        return SimpleNamespace(status="ok", code=None, message=None, steps=2, turns=1, repairs=0, elapsed=1)
    monkeypatch.setattr(session, "run_session", fake_session)
    class Ctx:
        job_id = "test"
        meta = {}
        def cancelled(self): return False
        def progress(self, *args): pass
    class Manager:
        def active(self, pid, kind): return None
        def start(self, **kw):
            result = kw["parts"][0].run(Ctx())
            return {"id": "test", "result": result}
    rec = job.start("p", project, manager=Manager())
    assert rec["result"]["cues"] == 1
    assert store.read(project)["cues"] == [cue]
    assert seen["library"]["one"]["character"] == "solo piano"
    assert seen["painting"]["place"] == "France"
    assert seen["narration"][0]["lines"][0]["text"] == "hello world"
    assert seen["pauses"] == [{"start": 1, "end": 3, "duration": 2}]
    # A new storyboard while the agent is working must not publish old placements.
    from bti.longjob import PartError
    import pytest
    def changed_session(root, **kwargs):
        result = fake_session(root, **kwargs)
        (project / "storyboard.json").write_text(json.dumps({"end": {"t": 8}, "shots": []}))
        return result
    monkeypatch.setattr(session, "run_session", changed_session)
    with pytest.raises(PartError) as exc:
        job.start("p", project, manager=Manager())
    assert exc.value.code == "stale_revision"
    assert store.read(project)["cues"] == [cue]


def test_agent_refuses_when_another_agent_is_working(tmp_path, monkeypatch):
    import pytest
    from types import SimpleNamespace
    from bti.music import job
    from bti.music.document import MusicError
    from bti.draft import run as draft
    from bti.picks.auto import session
    (tmp_path / "storyboard.json").write_text(json.dumps({"end": {"t": 10}, "shots": []}))
    (tmp_path / "timing.json").write_text(json.dumps({"words": [], "chapters": []}))
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "library.json").write_text(json.dumps([{"id": "one", "duration": 60}]))
    monkeypatch.setattr(library, "directory", lambda: lib)
    monkeypatch.setattr(draft, "_resolve", lambda p, role, model: SimpleNamespace(model="mock", public=lambda: {}))
    monkeypatch.setattr(session, "check_installed", lambda model: None)
    class Manager:
        def active(self, pid, kind): return {"id": "running", "kind": kind} if kind == "draft" else None
    with pytest.raises(MusicError) as exc:
        job.start("p", tmp_path, manager=Manager())
    assert exc.value.code == "agent_job_running"


def test_music_is_a_configured_agent_step():
    from bti import agents, settings
    choices = agents.load_choices()
    assert "music" in settings.ROLES
    assert choices.step_of("music") == "music"


def test_music_auto_requires_storyboard(tmp_path):
    root = tmp_path / "projects"
    (root / "p").mkdir(parents=True)
    client = TestClient(create_app(projects_root=root, engine_module=None, media_module=None))
    response = client.post("/api/projects/p/music/auto", json={})
    assert response.status_code in (409, 422)
    assert response.json()["code"] == "music_invalid"


def test_state_lists_music_actions_only_with_storyboard_and_marks_busy(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from bti.editor import state_api as state
    from bti.music import library
    monkeypatch.setattr(library, "index", lambda: {"one": {"duration": 60}})
    monkeypatch.setattr(state, "_model_needs", lambda c, role: [])
    ctx = SimpleNamespace(sb_exists=False, sb_corrupt=False, d=tmp_path, actor=lambda role: "agent:mock", agent_busy=lambda kind: False)
    assert state.b_music_auto(ctx) is None
    ctx.sb_exists = True
    assert state.b_music_auto(ctx)["advances"] is True
    ctx.agent_busy = lambda kind: True
    assert "no_running_job" in state.b_music_auto(ctx)["needs"]
    assert {"music.auto", "music.set", "music.clear"}.issubset(state.SPEC)
