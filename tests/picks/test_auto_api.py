"""The routes of the automatic picks job (POST and GET /api/projects/{pid}/picks/auto) and its place in the state answer, through the real app."""
import json
import tempfile
import time

import pytest
from auto_fixtures import paid  # noqa: F401
from auto_helpers import FakeAgent, fake_book_thumb, fake_thumb, install_agent, install_sources, make_auto_project
from fastapi.testclient import TestClient
from picks_helpers import mount

from bti import settings as S
from bti.editor.app import create_app
from bti.longjob import manager
from bti.picks import doc
from bti.picks.auto import search as asearch
from bti.script import env as env_mod, models as models_mod

MOCK_AGENTS = {"default": "gem", "agents": [{"id": "gem", "label": "Gemini giả", "model": "mock"}],
               "steps": {"script": ["script.outline", "script.narration"], "picks": ["picks"], "storyboard": ["draft", "edit.fast", "edit.deep"]}}


@pytest.fixture
def api(tmp_path, monkeypatch, paid):
    monkeypatch.setenv("BTI_ENV_FILE", str(tmp_path / "no.env"))
    monkeypatch.setenv("BTI_AGY_BIN", "")
    monkeypatch.setenv("BTI_CLAUDE_BIN", "")
    (tmp_path / "run").mkdir()
    monkeypatch.setenv("BTI_SETTINGS_FILE", str(tmp_path / "run" / "settings.json"))
    # titlestep: the title agent is an unknown model here (not usable), so the actions of the title never advance in these worlds; tests/title switches it on
    (tmp_path / "agents.json").write_text(json.dumps({**{r: "mock" for r in S.ROLES}, "script.title": "no-title-agent"}), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENTS_FILE", str(tmp_path / "agents.json"))
    (tmp_path / "choices.json").write_text(json.dumps(MOCK_AGENTS), encoding="utf-8")
    monkeypatch.setenv("BTI_AGENT_CHOICES_FILE", str(tmp_path / "choices.json"))
    models_mod.reset_cache()
    env_mod._cache.clear()
    root = tmp_path / "projects"
    root.mkdir()
    pdir = make_auto_project(root)
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    install_sources(monkeypatch)
    agent = install_agent(monkeypatch, FakeAgent())
    monkeypatch.setattr(asearch, "default_fetch_thumb", fake_thumb)
    monkeypatch.setattr(asearch, "default_book_thumb", fake_book_thumb)
    app = create_app(projects_root=root, engine_module=None, media_module=None)
    mount(app)
    with TestClient(app, raise_server_exceptions=False) as c:
        c.root, c.pdir, c.pid, c.agent = root, pdir, pdir.name, agent
        c.u = lambda tail="": "/api/projects/%s/picks/auto%s" % (pdir.name, tail)
        yield c
    assert paid == []


def wait(c, job_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get("/api/longjobs/" + job_id).json()
        if j["state"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.05)
    raise AssertionError(j)


def err(r, status, code):
    assert r.status_code == status, r.text
    b = r.json()
    assert b["code"] == code and b["fix"] and b["retry"] in ("no", "after_fix", "later") and b["detail"], b          # every refusal says what to change
    return b


# ---------------------------------------------------------------------------------------------------------------- the route
def test_start_runs_the_job_and_the_overview_tells_the_result(api):
    r = api.post(api.u(), json={})
    assert r.status_code == 200
    body = r.json()
    assert body["lines"] == 6 and body["model"] == "mock" and body["agent"]["id"] == "gem" and len(body["job_id"]) == 16
    job = wait(api, body["job_id"])
    assert job["state"] == "done", job.get("error")
    assert job["result"]["sentence"] == "Agent đã chọn hình cho 6/6 đoạn." and job["meta"]["action"] == "auto" and job["kind"] == "picks"
    ov = api.get(api.u()).json()
    assert ov["running"] is None and ov["last"]["result"]["lines_done"] == 6 and ov["agent"]["id"] == "gem"
    assert ov["reasons"]["b0001"] == "Mở bằng cả bức tranh." and ov["limits"]["plan"] == {"minutes": 30, "steps": 120, "repairs": 1} and ov["limits"]["choose"]["steps"] == 220
    assert ov["limits"]["search_seconds"] == 600 and ov["limits"]["write_seconds"] == 1500
    # what the page shows is in the picks answer too, and the job never approved
    page = api.get("/api/projects/%s/picks" % api.pid).json()
    assert page["approved"] is False and page["picks"]["beats"]["b0006"]["status"] == "skip" and [i["code"] for i in page["issues"] if i["level"] == "error"] == []
    # the stage says what is going on while the job runs
    assert api.get("/api/projects/%s/pipeline" % api.pid).status_code == 200


def test_the_request_is_checked_and_a_refusal_says_what_to_change(api):
    for body, field in (({"beats": "b0001"}, "beats"), ({"beats": [1]}, "beats"), ({"redo": "yes"}, "redo"), ({"base_rev": 3}, "base_rev")):
        b = err(api.post(api.u(), json=body), 422, "invalid_field")
        assert b["fields"][0]["path"] == field
    err(api.post(api.u(), json={"model": 5}), 422, "bad_model")
    err(api.post(api.u(), json={"model": "no way!"}), 422, "bad_model")
    err(api.post(api.u(), json=[1]), 422, "invalid_request")
    err(api.post(api.u(), json={"beats": ["b0099"]}), 404, "not_found")
    err(api.post(api.u(), json={"beats": []}), 422, "invalid_field")
    b = err(api.post(api.u(), json={"base_rev": "0" * 40}), 409, "stale")
    assert b["current_rev"] == doc.revision(doc.load_or_new(api.pdir))
    assert err(api.post("/api/projects/nope/picks/auto", json={}), 404, "project_not_found")
    assert api.get("/api/projects/nope/picks/auto").status_code == 404
    assert api.get(api.u()).json()["last"] is None


def test_a_project_that_is_not_ready_is_refused_with_its_reason(api):
    with doc.Held(api.pdir):
        d = doc.load_or_new(api.pdir)
        d["main_asset"] = None
        doc.save(api.pdir, d)
    err(api.post(api.u(), json={}), 409, "picks_no_main")
    from bti.script import store as sstore
    with doc.Held(api.pdir):
        d["main_asset"] = "A"
        doc.save(api.pdir, d)
    n = sstore.load_narration(api.pdir)
    n.chapters[0].beats[0].text += " More words."
    sstore.save_narration(api.pdir, n)
    err(api.post(api.u(), json={}), 409, "narration_not_approved")


def test_every_line_settled_and_an_approved_document_say_so_and_redo_is_the_way(api):
    from bti.picks import context
    job = wait(api, api.post(api.u(), json={}).json()["job_id"])
    assert job["state"] == "done"
    err(api.post(api.u(), json={}), 409, "picks_nothing_to_do")
    nv = context.narration_view(api.pdir)
    with doc.Held(api.pdir):
        doc.stamp_approval(api.pdir, doc.revision(doc.load(api.pdir)), nv["rev"])
    err(api.post(api.u(), json={}), 409, "picks_approved")
    again = api.post(api.u(), json={"redo": True})
    assert again.status_code == 200 and wait(api, again.json()["job_id"])["state"] == "done"


def hold_until_cancelled(mode, ws, kw):
    from bti.draft.providers.agy import AgyResult
    while not kw["cancel"]():
        time.sleep(0.02)
    return AgyResult(status="cancelled")


def test_a_second_start_while_one_runs_is_busy_and_cancel_stops_it(api):
    api.agent.hook = hold_until_cancelled
    jid = api.post(api.u(), json={}).json()["job_id"]
    b = err(api.post(api.u(), json={}), 409, "busy")
    assert b["job_id"] == jid
    ov = api.get(api.u()).json()
    assert ov["running"]["id"] == jid and ov["running"]["meta"]["action"] == "auto"
    from bti import picks
    assert picks.state(api.pdir)["detail"] == "Agent đang chọn hình."                        # the stage says who is working
    assert api.post("/api/longjobs/%s/cancel" % jid, json={}).status_code == 200
    assert wait(api, jid)["state"] == "cancelled"
    assert api.get(api.u()).json()["running"] is None and doc.load_or_new(api.pdir)["beats"] == {}


# ---------------------------------------------------------------------------------------------------------------- the state answer
def action(state, aid):
    return next(a for a in state["next_actions"] if a["id"] == aid)


def test_the_state_lists_picks_auto_as_a_long_job_that_uses_a_model_and_costs_time(api):
    st = api.get("/api/projects/%s/state" % api.pid).json()
    a = action(st, "picks.auto")
    assert (a["method"], a["path"], a["step"], a["label"]) == ("POST", "/api/projects/pk1/picks/auto", "picks", "Để agent chọn hình")
    assert a["long_job"] is True and a["uses_model"] is True and a["follow"] == "GET /api/longjobs/{job_id}"
    assert a["cost"] == {"kind": "model", "about": "about 20 minutes"} and a["gate"] is False and a["auto_ok"] is True
    assert a["agent"]["id"] == "gem" and a["ready"] is True and a["needs"] == [] and a["advances"] is True
    assert a["body"] == {"beats": None, "redo": False, "base_rev": doc.revision(doc.load_or_new(api.pdir)), "actor": "agent:mock"}      # join2: a caller names itself (the run, the command, the bench) as the operations' examples do
    ids = [x["id"] for x in st["next_actions"]]
    assert ids.index("picks.auto") < ids.index("picks.approve")                              # an agent that walks the project takes the agent before the gate
    assert action(st, "picks.approve")["gate"] is True
    # the body is valid as it stands: calling it starts the job
    r = api.post(a["path"], json=a["body"])
    assert r.status_code == 200 and wait(api, r.json()["job_id"])["state"] == "done"
    after = action(api.get("/api/projects/%s/state" % api.pid).json(), "picks.auto")
    assert after["advances"] is False and after["body"]["redo"] is True                       # every line settled: only `redo` runs it again
    again = api.post(after["path"], json=after["body"])
    assert again.status_code == 200 and wait(api, again.json()["job_id"])["state"] == "done"


def test_the_state_says_what_picks_auto_needs(api):
    with doc.Held(api.pdir):
        d = doc.load_or_new(api.pdir)
        d["main_asset"] = None
        doc.save(api.pdir, d)
    a = action(api.get("/api/projects/%s/state" % api.pid).json(), "picks.auto")
    assert a["ready"] is False and a["needs"] == ["main_asset"] and a["advances"] is False
    with doc.Held(api.pdir):
        d["main_asset"] = "A"
        doc.save(api.pdir, d)
    # while it runs: no second start, and the cancel action is there
    api.agent.hook = hold_until_cancelled
    jid = api.post(api.u(), json={}).json()["job_id"]
    st = api.get("/api/projects/%s/state" % api.pid).json()
    a = action(st, "picks.auto")
    assert a["ready"] is False and "no_running_job" in a["needs"]
    assert action(st, "picks.cancel")["job_id"] == jid and action(st, "picks.cancel")["path"] == "/api/longjobs/%s/cancel" % jid
    assert [j["kind"] for j in st["jobs"]] == ["picks"]
    api.post("/api/longjobs/%s/cancel" % jid, json={})
    wait(api, jid)


def test_the_codes_of_the_job_are_in_the_hints_the_document_and_the_page(api):
    from bti.editor import hints
    from bti.picks.auto import texts
    for code in ("picks_approved", "picks_nothing_to_do", "picks_auto_no_output", "picks_auto_limit", "picks_auto_tampered", "picks_auto_stale"):
        assert code in hints.HINTS and code in texts.VI, code
    assert all(c in hints.HINTS for c in texts.VI)
    text = hints.DOC_PATH.read_text(encoding="utf-8")
    assert "| `picks.auto` |" in text and "| `picks_auto_limit` |" in text
    page = (hints.REPO_ROOT / "bti" / "editor" / "static" / "js" / "errmsg.js").read_text(encoding="utf-8")
    for code, sentence in texts.VI.items():
        assert code in page, code                                                              # the page has its own sentence for every code the job can fail with
