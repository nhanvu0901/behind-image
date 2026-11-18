// Preview pane: engine still (POST /frame with the draft), draggable camera boxes and overlay handles.
import { api } from './api.js';
import { ctx, bus, primaryAsset } from './ctx.js';
import { $, h, svg, debounce, fmtTime } from './util.js';
import { describeError, renderFailText } from './errmsg.js';
import { DEBOUNCE_MS, MOCK } from './config.js';
import { cameraLists, cameraAt, engineFitCamera, round, shotIndexAt, clone } from './logic.js';
import { makeSpaces, dragPoint, boxToRect, paramSpace, splitSpace, resolvePoint, pickValue } from './coords.js';
import { setParam } from './actions.js';
import * as E from './edit.js';
import * as G from './camgeom.js';
import { camSel, setCamSel } from './camsel.js';
import { CAMERA_LABELS } from './labels.js';
import { paintAsset } from './placeholder.js';

// DOM is looked up when the view is mounted (initPreview), never at import time: the module outlives the view.
let root = null, scope = null, alive = false;
let canvasEl, svgEl, box, stage, sourceChk, regionsChk;
let seq = 0, shown = 0, lastBitmap = null, W = 640, H = 360;
let frozen = null; // mapping frozen during a drag
let srcImg = null, srcImgKey = '';
let lastReq = 0;
let frameFail = null;   // {shot, text}: the frame at the playhead could not be drawn; nothing stale is shown meanwhile (R3U-004)
let dragging = false;   // a camera-frame drag is going on: the picture is not asked from the server for every mouse move
let camFrozenS = null;  // the spaces of the camera frames when the drag began (the mapping must not move under the pointer)
let dragSeq = 0, viewCache = { sig: '', cam: null }, camPickEl = null;

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
    clearFrameFail();
    const inc = incompleteAt(t);
    stateEl.textContent = `khung ${fmtTime(t)}` + (inc ? ` | khung tạm, ${inc}` : '');
    stateEl.classList.toggle('warn', !!inc);
    drawBase();
  } catch (e) {
    if (mySeq !== seq) return;
    stateEl.classList.add('warn');
    const text = frameError(e, t);
    stateEl.textContent = text;
    setFrameFail(t, text);
  }
}
const shotKeyOf = (shotId) => shotId + '|' + (ctx.renderKey || ctx.store.rev);
/** The frame at time t cannot be drawn: forget the old picture (it belongs to another moment), say why on the canvas, and give the Shot tab the same sentence. */
function setFrameFail(t, text) {
  const sh = ctx.store.draft?.shots[shotIndexAt(ctx.store.draft.shots, t)];
  clearFrameFail(true);
  lastBitmap = null;
  frameFail = { shot: sh?.id || null, text, key: sh ? shotKeyOf(sh.id) : null, inTab: false };
  if (sh && !incompleteAt(t) && !ctx.thumbFails.has(frameFail.key)) { ctx.thumbFails.set(frameFail.key, text); frameFail.inTab = true; bus.emit('thumbfail'); }
  drawBase(); drawHandles();
}
function clearFrameFail(quiet = false) {
  if (!frameFail) return;
  const f = frameFail; frameFail = null;
  if (f.inTab) { ctx.thumbFails.delete(f.key); if (!quiet) bus.emit('thumbfail'); }
}
/** The failure that applies to what is under the playhead now (a failure of another shot does not). */
const failHere = () => (frameFail && !sourceChk.checked && frameFail.shot && frameFail.shot === playheadShot()?.id ? frameFail : null);
function wrapText(c, text, x, y, maxW, lh) {
  let line = '';
  for (const w of String(text).split(/\s+/)) {
    const t = line ? line + ' ' + w : w;
    if (line && c.measureText(t).width > maxW) { c.fillText(line, x, y); y += lh; line = w; } else line = t;
  }
  if (line) c.fillText(line, x, y);
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
  const inc = incompleteAt(t);
  if (inc) return `Chưa dựng được khung: ${inc}`;
  if (e?.body?.code === 'render_failed') return renderFailText(e.body);   // names the shot; the page keeps working
  const d = describeError(e);
  if (e && 'status' in e && e.status >= 500) return 'Máy chủ không dựng được khung này. Xem tab Lỗi.';
  return 'Lỗi dựng khung: ' + d.text;
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
  const pa0 = primaryAsset(shot);
  const canvas = ctx.canvasDims(), view = { W, H };
  const mk = (cam, canvasOk, mode, pa = pa0) => ({ S: makeSpaces({ canvas, view, cam, canvasOk }), pa, shot, mode });
  if (sourceChk.checked) {   // the picture shown is the source image, not the frame: the picture of the camera being edited, else the shot's first picture
    const cs = camState(shot);
    const pa = cs.set ? { key: cs.set.assetKey, asset: cs.set.asset } : pa0;
    return mk(pa ? sourceCam(shot, cs.set, pa, canvas) : null, false, 'source', pa);
  }
  const keys = mainCamera(shot);
  if (keys && pa0) return mk(cameraAt(keys, ctx.t) || keys[0], true, 'camera');
  // a camera technique without a camera key: the engine shows the whole image at 95.5 % of the frame height
  if (pa0 && ctx.tech(shot.technique)?.params.some((p) => p.type === 'camera')) return mk(engineFitCamera(pa0.asset, canvas), true, 'static');
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
    const canvas = ctx.canvasDims(), cam = cm.S.cam;
    const img = sourceImage(cm.pa.key, cm.pa.asset);
    if (img && img.complete && img.naturalWidth) {
      const [x0, y0] = cm.S.sourceToScreen(0, 0), k = cm.S.scale('source')[0];
      c.drawImage(img, x0, y0, cm.pa.asset.width * k, cm.pa.asset.height * k);
    } else paintAsset(c, cm.pa.key, cm.pa.asset, cam, canvas, W, H);
    return;
  }
  const ff = failHere();
  if (ff) { c.fillStyle = '#1b1f2a'; c.fillRect(0, 0, W, H); c.fillStyle = '#ffb4b4'; c.font = '14px sans-serif'; wrapText(c, ff.text, 20, 34, W - 40, 20); return; }
  if (lastBitmap) c.drawImage(lastBitmap, 0, 0, W, H);
  else { c.fillStyle = '#8a93a6'; c.font = '14px sans-serif'; c.fillText('Đang chờ khung hình từ engine...', 20, 30); }
}

