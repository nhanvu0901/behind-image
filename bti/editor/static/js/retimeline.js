// One plain line with a button on the storyboard page (step 5): "Khớp lại với giọng đọc". It is shown only while the state answer of the project
// (GET /api/projects/{pid}/state) lists the action `storyboard.retime`: the voice was made again and the cards, the channel-name beat or the end of the
// video no longer sit where the voice puts them. The button calls the action's own route with the body the state gave; the server does the work (one batch
// of the change log, undoable) and takeIn() loads the new storyboard. The words are in labels.js (RETIME_LABELS); errors go through errmsg.js.
import { api } from './api.js';
import { MOCK } from './config.js';
import { h, toast, errorToast } from './util.js';
import { ctx } from './ctx.js';
import { RETIME_LABELS as L } from './labels.js';

/** The action to offer, or null: listed, ready. Pure. */
export function retimeAction(state) {
  const a = (state?.next_actions || []).find((x) => x?.id === 'storyboard.retime');
  return a && a.ready ? a : null;
}

export function mountRetimeLine(container, { pid, scope = null, takeIn = null } = {}) {
  let dead = false, busy = false, act = null;
  const P = `/api/projects/${encodeURIComponent(pid)}`;
  const btn = h('button', { type: 'button', class: 'small', text: L.button, title: L.hint, onclick: () => go() });
  const line = h('span', { class: 'hint', text: L.line });
  const root = h('span', { class: 'retime-line', 'data-retime': '', hidden: true }, line, btn);
  container.replaceChildren(root);

  function paint() {
    if (dead) return;
    root.hidden = !act;
    btn.disabled = busy;
    btn.textContent = busy ? L.busy : L.button;
  }

  async function refresh() {
    try { act = retimeAction(await api.get(`${P}/state`)); }
    catch (e) { act = null; if (!MOCK && !dead) errorToast(e, L.loadFail); }
    paint();
  }

  async function go() {
    if (!act || busy) return;
    busy = true; paint();
    try {
      const res = await api.post(act.path, { ...act.body, actor: 'human' });
      if (takeIn) { try { await takeIn(); } catch { /* takeIn reports its own errors */ } }
      toast(L.done((res.changed || []).length), 'ok', 4500);
      if ((res.report?.left || []).length) toast(L.left, 'warn', 7000);
    } catch (e) {
      errorToast(e, L.fail, 8000);
      if (e?.status === 409 && takeIn) { try { await takeIn(); } catch { /* reported there */ } }
    } finally { busy = false; }
    await refresh();
  }

  // a new storyboard was loaded (another tab saved, an edit turn ended): ask the state again
  const off = ctx.store?.on?.((kind) => { if (kind === 'load' && !busy) refresh(); });
  const unmount = () => { dead = true; off?.(); root.remove(); };
  scope?.add?.(unmount);
  refresh();
  return unmount;
}
