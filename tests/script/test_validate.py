import pytest

from bti.script import validate
from bti.script.brief import build_brief
from bti.script.store import Beat
import functools

from script_helpers import make_narration as _mk, make_outline, words

make_narration = functools.partial(_mk, per_chapter=4)


def codes(issues, level=None):
    return sorted(i["code"] for i in issues if level is None or i["level"] == level)


def good():
    return make_narration((100, 200, 100)), make_outline(approved=True)


def test_a_clean_narration_has_no_errors_or_warnings():
    n, o = good()
    iss = validate.validate_narration(n, o)
    assert codes(iss, "error") == [] and codes(iss, "warning") == []
    assert "length" in codes(iss, "info")
    assert not validate.blocking(iss)


def test_error_chapter_missing():
    n, o = good()
    n.chapters.pop(1)
    iss = validate.validate_narration(n, o)
    assert "chapter_missing" in codes(iss, "error")
    n2, _ = good()
    n2.chapters[0].beats.clear()                                   # present but empty also counts as missing
    assert "chapter_missing" in codes(validate.validate_narration(n2, o), "error")


def test_error_empty_beat():
    n, o = good()
    n.chapters[0].beats[0].text = "   "
    iss = validate.validate_narration(n, o)
    assert "empty_beat" in codes(iss, "error")


@pytest.mark.parametrize("bad", ["[PAUSE] And so it begins.", "## c01 COLD OPEN", ">> facts: f01", "This is **bold** text.",
                                 "See PAY-07 for more.", "As f03 says.", "A <b>tag</b> inside.", "Wait (pause) for it.",
                                 "- a list marker", "Show: the mirror", "a | table", "`code`"])
def test_error_markup_in_text(bad):
    n, o = good()
    n.chapters[0].beats[0].text = "Good spoken words here. " + bad if not bad.startswith(("#", ">", "-")) else bad
    iss = validate.validate_narration(n, o)
    assert "markup_in_text" in codes(iss, "error"), bad


def test_plain_text_is_not_markup():
    for ok in ("In 1434, Jan van Eyck painted it, and he signed it.", "He said it cost 82 pounds.", "A well-known artist's style."):
        assert validate.markup_in(ok) is None


def test_error_words_under_70_percent_and_warning_off_target():
    o = make_outline(approved=True)                                 # target 400
    n = make_narration((60, 120, 60))                               # 240 words = 60%
    assert "words_under" in codes(validate.validate_narration(n, o), "error")
    n = make_narration((80, 160, 80))                               # 320 = 80%: no error, but off target
    iss = validate.validate_narration(n, o)
    assert "words_under" not in codes(iss, "error") and "words_off_target" in codes(iss, "warning")
    n = make_narration((100, 200, 100))
    assert "words_off_target" not in codes(validate.validate_narration(n, o))
    n = make_narration((140, 280, 140))                             # 560 = 140%
    assert "words_off_target" in codes(validate.validate_narration(n, o), "warning")


def test_error_stale_outline_approval():
    n, o = good()
    assert validate.outline_gate(o) is None
    o.thesis += " (edited after approval)"
    iss = validate.validate_narration(n, o)
    assert "outline_stale" in codes(iss, "error")
    o.approval = {"approved": False, "sha1": None, "approved_at": None}
    assert "outline_not_approved" in codes(validate.validate_narration(n, o), "error")
    assert "outline_missing" in codes(validate.validate_narration(n, None), "error")


def test_warning_chapter_off_budget():
    o = make_outline(approved=True)
    n = make_narration((100, 100, 100))                              # c02 budget 200, has 100 = 50%
    iss = validate.validate_narration(n, o)
    w = [i for i in iss if i["code"] == "chapter_off_budget"]
    assert [i["chapter"] for i in w] == ["c02"]
    n = make_narration((100, 240, 100))                              # +20% is inside +-30%
    assert "chapter_off_budget" not in codes(validate.validate_narration(n, o))


def test_warning_beat_over_90_words():
    n, o = good()
    n.chapters[1].beats[0].text = words(91)
    iss = validate.validate_narration(n, o)
    assert [i["beat"] for i in iss if i["code"] == "beat_too_long"] == [n.chapters[1].beats[0].id]
    n.chapters[1].beats[0].text = words(90)
    assert "beat_too_long" not in codes(validate.validate_narration(n, o))


def test_unknown_fact_and_no_show_are_warnings_unknown_chapter_is_an_error():
    n, o = good()
    n.chapters[0].beats[0].facts = ["f01", "f77"]
    n.chapters[0].beats[1].show = []
    n.chapters.append(type(n.chapters[0])("c09", "chapter", "EXTRA", False, [Beat("b0099", "x")]))
    iss = validate.validate_narration(n, o)
    assert {"unknown_fact", "no_show"} <= set(codes(iss, "warning"))
    assert "unknown_chapter" in codes(iss, "error")           # round 2 (R2B-001): a chapter the outline lacks blocks approval


def test_warning_spoken_chars_is_a_warning_only():
    n, o = good()
    n.chapters[0].beats[0].text = "Jan van Eyck (the painter) arrived; he stayed. " + words(20)
    iss = validate.validate_narration(n, o)
    assert "spoken_chars" in codes(iss, "warning") and "markup_in_text" not in codes(iss, "error")


def test_info_source_share_and_overlap(tproj):
    b = build_brief(tproj)
    n, o = good()
    o.facts[0].sources = ["PAY-01", "PAY-02"]
    n.chapters[0].beats[0].text = ("The mirror hangs on the back wall and shows two people who are not in front of us. " + "plus a little more of our own. ")
    iss = validate.validate_narration(n, o, brief=b)
    share = next(i for i in iss if i["code"] == "source_share")
    assert "PAY 2/3" in share["message"]
    ov = next(i for i in iss if i["code"] == "overlap")
    assert ov["level"] == "info"                                           # never a gate
    assert validate.source_overlap(n, b) > 0.04


def test_sentence_profile_is_information():
    n, o = good()
    for c in n.chapters:
        for b in c.beats:
            b.text = " ".join(["Word " * 40 + "end."] * 1)             # one 41-word sentence per beat
    iss = validate.validate_narration(n, o)
    prof = [i for i in iss if i["code"] == "sentence_profile"]
    assert prof and all(i["level"] == "info" for i in prof)


def test_outline_validation():
    o = make_outline()
    assert validate.blocking(validate.validate_outline(o)) == []
    o.thesis, o.chapters[0].title, o.chapters[1].word_budget = "", "", 0
    o.chapters.append(type(o.chapters[0])("c01", "chapter", "dup", False, "", 10))
    errs = codes(validate.validate_outline(o), "error")
    assert {"no_thesis", "chapter_no_title", "chapter_no_budget", "duplicate_chapter"} <= set(errs)
    assert "no_chapters" in codes(validate.validate_outline(type(o)()), "error")
    o2 = make_outline()
    o2.facts[1].conflict = None
    o2.facts[0].sources = []
    o2.chapters[0].facts = ["f01", "f42"]
    w = codes(validate.validate_outline(o2, {"paragraph_ids": ["PAY-01"]}), "warning")
    assert {"fact_no_source", "disputed_no_conflict", "unknown_fact"} <= set(w)
