import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'picks'))
from auto_helpers import make_auto_project


@pytest.mark.parametrize("repair,map_view,stale,region,cancel,wrong_path,cleanup", [(False, False, False, False, False, False, False), (True, False, False, False, False, False, False), (False, True, False, False, False, False, False), (False, False, True, False, False, False, False), (False, False, False, True, False, False, False), (False, False, False, True, False, True, False), (False, False, False, False, True, False, False), (False, False, False, False, False, False, True)])
def test_fake_agent_job_saves_script_and_projects_all_lines(tmp_path, monkeypatch, repair, map_view, stale, region, cancel, wrong_path, cleanup):
    from bti.picks import context, doc
    from bti.picks.auto import session
    from bti.longjob import LongJobManager
    from bti.visual import job, store
    root = tmp_path / 'projects'
    root.mkdir()
    pdir = make_auto_project(root)
    if map_view:
        from auto_helpers import install_sources, FakeSource
        from bti.media import api as media_api
        install_sources(monkeypatch)
        monkeypatch.setitem(media_api._SOURCES, 'wikipedia', FakeSource('wikipedia'))
    view = context.narration_view(pdir)
    words, beats = [], []
    for chapter in view['chapters']:
        for line in chapter['beats']:
            start = len(words)
            for word in line['text'].split():
                i = len(words)
                words.append({'w': word, 's': i * .8, 'e': (i + 1) * .8})
            beats.append({'id': line['id'], 'w0': start, 'w1': len(words)})
    timing = {'words': words, 'beats': beats}
    (pdir / 'timing.json').write_text(json.dumps(timing), encoding='utf-8')
    if cleanup:
        from bti.picks.auto.write import Writer
        writer = Writer(pdir, 'agent:test', redo=True)
        writer.send([{'op': 'set_region', 'asset': 'A', 'region': 'OBSOLETE', 'x': 10, 'y': 10},
                     {'op': 'set_picks', 'beat': beats[0]['id'], 'items': [{'asset': 'A', 'region': 'OBSOLETE', 'role': 'detail'}]}], 'setup')
    class FakeAgent:
        def run(self, ws, *, check, **kwargs):
            context_data = json.loads((ws / 'inputs/context.json').read_text(encoding='utf-8'))
            if cancel:
                manager.cancel(manager.active(pdir.name, kind='picks')['id'])
                return SimpleNamespace(status='cancelled', steps=1, turns=1, repairs=0, elapsed=0)
            if context_data['mode'] == 'choose':
                (ws / 'out/choice.json').write_text('{}')
                data = json.loads((ws / 'tighten/inputs/regions.json').read_text(encoding='utf-8'))['regions'][0]
                w, h = data['cutout_size']
                row = {'name': 'HEAD', 'action': 'tight', 'box': [int(w*.2), int(h*.2), int(w*.8), int(h*.8)], 'thing': 'a human face', 'confirmed': False}
                target = ws / 'out/tighten.json'
                target.write_text(json.dumps({'schema': 'bti.picks.tighten/1', 'regions': [row]}))
                first_check = check(1)
                assert 'tighten/look/check_' in first_check
                assert 'tighten/out/tighten.json' not in first_check
                row['confirmed'] = True
                target.write_text(json.dumps({'schema': 'bti.picks.tighten/1', 'regions': [row]}))
                assert check(2) is None
                if wrong_path:
                    target.replace(ws / 'tighten/out/tighten.json')
                return SimpleNamespace(status='ok', steps=2, turns=2, repairs=1, elapsed=0)
            moments = [{'id': f'm{i:04}', 'line': b['id'], 'w0': b['w0'], 'w1': b['w1'], 'about': None, 'show': {'whole': True}, 'move': 'hold', 'from': 'whole', 'say': [], 'why': 'Toàn cảnh.'} for i, b in enumerate(beats)]
            if region:
                moments[0]['show'] = {'region': 'HEAD'}
                (ws / 'out/regions.json').write_text(json.dumps({'HEAD': {'box': [.1,.1,.4,.5], 'what': 'a human face'}}))
            if map_view:
                moments[0]['show'] = {'map': {'places': ['Bruges, Belgium', 'Antwerp, Belgium']}, 'else': {'whole': True}}
            visual = {'schema': 'bti.visual/1', 'made_from': context_data['made_from'], 'cast': [], 'wanted': [], 'moments': moments}
            if repair:
                broken = json.loads(json.dumps(visual))
                broken['moments'][0].update(w1=1, about='missing')
                (ws / 'out/visual.json').write_text(json.dumps(broken), encoding='utf-8')
                problem = check(1)
                assert 'word' in problem and 'seconds' in problem and 'cast' in problem
            (ws / 'out/visual.json').write_text(json.dumps(visual), encoding='utf-8')
            assert check(2 if repair else 1) is None
            if stale:
                changed = json.loads((pdir / 'timing.json').read_text(encoding='utf-8'))
                changed['words'][0]['e'] += .1
                (pdir / 'timing.json').write_text(json.dumps(changed), encoding='utf-8')
            return SimpleNamespace(status='ok', steps=2 if repair else 1, turns=2 if repair else 1, repairs=int(repair), elapsed=0)
    monkeypatch.setattr(session, 'agent_module', lambda _: FakeAgent())
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    from bti.draft.guard import Guard
    manager = LongJobManager()
    manager.configure(projects_root=root)
    rec = job.start(pdir.name, pdir, manager=manager, guard_factory=lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), python=sys.executable)
    result = manager.wait(rec['id'], 60)
    if cancel:
        assert result['state'] == 'cancelled' and store.load(pdir) is None
        return
    if stale:
        assert result['state'] == 'error' and store.load(pdir) is None
        return
    assert result['state'] == 'done', result
    assert len(store.load(pdir)['moments']) == len(beats)
    assert all(doc.load(pdir)['beats'][b['id']]['items'] for b in beats)
    if cleanup:
        from bti.ops.log import ChangeLog
        assert 'OBSOLETE' not in doc.load(pdir)['assets']['A']['regions']
        assert any(any(op.get('op') == 'remove_region' and op.get('region') == 'OBSOLETE' for op in row['ops']) for row in ChangeLog(pdir).records('picks'))
    if region:
        assert doc.load(pdir)['assets']['A']['regions']['HEAD']['tight'] is True
    if map_view:
        assert store.load(pdir)['moments'][0]['show']['map']['picture'] in doc.load(pdir)['assets']
        assert doc.load(pdir)['beats'][beats[0]['id']]['items'][0]['role'] == 'map'


