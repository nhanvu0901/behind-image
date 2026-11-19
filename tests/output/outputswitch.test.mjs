// The words and the one decision of the settings switch of the output folder (outputswitch.js): Vietnamese, plain, and on unless the server says it is off.
import test from 'node:test';
import assert from 'node:assert/strict';
import { OUTPUT_LABELS as T } from '../../bti/editor/static/js/labels.js';
import { cleanChecked } from '../../bti/editor/static/js/outputswitch.js';
import { looksRaw } from '../../bti/editor/static/js/shotsentence.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('every word of the switch is Vietnamese and shows no id, file or parameter name', () => {
  for (const [k, v] of Object.entries(T)) {
    assert.equal(typeof v, 'string', k);
    assert.ok(VI.test(v), `${k}: "${v}" has no Vietnamese letter`);
    assert.ok(!looksRaw(v), `${k}: "${v}" looks raw`);
  }
  assert.match(T.hint, /không bị xóa/);
});

test('the switch is on unless the server says it is off', () => {
  assert.equal(cleanChecked({ clean_after_export: true }), true);
  assert.equal(cleanChecked({ clean_after_export: false }), false);
  assert.equal(cleanChecked({}), true);
  assert.equal(cleanChecked(null), true);
});
