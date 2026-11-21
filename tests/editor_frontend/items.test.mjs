// The list-of-records parameter type (`items`): the pure logic of the row editor and the Vietnamese sentences about it.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildFields, validateValue, coerce, defaultParams, newItem, addItem, removeItem, moveItem, setItemField, canAddItem, canRemoveItem, itemsProblem, fieldProblem, parseLonlat, lonlatToText } from '../../bti/editor/static/js/formgen.js';
import { storyboardIssueText, TEMPLATE_CODES } from '../../bti/editor/static/js/sbissues.js';
import { valueLabel } from '../../bti/editor/static/js/labels.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url), 'utf8')).techniques;
const MAP = REG.find((t) => t.id === 'MAP-01');
const PLACES = MAP.params.find((p) => p.name === 'places');
const ROUTE = MAP.params.find((p) => p.name === 'route');
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('the registry declares MAP-01 with items params that carry their fields', () => {
  assert.equal(PLACES.type, 'items');
  assert.deepEqual(PLACES.fields.map((f) => f.name), ['id', 'name', 'lonlat', 'at', 'label_side']);
  assert.equal(PLACES.min_items, 1);
  assert.equal(ROUTE.min_items, 0);
  const f = buildFields(MAP.params).find((x) => x.name === 'places');
  assert.equal(f.widget, 'items');
  assert.equal(f.problem, null, 'the default example has no problem');
  assert.equal(buildFields(MAP.params).find((x) => x.name === 'route').problem, null);
});

test('a new row has every declared field: the default, else something valid for its kind', () => {
  const r = newItem(PLACES);
  assert.deepEqual(Object.keys(r), ['id', 'name', 'lonlat', 'at', 'label_side']);
  assert.equal(r.id, '');
  assert.deepEqual(r.lonlat, [0, 0]);
  assert.equal(r.at, 1.0);
  assert.equal(r.label_side, 'auto');
  const route = newItem(ROUTE);
  assert.equal(route.shape, 'curve');
  assert.equal(route.draw_s, 3.0);
  assert.equal(route.via, '');
});

test('add, remove and move keep the registry limits and never change the list they were given', () => {
  const two = defaultParams(MAP.params).places;
  const snapshot = JSON.stringify(two);
  const three = addItem(PLACES, two);
  assert.equal(three.length, 3);
  assert.equal(JSON.stringify(two), snapshot, 'the original list is untouched');
  assert.equal(three[2].label_side, 'auto');
  const one = removeItem(PLACES, three, 0);
  assert.deepEqual(one.map((p) => p.id), ['lucca', '']);
  const lone = removeItem(PLACES, [two[0]], 0);
  assert.equal(lone.length, 1, 'min_items 1: the last place stays');
  assert.equal(canRemoveItem(PLACES, [two[0]]), false);
  assert.equal(canRemoveItem(ROUTE, [{}]), true, 'a route may be removed down to none');
  let many = [];
  for (let i = 0; i < 14; i++) many = addItem(PLACES, many);
  assert.equal(many.length, PLACES.max_items);
  assert.equal(canAddItem(PLACES, many), false);
  assert.deepEqual(moveItem(two, 0, 1).map((p) => p.id), ['lucca', 'bruges']);
  assert.deepEqual(moveItem(two, 0, -1).map((p) => p.id), ['bruges', 'lucca'], 'the first row cannot go up');
  assert.deepEqual(moveItem(two, 1, 1).map((p) => p.id), ['bruges', 'lucca'], 'the last row cannot go down');
  assert.deepEqual(moveItem(two, 5, 1), two, 'a row that does not exist');
});

test('typing into a field gives the typed value of that field', () => {
  const two = defaultParams(MAP.params).places;
  const a = setItemField(PLACES, two, 1, 'lonlat', '10.5, 43.8');
  assert.deepEqual(a[1].lonlat, [10.5, 43.8]);
  assert.deepEqual(two[1].lonlat, [10.5027, 43.8429], 'the original is untouched');
  assert.deepEqual(setItemField(PLACES, two, 0, 'lonlat', '3.2 51.2')[0].lonlat, [3.2, 51.2], 'a space also separates the pair');
  assert.equal(setItemField(PLACES, two, 0, 'lonlat', 'abc')[0].lonlat, 'abc', 'text that is not a pair stays, and the form shows the problem');
  assert.equal(setItemField(PLACES, two, 0, 'at', '2.5')[0].at, 2.5);
  assert.equal(setItemField(PLACES, two, 0, 'at', '-4')[0].at, 0, 'held to the registry minimum');
  assert.equal(setItemField(PLACES, two, 0, 'at', '9999')[0].at, 600);
  assert.equal(setItemField(PLACES, two, 0, 'at', '')[0].at, 1.0, 'blank goes back to the default');
  const word = { w: 12, off: 0, text: 'Bruges' };
  assert.deepEqual(setItemField(PLACES, two, 0, 'at', word)[0].at, word, 'a word anchor is kept as it is');
  assert.equal(setItemField(PLACES, two, 0, 'label_side', 'ne')[0].label_side, 'ne');
  assert.equal(setItemField(PLACES, two, 0, 'name', 'Brugge')[0].name, 'Brugge');
  assert.equal(setItemField(ROUTE, [newItem(ROUTE)], 0, 'draw_s', '999')[0].draw_s, 60);
  assert.deepEqual(setItemField(PLACES, two, 9, 'name', 'x'), two, 'a row that does not exist');
  assert.deepEqual(setItemField(PLACES, two, 0, 'nope', 'x'), two, 'a field that does not exist');
});

