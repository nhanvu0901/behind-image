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
    # Check target numbers: 8 to 18 words, none over 28, one idea per sentence
    assert "8 to 18" in t
    assert "28" in t
    assert "one idea per sentence" in t.lower()
    # Check that examples of split sentences are present
    assert "split" in t.lower() or "splitting" in t.lower()

