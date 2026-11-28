from bti.visual.review import review_and_repair


def row(sid, moment, words):
    return {'id': sid, 'moment': moment, 'words': words}


def test_clean_review_needs_no_edits():
    rows = [row('s1', 'm1', 'words')]
    result = review_and_repair(lambda: rows, lambda ids: {'shots': [{'id': 's1', 'problems': []}]},
                               lambda *a: (_ for _ in ()).throw(AssertionError('unexpected edit')))
    assert result['rounds'] == 0 and result['warnings'] == []


def test_findings_grouped_once_and_only_changed_shots_reviewed():
    rows = [row('s1', 'm1', 'first'), row('s2', 'm2', 'second')]
    seen, edits = [], []
    def review(ids):
        seen.append(ids)
        return {'shots': [{'id': s, 'problems': ([{'code': 'picture_mismatch', 'detail': 'wrong city'}] if len(seen) == 1 and s == 's1' else [])} for s in ids]}
    def edit(ids, instruction):
        edits.append((ids, instruction)); return {'changed': ['s1'], 'missing': {}}
    result = review_and_repair(lambda: rows, review, edit)
    assert seen == [['s1', 's2'], ['s1']]
    assert len(edits) == 1 and edits[0][0] == ['m1'] and 'wrong city' in edits[0][1]
    assert result['rounds'] == 1 and result['warnings'] == []


def test_missing_picture_reported_once_without_retry():
    rows = [row('s1', 'm1', 'the city')]
    calls = []
    def review(ids):
        calls.append(ids)
        return {'shots': [{'id': 's1', 'problems': [{'code': 'picture_mismatch', 'detail': 'city'}]}]}
    def edit(ids, instruction):
        return {'changed': ['s1'], 'missing': {'m1': 'Bruges'}}
    result = review_and_repair(lambda: rows, review, edit)
    assert len(calls) == 1 and result['rounds'] == 1
    assert len(result['warnings']) == 1 and 'Bruges' in result['warnings'][0]['message']


def test_short_answer_asks_again_for_missing_shot(tmp_path):
    import json
    from types import SimpleNamespace
    from bti.visual.review import run_model_review
    rows = [row('s1', 'm1', 'one'), row('s2', 'm2', 'two')]
    class Provider:
        def __init__(self): self.calls = []
        def run(self, ws, **kw):
            requested = json.loads((ws / 'shots.json').read_text(encoding='utf-8'))
            self.calls.append([r['id'] for r in requested])
            chosen = requested[:1]
            (ws / 'out/review.json').write_text(json.dumps({'shots': [{'id': r['id'], 'problems': []} for r in chosen]}))
            return SimpleNamespace(status='ok')
    provider = Provider()
    answer = run_model_review(tmp_path, rows, provider=provider, model='fake')
    assert provider.calls == [['s1', 's2'], ['s2']]
    assert answer['incomplete'] == 0 and len(answer['shots']) == 2


def test_two_repairs_max_and_remaining_finding_keeps_words():
    rows = [row('s1', 'm1', 'spoken words')]
    reviews, edits = [], []
    def review(ids):
        reviews.append(ids)
        return {'shots': [{'id': 's1', 'problems': [{'code': 'text_wrong', 'detail': 'Tên sai'}]}]}
    def edit(ids, instruction):
        edits.append(ids); return {'changed': ['s1'], 'missing': {}}
    result = review_and_repair(lambda: rows, review, edit)
    assert len(reviews) == 3 and len(edits) == 2
    assert result['warnings'][0]['words'] == 'spoken words' and 'Tên sai' in result['warnings'][0]['message']


def test_replaced_shot_does_not_leave_old_finding():
    rows = [row('s1', 'm1', 'words')]
    def review(ids):
        return {'shots': [{'id': sid, 'problems': ([{'code': 'context_missing', 'detail': 'Thiếu'}] if sid == 's1' else [])} for sid in ids]}
    def edit(ids, instruction):
        rows[:] = [row('s2', 'm1', 'words')]
        return {'changed': ['s2'], 'missing': {}}
    assert review_and_repair(lambda: rows, review, edit)['warnings'] == []


