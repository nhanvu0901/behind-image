// Edit actions that touch the store (every human edit sets source: "human").
import { ctx } from './ctx.js';
import { api } from './api.js';
import * as E from './edit.js';
import { clone, shotIndexAt, anchorFromTime, cameraAt } from './logic.js';
import { defaultParams } from './formgen.js';
import { toast } from './util.js';

const st = () => ctx.store;

export function commitShot(label, id, fn, coalesce) {
  return st().commit(label, (d) => {
    const s = d.shots.find((x) => x.id === id);
    if (!s) return;
    fn(s, d);
    E.markHuman(s);
  }, { coalesce: coalesce ? `${coalesce}:${id}` : null });
}
export function commitOverlay(label, id, fn, coalesce) {
  E.scope.shot = st().sel.shot;
  return st().commit(label, (d) => {
    const f = E.findOverlay(d, id);
    if (!f) return;
    fn(f.ov, f.shot, d);
    E.markHuman(f.ov);
  }, { coalesce: coalesce ? `${coalesce}:${id}` : null });
}
export const setParam = (kind, id, name, value) => (kind === 'overlay' ? commitOverlay : commitShot)(
  `Đổi ${name}`, id, (it) => { (it.params ||= {})[name] = value; }, 'p:' + name);

async function fetchDefaults(technique, context) {
  try { return (await api.defaults(ctx.pid, technique, context)).params || {}; }
  catch (e) {
    toast('Không lấy được giá trị mặc định từ server, dùng mặc định của registry', 'warn');
    return defaultParams(ctx.tech(technique)?.params);
  }
}
const assetsCtx = (d, slots) => Object.fromEntries(Object.values(slots || {}).map((v) => v?.asset).filter(Boolean).map((k) => {
  const a = d.assets[k] || {};
  return [k, { width: a.width, height: a.height, title: a.title, artist: a.artist, year: a.year, regions: a.regions || {} }];
}));
/** The camera the shot has at the playhead (so a new camera technique continues from the current framing). */
const cameraNow = (shot) => { const k = shot?.params?.camera; return Array.isArray(k) ? cameraAt(k, ctx.t) : null; };

export async function setShotTechnique(shotId, techId) {
  const t = ctx.tech(techId);
  const shot = st().shotById(shotId);
  if (!t || !shot) return;
  // keep assets of slots with the same name, then fill empty slots from the old ones in order
  const old = Object.values(shot.slots || {}).filter((v) => v?.asset);
  const slots = {};
  for (const sl of t.slots) {
    if (shot.slots?.[sl.name]) slots[sl.name] = clone(shot.slots[sl.name]);
  }
  let oi = 0;
  for (const sl of t.slots) if (!slots[sl.name] && sl.type !== 'text' && old[oi] && oi < old.length) {
    if (sl.type === 'image' || sl.type === 'video') slots[sl.name] = clone(old[oi]); oi++;
  }
  const draft = st().draft;
  const params = await fetchDefaults(techId, { item: 'shot', shot_id: shotId, duration: shot._t1 - shot._t0, slots, assets: assetsCtx(draft, slots), canvas: draft.canvas, camera: cameraNow(shot) || undefined });
  commitShot(`Đổi kỹ thuật ${techId}`, shotId, (s) => {
    s.technique = techId; s.params = params; s.slots = slots;
    if (!t.intents.includes(s.intent)) s.intent = t.intents[0];
  });
}

/** After a slot got another image, camera keys in the OLD image's pixels would frame the wrong place: ask the engine for the
 * technique's default camera on the new image and replace every camera-type param (other params are kept). */
export async function refitCamera(shotId) {
  const shot = st().shotById(shotId);
  const t = shot && ctx.tech(shot.technique);
  if (!t) return;
  const camParams = t.params.filter((p) => p.type === 'camera').map((p) => p.name);
  if (!camParams.length) return;
  const draft = st().draft;
  const params = await fetchDefaults(t.id, { item: 'shot', shot_id: shotId, duration: shot._t1 - shot._t0, slots: shot.slots, assets: assetsCtx(draft, shot.slots), canvas: draft.canvas });
  commitShot('Đặt lại camera cho hình mới', shotId, (s) => { for (const n of camParams) if (params[n]) (s.params ||= {})[n] = params[n]; });
}

