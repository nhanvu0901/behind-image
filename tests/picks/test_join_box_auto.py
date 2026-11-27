"""The prompt box of step 4 and the pictures agent on one page and one API (worker join2). The model of the box is the mock provider, the agent in a work
folder is the fake runner of `auto_helpers`, the picture sources are fakes. Nothing here calls a model, a program or a network.

A step-4 request that needs a picture the project does not have ends as `escalate`; the owner hands the same lines to the pictures agent
(`POST .../picks/edit/{turn}/escalate`, through `bti.picks.auto.escalate`), the turn follows that job to its result, and the two kinds of work
(a box turn, the agent's run, also a draft) run one at a time per project, the refusal saying so."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

DRAFT_TESTS = Path(__file__).resolve().parents[1] / "draft"
if str(DRAFT_TESTS) not in sys.path:
    sys.path.insert(0, str(DRAFT_TESTS))

from auto_fixtures import paid  # noqa: E402,F401
from box_helpers import HeldModel, ans  # noqa: E402
from test_auto_api import action, api, err, hold_until_cancelled, wait  # noqa: E402,F401

from bti.picks import doc  # noqa: E402
from bti.script.providers import mock  # noqa: E402

REASON = "Dự án chưa có hình chân dung họa sĩ, cần tìm thêm hình."
ASK = "thêm hình chân dung họa sĩ cho dòng này"


@pytest.fixture(autouse=True)
def _mock_model():
    mock.clear_canned()
    del mock.CALLS[:]
    yield
    mock.clear_canned()


def post_box(api, instruction=ASK, beats=("b0003",)):
    return api.post("/api/projects/%s/picks/edit" % api.pid, json={"instruction": instruction, "scope": {"beats": list(beats)}})


def thread(api):
    r = api.get("/api/projects/%s/picks/edit/thread" % api.pid)
    assert r.status_code == 200, r.text
    return r.json()


def escalated_turn(api, beats=("b0003",)):
    """A turn the box answered `escalate` (nothing written), as the page shows it."""
    mock.set_canned([ans(status="escalate", reason=REASON, summary="")])
    r = post_box(api, beats=beats)
    assert r.status_code == 200, r.text
    assert wait(api, r.json()["job_id"])["state"] == "done"
    turn = next(t for t in thread(api)["turns"] if t["id"] == r.json()["turn_id"])
    assert turn["status"] == "escalate" and turn["reason"] == REASON
    return turn


def escalate(api, turn, **body):
    return api.post("/api/projects/%s/picks/edit/%s/escalate" % (api.pid, turn["id"]), json=body)


# ---------------------------------------------------------------------------------------------------------------- the hand-over
def test_an_escalated_request_is_handed_to_the_pictures_agent_and_the_card_follows_it_to_its_result(api):
    turn = escalated_turn(api)
    assert not doc.load_or_new(api.pdir)["beats"] and not api.get("/api/projects/%s/changes" % api.pid).json()["changes"]      # the box wrote nothing
    r = escalate(api, turn)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["turn_id"] == turn["id"] and body["lines"] == 1 and body["agent"]["id"] == "gem" and len(body["job_id"]) == 16
    running = next(t for t in thread(api)["turns"] if t["id"] == turn["id"])                       # at once: the turn is a running one on that job
    assert running["status"] in ("running", "applied") and running["path"] == "agent" and running["escalated"] is True and running["job_id"] == body["job_id"]
    job = wait(api, body["job_id"])
    assert job["state"] == "done", job.get("error")
    assert job["kind"] == "picks" and job["meta"]["action"] == "auto" and job["meta"]["beats"] == ["b0003"] and job["meta"]["redo"] is True
    t = next(x for x in thread(api)["turns"] if x["id"] == turn["id"])
    assert t["status"] == "applied" and t["path"] == "agent" and t["doc"] == "picks"
    assert t["summary"] == "Agent đã chọn hình cho 1/1 đoạn." == job["result"]["sentence"]
    assert t["result"]["lines_done"] == 1 and t["result"]["lines_total"] == 1 and t["result"]["lines_without"] == []
    assert t["batch_changes"] and any(c["what"].startswith("Đoạn 3") for c in t["batch_changes"])              # the sentences of the batches the agent wrote
    assert t["seconds"] >= 0 and t["error"] is None and t["batch"] is None and t["has_undo"] is False
    picks = doc.load_or_new(api.pdir)
    assert [i["asset"] for i in picks["beats"]["b0003"]["items"]] and set(picks["beats"]) == {"b0003"}               # exactly the lines of the turn
    log = api.get("/api/projects/%s/changes" % api.pid).json()["changes"]
    assert log and all(c["actor"].startswith("agent:") for c in log) and set(job["result"]["batches"]) <= {c["batch"] for c in log}


def test_the_owners_words_reach_the_agent_and_the_lines_are_those_of_the_turn(api):
    turn = escalated_turn(api, beats=("b0003", "b0004"))
    seen = []
    api.agent.hook = lambda mode, ws, kw: seen.append((mode, (ws / "TASK.md").read_text(encoding="utf-8")))       # what the agent is told, in both of its sessions
    job = wait(api, escalate(api, turn).json()["job_id"])
    assert job["state"] == "done" and sorted(job["meta"]["beats"]) == ["b0003", "b0004"]
    assert [m for m, _ in seen] == ["plan", "choose"] and all(ASK in text for _, text in seen)
    from bti.picks.auto import store
    state = store.read(api.pdir, "plan.json")
    assert state and sorted(ln["beat"] for ln in state["plan"]["lines"]) == ["b0003", "b0004"]


def test_a_chapter_or_the_whole_video_scope_becomes_its_lines(api):
    mock.set_canned([ans(status="escalate", reason=REASON, summary="")])
    r = api.post("/api/projects/%s/picks/edit" % api.pid, json={"instruction": ASK, "scope": {"all": True}})
    assert wait(api, r.json()["job_id"])["state"] == "done"
    turn = next(t for t in thread(api)["turns"] if t["id"] == r.json()["turn_id"])
    body = escalate(api, turn).json()
    assert body["lines"] == 6
    assert wait(api, body["job_id"])["state"] == "done"


def test_only_a_turn_that_ended_as_escalate_can_be_handed_over(api):
    mock.set_canned([ans([{"op": "skip_beat", "beat": "b0003", "reason": "Không cần hình mới."}], summary="Dòng này giữ hình trước.")])
    r = post_box(api, "dòng này giữ hình trước")
    assert wait(api, r.json()["job_id"])["state"] == "done"
    applied = next(t for t in thread(api)["turns"] if t["id"] == r.json()["turn_id"])
    assert applied["status"] == "applied"
    b = err(escalate(api, applied), 409, "turn_not_escalated")
    assert "escalate" in b["detail"]
    err(api.post("/api/projects/%s/picks/edit/nope/escalate" % api.pid, json={}), 404, "turn_not_found")
    done = escalated_turn(api)
    assert wait(api, escalate(api, done).json()["job_id"])["state"] == "done"
    err(escalate(api, done), 409, "turn_not_escalated")                                           # handed over once: the result is on the card, nothing to hand over again
    err(api.post("/api/projects/%s/picks/edit/%s/escalate" % (api.pid, done["id"]), json=[1]), 422, "invalid_request")


def test_the_refusals_of_the_agent_come_back_with_their_own_codes(api):
    turn = escalated_turn(api)
    with doc.Held(api.pdir):
        d = doc.load_or_new(api.pdir)
        d["main_asset"] = None
        doc.save(api.pdir, d)
    err(escalate(api, turn), 409, "picks_no_main")
    err(api.post("/api/projects/%s/picks/edit/%s/escalate" % (api.pid, turn["id"]), json={"model": 3}), 422, "bad_model")


def test_a_failed_agent_run_ends_the_turn_with_its_code_and_it_can_be_handed_over_again(api):
    from bti.draft.providers.agy import AgyResult
    api.agent.hook = lambda mode, ws, kw: AgyResult(status="error", error_code="agy_error", elapsed=1.0)
    turn = escalated_turn(api)
    first = escalate(api, turn).json()
    job = wait(api, first["job_id"])
    assert job["state"] == "error"
    t = next(x for x in thread(api)["turns"] if x["id"] == turn["id"])
    assert t["status"] == "failed" and t["path"] == "agent" and t["error"] == job["error_code"] and t["has_undo"] is False
    assert not doc.load_or_new(api.pdir)["beats"]
    api.agent.hook = None                                                                          # the agent can run now: the same turn goes again
    again = escalate(api, t)
    assert again.status_code == 200, again.text
    assert wait(api, again.json()["job_id"])["state"] == "done"
    t2 = next(x for x in thread(api)["turns"] if x["id"] == turn["id"])
    assert t2["status"] == "applied" and t2["error"] is None and t2["summary"] == "Agent đã chọn hình cho 1/1 đoạn."


def test_a_stopped_agent_run_can_be_handed_over_again(api):
    api.agent.hook = hold_until_cancelled
    turn = escalated_turn(api)
    jid = escalate(api, turn).json()["job_id"]
    t = next(x for x in thread(api)["turns"] if x["id"] == turn["id"])
    assert t["status"] == "running" and thread(api)["active_job_id"] == jid                          # the card finds the job after a reload of the page
    assert api.post("/api/longjobs/%s/cancel" % jid, json={}).status_code == 200
    assert wait(api, jid)["state"] == "cancelled"
    t = next(x for x in thread(api)["turns"] if x["id"] == turn["id"])
    assert t["status"] == "cancelled" and t["path"] == "agent"
    api.agent.hook = None
    assert wait(api, escalate(api, t).json()["job_id"])["state"] == "done"


# ---------------------------------------------------------------------------------------------------------------- one agent run at a time
def test_a_box_turn_is_refused_while_the_pictures_agent_runs(api):
    api.agent.hook = hold_until_cancelled
    jid = api.post(api.u(), json={}).json()["job_id"]
    mock.set_canned([ans(status="cannot", reason="Không đổi được.", summary="")])
    b = err(post_box(api), 409, "agent_job_running")
    assert b["job_id"] == jid
    assert not mock.CALLS and thread(api)["turns"] == []                                            # nothing was asked of the model, no turn was recorded
    st = api.get("/api/projects/%s/state" % api.pid).json()
    edit = action(st, "picks.edit")
    assert edit["ready"] is False and edit["needs"] == ["no_running_job"]
    assert action(st, "picks.auto")["needs"] == ["no_running_job"]
    api.post("/api/longjobs/%s/cancel" % jid, json={})
    assert wait(api, jid)["state"] == "cancelled"
    after = api.get("/api/projects/%s/state" % api.pid).json()
    assert action(after, "picks.edit")["ready"] is True and action(after, "picks.auto")["ready"] is True


def test_the_pictures_agent_is_refused_while_a_box_turn_runs(api, monkeypatch):
    held = HeldModel(monkeypatch)
    mock.set_canned([ans(status="cannot", reason="Không đổi được.", summary="")])
    first = post_box(api)
    assert first.status_code == 200 and held.entered.wait(30)
    b = err(api.post(api.u(), json={}), 409, "agent_job_running")
    assert b["job_id"] == first.json()["job_id"]
    st = api.get("/api/projects/%s/state" % api.pid).json()
    assert action(st, "picks.auto")["ready"] is False and action(st, "picks.auto")["needs"] == ["no_running_job"]
    assert action(st, "picks.edit")["needs"] == ["no_running_job"]                                   # one box turn at a time, too (the same kind)
    held.release.set()
    assert wait(api, first.json()["job_id"])["state"] == "done"
    again = api.post(api.u(), json={})
    assert again.status_code == 200 and wait(api, again.json()["job_id"])["state"] == "done"                  # the job of the manager is global: end it before the next test


def test_handing_a_turn_over_is_refused_while_another_agent_job_runs(api, monkeypatch):
    turn = escalated_turn(api)
    held = HeldModel(monkeypatch)
    mock.set_canned([ans(status="cannot", reason="Không đổi được.", summary="")])
    other = post_box(api, "một yêu cầu khác", beats=("b0001",))
    assert other.status_code == 200 and held.entered.wait(30)
    err(escalate(api, turn), 409, "agent_job_running")
    held.release.set()
    assert wait(api, other.json()["job_id"])["state"] == "done"
    assert wait(api, escalate(api, turn).json()["job_id"])["state"] == "done"


def test_a_draft_or_a_storyboard_box_turn_does_not_start_while_the_pictures_agent_runs(api, monkeypatch):
    api.agent.hook = hold_until_cancelled
    jid = api.post(api.u(), json={}).json()["job_id"]
    from bti.draft import run as draft_run
    from bti.draft.inputs import DraftError
    with pytest.raises(DraftError) as e:
        draft_run.refuse_while_agent_busy(api.pid)
    assert e.value.code == "agent_job_running" and e.value.extra["job_id"] == jid
    r = api.post("/api/projects/%s/draft/edit" % api.pid, json={"instruction": "x", "scope": {"all": True}})
    assert r.status_code == 409 and r.json()["code"] == "agent_job_running" and r.json()["job_id"] == jid
    r = api.post("/api/projects/%s/draft/start" % api.pid, json={})
    assert r.status_code == 409 and r.json()["code"] in ("agent_job_running", "draft_not_ready")
    api.post("/api/longjobs/%s/cancel" % jid, json={})
    wait(api, jid)


def test_the_refusal_is_one_vietnamese_sentence_everywhere():
    from bti.draft import run as draft_run
    from bti.editor import hints
    from bti.picks.auto import texts
    sentence = draft_run.VI["agent_job_running"]
    assert texts.VI["agent_job_running"] == sentence and "Dừng" in sentence and "chọn hình" in sentence
    assert "agent_job_running" in hints.HINTS and hints.HINTS["agent_job_running"]["retry"] == "later"
    assert "turn_not_escalated" in hints.HINTS
    page = (hints.REPO_ROOT / "bti" / "editor" / "static" / "js" / "errmsg.js").read_text(encoding="utf-8")
    assert sentence in page


# ---------------------------------------------------------------------------------------------------------------- the state answer
def test_the_state_lists_both_in_the_order_of_the_page_with_consistent_marks(api):
    from bti.editor import state_api
    page = ["picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.suggest", "picks.put", "picks.auto", "picks.retry_missing", "picks.tighten", "picks.edit", "picks.ops",
            "picks.approve", "picks.cancel"]
    # planner: visual-script planning is an additional picks action.
    page.insert(7, "visual.plan")
    assert [s.id for s in state_api.SPECS if s.step == "picks"] == page                                  # the catalogue: search and import, the agent, its retry of the downloads (fixes4), the box, the operations, approve
    st = api.get("/api/projects/%s/state" % api.pid).json()
    ids = [a["id"] for a in st["next_actions"] if a["id"].startswith("picks.")]
    assert ids[0] == "picks.auto"                                                                        # no line has pictures yet: the agent advances the project, so it comes first
    ready = [i for i in ids if i != "picks.suggest" and i != "picks.approve"]
    assert ready == ["picks.auto", "picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put", "picks.edit", "picks.ops"]
    auto, edit = action(st, "picks.auto"), action(st, "picks.edit")
    for a in (auto, edit):
        assert a["long_job"] is True and a["uses_model"] is True and a["cost"]["kind"] == "model" and a["gate"] is False
        assert a["follow"] == "GET /api/longjobs/{job_id}" and a["agent"]["id"] == "gem" and a["step"] == "picks"
    assert auto["cost"]["about"] == "about 20 minutes" and edit["cost"]["about"] == "about 30 seconds"
    assert auto["auto_ok"] is True and edit["auto_ok"] is True                                       # model spending is allowed by the defaults of auto.json
    assert auto["body"]["beats"] is None and edit["fill"] == ["instruction", "scope"]
    assert edit["body_template"] == {"instruction": None, "scope": None, "base_rev": auto["body"]["base_rev"]}
    # the bodies the state gives are accepted as they stand
    r = api.post(auto["path"], json=auto["body"])
    assert r.status_code == 200 and wait(api, r.json()["job_id"])["state"] == "done"
    mock.set_canned([ans(status="cannot", reason="Không đổi được.", summary="")])
    after = api.get("/api/projects/%s/state" % api.pid).json()                                          # the revision moved with the agent's batches
    template = action(after, "picks.edit")["body_template"]
    assert template["base_rev"] != edit["body_template"]["base_rev"]
    r = api.post(edit["path"], json={**template, "instruction": ASK, "scope": {"beats": ["b0003"]}})
    assert r.status_code == 200 and wait(api, r.json()["job_id"])["state"] == "done"
    after = api.get("/api/projects/%s/state" % api.pid).json()
    done = [a["id"] for a in after["next_actions"] if a["id"].startswith("picks.") and a["id"] not in ("picks.suggest", "picks.approve")]
    assert done == ["picks.search", "picks.import", "picks.import_book_image", "picks.import_clip", "picks.put", "picks.auto", "picks.edit", "picks.ops"]       # the page's order


def test_the_owner_can_forbid_model_spending_for_both(api):
    r = api.put("/api/projects/%s/auto" % api.pid, json={"base_rev": api.get("/api/projects/%s/auto" % api.pid).json()["rev"], "spend": {"model": False}})
    assert r.status_code == 200, r.text
    st = api.get("/api/projects/%s/state" % api.pid).json()
    assert action(st, "picks.auto")["auto_ok"] is False and action(st, "picks.edit")["auto_ok"] is False
    assert action(st, "picks.search")["auto_ok"] is True and action(st, "picks.ops")["auto_ok"] is True       # what costs nothing stays free for an agent
    allowed = api.put("/api/projects/%s/auto" % api.pid, json={"base_rev": r.json()["rev"], "spend": {"model": True}})
    assert allowed.status_code == 200
    assert action(api.get("/api/projects/%s/state" % api.pid).json(), "picks.auto")["auto_ok"] is True
