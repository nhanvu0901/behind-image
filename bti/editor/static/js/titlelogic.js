// The decisions of the video's title box on the script page (titlepanel.js): what the strip and the dialog show, what each button sends, what a typed title is checked
// against before it is sent. Pure functions, no DOM and no requests: tests/editor_frontend/title.test.mjs. The words are in labels.js (TITLE_LABELS, TITLE_FORM_WORDS).
//
// The data is the answer of GET /api/projects/{pid}/title:
//   {rev, state: 'none' | 'done' | 'stale', title: {text, by, at, source, option} | null, candidates: [{text, form, lines, scores, why}], history, written, limits, running, storyboard}
import { TITLE_LABELS as L, TITLE_FORM_WORDS as FORMS } from './labels.js';

const LIMITS = { max_chars: 60, best: [28, 55], max_words: 9, person_max_chars: 60 };
export const NOTE_MAX = 600;

/** The limits of a title as the server states them (the defaults when the answer has none). */
export function limitsOf(data) {
  const l = data?.limits && typeof data.limits === 'object' ? data.limits : {};
  const best = Array.isArray(l.best) && l.best.length === 2 ? l.best : LIMITS.best;
  return { max: Number(l.person_max_chars) || LIMITS.person_max_chars, maxChars: Number(l.max_chars) || LIMITS.max_chars, bestMin: best[0], bestMax: best[1], maxWords: Number(l.max_words) || LIMITS.max_words };
}

/** One line: runs of white space become one space (what the server does before it counts). */
export const oneLine = (text) => String(text ?? '').replace(/\s+/g, ' ').trim();

/** What the counter and the check under the field say about a typed title: {chars, words, problem: 'empty' | 'newline' | 'long' | null, note: sentence or ''}. */
export function lengthInfo(text, limits = limitsOf(null)) {
  const raw = String(text ?? '');
  const clean = oneLine(raw);
  const chars = [...clean].length;
  const words = clean ? clean.split(' ').length : 0;
  let problem = null;
  if (!clean) problem = 'empty';
  else if (/[\r\n]/.test(raw.trim())) problem = 'newline';
  else if (chars > limits.max) problem = 'long';
  const note = problem === 'long' ? L.tooLong(chars, limits.max) : problem === 'newline' ? L.oneLine : problem === 'empty' ? '' : chars < limits.bestMin || chars > limits.bestMax ? L.outsideBest(limits.bestMin, limits.bestMax) : '';
  return { chars, words, problem, note, clean };
}

/** Who made a title, as the owner reads it: 'human' -> Bạn, 'agent:<model id>' -> Agent <label of the agent that wrote it>, 'cli:<name>' -> Lệnh bti (<name>). */
export function whoWords(by, data = null) {
  const s = String(by || '');
  if (!s) return '';
  if (s === 'human') return L.who.human;
  if (s.startsWith('agent:')) {
    const w = data?.written;
    const label = w && s === 'agent:' + w.model ? w.agent?.label : null;               // the label of the agent that wrote the document (its model id otherwise)
    return L.who.agent(label || s.slice(6));
  }
  if (s.startsWith('cli:')) return L.who.cli(s.slice(4));
  return L.who.other(s);
}

/** `20/11/2026 10:00` from an ISO stamp written by the server ('' when it is not one). */
export function whenWords(at) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(at || ''));
  return m ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : '';
}

/** A job of the title is still going (the record of GET /api/longjobs/{id} or the `running` of the title answer). */
export const jobRunning = (job) => !!job && ['queued', 'waiting', 'running'].includes(job.state);

/** The progress line of a running job: the note of its part, else the plain sentence. */
export function progressText(job) {
  const note = (job?.parts || []).map((p) => p?.note).filter(Boolean).pop();
  return L.progress(note && /\p{L}/u.test(note) && !/^Agent đang viết tựa video/.test(note) ? String(note) : '');
}

