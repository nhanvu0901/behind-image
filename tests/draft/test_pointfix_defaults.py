import pytest
from bti.draft import defaults


def test_highlight_default_runs_until_fade_at_shot_end():
    assert defaults.overlay_default_window('HI-01', 3, 0, 10, {'ramp_out': .5}, [], 4.5) == pytest.approx((3,9.5))


def test_late_highlight_starts_earlier():
    assert defaults.overlay_default_window('HI-01', 9, 0, 10, {'ramp_out': .5}, [], 4.5) == pytest.approx((7,9.5))


def test_short_shot_does_not_start_early():
    assert defaults.overlay_default_window('HI-01', 1, 0, 2, {'ramp_out': .5}, [], 4.5) == pytest.approx((0,1.5))


def test_text_default_starts_earlier_if_cut_short():
    assert defaults.overlay_default_window('X-ANN-01', 9, 0, 10, {'pop_in_s':.1,'fade_out_s':.2}, ['Green dress'], 3.2) == pytest.approx((8.2,10))


def test_key_default_ends_at_shot_end():
    assert defaults.overlay_default_window('KEY-01', 2, 0, 10, {}, [], 4) == pytest.approx((2,10))


def test_compiler_places_default_highlight_on_region_and_moves_start(proj):
    from bti.draft.inputs import load_inputs
    from bti.draft.compile import compile_specs
    from bti.engine.timing import Timing
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    specs = {k: clean_spec(v,k) for k,v in GOOD.items()}
    os = specs['c01']['shots'][1]['overlays'][0]
    os.pop('end_word', None)
    os['start_word'] = 19
    res = compile_specs(inp,specs,draw=False,identity=False)
    shot = next(s for s in res.storyboard['shots'] if s.get('technique') == 'CAM-05')
    o=shot['overlays'][0]
    tm=Timing(inp.timing)
    end=tm.resolve(res.storyboard['shots'][res.storyboard['shots'].index(shot)+1]['start'])
    assert o['params']['rx'] == 80 and o['params']['ry'] == 80
    assert o['params']['floor'] >= .6
    assert tm.resolve(o['start']) + o['dur'] == pytest.approx(end-o['params']['ramp_out'], abs=.002)
    assert o['dur'] >= 2.5
    assert tm.resolve(o['start']) < inp.timing['words'][19]['s']


def test_delayed_quote_starts_early_enough_to_be_read():
    p={'delay_s':1,'fade_in_s':.5,'fade_out_s':.5}
    assert defaults.overlay_default_window('STATIC-04', 9, 0, 10, p, ['A brief quotation'], 4) == pytest.approx((6.5,10))


def test_compiler_reports_when_shot_cannot_hold_a_default_highlight(proj):
    from bti.draft.inputs import load_inputs
    from bti.draft.compile import compile_specs
    from helpers import GOOD, clean_spec
    inp=load_inputs(proj)
    specs={k:clean_spec(v,k) for k,v in GOOD.items()}
    specs['c01']['shots'][1]['overlays'][0].pop('end_word', None)
    specs['c01']['shots'][2]['start_word']=13
    result=compile_specs(inp,specs,draw=False,identity=False)
    assert any(i['code']=='highlight_short_shot' for i in result.errors)
