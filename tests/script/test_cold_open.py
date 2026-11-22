"""Cold-open rules and validation checks (`bti/script/cold_open.py`, `bti/script/validate.py`, `prompts/`)."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from bti.editor.script_api import make_router
from bti.script import cold_open, store, validate
from bti.script.store import Beat, Fact, NChapter, Narration, OChapter, Outline
from script_helpers import make_project

ARNOLFINI_BRIEF = {
    "painting": {
        "title": "The Arnolfini Portrait",
        "artist": "Jan van Eyck",
        "year": "1434",
        "meta": {},
    },
    "sources": [],
}

# Verbatim current Arnolfini cold open from .scratch/agy_tasks/introresearch/data/arnolfini_narration.md (chapter c01)
CURRENT_ARNOLFINI_C01 = [
    ("b0001", "Look at the back wall of this room, just above the round mirror. There, in ornate Latin script, a line of writing runs across the wall. In English it says, Jan van Eyck was here, 1434."),
    ("b0002", "So the painter tells us, in his own lettering, that he stood in this room in that year. But another date sits uneasily beside it."),
    ("b0003", "The woman most often named as the wife in green is Costanza Trenta, first wife of the merchant Giovanni Arnolfini. She died in 1433, a full year before the date on the wall."),
    ("b0004", "This small panel is crowded with detail, and repeated close looking has not settled what it means. So which is it, a wedding happening in front of us, or a memory of a woman already gone?"),
    ("b0005", "Let your eye drop from the lettering, past the mirror, to the two people standing in the room below."),
]

# Verbatim rewrite from docs/research/2026-11-21-openings-of-art-videos.md section 5
STUDY_REWRITE_C01 = [
    ("b0001", "Look at the ornate Latin writing on the back wall of this room, right above the round mirror."),
    ("b0002", "In The Arnolfini Portrait of 1434, Jan van Eyck wrote his own name across the wall in Latin. In English the line says, Jan van Eyck was here, 1434."),
    ("b0003", "So the painter tells us he stood in this room in that year. Yet another date sits uneasily beside it."),
    ("b0004", "The woman most often named as the wife in green is Costanza Trenta, first wife of the merchant Giovanni Arnolfini. She died in 1433, a full year before the date on the wall."),
    ("b0005", "Repeated close looking at this small panel has still not settled what it means. Is this a wedding happening before our eyes, or a memory of a woman already gone?"),
]


def _cold_doc(beats: list[tuple[str, str]], c01_role: str = "cold_open") -> tuple[Narration, Outline]:
    c1_words = max(100, sum(len(t.split()) for _, t in beats))
    o = Outline(
        "What does this panel actually record?",
        [],
        None,
        [
            OChapter("c01", c01_role, "COLD OPEN", False, "Hook the viewer.", c1_words, ["f01"]),
            OChapter("c02", "chapter", "THE ROOM", True, "Examine the figures.", 200, ["f01"]),
        ],
        [Fact("f01", "The inscription reads 1434.", ["PAY-01"], "established")],
        c1_words + 200,
    )
    o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "2026-11-21T00:00:00"}
    n = Narration("t", "The Arnolfini Portrait", "en")
    c1 = NChapter("c01", c01_role, "COLD OPEN", False, [Beat(bid, txt, ["f01"], ["the mirror"]) for bid, txt in beats])
    body = " ".join(["Detail sentence about the green gown."] * 33)
    c2 = NChapter("c02", "chapter", "THE ROOM", True, [Beat("b0010", body, ["f01"], ["the green dress"])])
    n.chapters = [c1, c2]
    return n, o


def _warn_codes(n: Narration, o: Outline, brief: dict | None = ARNOLFINI_BRIEF) -> list[str]:
    iss = validate.validate_narration(n, o, brief=brief)
    return sorted(i["code"] for i in iss if i["level"] == "warning" and i["code"].startswith("cold_open_"))


def test_real_texts_current_arnolfini_warns_and_study_rewrite_warns():
    n_bad, o_bad = _cold_doc(CURRENT_ARNOLFINI_C01)
    bad_codes = set(_warn_codes(n_bad, o_bad))
    assert {
        "cold_open_missing_name",
        "cold_open_first_sentence_names",
        "cold_open_no_closing_question",
        "cold_open_word_count",
    } <= bad_codes

    n_ok, o_ok = _cold_doc(STUDY_REWRITE_C01)
    assert {"cold_open_first_sentence_names", "cold_open_roadmap"} <= set(_warn_codes(n_ok, o_ok))


def test_missing_name_and_quotation_and_translated_inscription_filtering():
    # Painter named ONLY inside quotes or translated inscription still fails; sitter surname ("Arnolfini") alone is not title.
    beats = [
        ("b0001", "Look closely at the writing on the back wall."),
        ("b0002", 'In English it says, Jan van Eyck was here, 1434. Also someone wrote "Jan van Eyck". Costanza died a year earlier, but Giovanni Arnolfini commissioned the work.'),
        ("b0003", "Every object in the room waits to be inspected carefully. Look at the amber beads on the wall beside the round convex mirror right now. Is it a wedding?"),
    ]
    n, o = _cold_doc(beats)
    iss = [i for i in validate.validate_narration(n, o, brief=ARNOLFINI_BRIEF) if i["code"] == "cold_open_missing_name"]
    assert len(iss) == 1 and set(iss[0]["args"]["missing"]) == {"title", "artist"}


def test_late_name_warning_when_both_spoken_after_72_words():
    filler = " ".join(["Careful detail of the velvet sleeve here."] * 10)  # 70 words without title or painter
    beats = [
        ("b0001", "Look closely at the green sleeve near the mirror, yet hold your first assumption."),
        ("b0002", filler),
        ("b0003", "Only now do we reveal The Arnolfini Portrait by Jan van Eyck, painted in 1434. What does this double portrait mean?"),
    ]
    n, o = _cold_doc(beats)
    assert "cold_open_late_name" in _warn_codes(n, o) and "cold_open_missing_name" not in _warn_codes(n, o)


def test_first_line_length_boundary_25_vs_26_words():
    ok_first = " ".join(["Word"] * 24) + " end."  # 25 words
    bad_first = " ".join(["Word"] * 25) + " end."  # 26 words
    rest = [
        ("b0002", "In The Arnolfini Portrait of 1434, Jan van Eyck painted this puzzle, but no single detail settles why he dated the wall so late."),
        ("b0003", "Look at the shoes, the mirror, the single burning candle, and the quiet faces in front of us. Is this a wedding or a memorial?"),
    ]
    n_ok, o_ok = _cold_doc([("b0001", ok_first)] + rest)
    assert "cold_open_first_line_long" not in _warn_codes(n_ok, o_ok)
    n_bad, o_bad = _cold_doc([("b0001", bad_first)] + rest)
    assert "cold_open_first_line_long" in _warn_codes(n_bad, o_bad)


def test_early_turn_and_closing_question_checks():
    no_turn = [
        ("b0001", "Look closely at the round mirror hanging behind them."),
        ("b0002", "In The Arnolfini Portrait of 1434, Jan van Eyck placed a chandelier above the centre of this quiet Netherlandish interior room."),
        ("b0003", "Every texture on the panel draws our eye back to the inscriptions above the silvered glass. Is this a wedding or a memory?"),
    ]
    n1, o1 = _cold_doc(no_turn)
    assert "cold_open_no_early_turn" in _warn_codes(n1, o1) and "cold_open_no_closing_question" not in _warn_codes(n1, o1)

    no_q = [
        ("b0001", "Look closely at the mirror on the back wall."),
        ("b0002", "In The Arnolfini Portrait, Jan van Eyck wrote 1434, yet Costanza died in 1433 before the date."),
        ("b0003", "Every object around them sharpens the tension between the ledger entry and the Latin writing above the convex mirror on the back wall."),
    ]
    n2, o2 = _cold_doc(no_q)
    assert "cold_open_no_closing_question" in _warn_codes(n2, o2) and "cold_open_no_early_turn" not in _warn_codes(n2, o2)


def test_roadmap_phrase_check():
    beats = [
        ("b0001", "In this video, look at the round mirror."),
        ("b0002", "In The Arnolfini Portrait, Jan van Eyck painted two quiet figures, yet their dates collide across the room right in front of us."),
        ("b0003", "Notice how the light crosses the bedframe, the slippers, and the beads. Today we will explore every detail. What happened in 1434?"),
    ]
    n, o = _cold_doc(beats)
    iss = [i for i in validate.validate_narration(n, o, brief=ARNOLFINI_BRIEF) if i["code"] == "cold_open_roadmap"]
    assert len(iss) == 2 and iss[0]["beat"] == "b0001" and iss[1]["beat"] == "b0003"


def test_word_count_bounds_60_to_145():
    too_short = [
        ("b0001", "Look at The Arnolfini Portrait."),
        ("b0002", "Jan van Eyck signed 1434, yet Costanza died earlier. Why?"),
    ]
    n_short, o_short = _cold_doc(too_short)
    assert "cold_open_word_count" in _warn_codes(n_short, o_short)

    too_long = [
        ("b0001", "Look closely at the mirror on the back wall."),
        ("b0002", "In The Arnolfini Portrait, Jan van Eyck added writing above it, yet one date fails to match."),
        ("b0003", " ".join(["Every carved detail matters in this painted room now."] * 16) + " Is this a wedding?"),
    ]
    n_long, o_long = _cold_doc(too_long)
    assert "cold_open_word_count" in _warn_codes(n_long, o_long)


def test_no_cold_open_chapter_in_outline_skips_cold_open_checks():
    n, o = _cold_doc(CURRENT_ARNOLFINI_C01, c01_role="chapter")
    assert _warn_codes(n, o) == []


def test_painter_epithets_and_accents():
    brief = {"painting": {"title": "Girl with a Pearl Earring", "artist": "Hans Holbein the Younger", "year": ""}, "sources": []}
    assert cold_open.painter_surnames("Hans Holbein the Younger") == ["holbein"]
    assert cold_open.painter_spoken("Holbein's line cuts sharply across the oak panel.", "Hans Holbein the Younger")
    assert cold_open.title_spoken("In Girl with a Pearl Earring, light turns soft.", brief["painting"]["title"])


def test_narration_api_surfaces_cold_open_issues(tmp_path):
    d = make_project(tmp_path, "arn")
    o = Outline(
        "Thesis?",
        [],
        None,
        [OChapter("c01", "cold_open", "COLD OPEN", False, "p", 100, ["f01"]), OChapter("c02", "chapter", "BODY", True, "p", 100, ["f01"])],
        [Fact("f01", "Fact.", ["PAY-01"], "established")],
        200,
    )
    store.save_outline(d, o)
    store.approve(d, "outline", o.rev())

    app = FastAPI()
    app.include_router(make_router(tmp_path, library_root=tmp_path / "no_lib"))
    client = TestClient(app)

    bad_text = "## c01 COLD OPEN\nToday we will look at this big painting in detail.\n>> facts: f01 | show: mirror\n\n## c02 BODY\nBody words.\n>> facts: f01 | show: whole\n"
    r = client.post("/api/projects/arn/narration/import", json={"text": bad_text})
    assert r.status_code == 200
    codes = {i["code"] for i in client.get("/api/projects/arn/narration").json()["issues"]}
    assert {"cold_open_missing_name", "cold_open_roadmap", "cold_open_no_closing_question", "cold_open_word_count"} <= codes


def test_new_open_and_first_sentence_name_checks():
    text = ("This is the Arnolfini Portrait, painted by Jan van Eyck in 1434. "
            "The man is thought to be Giovanni Arnolfini, an Italian merchant in Bruges. "
            "The woman beside him is usually named as his wife, Costanza. But Costanza died in 1433. "
            "And above the mirror, Van Eyck wrote the date he was here: 1434. "
            "A mirror that shows two more people, a single candle burning, a pair of shoes left on the floor: every object here seems to carry a message. "
            "So is this a wedding, or a memory of a woman already gone?")
    n, o = _cold_doc([("b0001", text)])
    assert _warn_codes(n, o) == []
    n, o = _cold_doc([("b0001", '"The Arnolfini Portrait, by Jan van Eyck." It shows two people, but what is their story?')])
    assert "cold_open_first_sentence_names" in _warn_codes(n, o)


def test_stock_phrases_and_prompt_list_agree():
    voice = Path("prompts/rules_voice.md").read_text().lower()
    for phrase in cold_open.STOCK_PHRASES:
        assert phrase in voice
        assert cold_open.find_roadmap("This " + phrase.upper() + " is here.")


def test_first_sentence_can_span_beats():
    n, o = _cold_doc([("b0001", "This is the Arnolfini Portrait,"), ("b0002", "painted by Jan van Eyck in 1434. But what happened here?")])
    assert "cold_open_first_sentence_names" not in _warn_codes(n, o)
    assert "cold_open_first_line_long" not in _warn_codes(n, o)
