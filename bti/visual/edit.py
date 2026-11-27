"""Scope handling for edits to a visual script."""
from __future__ import annotations


def scope_ids(visual: dict, scope: dict) -> list[str]:
    """Resolve a single explicit scope to moment ids in script order."""
    if not isinstance(scope, dict) or len(scope) != 1:
        raise ValueError('supply one scope')
    moments = visual['moments']
    if scope == {'all': True}:
        return [m['id'] for m in moments]
    key = next(iter(scope))
    if key not in ('moments', 'lines'):
        raise ValueError('unknown scope')
    values = scope[key]
    if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v for v in values):
        raise ValueError('scope must be a nonempty list of ids')
    field = 'id' if key == 'moments' else 'line'
    available = {m[field] for m in moments}
    if not set(values) <= available:
        raise ValueError('unknown scope id')
    return [m['id'] for m in moments if m[field] in values]


def check_scope(before: dict, after: dict, ids: list[str]) -> list[str]:
    """Return violations when moments outside the selection change or move."""
    selected = set(ids)
    old = [m for m in before['moments'] if m['id'] not in selected]
    new = [m for m in after['moments'] if m['id'] not in selected and m['id'] in {x['id'] for x in old}]
    issues = [] if old == new else ['Moments outside the requested scope must remain unchanged.']
    referenced = {m.get('about') for m in old}
    referenced.update(intent.get('intro') for m in old for intent in m.get('say', []) if isinstance(intent, dict))
    prior_cast = {c['id']: c for c in before.get('cast', []) if c.get('id') in referenced}
    next_cast = {c['id']: c for c in after.get('cast', []) if c.get('id') in referenced}
    if prior_cast != next_cast:
        issues.append('Cast used outside the requested scope must remain unchanged.')
    return issues


