"""The ends of an automatic run: every reason has its outcome and its sentences, the words the sentences need are the project's own words (steps, gates, needs), and
the list the page's own test reads is the server's."""
import json
import re
from pathlib import Path

import pytest

from bti.auto_run import checks, loop, reasons

REPO = Path(__file__).resolve().parents[2]


def test_there_are_exactly_the_six_outcomes_the_brief_names_and_every_reason_belongs_to_one():
    assert reasons.OUTCOMES == ("done", "needs_owner", "failed", "nothing_to_do", "cancelled", "limit")
    assert {v[0] for v in reasons.REASONS.values()} == set(reasons.OUTCOMES)
    assert sorted(sum(reasons.REASON_OF_OUTCOME.values(), [])) == sorted(reasons.REASONS)


def test_the_steps_gates_and_needs_are_the_apps_own():
    from bti import auto
    from bti.editor import pipeline_api, state_api
    assert reasons.STEPS == list(pipeline_api.STEPS)
    assert reasons.GATES == auto.GATES
    assert set(reasons.GATE_STEP.values()) <= set(reasons.STEP_IDS)
    for g in auto.GATES:                                                           # the step of a gate is the step of its approve action
        assert state_api.SPEC[g + ".approve"].step == {"script": "script", "picks": "picks", "edit": "edit"}[reasons.GATE_STEP[g]]
    missing = sorted(set(state_api.NEEDS) - set(reasons.NEED_VI))
    assert not missing, "a new word of `needs` has no Vietnamese phrase in bti/auto_run/reasons.py NEED_VI: %s" % missing


def test_every_sentence_is_vietnamese_one_sentence_and_free_of_placeholders():
    samples = reasons.samples()
    assert [r["reason"] for r in samples] == list(reasons.REASONS)
    for r in samples:
        s = r["sentence"]
        assert reasons._is_vietnamese(s), r["reason"]
        assert s.endswith("."), (r["reason"], s)
        assert "{" not in s and "}" not in s and " ? " not in s and "?." not in s, (r["reason"], s)
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", s) or r["reason"] in ("action_failed",), (r["reason"], s)        # no id on the page, but the code of a refused call is said once
        assert r["outcome"] in reasons.OUTCOMES and r["detail"] and (r["fix"] is None) == (r["outcome"] == "done"), r["reason"]
        assert not re.search(r"[{}]", r["detail"] + (r["fix"] or "")), r["reason"]


POINTS_TO_A_STEP = ("gate_not_allowed", "spend_not_allowed", "paid_needs_owner", "quality_warning", "quality_error", "gate_refused", "repair_needed", "nothing_to_do", "needs_content",
                    "no_progress", "until_reached")


def test_a_sentence_with_a_link_names_the_step_and_the_link_is_the_pages_own():
    for r in reasons.samples("arn"):
        if r["step"]:
            assert r["link"] == "#/project/arn/%s" % r["step"] and r["step_label"] == reasons.STEP_LABEL[r["step"]], r["reason"]
            if r["reason"] in POINTS_TO_A_STEP:
                assert r["step_label"] in r["sentence"], r["reason"]
        else:
            assert r["link"] is None


def test_every_outcome_is_made_by_the_loop_somewhere():
    """A reason that nothing makes is dead text: the loop's source names every reason (the other code makes them through its own helpers)."""
    src = "".join((REPO / "bti" / "auto_run" / f).read_text(encoding="utf-8") for f in ("loop.py", "job.py", "runlog.py"))
    for reason in reasons.REASONS:
        assert '"%s"' % reason in src, "nothing makes the reason %s" % reason


def test_the_file_the_page_reads_is_the_servers_list():
    f = REPO / "tests" / "editor_frontend" / "fixtures" / "autorun_results.json"
    assert json.loads(f.read_text(encoding="utf-8")) == json.loads(json.dumps(reasons.samples(), ensure_ascii=False)), \
        "regenerate it: python -m bti.auto_run.reasons --write tests/editor_frontend/fixtures/autorun_results.json"


def test_the_new_codes_have_a_hint_and_a_page_sentence():
    from bti.editor import hints
    for code in ("auto_not_enabled", "auto_running", "auto_run_not_found"):
        assert code in hints.HINTS and hints.HINTS[code]["fix"].endswith(".")
    js = (REPO / "bti" / "editor" / "static" / "js" / "errmsg.js").read_text(encoding="utf-8")
    for code in ("auto_not_enabled", "auto_running", "auto_run_not_found"):
        assert re.search(r"\b%s:" % code, js), code


def test_the_error_the_route_gives_is_the_one_the_cli_maps_to_a_person():
    from bti.cli import exitcodes as X
    assert X.exit_for_error(409, {"code": "auto_not_enabled", "retry": "after_fix"}) == X.PERSON
    assert X.exit_for_error(409, {"code": "auto_running", "retry": "later"}) == X.BUSY


def test_the_constants_of_the_loop_are_the_ones_the_documents_say():
    assert (loop.DEFAULT_MAX_STEPS, loop.MAX_STEPS_LIMIT, loop.ACTOR) == (40, 200, "agent:auto")
    assert set(checks.STOPS) == set(checks.TOLERATED) == set(reasons.GATES)


def test_the_result_names_what_a_reader_needs():
    r = reasons.make("gate_not_allowed", pid="arn", gate="picks", action="picks.approve", action_label="Duyệt chọn hình")
    assert r["step"] == "picks" and r["gate"] == "picks" and r["step_label"] == "Chọn hình" and r["fix"].count("picks") >= 1
    r = reasons.make("exported", pid="arn")
    assert r["step"] == "export" and r["link"] == "#/project/arn/export" and r["fix"] is None
    with pytest.raises(KeyError):
        reasons.make("no_such_reason")
