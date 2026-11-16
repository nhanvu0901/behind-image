import test from 'node:test';
import assert from 'node:assert/strict';
import { createScope } from '../../bti/editor/static/js/lifecycle.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test('dispose removes listeners: a shortcut of a left view never fires', () => {
  const doc = new EventTarget();
  let a = 0, b = 0;
  const s1 = createScope();
  s1.on(doc, 'keydown', () => { a++; });
  doc.dispatchEvent(new Event('keydown'));
  s1.dispose();
  const s2 = createScope();
  s2.on(doc, 'keydown', () => { b++; });
  doc.dispatchEvent(new Event('keydown'));
  assert.equal(a, 1); assert.equal(b, 1);
});

test('dispose stops timers and intervals, even ones that were already queued', async () => {
  const s = createScope();
  let n = 0;
  s.interval(() => { n++; }, 5);
  s.timeout(() => { n += 100; }, 20);
  await sleep(12);
  const seen = n;
  s.dispose();
  await sleep(40);
  assert.equal(n, seen);
});

test('dispose aborts the signal that pending requests carry, and runs registered cleanups once, newest first', () => {
  const s = createScope();
  const order = [];
  s.add(() => order.push('a')); s.add(() => order.push('b'));
  assert.equal(s.signal.aborted, false);
  s.dispose(); s.dispose();
  assert.equal(s.signal.aborted, true);
  assert.deepEqual(order, ['b', 'a']);
  assert.equal(s.dead, true);
});

test('a cleanup that throws does not stop the others; add() after dispose runs at once', () => {
  const s = createScope();
  let ok = 0;
  s.add(() => { ok++; }); s.add(() => { throw new Error('boom'); }); s.add(() => { ok++; });
  s.dispose();
  assert.equal(ok, 2);
  let late = 0;
  s.add(() => { late++; });
  assert.equal(late, 1);
});
