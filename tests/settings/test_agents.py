"""The two agents and the choice of one: the choices file, the project's `agent.json`, the machine default, availability, and the ONE
function that says which model a call uses (contract docs/design/2026-11-18-agent-choice.md, sections 2 to 4). No model is called."""
import json
import threading

import pytest

from bti import agents as AG
from bti import settings as S
from bti.script import models as models_mod
from bti.script.store import ProjectGone

DEFAULT_MODEL = "agy:gemini-3.8-flash-high"
OPUS_MODEL = "claude:claude-opus-5-5@high"
MOCK_FILE = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}, {"id": "ops", "label": "Opus giả", "model": "mock-b"}],
             "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


@pytest.fixture(autouse=True)
def _private_files(tmp_path, monkeypatch):
    run = tmp_path / "run"
    run.mkdir()
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(run / "settings.json"))
    monkeypatch.delenv("BTI_AGENT_CHOICES_FILE", raising=False)
    monkeypatch.setenv("BTI_AGENTS_FILE", str(tmp_path / "agents.json"))            # per-role defaults: every role on the Gemini model
    (tmp_path / "agents.json").write_text(json.dumps({r: DEFAULT_MODEL for r in S.ROLES}), encoding="utf-8")
    models_mod.reset_cache()


@pytest.fixture()
def settings_file(tmp_path):
    return tmp_path / "run" / "settings.json"


@pytest.fixture()
def mock_agents(tmp_path, monkeypatch):
    f = tmp_path / "choices.json"
    f.write_text(json.dumps(MOCK_FILE), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(f))
    return f


@pytest.fixture()
def proj(tmp_path):
    d = tmp_path / "projects" / "p1"
    d.mkdir(parents=True)
    return d


def choose(proj, **doc):
    (proj / "agent.json").write_text(json.dumps({"schema": "bti.agent/1", "agent": None, "steps": {}, **doc}), encoding="utf-8")


# ---------------------------------------------------------------- the file
def test_the_tracked_file_is_the_contract():
    c = AG.load_choices()
    assert c.problems == () and c.default == "gemini"
    assert [(a.id, a.label, a.model) for a in c.agents] == [("gemini", "Gemini 3.8 Flash", "agy:gemini-3.8-flash-high"),
                                                           ("opus", "Opus 5.5 High", "claude:claude-opus-5-5@high"),
                                                           ("argon", "Gemini Orchestrator Argon", "agy:gemini-pro-orchestrator-g1-pro")]
    assert {k: list(v) for k, v in c.steps.items()} == {"script": ["script.outline", "script.narration", "script.title"], "picks": ["picks"],      # titlestep: the title is the third role of step 2
                                                        "storyboard": ["draft", "edit.fast", "edit.deep"], "music": ["music"]}
    assert c.step_of("edit.deep") == "storyboard" and c.step_of("library.restore") is None


def test_an_environment_variable_replaces_the_file(mock_agents):
    c = AG.load_choices()
    assert c.ids == ["gem", "ops"] and c.default == "gem" and c.agent("ops").model == "mock-b" and c.for_model("mock").id == "gem"


@pytest.mark.parametrize("text", ["", "{not json", "[]", '"x"'])
def test_a_missing_or_broken_file_is_the_built_in_pair(tmp_path, monkeypatch, text):
    f = tmp_path / "bad.json"
    if text:
        f.write_text(text, encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(f))
    c = AG.load_choices()
    assert c.ids == ["gemini", "opus"] and c.problems


def test_bad_entries_are_dropped_and_named(tmp_path, monkeypatch):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"default": "nope", "agents": [{"id": "a", "label": "A", "model": "mock"}, {"id": "a", "label": "Again", "model": "mock"},
                                                             {"id": "B B", "label": "x", "model": "mock"}, {"id": "c", "label": " ", "model": "mock"}, 5],
                             "steps": {"script": ["script.outline", "no.such.role"], "x": "not a list", "dup": ["script.outline"]}}), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(f))
    c = AG.load_choices()
    assert c.ids == ["a"] and c.default == "a"
    assert {k: list(v) for k, v in c.steps.items()} == {"script": ["script.outline"]}
    assert len(c.problems) >= 6