test('a pair of numbers reads and writes as text', () => {
  assert.deepEqual(parseLonlat('3.2247, 51.2093'), [3.2247, 51.2093]);
  assert.deepEqual(parseLonlat('[-10, 5]'), [-10, 5]);
  assert.equal(parseLonlat('3.2247'), null);
  assert.equal(parseLonlat(''), null);
  assert.equal(lonlatToText([3.2247, 51.2093]), '3.2247, 51.2093');
  assert.equal(lonlatToText('x'), '');
});

test('the form says in Vietnamese which row and which field is wrong', () => {
  const two = defaultParams(MAP.params).places;
  assert.equal(itemsProblem(PLACES, two), null);
  const bad = setItemField(PLACES, two, 1, 'lonlat', '10.5, 95');
  assert.equal(itemsProblem(PLACES, bad), 'mục thứ 2 (Lucca), ô "lonlat": vĩ độ phải từ -85 đến 85');
  const noName = setItemField(PLACES, two, 0, 'name', '');
  assert.match(itemsProblem(PLACES, noName), /^mục thứ 1 \(bruges\), ô "name": bắt buộc nhập$/);
  assert.match(itemsProblem(PLACES, setItemField(PLACES, two, 0, 'id', 'a b')), /ô "id": Gõ một mã ngắn/);
  assert.match(itemsProblem(PLACES, []), /cần ít nhất 1 mục/);
  assert.match(itemsProblem(PLACES, 'x'), /danh sách/);
  assert.match(itemsProblem(PLACES, [null]), /mục thứ 1: bị hỏng/);
  assert.equal(validateValue(PLACES, bad), itemsProblem(PLACES, bad), 'validateValue uses the same rule');
  assert.match(itemsProblem(ROUTE, [{ ...newItem(ROUTE), from: 'a', to: 'b', via: '1,2;x' }]), /ô "via": Gõ các điểm uốn/);
  assert.equal(itemsProblem(ROUTE, []), null);
  assert.equal(fieldProblem(PLACES.fields.find((f) => f.name === 'at'), { w: 3, off: 0 }), null, 'a word anchor is a time');
  assert.equal(fieldProblem(PLACES.fields.find((f) => f.name === 'at'), { x: 1 }), 'mốc thời gian chưa đúng');
  assert.equal(coerce(PLACES, 'x').length, 0, 'the whole list coerces to a list');
});

test('every new issue code of the engine has a Vietnamese sentence that names the row and the field', () => {
  const codes = ['param_not_items', 'item_not_object', 'item_unknown_field', 'item_field_missing', 'item_field_bad_type', 'item_field_below_min', 'item_field_above_max',
    'item_field_not_in_values', 'item_field_bad_form', 'item_field_bad_lonlat', 'item_field_bad_at', 'item_anchor_invalid', 'item_anchor_stale', 'map_duplicate_place',
    'map_route_unknown_place', 'map_bad_via', 'map_bad_center', 'map_unknown_iso'];
  const args = { param: 'places', technique: 'MAP-01', index: 1, item: 'Lucca', field: 'lonlat', reason: 'lat', want: 'number', min: 0, max: 600, values: ['auto', 'ne'], hint: 'Gõ một dòng.', id: 'a', place: 'zz', code: 'XX' };
  for (const code of codes) {
    assert.ok(TEMPLATE_CODES.includes(code), code + ' has no template');
    const t = storyboardIssueText({ level: 'error', code, path: 'shots[0].params.places', args, message: 'raw english message' });
    assert.match(t.text, VI, code);
    assert.ok(!t.generic, code);
    assert.doesNotMatch(t.text, /raw english/, code);
  }
  const t = storyboardIssueText({ level: 'error', code: 'item_field_bad_lonlat', path: 'shots[0].params.places', args, message: 'x' }).text;
  assert.match(t, /mục thứ 2 \(Lucca\)/);
  assert.match(t, /ô "lonlat"/);
  assert.match(t, /vĩ độ phải từ -85 đến 85/);
});

test('the words of the choices of MAP-01 are Vietnamese', () => {
  for (const v of ['blue_grey', 'sepia', 'fit', 'manual', 'curve', 'straight', 'dot', 'none', 'auto', 'n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw']) {
    assert.notEqual(valueLabel(v), v, v);
    assert.doesNotMatch(valueLabel(v), /_/, v);
  }
  assert.equal(valueLabel('ne'), 'Đông bắc');
});
