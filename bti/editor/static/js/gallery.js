// Technique gallery modal: all registry entries, grouped by kind then category.
import { h, modal, debounce } from './util.js';
import { ctx } from './ctx.js';
import { PREVIEW_BASE } from './config.js';

export const KIND_VI = { base: 'Cảnh nền (base)', overlay: 'Lớp phủ (overlay)', transition: 'Chuyển cảnh (transition)', card: 'Thẻ chữ (card)' };
const KIND_ORDER = ['base', 'overlay', 'transition', 'card'];
export const USAGE_VI = { core: 'Cốt lõi', occasional: 'Thỉnh thoảng', rare: 'Hiếm', other_series: 'Series khác', shorts_only: 'Chỉ Shorts' };
export const CATEGORY_VI = { camera: 'Máy quay', layout: 'Bố cục', highlight: 'Làm nổi bật', annotation: 'Chú thích', card: 'Thẻ', text: 'Chữ', static: 'Tĩnh', diagram: 'Sơ đồ', compare: 'So sánh', footage: 'Cảnh quay', shorts: 'Shorts', transition: 'Chuyển cảnh' };

export const previewUrl = (t, which = 'clip') => {
  const f = t.preview?.[which];
  return f ? PREVIEW_BASE + f.split('/').pop() : '';
};
export const isAvailable = (t) => t.engine?.available === true;
export const unavailableReason = (t) => t.engine?.reason || t.engine?.notes || (t.engine?.available === undefined ? 'Engine chưa khai báo hỗ trợ kỹ thuật này' : 'Engine chưa render được kỹ thuật này');

export function usageChip(t) { return h('span', { class: 'chip ' + t.channel_usage, title: 'Mức dùng ở kênh gốc', text: USAGE_VI[t.channel_usage] || t.channel_usage }); }
export function engineChip(t) {
  if (!isAvailable(t)) return h('span', { class: 'chip missing', title: unavailableReason(t), text: 'Engine: chưa có' });
  const st = t.engine?.status;
  return h('span', { class: 'chip ' + (st === 'partial' ? 'partial' : 'ok'), title: t.engine?.impl || '', text: st === 'partial' ? 'Engine: một phần' : 'Engine: sẵn sàng' });
}

/** opts: {title, kinds:[allowed kinds], current, onPick(id)} */
export function openGallery({ title = 'Thư viện kỹ thuật', kinds = KIND_ORDER, current = null, onPick, q = '' }) {
  const st = { q, kind: kinds.length === 1 ? kinds[0] : 'all', intent: '', onlyOk: false };
  const grid = h('div', { class: 'body' });
  const count = h('span', { class: 'muted' });
  const search = h('input', { type: 'search', value: q, placeholder: 'Tìm theo tên, mã, mô tả...', oninput: debounce((e) => { st.q = e.target.value.toLowerCase(); render(); }, 120) });
  const intentSel = h('select', { onchange: (e) => { st.intent = e.target.value; render(); } }, h('option', { value: '', text: 'Mọi ý đồ (intent)' }), ...ctx.reg.intents.map((i) => h('option', { value: i, text: i })));
  const only = h('input', { type: 'checkbox', onchange: (e) => { st.onlyOk = e.target.checked; render(); } });
  const pills = {};
  const pillBar = h('div', { style: { display: 'flex', gap: '6px' } }, ...['all', ...KIND_ORDER].map((k) => (pills[k] = h('button', { class: 'pillbtn', text: k === 'all' ? 'Tất cả' : KIND_VI[k].split(' (')[0], onclick: () => { st.kind = k; render(); } }))));
  const filters = h('div', { class: 'gal-filters' }, search, pillBar, intentSel, h('label', { class: 'chk' }, only, 'Chỉ mục dùng được'), h('span', { class: 'grow', style: { flex: 1 } }), count);
  const body = h('div', { style: { display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 } }, filters, grid);

  function card(t) {
    const ok = isAvailable(t), allowed = kinds.includes(t.kind), pickable = ok && allowed;
    const pv = h('div', { class: 'pv' }, h('img', { src: previewUrl(t, 'thumb'), loading: 'lazy', alt: '', onerror: (e) => { e.target.remove(); pv.prepend(h('div', { class: 'nopv', text: 'chưa có clip xem trước' })); } }), h('span', { class: 'tid', text: t.id }));
    let vid = null;
    const c = h('div', { class: 'gcard' + (pickable ? '' : ' off') + (t.id === current ? ' cur' : ''), title: pickable ? 'Chọn kỹ thuật này' : (!ok ? unavailableReason(t) : `Loại ${t.kind} không dùng được ở vị trí này`),
      onmouseenter: () => { if (!previewUrl(t)) return; vid = h('video', { src: previewUrl(t), muted: true, loop: true, playsinline: true, autoplay: true }); pv.append(vid); vid.play().catch(() => {}); },
      onmouseleave: () => { vid?.pause(); vid?.remove(); vid = null; },
      onclick: () => { if (!pickable) return; dlg.close(); onPick?.(t.id); } },
      pv,
      h('div', { class: 'meta' },
        h('div', { class: 'vi', text: t.label_vi }), h('div', { class: 'en', text: t.name }),
        h('div', { class: 'chips' }, usageChip(t), engineChip(t), ...t.intents.map((i) => h('span', { class: 'chip', text: i }))),
        !ok ? h('div', { class: 'why', text: unavailableReason(t) }) : (!allowed ? h('div', { class: 'why', text: `Loại ${t.kind}: không dùng cho vị trí này` }) : h('div', { class: 'desc', text: t.description }))));
    return c;
  }

  function render() {
    for (const [k, b] of Object.entries(pills)) b.classList.toggle('on', st.kind === k);
    const list = ctx.reg.list.filter((t) => (st.kind === 'all' || t.kind === st.kind) && (!st.intent || t.intents.includes(st.intent)) && (!st.onlyOk || isAvailable(t)) &&
      (!st.q || [t.id, t.name, t.label_vi, t.description, t.category].join(' ').toLowerCase().includes(st.q)));
    grid.replaceChildren();
    count.textContent = `${list.length} / ${ctx.reg.list.length} kỹ thuật`;
    if (!list.length) grid.append(h('div', { class: 'empty', text: 'Không có kỹ thuật khớp bộ lọc.' }));
    for (const kind of KIND_ORDER) {
      const ofKind = list.filter((t) => t.kind === kind);
      if (!ofKind.length) continue;
      const cats = [...new Set(ofKind.map((t) => t.category))];
      for (const cat of cats) {
        const items = ofKind.filter((t) => t.category === cat);
        grid.append(h('div', { class: 'gal-group' }, h('h4', null, h('b', { text: KIND_VI[kind] }), ' / ', CATEGORY_VI[cat] || cat, ` (${items.length})`), h('div', { class: 'gal-grid' }, items.map(card))));
      }
    }
  }
  grid.style.flex = '1';
  const dlg = modal({ title, body, cls: 'gallery' });
  render();
  search.focus();
  return dlg;
}
