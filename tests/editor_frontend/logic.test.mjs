import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as L from '../../bti/editor/static/js/logic.js';
import * as E from '../../bti/editor/static/js/edit.js';
import { Store } from '../../bti/editor/static/js/store.js';
import * as F from '../../bti/editor/static/js/formgen.js';

const M = 'bti/editor/static/mock/';
const timing = JSON.parse(fs.readFileSync(M + 'timing.json'));
const sbRaw = JSON.parse(fs.readFileSync(M + 'storyboard.json'));
const reg = JSON.parse(fs.readFileSync(M + 'techniques.json')).techniques;
const words = timing.words;
const canvas = { w: 1920, h: 1080 };
const fresh = () => { const s = L.clone(sbRaw); L.derive(s, timing); return s; };

test('time <-> x mapping round trips', () => {
  const v = { t0: 12.5, pps: 40 };
  assert.equal(L.timeToX(12.5, v), 0);
  assert.equal(L.timeToX(13.5, v), 40);
  assert.ok(Math.abs(L.xToTime(L.timeToX(77.123, v), v) - 77.123) < 1e-9);
});

test('word lookup and snapping', () => {
  const i = L.wordIndexAt(words, words[10].s + 0.01);
  assert.equal(i, 10);
  assert.equal(L.wordIndexAt(words, -1), -1);
  const n = L.nearestWordStart(words, words[20].s + 0.02);
  assert.equal(n.idx, 20);
  const mid = (words[30].s + words[31].s) / 2 + 0.001;
  assert.equal(L.nearestWordStart(words, mid).idx, 31);
  const a = L.anchorFromTime(words[5].s + 0.03, words);
  assert.deepEqual(Object.keys(a).sort(), ['off', 'text', 'w']);
  assert.equal(a.w, 5);
  const free = L.anchorFromTime(3.14159, words, true);
  assert.deepEqual(free, { t: 3.142 });
});

test('anchor resolution: t, w, rel and stale detection', () => {
  assert.equal(L.resolveAnchor({ t: 4.2 }, words), 4.2);
  assert.equal(L.resolveAnchor({ w: 3, off: -0.1, text: 'x' }, words), words[3].s - 0.1);
  assert.equal(L.resolveAnchor({ rel: 0.5 }, words, { t0: 10, t1: 20 }), 15);
  assert.equal(L.resolveAnchor({ rel: 0.5 }, words, null), null);
  assert.equal(L.resolveAnchor({ w: 99999 }, words), null);
  assert.equal(L.anchorStale({ w: 0, text: L.cleanWord(words[0].w) }, words), false);
  assert.equal(L.anchorStale({ w: 0, text: 'zzz' }, words), true);
});

test('derive adds _t/_t0/_t1 and tiles shots; stripDerived removes them', () => {
  const sb = fresh();
  for (let i = 0; i < sb.shots.length - 1; i++) assert.equal(sb.shots[i]._t1, sb.shots[i + 1]._t0);
  assert.equal(sb.shots.at(-1)._t1, sb.end.t);
  assert.equal(sb.shots[0]._t0, 0);
  for (const s of sb.shots) for (const o of s.overlays) {
    assert.ok(o._t0 >= s._t0 && o._t1 <= s._t1 && o._t1 >= o._t0);
  }
  const stripped = L.stripDerived(sb);
  assert.ok(!JSON.stringify(stripped).includes('"_t'));
  assert.deepEqual(stripped, sbRaw);
});

test('box <-> camera conversion', () => {
  const cam = { cx: 2220, cy: 1790, zoom: 0.72 };
  const b = L.cameraToBox(cam, canvas);
  assert.ok(Math.abs(b.w - 1920 / 0.72) < 1e-9 && Math.abs(b.h - 1080 / 0.72) < 1e-9);
  assert.ok(Math.abs(b.x + b.w / 2 - 2220) < 1e-9);
  const back = L.boxToCamera(b, canvas);
  for (const k of ['cx', 'cy', 'zoom']) assert.ok(Math.abs(back[k] - cam[k]) < 1e-9, k);
  const fixed = L.fixAspect({ x: 0, y: 0, w: 1600, h: 100 }, canvas);
  assert.ok(Math.abs(fixed.h / fixed.w - 1080 / 1920) < 1e-9);
});

