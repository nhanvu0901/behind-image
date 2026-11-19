// The rows of the simple page of step 4 (c4pages): captions, the first sentence, the count of lines without a picture, the header, the three lists.
import test from 'node:test';
import assert from 'node:assert/strict';
import { splitSentence, captionOf, voiceStarts, pickRows, nextMissing, headerNumbers, approveState, pageBlocker, sectionsOf, selectedNumbers, regionLabel }
  from '../../bti/editor/static/js/views/picks_rows_logic.js';
import { PICKS_PAGE_LABELS as W, PICKS_AUTO_LABELS } from '../../bti/editor/static/js/labels.js';

const assets = {
  MAIN: { title: 'The Scream', kind: 'image', regions: { FACE: { x: 1, y: 1, rx: 5, ry: 5, label: 'Khuôn mặt' }, SKY: { x: 2, y: 2, rx: 5, ry: 5, label: 'Bầu trời' }, R1: { x: 3, y: 3, rx: 5, ry: 5, label: 'R1' } }, credit: {} },
  DIARY: { title: 'Trang nhật ký', kind: 'image', regions: {}, credit: { flag: 'unknown' } },
  MAP: { title: 'Bản đồ Oslo', kind: 'image', regions: {}, credit: {} },
  CLIP: { title: 'Vịnh Oslo', kind: 'video', duration: 6.2, regions: {}, credit: {} },
};
const chapters = [
  { id: 'c1', title: 'Mở đầu', beats: [{ id: 'b1', text: 'Một hình người đứng trên cầu, hai tay áp lên đầu. Ai cũng nhận ra nó.' }, { id: 'b2', text: 'Munch viết trong nhật ký về một buổi chiều đi dạo.' }] },
  { id: 'c2', title: 'THE_SKY', beats: [{ id: 'b3', text: 'Có ba cách giải thích bầu trời đỏ.' }, { id: 'b4', text: 'Đoạn thứ tư không cần hình.' }, { id: 'b5', text: 'Đoạn cuối.' }] },
];
const doc = {
  main_asset: 'MAIN', assets,
  beats: {
    b1: { items: [{ asset: 'MAIN', region: null, role: 'main' }, { asset: 'MAIN', region: 'FACE', role: 'detail' }], status: 'picked', note: 'Mở bằng cả bức tranh rồi vào khuôn mặt.' },
    b2: { items: [{ asset: 'DIARY', role: 'context' }, { asset: 'CLIP', role: 'video' }, { asset: 'MAP', role: 'map' }], status: 'picked', note: '' },
    b3: { items: [{ asset: 'MAIN', region: 'SKY', role: 'detail' }], status: 'picked', note: '' },
    b4: { items: [], status: 'skip', note: '' },
  },
};

test('the first sentence of a line and the rest (the rest is shown on request)', () => {
  assert.deepEqual(splitSentence('Một hình người đứng trên cầu. Ai cũng nhận ra nó.'), { first: 'Một hình người đứng trên cầu.', rest: 'Ai cũng nhận ra nó.', hasMore: true });
  assert.deepEqual(splitSentence('Chỉ một câu'), { first: 'Chỉ một câu', rest: '', hasMore: false });
  assert.deepEqual(splitSentence('Anh hỏi: "Đi đâu?" Cô không đáp.'), { first: 'Anh hỏi: "Đi đâu?"', rest: 'Cô không đáp.', hasMore: true });
  assert.deepEqual(splitSentence(''), { first: '', rest: '', hasMore: false });
  assert.deepEqual(splitSentence(null), { first: '', rest: '', hasMore: false });
});

test('the caption of a picture is plain: the whole painting, a close-up of a region, a picture, a map, a clip with its length', () => {
  const c = (it) => captionOf(it, assets, 'MAIN');
  assert.equal(c({ asset: 'MAIN', role: 'main' }), 'Cả bức tranh');
  assert.equal(c({ asset: 'MAIN' }), 'Cả bức tranh');
  assert.equal(c({ asset: 'MAIN', region: 'FACE', role: 'detail' }), 'Cận cảnh: Khuôn mặt');
  assert.equal(c({ asset: 'MAIN', region: 'R1' }), 'Cận cảnh: một chi tiết', 'a region called only by an id has no name to show');
  assert.equal(c({ asset: 'DIARY', role: 'context' }), 'Ảnh: Trang nhật ký');
  assert.equal(c({ asset: 'MAP', role: 'map' }), 'Bản đồ: Oslo');
  assert.equal(c({ asset: 'CLIP', role: 'video' }), 'Clip 6 giây: Vịnh Oslo');
  assert.equal(c({ asset: 'DIARY', role: 'document' }), 'Tài liệu: Trang nhật ký');
  assert.equal(c({ asset: 'DIARY', role: 'compare' }), 'So sánh: Trang nhật ký');
  assert.equal(c({ asset: 'GONE', role: 'context' }), W.caption.gone);
  assert.equal(regionLabel(assets.MAIN, 'FACE'), 'Khuôn mặt');
  assert.equal(regionLabel(assets.MAIN, 'R1'), '');
});