def build_workspace(inp, timing, visual, ids, instruction, *, root=None):
    """Prepare the same evidence and checks as planning, plus the edit request."""
    import json
    from bti.visual import workspace
    template = workspace.REPO / 'skills/visual_plan/EDIT.template.md'
    text = template.read_text(encoding='utf-8') if template.exists() else (
        'Edit the visual script in inputs/visual.json for inputs/scope.json. '
        'Follow the planner principles in PLAN.template.md. Write the complete '
        'script to out/visual.json and run {{CHECK_CMD}}.\n')
    text += '\nOwner request:\n' + instruction + '\n'
    root = workspace.build_plan(inp, timing, root=root, instruction=text)
    workspace._json(root / 'inputs/visual.json', visual)
    workspace._json(root / 'inputs/scope.json', ids)
    import sys
    plan = (workspace.REPO / 'skills/visual_plan/PLAN.template.md').read_text(encoding='utf-8')
    plan = plan.replace('{{CHECK_CMD}}', '.\\check.cmd' if sys.platform == 'win32' else './check')
    plan = plan.replace('{{CROP_CMD}}', '.\\crop.cmd' if sys.platform == 'win32' else './crop')
    (root / 'inputs/PLAN.md').write_text(plan, encoding='utf-8')
    import json
    context_path = root / 'inputs/context.json'
    context_data = json.loads(context_path.read_text(encoding='utf-8'))
    context_data['made_from'] = visual.get('made_from')
    context_path.write_text(json.dumps(context_data, ensure_ascii=False), encoding='utf-8')
    # Keep the command the model runs identical to the programmatic gate.
    import stat
    windows = sys.platform == 'win32'
    command = root / ('check.cmd' if windows else 'check')
    if windows:
        command.write_text(f'@echo off\r\nset "PYTHONPATH={workspace.REPO}"\r\n"{sys.executable}" -m bti.visual.edit %*\r\n', encoding='utf-8')
    else:
        command.write_text(f"#!/bin/sh\nPYTHONPATH='{workspace.REPO}' exec '{sys.executable}' -m bti.visual.edit \"$@\"\n", encoding='utf-8')
        command.chmod(command.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return root


def edit_check(root):
    """Run the planner check and enforce the selected edit boundary."""
    import json
    from pathlib import Path
    from bti.visual import check
    root = Path(root)
    report = check.run_check(root)
    try:
        before = json.loads((root / 'inputs/visual.json').read_text(encoding='utf-8'))
        after = json.loads((root / 'out/visual.json').read_text(encoding='utf-8'))
        ids = json.loads((root / 'inputs/scope.json').read_text(encoding='utf-8'))
        for msg in check_scope(before, after, ids):
            report['issues'].append({'rule': 'scope', 'moment': None, 'message': msg})
        old_words = {i for m in before['moments'] if m['id'] in ids for i in range(m['w0'], m['w1'])}
        old_ids = {m['id'] for m in before['moments']}
        for m in after['moments']:
            if m['id'] in ids or m['id'] not in old_ids:
                if not set(range(m['w0'], m['w1'])) <= old_words:
                    report['issues'].append({'rule': 'scope', 'moment': m['id'], 'message': 'New or changed moments must stay inside the requested scope.'})
        old_wants = {w['id']: w for w in before.get('wanted', [])}
        if (root / 'out/regions.json').exists():
            report['issues'].append({'rule': 'scope', 'moment': None, 'message': 'Use an existing region or a wanted picture; new regions are not supported by this edit.'})
        if any(w.get('status') != 'open' or w.get('picture') is not None for w in after.get('wanted', []) if w['id'] not in old_wants):
            report['issues'].append({'rule': 'scope', 'moment': None, 'message': 'New wanted entries must be open with a null picture.'})
        new_wants = {w['id']: w for w in after.get('wanted', [])}
        if any(new_wants.get(k) != v for k, v in old_wants.items()):
            report['issues'].append({'rule': 'scope', 'moment': None, 'message': 'Existing wanted entries must remain unchanged.'})
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report['issues'].append({'rule': 'scope', 'moment': None, 'message': str(exc)})
    report['ok'] = not any(i.get('level') != 'review' for i in report['issues'])
    return report


def missing_by_moment(visual, ids, *, before=None):
    """Associate unresolved wants with the original selected moments, including splits."""
    missing = {w['id']: w.get('search', w['id']) for w in visual.get('wanted', []) if w.get('status') == 'none'}
    originals = {m['id']: m for m in (before or visual)['moments'] if m['id'] in ids}
    result = {}
    for moment in visual['moments']:
        show = moment.get('show') or {}
        subjects = [missing[part['want']] for part in show.get('pair', [show]) if part.get('want') in missing]
        if not subjects:
            continue
        for mid, old in originals.items():
            overlaps = (moment.get('line') == old.get('line') and isinstance(moment.get('w0'), int)
                        and isinstance(moment.get('w1'), int) and isinstance(old.get('w0'), int)
                        and isinstance(old.get('w1'), int) and moment['w0'] < old['w1'] and old['w0'] < moment['w1'])
            if moment['id'] == mid or overlaps:
                result[mid] = subjects[0]
    return result


def run_edit(pid, pdir, instruction, scope, *, model, ctx, base_rev=None, **seams):
    """Run an edit in an existing agent job, including search, save and compose."""
    import json
    from pathlib import Path
    from bti.visual import check, job, projection, store
    from bti.picks.auto import inputs, search, session, write
    from bti.picks import context, doc, service, websettings
    from bti.script.store import read_object
    from bti.longjob import PartError
    from bti.draft.inputs import DraftError
    from bti.ops import OpError

    pdir = Path(pdir)
    inp = inputs.load(pdir, redo=True, need_targets=False)
    timing = read_object(pdir / 'timing.json', 'timing')
    before = store.load(pdir)
    if not before or not timing:
        raise PartError('validation_failed', 'Cần kịch bản hình và thời gian lời dẫn.')
    rev = store.revision(before)
    if base_rev is not None and base_rev != rev:
        raise PartError('picks_auto_stale', 'Kịch bản hình đã thay đổi.')
    ids = scope_ids(before, scope)
    ws = build_workspace(inp, timing, before, ids, instruction)
    ctx_path = ws / 'inputs/context.json'
    ws_context = json.loads(ctx_path.read_text(encoding='utf-8'))
    ws_context['made_from'] = before.get('made_from')
    ctx_path.write_text(json.dumps(ws_context, ensure_ascii=False), encoding='utf-8')
    limits = session.Limits(minutes=30, steps=140, repairs=2)

    def invoke(root, checker, label):
        def problems():
            report = checker(root)
            return '\n'.join(i['message'] for i in report['issues'] if i.get('level') != 'review') or None
        try:
            outcome = session.run_session(root, model=model, project_dir=pdir, ctx=ctx, label=label,
                                          limits=limits, check_fn=problems, python=seams.get('python'),
                                          guard_factory=seams.get('guard_factory'))
        except DraftError as exc:
            raise PartError(exc.code, session.refuse_text(exc)) from exc
        if outcome.status != 'ok' or problems():
            raise PartError(outcome.code or 'picks_auto_no_output', outcome.message or problems() or 'Agent không viết được kết quả.')

    invoke(ws, edit_check, 'Agent đang sửa kịch bản hình')
    visual = json.loads((ws / 'out/visual.json').read_text(encoding='utf-8'))
    old_ids = {w['id'] for w in before['wanted']}
    fresh = [w for w in visual['wanted'] if w['id'] not in old_ids]
    if any(w.get('status') != 'open' or w.get('picture') is not None for w in fresh):
        raise PartError('validation_failed', 'Hình mới phải có trạng thái open.')
    view = {**visual, 'wanted': fresh}
    found = search.new_state()
    requests = job.search_requests(view) + [r for r in job.map_requests(view) if r['id'][4:] in ids or r['id'][4:] not in {m['id'] for m in before['moments']}]
    web_cfg = seams.get('web') if isinstance(seams.get('web'), dict) else websettings.for_run()
    web = search.Web(on=True, max=web_cfg.get('max', 0), search=web_cfg.get('search')) if web_cfg.get('on') else None
    for req in requests:
        tried = []
        def track(fn):
            def call(project, query, *args, **kwargs):
                if query not in tried:
                    tried.append(query)
                return fn(project, query, *args, **kwargs)
            return call
        found = search.run(pdir, {}, found, [req], main_key=inp.painting.key, cancelled=ctx.cancelled,
                           progress=ctx.progress, save=lambda _: None,
                           search=track(seams.get('search') or service.search),
                           wiki_search=track(seams.get('wiki_search') or service.search),
                           fetch_thumb=seams.get('fetch_thumb'), web=web)
        row = found['wants'][req['id']]
        row['tried_queries'] = list(dict.fromkeys(tried + row.get('tried_queries', [])))
        if row.get('status') == 'pending' and not ctx.cancelled():
            raise PartError('picks_auto_no_output', 'Việc tìm hình chưa hoàn tất.')
    choices = {}
    if fresh:
        choose_ws = __import__('bti.visual.workspace', fromlist=['build_choose']).build_choose(pdir, view, found)
        invoke(choose_ws, check.run_check, 'Agent đang chọn hình')
        choices = json.loads((choose_ws / 'out/choice.json').read_text(encoding='utf-8'))
        if web is not None and web.usable():
            import time
            from bti.picks.auto import webround
            first = {'wants': {wid: {'pick': row.get('pick')} for wid, row in choices.items()}}
            found = webround.search_round_two(pdir, job.search_requests(view), found, first,
                     main_key=inp.painting.key, web=web, fetch_thumb=seams.get('fetch_thumb') or search.default_fetch_thumb,
                     clock=seams.get('clock') or time.time, cancelled=ctx.cancelled, progress=ctx.progress,
                     save=lambda _: None, search=seams.get('search'), wiki_search=seams.get('wiki_search'))
            for row in found['wants'].values():
                row['tried_queries'] = list(dict.fromkeys(row.get('tried_queries', []) + (row.get('web') or {}).get('queries', [])))
            new_ids = webround.second_wants(found)
            if new_ids:
                second_view = webround.second_search_view(found, first)
                second_visual = {**view, 'wanted': [w for w in fresh if w['id'] in new_ids]}
                second_ws = __import__('bti.visual.workspace', fromlist=['build_choose']).build_choose(pdir, second_visual, second_view)
                invoke(second_ws, check.run_check, 'Agent đang chọn hình tìm thêm')
                second = json.loads((second_ws / 'out/choice.json').read_text(encoding='utf-8'))
                for wid, row in second.items():
                    if row['pick'] is not None:
                        row['pick'] = found['round2']['map'][wid][row['pick'] - 1]
                        choices[wid] = row
    if store.revision(store.load(pdir)) != rev or read_object(pdir / 'timing.json', 'timing') != timing or doc.revision(doc.load_or_new(pdir)) != doc.revision(inp.picks):
        raise PartError('picks_auto_stale', 'Dữ liệu đã thay đổi trong lúc agent làm việc.')
    latest = context.narration_view(pdir)
    if latest.get('rev') != inp.narration_rev or not latest.get('approved'):
        raise PartError('picks_auto_stale', 'Lời dẫn đã thay đổi trong lúc agent làm việc.')
    writer = write.Writer(pdir, 'agent:' + model, redo=True)
    resolved = {}
    for wid, choice in choices.items():
        if choice['pick'] is None:
            continue
        cand = next(c for c in found['wants'][wid]['candidates'] if c['n'] == choice['pick'])
        try:
            result = writer.send([{'op': 'import', 'source': cand['source'], 'source_id': cand['source_id'], 'ref': 'pic'},
                                  {'op': 'set_caption', 'asset': '$pic', 'caption': choice['caption']}], 'Agent sửa kịch bản hình: nhập ảnh')
        except OpError as exc:
            if exc.code not in ('import_failed', 'source_rate_limited'):
                raise
            continue
        key = result['created']['refs']['pic']
        asset = doc.load_or_new(pdir)['assets'].get(key) or {}
        shows = list(dict.fromkeys((asset.get('shows') or []) + choice['shows']))
        writer.send([{'op': 'set_picture_info', 'asset': key, 'shows': shows,
                      'period': choice['period'] if choice['period'] is not None else asset.get('period')}], 'Agent sửa kịch bản hình: thông tin ảnh')
        resolved[wid] = {'status': 'found', 'picture': key}
    updated_fresh = job.apply_choices(view, resolved, found)
    by_id = {w['id']: w for w in updated_fresh['wanted']}
    visual['wanted'] = [by_id.get(w['id'], w) for w in visual['wanted']]
    for index, moment in enumerate(updated_fresh['moments']):
        visual['moments'][index] = moment
    maps = {}
    for req in requests:
        if not req['id'].startswith('map_'):
            continue
        candidates = found.get('wants', {}).get(req['id'], {}).get('candidates', [])
        if candidates:
            try:
                result = writer.send([{'op': 'import', 'source': candidates[0]['source'], 'source_id': candidates[0]['source_id'], 'ref': 'map'}], 'Agent sửa kịch bản hình: bản đồ')
            except OpError as exc:
                if exc.code not in ('import_failed', 'source_rate_limited'):
                    raise
                continue
            maps[req['id']] = result['created']['refs']['map']
    visual = job.apply_maps(visual, maps)
    picks = doc.load_or_new(pdir)
    if any(i.get('level') != 'review' for i in check.validate(visual, timing, picks)):
        raise PartError('validation_failed', 'Kịch bản hình không hợp lệ sau khi tìm hình.')
    operations = projection.operations(projection.project(visual, timing, inp.painting.key))
    for offset in range(0, len(operations), 200):
        writer.send(operations[offset:offset + 200], 'Agent sửa kịch bản hình: chọn hình theo đoạn')
    store.save(pdir, visual, base_rev=rev, actor='agent:' + model, compose=False)
    from bti.compose.api import compose_project
    composed = compose_project(pdir)
    missing_moments = missing_by_moment(visual, ids, before=before)
    missing_moments.update(missing_by_moment(visual, [m['id'] for m in visual['moments']]))
    return {'sentence': 'Đã sửa kịch bản hình và dựng lại storyboard.',
            'missing': job.missing_sentences({'wanted': list(by_id.values())}),
            'missing_moments': missing_moments, 'compose': composed}


def start(pid, pdir, *, instruction, scope, model=None, manager=None, by_run=False, **seams):
    """Start a project-exclusive agent job for a visual edit."""
    from pathlib import Path
    from bti.draft import run as draft_run
    from bti.picks.auto import inputs, session
    from bti.longjob import Part
    from bti.visual import store
    pdir = Path(pdir)
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 2000:
        raise inputs.AutoError('invalid_request', 'Supply an instruction of at most 2000 characters.', 422)
    visual = store.load(pdir)
    if not visual:
        raise inputs.AutoError('validation_failed', 'Visual script is missing.', 409)
    try:
        scope_ids(visual, scope)
    except (ValueError, KeyError) as exc:
        raise inputs.AutoError('invalid_request', str(exc), 422) from exc
    resolved = draft_run._resolve(pdir, 'picks', model)
    session.check_installed(resolved.model)
    if manager is None:
        from bti.longjob import manager
    other = draft_run.other_agent_job(pid, 'picks', manager, run_ok=by_run)
    if other:
        raise inputs.AutoError('agent_job_running', 'Another agent is working on this project.', 409, job_id=other.get('id'))
    rev = store.revision(visual)
    def run(ctx):
        return run_edit(pid, pdir, instruction, scope, model=resolved.model, ctx=ctx, base_rev=rev, **seams)
    return manager.start(kind='picks', pid=pid, project_dir=pdir,
                         parts=[Part('edit', 'Sửa kịch bản hình', run)],
                         meta={'action': 'edit', 'visual_action': 'edit', 'model': resolved.model, 'agent': resolved.public()})


def main():
    from pathlib import Path
    report = edit_check(Path.cwd())
    for issue in report['issues']:
        print(f"{'REPORT' if issue.get('level') == 'review' else 'ERROR'} {issue['rule']}: {issue['message']}")
    print('OK' if report['ok'] else 'Please repair the errors and check again.')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())


from fastapi import APIRouter, Body, Request
router = APIRouter(prefix='/api/projects/{pid}/visual')


@router.post('/edit')
def post_edit(pid: str, request: Request, body: dict = Body(...)):
    from bti.editor.common import ApiError
    from bti.editor.picks_api import _pdir
    from bti.picks.auto.inputs import AutoError
    from bti.draft.inputs import DraftError
    from bti.longjob import Busy
    try:
        result = start(pid, _pdir(request, pid), instruction=body.get('instruction'), scope=body.get('scope'),
                       model=body.get('model'), manager=getattr(request.app.state, 'longjob_manager', None))
    except AutoError as exc:
        raise ApiError(exc.status, exc.message, code=exc.code, **exc.extra) from exc
    except DraftError as exc:
        raise ApiError(409, exc.message, code=exc.code) from exc
    except Busy as exc:
        raise ApiError(409, 'An agent job is already running.', code='busy', job_id=exc.job_id) from exc
    return {'job_id': result['id'], 'model': (result.get('meta') or {}).get('model'), 'agent': (result.get('meta') or {}).get('agent')}
