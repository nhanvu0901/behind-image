import test from 'node:test';
import assert from 'node:assert/strict';
import { describeHttp, renderFailText, jobFailText } from '../../bti/editor/static/js/errmsg.js';
import { validateValue, patternRegex, countProblem } from '../../bti/editor/static/js/formgen.js';
import { agyProblem } from '../../bti/editor/static/js/labels.js';

const VI = /[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]/i;

test('the new codes of the API have a Vietnamese sentence (no status number, no raw text)', () => {
  const cases = [
    [409, { detail: 'a save of this project is in progress; try again in a moment', code: 'project_busy' }, /vài giây/],
    [422, { detail: 'request body nested too deep', code: 'too_deep' }, /lồng quá sâu/],
    [409, { detail: "project.json of 'x' is damaged", data_error: 'project', code: 'project_file_damaged' }, /sửa hoặc xóa thư mục/],
    [422, { detail: 'x', code: 'undrawable', undrawable: true, issues: [] }, /không vẽ được/],
    [422, { detail: 'x', code: 'render_failed', shot: 's0012', technique: 'CAM-01' }, /s0012.*CAM-01/],
    [409, { detail: 'x', data_error: 'source' }, /Văn bản nguồn/],
    [409, { detail: 'x', data_error: 'library' }, /thư viện/],
    [409, { detail: 'x', data_error: 'project' }, /project\.json/],
    [404, { detail: 'project not found' }, /Không có dự án/],
  ];
  for (const [st, body, re] of cases) {
    const d = describeHttp(st, body);
    assert.match(d.text, VI);
    assert.match(d.text, re, JSON.stringify(body));
    assert.doesNotMatch(d.text, /\b(40\d|42\d)\b|undefined/);
  }
});

test('render_failed names the shot, and the overlay and technique when given', () => {
  assert.match(renderFailText({ shot: 's0007', overlay: 'o2', technique: 'X-LAY-01' }), /shot s0007, lớp phủ o2 \(kỹ thuật X-LAY-01\)/);
  assert.match(renderFailText({}), /một shot/);
  assert.match(jobFailText({ error: 'render failed', error_code: 'render_failed', shot: 's0003' }).text, /s0003/);
  assert.doesNotMatch(jobFailText({ error: 'something odd' }).text, /something odd/);
});

test('a string with a pattern is marked before saving and shows the registry hint', () => {
  const d = { type: 'string', name: 'tiles', pattern: '[1-8]x[1-8]', pattern_hint: 'Số cột x số hàng, ví dụ 4x2' };
  assert.equal(validateValue(d, '4x2'), null);
  assert.equal(validateValue(d, '9x9'), 'Số cột x số hàng, ví dụ 4x2');
  assert.equal(validateValue(d, '4x2 extra'), 'Số cột x số hàng, ví dụ 4x2');
  assert.equal(validateValue({ type: 'text', pattern: '[a-z]+' }, 'ABC'), 'chưa đúng dạng cần nhập');
  assert.equal(patternRegex('(?i)abc'), null, 'a Python-only flag is skipped (the server checks)');
  assert.equal(validateValue({ type: 'string', pattern: '(?i)abc' }, 'zzz'), null);
});

test('lines: count limits and the pattern of every line', () => {
  const d = { type: 'lines', min_items: 2, max_items: 3, pattern: '[a-z]+', pattern_hint: 'Chỉ chữ thường' };
  assert.match(validateValue(d, ['a']), /ít nhất 2 mục \(hiện có 1\)/);
  assert.match(validateValue(d, ['a', 'b', 'c', 'd']), /nhiều nhất 3/);
  assert.match(validateValue(d, ['a', 'B']), /dòng 2: Chỉ chữ thường/);
  assert.equal(validateValue(d, ['a', 'b']), null);
});

test('points: exactly N items, and numeric_only refuses region names', () => {
  const d = { type: 'points', min_items: 4, max_items: 4, numeric_only: true };
  assert.match(validateValue(d, [[0, 0], [1, 1], [2, 2]]), /đúng 4 mục \(hiện có 3\)/);
  assert.match(validateValue(d, [[0, 0], [1, 1], [2, 2], 'face']), /chỉ nhập hai số/);
  assert.equal(validateValue(d, [[0, 0], [1, 1], [2, 2], [3, 3]]), null);
  assert.match(validateValue({ type: 'point', numeric_only: true }, 'face'), /chỉ nhập hai số/);
  assert.equal(validateValue({ type: 'point' }, 'face'), null);
  assert.equal(countProblem({}, 99), null);
});

test('a box must lie in the canvas and be at least 16 px', () => {
  const d = { type: 'box' };
  assert.equal(validateValue(d, [100, 100, 500, 400]), null);
  assert.match(validateValue(d, [100, 100, 110, 400]), /ít nhất 16 px/);
  assert.match(validateValue(d, [0, 0, 3000, 400]), /1920 x 1080/);
});

test('the model list flag: Antigravity not answering is named in words', () => {
  assert.equal(agyProblem([{ id: 'mock' }, { id: 'agy:x', agy: { ok: true } }]), null);
  assert.match(agyProblem([{ id: 'agy:x', agy: { ok: false, reason: 'timeout' } }]), /không trả lời kịp/);
  assert.match(agyProblem([{ id: 'agy:x', agy: { ok: false, reason: 'config' } }]), /chưa cài/);
  assert.match(agyProblem([{ id: 'agy:x', agy: { ok: false, reason: 'weird' } }]), /không trả lời/);
});
