"""The agent routes (contract docs/design/2026-11-18-agent-choice.md, section 5) and what they change in the script jobs: a job started
without a model uses the project's agent and says which one it used. The agents here are MOCK agents (a private choices file and a private
models file); no real model is called. Run in the snapshot of a worker (see docs/WINDOWS.md)."""
import json
import shutil
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti import agents as AG  # noqa: E402
from bti.editor.app import create_app  # noqa: E402
from bti.script import env as env_mod, models as models_mod  # noqa: E402
from bti.script.providers import ProviderError, mock as mock_mod, set_transport  # noqa: E402

REAL = REPO / "projects" / "arnolfini-from-books"
pytestmark = pytest.mark.skipif(not (REAL / "project.json").is_file(), reason="projects/arnolfini-from-books is missing")
A, B = "/api/projects/arn", "/api/projects/arn2"

MODELS = [{"id": "agy", "label": "Antigravity CLI", "provider": "antigravity", "default": True, "timeout": 900},
          {"id": "claude:claude-opus-5-5@high", "label": "Claude Code: Opus 5.5 High", "provider": "claudecode", "model": "claude-opus-5-5", "effort": "high", "timeout": 900},
          {"id": "mock", "label": "Mock (thử)", "provider": "mock", "model": "mock", "key_env": None},
          {"id": "mock-b", "label": "Mock B", "provider": "mock", "model": "mock", "key_env": None},
          {"id": "paid", "label": "Trả tiền", "provider": "openrouter", "model": "x/y", "key_env": "NO_SUCH_KEY_FOR_TESTS"}]
CHOICES = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}, {"id": "ops", "label": "Opus giả", "model": "mock-b"},
                                         {"id": "pay", "label": "Agent trả tiền", "model": "paid"}],
           "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


@pytest.fixture(autouse=True)
def _isolation(tmp_path, monkeypatch):
    (tmp_path / "run").mkdir()
    (tmp_path / "models.json").write_text(json.dumps(MODELS), encoding="utf-8")
    (tmp_path / "choices.json").write_text(json.dumps(CHOICES), encoding="utf-8")
    monkeypatch.setenv("BTI_MODELS_FILE", str(tmp_path / "models.json"))
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(tmp_path / "choices.json"))
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    monkeypatch.delenv("NO_SUCH_KEY_FOR_TESTS", raising=False)
    models_mod.reset_cache()
    env_mod._cache.clear()
    set_transport(None)
    mock_mod.CALLS.clear()
    yield
    set_transport(None)


@pytest.fixture()
def c(tmp_path):
    root = tmp_path / "projects"
    root.mkdir()
    for pid in ("arn", "arn2"):
        shutil.copytree(REAL, root / pid, ignore=shutil.ignore_patterns("script", "cache", "history"))
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    with TestClient(app) as cl:
        cl.root = root
        yield cl


def job(c, jid, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.03)
    raise AssertionError(j)


def rev(c, base):
    return c.get(base + "/agent").json()["rev"]


# ---------------------------------------------------------------- GET /api/agents and the machine default
def test_agents_list_has_the_shape_of_the_contract(c):
    r = c.get("/api/agents")
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"agents", "default", "machine_default", "warnings"} and d["default"] == "gem" and d["machine_default"] is None
    a = {x["id"]: x for x in d["agents"]}
    assert set(a["gem"]) == {"id", "label", "model", "available", "reason", "reason_code"}
    assert (a["gem"]["label"], a["gem"]["model"], a["gem"]["available"], a["gem"]["reason"]) == ("Gemini giả", "mock", True, None)
    assert a["pay"]["available"] is False and a["pay"]["reason"]


def test_the_real_file_lists_the_two_agents_with_their_availability(c, monkeypatch):
    monkeypatch.delenv("BTI_AGENT_CHOICES_FILE")
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: ([{"slug": "gemini-3.8-flash-high", "label": "G"}], None))
    monkeypatch.setattr(models_mod, "claude_status", lambda refresh=False: {"ok": False, "kind": "auth", "reason": "not_signed_in",
                                                                            "message": "Claude Code trên máy chủ chưa đăng nhập. Đăng nhập một lần."})
    d = c.get("/api/agents").json()
    assert [(x["id"], x["label"], x["available"]) for x in d["agents"]] == [("gemini", "Gemini 3.8 Flash", True), ("opus", "Opus 5.5 High", False)]
    assert d["agents"][1]["reason"].startswith("Claude Code trên máy chủ chưa đăng nhập")
    assert c.get("/api/agents?refresh=1").status_code == 200


