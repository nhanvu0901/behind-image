// Three-way merge of a STORYBOARD that two tabs (or a tab and an agent) edited. The same rule as the script view
// (merge.js): what only the owner changed is kept, what only the server changed is taken, and when both changed the same
// thing the owner decides. Units: each shot by id (the whole shot with its overlays) and each other top-level key
// (regions, assets, canvas...). The LIST of shots (which ids, in which order, from which start) is one more unit: if both
// sides changed it, the merge is not automatic.
//
//   mergeStoryboard(base, mine, theirs) -> { status: 'same' | 'merged' | 'conflict', value, fromTheirs: string[], conflicts: [{ kind, id?, key? }] }
//
// `base` is what this tab last loaded or saved, `mine` the draft, `theirs` what the server has now. All three are plain
// documents (no derived `_` keys, no `approvals`: those belong to the server). Pure; tested in tests/editor_frontend/sbmerge.test.mjs.
import { deepEqual, mergeDoc } from './merge.js';

const DROP = new Set(['shots', 'approvals']);
const rest = (d) => { const o = {}; for (const k of Object.keys(d || {})) if (!DROP.has(k) && !k.startsWith('_')) o[k] = d[k]; return o; };
const shotsOf = (d) => (Array.isArray(d?.shots) ? d.shots : []);
/** The list of shots: ids, order, start times. */
const structure = (d) => shotsOf(d).map((s) => [s?.id, s?.start ?? null]);

/** Order of the merged shot ids: the side that changed the list decides; ids only the other side has stay after their predecessor. */
function orderOf(bIds, mIds, tIds, mineChanged) {
  const [first, second] = mineChanged ? [mIds, tIds] : [tIds, mIds];
  const out = [...first];
  second.forEach((id, i) => {
    if (out.includes(id)) return;
    let at = 0;
    for (let k = i - 1; k >= 0; k--) { const p = out.indexOf(second[k]); if (p >= 0) { at = p + 1; break; } }
    out.splice(at, 0, id);
  });
  return out;
}

export function mergeStoryboard(base, mine, theirs) {
  const conflicts = [], fromTheirs = [];
  const noteTheirs = (what) => { if (!fromTheirs.includes(what)) fromTheirs.push(what); };
  if (deepEqual(rest(mine), rest(theirs)) && deepEqual(shotsOf(mine), shotsOf(theirs))) return { status: 'same', value: mine, fromTheirs, conflicts };

  // ---- the list of shots
  const sb = structure(base), sm = structure(mine), st = structure(theirs);
  const mineList = !deepEqual(sm, sb), theirList = !deepEqual(st, sb);
  if (mineList && theirList && !deepEqual(sm, st)) conflicts.push({ kind: 'list' });

  // ---- each shot
  const B = new Map(shotsOf(base).map((s) => [s.id, s])), M = new Map(shotsOf(mine).map((s) => [s.id, s])), T = new Map(shotsOf(theirs).map((s) => [s.id, s]));
  const ids = orderOf(sb.map((x) => x[0]), sm.map((x) => x[0]), st.map((x) => x[0]), mineList || !theirList);
  const shots = [];
  for (const id of ids) {
    const b = B.get(id), m = M.get(id), t = T.get(id);
    let v;
    if (deepEqual(m, t)) v = m;
    else if (deepEqual(m, b)) { v = t; noteTheirs('shot'); }
    else if (deepEqual(t, b)) v = m;
    else { conflicts.push({ kind: 'shot', id }); v = m; }
    if (v !== undefined) shots.push(v);
  }
  if (theirList && !mineList && shots.length !== sm.length) noteTheirs('shot');

  // ---- every other key of the document
  const r = mergeDoc(rest(base), rest(mine), rest(theirs), { collections: [] });
  for (const c of r.conflicts) conflicts.push({ kind: 'key', key: c.key });
  for (const k of new Set([...Object.keys(rest(mine)), ...Object.keys(rest(theirs))])) if (!deepEqual(r.value[k], rest(mine)[k])) noteTheirs(k);

  const value = { ...r.value, shots };
  return { status: conflicts.length ? 'conflict' : 'merged', value, fromTheirs, conflicts };
}

/** One Vietnamese line for the owner: what came from the other tab. */
export function mergedNote(fromTheirs) {
  const NAME = { assets: 'danh sách hình', canvas: 'khung hình', audio: 'âm thanh', end: 'điểm kết thúc', project: 'tên dự án', title: 'tiêu đề' };
  const parts = [];
  if (fromTheirs.includes('shot')) parts.push('một số shot');
  for (const k of fromTheirs) if (k !== 'shot') { const n = NAME[k] || 'cài đặt chung'; if (!parts.includes(n)) parts.push(n); }
  return parts.length ? `Đã ghép với bản sửa ở nơi khác (${parts.join(', ')}).` : 'Đã ghép với bản trên máy chủ.';
}
