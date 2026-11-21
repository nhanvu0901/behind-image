import pytest

from bti.script import prompting, store
from bti.script.brief import build_brief, save_options
from bti.script.prompting import PromptError, build_prompt, render_outline
from bti.script.parse import parse_outline
from script_helpers import make_narration, make_outline


def test_outline_prompt_demands_citations_and_conflicts(tproj):
    t = build_prompt("outline", tproj, notes="Focus on the mirror.")["text"]
    assert t.startswith("PHASE: outline")
    for must in ("[PAY-01]", "cite", "FLAG EVERY CONFLICT", "certainty", "established", "disputed", "OUTLINE", "TARGET WORDS",
                 "OWNER NOTES FOR THIS RUN", "Focus on the mirror.", "LEAD THE EYE", "THREE LAYERS", "competing reading",
                 "CONFLICTS BETWEEN SOURCES"):
        assert must.lower() in t.lower(), must
    assert "{{" not in t and "<!--" not in t
    assert "unreliable edition" not in t                                  # low trust text is withheld unless ticked


def test_low_trust_is_marked_in_the_prompt_when_ticked(tproj):
    save_options(tproj, {"include_low": ["grovier_nws"]})
    t = build_prompt("outline", tproj)["text"]
    assert "unreliable edition" in t and "LOW TRUST" in t


def test_every_prompt_that_speaks_of_low_trust_also_gives_the_restored_rule(tproj):
    """The prompts of the script step are outline.md and script.md; both speak of LOW TRUST sources, so both carry the RESTORED case.
    It keeps the substance of the note of the brief: a reading, never an established fact, no number, date or quotation without another source, a […] mark is
    never guessed; and it is spoken as a reading, never in the author's name (the old rule said "named once" and "say whose they are")."""
    from bti.script.brief import restored_note
    texts = {"outline": build_prompt("outline", tproj)["text"],
             "script": build_prompt("script", tproj, outline=make_outline(approved=True))["text"]}
    note = restored_note().lower()
    for name, t in texts.items():
        assert "{{" not in t and "<!--" not in t, name
        assert "Sources marked LOW TRUST" in t, name                                  # the rule for low sources is still there
        assert t.count("Sources marked RESTORED") == 1, name
        rule = t[t.index("Sources marked RESTORED"):].split("\n")[0].lower()           # the sentence(s) on that line
        assert "number, date or quotation" in rule and "never guess what a […] mark hides" in rule, name
        for word in ("established fact", "number", "date", "quotation", "another source", "[…]", "guess", "reading"):
            assert word in rule and word in note, (name, word)                       # the prompt and the brief's note say the same things
        assert "never in the author's name" in note and "named once" not in rule and "as the author's own" not in rule and "say whose" not in rule, name


OLD_RULES = ("name them by author", "say whose they are", "named once", "with the author named when it matters", "who says what", "name both",
             "with its owner and its weak point", "as the author's own", "none over 28", "within about 20 percent", "say \"{who} argues\"")


def test_the_old_rule_of_naming_the_authors_is_gone_from_every_prompt_file_and_note(tproj):
    """The cause of 95 author names in 2,060 words was in the prompts themselves: no wording of the old rule may be left in any of them."""
    from bti.script import brief as brief_mod
    texts = {f: (prompting.PROMPTS / f).read_text(encoding="utf-8") for f in ("outline.md", "script.md", "rules_voice.md", "rules_format.md")}
    texts["brief.py notes"] = brief_mod.RESTORED_NOTE + brief_mod.CARE_NOTE
    texts["built outline prompt"] = build_prompt("outline", tproj)["text"]
    texts["built script prompt"] = build_prompt("script", tproj, outline=make_outline(approved=True))["text"]
    for where, t in texts.items():
        for old in OLD_RULES:
            assert old.lower() not in t.lower(), (where, old)
    assert "Payne notes" not in texts["rules_voice.md"] and "Hodge points out" not in texts["rules_voice.md"]
    assert "says whose claim it is" not in brief_mod.CARE_NOTE and "whose claim" not in brief_mod.CARE_NOTE


