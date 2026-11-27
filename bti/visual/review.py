"""Viewer review of composed visual-script moments."""
from __future__ import annotations

from bti.draft.review import ReviewError, ISSUE_CODES, _validate, _incomplete_warning

LABELS = {'picture_mismatch': 'Hình không đúng nội dung lời dẫn',
          'text_wrong': 'Chữ trên hình không đúng',
          'context_missing': 'Thiếu thông tin để theo dõi',
          'picture_repeated': 'Hình lặp lại không có lý do'}


def review_and_repair(rows_now, review, edit):
    """Review once, then edit the affected moments at most twice."""
    rows = rows_now()
    pending = [r['id'] for r in rows]
    current = {r['id']: r for r in rows}
    outstanding = {}
    warnings = []
    history = []
    rounds = 0
    while pending:
        answer = review(pending)
        findings = _validate(pending, answer)
        if any(len(problems) > 1 for problems in findings.values()):
            raise ReviewError('at most one finding is allowed per shot')
        if answer.get('incomplete'):
            warnings.append(_incomplete_warning(answer['incomplete']))
        history.append(findings)
        for sid in pending:
            outstanding.pop(sid, None)
            if findings[sid]:
                outstanding[sid] = findings[sid][0]
        if not outstanding or rounds == 2:
            break
        affected = [(current[sid], p) for sid, p in outstanding.items() if sid in current and current[sid].get('moment')]
        if not affected:
            break
        ids = list(dict.fromkeys(row['moment'] for row, _ in affected))
        instruction = ('Sửa các vấn đề khi xem video sau đây, chỉ dựa vào lời dẫn và nguồn của dự án. '
                       'Có thể chọn vùng khác, ảnh khác trong kho, yêu cầu ảnh mới, ghép hai ảnh, '
                       'chuyển điểm cắt hoặc bỏ một ý định hiển thị. Không thêm chữ không cần thiết.\n' +
                       '\n'.join(f"{row['id']} ({row['moment']}): {LABELS[p['code']]}: {p['detail']}" for row, p in affected))
        result = edit(ids, instruction)
        rounds += 1
        missing = result.get('missing') or {}
        for sid in list(outstanding):
            row = current.get(sid, {})
            subject = missing.get(row.get('moment'))
            if subject:
                warnings.append({'level': 'warn', 'code': ISSUE_CODES[outstanding[sid]['code']], 'shot': sid,
                                 'words': row.get('words', ''), 'message': f'Không tìm thấy hình cho {subject}.'})
                del outstanding[sid]
        previous = current
        rows = rows_now()
        current = {r['id']: r for r in rows}
        pending = [sid for sid in result.get('changed', []) if sid in current
                   and current[sid].get('moment') not in missing
                   and sid not in {w.get('shot') for w in warnings}]
        changed_moments = {current[sid].get('moment') for sid in pending}
        for sid in list(outstanding):
            if sid not in current and previous.get(sid, {}).get('moment') in changed_moments:
                del outstanding[sid]
        if not pending:
            break
    for sid, problem in outstanding.items():
        row = current.get(sid, {})
        warnings.append({'level': 'warn', 'code': ISSUE_CODES[problem['code']], 'shot': sid,
                         'words': row.get('words', ''), 'message': f"{LABELS[problem['code']]}: {problem['detail']}"})
    return {'rounds': rounds, 'warnings': warnings, 'history': history}


def sample_time(shot, t0, t1):
    """Choose a time inside the first visible mark when its end is known."""
    from bti.scorecard.sheets import MARK_TECHNIQUES, POINTING_TECHNIQUES, shot_sample_time
    marks = [o for o in shot.get('overlays', []) if isinstance(o, dict) and o.get('technique') in MARK_TECHNIQUES
             and isinstance(o.get('_t0'), (int, float)) and isinstance(o.get('_t1'), (int, float))
             and min(t1, o['_t1']) > max(t0, o['_t0'])]
    points = [o for o in marks if o['technique'] in POINTING_TECHNIQUES]
    if points or marks:
        mark = min(points or marks, key=lambda o: o['_t0'])
        start, end = max(t0, mark['_t0']), min(t1, mark['_t1'])
        return (start + end) / 2
    return shot_sample_time(shot, t0, t1)


