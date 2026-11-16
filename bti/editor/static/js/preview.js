// Preview pane: engine still (POST /frame with the draft), draggable camera boxes and overlay handles.
import { api } from './api.js';
import { ctx, bus, primaryAsset } from './ctx.js';
import { $, svg, debounce, fmtTime } from './util.js';
import { DEBOUNCE_MS, MOCK } from './config.js';
import { cameraLists, cameraAt, engineFitCamera, cameraToBox, boxToCamera, fixAspect, makeMapping, fitCamera, round, shotIndexAt, clone } from './logic.js';
import { setParam, commitShot } from './actions.js';
import { paintAsset } from './placeholder.js';

const canvasEl = $('#frame'), svgEl = $('#handles'), box = $('#stage-box'), stage = $('#stage');
const sourceChk = $('#view-source'), regionsChk = $('#view-regions');
let seq = 0, shown = 0, lastBitmap = null, W = 640, H = 360;
let frozen = null; // mapping frozen during a drag
let srcImg = null, srcImgKey = '';
let lastReq = 0;

function fit() {
  const aw = stage.clientWidth - 16, ah = stage.clientHeight - 16;
  W = Math.max(160, Math.min(aw, (ah * 16) / 9)); H = (W * 9) / 16;
  box.style.width = W + 'px'; box.style.height = H + 'px';
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  drawBase(); drawHandles();
}

// ---- frame loading
async function refresh() {
  if (!ctx.store.draft) return;
  const mySeq = ++seq;
  const t = ctx.t;
  if (sourceChk.checked) return drawBase();
  const stateEl = $('#frame-state');
  try {
    stateEl.textContent = 'đang dựng...';
    const blob = await api.frame(ctx.pid, t, 960, ctx.draftPlain());
    if (mySeq !== seq) return; // out of date: drop
    const bmp = await createImageBitmap(blob);
    if (mySeq !== seq) return;
    lastBitmap = bmp; shown = mySeq;
    stateEl.textContent = `khung ${fmtTime(t)}`;
    drawBase();
  } catch (e) {
    if (mySeq !== seq) return;
    stateEl.textContent = 'lỗi dựng khung: ' + (e.status || e.message);
  }
}
const refreshDebounced = debounce(refresh, DEBOUNCE_MS);
export const requestFrame = () => { refreshDebounced(); };
export function requestFrameThrottled(minMs = 250) {
  const now = performance.now();
  if (now - lastReq >= minMs) { lastReq = now; refresh(); }
}

function sourceImage(key, asset) {
  if (MOCK) return null;
  if (srcImgKey !== key) {
    srcImgKey = key; srcImg = new Image();
    srcImg.onload = () => { drawBase(); drawHandles(); };
    srcImg.src = api.fileUrl(ctx.pid, asset.file);
  }
  return srcImg;
}

function currentMapping() {
  const shot = currentShot();
  if (!shot) return null;
  const pa = primaryAsset(shot);
  if (!pa) return null;
  const canvas = ctx.canvasDims();
  if (sourceChk.checked) return { m: makeMapping(fitCamera(pa.asset, canvas), canvas, { W, H }), pa, mode: 'source' };
  const keys = mainCamera(shot);
  if (keys) return { m: makeMapping(cameraAt(keys, ctx.t) || keys[0], canvas, { W, H }), pa, mode: 'camera' };
  // a camera technique without a camera key: the engine shows the whole image at 95.5 % of the frame height
  if (ctx.tech(shot.technique)?.params.some((p) => p.type === 'camera')) return { m: makeMapping(engineFitCamera(pa.asset, canvas), canvas, { W, H }), pa, mode: 'static' };
  return { m: null, pa, mode: 'none' };
}
const mainCamera = (shot) => (cameraLists(shot.params).find((l) => l.name === 'camera') || {}).keys || null;
function currentShot() { return ctx.store.shot || ctx.store.draft.shots[shotIndexAt(ctx.store.draft.shots, ctx.t)]; }

