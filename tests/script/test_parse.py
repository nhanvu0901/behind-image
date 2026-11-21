import pytest

from bti.script.parse import paragraph_listing, parse_outline, parse_script
from bti.script.prompting import render_outline
from bti.script.store import Fact, OChapter, Outline

OUT = Outline("t", [], None,
              [OChapter("c01", "cold_open", "COLD OPEN", False, "", 100, ["f01"]),
               OChapter("c02", "chapter", "THE MERCHANT CITY", True, "", 200, ["f02"]),
               OChapter("c03", "closing", "CLOSING", False, "", 100)],
              [Fact("f01", "x", ["PAY-01"], "established"), Fact("f02", "y", ["PAY-02"], "likely")], 400)

CLEAN = """FINAL SCRIPT

## c01 COLD OPEN
Look at the mirror on the back wall. It shows two people we cannot see.
>> facts: f01 | show: the convex mirror; the inscription above it

Then look at the lamp.
>> facts: f01, f02 | show: the chandelier

## c02 THE MERCHANT CITY
Bruges was a city of money.
>> facts: f02 | show: the whole painting

## c03 CLOSING
So what did we learn.
"""


def test_clean_script():
    r = parse_script(CLEAN, OUT, project="p")
    assert r.ok and r.error is None and [c.id for c in r.narration.chapters] == ["c01", "c02", "c03"]
    b = r.narration.chapters[0].beats
    assert [x.id for x in b] == ["b0001", "b0002"]
    assert b[0].facts == ["f01"] and b[0].show == ["the convex mirror", "the inscription above it"]
    assert b[1].facts == ["f01", "f02"]
    assert r.narration.chapters[2].beats[0].facts == [] and r.narration.chapters[2].beats[0].show == []   # metadata optional
    assert r.narration.chapters[1].card is True and r.narration.chapters[1].role == "chapter"          # from the outline
    assert r.issues == []


def test_text_after_last_final_script_and_messy_input():
    messy = """Sure! Here is my answer.

HOOK OPTIONS
1. Look at the mirror.
2. A wedding?
CHOSEN HOOK: 1

FINAL SCRIPT
(this is the template echo, ignored)

---

Some more chatter.

FINAL SCRIPT

```text
## c01: COLD OPEN
**Look** at the *mirror* on the wall.
(Word count: 9)
>> Facts: F01 | Show: the mirror

Second paragraph
continues on a second line.
>> facts: f09 | show: the hall

## [THE MERCHANT CITY]
Bruges was rich.

| Chapter | Words |
| c01 | 20 |

## c03 closing
The end of it.

WORD COUNT: 40
FACT TRACE
c01 | f01
```

## c01 COLD OPEN
Never reached because the audit tail ended the script.
"""
    r = parse_script(messy, OUT)             # the audit tail ends the script: the last block never counts
    assert r.ok and not any("Never reached" in b.text for c in r.narration.chapters for b in c.beats)
    # unknown fact ids are reported, kept, and do not abort
    r2 = parse_script(messy.rsplit("FINAL SCRIPT", 1)[0] + "FINAL SCRIPT\n" + messy.split("FINAL SCRIPT")[2], OUT)
    assert r2.ok
    c2 = {x.id: x for x in r2.narration.chapters}
    assert c2["c01"].beats[0].text == "Look at the mirror on the wall."
    assert c2["c01"].beats[0].facts == ["f01"] and c2["c01"].beats[0].show == ["the mirror"]     # case-insensitive keys
    assert c2["c01"].beats[1].text == "Second paragraph continues on a second line."
    assert any(i["code"] == "unknown_fact" and "f09" in i["message"] for i in r2.issues)
    assert c2["c01"].beats[1].facts == ["f09"]
    assert c2["c02"].beats[0].text == "Bruges was rich."                                        # [TITLE] matched by title
    assert c2["c03"].title == "CLOSING" and c2["c03"].beats[0].text == "The end of it."          # id match, title from the outline
    assert all("WORD COUNT" not in b.text and "|" not in b.text for ch in c2.values() for b in ch.beats)
    assert any("Word count" in d or "WORD COUNT" in d for d in r2.dropped)


