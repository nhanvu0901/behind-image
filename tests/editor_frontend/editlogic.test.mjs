// "Sửa video bằng lời": the pure parts (scope words, default scope, turn cards for every status, progress, clock, preview range,
// settings rows) and the list of codes with their Vietnamese sentences.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {
  EDIT_CODES, TURN_STATUS, clockTime, minSec, durationWords, chapterLabel, chapterAt, scopeWords, pickScope, retryScope, addToSelection,
  codeText, normStatus, wayLine, turnView, quotaView, parseMoment, whenWords, modelName, modelOptionText, modelListState, progressView, previewRange, takeInPlan, newlyChanged, modelRows, modelChanges, applyAllModels,
} from '../../bti/editor/static/js/editlogic.js';
import { stageErrorText, isVietnamese } from '../../bti/editor/static/js/errmsg.js';
import { EDIT_LABELS, SETTINGS_LABELS } from '../../bti/editor/static/js/labels.js';

const ROOT = new URL('../../', import.meta.url).pathname;
const SHOTS = [{ id: 's0001', _t0: 0, _t1: 4 }, { id: 's0002', _t0: 4, _t1: 9 }, { id: 's0003', _t0: 9, _t1: 12 }, { id: 's0004', _t0: 12, _t1: 20 }];
const CHAPS = [{ id: 'c01', name: 'Cold Open', start: 0, end: 9 }, { id: 'c02', name: 'The Merchant', start: 9, end: 20 }, { id: 'c03', name: 'c03', start: 20, end: 30 }];

test('the clock is 24-hour and never follows the browser language', () => {
  assert.equal(clockTime('2026-11-18T18:30:54'), '18:30:54');
  assert.equal(clockTime('2026-11-18T01:00:00'), '01:00:00');
  assert.equal(clockTime('2026-11-18 06:05:09.123'), '06:05:09');
  assert.equal(clockTime(''), '');
  assert.equal(clockTime('not a date'), '');
  assert.doesNotMatch(clockTime('2026-11-18T18:30:54'), /AM|PM/i);
});

test('positions and durations in words', () => {
  assert.equal(minSec(65.9), '1:05');
  assert.equal(minSec(0), '0:00');
  assert.equal(durationWords(2.45), '2,5 giây');
  assert.equal(durationWords(80), '1 phút 20 giây');
  assert.equal(durationWords(0), '');
});

test('scope words: shot numbers and chapter names, never a raw id', () => {
  assert.equal(scopeWords({ kind: 'shots', shots: ['s0002'] }, { shots: SHOTS, current: true }), 'Cảnh 2 đang chọn');
  assert.equal(scopeWords({ kind: 'shots', shots: ['s0003', 's0001'] }, { shots: SHOTS, current: true }), '2 cảnh đang chọn (1, 3)');
  assert.equal(scopeWords({ kind: 'shots', shots: ['s0003', 's0001'] }, { shots: SHOTS }), '2 cảnh (1, 3)');
  assert.equal(scopeWords({ kind: 'chapter', chapter: 'c02' }, { chapters: CHAPS }), 'Chương: The Merchant');
  assert.equal(scopeWords({ kind: 'chapter', chapter: 'c03' }, { chapters: CHAPS }), 'Chương 3');            // a name that is the id is not shown
  assert.equal(scopeWords({ kind: 'chapter', chapter: 'zz' }, { chapters: CHAPS }), 'Một chương');
  assert.equal(scopeWords({ kind: 'all' }), 'Cả video');
  const many = Array.from({ length: 9 }, (_, i) => ({ id: 'x' + i }));
  assert.match(scopeWords({ kind: 'shots', shots: many.map((s) => s.id) }, { shots: many }), /và 3 cảnh nữa/);
  for (const w of [scopeWords({ kind: 'shots', shots: ['s0002'] }, { shots: SHOTS }), scopeWords({ kind: 'chapter', chapter: 'c01' }, { chapters: CHAPS })]) assert.doesNotMatch(w, /\bs\d{4}\b|\bc\d\d\b/);
  assert.equal(chapterLabel(null, -1), 'Chương 1');
});

test('the default scope is the selected shot, else the chapter at the playhead; choosing wins', () => {
  const base = { shots: SHOTS, chapters: CHAPS, t: 10 };
  let r = pickScope({ ...base, selected: ['s0002'] });
  assert.deepEqual([r.kind, r.payload, r.ok], ['shots', { shots: ['s0002'] }, true]);
  assert.equal(r.words, 'Cảnh 2 đang chọn');
  r = pickScope({ ...base, selected: [] });
  assert.deepEqual([r.kind, r.payload], ['chapter', { chapter: 'c02' }]);
  assert.equal(r.words, 'Chương: The Merchant');
  r = pickScope({ ...base, selected: ['s0002'], choice: 'chapter' });
  assert.deepEqual(r.payload, { chapter: 'c02' });
  r = pickScope({ ...base, selected: ['s0002'], choice: 'all' });
  assert.deepEqual(r.payload, { all: true });
  r = pickScope({ ...base, selected: ['gone'], choice: 'shots' });
  assert.equal(r.ok, false);
  assert.ok(r.why);
  r = pickScope({ shots: SHOTS, chapters: [], selected: [], t: 0 });
  assert.deepEqual(r.payload, { all: true });                                  // no chapters: the whole video, never an empty scope
  r = pickScope({ ...base, selected: ['s0001', 's0004'], choice: 'shots' });
  assert.deepEqual(r.payload, { shots: ['s0001', 's0004'] });
});

test('chapter at the playhead: by time, else by word range, else the first', () => {
  assert.equal(chapterAt(CHAPS, 12).id, 'c02');
  assert.equal(chapterAt([{ id: 'a', w0: 0, w1: 5 }, { id: 'b', w0: 5, w1: 9 }], 3, 6).id, 'b');
  assert.equal(chapterAt([{ id: 'a' }], 3, -1).id, 'a');
  assert.equal(chapterAt([], 3), null);
});

