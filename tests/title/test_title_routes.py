"""GET and PUT /api/projects/{pid}/title and POST /api/projects/{pid}/title/generate, through the real app with a fake agent: the answers, every refusal with its code, its
`fix` and its `retry`, who is recorded, and the storyboard-less case (the storyboard side is tests/title/test_title_storyboard.py)."""
import threading

import pytest
from run_helpers import wait_longjob
from title_helpers import FakeTitleAgent, good_choice, install_agent, make_title_project

from bti.editor import hints
from bti.script import store as sstore
from bti.title import store as T

PID = "pk1"
P = "/api/projects/%s" % PID
TITLE = "The Saint Who Was Also an Advertisement"


@pytest.fixture()
def tc(client, root, monkeypatch):
    make_title_project(root, PID)
    client.agent = install_agent(monkeypatch, FakeTitleAgent())
    return client


def generate(c, **body):
    r = c.post(P + "/title/generate", json=body)
    assert r.status_code == 200, r.text
    return wait_longjob(c, r.json()["job_id"])


def test_get_before_anything_says_none_and_names_the_agent_and_the_limits(tc):
    r = tc.get(P + "/title")
    assert r.status_code == 200
    b = r.json()
    assert b["state"] == "none" and b["title"] is None and b["candidates"] == [] and b["history"] == [] and b["written"] is None and b["stale"] is False
    assert b["rev"] == T.EMPTY_REV and b["narration_rev"] is None and b["current_narration_rev"] == T.narration_rev(tc.root / PID)
    assert b["agent"]["id"] == "gem" and b["agent"]["model"] == "mock" and b["running"] is None and b["problems"] == []
    assert b["limits"] == {"max_chars": 60, "best": [28, 55], "max_words": 9, "person_max_chars": 60} and b["storyboard"] == {"exists": False, "title": None, "same": False}
    assert tc.get("/api/projects/nope/title").status_code == 404


def test_generate_answers_the_job_and_the_title_follows(tc):
    r = tc.post(P + "/title/generate", json={})
    assert r.status_code == 200
    b = r.json()
    assert set(b) == {"job_id", "model", "agent"} and b["model"] == "mock" and b["agent"]["id"] == "gem"
    job = wait_longjob(tc, b["job_id"])
    assert job["state"] == "done" and job["kind"] == "title"
    g = tc.get(P + "/title").json()
    assert g["state"] == "done" and g["title"]["text"] == TITLE and g["title"]["source"] == "agent" and g["title"]["by"] == "agent:mock" and len(g["candidates"]) == 6
    assert g["candidates"][0]["text"] == TITLE and g["candidates"][1]["form"] == "question" and g["candidates"][1]["why"].startswith("Câu hỏi")
    assert g["narration_rev"] == g["current_narration_rev"] and g["written"]["model"] == "mock" and g["storyboard"]["exists"] is False
    assert g["rev"] != T.EMPTY_REV
    assert tc.get("/api/longjobs/%s" % b["job_id"]).json()["result"]["title"] == TITLE


def test_generate_takes_the_owners_note_and_an_actor(tc):
    job = generate(tc, note="  make it about the mirror ", actor="cli:operator")
    assert job["meta"]["note"] == "make it about the mirror" and job["meta"]["requested_by"] == "cli:operator"
    assert "make it about the mirror" in tc.agent.calls[0]["task"]
    assert tc.get(P + "/title").json()["written"]["note"] == "make it about the mirror"


@pytest.mark.parametrize("body, status, code", [
    ({"note": "x" * 601}, 422, "title_note_too_long"), ({"note": 5}, 422, "title_note_invalid"), ({"model": 5}, 422, "bad_model"),
    ({"model": "bad model!"}, 422, "bad_model"), ({"actor": "root"}, 422, "invalid_field"), ({"actor": 5}, 422, "invalid_field")])
def test_generate_refuses_a_bad_body(tc, body, status, code):
    r = tc.post(P + "/title/generate", json=body)
    assert r.status_code == status and r.json()["code"] == code and r.json()["fix"] and r.json()["retry"] in ("after_fix", "later", "no")
    assert tc.get(P + "/title").json()["state"] == "none"


def test_generate_is_refused_until_the_narration_is_approved(client, root, monkeypatch):
    make_title_project(root, PID, approved=False)
    install_agent(monkeypatch, FakeTitleAgent())
    r = client.post(P + "/title/generate", json={})
    assert r.status_code == 409 and r.json()["code"] == "narration_not_approved" and "approve" in r.json()["fix"].lower()


def test_generate_is_refused_while_another_agent_job_runs_and_while_a_title_job_runs(tc, monkeypatch):
    from bti.longjob import Part, manager
    hold = threading.Event()
    other = manager.start("draft", PID, tc.root / PID, [Part(key="p", title="x", run=lambda ctx: hold.wait(10), est_seconds=1)], {})
    try:
        r = tc.post(P + "/title/generate", json={})
        assert r.status_code == 409 and r.json()["code"] == "agent_job_running" and r.json()["job_id"] == other["id"] and r.json()["retry"] == "later"
    finally:
        hold.set()
    wait_longjob(tc, other["id"])
    gate = threading.Event()
    install_agent(monkeypatch, FakeTitleAgent(hook=lambda ws, kw: (gate.wait(10), None)[1]))
    first = tc.post(P + "/title/generate", json={})
    try:
        again = tc.post(P + "/title/generate", json={})
        assert again.status_code == 409 and again.json()["code"] == "longjob_running" and again.json()["job_id"] == first.json()["job_id"]
        assert tc.get(P + "/title").json()["running"]["id"] == first.json()["job_id"]
    finally:
        gate.set()
    assert wait_longjob(tc, first.json()["job_id"])["state"] == "done"


