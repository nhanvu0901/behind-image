// The pure parts of the agent select and of the quota message (agentlogic.js), and the error sentences of the agent routes (errmsg.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  QUOTA_CODES, agentsOf, findAgent, agentLabel, labelForModel, effectiveOf, sourceView, selectView, unavailableNote, canChange, stepBody, projectBody,
  otherAgent, usedAgent, sourceWords, spanWords, quotaSentence, quotaView, isQuota, defaultView, authorLabel, proposalLine,
} from '../../bti/editor/static/js/agentlogic.js';
import { describeHttp, stageErrorText } from '../../bti/editor/static/js/errmsg.js';

const GEM = { id: 'gemini', label: 'Gemini 3.8 Flash', model: 'agy:gemini-3.8-flash-high', available: true, reason: null };
const OPUS = { id: 'opus', label: 'Opus 5.5 High', model: 'claude:claude-opus-5-5@high', available: true, reason: null };
const INFO = { agents: [GEM, OPUS], default: 'gemini', machine_default: null };
const DOWN = { agents: [GEM, { ...OPUS, available: false, reason: 'Claude Code trên máy chủ chưa đăng nhập.' }], default: 'gemini', machine_default: null };
const eff = (id, source, label) => ({ id, label: label || (id === 'opus' ? OPUS.label : GEM.label), model: id === 'opus' ? OPUS.model : GEM.model, source });

test('agents, labels and models', () => {
  assert.deepEqual(agentsOf(INFO).map((a) => a.id), ['gemini', 'opus']);
  assert.deepEqual(agentsOf(null), []);
  assert.deepEqual(agentsOf({ agents: [null, { id: 5 }, { id: 'a' }] }).map((a) => a.id), ['a']);
  assert.equal(findAgent(INFO, 'opus'), OPUS);
  assert.equal(findAgent(INFO, 'nope'), null);
  assert.equal(agentLabel(INFO, 'opus'), 'Opus 5.5 High');
  assert.equal(agentLabel(INFO, 'zzz'), 'zzz');
  assert.equal(agentLabel(INFO, null), '');
  assert.equal(labelForModel(INFO, 'claude:claude-opus-5-5@high'), 'Opus 5.5 High');
  assert.equal(labelForModel(INFO, 'mock'), 'mock');                       // no agent offers it: the model itself, never an empty word
  assert.equal(labelForModel(null, 'agy:x', 'mô hình'), 'mô hình');
});

test('the effective agent of a step', () => {
  assert.equal(effectiveOf({ effective: { script: { id: 'opus' } } }, 'script').id, 'opus');
  assert.equal(effectiveOf({ effective: {} }, 'script'), null);
  assert.equal(effectiveOf(null, 'script'), null);
});

test('where the value comes from, in words (contract section 1)', () => {
  assert.deepEqual(sourceView(eff('opus', 'step')), { key: 'step', text: 'Riêng cho bước này', whole: true });
  assert.deepEqual(sourceView(eff('opus', 'project')), { key: 'project', text: 'Theo dự án', whole: false });
  assert.deepEqual(sourceView(eff('gemini', 'default')), { key: 'default', text: 'Theo mặc định', whole: false });
  assert.equal(sourceView(eff('gemini', 'role')).text, 'Theo mặc định');
  assert.equal(sourceView(null).key, 'loading');
});

test('the select lists the two agents and selects the one that WILL be used', () => {
  const v = selectView(INFO, eff('opus', 'step'));
  assert.deepEqual(v.options.map((o) => [o.value, o.text]), [['gemini', 'Gemini 3.8 Flash'], ['opus', 'Opus 5.5 High']]);
  assert.equal(v.value, 'opus');
  assert.equal(v.disabled, false);
  assert.equal(selectView(INFO, eff('gemini', 'default'), { busy: true }).disabled, true);
});

test('an agent that cannot run is shown, says so, and can still be chosen', () => {
  const v = selectView(DOWN, eff('gemini', 'default'));
  assert.equal(v.options[1].text, 'Opus 5.5 High (chưa dùng được)');
  assert.equal(v.options[1].disabled, false);
  assert.equal(unavailableNote(DOWN, eff('opus', 'step')), 'Opus 5.5 High chưa dùng được: Claude Code trên máy chủ chưa đăng nhập.');
  assert.equal(unavailableNote(DOWN, eff('gemini', 'step')), '');
  assert.equal(unavailableNote(INFO, eff('opus', 'step')), '');
  assert.equal(unavailableNote(INFO, null), '');
});

