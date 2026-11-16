"""Regression fixture: the earlier hand-made 13.7 minute script (8 blocks, [NAME] headers, one paragraph per line)."""
import pytest

from bti.script import ops, stats, validate
from bti.script.parse import parse_script
from bti.script.store import Narration
from legacy import LEGACY, legacy_blocks, legacy_to_layout, outline_for, read_legacy

pytestmark = pytest.mark.skipif(not LEGACY.is_file(), reason="demo_runs/claude_code/script.txt is missing")


@pytest.fixture()
def parsed():
    text, chapters = legacy_to_layout(read_legacy())
    o = outline_for(chapters)
    r = parse_script(text, o, project="legacy")
    assert r.ok, r.error
    return r.narration, o


def test_converter_finds_eight_blocks():
    blocks = legacy_blocks(read_legacy())
    assert len(blocks) == 8 and blocks[0][0] == "COLD OPEN" and blocks[-1][0] == "CLOSING"
    text, chapters = legacy_to_layout(read_legacy())
    assert text.startswith("FINAL SCRIPT") and text.count("\n## c") == 8 and len(chapters) == 8


def test_parse_script_gives_eight_chapters(parsed):
    n, _ = parsed
    assert [c.id for c in n.chapters] == [f"c0{i}" for i in range(1, 9)]
    assert n.chapters[0].role == "cold_open" and n.chapters[-1].role == "closing"
    assert sum(len(c.beats) for c in n.chapters) == sum(len(p) for _, p in legacy_blocks(read_legacy()))
    assert all(b.text and "[" not in b.text for c in n.chapters for b in c.beats)


def test_parse_without_an_outline_also_works():
    text, _ = legacy_to_layout(read_legacy())
    r = parse_script(text, None)
    assert r.ok and len(r.narration.chapters) == 8


def test_stats_match_the_known_figures(parsed):
    n, o = parsed
    st = stats.narration_stats(n, o)
    assert 1960 <= st["words"] <= 1985                        # about 1,970 words
    assert 13.5 <= st["minutes"] <= 13.8                      # about 13.7 minutes at 2.41 words per second
    assert st["beats"] == 49 and len(st["chapters"]) == 8
    assert st["sentence_profile"]["median"] in range(12, 23)


def test_no_blocking_errors_on_the_legacy_script(parsed):
    n, o = parsed
    o.approval = {"approved": True, "sha1": o.rev(), "approved_at": "x"}
    iss = validate.validate_narration(n, o)
    assert validate.blocking(iss) == []


def test_beat_operations_on_the_legacy_script(parsed):
    n, o = parsed
    total = stats.narration_stats(n, o)["words"]
    c = n.chapter("c06")
    first = c.beats[2]
    nwords = len(first.text.split())
    new = ops.split_beat(n, first.id, nwords // 2)
    assert [b.id for b in c.beats][2:4] == [first.id, new]
    ops.merge_with_previous(n, new)
    assert len(c.beats[2].text.split()) == nwords
    ops.drop_beat(n, c.beats[0].id)
    nb = ops.insert_beat(n, "c06", None, "A short inserted line, spoken as is.")
    ops.move_beat(n, nb, "c07", None)
    assert n.chapter("c07").beats[0].id == nb
    ids = [b.id for ch in n.chapters for b in ch.beats]
    assert len(ids) == len(set(ids))
    assert stats.narration_stats(n, o)["words"] != total
    again = Narration.from_dict(n.to_dict())
    assert again.rev() == n.rev()
