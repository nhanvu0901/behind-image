import test from 'node:test';
import assert from 'node:assert/strict';

import { issueText, SUBJDRAFT_CODES } from '../../bti/editor/static/js/errmsg.js';
import { CODE } from '../../bti/editor/static/js/labels.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('subjdraft codes render clean Vietnamese issue sentences and labels', () => {
  assert.deepEqual([...SUBJDRAFT_CODES].sort(), ['subject_not_on_screen', 'year_already_on_screen']);
  for (const code of SUBJDRAFT_CODES) {
    assert.ok(CODE[code], `missing label in CODE for ${code}`);
    assert.match(CODE[code], VI);
  }

  const subj = issueText({
    code: 'subject_not_on_screen',
    level: 'warn',
    args: { shot: 's0012', beat: 'b0004', subject: 'costanza', name: 'Costanza Trenta' },
  });
  assert.ok(!subj.generic);
  assert.match(subj.text, VI);
  assert.match(subj.text, /s0012/);
  assert.match(subj.text, /Costanza Trenta/);
  assert.doesNotMatch(subj.text, /undefined|null|NaN|\[object/);

  const year = issueText({
    code: 'year_already_on_screen',
    level: 'warn',
    args: { shot: 's0009', year: '1434' },
  });
  assert.ok(!year.generic);
  assert.match(year.text, VI);
  assert.match(year.text, /s0009/);
  assert.match(year.text, /1434/);

  for (const code of SUBJDRAFT_CODES) {
    for (const args of [undefined, {}]) {
      const empty = issueText({ code, level: 'warn', args });
      assert.ok(!empty.generic, code);
      assert.match(empty.text, VI, code);
      assert.doesNotMatch(empty.text, /undefined|null|NaN|\[object/, `${code}: ${empty.text}`);
    }
  }
});
