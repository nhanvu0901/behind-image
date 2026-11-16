// Pure logic: time/x mapping, anchors, snapping, camera/box conversion, derived keys.
export const MIN_SHOT = 0.2;

// Must equal bti/engine/vfx.py EASE (the engine raises on any other name).
export const EASES = {
  linear: (x) => x,
  in_quad: (x) => x * x,
  in_cubic: (x) => x * x * x,
  out_cubic: (x) => 1 - Math.pow(1 - x, 3),
  out_quad: (x) => 1 - (1 - x) * (1 - x),
  inout_cubic: (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2),
  inout_sine: (x) => -(Math.cos(Math.PI * x) - 1) / 2,
};

export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const round = (v, n = 3) => { const k = 10 ** n; return Math.round(v * k) / k; };
export const clone = (o) => (o === undefined ? undefined : JSON.parse(JSON.stringify(o)));

// ---- time <-> x. view = {t0: time at x=0, pps: pixels per second}
export const timeToX = (t, view) => (t - view.t0) * view.pps;
export const xToTime = (x, view) => x / view.pps + view.t0;

// ---- words
export function wordIndexAt(words, t) {
  // last word with s <= t, or -1
  let lo = 0, hi = words.length - 1, ans = -1;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (words[m].s <= t) { ans = m; lo = m + 1; } else hi = m - 1;
  }
  return ans;
}

export function nearestWordStart(words, t) {
  if (!words.length) return null;
  const i = wordIndexAt(words, t);
  const cands = [i, i + 1].filter((k) => k >= 0 && k < words.length);
  let best = cands[0];
  for (const k of cands) if (Math.abs(words[k].s - t) < Math.abs(words[best].s - t)) best = k;
  return { idx: best, t: words[best].s, dist: Math.abs(words[best].s - t) };
}

export const cleanWord = (w) => String(w ?? '').replace(/[^\p{L}\p{N}'-]/gu, '') || String(w ?? '');

/** Snap a time to a word start and return an anchor. free=true (Alt) gives {"t"}. */
export function anchorFromTime(t, words, free = false) {
  t = round(Math.max(0, t), 3);
  if (free || !words.length) return { t };
  const n = nearestWordStart(words, t);
  return { w: n.idx, off: 0, text: cleanWord(words[n.idx].w) };
}

/** Resolve an anchor to seconds. parent = {t0, t1} for rel anchors. Returns null if unresolvable. */
export function resolveAnchor(a, words, parent) {
  if (!a || typeof a !== 'object') return null;
  if (typeof a.t === 'number') return a.t;
  if (typeof a.w === 'number') {
    const w = words[a.w];
    return w ? w.s + (a.off || 0) : null;
  }
  if (typeof a.rel === 'number' && parent) return parent.t0 + a.rel * (parent.t1 - parent.t0);
  return null;
}

export function anchorStale(a, words) {
  if (!a || typeof a.w !== 'number') return false;
  const w = words[a.w];
  return !w || (a.text != null && cleanWord(w.w) !== a.text && w.w !== a.text);
}

export function describeAnchor(a, words) {
  if (!a) return '';
  if (typeof a.t === 'number') return `t=${round(a.t, 2)}s`;
  if (typeof a.rel === 'number') return `${Math.round(a.rel * 100)}% shot`;
  if (typeof a.w === 'number') return `#${a.w} "${a.text ?? words[a.w]?.w ?? '?'}"${a.off ? (a.off > 0 ? ' +' : ' ') + round(a.off, 2) : ''}`;
  return '?';
}

// ---- derived keys (_t, _t0, _t1). Anything starting with "_" is derived.
export function stripDerived(o) {
  if (Array.isArray(o)) return o.map(stripDerived);
  if (o && typeof o === 'object') {
    const r = {};
    for (const k of Object.keys(o)) if (!k.startsWith('_')) r[k] = stripDerived(o[k]);
    return r;
  }
  return o;
}

function stampAnchor(a, words, parent) {
  if (a && typeof a === 'object') a._t = resolveAnchor(a, words, parent);
}

/** Every camera keyframe list inside a params object (a technique may have several, e.g. camera_left). */
export function cameraLists(params) {
  const out = [];
  for (const [name, v] of Object.entries(params || {})) {
    if (Array.isArray(v) && v.length && v.every((k) => k && typeof k === 'object' && k.at && typeof k.at === 'object' && 'zoom' in k)) out.push({ name, keys: v });
  }
  return out;
}

/** Recompute _t, _t0, _t1 in place on a storyboard. */
export function derive(sb, timing) {
  const words = timing?.words || [];
  const endT = sb.end?.t ?? timing?.duration ?? 0;
  const shots = sb.shots;
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i];
    stampAnchor(s.start, words, null);
    s._t0 = s.start?._t ?? (i ? shots[i - 1]._t1 : 0);
  }
  for (let i = 0; i < shots.length; i++) {
    const s = shots[i];
    s._t1 = i + 1 < shots.length ? shots[i + 1]._t0 : endT;
    const parent = { t0: s._t0, t1: s._t1 };
    for (const l of cameraLists(s.params)) for (const k of l.keys) stampAnchor(k.at, words, parent);
    for (const o of s.overlays || []) {
      stampAnchor(o.start, words, parent);
      o._t0 = o.start?._t ?? s._t0;
      if (typeof o.dur === 'number') o._t1 = o._t0 + o.dur;
      else if (o.end) { stampAnchor(o.end, words, parent); o._t1 = o.end._t ?? s._t1; }
      else o._t1 = s._t1;
      o._t0 = clamp(o._t0, s._t0, s._t1);
      o._t1 = clamp(o._t1, o._t0, s._t1);
    }
  }
  if (sb.end) sb.end._t = endT;
  return sb;
}

