from pathlib import Path

from bti.draft.techniques_md import generate
from bti.engine.registry import load_bundle

REPO = Path(__file__).resolve().parents[2]


def test_detail_pointer_guidance_reaches_the_draft():
    md = generate(load_bundle('gae'))
    assert 'EVERY time a detail sentence names a thing that is small on screen' in md
    assert 'never alone for a small thing' in md
    assert 'so close together that a pool of light would hold them all' in md
    for phrase in ('narrow or flat thing in a wide frame', 'a bench, a rug, a string of beads, a candle', 'under 20%'):
        assert phrase in md


def test_templates_carry_thin_thing_and_open_ended_dur_guidance():
    draft_tpl = (REPO / 'skills' / 'storyboard_draft' / 'TASK.template.md').read_text(encoding='utf-8')
    fast_tpl = (REPO / 'skills' / 'storyboard_edit' / 'FAST.template.md').read_text(encoding='utf-8')
    assert 'narrow or flat thing in a wide frame' in draft_tpl and 'a bench, a rug, a string of beads, a candle' in draft_tpl
    assert 'narrow or flat thing in a wide frame' in fast_tpl and 'a bench, a rug, a string of beads, a candle' in fast_tpl
    assert 'leave `dur` (and `end`) out' in fast_tpl and 'until the end of the shot' in fast_tpl