@pytest.mark.parametrize("broken_import,web_on,web_finds,by_run", [(False, False, False, False), (True, False, False, False), (False, True, False, False), (False, True, True, False), (False, True, False, True)])
def test_fake_agent_finds_one_picture_and_records_missed_one(tmp_path, monkeypatch, broken_import, web_on, web_finds, by_run):
    from auto_helpers import install_sources, FakeSource, fake_thumb
    from bti.picks import context, doc, websettings
    from bti.picks.auto import session
    from bti.longjob import LongJobManager
    from bti.visual import job, store
    from bti.media import api as media_api
    from bti.draft.guard import Guard
    root = tmp_path / 'projects'
    root.mkdir()
    pdir = make_auto_project(root)
    view = context.narration_view(pdir)
    words, beats = [], []
    for chapter in view['chapters']:
        for line in chapter['beats']:
            start = len(words)
            for word in line['text'].split():
                i = len(words)
                words.append({'w': word, 's': i * .8, 'e': (i + 1) * .8})
            beats.append({'id': line['id'], 'w0': start, 'w1': len(words)})
    (pdir / 'timing.json').write_text(json.dumps({'words': words, 'beats': beats}), encoding='utf-8')
    install_sources(monkeypatch)
    monkeypatch.setitem(media_api._SOURCES, 'wikipedia', FakeSource('wikipedia'))
    monkeypatch.setattr(websettings, 'settings', lambda: {'auto_web_search': 'off', 'auto_web_search_max': 0, 'source': 'default'})
    class FakeAgent:
        def run(self, ws, *, check, **kwargs):
            ctx = json.loads((ws / 'inputs/context.json').read_text(encoding='utf-8'))
            if ctx['mode'] == 'plan':
                moments = [{'id': f'm{i:04}', 'line': b['id'], 'w0': b['w0'], 'w1': b['w1'], 'about': None, 'show': {'whole': True}, 'move': 'hold', 'from': 'whole', 'say': [], 'why': 'Toàn cảnh.'} for i, b in enumerate(beats)]
                for i in range(2):
                    moments[i]['show'] = {'want': f'w{i}', 'else': {'whole': True}}
                cast = [{'id': f's{i}', 'kind': 'idea', 'name': f'Subject {i}', 'also': [], 'strip': False, 'sub': '', 'shown_by': []} for i in range(2)]
                wants = [{'id': f'w{i}', 'subject': f's{i}', 'kind': 'portrait', 'search': text, 'alt': (['missing city view'] if i == 1 else []), 'period': 'then', 'status': 'open', 'picture': None, 'tried': []} for i, text in enumerate(['portrait', 'nothing exists'])]
                out = {'schema': 'bti.visual/1', 'made_from': ctx['made_from'], 'cast': cast, 'wanted': wants, 'moments': moments}
                (ws / 'out/visual.json').write_text(json.dumps(out), encoding='utf-8')
            else:
                search_view = json.loads((ws / 'inputs/search.json').read_text())
                if set(search_view['wants']) == {'w1'}:
                    out = {'w1': {'pick': 1, 'caption': 'Another historical portrait', 'shows': ['s1'], 'period': None}}
                else:
                    out = {'w0': {'pick': 1, 'caption': 'A historical portrait', 'shows': ['s0'], 'period': 'then'}, 'w1': {'pick': None}}
                (ws / 'out/choice.json').write_text(json.dumps(out), encoding='utf-8')
            assert check(1) is None
            return SimpleNamespace(status='ok', steps=1, turns=1, repairs=0, elapsed=0)
    monkeypatch.setattr(session, 'agent_module', lambda _: FakeAgent())
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    if broken_import:
        from bti.picks.auto import write
        from bti.ops import OpError
        original_send = write.Writer.send
        def fail_import(self, ops, note):
            if any(op['op'] == 'import' for op in ops):
                raise OpError('import_failed', 'failed to download')
            return original_send(self, ops, note)
        monkeypatch.setattr(write.Writer, 'send', fail_import)
    manager = LongJobManager()
    manager.configure(projects_root=root)
    web_queries = []
    def fake_web(project, query, limit):
        web_queries.append(query)
        if web_finds and query == 'missing city view':
            from auto_helpers import meta
            item = meta('commons', 'File:Portrait A.jpg', 'Another portrait', 'unused')
            return {'items': [item], 'errors': []}
        return {'items': [], 'errors': []}
    rec = job.start(pdir.name, pdir, manager=manager, guard_factory=lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), python=sys.executable, fetch_thumb=fake_thumb, web={'on': web_on, 'max': 10, 'search': fake_web}, by_run=by_run)
    web_on = web_on and not by_run
    result = manager.wait(rec['id'], 60)
    assert bool(web_queries) == web_on
    if web_on:
        assert 'missing city view' in web_queries
    assert result['state'] == 'done', result
    if web_on:
        assert [part['key'] for part in result['parts']] == ['plan', 'search', 'choose', 'web', 'choose2', 'write']
    visual = store.load(pdir)
    assert visual['wanted'][0]['status'] == ('none' if broken_import else 'found')
    assert visual['wanted'][1]['status'] == ('found' if web_finds else 'none')
    if web_finds:
        assert 'missing city view' in visual['wanted'][1]['tried']
        first_key, second_key = [w['picture'] for w in visual['wanted']]
        assert first_key == second_key
        assert set(doc.load(pdir)['assets'][first_key]['shows']) == {'s0', 's1'}
        assert doc.load(pdir)['assets'][first_key]['period'] == 'then'
        return
    assert 'missing city view' in visual['wanted'][1]['tried'] and any('nothing exists' in x for x in result['result']['missing'])
    from bti.editor.state_api import build_state
    state = build_state(root, pdir.name, longjobs=manager)
    assert any('missing city view' in sentence for sentence in state['visual_missing'])
    from bti.cli.render import status_text
    assert any('missing city view' in line for line in status_text(state))
    picks = doc.load(pdir)
    if broken_import:
        assert visual['wanted'][0]['picture'] is None
        return
    assert picks['assets'][visual['wanted'][0]['picture']]['caption'] == 'A historical portrait'
    assert picks['beats'][beats[1]['id']]['missing'][0]['queries']
    before_assets = set(picks['assets'])
    again = job.start(pdir.name, pdir, manager=manager, guard_factory=lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), python=sys.executable, fetch_thumb=fake_thumb)
    second = manager.wait(again['id'], 60)
    assert second['state'] == 'done', second
    assert before_assets <= set(doc.load(pdir)['assets'])
    assert len(store.load(pdir)['wanted']) == 2


