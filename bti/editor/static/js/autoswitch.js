// The switch "Cho agent tự chạy dự án này": a button in the top bar (next to "Cài đặt") that shows whether an agent in a terminal may approve gates of the open
// project, and a small dialog with the switch, the four gates as checkboxes and the line "Việc tốn tiền luôn cần bạn.". Every change is saved at once with
// PUT /api/projects/{pid}/auto (the revision the page holds; one retry when it is stale). The rule is the server's (bti/auto.py); the decisions of this file are in
// autologic.js (pure, tested), the words in labels.js (AUTO_LABELS), errors go through errmsg.js.
import { api } from './api.js';
import { MOCK } from './config.js';
import { h, modal, toast } from './util.js';
import { stageErrorText } from './errmsg.js';
import { AUTO_LABELS as L } from './labels.js';
import { autoView, switchBody, gateBody, buttonTitle, isStale } from './autologic.js';

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
}

/** Wire the button of the top bar once. `getPid()` says which project is open (null on the home page and in the library). */
export function mountAutoButton(el, getPid) {
  button = el;
  if (MOCK) { el.hidden = true; return { sync() {} }; }       // the in-browser fixtures have no such route
  el.onclick = () => { const pid = getPid(); if (pid) openAutoDialog(pid); };
  return { sync };
}

/** Show or hide the button for the open project and read its document (the answer of an old project is ignored when another one is open by then). */
export async function sync(pid) {
  if (!button || MOCK) return;
  const mine = ++seq;
  if (!pid) { button.hidden = true; current = null; return; }
  button.hidden = false;
  if (current?.pid !== pid) { current = null; paintButton(); }
  try {
    const doc = await api.get(P(pid));
    if (mine !== seq) return;
    current = { pid, doc };
    paintButton();
  } catch { if (mine === seq) paintButton(); }               // the button still says "tắt": the server's rule is the same when the page cannot read it
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
    finally { busy = false; paint(); if (doc) { current = { pid, doc }; paintButton(); } }
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
