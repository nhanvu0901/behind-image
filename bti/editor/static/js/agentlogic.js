// The pure parts of the agent select (steps 2 and 5, the settings box) and of the quota message: what the select shows, where its value comes
// from, what a choice asks of the server, the sentence when an agent's quota is used up. No DOM, no network. Tested in
// tests/editor_frontend/agentlogic.test.mjs. The words are in labels.js (AGENT_LABELS); the routes are GET /api/agents and
// GET/PUT /api/projects/{pid}/agent (bti/editor/agent_api.py).
import { AGENT_LABELS as L } from './labels.js';

/** Error codes of a failed job or turn that mean "the agent's quota is used up". */
export const QUOTA_CODES = new Set(['rate_limit', 'agy_rate_limit', 'claude_rate_limit']);
/** The steps that call a model, as the server names them (config/agent_choices.json). */
export const STEP_SCRIPT = 'script';
export const STEP_PICKS = 'picks';
export const STEP_STORYBOARD = 'storyboard';

/** `info` is the answer of GET /api/agents: {agents: [{id, label, model, available, reason}], default, machine_default}. */
export const agentsOf = (info) => (Array.isArray(info?.agents) ? info.agents.filter((a) => a && typeof a.id === 'string') : []);
export const findAgent = (info, id) => agentsOf(info).find((a) => a.id === id) || null;

/** The label of an agent by its id; the id itself only when the list does not have it. */
export const agentLabel = (info, id) => findAgent(info, id)?.label || (id ? String(id) : '');

/** The label of the agent that owns a model id (what a stored source line or an old job knows); `fallback` when no agent offers it. */
export function labelForModel(info, model, fallback = '') {
  const a = agentsOf(info).find((x) => x.model === model);
  return a ? a.label : (fallback || (typeof model === 'string' ? model : ''));
}

/** `effective` of one step from GET /api/projects/{pid}/agent: {id, label, model, source} or null while unknown. */
export const effectiveOf = (doc, step) => {
  const e = doc?.effective?.[step];
  return e && typeof e === 'object' ? e : null;
};

/** Where the value of the select comes from, in words. `whole`: the link "Dùng cho cả dự án" is offered (only for a choice of this step). */
export function sourceView(effective) {
  if (!effective) return { key: 'loading', text: L.loading, whole: false };
  if (effective.source === 'step') return { key: 'step', text: L.sourceStep, whole: true };
  if (effective.source === 'project') return { key: 'project', text: L.sourceProject, whole: false };
  return { key: 'default', text: L.sourceDefault, whole: false };            // "default" and "role": no choice was made for this project
}

/** What the select shows: the agents (one that cannot run now says so in its name but stays choosable), and the agent that WILL be used
 *  selected. A model no agent offers (a per-role setting under "Nâng cao") gets a disabled first entry, so the select never lies. */
export function selectView(info, effective, { busy = false } = {}) {
  const list = agentsOf(info);
  if (!list.length) return { options: [{ value: '', text: L.loading, disabled: true }], value: '', disabled: true };
  const options = list.map((a) => ({ value: a.id, text: a.available === false ? L.unavailableOption(a.label) : a.label, disabled: false }));
  const known = effective?.id && list.some((a) => a.id === effective.id);
  if (effective && !known) options.unshift({ value: '', text: L.outside(effective.label || effective.model || ''), disabled: true });
  return { options, value: known ? effective.id : '', disabled: !!busy };
}

/** The line under the select when the agent that will be used cannot run now ('' when it can, or while unknown). */
export function unavailableNote(info, effective) {
  const a = effective?.id ? findAgent(info, effective.id) : null;
  return a && a.available === false ? L.unavailable(a.label, a.reason) : '';
}

/** Does choosing `id` ask the server for anything? Not while a request runs, not for the agent already in use, not for an unknown one. */
export const canChange = (info, effective, id, { busy = false } = {}) => !busy && !!findAgent(info, id) && effective?.id !== id;

/** The body of PUT /agent that sets this step's choice, and the one of "Dùng cho cả dự án" (the agent for the project, no step choices). */
export const stepBody = (step, id, rev) => ({ steps: { [step]: id }, base_rev: rev });
export const projectBody = (id, rev) => ({ agent: id, steps: null, base_rev: rev });

/** The agent offered when `used` ran out of quota: the first agent that is not the one used (by id, and by model for a model no agent lists).
 *  `used` is {id, model}. null when there is none. */
export function otherAgent(info, used) {
  return agentsOf(info).find((a) => a.id !== (used?.id ?? null) && a.model !== (used?.model ?? null)) || null;
}

/** The agent a finished job or turn says it used: {id, label, model} from its `agent` field, else the agent that owns its `model`. */
export function usedAgent(info, rec) {
  const a = rec?.agent && typeof rec.agent === 'object' ? rec.agent : (rec?.meta?.agent && typeof rec.meta.agent === 'object' ? rec.meta.agent : null);
  const model = a?.model || rec?.model || rec?.meta?.model || null;
  if (a && (a.label || a.id)) return { id: a.id ?? null, label: a.label || agentLabel(info, a.id), model };
  const own = agentsOf(info).find((x) => x.model === model);
  return own ? { id: own.id, label: own.label, model } : { id: null, label: model || '', model };
}

