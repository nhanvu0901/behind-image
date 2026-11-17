// Run on the server with: node --test tests/picks/picks_logic.test.mjs   (pure helpers of the picks view, no DOM)
import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../../bti/editor/static/js/views/picks_logic.js';

const doc = () => ({ main_asset: 'A', assets: { A: { width: 2000, height: 3000, regions: {} }, B: {} }, beats: {} });
const chapters = [{ beats: [{ id: 'b1' }, { id: 'b2' }] }, { beats: [{ id: 'b3' }] }];

test('addItem picks a role and marks the beat picked', () => {
  const d = doc();
  assert.equal(L.addItem(d, 'b1', { asset: 'A' }), 0);
  L.addItem(d, 'b1', { asset: 'A', region: 'MIRROR' });
  L.addItem(d, 'b1', { asset: 'B' });
  assert.deepEqual(d.beats.b1.items.map((i) => i.role), ['main', 'detail', 'context']);
  assert.equal(d.beats.b1.status, 'picked');
});

test('remove, move, skip', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.addItem(d, 'b1', { asset: 'B' });
  assert.equal(L.moveItem(d, 'b1', 0, 1), 1);
  assert.equal(d.beats.b1.items[1].asset, 'A');
  assert.equal(L.moveItem(d, 'b1', 0, -1), 0);
  assert.ok(L.removeItem(d, 'b1', 0) && L.removeItem(d, 'b1', 0));
  assert.equal(d.beats.b1.status, 'todo');
  assert.equal(L.removeItem(d, 'b1', 0), false);
  assert.equal(L.toggleSkip(d, 'b1'), 'skip');
  assert.equal(L.toggleSkip(d, 'b1'), 'todo');
});

test('progress and empty beats', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.toggleSkip(d, 'b3');
  assert.deepEqual(L.chapterProgress(chapters[0], d), { done: 1, total: 2 });
  assert.deepEqual(L.emptyBeats(chapters, d), ['b2']);
});

test('dropAsset clears the items and the main painting', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.addItem(d, 'b1', { asset: 'B' });
  L.dropAsset(d, 'A');
  assert.equal(d.main_asset, null);
  assert.deepEqual(d.beats.b1.items.map((i) => i.asset), ['B']);
});

test('region names', () => {
  assert.ok(L.regionNameOk('D1') && L.regionNameOk('The mirror') && !L.regionNameOk('a/b') && !L.regionNameOk(''));
  assert.equal(L.freeRegionName({}, 'D1'), 'D1');
  assert.equal(L.freeRegionName({ D1: 1, D1_2: 1 }, 'D1'), 'D1_3');
  assert.equal(L.freeRegionName({}, ''), 'VUNG');
  assert.deepEqual(L.regionNameChoices([{ id: 'D1', label: 'x' }, { id: 'D2', label: 'y' }], { D1: {} }), [{ name: 'D2', label: 'y' }]);
});

test('circleFromDrag keeps the centre inside and a minimum radius', () => {
  assert.deepEqual(L.circleFromDrag([100, 100], [130, 140], 2000, 3000), { x: 100, y: 100, rx: 50, ry: 50 });
  assert.equal(L.circleFromDrag([100, 100], [101, 100], 2000, 3000).rx, 8);
  const c = L.circleFromDrag([-5, 4000], [0, 0], 2000, 3000);
  assert.equal(c.x, 0); assert.equal(c.y, 3000);
});

test('cropStyle fills the box with the region', () => {
  const s = L.cropStyle({ width: 2000, height: 3000 }, { x: 1000, y: 1500, rx: 100, ry: 100 }, 64);
  assert.equal(s.backgroundSize, '640px 960px');
  assert.equal(s.backgroundPosition, '-288px -448px');
  assert.equal(L.cropStyle({}, { x: 1, y: 1 }), null);
});

test('show words use the dossier names', () => {
  const w = L.showWords(['D2', 'wide view'], [{ id: 'D2', label: 'Signature' }]);
  assert.deepEqual(w.map((x) => [x.text, x.query, x.detail]), [['D2: Signature', 'Signature', true], ['wide view', 'wide view', false]]);
});

test('sizes', () => {
  assert.equal(L.sizeText(0, 0), 'chưa biết kích thước');
  assert.ok(L.isSmall(800, 600) && !L.isSmall(1300, 1250) && !L.isSmall(0, 0));
});
