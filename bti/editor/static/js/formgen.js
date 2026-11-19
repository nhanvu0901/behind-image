// Parameter form generation from registry `params`. Pure part: descriptors, coercion, defaults.
import { clamp, clone } from './logic.js';
import { boxToRect, normBox } from './coords.js';

export const WIDGETS = {
  number: 'number', enum: 'select', bool: 'checkbox', string: 'text', color: 'color', text: 'textarea',
  point: 'point', points: 'points', lines: 'lines', box: 'box', camera: 'camera', asset: 'asset', items: 'items',
};

/** One descriptor per param definition, in registry order. Unknown types fall back to a JSON field. */
export function buildFields(defs, values = {}, required = null) {
  return (defs || []).map((d) => {
    const has = Object.prototype.hasOwnProperty.call(values, d.name);
    const widget = WIDGETS[d.type] || 'json';
    const value = has ? values[d.name] : d.default;
    const ranged = widget === 'number' && d.min != null && d.max != null;
    const f = {
      name: d.name, type: d.type, widget, def: d, value, isDefault: !has, unit: d.unit || '',
      min: d.min ?? null, max: d.max ?? null, values: d.values || null, measured: d.measured || null,
      slider: ranged, step: ranged ? stepFor(d.min, d.max) : 'any',
    };
    f.problem = validateValue(d, value) || (required?.has(d.name) && !String(value ?? '').trim() ? 'bắt buộc nhập' : null);
    return f;
  });
}

export function stepFor(min, max) {
  const span = max - min;
  if (span <= 2) return 0.01;
  if (span <= 20) return 0.05;
  if (span <= 200) return 0.5;
  return 1;
}

/** A registry `pattern` (Python regex, whole value must match) as a JS RegExp; null when JS cannot read it (the server still checks). */
export function patternRegex(src) { try { return new RegExp('^(?:' + src + ')$'); } catch { return null; } }
const oneLine = (s) => String(s).replace(/\s*[\r\n]+\s*/g, ' ');
const BAD_FORM = 'chưa đúng dạng cần nhập';
/** Count limits of a list param (`min_items` / `max_items`). */
export function countProblem(d, n) {
  const lo = d.min_items ?? null, hi = d.max_items ?? null;
  if (lo !== null && lo === hi && n !== lo) return `cần đúng ${lo} mục (hiện có ${n})`;
  if (lo !== null && n < lo) return `cần ít nhất ${lo} mục (hiện có ${n})`;
  if (hi !== null && n > hi) return `cần nhiều nhất ${hi} mục (hiện có ${n})`;
  return null;
}
const isPoint = (x) => Array.isArray(x) && x.length === 2 && x.every((n) => typeof n === 'number' && Number.isFinite(n));

export function validateValue(d, v) {
  if (v === null || v === undefined) return null;
  if ((d.type === 'string' || d.type === 'text') && d.pattern && typeof v === 'string') {
    const re = patternRegex(d.pattern);
    if (re && !re.test(oneLine(v))) return d.pattern_hint || BAD_FORM;
  }
  if (d.type === 'lines' && Array.isArray(v)) {
    const c = countProblem(d, v.length); if (c) return c;
    const re = d.pattern ? patternRegex(d.pattern) : null;
    if (re) { const i = v.findIndex((x) => !re.test(oneLine(x))); if (i >= 0) return `dòng ${i + 1}: ${d.pattern_hint || BAD_FORM}`; }
  }
  if (d.type === 'points' && Array.isArray(v)) {
    const c = countProblem(d, v.length); if (c) return c;
    if (d.numeric_only && v.some((x) => !isPoint(x))) return 'chỉ nhập hai số x, y, không dùng tên vùng';
  }
  if (d.type === 'point' && d.numeric_only && !isPoint(v)) return 'chỉ nhập hai số x, y, không dùng tên vùng';
  if (d.type === 'number') {
    if (typeof v !== 'number' || Number.isNaN(v)) return 'không phải số';
    if (d.min != null && v < d.min) return `nhỏ hơn ${d.min}`;
    if (d.max != null && v > d.max) return `lớn hơn ${d.max}`;
  }
  if (d.type === 'enum' && d.values && !d.values.includes(v)) return 'giá trị không có trong danh sách';
  if (d.type === 'items') return itemsProblem(d, v);
  if (d.type === 'box' && !boxToRect(v)) return 'khung phải là [x0, y0, x1, y1]';
  if (d.type === 'box' && Array.isArray(v) && v.length === 4 && v.every((n) => typeof n === 'number')) {
    const [x0, y0, x1, y1] = v;
    if (!(x0 >= 0 && y0 >= 0 && x1 <= 1920 && y1 <= 1080 && x1 - x0 >= 16 && y1 - y0 >= 16)) return 'khung phải nằm trong khung hình 1920 x 1080 và mỗi cạnh dài ít nhất 16 px';
  }
  return null;
}

/** A number held to the registry's range. Each bound counts alone (a param with only a min is still held to it). */
export function clampNumber(d, n) {
  if (d.min != null) n = Math.max(d.min, n);
  if (d.max != null) n = Math.min(d.max, n);
  return n;
}

