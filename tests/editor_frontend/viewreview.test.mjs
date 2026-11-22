import test from 'node:test';
import assert from 'node:assert/strict';
import { issueText } from '../../bti/editor/static/js/errmsg.js';
import { CODE } from '../../bti/editor/static/js/labels.js';

test('viewer findings show a Vietnamese sentence and shot', () => {
  for (const code of ['review_picture_mismatch', 'review_text_wrong', 'review_context_missing', 'review_picture_repeated']) {
    const issue = issueText({code, message: 'English detail', args: {shot: 's42'}});
    assert.match(issue.text, /s42/);
    assert.ok(CODE[code]);
    assert.notEqual(issue.text, 'English detail');
  }
});
