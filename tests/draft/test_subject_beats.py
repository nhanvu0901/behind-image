from types import SimpleNamespace
from bti.draft.workspace import _beats_doc


def test_subjects_and_about_reach_storyboard_model_in_order():
    subjects = [{'id': 'village', 'kind': 'place', 'name': 'Village', 'strip': True, 'where': {'region': 'VILLAGE'}},
                {'id': 'river', 'kind': 'thing', 'name': 'river', 'strip': False, 'where': {'region': 'RIVER'}}]
    about = [{'id': 'river', 'words': 'river'}, {'id': 'village', 'words': 'village'}]
    inp = SimpleNamespace(title='Landscape', narration=None, picks={'main_asset': 'A', 'subjects': subjects, 'beats': {'b1': {'about': about}}}, timing={
        'duration': 4, 'words': [], 'chapters': [{'id': 'c1', 'name': 'One', 'start': 0, 'end': 4, 'card': False, 'w0': 0, 'w1': 2}],
        'beats': [{'id': 'b1', 'chapter': 'c1', 'text': 'river village', 'start': 0, 'end': 4, 'w0': 0, 'w1': 2}]})
    result = _beats_doc(inp)
    assert result['subjects'] == subjects
    assert result['chapters'][0]['beats'][0]['about'] == about


def test_compiler_replaces_model_strip_and_pointer(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w12', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'][0]['start_word'] = 13
    result = compile_specs(inp, specs, draw=False, identity=False)
    overlays = result.storyboard['shots'][1]['overlays']
    assert len([o for o in overlays if o['technique'] == 'X-ANN-01' and o['params']['text'] == 'w12']) == 1
    assert len([o for o in overlays if o['technique'] == 'HI-01' and o['params']['at'] == 'MIRROR']) == 1
    assert next(o for o in overlays if o['technique'] == 'X-ANN-01')['start']['w'] == 12
    assert next(o for o in overlays if o['technique'] == 'HI-01')['start']['w'] == 12