def test_the_script_prompt_tells_a_narrator_not_a_reviewer(tproj):
    t = build_prompt("script", tproj, outline=make_outline(approved=True))["text"]
    for must in ("NEVER speak the name of an author of a source", "\"the books\"", "\"both books\"", "\"the sources\"", "\"that passage\"", "\"the book says\"",
                 "two readings of the same object, in your own voice", "one reading sees", "some historians think", "one historian argues", "it has been suggested",
                 "belongs to the story", "Panofsky in 1934", "Never speak a remark meant for the owner", "Leave the fact out of the narration instead",
                 "THE VIEWER HAS NEVER HEARD OF YOUR SOURCES", "not a review of books"):
        assert must in t, must
    assert "{{" not in t and "<!--" not in t
    assert "NOTE:" not in t.split("YOUR TASK")[0].split("THE APPROVED OUTLINE")[1]          # the narrator is not shown the notes to the owner


def test_the_voice_rules_keep_the_fact_table_attributions_out_of_the_spoken_text():
    v = (prompting.PROMPTS / "rules_voice.md").read_text(encoding="utf-8")
    assert "what is known" in v and "never as what a book says" in v and "told as a reading" in v
    assert "it has been read as ... and as ..." in v
    assert "Never quote a book about the painting" in v
    assert "at most six" not in v                                                      # no count that only fits one video; "a few times" is the prompt's own


def test_the_outline_prompt_keeps_exact_attributions_for_the_fact_table_and_keeps_remarks_out_of_them(tproj):
    t = build_prompt("outline", tproj)["text"]
    assert "the fact table keeps the exact attributions for the owner" in t
    assert "A conflict is never a remark to the owner or an instruction" in t and "a remark placed there gets spoken" in t
    assert "put it on a NOTE line" in t and "the narrator never sees them" in t and "do not build a fact on it" in t
    assert "never plan a chapter as a comparison of the books" in t
    assert "Each budget is a ceiling" in t
    fmt = (prompting.PROMPTS / "rules_format.md").read_text(encoding="utf-8")
    assert "NOTE: one sentence for the owner" in prompting._format_section("outline", None)
    assert "NOTE lines" in fmt and "note: one short sentence" in prompting._format_section("script", None)


def test_the_chapter_budget_is_a_ceiling_in_the_task_and_in_the_rules(tproj):
    t = build_prompt("script", tproj, outline=make_outline(approved=True), chapters=["c02"])["text"]
    assert "- c02 THE ROOM: at most 200 words (aim for 180 to 200)" in t and "about 200 words" not in t
    assert "Each chapter's budget is a CEILING: do not go over it" in t and "Aim for 90 to 100 percent of it" in t
    assert "comes to 400 words or fewer" in t


def test_one_sentence_limit_in_the_prompts_and_the_checks(tproj):
    from bti.script import stats, validate
    limit = str(stats.MAX_SENTENCE_WORDS)
    for t in (build_prompt("script", tproj, outline=make_outline(approved=True))["text"], build_prompt("outline", tproj)["text"]):
        assert "{{" not in t and f"none over {limit}" in t and "none over 28" not in t
    for f in ("outline.md", "script.md", "rules_voice.md", "rules_format.md"):
        raw = (prompting.PROMPTS / f).read_text(encoding="utf-8")
        assert "28" not in raw and "none over 25" not in raw                          # the number is said once, through the word MAX_SENTENCE_WORDS
    n = make_narration()
    n.chapters[0].beats[0].text = " ".join(["Word"] * (stats.MAX_SENTENCE_WORDS + 1)) + "."
    assert f"more than {limit}" in [i for i in validate.validate_narration(n, make_outline(approved=True)) if i["code"] == "long_sentence"][0]["message"]
