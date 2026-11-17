// Inspector tabs: Shot, Lớp phủ, Hình (media.js), Lỗi.
import { h, $, $$, detailFold, fillSelect, toast } from './util.js';
import { issueText, groupIssues } from './errmsg.js';
import { issueTarget } from './sbissues.js';
import { ctx, bus, assetThumbUrl, intentHsl, primaryAsset } from './ctx.js';
import { api } from './api.js';
import { renderForm } from './formui.js';
import { openGallery, previewUrl, usageChip, engineChip } from './gallery.js';
import { describeAnchor, anchorFromTime, round, anchorStale, cameraLists, fitCamera } from './logic.js';
import { paramSpace } from './coords.js';
import { slotKind, effectiveSlot, KIND_VI, isIncompleteIssue } from './slots.js';
import * as E from './edit.js';
import { intentLabel, sourceLabel } from './labels.js';
import * as A from './actions.js';
import { renderMedia, selectAsset } from './media.js';

let tab = 'shot';
let lastSig = '';
let handle = null; // current form handle {sync}
let root = null, body = null;                 // looked up when the view is mounted (initInspector)
export const currentTab = () => tab;

export function setTab(t) {
  tab = t; lastSig = '';
  $$('#tabs button', root).forEach((b) => b.classList.toggle('active', b.dataset.tab === t));
  render(true);
}

function sig() {
  const st = ctx.store, s = st.shot, o = st.overlay;
  if (tab === 'media') return 'media' + JSON.stringify([ctx.slotPick, Object.keys(st.draft?.assets || {})]);   // regions follow the draft on their own (media.js)
  if (tab === 'issues') return 'issues' + ctx.issues.length + JSON.stringify(ctx.issues.slice(0, 40));
  return JSON.stringify([tab, st.sel, s && [s.technique, s.intent, s.locked, s.source, s.transition_in?.technique, cameraLists(s.params).map((l) => l.name + l.keys.length), JSON.stringify(s.slots), (s.overlays || []).map((x) => x.id + x.technique + x.locked), ctx.incompleteText(s.id), ctx.thumbFailOf(s.id)],
    o && [o.technique, o.intent, o.locked, o.source, Object.keys(o.params || {}).length, !!o.end, typeof o.dur, JSON.stringify(o.slots), ctx.incompleteText(s.id, o.id), Object.keys(o.params || {}).map((k) => k === 'origin_space' || k === 'space' || k === 'background' ? o.params[k] : '').join()], JSON.stringify(Object.keys(st.draft?.assets || {}))]);
}

export function render(force = false) {
  if (!ctx.store.draft) { body.replaceChildren(h('div', { class: 'empty', text: 'Chưa mở dự án.' })); return; }
  const s = sig();
  if (!force && s === lastSig) { handle?.sync?.(); syncMeta(); return; }
  lastSig = s; handle = null;
  body.replaceChildren();
  if (tab === 'shot') renderShot();
  else if (tab === 'overlay') renderOverlay();
  else if (tab === 'media') renderMedia(body);
  else renderIssues();
  const n = ctx.issues.length;
  const badge = $('#tab-issues-n'); badge.hidden = !n; badge.textContent = n;
}
function syncMeta() { /* word start text etc. are rebuilt on structure change only */ }

const sect = (title, ...kids) => h('div', { class: 'sect' }, h('h4', null, title), ...kids);
const rowOf = (label, ...ctl) => h('div', { class: 'row' }, h('label', { text: label }), h('div', { class: 'ctl' }, ...ctl));

function techCard(t, onclick) {
  if (!t) return h('div', { class: 'tech-card', onclick }, h('div', null, h('div', { class: 'nm', text: 'Chưa chọn kỹ thuật' }), h('div', { class: 'en', text: 'Bấm để mở thư viện' })));
  return h('div', { class: 'tech-card', onclick, title: t.description },
    h('img', { src: previewUrl(t, 'thumb'), alt: '', onerror: (e) => { e.target.style.visibility = 'hidden'; } }),
    h('div', { style: { minWidth: 0 } }, h('div', { class: 'nm', text: `${t.label_vi}` }), h('div', { class: 'en', text: `${t.name} (${t.id})` }),
      h('div', { style: { display: 'flex', gap: '4px', marginTop: '4px', flexWrap: 'wrap' } }, usageChip(t), engineChip(t))));
}

