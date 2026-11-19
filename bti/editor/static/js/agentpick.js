// The agent select, the same on every step that calls a model, and the quota message with its one button.
//   const pick = mountAgentPick(container, { pid, step: 'script' | 'storyboard', scope, onChange });
//   pick.effective()  -> {id, label, model, source} of the agent that WILL be used for this step (null while unknown)
//   pick.agents()     -> the answer of GET /api/agents      pick.refresh() reads both again      pick.unmount()
//   container.append(quotaNode({ pid, step, rec, rerun }))  one sentence naming the agent and the time, one button
// A choice asks PUT /api/projects/{pid}/agent with the revision the page holds (one retry when it is stale: the owner's intent is explicit and
// the steps are independent). "Dùng cho cả dự án" makes the chosen agent the project's agent and removes the per-step choices. The decisions
// are in agentlogic.js (pure, tested); the words are in labels.js (AGENT_LABELS); errors go through errmsg.js (errorToast).
import { api } from './api.js';
import { MOCK } from './config.js';
import { h, kids, toast, errorToast } from './util.js';
import { AGENT_LABELS as L } from './labels.js';
import { selectView, sourceView, unavailableNote, canChange, stepBody, projectBody, effectiveOf, quotaView } from './agentlogic.js';

const P = (pid) => `/api/projects/${encodeURIComponent(pid)}`;

// every select of the page hears about a change made by another one (the draft panel and the prompt box share the step "storyboard")
const listeners = new Set();
const announce = (detail) => { for (const fn of [...listeners]) { try { fn(detail); } catch { /* one listener never stops the others */ } } };
export const onAgentChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };

export const loadAgents = (refresh = false) => api.get(refresh ? '/api/agents?refresh=1' : '/api/agents');
export const loadProjectAgent = (pid) => api.get(`${P(pid)}/agent`);

/** PUT the project's choice. `makeBody(rev)` builds the body; with no `doc` the revision is read first; a stale answer (409) reads it again and
 *  asks once more. Returns the new document (same shape as GET). */
export async function putProjectAgent(pid, makeBody, doc = null) {
  let cur = doc || await loadProjectAgent(pid);
  try { return await api.put(`${P(pid)}/agent`, makeBody(cur.rev)); }
  catch (e) {
    if (e?.status !== 409) throw e;
    cur = await loadProjectAgent(pid);
    return await api.put(`${P(pid)}/agent`, makeBody(cur.rev));
  }
}
export const setStepAgent = (pid, step, id, doc = null) => putProjectAgent(pid, (rev) => stepBody(step, id, rev), doc);
export const setProjectAgent = (pid, id, doc = null) => putProjectAgent(pid, (rev) => projectBody(id, rev), doc);

