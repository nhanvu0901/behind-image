// KEY-01, NUM-01 and DOC-01 on the page: their lists (labels, rows, lit lines) are edited as rows, built from the REAL registry entries.
// The generic row editor and its logic are tested in items.test.mjs with MAP-01; this file proves that the three new entries fit it.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildFields, validateValue, defaultParams, newItem, addItem, removeItem, setItemField, itemsProblem, fieldProblem, canAddItem, canRemoveItem } from '../../bti/editor/static/js/formgen.js';
import { storyboardIssueText, TEMPLATE_CODES } from '../../bti/editor/static/js/sbissues.js';
import { valueLabel, itemFieldLabel, ITEM_FIELD } from '../../bti/editor/static/js/labels.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url), 'utf8')).techniques;
const T = (id) => REG.find((t) => t.id === id);
const KEY = T('KEY-01'), NUM = T('NUM-01'), DOC = T('DOC-01');
const P = (t, n) => t.params.find((p) => p.name === n);
const LABELS = P(KEY, 'labels'), ROWS = P(NUM, 'rows'), LIT = P(DOC, 'lit');
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('the registry has the three entries after MAP-01, each with a list that the page edits as rows', () => {
  const ids = REG.map((t) => t.id);
  assert.deepEqual(ids.slice(-4), ['MAP-01', 'KEY-01', 'NUM-01', 'DOC-01']);
  for (const [t, name, fields] of [[KEY, 'labels', ['text', 'ref', 'side', 'at', 'style']], [NUM, 'rows', ['label', 'value', 'units', 'count', 'at']], [DOC, 'lit', ['ref', 'box', 'at', 'hold_s']]]) {
    const d = P(t, name);
    assert.equal(d.type, 'items');
    assert.deepEqual(d.fields.map((f) => f.name), fields, t.id);
    const f = buildFields(t.params).find((x) => x.name === name);
    assert.equal(f.widget, 'items', t.id);
    assert.equal(f.problem, null, t.id + ': the default data has no problem');
    assert.ok(d.min_items >= 1 && d.max_items >= d.min_items, t.id);
  }
  assert.equal(LABELS.max_items, 12);
  assert.equal(ROWS.max_items, 4);
  assert.equal(LIT.max_items, 6);
});

test('every field of every row has a Vietnamese name and every choice a Vietnamese word', () => {
  for (const [t, name] of [[KEY, 'labels'], [NUM, 'rows'], [DOC, 'lit']]) {
    for (const f of P(t, name).fields) {
      assert.notEqual(itemFieldLabel(f.name), f.name, `${t.id}.${name}.${f.name} shows its raw name`);
      assert.match(itemFieldLabel(f.name), VI, `${t.id}.${name}.${f.name}`);
      if (f.type === 'enum') for (const v of f.values) {
        assert.notEqual(valueLabel(v, f.name), v, `${t.id}.${name}.${f.name}=${v}`);
        assert.doesNotMatch(valueLabel(v, f.name), /_/, v);
      }
      if (f.type === 'string' && f.pattern) assert.match(f.pattern_hint, VI, `${t.id}.${name}.${f.name} has a Vietnamese hint`);
    }
  }
  for (const [t, p] of [[KEY, 'leader'], [NUM, 'align']]) for (const v of P(t, p).values) assert.notEqual(valueLabel(v, p), v, `${t.id}.${p}=${v}`);
  assert.equal(valueLabel('italic'), 'Nghiêng');
  assert.equal(valueLabel('caps'), 'Chữ hoa nhỏ');
  assert.equal(valueLabel('ne'), 'Đông bắc', 'the sides are the map block\'s words');
  assert.ok(ITEM_FIELD.hold_s && ITEM_FIELD.count && ITEM_FIELD.box);
});

test('a field name that two lists use in two ways has one word per list (join of the base techniques and the overlays)', () => {
  assert.equal(itemFieldLabel('side', 'items'), 'Phía', 'TIME-01: above or below the axis');
  assert.equal(itemFieldLabel('side', 'labels'), 'Phía đặt chữ', 'KEY-01: the side of the detail');
  assert.equal(itemFieldLabel('label', 'items'), 'Chữ ghi', 'TIME-01: the text of the event');
  assert.equal(itemFieldLabel('label', 'edges'), 'Chữ ghi', 'TREE-01: the text on a connector');
  assert.equal(itemFieldLabel('label', 'rows'), 'Nhãn nhỏ', 'NUM-01: the small caption of a figure');
  assert.equal(itemFieldLabel('side'), 'Phía', 'without a list the general word stays');
  assert.equal(itemFieldLabel('nothing_like_it', 'rows'), 'nothing_like_it');
});

