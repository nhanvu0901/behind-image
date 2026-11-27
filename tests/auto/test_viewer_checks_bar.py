"""Worker fixdraft: where the viewer checks of the storyboard (bti/engine/viewchecks.py) stand in the quality bar of an automatic run."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from bti.auto_run import checks                       # noqa: E402
from bti.engine import storyboard as SB               # noqa: E402
from bti.engine import viewchecks as VC               # noqa: E402

VI = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)
CATALOGUE = {"device_wrong_kind", "device_too_little", "figure_on_wrong_picture", "outside_on_painting", "outside_picture_small"}       # worker catalogue: what the kinds of a line call for
STOPPING = {"upright_whole_share", "highlight_off_frame", "highlight_too_dark", "caption_placeholder", "caption_repeats", "text_not_in_narration",
            "asset_not_in_lines", "explainer_early"} | CATALOGUE | {"frame_off_painting", "small_detail_not_lit", "highlight_nothing_to_dim", "text_too_brief",
                                                                    "subject_not_on_screen", "borrowed_without_caption", "camera_off_region", "thing_arrives_late", "name_not_shown", "strip_without_light", "year_already_on_screen",
                                                                    "outside_picture_brief", "outside_picture_dropped"}            # panelbox + boxcam + namefirst + idfix + pictime + subjvis


def issue(code, **kw):
    return {"level": "warn", "code": code, "path": "shots[3]", "message": "English", "args": {}, **kw}


def test_every_viewer_code_is_sorted_into_one_of_the_two_lists_of_the_storyboard_gate():
    assert set(VC.CODES) == STOPPING | {"shot_short"}
    stops, ok = checks.STOPS["storyboard"], checks.TOLERATED["storyboard"]
    for code in VC.CODES:
        assert (code in stops) != (code in ok), "exactly one list: %s" % code
    assert set(stops) & set(VC.CODES) == STOPPING and ok & set(VC.CODES) == {"shot_short"}


def test_a_code_that_stops_says_why_in_english_and_in_vietnamese():
    for code in STOPPING:
        en, vi = checks.STOPS["storyboard"][code]
        assert len(en) > 40 and VI.search(vi) and not VI.search(en), code


def test_a_stopping_warning_stops_the_run_with_its_sentence_and_the_flicker_does_not():
    verdict, stopping, tolerated = checks.vet("storyboard", [issue("shot_short"), issue("upright_whole_share")])
    assert verdict == "warning" and [s["code"] for s in stopping] == ["upright_whole_share"] and stopping[0]["why_vi"] and [t["code"] for t in tolerated] == ["shot_short"]
    assert checks.vet("storyboard", [issue("shot_short")])[0] == "ok"
    for code in STOPPING:
        v, rows, _ = checks.vet("storyboard", [issue(code)])
        assert v == "warning" and rows[0]["code"] == code and rows[0]["why"], code


def test_the_codes_are_warnings_in_the_engines_list_so_the_sorting_test_of_the_run_finds_them():
    for code in VC.CODES:
        assert "(warning)" in SB.ISSUE_CODES[code], code


def test_model_viewer_findings_stop_storyboard_approval():
    from bti.draft.review import ISSUE_CODES
    for code in ISSUE_CODES.values():
        verdict, stopping, _ = checks.vet("storyboard", [issue(code)])
        assert verdict == "warning" and stopping[0]["code"] == code
        assert VI.search(stopping[0]["why_vi"])


def test_visual_scorecard_hard_lines_ignore_other_quality_targets():
    from bti.auto_run.checks import visual_scorecard
    metrics = [
        {"key": "marks_on_person", "value": 1, "items": [{"shot": "s1"}]},
        {"key": "biggest_mark", "over_30_count": 1, "items": [{"shot": "s2"}]},
        {"key": "short_shots", "value": 1, "items": [{"shot": "s3"}]},
        {"key": "borrowed_pictures", "value": {"under_3s_count": 1}, "items": [{"shot": "s4", "under_3s": True}]},
        {"key": "name_strips", "value": {"sub_repeats": 1, "on_thing": 0}, "items": [{"shot": "s5", "sub_repeats": True}]},
        {"key": "small_painting_share", "ok": False, "items": [{"shot": "s6"}]},
    ]
    hard, other = visual_scorecard({"metrics": metrics})
    assert {x["metric"] for x in hard} == {"marks_on_person", "biggest_mark", "short_shots", "borrowed_pictures", "name_strips"}
    assert all(x["code"] == "validation_failed" and VI.search(x["why_vi"]) for x in hard)
    assert any(x["code"] == "small_painting_share" for x in other)


def test_visual_scorecard_cannot_pass_when_hard_metrics_are_missing():
    hard, _ = checks.visual_scorecard({"metrics": []})
    assert hard and hard[0]["code"] == "validation_failed"
    assert VI.search(hard[0]["why_vi"])


def test_visual_scorecard_hard_count_without_details_still_stops():
    metrics = [
        {"key": "marks_on_person", "value": 1, "items": []},
        {"key": "biggest_mark", "over_30_count": 0, "items": []},
        {"key": "short_shots", "value": 0, "items": []},
        {"key": "borrowed_pictures", "value": {"under_3s_count": 0}, "items": []},
        {"key": "name_strips", "value": {"sub_repeats": 0}, "items": []},
    ]
    hard, _ = checks.visual_scorecard({"metrics": metrics})
    assert any(i["metric"] == "marks_on_person" for i in hard)
