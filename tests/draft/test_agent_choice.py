"""Steps 5's model calls resolve through `bti.agents.model_for_project` when the request names no model: the draft, the fast edit and the
deep edit. The job record, the turn and the answer of the start routes say which agent was used; a request that names a model keeps working
as before. The agents are an agy agent (the fake `agy` program of the draft tests) and a mock agent; no real model is called."""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from bti import agents as AG
from bti.draft import run as R
from bti.draft.inputs import DraftError
from bti.editor import draft_api
from bti.editor.common import ApiError
from bti.script.providers import ProviderError, mock
from test_agy import fake  # noqa: F401  (the fake agy program and its fixture)
from test_edit_routes_e2e import env, sb_proj, why  # noqa: F401  (the app on a project with a storyboard, the mock model)
from test_run import finish, gf, mgr  # noqa: F401

GEM = {"id": "gem", "label": "Gemini giả", "model": "agy:gemini-x"}
ALT = {"id": "alt", "label": "Agent thứ hai", "model": "agy:other-y"}
MK = {"id": "mk", "label": "Mock giả", "model": "mock"}
STEPS = {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}


@pytest.fixture()
def agents(tmp_path, monkeypatch):
    f = tmp_path / "choices.json"
    f.write_text(json.dumps({"default": "gem", "agents": [GEM, ALT, MK], "steps": STEPS}), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(f))
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    return f


def choose(pdir, **doc):
    (pdir / "agent.json").write_text(json.dumps({"schema": "bti.agent/1", "agent": None, "steps": {}, **doc}), encoding="utf-8")


@pytest.fixture()
def client(proj, agents):
    app = FastAPI()
    app.state.projects_root = proj.parent

    @app.exception_handler(ApiError)
    async def _e(_, e):
        return JSONResponse({"detail": e.detail, **e.extra}, status_code=e.status)
    app.include_router(draft_api.router)
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------- what the panel is told
def test_the_overview_names_the_agent_the_next_draft_uses(client, proj):
    d = client.get("/api/projects/%s/draft" % proj.name).json()
    assert d["agent"]["source"] == "role" and d["default_model"] == d["agent"]["model"]
    choose(proj, steps={"storyboard": "alt"})
    d = client.get("/api/projects/%s/draft" % proj.name).json()
    assert d["agent"] == {"id": "alt", "label": "Agent thứ hai", "model": "agy:other-y", "source": "step"} and d["default_model"] == "agy:other-y"


def test_the_model_list_route_still_answers_and_its_default_is_the_projects(client, proj, monkeypatch):
    from bti.script import models as models_mod
    monkeypatch.setattr(models_mod, "agy_models", lambda refresh=False: ([{"slug": "other-y", "label": "Other"}], None))
    choose(proj, agent="alt")
    d = client.get("/api/projects/%s/draft/models" % proj.name).json()
    assert d["default"] == "agy:other-y" and d["agent"]["id"] == "alt" and d["models"] == [{"slug": "other-y", "label": "Other"}] and d["error"] is None


# ---------------------------------------------------------------- the draft job
def test_a_draft_without_a_model_uses_the_projects_agent_and_says_so(proj, mgr, fake, agents):
    choose(proj, steps={"storyboard": "alt"})
    rec = R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python")
    assert rec["meta"]["model"] == "agy:other-y" and rec["meta"]["agent"] == {"id": "alt", "label": "Agent thứ hai", "model": "agy:other-y", "source": "step"}
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["error_code"], j["log_tail"])
    a = fake.calls()[0]["argv"]
    assert a[a.index("--model") + 1] == "other-y"                                         # the program is started with the agent's model
    doc = json.loads((proj / "proposals" / (j["result"]["proposal_id"] + ".json")).read_text(encoding="utf-8"))
    assert doc["author"] == "agent:agy:other-y"
    last = R.last_run(proj)
    assert last["model"] == "agy:other-y" and last["agent"]["id"] == "alt"


def test_the_projects_agent_applies_when_the_step_has_no_choice(proj, mgr, fake, agents):
    choose(proj, agent="alt")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    assert j["meta"]["agent"]["source"] == "project" and j["state"] == "done"
    a = fake.calls()[0]["argv"]
    assert a[a.index("--model") + 1] == "other-y"


