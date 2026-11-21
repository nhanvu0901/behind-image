// The logic of the selector "Kiểu mở đầu và mốc chương" (step 5) and of its line in step 6: bti/editor/static/js/identitylogic.js.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { selectorView, canChoose, chooseBody, skippedLines, resultLine, exportRow, styleLabel, OLD_LOOK } from '../../bti/editor/static/js/identitylogic.js';
import { IDENTITY_LABELS as L } from '../../bti/editor/static/js/labels.js';

const OPTIONS = [{ id: 'raking', label: 'Vệt sáng quét' }, { id: 'dim', label: 'Tối lại, hiện tên' }];
const NONE = { style: null, default: 'raking', options: OPTIONS };
const RAKING = { style: 'raking', default: 'raking', options: OPTIONS };
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const SHOTS = [{ id: 's0001' }, { id: 's0002' }, { id: 's0003' }, { id: 's0015' }];

test('while nothing was chosen the dropdown shows "Kiểu cũ" (not selectable) and the two styles with the route\'s own words', () => {
  const v = selectorView(NONE);
  assert.equal(v.hidden, false);
  assert.equal(v.value, OLD_LOOK);
  assert.deepEqual(v.options.map((o) => o.text), ['Kiểu cũ', 'Vệt sáng quét', 'Tối lại, hiện tên']);
  assert.deepEqual(v.options.map((o) => o.disabled), [true, false, false]);
  assert.deepEqual(v.options.map((o) => o.value), ['', 'raking', 'dim']);
  assert.equal(v.note, L.oldNote);
  assert.match(v.note, /kiểu cũ/i);
});

test('once a style is chosen the old look is no longer an entry and the dropdown shows the chosen one', () => {
  const v = selectorView(RAKING);
  assert.deepEqual(v.options.map((o) => o.value), ['raking', 'dim']);
  assert.equal(v.value, 'raking');
  assert.equal(v.note, '');
  assert.equal(selectorView({ ...RAKING, style: 'dim' }).value, 'dim');
});

test('a style the route does not list is shown as "Kiểu cũ", and no answer or no options hides the selector', () => {
  assert.equal(selectorView({ ...RAKING, style: 'sepia' }).value, OLD_LOOK);
  assert.equal(selectorView(null).hidden, true);
  assert.equal(selectorView({ style: null, default: null, options: [] }).hidden, true);
  assert.equal(selectorView(undefined).hidden, true);
});

test('while a choice runs the dropdown is disabled', () => {
  assert.equal(selectorView(RAKING, { busy: true }).disabled, true);
  assert.equal(selectorView(RAKING).disabled, false);
});

test('canChoose: only another listed style, and never while a choice runs', () => {
  assert.equal(canChoose(NONE, 'raking'), true);
  assert.equal(canChoose(RAKING, 'dim'), true);
  assert.equal(canChoose(RAKING, 'raking'), false, 'the style already chosen');
  assert.equal(canChoose(RAKING, 'sepia'), false, 'not in the list');
  assert.equal(canChoose(RAKING, OLD_LOOK), false, 'the old look cannot be chosen back');
  assert.equal(canChoose(RAKING, 'dim', { busy: true }), false);
  assert.equal(canChoose(null, 'dim'), false);
});

test('the request body carries the style and the revision the page holds', () => {
  assert.deepEqual(chooseBody('dim', 'abc123'), { style: 'dim', base_rev: 'abc123' });
});

