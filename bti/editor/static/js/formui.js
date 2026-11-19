// Generic DOM form built from registry param definitions (see formgen.js). No per-technique code.
import { h, fillSelect } from './util.js';
import { valueLabel, CAMERA_LABELS, ITEMS_UI, itemFieldLabel } from './labels.js';
import { buildFields, coerce, pointToText, lonlatToText, addItem, removeItem, moveItem, setItemField, canAddItem, canRemoveItem, fieldProblem } from './formgen.js';
import { splitSpace, normBox } from './coords.js';
import { ctx, bus } from './ctx.js';
import { setCamSel, isCamSel } from './camsel.js';
import { EASES, describeAnchor, anchorFromTime, round, clone, cameraAt } from './logic.js';

const EASE_NAMES = Object.keys(EASES);

/**
 * opts: {onChange(name, value), assets: {key: asset}, regions: {name: region}, shotCtx: bool}
 * returns {el, sync(values)}
 */
export function renderForm(defs, values, opts) {
  const root = h('div', { class: 'form' });
  const widgets = {};
  const fields = buildFields(defs, values, opts.required);
  if (!fields.length) root.append(h('div', { class: 'hint', text: 'Kỹ thuật này không có tham số.' }));
  for (const f of fields) {
    const w = makeWidget(f, opts);
    widgets[f.name] = w;
    root.append(w.row);
  }
  return {
    el: root,
    sync(vals) {
      for (const f of buildFields(defs, vals, opts.required)) {
        const w = widgets[f.name];
        if (w && !w.row.contains(document.activeElement)) w.update(f.value, f);
        else if (w) w.mark(f);
      }
    },
  };
}

const placeholderOf = (space, numeric) => (numeric ? 'x, y (hai số)' : space === 'frame' ? 'x, y (0 đến 1 của khung)' : space === 'canvas' ? 'x, y (px khung hình)' : space === 'none' ? 'x, y' : 'tên vùng hoặc x, y');
const pickTitle = (space) => (space === 'none' ? 'Tham số này không chọn được trên ảnh: nhập số' : 'Bấm lên khung xem trước để lấy tọa độ' + (space === 'source' ? ' (Shift = luôn lấy x,y)' : ''));
const spaceTag = (space) => h('span', { class: 'hint', title: 'Hệ tọa độ của tham số', text: { source: 'px ảnh nguồn', canvas: 'px khung hình', frame: 'tỉ lệ khung (0 đến 1)', none: '' }[space] || '' });

function row(f, ctl, extra) {
  const label = h('label', { title: f.name + (f.def.unit ? ` (${f.def.unit})` : ''), text: f.name });
  const r = h('div', { class: 'row' + (f.problem ? ' field-problem' : '') }, label, h('div', { class: 'ctl' }, ctl));
  if (extra) r.append(extra);
  r.append(h('div', { class: 'hint field-note' }));
  setNote(r, f);
  return r;
}
/** Under the field: what to type (the registry's `pattern_hint`), or what is wrong with the value now. */
function setNote(r, f) {
  const el = r.querySelector(':scope > .field-note');
  if (!el) return;
  el.textContent = f.problem || f.def.pattern_hint || '';
  el.classList.toggle('warn', !!f.problem);
  el.hidden = !el.textContent;
}
const measuredTag = (f) => f.measured ? h('span', { class: 'measured', title: `Đo từ kênh gốc: ${f.measured.value}\n${f.measured.source || ''}`, text: typeof f.measured.value === 'number' ? `ref ${f.measured.value}` : 'ref*' }) : null;