function startRow(item, kind, id) {
  const a = item.start;
  const stale = anchorStale(a, ctx.words());
  const commit = kind === 'overlay' ? A.commitOverlay : A.commitShot;
  const offIn = h('input', { type: 'number', step: 0.05, value: a?.off ?? 0, disabled: typeof a?.w !== 'number', onchange: (e) => commit('Đổi offset', id, (it) => { it.start.off = Number(e.target.value) || 0; }) });
  return sect('Bắt đầu',
    rowOf('Neo', h('span', { class: stale ? 'hint err' : '', text: describeAnchor(a, ctx.words()) + (stale ? ' (từ đã đổi)' : '') }), h('span', { class: 'hint', text: `= ${round(item._t0, 2)} s` })),
    rowOf('Offset (s)', offIn),
    rowOf('Đặt', h('button', { class: 'small', text: 'Từ tại đầu phát', title: 'Gắn vào từ gần đầu phát nhất', onclick: () => {
      if (kind === 'shot') { const i = ctx.store.draft.shots.findIndex((s) => s.id === id); ctx.store.commit('Đặt điểm bắt đầu', (d) => E.moveBoundary(d, i, ctx.t, ctx.words(), false)); }
      else commit('Đặt điểm bắt đầu', id, (o) => { o.start = anchorFromTime(ctx.t, ctx.words(), false, Infinity); });
    } }), h('button', { class: 'small', text: 'Giây tự do', title: 'Neo theo giây tuyệt đối {t}', onclick: () => {
      if (kind === 'shot') { const i = ctx.store.draft.shots.findIndex((s) => s.id === id); ctx.store.commit('Đặt điểm bắt đầu', (d) => E.moveBoundary(d, i, item._t0, ctx.words(), true)); }
      else commit('Đặt điểm bắt đầu', id, (o) => { o.start = { t: round(o._t0, 3) }; });
    } })));
}

function metaSection(item, kind) {
  const commit = kind === 'overlay' ? A.commitOverlay : A.commitShot;
  const lock = h('input', { type: 'checkbox', checked: !!item.locked, onchange: (e) => commit('Khóa', item.id, (it) => { it.locked = e.target.checked; }) });
  const note = h('textarea', { value: item.note || '', placeholder: 'Ghi chú cho người sau và cho agent...' });
  note.addEventListener('input', () => commit('Ghi chú', item.id, (it) => { it.note = note.value; }, 'note'));
  return sect('Trạng thái', rowOf('Khóa (L)', lock, h('span', { class: 'hint', text: 'Agent và đề xuất không được sửa mục đã khóa' })),
    rowOf('Nguồn', h('span', { class: 'chip ' + item.source, text: sourceLabel(item.source), title: item.source || 'import' }), h('span', { class: 'hint', text: 'khi bạn sửa tay, mục này tự chuyển thành "bạn sửa tay"' })),
    h('div', null, note));
}

function formFor(item, kind, tech) {
  const draft = ctx.store.draft;
  const shot = ctx.store.shot;
  const pa = primaryAsset(shot);
  const regions = pa ? draft.assets[pa.key].regions : {};
  const live = () => (kind === 'overlay' ? ctx.store.overlay : ctx.store.shot) || item;
  const hasSlot = (n) => !!(live().slots?.[n]?.asset || shot?.slots?.[n]?.asset);
  const f = renderForm(tech.params, item.params || {}, {
    assets: draft.assets, regions,
    required: new Set((tech.slots || []).filter((sl) => sl.required && slotKind(sl) === 'text').map((sl) => sl.name)),
    spaceOf: (def) => paramSpace(tech.id, def, { params: live().params || {}, hasSlot }),
    centre: (space) => (space === 'frame' ? [0.5, 0.5] : space === 'canvas' ? [Math.round(ctx.canvasDims().w / 2), Math.round(ctx.canvasDims().h / 2)] : pa ? [Math.round(pa.asset.width / 2), Math.round(pa.asset.height / 2)] : [1000, 1000]),
    newKey: () => {
      const c = pa ? fitCamera(pa.asset, ctx.canvasDims()) : { cx: 1000, cy: 1000, zoom: 0.5 };
      return { at: { rel: 0 }, cx: Math.round(c.cx), cy: Math.round(c.cy), zoom: Math.round(c.zoom * 1e4) / 1e4, ease: 'linear' };
    },
    onChange: (name, value) => A.setParam(kind, item.id, name, value),
  });
  handle = { sync: () => { const it = live(); if (it) f.sync(it.params || {}); } };
  return f.el;
}

