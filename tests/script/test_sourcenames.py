"""The checks that keep a narration a narrator's: no author of a source book is named, nothing is said about "the books", and no remark meant for the
owner is spoken. The three real narrations of the first video made end to end with a real model (trimmed copies in fixtures/arnrun/: v1 named the authors
95 times and spoke a remark of the outline twice, v2 named them 64 times and said "the books", v3 is the accepted one) and small made-up lines for the
false hits."""
import json
from pathlib import Path

import pytest

from bti.script import sourcenames as sn, validate
from bti.script.store import Narration, Outline

FIX = Path(__file__).resolve().parent / "fixtures" / "arnrun"
NAMES = {"Payne": ["James"], "Hodge": ["Susie"], "Brooke-Hitching": ["Edward"], "Hagen": ["Rainer", "Rose-Marie"]}


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def beats(doc):
    return [(c["id"], b) for c in doc["chapters"] for b in c["beats"]]


# ------------------------------------------------------------------------------------------------------------------------- the author field of a book
def test_surnames_of_the_author_fields_of_the_library():
    assert sn.surnames("James Payne") == [("Payne", ["James"])]
    assert sn.surnames("Susie Hodge") == [("Hodge", ["Susie"])]
    assert sn.surnames("Edward Brooke-Hitching") == [("Brooke-Hitching", ["Edward"])]
    assert sn.surnames("Rose-Marie and Rainer Hagen") == [("Hagen", ["Rainer", "Rose-Marie"])]       # the single word is a given name, the surname is shared
    assert [s for s, _ in sn.surnames("Kelly Grovier")] == ["Grovier"] and [s for s, _ in sn.surnames("Jennifer Dasal")] == ["Dasal"]


def test_surnames_of_other_shapes():
    assert sn.surnames("Payne, James") == [("Payne", ["James"])]
    assert [s for s, _ in sn.surnames("James Payne, Susie Hodge")] == ["Payne", "Hodge"]
    assert [s for s, _ in sn.surnames("James Payne & Susie Hodge Jr.")] == ["Payne", "Hodge"]
    assert [s for s, _ in sn.surnames("Hagen")] == ["Hagen"]                          # a lone word is a surname when nobody else has a longer name
    assert sn.surnames("") == [] and sn.surnames(None) == [] and sn.surnames("Anonymous") == [] and sn.surnames("Li") == []


def test_the_names_come_from_every_source_of_the_brief_included_or_not():
    brief = load("brief.json")
    assert sn.author_names(brief) == {"Payne": ["James"], "Hodge": ["Susie"], "Brooke-Hitching": ["Edward"]}
    brief["sources"][2]["included"] = False
    assert set(sn.author_names(brief)) == {"Payne", "Hodge", "Brooke-Hitching"}
    assert sn.author_names(None) == {} and sn.author_names({"sources": [{"author": None}, "x"]}) == {}


# ------------------------------------------------------------------------------------------------------------------------- the three real narrations
@pytest.mark.parametrize("version,lines,mentions", [(1, 57, 95), (2, 47, 64), (3, 0, 0)])
def test_the_author_check_on_the_three_real_narrations(version, lines, mentions):
    names = sn.author_names(load("brief.json"))
    doc = load(f"narration_v{version}.json")
    flagged = [b["id"] for _, b in beats(doc) if sn.find_authors(b["text"], names)]
    assert len(flagged) == lines
    total = sum(len(sn._name_regex(s).findall(b["text"])) for _, b in beats(doc) for s in names)
    assert total == mentions                                  # the numbers the operator counted by hand: 95 and 64 (Payne 36, Hodge 17, Brooke-Hitching 11)


def test_the_accepted_narration_passes_both_checks_and_the_book_of_exodus_is_not_a_hit():
    names = sn.author_names(load("brief.json"))
    doc = load("narration_v3.json")
    assert all(not sn.find_authors(b["text"], names) and not sn.find_source_talk(b["text"]) for _, b in beats(doc))
    exodus = [b["text"] for _, b in beats(doc) if "Book of Exodus" in b["text"]]
    assert exodus and sn.find_source_talk(exodus[0]) == [] and sn.find_authors(exodus[0], names) == []


@pytest.mark.parametrize("version,lines", [(1, 8), (2, 7), (3, 0)])
def test_the_talk_check_on_the_three_real_narrations(version, lines):
    doc = load(f"narration_v{version}.json")
    assert len([b for _, b in beats(doc) if sn.find_source_talk(b["text"])]) == lines


