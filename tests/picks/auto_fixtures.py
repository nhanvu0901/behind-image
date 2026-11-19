"""Fixtures of the tests of the automatic picks job. A test module imports the ones it needs (`from auto_fixtures import env, paid  # noqa`).

`paid` makes every way into the paid suggestion service (You.com) record a call and raise; the `env` fixture checks at the end that there
was none, so no test can pass if the job reached it."""
import tempfile

import pytest

from auto_helpers import Env, FakeAgent, install_agent, install_sources, make_auto_project


@pytest.fixture
def paid(monkeypatch):
    calls = []

    def trap(name):
        def fn(*a, **k):
            calls.append(name)
            raise AssertionError("the paid suggestion service was called: " + name)
        return fn
    from bti.media import clips, research, youcom
    from bti.picks import service, suggest
    monkeypatch.setattr(suggest.YouComProvider, "suggest", trap("YouComProvider.suggest"))
    monkeypatch.setattr(suggest, "pick_provider", trap("suggest.pick_provider"))
    monkeypatch.setattr(suggest, "start", trap("suggest.start"))
    monkeypatch.setattr(research, "visual_research", trap("research.visual_research"))
    monkeypatch.setattr(clips, "moment_search", trap("clips.moment_search"))
    monkeypatch.setattr(youcom.YouComClient, "__init__", trap("YouComClient"))
    monkeypatch.setattr(service, "video_search", trap("service.video_search"))
    monkeypatch.setattr(service, "start_clip_job", trap("service.start_clip_job"))
    return calls


@pytest.fixture
def env(tmp_path, monkeypatch, paid):
    from bti.longjob import manager
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(work))                       # the agent's work folders are made (and left, when a run fails) here
    manager.configure(projects_root=root)
    sources = install_sources(monkeypatch)
    agent = install_agent(monkeypatch, FakeAgent())
    yield Env(root, pdir, agent, sources, manager)
    assert paid == [], "the paid suggestion service was reached: %s" % paid
