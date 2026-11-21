"""fixes4, point 2: the automatic run takes `picks.retry_missing` ONCE, between the pictures agent and the pictures gate. Real routes, the fake agent runner of tests/picks, the fake
sources: no model, no program, no network."""
import pytest

from run_helpers import P, actions_of, run_to_end, set_auto, state
from test_run_joined import act_of, agent  # noqa: F401
from picks_agent import FakeAgent  # noqa: F401

from bti.picks import service
from bti.picks.auto import retry
from bti.picks.errors import PicksError

REAL_FETCH = service.fetch_asset


def refusing_until_the_retry(monkeypatch, *, forever=False):
    """Commons refuses every download of the agent's write part; once the retry job runs (it calls `retry.run`) the source gives its pictures, unless `forever`."""
    state_ = {"retry_started": 0}
    real_run = retry.run

    def run(*a, **k):
        state_["retry_started"] += 1
        return real_run(*a, **k)

    def fetch(pdir, source, source_id):
        if source == "commons" and (forever or not state_["retry_started"]):
            raise PicksError(503, "limits", "source_rate_limited", retryable=True, retry_after=30)
        return REAL_FETCH(pdir, source, source_id)
    monkeypatch.setattr(retry, "run", run)
    monkeypatch.setattr(service, "fetch_asset", fetch)
    return state_


def test_the_run_retries_the_refused_downloads_once_before_it_approves_the_picks(client, agent, monkeypatch):
    refusing_until_the_retry(monkeypatch)
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="picks")
    assert actions_of(run) == ["picks.auto", "picks.retry_missing", "picks.approve"] and all(s["ok"] is True for s in run["steps"]), run["result"]
    assert run["reason"] == "until_reached"
    step = run["steps"][1]
    assert step["body"]["actor"] == "agent:auto" and step["job_state"] == "done"                              # the run named itself; its own job is not a reason to refuse
    picks = client.get(P + "/picks").json()
    assert picks["approved"] is True and all("missing" not in b for b in picks["picks"]["beats"].values())
    log = client.get(P + "/changes").json()["changes"]
    assert {c["actor"] for c in log if "Tải lại" in (c.get("note") or "")} == {"agent:auto"}


def test_a_line_that_stays_refused_is_tried_by_the_run_once_and_not_again(client, agent, monkeypatch):
    seen = refusing_until_the_retry(monkeypatch, forever=True)
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="picks")
    assert actions_of(run).count("picks.retry_missing") == 1 and seen["retry_started"] == 1                   # one try, then the run goes on to the gate
    assert actions_of(run)[:2] == ["picks.auto", "picks.retry_missing"]
    res = run["result"]
    assert res["reason"] == "quality_warning" and res["gate"] == "picks"                                       # the lines without their picture are judged by the gate's own rule (the share of the outside lines)
    assert client.get(P + "/picks").json()["approved"] is False


def test_when_nothing_was_refused_the_run_never_lists_the_action(client, agent):
    set_auto(client, enabled=True)
    job, run = run_to_end(client, until="picks")
    assert actions_of(run) == ["picks.auto", "picks.approve"]


def test_a_retry_the_owner_did_not_allow_to_spend_is_not_a_cost(client, agent, monkeypatch):
    refusing_until_the_retry(monkeypatch)
    set_auto(client, enabled=True, spend={"model": True, "machine_time": False})
    job, run = run_to_end(client, until="picks")
    assert "picks.retry_missing" in actions_of(run) and run["reason"] == "until_reached"                       # it has no cost: no spend is needed
