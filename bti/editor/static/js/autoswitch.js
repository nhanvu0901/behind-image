// The switch "Cho agent tự chạy dự án này": a button in the top bar (next to "Cài đặt") that shows whether an agent in a terminal may approve gates of the open
// project, and a small dialog with the switch, the four gates as checkboxes and the line "Việc tốn tiền luôn cần bạn.". Every change is saved at once with
// PUT /api/projects/{pid}/auto (the revision the page holds; one retry when it is stale). The rule is the server's (bti/auto.py); the decisions of this file are in
// autologic.js (pure, tested), the words in labels.js (AUTO_LABELS), errors go through errmsg.js.
import { api } from './api.js';
import { MOCK } from './config.js';
import { h, kids, modal, toast } from './util.js';
import { stageErrorText } from './errmsg.js';
import { AUTO_LABELS as L, AUTORUN_LABELS as R } from './labels.js';
import { autoView, switchBody, gateBody, buttonTitle, isStale, runBody, runButtonView, latestRun, progressText, runMoved, stopPath, endView, isRunning } from './autologic.js';

const P = (pid) => `/api/projects/${encodeURIComponent(pid)}/auto`;

/** PUT a change; `make(rev)` builds the body; a stale answer reads the document again and asks once more. Returns the new document. */
export async function putAuto(pid, make, doc) {
  let cur = doc || await api.get(P(pid));
  try { return await api.put(P(pid), make(cur.rev)); }
  catch (e) {
    if (!isStale(e)) throw e;
    cur = await api.get(P(pid));
    return await api.put(P(pid), make(cur.rev));
  }
}

let current = null;           // { pid, doc }: what the button shows
let button = null;
let seq = 0;

function paintButton() {
  if (!button) return;
  const v = autoView(current?.doc);
  button.textContent = v.button;
  button.title = buttonTitle(current?.doc);
  button.classList.toggle('on', v.enabled);
  paintRun();                                                // c6auto: the "Chạy tự động" button follows the switch
}

/** Wire the button of the top bar once. `getPid()` says which project is open (null on the home page and in the library). */
export function mountAutoButton(el, getPid) {
  button = el;
  if (MOCK) { el.hidden = true; return { sync() {} }; }       // the in-browser fixtures have no such route
  el.onclick = () => { const pid = getPid(); if (pid) openAutoDialog(pid); };
  mountRun(el);                                                // c6auto
  return { sync };
}

/** Show or hide the button for the open project and read its document (the answer of an old project is ignored when another one is open by then). */
export async function sync(pid) {
  if (!button || MOCK) return;
  const mine = ++seq;
  if (!pid) { button.hidden = true; current = null; stopPolling(); return; }          // c6auto: stopPolling
  button.hidden = false;
  if (current?.pid !== pid) { current = null; paintButton(); }
  try {
    const doc = await api.get(P(pid));
    if (mine !== seq) return;
    current = { pid, doc };
    paintButton();
  } catch { if (mine === seq) paintButton(); }               // the button still says "tắt": the server's rule is the same when the page cannot read it
  if (mine === seq) loadRun(pid);                            // c6auto
}

export function openAutoDialog(pid) {
  const status = h('div', { class: 'hint auto-status', role: 'status', text: L.loading });
  const box = h('div', { class: 'auto-body' }, status);
  const dlg = modal({ title: L.title, body: h('div', { class: 'body auto-dialog', style: { width: 'min(460px, 94vw)' } }, box) });
  let doc = null, busy = false;
  load();
  return dlg;

  async function load() {
    try { doc = await api.get(P(pid)); }
    catch (e) { status.textContent = L.loadFail + stageErrorText('auto', e).text; return; }
    paint();
  }

  async function change(make) {
    if (busy) return;
    busy = true; paint();
    try { doc = await putAuto(pid, make, doc); toast(L.saved, 'ok', 1800); }
    catch (e) { toast(L.saveFail + stageErrorText('auto', e).text, 'err', 8000); try { doc = await api.get(P(pid)); } catch { /* the dialog keeps what it had */ } }
    finally { busy = false; paint(); if (doc) { current = { pid, doc }; paintButton(); paintRun(); } }
  }

  function paint() {
    const v = autoView(doc);
    const sw = h('input', { type: 'checkbox', id: 'auto-switch', class: 'auto-switch', checked: v.enabled, disabled: busy || null,
      onchange: () => change((rev) => switchBody(rev, sw.checked)) });
    const rows = v.gates.map((g) => {
      const cb = h('input', { type: 'checkbox', id: 'auto-gate-' + g.id, class: 'auto-gate', 'data-gate': g.id, checked: g.checked, disabled: v.gatesDisabled || busy || null,
        onchange: () => change((rev) => gateBody(rev, g.id, cb.checked)) });
      return h('label', { class: 'auto-row', for: cb.id }, cb, h('span', { text: g.label }));
    });
    box.replaceChildren(
      h('label', { class: 'auto-row auto-main', for: sw.id }, sw, h('b', { text: L.switchLabel })),
      h('div', { class: 'hint auto-summary', role: 'status', text: v.summary }),
      h('div', { class: 'auto-gates' }, h('div', { class: 'lb', text: L.gatesTitle }), ...rows),
      h('div', { class: 'hint', text: L.hint }),
      h('div', { class: 'auto-money', text: L.money }));
  }
}

