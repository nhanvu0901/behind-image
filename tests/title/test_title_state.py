"""The title in the state answer (`GET /api/projects/{pid}/state`): the actions `title.generate`, `title.set` and `title.cancel`, when each is listed and ready and what it advances,
the summary `title`, the draft that waits for it, the warning of a storyboard without one, and the place of the step in the automatic run (before the voice, never over a person's
title, the run stops when the agent fails). Real routes, the fake pipeline of tests/auto, a fake title agent."""
import json
import threading

import pytest
from run_helpers import actions_of, run_to_end, set_auto, state, wait_longjob
from title_helpers import FakeTitleAgent, broken, good_choice, install_agent

from bti import settings as S
from bti.editor import state_api
from bti.script import models as models_mod
from bti.script import store as sstore
from bti.title import store as T

ARN = "arn"
P = "/api/projects/%s" % ARN


def A(st, aid):
    return next((a for a in st["next_actions"] if a["id"] == aid), None)


def put_title(c, text="A Title Of My Own", **kw):
    rev = c.get(P + "/title").json()["rev"]
    r = c.put(P + "/title", json={"base_rev": rev, "text": text, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def generate(c, **body):
    r = c.post(P + "/title/generate", json=body)
    assert r.status_code == 200, r.text
    return wait_longjob(c, r.json()["job_id"])


def make_title_agent_unusable(tmp_path):
    """The title role points at a program that is not on this machine (the other roles keep the mock agent)."""
    (tmp_path / "agents.json").write_text(json.dumps({**{r: "mock" for r in S.ROLES}, "script.title": "agy:gemini-3.8-flash-high"}), encoding="utf-8")
    models_mod.reset_cache()


# ------------------------------------------------------------------------------------------------------------ before and after the narration is approved
def test_before_the_narration_is_approved_the_action_is_listed_and_waits(client, world):
    world.build("outline_waiting")
    st = state(client)
    g = A(st, "title.generate")
    assert g["ready"] is False and g["needs"] == ["narration_approved"] and g["advances"] is False and g["step"] == "script"
    s = A(st, "title.set")
    assert s["ready"] is True and s["method"] == "PUT" and s["path"] == P + "/title" and s["fill"] == ["text"] and s["gate"] is False
    assert s["body_template"] == {"base_rev": T.EMPTY_REV, "text": None, "actor": "cli:title"} and s["body"] is None
    assert st["title"] == {"state": "none", "text": None, "by": None, "at": None, "source": None, "candidates": 0, "stale": False}
    assert "title.cancel" not in [a["id"] for a in st["next_actions"]]


def test_after_the_narration_is_approved_the_action_is_ready_and_advances(client, world):
    world.build("narration_approved")
    st = state(client)
    g = A(st, "title.generate")
    assert g["ready"] is True and g["needs"] == [] and g["advances"] is True and g["gate"] is False and g["auto_ok"] is True
    assert g["label"] == "Viết tựa video" and g["method"] == "POST" and g["path"] == P + "/title/generate" and g["long_job"] is True and g["follow"] == "GET /api/longjobs/{job_id}"
    assert g["cost"] == {"kind": "model", "about": "about 1 minute"} and g["uses_model"] is True and g["agent"]["usable"] is True and g["agent"]["id"] == "gem"
    assert g["body"] == {"note": None, "actor": "agent:mock"}


def test_with_a_storyboard_the_action_is_ready_by_hand_but_does_not_advance_and_the_run_leaves_it(client, world, monkeypatch):
    world.build("drafted")                                              # a storyboard exists: a title written now would change it and so stop its approval standing
    g = A(state(client), "title.generate")
    assert g["ready"] is True and g["advances"] is False and g["needs"] == []
    agent = install_agent(monkeypatch, FakeTitleAgent())
    assert generate(client)["state"] == "done" and len(agent.calls) == 1                  # asked for by hand it works


def test_the_step_comes_before_the_voice_among_the_actions_that_advance(client, world):
    world.build("narration_approved")
    advancing = [a["id"] for a in state(client)["next_actions"] if a["ready"] and a["advances"]]
    assert advancing.index("title.generate") < advancing.index("voice.generate")


def test_the_action_does_not_advance_once_a_title_is_written_and_advances_again_when_it_is_stale(client, world, monkeypatch):
    world.build("narration_approved")
    install_agent(monkeypatch, FakeTitleAgent())
    assert generate(client)["state"] == "done"
    st = state(client)
    g = A(st, "title.generate")
    assert g["ready"] is True and g["advances"] is False                                   # it can be asked again by hand, but nothing waits for it
    assert st["title"]["state"] == "done" and st["title"]["text"] == "The Saint Who Was Also an Advertisement" and st["title"]["by"] == "agent:mock"
    assert st["title"]["source"] == "agent" and st["title"]["candidates"] == 6 and st["title"]["stale"] is False
    n = sstore.load_narration(client.root / ARN)
    n.chapters[0].beats[0].text += " A changed sentence."
    sstore.save_narration(client.root / ARN, n)
    assert client.post(P + "/narration/approve", json={"rev": client.get(P + "/narration").json()["rev"]}).status_code == 200
    st = state(client)
    assert st["title"]["state"] == "stale" and st["title"]["stale"] is True and st["title"]["text"]
    g = A(st, "title.generate")
    assert g["advances"] is True and g["ready"] is True


def test_a_title_a_person_set_is_never_stale_and_the_action_never_advances_over_it(client, world):
    world.build("narration_approved")
    put_title(client)
    n = sstore.load_narration(client.root / ARN)
    n.chapters[0].beats[0].text += " A changed sentence."
    sstore.save_narration(client.root / ARN, n)
    assert client.post(P + "/narration/approve", json={"rev": client.get(P + "/narration").json()["rev"]}).status_code == 200
    st = state(client)
    assert st["title"]["state"] == "done" and st["title"]["source"] == "person" and st["title"]["by"] == "human" and A(st, "title.generate")["advances"] is False


def test_the_action_needs_a_usable_agent(client, world, tmp_path):
    world.build("narration_approved")
    make_title_agent_unusable(tmp_path)
    g = A(state(client), "title.generate")
    assert g["ready"] is False and g["needs"] == ["agent_usable"] and g["advances"] is False and g["agent"]["usable"] is False


def test_a_running_title_job_is_listed_cancellable_and_holds_the_agent(client, world, monkeypatch):
    world.build("narration_approved")
    gate = threading.Event()
    install_agent(monkeypatch, FakeTitleAgent(hook=lambda ws, kw: (gate.wait(10), None)[1]))
    r = client.post(P + "/title/generate", json={})
    try:
        st = state(client)
        job = next(j for j in st["jobs"] if j["kind"] == "title")
        assert job["id"] == r.json()["job_id"] and job["path"] == "/api/longjobs/" + job["id"] and job["cancel"] == "/api/longjobs/%s/cancel" % job["id"]
        c = A(st, "title.cancel")
        assert c["path"] == "/api/longjobs/%s/cancel" % job["id"] and c["ready"] is True and c["label"] == "Dừng"
        g = A(st, "title.generate")
        assert g["ready"] is False and g["needs"] == ["no_running_job"]
    finally:
        gate.set()
    assert wait_longjob(client, r.json()["job_id"])["state"] == "done"
    assert "title.cancel" not in [a["id"] for a in state(client)["next_actions"]]


def test_a_title_job_holds_the_pictures_agent_and_the_draft_too(client, world, monkeypatch):
    world.build("picks_approved")
    gate = threading.Event()
    install_agent(monkeypatch, FakeTitleAgent(hook=lambda ws, kw: (gate.wait(10), None)[1]))
    r = client.post(P + "/title/generate", json={})
    try:
        st = state(client)
        for aid in ("picks.auto", "draft.start", "picks.edit"):
            assert "no_running_job" in A(st, aid)["needs"], aid
    finally:
        gate.set()
    wait_longjob(client, r.json()["job_id"])


# ------------------------------------------------------------------------------------------------------------ the draft waits
def test_the_draft_waits_for_the_title_while_an_agent_can_write_it(client, world):
    world.build("picks_approved")
    d = A(state(client), "draft.start")
    assert d["ready"] is False and "title_done" in d["needs"] and d["advances"] is False
    assert "title_done" in state_api.NEEDS
    put_title(client)                                                                           # a person's title ends the wait
    d = A(state(client), "draft.start")
    assert "title_done" not in d["needs"] and d["ready"] is True and d["advances"] is True


def test_the_draft_waits_again_when_the_title_is_stale(client, world, monkeypatch):
    world.build("picks_approved")
    install_agent(monkeypatch, FakeTitleAgent())
    generate(client)
    assert "title_done" not in A(state(client), "draft.start")["needs"]
    # an agent's title written from another narration than this one (the voice and the pictures follow the narration, so the narration itself stays as it is here)
    T.write_generated(client.root / ARN, good_choice()["candidates"], by="agent:mock", narration_rev_="0" * 40, written={})
    st = state(client)
    assert st["title"]["state"] == "stale" and "title_done" in A(st, "draft.start")["needs"] and A(st, "draft.start")["advances"] is False


def test_the_draft_does_not_wait_when_no_agent_can_write_the_title(client, world, tmp_path):
    world.build("picks_approved")
    make_title_agent_unusable(tmp_path)
    d = A(state(client), "draft.start")
    assert "title_done" not in d["needs"] and d["ready"] is True and d["advances"] is True


def test_a_storyboard_without_a_title_has_one_warning_and_a_title_takes_it_away(client, world):
    world.build("drafted")
    st = state(client)
    w = [x for x in st.get("warnings", []) if x["code"] == "title_missing"]
    assert len(w) == 1 and "tựa video" in w[0]["sentence"] and "title.generate" in w[0]["detail"]
    put_title(client)
    assert not [x for x in state(client).get("warnings", []) if x["code"] == "title_missing"]


def test_a_title_the_storyboard_already_carries_ends_the_wait_and_the_warning(client, world):
    world.build("drafted")
    f = client.root / ARN / "storyboard.json"
    sb = json.loads(f.read_text(encoding="utf-8"))
    sb["identity"] = {"style": "raking", "video_title": "  A Title Set Through The Identity Route "}
    f.write_text(json.dumps(sb), encoding="utf-8")
    st = state(client)
    assert st["title"]["state"] == "none"                                                       # the document is what `title` says
    assert not [w for w in st.get("warnings", []) if w["code"] == "title_missing"] and "title_done" not in A(st, "draft.start")["needs"]
    sb["identity"]["video_title"] = "   "
    f.write_text(json.dumps(sb), encoding="utf-8")
    st = state(client)
    assert [w for w in st.get("warnings", []) if w["code"] == "title_missing"] and "title_done" in A(st, "draft.start")["needs"]


def test_a_project_before_its_storyboard_has_no_warning(client, world):
    world.build("narration_approved")
    assert "warnings" not in state(client)


def test_a_damaged_title_file_is_a_problem_of_the_step_and_not_a_blocker(client, world):
    world.build("narration_approved")
    (client.root / ARN / "title.json").write_text("{ nope", encoding="utf-8")
    st = state(client)
    p = next(x for x in st["problems"] if x["step"] == "script" and "title.json" in x["detail"])
    assert p["code"] == "document_corrupt" and "title.set" in p["fix"]
    g = A(st, "title.generate")
    assert g["ready"] is True and g["advances"] is True and st["title"]["state"] == "none"


# ------------------------------------------------------------------------------------------------------------ the automatic run
def test_the_run_takes_the_title_by_itself_before_the_voice(client, world, monkeypatch):
    world.build("narration_approved")
    agent = install_agent(monkeypatch, FakeTitleAgent())
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="voice")
    assert actions_of(run) == ["title.generate", "voice.generate"] and run["reason"] == "until_reached" and all(s["ok"] is True for s in run["steps"]), run["result"]
    first = run["steps"][0]
    assert first["body"]["actor"] == "agent:auto" and first["job_state"] == "done" and first["step"] == "script"
    assert len(agent.calls) == 1
    doc, _ = T.read(client.root / ARN)
    assert doc["chosen"]["by"] == "agent:mock" and doc["chosen"]["source"] == "agent" and doc["written"]["requested_by"] == "agent:auto"
    assert world.calls == ["voice"]                                                              # the voice started after the title, once


def test_the_run_never_takes_the_title_over_a_persons_title(client, world, monkeypatch):
    world.build("narration_approved")
    agent = install_agent(monkeypatch, FakeTitleAgent())
    put_title(client)
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="voice")
    assert actions_of(run) == ["voice.generate"] and agent.calls == [] and T.chosen_text(client.root / ARN) == "A Title Of My Own"


def test_the_run_goes_on_without_a_title_when_no_agent_can_write_one(client, world, tmp_path):
    world.build("narration_approved")
    make_title_agent_unusable(tmp_path)
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="voice")
    assert actions_of(run) == ["voice.generate"] and run["reason"] == "until_reached"
    assert not (client.root / ARN / "title.json").exists()


def test_the_run_stops_with_the_jobs_code_when_the_agent_fails(client, world, monkeypatch):
    world.build("narration_approved")
    install_agent(monkeypatch, FakeTitleAgent(answer=broken(lambda d: d["candidates"][1].update(text="The Saint: A Ring Story"))))
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="voice")
    assert actions_of(run) == ["title.generate"] and run["reason"] == "job_failed" and run["outcome"] == "failed", run["result"]
    assert run["result"]["error"]["code"] == "title_no_output" and world.calls == [] and not (client.root / ARN / "title.json").exists()


def test_every_need_and_job_kind_the_run_can_meet_has_its_words():
    from bti.auto_run import reasons
    assert "title_done" in reasons.NEED_VI and "title" in reasons.JOB_KIND_VI
    assert set(state_api.NEEDS) <= set(reasons.NEED_VI)
