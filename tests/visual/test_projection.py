from bti.visual.projection import project


def test_projection_keeps_each_moment_picture_and_subject_in_spoken_order():
    visual = {'cast': [{'id': 'p', 'kind': 'person', 'name': 'Ada', 'also': [], 'strip': True, 'sub': 'a mathematician', 'shown_by': [{'region': 'FACE'}, {'picture': 'B'}]}],
              'wanted': [{'id': 'w1', 'subject': 'p', 'status': 'found', 'picture': 'B'}],
              'moments': [{'line': 'b1', 'w0': 0, 'w1': 2, 'about': 'p', 'show': {'region': 'FACE'}, 'why': 'Khuôn mặt.'},
                          {'line': 'b1', 'w0': 2, 'w1': 4, 'about': 'p', 'show': {'want': 'w1', 'else': {'whole': True}}, 'why': 'Chân dung.'}]}
    timing = {'words': [{'w': w} for w in ['Ada', 'was', 'a', 'mathematician']]}
    out = project(visual, timing, 'A')
    assert out['subjects'][0]['where'] == [{'region': 'FACE'}, {'asset': 'B'}]
    assert out['lines'][0]['items'] == [{'asset': 'A', 'region': 'FACE', 'role': 'detail'}, {'asset': 'B', 'region': None, 'role': 'context'}]
    assert out['lines'][0]['about'][0] == {'id': 'p', 'words': 'Ada was'}
    assert out['lines'][0]['kinds'] == ['detail', 'outside']


def test_unfound_want_uses_fallback_and_records_every_query():
    doc = {'cast': [], 'wanted': [{'id': 'w', 'subject': 'x', 'status': 'none', 'picture': None, 'tried': ['first', 'second'], 'search': 'first'}],
           'moments': [{'line': 'b1', 'w0': 0, 'w1': 1, 'about': None, 'show': {'want': 'w', 'else': {'region': 'SKY'}}, 'why': 'Bầu trời.'}]}
    line = project(doc, {'words': [{'w': 'sky'}]}, 'A')['lines'][0]
    assert line['items'][0]['region'] == 'SKY'
    assert line['missing'][0]['queries'] == ['first', 'second']


def test_map_uses_imported_map_or_its_fallback():
    doc = {'cast': [], 'wanted': [], 'moments': [{'line': 'b1', 'w0': 0, 'w1': 1, 'about': None, 'show': {'map': {'places': ['A', 'B'], 'picture': 'M'}, 'else': {'region': 'SKY'}}, 'why': 'Bản đồ.'}]}
    timing = {'words': [{'w': 'journey'}]}
    line = project(doc, timing, 'A')['lines'][0]
    assert line['items'] == [{'asset': 'M', 'region': None, 'role': 'map'}]
    del doc['moments'][0]['show']['map']['picture']
    assert project(doc, timing, 'A')['lines'][0]['items'][0]['region'] == 'SKY'


def test_projection_operations_replace_subjects_and_each_line():
    from bti.visual.projection import operations
    projected = {'subjects': [{'id': 'p', 'kind': 'person', 'name': 'Ada', 'strip': True, 'where': {'region': 'FACE'}}],
                 'lines': [{'beat': 'b0001', 'items': [{'asset': 'A', 'region': 'FACE', 'role': 'detail'}], 'about': [{'id': 'p', 'words': 'Ada'}], 'kinds': ['detail'], 'missing': [], 'reason': 'Khuôn mặt.'}]}
    ops = operations(projected)
    assert [x['op'] for x in ops] == ['set_subjects', 'set_picks', 'set_about']
    assert ops[1]['items'] == projected['lines'][0]['items'] and ops[2]['about'] == projected['lines'][0]['about']


def test_projection_limits_legacy_queries_without_changing_visual():
    doc = {'cast': [], 'wanted': [{'id': 'w', 'subject': 'x', 'status': 'none', 'picture': None, 'tried': ['one', 'two', 'three', 'four', 'five'], 'search': 'one'}],
           'moments': [{'line': 'b0001', 'w0': 0, 'w1': 1, 'about': None, 'show': {'want': 'w', 'else': {'whole': True}}, 'why': 'Toàn cảnh.'}]}
    line = project(doc, {'words': [{'w': 'word'}]}, 'A')['lines'][0]
    assert line['missing'][0]['queries'] == ['one', 'two', 'three', 'four']
    assert len(doc['wanted'][0]['tried']) == 5


def test_projection_adds_found_wanted_pictures_to_subject_depictions():
    doc = {'cast': [{'id': 'p', 'kind': 'person', 'name': 'Ada', 'also': [], 'strip': True, 'sub': '', 'shown_by': [{'region': 'FACE'}]}],
           'wanted': [{'id': 'w', 'subject': 'p', 'status': 'found', 'picture': 'B'}], 'moments': []}
    subject = project(doc, {'words': []}, 'A')['subjects'][0]
    assert subject['where'] == [{'region': 'FACE'}, {'asset': 'B'}]


def test_projection_preserves_non_adjacent_repeated_picture_order():
    doc = {'cast': [], 'wanted': [], 'moments': [
        {'line': 'b0001', 'w0': i, 'w1': i + 1, 'about': None, 'show': show, 'why': 'Hình.'}
        for i, show in enumerate([{'picture': 'B'}, {'picture': 'C'}, {'picture': 'B'}])]}
    line = project(doc, {'words': [{'w': 'x'}] * 3}, 'A')['lines'][0]
    assert [item['asset'] for item in line['items']] == ['B', 'C', 'B']


def test_pair_with_missing_want_uses_its_explicit_fallback():
    doc = {'cast': [], 'wanted': [{'id': 'w', 'subject': 'x', 'status': 'none', 'picture': None, 'tried': [], 'search': 'x'}],
           'moments': [{'line': 'b0001', 'w0': 0, 'w1': 1, 'about': None, 'show': {'pair': [{'picture': 'B'}, {'want': 'w', 'else': {'region': 'FACE'}}]}, 'why': 'So sánh.'}]}
    line = project(doc, {'words': [{'w': 'word'}]}, 'A')['lines'][0]
    assert [(x['asset'], x['region']) for x in line['items']] == [('B', None), ('A', 'FACE')]
    assert line['missing'][0]['what'] == 'x'
