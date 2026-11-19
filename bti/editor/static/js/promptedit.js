// "Sửa video bằng lời" (step 5): type what to change, see what changed, undo it.
// One box beside the preview: the text field, the scope in words, the send button, then the thread of turns.
// A turn changes the saved storyboard on the server (fast or deep path); a card lists the changes with before and after pictures.
//   const unmount = mountPromptEdit(container, { pid, scope, takeIn, onPreview, onJobEnd });
//   takeIn(): the editor takes the new saved storyboard in (reload, or the merge with unsaved edits)
//   onPreview({t0, t1}): the existing preview clip of a range
// The agent that does the work is chosen with the agent select beside the send button (agentpick.js, step "storyboard"); the box sends no model
// of its own. When that agent's quota is used up the card names it and the time and offers ONE button: switch to the other agent and send the
// same request again (quotaNode).
// The decisions are in editlogic.js (pure, tested); the words are in labels.js (EDIT_LABELS); errors go through errmsg.js.
import { api } from './api.js';
import { h, kids, toast, confirmDialog, detailFold } from './util.js';
import { stageErrorText } from './errmsg.js';
import { EDIT_LABELS as L, AGENT_LABELS as AL } from './labels.js';
import { ctx, bus } from './ctx.js';
import { wordIndexAt } from './logic.js';
import { watchIdle, jobWatcher } from './idlewatch.js';
import { mountAgentPick, quotaNode, loadAgents } from './agentpick.js';
import { STEP_STORYBOARD, labelForModel } from './agentlogic.js';
import { ACTIVE, pickScope, retryScope, addToSelection, turnView, progressView, previewRange, newlyChanged, shotNumber } from './editlogic.js';

