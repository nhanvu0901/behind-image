// The plain sentence of a shot (c4pages, step 5): from the registry's Vietnamese names, the picture, the region and the overlays; never an id.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { shotSentence, overlayPhrases, mainAssetKey, regionWords, cameraFocus, looksRaw } from '../../bti/editor/static/js/shotsentence.js';
import { derive } from '../../bti/editor/static/js/logic.js';
import { isVietnamese } from '../../bti/editor/static/js/errmsg.js';

const read = (p) => JSON.parse(fs.readFileSync(new URL('../../' + p, import.meta.url), 'utf8'));
const REG = read('style/gae/techniques.json').techniques;
const BY = Object.fromEntries(REG.map((t) => [t.id, t]));
const tech = (id) => BY[id] || null;
const load = (p) => { const sb = read(`projects/${p}/storyboard.json`); let tm = { words: [], duration: 600 }; try { tm = read(`projects/${p}/timing.json`); } catch { /* none */ } derive(sb, tm); return sb; };
const envOf = (sb, title = 'The Arnolfini Portrait') => ({ tech, assets: sb.assets, mainKey: mainAssetKey(sb, title) });

test('ten real shots of the Arnolfini storyboard and the technique lab, in words (the examples of the report)', () => {
  const arn = load('arnolfini'), lab = load('technique_lab');
  const A = envOf(arn), B = envOf(lab);
  const S = (sb, id) => sb.shots.find((s) => s.id === id);
  const got = [
    shotSentence(S(arn, 's0001'), A), shotSentence(S(arn, 's0002'), A), shotSentence(S(arn, 's0003'), A), shotSentence(S(arn, 's0004'), A), shotSentence(S(arn, 's0009'), A),
    shotSentence(S(arn, 's0011'), A), shotSentence(S(arn, 's0020'), A), shotSentence(S(lab, 's0011'), B), shotSentence(S(lab, 's0014'), B), shotSentence(S(lab, 's0022'), B),
  ];
  assert.deepEqual(got, [
    'Zoom vào “Mirror”',
    'Kéo ra, thấy cả bức tranh',
    'Giữ yên cả bức tranh · thước kích thước',
    'Zoom kèm dịch tới “Latin inscription” · 2 vòng sáng · nhãn chi tiết',
    'Thẻ tiêu đề: The arnolfini portrait',
    'Ảnh tĩnh: ảnh “Grote Markt, Bruges” · nhãn tác phẩm',
    'Giữ yên cả bức tranh · 2 nhãn tên',
    'Hai ô: cả bức tranh và ảnh “Virgin and Child with Canon v…”',
    'Cửa sổ ảnh chèn: ảnh “The Arnolfini Portrait” và clip “Virgin and Child with Canon v…”',
    'Zoom kèm dịch tới “Dog” · khoanh tròn',
  ]);
});

test('every technique of the registry gives a sentence that is never empty, never its id and never an underscore word', () => {
  assert.ok(REG.length >= 85);
  for (const t of REG) {
    const asBase = shotSentence({ technique: t.id, slots: {}, params: {}, overlays: [] }, { tech, assets: {}, mainKey: null });
    assert.ok(asBase.length > 2 && asBase.length <= 96, `${t.id}: ${asBase}`);
    assert.ok(!looksRaw(asBase), `${t.id} shows something raw: ${asBase}`);
    assert.ok(!asBase.includes(t.id), `${t.id} is in its own sentence: ${asBase}`);
    const asOverlay = shotSentence({ technique: 'CAM-01', slots: {}, params: {}, overlays: [{ technique: t.id }] }, { tech, assets: {}, mainKey: null });
    assert.ok(!looksRaw(asOverlay), `${t.id} as an overlay: ${asOverlay}`);
    assert.ok(!asOverlay.includes(t.id), `${t.id} as an overlay: ${asOverlay}`);
  }
});

test('a shot of every real storyboard of the project gives a plain sentence', () => {
  let n = 0;
  for (const p of ['arnolfini', 'arnolfini_edit', 'technique_lab', 'lab_annot', 'lab_diagrams', 'lab_layouts', 'lab_text']) {
    const sb = load(p), env = envOf(sb);
    for (const s of sb.shots) {
      const t = shotSentence(s, env);
      n++;
      assert.ok(t && !looksRaw(t), `${p}/${s.id}: ${t}`);
      assert.ok(!t.includes(s.technique), `${p}/${s.id}: ${t}`);
      assert.ok(isVietnamese(t) || /^[A-Z]/.test(t), t);
    }
  }
  assert.ok(n > 200, 'the real storyboards have more than 200 shots: ' + n);
});

