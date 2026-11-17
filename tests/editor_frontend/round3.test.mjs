// Round 3 UI fixes: issue target (R3U-003), undo boundary after a merge (R3U-005), chapter differences (R3U-002).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as L from '../../bti/editor/static/js/logic.js';
import { Store } from '../../bti/editor/static/js/store.js';
import { issueTarget, shotsUsingAsset } from '../../bti/editor/static/js/sbissues.js';
import { chapterDiffItems, headerRole } from '../../bti/editor/static/js/chapdiff.js';

const M = 'bti/editor/static/mock/';
const timing = JSON.parse(fs.readFileSync(M + 'timing.json'));
const sbRaw = JSON.parse(fs.readFileSync(M + 'storyboard.json'));
const fresh = () => { const s = L.clone(sbRaw); L.derive(s, timing); return s; };

// ---- R3U-003
const draft = () => ({ assets: { durer: {}, spare: {} }, shots: [
  { id: 's1', slots: { image: { asset: 'x' } }, overlays: [{ id: 'o1', slots: {} }] },
  { id: 's2', slots: { image: { asset: 'durer' } } },
  { id: 's3', slots: {}, overlays: [{ id: 'o1', slots: { image: { asset: 'durer' } } }] }] });
test('an issue with a shot path goes to that shot (and overlay)', () => {
  assert.deepEqual(issueTarget({ path: 'shots[2].overlays[0].start' }, draft()), { kind: 'shot', shot: 2, overlay: 0 });
  assert.deepEqual(issueTarget({ path: 'shots[1].technique' }, draft()), { kind: 'shot', shot: 1, overlay: null });
});
test('an issue with only a shot id goes to that shot', () => {
  assert.deepEqual(issueTarget({ path: '', shot: 's3', overlay: 'o1' }, draft()), { kind: 'shot', shot: 2, overlay: 0 });
});
test('an issue about an asset goes to the shots that use it, in order, counting them', () => {
  const t = issueTarget({ path: 'assets.durer.file', args: { asset: 'durer' } }, draft());
  assert.deepEqual(t, { kind: 'asset', asset: 'durer', shots: ['s2', 's3'] });
  assert.deepEqual(issueTarget({ path: 'assets.durer.file' }, draft()).shots, ['s2', 's3']);
});
test('an asset nobody uses: the pictures tab, never shot 1', () => {
  assert.deepEqual(issueTarget({ args: { asset: 'spare' } }, draft()), { kind: 'asset', asset: 'spare', shots: [] });
  assert.deepEqual(shotsUsingAsset(draft(), 'spare'), []);
});
test('an issue with no place stays where the owner is', () => {
  for (const i of [{ path: 'canvas' }, { path: '' }, { path: 'shots[99].x' }, { args: { asset: 'gone' } }, null]) assert.equal(issueTarget(i, draft()).kind, 'none');
});

// ---- R3U-005
const store = () => { const s = new Store(); s.load(fresh(), timing, 'rev1'); return s; };
test('after a merge with another tab the history starts at the merged document', () => {
  const s = store();
  s.commit('mine', (d) => { d.shots[9].note = 'b1'; });
  assert.ok(s.canUndo);
  const theirs = L.clone(s.draft); theirs.shots[3].note = 'a1'; theirs.approvals = {};
  const merged = L.clone(s.draft); merged.shots[3].note = 'a1';
  s.rebase(merged, theirs, 'rev2', undefined, { fresh: true });
  assert.equal(s.canUndo, false); assert.equal(s.canRedo, false);
  assert.equal(s.draft.shots[3].note, 'a1');
  s.undo();                                    // nothing to undo: the other tab's edit stays
  assert.equal(s.draft.shots[3].note, 'a1');
});
test('edits after the merge can be undone, back to the merged document and no further', () => {
  const s = store();
  const theirs = L.clone(s.draft); theirs.shots[3].note = 'a1'; theirs.approvals = {};
  s.rebase(L.clone(theirs), theirs, 'rev2', undefined, { fresh: true });
  s.commit('again', (d) => { d.shots[5].note = 'c'; });
  s.undo(); s.undo();
  assert.equal(s.draft.shots[3].note, 'a1'); assert.ok(!s.draft.shots[5].note);
});
test('a rebase that changes nothing keeps the history; an overwrite keeps it too', () => {
  const s = store();
  s.commit('mine', (d) => { d.shots[9].note = 'b1'; });
  const theirs = L.clone(s.draft); theirs.approvals = {};
  s.rebase(L.clone(s.draft), theirs, 'rev2', undefined, { fresh: true });
  assert.ok(s.canUndo);
  s.rebase(JSON.parse(s.snap()), theirs, 'rev3', 'Ghi đè');
  assert.ok(s.canUndo);
});