def test_session_refusal_preserves_its_error_code(tmp_path, monkeypatch):
    from bti.draft.inputs import DraftError
    from bti.picks.auto import session
    from bti.longjob import LongJobManager
    from bti.visual import job
    root = tmp_path / 'projects'
    root.mkdir()
    pdir = make_auto_project(root)
    from bti.picks import context
    words, beats = [], []
    for chapter in context.narration_view(pdir)['chapters']:
        for line in chapter['beats']:
            start = len(words)
            for word in line['text'].split():
                i = len(words)
                words.append({'w': word, 's': i * .8, 'e': (i + 1) * .8})
            beats.append({'id': line['id'], 'w0': start, 'w1': len(words)})
    (pdir / 'timing.json').write_text(json.dumps({'words': words, 'beats': beats}), encoding='utf-8')
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    def refuse(*args, **kwargs):
        raise DraftError('agy_auth', 'sign in required')
    monkeypatch.setattr(session, 'run_session', refuse)
    manager = LongJobManager()
    manager.configure(projects_root=root)
    rec = job.start(pdir.name, pdir, manager=manager)
    result = manager.wait(rec['id'], 60)
    assert result['state'] == 'error' and result['error_code'] == 'agy_auth'


def test_visual_plan_refuses_when_another_agent_is_running(tmp_path, monkeypatch):
    from bti.picks.auto import session
    from bti.picks.auto.inputs import AutoError
    from bti.visual import job
    root = tmp_path / 'projects'
    root.mkdir()
    pdir = make_auto_project(root)
    (pdir / 'timing.json').write_text(json.dumps({'words': [], 'beats': []}), encoding='utf-8')
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    class Manager:
        def active(self, pid, kind):
            return {'id': '1234567890abcdef', 'kind': kind} if kind == 'draft' else None
    with pytest.raises(AutoError) as exc:
        job.start(pdir.name, pdir, manager=Manager())
    assert exc.value.code == 'agent_job_running'
    assert exc.value.extra['job_id'] == '1234567890abcdef'


