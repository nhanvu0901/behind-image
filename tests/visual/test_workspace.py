import json
from types import SimpleNamespace
from pathlib import Path
from bti.visual.workspace import build_plan


def test_replan_gets_whole_catalogue_without_old_subject_table(tmp_path):
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    p = SimpleNamespace(key='A', file=source, title='Landscape', artist='Artist', year='1800', regions={'TREE': {'box': [.1, .1, .5, .6], 'label': 'Tree'}}, width=100, height=100)
    inp = SimpleNamespace(pdir=tmp_path, painting=p, facts={'f': 'A fact'}, identity={}, details=[],
                          picks={'main_asset': 'A', 'assets': {'A': {'file': str(source)}, 'B': {'file': str(source), 'caption': 'A town', 'shows': ['town'], 'period': 'then'}, 'C': {'file': str(source), 'caption': 'A river'}}, 'subjects': [{'id': 'old'}], 'beats': {'b1': {'items': [{'asset': 'B'}]}}},
                          narration_rev='n', beats=[{'id': 'b1', 'text': 'A town. A river.'}])
    timing = {'words': [{'w': w, 's': i, 'e': i+1} for i, w in enumerate(['A', 'town.', 'A', 'river.'])], 'beats': [{'id': 'b1', 'w0': 0, 'w1': 4}]}
    ws = build_plan(inp, timing, root=tmp_path / 'work', instruction='Plan {{CHECK_CMD}}')
    painting = json.loads((ws / 'inputs/painting.json').read_text())
    assert (ws / painting['regions']['TREE']['thumbnail']).is_file()
    catalogue = json.loads((ws / 'inputs/catalogue.json').read_text())
    assert [x['key'] for x in catalogue] == ['B', 'C']
    assert all((ws / x['thumbnail']).is_file() for x in catalogue)
    assert catalogue[0]['shows'] == ['town'] and catalogue[0]['period'] == 'then'
    content = (ws / 'inputs/narration.json').read_text()
    assert 'old' not in content and 'already' not in content
    narration = json.loads(content)
    assert [(line['id'], line['w0'], line['w1']) for line in narration['lines']] == [('b1', 0, 4)]
    sentences = narration['sentences']
    assert [(s['w0'], s['w1']) for s in sentences] == [(0, 2), (2, 4)]
    assert 'subjects' not in json.loads((ws / 'inputs/picks.json').read_text())
    assert 'beats' not in json.loads((ws / 'inputs/picks.json').read_text())


def test_choose_folder_includes_numbered_candidate_sheets(tmp_path):
    from bti.visual.workspace import build_choose
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    visual = {'cast': [{'id': 'a'}], 'wanted': [{'id': 'w1', 'search': 'town'}]}
    search = {'wants': {'w1': {'candidates': [{'n': 1, 'thumb': str(source), 'title': 'Old town'}], 'tried_queries': ['town']}}}
    root = build_choose(tmp_path, visual, search, root=tmp_path / 'choose')
    wants = json.loads((root / 'inputs/wants.json').read_text())
    assert wants[0]['id'] == 'w1' and (root / wants[0]['sheet']).is_file()
    assert wants[0]['candidates'][0]['n'] == 1


def test_context_exposes_revisions_for_script(tmp_path):
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    p = SimpleNamespace(key='A', file=source, title='T', artist='A', year='', regions={})
    inp = SimpleNamespace(pdir=tmp_path, painting=p, facts={}, identity={}, details=[], picks={'main_asset':'A', 'assets':{'A':{'file':str(source)}}}, narration_rev='narration-rev', beats=[])
    timing = {'words': [], 'beats': []}
    root = build_plan(inp, timing, root=tmp_path / 'work', instruction='x')
    context = json.loads((root / 'inputs/context.json').read_text())
    assert context['made_from']['narration'] == 'narration-rev' and context['made_from']['timing']


def test_choose_workspace_prepares_new_region_cutouts(tmp_path):
    from bti.visual.workspace import build_choose
    from bti.picks.auto.session import Limits
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    main = {'file': str(source), 'width': 100, 'height': 100, 'regions': {}, 'title': 'Landscape'}
    visual = {'cast': [], 'wanted': []}
    root = build_choose(tmp_path, visual, {'wants': {}}, root=tmp_path / 'choose', main=main,
                        regions={'TREE': {'box': [0.1, 0.1, 0.5, 0.6], 'what': 'a tree'}}, limits=Limits(5, 30, 1))
    entries = json.loads((root / 'tighten/inputs/regions.json').read_text())['regions']
    assert entries[0]['name'] == 'TREE' and (root / 'tighten' / entries[0]['cutout']).exists()


def test_revisions_use_the_same_file_hashes_as_the_visual_converter(tmp_path):
    import hashlib
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    (tmp_path / 'script').mkdir()
    narration = tmp_path / 'script/narration.json'
    timing_file = tmp_path / 'timing.json'
    narration.write_text('{"chapters": []}\n')
    timing_file.write_text('{"words": [], "beats": []}\n')
    p = SimpleNamespace(key='A', file=source, title='T', artist='A', year='', regions={})
    inp = SimpleNamespace(pdir=tmp_path, painting=p, facts={}, identity={}, details=[], picks={'main_asset':'A', 'assets':{'A':{'file':str(source)}}}, narration_rev='other', beats=[])
    root = build_plan(inp, {'words': [], 'beats': []}, root=tmp_path / 'work', instruction='x')
    made = json.loads((root / 'inputs/context.json').read_text())['made_from']
    assert made == {'narration': hashlib.sha1(narration.read_bytes()).hexdigest(), 'timing': hashlib.sha1(timing_file.read_bytes()).hexdigest()}


def test_catalogue_resolves_old_cast_ids_to_names_without_exporting_old_table(tmp_path):
    source = Path(__file__).parent / 'fixtures' / 'landscape' / 'media' / 'painting.png'
    p = SimpleNamespace(key='A', file=source, title='T', artist='A', year='', regions={})
    picks = {'main_asset': 'A', 'assets': {'A': {'file': str(source)}, 'B': {'file': str(source), 'shows': ['old-id']}},
             'subjects': [{'id': 'old-id', 'name': 'A real person'}]}
    inp = SimpleNamespace(pdir=tmp_path, painting=p, facts={}, identity={}, details=[], picks=picks, narration_rev='n', beats=[])
    ws = build_plan(inp, {'words': [], 'beats': []}, root=tmp_path / 'work', instruction='x')
    catalogue = json.loads((ws / 'inputs/catalogue.json').read_text())
    assert catalogue[0]['shows'] == ['A real person']
    assert 'subjects' not in json.loads((ws / 'inputs/picks.json').read_text())