/** Convert a raw input string/value into the typed value (clamped for numbers). */
export function coerce(d, raw) {
  switch (d.type) {
    case 'number': {
      if (raw === '' || raw === null) return d.default ?? null;
      let n = typeof raw === 'number' ? raw : Number(raw);
      if (Number.isNaN(n)) return d.default ?? null;
      return clampNumber(d, n);
    }
    case 'bool': return !!raw;
    case 'enum': return raw;
    case 'point': {
      if (Array.isArray(raw)) return raw;
      const s = String(raw).trim();
      const m = s.match(/^\[?\s*(-?[\d.]+)\s*[, ]\s*(-?[\d.]+)\s*\]?$/);
      return m ? [Number(m[1]), Number(m[2])] : s || null;
    }
    case 'points': return Array.isArray(raw) ? raw : [];
    case 'items': return Array.isArray(raw) ? raw : [];
    case 'lines': { if (Array.isArray(raw)) return raw; const a = String(raw ?? '').split('\n').map((x) => x.replace(/\s+$/, '')); while (a.length && a[a.length - 1] === '') a.pop(); return a; }
    case 'box': return normBox(typeof raw === 'string' ? (() => { try { return JSON.parse(raw); } catch { return null; } })() : raw);   // always [x0, y0, x1, y1]
    case 'camera':
      if (typeof raw === 'string') { try { return JSON.parse(raw); } catch { return null; } }
      return raw;
    case 'string': case 'text': case 'color': case 'asset': return raw === '' ? '' : raw;
    default:
      if (typeof raw === 'string') { try { return JSON.parse(raw); } catch { return raw; } }
      return raw;
  }
}

/** Defaults for a registry technique's params (used when the backend is not asked). */
export function defaultParams(defs) {
  const o = {};
  for (const d of defs || []) if (d.default !== null && d.default !== undefined) o[d.name] = clone(d.default);
  return o;
}

/** A point as text. Whole pixels, except fractions of the frame (space 'frame') which keep 3 decimals. */
export const pointToText = (v, space = 'source') => {
  if (!Array.isArray(v)) return v ?? '';
  const f = (n) => (space === 'frame' ? String(Math.round(n * 1e3) / 1e3) : String(Math.round(n)));
  return `${f(v[0])}, ${f(v[1])}`;
};

// ---------------------------------------------------------------- the `items` type: a list of records edited as rows
// The same rules as bti/engine/registry.py `check_items`: the page says in Vietnamese what the engine would refuse. The row editor of
// formui.js only calls these pure functions, so they are tested without a browser (tests/editor_frontend/items.test.mjs).

const isNum = (n) => typeof n === 'number' && Number.isFinite(n);
export const SIDE_FIELDS = ['string', 'number', 'enum', 'bool', 'lonlat', 'ref', 'at'];

