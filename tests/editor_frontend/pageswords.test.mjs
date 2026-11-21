// The words of the two simple pages (c4pages) and the small changes the box needed: every sentence is Vietnamese, none shows an id; the chapter and the words
// the simple pages hand to the request box work, and without them the box is what it was.
import test from 'node:test';
import assert from 'node:assert/strict';
import { PICKS_PAGE_LABELS as P, EDIT_PAGE_LABELS as E, SHOT_WORDS as S, BOX_LABELS } from '../../bti/editor/static/js/labels.js';
import { pickScope, pickBeatScope } from '../../bti/editor/static/js/editlogic.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
/** Every string a label table gives, calling the functions with sample arguments. */
function leaves(x, path = '', out = []) {
  if (typeof x === 'string') out.push([path, x]);
  else if (typeof x === 'function') {
    for (const args of [[1], [3, 4], [2, 'Gương'], ['Gương'], [[4, 5]], [3, [4, 5]], [0, ''], ['Tên', 'unknown'], [1, 'Tên', true]]) {
      try { const v = x(...args); if (typeof v === 'string') out.push([path + '()', v]); } catch { /* wrong sample arguments */ }
    }
  } else if (x && typeof x === 'object') for (const [k, v] of Object.entries(x)) { if (k !== 'use') leaves(v, path + '.' + k, out); }      // `use` is a switch of the sentence builder, not a word
  return out;
}

test('every word of the two simple pages is Vietnamese or a plain sign, and none shows an id, a file or a parameter name', () => {
  for (const [name, table] of [['PICKS_PAGE_LABELS', P], ['EDIT_PAGE_LABELS', E], ['SHOT_WORDS', S]]) {
    const all = leaves(table, name);
    assert.ok(all.length > 60, `${name} has words to check`);
    for (const [path, t] of all) {
      if (!t.trim() || /^[\d\s\/.,:·–-]+[a-z]?$/.test(t) || /undefined/.test(t) || !/\p{L}/u.test(t)) continue;                    // empty, built from sample arguments that did not fit, or only numbers and signs
      if (/^[+·–\-▾▸/ ]+$/.test(t) || /^[A-Za-zĐđ]{1,3}$/.test(t)) continue;                  // "+", " · ", "/"
      const loan = /^(Clip|clip|Credit)\b/.test(t);                                         // words the app already writes as they are
      assert.ok(VI.test(t) || loan, `${path}: "${t}" has no Vietnamese letter`);
      assert.ok(!looksRaw(t), `${path}: "${t}" looks raw`);
    }
  }
});

test('the request box on the simple page of step 4 says "đoạn" where the hand tools say "dòng"', () => {
  const chapters = [{ id: 'c1', title: 'Mở đầu', beats: [{ id: 'a' }, { id: 'b' }, { id: 'c' }] }, { id: 'c2', title: 'Hai', beats: [{ id: 'd' }] }];
  const hand = pickBeatScope({ selected: ['b', 'c'], chapters });
  assert.equal(hand.words, '2 dòng đang chọn (2, 3)');
  const simple = pickBeatScope({ selected: ['b', 'c'], chapters, words: P.box });
  assert.equal(simple.words, '2 đoạn đang chọn (2, 3)');
  assert.equal(pickBeatScope({ selected: ['d'], chapters, words: P.box }).words, 'Đoạn 4 đang chọn');
  assert.equal(pickBeatScope({ selected: [], chapters, words: P.box, choice: 'beats' }).why, 'Chưa chọn đoạn nào.');
  assert.equal(pickBeatScope({ choice: 'all', chapters, words: P.box }).words, 'Cả video');
  assert.equal(pickBeatScope({ selected: ['a', 'b', 'c', 'd', 'a', 'b', 'c'], chapters, words: P.box }).words.includes('dòng'), false);
  assert.equal(BOX_LABELS.pictures.linesWords(1, '4'), 'Dòng 4 đang chọn', 'the hand tools keep their words');
});

