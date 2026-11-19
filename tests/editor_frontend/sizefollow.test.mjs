// Worker sizefollow. Run with: node --test tests/editor_frontend/sizefollow.test.mjs
//  - the sentence of the storyboard warning `asset_size_mismatch` (a picture recorded with a size that is not its file's)
//  - the reason in the step 4 search banner for a source that limits downloads (views/picks.js `searchErrorText`)
//  - the older import path of the storyboard's picture tab shows the minutes too (media.js -> errorToast -> describeError)
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { issueText, describeError, STAGE_CODES } from '../../bti/editor/static/js/errmsg.js';
import { storyboardIssueText, issueTarget, KNOWN_CODES } from '../../bti/editor/static/js/sbissues.js';
import { ApiError } from '../../bti/editor/static/js/errors.js';
import { searchErrorText } from '../../bti/editor/static/js/views/picks.js';

const JS = new URL('../../bti/editor/static/js/', import.meta.url).pathname;
const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const WAIT = 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau';

// ------------------------------------------------------------------ the warning
const mismatch = (args) => ({ level: 'warn', code: 'asset_size_mismatch', path: 'assets.scream', message: "asset 'scream' is recorded as 6703x8322 but its file is 3840x4767 pixels", args });
const ARGS = { asset: 'scream', width: 6703, height: 8322, stored_width: 3840, stored_height: 4767 };

test('asset_size_mismatch: the sentence names the picture, both sizes and what is wrong, and says what to do (a re-draft takes the stored size, followups item 4)', () => {
  const t = issueText(mismatch(ARGS));
  assert.equal(t.text, 'Hình "scream" được ghi là 6703 x 8322 nhưng tệp đã lưu là 3840 x 4767, nên khung hình sẽ lệch. Dựng nháp lại để cập nhật kích thước hình.');
  assert.ok(!t.generic);
  assert.equal(storyboardIssueText(mismatch(ARGS)).text, t.text);
  assert.match(t.text, VI);
  assert.doesNotMatch(t.text, /undefined|null|NaN|\[object|asset|recorded|pixels/);
});

test('asset_size_mismatch: a code the table knows, taken from args, with no shot in front of the sentence', () => {
  assert.ok(KNOWN_CODES.includes('asset_size_mismatch'));
  assert.ok(!/^Shot /i.test(issueText(mismatch(ARGS)).text));
  // the asset falls back to the path when args lack it; missing numbers never print "undefined"
  const t = issueText({ level: 'warn', code: 'asset_size_mismatch', path: 'assets.mirror', message: 'x', args: {} }).text;
  assert.match(t, /^Hình "mirror"/);
  assert.doesNotMatch(t, /undefined|NaN/);
});

test('asset_size_mismatch: a click on it leads to the picture (or to the pictures tab), not to a shot', () => {
  const draft = { shots: [{ id: 's0001', slots: { image: { asset: 'scream' } } }], assets: { scream: {} } };
  assert.deepEqual(issueTarget(mismatch(ARGS), draft), { kind: 'asset', asset: 'scream', shots: ['s0001'] });
});

// ------------------------------------------------------------------ step 4 search banner
test('searchErrorText: a limited source shows the wait it asked for, rounded up to whole minutes', () => {
  assert.equal(searchErrorText({ source: 'commons', code: 'source_rate_limited', retry_after: 600 }), `${WAIT} khoảng 10 phút.`);
  assert.equal(searchErrorText({ source: 'commons', code: 'source_rate_limited', retry_after: 601 }), `${WAIT} khoảng 11 phút.`);
  assert.equal(searchErrorText({ source: 'commons', code: 'source_rate_limited', retry_after: 20 }), `${WAIT} khoảng 1 phút.`);
});

test('searchErrorText: a limited source that gave no time says so without a number', () => {
  for (const e of [{ code: 'source_rate_limited', retry_after: null }, { code: 'source_rate_limited' }]) assert.equal(searchErrorText(e), `${WAIT}.`);
});

test('searchErrorText: every other code keeps the text it showed before', () => {
  const ERR = { ...STAGE_CODES.longjob, ...STAGE_CODES.picks };
  assert.ok(ERR.source_unreachable, 'the table has the old code');
  assert.equal(searchErrorText({ source: 'pexels', code: 'source_unreachable' }), ERR.source_unreachable);
  assert.equal(searchErrorText({ source: 'pexels', code: 'source_error' }), ERR.source_error);
  assert.equal(searchErrorText({ source: 'pexels', code: 'something_new' }), 'không tìm được.');
  assert.equal(searchErrorText({ source: 'pexels' }), 'không tìm được.');
  assert.equal(searchErrorText(undefined), 'không tìm được.');
});

test('the banner of the results list is built with searchErrorText (not with the old inline table lookup)', () => {
  const src = fs.readFileSync(JS + 'views/picks.js', 'utf8');
  const line = src.split('\n').find((l) => l.includes("class: 'pk-banner warn'") && l.includes('SOURCE_LABELS'));
  assert.ok(line, 'the search banner line exists');
  assert.match(line, /searchErrorText\(e\)/);
  assert.doesNotMatch(line, /ERR\[e\.code\]/);
  assert.match(src, /import \{[^}]*\bsourceLimitText\b[^}]*\} from '\.\.\/errmsg\.js'/);
});

// ------------------------------------------------------------------ the older import path of the storyboard's picture tab
test('the body the older import path now answers is shown with the minutes', () => {
  const body = (retry_after) => ({ detail: 'the image source limits downloads: wait before trying again (HTTP 429)', code: 'source_rate_limited', retryable: true, retry_after });
  assert.equal(describeError(new ApiError(503, body(600))).text, `${WAIT} khoảng 10 phút.`);
  assert.equal(describeError(new ApiError(503, body(null))).text, `${WAIT}.`);
  // the answer it still gives for a 503 that is not a rate limit: a Vietnamese sentence, no code
  const old = { detail: 'Nguồn ảnh đang giới hạn tốc độ hoặc không phản hồi (HTTP 503). Hãy thử lại sau vài giây.', retryable: true, retry_after: 10 };
  assert.match(describeError(new ApiError(503, old)).text, /Hãy thử lại sau vài giây/);
});

test('both calls of that tab (search and import) show a failure through errorToast, which goes through describeError', () => {
  const media = fs.readFileSync(JS + 'media.js', 'utf8');
  assert.match(media, /api\.search\([^)]*\)[^\n]*catch \(e\) \{[^}]*errorToast\(e/);
  assert.match(media, /api\.importAsset\([^)]*\)[\s\S]{0,400}catch \(e\) \{ errorToast\(e/);
  const util = fs.readFileSync(JS + 'util.js', 'utf8');
  assert.match(util, /export function errorToast\(e[^)]*\) \{\s*const d = describeError\(e\);/);
});