function makeWidget(f, opts) {
  const emit = (v) => opts.onChange(f.name, v);
  const d = f.def;
  let update = () => {};
  let ctlNodes = [];
  let r;
  const mark = (nf) => { r.classList.toggle('field-problem', !!nf.problem); setNote(r, nf); };
  switch (f.widget) {
    case 'number': {
      const num = h('input', { type: 'number', step: f.step, min: f.min ?? undefined, max: f.max ?? undefined, value: f.value ?? '' });
      const nodes = [num];
      const note = h('span', { class: 'hint warn', hidden: true });
      let rng = null;
      let last = f.value;                                    // the value that is stored: the field always ends up showing it
      const show = (v) => { num.value = v ?? ''; if (rng) rng.value = v ?? f.min; };
      if (f.slider) {
        rng = h('input', { type: 'range', min: f.min, max: f.max, step: f.step, value: f.value ?? f.min, style: { flex: 1, minWidth: 0 } });
        rng.addEventListener('input', () => { num.value = rng.value; last = coerce(d, rng.value); note.hidden = true; emit(last); });
        nodes.unshift(rng);
        num.style.width = '74px'; num.style.flex = 'none';
      }
      num.addEventListener('input', () => { note.hidden = true; if (num.value === '') return; const v = coerce(d, num.value); last = v; if (rng) rng.value = v; emit(v); });
      // leaving the field: show the stored (clamped) value, and say so when it differs from what was typed (U2-004)
      num.addEventListener('blur', () => {
        const typed = num.value;
        if (typed !== '' && Number(typed) !== last) { note.textContent = `đã ép về ${last}`; note.hidden = false; }
        show(last);
      });
      ctlNodes = [...nodes, f.unit ? h('span', { class: 'unit', text: f.unit }) : null, measuredTag(f), note];
      update = (v) => { last = v; show(v); note.hidden = true; };
      break;
    }
    case 'select': {
      const sel = h('select');
      const fill = (v) => fillSelect(sel, f.values || [], v, (x) => valueLabel(x, f.name));
      fill(f.value);
      sel.addEventListener('change', () => emit(sel.value));
      ctlNodes = [sel, measuredTag(f)];
      update = (v) => { if (sel.value !== String(v ?? '')) fill(v); };
      break;
    }
    case 'checkbox': {
      const c = h('input', { type: 'checkbox', checked: !!f.value });
      c.addEventListener('change', () => emit(c.checked));
      ctlNodes = [c, measuredTag(f)]; update = (v) => { c.checked = !!v; };
      break;
    }
    case 'color': {
      const norm = (v) => (/^#[0-9a-f]{6}$/i.test(v || '') ? v : '#000000');
      const c = h('input', { type: 'color', value: norm(f.value) });
      const t = h('input', { type: 'text', value: f.value ?? '' });
      c.addEventListener('input', () => { t.value = c.value; emit(c.value); });
      t.addEventListener('change', () => { c.value = norm(t.value); emit(t.value); });
      ctlNodes = [c, t]; update = (v) => { c.value = norm(v); t.value = v ?? ''; };
      break;
    }
    case 'textarea': {
      const t = h('textarea', { value: f.value ?? '' });
      t.addEventListener('input', () => emit(t.value));
      ctlNodes = [t]; update = (v) => { t.value = v ?? ''; };
      break;
    }
    case 'text': {
      const t = h('input', { type: 'text', value: f.value ?? '' });
      t.addEventListener('input', () => emit(t.value));
      ctlNodes = [t, measuredTag(f)]; update = (v) => { t.value = v ?? ''; };
      break;
    }
    case 'point': {
      const sp = () => splitSpace(opts.spaceOf ? opts.spaceOf(d) : 'source');
      const dl = 'dl-' + Math.random().toString(36).slice(2, 7);
      const t = h('input', { type: 'text', list: dl, placeholder: placeholderOf(sp().space, d.numeric_only), value: pointToText(f.value, sp().space) });
      const data = h('datalist', { id: dl }, ...(sp().space === 'source' && !d.numeric_only ? Object.keys(opts.regions || {}) : []).map((n) => h('option', { value: n })));
      t.addEventListener('change', () => emit(coerce(d, t.value)));
      const pick = h('button', { class: 'small', title: pickTitle(sp().space), text: 'Chọn trên ảnh', disabled: sp().space === 'none', onclick: () => {
        const { space } = sp();
        ctx.pick = { space, cb: (v) => { t.value = pointToText(v, space); emit(v); } };
        bus.emit('pick', true);
      } });
      ctlNodes = [h('div', { class: 'pt-ctl' }, t, data, pick), spaceTag(sp().space)];
      update = (v) => { t.value = pointToText(v, sp().space); };
      break;
    }
    case 'points': {
      const sp = () => splitSpace(opts.spaceOf ? opts.spaceOf(d) : 'source');
      const dl = 'dl-' + Math.random().toString(36).slice(2, 7);
      const data = h('datalist', { id: dl }, ...(sp().space === 'source' && !d.numeric_only ? Object.keys(opts.regions || {}) : []).map((n) => h('option', { value: n })));
      const wrap = h('div', { class: 'pts' }, data);
      const lo = d.min_items ?? 0, hi = d.max_items ?? Infinity;
      let cur = Array.isArray(f.value) ? clone(f.value) : [];
      const push = (n) => { cur = n; emit(clone(n)); build(); };
      const build = () => {
        const { space } = sp();
        wrap.replaceChildren(data);
        cur.forEach((pt, i) => {
          const t = h('input', { type: 'text', list: dl, value: pointToText(pt, space), placeholder: placeholderOf(space, d.numeric_only), style: { flex: 1, minWidth: 0 } });
          t.addEventListener('change', () => { const n = clone(cur); n[i] = coerce({ type: 'point' }, t.value); cur = n; emit(clone(n)); });
          wrap.append(h('div', { class: 'pt-ctl' }, h('span', { class: 'hint', text: String(i + 1) }), t,
            h('button', { class: 'small', text: 'Chọn trên ảnh', disabled: space === 'none', title: pickTitle(space), onclick: () => {
              ctx.pick = { space, cb: (v) => { const n = clone(cur); n[i] = v; cur = n; emit(clone(n)); build(); } }; bus.emit('pick', true);
            } }),
            h('button', { class: 'small danger', text: 'Xóa', disabled: cur.length <= lo, title: cur.length <= lo ? `Cần ít nhất ${lo} điểm` : '', onclick: () => push(cur.filter((_, k) => k !== i)) })));
        });
        wrap.append(h('div', { class: 'pt-ctl' }, h('button', { class: 'small', text: '+ Thêm điểm', disabled: cur.length >= hi, title: cur.length >= hi ? `Tối đa ${hi} điểm` : '', onclick: () => {
          const last = cur[cur.length - 1], step = space === 'frame' ? 0.05 : 100;
          push([...cur, Array.isArray(last) ? [last[0] + step, last[1] + step] : (opts.centre ? opts.centre(space) : [1000, 1000])]);
        } }), spaceTag(space)));
      };
      build();
      ctlNodes = [wrap];
      update = (v) => { const nv = Array.isArray(v) ? v : []; if (JSON.stringify(nv) !== JSON.stringify(cur)) { cur = clone(nv); build(); } };
      break;
    }
    case 'lines': {
      const t = h('textarea', { rows: 4, placeholder: 'Mỗi dòng một mục', value: Array.isArray(f.value) ? f.value.join('\n') : '' });
      t.addEventListener('input', () => emit(coerce(d, t.value)));
      ctlNodes = [t, h('span', { class: 'hint', text: 'mỗi dòng một mục' })];
      update = (v) => { t.value = Array.isArray(v) ? v.join('\n') : ''; };
      break;
    }
    case 'box': {
      // the registry form is [x0, y0, x1, y1] (two corners); it is written back in exactly that form
      const names = ['x0', 'y0', 'x1', 'y1'];
      const ins = names.map((k) => h('input', { type: 'number', step: 1, title: k, placeholder: k, style: { width: '25%' } }));
      const set = (v) => { const b = normBox(v); ins.forEach((i, n) => { i.value = b ? b[n] : ''; }); };
      set(f.value);
      const hint = h('span', { class: 'hint', text: f.unit ? `[x0, y0, x1, y1], ${f.unit}` : '[x0, y0, x1, y1]' });
      const commit = () => { if (ins.some((i) => i.value === '')) return; emit(ins.map((i) => Math.round(Number(i.value) || 0))); };
      ins.forEach((i) => i.addEventListener('input', commit));
      const clear = d.default == null ? h('button', { class: 'small', text: 'Bỏ khung', title: 'Để trống (kỹ thuật tự chọn)', onclick: () => { set(null); emit(null); } }) : null;
      ctlNodes = [h('div', { class: 'pt-ctl' }, ...ins), clear, hint];
      update = set;
      break;
    }
    case 'asset': {
      const sel = h('select');
      const cur = (v) => (v && v.asset) || v || '';
      const fill = (v) => fillSelect(sel, ['', ...Object.keys(opts.assets || {})], cur(v), (k) => (k === '' ? '(không)' : `${k}: ${opts.assets[k].title || opts.assets[k].file}`));
      fill(f.value);
      sel.addEventListener('change', () => emit(sel.value ? { asset: sel.value } : null));
      ctlNodes = [sel]; update = (v) => { if (sel.value !== String(cur(v))) fill(v); };
      break;
    }
    case 'items': {
      // a list of records as rows: one input per declared field, add, remove, move up and down (pure logic: formgen.js)
      const wrap = h('div', { class: 'items', style: { width: '100%' } });
      let cur = Array.isArray(f.value) ? clone(f.value) : [];
      const commit = (n, rebuild) => { cur = n; emit(clone(n)); if (rebuild) build(); };
      const input = (fd, v, i) => {
        const set = (raw, rebuild) => commit(setItemField(d, cur, i, fd.name, raw), rebuild);
        const note = h('div', { class: 'hint field-note warn', hidden: true });
        const show = (val) => { const p = fieldProblem(fd, val); note.textContent = p || ''; note.hidden = !p; return p; };
        let node;
        if (fd.type === 'enum') node = fillSelect(h('select', { onchange: (e) => set(e.target.value) }), fd.values || [], v, (x) => valueLabel(x, fd.name));
        else if (fd.type === 'bool') node = h('input', { type: 'checkbox', checked: !!v, onchange: (e) => set(e.target.checked) });
        else if (fd.type === 'number') node = h('input', { type: 'number', step: 'any', min: fd.min ?? undefined, max: fd.max ?? undefined, value: v ?? '', onchange: (e) => { set(e.target.value); e.target.value = cur[i][fd.name] ?? ''; show(cur[i][fd.name]); } });
        else if (fd.type === 'lonlat') node = h('input', { type: 'text', value: lonlatToText(v) || (typeof v === 'string' ? v : ''), placeholder: ITEMS_UI.lonlatHint, onchange: (e) => { set(e.target.value); show(cur[i][fd.name]); } });
        else if (fd.type === 'at') {
          const isWord = v && typeof v === 'object' && typeof v.w === 'number';
          const kindSel = h('select', { onchange: (e) => set(e.target.value === 'w' ? anchorFromTime(ctx.t, ctx.words(), false, Infinity) : round(ctx.t, 2), true) },
            ...[['t', ITEMS_UI.atSeconds], ['w', ITEMS_UI.atWord]].map(([k, l]) => h('option', { value: k, text: l, selected: (k === 'w') === !!isWord })));
          const val = isWord ? h('span', { class: 'hint', text: describeAnchor(v, ctx.words()) })
            : h('input', { type: 'number', step: 0.1, min: fd.min ?? undefined, max: fd.max ?? undefined, value: typeof v === 'number' ? v : '', title: ITEMS_UI.atUnit, onchange: (e) => { set(e.target.value); e.target.value = cur[i][fd.name]; show(cur[i][fd.name]); } });
          const here = h('button', { class: 'small', type: 'button', style: { whiteSpace: 'nowrap' }, title: ITEMS_UI.atHereTitle, text: ITEMS_UI.atHere, onclick: () => set(anchorFromTime(ctx.t, ctx.words(), false, Infinity), true) });
          node = h('div', { class: 'pt-ctl' }, kindSel, val, here);
        } else node = h('input', { type: 'text', value: typeof v === 'string' ? v : (v == null ? '' : JSON.stringify(v)), onchange: (e) => { set(e.target.value); show(cur[i][fd.name]); } });
        show(v);
        return h('div', { class: 'item-field' + (fd.type === 'bool' ? ' item-bool' : '') }, h('label', { text: itemFieldLabel(fd.name), title: fd.name + (fd.unit ? ` (${fd.unit})` : '') }), node, note);
      };
      const build = () => {
        wrap.replaceChildren();
        if (!cur.length) wrap.append(h('div', { class: 'hint', text: ITEMS_UI.empty }));
        cur.forEach((it, i) => {
          const name = ['name', 'id', 'text', 'label', 'date'].map((k) => it?.[k]).find((x) => (typeof x === 'string' || typeof x === 'number') && String(x).trim());
          wrap.append(h('div', { class: 'item-row kf' },
            h('div', { class: 'row' }, h('b', { style: { flex: 1 }, text: ITEMS_UI.row(i + 1, name !== undefined ? String(name).slice(0, 40) : '') }),
              h('button', { class: 'small', type: 'button', text: ITEMS_UI.up, disabled: i === 0, onclick: () => commit(moveItem(cur, i, -1), true) }),
              h('button', { class: 'small', type: 'button', text: ITEMS_UI.down, disabled: i === cur.length - 1, onclick: () => commit(moveItem(cur, i, 1), true) }),
              h('button', { class: 'small danger', type: 'button', text: ITEMS_UI.remove, disabled: !canRemoveItem(d, cur), title: canRemoveItem(d, cur) ? '' : ITEMS_UI.minTitle(d.min_items), onclick: () => commit(removeItem(d, cur, i), true) })),
            h('div', { class: 'item-fields' }, ...(d.fields || []).map((fd) => input(fd, it?.[fd.name], i)))));
        });
        wrap.append(h('button', { class: 'small', type: 'button', text: ITEMS_UI.add, disabled: !canAddItem(d, cur), title: canAddItem(d, cur) ? '' : ITEMS_UI.maxTitle(d.max_items), onclick: () => commit(addItem(d, cur), true) }));
      };
      build();
      ctlNodes = [wrap];
      update = (v) => { const nv = Array.isArray(v) ? v : []; if (JSON.stringify(nv) !== JSON.stringify(cur)) { cur = clone(nv); build(); } };
      break;
    }
    case 'camera': {
      const wrap = h('div', { style: { width: '100%' } });
      let cur = clone(f.value) || [];
      const build = (keys) => {
        wrap.replaceChildren();
        keys.forEach((k, i) => {
          const kind = typeof k.at?.t === 'number' ? 't' : typeof k.at?.w === 'number' ? 'w' : 'rel';
          // a number field never stores garbage: blank or not a number puts the old value back; zoom stays above 0
          const typed = (e, old, min = -Infinity, max = Infinity) => { const v = e.target.value.trim() === '' ? NaN : Number(e.target.value); if (!Number.isFinite(v)) { e.target.value = round(old ?? 0, 3); return null; } const c = Math.min(max, Math.max(min, v)); if (c !== v) e.target.value = c; return c; };
          const num = (key, step) => h('input', { type: 'number', step, value: round(k[key] ?? 0, 3), onchange: (e) => { const v = typed(e, k[key], key === 'zoom' ? 0.01 : -Infinity, key === 'zoom' ? 1000 : Infinity); if (v !== null) mutate(i, (kk) => { kk[key] = v; }); } });
          const kindSel = h('select', { onchange: (e) => mutate(i, (kk) => { kk.at = e.target.value === 'rel' ? { rel: i ? 1 : 0 } : e.target.value === 't' ? { t: round(ctx.t, 3) } : anchorFromTime(ctx.t, ctx.words(), false, Infinity); }, true) },
            ...[['rel', '% shot'], ['t', 'giây'], ['w', 'từ']].map(([v, l]) => h('option', { value: v, text: l, selected: v === kind })));
          const atIn = kind === 'rel' ? h('input', { type: 'number', step: 0.05, min: 0, max: 1, value: k.at?.rel ?? 0, onchange: (e) => { const v = typed(e, k.at?.rel, 0, 1); if (v !== null) mutate(i, (kk) => { kk.at = { rel: v }; }); } })
            : kind === 't' ? h('input', { type: 'number', step: 0.1, value: k.at.t, onchange: (e) => { const v = typed(e, k.at.t, 0); if (v !== null) mutate(i, (kk) => { kk.at = { t: v }; }); } })
              : h('span', { class: 'hint', text: describeAnchor(k.at, ctx.words()) });
          const block = h('div', { class: 'kf', onclick: () => pick(i), title: CAMERA_LABELS.keyHint },
            h('div', { class: 'row' }, h('b', { style: { flex: 1 } }, 'Khóa ' + (i + 1), h('span', { class: 'kf-tag', text: CAMERA_LABELS.selected, hidden: true })),
              h('button', { class: 'small danger', text: 'Xóa', onclick: () => { const n = clone(cur); n.splice(i, 1); cur = n; emit(n); build(n); } })),
            h('div', { class: 'row' }, h('label', { text: 'Thời điểm' }), h('div', { class: 'ctl' }, kindSel, atIn,
              h('button', { class: 'small', style: { whiteSpace: 'nowrap' }, title: 'Gắn vào từ tại đầu phát', text: '= đầu phát', onclick: () => mutate(i, (kk) => { kk.at = anchorFromTime(ctx.t, ctx.words(), false, Infinity); }, true) }))),
            h('div', { class: 'kf-grid' }, h('div', null, h('label', { text: 'cx' }), num('cx', 1)), h('div', null, h('label', { text: 'cy' }), num('cy', 1)), h('div', null, h('label', { text: 'zoom' }), num('zoom', 0.01))),
            h('div', { class: 'row', style: { marginTop: '4px' } }, h('label', { text: 'Chuyển động' }), h('div', { class: 'ctl' },
              fillSelect(h('select', { onchange: (e) => mutate(i, (kk) => { kk.ease = e.target.value; }) }), EASE_NAMES, k.ease || 'linear', (n) => valueLabel(n)))));
          block.addEventListener('focusin', () => pick(i));      // tabbing into a field of a key selects it on the picture too
          wrap.append(block);
        });
        wrap.append(h('button', { class: 'small', text: '+ Thêm khóa camera', onclick: () => {
          const n = cur.length ? [...clone(cur), { ...clone(cur[cur.length - 1]), at: { rel: 1 } }] : [opts.newKey ? opts.newKey() : { at: { rel: 0 }, cx: 1000, cy: 1000, zoom: 0.5, ease: 'linear' }]; cur = n; emit(n); build(n);
        } }));
        paint(false);
      };
      // the key selected on the picture (camsel.js) is marked here, and a click or focus on a key's block selects it there
      const pick = (i) => { const shot = ctx.store.sel.shot; if (shot) setCamSel(shot, f.name, i, 'form'); };
      const paint = (scroll) => {
        const shot = ctx.store.sel.shot;
        [...wrap.children].filter((el) => el.classList.contains('kf')).forEach((el, i) => {
          const on = !!shot && isCamSel(shot, f.name, i);
          el.classList.toggle('kf-sel', on);
          const tag = el.querySelector('.kf-tag'); if (tag) tag.hidden = !on;
          if (on && scroll) el.scrollIntoView({ block: 'nearest' });
        });
      };
      const off = bus.on('camsel', (e) => { if (!wrap.isConnected) { off(); return; } paint(e.from === 'preview'); });
      const mutate = (i, fn, rebuild) => { const n = clone(cur); fn(n[i]); cur = n; emit(n); if (rebuild) build(n); };
      build(cur);
      ctlNodes = [wrap];
      update = (v) => { const nv = v || []; const same = nv.length === cur.length; cur = clone(nv); if (!same) build(cur); else { const ins = wrap.querySelectorAll('.kf-grid input'); cur.forEach((k, i) => { ins[i * 3].value = round(k.cx, 1); ins[i * 3 + 1].value = round(k.cy, 1); ins[i * 3 + 2].value = round(k.zoom, 3); }); } };
      break;
    }
    default: {
      const t = h('textarea', { value: f.value === undefined ? '' : JSON.stringify(f.value) });
      t.addEventListener('change', () => emit(coerce(d, t.value)));
      ctlNodes = [t, h('span', { class: 'hint warn', text: `kiểu ${f.type}` })];
      update = (v) => { t.value = v === undefined ? '' : JSON.stringify(v); };
    }
  }
  r = row(f, ctlNodes.filter(Boolean));
  if (f.widget === 'camera' || f.widget === 'items') r.classList.add('stack');
  if (f.problem) r.title = f.problem;
  return { row: r, update, mark };
}