/** Slots that hold a picture (image, video, mask). A text "slot" is the parameter of the same name: it is edited in the parameter form. */
const pictureSlots = (tech) => (tech?.slots || []).filter((sl) => slotKind(sl) !== 'text');
const kids = (...x) => x.flat().filter((k) => k !== null && k !== undefined && k !== false);   // Element.append(null) would write the text "null"
const incompleteBanner = (shotId, overlayId) => {
  const n = ctx.incompleteOf(shotId, overlayId);
  return n ? h('div', { class: 'banner warn', text: `Chưa đủ (${ctx.incompleteText(shotId, overlayId)}). Lưu được, nhưng chưa duyệt được cho tới khi điền đủ.` }) : null;
};

const renderBanner = (shotId) => { const t = ctx.thumbFailOf(shotId); return t ? h('div', { class: 'banner warn render-fail', text: t }) : null; };

function renderShot() {
  const s = ctx.store.shot;
  if (!s) { body.append(h('div', { class: 'empty', text: 'Chọn một shot trên timeline.' })); return; }
  const tech = ctx.tech(s.technique);
  const intents = ctx.reg.intents;
  body.append(...kids(
    h('div', { class: 'hint', style: { marginBottom: '8px' }, text: `${s.id}: ${round(s._t0, 2)} - ${round(s._t1, 2)} s (${round(s._t1 - s._t0, 2)} s)` }),
    incompleteBanner(s.id), renderBanner(s.id),
    sect('Kỹ thuật', techCard(tech, () => openGallery({ title: 'Chọn kỹ thuật cho shot', kinds: ['base', 'card'], current: s.technique, onPick: (id) => A.setShotTechnique(s.id, id) })),
      !tech ? h('div', { class: 'hint err', text: `Kỹ thuật ${s.technique} không có trong registry` }) : null,
      rowOf('Ý đồ', fillSelect(h('select', { onchange: (e) => A.commitShot('Đổi ý đồ', s.id, (x) => { x.intent = e.target.value; }) }), intents, s.intent, (i) => intentLabel(i) + (tech && tech.intents.includes(i) ? ' *' : '')), h('span', { class: 'hint', text: '* hợp với kỹ thuật' }))),
    pictureSlots(tech).length ? sect('Slot hình', ...pictureSlots(tech).map((sl) => slotRow({ shotId: s.id }, s, sl, s, false))) : null,
    startRow(s, 'shot', s.id),
    tech ? sect('Tham số (sinh từ registry)', formFor(s, 'shot', tech)) : null,
    transitionSection(s),
    metaSection(s, 'shot')));
}

/** One slot of a shot or of an overlay. A slot shows its kind (ảnh, video, mặt nạ) and offers only assets of that kind. */
function slotRow(target, item, sl, shot, isOverlay) {
  const kind = slotKind(sl);
  const eff = effectiveSlot(item, sl.name, shot, isOverlay);
  const key = eff?.asset;
  const a = key && ctx.store.draft.assets[key];
  const missing = sl.required && !eff?.asset;
  const pick = () => { ctx.slotPick = { ...target, slot: sl.name, kind }; setTab('media'); };
  return h('div', { class: 'slot' + (missing ? ' missing' : ''), title: `${sl.required ? 'Bắt buộc' : 'Tùy chọn'}, cần ${KIND_VI[kind] || kind}` },
    a ? h('img', { src: assetThumbUrl(key, api), alt: '', onerror: (e) => { e.target.replaceWith(h('div', { class: 'thumb-none', title: 'Không đọc được hình này', style: { width: '56px', height: '42px', background: '#000' } })); } }) : h('div', { style: { width: '56px', height: '42px', background: '#000' } }),
    h('div', { class: 'nm', text: sl.name + (sl.required ? ' *' : '') }),
    h('div', { class: 'as', text: a ? `${eff.own === false ? '(theo shot) ' : ''}${key}: ${a.title || a.file}` : `(trống) cần ${KIND_VI[kind] || kind}` }),
    missing ? h('span', { class: 'chip partial', text: 'thiếu' }) : null,
    eff?.own ? h('button', { class: 'small', text: 'Bỏ', title: isOverlay && sl.name === 'image' ? 'Dùng lại hình của shot' : 'Để trống slot này', onclick: () => A.clearSlot(target, sl.name) }) : null,
    h('button', { class: 'small', text: 'Chọn', onclick: pick }));
}

