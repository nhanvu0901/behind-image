// "Hình" tab: assets, region manager, licence-aware search, import and upload.
import { h, svg, toast } from './util.js';
import { ctx, bus, assetThumbUrl } from './ctx.js';
import { api } from './api.js';
import { clone, makeMapping, fitCamera, round } from './logic.js';
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
function assign(key) {
  const p = ctx.slotPick; if (!p) return;
  const ak = ctx.store.draft.assets[key]?.kind || 'image';
  if ((p.kind === 'video') !== (ak === 'video')) { toast(p.kind === 'video' ? 'Slot này cần video.' : 'Slot này cần ảnh, không phải video.', 'warn'); return; }
  ctx.slotPick = null;
  A.commitShot('Chọn hình cho slot ' + p.slot, p.shotId, (s) => { (s.slots ||= {})[p.slot] = { asset: key }; });
  ctx.store.select(p.shotId);
  A.refitCamera(p.shotId);
  bus.emit('tab', 'shot');
}

export function renderMedia(body) {
  const d = ctx.store.draft;
  if (selKey && !d.assets[selKey]) selKey = null;
  selKey ||= Object.keys(d.assets)[0] || null;
  const root = h('div');
  if (ctx.slotPick) {
    root.append(h('div', { class: 'banner' }, h('div', { class: 'grow', text: `Chọn hình cho slot "${ctx.slotPick.slot}" (${ctx.slotPick.shotId}): bấm vào một hình bên dưới.` }),
      h('button', { class: 'small', text: 'Hủy', onclick: () => { ctx.slotPick = null; bus.emit('tab', 'shot'); } })));
  }
  // assets
  root.append(h('div', { class: 'sect' }, h('h4', null, `Hình của dự án (${Object.keys(d.assets).length})`),
    h('div', { class: 'media-cols' }, ...Object.entries(d.assets).map(([k, a]) => h('div', { class: 'asset-card' + (k === selKey ? ' sel' : ''), title: `${a.title || ''}\n${a.credit?.licence || ''}`,
      onclick: () => { if (ctx.slotPick) assign(k); else { selKey = k; bus.emit('assets'); } } },
      h('img', { src: assetThumbUrl(k, api), alt: k }), h('div', { class: 't', text: `${k}: ${a.title || a.file}` }))))));
  if (selKey) root.append(assetDetail(selKey, d.assets[selKey]));
  root.append(searchSection(), uploadSection());
  body.append(root);
}

function assetDetail(key, a) {
  const c = a.credit || {};
  const wrap = h('div', { class: 'sect' }, h('h4', null, `Hình ${key}`));
  wrap.append(h('div', { class: 'hint', text: `${a.width || '?'} x ${a.height || '?'} px | ${a.kind} | ${a.file}` }),
    h('div', { class: 'hint', text: `Nguồn: ${c.source || '?'} | Tác giả: ${c.author || '?'} | Giấy phép: ${c.licence || '?'}` }),
    c.source_url ? h('a', { href: c.source_url, target: '_blank', rel: 'noopener', style: { color: 'var(--accent)', fontSize: '11px' }, text: c.source_url }) : null);
  if (a.width && a.height && a.kind !== 'video') wrap.append(regionManager(key, a));
  return wrap;
}