test('choosing several shots: clicks add only while the switch is on and the playhead is not moving the selection', () => {
  assert.deepEqual(addToSelection(['s0001'], 's0003', { multi: true }), ['s0001', 's0003']);
  assert.deepEqual(addToSelection(['s0001'], 's0001', { multi: true }), ['s0001']);
  assert.deepEqual(addToSelection(['s0001'], 's0003', { multi: false }), ['s0001']);
  assert.deepEqual(addToSelection(['s0001'], 's0003', { multi: true, playing: true }), ['s0001']);
  assert.deepEqual(addToSelection([], null, { multi: true }), []);
});

test('retry keeps the scope of the old turn and drops shots that are gone', () => {
  assert.deepEqual(retryScope({ scope: { kind: 'shots', shots: ['s0001', 'gone'] } }, SHOTS), { shots: ['s0001'] });
  assert.equal(retryScope({ scope: { kind: 'shots', shots: ['gone'] } }, SHOTS), null);
  assert.deepEqual(retryScope({ scope: { kind: 'chapter', chapter: 'c02' } }, SHOTS), { chapter: 'c02' });
  assert.deepEqual(retryScope({ scope: { kind: 'all' } }, SHOTS), { all: true });
});

const TURN = {
  id: 't1', at: '2026-11-18T18:00:09', instruction: 'zoom chậm hơn', scope: { kind: 'shots', shots: ['s0001', 's0002'] }, status: 'applied', has_undo: true,
  path: 'fast', seconds: 2.45, summary: 'Đã làm chậm chuyển động zoom ở hai cảnh.',
  changes: [{ shot_id: 's0001', number: 1, start: 0, op: 'changed', what: 'Giảm tốc độ zoom' }, { shot_id: 's0002', number: 2, start: 4, op: 'changed', what: 'Thêm vòng sáng quanh gương' }],
};

test('turn card: every status has a badge, a tone and its own actions', () => {
  const env = { shots: SHOTS, chapters: CHAPS };
  const by = (patch) => turnView({ ...TURN, ...patch }, env);
  for (const s of TURN_STATUS) { const v = by({ status: s }); assert.equal(v.status, s); assert.ok(isVietnamese(v.badge), s); assert.ok(v.tone, s); }
  let v = by({});
  assert.equal(v.badge, 'Đã áp dụng');
  assert.equal(v.time, '18:00:09');
  assert.equal(v.scope, '2 cảnh (1, 2)');
  assert.equal(v.headline, TURN.summary);
  assert.equal(v.way, 'sửa nhanh · mất 2,5 giây');
  assert.deepEqual(v.changes.map((c) => [c.title, c.opText, c.hasBefore, c.hasAfter]), [['Cảnh 1 · 0:00', 'Đổi', true, true], ['Cảnh 2 · 0:04', 'Đổi', true, true]]);
  assert.deepEqual([v.actions.preview, v.actions.undo, v.actions.choices, v.actions.cancel, v.actions.retry], [true, 'yes', false, false, false]);
  assert.equal(by({ has_undo: false }).actions.undo, 'gone');
  v = by({ status: 'running', summary: '' });
  assert.deepEqual([v.actions.cancel, v.actions.undo, v.actions.preview], [true, '', false]);
  v = by({ status: 'needs_choice', conflicts: ['s0002'] });
  assert.equal(v.actions.choices, true);
  assert.match(v.extra, /cảnh 2/);
  v = by({ status: 'needs_choice', conflicts: null });
  assert.match(v.extra, /cảnh 1, 2/);                                            // no list from the server: the shots of the turn
  v = by({ status: 'needs_choice', conflicts: [], changes: [] });
  assert.match(v.extra, /cảnh 1, 2/);                                            // nothing recorded yet: the shots of the scope
  v = by({ status: 'needs_choice', conflicts: [{ kind: 'shot', id: 's0002', reason: 'both sides modified shot' }] });
  assert.match(v.extra, /cảnh 2\./);                                              // the server's own shape: {kind, id, reason}
  v = by({ status: 'needs_choice', conflicts: [{ kind: 'list', reason: 'shot structure changed' }] });
  assert.equal(v.extra, EDIT_LABELS.choiceLeadList);
  v = by({ status: 'failed', error: 'undo_conflict', summary: '' });
  assert.equal(v.actions.retry, true);
  assert.equal(v.headline, stageErrorText('draft', { body: { code: 'undo_conflict' } }).text);
  assert.match(v.detail, /undo_conflict/);                                      // the raw code only under "chi tiết"
  assert.doesNotMatch(v.headline + v.extra, /undo_conflict/);
  v = by({ status: 'cancelled', error: 'cancelled' });
  assert.equal(v.headline, EDIT_LABELS.cancelled);
  assert.deepEqual([v.actions.undo, v.actions.retry], ['', false]);
  v = by({ status: 'undone' });
  assert.equal(v.headline, EDIT_LABELS.undone);
  assert.equal(v.showChanges, false);
  v = by({ status: 'no_change', summary: 'Cần một tranh mới, dự án chưa có.' });
  assert.equal(v.headline, 'Cần một tranh mới, dự án chưa có.');
  assert.equal(v.extra, EDIT_LABELS.noChangeHelp);
});

test('turn card: English or id-like model text goes only under "chi tiết"', () => {
  const v = turnView({ ...TURN, summary: 'Reduced zoom on s0001', notes: 'AN-01 reduced from 8', changes: [{ shot_id: 's0001', number: 1, start: 0, op: 'changed', what: 'slower pan' }] }, { shots: SHOTS });
  assert.equal(v.headline, EDIT_LABELS.applied);
  assert.equal(v.changes[0].what, '');
  assert.match(v.detail, /Reduced zoom/);
  assert.match(v.detail, /AN-01 reduced/);
  assert.match(v.detail, /slower pan/);
  const shown = [v.headline, v.extra, v.way, v.scope, v.badge, ...v.changes.map((c) => c.title + c.opText + c.what)].join(' ');
  assert.doesNotMatch(shown, /s0001|AN-01|Reduced|slower/);
});

