import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeDoc, deepEqual } from '../../bti/editor/static/js/merge.js';

const beat = (id, text) => ({ id, text, facts: [], show: [], note: '', locked: false });
const chap = (id, ...beats) => ({ id, title: id.toUpperCase(), beats });
const doc = (...chapters) => ({ source: { kind: 'model', created_at: 't0' }, counters: { beat: 20 }, chapters });
const OPTS = { collections: ['chapters'] };
const base = () => doc(chap('c01', beat('b1', 'one'), beat('b2', 'two')), chap('c03', beat('b5', 'five')), chap('c05', beat('b8', 'eight')));

test('server unchanged: the owner\'s typing survives (U1-005 A: job cancelled)', () => {
  const mine = base(); mine.chapters[0].beats[0].text = 'KEEPME one';
  const r = mergeDoc(base(), mine, base(), OPTS);
  assert.deepEqual(r.conflicts, []);
  assert.equal(r.value.chapters[0].beats[0].text, 'KEEPME one');
});
test('a job rewrote c03, the owner typed in c05: both are kept (U1-005 B)', () => {
  const mine = base(); mine.chapters[2].beats[0].text = 'KEEPME eight';
  const theirs = base(); theirs.chapters[1] = chap('c03', beat('b21', 'new five'), beat('b22', 'new six')); theirs.counters.beat = 22; theirs.source.created_at = 't1';
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.deepEqual(r.conflicts, []);
  assert.equal(r.value.chapters[2].beats[0].text, 'KEEPME eight');
  assert.deepEqual(r.value.chapters[1].beats.map((b) => b.id), ['b21', 'b22']);
  assert.equal(r.value.counters.beat, 22);
  assert.equal(r.value.source.created_at, 't1');
});
test('the owner and the job both changed c03: a conflict, mine kept by default, theirs on request', () => {
  const mine = base(); mine.chapters[1].beats[0].text = 'mine five';
  const theirs = base(); theirs.chapters[1] = chap('c03', beat('b21', 'job five'));
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.equal(r.conflicts.length, 1);
  assert.equal(r.conflicts[0].key, 'chapters'); assert.equal(r.conflicts[0].id, 'c03');
  assert.equal(r.value.chapters[1].beats[0].text, 'mine five');
  const r2 = mergeDoc(base(), mine, theirs, OPTS, { 'chapters:c03': 'theirs' });
  assert.equal(r2.value.chapters[1].beats[0].text, 'job five');
  assert.deepEqual(r2.value.chapters.map((c) => c.id), ['c01', 'c03', 'c05']);
});
test('two edits in different beats of one chapter merge without a conflict (another tab saved first)', () => {
  const mine = base(); mine.chapters[0].beats[0].text = 'mine one';
  const theirs = base(); theirs.chapters[0].beats[1].text = 'their two';
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.deepEqual(r.conflicts, []);
  assert.deepEqual(r.value.chapters[0].beats.map((b) => b.text), ['mine one', 'their two']);
});
test('the same beat edited on both sides: conflict on that chapter', () => {
  const mine = base(); mine.chapters[0].beats[0].text = 'mine one';
  const theirs = base(); theirs.chapters[0].beats[0].text = 'their one';
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.equal(r.conflicts.length, 1);
  assert.equal(r.value.chapters[0].beats[0].text, 'mine one');
});
test('a beat added on one side and a beat edited on the other', () => {
  const mine = base(); mine.chapters[0].beats.push(beat('b30', 'added by me'));
  const theirs = base(); theirs.chapters[0].beats[0].text = 'their one';
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.deepEqual(r.conflicts, []);
  assert.deepEqual(r.value.chapters[0].beats.map((b) => b.id), ['b1', 'b2', 'b30']);
  assert.equal(r.value.chapters[0].beats[0].text, 'their one');
});
test('a chapter removed by the server that the owner did not touch goes; one the owner edited is a conflict', () => {
  const theirs = base(); theirs.chapters = theirs.chapters.filter((c) => c.id !== 'c03');
  assert.deepEqual(mergeDoc(base(), base(), theirs, OPTS).value.chapters.map((c) => c.id), ['c01', 'c05']);
  const mine = base(); mine.chapters[1].beats[0].text = 'mine five';
  const r = mergeDoc(base(), mine, theirs, OPTS);
  assert.equal(r.conflicts.length, 1);
  assert.deepEqual(r.value.chapters.map((c) => c.id), ['c01', 'c03', 'c05']);      // the owner's text is not dropped silently
});
test('atomic keys: only mine changed, only theirs changed, both changed', () => {
  const b = { thesis: 'q', target_words: 1500, chapters: [] }, o = { collections: ['chapters'] };
  assert.equal(mergeDoc(b, { ...b, thesis: 'mine' }, b, o).value.thesis, 'mine');
  assert.equal(mergeDoc(b, b, { ...b, thesis: 'theirs' }, o).value.thesis, 'theirs');
  const r = mergeDoc(b, { ...b, thesis: 'mine' }, { ...b, thesis: 'theirs' }, o);
  assert.equal(r.conflicts.length, 1); assert.equal(r.conflicts[0].key, 'thesis'); assert.equal(r.value.thesis, 'mine');
  assert.equal(mergeDoc(b, { ...b, thesis: 'mine' }, { ...b, thesis: 'theirs' }, o, { thesis: 'theirs' }).value.thesis, 'theirs');
  assert.equal(mergeDoc(b, { ...b, thesis: 'same' }, { ...b, thesis: 'same' }, o).conflicts.length, 0);
});
test('chapter order: the side that reordered wins; ids new to the other side are placed after their neighbour', () => {
  const mk = (...ids) => ({ chapters: ids.map((i) => chap(i)) });
  const b = mk('c01', 'c02', 'c03');
  const mine = mk('c03', 'c01', 'c02');
  assert.deepEqual(mergeDoc(b, mine, b, OPTS).value.chapters.map((c) => c.id), ['c03', 'c01', 'c02']);
  assert.deepEqual(mergeDoc(b, b, mk('c02', 'c01', 'c03'), OPTS).value.chapters.map((c) => c.id), ['c02', 'c01', 'c03']);
  assert.deepEqual(mergeDoc(b, mk('c01', 'c02', 'c03', 'c04'), mk('c01', 'c02', 'c03', 'c05'), OPTS).value.chapters.map((c) => c.id), ['c01', 'c02', 'c03', 'c04', 'c05']);
});
test('outline: facts and hook options merge by id', () => {
  const b = { thesis: 't', hook_options: [{ id: 'h1', text: 'a' }], facts: [{ id: 'f01', claim: 'x' }, { id: 'f02', claim: 'y' }], chapters: [] };
  const o = { collections: ['chapters', 'facts', 'hook_options'] };
  const mine = JSON.parse(JSON.stringify(b)); mine.facts[0].claim = 'mine x'; mine.hook_options.push({ id: 'h2', text: 'new' });
  const theirs = JSON.parse(JSON.stringify(b)); theirs.facts[1].claim = 'their y'; theirs.facts.push({ id: 'f03', claim: 'z' });
  const r = mergeDoc(b, mine, theirs, o);
  assert.deepEqual(r.conflicts, []);
  assert.deepEqual(r.value.facts.map((f) => f.claim), ['mine x', 'their y', 'z']);
  assert.equal(r.value.hook_options.length, 2);
});
test('missing sides: no draft = the server\'s version; no server version = the draft', () => {
  assert.deepEqual(mergeDoc(null, null, { a: 1 }, OPTS).value, { a: 1 });
  assert.deepEqual(mergeDoc({ a: 1 }, { a: 2 }, null, OPTS).value, { a: 2 });
});
test('deepEqual ignores key order and undefined', () => {
  assert.ok(deepEqual({ a: 1, b: [1, { c: 2 }] }, { b: [1, { c: 2 }], a: 1, z: undefined }));
  assert.ok(!deepEqual({ a: 1 }, { a: 2 }));
  assert.ok(!deepEqual([1], [1, 2]));
  assert.ok(!deepEqual(null, {}));
});
