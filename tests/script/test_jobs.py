import json
import time

import httpx
import pytest

from bti.script import generate, store
from bti.script.prompting import RETRY_MARK
from bti.script.providers import mock as mock_mod, set_transport
from bti.script.runner import ScriptJobs

MOCK = {"id": "mock", "provider": "mock", "model": "mock", "key_env": None}


def wait(jobs, job, seconds=15):
    end = time.time() + seconds
    while time.time() < end:
        if job.state in ("done", "error", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job still {job.state}")


def run(jobs, kind, pdir, fn, **kw):
    return wait(jobs, jobs.start(kind, pdir.name, "mock", fn, **kw))


def make_outline_job(jobs, pdir, notes=""):
    return run(jobs, "outline", pdir, lambda j: generate.run_outline(j, pdir, MOCK, notes))


@pytest.fixture()
def approved(tproj):
    jobs = ScriptJobs()
    j = make_outline_job(jobs, tproj)
    assert j.state == "done", j.error
    o = store.load_outline(tproj)
    store.approve(tproj, "outline", o.rev())
    return jobs, tproj


def test_outline_job_with_the_mock_provider(tproj):
    jobs = ScriptJobs()
    j = make_outline_job(jobs, tproj)
    assert j.state == "done" and j.progress == 1.0 and j.chapters[0]["state"] == "done" and j.chapters[0]["attempts"] == 1
    o = store.load_outline(tproj)
    assert o.source["kind"] == "model" and o.source["model"] == "mock" and len(o.chapters) == 6 and not o.approval["approved"]
    assert all(f.sources for f in o.facts) and any(f.certainty == "disputed" and f.conflict for f in o.facts)
    assert {s for f in o.facts for s in f.sources} <= {p for p in json.loads(json.dumps(__import__("bti.script.brief", fromlist=["x"]).build_brief(tproj)["paragraph_ids"]))}


def test_outline_retry_when_the_first_answer_cannot_be_read(tproj):
    jobs = ScriptJobs()
    j = make_outline_job(jobs, tproj, "[mock:badoutline]")
    assert j.state == "done" and j.chapters[0]["attempts"] == 2
    retry_call = [c for c in mock_mod.CALLS if c["retry"]]
    assert len(retry_call) == 1 and "could not be read as an outline" not in retry_call[0]["user"]   # the validator message is appended
    assert "No chapters were found" in retry_call[0]["user"] and RETRY_MARK in retry_call[0]["user"]
    assert store.read_paste(tproj, "outline") == ""                                                 # success clears the kept paste


def test_narration_job_per_chapter_progress_and_approval_gate(approved):
    jobs, d = approved
    o = store.load_outline(d)
    j = run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK))
    assert j.state == "done" and [c["state"] for c in j.chapters] == ["done"] * 6 and j.progress == 1.0
    assert all(c["words"] > 50 for c in j.chapters)
    n = store.load_narration(d)
    assert [c.id for c in n.chapters] == [c.id for c in o.chapters] and n.source["model"] == "mock"
    assert n.source["outline_sha1"] == o.rev()
    assert not n.approval["approved"]
    ids = [b.id for c in n.chapters for b in c.beats]
    assert len(ids) == len(set(ids)) and all(b.facts and b.show for c in n.chapters for b in c.beats)
    # a later chapter prompt carries the earlier chapters as context
    last = [c for c in mock_mod.CALLS if "Chapters to write now: c06" in c["user"]][0]["user"]
    assert "THE CHAPTERS ALREADY WRITTEN" in last and "## c01 COLD OPEN" in last


def test_narration_job_refuses_an_unapproved_or_stale_outline(tproj):
    jobs = ScriptJobs()
    make_outline_job(jobs, tproj)
    j = run(jobs, "narration", tproj, lambda job: generate.run_narration(job, tproj, MOCK))
    assert j.state == "error" and j.error_kind == "conflict" and "not approved" in j.error
    o = store.load_outline(tproj)
    store.approve(tproj, "outline", o.rev())
    o = store.load_outline(tproj)
    o.thesis += "!"
    store.save_outline(tproj, o, backup=False)                          # an edit drops the approval
    j = run(jobs, "narration", tproj, lambda job: generate.run_narration(job, tproj, MOCK))
    assert j.state == "error" and j.error_kind == "conflict"


def test_validation_retry_keeps_finished_chapters_and_uses_the_validators_message(approved):
    jobs, d = approved
    j = run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK, notes="[mock:bad c02]"))
    assert j.state == "done"
    c02 = next(c for c in j.chapters if c["id"] == "c02")
    assert c02["attempts"] == 2 and all(c["attempts"] == 1 for c in j.chapters if c["id"] != "c02")
    retry = [c for c in mock_mod.CALLS if c["retry"]]
    assert len(retry) == 1 and "Validation failed" in retry[0]["user"] and "c02" in retry[0]["user"]
    n = store.load_narration(d)
    assert not any("[PAUSE]" in b.text for c in n.chapters for b in c.beats)


def test_second_validation_failure_stops_the_job_but_keeps_what_was_written(approved):
    jobs, d = approved
    j = run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK, notes="[mock:alwaysbad c03]"))
    assert j.state == "error" and j.error_kind == "validation" and "c03" in j.error
    states = {c["id"]: c["state"] for c in j.chapters}
    assert states["c01"] == states["c02"] == "done" and states["c03"] == "failed" and states["c04"] == "pending"
    n = store.load_narration(d)
    assert [c.id for c in n.chapters] == ["c01", "c02"]                                    # finished chapters kept
    assert "[PAUSE]" in store.read_paste(d, "narration")                                   # the failed answer is kept for the owner
    # run again for the rest: the finished chapters stay, ids continue
    first_ids = [b.id for c in n.chapters for b in c.beats]
    j2 = run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK, ["c03", "c04", "c05", "c06"]))
    assert j2.state == "done"
    n2 = store.load_narration(d)
    assert [c.id for c in n2.chapters] == ["c01", "c02", "c03", "c04", "c05", "c06"]
    assert [b.id for c in n2.chapters[:2] for b in c.beats] == first_ids
    assert store.read_paste(d, "narration") == ""


