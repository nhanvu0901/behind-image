import test from 'node:test';
import assert from 'node:assert/strict';
import { describeHttp, describeError, issueText, jobErrorText, parseFailText, rawDetail, isVietnamese, stageErrorText, stageJobErrorText } from '../../bti/editor/static/js/errmsg.js';
import { ApiError } from '../../bti/editor/static/js/errors.js';
import { isQuota } from '../../bti/editor/static/js/agentlogic.js';
import { turnView } from '../../bti/editor/static/js/editlogic.js';

const noEnglish = (t) => !/\b(the|must|not found|already|required|failed|error|is|are)\b/i.test(t);

test('the errors the tester saw (U1-002) are Vietnamese, the raw text is kept under detail', () => {
  const cases = [
    [422, 'slug must match [a-z0-9][a-z0-9_-]{0,63}'],
    [422, 'slug may not start with lab_ or demo_'],
    [409, "project 'arnolfini' already exists"],
    [404, 'artwork not found'], [404, "'work not found'"], [404, 'book not found'],
    [409, 'the file changed since you loaded it; reload before saving'],
    [409, 'another model job is running for this project'],
    [422, 'the outline has errors: Chapter c01 has no title.'],
    [403, "project 'arnolfini' is protected and cannot be deleted"],
    [422, 'type the project id in `confirm` to delete it'],
    [404, 'project not found'], [404, 'job not found'], [404, 'unknown model'],
    [422, 'unknown chapter(s): c09, c10'],
    [409, 'locked beats would be replaced (c01:b0001, c01:b0002); unlock them or send force'],
    [422, 'beat b0009 is locked'], [422, 'cannot split a beat of 3 words at word 3'],
  ];
  for (const [st, detail] of cases) {
    const d = describeHttp(st, { detail });
    assert.ok(isVietnamese(d.text), `${detail} -> ${d.text}`);
    assert.ok(noEnglish(d.text), `${detail} -> ${d.text}`);
    assert.equal(d.detail, detail.replace(/^'(.*)'$/, '$1') === detail ? detail : detail);
  }
});
test('details carried in the sentence (names, ids, lists)', () => {
  assert.match(describeHttp(409, { detail: "project 'padded' already exists" }).text, /"padded"/);
  assert.match(describeHttp(422, { detail: 'unknown chapter(s): c09, c10' }).text, /c09, c10/);
  assert.match(describeHttp(422, { detail: 'beat b0009 is locked' }).text, /b0009/);
});
test('a message the server already wrote in Vietnamese is shown as it is', () => {
  const d = describeHttp(409, { detail: 'thiếu biến OPENROUTER_API_KEY' });
  assert.equal(d.text, 'thiếu biến OPENROUTER_API_KEY'); assert.equal(d.detail, '');
});
test('an unknown error: a general Vietnamese sentence, the raw text available as detail', () => {
  const d = describeHttp(422, { detail: 'flux capacitor misaligned' });
  assert.ok(isVietnamese(d.text)); assert.equal(d.detail, 'flux capacitor misaligned');
  assert.ok(!d.text.includes('flux'));
  const e = describeHttp(500, 'Traceback (most recent call last): boom');
  assert.match(e.text, /500/); assert.match(e.detail, /boom/);
});
test('it survives a body it does not recognise', () => {
  for (const body of [null, undefined, '', 42, [], {}, { detail: null }, { detail: { reason: 'r' } }, { detail: [{ loc: ['body', 'x'], msg: 'bad' }] }, { reason: 'because' }, { error: 'e' }, 'plain text', { issues: 5 }]) {
    const d = describeHttp(400, body);
    assert.equal(typeof d.text, 'string'); assert.ok(d.text.length > 0);
  }
  assert.equal(describeHttp(0, null).text.length > 0, true);
  assert.equal(rawDetail(422, { detail: [{ loc: ['body', 'x'], msg: 'bad' }] }), 'body.x: bad');
  assert.equal(rawDetail(422, { reason: 'because' }), 'because');
  assert.equal(rawDetail(422, { detail: { reason: 'r' } }), 'r');
});
test('reads detail, reason and issues of the consistent error bodies', () => {
  const d = describeHttp(422, { detail: 'validation failed', issues: [{ level: 'error' }, { level: 'warning' }] });
  assert.match(d.text, /1 lỗi/);
  assert.match(describeHttp(400, { detail: 'model is required' }).text, /Chưa chọn mô hình/);
  assert.match(describeHttp(400, { detail: 'model (string) is required' }).text, /Chưa chọn mô hình/);
});
test('ApiError carries the Vietnamese message; status, body and raw detail stay available', () => {
  const e = new ApiError(409, { detail: 'the file changed since you loaded it; reload before saving', rev: 'abc' }, '/x');
  assert.ok(isVietnamese(e.message)); assert.equal(e.status, 409); assert.equal(e.body.rev, 'abc');
  assert.match(e.detail, /reload before saving/);
  assert.deepEqual(describeError(e), { text: e.message, detail: e.detail });
});
test('non-HTTP failures: network and plain errors', () => {
  const n = describeError(new TypeError('Failed to fetch'));
  assert.match(n.text, /kết nối/); assert.equal(n.detail, 'Failed to fetch');
  assert.ok(isVietnamese(describeError(new Error('x')).text) || describeError(new Error('x')).text.length > 0);
  assert.equal(typeof describeError(undefined).text, 'string');
});
test('validation issues are Vietnamese sentences (the dialog of U1-002)', () => {
  const t = issueText({ level: 'warning', code: 'fact_unused', fact: 'f08', message: 'Fact f08 is not used by any chapter.' });
  assert.equal(t.text, 'Dữ kiện f08 chưa chương nào dùng.'); assert.match(t.detail, /Fact f08/);
  assert.match(issueText({ code: 'budget_sum', message: 'The chapter budgets add up to 1800 words; the target is 1500.' }).text, /1800.*1500/);
  assert.match(issueText({ code: 'beat_too_long', beat: 'b0006', message: 'Beat b0006 in c01 has 95 words (more than 90); split it.' }).text, /b0006.*95/);
  assert.match(issueText({ code: 'words_under', message: 'Only 500 words, under 70% of the target 2000.' }).text, /500.*2000/);
  assert.match(issueText({ code: 'outline_stale', message: 'Stale outline approval: x' }).text, /đã đổi sau khi được duyệt/);
  const g = issueText({ code: 'brand_new_code', message: 'Something new happened.' });
  assert.ok(g.generic); assert.equal(g.detail, 'Something new happened.'); assert.ok(isVietnamese(g.text));
  assert.equal(typeof issueText(null).text, 'string');
});
test('every code the server can raise has a Vietnamese sentence', () => {
  const codes = ['no_thesis', 'no_chapters', 'duplicate_chapter', 'chapter_no_title', 'chapter_no_budget', 'duplicate_fact', 'fact_no_source', 'unknown_source_id', 'disputed_no_conflict', 'unknown_fact', 'fact_unused', 'no_hook_choice', 'budget_sum', 'outline_missing', 'outline_not_approved', 'outline_stale', 'chapter_missing', 'empty_chapter', 'chapter_order', 'unknown_chapter', 'empty_beat', 'markup_in_text', 'spoken_chars', 'beat_too_long', 'no_show', 'words_under', 'words_off_target', 'chapter_off_budget', 'length', 'source_share', 'overlap', 'chapter_by_position', 'chapter_twice', 'meta_orphan', 'no_chapter_lines', 'preamble_dropped', 'chapter_empty', 'budget_defaulted', 'no_facts', 'hook_defaulted', 'long_sentence', 'sentence_median',
    /* worker fixscript */ 'source_author_named', 'source_talk', 'fact_for_owner', 'outline_note'];
  for (const code of codes) { const t = issueText({ code, message: 'x', chapter: 'c01', fact: 'f01', beat: 'b1' }); assert.ok(!t.generic, code); assert.ok(isVietnamese(t.text) || /\d|c01|f01|b1/.test(t.text), code); }
});
test('failed model jobs', () => {
  assert.match(jobErrorText({ error_kind: 'timeout', error: 'no answer within 300 seconds' }).text, /không trả lời kịp/);
  assert.match(jobErrorText({ error_kind: 'rate_limit', error: 'rate limit or quota reached (HTTP 429)' }).text, /giới hạn/);
  const v = jobErrorText({ error_kind: 'validation', error: 'Chapter c03 failed validation twice (x).' });
  assert.match(v.text, /Chương c03/); assert.match(v.detail, /failed validation/);
  assert.ok(isVietnamese(jobErrorText({ error_kind: 'weird', error: 'raw' }).text));
  assert.equal(jobErrorText({ error_kind: 'config', error: 'Chưa cài `agy` (Antigravity CLI).' }).detail, '');
  assert.equal(typeof jobErrorText(null).text, 'string');
});
test('a pasted text that could not be read: the reason in Vietnamese', () => {
  assert.match(parseFailText('The outline could not be read. No chapters were found (a chapter starts with a line like: ## c01 COLD OPEN).\nFound 1 paragraph(s):'), /không thấy chương nào/);
  assert.match(parseFailText('The script could not be placed. No narration paragraphs were found.'), /không thấy đoạn lời dẫn/);
  assert.match(parseFailText('The script could not be read. The text is empty.'), /văn bản trống/);
  assert.match(parseFailText('The script could not be placed. The text has no chapter lines (## c01 TITLE) and the outline has 5 chapters.'), /5 chương/);
  assert.ok(isVietnamese(parseFailText('something else entirely')));
});

