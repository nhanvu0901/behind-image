from types import SimpleNamespace
from bti.draft.workspace import _beats_doc


def test_cast_entries_reach_only_their_line():
    cast = {'name': 'Costanza Trenta', 'also': ['Costanza'], 'line': 'b0001',
            'where': {'region': 'HEAD'}, 'sure': False, 'words': 'most often named'}
    inp = SimpleNamespace(title='Title', narration=None, picks={'main_asset': 'A', 'beats': {}, 'names': [cast]}, timing={
        'duration': 8, 'words': [], 'chapters': [{'id': 'c1', 'name': 'One', 'start': 0, 'end': 8, 'card': False, 'w0': 0, 'w1': 2}],
        'beats': [{'id': 'b0001', 'chapter': 'c1', 'text': 'Costanza', 'start': 0, 'end': 4, 'w0': 0, 'w1': 1},
                  {'id': 'b0002', 'chapter': 'c1', 'text': 'Again', 'start': 4, 'end': 8, 'w0': 1, 'w1': 2}]})
    beats = _beats_doc(inp)['chapters'][0]['beats']
    assert beats[0]['present'] == [cast]
    assert beats[1]['present'] == []
