from bti.visual.job import search_requests, apply_choices, missing_sentences


def test_search_is_once_per_wanted_even_if_pool_already_has_it():
    doc = {'cast': [{'id': 'city', 'name': 'Bruges'}], 'wanted': [{'id': 'w1', 'subject': 'city', 'kind': 'place', 'search': 'Bruges old view', 'alt': ['Bruges engraving'], 'period': 'then'}], 'moments': [{'line': 'b0001', 'show': {'want': 'w1', 'else': {'whole': True}}}, {'line': 'b0002', 'show': {'want': 'w1', 'else': {'whole': True}}}]}
    wants = search_requests(doc)
    assert len(wants) == 1 and wants[0]['search'] == 'Bruges old view' and wants[0]['alt'] == ['Bruges engraving']


def test_choice_found_and_missing_record_searches():
    doc = {'wanted': [{'id': 'w1', 'subject': 'a', 'search': 'castle'}, {'id': 'w2', 'subject': 'b', 'search': 'town'}]}
    found = {'w1': {'status': 'found', 'picture': 'B'}, 'w2': {'status': 'none'}}
    search = {'wants': {'w1': {'tried_queries': ['castle']}, 'w2': {'tried_queries': ['town', 'old town']}}}
    out = apply_choices(doc, found, search)
    assert out['wanted'][0]['picture'] == 'B' and out['wanted'][0]['status'] == 'found'
    assert out['wanted'][1]['picture'] is None and out['wanted'][1]['tried'] == ['town', 'old town']
    assert 'town' in missing_sentences(out)[0] and 'old town' in missing_sentences(out)[0]


def test_choice_validation_requires_known_candidate_and_metadata():
    from bti.visual.job import choice_errors
    visual = {'cast': [{'id': 'a'}], 'wanted': [{'id': 'w1'}]}
    search = {'wants': {'w1': {'candidates': [{'n': 1}]}}}
    assert choice_errors({'w1': {'pick': 9, 'caption': '', 'shows': ['missing'], 'period': 'then'}}, visual, search)
    assert not choice_errors({'w1': {'pick': 1, 'caption': 'The old town', 'shows': ['a'], 'period': 'then'}}, visual, search)
    assert not choice_errors({'w1': {'pick': None}}, visual, search)


def test_maps_create_osm_requests_and_attach_found_key():
    from bti.visual.job import map_requests, apply_maps
    doc = {'moments': [{'id': 'm1', 'line': 'b0001', 'show': {'map': {'places': ['Lucca, Italy', 'Bruges, Belgium']}, 'else': {'whole': True}}}]}
    req = map_requests(doc)
    assert req[0]['type'] == 'map' and req[0]['places'] == ['Lucca, Italy', 'Bruges, Belgium']
    out = apply_maps(doc, {req[0]['id']: 'MAP1'})
    assert out['moments'][0]['show']['map']['picture'] == 'MAP1'
    assert 'picture' not in doc['moments'][0]['show']['map']


def test_missing_concrete_subject_records_why_fallback_is_used():
    doc = {'wanted': [{'id': 'w', 'subject': 'person', 'search': 'portrait'}], 'moments': [{'about': 'person', 'show': {'want': 'w', 'else': {'whole': True}}}]}
    resolved = apply_choices(doc, {'w': {'status': 'none'}}, {'wants': {'w': {'tried_queries': ['portrait']}}})
    assert resolved['moments'][0]['about_not_shown']


def test_missing_sentence_does_not_claim_a_failed_download_was_not_found():
    rows = missing_sentences({'wanted': [{'id': 'w', 'status': 'none', 'search': 'portrait', 'tried': ['portrait']}]})
    assert 'Chưa có hình dùng được' in rows[0]


def test_missing_fallback_reason_is_true_after_an_import_failure():
    doc = {'wanted': [{'id': 'w', 'subject': 'p', 'search': 'portrait'}], 'moments': [{'about': 'p', 'show': {'want': 'w', 'else': {'whole': True}}}]}
    out = apply_choices(doc, {'w': {'status': 'none'}}, {'wants': {}})
    assert 'chưa có hình dùng được' in out['moments'][0]['about_not_shown'].lower()


def test_missing_want_does_not_claim_subject_is_hidden_if_other_pair_picture_shows_it():
    doc = {'cast': [{'id': 'p', 'shown_by': [{'picture': 'B'}]}],
           'wanted': [{'id': 'w', 'subject': 'p', 'search': 'portrait'}],
           'moments': [{'about': 'p', 'show': {'pair': [{'picture': 'B'}, {'want': 'w', 'else': {'whole': True}}]}}]}
    out = apply_choices(doc, {'w': {'status': 'none'}}, {'wants': {}})
    assert 'about_not_shown' not in out['moments'][0]
