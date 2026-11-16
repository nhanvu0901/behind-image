// Canvas timeline: chapters, shots (thumbs), overlay chips, words, waveform, playhead, minimap.
import { api } from './api.js';
import { ctx, bus, intentHsl } from './ctx.js';
import { $, fmtTime } from './util.js';
import { timeToX, xToTime, wordIndexAt, clamp, shotIndexAt } from './logic.js';
import * as E from './edit.js';
import { toggleLock } from './actions.js';

// DOM is looked up when the view is mounted (initTimeline), never at import time: the module outlives the view.
let root = null, scope = null, alive = false;
let wrap, cv;
const R = { ruler: 20, chap: 18, shot: 58, lane: 15, lanes: 3, words: 16, wave: 40, mini: 22, gap: 3 };
R.ovH = R.lane * R.lanes + 2;
const Y = {};
let c, W = 800, Ht = 240, dpr = 1;
const view = { t0: 0, pps: 10 };
let waves = null, drawQueued = false, laneCache = { v: -1, map: new Map() };
const thumbs = new Map();
let hover = null, guide = null;

function layoutY() {
  let y = 0;
  for (const k of ['ruler', 'chap', 'shot']) { Y[k] = y; y += R[k] + R.gap; }
  Y.ov = y; y += R.ovH + R.gap;
  Y.words = y; y += R.words + R.gap;
  Y.wave = y; y += R.wave + R.gap;
  Y.mini = Math.max(y, Ht - R.mini - 2);
}
const dur = () => Math.max(1, ctx.duration());
const minPps = () => W / dur();
const clampView = () => { view.pps = clamp(view.pps, minPps(), 500); view.t0 = clamp(view.t0, 0, Math.max(0, dur() - W / view.pps)); };
const X = (t) => timeToX(t, view);
export const requestDraw = () => { if (alive && !drawQueued) { drawQueued = true; requestAnimationFrame(draw); } };

function resize() {
  const r = wrap.getBoundingClientRect();
  W = r.width; Ht = r.height; dpr = Math.min(2, window.devicePixelRatio || 1);
  cv.width = Math.round(W * dpr); cv.height = Math.round(Ht * dpr);
  c = cv.getContext('2d'); layoutY(); clampView(); requestDraw();
}

function lanes() {
  if (laneCache.v === ctx.store.version) return laneCache.map;
  const all = [];
  for (const s of ctx.store.draft.shots) for (const o of s.overlays || []) all.push({ o, k: s.id + '/' + o.id });
  all.sort((a, b) => a.o._t0 - b.o._t0);
  const ends = Array(R.lanes).fill(-1), map = new Map();
  for (const { o, k } of all) {
    let l = ends.findIndex((e) => e <= o._t0 + 1e-6);
    if (l < 0) l = ends.indexOf(Math.min(...ends));
    ends[l] = Math.max(o._t1, o._t0 + 0.4); map.set(k, l);
  }
  laneCache = { v: ctx.store.version, map };
  return map;
}

function thumb(shot) {
  const key = shot.id + '|' + ctx.store.rev;
  let t = thumbs.get(key);
  if (!t) {
    const img = new Image(); t = { img, ok: false };
    img.onload = () => { t.ok = true; requestDraw(); };
    img.onerror = () => { t.err = true; };
    img.src = api.url(api.thumbUrl(ctx.pid, shot.id, ctx.store.rev));
    thumbs.set(key, t);
    if (thumbs.size > 400) thumbs.delete(thumbs.keys().next().value);
  }
  return t.ok ? t.img : null;
}

function pill(text, x, y, bg, fg = '#fff') {
  c.font = '10px sans-serif';
  const w = c.measureText(text).width + 8;
  c.fillStyle = bg; c.beginPath(); c.roundRect(x, y, w, 13, 6); c.fill();
  c.fillStyle = fg; c.textBaseline = 'middle'; c.fillText(text, x + 4, y + 7);
  return w;
}
function lock(x, y, col = '#f4b400') {
  c.fillStyle = col; c.fillRect(x, y + 5, 9, 7);
  c.strokeStyle = col; c.lineWidth = 1.6; c.beginPath(); c.arc(x + 4.5, y + 5, 3, Math.PI, 0); c.stroke();
}

