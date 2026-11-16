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

// ---------------------------------------------------------------- messages and dialogs: the ONE system of the app
export function toast(msg, kind = '', ms = 4200) {
  const root = document.getElementById('toast-root');
  if (!root) return;
  const t = h('div', { class: 'toast ' + kind, text: msg });
  root.append(t);
  setTimeout(() => t.remove(), ms);
}

/** The status line of the app frame ("đang lưu...", "đang mở dự án..."). */
export function setStatus(text = '') {
  const el = document.getElementById('frame-status');
  if (el) el.textContent = text;
}

const openModals = new Set();
export function modal({ title, body, footer, cls = '', onClose, headerExtra }) {
  const root = document.getElementById('modal-root');
  const close = () => {
    if (!openModals.has(handle)) return;
    openModals.delete(handle);
    back.remove(); document.removeEventListener('keydown', esc, true); onClose?.();
  };
  const esc = (e) => { if (e.key === 'Escape' && [...openModals].pop() === handle) { e.stopPropagation(); close(); } };   // Esc closes only the dialog on top
  const m = h('div', { class: 'modal ' + cls },
    h('header', null, h('h3', { text: title }), h('span', { class: 'grow', style: { flex: 1 } }), headerExtra, h('button', { class: 'small', onclick: close, text: 'Đóng' })),
    body,
    footer || null);
  const back = h('div', { class: 'backdrop', onmousedown: (e) => { if (e.target === back) close(); } }, m);
  const handle = { close, el: m };
  openModals.add(handle);
  document.addEventListener('keydown', esc, true);
  root.append(back);
  return handle;
}
/** Close every open dialog (the shell calls this when a view is left). */
export function closeAllModals() { for (const m of [...openModals]) m.close(); }

/** Ask the owner to choose. buttons: [{ text, value, cls }]; Esc and the close button answer `cancelValue`. */
export function ask({ title, message, buttons, cancelValue = null, body }) {
  return new Promise((resolve) => {
    let done = false;
    const fin = (v) => { if (!done) { done = true; resolve(v); } };
    const m = modal({ title, cls: 'ask', onClose: () => fin(cancelValue),
      body: h('div', { class: 'body' }, message ? h('div', { class: 'confirm-msg', text: message }) : null, body || null),
      footer: h('footer', null, buttons.map((b) => h('button', { class: b.cls || '', text: b.text, onclick: () => { fin(b.value); m.close(); } }))) });
    m.el.querySelector('footer button:last-child')?.focus();
  });
}
/** Yes/no dialog in the app (never the browser's confirm()). Resolves true or false. */
export const confirmDialog = (message, { title = 'Xác nhận', ok = 'Đồng ý', cancel = 'Hủy', danger = false } = {}) =>
  ask({ title, message, cancelValue: false, buttons: [{ text: cancel, value: false }, { text: ok, value: true, cls: danger ? 'danger' : 'primary' }] });

export const fmtTime = (t) => {
  if (!isFinite(t)) return '0:00.00';
  const m = Math.floor(t / 60), s = t - m * 60;
  return `${m}:${s < 10 ? '0' : ''}${s.toFixed(2)}`;
};
export const debounce = (fn, ms) => { let id; const d = (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); }; d.cancel = () => clearTimeout(id); return d; };
export const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