function drawBase() {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvasEl.width = Math.round(W * dpr); canvasEl.height = Math.round(H * dpr);
  const c = canvasEl.getContext('2d');
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
  if (!ctx.store.draft) return;
  if (sourceChk.checked) {
    const cm = currentMapping();
    if (!cm) { c.fillStyle = '#8a93a6'; c.font = '14px sans-serif'; c.fillText('Shot này không có ảnh nguồn', 20, 30); return; }
    const canvas = ctx.canvasDims(), cam = fitCamera(cm.pa.asset, canvas);
    const img = sourceImage(cm.pa.key, cm.pa.asset);
    if (img && img.complete && img.naturalWidth) {
      const [x0, y0] = cm.m.toScreen(0, 0);
      c.drawImage(img, x0, y0, cm.pa.asset.width * cm.m.k, cm.pa.asset.height * cm.m.k);
    } else paintAsset(c, cm.pa.key, cm.pa.asset, cam, canvas, W, H);
    return;
  }
  if (lastBitmap) c.drawImage(lastBitmap, 0, 0, W, H);
  else { c.fillStyle = '#8a93a6'; c.font = '14px sans-serif'; c.fillText('Đang chờ khung hình từ engine...', 20, 30); }
}

// ---- handles
const COLORS = ['#4f9cff', '#f4b400', '#3ecf8e'];
function drawHandles() {
  svgEl.replaceChildren();
  const d = ctx.store.draft;
  svgEl.classList.toggle('picking', !!ctx.pick);
  const note = $('#map-note');
  if (!d) return;
  const shot = currentShot();
  const cm = currentMapping();
  const m = frozen?.m || cm?.m;
  note.textContent = !cm ? 'Shot không có ảnh nguồn.' : !m ? 'Không có ánh xạ camera: dùng ô số trong Shot/Lớp phủ, hoặc bật "Ảnh gốc".' : cm.mode === 'source' ? 'Chế độ ảnh gốc.' : '';
  if (!m) return;
  const canvas = ctx.canvasDims();
  const asset = cm.pa.asset;
  const to = m.toScreen;
  // regions (faint): only on request, while picking, or while an overlay with a point parameter is selected
  const ovSel = ctx.store.overlay;
  const wantRegions = regionsChk.checked || !!ctx.pick || (ovSel && ctx.tech(ovSel.technique)?.params.some((p) => p.type === 'point' || p.type === 'points'));
  if (wantRegions) for (const [name, r] of Object.entries(asset.regions || {})) {
    const [sx, sy] = to(r.x, r.y);
    const rrx = r.rx ?? 60, rry = r.ry ?? 60;   // a region may be only a point
    svgEl.append(svg('ellipse', { cx: sx, cy: sy, rx: rrx * m.k, ry: rry * m.k, fill: 'none', stroke: 'rgba(255,255,255,.35)', 'stroke-dasharray': '3 4' }));
    if (ctx.pick || regionsChk.checked) { const t = svg('text', { x: sx + 4, y: sy - rry * m.k - 4, class: 'rname' }); t.textContent = name; svgEl.append(t); }
  }
  // camera boxes of the selected shot
  const camName = (cameraLists(shot.params).find((l) => l.name === 'camera') || {}).name;
  const keys = mainCamera(shot);
  if (keys) keys.forEach((k, i) => {
    const b = cameraToBox(k, canvas);
    const [x, y] = to(b.x, b.y);
    const w = b.w * m.k, hgt = b.h * m.k;
    const col = i === 0 ? COLORS[0] : i === keys.length - 1 ? COLORS[2] : COLORS[1];
    const r = svg('rect', { x, y, width: w, height: hgt, class: 'hbox' + (i === keys.length - 1 ? ' end' : ''), style: `stroke:${col}` });
    const label = svg('g', { class: 'kleg' });   // legend in the top-left corner: never collides with region names
    label.append(svg('rect', { x: 6, y: 6 + i * 17, width: 96, height: 15, rx: 3, class: 'kbg' }), svg('rect', { x: 9, y: 9 + i * 17, width: 9, height: 9, fill: col }));
    const lt = svg('text', { x: 22, y: 17 + i * 17, class: 'klab' }); lt.textContent = `K${i + 1}  zoom ${round(k.zoom, 3)}`; label.append(lt);
    const knob = svg('rect', { x: x + w - 7, y: y + hgt - 7, width: 14, height: 14, class: 'hknob' });
    svgEl.append(r, label, knob);
    dragger(r, (ev0) => ({ start: clone(k), ev0 }), (st, dx, dy) => {
      setCam(shot.id, i, { ...st.start, cx: st.start.cx + dx / m.k, cy: st.start.cy + dy / m.k });
    });
    dragger(knob, (ev0) => ({ start: clone(k), ev0 }), (st, dx) => {
      const b0 = cameraToBox(st.start, canvas);
      let nb = fixAspect({ x: b0.x, y: b0.y, w: Math.max(40, b0.w + dx / m.k), h: b0.h }, canvas);
      nb = { ...nb, y: b0.y };
      const c = boxToCamera(nb, canvas);
      setCam(shot.id, i, { ...st.start, ...c });
    });
  });
  // overlay handles
  const ov = ctx.store.overlay;
  if (ov) itemHandles(ov, 'overlay', asset, m, to);
  else if (shot) itemHandles(shot, 'shot', asset, m, to);
}