test('camera interpolation and screen mapping', () => {
  const sb = fresh();
  const s = sb.shots[2];
  const keys = s.params.camera;
  const a = L.cameraAt(keys, s._t0), b = L.cameraAt(keys, s._t1 + 5);
  assert.equal(a.zoom, 0.18); assert.equal(b.zoom, 0.72);
  const mid = L.cameraAt(keys, (keys[0].at._t + keys[1].at._t) / 2);
  assert.ok(mid.zoom > 0.18 && mid.zoom < 0.72);
  const m = L.makeMapping({ cx: 100, cy: 200, zoom: 0.5 }, canvas, { W: 960, H: 540 });
  const [sx, sy] = m.toScreen(100, 200);
  assert.deepEqual([sx, sy], [480, 270]);
  const [x, y] = m.toSource(...m.toScreen(333, 444));
  assert.ok(Math.abs(x - 333) < 1e-9 && Math.abs(y - 444) < 1e-9);
});

test('moveBoundary snaps, honours Alt and the 0.2 s minimum', () => {
  const sb = fresh();
  const s = sb.shots[3];
  assert.ok(E.moveBoundary(sb, 3, s._t0 + 0.37, words, false));
  assert.ok('w' in s.start && s.start.off === 0);
  assert.equal(s.source, 'human');
  assert.ok(E.moveBoundary(sb, 3, 50.1234, words, true));
  assert.deepEqual(s.start, { t: 50.123 });
  L.derive(sb, timing);
  E.moveBoundary(sb, 3, 1e6, words, true);
  L.derive(sb, timing);
  assert.ok(sb.shots[3]._t1 - sb.shots[3]._t0 >= 0.2 - 1e-9);
  assert.ok(!E.moveBoundary(sb, 0, 5, words, true));
});

test('split / merge / delete keep the timeline tiled', () => {
  const sb = fresh();
  const n0 = sb.shots.length;
  const s = sb.shots[2];
  const t = (s._t0 + s._t1) / 2;
  const id = E.splitShot(sb, 2, t, words);
  assert.ok(id);
  L.derive(sb, timing);
  assert.equal(sb.shots.length, n0 + 1);
  assert.equal(sb.shots[3].id, id);
  assert.equal(sb.shots[2]._t1, sb.shots[3]._t0);
  assert.equal(E.splitShot(sb, 2, sb.shots[2]._t0 + 0.05, words), null);
  assert.ok(E.mergeWithPrev(sb, 3));
  L.derive(sb, timing);
  assert.equal(sb.shots.length, n0);
  assert.ok(E.deleteShot(sb, 0));
  L.derive(sb, timing);
  assert.equal(sb.shots[0]._t0, 0);
  assert.deepEqual(E.parseIssuePath('shots[3].overlays[1].start'), { shot: 3, overlay: 1 });
});

test('store: undo/redo, coalescing, history depth, dirty flag', () => {
  const st = new Store(150);
  st.load(sbRaw, timing, 'r1');
  assert.equal(st.dirty, false);
  for (let i = 0; i < 120; i++) st.commit('note' + i, (d) => { d.shots[0].note = 'n' + i; });
  assert.equal(st.undoStack.length, 120);
  assert.equal(st.dirty, true);
  for (let i = 0; i < 120; i++) assert.ok(st.undo());
  assert.equal(st.draft.shots[0].note, '');
  assert.equal(st.dirty, false);
  assert.ok(st.redo());
  assert.equal(st.draft.shots[0].note, 'n0');
  // coalesced drag = one step
  st.load(sbRaw, timing, 'r1');
  for (let i = 0; i < 10; i++) st.commit('drag', (d) => { E.moveBoundary(d, 3, 20 + i * 0.01, words, true); }, { coalesce: 'b3' });
  assert.equal(st.undoStack.length, 1);
  st.undo();
  assert.equal(st.dirty, false);
  // a no-op commit adds nothing
  assert.equal(st.commit('noop', () => {}), false);
  // derived keys survive undo
  assert.equal(typeof st.draft.shots[1]._t0, 'number');
  // limit
  const small = new Store(100);
  small.load(sbRaw, timing, 'r');
  for (let i = 0; i < 130; i++) small.commit('x', (d) => { d.shots[1].note = 'q' + i; });
  assert.equal(small.undoStack.length, 100);
});