// ---- handles
const COLORS = ['#4f9cff', '#f4b400', '#3ecf8e'];
function drawHandles() {
  svgEl.replaceChildren();
  syncCamPick(null);
  const d = ctx.store.draft;
  svgEl.classList.toggle('picking', !!ctx.pick);
  const note = $('#map-note');
  if (!d) return;
  if (failHere()) { note.textContent = ''; return; }   // handles belong to a picture; there is none
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
    svgEl.append(svg('ellipse', { cx: sx, cy: sy, rx: rrx * k, ry: rry * k, fill: 'none', stroke: 'rgba(255,255,255,.35)', 'stroke-dasharray': '3 4', style: 'pointer-events:none' }));
    if (ctx.pick || regionsChk.checked) { const t = svg('text', { x: sx + 4, y: sy - rry * k - 4, class: 'rname' }); t.textContent = name; svgEl.append(t); }
  }
  // camera frames of the selected shot: what each key sees (camgeom.js), through the spaces of the view
  const cv = camView(cm);
  syncCamPick(cv?.cs);
  if (cv?.rects) drawCameraFrames(cv);
  else if (cv?.cs.set && !note.textContent) note.textContent = CAMERA_LABELS.needSource;
  // handles of the selected overlay, else of the shot
  const ov = ctx.store.overlay;
  if (ov) itemHandles(ov, 'overlay', M, shot);
  else itemHandles(shot, 'shot', M, shot);
}

// ---- camera frames (D22)
// The cameras of the shot under the playhead that can be drawn, and which key of which camera is selected (camsel.js).
function camState(shot) {
  const sets = shot ? G.cameraSets(ctx.tech(shot.technique), shot, ctx.store.draft.assets, ctx.canvasDims()) : [];
  const sel = G.resolveSelection(camSel(), shot?.id, sets);
  return { sets, sel, set: sets.find((x) => x.name === sel.param) || null };
}
/** The "Ảnh gốc" view of the camera being edited: the picture, zoomed out only as far as its frames need. It is kept while the same
 * camera stays open, so the picture does not change size under a drag or under a number typed in the form. */