def test_the_remark_of_the_outline_that_was_spoken_is_found():
    doc = load("narration_v1.json")
    spoken = {b["id"]: sn.find_source_talk(b["text"]) for _, b in beats(doc) if "may describe" in b["text"]}
    assert len(spoken) == 2
    for found in spoken.values():
        assert {k for k, _ in found} == {"passage", "doubt"} and any("different painting" in w or "another painting" in w for _, w in found)


def test_the_books_and_the_sources_of_the_second_narration():
    doc = load("narration_v2.json")
    words = sorted({w.lower() for _, b in beats(doc) for _, w in sn.find_source_talk(b["text"])})
    assert words == ["both books", "the books", "two of the books"]


def test_the_outline_of_the_first_video_has_exactly_one_remark_to_the_owner():
    o = load("outline.json")
    flagged = {f["id"]: sn.find_owner_address(f["claim"]) + sn.find_owner_address(f.get("conflict") or "") for f in o["facts"]}
    assert {k: v for k, v in flagged.items() if v} == {"f10": ["the owner should", "before it is used"]}


# ------------------------------------------------------------------------------------------------------------------------- made-up lines: hits
@pytest.mark.parametrize("line,found", [
    ("Hodge says she is his wife.", ["Hodge"]),
    ("Both Payne and Hodge agree.", ["Payne", "Hodge"]),          # the first word of the sentence is no given name
    ("Then Hodge says so.", ["Hodge"]),
    ("Yet Payne's reading is odd.", ["Payne"]),                   # a possessive is the author too
    ("As Susie Hodge writes, it is plain.", ["Hodge"]),           # the author's own given name does not save the hit
    ("Dr Hodge notes the fur.", ["Hodge"]),
    ("Dr. Payne thinks so.", ["Payne"]),                          # a title of a modern writer
    ("J. Payne agrees.", ["Payne"]),                              # an initial
    ("Brooke Hitching suggests a second wife.", ["Brooke-Hitching"]),
    ("Hitching's view is different.", ["Brooke-Hitching"]),       # the short form of a double surname
    ("Edward Brooke-Hitching reports it.", ["Brooke-Hitching"]),
    ("Rainer Hagen writes of it.", ["Hagen"]),
    ("The mirror, says Payne, is spotless.", ["Payne"]),
])
def test_an_author_is_named(line, found):
    assert sn.find_authors(line, NAMES) == found


# ------------------------------------------------------------------------------------------------------------------------- made-up lines: no hit
@pytest.mark.parametrize("line", [
    "Sir Thomas Hodge founded the guild.",                        # another person who shares the surname: another capitalised word before it
    "The sculptor John Payne carved the tomb.",
    "The Hagen family of Lucca traded silk.",                     # an article before the surname
    "William Hodges painted the harbour.",                        # a longer word
    "He was hitching a ride to Bruges.",                          # the lower-case word
    "the Book of Exodus tells of holy ground",
    "Some historians think it a wedding, others a memorial.",
    "Panofsky proposed in 1934 that it records a marriage.",      # a scholar who belongs to the story is not an author of a source
    "Jan van Eyck was here, 1434.",
])
def test_not_an_author(line):
    assert sn.find_authors(line, NAMES) == [] and sn.find_source_talk(line) == []


@pytest.mark.parametrize("line", [
    "The books on the table are closed.",                         # painted books
    "She keeps the books that her father left.",
    "The books and the globe tell us he was a scholar.",
    "He opens the book and reads aloud.",                         # a book that does not say anything
    "The window is the only source of light.",
    "There are two sources of light in the room.",
    "A source of income for the family was silk.",
    "The passage in Exodus about holy ground explains the shoes.",
    "The owner of the painting sold it in 1850.",
    "The earliest inventory calls him Hernoul le Fin.",
])
def test_not_talk_about_the_sources(line):
    assert sn.find_source_talk(line) == []


@pytest.mark.parametrize("line,kind", [
    ("Both books say probably not.", "books"),
    ("Two of the books call her pose the manner of the period.", "books"),
    ("Then the books stop, unsure whether she is Costanza.", "books"),
    ("The book argues that the mirror is a witness.", "books"),
    ("The authors agree on the date.", "books"),
    ("The sources agree she is not pregnant.", "sources"),
    ("All three sources read that as purity.", "sources"),
    ("This source says otherwise.", "sources"),
    ("That passage may describe a different painting.", "passage"),
    ("This paragraph opens with a self portrait.", "passage"),
    ("It may describe another painting entirely.", "doubt"),
    ("The translation is unreliable here.", "doubt"),
    ("Please check this before it is used.", "doubt"),
    ("The owner should check the date.", "owner"),
    ("TODO find a better line.", "owner"),
])
def test_talk_about_the_sources_and_remarks_to_the_owner(line, kind):
    assert kind in {k for k, _ in sn.find_source_talk(line)}


