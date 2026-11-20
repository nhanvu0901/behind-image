// The words and the one decision of the settings switch of the web search of the automatic choice of pictures (websearchswitch.js): Vietnamese, plain,
// and OFF unless the server says it is on (it is a paid search: the owner's standing permission).
import test from 'node:test';
import assert from 'node:assert/strict';
import { WEBSEARCH_LABELS as T } from '../../bti/editor/static/js/labels.js';
import { STAGE_CODES } from '../../bti/editor/static/js/errmsg.js';
import { webSearchChecked, webSearchHint } from '../../bti/editor/static/js/websearchswitch.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('every word of the switch is Vietnamese and shows no id, file or parameter name', () => {
  for (const [k, v] of Object.entries(T)) {
    const text = typeof v === 'function' ? v(80) : v;
    assert.equal(typeof text, 'string', k);
    assert.ok(VI.test(text), `${k}: "${text}" has no Vietnamese letter`);
    assert.ok(!looksRaw(text), `${k}: "${text}" looks raw`);
  }
  assert.equal(T.on, 'Tìm hình trên web khi chọn hình tự động');
});

test('the hint says it costs money and how many searches one run may make', () => {
  assert.match(webSearchHint({ auto_web_search_max: 80 }), /tốn tiền/);
  assert.match(webSearchHint({ auto_web_search_max: 80 }), /tối đa 80 lượt/);
  assert.match(webSearchHint({ auto_web_search_max: 12 }), /tối đa 12 lượt/);
  assert.match(webSearchHint(null), /tối đa 80 lượt/);
});

test('the switch is off unless the server says it is on', () => {
  assert.equal(webSearchChecked({ auto_web_search: 'on' }), true);
  assert.equal(webSearchChecked({ auto_web_search: 'off' }), false);
  assert.equal(webSearchChecked({}), false);
  assert.equal(webSearchChecked(null), false);
});

test('the refusals of the web search have a Vietnamese sentence on the picks page', () => {
  for (const code of ['web_off', 'web_no_key', 'not_an_image', 'unsafe_url']) {
    assert.ok(VI.test(STAGE_CODES.picks[code] || ''), code);
  }
});
