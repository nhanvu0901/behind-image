"""Conservative region provenance and references for a visual re-plan."""
from __future__ import annotations


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def region_references(visual, storyboard, names):
    # A matching string is deliberately conservative: ambiguous data keeps a region.
    refs = set(_strings(visual)) & set(names)
    for shot in (storyboard or {}).get('shots', []):
        if shot.get('locked') or shot.get('source') != 'agent' or any(o.get('locked') or o.get('source') != 'agent' for o in shot.get('overlays', []) if isinstance(o, dict)):
            refs.update(set(_strings(shot)) & set(names))
    return refs


def cleanup_names(regions, visual, storyboard, agent_names):
    return set(regions) & set(agent_names) - region_references(visual, storyboard, regions)


def agent_regions(log, asset, current):
    """Only regions proved created by an agent and unchanged by people are eligible.

    Missing historical snapshots or an unlogged edit make provenance unknown.
    """
    known = {}
    for record in log.records('picks'):
        if 'regions:' + asset not in record.get('touched', []):
            continue
        copies = log.copies(record['batch'])
        if not copies:
            known.clear()
            continue
        before, after = copies
        old = before.get('assets', {}).get(asset, {}).get('regions', {})
        new = after.get('assets', {}).get(asset, {}).get('regions', {})
        for name in set(old) | set(new):
            if old.get(name) == new.get(name):
                continue
            if name not in old and name in new and str(record.get('actor', '')).startswith('agent:'):
                known[name] = new[name]
            elif name in known and old.get(name) == known[name] and str(record.get('actor', '')).startswith('agent:') and name in new:
                known[name] = new[name]
            else:
                known.pop(name, None)
    return {name for name, value in known.items() if current.get(name) == value}


def replacement_batch(current, asset, removed, additions, projection, *, keep_beats=None):
    """Keep region and affected line changes in the same undoable batch."""
    affected = {bid for bid, beat in current.get('beats', {}).items()
                if (keep_beats is None or bid in keep_beats)
                and any(item.get('asset') == asset and item.get('region') in removed
                        for item in beat.get('items', []))}
    # Subject changes must be paired with the final line so the batch validates
    # and a later projection does not make its undo conflict.
    for op in projection:
        if op.get('op') == 'set_about':
            beat = current.get('beats', {}).get(op['beat'], {})
            if (beat.get('about') or []) != op.get('about', []):
                affected.add(op['beat'])
    available = {op.get('beat') for op in projection if op.get('op') == 'set_picks'}
    if affected - available:
        raise ValueError('Cannot replace regions referenced by lines absent from the new script.')
    has_stale_cleanup = any(op.get('op') == 'remove_stale_beats' for op in projection)
    batch = ([{'op': 'remove_stale_beats'}] if has_stale_cleanup else []) + [
        {'op': 'remove_region', 'asset': asset, 'region': name} for name in sorted(removed)] + additions
    rest = []
    for op in projection:
        if op.get('op') == 'remove_stale_beats':
            continue
        if op['op'] == 'set_subjects' or op.get('beat') in affected:
            batch.append(op)
        else:
            rest.append(op)
    return batch, rest