test('the skipped items are told in plain Vietnamese by shot number, never by id', () => {
  const lines = skippedLines([
    { shot: 's0015', reason: 'locked', what: 'mark' },
    { shot: null, reason: 'no_title_slot', what: 'brand' },
    { shot: 's0001', reason: 'no_room', what: 'open' },
    { shot: 's0003', reason: 'too_short', what: 'mark' },
  ], SHOTS);
  assert.equal(lines.length, 4);
  assert.match(lines[0], /^Cảnh 4 \(mốc chương\) đang khóa/);
  assert.match(lines[1], /chưa có thẻ tiêu đề/);
  assert.match(lines[2], /phần mở đầu/);
  assert.match(lines[3], /Cảnh 3 ngắn quá/);
  for (const l of lines) { assert.match(l, VI); assert.doesNotMatch(l, /s00\d\d|_|undefined|null|\[object/); }
});

test('the same sentence is not repeated, an unknown reason and a shot the page does not have still give a Vietnamese sentence', () => {
  const dup = skippedLines([{ shot: 's0015', reason: 'locked', what: 'mark' }, { shot: 's0015', reason: 'locked', what: 'mark' }], SHOTS);
  assert.equal(dup.length, 1);
  const odd = skippedLines([{ shot: 's9999', reason: 'something_new', what: 'elsewhere' }, { shot: 's9999', reason: 'locked', what: 'mark' }], SHOTS);
  assert.equal(odd.length, 2);
  for (const l of odd) { assert.match(l, VI); assert.doesNotMatch(l, /s9999|something_new|elsewhere/); }
  assert.deepEqual(skippedLines(null, SHOTS), []);
  assert.deepEqual(skippedLines([], SHOTS), []);
});

test('every reason code the applier can report has a sentence in the labels', () => {
  const src = fs.readFileSync(new URL('../../bti/identity/apply.py', import.meta.url), 'utf8');
  const block = /REASONS = \{([\s\S]*?)\n\}/.exec(src)[1];
  const codes = [...block.matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => m[1]);
  assert.ok(codes.length >= 7, codes.join());
  for (const c of codes) {
    assert.equal(typeof L.skip[c], 'function', `no sentence for the reason ${c}`);
    for (const w of ['open', 'label', 'brand', 'mark']) assert.match(L.skip[c](L.what[w], 3), VI, `${c}/${w}`);
  }
});

test('the sentence after a choice says the style by its words and how many places changed', () => {
  assert.equal(resultLine(RAKING, { style: 'raking', changed: ['s1', 's2', 's3'] }), 'Đã đổi sang kiểu "Vệt sáng quét" (3 chỗ).');
  assert.equal(resultLine(RAKING, { style: 'dim', changed: [] }), 'Video đã ở kiểu "Tối lại, hiện tên", không có gì phải đổi.');
  assert.equal(styleLabel(RAKING, 'dim'), 'Tối lại, hiện tên');
  assert.equal(styleLabel(RAKING, 'zzz'), 'zzz');
});

test('step 6 says which style the video will be exported with', () => {
  assert.deepEqual(exportRow(RAKING), ['Kiểu mở đầu và mốc chương', 'Vệt sáng quét']);
  assert.deepEqual(exportRow({ ...RAKING, style: 'dim' }), ['Kiểu mở đầu và mốc chương', 'Tối lại, hiện tên']);
  const old = exportRow(NONE);
  assert.equal(old[0], 'Kiểu mở đầu và mốc chương');
  assert.match(old[1], /^Kiểu cũ/);
  assert.equal(exportRow(null), null);
  assert.equal(exportRow({ style: null, default: null, options: [] }), null);
});

test('every word of the block is Vietnamese (the owner reads it)', () => {
  const flat = [];
  const walk = (v, p) => { if (typeof v === 'string') flat.push([p, v]); else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) walk(x, `${p}.${k}`); else if (typeof v === 'function') flat.push([p, String(v(L.what.mark, 2, 3))]); };
  walk(L, 'IDENTITY_LABELS');
  assert.ok(flat.length > 20);
  for (const [p, s] of flat) {
    if (/^IDENTITY_LABELS\.(loading|close)$/.test(p)) continue;
    assert.match(s, VI, `${p}: ${s}`);
    assert.doesNotMatch(s, /undefined|\[object|NaN/, `${p}: ${s}`);
  }
});

import { issueText } from '../../bti/editor/static/js/errmsg.js';
test('a too-short element of the identity is told in plain words: what it is, how many seconds it needs, how many it has', () => {
  const t = (technique, path, args) => issueText({ level: 'error', code: 'element_too_short', path, args: { technique, min: 1.5, got: 0.8, ...args }, message: 'x' }).text;
  assert.match(t('ID-MARK-01', 'shots[3]'), /^Shot .*: mốc chương cần dài ít nhất 1,5 giây \(hiện chỉ 0,8 giây\)/i);
  assert.match(t('ID-BRAND-02', 'shots[3]'), /đoạn hiện tên kênh cần dài ít nhất 1,5 giây/);
  assert.match(t('ID-OPEN-01', 'shots[0].overlays[1]'), /lớp phủ.*: phần mở đầu cần dài/i);
  assert.match(t('ID-LABEL-01', 'shots[0].overlays[2]'), /nhãn tên tác phẩm cần dài/);
  for (const technique of ['ID-MARK-02', 'ID-OPEN-02', 'ID-BRAND-01', 'ID-LABEL-01']) assert.match(t(technique, 'shots[1]'), VI);
  const bare = issueText({ level: 'error', code: 'element_too_short', path: '', args: {}, message: 'x' });
  assert.ok(!bare.generic); assert.match(bare.text, VI); assert.doesNotMatch(bare.text, /undefined|NaN|null/);
});
