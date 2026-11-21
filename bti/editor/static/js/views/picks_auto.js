// The agent's bar of the pictures page ("Chọn hình"): the button "Để agent chọn hình" with the agent select of the step beside it, the progress
// line of the job with its cancel button, and at the end the result in one sentence with "Chọn lại phần còn thiếu". Mounted by views/picks.js into
// #pk-auto; the page gives it four small functions (what the document looks like now, reload, save first, the project id).
//   const auto = mountPicksAuto(host, { pid, scope, state: () => ({ doc, chapters, approved, narrationOk, hasMain }), reload, saveFirst });
//   auto.reasonFor(beatId, rec)  the agent's reason to show under the pictures of a line ('' when the line is no longer as the agent wrote it)
//   auto.whyMissing(beatId)      c4pages: why the last run left this line without a picture, in plain words ('' when it was not in the last result)
//   onInfo()                     c4pages: called when what the page reads from GET .../picks/auto (the reasons, the last result) changed
// The job is POST /api/projects/{pid}/picks/auto (a long job of kind `picks`); the page reads GET .../picks/auto (the running job, the last result,
// the reasons) and GET /api/longjobs/{id}. The decisions are in picks_logic.js (pure, tested); the words in labels.js (PICKS_AUTO_LABELS) and errmsg.js.
import { api } from '../api.js';
import { h, kids, toast, confirmDialog } from '../util.js';
import { PICKS_AUTO_LABELS as L } from '../labels.js';
import { STAGE_CODES, describeError, jobErrorText } from '../errmsg.js';
import { watchIdle } from '../idlewatch.js';
import { mountAgentPick, quotaNode } from '../agentpick.js';
import { isQuota, findAgent, STEP_PICKS } from '../agentlogic.js';
import * as PL from './picks_logic.js';

const errText = (e) => { const c = e?.body?.code; return STAGE_CODES.picks[c] || STAGE_CODES.draft[c] || describeError(e).text; };
const jobText = (job) => STAGE_CODES.picks[job?.error_code] || STAGE_CODES.draft[job?.error_code] || jobErrorText(job).text;