def test_a_draft_that_names_a_model_keeps_it(proj, mgr, fake, agents):
    choose(proj, agent="alt")
    rec = R.start(proj.name, proj, provider="agy", model="gemini-x", manager=mgr, guard_factory=gf, python="python")
    assert rec["meta"]["model"] == "agy:gemini-x" and rec["meta"]["agent"] == {"id": "gem", "label": "Gemini giả", "model": "agy:gemini-x", "source": "request"}
    j = finish(mgr, rec)
    assert j["state"] == "done"
    a = fake.calls()[0]["argv"]
    assert a[a.index("--model") + 1] == "gemini-x"
    doc = json.loads((proj / "proposals" / (j["result"]["proposal_id"] + ".json")).read_text(encoding="utf-8"))
    assert doc["author"] == "agent:agy:gemini-x"


def test_the_start_route_answers_with_the_model_and_the_agent(client, proj, fake):
    choose(proj, steps={"storyboard": "alt"})
    r = client.post("/api/projects/%s/draft/start" % proj.name, json={"provider": "agy"})
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "agy:other-y" and r.json()["agent"]["id"] == "alt" and r.json()["agent"]["label"] == "Agent thứ hai"
    from bti.longjob import manager
    manager.wait(r.json()["job_id"], timeout=120)


def test_the_automatic_draft_has_no_agent(client, proj, agents):
    r = client.post("/api/projects/%s/draft/start" % proj.name, json={"provider": "auto"})
    assert r.status_code == 200 and r.json()["agent"] is None
    from bti.longjob import manager
    j = manager.wait(r.json()["job_id"], timeout=120)
    assert j["state"] == "done" and R.last_run(proj)["agent"] is None


# ---------------------------------------------------------------- Claude Code that is missing or signed out is a 409, not a 422
@pytest.mark.parametrize("code", ["claude_missing", "claude_auth"])
def test_the_start_routes_answer_409_for_a_claude_code_that_cannot_run(client, proj, monkeypatch, code):
    def refuse(model_id):
        raise DraftError(code, "Claude Code is not usable")
    monkeypatch.setattr(R, "_check_agent_installed", refuse)
    r = client.post("/api/projects/%s/draft/start" % proj.name, json={"provider": "agy"})
    assert r.status_code == 409 and r.json()["code"] == code


@pytest.mark.parametrize("code", ["claude_missing", "claude_auth"])
def test_the_edit_route_answers_409_for_a_claude_code_that_cannot_run(env, monkeypatch, code):
    def refuse(model_id):
        raise DraftError(code, "Claude Code is not usable")
    monkeypatch.setattr(R, "_check_agent_installed", refuse)
    ids = env.content_ids("c01")[:2]
    r = env.post_edit("làm chậm hơn", ids, mode="deep")
    assert r.status_code == 409 and r.json()["code"] == code, r.text


# ---------------------------------------------------------------- the edit: fast and deep
def test_a_fast_edit_without_a_model_uses_the_projects_agent(env, agents):
    choose(env.pdir, agent="mk")
    ids = env.content_ids("c01")[:2]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "x"}})])
    r = env.post_edit("làm chậm hơn", ids, mode="fast")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"] == "mock" and body["agent"] == {"id": "mk", "label": "Mock giả", "model": "mock", "source": "project"}
    job = env.wait_job(body["job_id"])
    assert job["state"] == "done", why(job)
    assert job["meta"]["agent"]["id"] == "mk" and job["meta"]["model"] == "mock"
    turn = env.turn(body["turn_id"])
    assert turn["model"] == "mock" and turn["agent"]["id"] == "mk" and turn["status"] == "applied"
    assert mock.CALLS[-1]["model"] == "mock"


def test_a_fast_edit_that_names_a_model_keeps_it(env, agents):
    choose(env.pdir, agent="alt")
    ids = env.content_ids("c01")[:2]
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "x"}})])
    r = env.post_edit("làm chậm hơn", ids, mode="fast", model="mock")
    assert r.status_code == 200 and r.json()["agent"]["source"] == "request" and r.json()["agent"]["id"] == "mk"
    job = env.wait_job(r.json()["job_id"])
    assert job["state"] == "done", why(job)
    assert env.turn(r.json()["turn_id"])["model"] == "mock"