def test_rewrite_one_chapter_with_a_note(approved):
    jobs, d = approved
    run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK))
    before = store.load_narration(d)
    old_ids = {c.id: [b.id for b in c.beats] for c in before.chapters}
    j = run(jobs, "narration", d, lambda job: generate.run_narration(job, d, MOCK, ["c04"], "make it shorter"))
    assert j.state == "done" and [c["id"] for c in j.chapters] == ["c04"]
    after = store.load_narration(d)
    for c in after.chapters:
        if c.id != "c04":
            assert [b.id for b in c.beats] == old_ids[c.id]
    assert set(old_ids["c04"]).isdisjoint(b.id for b in after.chapter("c04").beats)         # fresh ids, never reused
    assert "make it shorter" in [c for c in mock_mod.CALLS if "Chapters to write now: c04" in c["user"]][-1]["user"]


def test_cancel_stops_the_job_and_keeps_finished_chapters(approved):
    jobs, d = approved
    job = jobs.start("narration", d.name, "mock", lambda j: generate.run_narration(j, d, MOCK, ["c01", "c02"]))
    wait_for = time.time() + 5
    while time.time() < wait_for and not (job.chapters and job.chapters[0]["state"] == "done"):
        time.sleep(0.01)
    # make the next call slow, then cancel while it runs
    job2 = wait(jobs, job)
    assert job2.state == "done"
    j = jobs.start("narration", d.name, "mock", lambda jb: generate.run_narration(jb, d, MOCK, ["c03", "c04"], "[mock:slow]"))
    while j.state == "queued" or not j.chapters or j.chapters[0]["state"] != "running":
        time.sleep(0.01)
    time.sleep(0.2)
    assert jobs.cancel(j.id)
    wait(jobs, j)
    assert j.state == "cancelled" and all(c["state"] in ("cancelled", "done") for c in j.chapters)
    n = store.load_narration(d)
    assert [c.id for c in n.chapters] == ["c01", "c02"]                                    # nothing from the cancelled run
    assert not jobs.cancel("nope")


def test_hard_timeout_and_offer_of_another_model(approved):
    jobs, d = approved
    jobs.hard_timeout = 0.4
    j = jobs.start("narration", d.name, "mock", lambda jb: generate.run_narration(jb, d, MOCK, ["c01"], "[mock:slow]"),
                   alternatives=lambda: ["mock", "gemini-4-argon"])
    wait(jobs, j)
    assert j.state == "error" and j.error_kind == "timeout" and "hard limit" in j.error
    assert j.alternatives == ["gemini-4-argon"]                                                 # offered, not switched silently
    assert store.load_narration(d) is None


def test_rate_limit_offers_the_next_model(approved):
    jobs, d = approved
    j = run(jobs, "narration", d, lambda jb: generate.run_narration(jb, d, MOCK, ["c01"], "[mock:ratelimit]"),
            alternatives=lambda: ["mock", "openrouter-claude"])
    assert j.state == "error" and j.error_kind == "rate_limit" and j.alternatives == ["openrouter-claude"]
    assert j.chapters[0]["state"] == "pending" or j.chapters[0]["state"] == "running"


def test_a_real_provider_through_the_job_with_a_recorded_shape_fake(approved, monkeypatch):
    jobs, d = approved
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKE0000000000")
    outline = store.load_outline(d)

    def handler(req: httpx.Request):
        user = json.loads(req.content)["contents"][0]["parts"][0]["text"]
        cid = user.rsplit("Chapters to write now: ", 1)[1].split()[0]
        oc = outline.chapter(cid.strip(","))
        text = f"FINAL SCRIPT\n\n## {oc.id} {oc.title}\n" + "\n\n".join(
            f"Look at this part of the panel, number {i}. It is plain to see.\n>> facts: f01 | show: the panel" for i in range(3))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]})
    set_transport(httpx.MockTransport(handler))
    spec = {"id": "gemini-4-argon", "provider": "gemini", "model": "gemini-4-argon", "key_env": "GEMINI_API_KEY"}
    j = run(jobs, "narration", d, lambda jb: generate.run_narration(jb, d, spec, ["c01", "c02"]))
    assert j.state == "done", j.error
    n = store.load_narration(d)
    assert [len(c.beats) for c in n.chapters] == [3, 3] and n.source["model"] == "gemini-4-argon"
    assert "AIzaFAKE" not in json.dumps(j.public())


def test_an_error_message_with_a_key_is_redacted(approved, monkeypatch):
    jobs, d = approved
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSECRET9999999999")
    set_transport(httpx.MockTransport(lambda req: httpx.Response(500, text="boom AIzaSECRET9999999999")))
    spec = {"id": "g", "provider": "gemini", "model": "m", "key_env": "GEMINI_API_KEY"}
    j = run(jobs, "narration", d, lambda jb: generate.run_narration(jb, d, spec, ["c01"]))
    assert j.state == "error" and "AIzaSECRET" not in json.dumps(j.public())


def test_one_job_per_project_is_visible_through_running(approved):
    jobs, d = approved
    j = jobs.start("narration", d.name, "mock", lambda jb: generate.run_narration(jb, d, MOCK, ["c01"], "[mock:slow]"))
    time.sleep(0.1)
    assert jobs.running(d.name).id == j.id
    jobs.cancel(j.id)
    wait(jobs, j)
    assert jobs.running(d.name) is None
