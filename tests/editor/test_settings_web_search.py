"""The owner's switch of the web search of the automatic choice of pictures: `GET/PUT /api/settings/web-search` (who may change it, what is refused), where it is
kept (`run/settings.json`, block `picks`, over `config/picks.json`, over the code's default: off), and the cost line of `picks.auto` that says what the switch allows."""
import json

import pytest

from bti.editor import state_api
from bti.picks import websettings


@pytest.fixture
def sfile(tmp_path, monkeypatch):
    f = tmp_path / "settings.json"
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(f))
    monkeypatch.setattr(websettings, "_config", lambda: {})                 # no config file: the code's own default
    return f


def test_the_switch_is_off_with_eighty_searches_in_code(client, sfile):
    r = client.get("/api/settings/web-search")
    assert r.status_code == 200 and r.json() == {"auto_web_search": "off", "auto_web_search_max": 80, "source": "default"}
    assert websettings.for_run() == {"on": False, "max": 80} and not websettings.enabled()


def test_the_config_file_sets_the_machines_default_and_the_owners_choice_wins_over_it(client, sfile, monkeypatch):
    monkeypatch.setattr(websettings, "_config", lambda: {"auto_web_search": "on", "auto_web_search_max": 30})
    assert client.get("/api/settings/web-search").json() == {"auto_web_search": "on", "auto_web_search_max": 30, "source": "config"}
    r = client.put("/api/settings/web-search", json={"auto_web_search": "off"})
    assert r.json() == {"auto_web_search": "off", "auto_web_search_max": 30, "source": "owner"}                  # the number the owner did not touch stays the config's
    monkeypatch.setattr(websettings, "_config", lambda: {"auto_web_search": "maybe", "auto_web_search_max": 0})        # nonsense in the config is ignored
    assert websettings.settings()["auto_web_search_max"] == 80 and websettings.settings()["auto_web_search"] == "off"


def test_the_owner_switches_it_on_and_sets_the_number_and_the_other_settings_are_kept(client, sfile):
    sfile.write_text(json.dumps({"models": {"draft": "agy:x"}, "output": {"clean_after_export": False}}), encoding="utf-8")
    r = client.put("/api/settings/web-search", json={"auto_web_search": "on"})
    assert r.status_code == 200 and r.json() == {"auto_web_search": "on", "auto_web_search_max": 80, "source": "owner"}
    r = client.put("/api/settings/web-search", json={"auto_web_search_max": 25})
    assert r.json() == {"auto_web_search": "on", "auto_web_search_max": 25, "source": "owner"}
    saved = json.loads(sfile.read_text(encoding="utf-8"))
    assert saved["picks"] == {"auto_web_search": "on", "auto_web_search_max": 25} and saved["models"] == {"draft": "agy:x"} and saved["output"] == {"clean_after_export": False}
    assert client.get("/api/settings/web-search").json()["auto_web_search"] == "on" and websettings.for_run() == {"on": True, "max": 25}
    assert client.put("/api/settings/web-search", json={"auto_web_search": True}).json()["auto_web_search"] == "on"           # a boolean says it too
    assert client.put("/api/settings/web-search", json={"auto_web_search": "off", "actor": "human"}).json()["auto_web_search"] == "off"


@pytest.mark.parametrize("body", [{}, {"auto_web_search": "maybe"}, {"auto_web_search": 1}, {"auto_web_search_max": 0}, {"auto_web_search_max": 501},
                                   {"auto_web_search_max": "80"}, {"auto_web_search_max": True}, {"auto_web_search_max": 2.5}, {"unrelated": "on"}])
def test_nonsense_is_refused_and_nothing_is_written(client, sfile, body):
    r = client.put("/api/settings/web-search", json=body)
    assert r.status_code == 422 and r.json()["code"] == "invalid_payload" and not sfile.exists()


@pytest.mark.parametrize("actor", ["agent:claude-opus-5-5", "cli:bti", "cli:someone"])
def test_an_agent_never_switches_on_a_paid_search(client, sfile, actor):
    r = client.put("/api/settings/web-search", json={"auto_web_search": "on", "actor": actor})
    assert r.status_code == 403 and r.json()["code"] == "spend_needs_human" and not sfile.exists()
    assert client.put("/api/settings/web-search", json={"auto_web_search": "on", "actor": "nonsense actor"}).status_code == 422
    assert not sfile.exists()


def test_the_cost_line_of_the_automatic_choice_says_what_the_switch_allows(sfile):
    spec = state_api.SPEC["picks.auto"]
    assert spec.cost == ("model", "about 20 minutes") and state_api.cost_about(spec) == "about 20 minutes"
    sfile.write_text(json.dumps({"picks": {"auto_web_search": "on", "auto_web_search_max": 12}}), encoding="utf-8")
    assert state_api.cost_about(spec) == "about 20 minutes, up to 12 web searches (You.com)"
    assert state_api.cost_about(state_api.SPEC["voice.generate"]) == "about 1 hour"                              # no other action says it
    sfile.write_text("{not json", encoding="utf-8")                                                                # a damaged settings file never breaks the answer
    assert state_api.cost_about(spec) == "about 20 minutes"


def test_it_is_off_and_the_kind_of_cost_does_not_change_so_an_agent_may_start_the_choice_as_before(sfile):
    spec = state_api.SPEC["picks.auto"]
    assert spec.cost[0] == "model" and spec.auto_ok is True                                                        # the kind stays `model`: no new permission is asked of the owner
