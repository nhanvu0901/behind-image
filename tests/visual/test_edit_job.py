import json
import sys
import pytest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'picks'))
from auto_helpers import make_auto_project


@pytest.mark.parametrize("missing", [False, True, "found"])
def test_edit_job_rechecks_repairs_saves_and_composes(tmp_path, monkeypatch, missing):
    from bti.visual import edit, store
    from bti.picks import context
    from bti.picks.auto import session
    from bti.longjob import LongJobManager
    from bti.draft.guard import Guard
    from bti.compose import api
    root = tmp_path / 'projects'; root.mkdir()
    pdir = make_auto_project(root)
    words, beats = [], []
    for chapter in context.narration_view(pdir)['chapters']:
        for line in chapter['beats']:
            start = len(words)
            for word in line['text'].split():
                i = len(words); words.append({'w': word, 's': i * .8, 'e': (i + 1) * .8})
            beats.append({'id': line['id'], 'w0': start, 'w1': len(words)})
    timing = {'words': words, 'beats': beats}
    (pdir / 'timing.json').write_text(json.dumps(timing), encoding='utf-8')
    moments = [{'id': f'm{i}', 'line': b['id'], 'w0': b['w0'], 'w1': b['w1'], 'about': None,
                'show': {'whole': True}, 'move': 'hold', 'from': 'whole', 'say': [], 'why': 'Toàn cảnh.'}
               for i, b in enumerate(beats)]
    visual = {'schema': 'bti.visual/1', 'made_from': {'narration': 'n', 'timing': 't'}, 'cast': [], 'wanted': [], 'moments': moments}
    store.save(pdir, visual, base_rev=None)
    class FakeAgent:
        def run(self, ws, *, check, **kwargs):
            doc = json.loads((ws / 'inputs/visual.json').read_text(encoding='utf-8'))
            if (ws / 'inputs/search.json').exists():
                (ws / 'out/choice.json').write_text(json.dumps({'w1': {'pick': 1, 'caption': 'A historical portrait', 'shows': ['city'], 'period': 'then'} if missing == 'found' else {'pick': None}}), encoding='utf-8')
                assert check(1) is None
                return SimpleNamespace(status='ok', steps=1, turns=1, repairs=0, elapsed=0)
            doc['moments'][0]['about'] = 'missing'
            (ws / 'out/visual.json').write_text(json.dumps(doc), encoding='utf-8')
            assert check(1)
            doc['moments'][0]['about'] = None
            doc['moments'][0]['why'] = 'Đã sửa.'
            if missing:
                doc['cast'].append({'id': 'city', 'kind': 'idea', 'name': 'City', 'also': [], 'strip': False, 'sub': '', 'shown_by': []})
                doc['wanted'].append({'id': 'w1', 'subject': 'city', 'kind': 'place', 'search': 'old city', 'alt': [], 'period': 'then', 'status': 'open', 'picture': None, 'tried': []})
                doc['moments'][0]['show'] = {'want': 'w1', 'else': {'whole': True}}
            (ws / 'out/visual.json').write_text(json.dumps(doc), encoding='utf-8')
            assert check(2) is None
            return SimpleNamespace(status='ok', steps=2, turns=2, repairs=1, elapsed=0)
    monkeypatch.setattr(session, 'agent_module', lambda _: FakeAgent())
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    from bti.picks.auto import search
    if missing:
        from auto_helpers import install_sources, meta
        install_sources(monkeypatch)
        def fake_search(pdir, old, state, requests, **kwargs):
            for req in requests:
                candidate = {**meta('commons', 'File:Portrait A.jpg', 'Portrait A', ''), 'n': 1} if missing == 'found' else None
                state['wants'][req['id']] = {'status': 'done', 'candidates': [candidate] if candidate else [], 'tried_queries': [req['search']]}
            return state
        monkeypatch.setattr(search, 'run', fake_search)
    composed = []
    monkeypatch.setattr(api, 'post_compose', lambda *a, **k: composed.append(True) or {})
    manager = LongJobManager(); manager.configure(projects_root=root)
    rec = edit.start(pdir.name, pdir, instruction='Sửa cảnh', scope={'moments': ['m0']}, manager=manager,
                     guard_factory=lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), python=sys.executable)
    result = manager.wait(rec['id'], 60)
    assert result['state'] == 'done', json.dumps(result, ensure_ascii=False, indent=2)
    assert store.load(pdir)['moments'][0]['why'] == 'Đã sửa.'
    assert composed == [True]
    if missing:
        assert store.load(pdir)['wanted'][0]['status'] == ('found' if missing == 'found' else 'none')
        if missing == 'found':
            assert store.load(pdir)['wanted'][0]['picture']
        else:
            assert 'old city' in result['result']['missing'][0]
    assert list((pdir / 'history').glob('visual_*.json'))