function setCam(shotId, i, k) {
  frozenKeep();
  commitShot('Kéo khung camera', shotId, (s) => {
    s.params.camera[i] = { ...s.params.camera[i], cx: round(k.cx, 1), cy: round(k.cy, 1), zoom: round(k.zoom, 4) };
  }, 'cam' + i);
}
const frozenKeep = () => { if (!frozen) frozen = currentMapping(); };

function resolvePoint(v, asset) {
  if (Array.isArray(v)) return v;
  if (typeof v === 'string' && asset.regions?.[v]) return [asset.regions[v].x, asset.regions[v].y];
  return null;
}

function itemHandles(ov, kind, asset, m, to) {
  const tech = ctx.tech(ov.technique);
  if (!tech) return;
  const params = ov.params || {};
  const radDef = tech.params.find((p) => p.name === 'radius' && p.type === 'number');
  const hasR = tech.params.some((p) => p.name === 'rx') && tech.params.some((p) => p.name === 'ry');
  const set = (name, v) => { frozenKeep(); setParam(kind, ov.id, name, v); };
  for (const p of tech.params) {
    const val = p.name in params ? params[p.name] : p.default;
    if ((p.type === 'point' || p.type === 'points') && (/canvas|screen/i.test(p.unit || '') || p.name.startsWith('screen'))) continue; // canvas pixels, not source pixels
    if (p.type === 'points' && Array.isArray(val)) {
      val.forEach((v, i) => {
        const pt = resolvePoint(v, asset);
        if (!pt) return;
        const [sx, sy] = to(pt[0], pt[1]);
        const c = svg('circle', { cx: sx, cy: sy, r: 8, class: 'hpt' });
        const t = svg('text', { x: sx + 10, y: sy - 8, class: 'rname' }); t.textContent = String(i + 1);
        svgEl.append(c, t);
        dragger(c, () => ({ pt, list: clone(val) }), (st, dx, dy) => { const n = clone(st.list); n[i] = [Math.round(st.pt[0] + dx / m.k), Math.round(st.pt[1] + dy / m.k)]; set(p.name, n); });
      });
    } else if (p.type === 'point') {
      const pt = resolvePoint(val, asset);
      if (!pt) continue;
      const [sx, sy] = to(pt[0], pt[1]);
      if (hasR) {
        const rx = (params.rx ?? tech.params.find((q) => q.name === 'rx').default ?? 100), ry = (params.ry ?? tech.params.find((q) => q.name === 'ry').default ?? 100);
        const e = svg('ellipse', { cx: sx, cy: sy, rx: rx * m.k, ry: ry * m.k, class: 'hell' });
        const kx = svg('circle', { cx: sx + rx * m.k, cy: sy, r: 6, class: 'hknob' });
        const ky = svg('circle', { cx: sx, cy: sy + ry * m.k, r: 6, class: 'hknob' });
        svgEl.append(e, kx, ky);
        dragger(e, () => ({ pt }), (st, dx, dy) => set(p.name, [Math.round(st.pt[0] + dx / m.k), Math.round(st.pt[1] + dy / m.k)]));
        dragger(kx, () => ({ rx }), (st, dx) => set('rx', Math.max(5, Math.round(st.rx + dx / m.k))));
        dragger(ky, () => ({ ry }), (st, dx, dy) => set('ry', Math.max(5, Math.round(st.ry + dy / m.k))));
      }
      if (!hasR && radDef) {
        const rad = params.radius ?? radDef.default ?? 150;
        const e = svg('circle', { cx: sx, cy: sy, r: rad * m.k, class: 'hell' });
        const kr = svg('circle', { cx: sx + rad * m.k, cy: sy, r: 6, class: 'hknob' });
        svgEl.append(e, kr);
        dragger(e, () => ({ pt }), (st, dx, dy) => set(p.name, [Math.round(st.pt[0] + dx / m.k), Math.round(st.pt[1] + dy / m.k)]));
        dragger(kr, () => ({ rad }), (st, dx) => set('radius', Math.max(5, Math.round(st.rad + dx / m.k))));
      }
      const c = svg('circle', { cx: sx, cy: sy, r: 7, class: 'hpt' });
      const t = svg('text', { x: sx + 10, y: sy - 8 }); t.textContent = `${p.name}${typeof val === 'string' ? ': ' + val : ''}`;
      svgEl.append(c, t);
      dragger(c, () => ({ pt }), (st, dx, dy) => set(p.name, [Math.round(st.pt[0] + dx / m.k), Math.round(st.pt[1] + dy / m.k)]));
    } else if (p.type === 'box' && val && typeof val === 'object') {
      const [x, y] = to(val.x, val.y);
      const r = svg('rect', { x, y, width: val.w * m.k, height: val.h * m.k, class: 'hbox', style: 'stroke:#f4b400' });
      const knob = svg('rect', { x: x + val.w * m.k - 7, y: y + val.h * m.k - 7, width: 14, height: 14, class: 'hknob' });
      svgEl.append(r, knob);
      dragger(r, () => ({ v: clone(val) }), (st, dx, dy) => set(p.name, { ...st.v, x: Math.round(st.v.x + dx / m.k), y: Math.round(st.v.y + dy / m.k) }));
      dragger(knob, () => ({ v: clone(val) }), (st, dx, dy) => set(p.name, { ...st.v, w: Math.max(10, Math.round(st.v.w + dx / m.k)), h: Math.max(10, Math.round(st.v.h + dy / m.k)) }));
    }
  }
}