test('a model that no agent offers (a per-role setting) is shown in a disabled first entry, so the select never lies', () => {
  const v = selectView(INFO, { id: null, label: 'Mock', model: 'mock', source: 'role' });
  assert.deepEqual(v.options[0], { value: '', text: 'Mock (theo cài đặt nâng cao)', disabled: true });
  assert.equal(v.value, '');
  assert.equal(v.options.length, 3);
});

test('before the list arrives the select says so and cannot be used', () => {
  const v = selectView(null, null);
  assert.equal(v.disabled, true);
  assert.equal(v.options[0].text, 'Đang tải...');
});

test('a choice asks the server only when it changes something', () => {
  assert.equal(canChange(INFO, eff('gemini', 'default'), 'opus'), true);
  assert.equal(canChange(INFO, eff('opus', 'step'), 'opus'), false);
  assert.equal(canChange(INFO, eff('gemini', 'default'), 'opus', { busy: true }), false);
  assert.equal(canChange(INFO, eff('gemini', 'default'), 'nope'), false);
  assert.equal(canChange(INFO, eff('gemini', 'default'), ''), false);
});

test('the bodies of PUT /agent: one step, and "Dùng cho cả dự án" (the agent for the project, no step choices)', () => {
  assert.deepEqual(stepBody('script', 'opus', 'r1'), { steps: { script: 'opus' }, base_rev: 'r1' });
  assert.deepEqual(projectBody('opus', 'r1'), { agent: 'opus', steps: null, base_rev: 'r1' });
});

test('the other agent: by id, and by model for a model no agent lists', () => {
  assert.equal(otherAgent(INFO, { id: 'opus', model: OPUS.model }), GEM);
  assert.equal(otherAgent(INFO, { id: 'gemini', model: GEM.model }), OPUS);
  assert.equal(otherAgent(INFO, { id: null, model: GEM.model }), OPUS);          // a model an agent owns, named without the id
  assert.equal(otherAgent(INFO, { id: null, model: 'mock' }), GEM);
  assert.equal(otherAgent({ agents: [GEM] }, { id: 'gemini', model: GEM.model }), null);
  assert.equal(otherAgent(null, { id: 'x' }), null);
});

test('the agent a job or a turn used', () => {
  assert.deepEqual(usedAgent(INFO, { agent: { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model } }), { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model });
  assert.equal(usedAgent(INFO, { meta: { agent: { id: 'gemini', label: 'Gemini 3.8 Flash', model: GEM.model } } }).id, 'gemini');
  assert.deepEqual(usedAgent(INFO, { model: OPUS.model }), { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model });          // an old record: the agent that owns its model
  assert.deepEqual(usedAgent(INFO, { model: 'mock' }), { id: null, label: 'mock', model: 'mock' });
  assert.deepEqual(usedAgent(null, {}), { id: null, label: '', model: null });
});

test('the source line names the agent by its label, not the raw model id', () => {
  assert.equal(sourceWords(INFO, { kind: 'model', model: OPUS.model }), 'Opus 5.5 High');
  assert.equal(sourceWords(INFO, { kind: 'model', model: GEM.model }), 'Gemini 3.8 Flash');
  assert.equal(sourceWords(null, { kind: 'model', model: 'agy:x' }), 'agy:x');
  assert.equal(sourceWords(INFO, { kind: 'model', model: '' }), 'mô hình');
  assert.equal(sourceWords(INFO, { kind: 'paste' }), 'dán vào');
  assert.equal(sourceWords(INFO, { kind: 'manual' }), 'viết tay');
});

test('time words: the two largest units', () => {
  assert.equal(spanWords(16200), '4 giờ 30 phút');
  assert.equal(spanWords(3600), '1 giờ');
  assert.equal(spanWords(3 * 86400 + 5 * 3600 + 60), '3 ngày 5 giờ');
  assert.equal(spanWords(86400), '1 ngày');
  assert.equal(spanWords(120), '2 phút');
  assert.equal(spanWords(5), '1 phút');
  assert.equal(spanWords(0), '1 phút');
  assert.equal(spanWords(16199), '4 giờ 30 phút');                       // rounded up: a second gone does not turn 4 h 30 into 4 h 29
  assert.equal(spanWords(16201), '4 giờ 31 phút');
});

test('the quota sentence is the one of the contract: the agent and the time', () => {
  assert.equal(quotaSentence('Opus 5.5 High', { retry_after_seconds: 16200 }), 'Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút.');
});

