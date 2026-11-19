"""The length of the narration binds: the budget of a chapter is a ceiling, and a chapter that comes out more than 10% over it is written again ONCE by the
job itself, with a note that says how many words to cut. Bounded (one retry per chapter, a few chapters per job), visible (the chapter's line and the job's
result), counted (one model call more each), and a retry that cannot be used leaves the first text and the warning."""
import time

import pytest

from bti.script import generate, store, validate
from bti.script.prompting import CUT_MARK, RETRY_MARK
from bti.script.providers import mock as mock_mod
from bti.script.runner import ScriptJobs
from bti.script.stats import count_words

MOCK = {"id": "mock", "provider": "mock", "model": "mock", "key_env": None}


def wait(job, seconds=20):
    end = time.time() + seconds
    while time.time() < end:
        if job.state in ("done", "error", "cancelled"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"job still {job.state}")


def narrate(jobs, d, notes="", chapters=None):
    return wait(jobs.start("narration", d.name, "mock", lambda job: generate.run_narration(job, d, MOCK, chapters, notes)))


@pytest.fixture()
def approved(tproj):
    jobs = ScriptJobs()
    assert wait(jobs.start("outline", tproj.name, "mock", lambda j: generate.run_outline(j, tproj, MOCK, ""))).state == "done"
    o = store.load_outline(tproj)
    store.approve(tproj, "outline", o.rev())
    mock_mod.CALLS.clear()
    return jobs, tproj


def words_of(d):
    return {c.id: sum(count_words(b.text) for b in c.beats) for c in store.load_narration(d).chapters}


def budgets_of(d):
    return {c.id: c.word_budget for c in store.load_outline(d).chapters}


def script_calls():
    return [c for c in mock_mod.CALLS if c["user"].startswith("PHASE: script")]


def codes(d, code):
    return [i for i in validate.validate_narration(store.load_narration(d), store.load_outline(d)) if i["code"] == code]


def test_a_normal_run_stays_under_every_budget_and_asks_for_no_cut(approved):
    jobs, d = approved
    j = narrate(jobs, d)
    assert j.state == "done" and "shortened" not in j.result and "shortened" not in j.public()["result"]
    assert not [c for c in mock_mod.CALLS if c["cut"]] and len(script_calls()) == 6          # one call per chapter, nothing more
    w, b = words_of(d), budgets_of(d)
    assert all(w[c] <= b[c] for c in b) and all(w[c] >= 0.8 * b[c] for c in b)                # the budget is a ceiling, and the chapters come near it
    assert all(c["attempts"] == 1 and c["message"] == "" for c in j.chapters)
    assert not codes(d, "chapter_off_budget") and not codes(d, "words_off_target") and not codes(d, "words_under")


def test_the_prompt_of_the_first_call_states_the_budget_as_a_ceiling(approved):
    jobs, d = approved
    narrate(jobs, d, chapters=["c02"])
    u = script_calls()[0]["user"]
    b = budgets_of(d)["c02"]
    assert f"at most {b} words (aim for {round(b * 0.9)} to {b})" in u and "Each chapter's budget is a CEILING" in u and "none over 25" in u


def test_a_chapter_over_its_budget_is_written_again_once_with_a_note_that_says_how_many_words_to_cut(approved):
    jobs, d = approved
    j = narrate(jobs, d, notes="[mock:long c02]")
    assert j.state == "done", j.error
    cuts = [c for c in mock_mod.CALLS if c["cut"]]
    assert len(cuts) == 1 and not cuts[0]["retry"] and len(script_calls()) == 6 + 1          # one call more, counted as a model call
    rec = j.result["shortened"]
    assert len(rec) == 1 and rec[0]["chapter"] == "c02" and rec[0]["kept"] == "rewrite"
    b = budgets_of(d)["c02"]
    assert rec[0]["budget"] == b and rec[0]["words"] > b * (1 + generate.CUT_OVER_SHARE) and rec[0]["after"] <= b
    u = cuts[0]["user"]
    assert "Chapters to write now: c02" in u and CUT_MARK in u and RETRY_MARK not in u
    assert f"It has {rec[0]['words']} words and the budget of this chapter is {b}" in u and f"at most {b} words" in u
    assert f"{rec[0]['words'] - round(b * 0.95)} words fewer" in u                           # how many words to cut
    assert "## c02 THE MERCHANT CITY" in u.split("Here is your previous answer:")[1] and ">> facts:" in u.split("Here is your previous answer:")[1]   # its own text, to be cut
    assert words_of(d)["c02"] == rec[0]["after"]                                             # the rewrite is what was saved
    c02 = next(c for c in j.chapters if c["id"] == "c02")
    assert c02["attempts"] == 2 and c02["state"] == "done" and c02["message"] == f"đã cắt từ {rec[0]['words']} xuống {rec[0]['after']} từ (ngân sách {b})"
    assert all(c["attempts"] == 1 and c["message"] == "" for c in j.chapters if c["id"] != "c02")      # only the chapter that was over
    assert j.public()["result"]["shortened"] == rec and j.result["written"] == ["c01", "c02", "c03", "c04", "c05", "c06"]
    assert not codes(d, "chapter_off_budget")


def test_only_the_chapters_over_the_share_are_retried_and_the_share_is_ten_percent():
    assert generate.CUT_OVER_SHARE == 0.10
    assert not generate.over_budget(110, 100) and generate.over_budget(111, 100)
    assert not generate.over_budget(500, 0) and not generate.over_budget(50, 100)             # no budget, or under it: never