/** "lon, lat" as the text of a longitude and latitude pair (a pair that is not a pair gives ''). */
export const lonlatToText = (v) => (Array.isArray(v) && v.length === 2 && v.every(isNum) ? `${Math.round(v[0] * 1e5) / 1e5}, ${Math.round(v[1] * 1e5) / 1e5}` : '');
/** The pair [lon, lat] typed as "lon, lat" (a comma or a space between them); null when it is not two numbers. */
export function parseLonlat(text) {
  const m = String(text ?? '').trim().match(/^\[?\s*(-?\d+(?:\.\d+)?)\s*[,; ]\s*(-?\d+(?:\.\d+)?)\s*\]?$/);
  return m ? [Number(m[1]), Number(m[2])] : null;
}
/** The value of one field of a new row: the declared default, else something that is valid for its kind (empty text stays empty). */
export function fieldStart(fd) {
  if (fd.default !== null && fd.default !== undefined) return clone(fd.default);
  switch (fd.type) {
    case 'number': return fd.min ?? 0;
    case 'enum': return (fd.values || [])[0] ?? '';
    case 'bool': return false;
    case 'lonlat': return [0, 0];
    case 'at': return fd.min ?? 0;
    default: return '';
  }
}
/** A new row: every declared field at its start value. */
export const newItem = (d) => Object.fromEntries((d.fields || []).map((fd) => [fd.name, fieldStart(fd)]));
const lo = (d) => d.min_items ?? 0, hi = (d) => d.max_items ?? Infinity;
export const canAddItem = (d, items) => (items || []).length < hi(d);
export const canRemoveItem = (d, items) => (items || []).length > lo(d);
/** The list with a new row at the end (the list itself when the registry's maximum is reached). */
export function addItem(d, items) {
  const cur = Array.isArray(items) ? items : [];
  return canAddItem(d, cur) ? [...clone(cur), newItem(d)] : cur;
}
/** The list without row `i` (the list itself when the registry's minimum would be broken or `i` is not a row). */
export function removeItem(d, items, i) {
  const cur = Array.isArray(items) ? items : [];
  return canRemoveItem(d, cur) && i >= 0 && i < cur.length ? clone(cur).filter((_, k) => k !== i) : cur;
}
/** The list with row `i` moved one place (`dir` -1 up, +1 down); the list itself at the ends. */
export function moveItem(items, i, dir) {
  const cur = Array.isArray(items) ? items : [], j = i + dir;
  if (i < 0 || i >= cur.length || j < 0 || j >= cur.length) return cur;
  const n = clone(cur);
  [n[i], n[j]] = [n[j], n[i]];
  return n;
}
/** What a field of a row holds after the person typed `raw` (a string from an input, a boolean, or an anchor object). */
export function coerceField(fd, raw) {
  switch (fd.type) {
    case 'number': {
      const n = typeof raw === 'number' ? raw : Number(String(raw).trim());
      if (raw === '' || raw === null || !Number.isFinite(n)) return fieldStart(fd);
      return clampNumber(fd, n);
    }
    case 'bool': return !!raw;
    case 'lonlat': return Array.isArray(raw) ? raw : (parseLonlat(raw) ?? raw);        // text that is not a pair stays text: the form shows the problem
    case 'at': {
      if (raw && typeof raw === 'object') return raw;
      const n = Number(String(raw).trim());
      return raw === '' || !Number.isFinite(n) ? fieldStart(fd) : clampNumber(fd, n);
    }
    case 'ref': {
      if (Array.isArray(raw)) return raw;
      const t = String(raw ?? '').trim(), m = t.match(/^\[?\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*\]?$/);
      return m ? [Number(m[1]), Number(m[2])] : t;
    }
    default: return raw;                                                              // string, enum
  }
}
/** The list with field `name` of row `i` set from `raw`. */
export function setItemField(d, items, i, name, raw) {
  const fd = (d.fields || []).find((f) => f.name === name), cur = Array.isArray(items) ? items : [];
  if (!fd || i < 0 || i >= cur.length) return cur;
  const n = clone(cur);
  n[i] = { ...n[i], [name]: coerceField(fd, raw) };
  return n;
}
const sideOf = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? 'anchor' : 'number');
/** The problem of one field of a row in Vietnamese, or null. */
export function fieldProblem(fd, v) {
  if (v === null || v === undefined || v === '') return fd.required ? 'bắt buộc nhập' : null;
  switch (fd.type) {
    case 'string': {
      if (typeof v !== 'string') return 'phải là chữ';
      const re = fd.pattern ? patternRegex(fd.pattern) : null;
      return re && !re.test(oneLine(v)) ? (fd.pattern_hint || BAD_FORM) : null;
    }
    case 'number': return !isNum(v) ? 'không phải số' : fd.min != null && v < fd.min ? `nhỏ hơn ${fd.min}` : fd.max != null && v > fd.max ? `lớn hơn ${fd.max}` : null;
    case 'enum': return (fd.values || []).includes(v) ? null : 'giá trị không có trong danh sách';
    case 'bool': return typeof v === 'boolean' ? null : 'phải là bật hoặc tắt';
    case 'lonlat':
      if (!(Array.isArray(v) && v.length === 2 && v.every(isNum))) return 'gõ kinh độ, vĩ độ, ví dụ 3.22, 51.21';
      return Math.abs(v[0]) > 180 ? 'kinh độ phải từ -180 đến 180' : Math.abs(v[1]) > 85 ? 'vĩ độ phải từ -85 đến 85' : null;
    case 'ref': return (typeof v === 'string' && v) || isPoint(v) ? null : 'phải là tên một vùng của hình hoặc hai số x, y';
    case 'at':
      if (sideOf(v) === 'anchor') return typeof v.t === 'number' || typeof v.w === 'number' || (typeof v.rel === 'number' && v.rel >= 0 && v.rel <= 1) ? null : 'mốc thời gian chưa đúng';
      return !isNum(v) ? 'không phải số' : fd.min != null && v < fd.min ? `nhỏ hơn ${fd.min}` : fd.max != null && v > fd.max ? `lớn hơn ${fd.max}` : null;
    default: return null;
  }
}
/** The first problem of a whole list, as one Vietnamese sentence that names the row and the field; null when the list is fine. */
export function itemsProblem(d, v) {
  if (v === null || v === undefined) return null;
  if (!Array.isArray(v)) return 'phải là một danh sách các mục';
  const c = countProblem(d, v.length); if (c) return c;
  for (let i = 0; i < v.length; i++) {
    const it = v[i];
    if (!it || typeof it !== 'object' || Array.isArray(it)) return `mục thứ ${i + 1}: bị hỏng`;
    const lab = ['name', 'id', 'text', 'label', 'date'].map((k) => it[k]).find((x) => (typeof x === 'string' || typeof x === 'number') && String(x).trim());
    for (const fd of d.fields || []) {
      const p = fieldProblem(fd, it[fd.name]);
      if (p) return `mục thứ ${i + 1}${lab !== undefined ? ` (${String(lab).slice(0, 40)})` : ''}, ô "${fd.name}": ${p}`;
    }
  }
  return null;
}