export function shotIndexAt(shots, t) {
  let lo = 0, hi = shots.length - 1, ans = 0;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (shots[m]._t0 <= t) { ans = m; lo = m + 1; } else hi = m - 1;
  }
  return ans;
}

// ---- camera <-> box. Canvas is {w,h}; the visible box is w/zoom by h/zoom.
export function cameraToBox(cam, canvas) {
  const w = canvas.w / cam.zoom, h = canvas.h / cam.zoom;
  return { x: cam.cx - w / 2, y: cam.cy - h / 2, w, h };
}
export function boxToCamera(box, canvas) {
  return { cx: box.x + box.w / 2, cy: box.y + box.h / 2, zoom: canvas.w / box.w };
}
/** Resize a box keeping the canvas aspect: width wins, height follows (anchored at the centre). */
export function fixAspect(box, canvas) {
  const h = (box.w * canvas.h) / canvas.w;
  return { x: box.x, y: box.y + (box.h - h) / 2, w: box.w, h };
}

/** Camera at time t, exactly like bti/engine/vfx.py Cam.at: keys in LIST order (the engine requires increasing time),
 * the ease of the segment's FIRST key, cx/cy linear and zoom interpolated in LOG space, holding the last pose after it. */
export function cameraAt(keys, t) {
  const ks = (keys || []).filter((k) => k.at && typeof k.at._t === 'number');
  if (!ks.length) return null;
  const pose = (k) => ({ cx: k.cx, cy: k.cy, zoom: k.zoom });
  if (t <= ks[0].at._t) return pose(ks[0]);
  for (let i = 0; i + 1 < ks.length; i++) {
    const a = ks[i], b = ks[i + 1];
    if (t <= b.at._t) {
      const span = b.at._t - a.at._t || 1e-9;
      const e = (EASES[a.ease] || EASES.linear)(clamp((t - a.at._t) / span, 0, 1));
      return { cx: a.cx + (b.cx - a.cx) * e, cy: a.cy + (b.cy - a.cy) * e, zoom: Math.exp(Math.log(a.zoom) + (Math.log(b.zoom) - Math.log(a.zoom)) * e) };
    }
  }
  return pose(ks[ks.length - 1]);
}

/** The camera the engine uses when a shot has no camera key: the whole image at 95.5 % of the frame height. */
export function engineFitCamera(asset, canvas = { w: 1920, h: 1080 }) {
  return { cx: asset.width / 2, cy: asset.height / 2, zoom: (0.955 * canvas.h) / asset.height };
}

/** Re-express a camera key list over a sub-range of its shot. Keys are {at, cx, cy, zoom, ease} with derived at._t.
 * `[ta, tb]` is the new absolute range, `[t0, t1]` the old shot range. rel anchors are rescaled to stay at the same absolute
 * time; word/t anchors are kept. The pose at the cut is interpolated with the engine semantics, so the picture is continuous. */
export function cropCamera(keys, ta, tb, t0, t1) {
  const ks = keys.filter((k) => k.at && typeof k.at._t === 'number');
  if (!ks.length) return clone(keys);
  const out = [];
  const re = (k) => {
    const c = clone(k);
    if (typeof c.at.rel === 'number') c.at = { rel: round(clamp((k.at._t - ta) / (tb - ta), 0, 1), 4) };
    return c;
  };
  const inside = ks.filter((k) => k.at._t > ta + 1e-6 && k.at._t < tb - 1e-6);
  const p0 = cameraAt(ks, ta), p1 = cameraAt(ks, tb);
  const before = ks.filter((k) => k.at._t <= ta + 1e-6).pop();
  const first = { at: { rel: 0 }, cx: round(p0.cx, 2), cy: round(p0.cy, 2), zoom: round(p0.zoom, 5), ease: before?.ease || 'linear' };
  out.push(first, ...inside.map(re));
  const lastIn = ks.find((k) => k.at._t >= tb - 1e-6);
  const endK = { at: { rel: 1 }, cx: round(p1.cx, 2), cy: round(p1.cy, 2), zoom: round(p1.zoom, 5), ease: lastIn?.ease || 'linear' };
  out.push(endK);
  return out;
}

/** After the shot got longer, keep every camera pose at the same absolute time: rel anchors shrink, the last pose is held. */
export function rescaleRel(keys, oldDur, newDur) {
  const f = oldDur / newDur;
  return keys.map((k) => (typeof k.at?.rel === 'number' ? { ...clone(k), at: { rel: round(k.at.rel * f, 4) } } : clone(k)));
}

// ---- screen <-> source mapping. view = {W,H} of the on-screen frame; cam in canvas units.
export function makeMapping(cam, canvas, view) {
  const k = (cam.zoom * view.W) / canvas.w; // screen px per source px
  return {
    k,
    toScreen: (x, y) => [(x - cam.cx) * k + view.W / 2, (y - cam.cy) * k + view.H / 2],
    toSource: (sx, sy) => [(sx - view.W / 2) / k + cam.cx, (sy - view.H / 2) / k + cam.cy],
  };
}
export function fitCamera(asset, canvas) {
  const zoom = Math.min(canvas.w / asset.width, canvas.h / asset.height) * 0.94;
  return { cx: asset.width / 2, cy: asset.height / 2, zoom };
}
