// "Lịch sử thay đổi" (worker c2box): the pure parts of the list of changes on both pages.
import test from 'node:test';
import assert from 'node:assert/strict';
import { whenLabel, whoLabel, undoTarget, changeRows, undoBody } from '../../bti/editor/static/js/changeslogic.js';
import { BOX_LABELS } from '../../bti/editor/static/js/labels.js';
import { isVietnamese } from '../../bti/editor/static/js/errmsg.js';

const AGENTS = { agents: [{ id: 'gemini', label: 'Gemini 3.8 Flash', model: 'agy:gemini-3.8-flash-high' }, { id: 'opus', label: 'Opus 5.5 High', model: 'claude:claude-opus-5-5@high' }] };
const NOW = new Date(2026, 10, 19, 16, 0, 0);

test('the time of a change is the clock of today, or the clock with the day', () => {
  assert.equal(whenLabel('2026-11-19T14:20:05+0700', NOW), '14:20');
  assert.equal(whenLabel('2026-11-18T09:05:00+0700', NOW), '09:05 ngày 18/11');
  assert.equal(whenLabel('2025-12-31T23:59:00+0700', NOW), '23:59 ngày 31/12/2025');
  assert.equal(whenLabel('', NOW), '');
  assert.equal(whenLabel('not a time', NOW), '');
});

test('who made a change: "Bạn", the label of the agent, never the raw actor', () => {
  assert.equal(whoLabel('human', AGENTS), BOX_LABELS.changes.you);
  assert.equal(whoLabel('agent:agy:gemini-3.8-flash-high', AGENTS), 'Gemini 3.8 Flash');
  assert.equal(whoLabel('agent:claude:claude-opus-5-5@high', AGENTS), 'Opus 5.5 High');
  assert.equal(whoLabel('cli:bti', AGENTS), BOX_LABELS.changes.tool);
  assert.doesNotMatch(whoLabel('agent:agy:something-new', null), /agent:|agy:/);          // an agent the list does not offer: "Agent something-new", not the raw id
  assert.ok(isVietnamese(whoLabel('', null)) || whoLabel('', null) === BOX_LABELS.changes.agent);
});

test('the undo the state names: the batch of the action changes.undo, only when it is ready', () => {
  const state = { next_actions: [{ id: 'picks.ops', ready: true, path: '/api/projects/p/picks/ops' },
    { id: 'changes.undo', ready: true, step: 'edit', path: '/api/projects/p/changes/batch_0007/undo', body: { base_rev: 'abc', actor: 'agent:x', note: '' } }] };
  const t = undoTarget(state);
  assert.deepEqual([t.batch, t.step, t.path], ['batch_0007', 'edit', '/api/projects/p/changes/batch_0007/undo']);
  assert.deepEqual(undoBody(t), { base_rev: 'abc', actor: 'human', note: '' });             // the page undoes as the owner
  assert.equal(undoTarget({ next_actions: [{ id: 'changes.undo', ready: false, path: '/api/projects/p/changes/batch_0007/undo' }] }), null);
  assert.equal(undoTarget({ next_actions: [] }), null);
  assert.equal(undoTarget(null), null);
});

test('the rows: newest first as given, the owner\'s request as the note, the sentences, undo only on the row the state names', () => {
  const recs = [
    { batch: 'batch_0003', time: '2026-11-19T14:20:05+0700', actor: 'human', note: '', undo_of: 'batch_0002', changes: [{ what: 'Cảnh 2: trở lại như trước khi sửa' }], undone_by: null },
    { batch: 'batch_0002', time: '2026-11-19T14:10:00+0700', actor: 'agent:agy:gemini-3.8-flash-high', note: 'làm vòng sáng to hơn', undo_of: null,
      changes: [{ what: 'Cảnh 2: đổi thiết lập rx, ry' }, { what: 'Cảnh 2: thêm lớp phủ Vòng khoanh' }], undone_by: 'batch_0003' },
    { batch: 'batch_0001', time: '2026-11-18T09:00:00+0700', actor: 'agent:claude:claude-opus-5-5@high', note: 'bỏ chữ', undo_of: null, changes: [{ what: 'Cảnh 5: bỏ lớp phủ Chữ' }], undone_by: null },
  ];
  const target = { batch: 'batch_0003' };
  const rows = changeRows(recs, { agents: AGENTS, now: NOW, target });
  assert.deepEqual(rows.map((r) => r.batch), ['batch_0003', 'batch_0002', 'batch_0001']);
  assert.deepEqual(rows.map((r) => r.who), ['Bạn', 'Gemini 3.8 Flash', 'Opus 5.5 High']);
  assert.deepEqual(rows.map((r) => r.when), ['14:20', '14:10', '09:00 ngày 18/11']);
  assert.deepEqual(rows.map((r) => r.canUndo), [true, false, false]);
  assert.deepEqual(rows.map((r) => r.undone), [false, true, false]);
  assert.deepEqual(rows.map((r) => r.isUndo), [true, false, false]);
  assert.equal(rows[1].note, 'làm vòng sáng to hơn');
  assert.equal(rows[0].note, '');                                                          // an undo has no request
  assert.deepEqual(rows[1].lines, ['Cảnh 2: đổi thiết lập rx, ry', 'Cảnh 2: thêm lớp phủ Vòng khoanh']);
  assert.deepEqual(changeRows(recs, { agents: AGENTS, now: NOW, target: null }).map((r) => r.canUndo), [false, false, false]);
  assert.deepEqual(changeRows(null), []);
  assert.deepEqual(changeRows([{}]).map((r) => [r.batch, r.lines, r.canUndo]), [['', [], false]]);          // a damaged record never throws
});

test('the words of the list are Vietnamese and short', () => {
  const C = BOX_LABELS.changes;
  for (const k of ['title', 'empty', 'you', 'tool', 'undo', 'undone', 'undoOf', 'undoDone', 'undoHint']) assert.ok(isVietnamese(C[k]), k);
  assert.equal(C.title, 'Lịch sử thay đổi');
  assert.equal(C.undo, 'Hoàn tác');
  assert.doesNotMatch(JSON.stringify([C.title, C.empty, C.undoDone]), /!/);
});