def test_hook_list_before_first_chapter_is_dropped_without_a_final_marker():
    t = "HOOK OPTIONS\n1. a\n2. b\n3. c\n\nThis is chatter before the script.\n\n## c01 COLD OPEN\nReal.\n\n## c02 THE MERCHANT CITY\nReal two.\n\n## c03 CLOSING\nEnd."
    r = parse_script(t, OUT)
    assert r.ok and [c.beats[0].text for c in r.narration.chapters] == ["Real.", "Real two.", "End."]
    assert any(i["code"] == "preamble_dropped" for i in r.issues)


def test_missing_metadata_lines_and_orphan_meta():
    r = parse_script("## c01 COLD OPEN\n>> facts: f01\nOnly text.\n\n## c02 THE MERCHANT CITY\nB.\n\n## c03 CLOSING\nC.", OUT)
    assert r.ok and r.narration.chapters[0].beats[0].facts == []
    assert any(i["code"] == "meta_orphan" for i in r.issues)


def test_chapter_matched_by_position_with_a_warning():
    r = parse_script("## First\nA.\n\n## Second\nB.\n\n## Third\nC.", OUT)
    assert r.ok and [c.id for c in r.narration.chapters] == ["c01", "c02", "c03"]
    assert sum(i["code"] == "chapter_by_position" for i in r.issues) == 3


def test_chapter_that_cannot_be_placed_fails_with_paragraph_list():
    t = "## c01 COLD OPEN\nOne.\n\n## c07 SOMETHING ELSE\nThis chapter is nowhere in the outline and holds a few words.\n\n## c03 CLOSING\nEnd."
    r = parse_script(t, OUT)
    assert not r.ok and r.narration is None
    assert "c07 SOMETHING ELSE" in r.error and "Found 3 paragraph(s)" in r.error
    assert '  ## c07 SOMETHING ELSE\n  [2] 12 words: "This chapter is nowhere in the outline and holds a few words."' in r.error
    assert r.error.rstrip().endswith("Nothing was saved.")
    assert [p["n"] for p in r.paragraphs] == [1, 2, 3] and r.paragraphs[1]["heading"] == "c07 SOMETHING ELSE"


def test_no_chapter_lines_with_several_outline_chapters_fails_and_lists_paragraphs():
    long = " ".join(["word"] * 100)
    r = parse_script(f"Short one here.\n\n{long}\n\nThird.", OUT)
    assert not r.ok
    assert 'Found 3 paragraph(s)' in r.error and '[2] 100 words: "word word' in r.error and "…" in r.error
    assert r.paragraphs[1] == {"n": 2, "words": 100, "start": ("word " * 100).strip()[:70] + "…", "heading": None}
    assert "(before any chapter line)" in r.error


def test_no_chapter_lines_with_one_chapter_places_everything():
    one = Outline("t", [], None, [OChapter("c01", "chapter", "ALL", False, "", 100)], [], 100)
    r = parse_script("A para.\n\nAnother para.", one)
    assert r.ok and [b.text for b in r.narration.chapters[0].beats] == ["A para.", "Another para."]
    assert any(i["code"] == "no_chapter_lines" for i in r.issues)


def test_empty_and_commentary_only_texts_fail():
    assert not parse_script("   \n", OUT).ok
    r = parse_script("FINAL SCRIPT\n\nWORD COUNT: 20\n", OUT)
    assert not r.ok and "No narration paragraphs" in r.error


def test_headings_without_paragraphs_fail():
    r = parse_script("## c01 COLD OPEN\n\n## c02 THE MERCHANT CITY\n", OUT)
    assert not r.ok and "no narration paragraphs follow" in r.error


