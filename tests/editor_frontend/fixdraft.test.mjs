// Worker fixdraft: the Vietnamese sentences of the viewer checks (bti/engine/viewchecks.py) and of the owner's note of the draft.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { issueText, stageErrorText, FIXDRAFT_CODES, FIXDRAFT_SENTENCES } from '../../bti/editor/static/js/errmsg.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
const NINE = ['shot_short', 'upright_whole_share', 'highlight_off_frame', 'highlight_too_dark', 'caption_placeholder', 'caption_repeats', 'text_not_in_narration',
  'asset_not_in_lines', 'explainer_early'];

// what the engine puts in `args` (bti/engine/viewchecks.py CODES), one realistic issue each
const ISSUES = {
  shot_short: { path: 'shots[72]', args: { shot: 's0073', min: 1.5, got: 1.1 } },
  upright_whole_share: { path: 'shots[87]', args: { asset: 'A', share: 0.268, seconds: 204.9, count: 41, limit: 0.06, worst: [{ shot: 's0088', seconds: 10.9 }, { shot: 's0089', seconds: 10.2 }] } },
  highlight_off_frame: { path: 'shots[75].overlays[0]', args: { shot: 's0076', overlay: 'o1', technique: 'HI-01', region: 'SIGNATURE', at: 528.9, x_pct: 39, y_pct: -28 } },
  highlight_too_dark: { path: 'shots[53].overlays[0]', args: { shot: 's0145', overlay: 'o37', technique: 'HI-01', region: 'LIT_CANDLE', luma: 23.4, luma_without: 48.2, min: 32, floor: 0.2, floor_needed: 0.5 } },
  caption_placeholder: { path: 'shots[75]', args: { shot: 's0112', technique: 'LAY-01', param: 'caption_left_sub', text: 'UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950', kind: 'placeholder' } },
  caption_repeats: { path: 'shots[75]', args: { shot: 's0112', technique: 'LAY-01', param: 'caption_left', text: 'Wedding Wedding', repeated: 'wedding' } },
  text_not_in_narration: { path: 'shots[12]', args: { shot: 's0013', technique: 'MAP-01', param: 'region_label', text: 'Belgium', missing: ['belgium'] } },
  asset_not_in_lines: { path: 'shots[29]', args: { asset: 'squirrel', title: 'A squirrel on a snowy branch', count: 1, shots: ['s0030'] } },
  explainer_early: { path: 'shots[2]', args: { shot: 's0003', technique: 'TIME-01', start: 14.8, end: 25.6, limit: 30 } },
};

test('the codes of the page are the nine codes of the engine', () => {
  assert.deepEqual([...FIXDRAFT_CODES].sort(), [...NINE].sort());
  assert.deepEqual(Object.keys(ISSUES).sort(), [...NINE].sort());
});

test('the codes of the page are the codes of bti/engine/viewchecks.py', () => {
  const src = fs.readFileSync(new URL('../../bti/engine/viewchecks.py', import.meta.url), 'utf8');
  const start = src.indexOf('CODES = {');
  const block = src.slice(start, src.indexOf('\n}', start) + 2);
  const py = [...block.matchAll(/^    "([a-z_]+)":/gm)].map((m) => m[1]);
  assert.deepEqual(py.sort(), [...FIXDRAFT_CODES].sort());
});

for (const code of NINE) {
  test(`${code}: a plain Vietnamese sentence that names the shot, with its numbers and no code or id of a technique`, () => {
    const issue = { level: 'warn', code, message: 'English text of the engine', ...ISSUES[code] };
    const t = issueText(issue);
    assert.ok(!t.generic, `${code}: fell back to the general sentence`);
    assert.match(t.text, VI);
    assert.doesNotMatch(t.text, /undefined|null|NaN|\[object|English text/);
    assert.doesNotMatch(t.text, /\b(HI-01|X-HI-01|MAP-01|TIME-01|LAY-01|STATIC-09|CAM-0\d|NUM-01)\b/, `${code}: a technique id on the page: ${t.text}`);
    assert.doesNotMatch(t.text, new RegExp(`\\b${code}\\b`));
    assert.ok(t.text.length < 420, `${code}: too long (${t.text.length})`);
    assert.equal(t.detail, 'English text of the engine');
  });
}

test('the numbers and the names are in the sentence', () => {
  const s = (c) => issueText({ level: 'warn', code: c, ...ISSUES[c] }).text;
  assert.match(s('shot_short'), /s0073.*1,1 giây.*1,5 giây/);
  assert.match(s('upright_whole_share'), /27%.*205 giây.*41 cảnh.*6%.*s0088 \(10,9 giây\)/);
  assert.match(s('highlight_off_frame'), /s0076.*SIGNATURE.*528,9/);
  assert.match(s('highlight_too_dark'), /s0145.*LIT_CANDLE.*23.*32.*0,5/);
  assert.match(s('caption_placeholder'), /s0112.*UNKNOWN AUTHOR UNKNOWN AUTHOR, 1950.*chữ giữ chỗ/);
  assert.match(issueText({ level: 'warn', code: 'caption_placeholder', args: { ...ISSUES.caption_placeholder.args, kind: 'metadata', text: 'JAN VAN EYCK, 1434' } }).text, /tên tác giả và năm lấy từ tệp hình/);
  assert.match(s('caption_repeats'), /Wedding Wedding.*wedding.*hai lần/);
  assert.match(s('text_not_in_narration'), /Belgium.*"belgium"/);
  assert.match(issueText({ level: 'warn', code: 'text_not_in_narration', args: { shot: 's0013', param: 'sea_names', missing: ['sea names'] } }).text, /tên các vùng biển/);
  assert.match(s('asset_not_in_lines'), /squirrel on a snowy branch.*1 cảnh.*s0030/);
  assert.match(s('explainer_early'), /s0003.*giây 15.*giây 26/);
});

test('an issue with no numbers still reads as a sentence', () => {
  for (const code of NINE) for (const args of [undefined, {}]) {
    const t = issueText({ level: 'warn', code, args, path: 'shots[0]' });
    assert.match(t.text, VI, code);
    assert.doesNotMatch(t.text, /undefined|null|NaN|\[object/, `${code}: ${t.text}`);
  }
});

test('the highlight sentence without a floor that would do falls back to 0,6', () => {
  const t = issueText({ level: 'warn', code: 'highlight_too_dark', args: { shot: 's0001', region: 'X', luma: 20, min: 32, floor_needed: null } }).text;
  assert.match(t, /0,6/);
});

test('the sentences are a table of functions the page can call', () => {
  for (const code of NINE) assert.equal(typeof FIXDRAFT_SENTENCES[code], 'function');
});

test('the two errors of the note of the draft have a sentence of the draft table', () => {
  for (const code of ['draft_note_too_long', 'draft_note_invalid']) {
    const t = stageErrorText('draft', { body: { code } });
    assert.match(t.text, VI);
    assert.match(t.text, /[Gg]hi chú/);
  }
});
