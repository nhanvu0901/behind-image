import json
import pytest
from bti.engine import viewchecks as V
from bti.engine import registry as R
from bti.engine.timing import Timing
import bti.engine.api  # noqa


def context(tmp_path, kinds=True, overlay=None, zoom=1.0, region=None):
    asset={'width': 1920, 'height':1080, 'regions': {'THING': region or {'x':960,'y':540,'rx':80,'ry':80}}}
    shot={'id':'s1','start':{'t':0},'technique':'CAM-01','slots':{'image':{'asset':'A'}},'params':{'camera':[{'at':{'rel':0},'cx':960,'cy':540,'zoom':zoom}, {'at':{'rel':1},'cx':960,'cy':540,'zoom':zoom}]},'overlays': [overlay] if overlay else []}
    sb={'assets':{'A':asset},'shots':[shot]}
    beat={'id':'b1','start':0,'end':8,'w0':0,'w1':0}
    entry={'items':[{'asset':'A','region':'THING','role':'detail'}]}
    if kinds: entry['kinds']=['detail']
    (tmp_path/'picks.json').write_text(json.dumps({'main_asset':'A','beats':{'b1':entry}}))
    return V._Ctx(sb,Timing({'duration':8,'words':[],'beats':[beat]}),R.load_bundle('gae'),tmp_path,[0],8,lambda *_: None)


def ov(tech='HI-01', **params):
    return {'id':'o1','technique':tech,'start':{'t':0},'dur':3,'params':params}


def test_small_detail_asked_for_light(tmp_path):
    c=context(tmp_path)
    assert len(V._small_detail_not_lit(c)) == 1
    c.shots[0]['overlays']=[ov(at='THING',rx=80,ry=80)]
    assert V._small_detail_not_lit(c) == []


def test_no_kinds_is_not_judged(tmp_path):
    assert V._small_detail_not_lit(context(tmp_path, kinds=False)) == []


def test_too_large_spotlight_is_flagged(tmp_path):
    c=context(tmp_path, overlay=ov(at='THING',rx=800,ry=500))
    assert len(V._highlight_nothing_to_dim(c)) == 1
    c.shots[0]['overlays'][0]['params'].update(rx=80,ry=80)
    assert V._highlight_nothing_to_dim(c) == []


def test_short_key_label_is_reported(tmp_path):
    c=context(tmp_path,overlay=ov('KEY-01', labels=[{'text':'Green dress','ref':'THING','at':0}], fade_s=.3,leave_s=.5))
    c.shots[0]['overlays'][0]['dur']=1
    assert len(V._text_too_brief(c)) == 1
    c.shots[0]['overlays'][0]['dur']=3
    assert V._text_too_brief(c) == []


@pytest.mark.parametrize('tech,params', [
    ('HI-01', {'at':[960,540],'rx':40,'ry':40}),
    ('X-HI-01', {'at':'THING','rx':40,'ry':40}),
    ('AN-01', {'at':'THING'}),
    ('KEY-01', {'labels':[{'text':'detail','ref':'THING','at':0}]}),
])
def test_pointer_inside_region_is_accepted(tmp_path, tech, params):
    c=context(tmp_path, overlay=ov(tech,**params))
    assert V._small_detail_not_lit(c) == []


def test_large_or_offscreen_region_is_not_judged(tmp_path):
    assert V._small_detail_not_lit(context(tmp_path,region={'x':960,'y':540,'rx':450,'ry':300})) == []
    assert V._small_detail_not_lit(context(tmp_path,region={'x':50,'y':50,'rx':80,'ry':80})) == []


def test_late_strip_and_adequate_strip(tmp_path):
    c=context(tmp_path,overlay=ov('X-ANN-01',text='Green dress',pop_in_s=.1,fade_out_s=.2))
    c.shots[0]['overlays'][0]['dur']=1.7
    assert V._text_too_brief(c)[0]['args']['needed'] == 1.5
    c.shots[0]['overlays'][0]['dur']=2
    assert V._text_too_brief(c) == []


def test_warnings_stop_automatic_storyboard_gate():
    from bti.auto_run.checks import judge
    for code in ('small_detail_not_lit','highlight_nothing_to_dim','text_too_brief'):
        result=judge('storyboard',[{'code':code,'level':'warn','message':'example'}])
        assert len(result['stopping']) == 1


def test_region_covering_extra_area_does_not_point_inside_small_box(tmp_path):
    c=context(tmp_path, overlay=ov(at='LOOSE',rx=500,ry=500))
    c.assets['A']['regions']['LOOSE']={'x':960,'y':540,'rx':500,'ry':500}
    assert len(V._small_detail_not_lit(c)) == 1


def test_large_ellipse_clipped_at_edge_uses_visible_area(tmp_path):
    c=context(tmp_path,overlay=ov(at=[-700,540],rx=800,ry=500))
    assert V._highlight_nothing_to_dim(c) == []


def test_delayed_quote_counts_its_actual_fade_in(tmp_path):
    c=context(tmp_path,overlay=ov('STATIC-04',quote='A brief quotation',attribution='',delay_s=1,fade_in_s=.5,fade_out_s=.5))
    c.shots[0]['overlays'][0]['dur']=3
    assert V._text_too_brief(c)[0]['args']['seconds'] == 1.0
    c.shots[0]['overlays'][0]['dur']=4
    assert V._text_too_brief(c) == []


def test_staggered_map_labels_are_timed_individually(tmp_path):
    c=context(tmp_path,overlay=ov('AN-04',places=[[0,0],[1,1]],labels=['First','Second'],label_delay_s=.5,label_stagger_s=1,label_fade_s=.5,fade_s=.5))
    c.shots[0]['overlays'][0]['dur']=3
    rows=V._text_too_brief(c)
    assert [r['args']['text'] for r in rows] == ['Second']
    assert rows[0]['args']['seconds'] == .5


def test_region_must_stay_small_through_all_painting_shots_of_line(tmp_path):
    import copy
    c=context(tmp_path)
    second=copy.deepcopy(c.shots[0]); second['id']='s2'; second['start']={'t':4}
    for key in second['params']['camera']: key['zoom']=4
    c.shots.append(second); c.spans=[(0,4),(4,8)]; c.specs.append(c.bundle.spec('CAM-01'))
    assert V._small_detail_not_lit(c) == []
