// Preview pane: engine still (POST /frame with the draft), draggable camera boxes and overlay handles.
import { api } from './api.js';
import { ctx, bus, primaryAsset } from './ctx.js';
import { $, svg, debounce, fmtTime } from './util.js';
import { DEBOUNCE_MS, MOCK } from './config.js';
import { cameraLists, cameraAt, engineFitCamera, cameraToBox, boxToCamera, fixAspect, fitCamera, round, shotIndexAt, clone } from './logic.js';
import { makeSpaces, dragPoint, boxToRect, paramSpace, splitSpace, resolvePoint, pickValue } from './coords.js';
import { setParam, commitShot } from './actions.js';
import { paintAsset } from './placeholder.js';

// DOM is looked up when the view is mounted (initPreview), never at import time: the module outlives the view.
let root = null, scope = null, alive = false;
let canvasEl, svgEl, box, stage, sourceChk, regionsChk;
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
  if (!alive || !ctx.store.draft) return;
  const mySeq = ++seq;
  const t = ctx.t;
  if (sourceChk.checked) return drawBase();
  const stateEl = $('#frame-state', root);
  try {
    stateEl.textContent = 'đang dựng...';
    const blob = await api.frame(ctx.pid, t, 960, ctx.draftPlain());
    if (mySeq !== seq) return; // out of date: drop
    const bmp = await createImageBitmap(blob);
    if (mySeq !== seq) return;
    lastBitmap = bmp; shown = mySeq;
    const inc = incompleteAt(t);
    stateEl.textContent = `khung ${fmtTime(t)}` + (inc ? ` | khung tạm, ${inc}` : '');
    stateEl.classList.toggle('warn', !!inc);
    drawBase();
  } catch (e) {
    if (mySeq !== seq) return;
    stateEl.classList.add('warn');
    stateEl.textContent = frameError(e, t);
  }
}
/** What is incomplete at time t (the shot and its overlays): "thiếu: right (s0031)". */
function incompleteAt(t) {
  const d = ctx.store.draft;
  if (!d) return '';
  const sh = d.shots[shotIndexAt(d.shots, t)];
  if (!sh) return '';
  const parts = [];
  const a = ctx.incompleteOf(sh.id); if (a) parts.push(`${sh.id}: ${a.join(', ')}`);
  for (const o of sh.overlays || []) { const b = ctx.incompleteOf(sh.id, o.id); if (b) parts.push(`${sh.id}/${o.id}: ${b.join(', ')}`); }
  return parts.length ? 'thiếu ' + parts.join('; ') : '';
}
/** The preview says WHY a frame could not be built, never just "500" (U2-012). */
export function frameError(e, t) {
  const detail = e?.body?.detail ?? e?.body;
  const text = typeof detail === 'string' ? detail : detail?.message || detail?.reason || '';
  const inc = incompleteAt(t);
  if (inc) return `Chưa dựng được khung: ${inc}`;
  if (text) return `Lỗi dựng khung: ${text}`;
  return e?.status >= 500 ? `Máy chủ không dựng được khung (${e.status}). Xem tab Lỗi.` : 'Lỗi dựng khung: ' + (e?.status || e?.message);
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

/** The mapping of the picture on screen, from the shot UNDER THE PLAYHEAD (the still shows that moment, so the handles must too).
 * S (see coords.js) is always there: canvas and frame space need no picture. Source space needs a camera (or the "Ảnh gốc" view). */
function currentMapping() {
  const shot = playheadShot();
  if (!shot) return null;
  const pa = primaryAsset(shot);
  const canvas = ctx.canvasDims(), view = { W, H };
  const mk = (cam, canvasOk, mode) => ({ S: makeSpaces({ canvas, view, cam, canvasOk }), pa, shot, mode });
  if (sourceChk.checked) return mk(pa ? fitCamera(pa.asset, canvas) : null, false, 'source');   // the picture shown is the source image, not the frame
  const keys = mainCamera(shot);
  if (keys && pa) return mk(cameraAt(keys, ctx.t) || keys[0], true, 'camera');
  // a camera technique without a camera key: the engine shows the whole image at 95.5 % of the frame height
  if (pa && ctx.tech(shot.technique)?.params.some((p) => p.type === 'camera')) return mk(engineFitCamera(pa.asset, canvas), true, 'static');
  return mk(null, true, 'none');
}
const mainCamera = (shot) => (cameraLists(shot.params).find((l) => l.name === 'camera') || {}).keys || null;
const playheadShot = () => ctx.store.draft.shots[shotIndexAt(ctx.store.draft.shots, ctx.t)];

function drawBase() {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvasEl.width = Math.round(W * dpr); canvasEl.height = Math.round(H * dpr);
  const c = canvasEl.getContext('2d');
  c.setTransform(dpr, 0, 0, dpr, 0, 0);
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H);
  if (!ctx.store.draft) return;
  if (sourceChk.checked) {
    const cm = currentMapping();
    if (!cm?.pa) { c.fillStyle = '#8a93a6'; c.font = '14px sans-serif'; c.fillText('Shot này không có ảnh nguồn', 20, 30); return; }
    const canvas = ctx.canvasDims(), cam = fitCamera(cm.pa.asset, canvas);
    const img = sourceImage(cm.pa.key, cm.pa.asset);
    if (img && img.complete && img.naturalWidth) {
      const [x0, y0] = cm.S.sourceToScreen(0, 0), k = cm.S.scale('source')[0];
      c.drawImage(img, x0, y0, cm.pa.asset.width * k, cm.pa.asset.height * k);
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
  const cm = currentMapping();
  const M = frozen || cm;
  const sel = ctx.store.sel;
  if (!cm) { note.textContent = ''; return; }
  const shot = cm.shot;
  if (sel.shot && sel.shot !== shot.id) { note.textContent = `Đầu phát đang ở shot ${shot.id}, khác shot đang chọn (${sel.shot}): chọn lại để kéo tay cầm.`; return; }
  const S = M.S;
  note.textContent = cm.mode === 'source' ? (cm.pa ? 'Chế độ ảnh gốc.' : 'Shot này không có ảnh nguồn.') : cm.mode === 'none' && !cm.pa ? 'Shot không có ảnh nguồn: chỉ tham số theo khung hình có tay cầm.'
    : cm.mode === 'none' ? 'Shot không có camera: tham số theo px ảnh nguồn sửa bằng ô số, hoặc bật "Ảnh gốc".' : '';
  const canvas = ctx.canvasDims();
  const asset = cm.pa?.asset;
  const k = S.has('source') ? S.scale('source')[0] : 1;
  // regions (faint): only on request, while picking, or while an overlay with a point parameter is selected
  const ovSel = ctx.store.overlay;
  const wantRegions = regionsChk.checked || !!ctx.pick || (ovSel && ctx.tech(ovSel.technique)?.params.some((p) => p.type === 'point' || p.type === 'points'));
  if (wantRegions && asset && S.has('source')) for (const [name, r] of Object.entries(asset.regions || {})) {
    const [sx, sy] = S.sourceToScreen(r.x, r.y);
    const rrx = r.rx ?? 60, rry = r.ry ?? 60;   // a region may be only a point
    svgEl.append(svg('ellipse', { cx: sx, cy: sy, rx: rrx * k, ry: rry * k, fill: 'none', stroke: 'rgba(255,255,255,.35)', 'stroke-dasharray': '3 4' }));
    if (ctx.pick || regionsChk.checked) { const t = svg('text', { x: sx + 4, y: sy - rry * k - 4, class: 'rname' }); t.textContent = name; svgEl.append(t); }
  }
  // camera boxes of the selected shot (source space)
  const keys = mainCamera(shot);
  if (keys && S.has('source')) keys.forEach((kk, i) => {
    const b = cameraToBox(kk, canvas);
    const [x, y] = S.sourceToScreen(b.x, b.y);
    const w = b.w * k, hgt = b.h * k;
    const col = i === 0 ? COLORS[0] : i === keys.length - 1 ? COLORS[2] : COLORS[1];
    const r = svg('rect', { x, y, width: w, height: hgt, class: 'hbox' + (i === keys.length - 1 ? ' end' : ''), style: `stroke:${col}` });
    const label = svg('g', { class: 'kleg' });   // legend in the top-left corner: never collides with region names
    label.append(svg('rect', { x: 6, y: 6 + i * 17, width: 96, height: 15, rx: 3, class: 'kbg' }), svg('rect', { x: 9, y: 9 + i * 17, width: 9, height: 9, fill: col }));
    const lt = svg('text', { x: 22, y: 17 + i * 17, class: 'klab' }); lt.textContent = `K${i + 1}  zoom ${round(kk.zoom, 3)}`; label.append(lt);
    const knob = svg('rect', { x: x + w - 7, y: y + hgt - 7, width: 14, height: 14, class: 'hknob' });
    svgEl.append(r, label, knob);
    dragger(r, (ev0) => ({ start: clone(kk), ev0 }), (st, dx, dy) => {
      setCam(shot.id, i, { ...st.start, cx: st.start.cx + dx / k, cy: st.start.cy + dy / k });
    });
    dragger(knob, (ev0) => ({ start: clone(kk), ev0 }), (st, dx) => {
      const b0 = cameraToBox(st.start, canvas);
      let nb = fixAspect({ x: b0.x, y: b0.y, w: Math.max(40, b0.w + dx / k), h: b0.h }, canvas);
      nb = { ...nb, y: b0.y };
      const c = boxToCamera(nb, canvas);
      setCam(shot.id, i, { ...st.start, ...c });
    });
  });
  // handles of the selected overlay, else of the shot
  const ov = ctx.store.overlay;
  if (ov) itemHandles(ov, 'overlay', M, shot);
  else itemHandles(shot, 'shot', M, shot);
}

function setCam(shotId, i, k) {
  frozenKeep();
  commitShot('Kéo khung camera', shotId, (s) => {
    s.params.camera[i] = { ...s.params.camera[i], cx: round(k.cx, 1), cy: round(k.cy, 1), zoom: round(k.zoom, 4) };
  }, 'cam' + i);
}
const frozenKeep = () => { if (!frozen) frozen = currentMapping(); };

/** Every handle is placed and moved through the Spaces of the mapping (coords.js): no arithmetic on coordinates here. */
function itemHandles(item, kind, M, shot) {
  const tech = ctx.tech(item.technique);
  if (!tech) return;
  const { S, pa } = M;
  const params = item.params || {};
  const hasSlot = (n) => !!(item.slots?.[n]?.asset || shot.slots?.[n]?.asset);
  const radDef = tech.params.find((p) => p.name === 'radius' && p.type === 'number');
  const hasR = tech.params.some((p) => p.name === 'rx') && tech.params.some((p) => p.name === 'ry');
  const set = (name, v) => { frozenKeep(); setParam(kind, item.id, name, v); };
  const regions = pa?.asset.regions;
  for (const p of tech.params) {
    if (!['point', 'points', 'box'].includes(p.type)) continue;
    const val = p.name in params ? params[p.name] : p.default;
    if (val === null || val === undefined) continue;
    const { space, slot } = splitSpace(paramSpace(tech.id, p, { params, hasSlot }));
    if (space === 'none' || !S.has(space)) continue;
    if (slot && (item.slots?.[slot]?.asset || shot.slots?.[slot]?.asset) !== pa?.key) continue;   // source px of another slot's picture
    const [kx] = S.scale(space);
    const pt = (v) => (space === 'source' ? resolvePoint(v, regions) : (Array.isArray(v) && v.length >= 2 && typeof v[0] === 'number' ? [v[0], v[1]] : null));
    if (p.type === 'points' && Array.isArray(val)) {
      val.forEach((v, i) => {
        const q = pt(v);
        const sc = q && S.toScreen(space, q);
        if (!sc) return;
        const c = svg('circle', { cx: sc[0], cy: sc[1], r: 8, class: 'hpt' });
        const t = svg('text', { x: sc[0] + 10, y: sc[1] - 8, class: 'rname' }); t.textContent = String(i + 1);
        svgEl.append(c, t);
        dragger(c, () => ({ q, list: clone(val) }), (st, dx, dy) => { const n = clone(st.list); n[i] = dragPoint(S, space, st.q, dx, dy); set(p.name, n); });
      });
    } else if (p.type === 'point') {
      const q = pt(val), sc = q && S.toScreen(space, q);
      if (!sc) continue;
      const [sx, sy] = sc;
      if (hasR && space === 'source') {
        const rx = (params.rx ?? tech.params.find((o) => o.name === 'rx').default ?? 100), ry = (params.ry ?? tech.params.find((o) => o.name === 'ry').default ?? 100);
        const e = svg('ellipse', { cx: sx, cy: sy, rx: rx * kx, ry: ry * kx, class: 'hell' });
        const knx = svg('circle', { cx: sx + rx * kx, cy: sy, r: 6, class: 'hknob' });
        const kny = svg('circle', { cx: sx, cy: sy + ry * kx, r: 6, class: 'hknob' });
        svgEl.append(e, knx, kny);
        dragger(e, () => ({ q }), (st, dx, dy) => set(p.name, dragPoint(S, space, st.q, dx, dy)));
        dragger(knx, () => ({ rx }), (st, dx) => set('rx', Math.max(5, Math.round(st.rx + dx / kx))));
        dragger(kny, () => ({ ry }), (st, dx, dy) => set('ry', Math.max(5, Math.round(st.ry + dy / kx))));
      }
      if (!hasR && radDef && space === 'source') {
        const rad = params.radius ?? radDef.default ?? 150;
        const e = svg('circle', { cx: sx, cy: sy, r: rad * kx, class: 'hell' });
        const kr = svg('circle', { cx: sx + rad * kx, cy: sy, r: 6, class: 'hknob' });
        svgEl.append(e, kr);
        dragger(e, () => ({ q }), (st, dx, dy) => set(p.name, dragPoint(S, space, st.q, dx, dy)));
        dragger(kr, () => ({ rad }), (st, dx) => set('radius', Math.max(5, Math.round(st.rad + dx / kx))));
      }
      const c = svg('circle', { cx: sx, cy: sy, r: 7, class: 'hpt' });
      const t = svg('text', { x: sx + 10, y: sy - 8 }); t.textContent = `${p.name}${typeof val === 'string' ? ': ' + val : ''}`;
      svgEl.append(c, t);
      dragger(c, () => ({ q }), (st, dx, dy) => set(p.name, dragPoint(S, space, st.q, dx, dy)));
    } else if (p.type === 'box') {
      const rc = boxToRect(val);
      if (!rc) continue;
      const a = S.toScreen(space, [rc.x, rc.y]), b = S.toScreen(space, [rc.x + rc.w, rc.y + rc.h]);
      if (!a || !b) continue;
      const r = svg('rect', { x: a[0], y: a[1], width: Math.max(1, b[0] - a[0]), height: Math.max(1, b[1] - a[1]), class: 'hbox', style: 'stroke:#f4b400' });
      const knob = svg('rect', { x: b[0] - 7, y: b[1] - 7, width: 14, height: 14, class: 'hknob' });
      const t = svg('text', { x: a[0] + 4, y: a[1] + 12 }); t.textContent = p.name;
      svgEl.append(r, knob, t);
      const minSize = space === 'frame' ? 0.01 : 10;
      dragger(r, () => ({ rc }), (st, dx, dy) => { const n = dragPoint(S, space, [st.rc.x, st.rc.y], dx, dy); set(p.name, boxFrom(space, n[0], n[1], n[0] + st.rc.w, n[1] + st.rc.h)); });
      dragger(knob, () => ({ rc }), (st, dx, dy) => {
        const n = dragPoint(S, space, [st.rc.x + st.rc.w, st.rc.y + st.rc.h], dx, dy);
        set(p.name, boxFrom(space, st.rc.x, st.rc.y, Math.max(st.rc.x + minSize, n[0]), Math.max(st.rc.y + minSize, n[1])));
      });
    }
  }
}
/** A box in [x0,y0,x1,y1] form, rounded like the space it lives in (whole pixels, or 4 decimals for fractions). */
const boxFrom = (space, x0, y0, x1, y1) => (space === 'frame' ? [x0, y0, x1, y1].map((v) => Math.round(v * 1e4) / 1e4) : [x0, y0, x1, y1].map((v) => Math.round(v)));

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
    scope.add(() => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); });
  });
}

