"""Tests for the four voice principles, the `attribution_phrase` narration warning,
the prompt cold-open examples, and zero painting-specific (Arnolfini) leakage."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bti.script import cold_open, prompting, sourcenames, validate
from bti.script.store import Beat, Fact, NChapter, Narration, OChapter, Outline
from script_helpers import words

REPO = Path(__file__).resolve().parents[2]


def _doc(beats: list[tuple[str, str]], title: str = "Hunters in the Snow", artist: str = "Pieter Bruegel the Elder") -> tuple[Narration, Outline, dict]:
    c1 = (
        f"This is {title}, painted by {artist} in 1565. "
        "Three hunters walk downhill on the left while skaters crowd the frozen ponds below. "
        "But jagged peaks rise behind a flat village where no mountains exist in Flanders. "
        "A broken inn sign hangs loose, crows watch from bare trees, and the hunters carry one lean fox. "
        "Is this a simple winter scene, or a quiet portrait of hard times?"
    )
    o = Outline(
        "What does this painting show?",
        [],
        None,
        [
            OChapter("c01", "cold_open", "COLD OPEN", False, "Orient then puzzle.", max(100, len(c1.split())), ["f01"]),
            OChapter("c02", "chapter", "THE VALLEY", True, "Examine the details.", 200, ["f01"]),
        ],
        [Fact("f01", "Painted in 1565.", ["PAY-01"], "established")],
        max(100, len(c1.split())) + 200,
    )
    o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "2026-11-22T00:00:00"}
    n = Narration("t", title, "en")
    n.chapters = [
        NChapter("c01", "cold_open", "COLD OPEN", False, [Beat("b0001", c1, ["f01"], ["the whole painting"])]),
        NChapter("c02", "chapter", "THE VALLEY", True, [Beat(bid, txt, ["f01"], ["the figures"]) for bid, txt in beats]),
    ]
    brief = {"painting": {"title": title, "artist": artist, "year": "1565", "meta": {}}, "sources": []}
    return n, o, brief


@pytest.mark.parametrize("phrase,sentence", [
    ("one reading", "One reading sees the peeled lemon as a warning about bitter pleasure."),
    ("another reading", "Another reading treats the silver plate as simple wealth."),
    ("a reading", "There is a reading that connects the broken string to discord."),
    ("has been read as", "The dark sky has been read as an approaching storm."),
    ("is read as", "The empty chair is read as an invitation to the viewer."),
    ("some see", "Some see political tension in the cold winter light."),
    ("others see", "Others see only an ordinary calendar picture of February."),
    ("historians", "Most historians accept that the canvas was painted in Antwerp."),
    ("scholars", "Later scholars dated the panel to the following spring."),
    ("critics", "Early critics praised the control of light across the snow."),
    ("has been described as", "The altarpiece has been described as a sermon in colour."),
    ("according to", "According to the earliest catalogue, the panel hung in Brussels."),
    ("it has been suggested", "It has been suggested that the commission came from a banker."),
    ("is thought to", "The patron is thought to have owned six seasonal panels."),
    ("is believed", "The chapel wing is believed to have opened only on feast days."),
])
def test_every_attribution_phrase_triggers_warning(phrase, sentence):
    found = sourcenames.find_attribution(sentence)
    assert found and found[0].lower() == phrase
    n, o, brief = _doc([("b0002", sentence + " " + words(180))])
    iss = [i for i in validate.validate_narration(n, o, brief=brief) if i["code"] == "attribution_phrase"]
    assert len(iss) == 1
    assert iss[0]["level"] == "warning"
    assert iss[0]["chapter"] == "c02" and iss[0]["beat"] == "b0002"
    assert iss[0]["found"]
    assert not validate.blocking(iss)


def test_multiple_phrases_count_each_line_once_and_narrator_voice_passes():
    bad_line = (
        "One reading sees a celebration, while historians and scholars argue it has been read as a warning "
        "and is believed to mark a loss."
    )
    bad_line_2 = "According to others see, critics think it is thought to be unfinished."
    n_bad, o_bad, brief = _doc([("b0002", bad_line), ("b0003", bad_line_2 + " " + words(140))])
    iss_bad = [i for i in validate.validate_narration(n_bad, o_bad, brief=brief) if i["code"] == "attribution_phrase"]
    assert [i["beat"] for i in iss_bad] == ["b0002", "b0003"]
    assert len(iss_bad[0]["found"]) == 3

    good_lines = [
        ("b0002", "It could be a celebration, or it could be a quiet warning about how fast pleasure fades."),
        ("b0003", "The patron was probably a wealthy merchant in Antwerp. If he hung the panels in his dining room, then guests saw the whole year on one wall."),
        ("b0004", "The books and the globe tell us he studied the heavens. A reading lamp sits beside the desk. " + words(130)),
    ]
    n_good, o_good, brief = _doc(good_lines)
    iss_good = [i for i in validate.validate_narration(n_good, o_good, brief=brief) if i["code"] == "attribution_phrase"]
    assert iss_good == []


def test_prompt_cold_open_examples_pass_all_cold_open_and_voice_checks():
    script_tpl = (prompting.PROMPTS / "script.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```\n## c01 COLD OPEN\n(.+?)\n```", script_tpl, re.S)
    assert len(blocks) == 2

    specs = [
        ("Hunters in the Snow", "Pieter Bruegel the Elder", "1565"),
        ("The Feast in the House of Levi", "Paolo Veronese", "1573"),
    ]
    for text, (title, artist, year) in zip(blocks, specs):
        w = len(text.split())
        o = Outline(
            "Thesis?",
            [],
            None,
            [
                OChapter("c01", "cold_open", "COLD OPEN", False, "Open.", max(100, w), ["f01"]),
                OChapter("c02", "chapter", "BODY", True, "Body.", 200, ["f01"]),
            ],
            [Fact("f01", "Supported fact.", ["PAY-01"], "established")],
            max(100, w) + 200,
        )
        o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "2026-11-22T00:00:00"}
        n = Narration("t", title, "en")
        n.chapters = [
            NChapter("c01", "cold_open", "COLD OPEN", False, [Beat("b0001", text.strip(), ["f01"], ["the whole painting"])]),
            NChapter("c02", "chapter", "BODY", True, [
                Beat(f"b000{k}", words(50), ["f01"], ["the details"]) for k in range(2, 6)
            ]),
        ]
        brief = {"painting": {"title": title, "artist": artist, "year": year, "meta": {}}, "sources": []}
        iss = validate.validate_narration(n, o, brief=brief)
        bad_codes = [
            i["code"] for i in iss
            if i["level"] in ("error", "warning")
            and (i["code"].startswith("cold_open_") or i["code"] in ("attribution_phrase", "spoken_chars", "long_sentence", "beat_too_long"))
        ]
        assert bad_codes == [], (title, iss)


def test_no_arnolfini_text_in_prompts_title_template_or_techniques_text():
    forbidden = re.compile(r"arnolfini|van\s*eyck|costanza|giovanni|1434|1433|panofsky|fuit hic|hernoul|trenta", re.I)
    for name in ("outline.md", "script.md", "rules_voice.md", "rules_format.md"):
        txt = (prompting.PROMPTS / name).read_text(encoding="utf-8")
        assert not forbidden.findall(txt), (name, forbidden.findall(txt))
    title_tpl = (REPO / "skills" / "title" / "TASK.template.md").read_text(encoding="utf-8")
    assert not forbidden.findall(title_tpl), forbidden.findall(title_tpl)

    reg = json.loads((REPO / "style" / "gae" / "techniques.json").read_text(encoding="utf-8"))
    for t in reg["techniques"]:
        for field in ("description", "usage_rule", "use_when", "needs", "never_when", "example"):
            val = t.get(field)
            if isinstance(val, str):
                assert not forbidden.findall(val), (t["id"], field, forbidden.findall(val))
        eng_notes = (t.get("engine") or {}).get("notes")
        if isinstance(eng_notes, str):
            assert not forbidden.findall(eng_notes), (t["id"], "engine.notes", forbidden.findall(eng_notes))
