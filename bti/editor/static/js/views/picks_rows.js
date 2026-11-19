// The simple page of step 4 ("Chọn hình"): a header (the project, how many lines have pictures, the lines without one, the approval), the narration lines as rows with the
// pictures that will be on screen while each is spoken, a plain caption for each, the agent's reason, "+" to add one and "Tự chọn tay" to open the hand tools for the line; under
// the rows three lists of what the project has (the regions of the main painting, the context pictures, the clips). The page itself (views/picks.js) keeps the data, the
// saving, the agent's bar and the request box; this module draws the rows and owns the selection of the page (a click on a row, Ctrl or Shift for several, a chapter header).
//   const rows = mountPickRows({ top, col, scope, api });   rows.paint()   rows.paintHeader()   rows.selection   rows.unmount()
//   api: { simple() -> bool (which face shows), projectTitle(), data(), doc(), chapters(), starts(), reasonFor(beatId, rec), whyMissing(beatId), thumb(asset, region, box) -> element, videoUrl(asset) -> url,
//          isDirty(), busy(), add(beatId, item) -> token, undoAdd(token) -> bool, openHand(beatId, tab?), approve(), check(), drawRegions(), setCurrent(beatId), scriptHref }
// The decisions are in picks_rows_logic.js and selectlogic.js (pure, tested); the words are labels.js (PICKS_PAGE_LABELS).
import { h, kids, toast } from '../util.js';
import { PICKS_PAGE_LABELS as W, PICKS_AUTO_LABELS as AL, FLAG, FLAG_HELP } from '../labels.js';
import { pickRows, nextMissing, headerNumbers, approveState, pageBlocker, sectionsOf } from './picks_rows_logic.js';
import { emptySelection, applyClick, selectChapter, pruneSelection, stepFocus } from '../selectlogic.js';

