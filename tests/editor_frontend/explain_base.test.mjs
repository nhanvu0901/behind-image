// The lists of TIME-01 (items) and TREE-01 (nodes, edges) as rows of the generated form, with the real registry entries; the words of their choices and
// the Vietnamese sentences of the rules between their params (techniques/explain_base.py).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildFields, defaultParams, newItem, addItem, removeItem, moveItem, setItemField, canAddItem, canRemoveItem, itemsProblem, validateValue } from '../../bti/editor/static/js/formgen.js';
import { storyboardIssueText, TEMPLATE_CODES } from '../../bti/editor/static/js/sbissues.js';
import { valueLabel, itemFieldLabel } from '../../bti/editor/static/js/labels.js';
import { TARGETS } from '../../bti/editor/static/js/camgeom.js';

const REG = JSON.parse(fs.readFileSync(new URL('../../style/gae/techniques.json', import.meta.url), 'utf8')).techniques;
const TIME = REG.find((t) => t.id === 'TIME-01'), TREE = REG.find((t) => t.id === 'TREE-01'), STATE = REG.find((t) => t.id === 'STATE-01');
const ITEMS = TIME.params.find((p) => p.name === 'items');
const NODES = TREE.params.find((p) => p.name === 'nodes'), EDGES = TREE.params.find((p) => p.name === 'edges');
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('the three entries come before the map in the registry and declare their lists as items with fields', () => {
  const ids = REG.map((t) => t.id);
  assert.ok(ids.indexOf('TIME-01') < ids.indexOf('TREE-01') && ids.indexOf('TREE-01') < ids.indexOf('STATE-01') && ids.indexOf('STATE-01') < ids.indexOf('MAP-01'));
  assert.deepEqual(ITEMS.fields.map((f) => f.name), ['date', 'label', 'side', 'at', 'accent']);
  assert.deepEqual(NODES.fields.map((f) => f.name), ['id', 'name', 'sub', 'row', 'col', 'at', 'strong']);
  assert.deepEqual(EDGES.fields.map((f) => f.name), ['from', 'to', 'kind', 'label', 'at']);
  for (const d of [ITEMS, NODES, EDGES]) {
    const f = buildFields([d]).find((x) => x.name === d.name);
    assert.equal(f.widget, 'items');
    assert.equal(f.problem, null, `${d.name}: the default example has no problem`);
  }
  for (const t of [TIME, TREE, STATE]) {
    assert.ok(t.label_vi && VI.test(t.label_vi), `${t.id} has a Vietnamese name`);
    for (const p of buildFields(t.params)) assert.equal(p.problem, null, `${t.id}.${p.name}`);
  }
});

test('the rows of the time axis: a new row is valid, the limits are the registry\'s and a date can be typed', () => {
  const r = newItem(ITEMS);
  assert.deepEqual(Object.keys(r), ['date', 'label', 'side', 'at', 'accent']);
  assert.equal(r.side, 'auto');
  assert.equal(r.accent, false);
  assert.equal(r.at, 1.0);
  const six = defaultParams(TIME.params).items;
  assert.equal(six.length, 6);
  assert.equal(canRemoveItem(ITEMS, [six[0]]), false, 'min_items 1: the last item stays');
  let many = [];
  for (let i = 0; i < 14; i++) many = addItem(ITEMS, many);
  assert.equal(many.length, ITEMS.max_items);
  assert.equal(canAddItem(ITEMS, many), false);
  assert.deepEqual(removeItem(ITEMS, six, 0).map((x) => x.date), [1510, 1520, 1530, 1540, 1550]);
  assert.deepEqual(moveItem(six, 0, 1).map((x) => x.date).slice(0, 2), [1510, 1500]);
  assert.equal(setItemField(ITEMS, six, 0, 'date', '-500')[0].date, -500, 'BC is a negative year');
  assert.equal(setItemField(ITEMS, six, 0, 'date', '99999')[0].date, 3000, 'held to the registry maximum');
  assert.equal(setItemField(ITEMS, six, 0, 'side', 'up')[0].side, 'up');
  assert.equal(setItemField(ITEMS, six, 0, 'accent', true)[0].accent, true);
  assert.deepEqual(setItemField(ITEMS, six, 0, 'at', { w: 12, off: 0, text: 'Bruges' })[0].at, { w: 12, off: 0, text: 'Bruges' }, 'a word anchor is a time');
  assert.equal(itemsProblem(ITEMS, six), null);
  assert.match(itemsProblem(ITEMS, setItemField(ITEMS, six, 1, 'label', 'x'.repeat(49))), /^mục thứ 2 \(.*\), ô "label": Gõ một dòng/);
  assert.match(itemsProblem(ITEMS, setItemField(ITEMS, six, 1, 'label', '')), /ô "label": bắt buộc nhập/);
  assert.match(validateValue(ITEMS, []), /cần ít nhất 1 mục/);
});

