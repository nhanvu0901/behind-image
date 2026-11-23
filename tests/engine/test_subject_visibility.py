import json
from bti.engine import registry as R, storyboard as SB, viewchecks as VC
from bti.engine.timing import Timing


def test_person_introduction_rejects_hands_and_accepts_figure(tmp_path):
    words = 'Beside him a woman in green rests her hand in his She is usually named as his wife Costanza Trenta'.split()
    tm = Timing({'words': [{'w': w, 's': i, 'e': i + .8} for i, w in enumerate(words)],
                 'beats': [{'id': 'b1', 'start': 0, 'end': len(words), 'w0': 0, 'w1': len(words)}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'woman', 'kind': 'person', 'name': 'woman', 'strip': False, 'where': {'region': 'FIGURE'}}],
             'beats': {'b1': {'about': [{'id': 'woman', 'words': 'woman'}, {'id': 'woman', 'words': 'Costanza Trenta'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    asset = {'width': 2000, 'height': 1500, 'regions': {'FIGURE': {'x': 1200, 'y': 750, 'rx': 300, 'ry': 650},
                                                       'HANDS': {'x': 700, 'y': 900, 'rx': 100, 'ry': 100}}}
    def run(cx, cy, zoom):
        camera = [{'at': {'rel': n}, 'cx': cx, 'cy': cy, 'zoom': zoom} for n in (0, 1)]
        shot = {'id': 's1', 'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {'camera': camera}}
        c = VC._Ctx({'assets': {'A': asset}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], len(words), SB.safe_rel)
        return VC._subject_not_on_screen(c)
    assert len(run(700, 900, 4)) == 2
    assert run(1200, 750, .7) == []


def test_borrowed_portrait_must_be_the_named_asset_and_ideas_are_ignored(tmp_path):
    words = [{'w': 'painter', 's': 1, 'e': 1.8}, {'w': 'hope', 's': 2, 'e': 2.8}]
    timing = Timing({'words': words, 'beats': [{'id': 'b', 'start': 0, 'end': 4, 'w0': 0, 'w1': 2}]})
    picks = {'main_asset': 'A', 'subjects': [
        {'id': 'painter', 'kind': 'person', 'name': 'Painter', 'strip': True, 'where': {'asset': 'B'}},
        {'id': 'hope', 'kind': 'idea', 'name': 'hope', 'strip': False, 'where': None}],
        'beats': {'b': {'about': [{'id': 'painter', 'words': 'painter'}, {'id': 'hope', 'words': 'hope'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    def check(asset):
        shot = {'id': 's', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': asset}}, 'params': {}}
        c = VC._Ctx({'assets': {}, 'shots': [shot]}, timing, R.load_bundle('gae'), tmp_path, [0], 4, SB.safe_rel)
        return VC._subject_not_on_screen(c)
    assert [issue['args']['subject'] for issue in check('A')] == ['painter']
    assert check('B') == []


def test_crowded_scene_flags_small_person_beside_dominant_figure(tmp_path):
    words = [{'w': 'saint', 's': 1, 'e': 1.7}]
    timing = Timing({'words': words, 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [
        {'id': 'saint', 'kind': 'person', 'name': 'saint', 'strip': False, 'where': {'region': 'SMALL'}},
        {'id': 'figure', 'kind': 'person', 'name': 'figure', 'strip': False, 'where': {'region': 'LARGE'}}],
        'beats': {'b': {'about': [{'id': 'saint', 'words': 'saint'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    regs = {'SMALL': {'x': 300, 'y': 300, 'rx': 20, 'ry': 50}, 'LARGE': {'x': 500, 'y': 500, 'rx': 500, 'ry': 500}}
    shot = {'id': 's', 'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {
        'camera': [{'at': {'rel': n}, 'cx': 500, 'cy': 500, 'zoom': 1.92} for n in (0, 1)]}}
    c = VC._Ctx({'assets': {'A': {'width': 1000, 'height': 1000, 'regions': regs}}, 'shots': [shot]}, timing,
                R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c)] == ['saint']


def test_visibility_uses_the_words_of_the_current_line_without_word_indices(tmp_path):
    words = [{'w': 'village', 's': 1, 'e': 1.5}, {'w': 'village', 's': 5, 'e': 5.5}]
    tm = Timing({'words': words, 'beats': [{'id': 'b', 'start': 4, 'end': 7}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'village', 'kind': 'place', 'name': 'village', 'strip': False, 'where': {'asset': 'B'}}],
             'beats': {'b': {'about': [{'id': 'village', 'words': 'village'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shots = [{'id': 'first', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': 'B'}}, 'params': {}},
             {'id': 'second', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}]
    c = VC._Ctx({'assets': {}, 'shots': shots}, tm, R.load_bundle('gae'), tmp_path, [0, 4], 7, SB.safe_rel)
    assert [i['args']['shot'] for i in VC._subject_not_on_screen(c)] == ['second']


def test_static_whole_view_uses_default_camera(tmp_path):
    words = [{'w': 'village', 's': 1, 'e': 1.5}]
    tm = Timing({'words': words, 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'village', 'kind': 'place', 'name': 'village', 'strip': False, 'where': {'region': 'EDGE'}}],
             'beats': {'b': {'about': [{'id': 'village', 'words': 'village'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'STATIC-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    asset = {'width': 4000, 'height': 1000, 'regions': {'EDGE': {'x': 100, 'y': 500, 'rx': 50, 'ry': 50}}}
    c = VC._Ctx({'assets': {'A': asset}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c)] == ['village']


def test_named_painting_is_visible_in_a_closeup(tmp_path):
    tm = Timing({'words': [{'w': 'painting', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'painting', 'kind': 'work', 'name': 'painting', 'strip': False, 'where': {'asset': 'A'}}],
             'beats': {'b': {'about': [{'id': 'painting', 'words': 'painting'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {
        'camera': [{'at': {'rel': n}, 'cx': 500, 'cy': 500, 'zoom': 4} for n in (0, 1)]}}
    c = VC._Ctx({'assets': {'A': {'width': 1000, 'height': 1000}}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_text_is_not_mistaken_for_a_visible_subject(tmp_path):
    tm = Timing({'words': [{'w': 'scripture', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'text', 'kind': 'text', 'name': 'scripture', 'strip': True, 'where': {'asset': 'B'}}],
             'beats': {'b': {'about': [{'id': 'text', 'words': 'scripture'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    c = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_repeated_words_are_checked_at_each_spoken_occurrence(tmp_path):
    tm = Timing({'words': [{'w': 'painter', 's': 1, 'e': 2}, {'w': 'painter', 's': 5, 'e': 6}],
                 'beats': [{'id': 'b', 'start': 0, 'end': 7, 'w0': 0, 'w1': 2}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'painter', 'kind': 'person', 'name': 'Painter', 'strip': True, 'where': {'asset': 'B'}}],
             'beats': {'b': {'about': [{'id': 'painter', 'words': 'painter'}, {'id': 'painter', 'words': 'painter'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shots = [{'id': 'first', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': 'B'}}, 'params': {}},
             {'id': 'second', 'technique': 'X-LAY-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}]
    c = VC._Ctx({'assets': {}, 'shots': shots}, tm, R.load_bundle('gae'), tmp_path, [0, 4], 7, SB.safe_rel)
    assert [i['args']['shot'] for i in VC._subject_not_on_screen(c)] == ['second']


def test_named_painting_is_visible_when_cropped(tmp_path):
    tm = Timing({'words': [{'w': 'painting', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'painting', 'kind': 'work', 'name': 'painting', 'strip': False, 'where': {'asset': 'A'}}],
             'beats': {'b': {'about': [{'id': 'painting', 'words': 'painting'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {
        'camera': [{'at': {'rel': n}, 'cx': 500, 'cy': 500, 'zoom': 1.4} for n in (0, 1)]}}
    c = VC._Ctx({'assets': {'A': {'width': 1000, 'height': 1000}}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_subject_in_second_comparison_panel_is_on_screen(tmp_path):
    tm = Timing({'words': [{'w': 'portrait', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'portrait', 'kind': 'work', 'name': 'portrait', 'strip': True, 'where': {'asset': 'B'}}],
             'beats': {'b': {'about': [{'id': 'portrait', 'words': 'portrait'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'LAY-01', 'slots': {'left': {'asset': 'A'}, 'right': {'asset': 'B'}}, 'params': {}}
    c = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_subject_in_comparison_panel_is_absent_before_slide_in(tmp_path):
    tm = Timing({'words': [{'w': 'portrait', 's': .1, 'e': .5}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'portrait', 'kind': 'work', 'name': 'portrait', 'strip': True, 'where': {'asset': 'B'}}],
             'beats': {'b': {'about': [{'id': 'portrait', 'words': 'portrait'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'LAY-01', 'slots': {'left': {'asset': 'A'}, 'right': {'asset': 'B'}}, 'params': {}}
    c = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c)] == ['portrait']


def test_comparison_panel_camera_must_contain_named_region(tmp_path):
    tm = Timing({'words': [{'w': 'saint', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'saint', 'kind': 'person', 'name': 'saint', 'strip': False, 'where': {'region': 'SAINT'}}],
             'beats': {'b': {'about': [{'id': 'saint', 'words': 'saint'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    camera = [{'at': {'rel': n}, 'cx': 100, 'cy': 100, 'zoom': 4} for n in (0, 1)]
    shot = {'id': 's', 'technique': 'LAY-01', 'slots': {'left': {'asset': 'A'}, 'right': {'asset': 'B'}}, 'params': {'camera_left': camera}}
    asset = {'width': 1000, 'height': 1000, 'regions': {'SAINT': {'x': 800, 'y': 800, 'rx': 100, 'ry': 100}}}
    c = VC._Ctx({'assets': {'A': asset}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c)] == ['saint']


def test_region_in_unrevealed_part_of_sliding_panel_is_not_visible(tmp_path):
    tm = Timing({'words': [{'w': 'saint', 's': .5, 'e': 1}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'saint', 'kind': 'person', 'name': 'saint', 'strip': False, 'where': {'region': 'SAINT'}}],
             'beats': {'b': {'about': [{'id': 'saint', 'words': 'saint'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    camera = [{'at': {'rel': n}, 'cx': 500, 'cy': 500, 'zoom': .9} for n in (0, 1)]
    shot = {'id': 's', 'technique': 'LAY-01', 'slots': {'left': {'asset': 'B'}, 'right': {'asset': 'A'}}, 'params': {'camera_right': camera}}
    asset = {'width': 1000, 'height': 1000, 'regions': {'SAINT': {'x': 950, 'y': 500, 'rx': 40, 'ry': 100}}}
    c = VC._Ctx({'assets': {'A': asset}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c)] == ['saint']


def test_region_in_sliding_panel_is_visible_after_slide_completes(tmp_path):
    tm = Timing({'words': [{'w': 'saint', 's': 1.5, 'e': 2.0}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'saint', 'kind': 'person', 'name': 'saint', 'strip': False, 'where': {'region': 'SAINT'}}],
             'beats': {'b': {'about': [{'id': 'saint', 'words': 'saint'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    camera = [{'at': {'rel': n}, 'cx': 500, 'cy': 500, 'zoom': .9} for n in (0, 1)]
    shot = {'id': 's', 'technique': 'LAY-01', 'slots': {'left': {'asset': 'B'}, 'right': {'asset': 'A'}}, 'params': {'camera_right': camera}}
    asset = {'width': 1000, 'height': 1000, 'regions': {'SAINT': {'x': 950, 'y': 500, 'rx': 40, 'ry': 100}}}
    c = VC._Ctx({'assets': {'A': asset}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_xcmp_swap_panel_visibility_follows_swap_schedule(tmp_path):
    tm = Timing({'words': [{'w': 'first', 's': 1.0, 'e': 1.5}, {'w': 'second', 's': 3.5, 'e': 4.0}],
                 'beats': [{'id': 'b', 'start': 0, 'end': 5, 'w0': 0, 'w1': 2}]})
    subjects = [{'id': 's1', 'kind': 'work', 'name': 'first', 'strip': True, 'where': {'asset': 'S1'}},
                {'id': 's2', 'kind': 'work', 'name': 'second', 'strip': True, 'where': {'asset': 'S2'}}]
    shot = {'id': 's', 'technique': 'X-CMP-01',
            'slots': {'anchor': {'asset': 'A'}, 'swap_1': {'asset': 'S1'}, 'swap_2': {'asset': 'S2'}},
            'params': {'seconds_per_swap': 2.5, 'swap_transition': 'cut'}}
    (tmp_path / 'picks.json').write_text(json.dumps({'main_asset': 'A', 'subjects': subjects, 'beats': {
        'b': {'about': [{'id': 's1', 'words': 'first'}, {'id': 's2', 'words': 'second'}]}}}), encoding='utf-8')
    c_ok = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 5, SB.safe_rel)
    assert VC._subject_not_on_screen(c_ok) == []

    (tmp_path / 'picks.json').write_text(json.dumps({'main_asset': 'A', 'subjects': subjects, 'beats': {
        'b': {'about': [{'id': 's2', 'words': 'first'}, {'id': 's1', 'words': 'second'}]}}}), encoding='utf-8')
    c_bad = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 5, SB.safe_rel)
    assert [i['args']['subject'] for i in VC._subject_not_on_screen(c_bad)] == ['s2', 's1']


def test_lay04_inset_visibility_respects_delay(tmp_path):
    tm = Timing({'words': [{'w': 'clip', 's': .2, 'e': .5}, {'w': 'clip', 's': 2.0, 'e': 2.5}],
                 'beats': [{'id': 'b', 'start': 0, 'end': 4, 'w0': 0, 'w1': 2}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'clip', 'kind': 'thing', 'name': 'clip', 'strip': False, 'where': {'asset': 'V'}}],
             'beats': {'b': {'about': [{'id': 'clip', 'words': 'clip'}, {'id': 'clip', 'words': 'clip'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'LAY-04', 'slots': {'image': {'asset': 'A'}, 'inset': {'asset': 'V'}},
            'params': {'inset_delay_s': 1.0, 'inset_fade_s': 0.4}}
    c = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 4, SB.safe_rel)
    assert len(VC._subject_not_on_screen(c)) == 1


def test_closeup_inside_person_region_is_visible():
    asset = {'width': 2000, 'height': 2000, 'regions': {'PERSON': {'x': 1000, 'y': 1000, 'rx': 800, 'ry': 900}}}
    shot = {'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    subject = {'id': 's', 'kind': 'person', 'where': {'region': 'PERSON'}}
    assert VC.subject_visible_at(shot, (0, 4), 1, subject, main='A', assets={'A': asset}, subjects=[subject],
                                 bundle=R.load_bundle('gae'), keys_fn=lambda _: [(0, 1000, 500, 4, 'linear')]) is True


def test_person_other_named_face_region_is_visible():
    asset = {'width': 2000, 'height': 2000, 'regions': {
        'FIGURE': {'x': 500, 'y': 1200, 'rx': 200, 'ry': 600, 'thing': 'Ada figure'},
        'FACE': {'x': 1400, 'y': 500, 'rx': 100, 'ry': 100, 'thing': 'Ada face'}}}
    shot = {'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    subject = {'id': 's', 'kind': 'person', 'name': 'Ada', 'where': {'region': 'FIGURE'}}
    assert VC.subject_visible_at(shot, (0, 4), 1, subject, main='A', assets={'A': asset}, subjects=[subject],
                                 bundle=R.load_bundle('gae'), keys_fn=lambda _: [(0, 1400, 500, 3, 'linear')]) is True


def test_null_location_never_flags_subject(tmp_path):
    tm = Timing({'words': [{'w': 'city', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'city', 'kind': 'place', 'name': 'city', 'where': None}],
             'beats': {'b': {'about': [{'id': 'city', 'words': 'city'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'STATIC-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    c = VC._Ctx({'assets': {}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_real_figure_head_closeup_is_visible():
    from pathlib import Path
    asset = json.loads((Path(__file__).parent / 'fixtures' / 'subject_real_regions.json').read_text(encoding='utf-8'))
    shot = {'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    subject = {'id': 'person', 'kind': 'person', 'where': {'region': 'MAN_FIGURE'}}
    assert VC.subject_visible_at(shot, (0, 4), 1, subject, main='A', assets={'A': asset}, subjects=[subject],
                                 bundle=R.load_bundle('gae'), keys_fn=lambda _: [(0, 1091, 943, 2, 'linear')]) is True


def test_main_work_with_null_location_and_catalogue_title_is_visible():
    shot = {'technique': 'STATIC-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    subject = {'id': 'work', 'kind': 'work', 'name': 'The Garden', 'where': None}
    assert VC.subject_visible_at(shot, (0, 3), 1, subject, main='A', assets={'A': {'title': 'Artist - Garden'}},
                                 subjects=[subject], bundle=R.load_bundle('gae'), keys_fn=lambda _: None) is True


def test_null_location_main_work_never_flags_other_picture(tmp_path):
    tm = Timing({'words': [{'w': 'Garden', 's': 1, 'e': 2}], 'beats': [{'id': 'b', 'start': 0, 'end': 3, 'w0': 0, 'w1': 1}]})
    picks = {'main_asset': 'A', 'subjects': [{'id': 'work', 'kind': 'work', 'name': 'The Garden', 'where': None}],
             'beats': {'b': {'about': [{'id': 'work', 'words': 'Garden'}]}}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf-8')
    shot = {'id': 's', 'technique': 'STATIC-01', 'slots': {'image': {'asset': 'B'}}, 'params': {}}
    c = VC._Ctx({'assets': {'A': {'title': 'Artist - Garden'}}, 'shots': [shot]}, tm, R.load_bundle('gae'), tmp_path, [0], 3, SB.safe_rel)
    assert VC._subject_not_on_screen(c) == []


def test_another_persons_face_does_not_make_subject_visible():
    asset = {'width': 2000, 'height': 2000, 'regions': {
        'FIGURE': {'x': 500, 'y': 1200, 'rx': 200, 'ry': 600, 'thing': 'Ada figure'},
        'FACE': {'x': 1400, 'y': 500, 'rx': 100, 'ry': 100, 'thing': 'Beatrice face'}}}
    shot = {'technique': 'CAM-01', 'slots': {'image': {'asset': 'A'}}, 'params': {}}
    subject = {'id': 's', 'kind': 'person', 'name': 'Ada', 'where': {'region': 'FIGURE'}}
    assert VC.subject_visible_at(shot, (0, 4), 1, subject, main='A', assets={'A': asset}, subjects=[subject],
                                 bundle=R.load_bundle('gae'), keys_fn=lambda _: [(0, 1400, 500, 3, 'linear')]) is False
