// The labels of the three trust levels of a source (normal, restored, low) and the words that go with them.
import test from 'node:test';
import assert from 'node:assert/strict';
import { LOW_TRUST, TEXT_SOURCE, textSourceLabel, TRUST_LEVEL, RESTORED_NOTE, RESTORED_TEXT, NO_NORMAL_SOURCE, trustOf, trustLabel, trustNote, noNormalSource } from '../../bti/editor/static/js/labels.js';

test('the three levels have their Vietnamese words', () => {
  assert.deepEqual(TRUST_LEVEL, { normal: 'Tin cậy', restored: 'Bản khôi phục', low: 'Tin cậy thấp' });
  assert.equal(trustLabel('restored'), 'Bản khôi phục');
  assert.equal(trustLabel('low'), 'Tin cậy thấp');
  assert.equal(trustLabel('normal'), 'Tin cậy');
});

test('the note of a restored source says what it is good for and what needs another source', () => {
  assert.equal(RESTORED_NOTE, 'Bản khôi phục từ bản dịch máy, đã rà soát: dùng được cho ý và mô tả; số liệu, năm và trích dẫn phải có nguồn khác xác nhận.');
  assert.equal(NO_NORMAL_SOURCE, 'Chưa có nguồn tin cậy đầy đủ cho tác phẩm này.');
  assert.match(RESTORED_TEXT, /\[…\]/);
});

test('a level that is missing counts as normal, a word that is none of the three counts as low', () => {
  for (const v of [undefined, null, '']) assert.equal(trustOf(v), 'normal');
  for (const v of ['normal', 'restored', 'low']) assert.equal(trustOf(v), v);
  for (const v of ['LOW', 'weird', 'toString', '__proto__', 0, true]) assert.equal(trustOf(v), 'low', String(v));
});

test('the note shown is the one the server sent, else the words of the level', () => {
  assert.equal(trustNote('restored', 'từ máy chủ'), 'từ máy chủ');
  assert.equal(trustNote('restored', ''), RESTORED_NOTE);
  assert.equal(trustNote('low', undefined), LOW_TRUST);
  assert.equal(trustNote('normal', ''), '');
});

test('"no source is normal" holds for restored only, restored and low, low only; not for a mix with a normal source or for nothing', () => {
  assert.equal(noNormalSource(['restored']), true);
  assert.equal(noNormalSource(['restored', 'low']), true);
  assert.equal(noNormalSource(['low']), true);
  assert.equal(noNormalSource(['normal', 'restored']), false);
  assert.equal(noNormalSource(['normal', 'low']), false);
  assert.equal(noNormalSource([undefined, 'restored']), false);       // an old file without a level is a normal source
  assert.equal(noNormalSource([]), false);
});

test('the text of a restored work is called a restored text, not shown as a raw word', () => {
  assert.equal(TEXT_SOURCE.restored, 'bản khôi phục');
  assert.equal(textSourceLabel('restored'), 'bản khôi phục');
});
