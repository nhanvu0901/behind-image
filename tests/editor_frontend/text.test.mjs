import test from 'node:test';
import assert from 'node:assert/strict';
import { wordCount, tokenCount, fold, findFolded, matchesFolded } from '../../bti/editor/static/js/text.js';

test('word counter: Vietnamese words made only of accented letters are counted (U1-004)', () => {
  assert.equal(wordCount('Đó là ở đây để ý. Việt Nam ơi!'), 9);
  assert.equal(wordCount('ở'), 1);
  assert.equal(wordCount('  '), 0);
  assert.equal(wordCount(''), 0);
  assert.equal(wordCount(null), 0);
});
test('word counter: any script, digits, underscore; punctuation alone is not a word', () => {
  assert.equal(wordCount('日本語 テキスト'), 2);
  assert.equal(wordCount('Привет мир'), 2);
  assert.equal(wordCount('مرحبا بالعالم'), 2);
  assert.equal(wordCount('1984 _ — … !!'), 2);                    // "1984" and "_" are words; the dashes are not
  assert.equal(wordCount('a b　c d'), 4);            // no-break, ideographic and em space separate words like the server's split()
  assert.equal(wordCount('é'), 1);                           // NFD letter with a combining accent
});
test('token count follows str.split(): punctuation alone is a token (the server splits on these)', () => {
  assert.equal(tokenCount('a — b'), 3);
  assert.equal(wordCount('a — b'), 2);
  assert.equal(tokenCount('  a   b '), 2);
});
test('fold: accents, case and đ', () => {
  assert.equal(fold('Đức'), 'duc');
  assert.equal(fold('đ'), 'd');
  assert.equal(fold('Dürer'), 'durer');
  assert.equal(fold('Việt Nam'), 'viet nam');
  assert.equal(fold('Vị̂et'), 'viet');                  // decomposed Vietnamese letters
  assert.equal(fold('Œuvre Ørsted Łódź ß'), 'oeuvre orsted lodz ss');
});
test('search matches with and without accents, either way (U1-001)', () => {
  assert.ok(matchesFolded('Đức Mẹ và Chúa Hài Đồng', 'duc'));
  assert.ok(matchesFolded('Đức Mẹ và Chúa Hài Đồng', 'đức'));
  assert.ok(matchesFolded('Albrecht Dürer', 'durer'));
  assert.ok(matchesFolded('Albrecht Durer', 'dürer'));
  assert.ok(matchesFolded('Hài Đồng', 'DONG'));
  assert.ok(!matchesFolded('Crucifixion', 'đức'));
  assert.ok(matchesFolded('anything', ''));                        // empty search = no filter
  assert.ok(matchesFolded('anything', '   '));
});
test('findFolded returns the range in the ORIGINAL text, so a highlight covers the accented letters', () => {
  assert.deepEqual(findFolded('Chúa Hài Đồng', 'dong'), [9, 13]);
  assert.deepEqual(findFolded('Chúa Hài Đồng', 'hai d'), [5, 10]);
  assert.equal(findFolded('abc', 'x'), null);
  assert.equal(findFolded('abc', ''), null);
  const t = 'Việt Nam';                               // decomposed: the mark after the letter stays in the match
  const [a, b] = findFolded(t, 'viet');
  assert.equal(t.slice(a, b), 'Việt');
});

test('fold agrees with the server (bti/textfold.py fold; 2005 cases compared offline)', () => {
  assert.equal(fold('½ạΩđł'), '1⁄2aωdl');
  assert.equal(fold('ﬁØ'), 'fio');
  assert.equal(fold('Ħ’'), "h'");
  assert.equal(fold('Σς'), 'σσ');
});