function sourceCam(shot, set, pa, canvas) {
  const sig = [shot.id, set?.name, pa.key, set?.keys.length, canvas.w, canvas.h].join('|');
  if (viewCache.sig !== sig) viewCache = { sig, cam: G.sourceViewCamera(pa.asset, canvas, set ? set.keys.map((k) => G.keyToRect(k, set.panel)) : []) };
  return viewCache.cam;
}
/** Spaces of the frames: the source view itself; in the frame view only a camera whose panel is the whole frame (through the camera at the playhead). */
function camSpaces(cm, set) {
  if (!set) return null;
  if (cm.mode === 'source') return cm.S;
  const canvas = ctx.canvasDims();
  if (set.panel.w !== canvas.w || set.panel.h !== canvas.h) return null;
  return makeSpaces({ canvas, view: { W, H }, cam: cameraAt(set.keys, ctx.t) || set.keys[0], canvasOk: true });
}
/** Everything the frames need now: {cs, S, ks, rects (screen px, one per key)}; rects is missing when nothing can be drawn. */
function camView(cm) {
  if (!cm || failHere()) return null;
  const sel = ctx.store.sel;
  if (sel.shot && sel.shot !== cm.shot.id) return null;
  const cs = camState(cm.shot);
  const S = camFrozenS || camSpaces(cm, cs.set);
  if (!cs.set || !S) return { cs };
  const [ks] = S.scale('source');
  const rects = cs.set.keys.map((k) => { const r = G.keyToRect(k, cs.set.panel); const [x, y] = S.sourceToScreen(r.x, r.y); return { x, y, w: r.w * ks, h: r.h * ks }; });
  return { cs, S, ks, rects, shot: cm.shot, set: cs.set };
}
const KCOL = (i, n) => (i === 0 ? COLORS[0] : i === n - 1 ? COLORS[2] : COLORS[1]);
function drawCameraFrames({ cs, rects, set }) {
  const cur = camSel();
  if (cur.shot !== cs.sel.shot || cur.param !== cs.sel.param || cur.index !== cs.sel.index) setCamSel(cs.sel.shot, cs.sel.param, cs.sel.index, 'preview');
  const n = rects.length, si = cs.sel.index;
  const legend = svg('g', { class: 'kleg' });
  const order = rects.map((_, i) => i).filter((i) => i !== si).concat(si);                // the selected frame is drawn last, on top
  for (const i of order) {
    const r = rects[i], col = KCOL(i, n), isSel = i === si;
    svgEl.append(svg('rect', { x: r.x, y: r.y, width: r.w, height: r.h, class: 'cframe' + (isSel ? ' sel' : ''), 'data-k': i + 1, style: `stroke:${col}` }));
    const tx = Math.min(Math.max(r.x + 3, 2), W - 30), ty = Math.min(Math.max(r.y + 3, 2), H - 16);
    const tag = svg('g', { class: 'ctag' + (isSel ? ' sel' : ''), 'data-k': i + 1 });
    tag.append(svg('rect', { x: tx, y: ty, width: 8 + String(i + 1).length * 7 + 5, height: 14, rx: 3, style: `fill:${isSel ? col : 'rgba(0,0,0,.7)'}` }));
    const tt = svg('text', { x: tx + 4, y: ty + 11, class: 'klab' }); tt.textContent = 'K' + (i + 1); tag.append(tt);
    svgEl.append(tag);
  }
  if (n <= 10) rects.forEach((_, i) => {                                                    // legend in the top-left corner: number and zoom of every key
    const col = KCOL(i, n);
    legend.append(svg('rect', { x: 6, y: 6 + i * 17, width: 96, height: 15, rx: 3, class: 'kbg' + (i === si ? ' sel' : '') }), svg('rect', { x: 9, y: 9 + i * 17, width: 9, height: 9, fill: col }));
    const lt = svg('text', { x: 22, y: 17 + i * 17, class: 'klab' + (i === si ? ' sel' : '') }); lt.textContent = CAMERA_LABELS.key(i, round(set.keys[i].zoom, 3)); legend.append(lt);
  });
  svgEl.append(legend);
  for (const [name, p] of Object.entries(G.cornerPoints(rects[si]))) svgEl.append(svg('rect', { x: p[0] - 6, y: p[1] - 6, width: 12, height: 12, class: 'hknob ck', 'data-corner': name }));
}
/** One camera at a time is drawn; a technique with several (LAY-01: left and right) gets a small chooser next to the view switches. */
function syncCamPick(cs) {
  if (!camPickEl) return;
  const sets = cs?.sets || [];
  camPickEl.hidden = sets.length < 2;
  const sel = camPickEl.querySelector('select');
  if (sets.length < 2) return;
  const names = sets.map((x) => x.name).join('|');
  if (sel.dataset.names !== names) { sel.dataset.names = names; sel.replaceChildren(...sets.map((x) => h('option', { value: x.name, text: x.name }))); }
  sel.value = cs.sel.param;
}
function commitKey(shotId, param, i, k, gesture) {
  const rk = G.roundKey(k);
  // one drag = one undo step: the gesture's own key keeps every move in the step it opened, however long it takes
  ctx.store.commit(CAMERA_LABELS.undo, (d) => {
    const s = d.shots.find((x) => x.id === shotId);
    const key = s?.params?.[param]?.[i];
    if (!key) return;
    s.params[param][i] = { ...key, ...rk };
    E.markHuman(s);
  }, { coalesce: gesture, ms: Infinity });
}
function installCameraDrag() {
  const ptOf = (e) => { const r = svgEl.getBoundingClientRect(); return [((e.clientX - r.left) * W) / r.width, ((e.clientY - r.top) * H) / r.height]; };
  const hitAt = (e) => { const cv = camView(currentMapping()); return cv?.rects ? { cv, hit: G.hitTest(cv.rects, cv.cs.sel.index, ptOf(e)) } : null; };
  scope.on(svgEl, 'pointermove', (e) => {
    if (dragging || ctx.pick) return;
    const over = hitAt(e)?.hit;
    svgEl.style.cursor = !over ? '' : over.part === 'corner' ? G.cornerCursor(over.corner) : 'move';
  });
  scope.on(svgEl, 'pointerdown', (e) => {
    if (ctx.pick || e.button !== 0 || dragging) return;
    const found = hitAt(e);
    if (!found?.hit) return;
    const { cv, hit } = found, { set, shot } = cv, i = hit.index;
    // equal frames lie on top of each other: a drag moves the selected one, a click without movement passes the selection on to the next
    const cycle = hit.part === 'body' && hit.ties.length > 1 && hit.ties.includes(cv.cs.sel.index) ? G.nextInStack(hit.ties, cv.cs.sel.index) : null;
    let moved = false;
    e.preventDefault(); e.stopPropagation();
    if (i !== cv.cs.sel.index) setCamSel(shot.id, set.name, i, 'preview');
    const tab = document.querySelector('#tabs button[data-tab="shot"]');                     // the form of the key is in the Shot tab
    if (tab && !tab.classList.contains('active')) tab.click();
    camFrozenS = cv.S; dragging = true;                                                      // the mapping does not move under the pointer
    const key0 = clone(set.keys[i]), bounds = G.centreBounds(set.asset, key0);
    const x0 = e.clientX, y0 = e.clientY, sc = W / box.getBoundingClientRect().width, gesture = 'camdrag:' + (++dragSeq);
    drawHandles();
    const mv = (ev) => {
      if (Math.abs(ev.clientX - x0) + Math.abs(ev.clientY - y0) > 3) moved = true;
      const dx = ((ev.clientX - x0) * sc) / cv.ks, dy = ((ev.clientY - y0) * sc) / cv.ks;
      commitKey(shot.id, set.name, i, hit.part === 'corner' ? G.resizeKey(key0, set.panel, hit.corner, dx, dy) : G.moveKey(key0, dx, dy, bounds), gesture);
    };
    const off = () => { window.removeEventListener('pointermove', mv); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up); };
    const up = () => {
      off(); dragging = false; camFrozenS = null;
      if (cycle !== null && !moved) setCamSel(shot.id, set.name, cycle, 'preview');
      drawHandles(); if (!sourceChk.checked) requestFrame();
    };
    window.addEventListener('pointermove', mv); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', up);
    scope.add(() => { off(); dragging = false; camFrozenS = null; });
  });
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
  seq = 0; shown = 0; lastBitmap = null; frameFail = null; frozen = null; srcImg = null; srcImgKey = ''; lastReq = 0;
  dragging = false; camFrozenS = null; viewCache = { sig: '', cam: null };
  camPickEl = h('label', { class: 'chk cam-pick', title: CAMERA_LABELS.pickHint, hidden: true }, CAMERA_LABELS.pick + ' ', h('select', {
    onchange: (e) => { const shot = playheadShot(); if (shot) { setCamSel(shot.id, e.target.value, 0, 'preview'); drawBase(); drawHandles(); } } }));
  $('#map-note', root).before(camPickEl);
  scope.add(() => { alive = false; refreshDebounced.cancel(); });
  installPick(); installCameraDrag();
  scope.add(bus.on('camsel', (e) => { if (e.from !== 'preview') { drawBase(); drawHandles(); } }));
  const ro = new ResizeObserver(fit); ro.observe(stage); scope.add(() => ro.disconnect());
  scope.on(sourceChk, 'change', () => { refresh(); drawBase(); drawHandles(); });
  scope.on(regionsChk, 'change', drawHandles);
  let lastSel = '';
  ctx.store.on((kind) => {
    const sig = ctx.store.sel.shot + '|' + ctx.store.sel.overlay;
    if (kind === 'select' || kind === 'load' || sig !== lastSel) { lastSel = sig; drawBase(); }
    drawHandles();
    if (kind !== 'select' && !dragging) requestFrame();
  });
  bus.on('time', () => { if (!ctx.playing) requestFrame(); drawHandles(); if (sourceChk.checked || frameFail) drawBase(); });
  bus.on('tick', () => { requestFrameThrottled(250); });
  fit();
  refresh();
}