def test_visual_plan_removes_old_narration_lines_first_and_undoes_in_one_batch(tmp_path, monkeypatch):
    from bti.picks import context, doc
    from bti.picks.auto import session
    from bti.picks.auto.write import Writer
    from bti.longjob import LongJobManager
    from bti.visual import job, store
    from bti.draft.guard import Guard
    from bti.script import store as sstore
    from bti.script.store import Beat, NChapter, Narration
    from bti.ops.adapters import PicksAdapter
    from bti.ops.log import ChangeLog
    from bti.ops.runner import run_undo
    root = tmp_path / 'projects'
    root.mkdir()
    pdir = make_auto_project(root)
    old_beats = context.narration_view(pdir)['beat_ids']
    writer = Writer(pdir, 'agent:old', redo=True)
    writer.send([
        {'op': 'set_region', 'asset': 'A', 'region': 'OLD_REG', 'x': 20, 'y': 20},
        {'op': 'set_subjects', 'subjects': [{'id': 'old_subj', 'kind': 'person', 'name': 'Old Person', 'also': [], 'strip': True, 'sub': '', 'where': {'region': 'OLD_REG'}}]},
        {'op': 'set_picks', 'beat': old_beats[0], 'items': [{'asset': 'A', 'region': 'OLD_REG', 'role': 'detail'}],
         'names': [{'name': 'Old Person', 'also': [], 'line': old_beats[0], 'where': {'region': 'OLD_REG'}, 'sure': True, 'words': ''}]},
        {'op': 'set_about', 'beat': old_beats[0], 'about': [{'id': 'old_subj', 'words': 'Old Person'}]},
        *[{'op': 'set_picks', 'beat': bid, 'items': [{'asset': 'A', 'region': None, 'role': 'main'}]} for bid in old_beats[1:]],
    ], 'narration A picks')
    old_picks_snapshot = doc.load(pdir)

    # Rewrite narration to B with brand-new line ids and new timing.
    n_b = Narration('t1', 'The Test Painting', 'en')
    ch = NChapter('c01', 'cold_open', 'COLD OPEN', False)
    ch.beats = [
        Beat('b0264', 'Giovanni Arnolfini wears a dark cloak here.', ['f01'], ['the cloak']),
        Beat('b0265', 'The mirror hangs behind them on the wall.', ['f01'], ['the mirror']),
    ]
    n_b.chapters = [ch]
    sstore.save_narration(pdir, n_b)
    sstore.approve(pdir, 'narration', n_b.rev())
    words, beats = [], []
    for line in ch.beats:
        start = len(words)
        for w in line.text.split():
            i = len(words)
            words.append({'w': w, 's': i * .8, 'e': (i + 1) * .8})
        beats.append({'id': line.id, 'w0': start, 'w1': len(words)})
    (pdir / 'timing.json').write_text(json.dumps({'words': words, 'beats': beats}), encoding='utf-8')

    class FakeAgent:
        def run(self, ws, *, check, **kwargs):
            ctx = json.loads((ws / 'inputs/context.json').read_text(encoding='utf-8'))
            if ctx['mode'] == 'choose':
                (ws / 'out/choice.json').write_text('{}')
                data = json.loads((ws / 'tighten/inputs/regions.json').read_text(encoding='utf-8'))['regions'][0]
                w, h = data['cutout_size']
                row = {'name': 'CLOAK', 'action': 'tight', 'box': [int(w * .2), int(h * .2), int(w * .8), int(h * .8)], 'thing': 'a dark cloak', 'confirmed': False}
                target = ws / 'out/tighten.json'
                target.write_text(json.dumps({'schema': 'bti.picks.tighten/1', 'regions': [row]}))
                assert 'tighten/look/check_' in check(1)
                row['confirmed'] = True
                target.write_text(json.dumps({'schema': 'bti.picks.tighten/1', 'regions': [row]}))
                assert check(2) is None
                return SimpleNamespace(status='ok', steps=2, turns=2, repairs=1, elapsed=0)
            (ws / 'out/regions.json').write_text(json.dumps({'CLOAK': {'box': [.1, .1, .4, .5], 'what': 'dark cloak'}}))
            visual = {
                'schema': 'bti.visual/1', 'made_from': ctx['made_from'],
                'cast': [{'id': 'giovanni', 'kind': 'person', 'name': 'Giovanni Arnolfini', 'also': [], 'strip': True, 'sub': '', 'shown_by': [{'region': 'CLOAK'}]}],
                'wanted': [],
                'moments': [
                    {'id': 'm0001', 'line': 'b0264', 'w0': beats[0]['w0'], 'w1': beats[0]['w1'], 'about': 'giovanni', 'show': {'region': 'CLOAK'}, 'move': 'hold', 'from': 'whole', 'say': [{'intro': 'giovanni', 'word': 0}], 'why': 'Giới thiệu.'},
                    {'id': 'm0002', 'line': 'b0265', 'w0': beats[1]['w0'], 'w1': beats[1]['w1'], 'about': None, 'show': {'whole': True}, 'move': 'hold', 'from': 'whole', 'say': [], 'why': 'Toàn cảnh.'},
                ],
            }
            (ws / 'out/visual.json').write_text(json.dumps(visual), encoding='utf-8')
            assert check(1) is None
            return SimpleNamespace(status='ok', steps=1, turns=1, repairs=0, elapsed=0)

    monkeypatch.setattr(session, 'agent_module', lambda _: FakeAgent())
    monkeypatch.setattr(session, 'check_installed', lambda _: None)
    manager = LongJobManager()
    manager.configure(projects_root=root)
    rec = job.start(pdir.name, pdir, manager=manager, guard_factory=lambda d: Guard(d, extra=lambda: None, repo_root=d.parent), python=sys.executable)
    result = manager.wait(rec['id'], 60)
    assert result['state'] == 'done', result

    after_picks = doc.load(pdir)
    assert set(after_picks['beats']) == {'b0264', 'b0265'}
    assert after_picks.get('names', []) == []
    assert [s['id'] for s in after_picks['subjects']] == ['giovanni']
    assert 'OLD_REG' not in after_picks['assets']['A']['regions']

    records = ChangeLog(pdir).records('picks')
    latest = records[-1]
    assert latest['ops'][0] == {'op': 'remove_stale_beats'}
    assert any(op.get('op') == 'set_subjects' for op in latest['ops'])
    assert {op.get('beat') for op in latest['ops'] if op.get('op') == 'set_picks'} == {'b0264', 'b0265'}

    undo_res = run_undo({'picks': PicksAdapter(pdir)}, latest['batch'], {'base_rev': doc.revision(after_picks), 'actor': 'human', 'note': 'undo'}, ChangeLog(pdir))
    assert undo_res['applied'] == 1
    restored = doc.load(pdir)
    assert set(restored['beats']) == set(old_beats)
    assert restored['subjects'] == old_picks_snapshot['subjects']
    assert restored['names'] == old_picks_snapshot['names']
    assert 'OLD_REG' in restored['assets']['A']['regions']
