"""Reading windows of the labels that name parts of a picture."""
import pytest
from bti.engine.techniques import explain_over


def test_room_enough_keeps_spoken_times():
    assert explain_over.plan_label_times([{'text': 'One', 'at': 1}, {'text': 'Two', 'at': 2}], 0, 6, .3, .5) == [1, 2]


def test_late_last_label_moves_just_enough():
    assert explain_over.plan_label_times([{'text': 'One', 'at': 1}, {'text': 'Two', 'at': 4}], 0, 5, .3, .5) == pytest.approx([1, 2.7])


def test_three_late_labels_keep_order_and_spacing():
    assert explain_over.plan_label_times([{'text': 'A', 'at': 4}, {'text': 'B', 'at': 4.3}, {'text': 'C', 'at': 4.6}], 0, 5, .3, .5) == pytest.approx([2.2, 2.45, 2.7])


def test_arnolfini_saved_labels_remain_readable_without_new_draft():
    import json
    from pathlib import Path
    from bti.engine.timing import Timing
    root = Path(__file__).parent / 'fixtures' / 'pointfix'
    sb = json.loads((root/'storyboard.json').read_text(encoding='utf-8'))
    tm = Timing(json.loads((root/'timing.json').read_text(encoding='utf-8')))
    shot = next(s for s in sb['shots'] if s['id']=='s0078')
    ov=shot['overlays'][0]; start=tm.resolve(ov['start']); p=ov['params']
    labels=[dict(x, at={'_t':tm.resolve(x['at'])}) for x in p['labels']]
    got=[start+t for t in explain_over.plan_label_times(labels,start,ov['dur'],p['fade_s'],p['leave_s'])]
    assert got == pytest.approx([472.8701, 473.1201, 473.3701],abs=.001)


def test_required_reading_time_counts_words_and_caps_at_four_seconds():
    assert explain_over.min_read_seconds('one two three') == pytest.approx(1.5)
    assert explain_over.min_read_seconds('one two three four five') == pytest.approx(2.1)
    assert explain_over.min_read_seconds(' '.join(['word'] * 20)) == pytest.approx(4.0)