export function mountPicksAuto(host, { pid, scope, state, reload, saveFirst, onInfo = null }) {
  const U = `/api/projects/${encodeURIComponent(pid)}/picks/auto`;
  let dead = false, info = null, job = null, jobId = null, starting = false, ended = null, lastBody = null, polling = false;
  const root = h('div', { class: 'pk-auto-bar', 'data-picks-auto': '' });
  const pickHost = h('div', { class: 'pk-auto-pick' });                          // kept across repaints: the select must not lose its state
  const pick = mountAgentPick(pickHost, { pid, step: STEP_PICKS, scope, onChange: () => paint() });
  host.replaceChildren(root);

  const usable = () => { const e = pick.effective(); const a = e ? findAgent(pick.agents(), e.id) : null; return a ? a.available !== false : undefined; };
  const controls = () => PL.autoControls({ ...state(), job, last: info?.last, agentUsable: usable() });

  function paint() {
    if (dead) return;
    const c = controls();
    const prog = PL.autoProgress(job);
    const res = info?.last?.result;
    const busy = c.running || starting;
    const top = h('div', { class: 'pk-auto-row' },
      h('b', { class: 'pk-auto-title', text: L.title }), pickHost,
      h('button', { class: 'primary', id: 'pk-auto-start', text: starting && !c.running ? L.starting : L.button, title: c.start.title || L.intro, disabled: busy || c.start.disabled,
        onclick: () => begin(c.start.body, c.start.confirm) }),
      c.cancel.visible ? h('button', { class: 'small', id: 'pk-auto-cancel', text: L.cancel, onclick: cancel }) : null);
    const body = [top];
    if (busy) {
      body.push(h('div', { class: 'pk-auto-prog', role: 'status' }, h('progress', { max: 1, value: prog.fraction }), h('span', { id: 'pk-auto-line', text: prog.text || L.working })));
      if (info?.limits) body.push(h('div', { class: 'hint', text: L.limits(info.limits.plan) }));
    } else {
      if (ended) body.push(failureNode(ended));
      if (res) body.push(resultNode(res, c));
      else if (!ended) body.push(h('div', { class: 'hint', text: L.intro }));
    }
    root.replaceChildren(...kids(...body));
    for (const e of pickHost.querySelectorAll('select, button')) e.disabled = c.select.disabled;      // the agent is not changed under a running job
    root.dataset.state = busy ? 'running' : ended && ended.state === 'error' ? 'failed' : res ? 'result' : 'idle';
  }

  function failureNode(j) {
    if (j.state === 'cancelled') return h('div', { class: 'pk-banner', text: L.cancelled });
    if (j.state !== 'error') return null;
    if (isQuota({ error_code: j.error_code })) {                                  // the agent's quota is used up: the sentence names it and the time, one button switches and runs again
      const rec = { ...j, retry_after_seconds: j.meta?.retry_after_seconds, retry_at: j.meta?.retry_at };
      return h('div', { class: 'pk-banner warn pk-auto-quota' }, quotaNode({ pid, step: STEP_PICKS, rec, rerun: () => begin(lastBody || { beats: null, redo: false }, null, true), getAgents: async () => pick.agents() }));
    }
    return h('div', { class: 'pk-banner warn', text: L.failed(jobText(j)) });
  }

  function resultNode(res, c) {
    const without = PL.autoWithout(res);
    const missing = PL.autoMissing(res);                                                            // a line that got some pictures says what it is still missing
    const detail = PL.autoDetailText(res);
    return h('div', { class: 'pk-auto-result' },
      h('div', { class: 'row' },
        h('span', { class: 'pk-auto-sentence', id: 'pk-auto-sentence', text: PL.autoResultText(res) }),
        c.again.visible ? h('button', { id: 'pk-auto-again', text: L.again, disabled: c.again.disabled || starting, onclick: () => begin(c.again.body, c.again.confirm) }) : null),
      detail ? h('div', { class: 'hint', text: detail }) : null,
      res.stopped === 'time' ? h('div', { class: 'hint warn', text: L.stopped.time }) : null,
      without.length ? h('details', { class: 'pk-auto-without' }, h('summary', { text: L.withoutTitle(without.length) }), h('ul', null, without.map((w) => h('li', { text: w.text })))) : null,
      missing.length ? h('details', { class: 'pk-auto-without' }, h('summary', { text: L.missingTitle }), h('ul', null, missing.map((t) => h('li', { text: t })))) : null);
  }

  // ---------------------------------------------------------------- start, follow, cancel
  async function begin(body, confirm, skipConfirm = false) {
    if (starting || PL.autoRunning(job)) return;
    if (confirm && !skipConfirm) {
      const t = confirm === 'redo' ? L.confirmRedo : L.confirmApproved;
      if (!(await confirmDialog(t.message, { title: t.title, ok: t.ok }))) return;
    }
    starting = true; ended = null; lastBody = body; paint();
    try {
      await saveFirst();                                                          // what the owner has typed is saved first: the job writes the same file
      const r = await api.post(U, body);
      jobId = r.job_id; job = null;
      await poll();
    } catch (e) { starting = false; toast(L.startFail + errText(e), 'err', 9000); paint(); return; }
    starting = false; paint();
  }
  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); await poll(); }
    catch (e) { toast(L.cancelFail + errText(e), 'err', 9000); }
  }
  async function poll() {
    if (dead || !jobId || polling) return;
    polling = true;
    try { job = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`); } catch { polling = false; return; }
    polling = false;
    if (dead) return;
    if (PL.autoRunning(job)) { paint(); return; }
    const finished = job; jobId = null; job = null; ended = finished;
    await refreshInfo();
    await reload();                                                               // the page shows the pictures the agent wrote
    paint();
  }
  async function refreshInfo() { try { info = await api.get(U); onInfo?.(); } catch { /* the bar stays as it was */ } }

  scope.interval(() => { if (jobId) poll(); }, 1500);
  scope.add?.(() => { dead = true; pick.unmount(); });
  watchIdle(scope, { root: () => root, idle: () => !jobId && !starting,                // a run started in another tab (or by an agent) shows up here
    check: async () => {
      const o = await api.get(U);
      if (o.running) { info = o; jobId = o.running.id; job = o.running; ended = null; paint(); }
      else if (!info) { info = o; onInfo?.(); }
      else if (o.last?.finished !== info.last?.finished) { info = o; await reload(); paint(); onInfo?.(); }
    } });

  (async () => {
    await refreshInfo();
    if (info?.running) { jobId = info.running.id; job = info.running; }
    paint();
  })();
  paint();
  return {
    reasonFor: (beatId, rec) => PL.autoReasonFor(rec, info?.reasons, beatId),
    whyMissing: (beatId) => { const w = (info?.last?.result?.lines_without || []).find((x) => x.beat === beatId); return typeof w?.why === 'string' ? w.why : ''; },
    refresh: async () => { await refreshInfo(); paint(); },
    /** A run was started elsewhere on this page (the card of the prompt box): take its job in and follow it. */
    follow: async () => { await refreshInfo(); if (info?.running) { jobId = info.running.id; job = info.running; ended = null; } paint(); },
    unmount() { dead = true; pick.unmount(); root.remove(); },
  };
}
