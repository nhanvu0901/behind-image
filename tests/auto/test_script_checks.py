"""worker fixscript: where the new checks of the script step stand in the quality bar of an automatic run, and that no warning of the script step is left unsorted
(a warning that is in neither list of bti/auto_run/checks.py stops every run until somebody sorts it)."""
import ast
import re
from pathlib import Path

import pytest

from bti.auto_run import checks, reasons

REPO = Path(__file__).resolve().parents[2]
JS = REPO / "bti" / "editor" / "static" / "js"


def script_warning_codes():
    """{gate: {code}} of the warnings `validate_outline` and `validate_narration` can raise: the literal codes of their `issue("warning", "code", ...)` calls."""
    tree = ast.parse((REPO / "bti" / "script" / "validate.py").read_text(encoding="utf-8"))
    out = {"outline": set(), "narration": set()}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name in ("validate_outline", "validate_narration"):
            gate = "outline" if fn.name == "validate_outline" else "narration"
            for n in ast.walk(fn):
                if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "issue" and len(n.args) >= 2 and isinstance(n.args[0], ast.Constant)
                        and n.args[0].value == "warning" and isinstance(n.args[1], ast.Constant)):
                    out[gate].add(n.args[1].value)
    return out


def test_every_warning_of_the_outline_and_the_narration_is_sorted_into_one_of_the_two_lists():
    found = script_warning_codes()
    assert {"fact_no_source", "fact_for_owner", "outline_note"} <= found["outline"]
    assert {"words_off_target", "source_author_named", "source_talk", "attribution_phrase", "long_sentence"} <= found["narration"]
    for gate, codes in found.items():
        sorted_codes = set(checks.STOPS[gate]) | set(checks.TOLERATED[gate])
        missing = sorted(c for c in codes if c not in sorted_codes)
        assert not missing, "a warning the %s check can give is in neither list of bti/auto_run/checks.py (it stops the run until it is sorted): %s" % (gate, missing)


def test_the_author_names_and_the_talk_about_the_sources_stop_the_run_because_the_voice_follows():
    for code in ("source_author_named", "source_talk"):
        assert code in checks.STOPS["narration"] and code not in checks.TOLERATED["narration"]
        why, why_vi = checks.STOPS["narration"][code]
        assert "voice" in why and reasons._is_vietnamese(why_vi)
    verdict = checks.vet("narration", [{"level": "warning", "code": "source_author_named", "message": "Beat b0002 in c01 names the author", "beat": "b0002"}])
    assert verdict[0] == "warning" and verdict[1][0]["code"] == "source_author_named" and verdict[1][0]["why_vi"].startswith("có dòng nêu tên tác giả")


def test_a_remark_for_the_owner_inside_a_fact_stops_before_the_outline_gate_and_the_models_own_note_does_not():
    assert "fact_for_owner" in checks.STOPS["outline"] and "outline_note" not in checks.STOPS["outline"]
    assert "outline_note" in checks.TOLERATED["outline"]
    stop = checks.vet("outline", [{"level": "warning", "code": "fact_for_owner", "message": "m", "fact": "f10"}])
    assert stop[0] == "warning" and stop[1][0]["fact"] == "f10"
    note = checks.vet("outline", [{"level": "warning", "code": "outline_note", "message": "Note for the owner: x"}, {"level": "info", "code": "length", "message": "m"}])
    assert note[0] == "ok" and checks.tally(note[2]) == {"outline_note": 1}              # the run goes on and its log keeps the note with its count


def test_the_length_warnings_keep_their_place():
    assert "words_off_target" in checks.STOPS["narration"] and "chapter_off_budget" in checks.TOLERATED["narration"] and "long_sentence" in checks.TOLERATED["narration"]


def test_the_new_codes_are_sorted_and_described_on_the_page():
    codes_7 = {
        "cold_open_missing_name",
        "cold_open_late_name",
        "cold_open_first_line_long",
        "cold_open_no_early_turn",
        "cold_open_no_closing_question",
        "cold_open_roadmap",
        "cold_open_word_count",
    }
    assert {"cold_open_missing_name", "cold_open_no_closing_question", "cold_open_roadmap"} <= set(checks.STOPS["narration"])
    assert {"cold_open_late_name", "cold_open_first_line_long", "cold_open_no_early_turn", "cold_open_word_count"} <= set(checks.TOLERATED["narration"])
    js = (JS / "errmsg.js").read_text(encoding="utf-8")
    labels = (JS / "labels.js").read_text(encoding="utf-8")
    for code in codes_7:
        assert re.search(r"\b%s:" % code, js), code
        assert re.search(r"\b%s:" % code, labels), code
    assert "worker introrules" in js and "worker introrules" in labels
    assert "Object.assign(BUILD, INTRORULES_ISSUES);" in js.splitlines() and "Object.assign(CODE, CODE_INTRORULES);" in labels.splitlines()
    assert "words_off_target" in checks.STOPS["narration"] and "chapter_off_budget" in checks.TOLERATED["narration"] and "long_sentence" in checks.TOLERATED["narration"]


def test_every_warning_of_the_script_step_has_a_sentence_for_the_page_and_the_new_ones_a_label():
    js = (JS / "errmsg.js").read_text(encoding="utf-8")
    labels = (JS / "labels.js").read_text(encoding="utf-8")
    for gate, codes in script_warning_codes().items():
        for code in codes:
            assert re.search(r"\b%s:" % code, js), "no Vietnamese sentence for %s in errmsg.js" % code
    for code in ("source_author_named", "source_talk", "fact_for_owner", "outline_note"):
        assert re.search(r"\b%s:" % code, labels), "no label for %s in labels.js" % code
    assert "worker fixscript" in js and "worker fixscript" in labels
    # each block is a complete statement of its own (other workers append their blocks after it, so it is not required to be the last line)
    assert "Object.assign(BUILD, FIXSCRIPT_ISSUES);" in js.splitlines() and "Object.assign(CODE, CODE_FIXSCRIPT);" in labels.splitlines()


def test_attribution_phrase_stops_the_run_and_has_page_labels():
    assert "attribution_phrase" in checks.STOPS["narration"] and "attribution_phrase" not in checks.TOLERATED["narration"]
    why, why_vi = checks.STOPS["narration"]["attribution_phrase"]
    assert "voice" in why and reasons._is_vietnamese(why_vi)
    verdict = checks.vet("narration", [{"level": "warning", "code": "attribution_phrase", "message": "Beat b0004 attributes", "beat": "b0004"}])
    assert verdict[0] == "warning" and verdict[1][0]["code"] == "attribution_phrase" and verdict[1][0]["why_vi"]
    js = (JS / "errmsg.js").read_text(encoding="utf-8")
    labels = (JS / "labels.js").read_text(encoding="utf-8")
    assert "worker voiceplain" in js and "worker voiceplain" in labels
    assert re.search(r"\battribution_phrase:", js) and re.search(r"\battribution_phrase:", labels)
    assert "Object.assign(BUILD, VOICEPLAIN_ISSUES);" in js.splitlines() and "Object.assign(CODE, CODE_VOICEPLAIN);" in labels.splitlines()


def test_saytwice_warnings_stop_automatic_narration_approval():
    for code in ('fact_said_too_often', 'return_same_words', 'sentence_repeated'):
        assert code in checks.STOPS['narration']
        verdict = checks.vet('narration', [{'level': 'warning', 'code': code, 'message': 'repeat'}])
        assert verdict[0] == 'warning' and verdict[1][0]['code'] == code
