// Pure edit operations on a draft storyboard (mutate the object they are given).
import { MIN_SHOT, clone, clamp, anchorFromTime, round, shotIndexAt, cropCamera, rescaleRel, cameraLists } from './logic.js';

export const markHuman = (item) => { if (item) item.source = 'human'; return item; };

export function nextId(list, prefix, pad = 0) {
  let n = 0;
  for (const it of list) {
    const m = String(it.id).match(/(\d+)$/);
    if (m) n = Math.max(n, +m[1]);
  }
  n += 1;
  return prefix + (pad ? String(n).padStart(pad, '0') : n);
}
export const allOverlays = (sb) => sb.shots.flatMap((s) => s.overlays || []);
export const nextShotId = (sb) => nextId(sb.shots, 's', 4);
export const nextOverlayId = (sb) => nextId(allOverlays(sb), 'o');

const MIN_OV = 0.1;

/** Keep an overlay inside [lo, hi] (the new span of its shot): shift it in when it starts early, shorten it when it ends late. */
export function fitOverlay(o, lo, hi, words) {
  const len = o._t1 - o._t0;
  let s = o._t0, e = o._t1;
  if (s < lo) { s = lo; e = Math.min(lo + len, hi); }
  if (s > hi - MIN_OV) { s = Math.max(lo, hi - Math.max(MIN_OV, Math.min(len, hi - lo))); }
  e = clamp(Math.min(e, hi), s + MIN_OV, Math.max(hi, s + MIN_OV));
  const runsToEnd = typeof o.dur !== 'number' && !o.end;
  if (Math.abs(s - o._t0) > 1e-6) {
    const free = !(o.start && typeof o.start.w === 'number');
    let a = anchorFromTime(s, words, free);
    const at = a.t ?? words[a.w].s;
    if (at < lo - 1e-6 || at > hi - MIN_OV + 1e-6) a = { t: round(s, 3) };
    o.start = a;
  }
  if (!runsToEnd || e < o._t1 - 1e-6 || Math.abs(s - o._t0) > 1e-6) {
    const startT = o.start.t ?? (o.start.w != null ? words[o.start.w].s + (o.start.off || 0) : s);
    if (runsToEnd && e >= hi - 1e-6) { /* still runs to the shot end */ }
    else { delete o.end; o.dur = round(Math.max(MIN_OV, e - (Math.abs(s - o._t0) > 1e-6 ? startT : o._t0)), 3); }
  }
  markHuman(o);
}
export function fitOverlays(shot, lo, hi, words) {
  for (const o of shot.overlays || []) {
    if (o._t0 < lo - 1e-6 || o._t1 > hi + 1e-6 || o._t0 > hi - MIN_OV) fitOverlay(o, lo, hi, words);
  }
}

/** Set a shot boundary (start of shot idx) to anchor; keeps tiling and the 0.2 s minimum.
 * Overlays of both neighbours are clamped into their shot's new span (shifted or shortened). */
export function moveBoundary(sb, idx, t, words, free) {
  if (idx <= 0 || idx >= sb.shots.length) return false;
  const prev = sb.shots[idx - 1], cur = sb.shots[idx];
  const lo = prev._t0 + MIN_SHOT, hi = cur._t1 - MIN_SHOT;
  if (hi < lo) return false;
  let a = anchorFromTime(clamp(t, lo, hi), words, free);
  // snapping may leave the legal window: fall back to a free anchor
  const tt = a.t ?? words[a.w].s;
  if (tt < lo - 1e-6 || tt > hi + 1e-6) a = { t: round(clamp(t, lo, hi), 3) };
  const nb = a.t ?? words[a.w].s + (a.off || 0);
  fitOverlays(prev, prev._t0, nb, words);
  fitOverlays(cur, nb, cur._t1, words);
  cur.start = a;
  markHuman(prev); markHuman(cur);
  return true;
}

export function splitShot(sb, idx, t, words, free = false) {
  const s = sb.shots[idx];
  if (!s || t < s._t0 + MIN_SHOT || t > s._t1 - MIN_SHOT) return null;
  let a = anchorFromTime(t, words, free);
  let at = a.t ?? words[a.w].s;
  if (at < s._t0 + MIN_SHOT || at > s._t1 - MIN_SHOT) { a = { t: round(t, 3) }; at = a.t; }
  const n = clone(s);
  for (const k of Object.keys(n)) if (k.startsWith('_')) delete n[k];
  n.id = nextShotId(sb);
  n.start = a;
  n.transition_in = null;
  n.locked = false;
  n.overlays = [];
  // camera: each half keeps the pose it had at that time (cx/cy linear, zoom in log space, like the engine)
  for (const l of cameraLists(s.params)) {
    const first = cropCamera(l.keys, s._t0, at, s._t0, s._t1);
    const second = cropCamera(l.keys, at, s._t1, s._t0, s._t1);
    s.params[l.name] = first;
    n.params[l.name] = second;
  }
  const keep = [];
  for (const o of s.overlays || []) {
    if (o._t0 >= at) { n.overlays.push(clone(o)); } else keep.push(o);
  }
  s.overlays = keep;
  fitOverlays(s, s._t0, at, words);
  markHuman(s); markHuman(n);
  sb.shots.splice(idx + 1, 0, n);
  return n.id;
}

