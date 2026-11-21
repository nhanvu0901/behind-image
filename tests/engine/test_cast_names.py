"""A cast entry is checked only during its own line, on its chosen picture."""
import json
from bti.engine import viewchecks as V
from test_pointfix_checks import context, ov


def setup_cast(tmp_path, overlay=None, where=None):
    c = context(tmp_path, overlay=overlay)
    c.tm.beats[0].update(text='Costanza Trenta appears', w0=0, w1=3)
    pk = json.loads((tmp_path / 'picks.json').read_text())
    pk['names'] = [{'name': 'Costanza Trenta', 'also': ['Costanza'], 'line': 'b1',
                    'where': where or {'region': 'THING'}, 'sure': False, 'words': 'appears'}]
    (tmp_path / 'picks.json').write_text(json.dumps(pk))
    return c


def test_missing_name_warns_and_matching_strip_clears_it(tmp_path):
    c = setup_cast(tmp_path)
    assert [(r['args']['name'], r['args']['shot']) for r in V._name_not_shown(c)] == [('Costanza Trenta', 's1')]
    c.shots[0]['overlays'] = [ov('X-ANN-01', text='COSTANZA TRENTA')]
    assert V._name_not_shown(c) == []


def test_absent_cast_is_silent(tmp_path):
    assert V._name_not_shown(context(tmp_path)) == []


def test_borrowed_picture_must_be_on_screen(tmp_path):
    c = setup_cast(tmp_path, overlay=ov('X-ANN-01', text='COSTANZA TRENTA'), where={'asset': 'B'})
    assert len(V._name_not_shown(c)) == 1
    c.shots[0]['slots']['image']['asset'] = 'B'
    assert V._name_not_shown(c) == []


def test_text_outside_line_does_not_count(tmp_path):
    c = setup_cast(tmp_path, overlay=ov('X-ANN-01', text='COSTANZA TRENTA'))
    c.shots[0]['overlays'][0]['start'] = {'t': 7}
    c.tm.beats[0]['end'] = 6
    assert len(V._name_not_shown(c)) == 1


def test_supplied_storyboard_first_presentations():
    from pathlib import Path
    from bti.engine.timing import Timing
    from bti.engine import registry
    folder = Path(__file__).parent / 'fixtures' / 'namefirst'
    sb = json.loads((folder / 'storyboard.json').read_text(encoding='utf-8'))
    tm = Timing.load(folder / 'timing.json')
    starts = [tm.resolve(s['start']) for s in sb['shots']]
    end = tm.resolve(sb['end'])
    c = V._Ctx(sb, tm, registry.load_bundle('gae'), folder, starts, end, lambda *_: None)
    issues = V._name_not_shown(c)
    assert {(x['args']['name'], x['args']['shot']) for x in issues} == {
        ('Costanza Trenta', 's0124'), ('Giovanni Arnolfini', 's0010'), ('Saint Martha', 's0112')}


def test_artist_name_in_borrowed_work_caption_counts(tmp_path):
    c = setup_cast(tmp_path, overlay=ov('X-ANN-02', title='A portrait', artist_year='Costanza Trenta, 1434'), where={'asset': 'B'})
    c.shots[0]['slots']['image']['asset'] = 'B'
    assert V._name_not_shown(c) == []
