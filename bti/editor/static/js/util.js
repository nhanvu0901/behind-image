export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'text') el.textContent = v;
    else if (k in el && k !== 'list' && k !== 'type' && k !== 'for') { try { el[k] = v; } catch { el.setAttribute(k, v); } }
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c !== null && c !== undefined && c !== false) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
export const svg = (tag, attrs) => {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
};
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function toast(msg, kind = '', ms = 4200) {
  const t = h('div', { class: 'toast ' + kind, text: msg });
  document.getElementById('toast-root').append(t);
  setTimeout(() => t.remove(), ms);
}

export function modal({ title, body, footer, cls = '', onClose, headerExtra }) {
  const root = document.getElementById('modal-root');
  const close = () => { back.remove(); document.removeEventListener('keydown', esc, true); onClose?.(); };
  const esc = (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } };
  const m = h('div', { class: 'modal ' + cls },
    h('header', null, h('h3', { text: title }), h('span', { class: 'grow', style: { flex: 1 } }), headerExtra, h('button', { class: 'small', onclick: close, text: 'Đóng' })),
    body,
    footer || null);
  const back = h('div', { class: 'backdrop', onmousedown: (e) => { if (e.target === back) close(); } }, m);
  document.addEventListener('keydown', esc, true);
  root.append(back);
  return { close, el: m };
}

export const fmtTime = (t) => {
  if (!isFinite(t)) return '0:00.00';
  const m = Math.floor(t / 60), s = t - m * 60;
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(2)}`;
};
export const debounce = (fn, ms) => { let id; const d = (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); }; d.cancel = () => clearTimeout(id); return d; };
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
