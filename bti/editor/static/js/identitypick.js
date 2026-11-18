// The selector "Kiểu mở đầu và mốc chương" in the tools row of step 5 (Dựng hình).
//   const unmount = mountIdentityPick(container, { pid, scope, takeIn });
//   takeIn(): the editor takes the new saved storyboard in (reload, or the merge with unsaved edits: the same rule the prompt-edit panel
//             uses for a change made on the server; the page invents no other)
// Choosing a style asks PUT /api/projects/{pid}/identity with the revision the page holds; the server applies the style to the saved
// storyboard (same lock, revision and history copy as a save) and answers what changed and what it skipped. Then takeIn() loads it, so the
// preview shows it. "Hoàn tác" puts the storyboard back the way it was before the choice (a normal save of the previous content).
// The decisions are in identitylogic.js (pure, tested); the words are in labels.js (IDENTITY_LABELS); errors go through errmsg.js.
import { api } from './api.js';
import { MOCK } from './config.js';
import { h, toast, errorToast } from './util.js';
import { ctx } from './ctx.js';
import { IDENTITY_LABELS as L } from './labels.js';
import { selectorView, canChoose, chooseBody, skippedLines, resultLine } from './identitylogic.js';

export function mountIdentityPick(container, { pid, scope = null, takeIn = null } = {}) {
  let dead = false, busy = false, info = null, undo = null;
  const P = `/api/projects/${encodeURIComponent(pid)}`;

  const sel = h('select', { id: 'identity-select', class: 'identity-select', 'aria-label': L.title, title: L.titleHint, onchange: () => choose(sel.value) });
  const label = h('label', { class: 'identity-label', for: 'identity-select', text: L.title, title: L.titleHint });
  const undoBtn = h('button', { type: 'button', class: 'small identity-undo', text: L.undo, title: L.undoHint, hidden: true, onclick: () => doUndo() });
  const note = h('span', { class: 'hint identity-note' });
  const skippedBox = h('div', { class: 'identity-skipped', role: 'status', hidden: true });
  const root = h('div', { class: 'identity-pick', 'data-identity': '', hidden: true }, label, sel, undoBtn, note, skippedBox);
  container.replaceChildren(root);

  function paint() {
    if (dead) return;
    const v = selectorView(info, { busy });
    root.hidden = v.hidden;
    sel.replaceChildren(...v.options.map((o) => h('option', { value: o.value, text: o.text, disabled: o.disabled || null })));
    sel.value = v.value;
    sel.disabled = v.disabled;
    note.textContent = busy ? L.busy : v.note;
    undoBtn.hidden = !undo || busy || ctx.store?.rev !== undo.rev;           // a save after the choice makes the saved revision another one: the button goes
    root.dataset.style = info?.style || '';
  }

  function showSkipped(lines) {
    skippedBox.replaceChildren();
    skippedBox.hidden = !lines.length;
    if (!lines.length) return;
    skippedBox.append(h('b', { text: L.skippedLead }),
      h('ul', null, ...lines.map((t) => h('li', { text: t }))),
      h('button', { type: 'button', class: 'small text-btn', text: L.close, onclick: () => { skippedBox.hidden = true; } }));
  }

  async function refresh() {
    try { info = await api.get(`${P}/identity`); }
    catch (e) { info = null; if (!MOCK && !dead) errorToast(e, L.loadFail); }
    paint();
  }

  const takeInNow = async () => { if (takeIn) { try { await takeIn(); } catch { /* takeIn reports its own errors */ } } };

  async function choose(want) {
    if (!canChoose(info, want, { busy })) { paint(); return; }
    if (!ctx.store?.draft) { paint(); return; }
    busy = true; undo = null; showSkipped([]); paint();
    const before = ctx.store.savedSnap ? JSON.parse(ctx.store.savedSnap) : null;       // the saved storyboard: what Hoàn tác brings back
    try {
      const res = await api.put(`${P}/identity`, chooseBody(want, ctx.store.rev));
      info = { ...info, style: res.style };
      await takeInNow();
      toast(resultLine(info, res), 'ok', 4500);
      showSkipped(skippedLines(res.skipped, ctx.store?.draft?.shots || []));
      if (before && res.changed?.length) undo = { before, rev: res.rev };
    } catch (e) {
      errorToast(e, L.chooseFail, 8000);
      if (e?.status === 409) await takeInNow();              // the storyboard changed elsewhere: take the new one in, then the owner chooses again
    } finally { busy = false; }
    await refresh();
  }

  async function doUndo() {
    if (!undo || busy) return;
    const u = undo;
    busy = true; paint();
    try {
      await api.save(pid, u.before, u.rev);
      undo = null; showSkipped([]);
      await takeInNow();
      toast(L.undone, 'ok', 3500);
    } catch (e) {
      undo = null;
      errorToast(e, L.undoFail, 8000);
    } finally { busy = false; }
    await refresh();
  }

  // a new storyboard was loaded (another tab saved, a proposal was adopted, an edit turn ended): the style shown is asked again
  const off = ctx.store?.on?.((kind) => {
    if (kind === 'load' && !busy) { undo = undo && ctx.store.rev === undo.rev ? undo : null; refresh(); }
    else if (kind === 'saved') paint();
  });
  const unmount = () => { dead = true; off?.(); root.remove(); };
  scope?.add?.(unmount);
  refresh();
  return unmount;
}
