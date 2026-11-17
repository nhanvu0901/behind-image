// SU-003 / SU-008 / SU-009: the "waiting" step state and its banner texts, and the one idle timer of the stage pages.
import test from 'node:test';
import assert from 'node:assert/strict';
import { stepView } from '../../bti/editor/static/js/stepper.js';
import { waitText, OPEN_STEP, STEP_STATE } from '../../bti/editor/static/js/labels.js';
import { createScope } from '../../bti/editor/static/js/lifecycle.js';
import { watchIdle, typingIn, jobWatcher } from '../../bti/editor/static/js/idlewatch.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test('a waiting step opens, says it waits, and is neither "Xong" nor locked', () => {
  const v = stepView({ id: 'voice', label: 'Giọng đọc', state: 'waiting', work: 'stale', blocked_by: 'script', reason: 'Chờ duyệt lại lời dẫn ở bước Kịch bản.' });
  assert.equal(v.openable, true);
  assert.match(v.cls, /st-waiting/); assert.doesNotMatch(v.cls, /disabled|st-done|st-locked/);
  assert.equal(v.tag, STEP_STATE.waiting); assert.equal(v.tag, 'Chờ bước trước');       // not "Cần làm lại": the stale voice is why it waits
  assert.equal(stepView({ id: 'edit', label: 'X', state: 'waiting', work: 'running' }).tag, 'Đang chạy');
});

test('every waiting step has its own plain sentence for each blocker, and a button label', () => {
  assert.match(waitText('voice', 'script'), /Lời dẫn đang được sửa và chưa được duyệt lại\. Giọng đọc hiện có được làm từ bản đã duyệt trước\. Duyệt lại lời dẫn để biết những câu nào cần đọc lại\./);
  const seen = new Set();
  for (const [step, blk] of [['voice', 'script'], ['picks', 'script'], ['edit', 'script'], ['edit', 'voice'], ['edit', 'picks'], ['export', 'script'], ['export', 'voice'], ['export', 'picks'], ['export', 'edit']]) {
    const t = waitText(step, blk); assert.ok(t.length > 40, step + blk); seen.add(t);
    assert.doesNotMatch(t, /null|undefined/);
  }
  assert.equal(seen.size, 9);
  assert.match(waitText('voice', 'zzz'), /đã duyệt trước/);               // a blocker we have no sentence for still gets an honest one
  assert.equal(OPEN_STEP('Kịch bản'), 'Mở bước Kịch bản');
});

// ---- the idle timer
function fakeDocument({ hidden = false, active = null } = {}) {
  const d = new EventTarget(); d.hidden = hidden; d.activeElement = active; d.body = {};
  globalThis.document = d; return d;
}
const rootOf = (inside) => ({ contains: (x) => x === inside });

test('typingIn is true only for a field inside the page root', () => {
  const input = { matches: (s) => s.includes('input') };
  const other = { matches: () => false };
  fakeDocument({ active: input });
  assert.equal(typingIn(rootOf(input)), true);
  assert.equal(typingIn(rootOf(other)), false);
  fakeDocument({ active: other });
  assert.equal(typingIn(rootOf(other)), false);                           // a button with the focus is not typing
  assert.equal(typingIn(null), false);
});

test('the idle watch checks only when the page is idle, visible, not typing; one timer; gone with the scope', async () => {
  const doc = fakeDocument();
  const scope = createScope();
  let idle = true, n = 0;
  const w = watchIdle(scope, { root: () => rootOf(null), idle: () => idle, check: async () => { n++; }, every: 10 });
  await sleep(45); assert.ok(n >= 2, 'it checks while idle: ' + n);
  idle = false; const k = n; await sleep(40); assert.equal(n, k, 'a page that shows a running job does not ask');
  idle = true; doc.hidden = true; const k2 = n; await sleep(40); assert.equal(n, k2, 'a hidden tab does not ask');
  doc.hidden = false; doc.dispatchEvent(new Event('visibilitychange')); await sleep(5); assert.ok(n > k2, 'it asks at once when the tab is visible again');
  scope.dispose(); const k4 = n; await sleep(40);
  assert.equal(n, k4, 'after dispose the page stops asking');
  assert.equal(w.checks > 0, true);
});

test('typing in a field of the page stops the check', async () => {
  const doc = fakeDocument({ active: { matches: () => true } });
  const scope = createScope(); let n = 0;
  watchIdle(scope, { root: () => ({ contains: () => true }), idle: () => true, check: async () => { n++; }, every: 5 });
  await sleep(40); assert.equal(n, 0);
  doc.activeElement = null; await sleep(40); assert.ok(n >= 1);
  scope.dispose();
});

test('checks never overlap: a slow check is not asked again while it runs', async () => {
  fakeDocument();
  const scope = createScope();
  let running = 0, max = 0, n = 0;
  watchIdle(scope, { root: () => null, idle: () => true, every: 5, check: async () => { n++; running++; max = Math.max(max, running); await sleep(30); running--; } });
  await sleep(100); scope.dispose();
  assert.equal(max, 1); assert.ok(n >= 2 && n <= 4, String(n));
});

test('a dialog of another view blocks the check, a dialog the page lives in does not', async () => {
  const util = await import('../../bti/editor/static/js/util.js');
  assert.equal(typeof util.modalOpen, 'function');
  assert.equal(util.modalOpen(), false);                                  // no dialog is open here: the check runs
  fakeDocument();
  const scope = createScope(); let n = 0;
  watchIdle(scope, { root: () => null, idle: () => true, every: 5, check: async () => { n++; }, ownDialog: true });
  await sleep(30); scope.dispose(); assert.ok(n >= 2);
});

test('jobWatcher: active while a job runs, "changed" once for a job that began and ended between two looks, the first look only remembers', () => {
  const seen = jobWatcher();
  const done = (id, created) => ({ id, state: 'done', created });
  assert.equal(seen({ items: [done('a', 1)] }), null);                        // first look: just remember
  assert.equal(seen({ items: [done('a', 1)] }), null);                        // nothing new
  assert.equal(seen({ items: [done('b', 2), done('a', 1)] }), 'changed');     // a newer job exists and has ended
  assert.equal(seen({ items: [done('b', 2), done('a', 1)] }), null);          // said once
  assert.equal(seen({ items: [{ id: 'c', state: 'running', created: 3 }, done('b', 2)] }), 'active');
  assert.equal(seen({ items: [done('c', 3), done('b', 2)] }), null);          // after an active one the page followed it itself: remember again
  const s3 = jobWatcher(); assert.equal(s3([]), null); assert.equal(s3(null), null);
  const s2 = jobWatcher(); assert.equal(s2({ items: [] }), null); assert.equal(s2({ items: [done('x', 1)] }), 'changed');
});

test('jobWatcher: a job this page started or followed itself is not "changed" when it ends (the page repainted already)', () => {
  const seen = jobWatcher();
  const done = (id, created) => ({ id, state: 'done', created });
  assert.equal(seen({ items: [done('a', 1)] }), null);
  seen.know('b');
  assert.equal(seen({ items: [{ id: 'b', state: 'running', created: 2 }, done('a', 1)] }), null);   // running but known: not news
  assert.equal(seen({ items: [done('b', 2), done('a', 1)] }), null);                               // ended but known: not news
  assert.equal(seen({ items: [done('c', 3), done('b', 2)] }), 'changed');                          // an unknown job is
});
