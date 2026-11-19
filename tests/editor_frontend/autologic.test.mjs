// The switch "Cho agent tự chạy dự án này" (worker c5cli): which gates an agent may approve in a project, and what the page shows and sends.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { GATES, autoView, summary, switchBody, gateBody, buttonTitle, needsOwner, isStale, NEEDS_OWNER_CODES } from '../../bti/editor/static/js/autologic.js';
import { AUTO_LABELS as L } from '../../bti/editor/static/js/labels.js';
import { describeHttp } from '../../bti/editor/static/js/errmsg.js';

const doc = (o = {}) => ({ schema: 'bti.auto/1', rev: 'r1', enabled: false, gates: { outline: true, narration: true, picks: true, storyboard: true }, spend: { model: true, machine_time: true, paid: false }, warnings: [], ...o });

test('the four gates are the server\'s four, in the order of the pipeline', () => {
  const src = fs.readFileSync(new URL('../../bti/auto.py', import.meta.url), 'utf8');
  const py = /^GATES = \(([^)]*)\)/m.exec(src)[1].split(',').map((x) => x.trim().replace(/"/g, '')).filter(Boolean);
  assert.deepEqual(GATES, py);
  assert.deepEqual(GATES, ['outline', 'narration', 'picks', 'storyboard']);
});

test('by default the switch is off, the boxes are shown ticked but cannot be changed, and every gate is the owner\'s', () => {
  const v = autoView(doc());
  assert.equal(v.ready, true); assert.equal(v.enabled, false); assert.equal(v.gatesDisabled, true);
  assert.deepEqual(v.gates.map((g) => [g.id, g.checked]), GATES.map((g) => [g, true]));
  assert.equal(v.summary, 'Tắt: mọi cổng do bạn duyệt trên trang.');
  assert.equal(v.button, 'Agent tự chạy: tắt');
});

test('turned on, the boxes can be changed and the summary names the gates the owner allowed', () => {
  const v = autoView(doc({ enabled: true, gates: { outline: true, narration: false, picks: true, storyboard: false } }));
  assert.equal(v.enabled, true); assert.equal(v.gatesDisabled, false);
  assert.deepEqual(v.gates.map((g) => g.checked), [true, false, true, false]);
  assert.equal(v.summary, 'Bật: agent được tự duyệt dàn ý, chọn hình.');
  assert.equal(v.button, 'Agent tự chạy: bật');
  assert.equal(summary(doc({ enabled: true, gates: { outline: false, narration: false, picks: false, storyboard: false } })), L.summary.onNone);
  assert.equal(summary(doc({ enabled: true })), 'Bật: agent được tự duyệt dàn ý, lời dẫn, chọn hình, storyboard.');
});

test('a document the page cannot read counts as off, never as on', () => {
  for (const bad of [null, undefined, {}, { enabled: true }, { rev: 'r', enabled: true }, 'x', { rev: 5, gates: {} }]) {
    const v = autoView(bad);
    assert.equal(v.ready, false); assert.equal(v.enabled, false); assert.equal(v.button, L.button.off); assert.deepEqual(v.gates, []);
    assert.equal(summary(bad), L.summary.off);
  }
  assert.equal(autoView(doc({ enabled: 'yes' })).enabled, false);                          // only a real true switches it on
  assert.equal(autoView(doc({ gates: { outline: 'yes' } })).gates[0].checked, false);
});

test('the switch sends only `enabled` and the boxes only their own gate, with the revision the page holds', () => {
  assert.deepEqual(switchBody('r1', true), { base_rev: 'r1', enabled: true });
  assert.deepEqual(switchBody('r1', false), { base_rev: 'r1', enabled: false });
  assert.deepEqual(switchBody('r1', 'yes'), { base_rev: 'r1', enabled: false });
  assert.deepEqual(gateBody('r2', 'picks', false), { base_rev: 'r2', gates: { picks: false } });
  assert.deepEqual(gateBody('r2', 'storyboard', true), { base_rev: 'r2', gates: { storyboard: true } });
  assert.equal(gateBody('r2', 'lunch', true), null);
  for (const b of [switchBody('r', true), gateBody('r', 'outline', true)]) assert.equal('actor' in b, false);    // the page sends no actor: it is the owner
  for (const b of [switchBody('r', true), gateBody('r', 'outline', true)]) assert.equal('spend' in b, false);    // money is never offered
});

test('the words: the title, the four gates, and the line that money is the owner\'s', () => {
  assert.equal(L.title, 'Cho agent tự chạy dự án này');
  assert.equal(L.switchLabel, 'Cho agent tự chạy dự án này');
  assert.equal(L.money, 'Việc tốn tiền luôn cần bạn.');
  assert.deepEqual(GATES.map((g) => L.gate[g]), ['Duyệt dàn ý', 'Duyệt lời dẫn', 'Duyệt chọn hình', 'Duyệt storyboard']);
  assert.notEqual(buttonTitle(doc()), buttonTitle(doc({ enabled: true })));
  const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;
  for (const t of [L.title, L.gatesTitle, L.hint, L.money, L.saved, L.saveFail, L.loadFail, L.summary.off, L.summary.onNone, L.buttonTitle.on, L.buttonTitle.off]) assert.match(t, VI);
});

test('the refusals of the rule have a Vietnamese sentence and are told apart from a stale revision', () => {
  for (const code of NEEDS_OWNER_CODES) {
    const t = describeHttp(403, { code, detail: 'English', fix: 'x', retry: 'after_fix' }).text;
    assert.match(t, /chủ dự án|bạn/, code); assert.doesNotMatch(t, /[A-Za-z]{4,}_[a-z]+/, code);
  }
  assert.match(describeHttp(403, { code: 'gate_needs_human', detail: 'x' }).text, /Cho agent tự chạy dự án này/);
  assert.equal(needsOwner({ body: { code: 'gate_needs_human' } }), true);
  assert.equal(needsOwner({ body: { code: 'stale' } }), false);
  assert.equal(isStale({ status: 409, body: { code: 'stale' } }), true);
  assert.equal(isStale({ status: 409, body: { code: 'stale_revision' } }), true);
  assert.equal(isStale({ status: 403, body: { code: 'gate_needs_human' } }), false);
  assert.equal(isStale(null), false);
});

test('the control is in the page: a button in the top bar, hidden until a project is open', () => {
  const html = fs.readFileSync(new URL('../../bti/editor/static/index.html', import.meta.url), 'utf8');
  assert.match(html, /<button id="btn-auto"[^>]*hidden/);
  const app = fs.readFileSync(new URL('../../bti/editor/static/js/app.js', import.meta.url), 'utf8');
  assert.match(app, /mountAutoButton/); assert.match(app, /autoButton\?\.sync/);
  const sw = fs.readFileSync(new URL('../../bti/editor/static/js/autoswitch.js', import.meta.url), 'utf8');
  assert.match(sw, /\/auto/); assert.doesNotMatch(sw, /actor/);                           // the page never names an actor: the server takes it for the owner
});
