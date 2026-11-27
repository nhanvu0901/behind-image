// The simple page of step 5 ("Dựng hình"): a header (the number of shots and the length, what needs fixing, "Chỉnh tay", "Duyệt"), the list of shots in plain words
// grouped by chapter, and under the player what the selected shot is. The player, the request box and the editor are the ones of views/storyboard.js; this module only
// draws what is new and owns the selection of the page (a click on a row, Ctrl or Shift for several, a chapter header for a whole chapter).
//   const simple = mountSimple(root, { pid, scope, shell, hooks });
//   hooks: { approve(), save(), setMode('hand'|'simple'), openInEditor({shot, overlay}), approving() -> bool, next() -> {label, go()} | null }
//   simple.paint()         draw everything again (after a load, a save, an edit, or when the page is shown)     simple.paintBar()   the header only
//   simple.selection       { get() -> {ids, chapter}, onChange(cb) -> off }: what the request box reads
//   simple.showProblems()  the dialog with every problem in words      simple.select(shotId)   select one shot and move the player there
// The decisions are in shotlist.js, shotsentence.js and selectlogic.js (pure, tested); the words are labels.js (EDIT_PAGE_LABELS).
import { ctx, bus } from './ctx.js';
import { api } from './api.js';
import { h, kids, modal } from './util.js';
import * as A from './actions.js';
import { EDIT_PAGE_LABELS as W } from './labels.js';
import { buildShotList, nextProblem, summaryText, spokenText, numbersText, approveView } from './shotlist.js';
import { mainAssetKey } from './shotsentence.js';
import { emptySelection, applyClick, selectChapter, pruneSelection, followPlayhead, stepFocus } from './selectlogic.js';
import { minSec, durationWords } from './editlogic.js';
import { shotIndexAt } from './logic.js';
import { momentWordsMap } from './visualedit_logic.js';

