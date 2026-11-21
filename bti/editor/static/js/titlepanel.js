// The video's title on the script page ("Kịch bản") and on the storyboard page ("Dựng hình"): one line under the toolbar with the title in use, who chose it and two buttons, and a
// dialog with the candidates the agent proposed (click one to choose it), a field to type your own title and a box to ask the agent again with a note. Mounted by views/script.js into
// #title-host and by views/storyboard.js into the host of its title row (one module, no copy):
//   const box = mountTitlePanel(host, { pid, scope, narrationApproved: () => bool, takeIn: async () => {} });
//   `takeIn` (the storyboard page): called after a title was set or written and the answer says the saved storyboard changed (it took the title), so that the page loads the new one.
//   While the storyboard is off the voice the answer says so (`storyboard.off_voice`): the title is stored, the strip says the storyboard takes it after "Khớp lại với giọng đọc".
//   box.refresh()   read the title again (the page calls it when the narration was approved)      box.repaint()   draw again from what is known (the page's chrome changed)
// The routes are GET/PUT /api/projects/{pid}/title and POST .../title/generate (a long job of kind `title`, followed at GET /api/longjobs/{id}); the decisions are in
// titlelogic.js (pure, tested); the words are in labels.js (TITLE_LABELS) and errmsg.js (STAGE_CODES.title). Nothing the owner reads comes from the server as it is.
import { api } from './api.js';
import { h, kids, toast, errorToast, modal, confirmDialog } from './util.js';
import { TITLE_LABELS as L } from './labels.js';
import { stageJobErrorText } from './errmsg.js';
import * as TL from './titlelogic.js';

const STYLE_ID = 'title-panel-style';
const CSS = `
.v-scr .title-host { flex: 1 0 100%; }
.title-strip { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 3px 0 1px; min-width: 0; }
.title-strip .name { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .07em; }
.title-strip .text { font-weight: 600; }
.title-strip .text.none { font-weight: 400; color: var(--muted); }
.title-strip .meta { color: var(--muted); font-size: 12px; }
.title-strip progress { width: 120px; }
.title-dlg .body { max-width: 720px; }
.title-dlg h4 { margin: 14px 0 6px; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.title-dlg .current { font-size: 16px; font-weight: 600; margin: 2px 0; }
.title-dlg .cands { display: flex; flex-direction: column; gap: 6px; }
.title-dlg .cand { display: block; width: 100%; text-align: left; padding: 7px 10px; border-radius: var(--radius); border: 1px solid var(--border); background: var(--panel); cursor: pointer; }
.title-dlg .cand:hover { border-color: var(--accent); }
.title-dlg .cand.inuse { border-color: var(--accent); background: #1a2a42; }
.title-dlg .cand .ct { font-weight: 600; }
.title-dlg .cand .cm { color: var(--muted); font-size: 11px; margin-top: 2px; }
.title-dlg .cand .cw { font-size: 12px; margin-top: 3px; }
.title-dlg .own { display: flex; gap: 8px; align-items: center; }
.title-dlg .own input { flex: 1; min-width: 0; }
.title-dlg textarea { width: 100%; min-height: 54px; resize: vertical; }
.title-dlg .counter { color: var(--muted); font-size: 12px; min-width: 44px; text-align: right; }
.title-dlg .counter.bad { color: var(--danger); }
`;

function ensureStyle() {
  if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
  const st = document.createElement('style');
  st.id = STYLE_ID;
  st.textContent = CSS;
  document.head.append(st);
}