def test_at_most_a_few_chapters_per_job_get_the_second_call(approved, monkeypatch):
    jobs, d = approved
    assert generate.MAX_CUTS == 4
    monkeypatch.setattr(generate, "MAX_CUTS", 1)
    j = narrate(jobs, d, notes="[mock:long c02] [mock:long c04]")
    assert j.state == "done"
    assert [r["chapter"] for r in j.result["shortened"]] == ["c02"] and len([c for c in mock_mod.CALLS if c["cut"]]) == 1
    c04 = next(c for c in j.chapters if c["id"] == "c04")
    assert c04["attempts"] == 1 and c04["message"] == ""
    w, b = words_of(d), budgets_of(d)
    assert w["c04"] > b["c04"] * 1.3 and codes(d, "chapter_off_budget") and [i["chapter"] for i in codes(d, "chapter_off_budget")] == ["c04"]   # the warning stays


def test_a_retry_that_is_not_shorter_leaves_the_first_text_and_the_warning(approved):
    jobs, d = approved
    j = narrate(jobs, d, notes="[mock:alwayslong c02]")
    assert j.state == "done"
    rec = j.result["shortened"][0]
    assert rec["kept"] == "first" and rec["why"] == "the rewrite is not nearer to the budget" and rec["after"] >= rec["words"]
    assert words_of(d)["c02"] == rec["words"]                                                # the first text is what was saved
    c02 = next(c for c in j.chapters if c["id"] == "c02")
    assert c02["attempts"] == 2 and c02["message"].startswith("giữ bản đầu") and c02["state"] == "done"
    assert len([c for c in mock_mod.CALLS if c["cut"]]) == 1                                  # one retry per chapter, never a second one
    assert [i["chapter"] for i in codes(d, "chapter_off_budget")] == ["c02"]


def test_a_retry_that_cannot_be_used_leaves_the_first_text(approved):
    jobs, d = approved
    j = narrate(jobs, d, notes="[mock:cutbad c02]")
    assert j.state == "done"
    rec = j.result["shortened"][0]
    assert rec["kept"] == "first" and rec["why"] == "the rewrite could not be used" and "after" not in rec
    n = store.load_narration(d)
    assert words_of(d)["c02"] == rec["words"] and not any("[PAUSE]" in b.text for c in n.chapters for b in c.beats)
    assert len([c for c in mock_mod.CALLS if c["cut"]]) == 1


def test_a_retry_whose_call_fails_leaves_the_first_text_and_the_job_goes_on(approved):
    jobs, d = approved
    j = narrate(jobs, d, notes="[mock:cutfail c02]")
    assert j.state == "done", j.error
    rec = j.result["shortened"][0]
    assert rec["kept"] == "first" and rec["why"] == "the second call failed (http)"
    assert j.result["written"] == ["c01", "c02", "c03", "c04", "c05", "c06"]                  # the other chapters were written as usual
    assert words_of(d)["c02"] == rec["words"] and next(c for c in j.chapters if c["id"] == "c02")["state"] == "done"


def test_a_job_cancelled_during_the_retry_is_cancelled_and_writes_nothing_of_it(approved):
    jobs, d = approved
    job = jobs.start("narration", d.name, "mock", lambda jb: generate.run_narration(jb, d, MOCK, ["c02"], "[mock:long c02] [mock:cutslow]"))
    end = time.time() + 10
    while time.time() < end and not any(c["state"] == "retrying" for c in job.chapters):      # the first answer of c02 is in, the slow cut is running
        time.sleep(0.005)
    assert any(c["state"] == "retrying" and c["attempts"] == 2 for c in job.chapters)
    assert jobs.cancel(job.id)
    wait(job)
    assert job.state == "cancelled" and job.error is None                                      # the cancel is not a failed retry
    assert store.load_narration(d) is None and "shortened" not in job.result


def test_a_chapter_written_again_by_the_owner_is_cut_too(approved):
    """The same rule for one chapter asked for later with a note (the owner's "Viết lại chương")."""
    jobs, d = approved
    narrate(jobs, d)
    mock_mod.CALLS.clear()
    j = narrate(jobs, d, notes="[mock:long c04]", chapters=["c04"])
    assert j.state == "done" and [r["chapter"] for r in j.result["shortened"]] == ["c04"] and j.result["shortened"][0]["kept"] == "rewrite"
    assert len(script_calls()) == 2 and words_of(d)["c04"] <= budgets_of(d)["c04"]


def test_the_cut_note_is_in_the_prompt_builder_and_the_layout_is_the_models_own(tproj):
    from bti.script.prompting import build_prompt, cut_note, render_chapter
    from script_helpers import make_narration, make_outline
    n = make_narration()
    ch = n.chapters[1]
    text = render_chapter(ch)
    assert text.startswith("## c02 THE ROOM") and ">> facts: f01 | show: the mirror" in text
    note = cut_note(260, 200, ch)
    assert note.startswith(CUT_MARK) and "It has 260 words and the budget of this chapter is 200" in note and "70 words fewer" in note and text in note
    p = build_prompt("script", tproj, outline=make_outline(True), chapters=["c02"], cut_message=note)["text"]
    assert p.rstrip().endswith("Write the answer again, complete, in the exact layout above.") and CUT_MARK in p and RETRY_MARK not in p
