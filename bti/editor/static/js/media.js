// "Hình" tab: assets, region manager, licence-aware search, import and upload.
import { h, svg, toast, ask, errorToast, errorInto } from './util.js';
import { licenceText } from './errmsg.js';
import { flagLabel, FLAG_HELP } from './labels.js';
import { ctx, bus, assetThumbUrl } from './ctx.js';
import { api } from './api.js';
import { clone } from './logic.js';
import { makeSpaces } from './coords.js';
import { fits, KIND_VI } from './slots.js';
import * as A from './actions.js';
import { paintAsset } from './placeholder.js';
import { MOCK } from './config.js';

let selKey = null;
const state = { q: '', source: 'commons', kind: 'image', results: null, busy: false, armName: '' };
// Only the sources bti.media implements (GET /api/media/search source=).
export const SOURCES = [['commons', 'Wikimedia Commons'], ['met', 'The Met']];

function addAsset(key, asset, thumb) {
  ctx.assetInfo[key] = { ...(ctx.assetInfo[key] || {}), thumb_url: asset.thumb_url || thumb || '' };
  ctx.store.commit('Thêm hình ' + key, (d) => { const a = clone(asset); delete a.thumb_url; d.assets[key] = a; });
  bus.emit('assets');
}
/** Put an asset into the slot being picked. A slot takes only an asset of its own kind (image, video or mask). */
async function assign(key) {
  const p = ctx.slotPick; if (!p) return;
  const done = await A.assignSlot({ shotId: p.shotId, overlayId: p.overlayId || null }, p.slot, key);
  if (!done) return;                                       // refused (wrong kind) or cancelled: stay in pick mode
  ctx.slotPick = null;
  A.selectItem(p.shotId, p.overlayId || null);
  bus.emit('tab', p.overlayId ? 'overlay' : 'shot');
}
const put = (el, ...kids) => { for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) el.append(k.nodeType ? k : document.createTextNode(String(k))); return el; };

/** Open the pictures tab on one asset (an issue about that picture leads here). */
export function selectAsset(key) { selKey = key; }

export function renderMedia(body) {
  const d = ctx.store.draft;
  if (selKey && !d.assets[selKey]) selKey = null;
  const root = h('div');
  const p = ctx.slotPick;
  // while a slot is being picked, only assets of that slot's kind are offered
  const slotSpec = p && ctx.tech((p.overlayId ? ctx.store.shotById(p.shotId)?.overlays?.find((o) => o.id === p.overlayId) : ctx.store.shotById(p.shotId))?.technique)?.slots.find((x) => x.name === p.slot);
  const entries = Object.entries(d.assets).filter(([, a]) => !slotSpec || fits(slotSpec, a));
  if (!selKey || (slotSpec && !entries.some(([k]) => k === selKey))) selKey = entries[0]?.[0] || null;
  if (p) {
    const kindName = KIND_VI[p.kind] || p.kind;
    put(root, h('div', { class: 'banner' }, h('div', { class: 'grow', text: `Chọn ${kindName} cho slot "${p.slot}" (${p.shotId}${p.overlayId ? '/' + p.overlayId : ''}): bấm vào một hình bên dưới. Chỉ hiện hình loại ${kindName}.` }),
      h('button', { class: 'small', text: 'Hủy', onclick: () => { ctx.slotPick = null; bus.emit('tab', p.overlayId ? 'overlay' : 'shot'); } })));
  }
  // assets
  put(root, h('div', { class: 'sect' }, h('h4', null, p ? `Hình loại ${KIND_VI[p.kind] || p.kind} (${entries.length})` : `Hình của dự án (${Object.keys(d.assets).length})`),
    entries.length ? h('div', { class: 'media-cols' }, ...entries.map(([k, a]) => h('div', { class: 'asset-card' + (k === selKey ? ' sel' : ''), title: `${a.title || ''}\n${a.credit?.licence || ''}${a.credit?.flag ? '\n' + flagLabel(a.credit.flag) : ''}`,
      onclick: () => { if (ctx.slotPick) assign(k); else { selKey = k; bus.emit('assets'); } } },
      h('img', { src: assetThumbUrl(k, api), alt: k }), h('div', { class: 't', text: `${k}: ${a.title || a.file}` }), a.credit?.flag ? h('span', { class: 'chip missing', title: FLAG_HELP[a.credit.flag] || '', text: flagLabel(a.credit.flag) }) : null)))
      : h('div', { class: 'empty', text: p ? `Dự án chưa có hình loại ${KIND_VI[p.kind] || p.kind}. Nhập hoặc tải lên bên dưới.` : 'Dự án chưa có hình nào.' })));
  if (selKey && !p) put(root, assetDetail(selKey, d.assets[selKey]));
  put(root, searchSection(), uploadSection());
  body.append(root);
}