test('the start of a line comes from the voice step, only when the voice is done', () => {
  const voice = { state: 'done', chunks: [{ beat: 'b1', start: 0.4 }, { beat: 'b1', start: 4.1 }, { beat: 'b2', start: 72.3 }, { beat: 'b3', start: null }, { beat: null, start: 1 }] };
  assert.deepEqual([...voiceStarts(voice)], [['b1', 0.4], ['b2', 72.3]]);
  assert.equal(voiceStarts({ ...voice, state: 'stale' }).size, 0);
  assert.equal(voiceStarts({ ...voice, state: 'running' }).size, 0);
  assert.equal(voiceStarts(null).size, 0);
});

test('one row per line, in order, grouped by chapter; the time only when known; the agent\'s reason as given', () => {
  const L = pickRows({ chapters, doc, starts: new Map([['b1', 0.4], ['b2', 72.3]]), reasonFor: (id, rec) => (id === 'b1' ? rec.note : '') });
  assert.deepEqual(L.rows.map((r) => [r.number, r.id, r.status, r.time]), [[1, 'b1', 'picked', '0:00'], [2, 'b2', 'picked', '1:12'], [3, 'b3', 'picked', ''], [4, 'b4', 'skip', ''], [5, 'b5', 'empty', '']]);
  assert.deepEqual(L.rows[0].pics.map((p) => p.caption), ['Cả bức tranh', 'Cận cảnh: Khuôn mặt']);
  assert.deepEqual(L.rows[1].pics.map((p) => [p.caption, p.video]), [['Ảnh: Trang nhật ký', false], ['Clip 6 giây: Vịnh Oslo', true], ['Bản đồ: Oslo', false]]);
  assert.equal(L.rows[1].pics[0].flag, 'unknown');
  assert.equal(L.rows[0].reason, 'Mở bằng cả bức tranh rồi vào khuôn mặt.');
  assert.equal(L.rows[1].reason, '');
  assert.equal(L.rows[0].first, 'Một hình người đứng trên cầu, hai tay áp lên đầu.');
  assert.equal(L.rows[0].hasMore, true);
  assert.deepEqual(L.groups.map((g) => [g.title, g.ids, g.done, g.total]), [['Chương 1 · Mở đầu', ['b1', 'b2'], 2, 2], ['Chương 2 · The sky', ['b3', 'b4', 'b5'], 2, 3]]);
  assert.deepEqual(L.chapterRows, { c1: ['b1', 'b2'], c2: ['b3', 'b4', 'b5'] });
  assert.deepEqual(L.counts, { total: 5, withPics: 3, skipped: 1, missing: ['b5'], missingCount: 1 });
});

test('a line that is skipped is not missing; a line with pictures and the skip mark counts as having pictures', () => {
  const d = { ...doc, beats: { ...doc.beats, b1: { ...doc.beats.b1, status: 'skip' } } };
  const L = pickRows({ chapters, doc: d });
  assert.equal(L.rows[0].status, 'picked', 'pictures win');
  assert.equal(L.counts.missingCount, 1);
});

test('no document, no chapters: empty and safe', () => {
  const L = pickRows({ chapters: [], doc: null });
  assert.deepEqual(L.rows, []);
  assert.equal(L.counts.total, 0);
  const E = pickRows({ chapters, doc: null });
  assert.equal(E.counts.missingCount, 5);
  assert.ok(E.rows.every((r) => r.status === 'empty' && r.pics.length === 0));
});

