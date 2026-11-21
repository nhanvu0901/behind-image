"""The program's check of the agent's file and of a title a person types: each refusal, each warning, and what passes."""
import json

import pytest
from title_helpers import LINES, beat_ids, broken, cand, good_choice, line_texts, make_title_project

from bti.title import check as C, helper, rules as R


@pytest.fixture()
def lines(root):
    return line_texts(make_title_project(root))


def check(doc, lines):
    return C.check_choice(doc, lines)


def errors_of(rep):
    return " | ".join(rep.errors)


def test_a_good_file_has_no_error_and_the_first_candidate_is_the_choice(lines):
    rep = check(good_choice(), lines)
    assert rep.ok and rep.errors == [] and rep.problems() is None
    assert [c["text"] for c in rep.value["candidates"]][0] == "The Saint Who Was Also an Advertisement"
    assert len(rep.value["candidates"]) == 6 and rep.value["candidates"][0]["lines"] == ["b0001", "b0002", "b0006"]
    assert rep.text().splitlines()[-1].startswith("0 error(s), ")


def test_the_one_warning_of_the_good_file_is_the_short_title(lines):
    rep = check(good_choice(), lines)
    assert len(rep.warnings) == 1 and "The Ring on the Scales" in rep.warnings[0] and "22 characters" in rep.warnings[0] and "28 to 55 is best" in rep.warnings[0]


def set_text(i, text):
    def f(d):
        d["candidates"][i]["text"] = text
    return f


@pytest.mark.parametrize("text, needle", [
    ("The Saint Who Was Also a Very Strange Advertisement That Sold Rings Daily", "characters: the limit is 60"),
    ("The Saint Who Was Also an Ad", None),             # fine in length: control, no error expected
    ("A B C D E F G H I J", "10 words: at most 9"),
    ("The Hidden Meaning of the Saint", "rule 6"),
    ("A Closer Look at the Ring", "rule 6"),
    ("More Than Meets the Eye in This Shop", "rule 6"),
    ("The Story Behind the Scales", "rule 6"),
    ("The Ring Scales Explained", "rule 6"),
    ("The Truth About the Saint", "rule 6"),
    ("The Shocking Saint of the Shop", "rule 7"),
    ("The Secret of the Ring", "rule 7"),
    ("The Insane Saint and the Ring", "rule 7"),
    ("You Won't Believe This Saint", "rule 7"),
    ("You Won’t Believe This Saint", "rule 7"),
    ("Nobody Knows Why the Saint Weighs", "rule 7"),
    ("The First Saint of the Shop", "rule 7"),
    ("The Only Saint With a Ring", "rule 7"),
    ("The Most Famous Saint Weighs", "rule 7"),
    ("The Saint: A Ring Story", "colon"),
    ("The Saint — and the Ring", "colon"),
    ("The Saint - and the Ring", "colon"),
    ("The Saint | The Ring", "colon"),
    ("The Saint (and the Ring)", "brackets"),
    ("The Saint [and the Ring]", "brackets"),
    ("The Saint and the Ring \U0001F48D", "emoji"),
    ("The SAINT and the Ring", "capitals"),
    ("Why Is a Saint Weighing a Ring?? Why?", "question marks"),
    ("The Ring Cost 1449 Coins", "number 1449"),
])
def test_each_refusal_of_the_title_itself(lines, text, needle):
    rep = check(broken(set_text(1, text)), lines)
    if needle is None:
        assert rep.ok, errors_of(rep)
        return
    assert not rep.ok and needle in errors_of(rep), (text, rep.errors)
    assert "candidates[2]" in errors_of(rep) and rep.value is None and rep.problems()


