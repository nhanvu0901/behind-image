// Selecting rows of a list with the usual keys, for the list of shots (step 5) and the list of narration lines (step 4). Pure: no DOM.
//   state: { ids: [...in list order], anchor: id | null, chapter: chapter key | null }
//   A plain click selects one; Ctrl or Cmd adds or removes one; Shift selects the run from the last clicked row. A chapter header selects the whole chapter and
//   remembers that it was the chapter that was chosen (the request box then says "Chương: ..." instead of listing the rows).
export const emptySelection = () => ({ ids: [], anchor: null, chapter: null });

const inOrder = (order, set) => order.filter((id) => set.has(id));

/** The selection after a click on row `id`. `order`: every row id in list order. `mods`: { shift, toggle } (toggle: Ctrl or Cmd). */
export function applyClick(sel, id, mods = {}, order = []) {
  if (!order.includes(id)) return sel;
  const cur = new Set((sel?.ids || []).filter((x) => order.includes(x)));
  if (mods.shift && sel?.anchor && order.includes(sel.anchor)) {
    const a = order.indexOf(sel.anchor), b = order.indexOf(id);
    const run = order.slice(Math.min(a, b), Math.max(a, b) + 1);
    const next = mods.toggle ? new Set([...cur, ...run]) : new Set(run);
    return { ids: inOrder(order, next), anchor: sel.anchor, chapter: null };
  }
  if (mods.toggle) {
    if (cur.has(id)) cur.delete(id); else cur.add(id);
    return { ids: inOrder(order, cur), anchor: id, chapter: null };
  }
  return { ids: [id], anchor: id, chapter: null };
}

/** Select a whole chapter: its rows, and the key of the chapter. A second click on the same chapter leaves only its first row selected. */
export function selectChapter(sel, chapterKey, rowIds, order = []) {
  const ids = inOrder(order, new Set(rowIds));
  if (!ids.length) return sel;
  if (sel?.chapter === chapterKey) return { ids: [ids[0]], anchor: ids[0], chapter: null };
  return { ids, anchor: ids[0], chapter: chapterKey };
}

/** Rows that are gone leave the selection; a chapter that has lost a row is no longer "the whole chapter". */
export function pruneSelection(sel, order = [], chapterRows = null) {
  const have = new Set(order);
  const ids = (sel?.ids || []).filter((id) => have.has(id));
  let chapter = ids.length ? sel?.chapter || null : null;
  if (chapter && chapterRows) {
    const rows = chapterRows[chapter] || [];
    if (rows.length !== ids.length || rows.some((id) => !ids.includes(id))) chapter = null;
  }
  const anchor = sel?.anchor && have.has(sel.anchor) ? sel.anchor : ids[0] || null;
  return { ids, anchor, chapter };
}

/** The playhead moved to row `id` (playing, a seek, a click in the timeline of the editor): what becomes of the selection.
 *  Several rows chosen by the owner stay while the video plays or when the row is one of them; otherwise the selection follows the playhead. */
export function followPlayhead(sel, id, { playing = false } = {}) {
  if (!id) return sel;
  if ((sel?.ids || []).includes(id)) return sel;                          // the anchor of a Shift run is where the owner clicked, not where the playhead is
  if (playing && (sel?.ids || []).length > 1) return sel;
  return { ids: [id], anchor: id, chapter: null };
}

/** Row ids that were added or removed: for the tests and for the page that repaints only what changed. */
export function selectionDiff(a, b) {
  const A = new Set(a?.ids || []), B = new Set(b?.ids || []);
  return { added: [...B].filter((x) => !A.has(x)), removed: [...A].filter((x) => !B.has(x)) };
}

/** Next row to focus for the arrow keys: dir -1 (up) or +1 (down); stays at the ends. */
export function stepFocus(order, currentId, dir) {
  if (!order.length) return null;
  const i = order.indexOf(currentId);
  if (i < 0) return order[dir < 0 ? order.length - 1 : 0];
  return order[Math.min(order.length - 1, Math.max(0, i + dir))];
}