def test_a_file_without_agents_or_steps_falls_back(tmp_path, monkeypatch):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"agents": [], "steps": {}}), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(f))
    assert AG.load_choices().ids == ["gemini", "opus"]
    f.write_text(json.dumps({"agents": [{"id": "a", "label": "A", "model": "mock"}], "steps": {}}), encoding="utf-8")
    c = AG.load_choices()
    assert c.ids == ["a"] and "storyboard" in c.steps and c.problems


# ---------------------------------------------------------------- the resolution order (contract section 4)
def test_rule_1_the_model_named_by_the_request_wins(mock_agents, proj, settings_file):
    choose(proj, agent="ops", steps={"script": "ops"})
    S.set_machine_agent("ops")
    r = AG.model_for_project(proj, "script.outline", "mock")
    assert (r.model, r.source, r.agent_id, r.label) == ("mock", "request", "gem", "Gemini giả")         # an agent's own model keeps its label
    r = AG.model_for_project(proj, "script.outline", "something-else")
    assert (r.model, r.source, r.agent_id) == ("something-else", "request", None)
    assert AG.model_for_project(proj, "script.outline", "  ").source == "step"                           # a blank name names nothing


def test_rule_2_the_projects_choice_for_the_step(mock_agents, proj):
    choose(proj, agent="gem", steps={"script": "ops", "storyboard": "gem"})
    S.set_machine_agent("gem")
    r = AG.model_for_project(proj, "script.narration")
    assert (r.model, r.agent_id, r.label, r.source) == ("mock-b", "ops", "Opus giả", "step")
    assert AG.model_for_project(proj, "script.outline").source == "step"
    assert AG.model_for_project(proj, "draft").agent_id == "gem"                       # another step has its own choice


def test_rule_3_the_projects_agent(mock_agents, proj):
    choose(proj, agent="ops", steps={"script": "gem"})
    S.set_machine_agent("gem")
    r = AG.model_for_project(proj, "edit.fast")
    assert (r.model, r.agent_id, r.source) == ("mock-b", "ops", "project")
    assert AG.model_for_project(proj, "picks").source == "project"
    assert AG.model_for_project(proj, "script.outline").source == "step"


def test_rule_4_the_machines_default(mock_agents, proj, settings_file):
    S.set_machine_agent("ops")
    r = AG.model_for_project(proj, "draft")
    assert (r.model, r.agent_id, r.source) == ("mock-b", "ops", "default")
    assert AG.model_for_project(None, "draft").source == "default"                      # no project at all


def test_rule_5_what_model_for_answers_today(mock_agents, proj, settings_file):
    S.save_model_settings({"script.outline": "mock"})
    r = AG.model_for_project(proj, "script.outline")
    assert (r.model, r.source) == ("mock", "role") and r.agent_id == "gem"                # that model is the agent gem's: it is named so
    r = AG.model_for_project(proj, "draft")
    assert (r.model, r.source, r.agent_id) == (DEFAULT_MODEL, "role", None)               # no agent offers it in this file: the model's own label
    assert r.label


def test_with_the_real_file_the_default_model_is_the_gemini_agent(proj):
    r = AG.model_for_project(proj, "draft")
    assert (r.model, r.agent_id, r.label, r.source) == (DEFAULT_MODEL, "gemini", "Gemini 3.8 Flash", "role")
    assert r.public() == {"id": "gemini", "label": "Gemini 3.8 Flash", "model": DEFAULT_MODEL, "source": "role"}
    S.set_machine_agent("opus")
    r = AG.model_for_project(proj, "script.outline")
    assert (r.model, r.agent_id, r.label, r.source) == (OPUS_MODEL, "opus", "Opus 5.5 High", "default")


