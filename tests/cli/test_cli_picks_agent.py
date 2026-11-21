"""`bti status` and `bti do` on the actions of the pictures agent and of the prompt box of step 4 (worker join2): `picks.auto` (the agent that chooses
the pictures) and `picks.edit` (the box on typed operations) are costly actions (a model call) like `draft.start` and `draft.edit`: the command follows the
state answer, so the marks (`costs model`, `needs --yes-cost`, `long job`), the rule of the owner (`spend.model` of auto.json) and the one-job-at-a-time
refusal reach it without a line of the command's own. The agent in a work folder is the fake runner of tests/picks, the model of the box is the mock provider,
the picture sources are fakes: no model, no program and no network."""
import json
import sys
import tempfile
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for p in (HERE.parents[1] / "tests" / "picks", HERE.parents[1] / "tests" / "draft"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from auto_fixtures import paid  # noqa: E402,F401
from auto_helpers import FakeAgent, fake_book_thumb, fake_thumb, install_agent, install_sources, make_auto_project  # noqa: E402
from box_helpers import ans  # noqa: E402

from bti.picks import doc, service  # noqa: E402
from bti.picks.auto import search as asearch  # noqa: E402
from bti.script.providers import mock  # noqa: E402

REAL_SEARCH = service.search               # the conftest of tests/cli stands in for the picture search; the agent's search part needs the real one over the fake sources

PID = "pk1"
P = "/api/projects/%s" % PID


@pytest.fixture()
def agent(client, tmp_path, monkeypatch, paid):
    """A project with an approved narration and a main painting, the fake agent and the fake sources; -> the fake agent."""
    make_auto_project(client.root, PID)
    (tmp_path / "work").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "work"))
    install_sources(monkeypatch)
    monkeypatch.setattr(service, "search", REAL_SEARCH)
    monkeypatch.setattr(asearch, "default_fetch_thumb", fake_thumb)
    monkeypatch.setattr(asearch, "default_book_thumb", fake_book_thumb)
    mock.clear_canned()
    del mock.CALLS[:]
    yield install_agent(monkeypatch, FakeAgent())
    mock.clear_canned()
    assert paid == [], "the paid suggestion service was reached: %s" % paid


def set_auto(client, **change):
    rev = client.get(P + "/auto").json()["rev"]
    r = client.put(P + "/auto", json={"base_rev": rev, **change})
    assert r.status_code == 200, r.text


def row(out, action_id):
    return next(l for l in out.splitlines() if l.strip().startswith(action_id + " "))


