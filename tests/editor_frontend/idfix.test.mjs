import test from 'node:test';
import assert from 'node:assert/strict';

import { issueText, IDFIX_CODES } from '../../bti/editor/static/js/errmsg.js';
import { CODE, CODE_IDFIX } from '../../bti/editor/static/js/labels.js';

test('strip_without_light renders clean Vietnamese issue sentence and label', () => {
  assert.deepEqual(IDFIX_CODES, ['strip_without_light']);
  assert.ok(CODE_IDFIX.strip_without_light && CODE.strip_without_light === CODE_IDFIX.strip_without_light);

  const msg = issueText({
    code: 'strip_without_light',
    level: 'warn',
    args: { shot: 's0040', text: 'Settle', region: 'SETTLE_CUSHION' },
  });
  assert.match(msg.text, /s0040/);
  assert.match(msg.text, /Settle/);
  assert.match(msg.text, /HI-01/);
  assert.match(msg.text, /AN-01/);

  const fallback = issueText({ code: 'strip_without_light', level: 'warn', args: {} });
  assert.match(fallback.text, /HI-01/);
});
