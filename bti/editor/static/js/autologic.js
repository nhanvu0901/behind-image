// The decisions of the switch "Cho agent tự chạy dự án này" (autoswitch.js shows it): which gates an agent may approve in this project. Pure; tested in
// tests/editor_frontend/autologic.test.mjs. The document is GET/PUT /api/projects/{pid}/auto: {rev, enabled, gates: {outline, narration, picks, storyboard},
// spend: {model, machine_time, paid}}; the server decides (an agent is refused a gate the owner did not allow), this file only builds what the page shows and sends.
import { AUTO_LABELS as L, AUTORUN_LABELS as R } from './labels.js';
import { describeHttp, isVietnamese } from './errmsg.js';       // c6auto: the sentence of a failed step

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

// ------------------------------------------------------------------------------------------------------------------------ c6auto: "Chạy tự động"
// The button next to the switch, the progress line and the sentence at the end of a run (autoswitch.js shows them). The server writes the sentence of every end
// (bti/auto_run/reasons.py) and the run's progress (GET /api/projects/{pid}/auto/runs: one line per run, newest first); this file decides what the page shows.

/** The body of POST /api/projects/{pid}/auto/run: all the way (`until` null), the usual number of steps. The page sends no actor: it is the owner. */
export const runBody = () => ({ until: null, max_steps: 40 });

export const isRunning = (item) => !!item && item.state === 'running';

/** The button: shown while a project is open; it works only while the switch is on and no run goes on (and not while a click is being answered). */
export function runButtonView(doc, item, busy = false) {
  const on = !!(isDoc(doc) && doc.enabled === true);
  const running = isRunning(item);
  return { label: R.button, enabled: on && !running && !busy, title: running ? R.buttonTitle.running : on ? R.buttonTitle.ready : R.buttonTitle.off };
}

/** The newest run of the answer of GET .../auto/runs, or null. */
export const latestRun = (answer) => (answer && Array.isArray(answer.items) && answer.items[0]) || null;

/** "Đang chạy tự động: Giọng đọc (3/6)" while a run goes on; null otherwise. */
export function progressText(item) {
  if (!isRunning(item)) return null;
  const l = item.live || {};
  return R.running(l.step_label, l.n, l.of);
}

/** A string that changes when the run moves on (another step, another call, the end): the page then asks the shell to read the pipeline again. */
export const runMoved = (item) => (item ? [item.id, item.state, item.live?.step || '', item.steps_taken ?? ''].join('|') : '');

/** The path that stops the run (the long job it is). */
export const stopPath = (item) => (item && typeof item.job_id === 'string' ? `/api/longjobs/${encodeURIComponent(item.job_id)}/cancel` : null);

const TONE = { done: 'ok', failed: 'err' };

/** What the page says when a run has ended: {tone, heading, sentence, link: {href, text} | null}; null while it runs or when there is nothing to say.
 *  The sentence is the server's (Vietnamese); a failed step is said with the page's own sentence of its code (errmsg.js), a record without a sentence with a fallback. */
export function endView(item) {
  if (!item || item.state === 'running') return null;
  const res = item.result && typeof item.result === 'object' ? item.result : {};
  const outcome = item.outcome || res.outcome || 'interrupted';
  let sentence = typeof item.sentence === 'string' && item.sentence.trim() ? item.sentence.trim() : R.fallback[outcome] || R.fallback.needs_owner;
  const err = res.error && typeof res.error === 'object' ? res.error : null;
  if (outcome === 'failed' && err && err.code && ['action_failed', 'job_failed'].includes(res.reason)) {
    const own = typeof err.detail === 'string' && isVietnamese(err.detail) ? err.detail : null;          // a failed job already says it in Vietnamese
    sentence = R.failed(res.action_label || res.action || '') + (own || describeHttp(Number(err.status) || 500, { ...err }).text);
  }
  const label = res.step_label || item.step_label || null;
  const href = typeof item.link === 'string' && item.link.startsWith('#/project/') ? item.link : null;
  return { tone: TONE[outcome] || 'warn', heading: R.heading[outcome] || R.heading.needs_owner, sentence, link: href && label ? { href, text: R.link(label) } : null };
}
