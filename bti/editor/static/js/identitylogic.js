// The pure parts of the selector "Kiểu mở đầu và mốc chương" (step 5) and of its line in step 6: what the dropdown shows, what a choice
// asks of the server, the sentences about what was and was not changed. No DOM, no network. Tested in tests/editor_frontend/identity.test.mjs.
// The words are in labels.js (IDENTITY_LABELS); the route is GET/PUT /api/projects/{pid}/identity (bti/editor/identity_api.py).
import { IDENTITY_LABELS as L } from './labels.js';

/** The value of the "nothing chosen yet" entry of the dropdown. */
export const OLD_LOOK = '';

/** `info` is the answer of GET /identity: {style: id|null, default: id|null, options: [{id, label}]}. */
const optionsOf = (info) => (Array.isArray(info?.options) ? info.options.filter((o) => o && typeof o.id === 'string') : []);

/** The label of a style id as the route gave it ("Vệt sáng quét"); the id itself only when the route does not list it. */
export function styleLabel(info, id) {
  const o = optionsOf(info).find((x) => x.id === id);
  return o ? (o.label || o.id) : (id || '');
}

/** What the dropdown shows. `hidden`: the style offers no choice (no options). While nothing was chosen the first entry is the disabled
 *  "Kiểu cũ" (the old look cannot be chosen back through the route: undo does that); once a style is chosen it is gone. */
export function selectorView(info, { busy = false } = {}) {
  const opts = optionsOf(info);
  if (!opts.length) return { hidden: true, value: OLD_LOOK, options: [], note: '', disabled: true };
  const chosen = typeof info.style === 'string' && opts.some((o) => o.id === info.style) ? info.style : null;
  const options = opts.map((o) => ({ value: o.id, text: o.label || o.id, disabled: false }));
  if (!chosen) options.unshift({ value: OLD_LOOK, text: L.old, disabled: true });
  return { hidden: false, value: chosen || OLD_LOOK, options, note: chosen ? '' : L.oldNote, disabled: !!busy };
}

/** Does choosing `want` ask the server for anything? Not while a choice is running, not for the style already chosen, not for an unknown one. */
export function canChoose(info, want, { busy = false } = {}) {
  if (busy || typeof want !== 'string' || !want) return false;
  return optionsOf(info).some((o) => o.id === want) && info?.style !== want;
}

/** The body of PUT /identity: the style and the revision of the storyboard the page holds (the saved one: unsaved edits are merged afterwards). */
export const chooseBody = (want, rev) => ({ style: want, base_rev: rev });

/** One Vietnamese sentence per item the route skipped. `shots`: the page's shots (a shot is named by its number, never by its id). */
export function skippedLines(skipped, shots = []) {
  const out = [];
  for (const s of Array.isArray(skipped) ? skipped : []) {
    const what = L.what[s?.what] || L.what.opening;
    const i = s?.shot ? (shots || []).findIndex((x) => x.id === s.shot) : -1;
    const n = i >= 0 ? i + 1 : null;
    const fn = L.skip[s?.reason] || L.skip.other;
    const line = fn(what, n);
    if (!out.includes(line)) out.push(line);
  }
  return out;
}

/** The sentence after a choice: what changed (how many places), the style by its words. */
export function resultLine(info, res) {
  const label = styleLabel(info, res?.style);
  const n = Array.isArray(res?.changed) ? res.changed.length : 0;
  return L.done(label, n);
}

/** The line of step 6: which style the video is exported with. `row` is [label, value] for the table "Sẽ làm ra"; null when there is no answer. */
export function exportRow(info) {
  if (!info || !optionsOf(info).length) return null;
  const chosen = typeof info.style === 'string' && optionsOf(info).some((o) => o.id === info.style);
  return [L.export.label, chosen ? styleLabel(info, info.style) : L.export.old];
}
