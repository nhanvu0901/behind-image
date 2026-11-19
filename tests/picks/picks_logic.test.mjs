// Run on the server with: node --test tests/picks/picks_logic.test.mjs   (pure helpers of the picks view, no DOM)
import test from 'node:test';
import assert from 'node:assert/strict';
import * as L from '../../bti/editor/static/js/views/picks_logic.js';

const doc = () => ({ main_asset: 'A', assets: { A: { width: 2000, height: 3000, regions: {} }, B: {} }, beats: {} });
const chapters = [{ beats: [{ id: 'b1' }, { id: 'b2' }] }, { beats: [{ id: 'b3' }] }];

test('addItem picks a role and marks the beat picked', () => {
  const d = doc();
  d.assets.V = { kind: 'video' };
  assert.equal(L.addItem(d, 'b1', { asset: 'A' }), 0);
  L.addItem(d, 'b1', { asset: 'A', region: 'MIRROR' });
  L.addItem(d, 'b1', { asset: 'B' });
  L.addItem(d, 'b1', { asset: 'V' });
  assert.deepEqual(d.beats.b1.items.map((i) => i.role), ['main', 'detail', 'context', 'video']);
  assert.equal(d.beats.b1.status, 'picked');
});

test('remove, move, skip', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.addItem(d, 'b1', { asset: 'B' });
  assert.equal(L.moveItem(d, 'b1', 0, 1), 1);
  assert.equal(d.beats.b1.items[1].asset, 'A');
  assert.equal(L.moveItem(d, 'b1', 0, -1), 0);
  assert.ok(L.removeItem(d, 'b1', 0) && L.removeItem(d, 'b1', 0));
  assert.equal(d.beats.b1.status, 'todo');
  assert.equal(L.removeItem(d, 'b1', 0), false);
  assert.equal(L.toggleSkip(d, 'b1'), 'skip');
  assert.equal(L.toggleSkip(d, 'b1'), 'todo');
});

test('progress and empty beats', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.toggleSkip(d, 'b3');
  assert.deepEqual(L.chapterProgress(chapters[0], d), { done: 1, total: 2 });
  assert.deepEqual(L.emptyBeats(chapters, d), ['b2']);
});

test('dropAsset clears the items and the main painting', () => {
  const d = doc();
  L.addItem(d, 'b1', { asset: 'A' }); L.addItem(d, 'b1', { asset: 'B' });
  L.dropAsset(d, 'A');
  assert.equal(d.main_asset, null);
  assert.deepEqual(d.beats.b1.items.map((i) => i.asset), ['B']);
});

test('region names', () => {
  assert.ok(L.regionNameOk('D1') && L.regionNameOk('The mirror') && !L.regionNameOk('a/b') && !L.regionNameOk(''));
  assert.equal(L.freeRegionName({}, 'D1'), 'D1');
  assert.equal(L.freeRegionName({ D1: 1, D1_2: 1 }, 'D1'), 'D1_3');
  assert.equal(L.freeRegionName({}, ''), 'VUNG');
  assert.deepEqual(L.regionNameChoices([{ id: 'D1', label: 'x' }, { id: 'D2', label: 'y' }], { D1: {} }), [{ name: 'D2', label: 'y' }]);
});

test('circleFromDrag keeps the centre inside and a minimum radius', () => {
  assert.deepEqual(L.circleFromDrag([100, 100], [130, 140], 2000, 3000), { x: 100, y: 100, rx: 50, ry: 50 });
  assert.equal(L.circleFromDrag([100, 100], [101, 100], 2000, 3000).rx, 8);
  const c = L.circleFromDrag([-5, 4000], [0, 0], 2000, 3000);
  assert.equal(c.x, 0); assert.equal(c.y, 3000);
});

test('cropStyle fills the box with the region', () => {
  const s = L.cropStyle({ width: 2000, height: 3000 }, { x: 1000, y: 1500, rx: 100, ry: 100 }, 64);
  assert.equal(s.backgroundSize, '640px 960px');
  assert.equal(s.backgroundPosition, '-288px -448px');
  assert.equal(L.cropStyle({}, { x: 1, y: 1 }), null);
});

test('show words use the dossier names', () => {
  const w = L.showWords(['D2', 'wide view'], [{ id: 'D2', label: 'Signature' }]);
  assert.deepEqual(w.map((x) => [x.text, x.query, x.detail]), [['D2: Signature', 'Signature', true], ['wide view', 'wide view', false]]);
});

test('sizes', () => {
  assert.equal(L.sizeText(0, 0), 'chưa biết kích thước');
  assert.ok(L.isSmall(800, 600) && !L.isSmall(1300, 1250) && !L.isSmall(0, 0));
});