def test_a_fast_edit_without_any_choice_uses_the_role_setting(env, agents):
    ids = env.content_ids("c01")[:2]                                  # the env fixture put the role edit.fast on the mock model
    mock.set_canned([env.edit_answer(ids, {ids[0]: {"note": "x"}})])
    r = env.post_edit("làm chậm hơn", ids, mode="fast")
    assert r.json()["agent"]["source"] == "role" and r.json()["agent"]["id"] == "mk"
    assert env.wait_job(r.json()["job_id"])["state"] == "done"


@pytest.mark.parametrize("code,retry", [("agy_rate_limit", None), ("claude_rate_limit", 16200)])
def test_a_quota_answer_of_the_fast_edit_keeps_the_agent_and_the_time(env, agents, monkeypatch, code, retry):
    choose(env.pdir, agent="mk")

    def quota(spec, system, user, **kw):
        e = ProviderError("rate_limit", "Hạn mức đã hết.")
        e.retry_after_seconds = retry
        if code.startswith("claude"):
            e.code = code
        raise e
    monkeypatch.setattr(mock, "complete", quota)
    ids = env.content_ids("c01")[:2]
    r = env.post_edit("làm chậm hơn", ids, mode="fast")
    job = env.wait_job(r.json()["job_id"])
    turn = env.turn(r.json()["turn_id"])
    assert job["state"] == "error" and turn["status"] == "failed" and turn["error"] == code
    assert turn["agent"]["id"] == "mk"
    if retry:
        assert turn["retry_after_seconds"] == retry and turn["retry_at"] and job["meta"]["retry_after_seconds"] == retry
    else:
        assert turn["retry_after_seconds"] is None and turn["retry_at"] is None


def test_a_deep_edit_without_a_model_starts_the_agent_of_the_project(env, fake, agents, monkeypatch):
    choose(env.pdir, steps={"storyboard": "alt"})
    ids = env.content_ids("c01")[:2]
    env.deep_cfg(fake.dir, {ids[0]: {"note": "deep note"}})
    r = env.post_edit("làm chậm hơn", ids, mode="deep")
    assert r.status_code == 200, r.text
    assert r.json()["model"] == "agy:other-y" and r.json()["agent"]["id"] == "alt"
    job = env.wait_job(r.json()["job_id"])
    assert job["state"] == "done", why(job)
    a = fake.calls()[0]["argv"]
    assert a[a.index("--model") + 1] == "other-y"
    turn = env.turn(r.json()["turn_id"])
    assert turn["model"] == "agy:other-y" and turn["agent"]["id"] == "alt" and turn["path"] == "deep"


def test_an_escalated_edit_records_the_agent_that_did_the_deep_part(env, fake, agents):
    """`escalate` never starts the slow path by itself any more: the owner's button sends the same request with mode deep, and THAT turn records the
    agent of the deep part (the role `edit.deep`), while the first turn keeps the agent of the fast part."""
    from bti import settings
    settings.save_model_settings({"edit.deep": "agy:other-y"})        # the fast part runs on the mock model, the deep part on the agy agent
    ids = env.content_ids("c01")[:2]
    mock.set_canned([json.dumps({"status": "escalate", "summary": "", "reason": "Cần nhìn kỹ vào tranh.", "ops": []}, ensure_ascii=False)])
    r = env.post_edit("sửa nhiều", ids, mode="auto")
    assert r.status_code == 200 and r.json()["agent"]["id"] == "mk"       # the turn starts on the fast path
    job = env.wait_job(r.json()["job_id"])
    first = env.turn(r.json()["turn_id"])
    assert job["state"] == "done", why(job)
    assert first["status"] == "escalate" and first["path"] == "fast" and first["escalated"] is False and first["agent"]["id"] == "mk"
    env.deep_cfg(fake.dir, {ids[0]: {"note": "deep note"}})
    r = env.post_edit("sửa nhiều", ids, mode="deep")
    job = env.wait_job(r.json()["job_id"])
    turn = env.turn(r.json()["turn_id"])
    assert job["state"] == "done", why(job)
    assert turn["path"] == "deep"
    assert turn["model"] == "agy:other-y" and turn["agent"] == {"id": "alt", "label": "Agent thứ hai", "model": "agy:other-y", "source": "role"}