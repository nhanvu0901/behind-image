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
STOPPING = {"upright_whole_share", "highlight_off_frame", "highlight_too_dark", "caption_placeholder", "caption_repeats", "text_not_in_narration",
            "asset_not_in_lines", "explainer_early"}


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