test('turn card: added and removed shots have one side of the pictures only; a removed shot cannot be previewed', () => {
  const v = turnView({ ...TURN, changes: [{ shot_id: 'n1', number: 3, start: 9, op: 'added', what: 'Cảnh mới' }, { shot_id: 'o1', number: 4, start: 12, op: 'removed', what: 'Bỏ cảnh thừa' }] }, { shots: SHOTS });
  assert.deepEqual(v.changes.map((c) => [c.opText, c.hasBefore, c.hasAfter]), [['Thêm', false, true], ['Xóa', true, false]]);
  assert.equal(v.actions.preview, true);
  assert.equal(turnView({ ...TURN, changes: [{ shot_id: 'o1', number: 4, start: 12, op: 'removed', what: 'Bỏ' }] }, {}).actions.preview, false);
  assert.equal(turnView({ ...TURN, changes: [] }, {}).noChanges, true);
});

test('statuses of older threads are mapped: done is an old proposal, error and refused are failures', () => {
  assert.equal(normStatus('done'), 'old');
  assert.equal(normStatus('error'), 'failed');
  assert.equal(normStatus('refused'), 'failed');
  assert.equal(normStatus('???'), 'failed');
  assert.equal(normStatus('applied'), 'applied');
  const v = turnView({ id: 'x', instruction: 'a', status: 'refused', error: 'edit_outside_scope', summary: 'Cảnh 14 và 15 nằm ngoài phần bạn chọn.' }, {});
  assert.equal(v.badge, EDIT_LABELS.status.failed);
  assert.match(v.extra, /Cảnh 14 và 15/);
});

test('the list of codes: every code of the edit routes has a Vietnamese sentence and codeText never returns a code', () => {
  for (const c of EDIT_CODES) {
    const t = codeText(c);
    assert.ok(isVietnamese(t), c);
    assert.notEqual(t, EDIT_LABELS.failedGeneric, `${c} has no sentence of its own`);
    assert.doesNotMatch(t, /[a-z]_[a-z]/, c);
    assert.equal(stageErrorText('draft', { status: 409, body: { code: c } }).text, t, c);
  }
  assert.equal(codeText('something_new'), EDIT_LABELS.failedGeneric);
  assert.equal(codeText(null), EDIT_LABELS.failedGeneric);
});