test('new backend answers: data errors, delete refused while busy, interrupted jobs', () => {
  for (const k of ['timing', 'storyboard', 'script', 'style', 'other']) { const d = describeHttp(409, { detail: 'DataError: x', data_error: k }); assert.ok(isVietnamese(d.text), k); assert.equal(d.detail, 'DataError: x'); }
  assert.match(describeHttp(409, { detail: 'a model job is running for this project; cancel it first (POST /api/jobs/{id}/cancel)', job_id: 'j' }).text, /tác vụ mô hình/);
  assert.match(describeHttp(409, { detail: 'a preview is being rendered for this project; wait for it to finish' }).text, /xem thử/);
  assert.match(jobErrorText({ error_kind: 'interrupted', error: 'the server restarted' }).text, /gián đoạn/);
  assert.match(describeHttp(500, { detail: 'internal error (ValueError)' }).text, /bất ngờ/);
});

// worker claudeprov: the second runner, Claude Code
test('Claude Code failures are Vietnamese sentences the owner can act on', () => {
  const signedOut = 'Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại.';
  for (const code of ['claude_missing', 'claude_auth', 'claude_rate_limit', 'claude_model', 'claude_config', 'claude_error', 'claude_no_result', 'claude_timeout']) {
    const t = stageJobErrorText('draft', { error_code: code });
    assert.ok(isVietnamese(t.text) && t.text.length > 20, code);
    assert.equal(stageErrorText('draft', { body: { code } }).text, t.text, code);
  }
  assert.equal(stageJobErrorText('draft', { error_code: 'claude_auth' }).text, signedOut);
  assert.match(stageJobErrorText('draft', { error_code: 'claude_missing' }).text, /claude auth login/);
  assert.match(stageJobErrorText('draft', { error_code: 'claude_rate_limit' }).text, /Claude Code/);
});
test('a script job that Claude Code failed shows its own sentence, with the time the plan opens again', () => {
  const quota = jobErrorText({ error_kind: 'rate_limit', error: 'Hạn mức của gói Claude Code đã dùng hết hoặc bị giới hạn lượt gọi. Thử lại sau 4 giờ 30 phút (khoảng 18:20).' });
  assert.match(quota.text, /Claude Code.*4 giờ 30 phút/);
  const signedOut = jobErrorText({ error_kind: 'auth', error: 'Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại.' });
  assert.match(signedOut.text, /claude auth login/);
  // the other runners and the key-based providers keep their sentences
  assert.match(jobErrorText({ error_kind: 'auth', error: 'the provider refused the key (HTTP 401)' }).text, /từ chối khóa truy cập/);
  assert.match(jobErrorText({ error_kind: 'rate_limit', error: 'Hạn mức của gói Antigravity đã dùng hết hoặc bị giới hạn lượt gọi. Thử lại sau 2 phút.' }).text, /^Mô hình bị giới hạn/);
});
test('the settings sentence no longer says only agy can run the deep work', () => {
  const t = describeHttp(422, { detail: "Role 'draft' requires an agent model", code: 'agentic_role_needs_agy' });
  assert.match(t.text, /agy hoặc qua Claude Code/);
});

