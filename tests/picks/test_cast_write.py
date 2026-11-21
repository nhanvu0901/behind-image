from bti.picks.auto import write


def test_resolve_cast_replaces_want_with_imported_asset_and_renamed_region():
    plan = {'names': [
        {'name': 'Costanza Trenta', 'also': ['Costanza'], 'line': 'b0001', 'where': {'region': 'HEAD'}, 'sure': False, 'words': 'most often named'},
        {'name': 'Saint Martha', 'also': [], 'line': 'b0002', 'where': {'want': 'b0002.1'}, 'sure': False, 'words': 'some historians see'},
        {'name': 'Missing Person', 'also': [], 'line': 'b0003', 'where': {'want': 'b0003.1'}, 'sure': True, 'words': ''}]}
    picks = {'b0002.1': {'pick': {'source': 'commons', 'source_id': 'martha'}}, 'b0003.1': {'pick': None}}
    rows = write.resolve_names(plan, picks, {('commons', 'martha'): 'picture_martha'}, {'HEAD': 'HEAD_2'}, set())
    assert [r['where'] for r in rows] == [{'region': 'HEAD_2'}, {'asset': 'picture_martha'}]
    assert [r['name'] for r in rows] == ['Costanza Trenta', 'Saint Martha']


def test_resolve_cast_omits_a_dropped_region():
    plan = {'names': [{'name': 'Costanza', 'also': [], 'line': 'b0001', 'where': {'region': 'HEAD'}, 'sure': True, 'words': ''}]}
    assert write.resolve_names(plan, {}, {}, {}, {'HEAD'}) == []
