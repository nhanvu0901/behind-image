// The list of shots of the simple page of step 5 (c4pages): chapters, sentences, problems in words, the numbers of the header.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { buildShotList, chapterTitle, problemKind, problemsOf, nextProblem, summaryText, spokenText, numbersText, approveView } from '../../bti/editor/static/js/shotlist.js';
import { mainAssetKey, looksRaw } from '../../bti/editor/static/js/shotsentence.js';
import { derive } from '../../bti/editor/static/js/logic.js';
import { EDIT_PAGE_LABELS as W } from '../../bti/editor/static/js/labels.js';

const read = (p) => JSON.parse(fs.readFileSync(new URL('../../' + p, import.meta.url), 'utf8'));
const REG = read('style/gae/techniques.json').techniques;
const BY = Object.fromEntries(REG.map((t) => [t.id, t]));
const sb = read('bti/editor/static/mock/storyboard.json'), timing = read('bti/editor/static/mock/timing.json');
derive(sb, timing);
const env = { tech: (id) => BY[id] || null, assets: sb.assets, mainKey: mainAssetKey(sb, sb.title) };
const issues = [
  { level: 'warn', code: 'incomplete', path: 'shots[9].slots.mask', message: 'required slot mask is missing' },
  { level: 'warn', code: 'incomplete', path: 'shots[9].slots.second', message: 'required slot second is missing' },
  { level: 'error', code: 'shot_too_short', path: 'shots[3].start', message: 'too short' },
  { level: 'warn', code: 'canvas_not_1080p', path: 'canvas', message: 'canvas' },
  { level: 'error', code: 'audio_missing', path: 'audio', message: 'audio file missing' },
  { level: 'error', code: 'asset_file_missing', path: 'assets.C.file', message: 'file does not exist', args: { asset: 'C' } },
];
const L = buildShotList({ draft: sb, chapters: timing.chapters, words: timing.words, issues, env });

test('one row per shot with its number, its start and its length in the words of the app', () => {
  assert.equal(L.rows.length, 12);
  assert.deepEqual(L.rows.slice(0, 3).map((r) => [r.number, r.time]), [[1, '0:00'], [2, '0:02'], [3, '0:22']]);
  assert.equal(L.rows[1].length, '20,1 giây');
  assert.equal(L.rows[0].sentence, 'Mở đầu: cả bức tranh');                  // fixes3: the mock's first shot (a title card) carries the reserved id s0000, which reads as the program's opening, as in shotwords.py
  assert.equal(L.rows[9].locked, true);
  assert.deepEqual(L.order, sb.shots.map((s) => s.id));
  for (const r of L.rows) assert.ok(!looksRaw(r.sentence), r.sentence);
});

test('the shots are grouped by the chapter they start in, with the chapter titled in words (an id-like name is read as words)', () => {
  assert.deepEqual(L.groups.map((g) => [g.title, g.ids.length]), [['Chương 1 · Opening', 2], ['Chương 2 · The mirror', 2], ['Chương 3 · Light and paint', 8]]);
  assert.deepEqual(L.chapterRows.c02, ['s0002', 's0003']);
  assert.equal(chapterTitle({ name: 'c03' }, 2), 'Chương 3');
  assert.equal(chapterTitle({ name: '' }, 0), 'Chương 1');
  assert.equal(chapterTitle({ name: 'Gương' }, 1), 'Chương 2 · Gương');
  assert.equal(chapterTitle({ title: 'THE_MIRROR' }, 1), 'Chương 2 · The mirror');
  const none = buildShotList({ draft: sb, chapters: [], words: [], issues: [], env });
  assert.equal(none.groups.length, 1);
  assert.equal(none.groups[0].title, '', 'no chapters: one group without a title');
});

test('chapters that carry only word ranges still group the shots', () => {
  const tm = { ...timing, chapters: [{ id: 'c1', name: 'A', w0: 0, w1: 100 }, { id: 'c2', name: 'B', w0: 100, w1: 400 }] };
  const l = buildShotList({ draft: sb, chapters: tm.chapters, words: timing.words, issues: [], env });
  assert.ok(l.groups.length >= 1 && l.groups.every((g) => g.ids.length > 0));
  assert.equal(l.rows.length, 12);
});