test('a new row has every declared field and the lists keep their limits', () => {
  const k = newItem(LABELS);
  assert.deepEqual(Object.keys(k), ['text', 'ref', 'side', 'at', 'style']);
  assert.equal(k.side, 'auto');
  assert.equal(k.style, 'italic');
  assert.equal(k.at, 1.0);
  const r = newItem(ROWS);
  assert.deepEqual(Object.keys(r), ['label', 'value', 'units', 'count', 'at']);
  assert.equal(r.count, 0);
  const l = newItem(LIT);
  assert.deepEqual(Object.keys(l), ['ref', 'box', 'at', 'hold_s']);
  assert.equal(l.hold_s, 0);
  let rows = defaultParams(NUM.params).rows;
  assert.equal(rows.length, 2);
  rows = addItem(ROWS, addItem(ROWS, rows));
  assert.equal(rows.length, 4);
  assert.equal(canAddItem(ROWS, rows), false, 'one to four rows');
  assert.equal(addItem(ROWS, rows).length, 4);
  assert.equal(canRemoveItem(ROWS, [rows[0]]), false, 'the last row stays');
  assert.equal(removeItem(ROWS, [rows[0]], 0).length, 1);
  let labels = defaultParams(KEY.params).labels;
  assert.equal(labels.length, 5);
  for (let i = 0; i < 12; i++) labels = addItem(LABELS, labels);
  assert.equal(labels.length, 12);
});

test('typing into the fields gives the typed value of the field', () => {
  const labels = defaultParams(KEY.params).labels;
  assert.equal(setItemField(LABELS, labels, 0, 'text', 'The candle')[0].text, 'The candle');
  assert.equal(setItemField(LABELS, labels, 1, 'side', 'nw')[1].side, 'nw');
  assert.equal(setItemField(LABELS, labels, 1, 'style', 'caps')[1].style, 'caps');
  assert.equal(setItemField(LABELS, labels, 2, 'ref', 'MIRROR')[2].ref, 'MIRROR');
  assert.deepEqual(setItemField(LABELS, labels, 2, 'ref', '1200, 800')[2].ref, [1200, 800], 'a pixel point of the picture');
  assert.equal(setItemField(LABELS, labels, 0, 'at', '99999')[0].at, 600, 'held to the registry maximum');
  const word = { w: 8, off: 0, text: 'candle' };
  assert.deepEqual(setItemField(LABELS, labels, 0, 'at', word)[0].at, word, 'a word anchor is kept');
  const rows = defaultParams(NUM.params).rows;
  assert.equal(setItemField(ROWS, rows, 1, 'value', '3,500')[1].value, '3,500');
  assert.equal(setItemField(ROWS, rows, 1, 'count', '25')[1].count, 25);
  assert.equal(setItemField(ROWS, rows, 1, 'count', '500')[1].count, 60);
  const lit = defaultParams(DOC.params).lit;
  assert.equal(setItemField(LIT, lit, 0, 'box', '1750, 1240, 2690, 1540')[0].box, '1750, 1240, 2690, 1540');
  assert.equal(setItemField(LIT, lit, 0, 'hold_s', '-3')[0].hold_s, 0);
  assert.equal(setItemField(LIT, lit, 0, 'ref', '')[0].ref, '', 'a blank ref stays blank: the engine treats it as no region');
});