def test_an_agent_the_file_no_longer_lists_falls_through(mock_agents, proj, settings_file):
    S.set_machine_agent("ops")
    choose(proj, agent="gone", steps={"script": "also-gone"})
    r = AG.model_for_project(proj, "script.outline")
    assert (r.agent_id, r.source) == ("ops", "default")                                   # step and project ids skipped, the machine's applies
    S.set_machine_agent("vanished")
    r = AG.model_for_project(proj, "script.outline")
    assert (r.source, r.model) == ("role", DEFAULT_MODEL)                                 # all unknown: the per-role setting
    w = AG.project_view(proj)["warnings"]
    assert {(x["where"], x["agent"]) for x in w if x["code"] == "unknown_agent"} == {("agent", "gone"), ("steps.script", "also-gone"), ("machine", "vanished")}


def test_a_role_that_is_no_step_only_knows_rules_1_and_5(mock_agents, proj, settings_file):
    choose(proj, agent="ops")
    S.set_machine_agent("ops")
    r = AG.model_for_project(proj, "library.restore")
    assert (r.source, r.model) == ("role", DEFAULT_MODEL)
    assert AG.model_for_project(proj, "library.restore", "mock").source == "request"


def test_a_damaged_agent_file_never_breaks_a_call(mock_agents, proj):
    (proj / "agent.json").write_text("{broken", encoding="utf-8")
    assert AG.model_for_project(proj, "draft").source == "role"
    (proj / "agent.json").write_text("[1, 2]", encoding="utf-8")
    assert AG.model_for_project(proj, "draft").source == "role"


def test_model_for_without_a_project_is_unchanged(mock_agents, settings_file):
    S.set_machine_agent("ops")
    assert S.model_for("script.outline") == DEFAULT_MODEL
    S.save_model_settings({"script.outline": "mock"})
    assert S.model_for("script.outline") == "mock"


# ---------------------------------------------------------------- the project's document
def test_no_file_is_no_choice_with_a_stable_revision(mock_agents, proj):
    v = AG.project_view(proj)
    assert (v["agent"], v["steps"], v["warnings"]) == (None, {}, [])
    assert v["rev"] == AG.project_view(proj)["rev"] and len(v["rev"]) == 40
    assert set(v["effective"]) == {"script", "picks", "storyboard"}
    assert {x["source"] for x in v["effective"].values()} == {"role"}
    assert not (proj / "agent.json").exists()


def test_a_choice_is_written_atomically_with_the_schema(mock_agents, proj):
    rev0 = AG.project_view(proj)["rev"]
    v = AG.update_project(proj, {"steps": {"script": "ops"}}, rev0)
    assert v["steps"] == {"script": "ops"} and v["agent"] is None and v["rev"] != rev0
    assert v["effective"]["script"] == {"id": "ops", "label": "Opus giả", "model": "mock-b", "source": "step"}
    assert json.loads((proj / "agent.json").read_text(encoding="utf-8")) == {"schema": "bti.agent/1", "agent": None, "steps": {"script": "ops"}}
    assert not list(proj.glob("*.tmp")) and not [p for p in proj.iterdir() if p.name != "agent.json"]


def test_a_stale_write_is_refused_and_writes_nothing(mock_agents, proj):
    rev0 = AG.project_view(proj)["rev"]
    v1 = AG.update_project(proj, {"agent": "ops"}, rev0)
    with pytest.raises(AG.AgentError) as e:
        AG.update_project(proj, {"agent": "gem"}, rev0)
    assert (e.value.status, e.value.code, e.value.extra["rev"]) == (409, "stale", v1["rev"])
    assert AG.project_view(proj)["agent"] == "ops"