export function mountPickRows({ top, col, scope, api }) {
  let list = null, sel = emptySelection(), dead = false, lastMissing = null, menu = null, sectionTab = null, added = null;
  const collapsed = new Set(), expanded = new Set(), listeners = new Set();
  const notify = () => { for (const fn of [...listeners]) { try { fn(); } catch { /* one listener never stops the others */ } } };
  const selection = { get: () => ({ ids: [...sel.ids], chapter: sel.chapter }), onChange: (fn) => { listeners.add(fn); return () => listeners.delete(fn); } };
  const build = () => pickRows({ chapters: api.chapters(), doc: api.doc(), starts: api.starts(), reasonFor: api.reasonFor });
  const $in = (s) => col.querySelector(s);

  // ---------------------------------------------------------------- the header
  function paintHeader() {
    if (dead || !top || !api.data() || !api.simple()) return;                      // the hand face has its own header
    const d = api.data(), counts = (list || (list = build())).counts, num = headerNumbers(counts);
    const ap = approveState({ d, doc: api.doc(), dirty: api.isDirty(), emptyCount: counts.missingCount, busy: api.busy() });
    const errs = ap.errors;
    top.replaceChildren(...kids(
      h('h1', { class: 'ph-title', text: W.title }),
      h('span', { class: 'ph-project', title: api.projectTitle(), text: api.projectTitle() }),
      h('span', { class: 'ph-progress', id: 'pk-progress' }, h('span', { text: num.progress }), counts.total ? h('progress', { max: 1, value: num.fraction, 'aria-hidden': 'true' }) : null),
      counts.missingCount ? h('button', { class: 'ph-missing', id: 'pk-missing', text: num.missing, title: W.missingHint, onclick: () => jumpMissing() }) : null,
      num.skipped ? h('span', { class: 'ph-skipped muted', text: num.skipped }) : null,
      h('span', { class: 'grow' }),
      h('span', { id: 'pk-state', class: 'muted ph-state' }),
      h('button', { class: 'small', id: 'pk-check', text: errs ? W.top.checkErrors(errs) : W.top.check, onclick: () => api.check() }),
      ap.why ? h('span', { class: 'ph-why hint', id: 'pk-why', text: ap.why }) : ap.note ? h('span', { class: 'ph-why hint', id: 'pk-why', text: ap.note }) : null,
      h('button', { class: ap.approved ? '' : ap.why ? 'blocked' : 'primary', id: 'pk-approve', text: ap.label, disabled: !ap.canPress, title: ap.why || '', onclick: () => api.approve() })));
  }

  // ---------------------------------------------------------------- the rows
  function pic(r, p) {
    const a = api.doc().assets?.[p.key];
    const box = h('span', { class: 'pr-thumb' + (p.gone ? ' gone' : '') });
    if (a && p.video) {
      const v = h('video', { src: api.videoUrl(a), preload: 'metadata', muted: true, playsinline: true, tabindex: -1, 'aria-hidden': 'true' });
      box.append(v, h('span', { class: 'pr-play', text: '▶' }));
    } else if (a) box.append(api.thumb(a, p.region, 64));
    if (p.flag && FLAG[p.flag]) box.append(h('span', { class: 'pr-flag', text: '!', title: `${FLAG[p.flag]}. ${FLAG_HELP[p.flag] || ''}` }));
    return h('figure', { class: 'pr-pic' }, box, h('figcaption', { class: 'pr-cap', title: p.caption, text: p.caption }));
  }
  function rowEl(r) {
    const open = expanded.has(r.id);
    const why = r.status === 'empty' ? api.whyMissing(r.id) : '';
    return h('li', { class: 'pr-item' },
      h('div', { class: 'pr-row st-' + r.status, 'data-id': r.id },
        h('div', { class: 'pr-left' },
          h('button', { type: 'button', class: 'pr-head', 'aria-pressed': 'false', 'data-id': r.id },
            h('span', { class: 'pr-no' }, r.time ? h('span', { class: 'mono pr-time', text: r.time }) : null, h('span', { class: 'pr-n', text: W.lineNo(r.number) })),
            h('span', { class: 'pr-text' + (open ? ' open' : ''), text: open && r.rest ? `${r.first} ${r.rest}` : r.first })),
          r.hasMore ? h('button', { type: 'button', class: 'small text-btn pr-more', text: open ? W.less : W.more, 'aria-expanded': String(open), onclick: () => { if (open) expanded.delete(r.id); else expanded.add(r.id); paintRows(); } }) : null,
          r.status === 'empty' ? h('div', { class: 'pr-empty' }, W.empty, why ? h('span', { class: 'pr-why', text: ' ' + AL.lineWhy(why) }) : null) : null,
          r.status === 'skip' ? h('div', { class: 'pr-skip muted', text: W.skip }) : null,
          r.reason ? h('div', { class: 'pr-reason', title: AL.lineWhyTitle, text: AL.lineWhy(r.reason) }) : null),
        h('div', { class: 'pr-right' },
          h('div', { class: 'pr-pics' }, ...r.pics.map((p) => pic(r, p)),
            h('button', { type: 'button', class: 'pr-add', 'data-id': r.id, text: W.add, title: W.addTitle, 'aria-haspopup': 'menu', onclick: (e) => openMenu(e.currentTarget, r) })),
          h('button', { type: 'button', class: 'small pr-hand', 'data-id': r.id, text: W.hand, title: W.handTitle, onclick: () => api.openHand(r.id) }))));
  }
  function groupEl(g) {
    const rows = g.ids.map((id) => list.rows.find((x) => x.id === id));
    const isOpen = !collapsed.has(g.key);
    const body = h('ul', { class: 'pr-rows', hidden: isOpen ? null : true }, rows.map(rowEl));
    const head = h('div', { class: 'chap-head', 'data-chapter': g.key },
      h('button', { type: 'button', class: 'chap-toggle', 'aria-expanded': String(isOpen), title: isOpen ? W.chapter.collapse : W.chapter.expand,
        onclick: () => { if (collapsed.has(g.key)) collapsed.delete(g.key); else collapsed.add(g.key); paintRows(); } },
        h('span', { class: 'chap-arrow', text: isOpen ? '▾' : '▸' }),
        h('span', { class: 'chap-names' }, h('span', { class: 'chap-title', text: g.title })),
        h('span', { class: 'chap-prog' + (g.done === g.total ? ' ok' : ''), text: W.chapter.count(g.done, g.total) })),
      h('button', { type: 'button', class: 'small chap-sel', 'data-chapter': g.key, text: W.chapter.selectAll, title: W.chapter.selectAllHint, onclick: () => pickChapter(g) }));
    return h('li', { class: 'chap-group', 'data-chapter': g.key }, head, body);
  }

  function paintRows() {
    if (dead || !col || !api.data()) return;
    closeMenu();
    list = build();
    sel = pruneSelection(sel, list.order, list.chapterRows);
    if (!sel.ids.length && list.order.length) { sel = { ids: [list.order[0]], anchor: list.order[0], chapter: null }; api.setCurrent(list.order[0]); queueMicrotask(notify); }    // the first line is the one selected, as it was on the old page
    const scroller = $in('#pk-rows-scroll');
    const keep = scroller ? scroller.scrollTop : 0;
    const blocker = pageBlocker(api.data(), api.doc());
    const box = h('div', { class: 'pr-scroll', id: 'pk-rows-scroll' },
      blocker ? h('div', { class: 'pr-blocker ' + blocker.kind }, h('span', { text: blocker.text }),
        blocker.kind === 'no_main' ? h('button', { class: 'primary small', id: 'pk-choose-main', text: W.main.choose, onclick: () => api.openHand(null, 'main') })
          : h('a', { class: 'lnk', href: api.scriptHref, text: W.stages.narration })) : null,
      list.rows.length ? h('ul', { class: 'pr-list' }, list.groups.map(groupEl)) : (blocker?.kind === 'no_narration' ? null : h('div', { class: 'empty muted', text: W.noLines })));
    col.replaceChildren(...kids(box, sectionsEl(), footEl()));
    box.scrollTop = keep;
    box.addEventListener('click', onClick);
    box.addEventListener('keydown', onKey);
    paintSelection();
    paintHeader();
  }

  // ---------------------------------------------------------------- the selection
  function paintSelection({ scroll = false } = {}) {
    if (dead || !col || !list) return;
    const on = new Set(sel.ids), first = sel.ids[0] || list.order[0];
    for (const b of col.querySelectorAll('.pr-head')) {
      const id = b.dataset.id, row = b.closest('.pr-row');
      row.classList.toggle('sel', on.has(id));
      b.setAttribute('aria-pressed', on.has(id) ? 'true' : 'false');
      b.tabIndex = id === first ? 0 : -1;
    }
    for (const g of col.querySelectorAll('.chap-group')) g.classList.toggle('chap-on', !!sel.chapter && g.dataset.chapter === sel.chapter);
    for (const b of col.querySelectorAll('.chap-sel')) b.classList.toggle('on', !!sel.chapter && b.dataset.chapter === sel.chapter);
    if (scroll && sel.ids[0]) col.querySelector(`.pr-row[data-id="${CSS.escape(sel.ids[sel.ids.length - 1])}"]`)?.scrollIntoView({ block: 'nearest' });
  }
  function select(id, mods = {}, { scroll = false } = {}) {
    if (!list?.order.includes(id)) return;
    const next = applyClick(sel, id, mods, list.order);
    if (!next.ids.length) return;                                                   // never nothing selected: a request would then fall back to a whole chapter
    sel = next;
    api.setCurrent(sel.ids.includes(id) ? id : sel.ids[sel.ids.length - 1] || id);
    paintSelection({ scroll });
    notify();
  }
  function pickChapter(g) {
    sel = selectChapter(sel, g.key, g.ids, list.order);
    api.setCurrent(sel.ids[0] || null);
    paintSelection();
    notify();
  }
  function onClick(e) {
    if (e.target.closest?.('button:not(.pr-head), a, input, summary, video')) return;           // a control of the row does its own thing
    const row = e.target.closest?.('.pr-row');
    if (row) select(row.dataset.id, { shift: e.shiftKey, toggle: e.ctrlKey || e.metaKey });
  }
  const visibleOrder = () => [...col.querySelectorAll('.pr-head')].filter((b) => !b.closest('[hidden]')).map((b) => b.dataset.id);
  function onKey(e) {
    const b = e.target.closest?.('.pr-head');
    if (!b || e.altKey || e.ctrlKey || e.metaKey) return;
    let id = null;
    if (e.key === 'ArrowDown') id = stepFocus(visibleOrder(), b.dataset.id, 1);
    else if (e.key === 'ArrowUp') id = stepFocus(visibleOrder(), b.dataset.id, -1);
    else if (e.key === 'Home') id = visibleOrder()[0];
    else if (e.key === 'End') id = visibleOrder().slice(-1)[0];
    if (!id) return;
    e.preventDefault();
    const n = col.querySelector(`.pr-head[data-id="${CSS.escape(id)}"]`);
    n?.focus(); n?.scrollIntoView({ block: 'nearest' });
  }
  function jumpMissing() {
    if (!list) return;
    const r = nextMissing(list, lastMissing);
    if (!r) return;
    lastMissing = r.id;
    let opened = false;
    for (const g of list.groups) if (g.ids.includes(r.id) && collapsed.delete(g.key)) opened = true;
    if (opened) paintRows();
    select(r.id, {}, { scroll: true });
    col.querySelector(`.pr-head[data-id="${CSS.escape(r.id)}"]`)?.focus({ preventScroll: true });
  }

  // ---------------------------------------------------------------- "+": add one picture to a line
  function closeMenu({ focus = false } = {}) {
    if (!menu) return;
    const { el, btn, off } = menu;
    menu = null; off(); el.remove();
    if (focus) btn?.focus();
  }
  /** "+" added a picture: the foot of the list says so for a few seconds, with "Hoàn tác" (the hand tools save the same way: this is their quick add, not a batch of the change log). */
  function addPicture(r, item, what) {
    const token = api.add(r.id, item);
    added = { token, text: W.added(what, r.number) };
    scope.timeout(() => { if (added?.token === token) { added = null; paintFoot(); } }, 9000);
    paintFoot();
  }
  function undoAdded() {
    if (!added) return;
    const ok = api.undoAdd(added.token);
    added = null;
    toast(ok ? W.undone : W.undoGone, ok ? 'ok' : 'warn', 3000);
    paintFoot();
  }
  function footEl() {
    return added ? h('div', { class: 'pr-foot pr-added', id: 'pk-added', role: 'status' }, h('span', { text: added.text }), h('button', { type: 'button', class: 'small', id: 'pk-added-undo', text: W.undo, title: W.undoHint, onclick: undoAdded }))
      : h('div', { class: 'pr-foot hint', text: W.rowsHint });
  }
  function paintFoot() { const old = $in('.pr-foot'); if (old && !dead) old.replaceWith(footEl()); }
  function openMenu(btn, r) {
    const wasOpen = menu?.btn === btn;
    closeMenu();
    if (wasOpen) return;
    const doc = api.doc(), main = doc.assets?.[doc.main_asset];
    const items = [];
    if (main) {
      items.push({ text: W.addMenu.whole, run: () => addPicture(r, { asset: doc.main_asset }, W.caption.whole) });
      for (const [name, reg] of Object.entries(main.regions || {})) {
        const label = (typeof reg?.label === 'string' && reg.label.trim() && !/^[A-Z0-9_]{2,}$/.test(reg.label.trim())) ? reg.label.trim() : W.caption.detailAny.replace('Cận cảnh: ', '');
        items.push({ text: W.addMenu.detail(label), run: () => addPicture(r, { asset: doc.main_asset, region: name }, W.caption.detail(label)) });
      }
    }
    items.push({ text: W.addMenu.other, run: () => api.openHand(r.id, 'search') });
    const el = h('div', { class: 'pr-menu', role: 'menu' }, items.map((it) => h('button', { type: 'button', role: 'menuitem', class: 'pr-menu-item', text: it.text, onclick: () => { closeMenu(); it.run(); } })));
    col.append(el);
    const b = btn.getBoundingClientRect(), c = col.getBoundingClientRect(), eh = el.offsetHeight;
    const below = c.bottom - b.bottom, up = b.top - c.top;
    el.style.left = Math.max(c.left + 6, Math.min(b.left, c.right - el.offsetWidth - 6)) + 'px';
    el.style.top = (below >= eh + 6 || below >= up ? b.bottom + 4 : b.top - eh - 4) + 'px';
    const away = (ev) => { if (!el.contains(ev.target) && ev.target !== btn) closeMenu(); };
    document.addEventListener('mousedown', away, true);
    const sc = $in('#pk-rows-scroll'); const onScroll = () => closeMenu(); sc?.addEventListener('scroll', onScroll);
    menu = { el, btn, off: () => { document.removeEventListener('mousedown', away, true); sc?.removeEventListener('scroll', onScroll); } };
    el.querySelector('button')?.focus();
  }
  scope.on(document, 'keydown', (e) => {
    if (!menu) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeMenu({ focus: true }); }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const bs = [...menu.el.querySelectorAll('button')], i = bs.indexOf(document.activeElement);
      e.preventDefault(); bs[(i + (e.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length]?.focus();
    }
  }, true);

  // ---------------------------------------------------------------- the three lists: regions of the main painting, context pictures, clips
  function sectionsEl() {
    const S = sectionsOf(api.doc(), list.rows);
    const tabs = [['regions', W.sections.regions, S.regions], ['context', W.sections.context, S.context], ['clips', W.sections.clips, S.clips]];
    const used = (n) => h('span', { class: 'ps-used muted', text: W.sections.usedIn(n) });
    const item = (k, x) => {
      const a = api.doc().assets;
      if (k === 'regions') { const main = a[api.doc().main_asset]; return h('div', { class: 'ps-item' }, api.thumb(main, x.key, 56), h('span', { class: 'ps-name', text: x.label }), used(x.usedIn)); }
      const asset = a[x.key];
      const th = asset?.kind === 'video' ? h('span', { class: 'pr-thumb' }, h('video', { src: api.videoUrl(asset), preload: 'metadata', muted: true, tabindex: -1, 'aria-hidden': 'true' }), h('span', { class: 'pr-play', text: '▶' })) : api.thumb(asset, null, 56);
      return h('div', { class: 'ps-item' }, th, h('span', { class: 'ps-name', text: k === 'clips' && x.seconds ? `${x.title} · ${W.sections.clipLen(x.seconds)}` : x.title }), used(x.usedIn));
    };
    const body = sectionTab && tabs.find((t) => t[0] === sectionTab);
    return h('div', { class: 'pr-sections' + (body ? ' open' : ''), id: 'pk-sections' },
      h('div', { class: 'ps-tabs', role: 'tablist', 'aria-label': W.sections.title },
        ...tabs.map(([k, label, items]) => h('button', { type: 'button', role: 'tab', 'aria-selected': String(sectionTab === k), class: 'ps-tab' + (sectionTab === k ? ' on' : ''), 'data-tab': k,
          text: `${label} (${items.length})`, onclick: () => { sectionTab = sectionTab === k ? null : k; paintRows(); } })),
        h('span', { class: 'grow' }),
        api.doc().main_asset ? h('button', { type: 'button', class: 'small', id: 'pk-draw-regions', text: W.sections.drawRegion, onclick: () => api.drawRegions() }) : null),
      body ? h('div', { class: 'ps-body', role: 'tabpanel' }, body[2].length ? body[2].map((x) => item(body[0], x)) : h('div', { class: 'muted ps-none', text: W.sections.none[body[0]] })) : null);
  }

  // ---------------------------------------------------------------- keys: "/" goes to the request box
  scope.on(document, 'keydown', (e) => {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || !col.isConnected || col.offsetParent === null) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (document.querySelector('#modal-root .backdrop')) return;
    const ta = document.querySelector('.prompt-edit[data-box="picks"] .prompt-instruction');
    if (ta && !ta.disabled) { e.preventDefault(); ta.focus(); }
  });

  scope.add(() => { dead = true; closeMenu(); });
  return {
    paint: paintRows, paintHeader, selection, notify, select, jumpMissing,
    get list() { return list; },
    unmount() { dead = true; closeMenu(); },
  };
}