def test_the_machine_default_is_put_and_cleared(c, tmp_path):
    r = c.put("/api/settings/agent", json={"agent": "ops"})
    assert r.status_code == 200 and r.json()["machine_default"] == "ops"
    assert c.get("/api/agents").json()["machine_default"] == "ops"
    assert json.loads((tmp_path / "run" / "settings.json").read_text(encoding="utf-8"))["agent"] == "ops"
    r = c.put("/api/settings/agent", json={"agent": None})
    assert r.status_code == 200 and r.json()["machine_default"] is None


def test_the_machine_default_refuses_an_unknown_agent(c):
    r = c.put("/api/settings/agent", json={"agent": "nope"})
    assert r.status_code == 422 and r.json()["code"] == "unknown_agent" and r.json()["allowed"] == ["gem", "ops", "pay"]
    assert c.put("/api/settings/agent", json={}).status_code == 422
    assert c.get("/api/agents").json()["machine_default"] is None


def test_the_model_settings_still_work_next_to_the_machine_default(c):
    assert c.put("/api/settings/agent", json={"agent": "ops"}).status_code == 200
    assert c.put("/api/settings/models", json={"script.outline": "mock"}).status_code == 200
    got = c.get("/api/settings/models").json()
    assert {r["role"]: r["model"] for r in got["roles"]}["script.outline"] == "mock"
    assert c.get("/api/agents").json()["machine_default"] == "ops"


# ---------------------------------------------------------------- the project's choice
def test_a_project_without_a_choice(c):
    d = c.get(A + "/agent").json()
    assert set(d) == {"rev", "agent", "steps", "effective", "warnings"} and d["agent"] is None and d["steps"] == {} and d["warnings"] == []
    assert set(d["effective"]) == {"script", "picks", "storyboard"}
    assert set(d["effective"]["script"]) == {"id", "label", "model", "source"}


def test_a_new_project_starts_on_the_machines_default(c):
    c.put("/api/settings/agent", json={"agent": "ops"})
    e = c.get(A + "/agent").json()["effective"]
    assert {s: (x["id"], x["source"]) for s, x in e.items()} == {"script": ("ops", "default"), "picks": ("ops", "default"), "storyboard": ("ops", "default")}
    assert c.get(B + "/agent").json()["effective"]["script"]["label"] == "Opus giả"


def test_put_a_step_choice_then_the_whole_project(c):
    d = c.put(A + "/agent", json={"steps": {"script": "ops"}, "base_rev": rev(c, A)}).json()
    assert d["steps"] == {"script": "ops"} and d["effective"]["script"] == {"id": "ops", "label": "Opus giả", "model": "mock-b", "source": "step"}
    assert d["effective"]["storyboard"]["source"] == "role"
    d = c.put(A + "/agent", json={"agent": "gem", "steps": None, "base_rev": d["rev"]}).json()        # "Dùng cho cả dự án"
    assert (d["agent"], d["steps"]) == ("gem", {}) and {x["source"] for x in d["effective"].values()} == {"project"}
    assert c.get(A + "/agent").json() == d
    assert (c.root / "arn" / "agent.json").is_file() and not (c.root / "arn2" / "agent.json").exists()


def test_a_second_project_is_not_affected(c):
    c.put(A + "/agent", json={"agent": "ops", "base_rev": rev(c, A)})
    assert c.get(B + "/agent").json()["agent"] is None


def test_clearing_a_key_with_null_and_leaving_a_key_out(c):
    d = c.put(A + "/agent", json={"agent": "ops", "steps": {"script": "gem", "picks": "gem"}, "base_rev": rev(c, A)}).json()
    d = c.put(A + "/agent", json={"steps": {"script": None}, "base_rev": d["rev"]}).json()
    assert (d["agent"], d["steps"]) == ("ops", {"picks": "gem"})
    d = c.put(A + "/agent", json={"agent": None, "base_rev": d["rev"]}).json()
    assert (d["agent"], d["steps"]) == (None, {"picks": "gem"})


