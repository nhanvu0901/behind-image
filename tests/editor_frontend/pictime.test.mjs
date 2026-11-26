// Worker pictime: Vietnamese sentences and labels for borrowed-picture duration warnings.
import test from 'node:test';
import assert from 'node:assert/strict';
import { issueText, PICTIME_CODES, PICTIME_SENTENCES } from '../../bti/editor/static/js/errmsg.js';
import { CODE_PICTIME } from '../../bti/editor/static/js/labels.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

const ISSUES = {
  outside_picture_brief: { path: 'shots[4]', args: { shot: 's0005', asset: 'CITY', min: 3.0, got: 1.6 } },
  outside_picture_dropped: { path: 'shots[4]', args: { beat: 'b0002', shot: 's0005', assets: ['CITY'], min: 3.0 } },
};

test('pictime codes have Vietnamese issue sentences without raw codes or technique ids', () => {
  assert.deepEqual([...PICTIME_CODES].sort(), Object.keys(ISSUES).sort());
  for (const code of PICTIME_CODES) {
    assert.equal(typeof PICTIME_SENTENCES[code], 'function');
    assert.match(CODE_PICTIME[code], VI);
    const t = issueText({ level: 'warn', code, message: 'English detail', ...ISSUES[code] });
    assert.ok(!t.generic, `${code} fell back to generic sentence`);
    assert.match(t.text, VI);
    assert.doesNotMatch(t.text, /undefined|null|NaN|\[object|English detail/);
    assert.doesNotMatch(t.text, /\b(X-LAY-01|MAP-01|CAM-0\d)\b/);
    assert.doesNotMatch(t.text, new RegExp(`\\b${code}\\b`));
  }
  assert.match(issueText({ level: 'warn', code: 'outside_picture_brief', ...ISSUES.outside_picture_brief }).text, /s0005.*1,6 giây.*3 giây/);
  assert.match(issueText({ level: 'warn', code: 'outside_picture_dropped', ...ISSUES.outside_picture_dropped }).text, /b0002.*3 giây/);
});
