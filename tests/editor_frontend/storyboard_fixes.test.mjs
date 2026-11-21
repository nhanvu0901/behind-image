// Unit tests for the storyboard fix round: ids, coordinates, the save flow, the shortcut gate, slots, the drag-left cause.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as L from '../../bti/editor/static/js/logic.js';
import * as E from '../../bti/editor/static/js/edit.js';
import { Store } from '../../bti/editor/static/js/store.js';
import * as F from '../../bti/editor/static/js/formgen.js';
import * as C from '../../bti/editor/static/js/coords.js';
import * as S from '../../bti/editor/static/js/slots.js';
import { resolveShortcut, targetKind } from '../../bti/editor/static/js/shortcuts.js';
import { outsideIssues } from '../../bti/editor/static/js/checks.js';

const M = 'bti/editor/static/mock/';
const timing = JSON.parse(fs.readFileSync(M + 'timing.json'));
const sbRaw = JSON.parse(fs.readFileSync(M + 'storyboard.json'));
const reg = JSON.parse(fs.readFileSync('style/gae/techniques.json')).techniques;
const byId = Object.fromEntries(reg.map((t) => [t.id, t]));
const fresh = () => { const s = L.clone(sbRaw); L.derive(s, timing); return s; };
const canvas = { w: 1920, h: 1080 };

// ------------------------------------------------------------------ ids (U2-001)
test('merge renames the overlay ids that collide, so every overlay keeps a unique id in its shot', () => {
  const sb = fresh();
  const [a, b] = [sb.shots[0], sb.shots[1]];
  a.overlays = [{ id: 'o1', technique: 'HI-01', params: {}, start: { t: 0.5 }, dur: 1 }];
  b.overlays = [{ id: 'o1', technique: 'AN-01', params: {}, start: { t: b._t0 + 0.2 }, dur: 1 }, { id: 'o2', technique: 'AN-01', params: {}, start: { t: b._t0 + 0.4 }, dur: 1 }];
  L.derive(sb, timing);
  assert.ok(E.mergeWithPrev(sb, 1));
  const ids = sb.shots[0].overlays.map((o) => o.id);
  assert.equal(new Set(ids).size, 3, ids.join());
  assert.equal(ids[0], 'o1');                                  // the first holder keeps its id
  assert.deepEqual(sb.shots[0].overlays.map((o) => o.technique), ['HI-01', 'AN-01', 'AN-01']);
});
test('dedupeIds repairs duplicate overlay ids and duplicate shot ids; unique input is left alone', () => {
  const sb = fresh();
  assert.deepEqual(E.dedupeIds(L.clone(sb)), []);
  sb.shots[1].id = sb.shots[0].id;
  sb.shots[0].overlays = [{ id: 'o1' }, { id: 'o1' }, { id: 'o2' }];
  const r = E.dedupeIds(sb);
  assert.equal(r.filter((x) => x.kind === 'shot').length, 1);
  assert.equal(new Set(sb.shots.map((s) => s.id)).size, sb.shots.length);
  assert.equal(new Set(sb.shots[0].overlays.map((o) => o.id)).size, 3);
});
test('split, add overlay and delete keep ids unique', () => {
  const sb = fresh();
  const i = sb.shots.findIndex((s) => (s.overlays || []).length && s._t1 - s._t0 > 3);
  const s = sb.shots[i];
  const mid = (s._t0 + s._t1) / 2;
  assert.ok(E.splitShot(sb, i, mid, timing.words, true));
  L.derive(sb, timing);
  assert.equal(new Set(sb.shots.map((x) => x.id)).size, sb.shots.length);
  const before = E.allOverlays(sb).length;
  E.addOverlay(sb, i, 'HI-01', 'isolate', {}, s._t0 + 0.1, timing.words);
  E.addOverlay(sb, i, 'HI-01', 'isolate', {}, s._t0 + 0.2, timing.words);
  const ids = sb.shots[i].overlays.map((o) => o.id);
  assert.equal(E.allOverlays(sb).length, before + 2);
  assert.equal(new Set(ids).size, ids.length);
});