/** Merge shot idx into the previous one. The previous shot's camera keeps every pose at the same absolute time
 * (its rel keys shrink) and holds its last pose over the merged part; the merged shot's own camera is dropped. */
export function mergeWithPrev(sb, idx) {
  if (idx <= 0) return false;
  const prev = sb.shots[idx - 1], cur = sb.shots[idx];
  const oldDur = prev._t1 - prev._t0, newDur = cur._t1 - prev._t0;
  for (const l of cameraLists(prev.params)) prev.params[l.name] = rescaleRel(l.keys, oldDur, newDur);
  prev.overlays = (prev.overlays || []).concat(cur.overlays || []);
  markHuman(prev);
  sb.shots.splice(idx, 1);
  return true;
}

export function deleteShot(sb, idx) {
  if (sb.shots.length <= 1) return false;
  const cur = sb.shots[idx];
  if (idx === 0) sb.shots[1].start = clone(cur.start);
  else markHuman(sb.shots[idx - 1]);
  sb.shots.splice(idx, 1);
  return true;
}

export function moveOverlay(sb, shot, ov, t, words, free) {
  const len = ov._t1 - ov._t0;
  const lo = shot._t0, hi = Math.max(lo, shot._t1 - Math.min(len, shot._t1 - shot._t0));
  ov.start = anchorFromTime(clamp(t, lo, hi), words, free);
  if (ov.end) { delete ov.end; ov.dur = round(len, 3); }
  else if (typeof ov.dur !== 'number' && ov._t1 < shot._t1) ov.dur = round(len, 3);
  markHuman(ov);
}

/** Drag one edge of an overlay chip. edge 'l' moves the start (the end stays), 'r' changes the duration. */
export function resizeOverlay(sb, shot, ov, edge, t, words, free) {
  if (edge === 'r') {
    const end = clamp(t, ov._t0 + MIN_OV, shot._t1);
    delete ov.end; ov.dur = round(end - ov._t0, 3);
  } else {
    const end = ov._t1;
    let a = anchorFromTime(clamp(t, shot._t0, end - MIN_OV), words, free);
    let st = a.t ?? words[a.w].s;
    if (st > end - MIN_OV || st < shot._t0) { st = round(clamp(t, shot._t0, end - MIN_OV), 3); a = { t: st }; }
    const toEnd = typeof ov.dur !== 'number' && !ov.end;
    ov.start = a;
    if (!toEnd || end < shot._t1 - 1e-6) { delete ov.end; ov.dur = round(end - st, 3); }
  }
  markHuman(ov);
}

export function addOverlay(sb, shotIdx, technique, intent, params, t, words) {
  const s = sb.shots[shotIdx];
  const at = clamp(t, s._t0, s._t1 - 0.5);
  const o = {
    id: nextOverlayId(sb), technique, intent, start: anchorFromTime(at, words), dur: round(Math.min(3, s._t1 - at), 2),
    params: params || {}, locked: false, source: 'human', note: '',
  };
  (s.overlays ||= []).push(o);
  return o.id;
}

/** Overlay ids are only unique inside their shot (o1, o2 ... per shot, as the exporter writes them), so every lookup is
 * scoped: `scope.shot` names the shot to look in first. Callers set it from the selection or from the dragged chip. */
export const scope = { shot: null };
const scoped = (sb) => (scope.shot ? [...sb.shots.filter((s) => s.id === scope.shot), ...sb.shots.filter((s) => s.id !== scope.shot)] : sb.shots);

export function removeOverlay(sb, id) {
  for (const s of scoped(sb)) {
    const i = (s.overlays || []).findIndex((o) => o.id === id);
    if (i >= 0) { s.overlays.splice(i, 1); markHuman(s); return true; }
  }
  return false;
}

export function findOverlay(sb, id) {
  for (const s of scoped(sb)) {
    const j = (s.overlays || []).findIndex((o) => o.id === id);
    if (j >= 0) return { shotIdx: sb.shots.indexOf(s), shot: s, idx: j, ov: s.overlays[j] };
  }
  return null;
}

/** Parse an issue path such as "shots[3].overlays[0].start" into {shot, overlay}. */
export function parseIssuePath(path) {
  const m = String(path || '').match(/^shots\[(\d+)\](?:\.overlays\[(\d+)\])?/);
  if (!m) return null;
  return { shot: +m[1], overlay: m[2] != null ? +m[2] : null };
}

export { shotIndexAt };