test('the rows of the tree: row and col start at -1 (automatic), so a new name is laid out by the technique', () => {
  const n = newItem(NODES);
  assert.equal(n.row, -1);
  assert.equal(n.col, -1);
  assert.equal(n.sub, '');
  assert.equal(n.strong, false);
  const e = newItem(EDGES);
  assert.equal(e.kind, 'link');
  assert.equal(e.label, '');
  const six = defaultParams(TREE.params).nodes, edges = defaultParams(TREE.params).edges;
  assert.equal(six.length, 6);
  assert.equal(edges.length, 5);
  assert.equal(setItemField(NODES, six, 0, 'row', '').at(0).row, -1, 'a blank cell goes back to automatic');
  assert.equal(setItemField(NODES, six, 0, 'row', '2')[0].row, 2);
  assert.equal(setItemField(NODES, six, 0, 'col', '99')[0].col, 11);
  assert.equal(setItemField(NODES, six, 0, 'col', '-7')[0].col, -1, 'nothing below automatic');
  assert.equal(setItemField(EDGES, edges, 2, 'kind', 'descent')[2].kind, 'descent');
  assert.equal(canRemoveItem(NODES, six.slice(0, 2)), false, 'two names at least');
  assert.equal(canRemoveItem(EDGES, [edges[0]]), true, 'a tree may have no connector');
  assert.equal(itemsProblem(NODES, six), null);
  assert.equal(itemsProblem(EDGES, edges), null);
  assert.match(itemsProblem(NODES, setItemField(NODES, six, 0, 'id', 'a b')), /ô "id": Gõ một mã ngắn/);
  assert.match(itemsProblem(EDGES, setItemField(EDGES, edges, 0, 'from', '')), /ô "from": bắt buộc nhập/);
});

test('the words of the rows and of the choices are Vietnamese', () => {
  for (const name of ['date', 'label', 'side', 'at', 'accent', 'sub', 'row', 'col', 'strong', 'kind', 'id', 'name', 'from', 'to']) {
    assert.match(itemFieldLabel(name), VI, name);
  }
  for (const v of ['auto', 'up', 'down', 'descent', 'marriage', 'link', 'a', 'b']) {
    assert.notEqual(valueLabel(v), v, v);
    assert.doesNotMatch(valueLabel(v), /_/, v);
  }
  assert.equal(valueLabel('up'), 'Phía trên');
});

test('every rule between the params has a Vietnamese sentence that names the item', () => {
  const codes = ['time_range_inverted', 'time_date_outside', 'time_crowded', 'tree_duplicate_node', 'tree_edge_unknown_node', 'tree_edge_self', 'tree_marriage_shape',
    'tree_marriage_rows', 'tree_overlap', 'tree_too_big', 'state_holds_count', 'state_hold_range'];
  const args = { param: 'items', technique: 'TIME-01', index: 1, item: 'Costanza is dead', date: 1433, from: 1424, to: 1430, count: 9, id: 'jan', field: 'to', node: 'ghost', a: 'jan', b: 'duke', reason: 'rows', rows: 6, min: 0.2, max: 60 };
  for (const code of codes) {
    assert.ok(TEMPLATE_CODES.includes(code), code + ' has no template');
    const t = storyboardIssueText({ level: 'error', code, path: 'shots[0].params.items', args, message: 'raw english message' });
    assert.match(t.text, VI, code);
    assert.ok(!t.generic, code);
    assert.doesNotMatch(t.text, /raw english/, code);
  }
  assert.match(storyboardIssueText({ level: 'error', code: 'time_date_outside', path: 'shots[0].params.items', args, message: 'x' }).text, /mục thứ 2 \(Costanza is dead\).*1433.*1424.*1430/);
  assert.match(storyboardIssueText({ level: 'error', code: 'tree_edge_unknown_node', path: 'shots[0].params.edges', args, message: 'x' }).text, /"ghost"/);
  assert.match(storyboardIssueText({ level: 'error', code: 'tree_too_big', path: 'shots[0].params.nodes', args, message: 'x' }).text, /6 thế hệ/);
});

test('the camera of STATE-01 looks through the whole frame at slot a', () => {
  assert.deepEqual(TARGETS['STATE-01'], { camera: ['a', 'canvas'] });
  assert.ok(STATE.params.some((p) => p.type === 'camera' && p.name === 'camera'));
  assert.deepEqual(STATE.slots.map((s) => [s.name, s.required]), [['a', true], ['b', true]]);
});