test('the time left is counted from when the answer came', () => {
  const now = new Date('2026-11-18T12:00:00');
  assert.equal(quotaSentence('Opus 5.5 High', { retry_after_seconds: 16200, since: new Date(now.getTime() - 3600 * 1000) }, now), 'Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 3 giờ 30 phút.');
  assert.equal(quotaSentence('Opus 5.5 High', { retry_after_seconds: 600, since: now.getTime() - 590 * 1000 }, now), 'Opus 5.5 High đã hết hạn mức, có thể đã mở lại, bạn thử lại được.');
});

test('without seconds the clock time is used; without anything it says it does not know', () => {
  assert.equal(quotaSentence('Gemini 3.8 Flash', { retry_at: '18:20' }), 'Gemini 3.8 Flash đã hết hạn mức, mở lại lúc 18:20.');
  assert.equal(quotaSentence('Gemini 3.8 Flash', { retry_at: '25/11 14:20' }), 'Gemini 3.8 Flash đã hết hạn mức, mở lại lúc 14:20 ngày 25/11.');
  for (const q of [{}, { retry_after_seconds: null }, { retry_after_seconds: 0 }, { retry_after_seconds: 'abc', retry_at: 'soon' }, { retry_at: '' }]) {
    assert.equal(quotaSentence('Gemini 3.8 Flash', q), 'Gemini 3.8 Flash đã hết hạn mức, chưa rõ khi nào mở lại.', JSON.stringify(q));
  }
  assert.match(quotaSentence('', { retry_after_seconds: 600 }), /^Agent đã hết hạn mức/);
});

test('the quota view: the sentence, ONE button naming the other agent', () => {
  const rec = { agent: { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model }, retry_after_seconds: 16200 };
  const v = quotaView(INFO, rec);
  assert.equal(v.sentence, 'Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ 30 phút.');
  assert.equal(v.button, 'Chuyển sang Gemini 3.8 Flash và chạy lại');
  assert.equal(v.other, GEM);
  assert.equal(v.canSwitch, true);
  assert.equal(v.why, '');
  const g = quotaView(INFO, { agent: { id: 'gemini', label: 'Gemini 3.8 Flash', model: GEM.model } });
  assert.equal(g.button, 'Chuyển sang Opus 5.5 High và chạy lại');
  assert.equal(g.sentence, 'Gemini 3.8 Flash đã hết hạn mức, chưa rõ khi nào mở lại.');
});

test('the quota view counts the time from the end of the job (`finished`, seconds)', () => {
  const now = new Date('2026-11-18T12:00:00');
  const v = quotaView(INFO, { agent: { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model }, retry_after_seconds: 16200, finished: (now.getTime() - 1800 * 1000) / 1000 }, now);
  assert.equal(v.sentence, 'Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 4 giờ.');
});

test('the other agent that cannot run: the button cannot be pressed and the reason is said', () => {
  const v = quotaView(DOWN, { agent: { id: 'gemini', label: 'Gemini 3.8 Flash', model: GEM.model } });
  assert.equal(v.button, 'Chuyển sang Opus 5.5 High và chạy lại');
  assert.equal(v.canSwitch, false);
  assert.equal(v.why, 'Opus 5.5 High cũng chưa dùng được: Claude Code trên máy chủ chưa đăng nhập.');
});

test('with only one agent there is nothing to switch to; before the list arrives the used agent still comes from the record', () => {
  const v = quotaView({ agents: [GEM] }, { agent: { id: 'gemini', label: 'Gemini 3.8 Flash', model: GEM.model } });
  assert.equal(v.other, null);
  assert.equal(v.button, '');
  assert.equal(v.why, 'Chưa có agent khác để chuyển sang.');
  assert.equal(quotaView(null, { agent: { id: 'opus', label: 'Opus 5.5 High', model: OPUS.model }, retry_after_seconds: 60 }).sentence, 'Opus 5.5 High đã hết hạn mức, mở lại sau khoảng 1 phút.');
});

test('which failures are a quota answer', () => {
  assert.deepEqual([...QUOTA_CODES].sort(), ['agy_rate_limit', 'claude_rate_limit', 'rate_limit']);
  assert.equal(isQuota({ error_kind: 'rate_limit' }), true);
  assert.equal(isQuota({ error_code: 'claude_rate_limit' }), true);
  assert.equal(isQuota({ error: 'agy_rate_limit' }), true);
  assert.equal(isQuota({ error_kind: 'timeout' }), false);
  assert.equal(isQuota({ error: 'Hạn mức đã hết.' }), false);
  assert.equal(isQuota(null), false);
});