function regionManager(key, a) {
  const W = 390, H = Math.round((W * a.height) / a.width);
  const stageH = Math.min(H, 300), Wf = Math.min(W, Math.round((stageH * a.width) / a.height));
  const stage = h('div', { class: 'regions-stage', style: { width: Wf + 'px', height: stageH + 'px', margin: '8px 0' } });
  const cv = h('canvas', { width: Wf, height: stageH }), sv = svg('svg', { viewBox: `0 0 ${Wf} ${stageH}` });
  stage.append(cv, sv);
  const canvas = { w: a.width, h: a.height };
  // screen px per source px
  const k = Math.min(Wf / a.width, stageH / a.height);
  const map = { toScreen: (x, y) => [(x - a.width / 2) * k + Wf / 2, (y - a.height / 2) * k + stageH / 2], toSource: (sx, sy) => [(sx - Wf / 2) / k + a.width / 2, (sy - stageH / 2) / k + a.height / 2] };
  const ctx2 = cv.getContext('2d');
  const regions = clone(a.regions || {});
  let selR = null, arm = false;
  const nameIn = h('input', { type: 'text', placeholder: 'Tên vùng (vd. MIRROR)', value: state.armName, oninput: (e) => { state.armName = e.target.value; } });
  const list = h('div', { class: 'list', style: { marginTop: '8px' } });
  const armBtn = h('button', { class: 'small primary', text: 'Vẽ vùng mới', onclick: () => { arm = !arm; armBtn.textContent = arm ? 'Kéo trên ảnh...' : 'Vẽ vùng mới'; stage.style.cursor = arm ? 'crosshair' : ''; } });

  const paintBase = () => {
    if (MOCK) { ctx2.fillStyle = '#000'; ctx2.fillRect(0, 0, Wf, stageH); paintAsset(ctx2, key, { ...a, regions: {} }, { cx: a.width / 2, cy: a.height / 2, zoom: k }, { w: Wf, h: stageH }, Wf, stageH); return; }
    const img = new Image(); img.onload = () => { ctx2.fillStyle = '#000'; ctx2.fillRect(0, 0, Wf, stageH); const [x0, y0] = map.toScreen(0, 0); ctx2.drawImage(img, x0, y0, a.width * k, a.height * k); };
    img.src = api.fileUrl(ctx.pid, a.file);
  };
  const redraw = () => {
    sv.replaceChildren();
    for (const [n, r] of Object.entries(regions)) {
      const [sx, sy] = map.toScreen(r.x, r.y);
      const rrx = r.rx ?? 60, rry = r.ry ?? 60;
      const e = svg('ellipse', { cx: sx, cy: sy, rx: rrx * k, ry: rry * k, class: 'rell' + (n === selR ? ' sel' : '') });
      e.style.cursor = 'pointer'; e.addEventListener('pointerdown', (ev) => { if (arm) return; ev.stopPropagation(); selR = n; redraw(); });
      const t = svg('text', { x: sx + 4, y: sy - rry * k - 3 }); t.textContent = n;
      sv.append(e, t);
    }
    list.replaceChildren(...Object.entries(regions).map(([n, r]) => h('div', { class: 'list-item' + (n === selR ? ' sel' : ''), onclick: () => { selR = n; redraw(); } },
      h('b', { text: n }), h('span', { class: 'muted', text: `${Math.round(r.x)}, ${Math.round(r.y)}` + (r.rx != null ? `  r ${Math.round(r.rx)} x ${Math.round(r.ry ?? r.rx)}` : '') }),
      h('input', { type: 'text', value: r.label || '', placeholder: 'nhãn', style: { flex: 1, minWidth: 0 }, onclick: (e) => e.stopPropagation(), onchange: (e) => { r.label = e.target.value; save(); } }),
      h('button', { class: 'small', text: 'Đổi tên', onclick: (e) => { e.stopPropagation(); const nn = prompt('Tên mới', n); if (nn && nn !== n && !regions[nn]) { regions[nn] = r; delete regions[n]; selR = nn; save(); redraw(); } } }),
      h('button', { class: 'small danger', text: 'Xóa', onclick: (e) => { e.stopPropagation(); delete regions[n]; save(); redraw(); } }))));
    if (!Object.keys(regions).length) list.append(h('div', { class: 'hint', text: 'Chưa có vùng nào. Bấm "Vẽ vùng mới" rồi kéo trên ảnh.' }));
  };
  const save = async () => {
    ctx.store.commit('Đổi vùng ' + key, (d) => { d.assets[key].regions = clone(regions); });
    try { const res = await api.putRegions(ctx.pid, key, regions); if (res?.rev) ctx.store.rev = res.rev; } catch (e) { toast('Không lưu được vùng lên server: ' + (e.status || e.message), 'err'); }
  };
  let st = null;
  sv.addEventListener('pointerdown', (e) => {
    if (!arm) { selR = null; redraw(); return; }
    const r = sv.getBoundingClientRect(); st = { x: e.clientX - r.left, y: e.clientY - r.top }; sv.setPointerCapture(e.pointerId);
    st.el = svg('ellipse', { class: 'rell sel' }); sv.append(st.el);
  });
  sv.addEventListener('pointermove', (e) => {
    if (!st) return; const r = sv.getBoundingClientRect(); const x = e.clientX - r.left, y = e.clientY - r.top;
    st.cur = [x, y]; st.el.setAttribute('cx', (st.x + x) / 2); st.el.setAttribute('cy', (st.y + y) / 2); st.el.setAttribute('rx', Math.abs(x - st.x) / 2); st.el.setAttribute('ry', Math.abs(y - st.y) / 2);
  });
  sv.addEventListener('pointerup', () => {
    if (!st) return; const s0 = st; st = null; arm = false; armBtn.textContent = 'Vẽ vùng mới'; stage.style.cursor = '';
    if (!s0.cur || Math.abs(s0.cur[0] - s0.x) < 4) { redraw(); return; }
    const [ax, ay] = map.toSource(s0.x, s0.y), [bx, by] = map.toSource(...s0.cur);
    let name = (state.armName || '').trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_') || 'R' + (Object.keys(regions).length + 1);
    while (regions[name]) name += '_2';
    regions[name] = { x: Math.round((ax + bx) / 2), y: Math.round((ay + by) / 2), rx: Math.round(Math.abs(bx - ax) / 2), ry: Math.round(Math.abs(by - ay) / 2), label: name };
    state.armName = ''; nameIn.value = ''; selR = name; save(); redraw();
  });
  paintBase(); redraw();
  return h('div', null, h('h4', { style: { margin: '10px 0 0', fontSize: '11px', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.06em' }, text: 'Quản lý vùng (region)' }),
    h('div', { class: 'row', style: { marginTop: '6px' } }, nameIn, armBtn), stage, list);
}

function licChip(c) {
  return h('span', { class: 'chip ' + (c.licence_ok ? 'ok' : 'missing'), title: c.licence_reason || '', text: `${c.licence || 'không rõ'}${c.licence_ok ? '' : ' (bị chặn)'}` });
}

function searchSection() {
  const out = h('div');
  const q = h('input', { type: 'text', placeholder: 'Tìm hình, vd. Arnolfini mirror', value: state.q, style: { flex: 1 } });
  const src = h('select', null, ...SOURCES.map(([v, l]) => h('option', { value: v, text: l, selected: v === state.source })));
  const kind = h('select', null, ...[['image', 'Ảnh'], ['video', 'Video']].map(([v, l]) => h('option', { value: v, text: l, selected: v === state.kind })));
  const go = async () => {
    state.q = q.value; state.source = src.value; state.kind = kind.value;
    out.replaceChildren(h('div', { class: 'hint', text: 'Đang tìm...' }));
    try { state.results = await api.search(state.q, state.source, state.kind, 24); } catch (e) { state.results = []; toast('Tìm thất bại: ' + (e.status || e.message), 'err'); }
    paint();
  };
  const paint = () => {
    out.replaceChildren();
    if (state.results === null) return;
    if (!state.results.length) out.append(h('div', { class: 'empty', text: 'Không có kết quả.' }));
    for (const c of state.results) {
      const imp = h('button', { class: 'small primary', text: 'Nhập', disabled: !c.licence_ok, title: c.licence_ok ? 'Tải về dự án' : (c.licence_reason || 'Giấy phép không được phép'), onclick: async () => {
        imp.disabled = true; imp.textContent = '...';
        try {
          const r = await api.importAsset(ctx.pid, c.source, c.source_id);
          addAsset(r.asset_key, r.asset, c.thumb_url); toast(`Đã nhập ${r.asset_key}`, 'ok');
          if (ctx.slotPick) assign(r.asset_key); else { selKey = r.asset_key; bus.emit('assets'); }
        } catch (e) { const reason = e.body?.detail?.reason || e.body?.reason || (typeof e.body?.detail === 'string' ? e.body.detail : '') || e.message; toast(e.status === 422 ? 'Giấy phép bị từ chối: ' + reason : 'Nhập thất bại: ' + reason, 'err', 6000); imp.disabled = false; imp.textContent = 'Nhập'; }
      } });
      out.append(h('div', { class: 'cand' }, h('img', { src: api.url(c.thumb_url), alt: '' }), h('div', { class: 'info' },
        h('div', { class: 't', title: c.title, text: c.title }), h('div', { class: 'hint', text: `${c.author || '?'} | ${c.width || '?'}x${c.height || '?'} | ${c.mime || ''}` }),
        h('div', { style: { display: 'flex', gap: '6px', alignItems: 'center', marginTop: '3px' } }, licChip(c), c.page_url ? h('a', { href: c.page_url, target: '_blank', rel: 'noopener', style: { color: 'var(--accent)', fontSize: '11px' }, text: 'trang gốc' }) : null),
        !c.licence_ok && c.licence_reason ? h('div', { class: 'hint err', text: c.licence_reason }) : null), imp));
    }
  };
  q.addEventListener('keydown', (e) => { if (e.key === 'Enter') go(); });
  const sec = h('div', { class: 'sect' }, h('h4', null, 'Tìm hình (chỉ giấy phép PD, CC0, CC BY, CC BY-SA)'), h('div', { class: 'row' }, q, h('button', { class: 'primary small', text: 'Tìm', onclick: go })),
    h('div', { class: 'row' }, src, kind), out);
  paint();
  return sec;
}

function uploadSection() {
  const f = {};
  const inp = (k, label, extra = {}) => { f[k] = h('input', { type: 'text', ...extra }); return h('div', null, h('label', { text: label }), f[k]); };
  f.file = h('input', { type: 'file', accept: 'image/*,video/*' });
  f.licence = h('select', null, ...['PD', 'CC0', 'CC BY', 'CC BY-SA'].map((l) => h('option', { value: l, text: l })));
  const msg = h('div', { class: 'hint' });
  const form = h('div', { class: 'form-grid' },
    h('div', { class: 'full' }, h('label', { text: 'Tệp' }), f.file), inp('title', 'Tiêu đề'), inp('artist', 'Họa sĩ'), inp('year', 'Năm'), h('div', null, h('label', { text: 'Giấy phép' }), f.licence),
    h('div', { class: 'full' }, inp('source_url', 'URL nguồn (bắt buộc)', { placeholder: 'https://...' })), h('div', { class: 'full' }, inp('author', 'Tác giả (hoặc "unknown, PD")')),
    h('div', { class: 'full' }, h('button', { class: 'primary', text: 'Tải lên', onclick: async () => {
      if (!f.file.files[0]) return (msg.textContent = 'Chọn tệp trước.');
      if (!f.source_url.value || !f.author.value) return (msg.textContent = 'Cần source_url và author (design 8.2).');
      const fd = new FormData(); fd.append('file', f.file.files[0]);
      for (const k of ['title', 'artist', 'year', 'licence', 'source_url', 'author']) fd.append(k, f[k].value);
      msg.textContent = 'Đang tải...';
      try { const r = await api.upload(ctx.pid, fd); addAsset(r.asset_key, r.asset); msg.textContent = ''; toast('Đã tải lên ' + r.asset_key, 'ok'); selKey = r.asset_key; bus.emit('assets'); }
      catch (e) { msg.textContent = 'Lỗi: ' + (e.body?.detail?.reason || e.body?.detail || e.body?.reason || e.message); }
    } }), msg));
  return h('div', { class: 'sect' }, h('h4', null, 'Tải lên hình của bạn'), form);
}
