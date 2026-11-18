"""A7 safety switch (`BTI_NO_REAL_MODELS=1`) for the real suggestion provider (`bti.picks.suggest.YouComProvider`).

Every `conftest.py` sets the switch. The config says "youcom" in these tests (so the config refusal does not hide the switch), a
tripwire stands behind the provider, and the key is a dummy one: a request that got through would fail the test.
"""
import urllib.request

import pytest
from fastapi.testclient import TestClient
from picks_helpers import mount

from bti.editor.app import create_app
from bti.longjob import manager
from bti.picks import suggest
from bti.picks.errors import PicksError

BEAT = {"id": "b1", "text": "A beat of narration.", "show": []}


@pytest.fixture(autouse=True)
def switch_on(monkeypatch):
    monkeypatch.setenv("BTI_NO_REAL_MODELS", "1")
    monkeypatch.setenv("YDC_API_KEY", "dummy-key")
    monkeypatch.setattr(suggest, "live_allowed", lambda: True)

    def net(*a, **k):
        raise AssertionError("the network was reached under the safety switch")
    monkeypatch.setattr(urllib.request, "urlopen", net)


def test_the_real_provider_refuses_with_the_code():
    with pytest.raises(PicksError) as e:
        suggest.YouComProvider().suggest(BEAT, {"title": "The Arnolfini Portrait"})
    assert e.value.code == "real_models_off" and "BTI_NO_REAL_MODELS" in str(e.value)


def test_the_config_refusal_still_comes_first(monkeypatch):
    monkeypatch.setattr(suggest, "live_allowed", lambda: False)
    with pytest.raises(PicksError) as e:
        suggest.YouComProvider().suggest(BEAT, {})
    assert e.value.code == "suggest_off"


def test_a_fake_provider_still_works_under_the_switch():
    assert suggest.FakeProvider(default=[{"what": "w"}]).suggest(BEAT, {}) == [{"what": "w"}]


def test_the_job_fails_with_the_code_and_a_sentence(root, proj):
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    app.state.picks_provider = suggest.YouComProvider()
    with TestClient(app) as c:
        r = c.post(f"/api/projects/{proj.name}/picks/suggest", json={"beats": ["b0001"], "confirm_paid": True})
        assert r.status_code == 200
        job = manager.wait(r.json()["job_id"], 20)
    assert job["state"] == "error" and job["error_code"] == "real_models_off"
    assert "BTI_NO_REAL_MODELS" not in job["error"] and job["error"]       # a sentence for the owner, not the variable name


def test_the_free_picture_searches_of_a_suggestion_refuse_too(monkeypatch):
    """The paid answer is faked here; the picture sources behind it (Commons, Met, ...) must refuse as well."""
    from bti.media import api as media_api, research
    monkeypatch.setattr(media_api, "_SOURCES", {})
    monkeypatch.setattr(research, "visual_research",
                        lambda *a, **k: [{"what": "W", "kind": "artwork", "why": "", "search_terms": ["w"], "source_urls": []}])
    with pytest.raises(PicksError) as e:
        suggest.YouComProvider().suggest(BEAT, {"title": "T"})
    assert e.value.code == "real_models_off"
