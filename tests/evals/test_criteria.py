"""Each kind of criterion on prepared outputs, one that passes and one that fails (and what it measured). The outputs are documents of the shape the app's routes give."""
import copy
import json
from pathlib import Path

import pytest

from bti.evals import criteria
import outputs as O

REPO = Path(__file__).resolve().parents[2]
TESTED: set[str] = set()


def check(kind, outs, **params):
    TESTED.add(kind)
    return criteria.evaluate({"id": "x", "kind": kind, **params}, outs)


def good(kind, outs, **params):
    r = check(kind, outs, **params)
    assert r["passed"] is True, r
    assert r["detail"]
    return r


def bad(kind, outs, **params):
    r = check(kind, outs, **params)
    assert r["passed"] is False, r
    assert r["detail"]
    return r


# ------------------------------------------------------------------------------------------------------------------------------- outline
def test_outline_chapters_between():
    assert good("outline.chapters_between", O.outline_outputs(), min=5, max=9)["value"] == 6
    r = bad("outline.chapters_between", O.outline_outputs(), min=7, max=9)
    assert r["value"] == 6 and "wanted 7 to 9" in r["detail"]


def test_outline_every_chapter_cites_a_source():
    good("outline.every_chapter_cites_a_source", O.outline_outputs())
    o = O.outline_outputs()
    o["outline"]["facts"][0]["sources"] = ["ZZZ-01"]                                 # c01 rests on a paragraph that is not in the dossier
    assert "c01" in bad("outline.every_chapter_cites_a_source", o)["value"]
    o = O.outline_outputs()
    o["outline"]["chapters"][2]["facts"] = []                                        # a chapter that uses no fact
    assert bad("outline.every_chapter_cites_a_source", o)["value"] == ["c03"]


def test_outline_facts_sourced():
    good("outline.facts_sourced", O.outline_outputs())
    o = O.outline_outputs()
    o["outline"]["facts"][0]["sources"] = ["ZZZ-01"]
    assert bad("outline.facts_sourced", o)["value"] == 0.8
    good("outline.facts_sourced", o, min_share=0.8)
    o["outline"]["facts"][1]["sources"] = []                                         # no source at all is unsourced too
    bad("outline.facts_sourced", o, min_share=0.8)


def test_outline_no_excluded_source():
    good("outline.no_excluded_source", O.outline_outputs())
    o = O.outline_outputs()
    o["outline"]["facts"][3]["sources"].append("MAD-01")                             # MAD is the book the brief excluded
    assert bad("outline.no_excluded_source", o)["value"] == ["f04"]


def test_outline_no_error_issues_and_warnings_at_most():
    good("outline.no_error_issues", O.outline_outputs())
    o = O.outline_outputs()
    o["issues"] = [{"level": "error", "code": "no_thesis", "message": "m"}]
    assert bad("outline.no_error_issues", o)["value"] == ["no_thesis"]
    o["issues"] = [{"level": "warning", "code": "fact_unused", "message": "m"}] * 2
    good("outline.warnings_at_most", o, max=2)
    assert bad("outline.warnings_at_most", o, max=1)["value"] == ["fact_unused", "fact_unused"]


def test_outline_budgets():
    assert good("outline.budget_near_target", O.outline_outputs(), tolerance=0.15)["value"] == 0.999
    o = O.outline_outputs()
    for c in o["outline"]["chapters"]:
        c["word_budget"] = 600
    assert bad("outline.budget_near_target", o)["value"] == 1.8
    good("outline.chapter_budget_between", O.outline_outputs(), min=80, max=450)
    o = O.outline_outputs()
    o["outline"]["chapters"][0]["word_budget"] = 40
    assert bad("outline.chapter_budget_between", o, min=80, max=450)["value"] == {"c01": 40}


def test_outline_thesis_and_hooks():
    good("outline.thesis_and_hooks", O.outline_outputs(), hooks=3)
    o = O.outline_outputs()
    o["outline"]["thesis"] = "This painting is about marriage."
    assert bad("outline.thesis_and_hooks", o)["value"]["thesis_is_question"] is False
    o = O.outline_outputs()
    o["outline"]["hook_choice"] = "h9"
    assert bad("outline.thesis_and_hooks", o)["value"]["chosen"] is False
    o = O.outline_outputs()
    del o["outline"]["hook_options"][2]
    bad("outline.thesis_and_hooks", o, hooks=3)