// ---------------------------------------------------------------- c3picks: "Để agent chọn hình" (the result sentence, the button states, the progress line, the reason under a line)
const autoState = (over = {}) => ({ doc: { main_asset: 'A', assets: { A: {} }, beats: {} }, chapters, job: null, approved: false, narrationOk: true, hasMain: true, agentUsable: true, last: null, ...over });
const settled = () => ({ b1: { items: [{ asset: 'A' }], status: 'picked', note: '' }, b2: { items: [], status: 'skip', note: '' }, b3: { items: [{ asset: 'A' }], status: 'picked', note: '' } });

test('the result sentence: the brief\'s own words, from the numbers', () => {
  assert.equal(L.autoResultText({ lines_total: 28, lines_done: 25, lines_without: [{ no: 3 }, { no: 9 }, { no: 15 }] }), 'Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp.');
  assert.equal(L.autoResultText({ lines_total: 28, lines_done: 28, lines_without: [] }), 'Agent đã chọn hình cho 28/28 đoạn.');
  assert.equal(L.autoResultText({ lines_total: 6, lines_done: 5, lines_without: [{}] }), 'Agent đã chọn hình cho 5/6 đoạn. 1 đoạn chưa có hình phù hợp.');
  assert.equal(L.autoResultText(null), '');
  assert.equal(L.autoResultText({ lines_total: 'x' }), '');
});

test('the second line of a result says what was made, and only what was', () => {
  assert.equal(L.autoDetailText({ pictures_imported: 9, regions_made: 6, clips: 2, lines_kept: 0 }), '9 hình mới, 6 vùng chi tiết, 2 clip.');
  assert.equal(L.autoDetailText({ pictures_imported: 0, regions_made: 0, clips: 0, lines_kept: 3, lines_by_others: 1 }), '3 đoạn dùng lại hình trước, 1 đoạn bạn đã chọn trong lúc đó, agent không đụng tới.');
  assert.equal(L.autoDetailText({}), '');
  assert.deepEqual(L.autoWithout({ lines_without: [{ no: 3, why: 'Không tìm thấy hình nào cho "tro núi lửa".' }] }), [{ no: 3, text: 'Đoạn 3: Không tìm thấy hình nào cho "tro núi lửa".' }]);
});

test('the buttons: nothing done yet', () => {
  const c = L.autoControls(autoState());
  assert.equal(c.running, false);
  assert.deepEqual(c.start, { disabled: false, title: '', confirm: null, body: { beats: null, redo: false } });         // the lines without pictures; nobody is asked
  assert.equal(c.again.visible, false);                                                                                  // "Chọn lại phần còn thiếu" only after a run
  assert.equal(c.cancel.visible, false);
  assert.equal(c.select.disabled, false);
  assert.deepEqual(c.missing, ['b1', 'b2', 'b3']);
});

test('the buttons: after a run that left lines without pictures', () => {
  const d = autoState().doc;
  d.beats = { b1: { items: [{ asset: 'A' }], status: 'picked', note: '' } };
  const c = L.autoControls(autoState({ doc: d, last: { result: { lines_total: 3 } } }));
  assert.equal(c.again.visible, true);
  assert.deepEqual(c.again.body, { beats: ['b2', 'b3'], redo: false });                                                  // the job is started for exactly the lines without pictures
  assert.equal(c.again.disabled, false);
  assert.equal(c.start.confirm, null);
  assert.equal(L.autoControls(autoState({ doc: d, last: { result: {} }, agentUsable: false })).again.disabled, true);
});

test('the buttons: nothing is missing any more, or the picks are approved', () => {
  const d = autoState().doc;
  d.beats = settled();
  let c = L.autoControls(autoState({ doc: d, last: { result: {} } }));
  assert.equal(c.again.visible, false);                                                                                  // nothing left to choose again
  assert.deepEqual(c.start, { disabled: false, title: '', confirm: 'redo', body: { beats: null, redo: true } });          // starting over replaces the pictures: the owner is asked first
  d.beats.b2 = { items: [], status: 'todo', note: '' };
  c = L.autoControls(autoState({ doc: d, approved: true, last: { result: {} } }));
  assert.equal(c.start.confirm, 'redo');
  assert.equal(c.start.body.redo, true);
  assert.deepEqual(c.again.body, { beats: ['b2'], redo: true });                                                         // an approved document needs `redo`, and the approval is dropped: asked
  assert.equal(c.again.confirm, 'approved');
});

test('the buttons: what stops the start, and the reason in words', () => {
  assert.equal(L.autoControls(autoState({ narrationOk: false })).start.title, 'Cần duyệt lời dẫn trước.');
  assert.equal(L.autoControls(autoState({ hasMain: false })).start.title, 'Chọn tranh chính trước.');
  assert.equal(L.autoControls(autoState({ agentUsable: false })).start.title, 'Agent đang chọn chưa dùng được.');
  assert.equal(L.autoControls(autoState({ agentUsable: undefined })).start.disabled, false);                              // the agents are not known yet: the server decides
  for (const over of [{ narrationOk: false }, { hasMain: false }, { agentUsable: false }]) assert.equal(L.autoControls(autoState(over)).start.disabled, true);
});