test('a whole chapter chosen in the list: the box edits that chapter, not the one at the playhead (step 4 and step 5)', () => {
  const chapters = [{ id: 'c1', title: 'Mở đầu', beats: [{ id: 'a' }, { id: 'b' }] }, { id: 'c2', title: 'Gương', beats: [{ id: 'd' }, { id: 'e' }] }];
  const s = pickBeatScope({ selected: ['d', 'e'], chapters, beat: 'a', chapter: 'c2', words: P.box });
  assert.deepEqual([s.kind, s.payload, s.words, s.ok], ['chapter', { chapter: 'c2' }, 'Chương: Gương', true]);
  const none = pickBeatScope({ selected: ['a'], chapters, beat: 'a', chapter: 'zzz' });
  assert.equal(none.kind, 'beats', 'a chapter that does not exist is ignored');
  assert.deepEqual(pickBeatScope({ selected: ['a'], chapters, beat: 'a', chapter: 'c2', choice: 'beats' }).payload, { beats: ['a'] }, 'the pill "Đoạn" still means the lines');
  const shots = [{ id: 's1' }, { id: 's2' }, { id: 's3' }];
  const tl = [{ id: 'c1', name: 'Mở đầu', start: 0, end: 10 }, { id: 'c2', name: 'Gương', start: 10, end: 30 }];
  const w = pickScope({ selected: ['s2', 's3'], shots, chapters: tl, t: 2, chapter: 'c2' });
  assert.deepEqual([w.kind, w.payload, w.words], ['chapter', { chapter: 'c2' }, 'Chương: Gương']);
  assert.deepEqual(pickScope({ selected: ['s2'], shots, chapters: tl, t: 2 }).payload, { shots: ['s2'] }, 'without a chosen chapter nothing changed');
  assert.deepEqual(pickScope({ selected: [], shots, chapters: tl, t: 12 }).payload, { chapter: 'c2' }, 'with nothing selected it is the chapter at the playhead, as before');
});

test('the chip of a card of the pictures box says how many lines it edited, not "Chưa chọn cảnh nào."', async () => {
  const { scopeWords } = await import('../../bti/editor/static/js/editlogic.js');
  assert.equal(scopeWords({ kind: 'beats', beats: ['b0005'] }), '1 đoạn');
  assert.equal(scopeWords({ beats: ['b1', 'b2', 'b3'] }), '3 đoạn');
  assert.equal(scopeWords({ kind: 'beats', beats: [] }), 'Chưa chọn đoạn nào.');
  assert.equal(scopeWords({ kind: 'all' }), 'Cả video');
  assert.equal(scopeWords({ kind: 'shots', shots: ['s1'] }, { shots: [{ id: 's1' }] }), 'Cảnh 1', 'the storyboard cards are as before');
});

test('a chapter written in capitals is read as words in the box, as in the list', async () => {
  const { chapterLabel, readableName } = await import('../../bti/editor/static/js/editlogic.js');
  assert.equal(chapterLabel({ name: 'COLD OPEN' }, 0), 'Chương: Cold open');
  assert.equal(chapterLabel({ name: 'THE_MIRROR' }, 1), 'Chương: The mirror');
  assert.equal(chapterLabel({ name: 'The Merchant' }, 1), 'Chương: The Merchant');
  assert.equal(chapterLabel({ name: 'Gương' }, 1), 'Chương: Gương');
  assert.equal(chapterLabel({ name: 'c03' }, 2), 'Chương 3');
  assert.equal(readableName('UV'), 'UV', 'a short acronym is left alone');
  const s = pickBeatScope({ selected: [], chapters: [{ id: 'c1', title: 'THE SKY', beats: [{ id: 'a' }] }], beat: 'a', choice: 'chapter' });
  assert.equal(s.words, 'Chương: The sky');
});
