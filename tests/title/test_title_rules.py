"""The limits and the refused phrases live in ONE place (`bti/title/rules.py`): the task template is rendered from them and the check reads them. Every phrase and number of the
module must be in the rendered task, the template keeps the coordinator's rules, and no placeholder is left."""
import re
from pathlib import Path

import pytest
from title_helpers import make_title_project

from bti.title import inputs as tinputs, rules as R, workspace as W

REPO = Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "skills" / "title" / "TASK.template.md"


class Limits:
    minutes, steps = 10, 40


@pytest.fixture()
def rendered(root):
    d = make_title_project(root)
    inp = tinputs.load(d)
    ws = W.build(inp, Limits, root=root.parent / "ws")
    return (ws.root / "TASK.md").read_text(encoding="utf-8"), ws.root


def test_no_placeholder_is_left_and_every_placeholder_of_the_template_is_known(rendered):
    text, _ = rendered
    assert "{{" not in text and "}}" not in text
    names = set(re.findall(r"\{\{[#/]?([A-Z_]+)\}\}", TEMPLATE.read_text(encoding="utf-8")))
    known = set(R.template_values()) | {"CHECK_CMD", "CHANNEL", "TITLE", "ARTIST", "YEAR", "N_LINES", "N_CHAPTERS", "MAX_STEPS", "MAX_MINUTES", "OWNER_NOTE"}
    assert names <= known, names - known


def test_every_refused_phrase_and_every_limit_of_the_module_is_in_the_task(rendered):
    text, _ = rendered
    for shown, _rx in R.VAGUE + R.BORROWED:
        assert '"%s"' % shown in text, shown
    assert "%d to %d characters is best" % (R.BEST_MIN, R.BEST_MAX) in text and "%d is the limit" % R.MAX_CHARS in text
    assert "%s words at most" % R.number_word(R.MAX_WORDS) in text
    assert "at least %s and at most %s" % (R.number_word(R.MIN_CANDIDATES), R.number_word(R.MAX_CANDIDATES)) in text
    assert "at least %s candidates, in at least %s different forms" % (R.number_word(R.WRITE_AT_LEAST), R.number_word(R.FORMS_AT_LEAST)) in text
    assert "scores under %d on `central`" % R.FIRST_CENTRAL_MIN in text
    for form in R.FORMS:
        assert "`%s`" % form in text
    assert R.SCHEMA in text


def test_the_template_is_the_coordinators_text_with_only_the_mechanical_changes():
    t = TEMPLATE.read_text(encoding="utf-8")
    # rules 1 to 9 and the two verdicts are there, word for word
    for needle in ("**Work only inside this folder**", "**Read the whole narration before you write a word.**", "**Every word is true to the narration.**",
                   "**Concrete words.**", "**It stands alone.**", "**It opens a gap and does not close it.**", "**No borrowed excitement.**", "**Short and plain.**",
                   "**The language of the narration.**", "Why: a title about something the video does not show is a lie to the viewer.",
                   "Nothing is taken from outside the narration.", "**Rejected: \"A Prayer or a Shop Sign?\"**", "**Accepted: \"The Saint Who Was Also an Advertisement\"**",
                   "not intriguing or interesting or capture the essence of the", "Be strict on rule 3", "Between equals, take the one whose promise the cold open starts to keep"):
        assert needle in t, needle
    # nothing a rule says was shortened: the coordinator's draft was 7,398 bytes and the template only adds to it
    assert len(t.encode("utf-8")) > 7398


def test_the_rendered_rules_read_like_the_drafts(rendered):
    text, _ = rendered
    assert ('("The Hidden Meaning", "More Than Meets the Eye", "A Closer Look", "The Story Behind ...", "... Explained", "The Truth About ..." are never titles here)' in text)
    assert ('No "shocking", "secret", "insane", "you won\'t believe", "nobody knows", "the first", "the only", "the most", unless the narration itself says exactly that' in text)
    assert "28 to 55 characters is best, 60 is the limit" in text and "nine words at most" in text


def test_the_owner_note_is_shown_only_when_there_is_one(root):
    d = make_title_project(root)
    plain = W.build(tinputs.load(d), Limits, root=root.parent / "ws1")
    noted = W.build(tinputs.load(d, "make it about the mirror, not the ring"), Limits, root=root.parent / "ws2")
    a = (plain.root / "TASK.md").read_text(encoding="utf-8")
    b = (noted.root / "TASK.md").read_text(encoding="utf-8")
    assert "The owner's request for this title" not in a
    assert "The owner's request for this title" in b and "make it about the mirror, not the ring" in b


def test_the_work_folder_holds_copies_of_the_inputs_and_the_check_command(rendered):
    text, ws = rendered
    for f in ("TASK.md", "inputs/narration.json", "inputs/outline.json", "inputs/painting.json", "inputs/context.json"):
        assert (ws / f).is_file(), f
    assert (ws / "out").is_dir() and not list((ws / "out").iterdir())
    assert (ws / ("check.cmd" if W.IS_WINDOWS else "check")).is_file()
    assert "run `%s` until it prints `0 error(s)`" % ("./check" if not W.IS_WINDOWS else ".\\check.cmd") in text
    assert "The Test Painting** by A. Painter, 1434" in text and "7 lines in 3 chapters" in text and "10 minutes" in text and "40 steps" in text


def test_the_channel_name_is_written_as_a_person_reads_it():
    assert tinputs.channel_name() == "Raking Light"


def test_the_numbers_a_person_may_type_are_the_agents_limits():
    assert R.PERSON_MAX_CHARS == R.MAX_CHARS == 60 and R.public()["max_chars"] == 60
    assert R.BEST_MAX_WORDS == 7 and R.public()["best_max_words"] == 7


def test_third_owner_verdict_and_plain_tone_guidance_are_in_rendered_prompt(rendered):
    text, _ = rendered
    assert "Did This Forbidden Banquet Almost Put Him on Trial?" in text
    assert "A Sacred Feast or a Public Scandal?" in text
    assert "A Prayer or a Shop Sign?" in text
    tpl = TEMPLATE.read_text(encoding="utf-8").lower()
    assert "arnolfini" not in tpl and "van eyck" not in tpl
    assert "BEST_MAX_WORDS" in R.template_values() and "BEST_MAX_WORDS_TEXT" in R.template_values()
    assert "%d words or fewer is best" % R.BEST_MAX_WORDS in text
