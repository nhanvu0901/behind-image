"""Project a visual script to the existing line-oriented picks vocabulary."""
from __future__ import annotations


def project(visual: dict, timing: dict, main_asset: str) -> dict:
    wants = {w['id']: w for w in visual['wanted']}
    subjects = []
    for c in visual['cast']:
        places = [{'asset': p['picture']} if 'picture' in p else dict(p) for p in c['shown_by']]
        for w in visual['wanted']:
            depiction = {'asset': w.get('picture')}
            if w.get('subject') == c['id'] and w.get('status') == 'found' and w.get('picture') and depiction not in places:
                places.append(depiction)
        subjects.append({'id': c['id'], 'kind': c['kind'], 'name': c['name'], 'also': list(c['also']),
                         'strip': c['strip'], 'sub': c['sub'], 'where': places or None})
    lines = {}
    def resolve(show):
        if 'want' in show:
            want = wants[show['want']]
            return {'picture': want['picture']} if want['status'] == 'found' and want.get('picture') else show.get('else', {'whole': True})
        return show
    for moment in visual['moments']:
        line = lines.setdefault(moment['line'], {'beat': moment['line'], 'items': [], 'about': [], 'kinds': [], 'missing': [], 'reason': moment['why']})
        show = moment['show']
        for part in [show, *show.get('pair', [])]:
            if 'want' in part:
                w = wants[part['want']]
                if w['status'] == 'none':
                    missing = {'what': w.get('search', w['id'])[:160], 'code': 'agent_none', 'queries': [q[:160] for q in w.get('tried', [])[:4]]}
                    if missing not in line['missing']:
                        line['missing'].append(missing)
        is_map = 'map' in show
        if is_map:
            show = {'map_picture': show['map']['picture']} if show['map'].get('picture') else show['else']
        show = resolve(show)
        shows = [resolve(p) for p in show.get('pair', [])] if 'pair' in show else [show]
        for s in shows:
            if 'map_picture' in s:
                item, kind = {'asset': s['map_picture'], 'region': None, 'role': 'map'}, 'journey'
            elif 'picture' in s:
                item, kind = {'asset': s['picture'], 'region': None, 'role': 'context'}, 'outside'
            elif 'region' in s:
                item, kind = {'asset': main_asset, 'region': s['region'], 'role': 'detail'}, 'detail'
            else:
                item, kind = {'asset': main_asset, 'region': None, 'role': 'main'}, 'journey' if 'map' in s else 'whole'
            if not line['items'] or item != line['items'][-1]:
                line['items'].append(item)
            if kind not in line['kinds'] and len(line['kinds']) < 2:
                line['kinds'].append(kind)
        if moment.get('about'):
            words = ' '.join(w['w'] for w in timing['words'][moment['w0']:moment['w1']]).strip()
            row = {'id': moment['about'], 'words': words}
            if words and not any(a['id'] == row['id'] for a in line['about']):
                line['about'].append(row)
    return {'subjects': subjects, 'lines': list(lines.values())}


def operations(projection: dict) -> list[dict]:
    """Typed picks operations for a complete projection, in dependency order."""
    ops = [{'op': 'set_subjects', 'subjects': projection['subjects']}]
    for line in projection['lines']:
        ops.append({'op': 'set_picks', 'beat': line['beat'], 'items': line['items'], 'reason': line['reason'][:400],
                    'kinds': line['kinds'], 'missing': line['missing']})
        ops.append({'op': 'set_about', 'beat': line['beat'], 'about': line['about']})
    return ops