function dragger(el, begin, move) {
  el.addEventListener('pointerdown', (e) => {
    if (ctx.pick) return;
    e.preventDefault(); e.stopPropagation();
    const st = begin(e); const x0 = e.clientX, y0 = e.clientY;
    const sc = W / box.getBoundingClientRect().width;
    // listeners live on window: the handle element is rebuilt on every edit
    const mv = (ev) => move(st, (ev.clientX - x0) * sc, (ev.clientY - y0) * sc);
    const up = () => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); frozen = null; drawHandles(); };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up);
  });
}

// pick mode: click on the preview to get a point (region name if inside one, Shift = raw x,y)
svgEl.addEventListener('pointerdown', (e) => {
  if (!ctx.pick) return;
  const cm = currentMapping();
  if (!cm?.m) { ctx.pick = null; drawHandles(); return; }
  const r = svgEl.getBoundingClientRect();
  const [x, y] = cm.m.toSource(((e.clientX - r.left) * W) / r.width, ((e.clientY - r.top) * H) / r.height);
  let value = [Math.round(x), Math.round(y)];
  if (!e.shiftKey) for (const [name, rg] of Object.entries(cm.pa.asset.regions || {})) if (((x - rg.x) / rg.rx) ** 2 + ((y - rg.y) / rg.ry) ** 2 <= 1) { value = name; break; }
  const p = ctx.pick; ctx.pick = null; p.cb(value); drawHandles();
});
bus.on('pick', () => { if (ctx.pick && !sourceChk.checked && currentMapping()?.mode === 'none') sourceChk.checked = true; drawBase(); drawHandles(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ctx.pick) { ctx.pick = null; drawHandles(); } });

export function initPreview() {
  new ResizeObserver(fit).observe(stage);
  sourceChk.addEventListener('change', () => { refresh(); drawBase(); drawHandles(); });
  regionsChk.addEventListener('change', drawHandles);
  let lastSel = '';
  ctx.store.on((kind) => {
    const sig = ctx.store.sel.shot + '|' + ctx.store.sel.overlay;
    if (kind === 'select' || kind === 'load' || sig !== lastSel) { lastSel = sig; drawBase(); }
    drawHandles();
    if (kind !== 'select') requestFrame();
  });
  bus.on('time', () => { if (!ctx.playing) requestFrame(); drawHandles(); if (sourceChk.checked) drawBase(); });
  bus.on('tick', () => { requestFrameThrottled(250); });
  fit();
  refresh();
}
