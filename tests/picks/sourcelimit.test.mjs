// Run with: node --test tests/picks/sourcelimit.test.mjs   (the sentence shown when a picture source says "too many requests")
import test from 'node:test';
import assert from 'node:assert/strict';
import { describeHttp, describeError, sourceLimitText, stageErrorText, isVietnamese } from '../../bti/editor/static/js/errmsg.js';
import { ApiError } from '../../bti/editor/static/js/errors.js';

const body = (retry_after) => ({ detail: 'the image source limits downloads: wait before trying again (HTTP 429)', code: 'source_rate_limited', retryable: true, retry_after });

test('with the wait the source gave: whole minutes, rounded up, at least one', () => {
  assert.equal(sourceLimitText({ retry_after: 600 }), 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 10 phút.');
  assert.equal(sourceLimitText({ retry_after: 601 }), 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 11 phút.');
  assert.equal(sourceLimitText({ retry_after: 30 }), 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 1 phút.');
  assert.equal(sourceLimitText({ retry_after: 3600 }), 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 60 phút.');
});

test('without a wait (null, missing, zero, not a number): the sentence says no time', () => {
  for (const b of [{ retry_after: null }, {}, null, undefined, { retry_after: 0 }, { retry_after: 'soon' }, { retry_after: -5 }]) {
    assert.equal(sourceLimitText(b), 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau.');
  }
});

test('the error of the import and search routes (code source_rate_limited) is shown through describeHttp and describeError', () => {
  assert.equal(describeHttp(503, body(120)).text, 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 2 phút.');
  assert.equal(describeHttp(503, body(null)).text, 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau.');
  const e = new ApiError(503, body(300));
  assert.equal(describeError(e).text, 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 5 phút.');
  assert.equal(stageErrorText('picks', e).text, 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 5 phút.');
});

test('a search error entry ({source, code, message, retry_after}) is read the same way', () => {
  const entry = { source: 'commons', code: 'source_rate_limited', message: 'x', retry_after: 90 };
  assert.equal(describeHttp(503, entry).text, 'Nguồn ảnh đang giới hạn lượt tải. Thử lại sau khoảng 2 phút.');
});

test('the sentence is Vietnamese, has no English word and no raw status; the server text stays under detail', () => {
  for (const t of [sourceLimitText({ retry_after: 240 }), sourceLimitText({})]) {
    assert.ok(isVietnamese(t));
    assert.ok(!/\b(HTTP|429|503|the|source|limit|wait)\b/i.test(t), t);
  }
  assert.match(describeHttp(503, body(60)).detail, /image source/);
});

test('the other source errors keep their own sentences', () => {
  assert.match(stageErrorText('picks', new ApiError(503, { detail: 'x', code: 'source_unreachable' })).text, /bận hoặc không trả lời/);
  assert.match(stageErrorText('picks', new ApiError(502, { detail: 'x', code: 'source_error' })).text, /báo lỗi/);
});