export function mountPromptEdit(container, { pid, scope = null, takeIn = null, onPreview = null, onJobEnd = null } = {}) {
  let dead = false, timer = null, jobId = null, job = null, thread = [], first = true, busy = false;
  let choice = 'auto', multi = false, selected = [], lastSig = '';
  const seenTurns = new Map(), shownStatus = new Map();
  let shownFirst = true;
  const seenJobs = jobWatcher();
  const P = `/api/projects/${encodeURIComponent(pid)}`;

  const root = h('div', { class: 'prompt-edit' });
  container.replaceChildren(root);

  // ---------------------------------------------------------------- the form
  const ta = h('textarea', {
    class: 'prompt-instruction', rows: 2, placeholder: L.placeholder, 'aria-label': L.title,
    onkeydown: (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit(); } },
  });
  const btnSend = h('button', { class: 'primary prompt-btn-submit', onclick: () => submit(), text: L.send, title: L.sendHint });
  const pills = {};
  const pillRow = h('div', { class: 'prompt-pills', role: 'group', 'aria-label': L.scopeLead },
    ...[['shots', L.scopeShots], ['chapter', L.scopeChapter], ['all', L.scopeAll]].map(([k, text]) =>
      (pills[k] = h('button', { type: 'button', class: 'pill', text, onclick: () => { choice = k; paintScope(true); } }))));
  const agentHost = h('div', { class: 'prompt-agent' });
  const pick = mountAgentPick(agentHost, { pid, step: STEP_STORYBOARD, scope });
  const multiBox = h('input', { type: 'checkbox', class: 'prompt-multi', onchange: (e) => setMulti(e.target.checked) });
  const multiLabel = h('label', { class: 'chk prompt-multi-label', title: L.multiHint }, multiBox, h('span', { text: L.multi }));
  const wordsLine = h('div', { class: 'prompt-scope-words' });
  const chipsBox = h('div', { class: 'prompt-shots-chips' });
  const form = h('div', { class: 'prompt-form' },
    ta,
    pillRow, wordsLine, chipsBox,
    agentHost,                                                                   // the agent select has a row of its own: the box is narrow
    h('div', { class: 'prompt-send-row' }, multiLabel,
      h('span', { class: 'grow' }), btnSend));
  const threadHead = h('div', { class: 'prompt-thread-header' });
  const threadList = h('div', { class: 'prompt-thread-list', tabindex: 0, 'aria-label': L.thread });
  root.append(form, threadHead, threadList);

  // ---------------------------------------------------------------- the scope
  const draftShots = () => ctx.store?.draft?.shots || [];
  const chapters = () => ctx.store?.timing?.chapters || [];
  const scopeNow = () => {
    const t = ctx.t || 0;
    return pickScope({ choice, selected, shots: draftShots(), chapters: chapters(), t, wIdx: chapters().some((c) => c.start == null) ? wordIndexAt(ctx.words(), t) : -1 });
  };
  function setMulti(on) {
    multi = on;
    if (on) choice = 'shots';
    else { selected = ctx.store?.sel?.shot ? [ctx.store.sel.shot] : []; choice = 'auto'; }
    paintScope(true);
  }
  function paintScope(force = false) {
    if (dead) return;
    const valid = new Set(draftShots().map((s) => s.id));
    selected = selected.filter((id) => valid.has(id));
    const sc = scopeNow();
    const sig = [sc.kind, sc.words, selected.join(','), multi, busy].join('|');
    if (!force && sig === lastSig) return;
    lastSig = sig;
    for (const [k, b] of Object.entries(pills)) { b.classList.toggle('on', sc.kind === k); b.disabled = busy; }
    multiBox.checked = multi; multiBox.disabled = busy;
    wordsLine.textContent = multi && sc.kind === 'shots' && selected.length < 2 ? `${L.scopeLead} ${sc.words}. ${L.multiOn}` : `${L.scopeLead} ${sc.words}`;
    const shots = draftShots();
    chipsBox.replaceChildren(...(multi || selected.length > 1 ? selected.map((id) => {
      const n = shotNumber(shots, id);
      return h('span', { class: 'prompt-shot-chip' }, h('span', { text: `Cảnh ${n ?? ''}`.trim() }),
        h('button', { type: 'button', class: 'prompt-shot-chip-del', title: L.dropShot(n ?? ''), disabled: busy, text: '×',
          onclick: () => { selected = selected.filter((x) => x !== id); paintScope(true); } }));
    }) : []));
    btnSend.disabled = busy || !sc.ok;
  }
  const offStore = ctx.store.on((kind) => {
    if (kind === 'select') {
      const id = ctx.store.sel?.shot;
      selected = multi ? addToSelection(selected, id, { multi, playing: ctx.playing }) : (id ? [id] : []);
      paintScope();
    } else if (kind === 'draft' || kind === 'load') paintScope();
  });
  const offTime = bus.on('time', () => paintScope());
  const offTick = bus.on('tick', () => { if (choice === 'chapter' || choice === 'auto') paintScope(); });
  scope?.add?.(() => { offStore?.(); offTime?.(); offTick?.(); });

  // ---------------------------------------------------------------- the thread
  async function loadThread() {
    let r = null;
    try { r = await api.get(`${P}/draft/thread`); } catch { /* the old list stays; the next look tries again */ }
    if (dead) return;
    if (r) {
      thread = r.turns || [];
      const fresh = newlyChanged(thread, seenTurns, first);
      first = false;
      if (r.active_job_id && !jobId) { jobId = r.active_job_id; seenJobs.know(jobId); job = null; busy = true; setTimeout(tick, 0); }
      if (fresh.length && takeIn) { try { await takeIn(fresh[fresh.length - 1]); } catch { /* takeIn reports its own errors */ } }
    }
    if (!dead) { renderThread(); paintScope(true); }
  }

  function setBusy(on) {
    busy = on;
    ta.disabled = on;
    paintScope(true);
  }

  async function tick() {
    if (dead || !jobId) return;
    try { job = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`); } catch { if (!dead) timer = setTimeout(tick, 1500); return; }
    if (dead) return;
    if (!ACTIVE.has(job.state)) {
      jobId = null; job = null; setBusy(false);
      await loadThread();
      onJobEnd?.();
      return;
    }
    paintProgress();
    timer = setTimeout(tick, 1200);
  }

  async function submit(retry = null) {
    if (busy || dead) return;
    const text = (retry ? retry.instruction : ta.value).trim();
    if (!text) { toast(L.emptyInstruction, 'warn', 4000); ta.focus(); return; }
    if (text.length > 2000) { toast(L.tooLong, 'warn', 4000); return; }
    if (!draftShots().length) { toast(L.noStoryboard, 'warn', 4000); return; }
    let payload;
    if (retry) { payload = retryScope(retry, draftShots()); if (!payload) { toast(L.noShotChosen, 'warn', 4000); return; } }
    else { const sc = scopeNow(); if (!sc.ok) { toast(sc.why, 'warn', 4000); return; } payload = sc.payload; }
    setBusy(true);
    try {
      const res = await api.post(`${P}/draft/edit`, { instruction: text, scope: payload, mode: 'auto', base_rev: ctx.store?.rev });
      jobId = res.job_id; seenJobs.know(jobId); job = null;
      if (!retry) ta.value = '';
      await loadThread();
      tick();
    } catch (e) { toast(L.sendFail + stageErrorText('draft', e).text, 'err', 8000); setBusy(false); }
  }

  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); tick(); }
    catch (e) { toast(L.cancelFail + stageErrorText('draft', e).text, 'err', 8000); }
  }

  /** One call on a turn (undo, resolve); then the editor takes the new storyboard in and the thread is read again. */
  async function act(turn, path, body, okText) {
    try {
      const res = await api.post(`${P}/draft/edit/${encodeURIComponent(turn.id)}/${path}`, body);
      if (okText) toast(okText, 'ok', 3000);
      return res || {};
    } catch (e) {
      if (path === 'undo' && e.status === 409 && e.body?.code === 'undo_conflict' && !body.force) return await undoConflict(turn, e.body.conflicts || []);
      toast(L.actionFail + stageErrorText('draft', e).text, 'err', 8000);
      return null;
    }
  }
  async function undoConflict(turn, ids) {
    const nums = ids.map((id) => shotNumber(draftShots(), id)).filter((n) => n != null).sort((a, b) => a - b);
    const words = nums.length ? `cảnh ${nums.join(', ')}` : 'các cảnh này';
    const ok = await confirmDialog(L.undoConflictLead(words), { title: L.undoConflictTitle, ok: L.undoForce, danger: true });
    return ok ? await act(turn, 'undo', { force: true }, L.undoDone) : null;
  }
  async function afterChange(turn, status) {
    seenTurns.set(turn.id, status);                // this page changed it: loadThread must not take it in a second time
    if (takeIn) { try { await takeIn({ ...turn, status }); } catch { /* takeIn reports its own errors */ } }
    await loadThread();
  }
  async function undo(turn) {
    const r = await act(turn, 'undo', { force: false }, L.undoDone);
    if (r && (r.ok || r.status)) await afterChange(turn, 'undone');
  }
  async function resolve(turn, action) {
    const r = await act(turn, 'resolve', { action }, L.resolved);
    if (!r) return;
    if (action === 'overwrite') await afterChange(turn, 'applied'); else await loadThread();
  }
  function preview(turn) {
    const r = previewRange(turn, draftShots());
    if (r) onPreview?.(r);
  }

  async function clearHistory() {
    if (!(await confirmDialog(L.clearAsk, { title: L.clear, ok: L.clearOk, danger: true }))) return;
    try { await api.del(`${P}/draft/thread`); thread = []; seenTurns.clear(); renderThread(); toast(L.cleared, 'ok', 2500); }
    catch (e) { toast(L.actionFail + stageErrorText('draft', e).text, 'err', 8000); }
  }

  // ---------------------------------------------------------------- the cards
  const frameUrl = (turn, shotId, when) => api.url(`${P}/draft/edit/${encodeURIComponent(turn.id)}/frames/${encodeURIComponent(shotId)}/${when}.jpg`);
  function frame(turn, c, when, has) {
    const cap = h('figcaption', { text: when === 'before' ? L.before : L.after });
    if (!has || !c.shotId) return h('figure', { class: 'prompt-frame none' }, h('div', { class: 'prompt-frame-box', text: L.noFrame }), cap);
    const box = h('div', { class: 'prompt-frame-box' });
    const img = h('img', { src: frameUrl(turn, c.shotId, when), alt: `${cap.textContent}, ${c.title}`, loading: 'lazy' });
    img.addEventListener('error', () => { box.textContent = L.frameFailed; box.classList.add('bad'); });
    box.append(img);
    return h('figure', { class: 'prompt-frame' }, box, cap);
  }
  function changeRow(turn, c) {
    return h('div', { class: 'prompt-change' },
      h('div', { class: 'prompt-change-head' }, h('span', { class: 'op ' + c.op, text: c.opText }), h('b', { text: c.title })),
      c.what ? h('div', { class: 'prompt-change-what', text: c.what }) : null,
      h('div', { class: 'prompt-frames' }, frame(turn, c, 'before', c.hasBefore), frame(turn, c, 'after', c.hasAfter)));
  }
  /** The buttons of a card: the only things the owner has to do on it. They sit right under the header line, above everything else. */
  function actionRow(turn, v) {
    const a = v.actions, btns = [];
    if (a.cancel) btns.push(h('button', { class: 'small prompt-btn-cancel', onclick: cancel, text: L.cancel }));
    if (a.choices) btns.push(
      h('button', { class: 'small primary prompt-btn-overwrite', text: L.choiceOverwrite, title: L.choiceOverwriteHelp, onclick: () => resolve(turn, 'overwrite') }),
      h('button', { class: 'small prompt-btn-discard', text: L.choiceDiscard, title: L.choiceDiscardHelp, onclick: () => resolve(turn, 'discard') }));
    if (a.preview) btns.push(h('button', { class: 'small prompt-btn-preview', text: L.preview, title: L.previewHint, onclick: () => preview(turn) }));
    if (a.undo) btns.push(h('button', { class: 'small prompt-btn-undo', text: L.undo, title: a.undo === 'gone' ? L.undoNone : L.undoHint, disabled: a.undo === 'gone', onclick: () => undo(turn) }));
    if (a.retry) btns.push(h('button', { class: 'small prompt-btn-retry', text: L.retry, disabled: busy, onclick: () => submit(turn) }));
    return btns.length ? h('div', { class: 'prompt-turn-actions' }, ...btns) : null;
  }
  /** The failed turn as the quota message reads it: the agent and the time it opens again, as the server counted it when the turn failed. (A turn only
   *  knows its start as a clock time of the SERVER's zone, so the time already gone is not subtracted here, unlike for a script job's epoch `finished`.) */
  const quotaRec = (turn) => ({ ...turn, finished: null });
  function card(turn) {
    const v = turnView(turn, { shots: draftShots(), chapters: chapters() });
    const kidsOf = [
      h('div', { class: 'prompt-turn-head' },
        h('span', { class: 'chip prompt-badge ' + v.tone, text: v.badge }),
        h('span', { class: 'chip', text: v.scope }),
        h('span', { class: 'grow' }),
        h('span', { class: 'muted prompt-turn-time', text: v.time })),
      actionRow(turn, v),
      h('div', { class: 'prompt-turn-instruction' }, h('b', { text: L.you + ': ' }), v.instruction),
    ];
    if (v.status === 'running') {
      kidsOf.push(h('div', { class: 'prompt-run' },
        h('span', { class: 'prompt-run-line', text: L.running }),
        h('progress', { class: 'prompt-progress', max: 1, value: 0 })));
    } else if (v.actions.settings) {
      // the agent's quota is used up: the sentence names the agent and the time; ONE button switches to the other agent and sends the same request again
      kidsOf.push(h('div', { class: 'prompt-turn-quota ' + v.tone }, quotaNode({ pid, step: STEP_STORYBOARD, rec: quotaRec(turn), rerun: () => submit(turn),
        getAgents: async () => pick.agents() || loadAgents() })));
    } else {
      if (v.headline) kidsOf.push(h('div', { class: 'prompt-turn-summary ' + v.tone, text: v.headline }));
      if (v.extra) kidsOf.push(h('div', { class: 'prompt-turn-extra hint', text: v.extra }));
      if (v.actions.choices) kidsOf.push(h('div', { class: 'hint prompt-choice-help', text: `${L.choiceOverwrite}: ${L.choiceOverwriteHelp} ${L.choiceDiscard}: ${L.choiceDiscardHelp}` }));
      if (v.showChanges) kidsOf.push(h('div', { class: 'prompt-changes' }, ...v.changes.map((c) => changeRow(turn, c))));
      if (v.noChanges) kidsOf.push(h('div', { class: 'prompt-turn-extra hint', text: L.changesNone }));
      if (v.way) kidsOf.push(h('div', { class: 'prompt-turn-way muted', text: v.way }));
      const who = turn.agent?.label || (turn.model ? labelForModel(pick.agents(), turn.model, '') : '');
      if (who) kidsOf.push(h('div', { class: 'prompt-turn-agent muted', text: AL.doneBy(who) }));
      if (v.detail) kidsOf.push(detailFold(v.detail, 'err-detail prompt-detail'));
    }
    return h('div', { class: 'prompt-turn-card st-' + v.status, 'data-turn': turn.id, 'data-status': v.status }, ...kidsOf);
  }
  function paintProgress() {
    const pv = progressView(job);
    for (const el of threadList.querySelectorAll('.prompt-run')) {
      const line = el.querySelector('.prompt-run-line'), bar = el.querySelector('progress');
      if (line) line.textContent = pv.line;
      if (bar) bar.value = pv.fraction;
    }
  }
  function renderThread() {
    threadHead.replaceChildren(...kids(h('h5', { text: `${L.thread} (${thread.length})` }), h('span', { class: 'grow' }),
      thread.length ? h('button', { class: 'small text-btn prompt-btn-clear', text: L.clear, onclick: clearHistory }) : null));
    const keepScroll = threadList.scrollTop;
    threadList.replaceChildren(...(thread.length
      ? thread.slice().reverse().map(card)                                   // the newest on top
      : [h('div', { class: 'empty muted', text: L.threadEmpty })]));
    threadList.scrollTop = keepScroll;
    // a turn that started, ended or needs a choice: its card goes to the top of the visible area (the first look at the page only remembers)
    const changed = thread.slice().reverse().filter((t) => shownStatus.get(t.id) !== t.status);
    for (const t of thread) shownStatus.set(t.id, t.status);
    if (shownFirst) shownFirst = false;
    else if (changed.length) {
      const el = threadList.querySelector(`[data-turn="${CSS.escape(changed[0].id)}"]`);
      if (el) threadList.scrollTop += el.getBoundingClientRect().top - threadList.getBoundingClientRect().top;
    }
    if (jobId) paintProgress();
  }

  function unmount() { dead = true; clearTimeout(timer); offStore?.(); offTime?.(); offTick?.(); pick.unmount(); root.remove(); }
  scope?.add?.(() => unmount());

  // a job started in another tab or window shows up here within a few seconds (one cheap GET: the list of draft jobs)
  if (scope) {
    watchIdle(scope, { root: () => root, idle: () => !dead && !jobId,
      check: async () => {
        const r = await api.get(`${P}/longjobs?kind=draft`);
        const what = seenJobs(r);
        if (what === 'active' || what === 'changed') await loadThread();
      } });
  }

  pick.ready.then(() => { if (!dead) renderThread(); });          // the cards name the agent by its label once the list of agents is known
  const sel0 = ctx.store?.sel?.shot;
  selected = sel0 ? [sel0] : [];
  paintScope(true);
  renderThread();
  loadThread();
  return unmount;
}