def test_without_outline_chapters_come_from_the_text():
    r = parse_script("## c01 COLD OPEN\nA.\n\n## Middle\nB.", None, counter_start=7)
    assert r.ok and [c.id for c in r.narration.chapters] == ["c01", "c02"]
    assert r.narration.chapters[0].role == "cold_open"
    assert r.narration.chapters[0].beats[0].id == "b0008"                      # ids continue from the counter


def test_paragraph_listing():
    assert paragraph_listing("a b c\n\n\nd") == [{"n": 1, "words": 3, "start": "a b c", "heading": None},
                                                   {"n": 2, "words": 1, "start": "d", "heading": None}]


# ------------------------------------------------------------------ outline
OUTLINE_TEXT = """Here is the outline you asked for.

OUTLINE

THESIS: What is the mirror really showing?

HOOKS
h1: Look at the mirror.
h2: A wedding?
3. Who signed above it?
HOOK CHOICE: h2

FACTS
f01 | established | PAY-01, HOD-05 | The painting is dated 1434.
f02 | disputed | PAY-02 | The couple are the Arnolfinis | conflict: Payne says Giovanni, Hodge says maybe not
f03 | PAY-09 | A fact with no certainty word.
f04 | likely | ZZZ-01 | Cites an unknown paragraph.

CHAPTERS
## c01 COLD OPEN
ROLE: cold_open
CARD: no
BUDGET: 190
PURPOSE: Open on a puzzle
the viewer can see.
FACTS: f01, f02, f09
SHOW: D2; the inscription above the mirror

## c02 THE ROOM
Budget: 1,800
FACTS: f03

## c03 CLOSING
CARD: yes

TARGET WORDS: 2000
"""


def test_outline_parse():
    r = parse_outline(OUTLINE_TEXT, {"PAY-01", "PAY-02", "PAY-09", "HOD-05"})
    assert r.ok
    o = r.outline
    assert o.thesis.startswith("What is the mirror") and o.target_words == 2000
    assert [(h.id, h.text) for h in o.hook_options] == [("h1", "Look at the mirror."), ("h2", "A wedding?"), ("h3", "Who signed above it?")]
    assert o.hook_choice == "h2"
    f = {x.id: x for x in o.facts}
    assert f["f01"].certainty == "established" and f["f01"].sources == ["PAY-01", "HOD-05"]
    assert f["f02"].certainty == "disputed" and f["f02"].conflict.startswith("Payne says")
    assert f["f03"].certainty == "likely" and f["f03"].sources == ["PAY-09"] and f["f03"].conflict is None
    c = {x.id: x for x in o.chapters}
    assert c["c01"].role == "cold_open" and c["c01"].word_budget == 190 and c["c01"].card is False
    assert c["c01"].purpose == "Open on a puzzle the viewer can see."
    assert c["c01"].facts == ["f01", "f02", "f09"] and c["c01"].show == ["D2", "the inscription above the mirror"]
    assert c["c02"].word_budget == 1800 and c["c03"].role == "closing" and c["c03"].card is True
    codes = {i["code"] for i in r.issues}
    assert {"unknown_fact", "unknown_source_id"} <= codes
    assert c["c03"].word_budget > 0 and "budget_defaulted" in codes


def test_outline_in_fences_and_marker_echo():
    t = "OUTLINE\n(echo)\n\nsome words\n\nOUTLINE\n```\nTHESIS: T\n\nCHAPTERS\n## c01 COLD OPEN\nBUDGET: 10\n```"
    r = parse_outline(t)
    assert r.ok and r.outline.thesis == "T" and r.outline.chapters[0].word_budget == 10


def test_outline_failure_lists_paragraphs():
    r = parse_outline("I cannot do this.\n\nSorry again, here are ideas about the painting and its history.")
    assert not r.ok and "Found 2 paragraph(s)" in r.error and "Nothing was saved" in r.error
    assert not parse_outline("").ok