def test_outline_disputed_facts_and_use_of_facts_and_roles():
    good("outline.disputed_facts_have_conflict", O.outline_outputs())
    o = O.outline_outputs()
    o["outline"]["facts"][2]["conflict"] = ""
    assert bad("outline.disputed_facts_have_conflict", o)["value"] == ["f03"]
    good("outline.facts_all_used", O.outline_outputs(), min_share=0.9)
    o = O.outline_outputs()
    for c in o["outline"]["chapters"]:
        c["facts"] = ["f01"]
    assert bad("outline.facts_all_used", o)["value"] == 0.2
    good("outline.roles", O.outline_outputs())
    o = O.outline_outputs()
    o["outline"]["chapters"][-1]["role"] = "chapter"
    assert bad("outline.roles", o)["value"] == ["cold_open", "chapter"]


# ----------------------------------------------------------------------------------------------------------------------------- narration
def test_narration_length_and_minutes():
    r = good("narration.words_within_target", O.narration_outputs(), tolerance=0.15)
    assert 0.95 < r["value"] < 1.05
    short = O.narration_outputs()
    short["narration"] = O.narration(per_chapter=150)
    assert bad("narration.words_within_target", short)["value"] < 0.5
    assert good("narration.minutes_at_least", O.narration_outputs(), minutes=10)["value"] > 12
    assert bad("narration.minutes_at_least", short, minutes=10)["value"] < 7


def test_narration_beats_and_sentences():
    good("narration.max_beat_words", O.narration_outputs(), max=90)
    long_beats = O.narration_outputs()
    long_beats["narration"] = O.narration(per_chapter=600)
    assert bad("narration.max_beat_words", long_beats, max=90)["value"][0][1] == 150
    good("narration.max_sentence_words", O.narration_outputs(), max=28)
    wordy = O.narration_outputs()
    wordy["narration"] = O.narration(sentence=40)
    assert bad("narration.max_sentence_words", wordy, max=28)["value"][0][1] == 40
    assert good("narration.median_sentence_words", O.narration_outputs(), min=8, max=22)["value"] == 10
    assert bad("narration.median_sentence_words", wordy, min=8, max=22)["value"] == 40
    terse = O.narration_outputs()
    terse["narration"] = O.narration(sentence=3)
    bad("narration.median_sentence_words", terse, min=8, max=22)


def test_narration_issues_chapters_budgets_show_facts():
    good("narration.no_error_issues", O.narration_outputs())
    o = O.narration_outputs()
    o["issues"].append({"level": "error", "code": "empty_beat", "message": "m"})
    assert bad("narration.no_error_issues", o)["value"] == ["empty_beat"]
    good("narration.chapters_match_outline", O.narration_outputs())
    o = O.narration_outputs()
    del o["narration"]["chapters"][2]
    assert len(bad("narration.chapters_match_outline", o)["value"]) == 5
    good("narration.chapter_budgets", O.narration_outputs(), tolerance=0.3)
    o = O.narration_outputs()
    o["narration"]["chapters"][1]["beats"] += o["narration"]["chapters"][1]["beats"]
    assert "c02" in bad("narration.chapter_budgets", o)["value"]
    good("narration.every_beat_has_show", O.narration_outputs())
    o = O.narration_outputs()
    o["narration"]["chapters"][0]["beats"][0]["show"] = []
    assert len(bad("narration.every_beat_has_show", o)["value"]) == 1
    good("narration.facts_in_outline", O.narration_outputs())
    o = O.narration_outputs()
    o["narration"]["chapters"][0]["beats"][0]["facts"] = ["f99"]
    assert bad("narration.facts_in_outline", o)["value"] == ["f99"]


def test_narration_spoken_words_and_copied_runs():
    good("narration.spoken_words_only", O.narration_outputs())
    for text in ("See PAY-07 for this.", "A line with f03 in it.", "**bold** words", "a [stage direction] here", "one | two"):
        o = O.narration_outputs()
        o["narration"]["chapters"][0]["beats"][0]["text"] = text
        assert bad("narration.spoken_words_only", o)["value"], text
    assert good("narration.copied_runs_at_most", O.narration_outputs(), max_share=0.25)["value"] == 0.12
    o = O.narration_outputs()
    o["issues"] = [{"level": "info", "code": "overlap", "message": "60% of the words sit in runs"}]
    assert bad("narration.copied_runs_at_most", o, max_share=0.25)["value"] == 0.6
    o["issues"] = []
    assert bad("narration.copied_runs_at_most", o)["value"] is None                      # the app gave no information: not a pass


