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

export function validateValue(d, v) {
  if (v === null || v === undefined) return null;
  if (d.type === 'number') {
    if (typeof v !== 'number' || Number.isNaN(v)) return 'không phải số';
    if (d.min != null && v < d.min) return `nhỏ hơn ${d.min}`;
    if (d.max != null && v > d.max) return `lớn hơn ${d.max}`;
  }
  if (d.type === 'enum' && d.values && !d.values.includes(v)) return 'giá trị không có trong danh sách';
  if (d.type === 'box' && !boxToRect(v)) return 'khung phải là [x0, y0, x1, y1]';
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