test('a technique the registry does not know, or a shot with nothing, is "Một cảnh" (never an id)', () => {
  assert.equal(shotSentence({ technique: 'ZZ-99', overlays: [] }, { tech }), 'Một cảnh');
  assert.equal(shotSentence({}, {}), 'Một cảnh');
  assert.equal(shotSentence(null, undefined), 'Một cảnh');
  assert.equal(shotSentence({ technique: 'ZZ-99', overlays: [{ technique: 'HI-01' }] }, { tech }), 'Một cảnh · vòng sáng');
  assert.equal(shotSentence({ technique: 'CAM-01', slots: { image: { asset: 'gone' } } }, { tech, assets: {} }), 'Zoom vào bức tranh');
  assert.equal(shotSentence({ technique: 'CAM-05', slots: {} }, { tech, assets: {} }), 'Zoom kèm dịch trên bức tranh', 'a shot that lost its picture still reads as a sentence');
});

test('the camera family: the region it ends on, the whole painting, another picture', () => {
  const assets = { A: { title: 'Portrait', kind: 'image', regions: { FACE: { x: 500, y: 300, rx: 100, ry: 120, label: 'Khuôn mặt' }, BIG: { x: 500, y: 500, rx: 600, ry: 600, label: 'Cả phòng' } } },
    B: { title: 'Bản đồ cũ của thành phố rất rất rất rất dài', kind: 'image', regions: {} } };
  const env = { tech, assets, mainKey: 'A' };
  const cam = (a, b) => [{ at: { rel: 0 }, cx: 500, cy: 500, zoom: a }, { at: { rel: 1 }, cx: 500, cy: 300, zoom: b }];
  assert.equal(shotSentence({ technique: 'CAM-01', slots: { image: { asset: 'A' } }, params: { camera: cam(0.5, 1.4) } }, env), 'Zoom vào khuôn mặt');
  assert.equal(shotSentence({ technique: 'CAM-05', slots: { image: { asset: 'A' } }, params: { camera: cam(0.5, 1.4) } }, env), 'Zoom kèm dịch tới khuôn mặt');
  assert.equal(shotSentence({ technique: 'CAM-05', slots: { image: { asset: 'A' } }, params: { camera: cam(1.4, 0.5) } }, env), 'Zoom kèm dịch trên cả bức tranh', 'the camera goes out: no detail');
  assert.equal(shotSentence({ technique: 'CAM-01', slots: { image: { asset: 'A', region: 'BIG' } }, params: {} }, env), 'Zoom vào cả phòng', 'the region of the slot wins');
  assert.equal(shotSentence({ technique: 'CAM-03', slots: { image: { asset: 'B' } }, params: {} }, env), 'Kéo ra, thấy cả bức tranh');
  assert.equal(shotSentence({ technique: 'STATIC-01', slots: { image: { asset: 'B' } } }, env), 'Giữ yên ảnh “Bản đồ cũ của thành phố rất r…”');
  assert.equal(shotSentence({ technique: 'CAM-06', slots: { image: { asset: 'A' } } }, env), 'Giữ yên cả bức tranh, hiện nhãn');
});

test('a region is named by its label: Vietnamese as it is, any other word in quotes, an id-looking label as "một chi tiết"', () => {
  const a = { regions: { A: { label: 'Khuôn mặt' }, B: { label: 'Joined hands' }, C: { label: 'HEAD_2' }, D: {}, E: { label: 'R1' } } };
  assert.equal(regionWords(a, 'A'), 'khuôn mặt');
  assert.equal(regionWords(a, 'B'), '“Joined hands”');
  assert.equal(regionWords(a, 'C'), 'một chi tiết của tranh');
  assert.equal(regionWords(a, 'D'), 'một chi tiết của tranh');
  assert.equal(regionWords(a, 'E'), 'một chi tiết của tranh');
  assert.equal(regionWords(a, 'none'), 'một chi tiết của tranh');
});

test('the region the camera ends on: the smallest that holds the centre; none when the camera goes out or the region has no size', () => {
  const asset = { regions: { SMALL: { x: 10, y: 10, rx: 20, ry: 20 }, BIG: { x: 10, y: 10, rx: 200, ry: 200 }, POINT: { x: 10, y: 10 } } };
  const keys = (z0, z1) => ({ params: { camera: [{ at: { rel: 0 }, cx: 0, cy: 0, zoom: z0 }, { at: { rel: 1 }, cx: 10, cy: 10, zoom: z1 }] } });
  assert.equal(cameraFocus(keys(1, 2), asset), 'SMALL');
  assert.equal(cameraFocus(keys(2, 1), asset), null);
  assert.equal(cameraFocus({ params: {} }, asset), null);
  assert.equal(cameraFocus(keys(1, 2), { regions: { POINT: { x: 10, y: 10 } } }), null);
});

