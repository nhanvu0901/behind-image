// The video's title box of the script page (worker titlestep): the decisions of titlelogic.js, the words of labels.js and errmsg.js, and that every code the title routes
// and the title job can answer has a Vietnamese sentence. No DOM: the panel (titlepanel.js) only draws what these functions say.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import * as TL from '../../bti/editor/static/js/titlelogic.js';
import { TITLE_LABELS as L, TITLE_FORM_WORDS, SETTINGS_LABELS } from '../../bti/editor/static/js/labels.js';
import { STAGE_CODES, TITLESTEP_SENTENCES, describeHttp, stageJobErrorText, isVietnamese } from '../../bti/editor/static/js/errmsg.js';

const ROOT = new URL('../../', import.meta.url).pathname;
const TITLE = 'The Saint Who Was Also an Advertisement';
const cand = (text, form = 'other', extra = {}) => ({ text, form, lines: ['b0001'], scores: { curiosity: 5, concrete: 5, central: 5, clear: 4 }, why: 'Hai thứ trái ngược mà đều đúng.', ...extra });
const answer = (over = {}) => ({
  rev: 'r1', state: 'done', stale: false, title: { text: TITLE, by: 'agent:claude:claude-opus-5-5@high', at: '2026-11-20T10:00:00+0700', source: 'agent', option: 1 },
  candidates: [cand(TITLE, 'contradiction'), cand('Why Is a Saint Weighing a Ring?', 'question'), cand('The Ring on the Scales', 'object')], history: [],
  written: { model: 'claude:claude-opus-5-5@high', agent: { id: 'opus', label: 'Opus 5.5 High' } }, limits: { max_chars: 60, best: [28, 55], max_words: 9, person_max_chars: 60 }, running: null,
  storyboard: { exists: false, title: null, same: false }, ...over });
const none = () => answer({ state: 'none', title: null, candidates: [], written: null });

test('the limits are the server\'s, and the defaults are the same numbers', () => {
  assert.deepEqual(TL.limitsOf(null), { max: 60, maxChars: 60, bestMin: 28, bestMax: 55, maxWords: 9 });
  assert.deepEqual(TL.limitsOf(answer({ limits: { max_chars: 60, best: [30, 50], max_words: 8, person_max_chars: 70 } })), { max: 70, maxChars: 60, bestMin: 30, bestMax: 50, maxWords: 8 });
});

test('a typed title: one line, counted in letters, refused over the limit and when empty, a gentle note outside the best length', () => {
  assert.equal(TL.oneLine('  The   Saint\n Who  '), 'The Saint Who');
  let i = TL.lengthInfo(TITLE);
  assert.deepEqual([i.chars, i.words, i.problem, i.note], [39, 7, null, '']);
  i = TL.lengthInfo('x'.repeat(61));
  assert.equal(i.problem, 'long'); assert.equal(i.note, L.tooLong(61, 60));
  assert.equal(TL.lengthInfo('x'.repeat(60)).problem, null);
  assert.equal(TL.lengthInfo('   ').problem, 'empty'); assert.equal(TL.lengthInfo('   ').note, '');
  assert.equal(TL.lengthInfo('Short').note, L.outsideBest(28, 55));
  assert.equal(TL.lengthInfo('Tựa tiếng Việt có dấu đủ dài để vừa khung').chars, [...'Tựa tiếng Việt có dấu đủ dài để vừa khung'].length);
  assert.equal(TL.lengthInfo('Hai\ndòng').problem, 'newline');         // the server refuses a line break inside the text (422), so the box says so before it sends
  assert.equal(TL.typeBody(answer(), 'Hai\ndòng'), null);
  assert.equal(TL.lengthInfo('  Hai   dòng  ').problem, null); assert.equal(TL.lengthInfo('  Hai   dòng  ').clean, 'Hai dòng');
});

test('who made the title, in the owner\'s words', () => {
  assert.equal(TL.whoWords('human'), 'Bạn');
  assert.equal(TL.whoWords('cli:operator'), 'Lệnh bti (operator)');
  assert.equal(TL.whoWords('agent:claude:claude-opus-5-5@high', answer()), 'Agent Opus 5.5 High');
  assert.equal(TL.whoWords('agent:agy:gemini-3.8-flash-high', answer()), 'Agent agy:gemini-3.8-flash-high');
  assert.equal(TL.whoWords(''), '');
  assert.equal(TL.whenWords('2026-11-20T10:05:00+0700'), '20/11/2026 10:05'); assert.equal(TL.whenWords('nope'), '');
});