def test_a_borrowed_word_passes_when_a_line_the_candidate_cites_says_it(lines, root):
    d = make_title_project(root, "pk2")
    from bti.script import store
    n = store.load_narration(d)
    n.chapters[0].beats[0].text = "The picture holds a secret, and it is the first of its kind: a saint weighing a ring on a pair of scales in a shop."
    store.save_narration(d, n)
    texts = line_texts(d)
    said = broken(lambda doc: doc["candidates"][1].update(text="The Secret of the Saint's Ring", lines=["b0001"]))
    assert check(said, texts).ok
    unsaid = broken(lambda doc: doc["candidates"][1].update(text="The Secret of the Saint's Ring", lines=["b0002"]))
    assert not check(unsaid, texts).ok and "rule 7" in errors_of(check(unsaid, texts))


def test_a_number_in_digits_must_be_in_a_cited_line(lines):
    ok = broken(lambda d: d["candidates"][1].update(text="Why a Saint Sold a Ring in 1449", lines=["b0002"]))
    assert check(ok, lines).ok
    bad = broken(lambda d: d["candidates"][1].update(text="Why a Saint Sold a Ring in 1450", lines=["b0002"]))
    assert "1450" in errors_of(check(bad, lines))


def test_unknown_or_missing_lines(lines):
    rep = check(broken(lambda d: d["candidates"][0].update(lines=["b0001", "b9999"])), lines)
    assert "b9999" in errors_of(rep) and "not a line of inputs/narration.json" in errors_of(rep)
    for bad in ([], "b0001", None, [3]):
        assert not check(broken(lambda d, b=bad: d["candidates"][0].update(lines=b)), lines).ok


@pytest.mark.parametrize("why", ["Two things that contradict and are both true to the painting.", "", "   ", 5, None])
def test_a_reason_must_be_vietnamese_and_present(lines, why):
    rep = check(broken(lambda d: d["candidates"][3].update(why=why)), lines)
    assert not rep.ok and "candidates[4].why" in errors_of(rep)


def test_a_long_reason_is_refused(lines):
    rep = check(broken(lambda d: d["candidates"][3].update(why="Rất dài. " * 40)), lines)
    assert "at most %d" % R.WHY_MAX_CHARS in errors_of(rep)


def test_the_number_of_candidates(lines):
    few = broken(lambda d: d.update(candidates=d["candidates"][:4]))
    assert "at least 5" in errors_of(check(few, lines))
    many = broken(lambda d: d.update(candidates=d["candidates"] + [cand("A Ring on the Scales Again Please", "other", ["b0001"])] * 3))
    assert "at most 8" in errors_of(check(many, lines))
    assert check(broken(lambda d: d.update(candidates=d["candidates"][:5])), lines).ok


def test_two_candidates_of_the_same_text_are_refused_whatever_the_punctuation_and_case(lines):
    rep = check(broken(lambda d: d["candidates"][4].update(text="the saint who was also an advertisement!")), lines)
    assert "same text as candidates[1]" in errors_of(rep)


def test_the_shape_of_the_file(lines):
    assert "JSON object" in errors_of(check([], lines))
    assert "schema must be" in errors_of(check(broken(lambda d: d.update(schema="x")), lines))
    assert "candidates must be a list" in errors_of(check({"schema": R.SCHEMA}, lines))
    assert "must be an object" in errors_of(check(broken(lambda d: d["candidates"].__setitem__(0, "A title")), lines))
    assert ".form must be one of" in errors_of(check(broken(lambda d: d["candidates"][0].update(form="slogan")), lines))
    assert ".text must be the title" in errors_of(check(broken(lambda d: d["candidates"][0].update(text=7)), lines))
    assert ".text must be one line" in errors_of(check(broken(lambda d: d["candidates"][0].update(text="Two\nLines")), lines))


@pytest.mark.parametrize("scores", [{"curiosity": 6, "concrete": 5, "central": 5, "clear": 4}, {"curiosity": 0, "concrete": 5, "central": 5, "clear": 4},
                                   {"curiosity": 5, "concrete": 5, "central": 5}, {"curiosity": 4.5, "concrete": 5, "central": 5, "clear": 4},
                                   {"curiosity": True, "concrete": 5, "central": 5, "clear": 4}, "5", None])
