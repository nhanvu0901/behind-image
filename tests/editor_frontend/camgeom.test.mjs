// d-camera (D22): the geometry of the camera frames in the source view (camgeom.js), with no DOM.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as G from '../../bti/editor/static/js/camgeom.js';
import { makeSpaces } from '../../bti/editor/static/js/coords.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url))).techniques;
const tech = (id) => REG.find((t) => t.id === id);
const CANVAS = { w: 1920, h: 1080 };
const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} != ${b}`);

// ---- what a key sees: the engine's definition (bti/engine/vfx.py Img.view: panel x = panel_w / 2 + (x - cx) * zoom)
test('the frame of a key is panel / zoom, centred on (cx, cy), and the engine maps its edges onto the panel edges', () => {
  const panel = { w: 900, h: 740 }, k = { cx: 1200, cy: 800, zoom: 0.65 };
  const r = G.keyToRect(k, panel);
  near(r.w, 900 / 0.65); near(r.h, 740 / 0.65);
  near(r.x + r.w / 2, 1200); near(r.y + r.h / 2, 800);
  const toPanel = (x, y) => [panel.w / 2 + (x - k.cx) * k.zoom, panel.h / 2 + (y - k.cy) * k.zoom];   // the engine's formula
  const [x0, y0] = toPanel(r.x, r.y), [x1, y1] = toPanel(r.x + r.w, r.y + r.h);
  near(x0, 0); near(y0, 0); near(x1, panel.w); near(y1, panel.h);
});
test('rectToKey undoes keyToRect', () => {
  const k = { cx: 321.5, cy: 77.25, zoom: 2.5 }, p = { w: 1920, h: 1080 };
  const b = G.rectToKey(G.keyToRect(k, p), p);
  near(b.cx, k.cx); near(b.cy, k.cy); near(b.zoom, k.zoom);
});
test('a frame drawn through the spaces of coords.js has the aspect of the panel', () => {
  const view = { W: 640, H: 360 };
  const S = makeSpaces({ canvas: CANVAS, view, cam: { cx: 500, cy: 400, zoom: 0.5 } });
  const panel = { w: 900, h: 740 }, r = G.keyToRect({ cx: 400, cy: 300, zoom: 1.2 }, panel);
  const a = S.sourceToScreen(r.x, r.y), b = S.sourceToScreen(r.x + r.w, r.y + r.h);
  near((b[0] - a[0]) / (b[1] - a[1]), 900 / 740, 1e-9);
});
test('roundKey keeps one decimal for the centre and four for the zoom', () => {
  assert.deepEqual(G.roundKey({ cx: 10.04, cy: 10.06, zoom: 0.123456 }), { cx: 10, cy: 10.1, zoom: 0.1235 });
});

// ---- the panel of every camera parameter, from the registry and the engine
const slotsOf = (names) => Object.fromEntries(names.map((n) => [n, { asset: 'A_' + n }]));
test('LAY-01: each camera looks at its own slot through the panel_w_px x panel_h_px cell (registry defaults, then the shot\'s values)', () => {
  const t = tech('LAY-01');
  let l = G.cameraTarget(t, 'camera_left', {}, slotsOf(['left', 'right']), CANVAS);
  assert.deepEqual([l.slot, l.panel, l.known], ['left', { w: 900, h: 740 }, true]);
  l = G.cameraTarget(t, 'camera_right', { panel_w_px: 700, panel_h_px: 500 }, slotsOf(['left', 'right']), CANVAS);
  assert.deepEqual([l.slot, l.panel], ['right', { w: 700, h: 500 }]);
});
test('a camera over the whole frame has the canvas as its panel, and a 1280x720 canvas changes it', () => {
  assert.deepEqual(G.cameraTarget(tech('CAM-01'), 'camera', {}, slotsOf(['image']), CANVAS).panel, { w: 1920, h: 1080 });
  assert.deepEqual(G.cameraTarget(tech('CAM-01'), 'camera', {}, slotsOf(['image']), { w: 1280, h: 720 }).panel, { w: 1280, h: 720 });
});
test('CAM-02: the two cameras look at the foreground and at the background', () => {
  const t = tech('CAM-02');
  assert.equal(G.cameraTarget(t, 'fg_camera', {}, {}, CANVAS).slot, 'foreground');
  assert.equal(G.cameraTarget(t, 'bg_camera', {}, {}, CANVAS).slot, 'background');
});
test('LAY-02 tiles, LAY-04 inset, CMP-01/03/04 panels, X-CMP-01 anchor', () => {
  assert.deepEqual(G.cameraTarget(tech('LAY-02'), 'camera_3', {}, {}, CANVAS), { slot: 'tile_3', panel: { w: 930, h: 520 }, known: true });
  assert.deepEqual(G.cameraTarget(tech('LAY-04'), 'inset_camera', {}, {}, CANVAS), { slot: 'inset', panel: { w: 560, h: 315 }, known: true });
  assert.deepEqual(G.cameraTarget(tech('LAY-04'), 'camera', {}, {}, CANVAS).panel, { w: 1920, h: 1080 });
  assert.deepEqual(G.cameraTarget(tech('CMP-01'), 'camera', {}, {}, CANVAS), { slot: 'colour', panel: { w: 930, h: 800 }, known: true });
  assert.deepEqual(G.cameraTarget(tech('CMP-03'), 'camera', {}, {}, CANVAS).panel, { w: 610, h: 900 });
  assert.deepEqual(G.cameraTarget(tech('CMP-04'), 'camera', {}, {}, CANVAS).panel, { w: 900, h: 900 });
  assert.deepEqual(G.cameraTarget(tech('X-CMP-01'), 'camera_anchor', {}, {}, CANVAS), { slot: 'anchor', panel: { w: 900, h: 740 }, known: true });
  assert.deepEqual(G.cameraTarget(tech('CMP-05'), 'camera', {}, {}, CANVAS), { slot: 'state_a', panel: { w: 1920, h: 1080 }, known: true });
});
test('CMP-02: the finished picture fills finished_box, the stage tile is derive_px square', () => {
  const t = tech('CMP-02');
  assert.deepEqual(G.cameraTarget(t, 'finished_camera', {}, {}, CANVAS).panel, { w: 1000, h: 1000 });
  assert.deepEqual(G.cameraTarget(t, 'finished_camera', { finished_box: [100, 100, 1100, 600] }, {}, CANVAS).panel, { w: 1000, h: 500 });
  assert.deepEqual(G.cameraTarget(t, 'stage_camera', { derive_px: 400 }, {}, CANVAS).panel, { w: 400, h: 400 });
  assert.equal(G.cameraTarget(t, 'stage_camera', {}, {}, CANVAS).slot, 'finished');
});
test('LAY-06: the base layer is the background slot, or the image slot when there is no background', () => {
  const t = tech('LAY-06');
  assert.equal(G.cameraTarget(t, 'camera_base', {}, slotsOf(['image', 'background']), CANVAS).slot, 'background');
  assert.equal(G.cameraTarget(t, 'camera_base', {}, slotsOf(['image']), CANVAS).slot, 'image');
});
test('LAY-07: the tile cell follows the number of tiles that have a picture and the columns; the object looks through the whole frame', () => {
  const t = tech('LAY-07');
  assert.deepEqual(G.cameraTarget(t, 'camera_1', {}, slotsOf(['tile_1', 'tile_2', 'tile_3', 'tile_4']), CANVAS).panel, { w: 960, h: 540 });
  assert.deepEqual(G.cameraTarget(t, 'camera_1', {}, slotsOf(['tile_1', 'tile_2']), CANVAS).panel, { w: 960, h: 1080 });
  assert.deepEqual(G.cameraTarget(t, 'camera_1', { columns: 3 }, slotsOf(['tile_1', 'tile_2', 'tile_3', 'tile_4']), CANVAS).panel, { w: 640, h: 540 });
  assert.deepEqual(G.cameraTarget(t, 'object_camera', {}, slotsOf(['object']), CANVAS), { slot: 'object', panel: { w: 1920, h: 1080 }, known: true });
});
test('LAY-08: the view is one tile of "CxR" tiles', () => {
  const t = tech('LAY-08');
  assert.deepEqual(G.cameraTarget(t, 'camera', {}, {}, CANVAS).panel, { w: 480, h: 540 });
  assert.deepEqual(G.cameraTarget(t, 'camera', { tiles: '2 x 2' }, {}, CANVAS).panel, { w: 960, h: 540 });
});
test('an unknown camera parameter falls back to the first image slot and the whole frame, and says it is not known', () => {
  const fake = { id: 'NEW-01', slots: [{ name: 'mask', type: 'mask' }, { name: 'pic', type: 'image' }], params: [{ name: 'camera', type: 'camera' }] };
  assert.deepEqual(G.cameraTarget(fake, 'camera', {}, {}, CANVAS), { slot: 'pic', panel: { w: 1920, h: 1080 }, known: false });
});

test('every camera parameter of the registry has an entry in the table, and the table names nothing that is not in the registry', () => {
  const missing = [], extra = [];
  for (const t of REG) {
    const cams = t.params.filter((p) => p.type === 'camera').map((p) => p.name);
    for (const n of cams) if (!G.TARGETS[t.id]?.[n]) missing.push(`${t.id}.${n}`);
  }
  for (const [id, m] of Object.entries(G.TARGETS)) for (const n of Object.keys(m)) {
    if (!tech(id)?.params.some((p) => p.name === n && p.type === 'camera')) extra.push(`${id}.${n}`);
  }
  assert.deepEqual(missing, []); assert.deepEqual(extra, []);
});
test('every table entry names a slot of its technique (alternatives of "a|b" included) and gives a positive panel with the registry defaults', () => {
  const bad = [];
  for (const t of REG) for (const p of t.params.filter((q) => q.type === 'camera')) {
    const r = G.cameraTarget(t, p.name, {}, {}, CANVAS);
    const slots = String(G.TARGETS[t.id][p.name][0]).split('|');
    if (!slots.every((s) => t.slots.some((x) => x.name === s))) bad.push(`${t.id}.${p.name}: slot ${slots}`);
    if (!(r.panel.w > 0 && r.panel.h > 0)) bad.push(`${t.id}.${p.name}: panel ${JSON.stringify(r.panel)}`);
  }
  assert.deepEqual(bad, []);
});

// ---- the cameras of a shot
const A = (w, h) => ({ width: w, height: h });
const keys = (n, z = 0.5) => Array.from({ length: n }, (_, i) => ({ at: { rel: i / Math.max(1, n - 1) }, cx: 500 + i * 100, cy: 400, zoom: z + i * 0.1, ease: 'linear' }));
test('cameraSets lists every camera that has keys and a picture, in registry order, with any number of keys', () => {
  const shot = { technique: 'LAY-01', slots: { left: { asset: 'p' }, right: { asset: 'q' } }, params: { camera_right: keys(5), camera_left: keys(3) } };
  const sets = G.cameraSets(tech('LAY-01'), shot, { p: A(3000, 2000), q: A(1000, 1500) }, CANVAS);
  assert.deepEqual(sets.map((s) => [s.name, s.slot, s.assetKey, s.keys.length, s.panel]), [
    ['camera_left', 'left', 'p', 3, { w: 900, h: 740 }], ['camera_right', 'right', 'q', 5, { w: 900, h: 740 }]]);
});
test('cameraSets skips a camera without a picture, without keys, or with a key that is not a number', () => {
  const t = tech('LAY-01');
  const shot = { slots: { left: { asset: 'p' }, right: {} }, params: { camera_left: keys(2), camera_right: keys(2) } };
  assert.deepEqual(G.cameraSets(t, shot, { p: A(100, 100) }, CANVAS).map((s) => s.name), ['camera_left']);
  assert.deepEqual(G.cameraSets(t, { ...shot, params: { camera_left: [{ at: { rel: 0 }, cx: 'x', cy: 1, zoom: 1 }] } }, { p: A(100, 100) }, CANVAS), []);
  assert.deepEqual(G.cameraSets(t, { ...shot, params: { camera_left: [{ at: { rel: 0 }, cx: 1, cy: 1, zoom: 0 }] } }, { p: A(100, 100) }, CANVAS), []);
  assert.deepEqual(G.cameraSets(t, shot, { p: A(0, 100) }, CANVAS), []);
});

// ---- moving the centre
test('moveKey moves the centre and keeps the zoom', () => {
  const k = { at: { rel: 0 }, cx: 100, cy: 100, zoom: 0.7, ease: 'out_cubic' };
  const b = G.centreBounds(A(2000, 1000), k);
  assert.deepEqual(G.moveKey(k, 50, -20, b), { ...k, cx: 150, cy: 80 });
});
test('the centre stays inside the picture, however far the pointer goes', () => {
  const k = { cx: 100, cy: 100, zoom: 1 }, a = A(2000, 1000), b = G.centreBounds(a, k);
  const m = G.moveKey(k, 1e7, 1e7, b);
  assert.deepEqual([m.cx, m.cy], [2000, 1000]);
  const n = G.moveKey(k, -1e7, -1e7, b);
  assert.deepEqual([n.cx, n.cy], [0, 0]);
});
test('a centre that is already outside the picture is not pulled back, only kept from going further out', () => {
  const k = { cx: -300, cy: 100, zoom: 1 }, b = G.centreBounds(A(2000, 1000), k);
  assert.equal(G.moveKey(k, 10, 0, b).cx, -290);
  assert.equal(b.x0, -300);
  assert.equal(G.moveKey(k, -10, 0, b).cx, -300);
});
test('the centre never passes the engine limit of 1e6', () => {
  const b = G.centreBounds(A(2000, 1000), { cx: 5e6, cy: 0, zoom: 1 });
  assert.equal(b.x1, 1e6);
});

// ---- resizing by a corner
const P = { w: 900, h: 740 };
test('a corner drag keeps the centre and the other fields, and changes only the zoom', () => {
  const k = { at: { rel: 1 }, cx: 700, cy: 500, zoom: 0.8, ease: 'in_quad' };
  const r = G.keyToRect(k, P);
  for (const corner of Object.keys(G.CORNERS)) {
    const [sx, sy] = G.CORNERS[corner];
    const out = G.resizeKey(k, P, corner, sx * 100, sy * 100 * P.h / P.w);   // pulled outward along the diagonal: a bigger frame
    assert.deepEqual([out.cx, out.cy, out.at, out.ease], [700, 500, k.at, 'in_quad'], corner);
    near(out.zoom, k.zoom / ((r.w / 2 + 100) / (r.w / 2)), 1e-9);
  }
});
test('dragging a corner along the diagonal lands it exactly on the pointer, outward or inward', () => {
  const k = { cx: 700, cy: 500, zoom: 1 };                          // frame 900 x 740, half 450 x 370
  const out = G.resizeKey(k, P, 'se', 90, 74);                      // +20 % along the diagonal
  near(out.zoom, 1 / 1.2, 1e-9);
  const inn = G.resizeKey(k, P, 'nw', 90, 74);                      // the nw corner pulled towards the centre by 20 %
  near(inn.zoom, 1 / 0.8, 1e-9);
  const r2 = G.keyToRect(out, P), r1 = G.keyToRect(k, P);
  near(r2.x + r2.w, r1.x + r1.w + 90); near(r2.y + r2.h, r1.y + r1.h + 74);   // the corner is where the pointer put it
});
test('pulling a corner along one side only resizes by half as much (the pointer is projected on the diagonal)', () => {
  const k = { cx: 0, cy: 0, zoom: 1 };
  near(G.resizeKey(k, P, 'se', 450, 0).zoom, 1 / 1.5, 1e-9);        // x doubled, y unchanged: s = (2 + 1) / 2
  near(G.resizeKey(k, P, 'se', 0, 370).zoom, 1 / 1.5, 1e-9);
});
test('the zoom stays within the limits of the form (0.01) and of the engine (1000)', () => {
  const k = { cx: 0, cy: 0, zoom: 1 };
  assert.equal(G.resizeKey(k, P, 'se', 1e9, 1e9).zoom, G.ZOOM_MIN);
  assert.equal(G.resizeKey(k, P, 'se', -1e9, -1e9).zoom, G.ZOOM_MAX);          // past the centre: the smallest frame
  assert.equal(G.clampZoom(NaN), 1);
  assert.equal(G.clampZoom(5000), 1000);
});
test('a corner drag then a centre drag compose: the frame keeps its size while moving', () => {
  const k = { cx: 700, cy: 500, zoom: 0.5 };
  const r1 = G.keyToRect(k, P), moved = G.moveKey(k, 40, 30, G.centreBounds(A(3000, 3000), k)), r2 = G.keyToRect(moved, P);
  near(r2.w, r1.w); near(r2.h, r1.h);
});

// ---- picking with overlap
const R = (x, y, w, h) => ({ x, y, w, h });
const body = (h) => h && { index: h.index, part: h.part };
test('a small frame inside a large one can be picked, the large one outside the small one', () => {
  const rects = [R(0, 0, 400, 300), R(150, 100, 60, 40)];
  assert.deepEqual(body(G.hitTest(rects, 0, [170, 120])), { index: 1, part: 'body' });
  assert.deepEqual(body(G.hitTest(rects, 0, [20, 250])), { index: 0, part: 'body' });
  assert.deepEqual(body(G.hitTest(rects, 1, [170, 120])), { index: 1, part: 'body' });
  assert.deepEqual(body(G.hitTest(rects, 1, [20, 250])), { index: 0, part: 'body' });
});
test('the handles of the selected key win over a smaller frame that covers them', () => {
  const rects = [R(0, 0, 400, 300), R(392, 292, 10, 10)];            // the small frame lies on the large one's corner
  assert.deepEqual(G.hitTest(rects, 0, [399, 299]), { index: 0, part: 'corner', corner: 'se' });
  assert.deepEqual(body(G.hitTest(rects, -1, [399, 299])), { index: 1, part: 'body' });      // nothing selected: the smallest frame there
});
test('only the selected key has corner handles', () => {
  const rects = [R(0, 0, 100, 100), R(300, 0, 100, 100)];
  assert.equal(G.hitTest(rects, 0, [400, 100]).part, 'body');
  assert.deepEqual(G.hitTest(rects, 1, [400, 100]), { index: 1, part: 'corner', corner: 'se' });
});
test('a corner is found within the tolerance, the nearest corner wins, and far away nothing is hit', () => {
  const rects = [R(100, 100, 12, 12)];
  assert.deepEqual(G.hitTest(rects, 0, [95, 95]), { index: 0, part: 'corner', corner: 'nw' });
  assert.deepEqual(G.hitTest(rects, 0, [116, 112]), { index: 0, part: 'corner', corner: 'se' });
  assert.equal(G.hitTest(rects, 0, [200, 200]), null);
  assert.equal(G.hitTest([], 0, [1, 1]), null);
});
test('equal frames are a stack: the selected one stays the target, else the last one; the stack is reported', () => {
  const rects = [R(0, 0, 100, 100), R(0, 0, 100, 100), R(0, 0, 100, 100)];
  for (const s of [0, 1, 2]) assert.deepEqual(G.hitTest(rects, s, [50, 50]), { index: s, part: 'body', ties: [0, 1, 2] });
  assert.equal(G.hitTest(rects.slice(0, 2), 5, [50, 50]).index, 1);
  const mixed = [R(0, 0, 100, 100), R(0, 0, 100, 100), R(40, 40, 10, 10)];
  assert.deepEqual(G.hitTest(mixed, 2, [10, 10]), { index: 1, part: 'body', ties: [0, 1] });   // the selected one is not under the pointer
  assert.deepEqual(G.hitTest(mixed, 0, [45, 45]), { index: 2, part: 'body', ties: [2] });      // the small one wins over the stack
});
test('a click walks through a stack of equal frames, round and round', () => {
  assert.equal(G.nextInStack([0, 1, 2], 0), 1);
  assert.equal(G.nextInStack([0, 1, 2], 1), 2);
  assert.equal(G.nextInStack([0, 1, 2], 2), 0);
  assert.equal(G.nextInStack([3], 3), 3);
  assert.equal(G.nextInStack([1, 4], 2), 4);
});
test('five nested frames: every one can be picked in turn from its own ring', () => {
  const rects = [0, 1, 2, 3, 4].map((i) => R(i * 40, i * 30, 500 - i * 80, 400 - i * 60));
  rects.forEach((r, i) => assert.equal(G.hitTest(rects, 0, [r.x + 12, r.y + r.h / 2]).index, i, `ring ${i}`));
});

// ---- the source view
test('without frames, or with frames inside the picture, the view is the picture fitted at 94 % (as it always was)', () => {
  const a = A(2000, 1000), fit = Math.min(1920 / 2000, 1080 / 1000) * 0.94;
  assert.deepEqual(G.sourceViewCamera(a, CANVAS), { cx: 1000, cy: 500, zoom: fit });
  assert.deepEqual(G.sourceViewCamera(a, CANVAS, [R(100, 100, 500, 300)]), { cx: 1000, cy: 500, zoom: fit });
});
test('a frame larger than the picture makes the view zoom out until it fits, centred on both', () => {
  const a = A(2000, 1000), fit = Math.min(1920 / 2000, 1080 / 1000) * 0.94;
  const c = G.sourceViewCamera(a, CANVAS, [R(-1000, -500, 4000, 2000)]);
  assert.ok(c.zoom < fit);
  near(c.cx, 1000); near(c.cy, 500);
  near(c.zoom, Math.min(1920 / 4000, 1080 / 2000) * 0.94);
  const d = G.sourceViewCamera(a, CANVAS, [R(1500, 100, 1500, 600)]);   // sticking out to the right only: the centre moves right
  assert.ok(d.cx > 1000);
});

// ---- the selection
test('the selection is kept while it exists, and falls back to the first camera, first key', () => {
  const sets = [{ name: 'a', keys: [1, 2, 3] }, { name: 'b', keys: [1] }];
  assert.deepEqual(G.resolveSelection({ shot: 's1', param: 'b', index: 0 }, 's1', sets), { shot: 's1', param: 'b', index: 0 });
  assert.deepEqual(G.resolveSelection({ shot: 's1', param: 'a', index: 2 }, 's1', sets), { shot: 's1', param: 'a', index: 2 });
  assert.deepEqual(G.resolveSelection({ shot: 's1', param: 'a', index: 9 }, 's1', sets), { shot: 's1', param: 'a', index: 2 });
  assert.deepEqual(G.resolveSelection({ shot: 's1', param: 'zz', index: 1 }, 's1', sets), { shot: 's1', param: 'a', index: 0 });
  assert.deepEqual(G.resolveSelection({ shot: 's0', param: 'b', index: 0 }, 's1', sets), { shot: 's1', param: 'a', index: 0 });
  assert.deepEqual(G.resolveSelection(null, 's1', []), { shot: 's1', param: null, index: 0 });
});