def test_a_remark_to_the_owner_in_a_fact():
    assert sn.find_owner_address("Payne says 1425, Hodge says 1426.") == []
    assert sn.find_owner_address("HOD-04 reports a frame inscription of 1433 but may describe another painting.") == []      # a fact about a source is a fact
    assert sn.find_owner_address("It may describe another painting, so the owner should check it before it is used.")
    assert sn.find_owner_address("Check this against the museum record.") and sn.find_owner_address("Ignore HOD-04.")
    assert sn.find_owner_address("The date should be checked.") and sn.find_owner_address("TODO")
    assert sn.find_owner_address("") == [] and sn.find_owner_address(None) == []


# ------------------------------------------------------------------------------------------------------------------------- inside the narration's checks
def approved_outline():
    o = Outline.from_dict(load("outline.json"))
    o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "2026-11-19T00:00:00"}
    return o


def issues_of(version, brief):
    return validate.validate_narration(Narration.from_dict(load(f"narration_v{version}.json")), approved_outline(), brief=brief)


@pytest.mark.parametrize("version,authors,talk", [(1, 57, 8), (2, 47, 7), (3, 0, 0)])
def test_validate_narration_warns_per_line(version, authors, talk):
    iss = issues_of(version, load("brief.json"))
    a = [i for i in iss if i["code"] == "source_author_named"]
    t = [i for i in iss if i["code"] == "source_talk"]
    assert (len(a), len(t)) == (authors, talk)
    assert all(i["level"] == "warning" and i["chapter"] and i["beat"] and i["names"] for i in a)
    assert all(i["level"] == "warning" and i["chapter"] and i["beat"] and i["found"] for i in t)
    assert not validate.blocking(a + t)                          # a warning: it never blocks the approval by itself
    if version == 3:
        assert [i for i in iss if i["level"] in ("warning", "error")] == []            # the accepted narration has no warning at all


def test_without_a_brief_the_names_are_not_known_but_the_phrases_are_checked():
    iss = issues_of(2, None)
    assert not [i for i in iss if i["code"] == "source_author_named"] and len([i for i in iss if i["code"] == "source_talk"]) == 7


def test_validate_outline_flags_the_remark_in_the_fact_and_shows_the_notes():
    o = Outline.from_dict(load("outline.json"))
    iss = validate.validate_outline(o)
    f = [i for i in iss if i["code"] == "fact_for_owner"]
    assert [(i["fact"], i["level"]) for i in f] == [("f10", "warning")] and f[0]["found"] == ["the owner should", "before it is used"]
    assert not validate.blocking(f)
    assert not [i for i in iss if i["code"] == "outline_note"]
    o.notes = ["Paragraph HOD-04 seems to describe another painting."]
    n = [i for i in validate.validate_outline(o) if i["code"] == "outline_note"]
    assert len(n) == 1 and n[0]["level"] == "warning" and n[0]["message"] == "Note for the owner: Paragraph HOD-04 seems to describe another painting."
    assert "fact" not in n[0] and "chapter" not in n[0]
    assert not [i for i in validate.validate_outline(o) if i["code"] == "fact_for_owner" and i["fact"] != "f10"]      # a NOTE line is not a remark inside a fact


def test_the_sentence_limit_is_one_number_everywhere():
    from bti.script.stats import MAX_SENTENCE_WORDS
    assert MAX_SENTENCE_WORDS == 25
    n, o = Narration.from_dict(load("narration_v3.json")), approved_outline()
    b = n.chapters[0].beats[0]
    b.text = " ".join(["word"] * MAX_SENTENCE_WORDS) + "."
    assert not [i for i in validate.validate_narration(n, o) if i["code"] == "long_sentence"]
    b.text = " ".join(["word"] * (MAX_SENTENCE_WORDS + 1)) + "."                # the 26-word sentence that used to pass in silence
    long = [i for i in validate.validate_narration(n, o) if i["code"] == "long_sentence"]
    assert len(long) == 1 and f"{MAX_SENTENCE_WORDS + 1} words (more than {MAX_SENTENCE_WORDS})" in long[0]["message"]
    med = [i for i in validate.validate_narration(n, o) if i["code"] == "sentence_median"][0]
    assert f"none over {MAX_SENTENCE_WORDS}" in med["message"]