export async function setOverlayTechnique(overlayId, techId) {
  const t = ctx.tech(techId);
  const draft = st().draft;
  E.scope.shot = st().sel.shot;
  const f = E.findOverlay(draft, overlayId);
  if (!t || !f) return;
  const params = await fetchDefaults(techId, { item: 'overlay', shot_id: f.shot.id, overlay_id: overlayId, duration: f.ov._t1 - f.ov._t0, slots: f.shot.slots, assets: assetsCtx(draft, f.shot.slots), canvas: draft.canvas });
  commitOverlay(`Đổi kỹ thuật ${techId}`, overlayId, (o) => {
    o.technique = techId; o.params = params;
    if (!t.intents.includes(o.intent)) o.intent = t.intents[0];
  });
}

export async function addOverlayAction(shotId, techId) {
  const t = ctx.tech(techId);
  const draft = st().draft;
  const i = draft.shots.findIndex((s) => s.id === shotId);
  if (i < 0 || !t) return;
  const s = draft.shots[i];
  const params = await fetchDefaults(techId, { item: 'overlay', shot_id: shotId, duration: 3, slots: s.slots, assets: assetsCtx(draft, s.slots), canvas: draft.canvas });
  let newId;
  const at = Math.min(Math.max(ctx.t, s._t0), s._t1 - 0.5);
  st().commit('Thêm lớp phủ', (d) => { newId = E.addOverlay(d, i, techId, t.intents[0], params, at, ctx.words()); E.markHuman(d.shots[i]); });
  st().select(shotId, newId);
  return newId;
}

export function setTransition(shotId, techId) {
  const t = ctx.tech(techId);
  commitShot('Đổi chuyển cảnh', shotId, (s) => {
    s.transition_in = techId ? { technique: techId, dur: Math.max(0.2, Math.min(1, t?.params.find((p) => p.name === 'duration_s')?.default || 1)), params: defaultParams(t.params) } : null;
  });
}

export function splitAtPlayhead() {
  const d = st().draft; const i = shotIndexAt(d.shots, ctx.t);
  let id = null;
  st().commit('Cắt shot', (dd) => { id = E.splitShot(dd, i, ctx.t, ctx.words()); });
  if (!id) toast('Không cắt được: mỗi phần phải dài ít nhất 0.2 s', 'warn'); else st().select(id);
}
export function mergePrev(shotId) {
  const i = st().draft.shots.findIndex((s) => s.id === shotId);
  if (i <= 0) return toast('Shot đầu không có shot trước để gộp', 'warn');
  const prevId = st().draft.shots[i - 1].id;
  st().commit('Gộp shot', (d) => E.mergeWithPrev(d, i));
  st().select(prevId);
}
export function deleteShotAction(shotId) {
  const d = st().draft; const i = d.shots.findIndex((s) => s.id === shotId);
  if (i < 0) return;
  if (d.shots.length <= 1) return toast('Không thể xóa shot cuối cùng', 'warn');
  st().commit('Xóa shot', (dd) => E.deleteShot(dd, i));
  const left = st().draft.shots;
  st().select(left[Math.min(i, left.length - 1)].id);
}
export function toggleLock() {
  const { shot, overlay } = st();
  if (overlay) commitOverlay('Khóa lớp phủ', overlay.id, (o) => { o.locked = !o.locked; });
  else if (shot) commitShot('Khóa shot', shot.id, (s) => { s.locked = !s.locked; });
}
export function removeOverlayAction(id) {
  const shotId = st().sel.shot;
  E.scope.shot = shotId;
  st().commit('Xóa lớp phủ', (d) => E.removeOverlay(d, id));
  st().select(shotId);
}
