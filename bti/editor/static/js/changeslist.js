// "Lịch sử thay đổi" on the pictures page and the storyboard page (worker c2box): the change log of that document, newest first, plain and small.
//   const list = mountChangesList(container, { pid, doc: 'storyboard' | 'picks', scope, getAgents, onUndone });
//   list.refresh()   read the log and the state again (after a turn, after an undo)      list.unmount()
// Each row: time, who ("Bạn" or the agent's label), the owner's request, the sentences of the change; "Hoàn tác" on the row the state answer says can be
// undone now. The decisions are in changeslogic.js (pure, tested); the words are in labels.js (BOX_LABELS.changes); errors go through errmsg.js.
import { api } from './api.js';
import { h, toast } from './util.js';
import { errorText } from './errmsg.js';
import { BOX_LABELS as BL } from './labels.js';
import { changeRows, undoTarget, undoBody } from './changeslogic.js';

export function mountChangesList(container, { pid, doc, scope = null, getAgents = null, onUndone = null } = {}) {
  let dead = false, busy = false, target = null, rows = [];
  const P = `/api/projects/${encodeURIComponent(pid)}`;
  const count = h('span', { class: 'changes-count', text: '' });
  const body = h('div', { class: 'changes-body' });
  const root = h('details', { class: 'changes-list', 'data-doc': doc }, h('summary', null, h('span', { text: BL.changes.title }), ' ', count), body);
  container.replaceChildren(root);

  async function undo(row) {
    if (busy || !target || target.batch !== row.batch) return;
    busy = true; paint();
    try {
      await api.post(target.path, undoBody(target));
      toast(BL.changes.undoDone, 'ok', 3000);
      await refresh();
      onUndone?.(row);
    } catch (e) { toast(errorText(e), 'err', 8000); await refresh(); }
    finally { busy = false; if (!dead) paint(); }
  }

  function paint() {
    if (dead) return;
    count.textContent = rows.length ? `(${rows.length})` : '';
    if (!rows.length) { body.replaceChildren(h('div', { class: 'empty muted', text: BL.changes.empty })); return; }
    body.replaceChildren(h('ul', { class: 'changes-rows' }, rows.map((r) => h('li', { class: 'changes-row' + (r.undone ? ' undone' : '') + (r.isUndo ? ' is-undo' : ''), 'data-batch': r.batch },
      h('div', { class: 'changes-head' },
        h('span', { class: 'changes-when muted', text: r.when }),
        h('b', { class: 'changes-who', text: r.who }),
        r.isUndo ? h('span', { class: 'chip', text: BL.changes.undoOf }) : null,
        r.undone ? h('span', { class: 'chip', text: BL.changes.undone }) : null,
        h('span', { class: 'grow' }),
        r.canUndo ? h('button', { class: 'small changes-btn-undo', text: BL.changes.undo, title: BL.changes.undoHint, disabled: busy, onclick: () => undo(r) }) : null),
      r.note ? h('div', { class: 'changes-note muted', text: BL.changes.note(r.note) }) : null,
      r.lines.length ? h('ul', { class: 'changes-lines' }, r.lines.map((t) => h('li', { text: t }))) : null))));
  }

  async function refresh() {
    if (dead) return;
    try {
      const [log, state] = await Promise.all([api.get(`${P}/changes?doc=${encodeURIComponent(doc)}&limit=30`), api.get(`${P}/state`).catch(() => null)]);
      if (dead) return;
      const agents = getAgents ? await Promise.resolve(getAgents()).catch(() => null) : null;
      const t = undoTarget(state);
      target = t && ((doc === 'picks') === (t.step === 'picks')) ? t : null;       // the undo the state names belongs to one document
      rows = changeRows(log.changes, { agents, target });
    } catch (e) { if (!dead) body.replaceChildren(h('div', { class: 'muted', text: BL.changes.loadFail + errorText(e) })); return; }
    paint();
  }

  scope?.add?.(() => { dead = true; });
  refresh();
  return { refresh, unmount() { dead = true; root.remove(); } };
}
