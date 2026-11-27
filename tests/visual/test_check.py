import json
from bti.visual.check import run_check
from test_validation import valid, timing


def test_check_refuses_errors_but_reports_whole_without_refusal(tmp_path):
    for name in ('inputs', 'out'):
        (tmp_path / name).mkdir()
    (tmp_path / 'inputs/timing.json').write_text(json.dumps(timing()), encoding='utf-8')
    (tmp_path / 'inputs/picks.json').write_text(json.dumps({'main_asset': 'A', 'assets': {'A': {'regions': {'RIVER': {}}}}}), encoding='utf-8')
    doc = valid()
    doc['moments'][0].update(w1=1, show={'region': 'SKY'})
    doc['cast'][0]['strip'] = True
    (tmp_path / 'out/visual.json').write_text(json.dumps(doc), encoding='utf-8')
    report = run_check(tmp_path)
    assert {'V1', 'V2', 'V3', 'V6'} <= {i['rule'] for i in report['issues']}
    assert not report['ok']
    doc = valid()
    doc['moments'][0].update(about=None, show={'whole': True})
    (tmp_path / 'out/visual.json').write_text(json.dumps(doc), encoding='utf-8')
    report = run_check(tmp_path)
    assert report['ok'] and any(i['rule'] == 'V9' for i in report['issues'])


def test_choose_check_reports_invalid_candidate(tmp_path):
    (tmp_path / 'inputs').mkdir()
    (tmp_path / 'out').mkdir()
    (tmp_path / 'inputs/context.json').write_text(json.dumps({'mode': 'choose'}))
    (tmp_path / 'inputs/visual.json').write_text(json.dumps({'cast': [{'id': 'a'}], 'wanted': [{'id': 'w1'}]}))
    (tmp_path / 'inputs/search.json').write_text(json.dumps({'wants': {'w1': {'candidates': [{'n': 1}]}}}))
    (tmp_path / 'out/choice.json').write_text(json.dumps({'w1': {'pick': 7}}))
    assert not run_check(tmp_path)['ok']
    (tmp_path / 'out/choice.json').write_text(json.dumps({'w1': {'pick': 1, 'caption': 'A city', 'shows': ['a'], 'period': 'then'}}))
    assert run_check(tmp_path)['ok']


def test_check_rejects_invalid_new_regions(tmp_path):
    for name in ('inputs', 'out'):
        (tmp_path / name).mkdir()
    (tmp_path / 'inputs/timing.json').write_text(json.dumps(timing()))
    (tmp_path / 'inputs/picks.json').write_text(json.dumps({'main_asset': 'A', 'assets': {'A': {'regions': {}}}}))
    (tmp_path / 'out/visual.json').write_text(json.dumps(valid()))
    (tmp_path / 'out/regions.json').write_text(json.dumps({'RIVER': {'box': [0.9, 0.2, 0.1, 0.3], 'what': 'river'}}))
    assert not run_check(tmp_path)['ok']


def test_check_rejects_outdated_source_hashes(tmp_path):
    for name in ('inputs', 'out'):
        (tmp_path / name).mkdir()
    (tmp_path / 'inputs/timing.json').write_text(json.dumps(timing()))
    (tmp_path / 'inputs/picks.json').write_text(json.dumps({'main_asset': 'A', 'assets': {'A': {'regions': {}}}}))
    (tmp_path / 'inputs/context.json').write_text(json.dumps({'mode': 'plan', 'made_from': {'narration': 'new', 'timing': 'new'}}))
    (tmp_path / 'out/visual.json').write_text(json.dumps(valid()))
    assert not run_check(tmp_path)['ok']


def test_choose_check_requires_tightening_when_cutouts_present(tmp_path):
    for folder in ('inputs', 'out', 'tighten'):
        (tmp_path / folder).mkdir()
    (tmp_path / 'inputs/context.json').write_text(json.dumps({'mode': 'choose'}))
    (tmp_path / 'inputs/visual.json').write_text(json.dumps({'cast': [], 'wanted': []}))
    (tmp_path / 'inputs/search.json').write_text(json.dumps({'wants': {}}))
    (tmp_path / 'out/choice.json').write_text('{}')
    assert not run_check(tmp_path)['ok']