# ------------------------------------------------------------------ remarks of the model to the owner (the NOTE lines of the outline)
NOTE_OUTLINE = """OUTLINE

THESIS: What is the mirror really showing?

HOOKS
h1: Look at the mirror.
HOOK CHOICE: h1

FACTS
f01 | established | PAY-01 | The painting is dated 1434.
f02 | disputed | PAY-02, HOD-04 | A frame inscription is dated 1433. | conflict: HOD-04 reports the inscription, but its paragraph opens "Believed to be a self-portrait" and may describe another painting.

CHAPTERS
## c01 COLD OPEN
ROLE: cold_open
CARD: no
BUDGET: 190
PURPOSE: Open on a puzzle the viewer can see.
NOTE: Paragraph HOD-04 seems to describe another painting, so no fact is built on its inscription.
FACTS: f01, f02
SHOW: D2

## c02 CLOSING
ROLE: closing
BUDGET: 150
PURPOSE: Close.
FACTS: f01
SHOW: the whole painting

- Note: The restored source is used as one reading only.
OWNER NOTE: A third remark, with a colon: inside.
TARGET WORDS: 340
"""


def test_note_lines_are_kept_apart_from_facts_and_purposes():
    r = parse_outline(NOTE_OUTLINE)
    assert r.ok
    o = r.outline
    assert o.notes == ["Paragraph HOD-04 seems to describe another painting, so no fact is built on its inscription.",
                       "The restored source is used as one reading only.", "A third remark, with a colon: inside."]
    assert o.chapters[0].purpose == "Open on a puzzle the viewer can see."          # a NOTE line ends the purpose, it never joins it
    assert o.chapters[0].facts == ["f01", "f02"] and o.chapters[0].show == ["D2"] and o.target_words == 340
    assert all("NOTE" not in f.claim and "NOTE" not in (f.conflict or "") for f in o.facts)
    assert o.to_dict()["notes"] == o.notes and Outline.from_dict(o.to_dict()).notes == o.notes


def test_notes_are_not_in_the_text_the_narrator_is_given_and_do_not_come_back_as_facts():
    o = parse_outline(NOTE_OUTLINE).outline
    text = render_outline(o)
    assert "NOTE" not in text and "HOD-04 seems to describe" not in text
    back = parse_outline(text).outline
    assert back.notes == [] and [f.id for f in back.facts] == [f.id for f in o.facts]


def test_an_outline_without_notes_keeps_its_revision_and_its_approval():
    plain = parse_outline(OUTLINE_TEXT).outline
    assert "notes" not in plain.to_dict()                                   # absent, not []: the revision (and every approval of an existing outline) is unchanged
    with_notes = Outline.from_dict({**plain.to_dict(), "notes": ["x"]})
    assert with_notes.rev() != plain.rev()
    assert Outline.from_dict(plain.to_dict()).rev() == plain.rev()


def test_a_note_line_needs_text_and_at_most_five_are_kept():
    text = NOTE_OUTLINE.replace("TARGET WORDS: 340", "\n".join(f"NOTE: remark {i}" for i in range(8)) + "\nNOTE:\nTARGET WORDS: 340")
    o = parse_outline(text).outline
    assert len(o.notes) == 5 and o.notes[0].startswith("Paragraph") and "NOTE" not in " ".join(o.notes)
    long = parse_outline(NOTE_OUTLINE.replace("TARGET WORDS: 340", "NOTE: " + "x" * 2000 + "\nTARGET WORDS: 340")).outline
    assert max(len(n) for n in long.notes) == 600


def test_the_shape_check_of_a_document_with_notes():
    from bti.script.store import doc_problem
    d = parse_outline(NOTE_OUTLINE).outline.to_dict()
    assert doc_problem("outline", d) is None
    assert "notes must be a list" in doc_problem("outline", {**d, "notes": "a string"})
    assert "notes must be a list" in doc_problem("outline", {**d, "notes": [1, 2]})
    assert "at most 5" in doc_problem("outline", {**d, "notes": ["x"] * 6})
