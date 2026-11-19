// "Sửa video bằng lời" (step 5) and "Sửa chọn hình bằng lời" (step 4): type what to change, see what changed, undo it.
// One box beside the preview (or the pictures): the text field, the scope in words, the send button, then the thread of turns.
// A turn is one call of the agent that answers with typed operations; the server checks them inside the owner's selection, applies them as ONE
// batch of the change log and the card shows the batch's own sentences, a before and after picture of every changed shot (step 5), "Xem thử" and
// "Hoàn tác" (the undo of that batch). A request the fast way cannot do says why: step 5 offers "Làm kỹ hơn" (the agent working in a folder, minutes),
// step 4 offers the search by hand.
//   const unmount = mountPromptEdit(container, { pid, scope, takeIn, onPreview, onJobEnd });                          // step 5
//   const unmount = mountPromptEdit(container, { pid, scope, kind: 'picks', takeIn, onJobEnd, picks });               // step 4
//   takeIn(turn): the page takes the new saved document in (reload, or the merge with unsaved edits)
//   onPreview({t0, t1}): the existing preview clip of a range (step 5)
//   picks: { chapters(), currentBeat(), onSelect(cb) -> off, rev(), isDirty(), save(), openSearch() }               (step 4: what the pictures page knows)
// The agent that does the work is chosen with the agent select beside the send button (agentpick.js, step "storyboard" or "picks"); the box sends no
// model of its own. When that agent's quota is used up the card names it and the time and offers ONE button: switch to the other agent and send the
// same request again (quotaNode).
// The decisions are in editlogic.js (pure, tested); the words are in labels.js (EDIT_LABELS, BOX_LABELS); errors go through errmsg.js.
import { api } from './api.js';
import { h, kids, toast, confirmDialog, detailFold } from './util.js';
import { stageErrorText, errorText, boxErrorText } from './errmsg.js';
import { EDIT_LABELS as L, AGENT_LABELS as AL, BOX_LABELS as BL } from './labels.js';
import { ctx, bus } from './ctx.js';
import { wordIndexAt } from './logic.js';
import { watchIdle, jobWatcher } from './idlewatch.js';
import { mountAgentPick, quotaNode, loadAgents } from './agentpick.js';
import { mountChangesList } from './changeslist.js';
import { STEP_STORYBOARD, STEP_PICKS, labelForModel } from './agentlogic.js';
import { ACTIVE, pickScope, pickBeatScope, retryScope, retryBeatScope, addToSelection, turnView, progressView, previewRange, newlyChanged, shotNumber, beatNumbers } from './editlogic.js';