function draw() {
  drawQueued = false;
  const d = ctx.store.draft;
  if (!c || !d) return;
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.clearRect(0, 0, W, Ht);
  c.textBaseline = 'middle';
  const t0 = view.t0, t1 = xToTime(W, view);
  const shots = d.shots;
  // ---- ruler
  c.fillStyle = '#12151c'; c.fillRect(0, Y.ruler, W, R.ruler);
  const steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
  const step = steps.find((s) => s * view.pps >= 70) || 600;
  c.font = '10px ui-monospace, Menlo, monospace'; c.fillStyle = '#8a93a6'; c.strokeStyle = '#2a3040'; c.lineWidth = 1;
  for (let t = Math.ceil(t0 / step) * step; t <= t1; t += step) {
    const x = Math.round(X(t)) + 0.5;
    c.beginPath(); c.moveTo(x, Y.ruler + 12); c.lineTo(x, Y.ruler + R.ruler); c.stroke();
    c.fillText(fmtTime(t).replace(/\.00$/, ''), x + 3, Y.ruler + 8);
  }
  // ---- chapters
  const chaps = ctx.store.timing?.chapters || [];
  chaps.forEach((ch, i) => {
    const x0 = X(ch.start), x1 = X(ch.end);
    if (x1 < 0 || x0 > W) return;
    c.fillStyle = i % 2 ? '#1d2433' : '#222b3d'; c.fillRect(x0, Y.chap, x1 - x0 - 1, R.chap);
    c.fillStyle = '#c3cbe0'; c.font = 'bold 10px sans-serif';
    c.save(); c.beginPath(); c.rect(x0, Y.chap, x1 - x0, R.chap); c.clip(); c.fillText(ch.name, Math.max(x0, 0) + 6, Y.chap + 10); c.restore();
  });
  // ---- shots
  const first = Math.max(0, shotIndexAt(shots, t0));
  for (let i = first; i < shots.length && shots[i]._t0 <= t1; i++) {
    const s = shots[i];
    const x0 = X(s._t0), x1 = X(s._t1), w = x1 - x0;
    const sel = ctx.store.sel.shot === s.id;
    c.fillStyle = intentHsl(s.intent, 38, sel ? 30 : 24); c.fillRect(x0, Y.shot, Math.max(1, w - 1), R.shot);
    c.save(); c.beginPath(); c.rect(x0, Y.shot, Math.max(1, w - 1), R.shot); c.clip();
    if (w > 60) {
      const img = thumb(s);
      if (img) { const th = R.shot - 18, tw = Math.min(w - 6, th * 16 / 9); c.drawImage(img, x0 + 3, Y.shot + 16, tw, th); }
    }
    if (w > 28) {
      const bw = pill(s.technique, x0 + 3, Y.shot + 2, 'rgba(0,0,0,.6)');
      if (w > bw + 36) { c.fillStyle = 'rgba(255,255,255,.7)'; c.font = '10px sans-serif'; c.fillText(s.id, x0 + bw + 8, Y.shot + 9); }
    }
    if (s.locked && w > 14) lock(x0 + w - 14, Y.shot + 2);
    if (s.source === 'human' && w > 22) { c.fillStyle = '#4f9cff'; c.beginPath(); c.arc(x0 + w - 22, Y.shot + 8, 3, 0, 7); c.fill(); }
    else if (s.source === 'agent' && w > 22) { c.fillStyle = '#b79cff'; c.beginPath(); c.arc(x0 + w - 22, Y.shot + 8, 3, 0, 7); c.fill(); }
    if (s.transition_in && w > 30) { c.fillStyle = '#ffd666'; c.fillText('TR', x0 + 3, Y.shot + R.shot - 7); }
    c.restore();
    if (sel) { c.strokeStyle = '#4f9cff'; c.lineWidth = 2; c.strokeRect(x0 + 1, Y.shot + 1, Math.max(1, w - 3), R.shot - 2); }
  }
  // ---- overlays
  c.fillStyle = '#10131a'; c.fillRect(0, Y.ov, W, R.ovH);
  const lm = lanes();
  for (const s of shots) {
    if (s._t1 < t0 || s._t0 > t1) continue;
    for (const o of s.overlays || []) {
      const x0 = X(o._t0), x1 = Math.max(x0 + 6, X(o._t1));
      if (x1 < 0 || x0 > W) continue;
      const y = Y.ov + 1 + (lm.get(s.id + '/' + o.id) || 0) * R.lane;
      const sel = ctx.store.sel.overlay === o.id && ctx.store.sel.shot === s.id;
      c.fillStyle = intentHsl(o.intent, 50, sel ? 42 : 34); c.beginPath(); c.roundRect(x0, y, x1 - x0, R.lane - 2, 4); c.fill();
      c.strokeStyle = sel ? '#fff' : (o.locked ? '#f4b400' : 'rgba(0,0,0,.4)'); c.lineWidth = sel ? 1.6 : 1; c.stroke();
      if (x1 - x0 > 26) { c.save(); c.beginPath(); c.rect(x0, y, x1 - x0, R.lane); c.clip(); c.fillStyle = '#fff'; c.font = '10px sans-serif'; c.fillText(o.technique, x0 + 4, y + 7); c.restore(); }
    }
  }
  // ---- words
  c.fillStyle = '#10131a'; c.fillRect(0, Y.words, W, R.words);
  const words = ctx.words();
  if (view.pps >= 26) {
    const w0 = Math.max(0, wordIndexAt(words, t0) - 1), cur = wordIndexAt(words, ctx.t);
    c.font = '11px sans-serif';
    for (let i = w0; i < words.length && words[i].s <= t1; i++) {
      const x0 = X(words[i].s), x1 = X(words[i].e);
      c.fillStyle = i === cur ? '#1c3b63' : '#1a2030'; c.fillRect(x0, Y.words + 1, Math.max(2, x1 - x0 - 1), R.words - 2);
      c.save(); c.beginPath(); c.rect(x0, Y.words, Math.max(2, x1 - x0), R.words); c.clip();
      c.fillStyle = i === cur ? '#9fd0ff' : '#aab3c8'; c.fillText(words[i].w, x0 + 2, Y.words + 8); c.restore();
    }
  } else { c.fillStyle = '#4a5368'; c.font = '10px sans-serif'; c.fillText('phóng to để thấy từng từ (Ctrl + cuộn)', 8, Y.words + 8); }
  // ---- waveform
  c.fillStyle = '#0e1016'; c.fillRect(0, Y.wave, W, R.wave);
  if (waves?.peaks?.length) {
    const n = waves.peaks.length, per = waves.duration / n, mid = Y.wave + R.wave / 2;
    c.fillStyle = '#3d7bc4';
    for (let x = 0; x < W; x++) {
      const a = Math.max(0, Math.floor((xToTime(x, view)) / per)), b = Math.min(n - 1, Math.max(a, Math.floor(xToTime(x + 1, view) / per)));
      let mx = 0; for (let k = a; k <= b; k++) if (waves.peaks[k] > mx) mx = waves.peaks[k];
      const hh = Math.max(1, mx * (R.wave - 4)); c.fillRect(x, mid - hh / 2, 1, hh);
    }
  }
  if (ctx.noAudio) { c.fillStyle = '#6b748a'; c.font = '11px sans-serif'; c.fillText('Dự án này chưa có file âm thanh (không có sóng âm, phát im lặng)', 10, Y.wave + R.wave / 2); }
  // ---- guide (snap line while dragging)
  if (guide != null) { c.strokeStyle = '#ffd666'; c.setLineDash([4, 3]); c.beginPath(); c.moveTo(X(guide) + 0.5, Y.shot); c.lineTo(X(guide) + 0.5, Y.wave + R.wave); c.stroke(); c.setLineDash([]); }
  // ---- playhead
  const px = X(ctx.t);
  if (px >= -4 && px <= W + 4) {
    c.strokeStyle = '#ff5c5c'; c.lineWidth = 1.5; c.beginPath(); c.moveTo(px, 0); c.lineTo(px, Y.mini); c.stroke();
    c.fillStyle = '#ff5c5c'; c.beginPath(); c.moveTo(px - 5, 0); c.lineTo(px + 5, 0); c.lineTo(px, 8); c.fill();
  }
  // ---- minimap
  const mw = W - 8, mk = mw / dur();
  c.fillStyle = '#0a0c10'; c.fillRect(0, Y.mini - 2, W, R.mini + 4);
  for (const s of shots) { c.fillStyle = intentHsl(s.intent, 45, 38); c.fillRect(4 + s._t0 * mk, Y.mini, Math.max(1, (s._t1 - s._t0) * mk - 0.5), R.mini - 8); }
  c.fillStyle = 'rgba(255,255,255,.06)'; c.fillRect(4 + t0 * mk, Y.mini - 1, (t1 - t0) * mk, R.mini - 6);
  c.strokeStyle = '#8a93a6'; c.lineWidth = 1; c.strokeRect(4 + t0 * mk + 0.5, Y.mini - 0.5, (t1 - t0) * mk, R.mini - 6);
  c.fillStyle = '#ff5c5c'; c.fillRect(4 + ctx.t * mk, Y.mini - 2, 1.5, R.mini - 4);
  $('#tl-info').textContent = `${shots.length} shot | ${shots.reduce((n, s) => n + (s.overlays || []).length, 0)} lớp phủ | ${words.length} từ | ${view.pps.toFixed(1)} px/s`;
}

