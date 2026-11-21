import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeStoryboard, mergedNote } from '../../bti/editor/static/js/sbmerge.js';

const shot = (id, start, note = '') => ({ id, start: { t: start }, technique: 'CAM-01', intent: 'explore', note, overlays: [] });
const board = (...shots) => ({ schema: 'x', canvas: { w: 1920, h: 1080, fps: 30 }, assets: { a: { file: 'a.jpg' } }, end: { t: 40 }, shots });
const base = () => board(shot('s1', 0), shot('s2', 10), shot('s3', 20), shot('s4', 30));
const withNote = (b, i, n) => { b.shots[i].note = n; return b; };

test('R2U-003: notes on two different shots merge and keep both', () => {
  const r = mergeStoryboard(base(), withNote(base(), 3, 'mine'), withNote(base(), 1, 'theirs'));
  assert.equal(r.status, 'merged');
  assert.deepEqual(r.conflicts, []);
  assert.equal(r.value.shots[1].note, 'theirs');
  assert.equal(r.value.shots[3].note, 'mine');
  assert.deepEqual(r.fromTheirs, ['shot']);
});

test('nothing changed on the server: my draft is kept and nothing is said to come from elsewhere', () => {
  const r = mergeStoryboard(base(), withNote(base(), 0, 'mine'), base());
  assert.equal(r.status, 'merged');
  assert.equal(r.value.shots[0].note, 'mine');
  assert.deepEqual(r.fromTheirs, []);
});

test('the same shot changed on both sides is a conflict, and my version stays in the value', () => {
  const r = mergeStoryboard(base(), withNote(base(), 1, 'mine'), withNote(base(), 1, 'theirs'));
  assert.equal(r.status, 'conflict');
  assert.deepEqual(r.conflicts, [{ kind: 'shot', id: 's2' }]);
  assert.equal(r.value.shots[1].note, 'mine');
});

test('the same change on both sides is not a conflict', () => {
  const r = mergeStoryboard(base(), withNote(base(), 1, 'same'), withNote(base(), 1, 'same'));
  assert.equal(r.status, 'same');
});

test('the other side added a shot: it is taken, my edit stays', () => {
  const theirs = base(); theirs.shots.splice(2, 0, shot('s9', 15));
  const r = mergeStoryboard(base(), withNote(base(), 3, 'mine'), theirs);
  assert.equal(r.status, 'merged');
  assert.deepEqual(r.value.shots.map((s) => s.id), ['s1', 's2', 's9', 's3', 's4']);
  assert.equal(r.value.shots[4].note, 'mine');
});

test('the other side deleted a shot I did not touch: it goes; one I edited: conflict', () => {
  const theirs = base(); theirs.shots.splice(1, 1);
  const a = mergeStoryboard(base(), withNote(base(), 3, 'mine'), theirs);
  assert.equal(a.status, 'merged');
  assert.deepEqual(a.value.shots.map((s) => s.id), ['s1', 's3', 's4']);
  const b = mergeStoryboard(base(), withNote(base(), 1, 'mine'), theirs);
  assert.equal(b.status, 'conflict');
  assert.deepEqual(b.conflicts, [{ kind: 'shot', id: 's2' }]);
});

test('the list of shots changed on both sides (a split on one, a delete on the other) is not automatic', () => {
  const mine = base(); mine.shots.splice(1, 0, shot('s8', 5));
  const theirs = base(); theirs.shots.splice(3, 1);
  const r = mergeStoryboard(base(), mine, theirs);
  assert.equal(r.status, 'conflict');
  assert.ok(r.conflicts.some((c) => c.kind === 'list'));
});

test('a start time moved on one side only is a change of the list on that side: still automatic', () => {
  const theirs = base(); theirs.shots[2].start = { t: 22 };
  const r = mergeStoryboard(base(), withNote(base(), 0, 'mine'), theirs);
  assert.equal(r.status, 'merged');
  assert.deepEqual(r.value.shots[2].start, { t: 22 });
  assert.equal(r.value.shots[0].note, 'mine');
});

test('other top-level keys merge on their own: assets on one side, canvas on the other', () => {
  const mine = base(); mine.assets.b = { file: 'b.jpg' };
  const theirs = base(); theirs.canvas.fps = 25;
  const r = mergeStoryboard(base(), mine, theirs);
  assert.equal(r.status, 'merged');
  assert.deepEqual(Object.keys(r.value.assets), ['a', 'b']);
  assert.equal(r.value.canvas.fps, 25);
  assert.ok(r.fromTheirs.includes('canvas'));
});

test('the same key changed on both sides differently is a conflict', () => {
  const mine = base(); mine.end = { t: 41 };
  const theirs = base(); theirs.end = { t: 42 };
  const r = mergeStoryboard(base(), mine, theirs);
  assert.equal(r.status, 'conflict');
  assert.deepEqual(r.conflicts, [{ kind: 'key', key: 'end' }]);
});

test('approvals and derived keys never take part', () => {
  const mine = withNote(base(), 0, 'mine'); mine.approvals = { storyboard: { rev: 'a' } }; mine.shots[1]._t0 = 3;
  const theirs = base(); theirs.approvals = { storyboard: { rev: 'b' } };
  const r = mergeStoryboard(base(), mine, theirs);
  assert.equal(r.status, 'merged');
  assert.equal('approvals' in r.value, false);
});

test('mergedNote is one Vietnamese line without numbers or codes', () => {
  const t = mergedNote(['shot', 'assets']);
  assert.match(t, /^Đã ghép/);
  assert.doesNotMatch(t, /\d|409/);
  assert.match(mergedNote([]), /^Đã ghép/);
});