def prepare_sheets(project, visual, storyboard, destination, *, ids=None, cancelled=lambda: False):
    """Render one numbered frame per shot at the scorecard's mark-visible time."""
    from pathlib import Path
    from PIL import Image, ImageDraw
    from bti.longjob import Cancelled
    dest = Path(destination); dest.mkdir(parents=True, exist_ok=True)
    wanted = set(ids) if ids is not None else None
    words = project.timing().get('words') or []
    moments = {m['id']: m for m in visual['moments']}
    cast = {c['id']: c for c in visual.get('cast', [])}
    notes = storyboard.get('compose_notes') or []
    rows, tiles, paths = [], [], []
    for number, shot in enumerate(project.resolve().get('shots') or [], 1):
        if cancelled():
            raise Cancelled()
        sid = shot.get('id')
        if wanted is not None and sid not in wanted:
            continue
        t0, t1 = shot.get('_t0'), shot.get('_t1')
        if not isinstance(t0, (int, float)) or not isinstance(t1, (int, float)) or t1 <= t0:
            raise ReviewError('invalid resolved shot')
        t = sample_time(shot, t0, t1)
        frame = project.frame_at(t, 640)
        if frame is None or getattr(frame, 'ndim', 0) != 3:
            raise ReviewError('could not render shot ' + str(sid))
        image = Image.fromarray(frame[:, :, ::-1].astype('uint8')).convert('RGB').resize((640, 360))
        tile = Image.new('RGB', (640, 392), 'black'); tile.paste(image, (0, 32))
        ImageDraw.Draw(tile).text((8, 8), f'#{number} {sid}  {t:.2f}s', fill='white')
        tiles.append(tile)
        moment = moments.get(shot.get('moment'), {})
        about = cast.get(moment.get('about'), {})
        spoken = ' '.join(w['w'] for w in words if t0 <= float(w['s']) < t1)
        rows.append({'id': sid, 'number': number, 'moment': shot.get('moment'), 'start': t0, 'end': t1,
                     'words': spoken, 'about': about.get('name'), 'why': moment.get('why'),
                     'compose_notes': [n for n in notes if n.get('moment') == shot.get('moment')],
                     'frames': [{'time': t, 'sheet': f'sheet-{(len(tiles)-1)//6+1:03d}.jpg'}]})
    for first in range(0, len(tiles), 6):
        chunk = tiles[first:first+6]
        sheet = Image.new('RGB', (1280, ((len(chunk)+1)//2)*392), 'black')
        for i, tile in enumerate(chunk):
            sheet.paste(tile, ((i % 2)*640, (i // 2)*392))
        path = dest / f'sheet-{first//6+1:03d}.jpg'; sheet.save(path, quality=85)
        paths.append(path)
    return rows, paths


def write_review_workspace(root, rows):
    import json
    from pathlib import Path
    from bti.visual.workspace import REPO
    root = Path(root); root.mkdir(parents=True, exist_ok=True); (root / 'out').mkdir(exist_ok=True)
    template = REPO / 'skills/visual_plan/REVIEW.template.md'
    task = template.read_text(encoding='utf-8') if template.exists() else ('Review every numbered shot using shots.json and the sheets. Write out/review.json with a shots list, one id and problems list per shot, at most one finding per shot. Codes: picture_mismatch, text_wrong, context_missing, picture_repeated. Details in Vietnamese.')
    (root / 'TASK.md').write_text(task, encoding='utf-8')
    (root / 'shots.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    return root


def run_model_review(workspace, rows, *, project_dir=None, model=None, provider=None, ctx=None):
    """Request missing answers once; an incomplete answer is never called clean."""
    import json
    import shutil
    from pathlib import Path
    from bti.draft import run as draft_run
    from bti.draft.guard import Guard
    from bti.draft.inputs import DraftError
    from bti.longjob import Cancelled
    root = Path(workspace)
    provider = provider or draft_run._agent_module(model)
    kwargs = {'model': model, 'timeout': 900, 'max_repairs': 0}
    if project_dir is not None:
        kwargs['guard'] = Guard(Path(project_dir))
    if ctx is not None:
        kwargs.update(cancel=ctx.cancelled, runner=ctx.run_process)
    found = {}; requested = list(rows)
    for attempt in range(2):
        work = root if attempt == 0 else root / 'follow-up'
        write_review_workspace(work, requested)
        if attempt:
            for name in {f['sheet'] for row in requested for f in row.get('frames', [])}:
                shutil.copyfile(root / name, work / name)
        output = work / 'out/review.json'
        if output.exists():
            raise ReviewError('review output already exists')
        result = provider.run(work, **kwargs)
        if result.status == 'cancelled':
            raise Cancelled()
        if result.status != 'ok':
            raise DraftError(getattr(result, 'error_code', None) or 'agy_error', getattr(result, 'error_message', '') or 'viewer review failed')
        try:
            if output.is_symlink() or output.parent.is_symlink() or output.stat().st_size > 2_000_000:
                raise ReviewError('review output is not a bounded regular file')
            answer = json.loads(output.read_text(encoding='utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            partial = _validate([r['id'] for r in requested], answer, allow_missing=True)
            if any(len(v) > 1 for v in partial.values()):
                raise ReviewError('at most one finding is allowed per shot')
        except (OSError, UnicodeError, ValueError) as exc:
            if attempt:
                raise ReviewError('review output is invalid') from exc
            continue
        found.update(partial)
        requested = [r for r in rows if r['id'] not in found]
        if not requested:
            break
    return {'shots': [{'id': r['id'], 'problems': found.get(r['id'], [])} for r in rows], 'incomplete': len(requested)}


def _rows(project):
    words = project.timing().get('words') or []
    out = []
    for shot in project.resolve().get('shots') or []:
        start, end = shot.get('_t0'), shot.get('_t1')
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise ReviewError('invalid resolved shot')
        out.append({'id': shot['id'], 'moment': shot.get('moment'),
                    'words': ' '.join(w['w'] for w in words if start <= float(w['s']) < end)})
    return out


def changed_shots(before, after):
    """Detect changes in resolved shot timing as well as shot content."""
    previous = {shot['id']: shot for shot in before}
    return [shot['id'] for shot in after if previous.get(shot['id']) != shot]


def run_job(pid, project_dir, model, ctx, *, review_round=None, edit_fn=None, **seams):
    """Review and edit within one existing project-exclusive agent job."""
    import json
    import uuid
    from pathlib import Path
    from bti.engine.api import open_project
    from bti.visual import edit, store
    from bti.draft import review as legacy
    from bti.editor.common import save_lock
    from bti.longjob import Cancelled
    pdir = Path(project_dir)
    root = pdir / 'cache' / 'visual_review' / uuid.uuid4().hex
    revision = legacy._revision(pdir)
    inputs = legacy._input_signature(pdir)
    counter = 0
    def current_rows():
        if ctx.cancelled():
            raise Cancelled()
        return _rows(open_project(pdir))
    def check_current():
        if legacy._revision(pdir) != revision or legacy._input_signature(pdir) != inputs:
            raise ReviewError('project changed during visual review')
    def review_shots(ids):
        nonlocal counter
        check_current()
        directory = root / str(counter); counter += 1
        if review_round:
            result = review_round(ids, directory)
        else:
            project = open_project(pdir)
            visual = store.load(pdir)
            storyboard = json.loads((pdir / 'storyboard.json').read_text(encoding='utf-8'))
            rows, _ = prepare_sheets(project, visual, storyboard, directory, ids=ids, cancelled=ctx.cancelled)
            if [r['id'] for r in rows] != ids:
                raise ReviewError('storyboard shots changed during review')
            result = run_model_review(directory, rows, project_dir=pdir, model=model, ctx=ctx)
        check_current()
        return result
    def edit_moments(ids, instruction):
        nonlocal revision, inputs
        check_current()
        old_shots = open_project(pdir).resolve().get('shots') or []
        fn = edit_fn or edit.run_edit
        result = fn(pid, pdir, instruction, {'moments': ids}, model=model, ctx=ctx, **seams)
        new_shots = open_project(pdir).resolve().get('shots') or []
        changed = changed_shots(old_shots, new_shots)
        revision = legacy._revision(pdir)
        inputs = legacy._input_signature(pdir)
        return {'changed': changed, 'missing': result.get('missing_moments', {})}
    result = review_and_repair(current_rows, review_shots, edit_moments)
    with save_lock(pdir):
        check_current()
        legacy.save_report(pdir, {**result, 'revision': revision, 'inputs': inputs})
    ctx.progress(1.0, 'Đã xem lại storyboard.')
    return result


def start(pid, project_dir, *, manager=None, run_ok=False, model=None, **seams):
    """Start one review job, holding the same agent slot as visual editing."""
    from pathlib import Path
    from bti.draft import run as draft_run
    from bti.picks.auto import inputs, session
    from bti.longjob import Part
    from bti.visual import store
    pdir = Path(project_dir)
    if not store.load(pdir) or not (pdir / 'storyboard.json').is_file():
        raise inputs.AutoError('validation_failed', 'Cần kịch bản hình và storyboard.', 409)
    resolved = draft_run._resolve(pdir, 'draft', model)
    session.check_installed(resolved.model)
    if manager is None:
        from bti.longjob import manager
    other = draft_run.other_agent_job(pid, 'draft', manager, run_ok=run_ok)
    if other:
        raise inputs.AutoError('agent_job_running', 'Another agent is working on this project.', 409, job_id=other.get('id'))
    if run_ok:
        # Automatic runs never spend on web search, including review repairs.
        seams['web'] = {'on': False, 'max': 0}
    def run(ctx):
        return run_job(pid, pdir, resolved.model, ctx, **seams)
    return manager.start(kind='draft', pid=pid, project_dir=pdir,
                         parts=[Part('review', 'Xem lại storyboard', run)],
                         meta={'action': 'review', 'visual_action': 'review', 'model': resolved.model, 'agent': resolved.public()})


from fastapi import APIRouter, Body, Request
router = APIRouter(prefix='/api/projects/{pid}/visual')


@router.post('/review')
def post_review(pid: str, request: Request, body: dict = Body(default={})):
    from bti.editor.common import ApiError
    from bti.editor.picks_api import _pdir
    from bti.editor.auto_api import actor_of
    from bti.auto import RUN_ACTOR
    from bti.picks.auto.inputs import AutoError
    from bti.draft.inputs import DraftError
    from bti.longjob import Busy
    try:
        result = start(pid, _pdir(request, pid), model=body.get('model'),
                       manager=getattr(request.app.state, 'longjob_manager', None), run_ok=actor_of(body) == RUN_ACTOR)
    except AutoError as exc:
        raise ApiError(exc.status, exc.message, code=exc.code, **exc.extra) from exc
    except DraftError as exc:
        raise ApiError(409, exc.message, code=exc.code) from exc
    except Busy as exc:
        raise ApiError(409, 'An agent job is already running.', code='busy', job_id=exc.job_id) from exc
    return {'job_id': result['id'], 'model': (result.get('meta') or {}).get('model'), 'agent': (result.get('meta') or {}).get('agent')}