test('the strip: no title, a title, a stale title, a running job, a narration that is not approved', () => {
  let v = TL.stripView(none(), { narrationApproved: true });
  assert.deepEqual([v.has, v.text, v.state, v.running, v.note], [false, L.none, 'none', false, L.noneHint]);
  assert.deepEqual([v.write.visible, v.write.disabled, v.write.label], [true, false, L.write]);
  v = TL.stripView(none(), { narrationApproved: false });
  assert.equal(v.note, L.needNarration); assert.equal(v.write.disabled, true); assert.equal(v.write.title, L.needNarration);
  v = TL.stripView(answer(), { narrationApproved: true });
  assert.deepEqual([v.has, v.text, v.state, v.by, v.when, v.source, v.note], [true, TITLE, 'done', 'Agent Opus 5.5 High', '20/11/2026 10:00', 'agent', '']);
  assert.equal(v.write.label, L.writeAgain); assert.equal(v.write.visible, true);
  v = TL.stripView(answer({ state: 'stale', stale: true }), { narrationApproved: true });
  assert.deepEqual([v.state, v.stale, v.note], ['stale', true, L.stale]);
  v = TL.stripView(answer(), { narrationApproved: true, job: { state: 'running' } });
  assert.deepEqual([v.running, v.write.visible, v.note], [true, false, L.working]);
  v = TL.stripView(answer({ running: { state: 'queued' } }), {});
  assert.equal(v.running, true);
  v = TL.stripView(answer(), { busy: true });
  assert.equal(v.running, true);
  v = TL.stripView(null, {});
  assert.deepEqual([v.has, v.open.visible, v.text], [false, false, L.none]);
});

test('the candidates, with the one in use marked, and the earlier titles newest first', () => {
  const rows = TL.candidateRows(answer());
  assert.equal(rows.length, 3);
  assert.deepEqual([rows[0].n, rows[0].inUse, rows[0].formWord, rows[0].chars, rows[0].linesText], [1, true, TITLE_FORM_WORDS.contradiction, 39, L.linesOf('b0001')]);
  assert.deepEqual([rows[1].n, rows[1].inUse, rows[1].formWord], [2, false, TITLE_FORM_WORDS.question]);
  assert.match(rows[1].scoresText, /Tò mò 5 · Cụ thể 5 · Trọng tâm 5 · Rõ 4/);
  assert.equal(TL.candidateRows(answer({ candidates: [cand('A', 'slogan')] }))[0].formWord, TITLE_FORM_WORDS.other);
  assert.deepEqual(TL.candidateRows(none()), []);
  const h = TL.historyRows(answer({ history: [{ text: 'First', by: 'agent:x', at: '2026-11-19T09:00:00+0700' }, { text: 'Second', by: 'human', at: '2026-11-20T09:00:00+0700' }] }));
  assert.deepEqual(h.map((x) => [x.text, x.who, x.when]), [['Second', 'Bạn', '20/11/2026 09:00'], ['First', 'Agent x', '19/11/2026 09:00']]);
});

test('what each button sends', () => {
  const d = answer();
  assert.deepEqual(TL.pickBody(d, 2), { base_rev: 'r1', option: 2, actor: 'human' });
  assert.deepEqual(TL.typeBody(d, '  My  own\ttitle '), { base_rev: 'r1', text: 'My own title', actor: 'human' });
  assert.equal(TL.typeBody(d, ''), null); assert.equal(TL.typeBody(d, 'x'.repeat(61)), null);
  assert.deepEqual(TL.generateBody(''), { actor: 'human' });
  assert.deepEqual(TL.generateBody('  make it about\n the mirror '), { note: 'make it about the mirror', actor: 'human' });
  assert.equal(TL.generateBody('y'.repeat(900)).note.length, TL.NOTE_MAX);
  assert.equal(TL.replacesPersonsTitle(answer({ title: { text: 'Mine', source: 'person' } })), true);
  assert.equal(TL.replacesPersonsTitle(answer()), false); assert.equal(TL.replacesPersonsTitle(none()), false);
});

test('the toasts say what the storyboard did', () => {
  assert.deepEqual(TL.savedToast({ storyboard: null }), [L.saved, 'ok']);
  assert.deepEqual(TL.savedToast({ storyboard: { sentence: 'Đã cập nhật tựa video trên storyboard (3 cảnh). Storyboard đã đổi nên cần được duyệt lại.' } }), [`${L.saved} Đã cập nhật tựa video trên storyboard (3 cảnh). Storyboard đã đổi nên cần được duyệt lại.`, 'ok']);
  assert.equal(TL.savedToast({ storyboard: { sentence: 'Chưa cập nhật được tựa video trên storyboard: x', error: 'x' } })[1], 'warn');
  assert.deepEqual(TL.doneToast({ result: { title: TITLE } }), [L.generated(TITLE), 'ok']);
  assert.equal(TL.doneToast({ result: { title: TITLE, storyboard: { sentence: 'S.', error: 'e' } } })[1], 'warn');
  assert.deepEqual(TL.doneToast({}), [L.saved, 'ok']);
});

test('a running job: the states that count, and the progress line never shows a raw note', () => {
  for (const s of ['queued', 'waiting', 'running']) assert.equal(TL.jobRunning({ state: s }), true);
  for (const s of ['done', 'error', 'cancelled', 'interrupted']) assert.equal(TL.jobRunning({ state: s }), false);
  assert.equal(TL.jobRunning(null), false);
  assert.equal(TL.progressText({ parts: [{ note: '' }] }), L.progress(''));
  assert.equal(TL.progressText({ parts: [{ note: 'Agent đang viết tựa video: bước 3/40, 0/10 phút.' }] }), L.progress(''));
  assert.equal(TL.progressText({ parts: [{ note: 'Đã chuẩn bị dữ liệu cho agent.' }] }), L.progress('Đã chuẩn bị dữ liệu cho agent.'));
  assert.equal(TL.progressText({ parts: [{ note: 'running tool call 3' }] }), L.progress('running tool call 3'));       // English notes are shown as the sentence of the part only when they hold letters: the server writes Vietnamese here
});

