// Inspector tabs: Shot, Lớp phủ, Hình (media.js), Lỗi.
import { h, $, $$ } from './util.js';
import { ctx, bus, assetThumbUrl, intentHsl, primaryAsset } from './ctx.js';
import { api } from './api.js';
import { renderForm } from './formui.js';
import { openGallery, previewUrl, usageChip, engineChip } from './gallery.js';
import { describeAnchor, anchorFromTime, round, anchorStale, shotIndexAt, cameraLists, fitCamera } from './logic.js';
import * as E from './edit.js';
const { parseIssuePath } = E;
import * as A from './actions.js';
import { renderMedia } from './media.js';
import { seek } from './timeline.js';

let tab = 'shot';
let lastSig = '';
let handle = null; // current form handle {sync}
const body = $('#tab-body');
export const currentTab = () => tab;

export function setTab(t) {
  tab = t; lastSig = '';
  $$('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === t));
  render(true);
}

function sig() {
  const st = ctx.store, s = st.shot, o = st.overlay;
  if (tab === 'media') return 'media';
  if (tab === 'issues') return 'issues' + ctx.issues.length + JSON.stringify(ctx.issues.slice(0, 40));
  return JSON.stringify([tab, st.sel, s && [s.technique, s.intent, s.locked, s.source, s.transition_in?.technique, cameraLists(s.params).map((l) => l.name + l.keys.length), JSON.stringify(s.slots), (s.overlays || []).map((x) => x.id + x.technique + x.locked)],
    o && [o.technique, o.intent, o.locked, o.source, Object.keys(o.params || {}).length, !!o.end, typeof o.dur], JSON.stringify(Object.keys(st.draft?.assets || {}))]);
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
      else commit('Đặt điểm bắt đầu', id, (o) => { o.start = anchorFromTime(ctx.t, ctx.words()); });
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
    rowOf('Nguồn', h('span', { class: 'chip ' + item.source, text: item.source || 'import' }), h('span', { class: 'hint', text: 'sửa tay luôn đặt = human' })),
    h('div', null, note));
}

function formFor(item, kind, tech) {
  const draft = ctx.store.draft;
  const primary = Object.values(item.slots || ctx.store.shot?.slots || {}).map((v) => v?.asset).find((k) => k && draft.assets[k]);
  const regions = primary ? draft.assets[primary].regions : {};
  const f = renderForm(tech.params, item.params || {}, {
    assets: draft.assets, regions,
    newKey: () => {
      const sh = kind === 'overlay' ? ctx.store.shot : ctx.store.shot;
      const pa = primaryAsset(sh);
      const c = pa ? fitCamera(pa.asset, ctx.canvasDims()) : { cx: 1000, cy: 1000, zoom: 0.5 };
      return { at: { rel: 0 }, cx: Math.round(c.cx), cy: Math.round(c.cy), zoom: Math.round(c.zoom * 1e4) / 1e4, ease: 'linear' };
    },
    onChange: (name, value) => A.setParam(kind, item.id, name, value),
  });
  handle = { sync: () => { const it = kind === 'overlay' ? ctx.store.overlay : ctx.store.shot; if (it) f.sync(it.params || {}); } };
  return f.el;
}

function renderShot() {
  const s = ctx.store.shot;
  if (!s) { body.append(h('div', { class: 'empty', text: 'Chọn một shot trên timeline.' })); return; }
  const tech = ctx.tech(s.technique);
  const intents = ctx.reg.intents;
  body.append(
    h('div', { class: 'hint', style: { marginBottom: '8px' }, text: `${s.id}: ${round(s._t0, 2)} - ${round(s._t1, 2)} s (${round(s._t1 - s._t0, 2)} s)` }),
    sect('Kỹ thuật', techCard(tech, () => openGallery({ title: 'Chọn kỹ thuật cho shot', kinds: ['base', 'card'], current: s.technique, onPick: (id) => A.setShotTechnique(s.id, id) })),
      !tech ? h('div', { class: 'hint err', text: `Kỹ thuật ${s.technique} không có trong registry` }) : null,
      rowOf('Ý đồ (intent)', h('select', { onchange: (e) => A.commitShot('Đổi intent', s.id, (x) => { x.intent = e.target.value; }) },
        ...intents.map((i) => h('option', { value: i, text: i + (tech && tech.intents.includes(i) ? ' *' : ''), selected: i === s.intent }))), h('span', { class: 'hint', text: '* hợp với kỹ thuật' }))),
    tech?.slots.length ? sect('Slot hình', ...tech.slots.map((sl) => slotRow(s, sl))) : null,
    startRow(s, 'shot', s.id),
    tech ? sect('Tham số (sinh từ registry)', formFor(s, 'shot', tech)) : null,
    transitionSection(s),
    metaSection(s, 'shot'));
}