// ------------------------------------------------------------------ coordinates (U2-008, U2-009)
const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} vs ${b}`);
const roundTrip = (S, space, pts) => { for (const p of pts) { const q = S.fromScreen(space, S.toScreen(space, p)); near(q[0], p[0], 1e-6); near(q[1], p[1], 1e-6); } };

test('coordinates: wide image through the camera, canvas and frame spaces round trip', () => {
  const asset = { width: 4386, height: 1200 };
  const cam = L.engineFitCamera(asset, canvas);
  const S2 = C.makeSpaces({ canvas, view: { W: 640, H: 360 }, cam });
  roundTrip(S2, 'source', [[0, 0], [2193, 600], [4386, 1200], [1000, 100]]);
  roundTrip(S2, 'canvas', [[0, 0], [960, 540], [1920, 1080]]);
  roundTrip(S2, 'frame', [[0, 0], [0.5, 0.5], [1, 1], [0.12, 0.98]]);
  // the image centre sits at the centre of the screen; frame (0.5,0.5) and canvas centre are the same screen point
  const c = S2.toScreen('source', [asset.width / 2, asset.height / 2]);
  near(c[0], 320); near(c[1], 180);
  assert.deepEqual(S2.toScreen('frame', [0.5, 0.5]), S2.toScreen('canvas', [960, 540]));
});
test('coordinates: tall image and a mask-sized image (matte)', () => {
  for (const asset of [{ width: 1200, height: 4300 }, { width: 1097, height: 1500 }]) {
    const cam = L.engineFitCamera(asset, canvas);
    const S2 = C.makeSpaces({ canvas, view: { W: 800, H: 450 }, cam });
    roundTrip(S2, 'source', [[0, 0], [asset.width, asset.height], [asset.width / 3, asset.height / 5]]);
    // 95.5 % of the frame height is the image height on screen
    const top = S2.toScreen('source', [0, 0]), bot = S2.toScreen('source', [0, asset.height]);
    near((bot[1] - top[1]) / 450, 0.955, 1e-9);
    // a camera pose: the point at the camera centre is the centre of the screen
    const cam2 = { cx: asset.width / 3, cy: asset.height / 4, zoom: 0.8 };
    const S3 = C.makeSpaces({ canvas, view: { W: 800, H: 450 }, cam: cam2 });
    const m = S3.toScreen('source', [cam2.cx, cam2.cy]);
    near(m[0], 400); near(m[1], 225);
  }
});
test('coordinates: a base shot without a camera has canvas and frame space but no source space', () => {
  const S2 = C.makeSpaces({ canvas, view: { W: 640, H: 360 }, cam: null });
  assert.equal(S2.has('source'), false);
  assert.equal(S2.toScreen('source', [10, 10]), null);
  assert.deepEqual(S2.toScreen('canvas', [1920, 1080]), [640, 360]);
  assert.deepEqual(S2.fromScreen('frame', [320, 180]), [0.5, 0.5]);
});
test('coordinates: the "Ảnh gốc" view has no canvas space (it shows the source image, not the frame)', () => {
  const S2 = C.makeSpaces({ canvas, view: { W: 640, H: 360 }, cam: L.fitCamera({ width: 1000, height: 1000 }, canvas), canvasOk: false });
  assert.equal(S2.has('canvas'), false); assert.equal(S2.has('frame'), false); assert.equal(S2.has('source'), true);
});
test('dragging a handle moves it by the same screen distance in every space', () => {
  const cam = { cx: 500, cy: 400, zoom: 0.7 };
  const S2 = C.makeSpaces({ canvas, view: { W: 960, H: 540 }, cam });
  for (const [space, p] of [['source', [620, 330]], ['canvas', [700, 300]], ['frame', [0.3, 0.6]]]) {
    const q = C.dragPoint(S2, space, p, 60, 40);
    const a = S2.toScreen(space, p), b = S2.toScreen(space, q);
    near(b[0] - a[0], 60, space === 'frame' ? 0.05 * 960 * 1e-3 + 0.1 : 0.6); near(b[1] - a[1], 40, space === 'frame' ? 0.1 : 0.6);
  }
});
test('the AN-03 default origins (frame fractions) land on distinct screen points, not one corner', () => {
  const t = byId['AN-03'];
  const def = t.params.find((p) => p.name === 'origins');
  const space = C.paramSpace('AN-03', def, { params: {} });
  assert.equal(space, 'frame');
  const S2 = C.makeSpaces({ canvas, view: { W: 640, H: 360 }, cam: L.engineFitCamera({ width: 4386, height: 6000 }, canvas) });
  const pts = def.default.map((v) => S2.toScreen(space, v).map(Math.round).join());
  assert.ok(new Set(pts).size > pts.length / 2, pts.join(' '));
  assert.equal(C.paramSpace('AN-03', def, { params: { origin_space: 'source' } }), 'source');
});
test('paramSpace: every point, points and box parameter of the registry has a space', () => {
  const seen = {};
  for (const t of reg) for (const p of t.params) {
    if (!['point', 'points', 'box'].includes(p.type)) continue;
    const sp = C.splitSpace(C.paramSpace(t.id, p, { params: {} })).space;
    assert.ok(['source', 'canvas', 'frame', 'none'].includes(sp), `${t.id}.${p.name} -> ${sp}`);
    seen[`${t.id}.${p.name}`] = sp;
  }
  assert.equal(seen['STATIC-06.from_point'], 'canvas');           // canvas px: drawn and written as canvas px
  assert.equal(seen['AN-04.places'], 'canvas');                   // background auto without a map slot = the procedural map
  assert.equal(seen['DIA-01.focus'], 'source');
  assert.equal(seen['DIA-02.to_quad'], 'none');
  assert.equal(seen['CMP-02.finished_box'], 'canvas');
  assert.equal(C.paramSpace('AN-04', byId['AN-04'].params.find((p) => p.name === 'places'), { params: { background: 'base' } }), 'source');
  assert.equal(C.splitSpace(C.paramSpace('DIA-06', byId['DIA-06'].params.find((p) => p.name === 'painting_box'), {})).slot, 'room');
});
test('boxes: the registry array form is read and written as [x0, y0, x1, y1]', () => {
  assert.deepEqual(C.boxToRect([520, 40, 1520, 1040]), { x: 520, y: 40, w: 1000, h: 1000 });
  assert.deepEqual(C.boxToRect({ x: 1, y: 2, w: 3, h: 4 }), { x: 1, y: 2, w: 3, h: 4 });          // the old object form is still readable
  assert.deepEqual(C.rectToBox({ x: 1, y: 2, w: 3, h: 4 }), [1, 2, 4, 6]);
  assert.deepEqual(F.coerce({ type: 'box' }, { x: 1, y: 2, w: 3, h: 4 }), [1, 2, 4, 6]);
  assert.deepEqual(F.coerce({ type: 'box' }, '[1,2,3,4]'), [1, 2, 3, 4]);
  assert.equal(F.coerce({ type: 'box' }, 'x'), null);
  for (const t of reg) for (const p of t.params.filter((q) => q.type === 'box' && q.default)) {
    assert.ok(C.boxToRect(p.default), `${t.id}.${p.name}`);
    assert.equal(F.validateValue(p, p.default), null);
  }
  assert.ok(F.validateValue({ type: 'box' }, { x: 500, y: 0, w: 0 }));                              // the value the old widget wrote is flagged
});
test('pick: a click gives a value in the space of the field; region names only in source space', () => {
  const S2 = C.makeSpaces({ canvas, view: { W: 640, H: 360 }, cam: { cx: 500, cy: 500, zoom: 1 } });
  const regions = { EYE: { x: 500, y: 500, rx: 30, ry: 30 } };
  assert.equal(C.pickValue(S2, 'source', [320, 180], regions), 'EYE');
  assert.deepEqual(C.pickValue(S2, 'source', [320, 180], regions, true), [500, 500]);
  assert.deepEqual(C.pickValue(S2, 'canvas', [320, 180], regions), [960, 540]);
  assert.deepEqual(C.pickValue(S2, 'frame', [320, 180], regions), [0.5, 0.5]);
});

// ------------------------------------------------------------------ the save flow (U2-003)
const store = () => { const s = new Store(); s.load(fresh(), timing, 'rev1'); return s; };
const serverCopy = (sent, extra = {}) => ({ ...L.clone(sent.board), approvals: { storyboard: null }, ...extra });

test('save with no edit in between: the draft is the server copy, nothing is unsaved', () => {
  const s = store();
  s.commit('x', (d) => { d.shots[0].note = 'a'; });
  assert.equal(s.dirty, true);
  const sent = s.beginSave();
  const r = s.finishSave(sent, serverCopy(sent), 'rev2');
  assert.equal(r.edited, false); assert.equal(s.dirty, false); assert.equal(s.rev, 'rev2');
});
test('an edit made while the save is in flight is kept and stays unsaved', () => {
  const s = store();
  s.commit('x', (d) => { d.shots[0].note = 'a'; });
  const sent = s.beginSave();
  s.commit('typed meanwhile', (d) => { d.shots[0].note = 'a+b'; d.shots[1].note = 'second'; });
  const r = s.finishSave(sent, serverCopy(sent), 'rev2');
  assert.equal(r.edited, true);
  assert.equal(s.draft.shots[0].note, 'a+b'); assert.equal(s.draft.shots[1].note, 'second');
  assert.equal(s.dirty, true, 'the unsaved marker must stay on');
  // the next save sends the new edits
  const sent2 = s.beginSave();
  assert.equal(sent2.board.shots[0].note, 'a+b');
  s.finishSave(sent2, serverCopy(sent2), 'rev3');
  assert.equal(s.dirty, false);
});
test('an edit that is undone while the save is in flight leaves nothing unsaved; undo history survives the save', () => {
  const s = store();
  s.commit('x', (d) => { d.shots[0].note = 'a'; });
  const sent = s.beginSave();
  s.commit('y', (d) => { d.shots[0].note = 'b'; });
  s.undo();
  const r = s.finishSave(sent, serverCopy(sent), 'rev2');
  assert.equal(r.edited, false); assert.equal(s.dirty, false);
  assert.ok(s.canUndo);
  s.undo(); assert.equal(s.draft.shots[0].note, sbRaw.shots[0].note);
  assert.equal(s.dirty, true);
});
test('server-owned approvals are adopted and never count as unsaved; undo does not bring old approvals back', () => {
  const s = store();
  s.commit('x', (d) => { d.shots[0].note = 'a'; });
  const sent = s.beginSave();
  s.commit('y', (d) => { d.shots[0].note = 'b'; });
  s.finishSave(sent, serverCopy(sent, { approvals: { storyboard: { rev: 'rev2' } } }), 'rev2');
  assert.deepEqual(s.draft.approvals, { storyboard: { rev: 'rev2' } });
  s.undo();
  assert.deepEqual(s.draft.approvals, { storyboard: { rev: 'rev2' } }, 'undo keeps the server-owned approvals');
  const was = s.dirty;
  s.setApprovals({ storyboard: { rev: 'rev3' } });
  assert.equal(s.dirty, was, 'approving never changes the unsaved marker');
});
test('editVersion changes on every change of the draft and on nothing else', () => {
  const s = store(); const v = s.editVersion;
  s.select('s0001', null); assert.equal(s.editVersion, v);
  s.commit('x', (d) => { d.shots[0].note = 'q'; }); assert.equal(s.editVersion, v + 1);
  s.commit('same', (d) => { d.shots[0].note = 'q'; }); assert.equal(s.editVersion, v + 1);
  s.undo(); assert.equal(s.editVersion, v + 2);
});

// ------------------------------------------------------------------ the shortcut gate (U2-002)
const key = (k, o = {}) => ({ key: k, target: { tag: 'BODY' }, hasDraft: true, ...o });
test('no timeline shortcut acts while a dialog is open (any key, any dialog)', () => {
  for (const k of ['Delete', 'Backspace', ' ', 's', 'S', 'l', '[', ']', 'ArrowLeft', 'ArrowRight', 'Escape']) assert.equal(resolveShortcut(key(k, { modalOpen: true })), null, k);
  assert.equal(resolveShortcut(key('z', { ctrl: true, modalOpen: true })), null);
  assert.equal(resolveShortcut(key('s', { ctrl: true, modalOpen: true })), 'swallow');
});
test('typing in any text field keeps its own keys; Ctrl+S still saves', () => {
  for (const target of [{ tag: 'INPUT', type: 'text' }, { tag: 'INPUT', type: 'number' }, { tag: 'TEXTAREA' }, { tag: 'INPUT', type: 'search' }, { tag: 'DIV', editable: true }]) {
    for (const k of ['Delete', 'Backspace', ' ', 's', 'l', 'ArrowLeft', '[']) assert.equal(resolveShortcut(key(k, { target })), null, `${target.tag}/${k}`);
    assert.equal(resolveShortcut(key('z', { ctrl: true, target })), null);
    assert.equal(resolveShortcut(key('s', { ctrl: true, target })), 'save');
  }
});
test('a focused button, checkbox, range or select keeps Space, Enter and the arrows', () => {
  for (const target of [{ tag: 'BUTTON' }, { tag: 'INPUT', type: 'checkbox' }, { tag: 'INPUT', type: 'range' }, { tag: 'SELECT' }, { tag: 'A' }, { tag: 'DIV', role: 'button' }]) {
    for (const k of [' ', 'Enter', 'ArrowLeft', 'ArrowRight']) assert.equal(resolveShortcut(key(k, { target })), null, `${target.tag}/${k}`);
  }
  assert.equal(targetKind({ tag: 'INPUT', type: 'color' }), 'control');
  for (const k of ['s', 'l', 'Delete', '[']) assert.equal(resolveShortcut(key(k, { target: { tag: 'SELECT' } })), null, `select/${k}`);   // type-ahead letters belong to a select
});
test('in pick modes only Escape is ours (and Ctrl+S)', () => {
  for (const mode of ['picking', 'slotPicking']) {
    for (const k of ['Delete', ' ', 's', 'l', '[']) assert.equal(resolveShortcut(key(k, { [mode]: true })), null, `${mode}/${k}`);
    assert.equal(resolveShortcut(key('Escape', { [mode]: true })), 'cancelpick');
    assert.equal(resolveShortcut(key('s', { ctrl: true, [mode]: true })), 'save');
  }
});
test('on the page itself the shortcuts work; a held key does not repeat a destructive action', () => {
  assert.equal(resolveShortcut(key(' ')), 'play');
  assert.equal(resolveShortcut(key('s')), 'split');
  assert.equal(resolveShortcut(key('Delete')), 'delete');
  assert.equal(resolveShortcut(key('Delete', { repeat: true })), null);
  assert.equal(resolveShortcut(key('z', { ctrl: true })), 'undo');
  assert.equal(resolveShortcut(key('z', { meta: true, shift: true })), 'redo');
  assert.equal(resolveShortcut(key('s', { alt: true })), null);
  assert.equal(resolveShortcut(key('a', { composing: true })), null);
  assert.equal(resolveShortcut(key('Delete', { hasDraft: false })), null);
});

// ------------------------------------------------------------------ slots (U2-013, U2-014)
const assets = { P: { kind: 'image', width: 100, height: 100 }, Q: { kind: 'image', width: 90, height: 90 }, M: { kind: 'mask', width: 100, height: 100 }, V: { kind: 'video', width: 10, height: 10 } };
test('a slot takes only an asset of its own kind: image, video, mask', () => {
  const mask = { name: 'mask', type: 'image', required: true }, img = { name: 'image', type: 'image' }, vid = { name: 'inset', type: 'video' }, m1 = { name: 'mask_3', type: 'image' };
  assert.equal(S.slotKind(mask), 'mask'); assert.equal(S.slotKind(m1), 'mask'); assert.equal(S.slotKind(img), 'image'); assert.equal(S.slotKind(vid), 'video');
  assert.equal(S.slotKind({ name: 'x', type: 'mask' }), 'mask');
  assert.ok(S.fits(mask, assets.M)); assert.ok(!S.fits(mask, assets.P)); assert.ok(!S.fits(img, assets.M)); assert.ok(!S.fits(img, assets.V)); assert.ok(S.fits(vid, assets.V)); assert.ok(!S.fits(vid, assets.P));
  assert.ok(S.whyNot(mask, assets.P).includes('mặt nạ'));
  // every registry slot has a known kind
  for (const t of reg) for (const sl of t.slots) assert.ok(['image', 'video', 'mask', 'text'].includes(S.slotKind(sl)), `${t.id}.${sl.name}`);
});
test('switching technique never puts the painting into a video or mask slot', () => {
  const old = { image: { asset: 'P' } };
  for (const id of ['LAY-04', 'FOOT-01', 'LAY-05', 'DIA-05', 'HI-02', 'LAY-07']) {
    const out = S.carrySlots(byId[id].slots, old, assets);
    for (const sl of byId[id].slots) {
      const a = out[sl.name]?.asset;
      if (a) assert.ok(S.fits(sl, assets[a]), `${id}.${sl.name} got ${a}`);
    }
  }
  const lay4 = S.carrySlots(byId['LAY-04'].slots, old, assets);
  assert.equal(lay4.image.asset, 'P'); assert.equal(lay4.inset, undefined);
  const lay5 = S.carrySlots(byId['LAY-05'].slots, old, assets);
  assert.equal(lay5.mask, undefined);
  // same-name slots stay when the kind fits, other image assets fill the next image slot in order
  const two = S.carrySlots(byId['LAY-01'].slots, { left: { asset: 'P' }, right: { asset: 'Q' } }, assets);
  assert.deepEqual(two, { left: { asset: 'P' }, right: { asset: 'Q' } });
  // a mask that was in a mask slot stays in a mask slot of the new technique, never becomes "the picture"
  const m = S.carrySlots(byId['LAY-05'].slots, { image: { asset: 'P' }, mask: { asset: 'M' } }, assets);
  assert.deepEqual(m.mask, { asset: 'M' });
});
test('an overlay has its own slots: a missing mask makes it incomplete, the inherited image does not', () => {
  const tech = byId['HI-03'];
  const shot = { id: 's1', slots: { image: { asset: 'P' } } };
  const ov = { id: 'o1', technique: 'HI-03', params: {} };
  assert.deepEqual(S.missingSlots(ov, tech, shot, true).map((m) => m.name), ['mask']);
  ov.slots = { mask: { asset: 'M' } };
  assert.deepEqual(S.missingSlots(ov, tech, shot, true), []);
  assert.deepEqual(S.missingSlots(ov, tech, { id: 's2', slots: {} }, true).map((m) => m.name), ['image']);
  assert.deepEqual(S.effectiveSlot({ id: 'o' }, 'image', shot, true), { asset: 'P', own: false });
  assert.equal(S.effectiveSlot({ id: 'o' }, 'mask', { slots: { mask: { asset: 'M' } } }, true), null);   // only `image` is inherited
});
test('the incomplete map joins the registry rules and the server issues, and labels them "thiếu: ..."', () => {
  const draft = { shots: [{ id: 's1', technique: 'LAY-01', slots: { left: { asset: 'P' } }, overlays: [{ id: 'o1', technique: 'HI-03' }] }] };
  const issues = [{ level: 'warn', code: 'incomplete', path: 'shots[0].overlays[0].params.at', message: "required parameter 'at' is empty" }, { level: 'warn', code: 'other', path: 'shots[0]', message: 'x' }];
  const m = S.incompleteMap(draft, (id) => byId[id], issues);
  assert.deepEqual(m.get('s1'), ['right']);
  assert.deepEqual(m.get('s1/o1'), ['at', 'mask']);                 // its image is the shot's picture
  assert.equal(S.missingLabel(['mask']), 'thiếu: mask');
  assert.deepEqual(S.issueMissing({ missing: ['a', 'b'] }), ['a', 'b']);
});
test('region usage finds the items that name a region and rename updates them', () => {
  const draft = { shots: [
    { id: 's1', technique: 'STATIC-01', slots: { image: { asset: 'A' } }, params: {}, overlays: [{ id: 'o1', technique: 'HI-01', params: { at: 'MIRROR' } }, { id: 'o2', technique: 'AN-02', params: { points: ['MIRROR', [1, 2], 'LAMP'] } }] },
    { id: 's2', technique: 'STATIC-01', slots: { image: { asset: 'B' } }, params: {}, overlays: [{ id: 'o1', technique: 'HI-01', params: { at: 'MIRROR' } }] },
  ] };
  const u = S.regionUsage(draft, 'A', 'MIRROR');
  assert.deepEqual(u.map((x) => x.where), ['s1/o1', 's1/o2']);                 // asset B's own MIRROR is not asset A's
  assert.deepEqual(S.replaceRegionRefs(draft.shots[0].overlays[1].params, 'MIRROR', 'GLASS'), { points: ['GLASS', [1, 2], 'LAMP'] });
  assert.deepEqual(S.replaceRegionRefs({ at: 'MIRROR' }, 'MIRROR', [10, 20]), { at: [10, 20] });
});

// ------------------------------------------------------------------ drag to the left (U2-016)
test('U2-016 cause: in a pause the nearest word start is a far, later word; the drag used to jump to it', () => {
  const real = JSON.parse(fs.readFileSync('projects/arnolfini_edit/storyboard.json'));
  const tm = JSON.parse(fs.readFileSync('projects/arnolfini_edit/timing.json'));
  const sb = L.derive(L.clone(real), tm);
  const i = sb.shots.findIndex((s) => s.id === 's0011');
  const before = sb.shots[i]._t0;                         // 80.01, right after a long pause
  // the old rule (always the nearest word start) sends every time of the pause to the word at 80.15
  const old = (t) => tm.words[L.nearestWordStart(tm.words, t).idx].s;
  for (const t of [79.5, 79, 78.5, 78, 77.6]) assert.equal(old(t), 80.15);
  // now a word is only snapped to when it is close; in a pause the time is free and follows the pointer
  for (const t of [79.5, 79, 78.5, 78]) {
    const c = L.clone(sb); L.derive(c, tm);
    assert.ok(E.moveBoundary(c, i, t, tm.words, false));
    L.derive(c, tm);
    assert.ok(Math.abs(c.shots[i]._t0 - t) < 1e-6, `${t} -> ${c.shots[i]._t0}`);
    assert.ok(c.shots[i]._t0 < before);
  }
  // near a word it still snaps
  const c = L.clone(sb); L.derive(c, tm);
  E.moveBoundary(c, i, 80.2, tm.words, false); L.derive(c, tm);
  assert.ok(Math.abs(c.shots[i]._t0 - 80.15) < 1e-6);
  assert.equal(L.anchorFromTime(78, tm.words, false, Infinity).w, 189);   // the explicit "nearest word" buttons keep their meaning
});

// ------------------------------------------------------------------ timeline grab zone (U2-007)
test('the boundary grab zone scales with the shot width: a click on a shot is never swallowed', () => {
  assert.equal(L.grabZone(200, 200), 5);
  assert.equal(L.grabZone(20, 20), 3);
  assert.ok(L.grabZone(8, 400) < 1.5);                 // too narrow to grab: it is a click
  let grabbed = 0;
  for (let x = 0; x < 20; x += 0.5) if (Math.min(x, 20 - x) <= L.grabZone(20, 20)) grabbed++;
  assert.ok(grabbed / 40 <= 0.35, `${grabbed}/40 of a 20 px shot is grab zone`);
});

// ------------------------------------------------------------------ form values (U2-004) and local checks (U2-005)
test('numbers are held to each bound alone', () => {
  const d = { type: 'number', min: 5, max: 5000, default: 440 };
  assert.equal(F.coerce(d, '-5'), 5); assert.equal(F.coerce(d, 99999), 5000); assert.equal(F.coerce(d, '1e3'), 1000);
  assert.equal(F.coerce({ type: 'number', min: 0 }, -3), 0);
  assert.equal(F.coerce({ type: 'number', max: 1 }, 7), 1);
  assert.equal(F.coerce(d, 'abc'), 440);
});
test('a point outside its picture is reported; one inside, a region name and a canvas point are not', () => {
  const sb = { assets: { A: { kind: 'image', width: 4386, height: 6000, regions: { R: { x: 10, y: 10 } } } },
    shots: [{ id: 's1', technique: 'STATIC-01', slots: { image: { asset: 'A' } }, params: {}, overlays: [
      { id: 'o1', technique: 'HI-01', params: { at: [5000, 99999] } }, { id: 'o2', technique: 'HI-01', params: { at: [100, 100] } },
      { id: 'o3', technique: 'HI-01', params: { at: 'R' } }, { id: 'o4', technique: 'HI-01', params: { at: [-10, -10] } }] }] };
  const r = outsideIssues(sb, (id) => byId[id]);
  assert.deepEqual(r.map((i) => i.path), ['shots[0].overlays[0].params.at', 'shots[0].overlays[3].params.at']);
  assert.ok(r.every((i) => i.level === 'warn'));
});