test('"3 đoạn chưa có hình" leads to the first line without a picture, then to the next, and goes round', () => {
  const L = pickRows({ chapters, doc: { ...doc, beats: { b1: doc.beats.b1 } } });
  assert.deepEqual(L.counts.missing, ['b2', 'b3', 'b4', 'b5']);
  assert.equal(nextMissing(L).id, 'b2');
  assert.equal(nextMissing(L, 'b2').id, 'b3');
  assert.equal(nextMissing(L, 'b5').id, 'b2');
  assert.equal(nextMissing(L, 'b1').id, 'b2');
  assert.equal(nextMissing(pickRows({ chapters, doc })).id, 'b5', 'the skipped line is not a missing one');
  assert.equal(nextMissing(pickRows({ chapters: [{ id: 'c', beats: [{ id: 'x', text: 't' }] }], doc: { beats: { x: { items: [{ asset: 'MAIN' }] } }, assets, main_asset: 'MAIN' } })), null);
});

test('the numbers of the header in words', () => {
  assert.deepEqual(headerNumbers({ total: 28, withPics: 25, skipped: 0, missing: ['a', 'b', 'c'], missingCount: 3 }), { progress: '25/28 đoạn đã có hình', missing: '3 đoạn chưa có hình', skipped: '', fraction: 25 / 28 });
  const settled = headerNumbers({ total: 28, withPics: 26, skipped: 2, missing: [], missingCount: 0 });
  assert.deepEqual([settled.progress, settled.missing, settled.skipped, settled.fraction], ['28/28 đoạn đã có hình', '', '2 đoạn bỏ qua', 1], 'a skipped line is settled, as in the agent\'s sentence');
  assert.equal(headerNumbers({ total: 6, withPics: 4, skipped: 1, missing: ['x'], missingCount: 1 }).progress, '5/6 đoạn đã có hình');
  assert.equal(headerNumbers({ total: 0, withPics: 0, skipped: 0, missing: [], missingCount: 0 }).progress, W.noLines);
  assert.equal(headerNumbers({ total: 0, withPics: 0, skipped: 0, missing: [], missingCount: 0 }).missing, '');
});

test('"Duyệt chọn hình": what is missing when it cannot be pressed, in this order', () => {
  const ok = { narration: { present: true, approved: true }, picks: { main_asset: 'MAIN' }, issues: [], approved: false };
  assert.deepEqual(approveState({ d: ok }), { approved: false, label: 'Duyệt chọn hình', canPress: true, why: '', note: '', errors: 0 });
  assert.equal(approveState({ d: { ...ok, narration: { present: false } } }).why, W.approveWhy.noNarration);
  assert.equal(approveState({ d: { ...ok, narration: { present: true, approved: false } } }).why, W.approveWhy.narration);
  assert.equal(approveState({ d: { ...ok, picks: { main_asset: null } } }).why, W.approveWhy.main);
  assert.equal(approveState({ d: { ...ok, picks: { main_asset: null } }, doc: { main_asset: 'MAIN' } }).why, '', 'the document the page holds wins');
  assert.equal(approveState({ d: { ...ok, issues: [{ level: 'error' }, { level: 'warning' }, { level: 'error' }] } }).why, W.approveWhy.errors(2));
  assert.equal(approveState({ d: ok, busy: true }).why, W.approveWhy.saving);
  assert.equal(approveState({ d: ok, busy: true }).canPress, false);
  assert.equal(approveState({ d: { ...ok, approved: true } }).label, 'Đã duyệt');
  assert.equal(approveState({ d: { ...ok, approved: true } }).canPress, false);
  assert.equal(approveState({ d: { ...ok, approved: true }, dirty: true }).approved, false, 'a change after approving needs approving again');
  assert.equal(approveState({ d: ok, emptyCount: 3 }).note, W.approveWhy.emptyLines(3), 'lines without a picture warn, they do not block');
  assert.equal(approveState({ d: ok, emptyCount: 3 }).canPress, true);
  assert.equal(approveState({ d: { ...ok, approval_reason: 'picks_edited' } }).note, W.approveWhy.again);
});

test('what stands in the way of the whole page', () => {
  assert.equal(pageBlocker({ narration: { present: false } }).kind, 'no_narration');
  assert.equal(pageBlocker({ narration: { present: true, approved: true }, picks: { main_asset: null } }).kind, 'no_main');
  assert.equal(pageBlocker({ narration: { present: true, approved: true }, picks: { main_asset: null } }, { main_asset: 'A' }), null);
  assert.equal(pageBlocker({ narration: { present: true, approved: true }, picks: { main_asset: 'A' } }), null);
  assert.equal(pageBlocker({ narration: { present: true, approved: false }, picks: { main_asset: 'A' } }).kind, 'narration_unapproved', 'a narration that is not approved: pictures can still be chosen');
  assert.match(pageBlocker({ narration: { present: true, approved: false, reason: 'narration_edited' }, picks: { main_asset: 'A' } }).text, /đã đổi sau khi duyệt/);
});