test('problems: the shots that need fixing, each in a sentence with no id; a problem of the whole video is general', () => {
  assert.equal(L.summary.problemShots, 3, 'shots 4 (too short), 8 and 10 (the picture C is missing)');
  const by = Object.fromEntries(L.rows.filter((r) => r.problems.length).map((r) => [r.number, r.problems.map((p) => p.kind)]));
  assert.deepEqual(Object.keys(by), ['4', '8', '10']);
  assert.deepEqual(by[4], ['short']);
  assert.deepEqual(by[10], ['incomplete', 'asset'], 'two incomplete slots of one shot are one problem');
  assert.deepEqual(by[8], ['asset']);
  assert.equal(L.general.length, 1, 'the missing audio file belongs to no shot');
  assert.match(L.general[0].text, /chung cho cả video/);
  for (const p of L.rows.flatMap((r) => r.problems).concat(L.general)) { assert.ok(!looksRaw(p.text), p.text); assert.match(p.text, /[àáảãạăâêôơưđ]/); }
  assert.equal(L.groups[2].problems, 2, 'chapter 3 holds shots 8 and 10');
  assert.equal(L.groups[1].problems, 1);
});

test('what counts as a problem: an error, an incomplete shot, a shot that cannot be drawn; a warning does not', () => {
  assert.deepEqual(problemKind({ level: 'warn', code: 'incomplete' }), { kind: 'incomplete', counted: true });
  assert.deepEqual(problemKind({ level: 'warn', code: 'undrawable' }), { kind: 'undrawable', counted: true });
  assert.deepEqual(problemKind({ level: 'error', code: 'unknown_param' }), { kind: 'other', counted: true });
  assert.deepEqual(problemKind({ level: 'warn', code: 'canvas_not_1080p' }), { kind: 'other', counted: false });
  assert.deepEqual(problemKind({ level: 'error', code: 'region_undefined' }), { kind: 'region', counted: true });
  assert.deepEqual(problemKind({ level: 'error', code: 'overlay_outside_shot' }), { kind: 'outside', counted: true });
  assert.deepEqual(problemKind({ level: 'error', code: 'anchor_invalid' }), { kind: 'time', counted: true });
  assert.equal(problemsOf([], sb).byShot.size, 0);
  const o = problemsOf([{ level: 'error', code: 'overlay_outside_shot', path: 'shots[2].overlays[1].start' }], sb);
  assert.deepEqual(o.byShot.get('s0002'), [{ kind: 'outside', text: W.problems.text.outside, overlay: 'o2' }]);
});

test('"2 cảnh cần sửa" leads to the first shot with a problem, then to the next', () => {
  assert.equal(nextProblem(L).number, 4);
  assert.equal(nextProblem(L, 's0003').number, 8);
  assert.equal(nextProblem(L, 's0009').number, 4, 'after the last it goes round to the first');
  assert.equal(nextProblem(buildShotList({ draft: sb, chapters: [], issues: [], env })), null);
});

test('the header numbers, the spoken words of a shot, the numbers of several shots', () => {
  assert.equal(summaryText(L.summary), '12 cảnh · 1:58');
  const first = timing.words.filter((w) => w.s < 3).map((w) => w.w).join(' ');
  assert.equal(spokenText(timing.words, 0, 3), first.replace(/\s+/g, ' ').trim());
  assert.ok(first.length > 10);
  assert.equal(spokenText([{ w: 'a', s: 1 }, { w: 'b', s: 5 }], 0, 3), 'a');
  assert.equal(spokenText([{ w: 'x'.repeat(300), s: 1 }], 0, 3, 50).length, 50);
  assert.equal(spokenText(null, 0, 3), '');
  assert.equal(numbersText([12, 3, 7]), '3, 7, 12');
  assert.equal(numbersText([1, 2, 3, 4, 5, 6, 7, 8]), '1, 2, 3, 4, 5, 6 và 2 cảnh nữa');
});

test('the approval of the header: approved, an old approval, none; what is missing when it cannot be pressed', () => {
  assert.deepEqual(approveView({ ap: { rev: 'r1' }, rev: 'r1' }), { state: 'approved', label: 'Đã duyệt', canPress: false, why: '', current: true });
  assert.equal(approveView({ ap: { rev: 'r0' }, rev: 'r1' }).state, 'old');
  assert.equal(approveView({ ap: null, rev: 'r1' }).label, 'Duyệt');
  assert.equal(approveView({ ap: { rev: 'r1' }, rev: 'r1', dirty: true }).state, 'old');
  assert.equal(approveView({ rev: 'r1', dirty: true }).why, W.top.approveSave);
  assert.equal(approveView({ rev: 'r1', problemShots: 2 }).why, W.top.approveFix(2));
  assert.equal(approveView({ rev: 'r1', approving: true }).canPress, false);
  assert.equal(approveView({ rev: 'r1', approving: true }).label, 'Đang duyệt...');
  assert.equal(approveView({ rev: 'r1', problemShots: 2 }).canPress, true, 'the click explains what is missing');
});
