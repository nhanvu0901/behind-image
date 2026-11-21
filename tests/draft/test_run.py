import json
import threading
import time

import pytest

from bti.draft import run as R
from bti.draft.guard import Guard
from bti.draft.inputs import DraftError
from bti.editor import proposals
from bti.longjob import LongJobManager
from test_agy import fake  # noqa: F401  (the fake agy fixture)


@pytest.fixture()
def mgr(proj):
    return LongJobManager(projects_root=proj.parent)


def finish(mgr, rec, timeout=120):
    j = mgr.wait(rec, timeout=timeout)
    assert j is not None and j["state"] not in ("queued", "running", "waiting"), j
    return j


def gf(d):
    return Guard(d, extra=lambda: None, repo_root=d.parent)


def test_readiness_and_state(proj):
    r = R.readiness(proj)
    assert r["ok"] and r["voice"]["ok"] and r["picks"]["ok"]
    assert R.state(proj)["state"] == "none"
    p = json.loads((proj / "picks.json").read_text())
    p["approval"] = {"approved": False}
    (proj / "picks.json").write_text(json.dumps(p))
    r = R.readiness(proj)
    assert not r["ok"] and "duyệt" in r["picks"]["detail"]


def test_start_refuses_when_not_ready(proj, mgr):
    p = json.loads((proj / "picks.json").read_text())
    p["approval"] = {"approved": False}
    (proj / "picks.json").write_text(json.dumps(p))
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="auto", manager=mgr)
    assert e.value.code == "draft_not_ready"
    with pytest.raises(DraftError) as e:
        R.start(proj.name, proj, provider="nope", manager=mgr)
    assert e.value.code == "bad_provider"


def test_auto_job_writes_a_proposal_with_hashes(proj, mgr):
    rec = R.start(proj.name, proj, provider="auto", manager=mgr)
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["error_code"], j["log_tail"])
    pid = j["result"]["proposal_id"]
    doc = json.loads((proj / "proposals" / (pid + ".json")).read_text(encoding="utf-8"))
    assert doc["author"] == "agent:auto" and doc["id"] == pid and doc["base_rev"] is None
    assert proposals.shape_problem(doc["storyboard"]) is None and len(doc["storyboard"]["shots"]) >= 6
    assert doc["made_from"]["timing"] and doc["made_from"]["picks"] and doc["issues_left"] == [] or all(i["level"] != "error" for i in doc["issues_left"])
    assert not (proj / "storyboard.json").exists()                           # a draft never writes into the project
    st = R.state(proj)
    assert st["state"] == "done" and st["proposal"] == pid
    assert R.last_run(proj)["status"] == "done"
    t = json.loads((proj / "timing.json").read_text())
    t["words"][0]["w"] = "changed"
    (proj / "timing.json").write_text(json.dumps(t))
    assert R.state(proj)["state"] == "stale"


def test_one_number_of_shots_everywhere(proj, mgr):
    """SU-007: the panel, the proposal summary and the storyboard that "Áp dụng" makes all say the shots of the compiled storyboard."""
    rec = R.start(proj.name, proj, provider="auto", manager=mgr)
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["error_code"])
    pid = j["result"]["proposal_id"]
    doc = json.loads((proj / "proposals" / (pid + ".json")).read_text(encoding="utf-8"))
    n_all = len(doc["storyboard"]["shots"])
    last = R.last_run(proj)
    assert last["n_shots"] == n_all == j["result"]["n_shots"]
    assert last["n_content"] + last["n_cards"] == n_all
    assert doc["summary"] == "Bản nháp tự động: %d cảnh: %d cảnh nội dung, %d thẻ" % (n_all, last["n_content"], last["n_cards"])
    assert R.shots_text(54, 48, 6) == "54 cảnh: 48 cảnh nội dung, 6 thẻ"


def test_a_second_job_while_one_runs_is_busy(proj, mgr, fake):
    fake.mode("slow")
    rec = R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python")
    time.sleep(1.0)
    with pytest.raises(Exception) as e:
        R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf)
    assert type(e.value).__name__ == "Busy"
    mgr.cancel(rec)
    finish(mgr, rec, 60)


def test_agy_job_end_to_end(proj, mgr, fake):
    rec = R.start(proj.name, proj, provider="agy", model="gemini-x", manager=mgr, guard_factory=gf, python="python")
    j = finish(mgr, rec)
    assert j["state"] == "done", (j["error"], j["error_code"], j["log_tail"])
    pid = j["result"]["proposal_id"]
    doc = json.loads((proj / "proposals" / (pid + ".json")).read_text(encoding="utf-8"))
    assert doc["author"] == "agent:agy:gemini-x" and doc["summary"] == "Fake agent summary"
    assert [e for e in doc["issues_left"] if e["level"] == "error"] == []
    run_dir = next((proj / "cache" / "draft").iterdir() if False else (p for p in (proj / "cache" / "draft").iterdir() if p.is_dir()))
    assert (run_dir / "events.jsonl").is_file() and (run_dir / "out" / "c01.json").is_file()
    a = fake.calls()[0]["argv"]
    assert a[a.index("--model") + 1] == "gemini-x"


def test_bad_output_is_repaired_then_degraded(proj, mgr, fake):
    fake.mode("bad")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"), 180)
    assert j["state"] == "done", (j["error"], j["error_code"], j["log_tail"])
    doc = json.loads((proj / "proposals" / (j["result"]["proposal_id"] + ".json")).read_text(encoding="utf-8"))
    assert doc["degraded"] and [e for e in doc["issues_left"] if e["level"] == "error"] == []
    assert len(fake.prompts()) == 3                                          # first turn and two repair turns


def test_tampered_run_takes_nothing(proj, mgr, fake):
    fake.mode("tamper")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == "draft_tampered"
    assert not list((proj / "proposals").glob("*")) if (proj / "proposals").exists() else True
    assert R.last_run(proj)["status"] == "tampered"


def test_agent_that_writes_nothing_fails_clearly(proj, mgr, fake):
    (fake.dir / "cfg.json").write_text(json.dumps({"specs": {}, "victim": str(proj / "picks.json")}))
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == "draft_no_output"


def test_agy_error_codes_reach_the_job(proj, mgr, fake):
    fake.mode("auth")
    j = finish(mgr, R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python"))
    assert j["state"] == "error" and j["error_code"] == "agy_auth" and "đăng nhập" in j["error"]


def test_cancel_stops_the_agent(proj, mgr, fake):
    fake.mode("slow")
    rec = R.start(proj.name, proj, provider="agy", manager=mgr, guard_factory=gf, python="python")
    time.sleep(2.0)
    assert mgr.cancel(rec)
    j = finish(mgr, rec, 60)
    assert j["state"] == "cancelled"
    assert not (proj / "proposals").exists() or not list((proj / "proposals").glob("*"))
