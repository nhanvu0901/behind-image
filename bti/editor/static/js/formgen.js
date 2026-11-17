// Parameter form generation from registry `params`. Pure part: descriptors, coercion, defaults.
import { clamp, clone } from './logic.js';
import { boxToRect, normBox } from './coords.js';

export const WIDGETS = {
  number: 'number', enum: 'select', bool: 'checkbox', string: 'text', color: 'color', text: 'textarea',
  point: 'point', points: 'points', lines: 'lines', box: 'box', camera: 'camera', asset: 'asset',
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
