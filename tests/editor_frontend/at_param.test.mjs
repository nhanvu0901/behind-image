// The parameter type `at` (one moment: seconds, or a word of the narration) and the warning of MAP-01 for a view that is too close.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildFields, validateValue, coerce, WIDGETS, defaultParams } from '../../bti/editor/static/js/formgen.js';
import { storyboardIssueText, TEMPLATE_CODES } from '../../bti/editor/static/js/sbissues.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url), 'utf8')).techniques;
const MAP = REG.find((t) => t.id === 'MAP-01');
const REGION_AT = MAP.params.find((p) => p.name === 'region_at');

test('region_at is a parameter of type at, and the form makes an at widget of it', () => {
  assert.equal(REGION_AT.type, 'at');
  assert.equal(WIDGETS.at, 'at');
  const f = buildFields(MAP.params).find((x) => x.name === 'region_at');
  assert.equal(f.widget, 'at');
  assert.equal(f.value, 0.6);
  assert.equal(f.problem, null);
  assert.equal(defaultParams(MAP.params).region_at, 0.6);
});

test('focus_s (TIME-01) and reading_at (DOC-01) are also parameters of type at, with their old defaults and range', () => {
  for (const [id, name, def] of [['TIME-01', 'focus_s', 6], ['DOC-01', 'reading_at', 2.4]]) {
    const t = REG.find((x) => x.id === id);
    const d = t.params.find((p) => p.name === name);
    assert.equal(d.type, 'at', id);
    assert.equal(d.min, 0, id);
    assert.equal(d.max, 600, id);
    const f = buildFields(t.params).find((x) => x.name === name);
    assert.equal(f.widget, 'at', id);
    assert.equal(f.value, def, id);
    assert.equal(f.problem, null, id);
    assert.equal(defaultParams(t.params)[name], def, id);
    assert.equal(validateValue(d, { w: 4, off: 0, text: 'x' }), null, id);
    assert.equal(validateValue(d, 601), 'lớn hơn 600', id);
  }
});

test('a moment is seconds held to the registry range, or a word anchor; the sentence is Vietnamese', () => {
  for (const ok of [0, 0.6, 600, { w: 4, off: 0, text: 'x' }, { t: 3 }, { rel: 0.5 }]) assert.equal(validateValue(REGION_AT, ok), null, JSON.stringify(ok));
  assert.equal(validateValue(REGION_AT, -1), 'nhỏ hơn 0');
  assert.equal(validateValue(REGION_AT, 601), 'lớn hơn 600');
  assert.equal(validateValue(REGION_AT, { x: 1 }), 'mốc thời gian chưa đúng');
  assert.equal(validateValue(REGION_AT, 'soon'), 'không phải số');
  assert.equal(validateValue(REGION_AT, null), null);
});

test('typing into an at parameter gives a number held to the range, or keeps a word anchor', () => {
  assert.equal(coerce(REGION_AT, '2.5'), 2.5);
  assert.equal(coerce(REGION_AT, '-4'), 0);
  assert.equal(coerce(REGION_AT, '9999'), 600);
  assert.equal(coerce(REGION_AT, ''), REGION_AT.default);
  const word = { w: 12, off: 0, text: 'Bruges' };
  assert.deepEqual(coerce(REGION_AT, word), word);
});

test('the new codes have a sentence: a moment that is neither seconds nor a word, and a view that is too close', () => {
  for (const code of ['param_bad_at', 'map_view_coarse']) assert.ok(TEMPLATE_CODES.includes(code), code);
  const bad = storyboardIssueText({ level: 'error', code: 'param_bad_at', path: 'shots[0].params.region_at', args: { param: 'region_at', technique: 'MAP-01' }, message: 'x' }).text;
  assert.match(bad, /^Shot thứ 1: Tham số "region_at": thời điểm phải là số giây hoặc gắn vào một từ của lời đọc\.$/);
  const coarse = storyboardIssueText({ level: 'warn', code: 'map_view_coarse', path: 'shots[2].params.view_end_width_km', args: { param: 'view_end_width_km', technique: 'MAP-01', width_km: 60 }, message: 'x' });
  assert.equal(coarse.text, 'Shot thứ 3: Bản đồ này quá gần: đường bờ biển chỉ còn nét thô. Với một địa điểm trong thành phố, hãy dùng ảnh bản đồ đường phố ở bước Chọn hình thay cho bản đồ atlas.');
  assert.ok(!coarse.generic);
});