export function mountSimple(root, { pid, scope, shell, hooks, visual = null }) {
  const st = ctx.store;
  const $ = (s) => root.querySelector(s);
  const bar = $('#sbar'), col = $('#shots-col'), panel = $('#sel-panel');
  let list = null, sel = emptySelection(), selfDriven = false, dead = false, lastProblem = null;
  const collapsed = new Set(), listeners = new Set();
  const isSimple = () => root.dataset.mode === 'simple';

  const envNow = () => ({ tech: (id) => ctx.tech(id), assets: st.draft?.assets || {}, mainKey: mainAssetKey(st.draft, shell.pipeline?.painting?.title) });
  const notify = () => { for (const fn of [...listeners]) { try { fn(); } catch { /* one listener never stops the others */ } } };
  const selection = {
    get: () => ({ ids: [...sel.ids], chapter: sel.chapter }),
    onChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
  };
  const rowOf = (id) => list?.rows.find((r) => r.id === id) || null;

  // ---------------------------------------------------------------- the header
  function paintBar() {
    if (dead || !bar || !st.draft) return;
    if (!list) list = buildNow();
    const ap = st.draft.approvals?.storyboard || null;
    const av = approveView({ ap, rev: st.rev, dirty: st.dirty, problemShots: list.summary.problemShots, approving: hooks.approving() });
    const nx = av.current ? hooks.next() : null;
    const bad = list.summary.problemShots;
    bar.replaceChildren(...kids(
      h('h1', { class: 'sb-title', text: W.title }),
      h('span', { class: 'sb-project', title: shell.pipeline?.title || '', text: shell.pipeline?.title || '' }),
      h('span', { class: 'sb-sum', id: 'sb-sum', text: summaryText(list.summary) }),
      bad ? h('button', { class: 'sb-problems', id: 'sb-problems', text: W.problems.count(bad), title: W.problems.first, onclick: () => jumpToProblem() }) : null,
      list.summary.general ? h('button', { class: 'sb-problems general', id: 'sb-general', text: W.problems.general(list.summary.general), onclick: () => showProblems() }) : null,
      h('span', { class: 'grow' }),
      st.dirty ? h('span', { class: 'sb-dirty hint warn', text: W.top.dirty }) : null,
      st.dirty ? h('button', { class: 'small', id: 'sb-save', text: W.top.save, onclick: () => hooks.save() }) : null,
      av.why ? h('span', { class: 'sb-why hint', id: 'sb-why', text: av.why }) : null,
      h('button', { id: 'sb-hand', text: W.top.hand, title: W.top.handHint, onclick: () => hooks.setMode('hand') }),
      av.current ? h('span', { class: 'badge ok sb-approved', id: 'sb-approved', text: W.top.approved }) : h('button', { class: av.why ? 'blocked' : 'primary', id: 'sb-approve', text: av.label, disabled: !av.canPress, title: av.why || '', onclick: () => hooks.approve() }),
      nx ? h('button', { class: 'primary', id: 'sb-next', text: W.top.next(nx.label), onclick: () => nx.go() }) : null));
  }

  // ---------------------------------------------------------------- the list
  const buildNow = () => {
    const mw = visual ? momentWordsMap({ storyboard: st.draft, visual, words: st.timing?.words || [] }) : null;
    return buildShotList({ draft: st.draft, chapters: st.timing?.chapters || [], words: st.timing?.words || [], issues: ctx.issues, env: envNow(), momentWords: mw });
  };

  const BLOCKING = new Set(['incomplete', 'undrawable', 'asset']);
  const cannotDraw = (r) => !!r && r.problems.some((p) => BLOCKING.has(p.kind) && !p.overlay);          // the engine can only draw a stand-in with technical words for this shot
  function frame(r) {
    const rk = ctx.renderKey || st.rev;
    const box = h('span', { class: 'sr-frame' });
    if (cannotDraw(r)) { box.classList.add('bad'); box.title = W.frameFail; return box; }
    const img = h('img', { alt: '', loading: 'lazy', src: api.url(api.thumbUrl(pid, r.id, rk)) });
    img.addEventListener('error', () => { box.classList.add('bad'); box.title = W.frameFail; img.remove(); });
    box.append(img);
    return box;
  }
  function rowEl(r) {
    const meta = [r.length, r.locked ? W.locked : ''].filter(Boolean).join(' · ');
    return h('li', { class: 'shot-item' },
      h('button', { type: 'button', class: 'shot-row' + (r.problems.length ? ' has-problem' : ''), 'data-id': r.id, 'aria-pressed': 'false', title: r.locked ? W.lockedHint : '' },
        h('span', { class: 'sr-no', text: String(r.number) }),
        h('span', { class: 'sr-time mono', text: r.time }),
        frame(r),
        h('span', { class: 'sr-text' },
          h('span', { class: 'sr-sentence', text: r.sentence }),
          r.momentWords ? h('span', { class: 'sr-moment', text: `“${r.momentWords}”` }) : null,
          h('span', { class: 'sr-meta', text: meta }),
          ...r.problems.map((p) => h('span', { class: 'sr-prob', text: W.problems.line(p.text, !!p.overlay) })))));
  }
  function groupEl(g) {
    const rows = g.ids.map((id) => rowOf(id));
    const body = h('ul', { class: 'chap-rows', hidden: collapsed.has(g.key) ? true : null }, rows.map(rowEl));
    if (!g.title) return h('li', { class: 'chap-group no-title', 'data-chapter': g.key }, body);
    const open = !collapsed.has(g.key);
    const head = h('div', { class: 'chap-head', 'data-chapter': g.key },
      h('button', { type: 'button', class: 'chap-toggle', 'aria-expanded': String(open), title: open ? W.chapter.collapse : W.chapter.expand,
        onclick: () => { if (collapsed.has(g.key)) collapsed.delete(g.key); else collapsed.add(g.key); paintList(); } },
        h('span', { class: 'chap-arrow', text: open ? '▾' : '▸' }),
        h('span', { class: 'chap-names' }, h('span', { class: 'chap-title', text: g.title }), h('span', { class: 'chap-count muted', text: W.chapter.from(g.ids.length, minSec(g.t0)) })),
        g.problems ? h('span', { class: 'chap-bad', text: String(g.problems), title: W.problems.count(g.problems) }) : null),
      h('button', { type: 'button', class: 'small chap-sel', 'data-chapter': g.key, text: W.chapter.selectAll, title: W.chapter.selectAllHint, onclick: () => pickChapter(g) }));
    return h('li', { class: 'chap-group', 'data-chapter': g.key }, head, body);
  }

  function paintList() {
    const target = col?.querySelector('.ve-shots-host') || col;
    if (dead || !target || !st.draft) return;
    list = buildNow();
    sel = pruneSelection(sel, list.order, list.chapterRows);
    if (!sel.ids.length && st.sel.shot && list.order.includes(st.sel.shot)) sel = { ids: [st.sel.shot], anchor: st.sel.shot, chapter: null };
    const top = $('#shots-scroll')?.scrollTop || 0;
    const scroller = h('div', { class: 'shots-scroll', id: 'shots-scroll', tabindex: -1 },
      list.rows.length ? h('ul', { class: 'shot-list', 'aria-label': W.listTitle }, list.groups.map(groupEl)) : h('div', { class: 'empty muted', text: W.noShots }));
    target.replaceChildren(h('div', { class: 'shots-head' }, h('h2', { text: W.listTitle })), scroller, h('div', { class: 'shots-foot hint', text: W.listHint }));
    scroller.scrollTop = top;
    scroller.addEventListener('click', onListClick);
    scroller.addEventListener('keydown', onListKey);
    paintSelection();
    paintBar();
    hooks.onPaint?.();
  }

  // ---------------------------------------------------------------- the selection
  function paintSelection({ scroll = false } = {}) {
    if (dead || !col) return;
    const on = new Set(sel.ids), cur = st.sel.shot;
    for (const b of col.querySelectorAll('.shot-row')) {
      const id = b.dataset.id;
      b.classList.toggle('sel', on.has(id)); b.classList.toggle('now', id === cur);
      b.setAttribute('aria-pressed', on.has(id) ? 'true' : 'false');
      b.tabIndex = id === (cur && on.has(cur) ? cur : sel.ids[0] || list?.order[0]) ? 0 : -1;
    }
    for (const g of col.querySelectorAll('.chap-group')) g.classList.toggle('chap-on', !!sel.chapter && g.dataset.chapter === sel.chapter);
    for (const b of col.querySelectorAll('.chap-sel')) b.classList.toggle('on', !!sel.chapter && b.dataset.chapter === sel.chapter);
    if (scroll && cur) col.querySelector(`.shot-row[data-id="${CSS.escape(cur)}"]`)?.scrollIntoView({ block: 'nearest' });
    paintPanel(); paintStageNote();
  }
  function select(id, mods = {}) {
    if (!list?.order.includes(id)) return;
    const next = applyClick(sel, id, mods, list.order);
    if (!next.ids.length) return;                                                   // never nothing selected: a request would then fall back to a whole chapter
    sel = next;
    const go = sel.ids.includes(id) ? id : sel.ids[sel.ids.length - 1] || id;       // after taking a row away the player stays where it is
    selfDriven = true;
    try { A.selectItem(go); } finally { selfDriven = false; }
    paintSelection({ scroll: true });
    notify();
  }
  function pickChapter(g) {
    sel = selectChapter(sel, g.key, g.ids, list.order);
    selfDriven = true;
    try { A.selectItem(sel.ids[0]); } finally { selfDriven = false; }
    paintSelection();
    notify();
  }
  function onListClick(e) {
    const b = e.target.closest?.('.shot-row');
    if (b) select(b.dataset.id, { shift: e.shiftKey, toggle: e.ctrlKey || e.metaKey });
  }
  function onListKey(e) {
    const b = e.target.closest?.('.shot-row');
    if (!b || e.altKey || e.ctrlKey || e.metaKey) return;
    let id = null;
    if (e.key === 'ArrowDown') id = stepFocus(visibleOrder(), b.dataset.id, 1);
    else if (e.key === 'ArrowUp') id = stepFocus(visibleOrder(), b.dataset.id, -1);
    else if (e.key === 'Home') id = visibleOrder()[0];
    else if (e.key === 'End') id = visibleOrder().slice(-1)[0];
    if (!id) return;
    e.preventDefault();
    const next = col.querySelector(`.shot-row[data-id="${CSS.escape(id)}"]`);
    next?.focus();
    next?.scrollIntoView({ block: 'nearest' });
  }
  const visibleOrder = () => [...col.querySelectorAll('.shot-row')].filter((b) => !b.closest('[hidden]')).map((b) => b.dataset.id);

  /** The playhead or the timeline selected a shot (not a click on a row): the selection follows. */
  function onStoreSelect() {
    if (dead || selfDriven || !list) return;
    sel = followPlayhead(sel, st.sel.shot, { playing: ctx.playing });
    paintSelection({ scroll: true });
    notify();
  }

  /** Under the player: when the shot at the playhead cannot be drawn, the player says so in words instead of showing the engine's stand-in picture (a card with the technique's id). */
  function paintStageNote() {
    const stage = root.querySelector('#stage-box');
    if (!stage || !st.draft || !list) return;
    let note = stage.querySelector('.stage-note');
    if (!note) { note = h('div', { class: 'stage-note', role: 'status', hidden: true }); stage.append(note); }
    const r = list.rows[shotIndexAt(st.draft.shots, ctx.t)];
    const p = cannotDraw(r) ? r.problems.find((x) => BLOCKING.has(x.kind) && !x.overlay) : null;
    note.hidden = !p;
    note.textContent = p ? W.problems.stageNote(r.number, p.text) : '';
  }

  // ---------------------------------------------------------------- the selected shot, under the player
  function paintPanel() {
    if (!panel || !st.draft || !list) return;
    const r = rowOf(st.sel.shot) || rowOf(sel.ids[0]);
    if (!r) { panel.replaceChildren(h('div', { class: 'sel-none muted', text: W.now.none })); return; }
    const shot = st.shotById(r.id);
    const spoken = shot ? spokenText(ctx.words(), shot._t0, shot._t1) : '';
    const picked = sel.ids.length > 1 ? sel.ids.map((id) => rowOf(id)).filter(Boolean) : [];
    const many = picked.map((x) => x.number);
    const t0 = many.length ? Math.min(...picked.map((x) => x.t0)) : r.t0, t1 = many.length ? Math.max(...picked.map((x) => x.t1)) : r.t1;          // several shots: the span they cover
    panel.replaceChildren(...kids(
      h('div', { class: 'sel-head' },
        h('b', { class: 'sel-no', text: many.length ? W.now.several(many.length, numbersText(many)) : W.shotNo(r.number) }),
        h('span', { class: 'mono sel-time', text: W.now.time(minSec(t0), minSec(t1)) }),
        h('span', { class: 'muted', text: durationWords(t1 - t0) }),
        r.locked && !many.length ? h('span', { class: 'chip', text: W.locked, title: W.lockedHint }) : null),
      h('div', { class: 'sel-sentence', text: many.length ? `${W.shotNo(r.number)}: ${r.sentence}` : r.sentence }),
      h('div', { class: 'sel-spoken' }, h('span', { class: 'muted', text: spoken ? W.now.spoken : W.now.noSpoken }), spoken ? ` “${spoken}”` : ''),
      ...r.problems.map((p) => h('div', { class: 'sel-problem', text: W.problems.at(r.number, p.text, !!p.overlay) })),
      h('div', { class: 'sel-actions' }, h('button', { class: 'small', id: 'sel-hand', text: W.now.hand, onclick: () => hooks.openInEditor({ shot: r.id, overlay: r.problems.find((p) => p.overlay)?.overlay || null }) }))));
  }

  // ---------------------------------------------------------------- problems
  function jumpToProblem() {
    if (!list) return;
    const r = nextProblem(list, lastProblem);
    if (!r) return;
    lastProblem = r.id;
    let opened = false;
    for (const g of list.groups) if (g.ids.includes(r.id) && collapsed.delete(g.key)) opened = true;
    if (opened) paintList();
    select(r.id);
    col.querySelector(`.shot-row[data-id="${CSS.escape(r.id)}"]`)?.focus({ preventScroll: true });
  }
  function showProblems() {
    if (!list) list = buildNow();
    const bad = list.rows.filter((r) => r.problems.length);
    let m = null;
    const row = (r, p) => h('li', { class: 'prob-row' },
      h('span', { class: 'prob-text', text: W.problems.at(r.number, p.text, !!p.overlay) }),
      h('button', { class: 'small', text: W.problems.see, onclick: () => { m.close(); select(r.id); } }),
      h('button', { class: 'small', text: W.problems.inEditor, onclick: () => { m.close(); hooks.openInEditor({ shot: r.id, overlay: p.overlay }); } }));
    m = modal({ title: W.problems.title, cls: 'prob-dialog',
      body: h('div', { class: 'body' },
        list.general.length ? h('ul', { class: 'prob-list' }, list.general.map((g) => h('li', { class: 'prob-row' }, h('span', { class: 'prob-text', text: W.problems.generalText.charAt(0).toUpperCase() + W.problems.generalText.slice(1) + '.' }),
          h('button', { class: 'small', text: W.problems.inEditor, onclick: () => { m.close(); hooks.setMode('hand'); } })))) : null,
        bad.length ? h('ul', { class: 'prob-list' }, bad.flatMap((r) => r.problems.map((p) => row(r, p)))) : null,
        !bad.length && !list.general.length ? h('p', { class: 'muted', text: W.problems.none }) : null),
      footer: null });                                                            // the dialog's own "Đóng" is the way out
    return m;
  }

  // ---------------------------------------------------------------- keys: "/" goes to the request box
  scope.on(document, 'keydown', (e) => {
    if (!isSimple() || e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (document.querySelector('#modal-root .backdrop')) return;
    const ta = root.querySelector('#prompt-edit-container .prompt-instruction');
    if (ta && !ta.disabled) { e.preventDefault(); ta.focus(); }
  });

  // ---------------------------------------------------------------- what makes it draw again
  const offStore = st.on((kind) => {
    if (kind === 'select') onStoreSelect();
    else if (['load', 'draft', 'saved'].includes(kind)) { if (isSimple()) paintList(); else list = null; }
    else if (kind === 'approvals') paintBar();
  });
  const offIssues = bus.on('issues', () => { if (isSimple()) paintList(); else list = null; });
  scope.add(() => { dead = true; offStore(); offIssues(); });

  function paint() { if (st.draft) paintList(); }
  paint();
  return { paint, paintBar, paintPanel, select, selection, notify, showProblems, jumpToProblem, get list() { return list; } };
}