test('the buttons: while the job runs', () => {
  for (const state of ['queued', 'waiting', 'running']) {
    const c = L.autoControls(autoState({ job: { state }, last: { result: {} } }));
    assert.equal(c.running, true);
    assert.equal(c.start.disabled, true);
    assert.equal(c.start.title, 'Agent đang làm việc.');
    assert.equal(c.cancel.visible, true);
    assert.equal(c.again.visible, false);
    assert.equal(c.select.disabled, true);                                                                               // the agent is not changed under a running job
  }
  for (const state of ['done', 'error', 'cancelled']) assert.equal(L.autoControls(autoState({ job: { state } })).running, false);
});

test('the progress line is the part that works, with its note (and its limits)', () => {
  assert.deepEqual(L.autoProgress(null), { text: '', fraction: 0 });
  assert.deepEqual(L.autoProgress({ state: 'done', parts: [] }), { text: '', fraction: 0 });
  const job = { state: 'running', progress: 0.3, parts: [
    { key: 'plan', title: 'Lập danh sách hình cần tìm (1/4)', state: 'done', note: '' },
    { key: 'search', title: 'Tìm hình (2/4)', state: 'running', note: 'Đang tìm hình 3/12: chân dung họa sĩ' },
    { key: 'choose', title: 'Chọn hình (3/4)', state: 'queued', note: '' }] };
  assert.deepEqual(L.autoProgress(job), { text: 'Tìm hình (2/4) - Đang tìm hình 3/12: chân dung họa sĩ', fraction: 0.3 });
  job.parts[1] = { ...job.parts[1], key: 'plan2', title: 'Lập danh sách hình cần tìm (1/4)', note: 'Agent đang lập danh sách hình: bước 12/80, 3/20 phút.' };
  assert.equal(L.autoProgress({ ...job, parts: [job.parts[1]] }).text, 'Lập danh sách hình cần tìm (1/4) - Agent đang lập danh sách hình: bước 12/80, 3/20 phút.');   // the limits are in the line
  assert.equal(L.autoProgress({ state: 'queued', parts: [], progress: 0 }).text, 'Đang bắt đầu...');
  assert.equal(L.autoProgress({ state: 'waiting', parts: [{ state: 'waiting', title: 'Tìm hình (2/4)', note: '' }], progress: 2 }).fraction, 1);
});

test('the agent\'s reason is shown only while the line is as the agent wrote it', () => {
  const reasons = { b1: 'Mở bằng cả bức tranh.', b2: 'Vẫn cùng ý.' };
  assert.equal(L.autoReasonFor({ items: [{ asset: 'A' }], status: 'picked', note: 'Mở bằng cả bức tranh.' }, reasons, 'b1'), 'Mở bằng cả bức tranh.');
  assert.equal(L.autoReasonFor({ items: [], status: 'skip', note: 'Vẫn cùng ý.' }, reasons, 'b2'), 'Vẫn cùng ý.');                // a line that needs nothing new has a reason too
  assert.equal(L.autoReasonFor({ items: [{ asset: 'A' }], status: 'picked', note: 'Tôi đổi ghi chú.' }, reasons, 'b1'), '');     // the owner changed the note: no longer the agent's
  assert.equal(L.autoReasonFor({ items: [], status: 'todo', note: 'Mở bằng cả bức tranh.' }, reasons, 'b1'), '');               // the pictures were removed
  assert.equal(L.autoReasonFor({ items: [{ asset: 'A' }], status: 'picked', note: 'x' }, reasons, 'b9'), '');
  assert.equal(L.autoReasonFor(undefined, reasons, 'b1'), '');
  assert.equal(L.autoReasonFor({ items: [{ asset: 'A' }], note: '' }, { b1: '' }, 'b1'), '');
});

test('what a written line is still missing is listed apart from the lines left without pictures', () => {
  const result = { lines_without: [{ beat: 'b3', no: 3, why: 'x' }], missing: [
    { beat: 'b3', want: 'b3.1', why: 'Không tìm thấy hình nào cho "tro".' },
    { beat: 'b4', want: 'b4.2', why: 'Đã chọn được hình cho "Kênh đào" nhưng không tải về được.' }, { beat: 'b5', why: '' }, { beat: 'b6' }] };
  assert.deepEqual(L.autoMissing(result), ['Đã chọn được hình cho "Kênh đào" nhưng không tải về được.']);
  assert.deepEqual(L.autoMissing(null), []);
});