# ------------------------------------------------------------------------------------------------------------------------------- draft
def test_draft_no_error_issues():
    good("draft.no_error_issues", O.draft_outputs())
    o = O.draft_outputs()
    o["issues"] = [{"level": "error", "code": "undrawable", "message": "m"}]
    assert bad("draft.no_error_issues", o)["value"] == ["undrawable"]


def test_draft_shot_pace():
    r = good("draft.shot_pace", O.draft_outputs(step=7.0))
    assert r["value"]["median"] == 7.0
    assert bad("draft.shot_pace", O.draft_outputs(step=20.0))["value"]["median"] == 20.0
    assert bad("draft.shot_pace", O.draft_outputs(step=1.0))["value"]["shortest"] == 1.0
    o = O.draft_outputs(step=7.0)
    o["storyboard"]["shots"][3]["_t0"], o["storyboard"]["shots"][3]["_t1"] = 21.0, 61.0           # resolved times win: one shot of 40 s
    assert bad("draft.shot_pace", o)["value"]["longest"] == 40.0


def test_draft_techniques():
    r = good("draft.distinct_techniques_at_least", O.draft_outputs(), k=6)
    assert len(r["value"]) == 7
    bad("draft.distinct_techniques_at_least", O.draft_outputs(), k=12)
    good("draft.core_techniques", O.draft_outputs(), min_share=0.2)
    reg = json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))["techniques"]
    shorts = next(t["id"] for t in reg if t.get("channel_usage") == "shorts_only")
    o = O.draft_outputs(techniques=[shorts])
    r = bad("draft.core_techniques", o, min_share=0.0)
    assert r["value"]["shorts_only"] == [shorts]


def test_draft_covers_the_narration():
    good("draft.covers_the_narration", O.draft_outputs())
    o = O.draft_outputs()
    o["storyboard"]["shots"][0]["start"] = {"t": 5.0}
    assert bad("draft.covers_the_narration", o)["value"]["first"] == 5.0
    o = O.draft_outputs()
    o["storyboard"]["shots"][3]["_t0"], o["storyboard"]["shots"][3]["_t1"] = 21.0, 26.0          # resolved times: shot 4 ends at 26 s, shot 5 starts at 28 s
    o["storyboard"]["shots"][4]["_t0"], o["storyboard"]["shots"][4]["_t1"] = 28.0, 35.0
    assert bad("draft.covers_the_narration", o)["value"]["gaps"] == [2.0]
    o = O.draft_outputs()
    o["storyboard"]["end"] = {"t": 50.0}
    assert bad("draft.covers_the_narration", o)["value"]["last_end"] == 50.0


def test_draft_context_lines_and_picks_and_notes():
    good("draft.context_lines_avoid_the_main_painting", O.draft_outputs())
    o = O.draft_outputs()
    for s in o["storyboard"]["shots"]:
        if s["intent"] == "context":
            s["slots"]["image"]["asset"] = "A"                                         # the main painting
    assert bad("draft.context_lines_avoid_the_main_painting", o)["value"]
    assert good("draft.picks_are_used", O.draft_outputs(), min_share=0.8)["value"] == 1.0
    o = O.draft_outputs()
    o["picks"]["beats"]["b0002"]["items"][0]["asset"] = "C"
    assert bad("draft.picks_are_used", o, min_share=0.8)["value"] == 0.0
    good("draft.every_shot_has_a_reason", O.draft_outputs(), min_share=0.9)
    o = O.draft_outputs()
    for s in o["storyboard"]["shots"][:6]:
        s["note"] = ""
    assert bad("draft.every_shot_has_a_reason", o, min_share=0.9)["value"] < 0.6


def test_draft_no_narration_on_screen_and_locked_shots():
    good("draft.no_narration_on_screen", O.draft_outputs(), run=5)
    o = O.draft_outputs()
    o["storyboard"]["shots"][2]["overlays"] = [{"technique": "X-ANN-01", "params": {"text": "w10 w11 w12 w13 w14 and more"}}]
    assert bad("draft.no_narration_on_screen", o, run=5)["value"] == ["s0003"]
    o = O.draft_outputs()
    o["storyboard"]["shots"][2]["params"]["label"] = "Latin inscription"
    good("draft.no_narration_on_screen", o, run=5)
    o = O.draft_outputs()
    o["before"] = copy.deepcopy(o["storyboard"])
    o["before"]["shots"][1]["locked"] = True
    o["storyboard"]["shots"][1]["locked"] = True
    good("draft.locked_shots_unchanged", o)
    o["storyboard"]["shots"][1]["technique"] = "CAM-03"
    assert bad("draft.locked_shots_unchanged", o)["value"] == ["s0002"]