function assetDetail(key, a) {
  const c = a.credit || {};
  const wrap = h('div', { class: 'sect' }, h('h4', null, `Hình ${key}`));
  put(wrap, h('div', { class: 'hint', text: `${a.width || '?'} x ${a.height || '?'} px | ${a.kind} | ${a.file}` }),
    h('div', { class: 'hint', text: `Nguồn: ${c.source || '?'} | Tác giả: ${c.author || '?'} | Giấy phép: ${c.licence || '?'}` }),
    c.source_url ? h('a', { href: c.source_url, target: '_blank', rel: 'noopener', style: { color: 'var(--accent)', fontSize: '11px' }, text: c.source_url }) : null,
    c.flag ? h('div', { class: 'hint warn', text: `${flagLabel(c.flag)}: ${FLAG_HELP[c.flag] || ''}` }) : null);
  if (a.width && a.height && a.kind !== 'video') put(wrap, regionManager(key, a));
  return wrap;
}

/** Regions are part of the storyboard draft: every change below goes through the store (undo, redo, the unsaved marker) and
 * reaches the disk only with "Lưu". The page never calls the server's regions endpoint. */
function regionManager(key, a) {
  const W = 390, H = Math.round((W * a.height) / a.width);
  const stageH = Math.min(H, 300), Wf = Math.min(W, Math.round((stageH * a.width) / a.height));
  const stage = h('div', { class: 'regions-stage', style: { width: Wf + 'px', height: stageH + 'px', margin: '8px 0' } });
  const cv = h('canvas', { width: Wf, height: stageH }), sv = svg('svg', { viewBox: `0 0 ${Wf} ${stageH}` });
  stage.append(cv, sv);
  // this stage maps an asset onto itself (source <-> stage px); the only mapping in the editor that is not a camera, so it lives here
  const view = { W: Wf, H: stageH }, k = Math.min(Wf / a.width, stageH / a.height);
  const S = makeSpaces({ canvas: { w: Wf / k, h: stageH / k }, view, cam: { cx: a.width / 2, cy: a.height / 2, zoom: 1 } });
  const ctx2 = cv.getContext('2d');
  const regions = () => ctx.store.draft.assets[key]?.regions || {};
  let selR = null, arm = false;
  const nameIn = h('input', { type: 'text', placeholder: 'Tên vùng (vd. MIRROR)', value: state.armName, oninput: (e) => { state.armName = e.target.value; } });
  const list = h('div', { class: 'list', style: { marginTop: '8px' } });
  const armBtn = h('button', { class: 'small primary', text: 'Vẽ vùng mới', onclick: () => { arm = !arm; armBtn.textContent = arm ? 'Kéo trên ảnh...' : 'Vẽ vùng mới'; stage.style.cursor = arm ? 'crosshair' : ''; } });

  const paintBase = () => {
    if (MOCK) { ctx2.fillStyle = '#000'; ctx2.fillRect(0, 0, Wf, stageH); paintAsset(ctx2, key, { ...a, regions: {} }, { cx: a.width / 2, cy: a.height / 2, zoom: k }, { w: Wf, h: stageH }, Wf, stageH); return; }
    const img = new Image(); img.onload = () => { ctx2.fillStyle = '#000'; ctx2.fillRect(0, 0, Wf, stageH); const [x0, y0] = S.sourceToScreen(0, 0); ctx2.drawImage(img, x0, y0, a.width * k, a.height * k); };
    img.src = api.fileUrl(ctx.pid, a.file);
  };
  const usageText = (u) => [...new Set(u.map((x) => x.where))].join(', ');
  const askDelete = async (n) => {
    const res = A.deleteRegion(key, n);
    if (res.ok) { if (selR === n) selR = null; return; }
    const first = res.usage[0];
    const choice = await ask({ title: `Không xóa được vùng ${n}`, cancelValue: 'close',
      message: `Vùng ${n} đang được dùng bởi: ${usageText(res.usage)}. Bỏ tham chiếu ở các mục đó (hoặc đổi sang vùng khác) rồi xóa lại.`,
      buttons: [{ text: 'Đóng', value: 'close' }, { text: `Tới ${first.where}`, value: 'go', cls: 'primary' }] });
    if (choice === 'go') { A.selectItem(first.shotId, first.overlayId); bus.emit('tab', first.overlayId ? 'overlay' : 'shot'); }
  };
  const askRename = async (n) => {
    const inp = h('input', { type: 'text', value: n, style: { width: '100%', marginTop: '8px' } });
    const submit = () => document.querySelector('.modal.ask footer button:last-child')?.click();
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') submit(); });
    scopeTimeout(() => { inp.focus(); inp.select(); }, 30);
    const ok = await ask({ title: `Đổi tên vùng ${n}`, cancelValue: false, body: inp, buttons: [{ text: 'Hủy', value: false }, { text: 'Đổi tên', value: true, cls: 'primary' }] });
    const nn = inp.value.trim();
    if (!ok || !nn || nn === n) return;
    if (regions()[nn]) { toast(`Đã có vùng tên ${nn}.`, 'warn'); return; }
    const usage = A.regionUse(key, n);
    let update = true;
    if (usage.length) {
      const c = await ask({ title: 'Vùng đang được dùng', cancelValue: 'cancel',
        message: `${usage.length} tham chiếu tới ${n} ở: ${usageText(usage)}. Cập nhật chúng sang tên mới?`,
        buttons: [{ text: 'Hủy', value: 'cancel' }, { text: 'Đổi tên, giữ tham chiếu cũ (sẽ báo lỗi)', value: 'keep' }, { text: `Đổi tên và cập nhật ${usage.length} tham chiếu`, value: 'update', cls: 'primary' }] });
      if (c === 'cancel') return;
      update = c === 'update';
    }
    A.renameRegion(key, n, nn, update);
    selR = nn;
  };
  const redraw = () => {
    sv.replaceChildren();
    const regs = regions();
    if (selR && !regs[selR]) selR = null;
    for (const [n, r] of Object.entries(regs)) {
      const [sx, sy] = S.sourceToScreen(r.x, r.y);
      const rrx = r.rx ?? 60, rry = r.ry ?? 60;
      const e = svg('ellipse', { cx: sx, cy: sy, rx: rrx * k, ry: rry * k, class: 'rell' + (n === selR ? ' sel' : '') });
      e.style.cursor = 'move'; e.dataset.region = n;
      const t = svg('text', { x: sx + 4, y: sy - rry * k - 3 }); t.textContent = n;
      sv.append(e, t);
      if (n === selR) { const kn = svg('circle', { cx: sx + rrx * k, cy: sy + rry * k, r: 5, class: 'rknob' }); kn.dataset.knob = n; sv.append(kn); }
    }
    list.replaceChildren(...Object.entries(regs).map(([n, r]) => h('div', { class: 'list-item' + (n === selR ? ' sel' : ''), onclick: () => { selR = n; redraw(); } },
      h('b', { text: n }), h('span', { class: 'muted', text: `${Math.round(r.x)}, ${Math.round(r.y)}` + (r.rx != null ? `  r ${Math.round(r.rx)} x ${Math.round(r.ry ?? r.rx)}` : '') }),
      h('input', { type: 'text', value: r.label || '', placeholder: 'nhãn', style: { flex: 1, minWidth: 0 }, onclick: (e) => e.stopPropagation(), onchange: (e) => { A.patchRegion(key, n, { label: e.target.value }); } }),
      h('button', { class: 'small', text: 'Đổi tên', onclick: (e) => { e.stopPropagation(); askRename(n); } }),
      h('button', { class: 'small danger', text: 'Xóa', onclick: (e) => { e.stopPropagation(); askDelete(n); } }))));
    if (!Object.keys(regs).length) list.append(h('div', { class: 'hint', text: 'Chưa có vùng nào. Bấm "Vẽ vùng mới" rồi kéo trên ảnh.' }));
  };
  // draw a new region, or move / resize the selected one: all of it edits the draft
  let st = null;
  const local = (e) => { const r = sv.getBoundingClientRect(); return [((e.clientX - r.left) * Wf) / r.width, ((e.clientY - r.top) * stageH) / r.height]; };
  sv.addEventListener('pointerdown', (e) => {
    const [x, y] = local(e);
    if (arm) { st = { mode: 'new', x, y }; sv.setPointerCapture(e.pointerId); st.el = svg('ellipse', { class: 'rell sel' }); sv.append(st.el); return; }
    const knob = e.target.dataset?.knob, name = e.target.dataset?.region;
    if (knob && regions()[knob]) { const r = regions()[knob]; st = { mode: 'size', name: knob, x, y, rx: r.rx ?? 60, ry: r.ry ?? 60 }; sv.setPointerCapture(e.pointerId); e.preventDefault(); return; }
    if (name && regions()[name]) { const r = regions()[name]; selR = name; st = { mode: 'move', name, x, y, r0: [r.x, r.y], moved: false }; sv.setPointerCapture(e.pointerId); e.preventDefault(); redraw(); return; }
    selR = null; redraw();
  });
  sv.addEventListener('pointermove', (e) => {
    if (!st) return;
    const [x, y] = local(e);
    if (st.mode === 'new') { st.cur = [x, y]; st.el.setAttribute('cx', (st.x + x) / 2); st.el.setAttribute('cy', (st.y + y) / 2); st.el.setAttribute('rx', Math.abs(x - st.x) / 2); st.el.setAttribute('ry', Math.abs(y - st.y) / 2); }
    else if (st.mode === 'move') { A.patchRegion(key, st.name, { x: Math.round(st.r0[0] + (x - st.x) / k), y: Math.round(st.r0[1] + (y - st.y) / k) }, 'rmove'); }
    else if (st.mode === 'size') { A.patchRegion(key, st.name, { rx: Math.max(5, Math.round(st.rx + (x - st.x) / k)), ry: Math.max(5, Math.round(st.ry + (y - st.y) / k)) }, 'rsize'); }
  });
  const finish = () => {
    if (!st) return; const s0 = st; st = null;
    if (s0.mode !== 'new') { redraw(); return; }
    arm = false; armBtn.textContent = 'Vẽ vùng mới'; stage.style.cursor = '';
    if (!s0.cur || Math.abs(s0.cur[0] - s0.x) < 4) { redraw(); return; }
    const [ax, ay] = S.screenToSource(s0.x, s0.y), [bx, by] = S.screenToSource(...s0.cur);
    const regs = regions();
    let name = (state.armName || '').trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_') || 'R' + (Object.keys(regs).length + 1);
    while (regs[name]) name += '_2';
    state.armName = ''; nameIn.value = ''; selR = name;
    A.addRegion(key, name, { x: Math.round((ax + bx) / 2), y: Math.round((ay + by) / 2), rx: Math.round(Math.abs(bx - ax) / 2), ry: Math.round(Math.abs(by - ay) / 2), label: name });
  };
  sv.addEventListener('pointerup', finish); sv.addEventListener('pointercancel', finish);
  // follow the draft (undo, redo, edits from elsewhere) without rebuilding the stage, so a drag in progress is never interrupted
  const unsub = ctx.store.on(() => { if (!stage.isConnected) { unsub(); return; } if (!st) redraw(); });
  paintBase(); redraw();
  return h('div', null, h('h4', { style: { margin: '10px 0 0', fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.06em' }, text: 'Quản lý vùng (region)' }),
    h('div', { class: 'row', style: { marginTop: '6px' } }, nameIn, armBtn), stage, list, h('div', { class: 'hint', text: 'Vùng nằm trong bản nháp: Hoàn tác được, chỉ ghi lên đĩa khi bấm Lưu.' }));
}
const scopeTimeout = (fn, ms) => setTimeout(fn, ms);

function licChip(c) {
  // advisory: the flag is information, an image is never refused for it
  const tip = [c.licence_reason ? licenceText(c.licence_reason).text : '', FLAG_HELP[c.flag] || ''].filter(Boolean).join(' ');
  return h('span', { class: 'chip ' + (c.licence_ok && !c.flag ? 'ok' : 'missing'), title: tip, text: `${c.licence || 'không rõ'}${c.flag ? ` (${flagLabel(c.flag)})` : ''}` });
}

function searchSection() {
  const out = h('div');
  const q = h('input', { type: 'text', placeholder: 'Tìm hình, vd. Arnolfini mirror', value: state.q, style: { flex: 1 } });
  const src = h('select', null, ...SOURCES.map(([v, l]) => h('option', { value: v, text: l, selected: v === state.source })));
  const kind = h('select', null, ...[['image', 'Ảnh'], ['video', 'Video']].map(([v, l]) => h('option', { value: v, text: l, selected: v === state.kind })));
  const go = async () => {
    state.q = q.value; state.source = src.value; state.kind = kind.value;
    out.replaceChildren(h('div', { class: 'hint', text: 'Đang tìm...' }));
    try { state.results = await api.search(state.q, state.source, state.kind, 24); } catch (e) { state.results = []; errorToast(e, 'Tìm thất bại: '); }
    paint();
  };
  const paint = () => {
    out.replaceChildren();
    if (state.results === null) return;
    if (!state.results.length) out.append(h('div', { class: 'empty', text: 'Không có kết quả.' }));
    for (const c of state.results) {
      const imp = h('button', { class: 'small primary', text: 'Nhập', title: c.flag ? `Nhập được; ${flagLabel(c.flag)}. Nguồn và giấy phép được ghi lại.` : 'Tải về dự án', onclick: async () => {
        imp.disabled = true; imp.textContent = '...';
        try {
          const r = await api.importAsset(ctx.pid, c.source, c.source_id);
          addAsset(r.asset_key, r.asset, c.thumb_url); toast(`Đã nhập ${r.asset_key}`, 'ok');
          if (ctx.slotPick) await assign(r.asset_key); else { selKey = r.asset_key; bus.emit('assets'); }
        } catch (e) { errorToast(e, 'Nhập thất bại: ', 6000); imp.disabled = false; imp.textContent = 'Nhập'; }
      } });
      out.append(h('div', { class: 'cand' }, h('img', { src: api.url(c.thumb_url), alt: '' }), h('div', { class: 'info' },
        h('div', { class: 't', title: c.title, text: c.title }), h('div', { class: 'hint', text: `${c.author || '?'} | ${c.width || '?'}x${c.height || '?'} | ${c.mime || ''}` }),
        h('div', { style: { display: 'flex', gap: '6px', alignItems: 'center', marginTop: '3px' } }, licChip(c), c.page_url ? h('a', { href: c.page_url, target: '_blank', rel: 'noopener', style: { color: 'var(--accent)', fontSize: '11px' }, text: 'trang gốc' }) : null),
        c.flag ? h('div', { class: 'hint', text: FLAG_HELP[c.flag] || '' }) : null), imp));
    }
  };
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  const sec = h('div', { class: 'sect' }, h('h4', null, 'Tìm hình (nguồn và giấy phép được ghi lại; hình có hạn chế chỉ bị gắn cờ, không bị chặn)'), h('div', { class: 'row' }, q, h('button', { class: 'primary small', text: 'Tìm', onclick: go })),
    h('div', { class: 'row' }, src, kind), out);
  paint();
  return sec;
}

function uploadSection() {
  const f = {};
  const inp = (k, label, extra = {}) => { f[k] = h('input', { type: 'text', ...extra }); return h('div', null, h('label', { text: label }), f[k]); };
  f.file = h('input', { type: 'file', accept: 'image/*,video/*' });
  f.licence = h('select', null, h('option', { value: '', text: 'Chưa rõ' }), ...['PD', 'CC0', 'CC BY', 'CC BY-SA'].map((l) => h('option', { value: l, text: l })));
  const msg = h('div', { class: 'hint' });
  const form = h('div', { class: 'form-grid' },
    h('div', { class: 'full' }, h('label', { text: 'Tệp' }), f.file), inp('title', 'Tiêu đề'), inp('artist', 'Họa sĩ'), inp('year', 'Năm'), h('div', null, h('label', { text: 'Giấy phép' }), f.licence),
    h('div', { class: 'full' }, inp('source_url', 'Địa chỉ trang nguồn (không bắt buộc)', { placeholder: 'https://...' })), h('div', { class: 'full' }, inp('author', 'Tác giả (không bắt buộc)')),
    h('div', { class: 'full' }, h('button', { class: 'primary', text: 'Tải lên', onclick: async () => {
      if (!f.file.files[0]) return (msg.textContent = 'Chọn tệp trước.');
      const fd = new FormData(); fd.append('file', f.file.files[0]);
      for (const k of ['title', 'artist', 'year', 'licence', 'source_url', 'author']) fd.append(k, f[k].value);
      msg.textContent = 'Đang tải...';
      try { const r = await api.upload(ctx.pid, fd); addAsset(r.asset_key, r.asset); msg.textContent = ''; toast('Đã tải lên ' + r.asset_key, 'ok'); selKey = r.asset_key; bus.emit('assets'); }
      catch (e) { errorInto(msg, e, 'Không tải lên được: '); }
    } }), msg));
  return h('div', { class: 'sect' }, h('h4', null, 'Tải lên hình của bạn'), form);
}