/** "Nguồn" words for a stored source ({kind: model|paste|manual, model}) of the outline or the narration: the agent's label, never the raw id. */
export function sourceWords(info, source) {
  if (source?.kind === 'model') return labelForModel(info, source.model) || 'mô hình';
  return { paste: 'dán vào', manual: 'viết tay' }[source?.kind] || String(source?.kind || '');
}

/** Who wrote a proposal, in words. The server stores `author` as `agent:<model id>` (`agent:claude:claude-opus-5-5@high`, `agent:agy:gemini-x`),
 *  `agent:auto` for the automatic draft, or a free text of an older build or another tool. An agent that the list offers is shown by its label
 *  ("Opus 5.5 High"); an agent the list does not offer, as "Agent <model without the runner name>"; "human" as "Bạn"; anything else as stored.
 *  Never throws and never returns the raw `agent:` id. */
export function authorLabel(info, author) {
  const raw = typeof author === 'string' ? author.trim() : '';
  if (!raw) return '';
  if (raw.toLowerCase() === 'human') return L.author.you;
  if (!/^agent:/i.test(raw)) return raw;
  const rest = raw.slice('agent:'.length);
  if (rest === 'auto') return L.author.auto;
  const own = findAgent(info, rest) || agentsOf(info).find((a) => a.model === rest);       // the stored form is the agent's id or its model id
  if (own) return own.label;
  return L.author.agent(rest.replace(/^(?:agy|claude):/, ''));
}

/** The grey line of a proposal in the list and in its header: author (by label), time, and the id when `withId`; empty parts are left out. */
export const proposalLine = (info, p, withId = true) => [authorLabel(info, p?.author), p?.created_at, withId ? p?.id : ''].filter(Boolean).join(' | ');

// ---------------------------------------------------------------- the quota message
/** "4 giờ 30 phút": the two largest units, in Vietnamese ("2 phút", "1 ngày 3 giờ"). The time is rounded UP to whole minutes (a few seconds gone
 *  since the answer came must not turn "4 giờ 30 phút" into "4 giờ 29 phút"); under a minute is said as one minute. */
export function spanWords(seconds) {
  let s = Math.max(60, Math.ceil((Number(seconds) || 0) / 60) * 60);
  const parts = [];
  for (const [size, one] of [[86400, L.quota.days], [3600, L.quota.hours], [60, L.quota.minutes]]) {
    const n = Math.floor(s / size);
    s -= n * size;
    if (n) parts.push(one(n));
  }
  return parts.slice(0, 2).join(' ');
}

const finite = (v) => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));

/** The sentence of the quota message: the agent by its label and the time it opens again.
 *  `q`: {retry_after_seconds, retry_at, since}. `since` (a Date or milliseconds) is when the answer came: the time left is counted from it, so a
 *  message read an hour later says what is left now. Without seconds, the clock time the server gave ("14:20" or "25/11 14:20") is used. */
export function quotaSentence(label, q = {}, now = new Date()) {
  const who = label || L.label;
  if (finite(q.retry_after_seconds) && Number(q.retry_after_seconds) > 0) {
    let left = Number(q.retry_after_seconds);
    const since = q.since instanceof Date ? q.since.getTime() : finite(q.since) ? Number(q.since) : null;
    if (since !== null) left -= Math.max(0, (now.getTime() - since) / 1000);
    return L.quota.sentence(who, left > 30 ? L.quota.after(spanWords(left)) : L.quota.reopened);
  }
  const m = /^(?:(\d{1,2}\/\d{1,2})\s+)?(\d{1,2}:\d{2})$/.exec(String(q.retry_at ?? '').trim());
  if (m) return L.quota.sentence(who, m[1] ? L.quota.atDate(m[2], m[1]) : L.quota.atTime(m[2]));
  return L.quota.sentence(who, L.quota.unknown);
}

/** Everything the quota message needs: the sentence, the one button (the other agent, with its label) and why it cannot be pressed.
 *  `rec`: the failed job or turn ({agent, model, retry_after_seconds, retry_at, finished|at}); `info`: GET /api/agents. */
export function quotaView(info, rec, now = new Date()) {
  const used = usedAgent(info, rec);
  const other = otherAgent(info, used);
  const finished = finite(rec?.finished) ? Number(rec.finished) * 1000 : null;
  const sentence = quotaSentence(used.label, { retry_after_seconds: rec?.retry_after_seconds, retry_at: rec?.retry_at, since: finished }, now);
  if (!other) return { used, sentence, other: null, button: '', canSwitch: false, why: L.quota.noOther };
  const down = other.available === false;
  return { used, sentence, other, button: L.quota.switchTo(other.label), canSwitch: !down, why: down ? L.quota.otherDown(other.label, other.reason) : '' };
}

/** Is this failed job or turn a quota answer? (`error_kind` of a script job, `error` / `error_code` of a draft job or an edit turn.) */
export const isQuota = (rec) => QUOTA_CODES.has(rec?.error_kind) || QUOTA_CODES.has(rec?.error_code) || QUOTA_CODES.has(rec?.error);

// ---------------------------------------------------------------- the settings box: the default agent for new projects
/** What the default select shows: the agent of the machine's default, else the one the file calls default. */
export function defaultView(info) {
  const list = agentsOf(info);
  const value = findAgent(info, info?.machine_default) ? info.machine_default : (findAgent(info, info?.default) ? info.default : (list[0]?.id || ''));
  return { value, options: list.map((a) => ({ value: a.id, text: a.available === false ? L.unavailableOption(a.label) : a.label })), disabled: !list.length };
}