test('every error code the server raises for an edit, an undo, a resolve or a setting is in the list', () => {
  const found = new Set();
  const scan = (f) => {
    const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
    for (const m of src.matchAll(/(?:DraftError|PartError|SettingsError)\(\s*["']([a-z_]+)["']/g)) found.add(m[1]);
    for (const m of src.matchAll(/\bcode\s*=\s*["']([a-z_]+)["']/g)) found.add(m[1]);
    for (const m of src.matchAll(/\berror\s*=\s*["']([a-z_]+)["']/g)) found.add(m[1]);
  };
  for (const f of ['bti/editor/draft_api.py', 'bti/draft/run.py', 'bti/draft/thread.py', 'bti/draft/fastedit.py', 'bti/draft/merge.py',
    'bti/draft/boxops.py', 'bti/draft/picksedit.py', 'bti/editor/boxroutes.py']) scan(f);          // c2box: the typed-operations box
  // not an edit code: the picks/draft whole-video start, the settings (own table), or never shown
  const OTHER = new Set(['bad_provider', 'bad_chapters', 'draft_not_ready', 'picks_missing', 'timing_missing', 'busy', 'longjob_running']);
  const missing = [...found].filter((c) => !EDIT_CODES.includes(c) && !OTHER.has(c) && !stageErrorText('draft', { body: { code: c } }).text.startsWith('Có lỗi'));
  assert.deepEqual(missing, []);
  const unsaid = [...found].filter((c) => !isVietnamese(stageErrorText('draft', { status: 422, body: { code: c } }).text));
  assert.deepEqual(unsaid, []);
});

test('the settings codes have sentences too', () => {
  for (const c of ['invalid_payload', 'unknown_role', 'invalid_model', 'agentic_role_needs_agy', 'unknown_model']) assert.ok(isVietnamese(stageErrorText('settings', { status: 422, body: { code: c } }).text), c);
});

test('progress line: words from labels, never the model\'s raw text', () => {
  const P = EDIT_LABELS.progress;
  const j = (key, note, progress = 0.3) => ({ progress, parts: [{ key: 'prepare', state: 'done' }, { key, state: 'running', note }] });
  assert.equal(progressView(j('edit', 'Đang nghĩ…')).line, P.think);
  assert.equal(progressView(j('edit', 'Đang kiểm tra…')).line, P.check);
  assert.equal(progressView(j('edit', 'Chuyển sang phân tích sâu…')).line, P.deep);
  assert.equal(progressView(j('agent', 'Bước 86, agent_response; đã viết 1/1 chương.')).line, P.agentStep(86));
  assert.doesNotMatch(progressView(j('agent', 'Bước 86, agent_response')).line, /agent_response/);
  assert.equal(progressView(j('apply', '')).line, P.write);
  assert.equal(progressView({ progress: 0, parts: [{ key: 'prepare', state: 'queued' }] }).line, P.prepare);
  assert.equal(progressView({ progress: 0, parts: [] }).line, P.queued);
  assert.equal(progressView({ progress: 7, parts: [] }).fraction, 1);
  assert.equal(progressView(null).fraction, 0);
});

test('preview range: the changed shots as they are now, at most 10 seconds', () => {
  assert.deepEqual(previewRange(TURN, SHOTS), { t0: 0, t1: 9 });
  assert.deepEqual(previewRange({ changes: [{ shot_id: 's0004', op: 'changed', start: 12 }] }, SHOTS), { t0: 12, t1: 20 });
  assert.deepEqual(previewRange({ changes: [{ shot_id: 's0001', op: 'changed', start: 0 }, { shot_id: 's0004', op: 'changed', start: 12 }] }, SHOTS), { t0: 0, t1: 10 });
  assert.deepEqual(previewRange({ changes: [{ shot_id: 'gone', op: 'changed', start: 30 }] }, SHOTS), { t0: 30, t1: 34 });
  assert.equal(previewRange({ changes: [{ shot_id: 's0001', op: 'removed', start: 0 }] }, SHOTS), null);
  assert.equal(previewRange({}, SHOTS), null);
});

test('taking a turn in: reload with no unsaved edits, merge with unsaved ones; only a new state of an applied or undone turn counts', () => {
  assert.equal(takeInPlan(false), 'reload');
  assert.equal(takeInPlan(true), 'merge');
  const seen = new Map();
  assert.deepEqual(newlyChanged([{ id: 'a', status: 'applied' }], seen, true), []);                          // the first look only remembers
  assert.deepEqual(newlyChanged([{ id: 'a', status: 'applied' }], seen, false), []);
  assert.deepEqual(newlyChanged([{ id: 'a', status: 'applied' }, { id: 'b', status: 'running' }], seen, false), []);
  assert.deepEqual(newlyChanged([{ id: 'a', status: 'applied' }, { id: 'b', status: 'applied' }], seen, false).map((t) => t.id), ['b']);   // job ended
  assert.deepEqual(newlyChanged([{ id: 'a', status: 'undone' }, { id: 'b', status: 'applied' }], seen, false).map((t) => t.id), ['a']);       // undone elsewhere
  assert.deepEqual(newlyChanged([{ id: 'c', status: 'failed' }, { id: 'a', status: 'undone' }], seen, false), []);                           // a failure changes nothing
  assert.deepEqual(newlyChanged([{ id: 'c', status: 'needs_choice' }], seen, false), []);
  assert.deepEqual(newlyChanged([{ id: 'c', status: 'applied' }], seen, false).map((t) => t.id), ['c']);                                      // chosen: overwrite
});

const RESP = {
  roles: [
    { role: 'draft', label: 'Dựng', value: 'agy:a', model: 'agy:a', source: 'setting', agentic: true },
    { role: 'edit.fast', label: 'Sửa nhanh', value: 'agy:a', source: 'default', agentic: false },
    { role: 'script.outline', label: 'Dàn ý', value: 'mock', source: 'default', agentic: false },
  ],
  models: [{ id: 'agy:a', name: 'Model A' }, { id: 'agy:b', name: 'Model B' }, { id: 'mock', name: 'Mock' }],
};

test('settings: a row per role, agentic roles only offer agy models, only changed roles are saved, "all" skips roles that cannot use it', () => {
  const rows = modelRows(RESP);
  assert.deepEqual(rows.map((r) => r.role), ['draft', 'edit.fast', 'script.outline']);
  assert.deepEqual(rows[0].options, ['agy:a', 'agy:b']);
  assert.deepEqual(rows[1].options, ['agy:a', 'agy:b', 'mock']);
  assert.equal(rows[0].fromSetting, true);
  const values = Object.fromEntries(rows.map((r) => [r.role, r.value]));
  assert.deepEqual(modelChanges(rows, values), {});
  assert.deepEqual(modelChanges(rows, { ...values, 'edit.fast': 'agy:b' }), { 'edit.fast': 'agy:b' });
  const all = applyAllModels(rows, values, 'agy:b');
  assert.deepEqual(modelChanges(rows, all), { draft: 'agy:b', 'edit.fast': 'agy:b', 'script.outline': 'agy:b' });
  const mock = applyAllModels(rows, values, 'mock');
  assert.deepEqual(modelChanges(rows, mock), { 'edit.fast': 'mock' });
  assert.deepEqual(modelRows(null), []);
});

test('the words of the box and the dialog are Vietnamese', () => {
  const walk = (o, where) => {
    for (const [k, v] of Object.entries(o)) {
      if (typeof v === 'string') { if (!['you'].includes(k)) assert.ok(isVietnamese(v) || /^(chi tiết)$/.test(v) || v.length < 4, `${where}.${k}: ${v}`); }
      else if (v && typeof v === 'object') walk(v, `${where}.${k}`);
    }
  };
  walk(EDIT_LABELS, 'EDIT'); walk(SETTINGS_LABELS, 'SETTINGS');
});

const NOW = new Date(2026, 10, 18, 10, 0, 0);                                   // 18 Nov 2026, 10:00 local

test('quota used up: a time today, a time next week, a time in another year, only a span, and nothing at all', () => {
  const q = (patch) => quotaView({ status: 'failed', error: 'rate_limit', ...patch }, NOW);
  assert.deepEqual(q({ retry_at: '2026-11-18T14:20:00', retry_after_seconds: 15600 }), { headline: 'Mô hình đã dùng hết hạn mức.', extra: 'Mở lại lúc 14:20. Bạn có thể chọn mô hình khác.' });
  assert.equal(q({ retry_at: '2026-11-25T14:20:00' }).extra, 'Mở lại lúc 14:20 ngày 25/11. Bạn có thể chọn mô hình khác.');
  assert.equal(q({ retry_at: '2027-01-02T09:05:00' }).extra, 'Mở lại lúc 09:05 ngày 02/01/2027. Bạn có thể chọn mô hình khác.');
  assert.equal(q({ retry_after_seconds: 3 * 3600 }).extra, 'Mở lại lúc 13:00. Bạn có thể chọn mô hình khác.');              // only a span: the time is worked out
  assert.equal(q({ retry_after_seconds: 7 * 86400 }).extra, 'Mở lại lúc 10:00 ngày 25/11. Bạn có thể chọn mô hình khác.');
  assert.equal(q({}).extra, 'Chưa rõ khi nào mở lại. Bạn có thể chọn mô hình khác.');                                              // fields absent
  assert.equal(q({ retry_at: null, retry_after_seconds: null }).extra, 'Chưa rõ khi nào mở lại. Bạn có thể chọn mô hình khác.');
  assert.equal(q({ retry_at: 'không phải giờ' }).extra, 'Chưa rõ khi nào mở lại. Bạn có thể chọn mô hình khác.');
  assert.equal(quotaView({ error: 'agy_rate_limit' }, NOW).headline, 'Mô hình đã dùng hết hạn mức.');
  assert.equal(quotaView({ error: 'agy_timeout' }, NOW), null);
  assert.equal(quotaView({ error: 'compile_error' }, NOW), null);
  assert.equal(parseMoment(Math.floor(new Date(2026, 10, 18, 14, 20).getTime() / 1000)).getHours(), 14);            // epoch seconds
  assert.match(whenWords(new Date(2026, 10, 18, 7, 3), NOW), /^lúc 07:03$/);
});

test('the failed card for a used-up quota: the sentence, the time, a link to the settings, and the raw code only under "chi tiết"', () => {
  const turn = { id: 't', instruction: 'x', status: 'failed', error: 'rate_limit', retry_at: '2026-11-18T14:20:00', summary: 'Hết lượt.', scope: { kind: 'all' } };
  const v = turnView(turn, { shots: SHOTS, chapters: CHAPS, now: NOW });
  assert.equal(v.headline, 'Mô hình đã dùng hết hạn mức.');
  assert.match(v.extra, /Mở lại lúc 14:20/);
  assert.match(v.extra, /chọn mô hình khác/);
  assert.equal(v.actions.settings, true);
  assert.equal(v.actions.retry, true);
  assert.doesNotMatch(v.headline + v.extra, /rate_limit/);
  assert.match(v.detail, /rate_limit/);
  const w = turnView({ ...turn, retry_at: undefined }, { shots: SHOTS, now: NOW });                                   // fields absent: still reads well
  assert.match(w.extra, /^Chưa rõ khi nào mở lại\. Bạn có thể chọn mô hình khác\.$/);
  assert.equal(w.actions.settings, true);
  assert.equal(turnView({ ...turn, error: 'compile_error', retry_at: undefined }, { shots: SHOTS, now: NOW }).actions.settings, false);
});

const REAL = {                                                                  // the shape of a real answer of GET /api/settings/models
  roles: [
    { role: 'draft', label: 'Dựng storyboard', value: 'agy:gemini-3.8-flash-high', agentic: true, source: 'default' },
    { role: 'edit.fast', label: 'Sửa nhanh', value: 'agy:gemini-3.8-flash-medium', agentic: false, source: 'setting' },
    { role: 'picks', label: 'Chọn hình', value: 'agy:gone-model', agentic: false, source: 'default' },
  ],
  models: [
    { id: 'agy:gemini-3.8-flash-high', label: 'Antigravity CLI: Gemini 3.8 Flash (High)', provider: 'antigravity', enabled: true, agy: { ok: true, reason: null } },
    { id: 'agy:gemini-3.8-flash-medium', label: 'Antigravity CLI: Gemini 3.8 Flash (Medium)', provider: 'antigravity', enabled: true, agy: { ok: true, reason: null } },
    { id: 'mock', label: 'Mock (thử, không gọi mạng)', provider: 'mock', enabled: true },
    { id: 'openrouter-claude', label: 'Claude qua OpenRouter', provider: 'openrouter', enabled: false, message: 'thiếu biến OPENROUTER_API_KEY' },
  ],
};
const DOWN = { roles: REAL.roles, models: [{ id: 'agy', label: 'Antigravity CLI', provider: 'antigravity', enabled: false, agy: { ok: false, reason: 'config' }, message: 'agy chưa cài' }, REAL.models[2]] };

test('settings, normal case: the name with the id as secondary text, only usable models, a missing current value keeps its note', () => {
  assert.equal(modelListState(REAL), 'ok');
  assert.equal(modelName(REAL.models, 'agy:gemini-3.8-flash-high'), 'Antigravity CLI: Gemini 3.8 Flash (High)');
  assert.equal(modelOptionText(REAL.models, 'agy:gemini-3.8-flash-high'), 'Antigravity CLI: Gemini 3.8 Flash (High) (agy:gemini-3.8-flash-high)');
  assert.equal(modelOptionText(REAL.models, 'mock'), 'Mock (thử, không gọi mạng) (mock)');
  assert.equal(modelOptionText(REAL.models, 'agy:gone-model'), 'agy:gone-model');                                       // not in the list: no name to show
  const rows = modelRows(REAL);
  assert.deepEqual(rows[0].options, ['agy:gemini-3.8-flash-high', 'agy:gemini-3.8-flash-medium']);                    // agent role: agy only
  assert.deepEqual(rows[1].options, ['agy:gemini-3.8-flash-high', 'agy:gemini-3.8-flash-medium', 'mock']);            // the model without a key is not offered
  assert.equal(rows[2].options.includes('agy:gone-model'), false);                                                   // the dialog adds it, with the note
});

test('settings, agy gave no list: one state for the whole dialog, agy entry is not a model', () => {
  assert.equal(modelListState(DOWN), 'down');
  assert.equal(modelListState({ roles: [], models: [] }), 'down');
  assert.equal(modelListState(null), 'down');
  assert.deepEqual(modelRows(DOWN)[1].options, ['mock']);
  assert.deepEqual(modelRows(DOWN)[0].options, []);
});

// ---------------------------------------------------------------- c2box: the box on typed operations (step 5 and step 4)
import { pickBeatScope, retryBeatScope, beatNumbers } from '../../bti/editor/static/js/editlogic.js';
import { BOX_LABELS } from '../../bti/editor/static/js/labels.js';
import { boxErrorText } from '../../bti/editor/static/js/errmsg.js';

const BATCH_TURN = {
  id: 't2', at: '2026-11-19T10:00:09', instruction: 'làm vòng sáng to hơn', scope: { kind: 'shots', shots: ['s0002'] }, status: 'applied', doc: 'storyboard', has_undo: true,
  path: 'fast', seconds: 14.2, summary: 'Vòng sáng ở cảnh này to hơn.', batch: 'batch_0003',
  batch_changes: [{ target: { shot: 's0002', overlay: 'o1' }, time: '0:04', what: 'Cảnh 2: đổi thiết lập rx, ry của lớp phủ Rọi sáng' }],
  changes: [{ shot_id: 's0002', number: 2, start: 4, op: 'changed', what: 'Cảnh 2: đổi thiết lập rx, ry của lớp phủ Rọi sáng', facts: ['Cảnh 2: đổi thiết lập rx, ry của lớp phủ Rọi sáng', 'Cảnh 2: thêm lớp phủ Vòng khoanh'], what_source: 'batch' }],
};
const PICKS_TURN = {
  id: 't3', at: '2026-11-19T10:05:00', instruction: 'dòng này chỉ cho xem khuôn mặt', scope: { kind: 'beats', beats: ['b0003'], shots: null, chapter: null }, status: 'applied', doc: 'picks',
  has_undo: true, path: 'fast', seconds: 9, summary: 'Dòng này giờ chỉ cho xem khuôn mặt.', batch: 'batch_0004',
  batch_changes: [{ target: { beat: 'b0003' }, time: '0:48', what: 'Đoạn 3: thay 1 hình' }], changes: [],
};

test('c2box: a storyboard card shows the sentences of the batch under the shot, and its undo is the undo of the batch', () => {
  const v = turnView(BATCH_TURN, { shots: SHOTS, chapters: CHAPS });
  assert.equal(v.headline, BATCH_TURN.summary);
  assert.equal(v.doc, 'storyboard');
  assert.deepEqual(v.changes[0].lines, BATCH_TURN.changes[0].facts);                      // both sentences of the batch about this shot
  assert.equal(v.changes[0].title, 'Cảnh 2 · 0:04');
  assert.deepEqual([v.actions.undo, v.actions.preview, v.actions.escalate], ['yes', true, '']);
  assert.equal(turnView({ ...BATCH_TURN, has_undo: false }, {}).actions.undo, 'gone');
  assert.equal(turnView({ ...BATCH_TURN, status: 'undone' }, {}).actions.undo, '');
});

test('c2box: a card of the pictures box shows the batch sentences, has no frames and no preview', () => {
  const v = turnView(PICKS_TURN, { shots: [], chapters: [] });
  assert.equal(v.doc, 'picks');
  assert.equal(v.headline, PICKS_TURN.summary);
  assert.equal(v.showChanges, false);
  assert.equal(v.showSentences, true);
  assert.deepEqual(v.sentences, [{ text: 'Đoạn 3: thay 1 hình', time: '0:48' }]);
  assert.equal(v.actions.preview, false);
  assert.equal(v.actions.undo, 'yes');
  assert.equal(v.noChanges, false);
  assert.equal(turnView({ ...PICKS_TURN, summary: '' }, {}).headline, BOX_LABELS.pictures.applied);              // never an empty card
});

test('c2box: escalate offers the slower way on step 5 and the search by hand on step 4, and says plainly it changes nothing', () => {
  const reason = 'Chi tiết này chưa có vùng nào trên tranh, cần bước xem tranh kỹ hơn.';
  const sb = turnView({ id: 't4', instruction: 'zoom vào nhẫn', scope: { kind: 'shots', shots: ['s0001'] }, status: 'escalate', doc: 'storyboard', reason, summary: reason, path: 'fast' }, { shots: SHOTS });
  assert.equal(sb.badge, BOX_LABELS.status.escalate);
  assert.equal(sb.headline, reason);
  assert.equal(sb.extra, BOX_LABELS.slow.hint);
  assert.match(sb.extra, /vài phút/);
  assert.equal(sb.actions.escalate, 'slow');
  assert.deepEqual([sb.actions.undo, sb.actions.retry, sb.actions.preview], ['', false, false]);
  const pk = turnView({ id: 't5', instruction: 'thêm bản đồ', scope: { kind: 'beats', beats: ['b0001'] }, status: 'escalate', doc: 'picks', reason, summary: reason }, {});
  assert.equal(pk.actions.escalate, 'agent');                                              // join2: the pictures agent is the first choice, the search by hand the second
  assert.equal(pk.actions.manual, true);
  assert.equal(sb.actions.manual, false);
  assert.equal(pk.extra, BOX_LABELS.pictures.escalate);
  assert.match(pk.extra, /agent chọn hình/);
  assert.match(pk.extra, /tìm hình bằng tay/);
  for (const v of [sb, pk]) for (const t of [v.badge, v.headline, v.extra]) assert.ok(isVietnamese(t), t);
});

test('c2box: a reason in English is never the headline of a card: a fixed sentence, the English under "chi tiết"', () => {
  const v = turnView({ id: 't6', instruction: 'cho dài hơn', scope: { kind: 'all' }, status: 'escalate', doc: 'storyboard', reason: 'Select the next shot too.', summary: 'Select the next shot too.' }, {});
  assert.equal(v.headline, BOX_LABELS.escalate);
  assert.match(v.detail, /Select the next shot too/);
  assert.ok(isVietnamese(v.headline));
  const cannot = turnView({ id: 't7', instruction: 'x', scope: { kind: 'all' }, status: 'no_change', doc: 'storyboard', summary: 'Cần một tranh mới, dự án chưa có.', reason: 'Cần một tranh mới, dự án chưa có.' }, {});
  assert.equal(cannot.headline, 'Cần một tranh mới, dự án chưa có.');
});

test('c2box: the slower way states its limits on the card when it starts', () => {
  const v = turnView({ id: 't8', instruction: 'x', scope: { kind: 'all' }, status: 'running', path: 'deep', limits: { minutes: 30, repairs: 2, part_minutes: 35 } }, {});
  assert.match(v.limits, /30 phút/);
  assert.match(v.limits, /2 lần/);
  assert.match(v.limits, /Dừng/);
  assert.equal(turnView({ id: 't9', instruction: 'x', scope: { kind: 'all' }, status: 'running', path: 'fast' }, {}).limits, '');
  assert.equal(turnView({ id: 't9', instruction: 'x', scope: { kind: 'all' }, status: 'running', path: 'deep' }, {}).limits, '');
  assert.match(BOX_LABELS.slow.takes, /vài phút/);
});

test('c2box: a turn refused twice shows the sentence of the last refusal, in plain Vietnamese, with the code only under "chi tiết"', () => {
  for (const code of ['out_of_scope', 'locked', 'unknown_asset', 'unknown_op', 'validation_failed', 'span_mismatch', 'spec_invalid', 'stale_revision']) {
    const v = turnView({ id: 'tx', instruction: 'x', scope: { kind: 'all' }, status: 'failed', error: code, summary: 'Agent định sửa cả phần bạn chưa chọn nên chưa đổi gì.', doc: 'storyboard' }, {});
    assert.ok(isVietnamese(v.headline), code);
    assert.notEqual(v.headline, EDIT_LABELS.failedGeneric, code);
    assert.doesNotMatch(v.headline + v.extra, new RegExp(code), code);
    assert.equal(v.actions.retry, true);
  }
});

test('c2box: no card of any status is empty or says an English word where the owner wrote Vietnamese', () => {
  for (const doc of ['storyboard', 'picks']) for (const status of ['running', 'applied', 'no_change', 'needs_choice', 'failed', 'cancelled', 'undone', 'escalate']) {
    const t = { id: 'tz', instruction: 'x', scope: { kind: 'all' }, status, doc, summary: '', reason: '', error: status === 'failed' ? 'edit_failed' : null, changes: [], batch_changes: [], path: 'fast' };
    const v = turnView(t, {});
    const shown = [v.badge, v.headline, v.extra].filter(Boolean);
    assert.ok(v.badge && (v.headline || v.extra || v.status === 'running'), `${doc}/${status} has something to read`);
    for (const x of shown) assert.ok(isVietnamese(x), `${doc}/${status}: ${x}`);
  }
});

test('c2box: boxErrorText speaks for the errors of both boxes and never shows a code', () => {
  const body = (code) => ({ status: 409, body: { code, detail: 'x', fix: 'y', retry: 'after_fix' } });
  for (const c of ['undo_conflict', 'undo_unavailable', 'stale_revision', 'edit_empty_instruction', 'edit_bad_scope', 'busy', 'already_undone', 'turn_not_applied', 'out_of_scope', 'invalid_field']) {
    const t = boxErrorText(body(c)).text;
    assert.ok(isVietnamese(t), c);
    assert.doesNotMatch(t, new RegExp(c), c);
  }
  assert.match(boxErrorText(body('undo_conflict')).text, /Không hoàn tác được|sửa tiếp/);
});

test('c2box: the scope of the pictures box: the line looked at, several lines, the chapter, the whole video', () => {
  const chapters = [{ id: 'c01', title: 'Mở đầu', beats: [{ id: 'b0001' }, { id: 'b0002' }] }, { id: 'c02', title: 'c02', beats: [{ id: 'b0003' }, { id: 'b0004' }] }];
  assert.deepEqual([...beatNumbers(chapters)], [['b0001', 1], ['b0002', 2], ['b0003', 3], ['b0004', 4]]);
  let s = pickBeatScope({ chapters, selected: ['b0003'], beat: 'b0003' });
  assert.deepEqual([s.kind, s.payload, s.words, s.ok], ['beats', { beats: ['b0003'] }, 'Dòng 3 đang chọn', true]);
  s = pickBeatScope({ chapters, selected: ['b0004', 'b0001'], beat: 'b0004', choice: 'beats' });
  assert.deepEqual([s.payload, s.words], [{ beats: ['b0004', 'b0001'] }, '2 dòng đang chọn (1, 4)']);
  s = pickBeatScope({ chapters, beat: 'b0002' });                                          // nothing selected: the chapter of the line looked at
  assert.deepEqual([s.kind, s.payload, s.words], ['chapter', { chapter: 'c01' }, 'Chương: Mở đầu']);
  s = pickBeatScope({ chapters, beat: 'b0003', choice: 'chapter' });
  assert.equal(s.words, 'Chương 2');                                                       // a title that is the id is not shown
  s = pickBeatScope({ chapters, choice: 'all' });
  assert.deepEqual([s.payload, s.words], [{ all: true }, 'Cả video']);
  s = pickBeatScope({ chapters, choice: 'beats', selected: [] });
  assert.deepEqual([s.ok, s.payload, s.why], [false, null, BOX_LABELS.pictures.noLineChosen]);
  s = pickBeatScope({ chapters: [], choice: 'all' });
  assert.deepEqual([s.ok, s.why], [false, BOX_LABELS.pictures.noNarration]);
  for (const x of [pickBeatScope({ chapters, beat: 'b0002' }).words, pickBeatScope({ chapters, choice: 'beats' }).why]) assert.doesNotMatch(x, /\bb\d{4}\b|\bc\d\d\b/);
});

test('c2box: "Thử lại" on the pictures box drops lines that are gone', () => {
  assert.deepEqual(retryBeatScope({ scope: { kind: 'beats', beats: ['b0003', 'b9999'] } }, ['b0001', 'b0003']), { beats: ['b0003'] });
  assert.equal(retryBeatScope({ scope: { kind: 'beats', beats: ['b9999'] } }, ['b0001']), null);
  assert.deepEqual(retryBeatScope({ scope: { kind: 'chapter', chapter: 'c02' } }, []), { chapter: 'c02' });
  assert.deepEqual(retryBeatScope({ scope: { kind: 'all' } }, []), { all: true });
});

// ---------------------------------------------------------------- join2: a request the box cannot do is handed to the pictures agent, and the card follows it
const AGENT_RUNNING = { id: 't10', at: '2026-11-19T11:00:00', instruction: 'thêm bản đồ Bruges', scope: { kind: 'beats', beats: ['b0004'], shots: null, chapter: null }, status: 'running', doc: 'picks', path: 'agent', escalated: true, job_id: 'j1', reason: 'Dự án chưa có hình bản đồ.' };
const AGENT_DONE = { ...AGENT_RUNNING, status: 'applied', summary: 'Agent đã chọn hình cho 1/1 đoạn.', batch: null, has_undo: false, seconds: 61,
  batch_changes: [{ target: { beat: 'b0004' }, time: '0:59', what: 'Đoạn 4: thay 2 hình' }], result: { lines_total: 1, lines_done: 1, lines_without: [], stopped: null } };

test('join2: the card of an escalated request offers the pictures agent first and the search by hand second, both said in Vietnamese', () => {
  const v = turnView({ ...AGENT_RUNNING, status: 'escalate', path: 'fast', escalated: false, job_id: null, summary: 'Dự án chưa có hình bản đồ.' }, {});
  assert.deepEqual([v.actions.escalate, v.actions.manual, v.actions.undo, v.actions.retry], ['agent', true, '', false]);
  assert.match(BOX_LABELS.pictures.agentButton, /^Để agent chọn hình$/);
  assert.match(BOX_LABELS.pictures.agentHint, /vài phút/);                                  // the button says it takes minutes
  assert.match(BOX_LABELS.pictures.agentTakes, /vài phút/);
  for (const t of [BOX_LABELS.pictures.agentButton, BOX_LABELS.pictures.agentHint, BOX_LABELS.pictures.agentTakes, BOX_LABELS.pictures.agentDone, BOX_LABELS.pictures.agentUndoHint,
    BOX_LABELS.pictures.agentUnusable, BOX_LABELS.pictures.agentWithout([4]), BOX_LABELS.pictures.agentWithout([4, 9])]) assert.ok(isVietnamese(t), t);
});

test('join2: while the pictures agent works the card is a running one that says it takes minutes and has Dừng', () => {
  const v = turnView(AGENT_RUNNING, {});
  assert.equal(v.status, 'running');
  assert.equal(v.actions.cancel, true);
  assert.equal(v.limits, BOX_LABELS.pictures.agentTakes);
  assert.equal(v.way, '');
  assert.equal(wayLine({ ...AGENT_RUNNING, seconds: 61, status: 'applied' }), 'agent chọn hình · mất 1 phút 1 giây');          // never "chuyển sang sửa sâu"
  assert.equal(turnView({ ...AGENT_RUNNING, path: 'deep' }, {}).limits, '');
});

test('join2: the card of a finished agent run says the result, lists the sentences of its batches and sends the owner to the list of changes for the undo', () => {
  const v = turnView(AGENT_DONE, {});
  assert.equal(v.status, 'applied');
  assert.equal(v.headline, 'Agent đã chọn hình cho 1/1 đoạn.');
  assert.equal(v.showSentences, true);
  assert.deepEqual(v.sentences, [{ text: 'Đoạn 4: thay 2 hình', time: '0:59' }]);
  assert.equal(v.actions.undo, '');                                                           // several batches: each is undone from the list of changes
  assert.equal(v.extra, BOX_LABELS.pictures.agentUndoHint);
  assert.match(v.extra, /Lịch sử thay đổi/);
  assert.equal(v.way, 'agent chọn hình · mất 1 phút 1 giây');
  const part = turnView({ ...AGENT_DONE, summary: 'Agent đã chọn hình cho 1/2 đoạn. 1 đoạn chưa có hình phù hợp.', result: { lines_total: 2, lines_done: 1, lines_without: [{ beat: 'b0005', no: 5, why: 'x' }] } }, {});
  assert.match(part.extra, /dòng 5/);
  assert.match(part.extra, /tìm hình bằng tay/);
  assert.equal(turnView({ ...AGENT_DONE, summary: '' }, {}).headline, BOX_LABELS.pictures.agentDone);                        // never an empty card
});

test('join2: a failed or stopped agent run says why in Vietnamese and can be handed over again', () => {
  for (const code of ['picks_auto_no_output', 'picks_auto_limit', 'picks_auto_tampered', 'picks_auto_stale', 'agent_job_running', 'turn_not_escalated', 'picks_approved', 'picks_no_main', 'narration_not_approved']) {
    const t = codeText(code);
    assert.ok(isVietnamese(t), code);
    assert.notEqual(t, EDIT_LABELS.failedGeneric, code);
  }
  const failed = turnView({ ...AGENT_RUNNING, status: 'failed', error: 'picks_auto_limit' }, {});
  assert.equal(failed.headline, codeText('picks_auto_limit'));
  assert.equal(failed.actions.retry, true);
  assert.equal(turnView({ ...AGENT_RUNNING, status: 'cancelled', error: 'cancelled' }, {}).headline, EDIT_LABELS.cancelled);
  const quota = turnView({ ...AGENT_RUNNING, status: 'failed', error: 'agy_rate_limit', retry_after_seconds: 3600 }, { now: new Date('2026-11-19T11:00:00') });
  assert.equal(quota.actions.settings, true);
});

test('join2: the progress line of the pictures agent names its part (1/4 to 4/4) and what it does', () => {
  const job = { progress: 0.1, meta: { action: 'auto' }, parts: [{ key: 'plan', title: 'Lập danh sách hình cần tìm (1/4)', state: 'running', note: 'Agent đang lập danh sách hình: bước 12/80, 3/20 phút.' }, { key: 'search', title: 'Tìm hình (2/4)', state: 'waiting', note: '' }] };
  assert.equal(progressView(job).line, 'Lập danh sách hình cần tìm (1/4) - Agent đang lập danh sách hình: bước 12/80, 3/20 phút.');
  assert.equal(progressView({ ...job, parts: [{ ...job.parts[0], state: 'done' }, { ...job.parts[1], state: 'running', note: '' }] }).line, 'Tìm hình (2/4)');
  assert.equal(progressView({ progress: 0.2, parts: [{ key: 'edit', state: 'running', note: 'Đang nghĩ…' }] }).line, EDIT_LABELS.progress.think);          // the box's own job is unchanged
});

test('join2: no card of the agent path is empty or says an English word', () => {
  for (const status of ['running', 'applied', 'failed', 'cancelled']) {
    const v = turnView({ ...AGENT_RUNNING, status, summary: '', error: status === 'failed' ? 'edit_failed' : null }, {});
    for (const x of [v.badge, v.headline, v.extra, v.limits].filter(Boolean)) assert.ok(isVietnamese(x), `${status}: ${x}`);
    assert.ok(v.badge && (v.headline || v.extra || v.limits || v.status === 'running'), status);
  }
});
