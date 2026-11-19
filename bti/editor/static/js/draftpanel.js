// The storyboard draft panel (design 7): what is ready, the model, "Dựng bản nháp", progress, cancel, then open the proposal.
// Mounted by the storyboard view into a container element it owns:
//   const unmount = mountDraftPanel(container, { pid, scope, onProposal: (proposalId) => openProposals(onApplied, proposalId) });
// The panel is self contained: it talks to /api/projects/{pid}/draft and /api/longjobs/{id} through the generic verbs of api.js.
// The agent that builds the draft is chosen with the agent select (agentpick.js, step "storyboard"); the panel sends no model of its own, the
// server uses the project's agent. When the agent's quota is used up the message names it and offers one button (quotaNode).
// The Vietnamese words are in labels.js (DRAFT_LABELS, used here as TEXT); errors go through errmsg.js (stageErrorText / errorInto).
import { api } from './api.js';
import { h, toast, errorInto, confirmDialog } from './util.js';
import { stageJobErrorText, stageErrorText } from './errmsg.js';
import { DRAFT_LABELS, AGENT_LABELS as AL } from './labels.js';
import { watchIdle, jobWatcher } from './idlewatch.js';
import { mountAgentPick, quotaNode, loadAgents } from './agentpick.js';
import { isQuota, STEP_STORYBOARD } from './agentlogic.js';

const TEXT = DRAFT_LABELS;
const ACTIVE = new Set(['queued', 'waiting', 'running']);