test('form generation covers every registry param type, no per-technique code', () => {
  const types = new Set();
  for (const t of reg) {
    const fields = F.buildFields(t.params, {});
    assert.equal(fields.length, t.params.length);
    for (const f of fields) { types.add(f.type); assert.ok(f.widget, t.id + '.' + f.name); }
  }
  for (const k of ['number', 'enum', 'bool', 'string', 'color', 'text', 'point', 'box', 'camera', 'asset']) assert.ok(types.has(k), k);
  // pick a ranged number and an enum from whatever the registry currently defines
  const ranged = reg.flatMap((t) => t.params).find((p) => p.type === 'number' && p.min != null && p.max != null);
  const f1 = F.buildFields([ranged], { [ranged.name]: ranged.max + 99 })[0];
  assert.equal(f1.widget, 'number'); assert.ok(f1.slider); assert.ok(f1.problem); assert.equal(f1.isDefault, false);
  assert.equal(F.coerce(ranged, ranged.max + 99), ranged.max);
  const withMeasured = reg.flatMap((t) => t.params).find((p) => p.measured);
  if (withMeasured) assert.ok(F.buildFields([withMeasured], {})[0].measured);
  const en = reg.flatMap((t) => t.params).find((p) => p.type === 'enum');
  if (en) { const e1 = F.buildFields([en], {})[0]; assert.equal(e1.widget, 'select'); assert.ok(e1.values.includes(e1.value)); }
  // the real registry file must also produce a field for every param, without throwing
  const real = JSON.parse(fs.readFileSync('style/gae/techniques.json')).techniques;
  for (const t of real) assert.equal(F.buildFields(t.params, {}).length, t.params.length);
  const unknown = F.buildFields([{ name: 'weird', type: 'quaternion', default: [1, 2] }], {})[0];
  assert.equal(unknown.widget, 'json');
});

test('coerce clamps numbers and parses points', () => {
  const d = { name: 'a', type: 'number', min: 1, max: 5, default: 2 };
  assert.equal(F.coerce(d, '9'), 5);
  assert.equal(F.coerce(d, 'abc'), 2);
  const p = { name: 'at', type: 'point' };
  assert.deepEqual(F.coerce(p, '120, 340'), [120, 340]);
  assert.equal(F.coerce(p, 'MIRROR'), 'MIRROR');
  assert.deepEqual(F.defaultParams([{ name: 'x', default: 3 }, { name: 'y', default: null }]), { x: 3 });
});

test('cameraLists finds every camera key list in params and derive stamps them', () => {
  const sb = fresh();
  const lists = L.cameraLists(sb.shots[2].params);
  assert.equal(lists.length, 1); assert.equal(lists[0].name, 'camera');
  const two = { camera_left: [{ at: { rel: 0 }, cx: 1, cy: 1, zoom: 1 }], camera_right: [{ at: { rel: 1 }, cx: 1, cy: 1, zoom: 1 }], caption: 'x', empty: [] };
  assert.deepEqual(L.cameraLists(two).map((l) => l.name), ['camera_left', 'camera_right']);
  sb.shots[1].params = two; L.derive(sb, timing);
  assert.equal(two.camera_right[0].at._t, sb.shots[1]._t1);
});