def test_idea_never_gets_a_strip(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'hope', 'kind': 'idea', 'name': 'w12', 'strip': True, 'where': None}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'hope', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 12, 'params': {'text': 'w12'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert not any(o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12'
                   for shot in result.storyboard['shots'] for o in shot.get('overlays', []))


def test_compiler_removes_model_subject_strip_if_subject_is_not_visible(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'painter', 'kind': 'person', 'name': 'w12', 'strip': True, 'where': {'asset': 'B'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'painter', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 12, 'params': {'text': 'w12'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert not any(o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12'
                   for s in result.storyboard['shots'] for o in s.get('overlays', []))


def test_strip_starts_on_subject_name_not_description(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w14', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01']
    assert len(strips) == 1 and strips[0]['start']['w'] == 14


def test_multiple_named_landscape_features_get_circles(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['RIVER'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'River'}
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'river', 'kind': 'thing', 'name': 'w14', 'strip': False, 'where': {'region': 'RIVER'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w12'}, {'id': 'river', 'words': 'w14'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    result = compile_specs(inp, specs, draw=False, identity=False)
    marks = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'AN-01']
    assert {(o['params']['at'], o['start']['w']) for o in marks} == {('MIRROR', 12), ('RIVER', 14)}


def test_strip_can_start_after_a_cut_inside_a_line(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w17', 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'].insert(2, clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 15)]}, 'c01')['shots'][0])
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w17']
    assert len(strips) == 1 and strips[0]['start']['w'] == 17


def test_multiple_circles_continue_across_a_cut_until_sentence_end(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['RIVER'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'River'}
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w11', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'RIVER'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w11'}, {'id': 'river', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'].insert(2, clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 15, slots={'image': {'asset': 'A', 'region': 'MIRROR'}})]}, 'c01')['shots'][0])
    result = compile_specs(inp, specs, draw=False, identity=False)
    later = result.storyboard['shots'][2]
    assert {o['params']['at'] for o in later['overlays'] if o['technique'] == 'AN-01'} == {'MIRROR', 'RIVER'}


def test_named_artwork_gets_a_strip_on_its_own_picture(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'painting', 'kind': 'work', 'name': 'w32', 'strip': True, 'where': {'asset': 'B'}}]
    inp.picks['beats']['b0004']['about'] = [{'id': 'painting', 'words': 'w32'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w32']
    assert len(strips) == 1 and strips[0]['start']['w'] == 32


def test_pointer_stops_at_sentence_end_even_if_beat_has_another_sentence(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][15]['w'] = 'w15.'
    inp.picks['subjects'] = [{'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'river', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    result = compile_specs(inp, specs, draw=False, identity=False)
    light = next(o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'HI-01')
    assert light['start']['w'] == 12
    assert light['dur'] == round(inp.timing['words'][15]['e'] - inp.timing['words'][12]['s'], 3)


def test_each_proper_alias_is_shown_once_and_descriptions_are_not_names(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'also': ['w14'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w11'}, {'id': 'person', 'words': 'w12'}, {'id': 'person', 'words': 'w14'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    result = compile_specs(inp, specs, draw=False, identity=False)
    labels = [(o['params']['text'], o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert labels == [('w12', 12)]


def test_text_subject_never_has_model_or_generated_strip(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'book', 'kind': 'text', 'name': 'w12', 'also': ['w13'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'book', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 13, 'params': {'text': 'w13'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert not any(o['technique'] == 'X-ANN-01' and o['params'].get('text') in ('w12', 'w13') for s in result.storyboard['shots'] for o in s.get('overlays', []))


def test_alias_is_only_introduced_once_when_repeated(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][22]['w'] = 'w14'
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'also': ['w14'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}, {'id': 'person', 'words': 'w14'}]
    inp.picks['beats']['b0003'] = {'about': [{'id': 'person', 'words': 'w14'}]}
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    labels = [(o['params']['text'], o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert labels == [('w12', 12)]


def test_short_name_inside_full_name_waits_until_spoken_on_its_own(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][16]['w'] = 'w12'
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12 w13', 'also': ['w12'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12 w13'}, {'id': 'person', 'words': 'w12'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    labels = [(o['params']['text'], o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert labels == [('w12 w13', 12)]


def test_repeated_subject_in_two_sentences_gets_a_pointer_in_each(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][14]['w'] = 'w14.'
    inp.picks['subjects'] = [{'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'river', 'words': 'w12'}, {'id': 'river', 'words': 'w16'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    marks = [o['start']['w'] for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'HI-01']
    assert marks == [12, 16]


def test_model_cannot_repeat_known_name_on_an_unrelated_line(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'also': [], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][2]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 22, 'params': {'text': 'w12'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    labels = [(o['params']['text'], o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12']
    assert labels == [('w12', 12)]


def test_strip_uses_camera_after_frame_fitting(proj, monkeypatch):
    from bti.draft.compile import compile_specs, _Compiler
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}]
    def fit_away(self, doc, origin):
        shot = next(s for s, o in zip(doc['shots'], origin) if o['beat'] == 'b0002')
        shot['params']['camera'] = [{'at': {'rel': n}, 'cx': 0, 'cy': 1100, 'zoom': 4} for n in (0, 1)]
        return []
    monkeypatch.setattr(_Compiler, 'fit_to_box', fit_away)
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    assert not any(o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12' for s in result.storyboard['shots'] for o in s.get('overlays', []))


def test_painting_label_is_added_over_its_detail(proj):
    from bti.draft.compile import compile_specs, _Compiler
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'painting', 'kind': 'work', 'name': 'w12', 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'painting', 'words': 'w12'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    # The picture is still the painting when the shot zooms to a detail.
    strip = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12']
    assert len(strip) == 1


def test_subject_strips_do_not_overlap_when_two_names_are_spoken(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from bti.engine.timing import Timing
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [
        {'id': 'person1', 'kind': 'person', 'name': 'w12', 'strip': True, 'where': {'asset': 'A'}},
        {'id': 'person2', 'kind': 'person', 'name': 'w16', 'strip': True, 'where': {'asset': 'A'}},
    ]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person1', 'words': 'w12'}, {'id': 'person2', 'words': 'w16'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01']
    tm = Timing(inp.timing)
    assert len(strips) == 2
    assert tm.resolve(strips[0]['start']) + strips[0]['dur'] <= tm.resolve(strips[1]['start'])


def test_first_named_subject_uses_circle_when_second_is_named_after_a_cut(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['RIVER'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'River'}
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'river', 'kind': 'thing', 'name': 'w16', 'strip': False, 'where': {'region': 'RIVER'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w12'}, {'id': 'river', 'words': 'w16'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'].insert(2, clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 15, slots={'image': {'asset': 'A', 'region': 'MIRROR'}})]}, 'c01')['shots'][0])
    result = compile_specs(inp, specs, draw=False, identity=False)
    marks = [(o['technique'], o['params'].get('at'), o['start']['w']) for o in result.storyboard['shots'][1]['overlays']]
    assert ('AN-01', 'MIRROR', 12) in marks


def test_repeated_about_words_are_matched_in_spoken_order(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][14]['w'] = 'w14.'
    inp.timing['words'][16]['w'] = 'w12'
    inp.picks['subjects'] = [{'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'river', 'words': 'w12'}, {'id': 'river', 'words': 'w12'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    marks = [o['start']['w'] for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'HI-01']
    assert marks == [12, 16]


def test_multiple_subjects_get_circles_even_if_not_small(proj, monkeypatch):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from bti.engine import viewchecks
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['RIVER'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'River'}
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'river', 'kind': 'thing', 'name': 'w14', 'strip': False, 'where': {'region': 'RIVER'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w12'}, {'id': 'river', 'words': 'w14'}]
    monkeypatch.setattr(viewchecks, 'is_small_on_screen', lambda *args, **kwargs: False)
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    marks = [o['params']['at'] for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'AN-01']
    assert set(marks) == {'MIRROR', 'RIVER'}


def test_multiple_saints_are_distinguished_with_circles(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['SAINT2'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'Saint'}
    inp.picks['subjects'] = [{'id': 'saint1', 'kind': 'person', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'saint2', 'kind': 'person', 'name': 'w14', 'strip': False, 'where': {'region': 'SAINT2'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'saint1', 'words': 'w12'}, {'id': 'saint2', 'words': 'w14'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    marks = [o['params']['at'] for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'AN-01']
    assert set(marks) == {'MIRROR', 'SAINT2'}


def test_model_pointer_on_an_unrelated_line_is_not_kept(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'river', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][2]['overlays'].append({'technique': 'HI-01', 'start_word': 22, 'params': {'at': 'MIRROR'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert not any(o['technique'] == 'HI-01' and o['params'].get('at') == 'MIRROR' for o in result.storyboard['shots'][2]['overlays'])


def test_circle_continues_from_cut_before_next_spoken_word(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from bti.engine.timing import Timing
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['RIVER'] = {'x': 410, 'y': 310, 'rx': 20, 'ry': 20, 'label': 'River'}
    inp.picks['subjects'] = [{'id': 'village', 'kind': 'place', 'name': 'w11', 'strip': False, 'where': {'region': 'MIRROR'}},
                             {'id': 'river', 'kind': 'thing', 'name': 'w12', 'strip': False, 'where': {'region': 'RIVER'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'village', 'words': 'w11'}, {'id': 'river', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    new_shot = shot('b0002', 15, off=-.2, slots={'image': {'asset': 'A', 'region': 'MIRROR'}})
    specs['c01']['shots'].insert(2, clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [new_shot]}, 'c01')['shots'][0])
    result = compile_specs(inp, specs, draw=False, identity=False)
    later = result.storyboard['shots'][2]
    tm = Timing(inp.timing)
    starts = [tm.resolve(o['start']) for o in later['overlays'] if o['technique'] == 'AN-01']
    assert len(starts) == 2 and all(t == tm.resolve(later['start']) for t in starts)


def test_strip_names_subject_in_second_comparison_panel(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'portrait', 'kind': 'work', 'name': 'w12', 'strip': True, 'where': {'asset': 'B'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'portrait', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['technique'] = 'LAY-01'
    specs['c01']['shots'][1]['slots'] = {'left': {'asset': 'A'}, 'right': {'asset': 'B'}}
    specs['c01']['shots'][1]['overlays'] = []
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12']
    assert len(strips) == 1 and strips[0]['start']['w'] == 12


def test_legacy_project_without_subjects_keeps_model_overlays(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    assert 'subjects' not in inp.picks
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 12, 'dur': 2.0, 'params': {'text': 'Mirror'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    overlays = result.storyboard['shots'][1]['overlays']
    assert any(o['technique'] == 'HI-01' and o['params']['at'] == 'MIRROR' for o in overlays)
    assert any(o['technique'] == 'X-ANN-01' and o['params']['text'] == 'Mirror' for o in overlays)


def test_multi_beat_shot_generates_strip_for_later_beat_subject(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'tower', 'kind': 'thing', 'name': 'w22', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0003'] = {'about': [{'id': 'tower', 'words': 'w22'}]}
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'] = specs['c01']['shots'][:2]
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w22']
    assert len(strips) == 1 and strips[0]['start']['w'] == 22


def test_portrait_person_gets_strip_with_sub_and_no_spotlight(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['FACE'] = {'x': 400, 'y': 300, 'rx': 20, 'ry': 20, 'label': 'Face'}
    inp.picks['subjects'] = [{'id': 'sitter', 'kind': 'person', 'name': 'w12', 'sub': 'a merchant', 'strip': True, 'where': {'region': 'FACE'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'sitter', 'words': 'w11'}, {'id': 'sitter', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1] = clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 10, 'STATIC-01', slots={'image': {'asset': 'A'}})]}, 'c01')['shots'][0]
    result = compile_specs(inp, specs, draw=False, identity=False)
    overlays = result.storyboard['shots'][1]['overlays']
    strips = [o for o in overlays if o['technique'] == 'X-ANN-01']
    assert len(strips) == 1 and strips[0]['params']['text'] == 'w12' and strips[0]['params']['sub'] == 'a merchant' and strips[0]['start']['w'] == 12
    assert not any(o['technique'] in ('HI-01', 'X-HI-01', 'AN-01') for o in overlays)


def test_text_never_gets_strip_while_illustrating_work_gets_its_title(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [
        {'id': 'scripture', 'kind': 'text', 'name': 'w11', 'strip': True, 'where': None},
        {'id': 'illu', 'kind': 'work', 'name': 'w32', 'sub': '1490 manuscript', 'strip': True, 'where': {'asset': 'B'}},
    ]
    inp.picks['beats']['b0002']['about'] = [{'id': 'scripture', 'words': 'w11'}]
    inp.picks['beats']['b0004']['about'] = [{'id': 'illu', 'words': 'w32'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 11, 'params': {'text': 'w11'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    all_strips = [(o['params'].get('text'), o['params'].get('sub'), o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert ('w11', '', 11) not in all_strips
    assert all(text != 'w11' for text, _, _ in all_strips)
    assert ('w32', '1490 manuscript', 32) in all_strips


def test_lay01_right_panel_main_painting_gets_strip_without_pointer_error(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'saint', 'kind': 'thing', 'name': 'w14', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'saint', 'words': 'w14'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['technique'] = 'LAY-01'
    specs['c01']['shots'][1]['slots'] = {'left': {'asset': 'B'}, 'right': {'asset': 'A', 'region': 'MIRROR'}}
    specs['c01']['shots'][1]['overlays'] = []
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert result.errors == []
    overlays = result.storyboard['shots'][1]['overlays']
    assert [o['params']['text'] for o in overlays if o['technique'] == 'X-ANN-01'] == ['w14']
    assert not any(o['technique'] in ('HI-01', 'AN-01') for o in overlays)


def test_template_generic_and_repair_loop_prioritizes_subject_warning():
    from pathlib import Path
    from bti.draft.compile import CompileResult, summary_text
    from bti.engine import viewchecks as VC
    tpl = (Path(__file__).resolve().parents[2] / 'skills' / 'storyboard_draft' / 'TASK.template.md').read_text(encoding='utf-8')
    assert len(tpl.encode('utf-8')) < 35_500
    for forbidden in ('Arnolfini', 'Costanza', 'Giovanni', 'Joined hands', 'Latin inscription', '60 cm', '82 cm', 'a painter does not sign'):
        assert forbidden.lower() not in tpl.lower(), forbidden
    assert 'subjects' in tpl and 'about' in tpl and 'subject_not_on_screen' in tpl
    assert 'subject_not_on_screen' in VC.CODES
    res = CompileResult({'shots': []}, [{'level': 'warn', 'code': 'shot_short', 'message': 'short'},
                                        {'level': 'warn', 'code': 'subject_not_on_screen', 'message': 'subject hidden'}], [], [], {}, False)
    assert 'warning subject_not_on_screen: subject hidden' in summary_text(res, limit=1)


def test_person_in_painting_comparison_panel_gets_strip(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'saint', 'kind': 'person', 'name': 'w12', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'saint', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['technique'] = 'LAY-01'
    specs['c01']['shots'][1]['slots'] = {'left': {'asset': 'A', 'region': 'MIRROR'}, 'right': {'asset': 'B'}}
    specs['c01']['shots'][1]['overlays'] = []
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w12']
    assert len(strips) == 1 and strips[0]['start']['w'] == 12


def test_legacy_project_without_subjects_keeps_model_overlays(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    assert 'subjects' not in inp.picks
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 12, 'dur': 2.0, 'params': {'text': 'Mirror'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    overlays = result.storyboard['shots'][1]['overlays']
    assert any(o['technique'] == 'HI-01' and o['params']['at'] == 'MIRROR' for o in overlays)
    assert any(o['technique'] == 'X-ANN-01' and o['params']['text'] == 'Mirror' for o in overlays)


def test_multi_beat_shot_generates_strip_for_later_beat_subject(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'tower', 'kind': 'thing', 'name': 'w22', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0003'] = {'about': [{'id': 'tower', 'words': 'w22'}]}
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'] = specs['c01']['shots'][:2]
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01' and o['params'].get('text') == 'w22']
    assert len(strips) == 1 and strips[0]['start']['w'] == 22


def test_portrait_person_gets_strip_with_sub_and_no_spotlight(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['FACE'] = {'x': 400, 'y': 300, 'rx': 20, 'ry': 20, 'label': 'Face'}
    inp.picks['subjects'] = [{'id': 'sitter', 'kind': 'person', 'name': 'w12', 'sub': 'a merchant', 'strip': True, 'where': {'region': 'FACE'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'sitter', 'words': 'w11'}, {'id': 'sitter', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1] = clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 10, 'STATIC-01', slots={'image': {'asset': 'A'}})]}, 'c01')['shots'][0]
    result = compile_specs(inp, specs, draw=False, identity=False)
    overlays = result.storyboard['shots'][1]['overlays']
    strips = [o for o in overlays if o['technique'] == 'X-ANN-01']
    assert len(strips) == 1 and strips[0]['params']['text'] == 'w12' and strips[0]['params']['sub'] == 'a merchant' and strips[0]['start']['w'] == 12
    assert not any(o['technique'] in ('HI-01', 'X-HI-01', 'AN-01') for o in overlays)


def test_text_never_gets_strip_while_illustrating_work_gets_its_title(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [
        {'id': 'scripture', 'kind': 'text', 'name': 'w11', 'strip': True, 'where': None},
        {'id': 'illu', 'kind': 'work', 'name': 'w32', 'sub': '1490 manuscript', 'strip': True, 'where': {'asset': 'B'}},
    ]
    inp.picks['beats']['b0002']['about'] = [{'id': 'scripture', 'words': 'w11'}]
    inp.picks['beats']['b0004']['about'] = [{'id': 'illu', 'words': 'w32'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['overlays'].append({'technique': 'X-ANN-01', 'start_word': 11, 'params': {'text': 'w11'}})
    result = compile_specs(inp, specs, draw=False, identity=False)
    all_strips = [(o['params'].get('text'), o['params'].get('sub'), o['start']['w']) for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert ('w11', '', 11) not in all_strips
    assert all(text != 'w11' for text, _, _ in all_strips)
    assert ('w32', '1490 manuscript', 32) in all_strips


def test_lay01_right_panel_main_painting_gets_strip_without_pointer_error(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'saint', 'kind': 'thing', 'name': 'w14', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'saint', 'words': 'w14'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['technique'] = 'LAY-01'
    specs['c01']['shots'][1]['slots'] = {'left': {'asset': 'B'}, 'right': {'asset': 'A', 'region': 'MIRROR'}}
    specs['c01']['shots'][1]['overlays'] = []
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert result.errors == []
    overlays = result.storyboard['shots'][1]['overlays']
    assert [o['params']['text'] for o in overlays if o['technique'] == 'X-ANN-01'] == ['w14']
    assert not any(o['technique'] in ('HI-01', 'AN-01') for o in overlays)


def test_template_generic_and_repair_loop_prioritizes_subject_warning():
    from pathlib import Path
    from bti.draft.compile import CompileResult, summary_text
    from bti.engine import viewchecks as VC
    tpl = (Path(__file__).resolve().parents[2] / 'skills' / 'storyboard_draft' / 'TASK.template.md').read_text(encoding='utf-8')
    assert len(tpl.encode('utf-8')) < 35_500
    for forbidden in ('Arnolfini', 'Costanza', 'Giovanni', 'Joined hands', 'Latin inscription', '60 cm', '82 cm', 'a painter does not sign'):
        assert forbidden.lower() not in tpl.lower(), forbidden
    assert 'subjects' in tpl and 'about' in tpl and 'subject_not_on_screen' in tpl
    assert 'subject_not_on_screen' in VC.CODES
    res = CompileResult({'shots': []}, [{'level': 'warn', 'code': 'shot_short', 'message': 'short'},
                                        {'level': 'warn', 'code': 'subject_not_on_screen', 'message': 'subject hidden'}], [], [], {}, False)
    assert 'warning subject_not_on_screen: subject hidden' in summary_text(res, limit=1)


def test_generated_overlay_duration_does_not_overshoot_fractional_shot_end():
    from bti.draft.compile import _bounded_duration
    start, end = 95.123, 98.7904
    duration = _bounded_duration(start, end)
    assert start + duration <= end
    assert duration > 3.66


def test_generated_strip_stays_inside_fractional_cut(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from bti.engine.timing import Timing
    from helpers import GOOD, clean_spec, shot
    inp = load_inputs(proj)
    inp.timing['words'][15]['s'] = 7.9006
    inp.picks['subjects'] = [{'id': 'v', 'kind': 'place', 'name': 'w12', 'strip': True, 'where': {'region': 'MIRROR'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'v', 'words': 'w12'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'].insert(2, clean_spec({'schema': 'bti.draft/1', 'chapter': 'c01', 'shots': [shot('b0002', 15)]}, 'c01')['shots'][0])
    result = compile_specs(inp, specs, draw=False, identity=False)
    tm = Timing(inp.timing)
    strips = [o for o in result.storyboard['shots'][1]['overlays'] if o['technique'] == 'X-ANN-01']
    assert len(strips) == 1
    assert tm.resolve(strips[0]['start']) + strips[0]['dur'] <= tm.resolve(result.storyboard['shots'][2]['start'])


def test_subject_strip_with_narration_phrasing_in_sub_is_not_dropped(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['assets']['A']['regions']['FIGURE'] = {'x': 400, 'y': 600, 'rx': 150, 'ry': 450, 'label': 'Standing figure'}
    inp.picks['assets']['A']['regions']['HEAD'] = {'x': 400, 'y': 260, 'rx': 80, 'ry': 80, 'label': 'Head'}
    sub_text = ' '.join(w['w'] for w in inp.timing['words'][10:16])
    inp.picks['subjects'] = [{
        'id': 'sitter', 'kind': 'person', 'name': 'w12 w13', 'also': ['w12'],
        'sub': sub_text, 'strip': True,
        'where': [{'region': 'FIGURE'}, {'region': 'HEAD'}],
    }]
    inp.picks['beats']['b0002']['about'] = [{'id': 'sitter', 'words': 'w12 w13'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['slots'] = {'image': {'asset': 'A', 'region': 'HEAD'}}
    result = compile_specs(inp, specs, draw=False, identity=False)
    assert not any(i['code'] == 'narration_on_screen' for i in result.errors)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert len(strips) == 1
    assert strips[0]['params']['text'] == 'w12 w13'
    assert strips[0]['params']['sub'] == sub_text


def test_subject_with_two_names_in_one_sentence_gets_one_strip(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'also': ['w14'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}, {'id': 'person', 'words': 'w14'}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert [(o['params']['text'], o['start']['w']) for o in strips] == [('w12', 12)]
    assert strips[0]['dur'] >= 3.0


def test_later_alias_on_later_shot_gets_no_second_strip(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.timing['words'][22]['w'] = 'w14'
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w12', 'also': ['w14'], 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w12'}]
    inp.picks['beats']['b0003'] = {'about': [{'id': 'person', 'words': 'w14'}]}
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert [(o['params']['text'], o['start']['w']) for o in strips] == [('w12', 12)]


def test_alias_spoken_first_while_visible_uses_spoken_alias_and_suppresses_canonical_name(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    inp.picks['subjects'] = [{'id': 'person', 'kind': 'person', 'name': 'w22', 'also': ['w14'], 'strip': True, 'where': {'asset': 'B'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'person', 'words': 'w14'}]
    inp.picks['beats']['b0004']['about'] = [{'id': 'person', 'words': 'w22'}]
    specs = {c: clean_spec(s, c) for c, s in GOOD.items()}
    specs['c01']['shots'][1]['technique'] = 'X-LAY-01'
    specs['c01']['shots'][1]['slots'] = {'image': {'asset': 'B'}}
    specs['c01']['shots'][1]['overlays'] = []
    inp.timing['words'][32]['w'] = 'w22'
    result = compile_specs(inp, specs, draw=False, identity=False)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert [(o['params']['text'], o['start']['w']) for o in strips] == [('w14', 14)]


def test_subject_with_five_word_proper_name_is_not_dropped(proj):
    from bti.draft.compile import compile_specs
    from bti.draft.inputs import load_inputs
    from helpers import GOOD, clean_spec
    inp = load_inputs(proj)
    long_name = ' '.join(w['w'] for w in inp.timing['words'][12:17])
    inp.picks['subjects'] = [{'id': 'work', 'kind': 'work', 'name': long_name, 'strip': True, 'where': {'asset': 'A'}}]
    inp.picks['beats']['b0002']['about'] = [{'id': 'work', 'words': long_name}]
    result = compile_specs(inp, {c: clean_spec(s, c) for c, s in GOOD.items()}, draw=False, identity=False)
    assert not any(i['code'] == 'narration_on_screen' for i in result.errors)
    strips = [o for s in result.storyboard['shots'] for o in s.get('overlays', []) if o['technique'] == 'X-ANN-01']
    assert [(o['params']['text'], o['start']['w']) for o in strips] == [(long_name, 12)]
