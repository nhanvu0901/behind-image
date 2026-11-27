"""Building blocks of the visual planning job."""
from __future__ import annotations
import copy


def search_requests(visual: dict) -> list[dict]:
    """Translate each wanted picture once to the existing search vocabulary."""
    members = {c['id']: c for c in visual['cast']}
    out = []
    for n, w in enumerate(visual['wanted'], 1):
        line = next((m['line'] for m in visual['moments'] if any(part.get('want') == w['id'] for part in [m['show'], *m['show'].get('pair', [])])), '')
        out.append({'id': w['id'], 'beat': line, 'n': n, 'type': 'context', 'kind': w['kind'],
                    'what': members[w['subject']]['name'], 'entity': members[w['subject']]['name'],
                    'search': w['search'], 'alt': w['alt'], 'period': w['period'], 'kinds': ['outside']})
    return out


def apply_choices(visual: dict, choices: dict, search: dict) -> dict:
    out = copy.deepcopy(visual)
    for w in out['wanted']:
        result = choices.get(w['id'], {})
        found = result.get('status') == 'found' and result.get('picture')
        w['status'] = 'found' if found else 'none'
        w['picture'] = result['picture'] if found else None
        w['tried'] = list(search.get('wants', {}).get(w['id'], {}).get('tried_queries') or [])
    wants = {w['id']: w for w in out['wanted']}
    cast = {c['id']: c for c in out.get('cast', [])}
    for moment in out.get('moments', []):
        show = moment.get('show', {})
        member = cast.get(moment.get('about'), {})
        parts = show.get('pair', [show])
        places = member.get('shown_by', [])
        visible = any(part in places or (part.get('want') in wants and wants[part['want']]['status'] == 'found'
                      and wants[part['want']]['subject'] == moment.get('about')) or part.get('else') in places for part in parts)
        for part in parts:
            want = wants.get(part.get('want'))
            if want and want['status'] == 'none' and moment.get('about') == want['subject'] and not visible:
                moment.setdefault('about_not_shown', 'Chưa có hình dùng được; dùng hình dự phòng.')
    return out


def missing_sentences(visual: dict) -> list[str]:
    return [f"Chưa có hình dùng được cho {w.get('search', w['id'])}. Đã thử: {', '.join(w.get('tried') or []) or 'chưa có từ khóa'}."
            for w in visual['wanted'] if w.get('status') == 'none']


def choice_errors(choice: dict, visual: dict, search: dict) -> list[str]:
    from bti.picks.doc import caption_valid
    if not isinstance(choice, dict):
        return ['choice must be an object keyed by wanted id']
    errors = []
    ids = {c['id'] for c in visual['cast']}
    for w in visual['wanted']:
        wid = w['id']
        row = choice.get(wid)
        if not isinstance(row, dict) or 'pick' not in row:
            errors.append(f'{wid}: supply a choice or null')
            continue
        if row['pick'] is None:
            continue
        candidates = search.get('wants', {}).get(wid, {}).get('candidates', [])
        if not any(c['n'] == row['pick'] for c in candidates):
            errors.append(f'{wid}: choose a candidate number on its sheet')
        if not caption_valid(row.get('caption')):
            errors.append(f'{wid}: supply a short descriptive caption')
        if not isinstance(row.get('shows'), list) or any(i not in ids for i in row['shows']):
            errors.append(f'{wid}: shows must list known cast ids')
        if row.get('period') not in ('then', 'later', 'today', None) or 'period' not in row:
            errors.append(f'{wid}: period must be then, later, today or null')
    if set(choice) - {w['id'] for w in visual['wanted']}:
        errors.append('remove unrecognized wanted ids')
    return errors


def map_requests(visual: dict) -> list[dict]:
    out = []
    for m in visual['moments']:
        show = m['show']
        if 'map' not in show or show['map'].get('picture'):
            continue
        places = show['map']['places']
        out.append({'id': 'map_' + m['id'], 'beat': m['line'], 'n': 1, 'type': 'map', 'places': places,
                    'place': places[0], 'what': places[0]})
    return out