def test_a_key_present_with_null_clears_an_absent_key_stays(mock_agents, proj):
    v = AG.update_project(proj, {"agent": "ops", "steps": {"script": "gem", "storyboard": "ops"}}, AG.project_view(proj)["rev"])
    v = AG.update_project(proj, {"steps": {"script": None}}, v["rev"])                  # one step cleared, the other and the agent stay
    assert (v["agent"], v["steps"]) == ("ops", {"storyboard": "ops"})
    v = AG.update_project(proj, {"agent": None}, v["rev"])                                # the agent cleared, the steps stay
    assert (v["agent"], v["steps"]) == (None, {"storyboard": "ops"})
    v = AG.update_project(proj, {}, v["rev"])                                             # nothing named: nothing changes
    assert (v["agent"], v["steps"]) == (None, {"storyboard": "ops"})
    v = AG.update_project(proj, {"steps": None}, v["rev"])                                # null steps: every step choice goes
    assert (v["agent"], v["steps"]) == (None, {})


def test_use_for_the_whole_project_is_the_agent_plus_no_steps(mock_agents, proj):
    v = AG.update_project(proj, {"steps": {"script": "gem", "picks": "gem"}}, AG.project_view(proj)["rev"])
    v = AG.update_project(proj, {"agent": "ops", "steps": None}, v["rev"])
    assert (v["agent"], v["steps"]) == ("ops", {})
    assert {s: x["id"] for s, x in v["effective"].items()} == {"script": "ops", "picks": "ops", "storyboard": "ops"}
    assert {x["source"] for x in v["effective"].values()} == {"project"}


def test_bad_ids_and_bad_payloads_are_422_and_write_nothing(mock_agents, proj):
    rev = AG.project_view(proj)["rev"]
    for changes, code in (({"agent": "nope"}, "unknown_agent"), ({"agent": 5}, "unknown_agent"), ({"steps": {"script": "nope"}}, "unknown_agent"),
                          ({"steps": {"nowhere": "gem"}}, "unknown_step"), ({"steps": ["x"]}, "invalid_payload"), ({"steps": "x"}, "invalid_payload")):
        with pytest.raises(AG.AgentError) as e:
            AG.update_project(proj, changes, rev)
        assert (e.value.status, e.value.code) == (422, code), changes
    for bad in (None, "", 5):
        with pytest.raises(AG.AgentError) as e:
            AG.update_project(proj, {"agent": "gem"}, bad)
        assert e.value.code == "invalid_payload"
    assert not (proj / "agent.json").exists()


def test_a_no_op_does_not_create_the_file(mock_agents, proj):
    AG.update_project(proj, {"agent": None, "steps": None}, AG.project_view(proj)["rev"])
    assert not (proj / "agent.json").exists()


def test_a_damaged_file_is_replaced_by_the_next_choice_and_kept_aside(mock_agents, proj):
    (proj / "agent.json").write_text("{broken", encoding="utf-8")
    v = AG.project_view(proj)
    assert v["agent"] is None and [w["code"] for w in v["warnings"]] == ["agent_file_unreadable"]
    v = AG.update_project(proj, {"agent": "ops"}, v["rev"])
    assert v["agent"] == "ops" and v["warnings"] == []
    assert [p.name for p in proj.glob("agent.json.corrupt-*")] and json.loads((proj / "agent.json").read_text(encoding="utf-8"))["agent"] == "ops"


def test_a_deleted_project_is_not_made_again(mock_agents, tmp_path):
    gone = tmp_path / "projects" / "gone"
    with pytest.raises(ProjectGone):
        AG.update_project(gone, {"agent": "ops"}, AG.project_view(gone)["rev"])
    assert not gone.exists()