def test_generate_says_when_the_agent_cannot_run(client, root, monkeypatch):
    from bti.picks.auto import session
    from bti.draft.inputs import DraftError
    make_title_project(root, PID)
    monkeypatch.setattr(session, "check_installed", lambda m: (_ for _ in ()).throw(DraftError("claude_auth", "not signed in")))
    r = client.post(P + "/title/generate", json={})
    assert r.status_code == 409 and r.json()["code"] == "claude_auth"


# ------------------------------------------------------------------------------------------------------------ PUT
def put(c, rev=None, **body):
    rev = rev if rev is not None else c.get(P + "/title").json()["rev"]
    return c.put(P + "/title", json={"base_rev": rev, **body})


def test_put_text_sets_the_title_and_names_who_set_it(tc):
    r = put(tc, text="  The Saint Who Was Also an Ad ", actor="cli:operator")
    assert r.status_code == 200, r.text
    b = r.json()
    assert set(b) == {"rev", "state", "title", "candidates", "storyboard"} and b["state"] == "done" and b["storyboard"] is None
    assert b["title"]["text"] == "The Saint Who Was Also an Ad" and b["title"]["by"] == "cli:operator" and b["title"]["source"] == "person"
    g = tc.get(P + "/title").json()
    assert g["rev"] == b["rev"] and g["title"] == b["title"]
    assert put(tc, text="By The Page").json()["title"]["by"] == "human"


def test_put_option_takes_a_candidate_of_the_agent(tc):
    generate(tc)
    r = put(tc, option=3)
    assert r.status_code == 200 and r.json()["title"]["text"] == "The Two Strangers in the Mirror" and r.json()["title"]["option"] == 3 and r.json()["title"]["source"] == "person"
    assert len(r.json()["candidates"]) == 6 and tc.get(P + "/title").json()["history"][0]["text"] == TITLE


def test_a_persons_title_is_not_stale_after_the_narration_changes(tc):
    generate(tc)
    put(tc, option=2)
    n = sstore.load_narration(tc.root / PID)
    n.chapters[0].beats[0].text += " Changed."
    sstore.save_narration(tc.root / PID, n)
    g = tc.get(P + "/title").json()
    assert g["state"] == "done" and g["stale"] is False and g["narration_rev"] != g["current_narration_rev"]


def test_an_agents_title_is_stale_after_the_narration_changes(tc):
    generate(tc)
    n = sstore.load_narration(tc.root / PID)
    n.chapters[0].beats[0].text += " Changed."
    sstore.save_narration(tc.root / PID, n)
    g = tc.get(P + "/title").json()
    assert g["state"] == "stale" and g["stale"] is True and g["title"]["text"] == TITLE


@pytest.mark.parametrize("body, status, code", [
    ({"text": ""}, 422, "title_invalid"), ({"text": 5}, 422, "title_invalid"), ({"text": "a\nb"}, 422, "title_not_one_line"), ({"text": "x" * 61}, 422, "title_too_long"),
    ({"option": 1}, 422, "title_option_unknown"), ({}, 422, "title_choice_needed"), ({"text": "A", "option": 1}, 422, "title_choice_needed"),
    ({"text": "A", "actor": "root"}, 422, "invalid_field")])
def test_put_refuses_a_bad_title_and_writes_nothing(tc, body, status, code):
    r = put(tc, **body)
    assert r.status_code == status and r.json()["code"] == code and r.json()["fix"] and r.json()["retry"] == "after_fix"
    assert not (tc.root / PID / "title.json").exists()


def test_put_with_a_stale_revision_is_409_with_the_revision_now_and_writes_nothing(tc):
    generate(tc)
    old = T.EMPTY_REV
    now = tc.get(P + "/title").json()["rev"]
    r = tc.put(P + "/title", json={"base_rev": old, "text": "Mine"})
    assert r.status_code == 409 and r.json()["code"] == "stale_revision" and r.json()["current_rev"] == now and r.json()["rev"] == now
    assert tc.get(P + "/title").json()["title"]["text"] == TITLE
    assert tc.put(P + "/title", json={"text": "Mine"}).status_code == 422
    assert tc.put(P + "/title", json=[1]).status_code == 422
    assert tc.put("/api/projects/nope/title", json={"base_rev": "x", "text": "A"}).status_code == 404


def test_a_damaged_title_file_is_reported_and_replaced_by_the_next_put(tc):
    (tc.root / PID / "title.json").write_text("{ nope", encoding="utf-8")
    g = tc.get(P + "/title").json()
    assert g["state"] == "none" and g["problems"][0]["code"] == "document_corrupt" and g["rev"] == T.EMPTY_REV
    assert put(tc, text="A Fresh Start").status_code == 200 and tc.get(P + "/title").json()["problems"] == []


def test_every_code_the_title_routes_raise_has_a_hint_of_its_own():
    for code in ("title_invalid", "title_not_one_line", "title_too_long", "title_option_unknown", "title_choice_needed", "title_note_too_long", "title_note_invalid", "title_no_output",
                 "title_limit", "title_tampered"):
        assert code in hints.HINTS and hints.HINTS[code]["fix"], code
    assert hints.HINTS["title_no_output"]["retry"] == "later" and hints.HINTS["title_too_long"]["retry"] == "after_fix"


def test_a_generation_after_a_persons_title_replaces_it_when_asked_by_hand(tc):
    put(tc, text="My Own Title")
    generate(tc)
    g = tc.get(P + "/title").json()
    assert g["title"]["source"] == "agent" and [h["text"] for h in g["history"]] == ["My Own Title"]
