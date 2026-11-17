import { describeError } from './errmsg.js';
import { dropdownOptions } from './labels.js';
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
/** The children worth appending: drops null, undefined and false (Element.append would write them as the words "null" and "false").
 * Use it for every conditional child that is not built through h(): `el.append(...kids(a, cond ? b : null))`. */
export const kids = (...c) => c.flat(Infinity).filter((x) => x !== null && x !== undefined && x !== false);
/** Fill a <select> from a list so that it shows the stored value (see `dropdownOptions`). `extra(v)` may add {disabled, text} per entry. Safe to call again on sync. */
export function fillSelect(sel, values, current, labelOf = String, extra = null) {
  const { options, selected } = dropdownOptions(values, current, labelOf);
  sel.replaceChildren(...options.map((o) => { const x = extra && o.state === 'ok' ? extra(o.value) || {} : {}; const el = h('option', { value: o.value, text: x.text || o.text, title: o.title, disabled: o.disabled || x.disabled }); el.dataset.state = o.state; return el; }));
  sel.value = selected;
  return sel;
}
export const svg = (tag, attrs) => {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  return el;
};
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

// ---------------------------------------------------------------- messages and dialogs: the ONE system of the app
/** "chi tiết": a fold-out with the raw text of the server. The raw text is put in the page only when it is opened, so
 *  it is never read out or copied by accident with the message above it. */
export function detailFold(raw, cls = 'err-detail', onToggle) {
  const body = h('div', { class: 'raw' });
  const det = h('details', { class: cls }, h('summary', { text: 'chi tiết' }));
  det.addEventListener('toggle', () => { if (det.open && !body.isConnected) { body.textContent = String(raw); det.append(body); } onToggle?.(det.open); });
  return det;
}
/** A message that fades after `ms`. With `detail` (raw server text) it carries a "chi tiết" fold-out and stays longer;
 *  it does not fade while the pointer is on it or its detail is open. */
export function toast(msg, kind = '', ms = 4200, detail = null) {
  const root = document.getElementById('toast-root');
  if (!root) return;
  if (detail) ms = Math.max(ms, 12000);
  const t = h('div', { class: 'toast ' + kind, role: kind === 'err' ? 'alert' : 'status' }, h('div', { text: msg }));
  let timer = null, held = false;
  const arm = () => { clearTimeout(timer); if (!held) timer = setTimeout(() => t.remove(), ms); };
  if (detail) t.append(detailFold(detail, 'toast-detail', (open) => { held = open; arm(); }));
  t.addEventListener('mouseenter', () => { clearTimeout(timer); });
  t.addEventListener('mouseleave', arm);
  root.append(t); arm();
}
/** A toast for an error (anything thrown): Vietnamese sentence, raw text under "chi tiết". */
export function errorToast(e, prefix = '', ms = 8000) {
  const d = describeError(e);
  toast(prefix + d.text, 'err', ms, d.detail);
}
/** Fill `el` with the Vietnamese message of an error and a "chi tiết" fold-out with the raw text. */
export function errorInto(el, e, prefix = '') {
  const d = describeError(e);
  el.replaceChildren(prefix + d.text, ...(d.detail ? [detailFold(d.detail)] : []));
}

/** The status line of the app frame ("đang lưu...", "đang mở dự án..."). */
export function setStatus(text = '') {
  const el = document.getElementById('frame-status');
  if (el) el.textContent = text;
}

// Dialogs. Every dialog of the app comes from modal(): role="dialog", the page behind is inert, Tab turns round inside
// the dialog, Esc closes the one on top (and is never seen by the page), Enter in a text field presses the primary button.
const stack = [];
const FOCUSABLE = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex]';
const shown = (el) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
/** Elements of `root` the Tab key stops on, in order. */
export const focusablesIn = (root) => [...root.querySelectorAll(FOCUSABLE)].filter((e) => !e.disabled && e.tabIndex >= 0 && !e.closest('[hidden],[inert]') && shown(e));
let modalSeq = 0;

function onModalKey(e) {
  const top = stack[stack.length - 1];
  if (!top || e.isComposing || e.keyCode === 229) return;
  if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); top.close(); return; }
  if (e.key === 'Tab') {
    const list = focusablesIn(top.el), a = document.activeElement;
    if (!list.length) { e.preventDefault(); top.el.focus(); return; }
    const i = list.indexOf(a);
    if (!top.el.contains(a)) { e.preventDefault(); (e.shiftKey ? list[list.length - 1] : list[0]).focus(); }
    else if (e.shiftKey && (i <= 0)) { e.preventDefault(); list[list.length - 1].focus(); }
    else if (!e.shiftKey && i === list.length - 1) { e.preventDefault(); list[0].focus(); }
    return;
  }
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && top.enter && top.el.contains(e.target) && e.target.matches?.('input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=file])')) {
    const b = top.el.querySelector('footer button.primary:not(:disabled)');
    if (b) { e.preventDefault(); e.stopPropagation(); b.click(); }
  }
}
const syncBackground = () => {
  const bg = document.getElementById('shell');
  if (!bg) return;
  if (stack.length) bg.setAttribute('inert', ''); else bg.removeAttribute('inert');
};

/** Open a dialog. `backdrop: false` keeps it open when the backdrop is clicked (dialogs holding typed text). */
export function modal({ title, body, footer, cls = '', onClose, headerExtra, backdrop = true, enter = true }) {
  const root = document.getElementById('modal-root');
  const opener = document.activeElement;
  const close = () => {
    if (!stack.includes(handle)) return;
    stack.splice(stack.indexOf(handle), 1);
    back.remove();
    if (!stack.length) document.removeEventListener('keydown', onModalKey, true);
    syncBackground();
    if (opener?.isConnected && opener !== document.body && !stack.length) { try { opener.focus({ preventScroll: true }); } catch { /* gone */ } }
    onClose?.();
  };
  const tid = 'dlg-title-' + (++modalSeq);
  const m = h('div', { class: 'modal ' + cls, role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: -1 },
    h('header', null, h('h3', { id: tid, text: title }), h('span', { class: 'grow', style: { flex: 1 } }), headerExtra, h('button', { class: 'small', onclick: close, text: 'Đóng' })),
    body,
    footer || null);
  const back = h('div', { class: 'backdrop', onmousedown: (e) => { if (backdrop && e.target === back) close(); } }, m);
  const handle = { close, el: m, enter };
  if (!stack.length) document.addEventListener('keydown', onModalKey, true);
  stack.push(handle);
  syncBackground();
  root.append(back);
  // first focus: a field of the body, else the first footer button, else the dialog itself
  const first = m.querySelector('.body input:not([type=checkbox]):not([type=radio]), .body textarea, .body select') || m.querySelector('footer button:last-child') || m;
  if (!m.contains(document.activeElement)) first.focus({ preventScroll: true });
  return handle;
}
/** Close every open dialog (the shell calls this when a view is left). */
export function closeAllModals() { for (const m of [...stack].reverse()) m.close(); }
/** True while a dialog is open (shortcuts of a view must not act behind it). */
export const modalOpen = () => stack.length > 0;

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