// ---- integration additions: engine semantics for the camera, camera and overlay fixes
test('cameraAt interpolates zoom in LOG space with the ease of the first key (bti/engine/vfx.py Cam.at)', () => {
  const keys = [
    { at: { rel: 0, _t: 0 }, cx: 0, cy: 0, zoom: 0.25, ease: 'linear' },
    { at: { rel: 1, _t: 10 }, cx: 100, cy: 50, zoom: 1, ease: 'linear' },
  ];
  const m = L.cameraAt(keys, 5);
  assert.ok(Math.abs(m.zoom - 0.5) < 1e-9, 'geometric mean, not 0.625');
  assert.equal(m.cx, 50);
  assert.ok(!('inout_quad' in L.EASES), 'only engine ease names');
  keys[0].ease = 'in_quad';
  assert.ok(Math.abs(L.cameraAt(keys, 5).cx - 25) < 1e-9);
});

test('splitting a shot keeps the camera pose at the cut; merging keeps absolute camera timing', () => {
  const sb = fresh();
  const s = sb.shots[2];
  const t = (s._t0 + s._t1) / 2;
  const before = L.cameraAt(s.params.camera, t);
  const id = E.splitShot(sb, 2, t, words, true);
  L.derive(sb, timing);
  const a = sb.shots[2], b = sb.shots[3];
  assert.equal(b.id, id);
  const endA = L.cameraAt(a.params.camera, a._t1), startB = L.cameraAt(b.params.camera, b._t0);
  for (const k of ['cx', 'cy', 'zoom']) { assert.ok(Math.abs(endA[k] - before[k]) < 1e-3 * Math.max(1, Math.abs(before[k])), k); assert.ok(Math.abs(startB[k] - before[k]) < 1e-3 * Math.max(1, Math.abs(before[k])), k); }
  const tMid = a._t0 + (a._t1 - a._t0) / 2;
  const mid = L.cameraAt(a.params.camera, tMid);
  E.mergeWithPrev(sb, 3);
  L.derive(sb, timing);
  const m = sb.shots[2];
  const again = L.cameraAt(m.params.camera, tMid);
  assert.ok(Math.abs(again.zoom - mid.zoom) < 1e-3, 'same pose at the same absolute time after merge');
  assert.ok(m.params.camera.at(-1).at.rel < 1, 'last pose is held over the merged part');
});

test('moving a boundary clamps or shifts overlays; chip edges resize', () => {
  const sb = fresh();
  const idx = sb.shots.findIndex((s) => (s.overlays || []).length && s.overlays.some((o) => o._t1 > s._t0 + 0.6));
  const s = sb.shots[idx], o = s.overlays[0];
  // pull the END of the shot (= start of the next one) in so that the overlay no longer fits
  const target = s._t0 + 0.3 + 1e-3;
  E.moveBoundary(sb, idx + 1, target, words, true);
  L.derive(sb, timing);
  for (const ov of sb.shots[idx].overlays) { assert.ok(ov._t0 >= sb.shots[idx]._t0 - 1e-6 && ov._t1 <= sb.shots[idx]._t1 + 1e-6, 'inside its shot'); }
  // right-edge resize
  const sb2 = fresh(); const s2 = sb2.shots[idx], o2 = s2.overlays[0];
  E.resizeOverlay(sb2, s2, o2, 'r', o2._t0 + 0.5, words, true);
  assert.equal(o2.dur, 0.5);
  L.derive(sb2, timing);
  const end = o2._t1;
  E.resizeOverlay(sb2, s2, o2, 'l', o2._t0 + 0.2, words, true);
  L.derive(sb2, timing);
  assert.ok(Math.abs(o2._t1 - end) < 1e-3 && o2.source === 'human');
});

test('points and lines params', () => {
  assert.equal(F.WIDGETS.points, 'points'); assert.equal(F.WIDGETS.lines, 'lines');
  assert.deepEqual(F.coerce({ type: 'lines' }, 'a\nb\n\n'), ['a', 'b']);
  assert.deepEqual(F.coerce({ type: 'points' }, [[1, 2], 'MIRROR']), [[1, 2], 'MIRROR']);
  const f = F.buildFields([{ name: 'xs', type: 'points', default: null }, { name: 'ls', type: 'lines', default: ['x'] }, { name: 'z', type: 'future_type', default: 1 }]);
  assert.deepEqual(f.map((x) => x.widget), ['points', 'lines', 'json']);
});