function installPick() {
  // pick mode: click on the preview to get a value in the space of the field (region name if inside one in source space, Shift = raw x,y)
  svgEl.addEventListener('pointerdown', (e) => {
    if (!ctx.pick) return;
    const cm = currentMapping();
    const r = svgEl.getBoundingClientRect();
    const value = cm && cm.S.has(ctx.pick.space)
      ? pickValue(cm.S, ctx.pick.space, [((e.clientX - r.left) * W) / r.width, ((e.clientY - r.top) * H) / r.height], cm.pa?.asset.regions, e.shiftKey) : null;
    if (!value) { ctx.pick = null; $('#map-note').textContent = 'Không chọn được trên ảnh ở chế độ này: nhập số vào ô.'; drawHandles(); return; }
    const p = ctx.pick; ctx.pick = null; p.cb(value); drawHandles();
  });
  bus.on('pick', () => {
    // make the view fit the field: source px need a picture mapping ("Ảnh gốc" when the shot has no camera); canvas and frame px need the frame
    if (ctx.pick) {
      const sp = ctx.pick.space, cm = currentMapping();
      if (sp === 'source' && !sourceChk.checked && cm && !cm.S.has('source')) sourceChk.checked = true;
      else if ((sp === 'canvas' || sp === 'frame') && sourceChk.checked) { sourceChk.checked = false; refresh(); }
    }
    drawBase(); drawHandles();
  });
  scope.on(document, 'keydown', (e) => { if (e.key === 'Escape' && ctx.pick) { ctx.pick = null; drawHandles(); } });

}

export function initPreview(viewRoot, viewScope) {
  root = viewRoot; scope = viewScope; alive = true;
  canvasEl = $('#frame', root); svgEl = $('#handles', root); box = $('#stage-box', root); stage = $('#stage', root);
  sourceChk = $('#view-source', root); regionsChk = $('#view-regions', root);
  seq = 0; shown = 0; lastBitmap = null; frozen = null; srcImg = null; srcImgKey = ''; lastReq = 0;
  scope.add(() => { alive = false; refreshDebounced.cancel(); });
  installPick();
  const ro = new ResizeObserver(fit); ro.observe(stage); scope.add(() => ro.disconnect());
  scope.on(sourceChk, 'change', () => { refresh(); drawBase(); drawHandles(); });
  scope.on(regionsChk, 'change', drawHandles);
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