test('the three lists: the regions of the main painting, the context pictures and the clips, each with where it is used', () => {
  const L = pickRows({ chapters, doc });
  const S = sectionsOf(doc, L.rows);
  assert.deepEqual(S.regions.map((r) => [r.key, r.label, r.usedIn]), [['FACE', 'Khuôn mặt', [1]], ['SKY', 'Bầu trời', [3]], ['R1', 'Chi tiết chưa đặt tên', []]]);
  assert.deepEqual(S.context.map((c) => [c.key, c.title, c.usedIn, c.flag]), [['DIARY', 'Trang nhật ký', [2], 'unknown'], ['MAP', 'Bản đồ Oslo', [2], null]]);
  assert.deepEqual(S.clips.map((c) => [c.key, c.title, c.seconds, c.usedIn]), [['CLIP', 'Vịnh Oslo', 6, [2]]]);
  assert.equal(W.sections.usedIn([1, 3]), 'Dùng ở đoạn 1, 3');
  assert.equal(W.sections.usedIn([]), 'Chưa đoạn nào dùng');
  assert.equal(W.sections.usedIn([1, 2, 3, 4, 5, 6, 7, 8]), 'Dùng ở đoạn 1, 2, 3, 4, 5, 6 và 2 đoạn nữa');
  assert.deepEqual(sectionsOf(null, []), { regions: [], context: [], clips: [] });
});

test('the numbers of the selected lines for the request box', () => {
  const L = pickRows({ chapters, doc });
  assert.deepEqual(selectedNumbers(['b4', 'b2', 'zzz'], L.rows), [2, 4]);
  assert.equal(W.box.linesWords(1, '4'), 'Đoạn 4 đang chọn');
  assert.equal(W.box.linesWords(2, '4, 5'), '2 đoạn đang chọn (4, 5)');
});

test('the agent\'s sentence under a line keeps the label of the agent\'s build', () => {
  assert.equal(PICKS_AUTO_LABELS.lineWhy('x'), 'Agent: x');
});

test('the check of the picks names a line by its number and a picture by its title, never by an id', async () => {
  const { issueSentence } = await import('../../bti/editor/static/js/views/picks_rows_logic.js');
  const numberOf = (id) => ({ b0004: 4, b0010: 10 }[id] ?? null);
  const S = (i) => issueSentence(i, { numberOf, assets });
  assert.equal(S({ code: 'no_main', level: 'error' }), 'Chưa chọn tranh chính.');
  assert.equal(S({ code: 'beat_no_pick', level: 'warning', beat: 'b0004' }), 'Đoạn 4 chưa có hình: bản nháp sẽ dùng tranh chính ở đó.');
  assert.equal(S({ code: 'unknown_asset', level: 'error', beat: 'b0010', asset: 'X' }), 'Đoạn 10 dùng một hình không còn trong danh sách.');
  assert.equal(S({ code: 'unknown_region', level: 'error', beat: 'b0004', asset: 'MAIN', region: 'HEAD' }), 'Đoạn 4 dùng một vùng của hình không còn nữa.');
  assert.equal(S({ code: 'beat_unknown', level: 'warning', beat: 'b9999' }), 'Có hình cho một đoạn không còn trong lời dẫn.');
  assert.equal(S({ code: 'asset_file_missing', level: 'error', asset: 'DIARY' }), 'Thiếu tệp ảnh của hình “Trang nhật ký”.');
  assert.equal(S({ code: 'asset_flag', level: 'warning', asset: 'DIARY', flag: 'unknown' }), 'Hình “Trang nhật ký”: Chưa rõ giấy phép.');
  assert.equal(S({ code: 'something_new', level: 'error' }), 'Có một lỗi trong chọn hình.');
  assert.equal(S({ code: 'something_new', level: 'warning' }), 'Có một điều cần xem trong chọn hình.');
  assert.equal(S({ code: 'beat_no_pick', level: 'warning', beat: 'zzz' }), 'Một đoạn chưa có hình: bản nháp sẽ dùng tranh chính ở đó.');
  for (const code of ['no_main', 'beat_no_pick', 'unknown_asset', 'unknown_region', 'beat_unknown', 'asset_file_missing', 'asset_flag', 'new_one']) {
    const t = S({ code, level: 'error', beat: 'b0004', asset: 'MAIN', flag: 'small' });
    assert.doesNotMatch(t, /\bb\d{4}\b|MAIN|_/, t);
  }
});
