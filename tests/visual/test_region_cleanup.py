from bti.visual.regions import cleanup_names, region_references


def test_references_include_nested_visual_and_locked_storyboard():
    visual = {'cast': [{'shown_by': [{'region': 'CAST'}]}], 'moments': [{'show': {'want': 'x', 'else': {'region': 'FALLBACK'}}, 'say': [{'point': [{'region': 'POINT'}]}]}]}
    storyboard = {'shots': [{'locked': True, 'params': {'at': 'LOCKED'}}, {'source': 'human', 'slots': {'image': {'asset': 'A', 'region': 'HAND'}}}, {'source': 'agent', 'params': {'at': 'OLD'}}]}
    assert region_references(visual, storyboard, {'CAST', 'FALLBACK', 'POINT', 'LOCKED', 'HAND', 'OLD'}) == {'CAST', 'FALLBACK', 'POINT', 'LOCKED', 'HAND'}


def test_cleanup_only_removes_proven_agent_regions_not_referenced():
    regions = {'USED': {}, 'OLD': {}, 'HUMAN': {}, 'UNKNOWN': {}, 'LOCKED': {}}
    visual = {'moments': [{'show': {'region': 'USED'}}]}
    storyboard = {'shots': [{'locked': True, 'params': {'at': 'LOCKED'}}]}
    assert cleanup_names(regions, visual, storyboard, {'USED', 'OLD', 'LOCKED'}) == {'OLD'}


def test_batch_removes_before_add_and_rewrites_references_once():
    from bti.visual.regions import replacement_batch
    current = {'beats': {'b1': {'items': [{'asset': 'A', 'region': 'OLD'}]}, 'b2': {'items': [{'asset': 'A', 'region': 'KEEP'}]}}}
    projected = [{'op': 'set_subjects', 'subjects': []}, {'op': 'set_picks', 'beat': 'b1', 'items': [{'asset': 'A', 'region': 'NEW'}]}, {'op': 'set_about', 'beat': 'b1', 'about': []}, {'op': 'set_picks', 'beat': 'b2', 'items': [{'asset': 'A'}]}]
    batch, rest = replacement_batch(current, 'A', {'OLD'}, [{'op': 'set_region', 'asset': 'A', 'region': 'NEW', 'x': 1, 'y': 1}], projected)
    assert [o['op'] for o in batch] == ['remove_region', 'set_region', 'set_subjects', 'set_picks', 'set_about']
    assert rest == [projected[-1]]


def test_provenance_discards_unlogged_edits_and_missing_history():
    from bti.visual.regions import agent_regions
    def snapshot(value):
        return {'assets': {'A': {'regions': value}}}
    class Log:
        def records(self, doc):
            return [{'batch': 'one', 'actor': 'agent:test', 'touched': ['regions:A']}, {'batch': 'two', 'actor': 'agent:test', 'touched': ['regions:A']}]
        def copies(self, batch):
            if batch == 'one':
                return snapshot({}), snapshot({'R': {'x': 1}})
            return snapshot({'R': {'x': 2}}), snapshot({'R': {'x': 3}})
    assert agent_regions(Log(), 'A', {'R': {'x': 3}}) == set()


def test_replacement_batch_keeps_changed_subject_mentions_with_their_final_lines():
    from bti.visual.regions import replacement_batch
    current = {'beats': {'b1': {'items': [], 'about': [{'id': 'old', 'words': 'old'}]}}}
    projected = [{'op': 'set_subjects', 'subjects': []}, {'op': 'set_picks', 'beat': 'b1', 'items': [{'asset': 'A'}]}, {'op': 'set_about', 'beat': 'b1', 'about': []}]
    batch, rest = replacement_batch(current, 'A', {'OLD'}, [], projected)
    assert batch[1:] == projected
    assert rest == []
