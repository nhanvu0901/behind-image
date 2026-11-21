// Worker catalogue (2026-11-20): the Vietnamese sentences of the checks of what the `kinds` of a line call for (bti/engine/viewchecks.py `CATALOGUE_ISSUES`).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { issueText, CATALOGUE_CODES, CATALOGUE_SENTENCES, FIXDRAFT_CODES } from '../../bti/editor/static/js/errmsg.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const FIVE = ['device_wrong_kind', 'device_too_little', 'figure_on_wrong_picture', 'outside_on_painting', 'outside_picture_small'];

// what the engine puts in `args` (bti/engine/viewchecks.py CODES), one realistic issue each
const ISSUES = {
  device_wrong_kind: { path: 'shots[23]', args: { shot: 's0024', overlay: null, technique: 'MAP-01', beats: ['b0011'], kinds: ['detail', 'outside'], needs: ['journey'] } },
  device_too_little: { path: 'shots[53]', args: { shot: 's0054', overlay: null, technique: 'MAP-01', count: 1, min: 2, items: 'places', beats: ['b0027'] } },
  figure_on_wrong_picture: { path: 'shots[55].overlays[0]', args: { shot: 's0056', overlay: 'o1', asset: 'goldsmith_his_shop_3bc1', assets: ['caravel_view'], beats: ['b0028'] } },
  outside_on_painting: { path: 'shots[11]', args: { beat: 'b0012', shot: 's0012', assets: ['portret_van_dagobert'], seconds: 3.2, beat_seconds: 10.5, share: 0.3, limit: 0.5 } },
  outside_picture_small: { path: 'shots[30]', args: { shot: 's0031', asset: 'engraving', zoom: 0.4, fit: 1.54, share: 0.26, limit: 0.8 } },
};

test('the codes of the page for the catalogue pass are the five codes of the engine', () => {
  assert.deepEqual([...CATALOGUE_CODES].sort(), [...FIVE].sort());
  assert.deepEqual(Object.keys(ISSUES).sort(), [...FIVE].sort());
  const src = fs.readFileSync(new URL('../../bti/engine/viewchecks.py', import.meta.url), 'utf8');
  const start = src.indexOf('CATALOGUE_ISSUES = {');
  const block = src.slice(start, src.indexOf('\n}', start) + 2);
  const py = [...block.matchAll(/^    "([a-z_]+)":/gm)].map((m) => m[1]);
  assert.deepEqual(py.sort(), [...FIVE].sort());
  for (const c of FIVE) assert.ok(!FIXDRAFT_CODES.includes(c), 'the fixdraft list stays as it was');
});

for (const code of FIVE) {
  test(`${code}: a plain Vietnamese sentence with its numbers, no code and no id of a technique`, () => {
    const issue = { level: 'warn', code, message: 'English text of the engine', ...ISSUES[code] };
    const t = issueText(issue);
    assert.ok(!t.generic, `${code}: fell back to the general sentence`);
    assert.match(t.text, VI);
    assert.doesNotMatch(t.text, /undefined|null|NaN|\[object|English text/);
    assert.doesNotMatch(t.text, /\b(HI-01|X-HI-01|MAP-01|TIME-01|LAY-01|STATIC-09|CAM-0\d|NUM-01|DOC-01|AN-0\d|TREE-01|KEY-01|X-LAY-01|X-CMP-01)\b/, `${code}: a technique id on the page: ${t.text}`);
    assert.doesNotMatch(t.text, new RegExp(`\\b${code}\\b`));
    assert.ok(t.text.length < 420, `${code}: too long (${t.text.length})`);
    assert.equal(t.detail, 'English text of the engine');
  });
}

test('the numbers and the names are in the sentences', () => {
  const s = (code) => issueText({ level: 'warn', code, ...ISSUES[code] }).text;
  assert.match(s('device_wrong_kind'), /s0024.*bản đồ.*b0011.*chuyến đi hoặc mối liên hệ/);
  assert.match(s('device_too_little'), /s0054.*bản đồ.*chỉ có 1 địa điểm.*ít nhất 2.*hình của nơi đó/);
  assert.match(s('figure_on_wrong_picture'), /s0056.*goldsmith_his_shop_3bc1.*b0028/);
  assert.match(s('outside_on_painting'), /b0012.*3,2 trong 10,5 giây.*30%/);
  assert.match(s('outside_picture_small'), /s0031.*engraving.*26%.*1000 px/);
});

test('an issue with no numbers still reads as a sentence', () => {
  for (const code of FIVE) for (const args of [undefined, {}]) {
    const t = issueText({ level: 'warn', code, args, path: 'shots[0]' });
    assert.match(t.text, VI, code);
    assert.doesNotMatch(t.text, /undefined|null|NaN|\[object/, `${code}: ${t.text}`);
  }
});

test('every kind that a device needs and every device has a plain name', () => {
  for (const tech of ['MAP-01', 'TIME-01', 'NUM-01', 'DOC-01', 'AN-03', 'AN-06', 'TREE-01', 'LAY-01', 'X-CMP-01', 'KEY-01']) {
    const t = issueText({ level: 'warn', code: 'device_wrong_kind', args: { shot: 's1', technique: tech, beats: ['b1'], needs: ['journey', 'dates', 'figure', 'inscription', 'construction', 'relations', 'compare'] } }).text;
    assert.doesNotMatch(t, /hiệu ứng này/, tech + ' has no plain name');
    assert.doesNotMatch(t, /undefined/, tech);
  }
});

test('the sentences are a table of functions the page can call', () => {
  for (const code of FIVE) assert.equal(typeof CATALOGUE_SENTENCES[code], 'function');
});