def test_a_stale_write_is_409_and_carries_the_current_revision(c):
    r0 = rev(c, A)
    d = c.put(A + "/agent", json={"agent": "ops", "base_rev": r0}).json()
    r = c.put(A + "/agent", json={"agent": "gem", "base_rev": r0})
    assert r.status_code == 409 and r.json()["code"] == "stale" and r.json()["rev"] == d["rev"]
    assert c.get(A + "/agent").json()["agent"] == "ops"


def test_bad_ids_are_422_and_nothing_is_written(c):
    base = rev(c, A)
    for body, code in (({"agent": "nope"}, "unknown_agent"), ({"steps": {"script": "nope"}}, "unknown_agent"), ({"steps": {"nowhere": "gem"}}, "unknown_step"),
                       ({"steps": 5}, "invalid_payload"), ({"agent": "gem", "base_rev": None}, "invalid_payload")):
        r = c.put(A + "/agent", json={"base_rev": base, **body})
        assert r.status_code == 422 and r.json()["code"] == code, (body, r.text)
    r = c.put(A + "/agent", json={"agent": "gem"})                                          # no base_rev at all
    assert r.status_code == 422 and r.json()["code"] == "invalid_payload"
    assert not (c.root / "arn" / "agent.json").exists()


def test_an_unknown_project_is_404(c):
    assert c.get("/api/projects/nope/agent").status_code == 404
    assert c.put("/api/projects/nope/agent", json={"agent": "gem", "base_rev": "x"}).status_code == 404
    assert c.get("/api/projects/Bad..Id/agent").status_code == 404


def test_a_body_that_is_not_an_object_is_422(c):
    assert c.put(A + "/agent", json=[1]).status_code == 422


