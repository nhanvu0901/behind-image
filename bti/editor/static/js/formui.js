// Generic DOM form built from registry param definitions (see formgen.js). No per-technique code.
import { h } from './util.js';
import { buildFields, coerce, pointToText } from './formgen.js';
import { ctx, bus } from './ctx.js';
import { EASES, describeAnchor, anchorFromTime, round, clone, cameraAt } from './logic.js';

const EASE_NAMES = Object.keys(EASES);

/**
 * opts: {onChange(name, value), assets: {key: asset}, regions: {name: region}, shotCtx: bool}
 * returns {el, sync(values)}
 */
export function renderForm(defs, values, opts) {
  const root = h('div', { class: 'form' });
  const widgets = {};
  const fields = buildFields(defs, values);
  if (!fields.length) root.append(h('div', { class: 'hint', text: 'Kỹ thuật này không có tham số.' }));
  for (const f of fields) {
    const w = makeWidget(f, opts);
    widgets[f.name] = w;
    root.append(w.row);
  }
  return {
    el: root,
    sync(vals) {
      for (const f of buildFields(defs, vals)) {
        const w = widgets[f.name];
        if (w && !w.row.contains(document.activeElement)) w.update(f.value, f);
        else if (w) w.mark(f);
      }
    },
  };
}

function row(f, ctl, extra) {
  const label = h('label', { title: f.name + (f.def.unit ? ` (${f.def.unit})` : ''), text: f.name });
  const r = h('div', { class: 'row' + (f.problem ? ' field-problem' : '') }, label, h('div', { class: 'ctl' }, ctl));
  if (extra) r.append(extra);
  return r;
}
const measuredTag = (f) => f.measured ? h('span', { class: 'measured', title: `Đo từ kênh gốc: ${f.measured.value}\n${f.measured.source || ''}`, text: typeof f.measured.value === 'number' ? `ref ${f.measured.value}` : 'ref*' }) : null;