// ---- hit testing
function band(y) {
  if (y >= Y.mini - 2) return 'mini';
  if (y >= Y.shot && y < Y.shot + R.shot) return 'shot';
  if (y >= Y.ov && y < Y.ov + R.ovH) return 'ov';
  return 'other';
}
function hitBoundary(x) {
  const shots = ctx.store.draft.shots, t = xToTime(x, view);
  const i = shotIndexAt(shots, t);
  for (const k of [i, i + 1]) if (k > 0 && k < shots.length && Math.abs(X(shots[k]._t0) - x) <= 5) return k;
  return -1;
}
function overlayEdge(x, hit) {
  const x0 = X(hit.ov._t0), x1 = Math.max(x0 + 6, X(hit.ov._t1)), w = x1 - x0, g = Math.min(6, w / 3);
  return x <= x0 + g ? 'l' : x >= x1 - g ? 'r' : null;
}
function hitOverlay(x, y) {
  const lm = lanes(), lane = Math.floor((y - Y.ov - 1) / R.lane), t = xToTime(x, view);
  let best = null;
  for (const s of ctx.store.draft.shots) {
    if (s._t0 > t + 1 || s._t1 < t - 1) continue;
    for (const o of s.overlays || []) {
      if ((lm.get(s.id + '/' + o.id) || 0) !== lane) continue;
      if (x >= X(o._t0) - 1 && x <= Math.max(X(o._t0) + 6, X(o._t1)) + 1) best = { shot: s, ov: o };
    }
  }
  return best;
}