function slotRow(s, sl) {
  const key = s.slots?.[sl.name]?.asset;
  const a = key && ctx.store.draft.assets[key];
  if (sl.type === 'text') {
    return h('div', { class: 'slot' }, h('div', { class: 'nm', text: sl.name }), h('input', { type: 'text', value: s.slots?.[sl.name]?.text || '', placeholder: 'văn bản', style: { flex: 1 },
      oninput: (e) => A.commitShot('Đổi slot', s.id, (x) => { (x.slots ||= {})[sl.name] = { text: e.target.value }; }, 'slot' + sl.name) }));
  }
  return h('div', { class: 'slot', title: sl.required ? 'Bắt buộc' : 'Tùy chọn' },
    a ? h('img', { src: assetThumbUrl(key, api), alt: key }) : h('div', { style: { width: '56px', height: '42px', background: '#000' } }),
    h('div', { class: 'nm', text: sl.name + (sl.required ? ' *' : '') }),
    h('div', { class: 'as', text: a ? `${key}: ${a.title || a.file}` : '(trống)' }),
    h('button', { class: 'small', text: 'Chọn', onclick: () => { ctx.slotPick = { shotId: s.id, slot: sl.name, kind: sl.type }; setTab('media'); } }));
}

function transitionSection(s) {
  const trs = ctx.reg.list.filter((t) => t.kind === 'transition');
  const cur = s.transition_in;
  const sel = h('select', { onchange: (e) => A.setTransition(s.id, e.target.value) }, h('option', { value: '', text: 'Cắt thẳng (mặc định của kênh)' }),
    ...trs.map((t) => h('option', { value: t.id, disabled: t.engine?.available !== true, selected: cur?.technique === t.id, text: `${t.id} ${t.label_vi}${t.engine?.available === true ? '' : ' (chưa có)'}` })));
  const kids = [rowOf('Chuyển vào', sel)];
  if (cur) {
    kids.push(rowOf('Thời lượng (s)', h('input', { type: 'number', step: 0.1, min: 0.1, value: cur.dur, onchange: (e) => A.commitShot('Đổi thời lượng chuyển cảnh', s.id, (x) => { x.transition_in.dur = Number(e.target.value) || 1; }) })));
    const t = ctx.tech(cur.technique);
    if (t) kids.push(renderForm(t.params, cur.params || {}, { assets: ctx.store.draft.assets, regions: {}, onChange: (n, v) => A.commitShot('Đổi tham số chuyển cảnh', s.id, (x) => { (x.transition_in.params ||= {})[n] = v; }, 'tr' + n) }).el);
  }
  return sect('Chuyển cảnh', ...kids);
}