def test_sheets_show_one_mark_timed_frame_and_moment_context(tmp_path):
    import numpy as np
    from bti.visual.review import prepare_sheets
    class Project:
        def timing(self): return {'words': [{'w': 'city', 's': 1.2, 'e': 1.8}]}
        def resolve(self): return {'shots': [{'id': 's1', 'moment': 'm1', '_t0': 0, '_t1': 4, 'overlays': [{'technique': 'HI-01', '_t0': 1}]}]}
        def frame_at(self, t, width):
            assert t == 2.3
            return np.zeros((360, 640, 3), dtype=np.uint8)
    visual = {'moments': [{'id': 'm1', 'about': 'city', 'why': 'Cho thấy thành phố.'}], 'cast': [{'id': 'city', 'name': 'Bruges'}]}
    rows, sheets = prepare_sheets(Project(), visual, {'compose_notes': [{'moment': 'm1', 'what': 'note'}]}, tmp_path)
    assert rows[0]['about'] == 'Bruges' and rows[0]['words'] == 'city'
    assert rows[0]['why'] == 'Cho thấy thành phố.' and rows[0]['compose_notes'][0]['what'] == 'note'
    assert len(rows[0]['frames']) == 1 and sheets[0].is_file()


def test_sample_stays_inside_short_mark():
    from bti.visual.review import sample_time
    shot = {'overlays': [{'technique': 'HI-01', '_t0': 1.0, '_t1': 1.5}]}
    assert 1.0 < sample_time(shot, 0.0, 4.0) < 1.5


def test_changed_shots_includes_previous_shot_when_its_end_moves():
    from bti.visual.review import changed_shots
    before = [{'id': 's1', '_t0': 0, '_t1': 3}, {'id': 's2', '_t0': 3, '_t1': 8}]
    after = [{'id': 's1', '_t0': 0, '_t1': 4}, {'id': 's2', '_t0': 4, '_t1': 8}]
    assert changed_shots(before, after) == ['s1', 's2']


def test_missing_picture_does_not_retry_replacement_shot():
    rows = [row('s1', 'm1', 'city')]
    reviews = []
    def review(ids):
        reviews.append(ids)
        return {'shots': [{'id': sid, 'problems': [{'code': 'picture_mismatch', 'detail': 'Thành phố'}]} for sid in ids]}
    def edit(ids, instruction):
        rows[:] = [row('s2', 'm1b', 'city')]
        return {'changed': ['s2'], 'missing': {'m1': 'Bruges', 'm1b': 'Bruges'}}
    result = review_and_repair(lambda: rows, review, edit)
    assert reviews == [['s1']]
    assert len(result['warnings']) == 1 and 'Bruges' in result['warnings'][0]['message']


def test_approval_only_change_does_not_invalidate_review(tmp_path):
    import json
    from bti.draft.review import _input_signature
    (tmp_path / 'timing.json').write_text('{}', encoding='utf8')
    picks = {'schema': 'bti.picks/1', 'main_asset': None, 'assets': {}, 'beats': {}, 'approval': {'approved': False}}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf8')
    before = _input_signature(tmp_path)
    picks['approval'] = {'approved': True, 'sha1': 'same-content', 'approved_at': 'now'}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf8')
    assert _input_signature(tmp_path) == before
    picks['beats']['b1'] = {'items': []}
    (tmp_path / 'picks.json').write_text(json.dumps(picks), encoding='utf8')
    assert _input_signature(tmp_path) != before


def test_prepare_sheets_ignores_moments_from_old_narration_lines(tmp_path):
    import numpy as np
    from bti.visual.review import prepare_sheets
    class Project:
        def timing(self):
            return {'words': [{'w': 'city', 's': 1.2, 'e': 1.8}], 'beats': [{'id': 'b_new', 'w0': 0, 'w1': 1}]}
        def resolve(self):
            return {'shots': [{'id': 's1', 'moment': 'm_old', '_t0': 0, '_t1': 4, 'overlays': []}]}
        def frame_at(self, t, width):
            return np.zeros((360, 640, 3), dtype=np.uint8)
    visual = {'moments': [{'id': 'm_old', 'line': 'b_old', 'about': 'old_cast', 'why': 'Cũ.'}],
              'cast': [{'id': 'old_cast', 'name': 'Old Name'}]}
    rows, _ = prepare_sheets(Project(), visual, {'compose_notes': [{'moment': 'm_old', 'what': 'note'}]}, tmp_path)
    assert rows[0]['about'] is None and rows[0]['why'] is None