// ------------------------------------------------------------------------------------------------------------------------ c6auto: "Chạy tự động"
// A button "Chạy tự động" beside the switch (it works only while the switch is on), and a bar under the top bar: "Đang chạy tự động: Giọng đọc (3/6)" with "Dừng"
// while a run goes on; when it ended, one sentence that says where it stopped and why, with a link to that step. What it shows is decided in autologic.js, the
// words are in labels.js (AUTORUN_LABELS) and errmsg.js; the runs are GET /api/projects/{pid}/auto/runs (the run is a long job of kind auto).
const RUNS = (pid) => `/api/projects/${encodeURIComponent(pid)}/auto/runs?limit=1`;
const POLL_MS = 3000;
let runBtn = null, bar = null, runItem = null, runBusy = false, timer = null, moved = '';

function seenMap() { try { return JSON.parse(localStorage.getItem('bti.autorun.seen') || '{}') || {}; } catch { return {}; } }
function markSeen(pid, id) { try { const m = seenMap(); m[pid] = id; localStorage.setItem('bti.autorun.seen', JSON.stringify(m)); } catch { /* the bar just shows again next time */ } }

function mountRun(after) {
  runBtn = h('button', { id: 'btn-auto-run', class: 'small', type: 'button', onclick: startRun });
  runBtn.hidden = true;
  after.after(runBtn);
  bar = h('div', { id: 'auto-run-bar', role: 'status' });
  bar.hidden = true;
  const anchor = document.getElementById('step-banner') || document.getElementById('stepper') || after.closest('header');
  if (anchor) anchor.after(bar);
}

function stopPolling() { clearTimeout(timer); timer = null; runItem = null; moved = ''; paintRun(); }

async function loadRun(pid) {
  clearTimeout(timer);
  let item = null;
  try { item = latestRun(await api.get(RUNS(pid))); } catch { item = runItem && runItem.pid === pid ? runItem : null; }
  if (current?.pid !== pid) return;                                         // another project was opened meanwhile
  runItem = item ? { ...item, pid } : null;
  const m = runMoved(item);
  if (moved && m !== moved) refreshShell();                                  // the run moved on: the stepper and the view read the project again
  moved = m;
  paintRun();
  if (isRunning(item)) timer = setTimeout(() => loadRun(pid), POLL_MS);
}

async function refreshShell() {
  try { const app = await import('./app.js'); await app.shell?.refreshPipeline?.(); } catch { /* the page shows the new state the next time it reads the project */ }
}

function paintRun() {
  if (!runBtn || !bar) return;
  runBtn.hidden = !current;
  const v = runButtonView(current?.doc, runItem, runBusy);
  runBtn.textContent = runBusy && !isRunning(runItem) ? R.starting : v.label;
  runBtn.disabled = !v.enabled;
  runBtn.title = v.title;
  const prog = progressText(runItem);
  const end = prog ? null : endView(runItem);
  const hide = !current || (!prog && (!end || seenMap()[current.pid] === runItem?.id));
  bar.hidden = hide;
  bar.className = hide ? '' : 'auto-run-bar ' + (prog ? 'run' : end.tone);
  if (hide) { bar.replaceChildren(); return; }
  if (prog) {
    bar.replaceChildren(h('span', { class: 'msg', text: runBusy ? R.stopping : prog }), h('button', { class: 'small', type: 'button', disabled: runBusy || null, text: R.stop, onclick: stopRun }));
    return;
  }
  const pid = current.pid, id = runItem.id;
  bar.replaceChildren(...kids(h('b', { class: 'hd', text: end.heading + ': ' }), h('span', { class: 'msg', text: end.sentence }),
    end.link && h('a', { class: 'go', href: end.link.href, text: end.link.text }),
    h('button', { class: 'small', type: 'button', text: R.close, onclick: () => { markSeen(pid, id); paintRun(); } })));
}

async function startRun() {
  const pid = current?.pid;
  if (!pid || runBusy) return;
  runBusy = true; paintRun();
  try { await api.post(`/api/projects/${encodeURIComponent(pid)}/auto/run`, runBody()); }
  catch (e) { toast(R.startFail + stageErrorText('autorun', e).text, 'err', 8000); }
  finally { runBusy = false; }
  await loadRun(pid);
}

async function stopRun() {
  const pid = current?.pid, path = stopPath(runItem);
  if (!pid || !path || runBusy) return;
  runBusy = true; paintRun();
  try { await api.post(path, {}); }
  catch (e) { toast(R.stopFail + stageErrorText('autorun', e).text, 'err', 8000); }
  finally { runBusy = false; }
  await loadRun(pid);
}