export function seek(t) { ctx.t = clamp(t, 0, dur()); bus.emit('time', ctx.t); requestDraw(); }
export function ensureVisible(t) {
  const x = X(t);
  if (x < 20 || x > W - 20) { view.t0 = t - (W / view.pps) * 0.2; clampView(); requestDraw(); }
}
function zoomAt(factor, ax) {
  const tA = xToTime(ax, view);
  view.pps = clamp(view.pps * factor, minPps(), 500);
  view.t0 = tA - ax / view.pps; clampView(); requestDraw();
}

let drag = null;
function pos(e) { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
function installCanvas() {
  cv.addEventListener('pointerdown', (e) => {
    if (!ctx.store.draft || e.button !== 0) return;
    const [x, y] = pos(e);
    const b = band(y), st = ctx.store, shots = st.draft.shots;
    cv.setPointerCapture(e.pointerId);
    if (b === 'mini') {
      const mk = (W - 8) / dur();
      const center = (x - 4) / mk; view.t0 = center - W / view.pps / 2; clampView(); requestDraw();
      drag = { kind: 'mini' }; return;
    }
    if (b === 'shot') {
      const k = hitBoundary(x);
      if (k > 0) { drag = { kind: 'boundary', idx: k, id: shots[k].id }; st.select(shots[k].id); return; }
      const s = shots[shotIndexAt(shots, xToTime(x, view))];
      st.select(s.id); seek(xToTime(x, view)); drag = { kind: 'scrub' }; return;
    }
    if (b === 'ov') {
      const hit = hitOverlay(x, y);
      if (hit) {
        st.select(hit.shot.id, hit.ov.id); bus.emit('tab', 'overlay');
        const edge = overlayEdge(x, hit);
        if (edge) { drag = { kind: 'ovedge', id: hit.ov.id, shotId: hit.shot.id, edge }; return; }
        drag = { kind: 'overlay', id: hit.ov.id, shotId: hit.shot.id, off: xToTime(x, view) - hit.ov._t0, x0: x, moved: false }; return;
      }
    }
    seek(xToTime(x, view)); drag = { kind: 'scrub' };
    const s = shots[shotIndexAt(shots, ctx.t)]; if (s && st.sel.shot !== s.id) st.select(s.id);
  });
  cv.addEventListener('pointermove', (e) => {
    if (!ctx.store.draft) return;
    const [x, y] = pos(e);
    if (!drag) {
      const b = band(y);
      const oh = b === 'ov' ? hitOverlay(x, y) : null;
      cv.style.cursor = b === 'shot' && hitBoundary(x) > 0 ? 'ew-resize' : oh ? (overlayEdge(x, oh) ? 'ew-resize' : 'grab') : 'default';
      return;
    }
    const st = ctx.store, words = ctx.words();
    if (drag.kind === 'mini') { const mk = (W - 8) / dur(); view.t0 = (x - 4) / mk - W / view.pps / 2; clampView(); requestDraw(); }
    else if (drag.kind === 'scrub') { seek(xToTime(clamp(x, 0, W), view)); const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)]; if (s && st.sel.shot !== s.id) st.select(s.id); }
    else if (drag.kind === 'boundary') {
      const t = xToTime(x, view);
      st.commit('Kéo ranh giới shot', (d) => E.moveBoundary(d, d.shots.findIndex((s) => s.id === drag.id), t, words, e.altKey), { coalesce: 'bd:' + drag.id });
      guide = st.shotById(drag.id)?._t0 ?? null; requestDraw();
    } else if (drag.kind === 'ovedge') {
      const t = xToTime(x, view);
      E.scope.shot = drag.shotId;
      st.commit('Kéo cạnh lớp phủ', (d) => { const f = E.findOverlay(d, drag.id); if (f) E.resizeOverlay(d, f.shot, f.ov, drag.edge, t, words, e.altKey); }, { coalesce: 'oe:' + drag.shotId + drag.id });
      guide = drag.edge === 'l' ? st.overlay?._t0 ?? null : st.overlay?._t1 ?? null; requestDraw();
    } else if (drag.kind === 'overlay') {
      if (!drag.moved && Math.abs(x - drag.x0) < 3) return;
      drag.moved = true; cv.style.cursor = 'grabbing';
      const t = xToTime(x, view) - drag.off;
      E.scope.shot = drag.shotId;
      st.commit('Kéo lớp phủ', (d) => { const f = E.findOverlay(d, drag.id); if (f) E.moveOverlay(d, f.shot, f.ov, t, words, e.altKey); }, { coalesce: 'ov:' + drag.shotId + drag.id });
    }
  });
  const end = () => { drag = null; guide = null; requestDraw(); };
  cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
  cv.addEventListener('wheel', (e) => {
    e.preventDefault();
    const [x] = pos(e);
    if (e.ctrlKey || e.metaKey) zoomAt(Math.exp(-e.deltaY * 0.0025), x);
    else { view.t0 += (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY) ? (e.deltaX || e.deltaY) : e.deltaY) / view.pps; clampView(); requestDraw(); }
  }, { passive: false });
  cv.addEventListener('dblclick', (e) => { const [x, y] = pos(e); if (band(y) === 'shot') bus.emit('tab', 'shot'); });

}