def test_scores_are_whole_numbers_from_one_to_five(lines, scores):
    rep = check(broken(lambda d: d["candidates"][2].update(scores=scores)), lines)
    assert not rep.ok and "candidates[3].scores" in errors_of(rep)


def test_the_warnings_that_do_not_stop_a_file(lines):
    quoted = check(broken(lambda d: d["candidates"][1].update(text='The "Prayer" of the Saint')), lines)
    assert quoted.ok and any("quotation marks" in w for w in quoted.warnings)
    lower = check(broken(lambda d: d["candidates"][1].update(text="why is a saint weighing a ring?")), lines)
    assert lower.ok and any("Title Case" in w for w in lower.warnings)
    low_central = check(broken(lambda d: d["candidates"][0].update(scores={"curiosity": 5, "concrete": 5, "central": 3, "clear": 5})), lines)
    assert low_central.ok and any("on `central`" in w for w in low_central.warnings)
    not_top = check(broken(lambda d: d["candidates"][0].update(scores={"curiosity": 3, "concrete": 4, "central": 4, "clear": 4})), lines)
    assert not_top.ok and any("highest total" in w for w in not_top.warnings)
    strangers = check(broken(lambda d: d["candidates"][2].update(text="Painted Goldfish Swimming Quietly", lines=["b0001"])), lines)
    assert strangers.ok and any("none of its words is in the lines it cites" in w for w in strangers.warnings)
    nine = check(broken(lambda d: d["candidates"][1].update(text="Why a Saint Weighs a Ring in a Shop?")), lines)
    assert nine.ok and any("9 words" in w and "7" in w for w in nine.warnings)                  # nine words passes limit with a soft >7 word warning
    seven = check(broken(lambda d: d["candidates"][1].update(text="Why a Saint Weighs a Shop Ring?")), lines)
    assert seven.ok and not any("words" in w for w in seven.warnings)                            # seven words: inside the best word count


def test_a_person_may_type_what_they_want_up_to_the_limit():
    assert C.check_text("  The Saint:   Who Was\tAlso (an) Advertisement ") == ("The Saint: Who Was Also (an) Advertisement", None)
    assert C.check_text("A" * 60)[1] is None and C.check_text("A" * 61) == ("", "title_too_long")
    assert C.check_text("The Secret of the Most Shocking Ring")[1] is None            # banned phrases are not looked for
    assert C.check_text("Two\nlines") == ("", "title_not_one_line") and C.check_text("Two\r\nlines")[1] == "title_not_one_line"
    for bad in ("", "   ", None, 5, ["x"]):
        assert C.check_text(bad) == ("", "title_invalid")


# ---------------------------------------------------------------------------------------------------------------- ./check
def test_the_helper_reads_the_work_folder_and_prints_the_report(root, capsys, monkeypatch):
    from bti.title import inputs as tinputs, workspace as W

    class L:
        minutes, steps = 10, 40
    d = make_title_project(root)
    ws = W.build(tinputs.load(d), L, root=root.parent / "ws")
    monkeypatch.chdir(ws.root)
    assert helper.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "ERROR out/title.json is missing" in out and out.rstrip().endswith("1 error(s), 0 warning(s)")
    (ws.root / "out" / "title.json").write_text(json.dumps(good_choice()), encoding="utf-8")
    assert helper.main(["check"]) == 0
    assert "0 error(s), 1 warning(s)" in capsys.readouterr().out
    (ws.root / "out" / "title.json").write_text("{ nope", encoding="utf-8")
    assert helper.main(["check"]) == 1 and "not valid JSON" in capsys.readouterr().out
    (ws.root / "inputs" / "context.json").unlink()
    with pytest.raises(SystemExit) as e:
        helper.run_check(ws.root)
    assert "not a title work folder" in str(e.value)


def test_the_narration_has_the_lines_the_tests_cite(root):
    d = make_title_project(root)
    assert beat_ids(d) == ["b0001", "b0002", "b0003", "b0004", "b0005", "b0006", "b0007"] and sum(len(t) for *_x, t in LINES) == 7
