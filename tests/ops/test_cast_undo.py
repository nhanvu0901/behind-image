from bti.ops import things, undo


def test_cast_entries_are_tracked_and_undone_as_one_list():
    before = {'main_asset': 'A', 'assets': {}, 'beats': {}, 'names': [
        {'name': 'Other', 'line': 'b0002', 'also': [], 'where': {'region': 'B'}, 'sure': True, 'words': ''}]}
    after = {**before, 'names': before['names'] + [
        {'name': 'Costanza', 'line': 'b0001', 'also': [], 'where': {'region': 'HEAD'}, 'sure': True, 'words': ''}]}
    keys = things.changed_keys('picks', before, after)
    assert keys == ['names']
    restored = undo.restore_picks(after, before, keys)
    assert restored['names'] == before['names']


def test_cast_change_conflicts_with_later_change_to_same_line():
    before = {'assets': {}, 'beats': {}, 'names': []}
    after = {**before, 'names': [{'name': 'One', 'line': 'b0001'}]}
    current = {**before, 'names': [{'name': 'Two', 'line': 'b0001'}]}
    keys, conflicts = undo.find_conflicts('picks', current, before, after, [])
    assert keys == ['names'] and conflicts[0]['key'] == 'names'


def test_logged_cast_updates_and_undo_preserve_other_lines(client):
    from ops_helpers import pk, pk_rev, read_json
    from test_undo_log import undo
    cast1 = {'name': 'Costanza', 'also': [], 'line': 'b0001', 'where': {'region': 'HEAD'}, 'sure': True, 'words': ''}
    cast2 = {'name': 'Martha', 'also': [], 'line': 'b0003', 'where': {'asset': 'B'}, 'sure': True, 'words': ''}
    a = pk(client, [{'op': 'set_picks', 'beat': 'b0001', 'items': [{'asset': 'A', 'region': 'HEAD'}], 'names': [cast1]}])
    assert a.status_code == 200, a.text
    b = pk(client, [{'op': 'set_picks', 'beat': 'b0003', 'items': [{'asset': 'B'}], 'names': [cast2]}])
    assert b.status_code == 200, b.text
    assert read_json(client.pdir / 'picks.json')['names'] == [cast1, cast2]
    result = undo(client, 'pk', b.json()['batch'], rev=pk_rev(client))
    assert result.status_code == 200, result.text
    assert read_json(client.pdir / 'picks.json')['names'] == [cast1]
