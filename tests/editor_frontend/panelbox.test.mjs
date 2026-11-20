// Worker panelbox (2026-11-20): the sentences of the check `frame_off_painting` (bti/engine/viewchecks.py) and of the picks warning `content_box_unsure` (bti/picks/doc.py).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { issueText, PANELBOX_CODES, PANELBOX_SENTENCES, CATALOGUE_CODES, FIXDRAFT_CODES } from '../../bti/editor/static/js/errmsg.js';
import { PICKS_LABELS, PICKS_PAGE_LABELS } from '../../bti/editor/static/js/labels.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
// what the engine puts in `args` (bti/engine/viewchecks.py CODES): the worst camera key of a mirror close-up of the first test video
const ISSUE = { level: 'warn', code: 'frame_off_painting', path: 'shots[76].params.camera[1]', message: 'English text of the engine',
  args: { shot: 's0077', asset: 'goldsmith_his_shop_3bc1', key: 1, share: 0.103, limit: 0.01, box: [100, 106, 3363, 3900], cx: 3000, cy: 2700, zoom: 2.1 } };

test('the one code of the page for the panelbox check is the one code of the engine and no other list knows it', () => {
  assert.deepEqual([...PANELBOX_CODES], ['frame_off_painting']);
  const src = fs.readFileSync(new URL('../../bti/engine/viewchecks.py', import.meta.url), 'utf8');
  assert.match(src, /CODES\["frame_off_painting"\] = /);
  assert.ok(!CATALOGUE_CODES.includes('frame_off_painting') && !FIXDRAFT_CODES.includes('frame_off_painting'));
  assert.equal(typeof PANELBOX_SENTENCES.frame_off_painting, 'function');
});

test('frame_off_painting: a plain Vietnamese sentence with the shot and the share, no code, no technique id, nothing undefined', () => {
  const t = issueText(ISSUE);
  assert.ok(!t.generic, 'fell back to the general sentence');
  assert.match(t.text, VI);
  assert.match(t.text, /s0077.*10%/);
  assert.doesNotMatch(t.text, /undefined|null|NaN|\[object|English text|frame_off_painting|CAM-0\d/);
  assert.ok(t.text.length < 420, `too long (${t.text.length})`);
  assert.equal(t.detail, 'English text of the engine');
});

test('frame_off_painting: a missing share or shot still makes a sentence', () => {
  const t = issueText({ level: 'warn', code: 'frame_off_painting', path: 'shots[1]', message: 'x', args: {} });
  assert.ok(!t.generic);
  assert.doesNotMatch(t.text, /undefined|NaN|\[object/);
});

test('content_box_unsure: the list and the simple page both have a Vietnamese sentence', () => {
  assert.equal(typeof PICKS_LABELS.issue.content_box_unsure, 'function');
  assert.match(PICKS_LABELS.issue.content_box_unsure({ code: 'content_box_unsure', asset: 'A' }), VI);
  assert.match(PICKS_PAGE_LABELS.issue.contentBoxUnsure, VI);
  assert.doesNotMatch(PICKS_PAGE_LABELS.issue.contentBoxUnsure, /content_box|undefined/);
});