test('overlays: a short phrase each, the same one counted, more than three folded', () => {
  const env = { tech };
  const o = (t) => ({ technique: t });
  assert.deepEqual(overlayPhrases({ overlays: [o('HI-01'), o('HI-01'), o('X-ANN-01')] }, env), ['2 vòng sáng', 'nhãn chi tiết']);
  assert.deepEqual(overlayPhrases({ overlays: [o('ZZ-1')] }, env), []);
  assert.deepEqual(overlayPhrases({ overlays: [o('TR-01')] }, env), ['hòa mờ'], 'no phrase: the lower-case Vietnamese name');
  const s = shotSentence({ technique: 'CAM-01', overlays: [o('HI-01'), o('AN-01'), o('AN-02'), o('X-ANN-01'), o('KEY-01')] }, { tech, assets: {} });
  assert.equal(s, 'Zoom vào bức tranh · vòng sáng · khoanh tròn · viền quanh · và 2 lớp khác');
});

test('the explainers: a map with a route, places, a timeline, a tree, two states', () => {
  const env = { tech, assets: {} };
  const map = (params) => shotSentence({ technique: 'MAP-01', params }, env);
  assert.equal(map({ places: [{ id: 'bru', name: 'Bruges' }, { id: 'luc', name: 'Lucca' }], route: [{ from: 'bru', to: 'luc' }] }), 'Bản đồ: Bruges tới Lucca');
  assert.equal(map({ places: [{ id: 'a', name: 'Bruges' }] }), 'Bản đồ: Bruges');
  assert.equal(map({ places: [{ id: 'a', name: 'Bruges' }, { id: 'b', name: 'Ghent' }] }), 'Bản đồ: Bruges và Ghent');
  assert.equal(map({ places: [{ id: 'a', name: 'A1' }, { id: 'b', name: 'B2' }, { id: 'c', name: 'C3' }, { id: 'd', name: 'D4' }] }), 'Bản đồ: A1, B2 và 2 nơi khác');
  assert.equal(map({}), 'Bản đồ');
  assert.equal(shotSentence({ technique: 'STATIC-06', params: { from_label: 'Bruges', to_label: 'Lucca' } }, env), 'Bản đồ và tuyến: Bruges tới Lucca');
  assert.equal(shotSentence({ technique: 'TIME-01', params: { items: [{}, {}, {}, {}, {}, {}] } }, env), 'Trục thời gian: 6 mốc');
  assert.equal(shotSentence({ technique: 'TREE-01', params: { nodes: [{}, {}, {}] } }, env), 'Sơ đồ quan hệ: 3 người');
  assert.equal(shotSentence({ technique: 'STATE-01', params: { label_a: 'Màu', label_b: 'Hồng ngoại' } }, env), 'Một tranh, hai trạng thái: Màu và Hồng ngoại');
  assert.equal(shotSentence({ technique: 'TIME-01', params: {} }, env), 'Trục thời gian');
});

test('a clip, text cards and a long sentence', () => {
  const assets = { V: { kind: 'video', title: 'Vịnh Oslo', duration: 6.2 }, P: { kind: 'image', title: 'Bức tranh', regions: {} } };
  assert.equal(shotSentence({ technique: 'FOOT-01', slots: { footage: { asset: 'V' } } }, { tech, assets, mainKey: 'P' }), 'Footage chất liệu và bảng màu: clip “Vịnh Oslo”, 6 giây');
  assert.equal(shotSentence({ technique: 'X-CARD-01', params: { title: 'MERCHANT CITY' } }, { tech }), 'Thẻ chương: Merchant city');
  assert.equal(shotSentence({ technique: 'X-CARD-01', params: { title: 'c03' } }, { tech }), 'Thẻ chương: c03', 'only an all-capitals id-looking title is dropped');
  assert.equal(shotSentence({ technique: 'X-CARD-01', params: { title: 'MIRROR_2' } }, { tech }), 'Thẻ chương');
  const long = shotSentence({ technique: 'CAM-01', slots: {}, overlays: Array.from({ length: 3 }, () => ({ technique: 'KEY-01' })) }, { tech });
  assert.ok(long.length <= 96);
});

test('the main painting: the one with the painting\'s title, else the one the shots use most', () => {
  const sb = { assets: { A: { title: 'Other', kind: 'image' }, B: { title: 'The Painting', kind: 'image' }, V: { title: 'The Painting', kind: 'video' } },
    shots: [{ slots: { image: { asset: 'A' } } }, { slots: { image: { asset: 'A' } } }, { slots: { image: { asset: 'B' } } }] };
  assert.equal(mainAssetKey(sb, 'the painting'), 'B', 'by the title, an image only');
  assert.equal(mainAssetKey(sb, ''), 'A', 'by use');
  assert.equal(mainAssetKey({ assets: {}, shots: [] }, 'x'), null);
});