function makeWidget(f, opts) {
  const emit = (v) => opts.onChange(f.name, v);
  const d = f.def;
  let update = () => {};
  let ctlNodes = [];
  let r;
  const mark = (nf) => r.classList.toggle('field-problem', !!nf.problem);
  switch (f.widget) {
    case 'number': {
      const num = h('input', { type: 'number', step: f.step, min: f.min ?? undefined, max: f.max ?? undefined, value: f.value ?? '' });
      const nodes = [num];
      let rng = null;
      if (f.slider) {
        rng = h('input', { type: 'range', min: f.min, max: f.max, step: f.step, value: f.value ?? f.min, style: { flex: 1, minWidth: 0 } });
        rng.addEventListener('input', () => { num.value = rng.value; emit(coerce(d, rng.value)); });
        nodes.unshift(rng);
        num.style.width = '74px'; num.style.flex = 'none';
      }
      num.addEventListener('input', () => { if (num.value === '') return; const v = coerce(d, num.value); if (rng) rng.value = v; emit(v); });
      ctlNodes = [...nodes, f.unit ? h('span', { class: 'unit', text: f.unit }) : null, measuredTag(f)];
      update = (v) => { num.value = v ?? ''; if (rng) rng.value = v ?? f.min; };
      break;
    }
    case 'select': {
      const sel = h('select', null, ...(f.values || []).map((v) => h('option', { value: v, text: v })));
      if (f.value != null && !(f.values || []).includes(f.value)) sel.prepend(h('option', { value: f.value, text: String(f.value) }));
      sel.value = f.value ?? '';
      sel.addEventListener('change', () => emit(sel.value));
      ctlNodes = [sel, measuredTag(f)];
      update = (v) => { sel.value = v ?? ''; };
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
      const dl = 'dl-' + Math.random().toString(36).slice(2, 7);
      const t = h('input', { type: 'text', list: dl, placeholder: 'tên vùng hoặc x, y', value: pointToText(f.value) });
      const data = h('datalist', { id: dl }, ...Object.keys(opts.regions || {}).map((n) => h('option', { value: n })));
      t.addEventListener('change', () => emit(coerce(d, t.value)));
      const pick = h('button', { class: 'small', title: 'Bấm lên khung xem trước để lấy tọa độ (Shift = luôn lấy x,y)', text: 'Chọn trên ảnh', onclick: () => {
        ctx.pick = { cb: (v) => { t.value = pointToText(v); emit(v); } };
        bus.emit('pick', true);
      } });
      ctlNodes = [h('div', { class: 'pt-ctl' }, t, data, pick)];
      update = (v) => { t.value = pointToText(v); };
      break;
    }
    case 'points': {
      const dl = 'dl-' + Math.random().toString(36).slice(2, 7);
      const data = h('datalist', { id: dl }, ...Object.keys(opts.regions || {}).map((n) => h('option', { value: n })));
      const wrap = h('div', { class: 'pts' }, data);
      let cur = Array.isArray(f.value) ? clone(f.value) : [];
      const push = (n) => { cur = n; emit(clone(n)); build(); };
      const build = () => {
        wrap.replaceChildren(data);
        cur.forEach((pt, i) => {
          const t = h('input', { type: 'text', list: dl, value: pointToText(pt), placeholder: 'tên vùng hoặc x, y', style: { flex: 1, minWidth: 0 } });
          t.addEventListener('change', () => { const n = clone(cur); n[i] = coerce({ type: 'point' }, t.value); cur = n; emit(clone(n)); });
          wrap.append(h('div', { class: 'pt-ctl' }, h('span', { class: 'hint', text: String(i + 1) }), t,
            h('button', { class: 'small', text: 'Chọn trên ảnh', title: 'Bấm lên khung xem trước để lấy tọa độ cho điểm này (Shift = luôn lấy x,y)', onclick: () => {
              ctx.pick = { cb: (v) => { const n = clone(cur); n[i] = v; cur = n; emit(clone(n)); build(); } }; bus.emit('pick', true);
            } }),
            h('button', { class: 'small danger', text: 'Xóa', onclick: () => push(cur.filter((_, k) => k !== i)) })));
        });
        wrap.append(h('button', { class: 'small', text: '+ Thêm điểm', onclick: () => {
          const last = cur[cur.length - 1];
          push([...cur, Array.isArray(last) ? [last[0] + 100, last[1] + 100] : (opts.centre ? opts.centre() : [1000, 1000])]);
        } }));
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
      const keys = ['x', 'y', 'w', 'h'];
      const ins = keys.map((k) => h('input', { type: 'number', step: 1, title: k, placeholder: k, style: { width: '25%' } }));
      const set = (v) => ins.forEach((i, n) => { i.value = v && v[keys[n]] != null ? Math.round(v[keys[n]]) : ''; });
      set(f.value);
      const commit = () => { const o = {}; keys.forEach((k, n) => { o[k] = Number(ins[n].value) || 0; }); emit(o); };
      ins.forEach((i) => i.addEventListener('input', commit));
      ctlNodes = [h('div', { class: 'pt-ctl' }, ...ins)];
      update = set;
      break;
    }
    case 'asset': {
      const sel = h('select', null, h('option', { value: '', text: '(không)' }), ...Object.entries(opts.assets || {}).map(([k, a]) => h('option', { value: k, text: `${k}: ${a.title || a.file}` })));
      sel.value = (f.value && f.value.asset) || f.value || '';
      sel.addEventListener('change', () => emit(sel.value ? { asset: sel.value } : null));
      ctlNodes = [sel]; update = (v) => { sel.value = (v && v.asset) || v || ''; };
      break;
    }
    case 'camera': {
      const wrap = h('div', { style: { width: '100%' } });
      let cur = clone(f.value) || [];
      const build = (keys) => {
        wrap.replaceChildren();
        keys.forEach((k, i) => {
          const kind = typeof k.at?.t === 'number' ? 't' : typeof k.at?.w === 'number' ? 'w' : 'rel';
          const num = (key, step) => h('input', { type: 'number', step, value: round(k[key] ?? 0, 3), onchange: (e) => mutate(i, (kk) => { kk[key] = Number(e.target.value); }) });
          const kindSel = h('select', { onchange: (e) => mutate(i, (kk) => { kk.at = e.target.value === 'rel' ? { rel: i ? 1 : 0 } : e.target.value === 't' ? { t: round(ctx.t, 3) } : anchorFromTime(ctx.t, ctx.words()); }, true) },
            ...[['rel', '% shot'], ['t', 'giây'], ['w', 'từ']].map(([v, l]) => h('option', { value: v, text: l, selected: v === kind })));
          const atIn = kind === 'rel' ? h('input', { type: 'number', step: 0.05, min: 0, max: 1, value: k.at?.rel ?? 0, onchange: (e) => mutate(i, (kk) => { kk.at = { rel: Number(e.target.value) }; }) })
            : kind === 't' ? h('input', { type: 'number', step: 0.1, value: k.at.t, onchange: (e) => mutate(i, (kk) => { kk.at = { t: Number(e.target.value) }; }) })
              : h('span', { class: 'hint', text: describeAnchor(k.at, ctx.words()) });
          wrap.append(h('div', { class: 'kf' },
            h('div', { class: 'row' }, h('b', { text: 'Khóa ' + (i + 1), style: { flex: 1 } }),
              h('button', { class: 'small danger', text: 'Xóa', onclick: () => { const n = clone(cur); n.splice(i, 1); cur = n; emit(n); build(n); } })),
            h('div', { class: 'row' }, h('label', { text: 'Thời điểm' }), h('div', { class: 'ctl' }, kindSel, atIn,
              h('button', { class: 'small', style: { whiteSpace: 'nowrap' }, title: 'Gắn vào từ tại đầu phát', text: '= đầu phát', onclick: () => mutate(i, (kk) => { kk.at = anchorFromTime(ctx.t, ctx.words()); }, true) }))),
            h('div', { class: 'kf-grid' }, h('div', null, h('label', { text: 'cx' }), num('cx', 1)), h('div', null, h('label', { text: 'cy' }), num('cy', 1)), h('div', null, h('label', { text: 'zoom' }), num('zoom', 0.01))),
            h('div', { class: 'row', style: { marginTop: '4px' } }, h('label', { text: 'ease' }), h('div', { class: 'ctl' },
              h('select', { onchange: (e) => mutate(i, (kk) => { kk.ease = e.target.value; }) }, ...EASE_NAMES.map((n) => h('option', { value: n, text: n, selected: n === (k.ease || 'linear') })))))));
        });
        wrap.append(h('button', { class: 'small', text: '+ Thêm khóa camera', onclick: () => {
          const n = cur.length ? [...clone(cur), { ...clone(cur[cur.length - 1]), at: { rel: 1 } }] : [opts.newKey ? opts.newKey() : { at: { rel: 0 }, cx: 1000, cy: 1000, zoom: 0.5, ease: 'linear' }]; cur = n; emit(n); build(n);
        } }));
      };
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
  if (f.widget === 'camera') r.classList.add('stack');
  if (f.problem) r.title = f.problem;
  return { row: r, update, mark };
}