test('the default agent of the settings box: the machine default, else the one the file calls default', () => {
  assert.equal(defaultView(INFO).value, 'gemini');
  assert.equal(defaultView({ ...INFO, machine_default: 'opus' }).value, 'opus');
  assert.equal(defaultView({ ...INFO, machine_default: 'gone' }).value, 'gemini');
  assert.deepEqual(defaultView(DOWN).options.map((o) => o.text), ['Gemini 3.8 Flash', 'Opus 5.5 High (chưa dùng được)']);
  assert.equal(defaultView(null).disabled, true);
});

test('the error sentences of the agent routes are Vietnamese; an agent that cannot run keeps the server sentence', () => {
  const sentence = 'Claude Code trên máy chủ chưa đăng nhập. Hãy đăng nhập một lần trên máy chủ bằng lệnh `claude auth login`, rồi thử lại.';
  assert.equal(describeHttp(409, { detail: sentence, code: 'agent_unavailable', agent: { id: 'opus' } }).text, sentence);
  assert.equal(describeHttp(409, { detail: 'not available', code: 'agent_unavailable' }).text, 'Agent đang chọn chưa dùng được trên máy này.');
  assert.match(stageErrorText('settings', { status: 422, body: { code: 'unknown_agent', detail: 'unknown agent' } }).text, /Agent này không có trong danh sách/);
  assert.match(describeHttp(422, { code: 'unknown_step', detail: 'x' }).text, /Bước này không có/);
});

// ---- followups item 1: the list of proposals shows the agent by its label, never the stored id
test('the author of a proposal is the agent label; "human" is Bạn; other text stays as stored', () => {
  assert.equal(authorLabel(INFO, 'agent:claude:claude-opus-5-5@high'), 'Opus 5.5 High');
  assert.equal(authorLabel(INFO, 'agent:agy:gemini-3.8-flash-high'), 'Gemini 3.8 Flash');
  assert.equal(authorLabel(INFO, 'agent:opus'), 'Opus 5.5 High');                      // the stored form may also be the agent's id
  assert.equal(authorLabel(INFO, 'agent:auto'), 'Dựng tự động');
  assert.equal(authorLabel(INFO, 'human'), 'Bạn');
  assert.equal(authorLabel(INFO, 'Human'), 'Bạn');
  assert.equal(authorLabel(INFO, 'Nguyễn Văn A'), 'Nguyễn Văn A');                       // an old free-text name
  assert.equal(authorLabel(INFO, ''), '');
  assert.equal(authorLabel(INFO, null), '');
  assert.equal(authorLabel(INFO, undefined), '');
  assert.equal(authorLabel(INFO, { x: 1 }), '');
});

test('an agent the list does not offer (or a list that did not load) never shows the raw "agent:" id', () => {
  assert.equal(authorLabel(INFO, 'agent:agy:other-y'), 'Agent other-y');
  assert.equal(authorLabel(null, 'agent:claude:claude-opus-5-5@high'), 'Agent claude-opus-5-5@high');
  assert.equal(authorLabel({}, 'agent:test'), 'Agent test');
  for (const a of ['agent:claude:claude-opus-5-5@high', 'agent:agy:zzz', 'agent:auto', 'agent:test']) assert.ok(!/agent:/.test(authorLabel(null, a)), a);
});

test('the grey line of a proposal: author label, time, id; empty parts are left out', () => {
  const p = { id: 'draft_20261118', author: 'agent:claude:claude-opus-5-5@high', created_at: '2026-11-18T10:00:00' };
  assert.equal(proposalLine(INFO, p), 'Opus 5.5 High | 2026-11-18T10:00:00 | draft_20261118');
  assert.equal(proposalLine(INFO, p, false), 'Opus 5.5 High | 2026-11-18T10:00:00');
  assert.equal(proposalLine(INFO, { id: 'x', author: null, created_at: null }), 'x');   // no "null | null | x"
});

test('proposals.js builds both author lines through proposalLine, and prints p.author nowhere', async () => {
  const fs = await import('node:fs');
  const src = fs.readFileSync(new URL('../../bti/editor/static/js/proposals.js', import.meta.url), 'utf8');
  assert.equal((src.match(/proposalLine\(/g) || []).length, 2, 'the list and the opened proposal both use proposalLine');
  assert.ok(!/\.author\b/.test(src), 'no raw .author is read in proposals.js');
});
