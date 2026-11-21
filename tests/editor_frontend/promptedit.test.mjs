import test from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../../bti/editor/static/js/store.js';
import { ctx, bus } from '../../bti/editor/static/js/ctx.js';

test('Store.on accepts callback function and emits properly without crashing', () => {
  const st = new Store();
  const events = [];
  const unsub = st.on((kind) => {
    events.push(kind);
  });

  st.emit('draft');
  st.select('s0001');
  assert.deepEqual(events, ['draft', 'select']);

  unsub();
  st.emit('select');
  assert.equal(events.length, 2);
});

test('bus on and emit work without leaking', () => {
  const times = [];
  const off = bus.on('time', (t) => times.push(t));
  bus.emit('time', 1.25);
  assert.deepEqual(times, [1.25]);
  off();
  bus.emit('time', 2.5);
  assert.deepEqual(times, [1.25]);
});

test('ctx seek updates t and emits time event', () => {
  let seen = null;
  const off = bus.on('time', (t) => { seen = t; });
  ctx.store.timing = { duration: 100, words: [] };
  ctx.seek(42.5);
  assert.equal(ctx.t, 42.5);
  assert.equal(seen, 42.5);
  off();
});

test('Store unsaved check detects changes between snap and savedSnap', () => {
  const st = new Store();
  st.load({ shots: [{ id: 's0001', technique: 'PAN-01' }] }, { duration: 10, words: [] }, 'rev1');
  assert.equal(st.snap(), st.savedSnap);

  // Modify draft
  st.draft.shots[0].technique = 'ZOOM-01';
  assert.notEqual(st.snap(), st.savedSnap);

  // Restore or save
  st.savedSnap = st.snap();
  assert.equal(st.snap(), st.savedSnap);
});