// ------------------------------------------------------------------------------------------------------------------------ the words
function leaves(x, p = '', out = []) {
  if (typeof x === 'string') out.push([p, x]);
  else if (typeof x === 'function') { for (const args of [[1], [3, 4], [{ curiosity: 5 }], [60], [28, 55], [600], [5, 60], ['Gương']]) { try { const v = x(...args); if (typeof v === 'string') out.push([p + '()', v]); } catch { /* wrong sample */ } } }
  else if (x && typeof x === 'object') for (const [k, v] of Object.entries(x)) leaves(v, p + '.' + k, out);
  return out;
}

test('every word of the title box is Vietnamese or a plain sign, and none shows an id', () => {
  const all = [...leaves(L, 'TITLE_LABELS'), ...leaves(TITLE_FORM_WORDS, 'TITLE_FORM_WORDS')];
  assert.ok(all.length > 50);
  for (const [p, t] of all) {
    if (p.endsWith('who.other()') || p.endsWith('chosenBy()') || p.includes('.who.')) continue;      // hand names back as they are
    if (!t.trim() || !/\p{L}/u.test(t) || /undefined/.test(t) || /^[\d\s\/.,:·–-]+$/.test(t)) continue;
    assert.ok(isVietnamese(t) || /^Agent |^Lệnh bti/.test(t), `${p}: "${t}" has no Vietnamese letter`);
    assert.doesNotMatch(t, /[a-z]_[a-z]/, `${p} shows an id`);
  }
  assert.equal(SETTINGS_LABELS.role['script.title'], 'Tựa video');
});

test('every sentence of the title stage is Vietnamese and shows no id', () => {
  for (const [code, t] of Object.entries(STAGE_CODES.title)) { assert.ok(isVietnamese(t), code); assert.doesNotMatch(t, /[a-z]_[a-z]/, code); }
});

function pyCodes() {
  const out = new Set();
  const scan = (p) => {
    const src = fs.readFileSync(p, 'utf8');
    for (const m of src.matchAll(/\bcode\s*=\s*["']([a-z_]+)["']/g)) out.add(m[1]);
    for (const m of src.matchAll(/(?:PartError|TitleError)\(\s*["']([a-z_]+)["']/g)) out.add(m[1]);
    for (const m of src.matchAll(/return "(title_[a-z_]+)", /g)) out.add(m[1]);
    for (const m of src.matchAll(/"(title_[a-z_]+)": /g)) out.add(m[1]);
  };
  for (const f of fs.readdirSync(path.join(ROOT, 'bti/title'))) if (f.endsWith('.py')) scan(path.join(ROOT, 'bti/title', f));
  scan(path.join(ROOT, 'bti/editor/title_api.py'));
  return out;
}
// answered with a sentence of their own elsewhere, or never shown to the owner by this box
const OTHER = new Set(['invalid_request', 'template_missing', 'document_corrupt', 'bad_model']);

test('every code the title routes and the title job can answer has a Vietnamese sentence', () => {
  const codes = [...pyCodes()].filter((c) => !OTHER.has(c));
  assert.ok(codes.length >= 12, `found ${codes.length} codes`);
  const missing = [];
  for (const c of codes) {
    const t = describeHttp(c === 'narration_not_approved' || c.startsWith('agy_') || c.startsWith('claude_') ? 409 : 422, { detail: 'English text of the server', code: c }).text;
    const j = stageJobErrorText('title', { error_code: c, error: 'English text of the server' }).text;
    if (!isVietnamese(t) && !isVietnamese(j)) missing.push(c);
  }
  assert.deepEqual(missing, []);
  for (const c of Object.keys(TITLESTEP_SENTENCES)) assert.ok(isVietnamese(describeHttp(422, { detail: 'x', code: c }).text) || c === 'stale_revision', c);
  assert.match(describeHttp(422, { detail: 'x', code: 'title_too_long' }).text, /60 ký tự/);
  assert.match(stageJobErrorText('title', { error_code: 'title_no_output' }).text, /nhắc sửa/);
  assert.match(stageJobErrorText('title', { error_code: 'agy_rate_limit' }).text, /hạn mức/);
});

test('the title files exist and the page script mounts the box', () => {
  const js = (f) => fs.readFileSync(path.join(ROOT, 'bti/editor/static/js', f), 'utf8');
  assert.match(js('views/script.js'), /mountTitlePanel/); assert.match(js('views/script.js'), /id="title-host"/);
  assert.match(js('titlepanel.js'), /\/title\/generate/); assert.match(js('titlepanel.js'), /TL\.pickBody/);
});
