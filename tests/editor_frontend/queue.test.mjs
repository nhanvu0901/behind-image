import test from 'node:test';
import assert from 'node:assert/strict';
import { createQueue } from '../../bti/editor/static/js/queue.js';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

test('jobs run one at a time, in the order they were queued (U1-003)', async () => {
  const q = createQueue(); const log = [];
  const job = (n, ms) => q.run(async () => { log.push('start' + n); await sleep(ms); log.push('end' + n); return n; });
  const r = await Promise.all([job(1, 30), job(2, 5), job(3, 1)]);
  assert.deepEqual(r, [1, 2, 3]);
  assert.deepEqual(log, ['start1', 'end1', 'start2', 'end2', 'start3', 'end3']);
});
test('a revision-dependent sequence never uses a stale revision', async () => {
  // a fake server: each request must carry the revision of the previous answer, like base_rev
  let rev = 0; const conflicts = [];
  const request = async (base) => { await sleep(10); if (base !== rev) { conflicts.push([base, rev]); throw new Error('409'); } rev++; return rev; };
  const q = createQueue(); let known = 0;
  const op = () => q.run(async () => { known = await request(known); });
  await Promise.all([op(), op(), op()]);
  assert.deepEqual(conflicts, []);
  assert.equal(known, 3);
  // without the queue the same three calls conflict
  rev = 0; known = 0;
  const bare = async () => { known = await request(known); };
  const res = await Promise.allSettled([bare(), bare(), bare()]);
  assert.ok(res.some((x) => x.status === 'rejected'));
});
test('a failing job rejects its own promise and the queue keeps going', async () => {
  const q = createQueue();
  const a = q.run(async () => { throw new Error('boom'); });
  const b = q.run(async () => 'ok');
  await assert.rejects(a, /boom/);
  assert.equal(await b, 'ok');
});
test('jobs queued from the answer of another job run after the ones already waiting', async () => {
  const q = createQueue(); const log = [];
  const p1 = q.run(async () => { log.push(1); q.run(async () => { log.push('inner'); }); });
  const p2 = q.run(async () => { log.push(2); });
  await Promise.all([p1, p2]); await q.idle(); await sleep(5);
  assert.deepEqual(log, [1, 2, 'inner']);
});
test('busy state: onBusy is told when work starts and when the queue is empty again', async () => {
  const seen = []; const q = createQueue({ onBusy: (b) => seen.push(b) });
  assert.equal(q.busy, false);
  const p = q.run(async () => { await sleep(5); });
  assert.equal(q.busy, true); assert.equal(q.pending, 1);
  await p; await q.idle();
  assert.equal(q.busy, false);
  assert.deepEqual(seen, [true, false]);
});