# ------------------------------------------------------------------------------------------------------------------------------- edits
def test_edit_only_scope_changed_and_changed_something():
    good("edit.only_scope_changed", O.edit_outputs())
    good("edit.changed_something_in_scope", O.edit_outputs())
    o = O.edit_outputs()
    o["after"]["shots"][0]["technique"] = "CAM-03"                                     # a shot outside the scope changed
    assert bad("edit.only_scope_changed", o)["value"]["outside"] == ["s0001"]
    o = O.edit_outputs()
    del o["after"]["shots"][5]                                                         # a shot was removed
    assert bad("edit.only_scope_changed", o)["value"]["outside"] == ["s0006"]
    o = O.edit_outputs()
    o["before"]["shots"][5]["locked"] = True
    o["after"]["shots"][5]["locked"] = True
    o["after"]["shots"][5]["note"] = "changed"
    r = bad("edit.only_scope_changed", o)
    assert r["value"]["locked"] == ["s0006"]
    o = O.edit_outputs()
    o["after"] = copy.deepcopy(o["before"])
    bad("edit.changed_something_in_scope", o)
    o = O.edit_outputs()
    o["scope"] = {"all": True}
    o["after"]["shots"][0]["technique"] = "CAM-03"
    good("edit.only_scope_changed", o)                                                 # the scope is the whole video
    o["scope"] = {"chapter": "c02"}
    o["timing"] = O.timing()
    o["before"]["shots"][0]["start"] = {"t": 0.0}
    r = check("edit.only_scope_changed", o)
    assert r["passed"] is False                                                        # shot 1 is in chapter c01: outside the scope


def test_edit_metric_moved():
    r = good("edit.metric_moved", O.edit_outputs(), metric="zoom_rate", direction="decrease")
    assert len(r["value"]["moved"]) == 2
    bad("edit.metric_moved", O.edit_outputs(), metric="zoom_rate", direction="increase")
    o = O.edit_outputs()
    o["after"]["shots"][3]["overlays"] = [{"technique": "HI-01"}]
    good("edit.metric_moved", o, metric="overlay_count", direction="increase", min_shots=1)
    bad("edit.metric_moved", O.edit_outputs(), metric="overlay_count", direction="increase")
    o = O.edit_outputs()
    o["before"]["shots"][3]["params"]["ramp_in"] = 0.5
    o["after"]["shots"][3]["params"]["ramp_in"] = 1.0
    good("edit.metric_moved", o, metric="param:ramp_in", direction="increase", shots=["s0004"])
    assert "unknown metric" in check("edit.metric_moved", O.edit_outputs(), metric="beauty", direction="increase")["detail"]


def test_edit_no_error_issues_and_answered_cannot():
    good("edit.no_error_issues", O.edit_outputs())
    o = O.edit_outputs()
    o["issues"] = [{"level": "error", "code": "undrawable", "message": "m"}]
    bad("edit.no_error_issues", o)
    o = O.edit_outputs()
    o["after"] = copy.deepcopy(o["before"])
    o["answer"] = {"code": "cannot", "state": "done", "reason": "Cần một bức tranh mới: hãy nhập hình trước."}
    good("edit.answered_cannot", o)
    o["answer"]["reason"] = ""
    assert bad("edit.answered_cannot", o)["value"]["reason"] == ""
    o["answer"] = {"code": "applied", "reason": "x"}
    bad("edit.answered_cannot", o)
    o = O.edit_outputs()
    o["answer"] = {"code": "cannot", "reason": "x"}
    assert bad("edit.answered_cannot", o)["value"]["unchanged"] is False              # it said cannot but changed something
    good("edit.answered_cannot", {**o, "after": o["before"], "answer": {"code": "escalate", "reason": "closer look"}}, codes=["escalate"])


