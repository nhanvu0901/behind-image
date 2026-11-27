import copy

import pytest

from bti.visual.edit import scope_ids, check_scope


def document():
    return {'moments': [{'id': 'm1', 'line': 'b1', 'why': 'one'},
                        {'id': 'm2', 'line': 'b1', 'why': 'two'},
                        {'id': 'm3', 'line': 'b2', 'why': 'three'}]}


def test_scope_moments_lines_and_all():
    doc = document()
    assert scope_ids(doc, {'moments': ['m2']}) == ['m2']
    assert scope_ids(doc, {'lines': ['b1']}) == ['m1', 'm2']
    assert scope_ids(doc, {'all': True}) == ['m1', 'm2', 'm3']


@pytest.mark.parametrize('scope', [{}, {'moments': ['missing']}, {'lines': ['missing']},
                                  {'all': True, 'moments': ['m1']}, {'moments': []}])
def test_scope_rejects_invalid_selection(scope):
    with pytest.raises(ValueError):
        scope_ids(document(), scope)


def test_scope_rejects_changes_outside_selection():
    before = document()
    after = copy.deepcopy(before)
    after['moments'][1]['why'] = 'changed'
    assert check_scope(before, after, ['m1'])
    assert not check_scope(before, after, ['m2'])


def test_edit_workspace_carries_script_scope_and_instruction(tmp_path):
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from bti.visual.edit import build_workspace
    image = Path(__file__).parent / 'fixtures/landscape/media/painting.png'
    painting = SimpleNamespace(key='A', file=image, title='T', artist='A', year='', regions={})
    inp = SimpleNamespace(pdir=tmp_path, painting=painting, facts={}, identity={}, details=[],
                          picks={'main_asset': 'A', 'assets': {'A': {'file': str(image)}}},
                          narration_rev='rev', beats=[{'id': 'b1', 'text': 'A town.'}])
    timing = {'words': [{'w': 'A', 's': 0, 'e': 1}, {'w': 'town.', 's': 1, 'e': 2}],
              'beats': [{'id': 'b1', 'w0': 0, 'w1': 2}]}
    visual = {'moments': [{'id': 'm1', 'line': 'b1'}]}
    root = build_workspace(inp, timing, visual, ['m1'], 'Show the town', root=tmp_path / 'edit')
    assert json.loads((root / 'inputs/visual.json').read_text()) == visual
    assert json.loads((root / 'inputs/scope.json').read_text()) == ['m1']
    assert 'Show the town' in (root / 'TASK.md').read_text()
    assert (root / 'inputs/catalogue.json').is_file()


def test_scope_rejects_new_moment_outside_requested_words(tmp_path):
    import json
    from bti.visual.edit import edit_check
    from bti.visual import check
    from unittest.mock import patch
    before = {'moments': [{'id': 'm1', 'w0': 0, 'w1': 2}, {'id': 'm2', 'w0': 2, 'w1': 4}], 'wanted': []}
    after = {'moments': [before['moments'][0], {'id': 'new', 'w0': 2, 'w1': 3}, before['moments'][1]], 'wanted': []}
    (tmp_path / 'inputs').mkdir(); (tmp_path / 'out').mkdir()
    for path, value in [('inputs/visual.json', before), ('inputs/scope.json', ['m1']), ('out/visual.json', after)]:
        (tmp_path / path).write_text(json.dumps(value))
    with patch.object(check, 'run_check', return_value={'issues': [], 'ok': True}):
        assert not edit_check(tmp_path)['ok']


def test_shared_cast_changes_cannot_silently_change_unselected_moments():
    before = {'moments': [{'id': 'm1', 'about': 'p', 'say': []}, {'id': 'm2', 'about': 'p', 'say': []}],
              'cast': [{'id': 'p', 'name': 'Person', 'sub': 'old'}]}
    after = copy.deepcopy(before)
    after['cast'][0]['sub'] = 'changed'
    assert check_scope(before, after, ['m1'])


def test_missing_picture_for_existing_want_is_reported_by_moment():
    from bti.visual.edit import missing_by_moment
    visual = {'wanted': [{'id': 'w1', 'status': 'none', 'search': 'Bruges'}],
              'moments': [{'id': 'm1', 'show': {'want': 'w1', 'else': {'whole': True}}}]}
    assert missing_by_moment(visual, ['m1']) == {'m1': 'Bruges'}


def test_missing_picture_maps_split_moment_to_original_scope():
    from bti.visual.edit import missing_by_moment
    old = {'moments': [{'id': 'm1', 'line': 'b1', 'w0': 0, 'w1': 8}]}
    new = {'wanted': [{'id': 'w1', 'status': 'none', 'search': 'Bruges'}],
           'moments': [{'id': 'm1a', 'line': 'b1', 'w0': 0, 'w1': 4, 'show': {'whole': True}},
                       {'id': 'm1b', 'line': 'b1', 'w0': 4, 'w1': 8, 'show': {'want': 'w1', 'else': {'whole': True}}}]}
    assert missing_by_moment(new, ['m1'], before=old) == {'m1': 'Bruges'}
