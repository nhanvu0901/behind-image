import test from 'node:test';
import assert from 'node:assert/strict';
import { issueText } from '../../bti/editor/static/js/errmsg.js';

test('viewer warnings explain what to do in Vietnamese', () => {
  assert.match(issueText({code:'small_detail_not_lit',args:{beat:'b1',shot:'s1'}}).text, /rọi sáng/);
  assert.match(issueText({code:'highlight_nothing_to_dim',args:{shot:'s1'}}).text, /rộng hơn/);
  const text=issueText({code:'text_too_brief',args:{shot:'s1',text:'Green dress',seconds:0.2,needed:1.5}}).text;
  assert.match(text,/Green dress/); assert.match(text,/giây/);
});