# ------------------------------------------------------------------------------------------------------------------------------- picks
def test_picks_decided_main_issues_credit_variety_flags():
    good("picks.every_beat_decided", O.picks_outputs(), min_share=1.0)
    o = O.picks_outputs()
    del o["picks"]["beats"]["b0003"]
    assert bad("picks.every_beat_decided", o)["value"] == 0.875
    o["picks"]["beats"]["b0003"] = {"items": [], "status": "skip"}                    # a skip is a decision
    good("picks.every_beat_decided", o)
    good("picks.main_painting_chosen", O.picks_outputs())
    o = O.picks_outputs()
    o["picks"]["main_asset"] = None
    bad("picks.main_painting_chosen", o)
    good("picks.no_error_issues", O.picks_outputs())
    o = O.picks_outputs()
    o["issues"] = [{"level": "error", "code": "no_main", "message": "m"}]
    bad("picks.no_error_issues", o)
    good("picks.credited", O.picks_outputs())
    o = O.picks_outputs()
    o["picks"]["assets"]["P1"]["credit"] = {}
    assert bad("picks.credited", o)["value"] == ["P1"]
    assert len(good("picks.variety_at_least", O.picks_outputs(), k=4)["value"]) == 4
    bad("picks.variety_at_least", O.picks_outputs(), k=20)
    good("picks.no_flagged_picture", O.picks_outputs())
    o = O.picks_outputs()
    o["issues"] = [{"level": "warning", "code": "asset_flag", "asset": "P2", "message": "m"}]
    assert bad("picks.no_flagged_picture", o)["value"] == ["P2"]


def test_picks_only_scope_changed_and_changed_in_scope():
    before = O.picks_doc()
    after = copy.deepcopy(before)
    after["beats"]["b0004"] = {"items": [{"asset": "MAIN", "region": None}], "status": "picked"}
    o = {"before": before, "after": after}
    good("picks.only_scope_changed", o, beats=["b0004"])
    good("picks.changed_in_scope", o, beats=["b0004"])
    after["beats"]["b0001"]["status"] = "skip"
    assert bad("picks.only_scope_changed", o, beats=["b0004"])["value"]["outside"] == ["b0001"]
    after["beats"]["b0001"] = before["beats"]["b0001"]
    after["main_asset"] = "P0"
    assert bad("picks.only_scope_changed", o, beats=["b0004"])["value"]["main_unchanged"] is False
    bad("picks.changed_in_scope", {"before": before, "after": copy.deepcopy(before)}, beats=["b0004"])
    good("picks.only_scope_changed", {"before": before, "after": copy.deepcopy(before)}, beats=[])


# ------------------------------------------------------------------------------------------------------------------------------- the rest
def test_a_criterion_with_no_output_to_read_fails_and_says_why():
    r = criteria.evaluate({"id": "x", "kind": "outline.chapters_between", "min": 1, "max": 9}, {"outline": None})
    assert r["passed"] is False and r["value"] is None and "nothing to check" in r["detail"] and "outline" in r["detail"]
    r = criteria.evaluate({"id": "x", "kind": "outline.every_chapter_cites_a_source"}, {"outline": {"chapters": []}})
    assert r["passed"] is False and "brief" in r["detail"]


def test_a_criterion_that_cannot_read_the_output_fails_it_never_raises():
    r = criteria.evaluate({"id": "x", "kind": "outline.chapters_between", "min": 1, "max": 9}, {"outline": {"chapters": 5}})
    assert r["passed"] is False and "could not read" in r["detail"]


def test_every_kind_is_tested_here_and_documented():
    import re
    src = Path(__file__).read_text(encoding="utf-8")
    tested = set(re.findall(r'"((?:outline|narration|draft|edit|picks)\.[a-z_]+)"', src))
    assert tested >= set(criteria.REGISTRY), sorted(set(criteria.REGISTRY) - tested)
    for c in criteria.describe():
        assert c["doc"] and isinstance(c["needs"], list), c["kind"]


def test_the_specs_of_a_case_are_checked():
    assert criteria.check_spec({"id": "a", "kind": "outline.chapters_between", "min": 1, "max": 2}) == []
    assert any("unknown kind" in p for p in criteria.check_spec({"id": "a", "kind": "outline.nope"}))
    assert any("required" in p for p in criteria.check_spec({"id": "a", "kind": "outline.chapters_between", "min": 1}))
    assert any("not a parameter" in p for p in criteria.check_spec({"id": "a", "kind": "outline.chapters_between", "min": 1, "max": 2, "lunch": 1}))
    assert any("must be int" in p for p in criteria.check_spec({"id": "a", "kind": "outline.chapters_between", "min": "1", "max": 2}))
    assert any("`id`" in p for p in criteria.check_spec({"id": "A B", "kind": "outline.no_error_issues"}))
    assert criteria.check_spec("x") == ["a criterion must be an object"]
