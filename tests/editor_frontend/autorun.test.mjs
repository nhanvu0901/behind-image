// "Chạy tự động" (worker c6auto): the button next to the switch, the progress line, and the one sentence at the end of a run. The sentences of the
// server (bti/auto_run/reasons.py) come from tests/editor_frontend/fixtures/autorun_results.json, which a Python test keeps equal to the server's own list.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { runBody, runButtonView, latestRun, progressText, runMoved, stopPath, endView, isRunning } from '../../bti/editor/static/js/autologic.js';
import { AUTORUN_LABELS as R, AUTO_LABELS } from '../../bti/editor/static/js/labels.js';
import { describeHttp, STAGE_CODES, isVietnamese } from '../../bti/editor/static/js/errmsg.js';

const RESULTS = JSON.parse(fs.readFileSync(new URL('./fixtures/autorun_results.json', import.meta.url), 'utf8'));
const doc = (o = {}) => ({ schema: 'bti.auto/1', rev: 'r1', enabled: true, gates: { outline: true, narration: true, picks: true, storyboard: true }, spend: {}, warnings: [], ...o });
const finished = (res, over = {}) => ({ id: '20261119-142301-a1b2', job_id: 'j1', state: 'finished', outcome: res.outcome, reason: res.reason, sentence: res.sentence, link: res.link, step: res.step, step_label: res.step_label, result: res, ...over });
const running = (live = {}) => ({ id: '20261119-142301-a1b2', job_id: 'j1', state: 'running', live: { step: 'voice', step_label: 'Giọng đọc', n: 3, of: 6, ...live } });

test('the button says "Chạy tự động" and works only while the switch is on and no run goes on', () => {
  assert.equal(R.button, 'Chạy tự động');
  assert.deepEqual(runButtonView(doc(), null), { label: 'Chạy tự động', enabled: true, title: R.buttonTitle.ready });
  assert.equal(runButtonView(doc({ enabled: false }), null).enabled, false);
  assert.equal(runButtonView(doc({ enabled: false }), null).title, R.buttonTitle.off);
  assert.equal(runButtonView(doc(), running()).enabled, false);
  assert.equal(runButtonView(doc(), running()).title, R.buttonTitle.running);
  assert.equal(runButtonView(doc(), null, true).enabled, false);                       // while the click is being answered
  for (const bad of [null, undefined, {}, { enabled: true }, 'x']) assert.equal(runButtonView(bad, null).enabled, false);      // a document the page cannot read counts as off
  assert.equal(runButtonView(doc({ enabled: 'yes' }), null).enabled, false);
});

test('the button sends all the way and no actor: it is the owner who presses it', () => {
  assert.deepEqual(runBody(), { until: null, max_steps: 40 });
  assert.equal('actor' in runBody(), false);
});

test('the progress line names the step the run is at and how many of the six', () => {
  assert.equal(progressText(running()), 'Đang chạy tự động: Giọng đọc (3/6)');
  assert.equal(R.running('Giọng đọc', 2, 6), 'Đang chạy tự động: Giọng đọc (2/6)');
  assert.equal(progressText(running({ step_label: 'Kịch bản', n: 2 })), 'Đang chạy tự động: Kịch bản (2/6)');
  assert.equal(progressText({ id: 'x', state: 'running' }), 'Đang chạy tự động...');          // nothing known yet: the run has just started
  assert.equal(progressText(running({ step_label: null, n: null })), 'Đang chạy tự động...');
  assert.equal(progressText(finished(RESULTS[0])), null);
  assert.equal(progressText(null), null);
  assert.equal(isRunning(running()), true);
  assert.equal(isRunning(finished(RESULTS[0])), false);
});

test('"Dừng" stops the long job of the run', () => {
  assert.equal(R.stop, 'Dừng');
  assert.equal(stopPath(running()), '/api/longjobs/j1/cancel');
  assert.equal(stopPath(null), null);
  assert.equal(stopPath({ job_id: 5 }), null);
});

test('the newest run is the first of the list; the page reads the project again when the run moves on', () => {
  assert.equal(latestRun({ items: [{ id: 'a' }, { id: 'b' }] }).id, 'a');
  assert.equal(latestRun({ items: [] }), null);
  assert.equal(latestRun(null), null);
  assert.notEqual(runMoved(running({ step: 'voice' })), runMoved(running({ step: 'picks' })));
  assert.notEqual(runMoved(running()), runMoved({ ...running(), steps_taken: 2 }));
  assert.notEqual(runMoved(running()), runMoved({ ...running(), state: 'finished' }));
  assert.equal(runMoved(running()), runMoved(running()));
  assert.equal(runMoved(null), '');
});

test('every end the server can make is one sentence of the server, with the heading and the tone of its outcome and a link to its step', () => {
  const tone = { done: 'ok', failed: 'err', needs_owner: 'warn', nothing_to_do: 'warn', cancelled: 'warn', limit: 'warn' };
  assert.equal(RESULTS.length, 22);
  for (const res of RESULTS) {
    const v = endView(finished(res));
    assert.ok(v, res.reason);
    assert.equal(v.tone, tone[res.outcome], res.reason);
    assert.ok(isVietnamese(v.sentence), `${res.reason}: ${v.sentence}`);
    assert.ok(v.heading, res.reason);
    if (res.outcome !== 'failed') assert.equal(v.sentence, res.sentence, res.reason);            // shown as the server wrote it
    if (res.step_label && res.link) assert.deepEqual(v.link, { href: res.link, text: `Mở bước "${res.step_label}"` }, res.reason);
    else assert.equal(v.link, null, res.reason);
  }
});