def test_a_restored_source_reaches_the_prompt_with_its_note_and_its_text(tmp_path):
    from test_brief_trust import RESTORED_TEXT, project
    d, lib = project(tmp_path, [("grovier_nws", "restored", RESTORED_TEXT), ("hodge_aid", "low", "# Low\n\nThe lamp was lit, says this unreliable edition.\n")])
    from bti.script.brief import build_brief
    t = build_prompt("outline", d, brief=build_brief(d, library_root=lib))["text"]
    assert "[RESTORED: restored and reviewed rendering" in t and "=== SOURCE GRO: A New Way of Seeing (grovier_nws/001) [RESTORED] ===" in t
    assert "Bosch's triptych" in t and "[…]" in t and "NO FULLY TRUSTED SOURCE" in t
    assert "unreliable edition" not in t and "[LOW TRUST:" in t                       # the low text is withheld and its mark stays


def test_script_prompt_layout_rules_and_context(tproj):
    o = make_outline(approved=True)
    n = make_narration()
    p = build_prompt("script", tproj, outline=o, narration=n, chapters=["c02"])
    t = p["text"]
    assert t.startswith("PHASE: script") and p["user"] == t and p["system"]
    for must in ("FINAL SCRIPT", ">> facts:", "Chapters to write now: c02", "THE APPROVED OUTLINE", "spoken words only",
                 "THE CHAPTERS ALREADY WRITTEN", "## c01 COLD OPEN", "## c03 CLOSING", "SPOKEN TEXT RULES"):
        assert must in t, must
    assert "## c02 THE ROOM\nword" not in t.split("YOUR TASK")[0].split("THE CHAPTERS ALREADY WRITTEN")[1]    # c02 is not given as context
    whole = build_prompt("script", tproj, outline=o, narration=None)["text"]
    assert "Chapters to write now: c01, c02, c03" in whole and "THE CHAPTERS ALREADY WRITTEN" not in whole


def test_retry_message_is_appended(tproj):
    t = build_prompt("script", tproj, outline=make_outline(True), chapters=["c01"], retry_message="beat b1 has markup")["text"]
    assert t.rstrip().splitlines()[-2].startswith(prompting.RETRY_MARK) and "beat b1 has markup" in t


def test_errors(tproj):
    with pytest.raises(PromptError):
        build_prompt("script", tproj, outline=None)
    with pytest.raises(PromptError):
        build_prompt("script", tproj, outline=make_outline(), chapters=["c42"])
    with pytest.raises(PromptError):
        build_prompt("nope", tproj)


def test_rendered_outline_is_readable_by_the_parser():
    o = make_outline()
    o.hook_options = [store.Hook("h1", "Look at it."), store.Hook("h2", "Or this.")]
    o.hook_choice = "h2"
    r = parse_outline(render_outline(o))
    assert r.ok
    back = r.outline
    assert back.thesis == o.thesis and back.hook_choice == "h2" and [h.text for h in back.hook_options] == ["Look at it.", "Or this."]
    assert [(c.id, c.title, c.word_budget, c.role, c.card, c.facts) for c in back.chapters] == \
           [(c.id, c.title, c.word_budget, c.role, c.card, c.facts) for c in o.chapters]
    assert [(f.id, f.certainty, f.sources, f.claim, f.conflict) for f in back.facts] == \
           [(f.id, f.certainty, f.sources, f.claim, f.conflict) for f in o.facts]
    assert back.target_words == o.target_words


def test_templates_on_disk_have_all_sections():
    for name in ("outline.md", "script.md", "rules_voice.md", "rules_format.md"):
        assert (prompting.PROMPTS / name).is_file()
    assert prompting._format_section("outline", None).startswith("OUTPUT LAYOUT FOR THE OUTLINE")
    assert prompting._format_section("script", None).startswith("OUTPUT LAYOUT FOR THE NARRATION")


def test_real_project_prompt(real_project):
    t = build_prompt("outline", real_project)["text"]
    assert "[PAY-01]" in t and "D5 THE MIRROR" in t and len(t) > 10000


def test_sentence_length_targets_and_split_examples(tproj):
    o = make_outline(approved=True)
    p = build_prompt("script", tproj, outline=o, narration=None)
    t = p["text"]
    # Check target numbers: 8 to 18 words, none over the one limit (25), one idea per sentence
    assert "8 to 18" in t
    assert "none over 25" in t
    assert "one idea per sentence" in t.lower()
    # Check that examples of split sentences are present
    assert "split" in t.lower() or "splitting" in t.lower()