function renderOverlay() {
  const st = ctx.store, s = st.shot;
  if (!s) { body.append(h('div', { class: 'empty', text: 'Chọn một shot hoặc lớp phủ.' })); return; }
  const list = h('div', { class: 'list' }, ...(s.overlays || []).map((o) => h('div', { class: 'list-item' + (o.id === st.sel.overlay ? ' sel' : ''), onclick: () => st.select(s.id, o.id) },
    h('span', { style: { width: '10px', height: '10px', borderRadius: '50%', background: intentHsl(o.intent, 50, 45) } }),
    h('b', { text: o.technique }), h('span', { class: 'muted', text: ctx.tech(o.technique)?.label_vi || '' }), h('span', { class: 'grow', style: { flex: 1 } }),
    h('span', { class: 'hint', text: `${round(o._t0, 1)} s` }), o.locked ? h('span', { class: 'chip partial', text: 'khóa' }) : null)));
  body.append(sect(`Lớp phủ của ${s.id} (${(s.overlays || []).length})`, (s.overlays || []).length ? list : h('div', { class: 'hint', text: 'Shot này chưa có lớp phủ.' }),
    h('div', { style: { marginTop: '8px', display: 'flex', gap: '8px' } }, h('button', { class: 'primary small', text: '+ Thêm lớp phủ', onclick: () => openGallery({ title: 'Chọn lớp phủ', kinds: ['overlay'], onPick: (id) => A.addOverlayAction(s.id, id) }) }))));
  const o = st.overlay;
  if (!o) return;
  const tech = ctx.tech(o.technique);
  body.append(
    sect('Kỹ thuật', techCard(tech, () => openGallery({ title: 'Đổi kỹ thuật lớp phủ', kinds: ['overlay'], current: o.technique, onPick: (id) => A.setOverlayTechnique(o.id, id) })),
      rowOf('Ý đồ (intent)', h('select', { onchange: (e) => A.commitOverlay('Đổi intent', o.id, (x) => { x.intent = e.target.value; }) }, ...ctx.reg.intents.map((i) => h('option', { value: i, text: i, selected: i === o.intent }))))),
    startRow(o, 'overlay', o.id),
    sect('Thời lượng', rowOf('dur (s)', h('input', { type: 'number', step: 0.1, min: 0.1, value: round(o._t1 - o._t0, 2),
      onchange: (e) => A.commitOverlay('Đổi thời lượng', o.id, (x, sh) => { delete x.end; x.dur = Math.max(0.1, Math.min(Number(e.target.value) || 1, sh._t1 - x._t0)); }) }),
      h('button', { class: 'small', text: 'Đến hết shot', onclick: () => A.commitOverlay('Đến hết shot', o.id, (x) => { delete x.end; delete x.dur; }) }))),
    tech ? sect('Tham số (sinh từ registry)', formFor(o, 'overlay', tech)) : null,
    metaSection(o, 'overlay'),
    h('button', { class: 'danger', text: 'Xóa lớp phủ này', onclick: () => A.removeOverlayAction(o.id) }));
}

function renderIssues() {
  const list = ctx.issues;
  if (!list.length) { body.append(h('div', { class: 'empty', text: 'Không có lỗi hay cảnh báo. Bấm "Kiểm tra" để chạy lại.' })); return; }
  const errs = list.filter((i) => i.level === 'error').length;
  body.append(h('div', { class: 'hint', style: { marginBottom: '8px' }, text: `${errs} lỗi, ${list.length - errs} cảnh báo` }));
  body.append(h('div', { class: 'list' }, ...list.map((i) => h('div', { class: 'list-item issue ' + i.level, onclick: () => selectIssue(i) },
    h('div', { class: 'msg' }, h('div', { text: i.message }), h('div', { class: 'path', text: i.path })),
    h('span', { class: 'chip ' + (i.level === 'error' ? 'missing' : 'partial'), text: i.level === 'error' ? 'lỗi' : 'cảnh báo' })))));
}

export function selectIssue(i) {
  const p = parseIssuePath(i.path), d = ctx.store.draft;
  if (!p || !d.shots[p.shot]) return;
  const s = d.shots[p.shot], o = p.overlay != null ? (s.overlays || [])[p.overlay] : null;
  ctx.store.select(s.id, o?.id || null);
  seek((o || s)._t0 + 0.01);
  setTab(o ? 'overlay' : 'shot');
}

export function initInspector() {
  $$('#tabs button').forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));
  bus.on('tab', (t) => setTab(t));
  bus.on('issues', () => { if (tab === 'issues') render(); const b = $('#tab-issues-n'); b.hidden = !ctx.issues.length; b.textContent = ctx.issues.length; });
  bus.on('assets', () => { if (tab === 'media') render(true); });
  ctx.store.on((kind) => { if (kind === 'select' && tab === 'media' && !ctx.slotPick) { /* keep media tab */ } else render(); });
  render(true);
}
