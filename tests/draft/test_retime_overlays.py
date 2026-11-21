"""A faster voice must fit overlays without lengthening the shots."""
import copy

import pytest

from bti.draft import retime as RT
from intro_helpers import brand03, compiled, intro_timing, make_project, style_doc


@pytest.mark.parametrize('offset,duration,expected', [(0.0, 100, 'shortened'), (0.4, 100, 'moved'), (0.0, 100, 'removed')])
def test_overlay_fits_shorter_shot(tmp_path, brand03, offset, duration, expected):
    timing = intro_timing()
    sb = compiled(make_project(tmp_path, timing)).storyboard
    shot = next(s for s in sb['shots'] if 'w' in s.get('start', {}))
    i = sb['shots'].index(shot)
    f = RT._Fit(sb, timing, style_doc())
    start = f.t0[i]
    length = 0.6 if expected == 'removed' else (1.1 if expected == 'moved' else 2.0)
    sb['shots'][i + 1]['start'] = {'t': start + length}
    shot['overlays'] = [{'id': 'test-overlay', 'technique': 'AN-03', 'start': {'t': start + offset}, 'dur': duration}]
    original = copy.deepcopy(sb)
    assert any(p['code'] == 'overlay_off_shot' for p in RT.off_voice(sb, timing, style_doc()))
    result, report = RT.retime(sb, timing, style_doc())
    assert sb == original
    assert report['overlays'][0]['what'] == expected
    assert not any(p['code'] == 'overlay_off_shot' for p in report['left'])
    again, rep2 = RT.retime(result, timing, style_doc())
    assert again == result and rep2['overlays'] == []


def test_faster_voice_makes_a_previously_fitting_overlay_overflow(tmp_path, brand03):
    slow = intro_timing(spacing=0.6)
    fast = intro_timing(spacing=0.4)
    sb = compiled(make_project(tmp_path, slow)).storyboard
    a, b = RT._Fit(sb, slow, style_doc()), RT._Fit(sb, fast, style_doc())
    i = next(i for i, shot in enumerate(sb['shots'])
             if 'w' in shot.get('start', {}) and a.t1[i] is not None and b.t1[i] is not None
             and a.t1[i] - a.t0[i] > b.t1[i] - b.t0[i] + 0.1 and b.t1[i] - b.t0[i] > 1.1)
    shot = sb['shots'][i]
    shot['overlays'] = [{'id': 'speed', 'technique': 'AN-03', 'start': copy.deepcopy(shot['start']),
                         'dur': a.t1[i] - a.t0[i] - 0.01}]
    assert not any(p['code'] == 'overlay_off_shot' and p['shot'] == shot['id'] for p in RT.off_voice(sb, slow, style_doc()))
    assert any(p['code'] == 'overlay_off_shot' and p['shot'] == shot['id'] for p in RT.off_voice(sb, fast, style_doc()))
    _, report = RT.retime(sb, fast, style_doc())
    assert any(o['shot'] == shot['id'] and o['what'] == 'shortened' for o in report['overlays'])


def test_explicit_end_anchor_is_fitted(tmp_path, brand03):
    timing = intro_timing()
    sb = compiled(make_project(tmp_path, timing)).storyboard
    f = RT._Fit(sb, timing, style_doc())
    i = next(i for i, s in enumerate(sb['shots']) if 'w' in s.get('start', {}) and f.t1[i] - f.t0[i] > 1.1)
    shot = sb['shots'][i]
    shot['overlays'] = [{'id': 'end-anchor', 'technique': 'AN-03', 'start': copy.deepcopy(shot['start']), 'end': {'t': f.t1[i] + 2}}]
    result, report = RT.retime(sb, timing, style_doc())
    assert any(o['overlay'] == 'end-anchor' and o['what'] == 'shortened' for o in report['overlays'])
    assert not any(p['code'] == 'overlay_off_shot' for p in RT.off_voice(result, timing, style_doc()))