function transitionSection(s) {
  const trs = ctx.reg.list.filter((t) => t.kind === 'transition');
  const cur = s.transition_in;
  const sel = fillSelect(h('select', { onchange: (e) => A.setTransition(s.id, e.target.value) }), ['', ...trs.map((t) => t.id)], cur?.technique || '',
    (id) => { const t = trs.find((x) => x.id === id); return !id ? 'Cắt thẳng (mặc định của kênh)' : t ? `${t.id} ${t.label_vi}` : id; },
    (id) => { const t = trs.find((x) => x.id === id); return id && t && t.engine?.available !== true ? { disabled: true, text: `${t.id} ${t.label_vi} (chưa có)` } : null; });
  const kids = [rowOf('Chuyển vào', sel)];
  if (cur) {
    kids.push(rowOf('Thời lượng (s)', h('input', { type: 'number', step: 0.1, min: 0.1, value: cur.dur, onchange: (e) => A.commitShot('Đổi thời lượng chuyển cảnh', s.id, (x) => { x.transition_in.dur = Number(e.target.value) || 1; }) })));
    const t = ctx.tech(cur.technique);
    if (t) kids.push(renderForm(t.params, cur.params || {}, { assets: ctx.store.draft.assets, regions: {}, spaceOf: (def) => paramSpace(t.id, def, { params: ctx.store.shotById(s.id)?.transition_in?.params || {} }), onChange: (n, v) => A.commitShot('Đổi tham số chuyển cảnh', s.id, (x) => { (x.transition_in.params ||= {})[n] = v; }, 'tr' + n) }).el);
  }
  return sect('Chuyển cảnh', ...kids);
}

function renderOverlay() {
  const st = ctx.store, s = st.shot;
  if (!s) { body.append(h('div', { class: 'empty', text: 'Chọn một shot hoặc lớp phủ.' })); return; }
  const list = h('div', { class: 'list' }, ...(s.overlays || []).map((o) => h('div', { class: 'list-item' + (o.id === st.sel.overlay ? ' sel' : ''), onclick: () => A.selectItem(s.id, o.id) },
    h('span', { style: { width: '10px', height: '10px', borderRadius: '50%', background: intentHsl(o.intent, 50, 45) } }),
    h('b', { text: o.technique }), h('span', { class: 'muted', text: ctx.tech(o.technique)?.label_vi || '' }), h('span', { class: 'grow', style: { flex: 1 } }),
    ctx.incompleteOf(s.id, o.id) ? h('span', { class: 'chip partial', title: ctx.incompleteText(s.id, o.id), text: ctx.incompleteText(s.id, o.id) }) : null,
    h('span', { class: 'hint', text: `${round(o._t0, 1)} s` }), o.locked ? h('span', { class: 'chip partial', text: 'khóa' }) : null)));
  body.append(sect(`Lớp phủ của ${s.id} (${(s.overlays || []).length})`, (s.overlays || []).length ? list : h('div', { class: 'hint', text: 'Shot này chưa có lớp phủ.' }),
    h('div', { style: { marginTop: '8px', display: 'flex', gap: '8px' } }, h('button', { class: 'primary small', text: '+ Thêm lớp phủ', onclick: () => openGallery({ title: 'Chọn lớp phủ', kinds: ['overlay'], onPick: (id) => A.addOverlayAction(s.id, id) }) }))));
  const o = st.overlay;
  if (!o) return;
  const tech = ctx.tech(o.technique);
  const target = { shotId: s.id, overlayId: o.id };
  body.append(...kids(
    incompleteBanner(s.id, o.id),
    sect('Kỹ thuật', techCard(tech, () => openGallery({ title: 'Đổi kỹ thuật lớp phủ', kinds: ['overlay'], current: o.technique, onPick: (id) => A.setOverlayTechnique(o.id, id, s.id) })),
      rowOf('Ý đồ', fillSelect(h('select', { onchange: (e) => A.commitOverlay('Đổi ý đồ', o.id, (x) => { x.intent = e.target.value; }) }), ctx.reg.intents, o.intent, intentLabel))),
    pictureSlots(tech).length ? sect('Slot hình của lớp phủ', ...pictureSlots(tech).map((sl) => slotRow(target, o, sl, s, true))) : null,
    startRow(o, 'overlay', o.id),
    sect('Thời lượng', rowOf('dur (s)', h('input', { type: 'number', step: 0.1, min: 0.1, value: round(o._t1 - o._t0, 2),
      onchange: (e) => A.commitOverlay('Đổi thời lượng', o.id, (x, sh) => { delete x.end; x.dur = Math.max(0.1, Math.min(Number(e.target.value) || 1, sh._t1 - x._t0)); }) }),
      h('button', { class: 'small', text: 'Đến hết shot', onclick: () => A.commitOverlay('Đến hết shot', o.id, (x) => { delete x.end; delete x.dur; }) }))),
    tech ? sect('Tham số (sinh từ registry)', formFor(o, 'overlay', tech)) : null,
    metaSection(o, 'overlay'),
    h('button', { class: 'danger', text: 'Xóa lớp phủ này', onclick: () => A.removeOverlayAction(o.id, s.id) })));
}

