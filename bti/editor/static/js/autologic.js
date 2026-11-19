// The decisions of the switch "Cho agent tự chạy dự án này" (autoswitch.js shows it): which gates an agent may approve in this project. Pure; tested in
// tests/editor_frontend/autologic.test.mjs. The document is GET/PUT /api/projects/{pid}/auto: {rev, enabled, gates: {outline, narration, picks, storyboard},
// spend: {model, machine_time, paid}}; the server decides (an agent is refused a gate the owner did not allow), this file only builds what the page shows and sends.
import { AUTO_LABELS as L } from './labels.js';

export const GATES = ['outline', 'narration', 'picks', 'storyboard'];

const isDoc = (d) => d && typeof d === 'object' && typeof d.rev === 'string' && d.gates && typeof d.gates === 'object';

/** What the dialog shows for a document: the switch, one checkbox per gate (in the order of the pipeline), whether the checkboxes can be changed. */
export function autoView(doc) {
  if (!isDoc(doc)) return { ready: false, enabled: false, gates: [], gatesDisabled: true, summary: '', button: L.button.off };
  const enabled = doc.enabled === true;
  const gates = GATES.map((id) => ({ id, label: L.gate[id], checked: doc.gates[id] === true }));
  return { ready: true, enabled, gates, gatesDisabled: !enabled, summary: summary(doc), button: enabled ? L.button.on : L.button.off };
}

/** One sentence about what an agent may do now. */
export function summary(doc) {
  if (!isDoc(doc) || doc.enabled !== true) return L.summary.off;
  const names = GATES.filter((g) => doc.gates[g] === true).map((g) => L.gateShort[g]);
  return names.length ? L.summary.on(names) : L.summary.onNone;
}

/** The body of the switch: only `enabled` changes; `rev` is the revision the page holds. */
export const switchBody = (rev, on) => ({ base_rev: rev, enabled: on === true });

/** The body of one checkbox: only that gate changes. An unknown gate gives null (nothing is sent). */
export const gateBody = (rev, gate, on) => (GATES.includes(gate) ? { base_rev: rev, gates: { [gate]: on === true } } : null);

/** The tooltip of the button in the top bar. */
export const buttonTitle = (doc) => (isDoc(doc) && doc.enabled === true ? L.buttonTitle.on : L.buttonTitle.off);

/** The server marks a refusal of its own rule with these codes; the page never makes them (it sends no actor), a program may. */
export const NEEDS_OWNER_CODES = ['gate_needs_human', 'auto_needs_human', 'spend_needs_human'];
export const needsOwner = (e) => NEEDS_OWNER_CODES.includes(e?.body?.code);

/** After a stale answer (409) the page reads the document again and asks once more: true when this error is one. */
export const isStale = (e) => e?.status === 409 && ['stale', 'stale_revision'].includes(e?.body?.code);
