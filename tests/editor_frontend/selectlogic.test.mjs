// Selecting rows with the usual keys (c4pages): the list of shots (step 5) and the list of narration lines (step 4).
import test from 'node:test';
import assert from 'node:assert/strict';
import { emptySelection, applyClick, selectChapter, pruneSelection, followPlayhead, selectionDiff, stepFocus } from '../../bti/editor/static/js/selectlogic.js';

const ORDER = ['a', 'b', 'c', 'd', 'e', 'f'];

test('a plain click selects one row and makes it the anchor', () => {
  const s = applyClick(emptySelection(), 'c', {}, ORDER);
  assert.deepEqual(s, { ids: ['c'], anchor: 'c', chapter: null });
  assert.deepEqual(applyClick(s, 'e', {}, ORDER).ids, ['e']);
});

test('Ctrl or Cmd adds and removes one row, the ids stay in list order', () => {
  let s = applyClick(emptySelection(), 'd', {}, ORDER);
  s = applyClick(s, 'b', { toggle: true }, ORDER);
  assert.deepEqual(s.ids, ['b', 'd']);
  s = applyClick(s, 'd', { toggle: true }, ORDER);
  assert.deepEqual(s.ids, ['b']);
  s = applyClick(s, 'b', { toggle: true }, ORDER);
  assert.deepEqual(s.ids, [], 'the last row can be taken away');
});

test('Shift selects the run from the anchor, either way; with Ctrl it adds the run', () => {
  let s = applyClick(emptySelection(), 'b', {}, ORDER);
  s = applyClick(s, 'e', { shift: true }, ORDER);
  assert.deepEqual(s.ids, ['b', 'c', 'd', 'e']);
  assert.equal(s.anchor, 'b', 'the anchor stays');
  s = applyClick(s, 'a', { shift: true }, ORDER);
  assert.deepEqual(s.ids, ['a', 'b'], 'a new run replaces the old one');
  let t = applyClick(emptySelection(), 'a', {}, ORDER);
  t = applyClick(t, 'e', { toggle: true }, ORDER);
  t = applyClick(t, 'f', { shift: true, toggle: true }, ORDER);
  assert.deepEqual(t.ids, ['a', 'e', 'f']);
  assert.deepEqual(applyClick(emptySelection(), 'c', { shift: true }, ORDER).ids, ['c'], 'Shift with no anchor is a plain click');
});

test('a row that is not in the list changes nothing', () => {
  const s = applyClick(emptySelection(), 'a', {}, ORDER);
  assert.equal(applyClick(s, 'zzz', {}, ORDER), s);
});

test('a chapter header selects the whole chapter and remembers it; a second click leaves its first row', () => {
  let s = selectChapter(emptySelection(), 'c02', ['c', 'd', 'e'], ORDER);
  assert.deepEqual(s, { ids: ['c', 'd', 'e'], anchor: 'c', chapter: 'c02' });
  s = selectChapter(s, 'c02', ['c', 'd', 'e'], ORDER);
  assert.deepEqual(s, { ids: ['c'], anchor: 'c', chapter: null });
  assert.equal(selectChapter(emptySelection(), 'x', [], ORDER).ids.length, 0);
  const t = applyClick(selectChapter(emptySelection(), 'c02', ['c', 'd'], ORDER), 'f', { toggle: true }, ORDER);
  assert.equal(t.chapter, null, 'adding a row is no longer "the whole chapter"');
});

test('rows that are gone leave the selection; a chapter that lost a row is no longer the whole chapter', () => {
  const s = { ids: ['c', 'd', 'e'], anchor: 'c', chapter: 'c02' };
  assert.deepEqual(pruneSelection(s, ORDER, { c02: ['c', 'd', 'e'] }), s);
  assert.deepEqual(pruneSelection({ ids: ['c', 'd'], anchor: 'c', chapter: 'c02' }, ORDER, { c02: ['c', 'd', 'e'] }), { ids: ['c', 'd'], anchor: 'c', chapter: null }, 'the chapter has a row the selection has not');
  assert.deepEqual(pruneSelection(s, ['a', 'c', 'e'], { c02: ['c', 'e'] }), { ids: ['c', 'e'], anchor: 'c', chapter: 'c02' }, 'the chapter lost the same row: still the whole chapter');
  assert.deepEqual(pruneSelection(s, ['a', 'b'], {}), { ids: [], anchor: null, chapter: null });
});

test('the playhead: the selection follows it, but several rows the owner chose stay while the video plays', () => {
  const one = { ids: ['b'], anchor: 'b', chapter: null };
  assert.deepEqual(followPlayhead(one, 'c', { playing: true }), { ids: ['c'], anchor: 'c', chapter: null });
  const many = { ids: ['b', 'c'], anchor: 'b', chapter: null };
  assert.equal(followPlayhead(many, 'e', { playing: true }), many);
  assert.deepEqual(followPlayhead(many, 'e', { playing: false }).ids, ['e'], 'a click elsewhere replaces it');
  assert.equal(followPlayhead(many, 'c', { playing: false }), many, 'a row that is already in it keeps it, and the anchor of a Shift run stays');
  assert.equal(followPlayhead(many, null), many);
});

test('what was added and removed; the arrow keys move between rows and stop at the ends', () => {
  assert.deepEqual(selectionDiff({ ids: ['a', 'b'] }, { ids: ['b', 'c'] }), { added: ['c'], removed: ['a'] });
  assert.equal(stepFocus(ORDER, 'c', 1), 'd');
  assert.equal(stepFocus(ORDER, 'a', -1), 'a');
  assert.equal(stepFocus(ORDER, 'f', 1), 'f');
  assert.equal(stepFocus(ORDER, 'nope', 1), 'a');
  assert.equal(stepFocus(ORDER, 'nope', -1), 'f');
  assert.equal(stepFocus([], 'a', 1), null);
});