export function initTimeline(viewRoot, viewScope) {
  root = viewRoot; scope = viewScope; alive = true;
  wrap = $('#timeline', root); cv = $('#tl-canvas', root);
  drag = null; hover = null; guide = null; waves = null; drawQueued = false; laneCache = { v: -1, map: new Map() }; view.t0 = 0; view.pps = 10;
  scope.add(() => { alive = false; });
  installCanvas();
  window.__tl = { view, Y, R, X, drawNow: () => draw(), get W() { return W; } };
  const ro = new ResizeObserver(resize); ro.observe(wrap); scope.add(() => ro.disconnect());
  ctx.store.on((kind) => { if (kind === 'load') { view.t0 = 0; view.pps = minPps(); clampView(); loadWave(); } requestDraw(); });
  bus.on('time', requestDraw); bus.on('tick', () => { ensureVisible(ctx.t); requestDraw(); });
  $('#tl-zin', root).onclick = () => zoomAt(1.6, W / 2);
  $('#tl-zout', root).onclick = () => zoomAt(1 / 1.6, W / 2);
  $('#tl-fit', root).onclick = () => { view.pps = minPps(); view.t0 = 0; clampView(); requestDraw(); };
  resize();
}
export function fitView() { view.pps = minPps(); view.t0 = 0; clampView(); requestDraw(); }
export function zoomToShowWords() { view.pps = Math.max(view.pps, 140); clampView(); requestDraw(); }
async function loadWave() {
  waves = null; ctx.noAudio = false;
  try { waves = await api.waveform(ctx.pid, 4000); } catch (e) { waves = null; ctx.noAudio = e.status === 404; }
  bus.emit('audio-state', !ctx.noAudio);
  requestDraw();
}
export { toggleLock };