/** What the strip shows and which buttons it has.
 *  `ctx`: {narrationApproved: bool, busy: bool (a request of this box is going), job: the running job or null}
 *  -> {has, text, state, stale, by, when, source, running, write: {visible, disabled, label, title}, open: {visible}, note: the line under the title} */
export function stripView(data, ctx = {}) {
  const t = data?.title && typeof data.title.text === 'string' && data.title.text ? data.title : null;
  const running = jobRunning(ctx.job) || jobRunning(data?.running) || !!ctx.busy;
  const approved = ctx.narrationApproved !== false;
  const state = data?.state === 'stale' || data?.stale ? 'stale' : t ? 'done' : 'none';
  let note = '';
  if (running) note = L.working;
  else if (!t) note = approved ? L.noneHint : L.needNarration;
  else if (state === 'stale') note = L.stale;
  return {
    has: !!t, text: t ? t.text : L.none, state, stale: state === 'stale', by: t ? whoWords(t.by, data) : '', when: t ? whenWords(t.at) : '', source: t ? t.source : null, running, note,
    write: { visible: !running, disabled: !approved, label: t ? L.writeAgain : L.write, title: approved ? L.writeHint : L.needNarration },
    open: { visible: !!data },
  };
}

/** The rows of the list of candidates: {n, text, chars, form, formWord, scores, scoresText, why, lines, linesText, inUse}. */
export function candidateRows(data) {
  const cur = data?.title?.text;
  return (data?.candidates || []).map((c, i) => ({
    n: i + 1, text: c.text, chars: [...String(c.text || '')].length, form: c.form, formWord: FORMS[c.form] || FORMS.other, scores: c.scores || {}, scoresText: L.scoresOf(c.scores || {}),
    why: c.why || '', lines: c.lines || [], linesText: (c.lines || []).length ? L.linesOf(c.lines.join(', ')) : '', inUse: !!cur && c.text === cur,
  }));
}

/** The earlier titles, newest first: {text, who, when}. */
export function historyRows(data) {
  return (data?.history || []).slice().reverse().map((h) => ({ text: h.text, who: whoWords(h.by, data), when: whenWords(h.at) }));
}

/** The body of PUT .../title for a candidate (the number, from 1). */
export const pickBody = (data, n) => ({ base_rev: data?.rev, option: n, actor: 'human' });
/** The body of PUT .../title for a typed title; null when it must not be sent (the problem is shown under the field). */
export function typeBody(data, text) {
  const info = lengthInfo(text, limitsOf(data));
  return info.problem ? null : { base_rev: data?.rev, text: info.clean, actor: 'human' };
}
/** The body of POST .../title/generate: the owner's note (trimmed to its limit) when there is one. */
export function generateBody(note) {
  const n = oneLine(note).slice(0, NOTE_MAX);
  return n ? { note: n, actor: 'human' } : { actor: 'human' };
}

/** Does asking the agent again replace a title the owner chose or typed (then the page asks first)? */
export const replacesPersonsTitle = (data) => data?.title?.source === 'person';

/** What the toast says after a title was set: the storyboard's own sentence when the answer has one. -> [text, kind] */
export function savedToast(res) {
  const sb = res?.storyboard;
  if (sb && typeof sb.sentence === 'string' && sb.sentence) return [`${L.saved} ${sb.sentence}`, sb.error ? 'warn' : 'ok'];
  return [L.saved, 'ok'];
}

/** What the toast says when the job ended well: the title it chose (and, when a storyboard took it, its sentence). -> [text, kind] */
export function doneToast(job) {
  const r = job?.result || {};
  const base = r.title ? L.generated(r.title) : L.saved;
  const sb = r.storyboard;
  return sb && typeof sb.sentence === 'string' && sb.sentence ? [`${base} ${sb.sentence}`, sb.error ? 'warn' : 'ok'] : [base, 'ok'];
}