def wait_idle(client, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if not client.get(P + "/state").json()["jobs"]:
            return
        time.sleep(0.05)
    raise AssertionError("a job did not end")


# ------------------------------------------------------------------------------------------------------------------------ status
def test_status_lists_the_agent_and_the_box_as_costly_long_jobs_in_the_order_of_the_page(bti, agent):
    r = bti("status", PID)
    assert r.code == 0, r
    assert "[advances; costs model (about 20 minutes); needs --yes-cost; long job: add --wait]" in row(r.out, "picks.auto")
    edit = row(r.out, "picks.edit")
    assert "costs model (about 30 seconds); needs --yes-cost; long job: add --wait" in edit and "advances" not in edit
    assert "Để agent chọn hình" in row(r.out, "picks.auto") and "Nhờ agent sửa chọn hình" in edit
    ids = [a["id"] for a in bti("status", PID, "--json").json["next_actions"] if a["id"].startswith("picks.")]
    assert ids[0] == "picks.auto" and [i for i in ids if i not in ("picks.suggest", "picks.approve")] == [
        "picks.auto", "picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put", "picks.edit", "picks.ops"]
    acts = {a["id"]: a for a in bti("status", PID, "--json").json["next_actions"]}
    assert acts["picks.auto"]["uses_model"] is True and acts["picks.edit"]["uses_model"] is True and acts["picks.ops"]["uses_model"] is False


def test_status_says_when_the_owner_did_not_allow_a_model_call_for_them(bti, agent, client):
    set_auto(client, spend={"model": False})
    out = bti("status", PID).out
    assert all(a["auto_ok"] is False for a in bti("status", PID, "--json").json["next_actions"] if a["id"] in ("picks.auto", "picks.edit"))
    assert "picks.auto" in out and "picks.edit" in out


# ------------------------------------------------------------------------------------------------------------------------ do
def test_the_agent_runs_only_with_yes_cost_and_walks_a_job_to_its_end(bti, agent, client):
    r = bti("do", PID, "picks.auto")
    assert r.code == 3 and r.out == "" and r.err.splitlines()[0] == "a person is needed: cost_not_confirmed"
    assert "picks.auto costs model (about 20 minutes)." in r.err and "--yes-cost" in r.err and agent.calls == []
    j = bti("do", PID, "picks.auto", "--json").json
    assert j["exit"] == 3 and j["code"] == "cost_not_confirmed" and j["cost"] == {"kind": "model", "about": "about 20 minutes"}
    ok = bti("do", PID, "picks.auto", "--yes-cost", "--wait")
    assert ok.code == 0, ok
    assert ok.out.startswith("started job ") and "(picks.auto)" in ok.out.splitlines()[0] and ok.out.splitlines()[-1].startswith("done: ")
    assert "running 100%" in ok.out or "done 100%" in ok.out
    d = doc.load_or_new(client.root / PID)
    assert len(d["beats"]) == 6 and [c["mode"] for c in agent.calls] == ["plan", "choose"]
    job = client.get("/api/longjobs/" + ok.out.split("started job ")[1].split(" ")[0]).json()
    assert job["state"] == "done" and job["result"]["sentence"] == "Agent đã chọn hình cho 6/6 đoạn."
    log = client.get(P + "/changes").json()["changes"]
    assert log and all(c["actor"] == "agent:mock" for c in log)                                     # who made each batch is in the change log


def test_the_agent_can_be_told_which_lines(bti, agent, client):
    ok = bti("do", PID, "picks.auto", "--yes-cost", "--wait", "--json", "--set", 'beats=["b0003"]')
    assert ok.code == 0, ok
    assert ok.json["state"] == "done" and ok.json["result"]["sentence"] == "Agent đã chọn hình cho 1/1 đoạn."
    assert list(doc.load_or_new(client.root / PID)["beats"]) == ["b0003"]


def test_yes_cost_cannot_override_the_owner_who_forbade_model_spending(bti, agent, client):
    set_auto(client, spend={"model": False})
    for action_id, extra in (("picks.auto", []), ("picks.edit", ["--set", "instruction=thêm bản đồ", "--set", 'scope={"beats":["b0003"]}'])):
        r = bti("do", PID, action_id, "--yes-cost", *extra)
        assert r.code == 3 and r.err.splitlines()[0] == "a person is needed: spend_not_allowed", (action_id, r)
        assert "did not allow an agent to spend" in r.err
    assert agent.calls == [] and mock.CALLS == [] and not any(c[0] == "POST" for c in bti.transport.log)       # nothing was sent, no model was asked
    set_auto(client, spend={"model": True})
    assert bti("do", PID, "picks.auto", "--yes-cost", "--wait").code == 0


def test_the_box_through_the_command_then_the_agent_for_what_the_box_cannot_do(bti, agent, client):
    reason = "Dự án chưa có hình bản đồ Bruges, cần tìm thêm hình."
    mock.set_canned([ans(status="escalate", reason=reason, summary="")])
    no = bti("do", PID, "picks.edit", "--set", "instruction=thêm bản đồ Bruges", "--set", 'scope={"beats":["b0004"]}')
    assert no.code == 3 and "cost_not_confirmed" in no.err and mock.CALLS == []
    r = bti("do", PID, "picks.edit", "--yes-cost", "--wait", "--set", "instruction=thêm bản đồ Bruges", "--set", 'scope={"beats":["b0004"]}')
    assert r.code == 0, r
    assert '"status":"escalate"' in r.out.replace(" ", "") and reason in r.out
    assert doc.load_or_new(client.root / PID)["beats"] == {} and agent.calls == []                       # the box wrote nothing, and the agent did not start by itself
    # what the box could not do is what picks.auto does, for those lines
    go = bti("do", PID, "picks.auto", "--yes-cost", "--wait", "--json", "--set", 'beats=["b0004"]')
    assert go.code == 0, go
    assert go.json["result"]["sentence"] == "Agent đã chọn hình cho 1/1 đoạn." and list(doc.load_or_new(client.root / PID)["beats"]) == ["b0004"]


def test_one_agent_job_at_a_time_is_exit_5_for_both_and_the_status_says_to_wait(bti, agent, client):
    from bti.draft.providers.agy import AgyResult

    def hold(mode, ws, kw):
        while not kw["cancel"]():
            time.sleep(0.02)
        return AgyResult(status="cancelled")
    agent.hook = hold
    start = bti("do", PID, "picks.auto", "--yes-cost")
    assert start.code == 0 and "started job " in start.out
    jid = start.out.split("started job ")[1].split(";")[0]
    mock.set_canned([ans(status="cannot", reason="Không đổi được.", summary="")])
    blocked = bti("do", PID, "picks.edit", "--yes-cost", "--set", "instruction=đổi hình", "--set", 'scope={"beats":["b0001"]}')
    assert blocked.code == 5 and blocked.err.splitlines()[0] == "busy: not_ready" and "no_running_job" in blocked.err, blocked
    again = bti("do", PID, "picks.auto", "--yes-cost")
    assert again.code == 5 and "no_running_job" in again.err
    assert mock.CALLS == []                                                                           # the box never reached the model
    st = bti("status", PID)
    assert st.out.splitlines()[-1].startswith("next: bti job %s --wait" % jid) and "no_running_job" in row(st.out, "picks.edit")
    # the server itself refuses too (a caller that does not read the state), with the sentence the owner reads on the page
    raw = client.post(P + "/picks/edit", json={"instruction": "đổi hình", "scope": {"beats": ["b0001"]}})
    assert raw.status_code == 409 and raw.json()["code"] == "agent_job_running" and raw.json()["retry"] == "later" and raw.json()["job_id"] == jid
    assert bti("job", jid, "--cancel").code == 0
    wait_idle(client)
    assert bti("do", PID, "picks.edit", "--yes-cost", "--wait", "--set", "instruction=đổi hình", "--set", 'scope={"beats":["b0001"]}').code == 0


def test_a_storyboard_box_and_a_draft_cost_the_same_way(bti, client, monkeypatch):
    """The step 5 actions meet the rule as they did: marks, `--yes-cost`, the owner's refusal (the project is the sample one of tests/state)."""
    from state_helpers import make_book_project, build
    make_book_project(client.root)
    build("drafted", client, monkeypatch)
    out = bti("status", "arn")
    assert "costs model (from about 30 seconds to about 20 minutes); needs --yes-cost; long job" in row(out.out, "draft.edit")
    no = bti("do", "arn", "draft.edit", "--set", "instruction=cho dài hơn", "--set", 'scope={"all":true}')
    assert no.code == 3 and "cost_not_confirmed" in no.err
    rev = client.get("/api/projects/arn/auto").json()["rev"]
    assert client.put("/api/projects/arn/auto", json={"base_rev": rev, "spend": {"model": False}}).status_code == 200
    r = bti("do", "arn", "draft.edit", "--yes-cost", "--set", "instruction=cho dài hơn", "--set", 'scope={"all":true}')
    assert r.code == 3 and r.err.splitlines()[0] == "a person is needed: spend_not_allowed"
