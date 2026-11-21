import test from 'node:test';
import assert from 'node:assert/strict';
import { stepView, nextOpenable, landing } from '../../bti/editor/static/js/stepper.js';

const mk = (states, current) => ({ current, steps: ['artwork', 'script', 'voice', 'picks', 'edit', 'export'].map((id, i) => ({ id, n: i + 1, label: id, state: states[i], reason: states[i] === 'locked' ? 'vì sao khóa' : '', detail: '' })) });

test('a step is openable unless it is locked', () => {
  for (const s of ['done', 'current', 'available', 'not_built', 'no_data']) assert.equal(stepView({ id: 'x', label: 'X', state: s }).openable, true, s);
  assert.equal(stepView({ id: 'x', label: 'X', state: 'locked', reason: 'cần storyboard' }).openable, false);
});

test('each state has its own class and label', () => {
  const v = (state, o = {}) => stepView({ id: 'a', label: 'A', state, reason: 'r', detail: '' }, o);
  assert.match(v('done').cls, /st-done/); assert.equal(v('done').tag, 'Xong');
  assert.match(v('current', { current: 'a' }).cls, /st-current/); assert.equal(v('current', { current: 'a' }).tag, 'Hiện tại');
  assert.match(v('available').cls, /st-available/); assert.equal(v('available').tag, 'Mở được');
  assert.match(v('locked').cls, /st-locked.*disabled/); assert.equal(v('locked').tag, 'Khóa');
  assert.match(v('not_built').cls, /st-not_built/); assert.equal(v('not_built').tag, 'Chưa xây dựng');
  assert.match(v('no_data').cls, /st-no_data/); assert.equal(v('no_data').tag, 'Không có dữ liệu');
});

test('the open step and the step the stage calls for are marked', () => {
  const s = { id: 'voice', label: 'Giọng đọc', state: 'not_built', reason: 'Bước này chưa được xây dựng.' };
  assert.match(stepView(s, { active: true, current: 'voice' }).cls, /active/);
  assert.match(stepView(s, { active: false, current: 'voice' }).cls, /\bat\b/);
  assert.doesNotMatch(stepView(s, { active: false, current: 'script' }).cls, /\bat\b|active/);
  assert.match(stepView(s, { current: 'voice' }).tag, /ở đây/);
});

test('the reason of a locked step is the tooltip', () => {
  const v = stepView({ id: 'edit', label: 'Dựng hình', state: 'locked', reason: 'Chưa có storyboard.' });
  assert.equal(v.title, 'Dựng hình: Chưa có storyboard.');
});

test('Tiếp tục leads to the next step that can be opened (locked steps are skipped, placeholders are not)', () => {
  const p = mk(['done', 'done', 'not_built', 'not_built', 'locked', 'not_built'], 'voice');
  assert.equal(nextOpenable(p.steps, 'script').id, 'voice');
  assert.equal(nextOpenable(p.steps, 'voice').id, 'picks');
  assert.equal(nextOpenable(p.steps, 'picks').id, 'export');       // 'edit' is locked: skipped
  assert.equal(nextOpenable(p.steps, 'export'), null);
  const q = mk(['no_data', 'no_data', 'no_data', 'no_data', 'done', 'not_built'], 'export');
  assert.equal(nextOpenable(q.steps, 'edit').id, 'export');
});

test('opening a project lands on the current step of the pipeline', () => {
  assert.equal(landing(mk(['done', 'current', 'not_built', 'not_built', 'locked', 'not_built'], 'script')), 'script');
  assert.equal(landing(mk(['no_data', 'no_data', 'no_data', 'no_data', 'current', 'not_built'], 'edit')), 'edit');
  assert.equal(landing({ steps: mk(['done', 'locked', 'locked', 'locked', 'locked', 'locked']).steps }), 'artwork');
});