// ---- R3U-002
const outline = { chapters: [{ id: 'c01', title: 'MỞ ĐẦU' }, { id: 'c02', title: 'GƯƠNG' }, { id: 'c03', title: 'KẾT' }] };
test('every chapter difference has its own action', () => {
  const items = chapterDiffItems({ not_in_outline: ['c06'], missing_in_narration: ['c03'], empty_in_narration: ['c02'], order: true }, outline, { chapters: [{ id: 'c06', title: 'THỪA' }] });
  assert.deepEqual(items.map((i) => i.kind), ['extra', 'missing', 'empty', 'order']);
  assert.deepEqual(items[0].actions.map((a) => a.id), ['drop']);
  assert.deepEqual(items[1].actions.map((a) => a.id), ['write', 'add_empty']);
  assert.deepEqual(items[2].actions.map((a) => a.id), ['write', 'add_beat']);
  assert.deepEqual(items[3].actions.map((a) => a.id), ['order']);
  assert.match(items[0].actions[0].label, /Xóa chương này khỏi lời dẫn/);
  assert.match(items[3].actions[0].label, /Sắp xếp theo dàn ý/);
  for (const i of items) assert.ok(/[à-ỹ]/i.test(i.text), i.text);
});
test('no differences, no items; the drop action exists only for chapters the outline lacks', () => {
  assert.deepEqual(chapterDiffItems({ not_in_outline: [], missing_in_narration: [], empty_in_narration: [] }, outline), []);
  assert.deepEqual(chapterDiffItems(null, outline), []);
  assert.equal(headerRole('c02', outline).inOutline, true);
  assert.equal(headerRole('c06', outline).inOutline, false);
});

// ---- observations: repeated issue sentences, keys told apart
import { issueText, groupIssues, describeHttp } from '../../bti/editor/static/js/errmsg.js';
test('camera key issues name the key; identical sentences are grouped with a count', () => {
  const mk = (index) => ({ level: 'error', code: 'camera_keys_order', path: 'shots[3].params.camera[' + index + '].at', shot: 's0004', message: 'camera keys must be in strictly increasing time order', args: { param: 'camera', index } });
  assert.match(issueText(mk(2)).text, /mốc camera thứ 3/i);
  assert.notEqual(issueText(mk(1)).text, issueText(mk(2)).text);
  const same = { level: 'error', code: 'no_shots', path: 'shots', message: 'x' };
  const g = groupIssues([same, same, same, mk(1)]);
  assert.deepEqual(g.map((x) => x.n), [3, 1]);
});
test('an undrawable issue about an asset names the asset', () => {
  const t = issueText({ level: 'error', code: 'undrawable', path: 'shots[0]', shot: 's0001', message: 'x', args: { asset: 'durer' } }).text;
  assert.match(t, /durer/); assert.match(t, /tab Hình/);
});
test('render_failed never shows the server text under "chi tiết"', () => {
  const d = describeHttp(422, { detail: '/Users/x/project/media/a.jpg: cannot identify image file', code: 'render_failed', shot: 's0080', asset: 'durer' });
  assert.equal(d.detail, ''); assert.match(d.text, /s0080/); assert.match(d.text, /durer/); assert.ok(!/Users/.test(d.text));
});
test('413 too_large has a Vietnamese sentence', () => {
  const d = describeHttp(413, { detail: 'Request body too large', code: 'too_large' });
  assert.match(d.text, /quá lớn/); assert.ok(!/413/.test(d.text));
});