let seq = 0;
export function mountAgentPick(container, { pid, step, scope = null, onChange = null } = {}) {
  let dead = false, busy = false, info = null, doc = null;
  const uid = ++seq;
  const sel = h('select', { id: `agent-select-${step}-${uid}`, class: 'agent-select', 'data-step': step, 'aria-label': L.label, title: L.titleHint,
    onchange: () => choose(sel.value) });
  const label = h('label', { class: 'agent-label', for: sel.id, text: L.label + ':', title: L.titleHint });
  const src = h('span', { class: 'agent-source', text: L.loading });
  const whole = h('button', { type: 'button', class: 'small text-btn agent-whole', text: L.whole, title: L.wholeHint, hidden: true, onclick: () => useForProject() });
  const warn = h('div', { class: 'agent-warn hint warn', role: 'status', hidden: true });
  const root = h('div', { class: 'agent-pick', 'data-agent-step': step },
    h('div', { class: 'agent-row' }, label, sel),
    h('div', { class: 'agent-line hint' }, src, whole),
    warn);
  container.replaceChildren(root);

  const effective = () => effectiveOf(doc, step);

  function paint() {
    if (dead) return;
    const eff = effective();
    const v = selectView(info, eff, { busy });
    sel.replaceChildren(...v.options.map((o) => h('option', { value: o.value, text: o.text, disabled: o.disabled || null })));
    sel.value = v.value;
    sel.disabled = v.disabled;
    const s = sourceView(eff);
    src.textContent = s.text;
    whole.hidden = !s.whole || busy;
    const why = unavailableNote(info, eff);
    warn.hidden = !why;
    warn.textContent = why;
    root.dataset.agent = eff?.id || '';
    root.dataset.model = eff?.model || '';
    root.dataset.source = eff?.source || '';
  }

  async function refresh(refreshAgents = false) {
    try {
      [info, doc] = await Promise.all([loadAgents(refreshAgents), loadProjectAgent(pid)]);
    } catch (e) {
      if (!MOCK && !dead) errorToast(e, L.loadFail);
    }
    paint();
    return effective();
  }

  async function ask(run) {
    busy = true; paint();
    try { doc = await run(); announce({ pid, step, from: uid }); onChange?.(effective(), doc); }
    catch (e) { errorToast(e, L.changeFail, 8000); await refresh(); }
    finally { busy = false; paint(); }
  }
  async function choose(id) {
    if (!canChange(info, effective(), id, { busy })) { paint(); return; }
    await ask(() => setStepAgent(pid, step, id, doc));
  }
  async function useForProject() {
    const id = effective()?.id;
    if (!id || busy) return;
    await ask(() => setProjectAgent(pid, id, doc));
    toast(L.wholeDone(effective()?.label || ''), 'ok', 3500);
  }

  const off = onAgentChange((d) => { if (d.pid === pid && d.from !== uid && !busy) refresh(); });
  const unmount = () => { dead = true; off(); root.remove(); };
  scope?.add?.(unmount);
  const ready = refresh();                                // resolves when the first answer was drawn (the select never rejects)
  return {
    unmount, refresh, ready, root,
    effective, agents: () => info, doc: () => doc,
    /** Make `id` this step's agent (the quota button does this through quotaNode; the page may too). */
    async setStep(id) { doc = await setStepAgent(pid, step, id, doc); announce({ pid, step, from: uid }); paint(); onChange?.(effective(), doc); return effective(); },
  };
}

/** The quota message: ONE sentence naming the agent and the time it opens again, and exactly ONE button, "Chuyển sang <the other agent> và chạy lại".
 *  The button stores the other agent as this step's choice and then calls `rerun()` (the same request again). Nothing switches by itself.
 *  `rec`: the failed job or turn ({agent, model, retry_after_seconds, retry_at, finished}); `onSwitched` runs after the rerun was started. */
export function quotaNode({ pid, step, rec, rerun, onSwitched = null, getAgents = loadAgents } = {}) {
  let info = null, busy = false, dead = false;
  const sentence = h('div', { class: 'agent-quota-text' });
  const slot = h('div', { class: 'agent-quota-action' });
  const box = h('div', { class: 'agent-quota', role: 'status', 'data-agent-quota': '' }, sentence, slot);

  function paint() {
    if (dead) return;
    const v = quotaView(info, rec);
    sentence.textContent = v.sentence;
    if (!info) { slot.replaceChildren(); return; }                              // the other agent is not known yet
    if (!v.other) { slot.replaceChildren(h('div', { class: 'hint', text: v.why })); return; }
    slot.replaceChildren(...kids(
      h('button', { type: 'button', class: 'primary agent-quota-switch', text: busy ? L.quota.switching : v.button, disabled: busy || !v.canSwitch, onclick: () => go(v) }),
      v.why ? h('div', { class: 'hint warn agent-quota-why', text: v.why }) : null));
  }
  async function go(v) {
    if (busy) return;
    busy = true; paint();
    try { await setStepAgent(pid, step, v.other.id); announce({ pid, step, from: 0 }); }
    catch (e) { errorToast(e, L.quota.fail, 8000); busy = false; paint(); return; }
    try { await rerun?.(); onSwitched?.(); }
    catch (e) { errorToast(e, L.quota.rerunFail, 8000); }
    busy = false; paint();
  }
  paint();
  Promise.resolve().then(() => getAgents()).then((r) => { info = r; paint(); }).catch(() => { /* the sentence stays; there is no button without the list */ });
  box.stop = () => { dead = true; };
  return box;
}