def apply_maps(visual: dict, keys: dict) -> dict:
    out = copy.deepcopy(visual)
    for m in out['moments']:
        if 'map' in m['show'] and keys.get('map_' + m['id']):
            m['show']['map']['picture'] = keys['map_' + m['id']]
    return out


def start(pid, pdir, *, model=None, manager=None, by_run=False, **seams):
    """Start a visual-script job using the project's picks agent."""
    import json
    from pathlib import Path
    from bti.draft import run as draft_run
    from bti.longjob import Part, PartError
    from bti.picks.auto import inputs, session, search, write
    from bti.picks import doc
    from bti.visual import check, projection, store, workspace
    from bti.script.store import read_object

    pdir = Path(pdir)
    inp = inputs.load(pdir, redo=True, need_targets=False)
    timing = read_object(pdir / 'timing.json', 'timing')
    if not timing:
        raise inputs.AutoError('timing_missing', 'Timing is required before planning.', 409)
    resolved = draft_run._resolve(pdir, 'picks', model)
    session.check_installed(resolved.model)
    if manager is None:
        from bti.longjob import manager
    other = draft_run.other_agent_job(pid, 'picks', manager, run_ok=by_run)
    if other:
        raise inputs.AutoError('agent_job_running', 'Another agent is working on this project.', 409, job_id=other.get('id'))
    before = store.load(pdir)
    base_rev = store.revision(before) if before else None
    from bti.picks import websettings
    web_config = seams.get('web') if isinstance(seams.get('web'), dict) else websettings.for_run()
    if by_run:
        web_config = {'on': False, 'max': 0}
    state = {}
    limits_plan = session.Limits(minutes=30, steps=140, repairs=2)
    limits_choose = session.Limits(minutes=30, steps=200, repairs=2)

    def invoke(root, ctx, limits, label):
        def problems():
            report = check.run_check(root)
            return '\n'.join(i['message'] for i in report['issues'] if i.get('level') != 'review') or None
        from bti.draft.inputs import DraftError
        try:
            outcome = session.run_session(root, model=resolved.model, project_dir=pdir, ctx=ctx, label=label,
                                          limits=limits, check_fn=problems, python=seams.get('python'),
                                          guard_factory=seams.get('guard_factory'))
        except DraftError as e:
            raise PartError(e.code, session.refuse_text(e)) from e
        # Recover unambiguous misplaced outputs only after the session has ended.
        from bti.fsio import atomic_replace
        mode = json.loads((root / 'inputs/context.json').read_text(encoding='utf-8'))['mode']
        paths = [('visual.json', 'out/visual.json'), ('regions.json', 'out/regions.json')] if mode == 'plan' else [('choice.json', 'out/choice.json'), ('tighten/out/choice.json', 'out/choice.json'), ('out/tighten.json', 'tighten/out/tighten.json')]
        notes = []
        for source, destination in paths:
            src, dest = root / source, root / destination
            if dest.parent.is_dir() and not dest.exists() and src.is_file():
                atomic_replace(src, dest)
                notes.append(f'Moved {source} to {destination}.')
        if outcome.retry_after_seconds:
            ctx.meta.update(draft_run.rate_limit_fields(outcome.retry_after_seconds))
        if outcome.status != 'ok' or problems():
            raise PartError(outcome.code or 'picks_auto_no_output', outcome.message or problems() or 'Agent không viết được kết quả.')
        return notes

    def run_plan(ctx):
        ws = workspace.build_plan(inp, timing)
        notes = invoke(ws, ctx, limits_plan, 'Agent đang viết kịch bản hình')
        state['visual'] = json.loads((ws / 'out/visual.json').read_text(encoding='utf-8'))
        f = ws / 'out/regions.json'
        state['regions'] = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
        return {'moments': len(state['visual']['moments']), 'notes': notes}

    def run_search(ctx):
        visual = state['visual']
        requests = search_requests(visual) + map_requests(visual)
        from bti.picks import service
        web = search.Web(on=web_config.get('on', False), max=web_config.get('max', 0), search=web_config.get('search')) if web_config.get('on') else None
        result = search.new_state()
        for req in requests:
            tried = []
            def track(fn):
                def call(project, query, *args, **kwargs):
                    if query not in tried:
                        tried.append(query)
                    return fn(project, query, *args, **kwargs)
                return call
            result = search.run(pdir, {}, result, [req], main_key=inp.painting.key, cancelled=ctx.cancelled,
                                progress=ctx.progress, save=lambda _: None,
                                search=track(seams.get('search') or service.search),
                                wiki_search=track(seams.get('wiki_search') or service.search),
                                fetch_thumb=seams.get('fetch_thumb'), web=web)
            row = result['wants'][req['id']]
            row['tried_queries'] = list(dict.fromkeys(tried + row.get('tried_queries', [])))
            if row.get('status') == 'pending' and not ctx.cancelled():
                raise PartError('picks_auto_no_output', 'Việc tìm hình chưa hoàn tất; hãy chạy lại.')
        state['search'] = result
        state['web'] = web
        return {'wanted': len(requests)}

    def run_choose(ctx):
        visual, found = state['visual'], state['search']
        if not visual['wanted'] and not state['regions']:
            state['choice'] = {}
            return {'chosen': 0}
        ws = workspace.build_choose(pdir, visual, found, main=inp.picks['assets'][inp.painting.key], regions=state['regions'], limits=limits_choose)
        notes = invoke(ws, ctx, limits_choose, 'Agent đang chọn hình')
        state['choice'] = json.loads((ws / 'out/choice.json').read_text(encoding='utf-8'))
        if state['regions']:
            from bti.picks.auto import helper
            check.sync_tighten(ws)
            rep = helper.run_check(ws / 'tighten')
            state['region_choices'] = rep.value['regions']
        return {'chosen': len(state['choice']), 'notes': notes}

    def run_web(ctx):
        import time
        from bti.picks.auto import webround
        web = state.get('web')
        if web is None or not web.usable():
            return {'searched': 0}
        visual, found = state['visual'], state['search']
        first = {'wants': {wid: {'pick': row.get('pick')} for wid, row in state['choice'].items()}}
        found = webround.search_round_two(pdir, search_requests(visual), found, first, main_key=inp.painting.key,
                     web=web, fetch_thumb=seams.get('fetch_thumb') or search.default_fetch_thumb,
                     clock=seams.get('clock') or time.time, cancelled=ctx.cancelled, progress=ctx.progress,
                     save=lambda _: None, search=seams.get('search'), wiki_search=seams.get('wiki_search'))
        for row in found['wants'].values():
            row['tried_queries'] = list(dict.fromkeys(row.get('tried_queries', []) + (row.get('web') or {}).get('queries', [])))
        state['search'] = found
        return {'searched': web.spent}

    def run_choose2(ctx):
        from bti.picks.auto import webround
        visual, found = state['visual'], state['search']
        new_ids = webround.second_wants(found)
        if not new_ids:
            return {'chosen': 0}
        first = {'wants': {wid: {'pick': row.get('pick')} for wid, row in state['choice'].items()}}
        second_view = webround.second_search_view(found, first)
        second_visual = {**visual, 'wanted': [w for w in visual['wanted'] if w['id'] in new_ids]}
        ws = workspace.build_choose(pdir, second_visual, second_view)
        notes = invoke(ws, ctx, limits_choose, 'Agent đang chọn hình tìm thêm')
        second = json.loads((ws / 'out/choice.json').read_text(encoding='utf-8'))
        for wid, row in second.items():
            if row['pick'] is not None:
                row['pick'] = found['round2']['map'][wid][row['pick'] - 1]
                state['choice'][wid] = row
        return {'chosen': len(second), 'notes': notes}

    def run_write(ctx):
        writer = write.Writer(pdir, 'agent:' + resolved.model, redo=True)
        visual = state['visual']
        from bti.picks import context
        current = doc.load_or_new(pdir)
        current_visual = store.load(pdir)
        if (store.revision(current_visual) if current_visual is not None else None) != base_rev:
            raise PartError('picks_auto_stale', 'Kịch bản hình đã thay đổi trong lúc agent làm việc.')
        latest_timing = read_object(pdir / 'timing.json', 'timing')
        latest_narration = context.narration_view(pdir)
        if latest_timing != timing or latest_narration.get('rev') != inp.narration_rev or not latest_narration.get('approved'):
            raise PartError('picks_auto_stale', 'Lời dẫn hoặc thời gian đã thay đổi trong lúc agent làm việc.')
        if doc.revision(current) != doc.revision(inp.picks):
            raise PartError('picks_auto_stale', 'Chọn hình đã thay đổi trong lúc agent làm việc.')
        if state['regions']:
            keep, dropped = write.final_regions({'regions': state['regions']}, {'regions': state['region_choices']})
            if dropped:
                raise PartError('validation_failed', 'Có vùng không tìm thấy trong tranh; hãy sửa kịch bản và chạy lại.')
            ops, names, _ = write.region_ops(inp.painting.key, current['assets'][inp.painting.key], keep, inp.painting.width, inp.painting.height)
            if any(names.get(k) != k for k in state['regions']):
                raise PartError('picks_auto_stale', 'Tên vùng đã thay đổi; hãy chạy lại.')
            if ops:
                writer.send(ops, 'Agent viết kịch bản hình: vùng chi tiết')
        from bti.ops import OpError
        choices = {}
        for wid, choice in state['choice'].items():
            if choice['pick'] is None:
                continue
            cand = next(c for c in state['search']['wants'][wid]['candidates'] if c['n'] == choice['pick'])
            ops = [{'op': 'import', 'source': cand['source'], 'source_id': cand['source_id'], 'ref': 'pic'},
                   {'op': 'set_caption', 'asset': '$pic', 'caption': choice['caption']}]
            try:
                result = writer.send(ops, 'Agent viết kịch bản hình: nhập ảnh')
            except OpError as e:
                if e.code not in ('import_failed', 'source_rate_limited'):
                    raise
                continue
            key = result['created']['refs']['pic']
            asset = doc.load_or_new(pdir)['assets'].get(key) or {}
            existing = asset.get('shows') or []
            shows = list(dict.fromkeys(existing + choice['shows']))
            period = choice['period'] if choice['period'] is not None else asset.get('period')
            writer.send([{'op': 'set_picture_info', 'asset': key, 'shows': shows, 'period': period}], 'Agent viết kịch bản hình: thông tin ảnh')
            choices[wid] = {'status': 'found', 'picture': key}
        visual = apply_choices(visual, choices, state['search'])
        maps = {}
        for req in map_requests(visual):
            candidates = state['search']['wants'][req['id']]['candidates']
            if candidates:
                cand = candidates[0]
                try:
                    result = writer.send([{'op': 'import', 'source': cand['source'], 'source_id': cand['source_id'], 'ref': 'map'}], 'Agent viết kịch bản hình: bản đồ')
                except OpError as e:
                    if e.code not in ('import_failed', 'source_rate_limited'):
                        raise
                    continue
                maps[req['id']] = result['created']['refs']['map']
        visual = apply_maps(visual, maps)
        current = doc.load_or_new(pdir)
        issues = check.validate(visual, timing, current)
        if any(i.get('level') != 'review' for i in issues):
            raise PartError('validation_failed', 'Kịch bản hình không hợp lệ sau khi tìm hình.')
        proj = projection.project(visual, timing, inp.painting.key)
        ops = projection.operations(proj)
        for offset in range(0, len(ops), 200):
            writer.send(ops[offset:offset + 200], 'Agent viết kịch bản hình: chọn hình theo đoạn')
        store.save(pdir, visual, base_rev=base_rev, actor='agent:' + resolved.model)
        missing = missing_sentences(visual)
        return {'sentence': 'Đã viết kịch bản hình.', 'missing': missing}

    parts = [Part('plan', 'Viết kịch bản hình', run_plan), Part('search', 'Tìm hình', run_search),
             Part('choose', 'Chọn hình', run_choose)]
    if web_config.get('on'):
        parts += [Part('web', 'Tìm thêm trên web', run_web), Part('choose2', 'Chọn hình tìm thêm', run_choose2)]
    parts.append(Part('write', 'Lưu kịch bản hình', run_write))
    return manager.start(kind='picks', pid=pid, project_dir=pdir, parts=parts,
                         meta={'action': 'auto', 'visual_action': 'plan', 'model': resolved.model, 'agent': resolved.public()})
