// Phase 2: the words of steps 3 to 6 live in labels.js and errmsg.js (one place), and every error code the stage packages can
// answer or raise has a Vietnamese sentence there.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { STAGE_CODES, stageErrorText, stageJobErrorText, describeHttp, isVietnamese } from '../../bti/editor/static/js/errmsg.js';
import { VOICE_LABELS, PICKS_LABELS, EXPORT_LABELS, DRAFT_LABELS, STEP_WORK, flagLabel } from '../../bti/editor/static/js/labels.js';
import { stepView } from '../../bti/editor/static/js/stepper.js';

const ROOT = new URL('../../', import.meta.url).pathname;
const ALL = Object.assign({}, ...Object.values(STAGE_CODES));

test('every sentence is Vietnamese and ends like a sentence', () => {
  for (const [stage, table] of Object.entries(STAGE_CODES)) for (const [code, text] of Object.entries(table)) {
    assert.ok(isVietnamese(text), `${stage}.${code}: ${text}`);
    assert.doesNotMatch(text, /[a-z]_[a-z]/, `${stage}.${code} shows an id`);
  }
});

function pyCodes() {
  const out = new Set();
  const walk = (d) => { for (const f of fs.readdirSync(d, { withFileTypes: true })) { const p = path.join(d, f.name); if (f.isDirectory()) { if (f.name !== '__pycache__') walk(p); } else if (f.name.endsWith('.py')) scan(p); } };
  const scan = (p) => {
    const src = fs.readFileSync(p, 'utf8');
    for (const m of src.matchAll(/\bcode\s*=\s*["']([a-z_]+)["']/g)) out.add(m[1]);
    for (const m of src.matchAll(/PartError\(\s*["']([a-z_]+)["']/g)) out.add(m[1]);
  };
  for (const d of ['bti/voice', 'bti/picks', 'bti/draft', 'bti/export']) walk(path.join(ROOT, d));
  for (const f of ['voice_api', 'picks_api', 'draft_api', 'export_api']) scan(path.join(ROOT, 'bti/editor', f + '.py'));
  return out;
}
// codes that are answered with a sentence of their own, or that never reach the owner
const OK_WITHOUT = new Set(['stale', 'not_found', 'busy', 'data_error']);

test('every code of the stage packages has a Vietnamese sentence', () => {
  const missing = [...pyCodes()].filter((c) => !ALL[c] && !OK_WITHOUT.has(c));
  assert.deepEqual(missing, []);
});

test('real_models_off (test mode refuses models and outside services) has a sentence for every stage that can answer it', () => {
  for (const stage of ['draft', 'picks', 'voice', 'export']) {
    const t = stageErrorText(stage, { status: 409, body: { code: 'real_models_off' } }).text;
    assert.match(t, /chế độ thử/, stage);
    assert.ok(isVietnamese(t));
  }
  assert.match(stageJobErrorText('picks', { error_code: 'real_models_off' }).text, /chế độ thử/);
  assert.match(describeHttp(409, { detail: 'x', code: 'real_models_off' }).text, /chế độ thử/);
});

test('stage tables win over the shared one, and a failed job speaks through its error_code', () => {
  assert.match(stageErrorText('picks', { status: 409, body: { code: 'busy' } }).text, /gợi ý/);
  assert.match(stageErrorText('export', { status: 409, body: { code: 'busy' } }).text, /xuất video/);
  assert.match(stageErrorText('draft', { status: 409, body: { code: 'busy' } }).text, /bản nháp/);
  assert.match(stageErrorText('voice', { status: 409, body: { code: 'part_timeout' } }).text, /quá lâu/);
  assert.match(stageJobErrorText('export', { error_code: 'render_failed', error: 'x' }).text, /Dựng hình/);
  assert.match(stageJobErrorText('voice', { error_code: 'interrupted' }).text, /khởi động lại/);
  assert.match(stageJobErrorText('voice', { error: 'Lỗi gì đó.' }).text, /Lỗi gì đó/);
});

test('codes that belong to one stage are understood everywhere (describeHttp)', () => {
  assert.match(describeHttp(422, { detail: 'x', code: 'voice_not_configured' }).text, /giọng đọc/);
  assert.match(describeHttp(422, { detail: 'x', code: 'accept_all_required' }).text, /cả đề xuất/);
  assert.match(describeHttp(409, { detail: 'x', code: 'longjob_running' }).text, /việc dài/);
});

test('DATA_ERROR knows the new documents', () => {
  for (const k of ['voice', 'picks', 'export', 'draft']) assert.match(describeHttp(409, { detail: 'x', data_error: k }).text, /hỏng/, k);
});

test('label tables exist for the four stages and the advisory flags', () => {
  assert.ok(VOICE_LABELS.state.done && VOICE_LABELS.job.waiting && VOICE_LABELS.reason.never_built);
  assert.ok(PICKS_LABELS.flag.small && PICKS_LABELS.role.main && PICKS_LABELS.tabs.main);
  assert.ok(EXPORT_LABELS.job.done && EXPORT_LABELS.report.duration);
  assert.ok(DRAFT_LABELS.title && DRAFT_LABELS.partState.waiting);
  assert.equal(flagLabel('small'), 'Ảnh nhỏ');
  assert.equal(flagLabel(null), '');
  assert.match(PICKS_LABELS.issue.asset_flag({ asset: 'A', flag: 'small' }), /Ảnh nhỏ/);
});

test('the stepper says when a stage is running or out of date', () => {
  assert.equal(stepView({ id: 'voice', label: 'Giọng đọc', state: 'available', work: 'running' }).tag, STEP_WORK.running);
  assert.equal(stepView({ id: 'picks', label: 'Chọn hình', state: 'available', work: 'stale' }).tag, STEP_WORK.stale);
  assert.equal(stepView({ id: 'picks', label: 'Chọn hình', state: 'locked', work: 'stale' }).tag, 'Khóa');
  assert.equal(stepView({ id: 'voice', label: 'Giọng đọc', state: 'done', work: 'done' }).tag, 'Xong');
});

test('the shell wires the three stage views and the index links their style sheets', () => {
  const app = fs.readFileSync(path.join(ROOT, 'bti/editor/static/js/app.js'), 'utf8');
  for (const v of ['voice', 'picks', 'export']) assert.match(app, new RegExp(`${v}: \\(\\) => import\\('./views/${v}.js'\\)`));
  assert.doesNotMatch(app, /kind: 'planned'/);
  const html = fs.readFileSync(path.join(ROOT, 'bti/editor/static/index.html'), 'utf8');
  for (const c of ['voice', 'picks', 'export']) assert.match(html, new RegExp(`css/${c}.css`));
});