# ---------------------------------------------------------------- a job without a model uses the agent and says which
def start(c, base, kind, **body):
    r = c.post(f"{base}/{kind}/generate", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_job_started_without_a_model_uses_the_projects_step_choice(c):
    c.put(A + "/agent", json={"steps": {"script": "ops"}, "base_rev": rev(c, A)})
    started = start(c, A, "outline")
    assert started["model"] == "mock-b" and started["agent"] == {"id": "ops", "label": "Opus giả", "model": "mock-b", "source": "step"}
    j = job(c, started["job_id"])
    assert j["state"] == "done", j
    assert j["model"] == "mock-b" and j["agent"] == {"id": "ops", "label": "Opus giả", "model": "mock-b", "source": "step"}
    assert mock_mod.CALLS[-1]["model"] == "mock-b"
    assert c.get(A + "/outline").json()["outline"]["source"]["model"] == "mock-b"
    assert c.get(f"/api/projects/arn/script/jobs").json()[0]["agent"]["id"] == "ops"


def test_the_other_project_uses_its_own_agent(c):
    c.put(A + "/agent", json={"steps": {"script": "ops"}, "base_rev": rev(c, A)})
    c.put(B + "/agent", json={"agent": "gem", "base_rev": rev(c, B)})
    j = job(c, start(c, B, "outline")["job_id"])
    assert j["model"] == "mock" and j["agent"]["id"] == "gem" and j["agent"]["source"] == "project"


def test_narration_resolves_through_the_same_function(c):
    c.put(A + "/agent", json={"agent": "ops", "base_rev": rev(c, A)})
    assert job(c, start(c, A, "outline")["job_id"])["state"] == "done"
    o = c.get(A + "/outline").json()
    assert c.post(A + "/outline/approve", json={"rev": o["rev"]}).status_code == 200
    started = start(c, A, "narration", force=True)
    assert started["agent"]["id"] == "ops" and started["agent"]["source"] == "project"
    j = job(c, started["job_id"])
    assert j["state"] == "done" and j["model"] == "mock-b" and j["agent"]["id"] == "ops"
    assert c.get(A + "/narration").json()["narration"]["source"]["model"] == "mock-b"


def test_a_machine_default_applies_when_the_project_has_no_choice(c):
    c.put("/api/settings/agent", json={"agent": "ops"})
    started = start(c, A, "outline")
    assert started["agent"]["id"] == "ops" and started["agent"]["source"] == "default" and started["model"] == "mock-b"
    job(c, started["job_id"])


def test_a_request_that_names_a_model_keeps_working_as_today(c):
    c.put(A + "/agent", json={"agent": "ops", "base_rev": rev(c, A)})
    started = start(c, A, "outline", model="mock")
    assert started["model"] == "mock" and started["agent"] == {"id": "gem", "label": "Gemini giả", "model": "mock", "source": "request"}
    assert job(c, started["job_id"])["model"] == "mock"
    r = c.post(A + "/outline/generate", json={"model": "nope"})
    assert r.status_code == 404
    r = c.post(A + "/outline/generate", json={"model": "paid"})
    assert r.status_code == 409 and r.json()["missing_env"] == "NO_SUCH_KEY_FOR_TESTS" and "code" not in r.json()


@pytest.mark.parametrize("bad", ["", "  ", 5, ["mock"], {"id": "mock"}])
def test_a_model_that_is_not_a_model_id_is_still_refused(c, bad):
    r = c.post(A + "/outline/generate", json={"model": bad})
    assert r.status_code == 400 and "model" in r.json()["detail"]
    assert c.get(A + "/script/jobs").json() == []


def test_an_agent_that_cannot_run_is_409_agent_unavailable(c):
    c.put(A + "/agent", json={"steps": {"script": "pay"}, "base_rev": rev(c, A)})
    r = c.post(A + "/outline/generate", json={})
    assert r.status_code == 409 and r.json()["code"] == "agent_unavailable"
    assert r.json()["agent"] == {"id": "pay", "label": "Agent trả tiền", "model": "paid", "source": "step"} and r.json()["detail"]
    assert c.get(A + "/script/jobs").json() == []


def test_an_agent_whose_model_is_unknown_is_409_agent_unavailable(c, tmp_path):
    bad = dict(CHOICES, agents=CHOICES["agents"] + [{"id": "ghost", "label": "Agent ma", "model": "no-such-model"}])
    (tmp_path / "choices.json").write_text(json.dumps(bad), encoding="utf-8")
    c.put(A + "/agent", json={"agent": "ghost", "base_rev": rev(c, A)})
    r = c.post(A + "/outline/generate", json={})
    assert r.status_code == 409 and r.json()["code"] == "agent_unavailable" and r.json()["agent"]["id"] == "ghost"
    assert "Agent ma" in r.json()["detail"]


# ---------------------------------------------------------------- the quota answer carries the time
def test_a_quota_answer_is_in_the_job_record_with_the_agent_and_the_time(c, monkeypatch):
    def quota(spec, system, user, **kw):
        e = ProviderError("rate_limit", "Hạn mức của gói Claude Code đã hết. Thử lại sau 4 giờ 30 phút (khoảng 18:20).")
        e.retry_after_seconds = 16200
        raise e
    monkeypatch.setattr(mock_mod, "complete", quota)
    c.put(A + "/agent", json={"agent": "ops", "base_rev": rev(c, A)})
    j = job(c, start(c, A, "outline")["job_id"])
    assert j["state"] == "error" and j["error_kind"] == "rate_limit"
    assert j["retry_after_seconds"] == 16200 and j["retry_at"]
    assert j["agent"]["id"] == "ops" and j["agent"]["label"] == "Opus giả"
    assert c.get(f"/api/jobs/{j['id']}").json()["retry_after_seconds"] == 16200                       # also from the persisted record
    assert c.app.state.script_jobs.persisted(j["id"])["agent"]["id"] == "ops"


def test_a_quota_answer_without_a_time_has_no_time(c, monkeypatch):
    def quota(spec, system, user, **kw):
        raise ProviderError("rate_limit", "rate limit or quota reached (mock)")
    monkeypatch.setattr(mock_mod, "complete", quota)
    c.put(A + "/agent", json={"agent": "gem", "base_rev": rev(c, A)})
    j = job(c, start(c, A, "outline")["job_id"])
    assert j["error_kind"] == "rate_limit" and j["retry_after_seconds"] is None and j["retry_at"] is None


def test_the_job_record_of_a_named_model_without_a_quota_has_no_time(c):
    j = job(c, start(c, A, "outline", model="mock")["job_id"])
    assert j["state"] == "done" and j["retry_after_seconds"] is None and j["retry_at"] is None