export function mountPromptEdit(container, { pid, scope = null, kind = 'storyboard', takeIn = null, onPreview = null, onJobEnd = null, picks = null } = {}) {
  const isPicks = kind === 'picks';
  const LP = BL.pictures;
  // the words of this box: the pictures' box says "dòng" where the storyboard's says "cảnh"
  const W = isPicks ? { ...L, title: LP.title, placeholder: LP.placeholder, scopeLead: LP.scopeLead, noShotChosen: LP.noLineChosen, multi: LP.multi, multiHint: LP.multiHint,
    multiOn: LP.multiOn, dropShot: LP.dropLine, thread: LP.thread, threadEmpty: LP.threadEmpty, applied: LP.applied, undoHint: LP.undoHint, noStoryboard: LP.noNarration,
    stale: LP.stale, tookIn: LP.tookIn, tookInFail: LP.tookInFail } : L;
  let dead = false, timer = null, jobId = null, job = null, thread = [], first = true, busy = false;
  let choice = 'auto', multi = false, selected = [], lastSig = '';
  const seenTurns = new Map(), shownStatus = new Map();
  let shownFirst = true;
  const seenJobs = jobWatcher();
  const P = `/api/projects/${encodeURIComponent(pid)}`;
  const PATH = isPicks
    ? { start: `${P}/picks/edit`, thread: `${P}/picks/edit/thread`, turn: (id) => `${P}/picks/edit/${encodeURIComponent(id)}` }
    : { start: `${P}/draft/edit`, thread: `${P}/draft/thread`, turn: (id) => `${P}/draft/edit/${encodeURIComponent(id)}` };
  const STEP = isPicks ? STEP_PICKS : STEP_STORYBOARD;

  const root = h('div', { class: 'prompt-edit' + (isPicks ? ' prompt-edit-picks' : ''), 'data-box': kind });
  container.replaceChildren(root);

  // ---------------------------------------------------------------- the form
  const ta = h('textarea', {
    class: 'prompt-instruction', rows: 2, placeholder: W.placeholder, 'aria-label': W.title,
    onkeydown: (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit(); } },
  });
  const btnSend = h('button', { class: 'primary prompt-btn-submit', onclick: () => submit(), text: L.send, title: L.sendHint });
  const pills = {};
  const PILLS = isPicks ? [['beats', LP.scopeBeats], ['chapter', LP.scopeChapter], ['all', LP.scopeAll]] : [['shots', L.scopeShots], ['chapter', L.scopeChapter], ['all', L.scopeAll]];
  const pillRow = h('div', { class: 'prompt-pills', role: 'group', 'aria-label': W.scopeLead },
    ...PILLS.map(([k, text]) => (pills[k] = h('button', { type: 'button', class: 'pill', text, onclick: () => { choice = k; paintScope(true); } }))));
  const agentHost = h('div', { class: 'prompt-agent' });
  const pick = mountAgentPick(agentHost, { pid, step: STEP, scope });
  const multiBox = h('input', { type: 'checkbox', class: 'prompt-multi', onchange: (e) => setMulti(e.target.checked) });
  const multiLabel = h('label', { class: 'chk prompt-multi-label', title: W.multiHint }, multiBox, h('span', { text: W.multi }));
  const wordsLine = h('div', { class: 'prompt-scope-words' });
  const chipsBox = h('div', { class: 'prompt-shots-chips' });
  const form = h('div', { class: 'prompt-form' },
    ta,
    pillRow, wordsLine, chipsBox,
    agentHost,                                                                   // the agent select has a row of its own: the box is narrow
    h('div', { class: 'prompt-send-row' }, multiLabel,
      h('span', { class: 'grow' }), btnSend));
  const threadHead = h('div', { class: 'prompt-thread-header' });
  const threadList = h('div', { class: 'prompt-thread-list', tabindex: 0, 'aria-label': W.thread });
  const changesHost = h('div', { class: 'prompt-changes-host' });
  root.append(form, threadHead, threadList, changesHost);

  // ---------------------------------------------------------------- the scope
  const draftShots = () => ctx.store?.draft?.shots || [];
  const chapters = () => ctx.store?.timing?.chapters || [];
  const scopeNow = () => {
    if (isPicks) return pickBeatScope({ choice, selected, chapters: picks?.chapters?.() || [], beat: picks?.currentBeat?.() || null });
    const t = ctx.t || 0;
    return pickScope({ choice, selected, shots: draftShots(), chapters: chapters(), t, wIdx: chapters().some((c) => c.start == null) ? wordIndexAt(ctx.words(), t) : -1 });
  };
  const validIds = () => (isPicks ? [...beatNumbers(picks?.chapters?.() || []).keys()] : draftShots().map((s) => s.id));
  const numberOf = (id) => (isPicks ? beatNumbers(picks?.chapters?.() || []).get(id) : shotNumber(draftShots(), id));
  const selectedNow = () => (isPicks ? picks?.currentBeat?.() : ctx.store?.sel?.shot);
  function setMulti(on) {
    multi = on;
    if (on) choice = isPicks ? 'beats' : 'shots';
    else { const id = selectedNow(); selected = id ? [id] : []; choice = 'auto'; }
    paintScope(true);
  }
  function paintScope(force = false) {
    if (dead) return;
    const valid = new Set(validIds());
    selected = selected.filter((id) => valid.has(id));
    const sc = scopeNow();
    const sig = [sc.kind, sc.words, selected.join(','), multi, busy].join('|');
    if (!force && sig === lastSig) return;
    lastSig = sig;
    for (const [k, b] of Object.entries(pills)) { b.classList.toggle('on', sc.kind === k); b.disabled = busy; }
    multiBox.checked = multi; multiBox.disabled = busy;
    wordsLine.textContent = multi && (sc.kind === 'shots' || sc.kind === 'beats') && selected.length < 2 ? `${W.scopeLead} ${sc.words}. ${W.multiOn}` : `${W.scopeLead} ${sc.words}`;
    chipsBox.replaceChildren(...(multi || selected.length > 1 ? selected.map((id) => {
      const n = numberOf(id);
      return h('span', { class: 'prompt-shot-chip' }, h('span', { text: isPicks ? LP.lineAt(n ?? '') : `Cảnh ${n ?? ''}`.trim() }),
        h('button', { type: 'button', class: 'prompt-shot-chip-del', title: W.dropShot(n ?? ''), disabled: busy, text: '×',
          onclick: () => { selected = selected.filter((x) => x !== id); paintScope(true); } }));
    }) : []));
    btnSend.disabled = busy || !sc.ok;
  }
  function selectionChanged() {
    const id = selectedNow();
    selected = multi ? addToSelection(selected, id, { multi, playing: !isPicks && ctx.playing }) : (id ? [id] : []);
    paintScope();
  }
  const offs = [];
  if (isPicks) offs.push(picks?.onSelect?.(selectionChanged));
  else {
    offs.push(ctx.store.on((kind2) => {
      if (kind2 === 'select') selectionChanged();
      else if (kind2 === 'draft' || kind2 === 'load') paintScope();
    }));
    offs.push(bus.on('time', () => paintScope()));
    offs.push(bus.on('tick', () => { if (choice === 'chapter' || choice === 'auto') paintScope(); }));
  }
  scope?.add?.(() => { for (const off of offs) off?.(); });

  // ---------------------------------------------------------------- the thread
  async function loadThread() {
    let r = null;
    try { r = await api.get(PATH.thread); } catch { /* the old list stays; the next look tries again */ }
    if (dead) return;
    if (r) {
      thread = r.turns || [];
      const fresh = newlyChanged(thread, seenTurns, first);
      first = false;
      if (r.active_job_id && !jobId) { jobId = r.active_job_id; seenJobs.know(jobId); job = null; busy = true; setTimeout(tick, 0); }
      if (fresh.length && takeIn) { try { await takeIn(fresh[fresh.length - 1]); } catch { /* takeIn reports its own errors */ } }
    }
    if (!dead) { renderThread(); paintScope(true); changes?.refresh(); }
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

  /** Send the request. `retry`: an older turn to send again (same instruction, same scope); `deep`: the owner pressed "Làm kỹ hơn" on a turn that
   *  asked for it: the same request goes to the slower way. */
  async function submit(retry = null, { deep = false } = {}) {
    if (busy || dead) return;
    const text = (retry ? retry.instruction : ta.value).trim();
    if (!text) { toast(L.emptyInstruction, 'warn', 4000); ta.focus(); return; }
    if (text.length > 2000) { toast(L.tooLong, 'warn', 4000); return; }
    if (isPicks ? !validIds().length : !draftShots().length) { toast(W.noStoryboard, 'warn', 4000); return; }
    let payload;
    if (retry) {
      payload = isPicks ? retryBeatScope(retry, validIds()) : retryScope(retry, draftShots());
      if (!payload) { toast(W.noShotChosen, 'warn', 4000); return; }
    } else { const sc = scopeNow(); if (!sc.ok) { toast(sc.why, 'warn', 4000); return; } payload = sc.payload; }
    setBusy(true);
    try {
      let body;
      if (isPicks) {
        if (picks?.isDirty?.()) await picks.save?.();                      // the server reads the saved picks: what the owner just did must be saved first
        body = { instruction: text, scope: payload, base_rev: picks?.rev?.() };
      } else body = { instruction: text, scope: payload, mode: deep ? 'deep' : 'auto', base_rev: ctx.store?.rev };
      const res = await api.post(PATH.start, body);
      jobId = res.job_id; seenJobs.know(jobId); job = null;
      if (!retry) ta.value = '';
      await loadThread();
      tick();
    } catch (e) { toast(L.sendFail + boxErrorText(e).text, 'err', 8000); setBusy(false); }
  }

  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); tick(); }
    catch (e) { toast(L.cancelFail + boxErrorText(e).text, 'err', 8000); }
  }

  /** One call on a turn (undo, resolve); then the page takes the new document in and the thread is read again. A turn made through typed operations
   *  undoes its batch: if something it changed was changed since, the server says so and nothing is undone (no "force"). */
  async function act(turn, path, body, okText) {
    try {
      const res = await api.post(`${PATH.turn(turn.id)}/${path}`, body);
      if (okText) toast(okText, 'ok', 3000);
      return res || {};
    } catch (e) {
      if (path === 'undo' && !turn.batch && e.status === 409 && e.body?.code === 'undo_conflict' && !body.force) return await undoConflict(turn, e.body.conflicts || []);
      toast(L.actionFail + (turn.batch ? errorText(e) : stageErrorText('draft', e).text), 'err', 8000);
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
    onJobEnd?.();
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
  /** "Làm kỹ hơn": the same request, the same scope, to the agent that works in a folder (it takes minutes: the card said so). */
  function slower(turn) { submit(turn, { deep: true }); }

  async function clearHistory() {
    if (!(await confirmDialog(L.clearAsk, { title: L.clear, ok: L.clearOk, danger: true }))) return;
    try { await api.del(PATH.thread); thread = []; seenTurns.clear(); renderThread(); toast(L.cleared, 'ok', 2500); }
    catch (e) { toast(L.actionFail + boxErrorText(e).text, 'err', 8000); }
  }

  // ---------------------------------------------------------------- the cards
  const frameUrl = (turn, shotId, when) => api.url(`${PATH.turn(turn.id)}/frames/${encodeURIComponent(shotId)}/${when}.jpg`);
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
      c.lines?.length > 1 ? h('ul', { class: 'prompt-change-lines' }, c.lines.map((t) => h('li', { text: t }))) : (c.lines?.[0] || c.what ? h('div', { class: 'prompt-change-what', text: c.lines?.[0] || c.what }) : null),
      h('div', { class: 'prompt-frames' }, frame(turn, c, 'before', c.hasBefore), frame(turn, c, 'after', c.hasAfter)));
  }
  /** The buttons of a card: the only things the owner has to do on it. They sit right under the header line, above everything else. */
  function actionRow(turn, v) {
    const a = v.actions, btns = [];
    if (a.cancel) btns.push(h('button', { class: 'small prompt-btn-cancel', onclick: cancel, text: L.cancel }));
    if (a.choices) btns.push(
      h('button', { class: 'small primary prompt-btn-overwrite', text: L.choiceOverwrite, title: L.choiceOverwriteHelp, onclick: () => resolve(turn, 'overwrite') }),
      h('button', { class: 'small prompt-btn-discard', text: L.choiceDiscard, title: L.choiceDiscardHelp, onclick: () => resolve(turn, 'discard') }));
    if (a.escalate === 'slow') btns.push(h('button', { class: 'small primary prompt-btn-slower', text: BL.slow.button, title: BL.slow.hint, disabled: busy, onclick: () => slower(turn) }));
    if (a.escalate === 'manual') btns.push(h('button', { class: 'small primary prompt-btn-manual', text: LP.escalateButton, onclick: () => picks?.openSearch?.() }));
    if (a.preview) btns.push(h('button', { class: 'small prompt-btn-preview', text: L.preview, title: L.previewHint, onclick: () => preview(turn) }));
    if (a.undo) btns.push(h('button', { class: 'small prompt-btn-undo', text: L.undo, title: a.undo === 'gone' ? L.undoNone : W.undoHint, disabled: a.undo === 'gone', onclick: () => undo(turn) }));
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
      if (turn.path === 'deep') kidsOf.push(h('div', { class: 'prompt-run-limits hint', text: [BL.slow.takes, v.limits].filter(Boolean).join(' ') }));      // the slow way says so, and its limits, when it starts
    } else if (v.actions.settings) {
      // the agent's quota is used up: the sentence names the agent and the time; ONE button switches to the other agent and sends the same request again
      kidsOf.push(h('div', { class: 'prompt-turn-quota ' + v.tone }, quotaNode({ pid, step: STEP, rec: quotaRec(turn), rerun: () => submit(turn),
        getAgents: async () => pick.agents() || loadAgents() })));
    } else {
      if (v.headline) kidsOf.push(h('div', { class: 'prompt-turn-summary ' + v.tone, text: v.headline }));
      if (v.extra) kidsOf.push(h('div', { class: 'prompt-turn-extra hint', text: v.extra }));
      if (v.actions.choices) kidsOf.push(h('div', { class: 'hint prompt-choice-help', text: `${L.choiceOverwrite}: ${L.choiceOverwriteHelp} ${L.choiceDiscard}: ${L.choiceDiscardHelp}` }));
      if (v.showChanges) kidsOf.push(h('div', { class: 'prompt-changes' }, ...v.changes.map((c) => changeRow(turn, c))));
      if (v.showSentences) kidsOf.push(h('ul', { class: 'prompt-sentences' }, v.sentences.map((s) => h('li', { text: s.text }))));
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
    threadHead.replaceChildren(...kids(h('h5', { text: `${W.thread} (${thread.length})` }), h('span', { class: 'grow' }),
      thread.length ? h('button', { class: 'small text-btn prompt-btn-clear', text: L.clear, onclick: clearHistory }) : null));
    const keepScroll = threadList.scrollTop;
    threadList.replaceChildren(...(thread.length
      ? thread.slice().reverse().map(card)                                   // the newest on top
      : [h('div', { class: 'empty muted', text: W.threadEmpty })]));
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

  // "Lịch sử thay đổi": the change log of this step's document, with the undo of the batch the state answer says can be undone
  const changes = mountChangesList(changesHost, { pid, doc: isPicks ? 'picks' : 'storyboard', scope, getAgents: async () => pick.agents() || loadAgents(),
    onUndone: async () => { if (takeIn) { try { await takeIn({ status: 'undone' }); } catch { /* takeIn reports its own errors */ } } await loadThread(); } });

  function unmount() { dead = true; clearTimeout(timer); for (const off of offs) off?.(); changes.unmount(); pick.unmount(); root.remove(); }
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
  const sel0 = selectedNow();
  selected = sel0 ? [sel0] : [];
  paintScope(true);
  renderThread();
  loadThread();
  return unmount;
}