// followups item 2: "Claude Code is too old for this model" has its own code, claude_outdated: it says to update, never to pick another model, never "hết hạn mức"
const OUTDATED_FULL = 'Claude Code trên máy chủ quá cũ cho mô hình này (cần bản 2.1.280 trở lên, đang là 2.1.233). Chạy `claude update` trên máy chủ rồi thử lại.';
const OUTDATED_BARE = 'Claude Code trên máy chủ quá cũ cho mô hình này. Chạy `claude update` trên máy chủ rồi thử lại.';
test('claude_outdated: the draft job and the edit routes have a sentence of their own; with the versions the server gave, those are shown', () => {
  const bare = stageJobErrorText('draft', { error_code: 'claude_outdated' }).text;
  assert.equal(bare, OUTDATED_BARE);
  assert.equal(stageErrorText('draft', { status: 409, body: { code: 'claude_outdated' } }).text, OUTDATED_BARE);
  assert.equal(describeHttp(409, { code: 'claude_outdated', detail: 'x' }).text, OUTDATED_BARE);
  assert.equal(stageJobErrorText('draft', { error_code: 'claude_outdated', error: OUTDATED_FULL }).text, OUTDATED_FULL);
  // a server text that is not that sentence never replaces ours
  assert.equal(stageJobErrorText('draft', { error_code: 'claude_outdated', error: 'Claude Code 2.1.233 does not support this model' }).text, OUTDATED_BARE);
  for (const t of [bare, OUTDATED_FULL]) { assert.match(t, /claude update/); assert.doesNotMatch(t, /hết hạn mức|mô hình khác|chọn agent khác|Dựng tự động/); }
});
test('claude_outdated: a failed script job (kind config) shows the server sentence, and none of these is a quota answer', () => {
  assert.equal(jobErrorText({ error_kind: 'config', error: OUTDATED_FULL }).text, OUTDATED_FULL);
  assert.equal(isQuota({ error_kind: 'config', error: OUTDATED_FULL }), false);
  assert.equal(isQuota({ error_code: 'claude_outdated' }), false);
  assert.equal(isQuota({ error: 'claude_outdated' }), false);
  const turn = turnView({ id: 't1', status: 'failed', error: 'claude_outdated', summary: OUTDATED_FULL, instruction: 'đổi' }, {});
  assert.equal(turn.actions.settings, false);                         // the quota card ("Chọn mô hình khác") is not offered
  assert.equal(turn.headline, OUTDATED_BARE);
  assert.equal(turn.extra, OUTDATED_FULL);
  assert.doesNotMatch(`${turn.headline} ${turn.extra}`, /hết hạn mức/);
});