export function mountDraftPanel(container, { pid, scope = null, onProposal = null, onJobEnd = null, inDialog = false } = {}) {
  let dead = false, timer = null, jobId = null, info = null, job = null;
  const seen = jobWatcher();
  const root = h('div', { class: 'draft-panel' });
  container.replaceChildren(root);
  const pickHost = h('div', { class: 'row draft-agent' });                      // kept across redraws: the select must not lose its state
  const pick = mountAgentPick(pickHost, { pid, step: STEP_STORYBOARD, scope });

  const poll = () => { clearTimeout(timer); if (!dead) timer = setTimeout(tick, 1500); };
  scope?.add?.(() => unmount());

  async function load() {
    try { info = await api.get(`/api/projects/${encodeURIComponent(pid)}/draft`); } catch (e) { if (!dead) errorInto(root, e, 'Không đọc được trạng thái bản nháp: '); return; }
    if (dead) return;
    jobId = info.job_id || jobId;
    seen.know(jobId);
    render();
    if (jobId && !job) tick();
  }
  async function tick() {
    if (dead || !jobId) return;
    try { job = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`); } catch (e) { if (!dead) poll(); return; }
    if (dead) return;
    if (!ACTIVE.has(job.state)) {
      const finished = job; jobId = null;
      scope?.timeout?.(() => onJobEnd?.(), 1000);          // once more a moment later: the stepper must not keep saying "Đang chạy"
      await load();
      onJobEnd?.();
      job = finished;
      render();
      return;
    }
    render();
    poll();
  }
  async function start(provider, { confirm = true } = {}) {
    if (confirm && info?.state?.proposal && provider && !(await confirmDialog(TEXT.confirmReplace, { ok: TEXT.start }))) return;
    const body = { provider };                                                  // no model: the server uses the project's agent
    try {
      const r = await api.post(`/api/projects/${encodeURIComponent(pid)}/draft/start`, body);
      jobId = r.job_id; seen.know(jobId); job = null; render(); tick();
    } catch (e) { toast('Không bắt đầu được: ' + stageErrorText('draft', e).text, 'err', 9000); }
  }
  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); tick(); } catch (e) { toast('Không dừng được: ' + stageErrorText('draft', e).text, 'err', 9000); }
  }

  function readyRow(label, r) {
    return h('div', { class: 'row' }, h('span', { class: 'chip ' + (r.ok ? 'ok' : 'partial'), text: r.ok ? 'xong' : 'chưa' }), h('b', { text: ' ' + label + ': ' }), r.detail);
  }
  function render() {
    if (dead || !info) return;
    const running = !!(jobId && job && ACTIVE.has(job.state)) || (!!jobId && !job);
    const kids = [h('h4', { text: TEXT.title }), h('div', { class: 'hint', text: TEXT.intro }),
      readyRow(TEXT.voice, info.ready.voice), readyRow(TEXT.picks, info.ready.picks)];
    const st = info.state || {};
    if (st.state === 'stale') kids.push(h('div', { class: 'banner warn', text: TEXT.stale }));
    if (running) {
      const parts = (job?.parts || []).map((p) => h('div', { class: 'hint' }, `${p.title}: ${TEXT.partState[p.state] || p.state}`, p.note ? ' - ' + p.note : ''));
      const who = job?.meta?.agent?.label;
      kids.push(h('div', { class: 'row' }, h('b', { text: TEXT.running }), h('progress', { max: 1, value: job?.progress ?? 0 }), h('button', { class: 'small', text: TEXT.cancel, onclick: cancel })),
        who ? h('div', { class: 'hint draft-running-agent', text: AL.runWith(who) }) : null, ...parts);
    } else {
      kids.push(pickHost,
        h('div', { class: 'row' }, h('button', { class: 'primary', text: TEXT.start, disabled: !info.ready.ok, onclick: () => start('agy') }),
          h('button', { class: 'small', text: TEXT.startAuto, disabled: !info.ready.ok, onclick: () => start('auto') })),
        info.ready.ok ? null : h('div', { class: 'hint warn', text: TEXT.notReady }));
      const lr = info.last_run;
      if (job && job.state === 'error') {
        if (isQuota({ error_code: job.error_code })) {         // the agent's quota is used up: the sentence names it and the time, one button switches and runs again
          const rec = { ...job, retry_after_seconds: job.meta?.retry_after_seconds, retry_at: job.meta?.retry_at };
          kids.push(h('div', { class: 'banner warn draft-quota' }, quotaNode({ pid, step: STEP_STORYBOARD, rec, rerun: () => start('agy', { confirm: false }), getAgents: async () => pick.agents() || loadAgents() })));
        } else kids.push(h('div', { class: 'banner warn', text: stageJobErrorText('draft', job).text }));
      }
      if (lr && lr.status === 'tampered') kids.push(h('div', { class: 'banner warn', text: TEXT.tampered }));
      if (st.proposal) {
        const note = lr && lr.status === 'done' ? [(lr.n_content != null && lr.n_cards != null ? TEXT.doneSplit.replace('%n', lr.n_shots).replace('%c', lr.n_content).replace('%k', lr.n_cards) : TEXT.doneNote.replace('%n', lr.n_shots)), (lr.errors_left || lr.incomplete) ? ' ' + TEXT.issues.replace('%n', (lr.errors_left || 0) + (lr.incomplete || 0)) : ''].join('') : st.detail;
        kids.push(h('div', { class: 'row' }, h('span', { class: 'hint', text: note + (lr && lr.status === 'done' && lr.agent?.label ? ' ' + AL.doneBy(lr.agent.label) : '') }), onProposal ? h('button', { class: 'primary small', text: TEXT.open, onclick: () => onProposal(st.proposal) }) : null));
      }
    }
    root.replaceChildren(...kids.filter(Boolean));
  }
  function unmount() { dead = true; clearTimeout(timer); pick.unmount(); root.remove(); }

  load();
  // a draft started in another tab shows up here within a few seconds (one cheap GET: the list of draft jobs)
  if (scope) watchIdle(scope, { root: () => root, idle: () => !dead && !jobId, ownDialog: inDialog,
    check: async () => {
      const r = await api.get(`/api/projects/${encodeURIComponent(pid)}/longjobs?kind=draft`);
      const what = seen(r);
      const act = what === 'active' ? (r?.items || []).find((j) => ACTIVE.has(j.state)) : null;
      if (act && !jobId) { jobId = act.id; job = null; render(); tick(); }
      else if (what === 'changed') { await load(); onJobEnd?.(); }                             // a draft ended elsewhere
    } });
  return unmount;
}