test('the form says in Vietnamese which row and which field is wrong', () => {
  const labels = defaultParams(KEY.params).labels;
  assert.equal(itemsProblem(LABELS, labels), null);
  assert.match(itemsProblem(LABELS, setItemField(LABELS, labels, 1, 'text', '')), /^mục thứ 2, ô "text": bắt buộc nhập$/);
  assert.match(itemsProblem(LABELS, setItemField(LABELS, labels, 0, 'ref', '')), /mục thứ 1 \(One candle, lit\), ô "ref": bắt buộc nhập/);
  assert.match(itemsProblem(LABELS, setItemField(LABELS, labels, 0, 'text', 'x'.repeat(61))), /ô "text": Gõ một dòng, 1 đến 60 ký tự/);
  assert.match(itemsProblem(LABELS, []), /cần ít nhất 1 mục/);
  const rows = defaultParams(NUM.params).rows;
  assert.equal(itemsProblem(ROWS, rows), null);
  assert.match(itemsProblem(ROWS, setItemField(ROWS, rows, 1, 'value', '')), /mục thứ 2 \(This gown\), ô "value": bắt buộc nhập/);
  assert.match(itemsProblem(ROWS, setItemField(ROWS, rows, 0, 'units', 'x'.repeat(25))), /ô "units": Gõ một dòng, tối đa 24 ký tự/);
  assert.match(itemsProblem(ROWS, [...rows, ...rows, ...rows]), /nhiều nhất 4 mục/);
  const lit = defaultParams(DOC.params).lit;
  assert.equal(itemsProblem(LIT, lit), null);
  assert.equal(itemsProblem(LIT, setItemField(LIT, lit, 0, 'ref', '')), null, 'a line may name a box instead of a region: the engine says if it names neither');
  assert.match(itemsProblem(LIT, setItemField(LIT, lit, 0, 'box', '1, 2, 3')), /ô "box": Gõ bốn số theo điểm ảnh của ảnh gốc/);
  assert.equal(itemsProblem(LIT, setItemField(LIT, lit, 0, 'box', '1750, 1240, 2690, 1540')), null);
  assert.equal(validateValue(LIT, setItemField(LIT, lit, 0, 'box', '1, 2, 3')), itemsProblem(LIT, setItemField(LIT, lit, 0, 'box', '1, 2, 3')));
  const at = LIT.fields.find((f) => f.name === 'at');
  assert.equal(fieldProblem(at, { w: 3, off: 0.2, text: 'x' }), null);
  assert.equal(fieldProblem(at, -1), 'nhỏ hơn 0');
});

test('the new codes of the engine have Vietnamese sentences that name the line', () => {
  const args = { param: 'lit', technique: 'DOC-01', index: 1, base: 'X-CARD-01' };
  for (const code of ['overlay_needs_camera', 'doc_lit_no_target', 'doc_bad_box']) {
    assert.ok(TEMPLATE_CODES.includes(code), code + ' has no template');
    for (const a of [args, {}, undefined]) {
      const t = storyboardIssueText({ level: 'error', code, path: 'shots[0].overlays[0].params.lit', args: a, message: 'raw english message' });
      assert.match(t.text, VI, code);
      assert.ok(!t.generic, code);
      assert.doesNotMatch(t.text, /raw english|undefined|null|NaN/, code);
    }
  }
  assert.match(storyboardIssueText({ level: 'error', code: 'doc_lit_no_target', path: 'x', args, message: 'x' }).text, /Dòng sáng thứ 2/);
  assert.match(storyboardIssueText({ level: 'error', code: 'overlay_needs_camera', path: 'x', args, message: 'x' }).text, /DOC-01.*X-CARD-01/);
  const short = storyboardIssueText({ level: 'error', code: 'element_too_short', path: 'x', args: { technique: 'NUM-01', min: 3, got: 2 }, message: 'x' }).text;
  assert.match(short, /phần con số cần dài ít nhất 3 giây/);
});

test('the three values of `leader` have their own Vietnamese words and `auto` is the default', () => {
  const leader = P(KEY, 'leader');
  assert.deepEqual(leader.values, ['none', 'hairline', 'auto']);
  assert.equal(leader.default, 'auto');
  assert.equal(defaultParams(KEY.params).leader, 'auto');
  const words = leader.values.map((v) => valueLabel(v, 'leader'));
  assert.equal(new Set(words).size, 3, 'three different words');
  for (const w of words) assert.match(w, VI);
  assert.match(valueLabel('auto', 'leader'), /bị đẩy xa chi tiết/);
  assert.equal(valueLabel('auto', 'side'), 'Tự chọn', 'the same word elsewhere keeps its meaning');
  assert.match(KEY.usage_rule, /at most five labels on screen at a time/);
  assert.match(KEY.usage_rule, /two shots/);
});