export function mountTitlePanel(host, { pid, scope, narrationApproved = () => true, takeIn = null }) {
  ensureStyle();
  const P = `/api/projects/${encodeURIComponent(pid)}`;
  let dead = false, data = null, job = null, jobId = null, busy = false, polling = false, dlg = null, draft = '', note = '';
  const root = h('div', { class: 'title-strip', 'data-title': '' });
  host.replaceChildren(root);
  const ctx = () => ({ narrationApproved: narrationApproved(), busy, job });

  // ---------------------------------------------------------------- the strip
  function paint() {
    if (dead) return;
    const v = TL.stripView(data, ctx());
    root.dataset.state = v.running ? 'running' : v.state;
    root.replaceChildren(...kids(
      h('span', { class: 'name', text: L.name }),
      h('span', { class: 'text' + (v.has ? '' : ' none'), id: 'title-text', text: v.text }),
      v.by ? h('span', { class: 'meta', text: L.chosenBy(v.by, v.when) }) : null,
      v.note && !v.running ? h('span', { class: 'hint' + (v.stale ? ' warn' : ''), id: 'title-note', text: v.note }) : null,
      v.running ? h('span', { class: 'title-prog', role: 'status' }, h('progress', { max: 1, value: job?.progress ?? 0 }), h('span', { id: 'title-line', text: job ? TL.progressText(job) : L.working })) : null,
      v.running && jobId ? h('button', { class: 'small', id: 'title-cancel', text: L.cancel, onclick: cancel }) : null,
      v.open.visible ? h('button', { class: 'small', id: 'title-open', text: L.openButton, title: L.openHint, onclick: openDialog }) : null,
      v.write.visible ? h('button', { class: 'small' + (v.has ? '' : ' primary'), id: 'title-write', text: v.write.label, title: v.write.title, disabled: v.write.disabled || busy, onclick: () => generate('') }) : null));
    if (dlg) paintDialog();
  }

  async function load() {
    try {
      data = await api.get(`${P}/title`);
      if (data?.running && TL.jobRunning(data.running) && !jobId) { jobId = data.running.id; job = data.running; }
    } catch (e) { errorToast(e, L.loadFail); }
    paint();
  }

  // ---------------------------------------------------------------- the actions
  /** The server applied the title to the saved storyboard: a page that holds the storyboard (the storyboard page) takes the new one in. */
  async function takeStoryboard(res) {
    if (!takeIn || !TL.storyboardChanged(res)) return;
    try { await takeIn(); } catch { /* takeIn reports its own errors */ }
  }
  async function pick(n) {
    if (busy) return;
    busy = true; paint();
    try {
      const res = await api.put(`${P}/title`, TL.pickBody(data, n));
      const [text, kind] = TL.savedToast(res);
      toast(text, kind, 6500);
      draft = '';
      await load();
      await takeStoryboard(res);
    } catch (e) { errorToast(e, L.saveFail); if (e?.status === 409) await load(); }
    busy = false; paint();
  }
  async function useOwn() {
    if (busy) return;
    const body = TL.typeBody(data, draft);
    if (!body) { paintDialog(); return; }
    busy = true; paint();
    try {
      const res = await api.put(`${P}/title`, body);
      const [text, kind] = TL.savedToast(res);
      toast(text, kind, 6500);
      draft = '';
      await load();
      await takeStoryboard(res);
    } catch (e) { errorToast(e, L.saveFail); if (e?.status === 409) await load(); }
    busy = false; paint();
  }
  async function generate(withNote) {
    if (busy || TL.jobRunning(job)) return;
    if (TL.replacesPersonsTitle(data) && !(await confirmDialog(L.confirmReplace.message, { title: L.confirmReplace.title, ok: L.confirmReplace.ok }))) return;
    busy = true; paint();
    try {
      const r = await api.post(`${P}/title/generate`, TL.generateBody(withNote));
      jobId = r.job_id; job = null; note = '';
      await poll();
    } catch (e) { errorToast(e, L.startFail, 9000); }
    busy = false; paint();
  }
  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); await poll(); }
    catch (e) { errorToast(e, L.cancelFail, 9000); }
  }
  async function poll() {
    if (dead || !jobId || polling) return;
    polling = true;
    let j;
    try { j = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`); } catch { polling = false; return; }
    polling = false;
    if (dead) return;
    job = j;
    if (TL.jobRunning(j)) { paint(); return; }
    jobId = null; job = null;
    if (j.state === 'done') { const [text, kind] = TL.doneToast(j); toast(text, kind, 7000); await takeStoryboard(j.result); }
    else if (j.state === 'cancelled') toast(L.cancelled, '', 4000);
    else toast(L.jobFail + stageJobErrorText('title', j).text, 'err', 9000);
    await load();
  }

  // ---------------------------------------------------------------- the dialog
  function openDialog() {
    if (dlg || !data) return;
    dlg = modal({ title: L.dialogTitle, cls: 'v-scr title-dlg', body: h('div', { class: 'body', 'data-title-dialog': '' }), backdrop: false, onClose: () => { dlg = null; } });
    paintDialog();
  }
  function paintDialog() {
    const body = dlg?.el?.querySelector('[data-title-dialog]');
    if (!body || !data) return;
    const v = TL.stripView(data, ctx());
    const limits = TL.limitsOf(data);
    const info = TL.lengthInfo(draft, limits);
    const locked = busy || v.running;
    const rows = TL.candidateRows(data);
    const hist = TL.historyRows(data);
    const input = h('input', { type: 'text', id: 'title-own', value: draft, placeholder: L.ownPlaceholder, maxlength: 400, disabled: locked,
      oninput: (e) => { draft = e.target.value; const i = TL.lengthInfo(draft, limits); counter.textContent = L.counter(i.chars, limits.max); counter.className = 'counter' + (i.problem === 'long' ? ' bad' : ''); useBtn.disabled = !!i.problem || locked; hint.textContent = i.problem === 'long' || i.problem === 'newline' ? i.note : i.problem === 'empty' ? '' : i.note; },
      onkeydown: (e) => { if (e.key === 'Enter') { e.preventDefault(); useOwn(); } } });
    const counter = h('span', { class: 'counter' + (info.problem === 'long' ? ' bad' : ''), id: 'title-counter', text: L.counter(info.chars, limits.max) });
    const useBtn = h('button', { class: 'primary', id: 'title-use-own', text: L.useOwn, disabled: !!info.problem || locked, onclick: useOwn });
    const hint = h('div', { class: 'hint', id: 'title-own-note', text: info.problem === 'empty' ? '' : info.note });
    const noteBox = h('textarea', { id: 'title-note-box', placeholder: L.notePlaceholder, maxlength: TL.NOTE_MAX, value: note, disabled: locked, oninput: (e) => { note = e.target.value; } });
    body.replaceChildren(...kids(
      h('p', { class: 'hint', text: L.intro }),
      h('h4', { text: L.current }),
      v.has ? h('div', null, h('div', { class: 'current', id: 'title-current', text: v.text }), h('div', { class: 'meta hint', text: L.chosenBy(v.by, v.when) }), v.stale ? h('div', { class: 'hint warn', text: L.stale }) : null)
            : h('div', { class: 'hint', text: v.note }),
      h('h4', { text: L.candidates }),
      rows.length ? h('div', { class: 'cands' }, h('div', { class: 'hint', text: L.candidateHint }), ...rows.map((r) => h('button', { type: 'button', class: 'cand' + (r.inUse ? ' inuse' : ''), 'data-n': String(r.n), disabled: locked || r.inUse, onclick: () => pick(r.n) },
        h('div', { class: 'ct', text: r.text + (r.inUse ? ` (${L.inUse})` : '') }),
        h('div', { class: 'cm', text: `${L.chars(r.chars)} · ${r.formWord} · ${r.scoresText}` }),
        r.why ? h('div', { class: 'cw', text: r.why }) : null,
        r.linesText ? h('div', { class: 'cm', text: r.linesText }) : null)))
        : h('div', { class: 'hint', text: L.noCandidates }),
      h('h4', { text: L.own }),
      h('div', { class: 'own' }, input, counter, useBtn),
      hint,
      h('div', { class: 'hint', text: L.ownHint(limits.max) }),
      h('h4', { text: L.again }),
      h('label', { class: 'hint', for: 'title-note-box', text: L.noteLabel }),
      noteBox,
      h('div', { class: 'hint', text: L.noteHint(TL.NOTE_MAX) }),
      h('div', { class: 'row', style: { marginTop: '6px' } },
        h('button', { id: 'title-write-dialog', text: v.has ? L.writeAgain : L.write, disabled: locked || v.write.disabled, title: v.write.title, onclick: () => generate(note) })),
      hist.length ? h('div', null, h('h4', { text: L.history }), h('ul', null, ...hist.map((x) => h('li', { text: `${x.text} (${L.chosenBy(x.who, x.when)})` })))) : null));
  }

  scope.interval(() => { if (jobId) poll(); }, 1500);
  scope.interval(() => { if (!jobId && !busy && !dlg && !(typeof document !== 'undefined' && document.hidden)) load(); }, 8000);       // a title written meanwhile (by the automatic run, in another tab) shows up
  scope.add?.(() => { dead = true; dlg?.close?.(); });
  load();
  paint();
  return {
    refresh: load,
    repaint: paint,
    unmount() { dead = true; dlg?.close?.(); root.remove(); },
  };
}