def test_two_writers_with_one_revision_one_wins(mock_agents, proj):
    rev = AG.project_view(proj)["rev"]
    out = []

    def go(a):
        try:
            AG.update_project(proj, {"agent": a}, rev)
            out.append("ok")
        except AG.AgentError as e:
            out.append(e.code)
    ts = [threading.Thread(target=go, args=(a,)) for a in ("gem", "ops")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(out) == ["ok", "stale"]


def test_projects_do_not_share_a_choice(mock_agents, proj, tmp_path):
    other = tmp_path / "projects" / "p2"
    other.mkdir()
    AG.update_project(proj, {"agent": "ops"}, AG.project_view(proj)["rev"])
    assert AG.project_view(other)["agent"] is None and AG.model_for_project(other, "draft").source == "role"


# ---------------------------------------------------------------- the machine default
def test_the_machine_default_is_stored_in_the_settings_file_and_keeps_the_rest(mock_agents, settings_file):
    S.save_model_settings({"script.outline": "mock"})
    out = AG.set_machine_default("ops")
    assert out["machine_default"] == "ops" and out["default"] == "gem"
    saved = json.loads(settings_file.read_text(encoding="utf-8"))
    assert saved["agent"] == "ops" and saved["models"] == {"script.outline": "mock"}
    assert S.get_machine_agent() == "ops"
    out = AG.set_machine_default(None)
    assert out["machine_default"] is None and "agent" not in json.loads(settings_file.read_text(encoding="utf-8"))
    assert json.loads(settings_file.read_text(encoding="utf-8"))["models"] == {"script.outline": "mock"}


def test_an_unknown_machine_default_is_refused(mock_agents, settings_file):
    with pytest.raises(AG.AgentError) as e:
        AG.set_machine_default("nope")
    assert (e.value.status, e.value.code) == (422, "unknown_agent") and not settings_file.exists()
    S.set_machine_agent("nope")                                                              # a value the file no longer lists: ignored, with a warning
    out = AG.public_agents()
    assert out["machine_default"] is None and [w["code"] for w in out["warnings"]] == ["unknown_agent"]


# ---------------------------------------------------------------- availability (no model call)
def test_availability_comes_from_the_two_caches(monkeypatch):
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: ([{"slug": "gemini-3.8-flash-high", "label": "G"}], None))
    monkeypatch.setattr(models_mod, "claude_status", lambda refresh=False: {"ok": False, "kind": "auth", "reason": "not_signed_in",
                                                                            "message": "Claude Code trên máy chủ chưa đăng nhập. Đăng nhập một lần."})
    out = AG.public_agents()
    a = {x["id"]: x for x in out["agents"]}
    assert a["gemini"]["available"] is True and a["gemini"]["reason"] is None
    assert a["opus"] == {"id": "opus", "label": "Opus 5.5 High", "model": OPUS_MODEL, "available": False,
                         "reason": "Claude Code trên máy chủ chưa đăng nhập. Đăng nhập một lần.", "reason_code": "not_signed_in"}
    assert out["default"] == "gemini" and out["machine_default"] is None and out["warnings"] == []


def test_availability_when_agy_does_not_answer_or_lacks_the_model(monkeypatch):
    monkeypatch.setattr(models_mod, "claude_status", lambda refresh=False: {"ok": True, "kind": None, "reason": None, "message": None})
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: (None, "`agy models` không trả lời."))
    models_mod._cache.update({"at": __import__("time").time(), "ttl": 60, "rows": None, "error": "`agy models` không trả lời.", "kind": "timeout"})
    a = {x["id"]: x for x in AG.public_agents()["agents"]}
    assert a["gemini"]["available"] is False and "agy models" in a["gemini"]["reason"] and a["gemini"]["reason_code"] == "timeout"
    assert a["opus"]["available"] is True
    models_mod.reset_cache()
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: ([{"slug": "other", "label": "O"}], None))
    models_mod._cache.update({"at": __import__("time").time(), "ttl": 60, "rows": [{"slug": "other", "label": "O"}], "error": None, "kind": None})
    g = {x["id"]: x for x in AG.public_agents()["agents"]}["gemini"]
    assert g["available"] is False and g["reason_code"] == "model_not_listed"


def test_a_mock_agent_is_available(mock_agents):
    out = AG.public_agents()
    assert {x["id"]: x["available"] for x in out["agents"]} == {"gem": True, "ops": False}      # `mock-b` is no configured model: its reason says so
    assert {x["id"]: x["reason_code"] for x in out["agents"]}["ops"] == "unknown_model"


def test_availability_never_raises(monkeypatch):
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: (_ for _ in ()).throw(RuntimeError("boom")))
    a = {x["id"]: x for x in AG.public_agents()["agents"]}
    assert a["gemini"]["available"] is False and a["gemini"]["reason_code"] == "unreadable"