/** One issue in words; the server's English text is kept under "chi tiết" only when the sentence is a general one. */
function issueLine(i, n = 1) {
  const t = issueText(i);
  return h('div', null, h('div', { text: n > 1 ? `${t.text} (${n} chỗ)` : t.text }), t.generic && t.detail ? detailFold(t.detail) : null);
}
function renderIssues() {
  const list = ctx.issues;
  if (!list.length) { body.append(h('div', { class: 'empty', text: 'Không có lỗi hay cảnh báo. Bấm "Kiểm tra" để chạy lại.' })); return; }
  const errs = list.filter((i) => i.level === 'error').length;
  body.append(h('div', { class: 'hint', style: { marginBottom: '8px' }, text: `${errs} lỗi, ${list.length - errs} cảnh báo` }));
  body.append(h('div', { class: 'list' }, ...groupIssues(list).map(({ issue: i, n }) => h('div', { class: 'list-item issue ' + i.level, onclick: () => selectIssue(i) },
    h('div', { class: 'msg' }, issueLine(i, n)),
    h('span', { class: 'chip ' + (i.level === 'error' ? 'missing' : 'partial'), text: i.level === 'error' ? 'lỗi' : isIncompleteIssue(i) ? 'chưa đủ' : 'cảnh báo' })))));
}

export function selectIssue(i) {
  const d = ctx.store.draft;
  const tg = issueTarget(i, d);
  if (tg.kind === 'shot') {
    const s = d.shots[tg.shot], o = tg.overlay != null ? (s.overlays || [])[tg.overlay] : null;
    A.selectItem(s.id, o?.id || null);       // the playhead goes into the item
    setTab(o ? 'overlay' : 'shot');
  } else if (tg.kind === 'asset') {
    if (tg.shots.length) {
      A.selectItem(tg.shots[0], null); setTab('shot');
      toast(tg.shots.length === 1 ? `Hình ${tg.asset} chỉ dùng ở shot ${tg.shots[0]}.` : `Hình ${tg.asset} được dùng ở ${tg.shots.length} shot. Đang mở shot đầu tiên (${tg.shots[0]}).`, '', 5000);
    } else { selectAsset(tg.asset); ctx.slotPick = null; setTab('media'); toast(`Hình ${tg.asset} chưa shot nào dùng. Đã mở tab Hình.`, '', 4000); }
  } else {
    const t = issueText(i);
    toast(t.text, '', 6000, t.detail || null);       // no place to go: stay where the owner is, show only the detail
  }
}

export function initInspector(viewRoot) {
  root = viewRoot; body = $('#tab-body', root); tab = 'shot'; lastSig = ''; handle = null;
  $$('#tabs button', root).forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));
  bus.on('tab', (t) => setTab(t));
  bus.on('issues', () => { if (tab === 'issues') render(); const b = $('#tab-issues-n', root); b.hidden = !ctx.issues.length; b.textContent = ctx.issues.length; });
  bus.on('assets', () => { if (tab === 'media') render(true); });
  bus.on('thumbfail', () => { if (tab === 'shot') render(); });
  ctx.store.on((kind) => { if (kind === 'select' && tab === 'media' && !ctx.slotPick) { /* keep media tab */ } else render(); });
  render(true);
}