test('the sentences say where the run stopped and why: the gate, the cost, the warning, what it waits for', () => {
  const by = (r) => endView(finished(RESULTS.find((x) => x.reason === r)));
  assert.match(by('gate_not_allowed').sentence, /cổng duyệt lời dẫn.*Kịch bản/);
  assert.equal(by('gate_not_allowed').link.href, '#/project/arn/script');
  assert.match(by('spend_not_allowed').sentence, /Tạo giọng đọc/);
  assert.match(by('paid_needs_owner').sentence, /tốn tiền/);
  assert.match(by('quality_warning').sentence, /chưa có hình/);
  assert.match(by('quality_warning').link.text, /Chọn hình/);
  assert.match(by('nothing_to_do').sentence, /tranh chính/);
  assert.match(by('busy_elsewhere').sentence, /việc khác/);
  assert.match(by('step_limit').sentence, /40 việc/);
  assert.match(by('cancelled').sentence, /Đã dừng/);
  assert.equal(by('exported').heading, 'Xong');
});

test('a failed step is said with the page\'s own sentence of its code, and a failed job with the job\'s own Vietnamese', () => {
  const action = endView(finished(RESULTS.find((x) => x.reason === 'action_failed')));
  assert.equal(action.sentence, R.failed('Tạo giọng đọc') + describeHttp(422, { code: 'voice_not_configured' }).text);
  assert.match(action.sentence, /^Việc "Tạo giọng đọc" không làm được: /);
  assert.ok(isVietnamese(action.sentence));
  assert.doesNotMatch(action.sentence, /voice_not_configured|this machine/);                   // no code and no English from the server on the page
  const job = endView(finished(RESULTS.find((x) => x.reason === 'job_failed')));
  assert.equal(job.sentence, 'Việc "Tạo giọng đọc" không làm được: Máy đọc giọng bị lỗi.');
  assert.equal(job.tone, 'err');
});

test('a record without a sentence is said with a fallback of the page, never with nothing', () => {
  for (const outcome of ['done', 'needs_owner', 'nothing_to_do', 'failed', 'cancelled', 'limit']) {
    const v = endView({ id: 'x', state: 'finished', outcome });
    assert.equal(v.sentence, R.fallback[outcome]);
    assert.ok(isVietnamese(v.sentence));
    assert.equal(v.link, null);
  }
  const lost = endView({ id: 'x', state: 'finished', outcome: null });                       // a run whose process died: the server says "interrupted" in its sentence; without one the page does
  assert.equal(lost.sentence, R.fallback.interrupted);
  assert.equal(endView(running()), null);
  assert.equal(endView(null), null);
  assert.equal(endView({ id: 'x', state: 'finished', outcome: 'done', sentence: '   ' }).sentence, R.fallback.done);
});

test('a link that is not an address of the page is never made', () => {
  const v = endView(finished(RESULTS[2], { link: 'javascript:alert(1)' }));
  assert.equal(v.link, null);
  assert.equal(endView(finished(RESULTS[2], { link: null })).link, null);
});

test('the refusals of the route have a sentence the owner can read, and the words are in labels.js and errmsg.js', () => {
  for (const [code, re] of [['auto_not_enabled', /Cho agent tự chạy/], ['auto_running', /đang chạy tự động/], ['auto_run_not_found', /không tìm thấy/i]]) {
    const t = STAGE_CODES.autorun[code];
    assert.ok(isVietnamese(t) && re.test(t), code);
    assert.equal(describeHttp(409, { detail: 'x', code }).text, t);
    assert.doesNotMatch(t, /[a-z]_[a-z]/);
  }
  assert.match(describeHttp(409, { detail: 'x', code: 'longjob_running' }).text, /việc dài/);              // the code the route gives for another job of the project
  assert.equal(AUTO_LABELS.title, 'Cho agent tự chạy dự án này');                                      // the switch the button sits beside is untouched
  const texts = [R.button, ...Object.values(R.buttonTitle), R.starting, R.stop, R.stopping, R.close, R.startFail, R.stopFail, ...Object.values(R.fallback), R.running('A', 1, 6), R.link('A'), R.failed('A')];
  for (const t of texts) assert.ok(isVietnamese(t), t);
});

test('the page code of the button is in a block marked c6auto', () => {
  for (const f of ['labels.js', 'errmsg.js']) {
    const src = fs.readFileSync(new URL(`../../bti/editor/static/js/${f}`, import.meta.url), 'utf8');
    assert.match(src, /worker c6auto/, f);
  }
  const sw = fs.readFileSync(new URL('../../bti/editor/static/js/autoswitch.js', import.meta.url), 'utf8');
  assert.match(sw, /c6auto: "Chạy tự động"/);
});