// worker fixscript: the new checks of the script step say what was found, in Vietnamese, and the sentence limit is the server's
test('the new script checks: a sentence in Vietnamese that carries what was found', () => {
  const a = issueText({ level: 'warning', code: 'source_author_named', chapter: 'c01', beat: 'b0002', names: ['Hodge', 'Payne'], message: 'Beat b0002 in c01 names the author of a source book (Hodge, Payne); the narrator tells it in his own voice, without the name.' });
  assert.ok(isVietnamese(a.text) && /b0002/.test(a.text) && /Hodge, Payne/.test(a.text) && !a.generic);
  const t = issueText({ level: 'warning', code: 'source_talk', chapter: 'c04', beat: 'b0087', found: ['the books'], message: "Beat b0087 in c04 speaks about the sources themselves ('the books')." });
  assert.ok(isVietnamese(t.text) && /b0087/.test(t.text) && /"the books"/.test(t.text) && !t.generic);
  const f = issueText({ level: 'warning', code: 'fact_for_owner', fact: 'f10', found: ['the owner should', 'before it is used'], message: 'Fact f10 has a remark for the owner.' });
  assert.ok(isVietnamese(f.text) && /f10/.test(f.text) && /the owner should/.test(f.text));
  const n = issueText({ level: 'warning', code: 'outline_note', note: 1, message: 'Note for the owner: The paragraph HOD-04 seems to describe another painting.' });
  assert.ok(isVietnamese(n.text) && /HOD-04 seems to describe another painting/.test(n.text) && !/Note for the owner/.test(n.text));
  assert.match(issueText({ code: 'long_sentence', beat: 'b0147', message: 'Beat b0147 in c07 has a sentence with 26 words (more than 25); split it.' }).text, /26 từ.*trên 25 từ/);
});

test('cold-open check issues format clean Vietnamese sentences', () => {
  const cases = [
    ['cold_open_missing_name', { chapter: 'c01', missing: ['title', 'artist'] }],
    ['cold_open_late_name', { chapter: 'c01', late: ['artist'], max_words: 72 }],
    ['cold_open_first_line_long', { chapter: 'c01', beat: 'b0001', words: 36, max: 25 }],
    ['cold_open_no_early_turn', { chapter: 'c01', max_words: 72 }],
    ['cold_open_no_closing_question', { chapter: 'c01', beat: 'b0005' }],
    ['cold_open_roadmap', { chapter: 'c01', beat: 'b0001', found: ['in this video'] }],
    ['cold_open_word_count', { chapter: 'c01', words: 149, min: 60, max: 145 }],
  ];
  for (const [code, args] of cases) {
    const res = issueText({ level: 'warning', code, chapter: args.chapter, beat: args.beat, args });
    assert.ok(isVietnamese(res.text) && !res.generic, `${code} -> ${res.text}`);
  }
});
