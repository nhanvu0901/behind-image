// Edit actions that touch the store (every human edit sets source: "human").
import { ctx } from './ctx.js';
import { api } from './api.js';
import * as E from './edit.js';
import { shotIndexAt, cameraAt } from './logic.js';
import { defaultParams } from './formgen.js';
import { toast, ask, h } from './util.js';
import { carrySlots, slotKind, whyNot, regionUsage, scanRegionRefs, replaceRegionRefs } from './slots.js';

const st = () => ctx.store;

export function commitShot(label, id, fn, coalesce) {
  return st().commit(label, (d) => {
    const s = d.shots.find((x) => x.id === id);
    if (!s) return;
    fn(s, d);
    E.markHuman(s);
  }, { coalesce: coalesce ? `${coalesce}:${id}` : null });
}
/** `shotId`: the shot that holds the overlay (overlay ids are unique inside their shot). Defaults to the selected shot. */
export function commitOverlay(label, id, fn, coalesce, shotId = null) {
  E.scope.shot = shotId || st().sel.shot;
  return st().commit(label, (d) => {
    const f = E.findOverlay(d, id);
    if (!f) return;
    fn(f.ov, f.shot, d);
    E.markHuman(f.ov);
  }, { coalesce: coalesce ? `${coalesce}:${E.scope.shot}/${id}` : null });
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
  if (!t || !st().shotById(shotId)) return;
  // slots: same-name slots stay when the asset still fits; the painting goes only into IMAGE slots (never a video or mask slot)
  const slotsNow = () => carrySlots(t.slots, st().shotById(shotId)?.slots, st().draft.assets);
  let slots = slotsNow(), params = null;
  for (let tries = 0; tries < 2; tries++) {                 // the user may change the slots while the defaults are on their way
    const shot = st().shotById(shotId); const draft = st().draft;
    if (!shot) return;
    const sig = JSON.stringify(slots);
    params = await fetchDefaults(techId, { item: 'shot', shot_id: shotId, duration: shot._t1 - shot._t0, slots, assets: assetsCtx(draft, slots), canvas: draft.canvas, camera: cameraNow(shot) || undefined });
    slots = slotsNow();
    if (JSON.stringify(slots) === sig) break;
  }
  commitShot(`Đổi kỹ thuật ${techId}`, shotId, (s) => {
    s.technique = techId; s.params = params; s.slots = slots;
    if (!t.intents.includes(s.intent)) s.intent = t.intents[0];
  });
}

/** After a slot got another image, camera keys in the OLD image's pixels would frame the wrong place: ask the engine for the
 * technique's default camera on the new image. Returns {names, params, before}: the camera params to replace (other params are
 * kept) and the camera as it was when asked, so a camera the user moved meanwhile is left alone. null when there is no camera. */
async function cameraRefit(shot, slots) {
  const t = ctx.tech(shot.technique);
  const names = (t?.params || []).filter((p) => p.type === 'camera').map((p) => p.name);
  if (!names.length) return null;
  const draft = st().draft;
  const before = JSON.stringify(names.map((n) => shot.params?.[n]));
  const params = await fetchDefaults(t.id, { item: 'shot', shot_id: shot.id, duration: shot._t1 - shot._t0, slots, assets: assetsCtx(draft, slots), canvas: draft.canvas });
  return { names, params, before };
}
const applyRefit = (s, r) => {
  if (!r || JSON.stringify(r.names.map((n) => s.params?.[n])) !== r.before) return;
  for (const n of r.names) if (r.params[n]) (s.params ||= {})[n] = r.params[n];
};
export async function refitCamera(shotId) {
  const shot = st().shotById(shotId);
  const r = shot && await cameraRefit(shot, shot.slots);
  if (r) commitShot('Đặt lại camera cho hình mới', shotId, (s) => applyRefit(s, r));
}

const ovContextSlots = (shot, ov) => ({ ...(shot.slots || {}), ...(ov?.slots || {}) });

export async function setOverlayTechnique(overlayId, techId, shotId = null) {
  const t = ctx.tech(techId);
  const draft = st().draft;
  E.scope.shot = shotId || st().sel.shot;
  const f = E.findOverlay(draft, overlayId);
  if (!t || !f) return;
  const slots = carrySlots(t.slots, f.ov.slots, draft.assets);
  const params = await fetchDefaults(techId, { item: 'overlay', shot_id: f.shot.id, overlay_id: overlayId, duration: f.ov._t1 - f.ov._t0, slots: ovContextSlots(f.shot, { slots }), assets: assetsCtx(draft, ovContextSlots(f.shot, { slots })), canvas: draft.canvas });
  commitOverlay(`Đổi kỹ thuật ${techId}`, overlayId, (o) => {
    o.technique = techId; o.params = params;
    if (Object.keys(slots).length) o.slots = slots; else delete o.slots;
    if (!t.intents.includes(o.intent)) o.intent = t.intents[0];
  }, null, f.shot.id);
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
  selectItem(shotId, newId);
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
export function removeOverlayAction(id, shotId = null) {
  const sh = shotId || st().sel.shot;
  E.scope.shot = sh;
  st().commit('Xóa lớp phủ', (d) => E.removeOverlay(d, id));
  st().select(sh);
}

// ---------------------------------------------------------------- selection moves the playhead
/** Put the playhead inside the selected item (an overlay, else the shot), so the still and the handles are one moment. */
export function alignPlayhead() {
  const s = st().shot;
  if (!s) return;
  const o = st().overlay;
  const a = o ? o._t0 : s._t0, b = o ? o._t1 : s._t1;
  if (ctx.t >= a - 1e-6 && ctx.t < b - 1e-6) return;
  ctx.seek(Math.min(a + 0.01, (a + b) / 2));
}
export function selectItem(shotId, overlayId = null) {
  st().select(shotId, overlayId);
  alignPlayhead();
}

// ---------------------------------------------------------------- slots (shots and overlays)
const itemOf = (target) => {
  const shot = st().shotById(target.shotId);
  if (!shot) return {};
  return { shot, item: target.overlayId ? (shot.overlays || []).find((o) => o.id === target.overlayId) : shot };
};
const commitTarget = (label, target, fn, coalesce) => (target.overlayId
  ? commitOverlay(label, target.overlayId, fn, coalesce, target.shotId)
  : commitShot(label, target.shotId, fn, coalesce));

/** Ask what to do with region names that the new picture does not have. Resolves 'cancel' | 'keep' | 'coords'. */
async function askRegionChange(dangling) {
  const list = h('ul', { class: 'ref-list' }, ...dangling.map((d) => h('li', null, h('b', { text: d.name }), ` dùng ở ${d.uses.map((u) => `${u.where} (${u.param})`).join(', ')}`)));
  return ask({
    title: 'Hình mới không có các vùng này', cancelValue: 'cancel',
    message: 'Các lớp phủ/shot đang trỏ vào vùng (region) của hình cũ. Hình mới không có vùng cùng tên.',
    body: list,
    buttons: [{ text: 'Hủy, giữ hình cũ', value: 'cancel' }, { text: 'Giữ tên vùng (sẽ báo lỗi)', value: 'keep' }, { text: 'Đổi thành tọa độ', value: 'coords', cls: 'primary' }],
  });
}

/** Put an asset into a slot. A slot takes only an asset of its own kind. Returns true when it was done. */
export async function assignSlot(target, slotName, key) {
  const { shot, item } = itemOf(target);
  const draft = st().draft;
  const tech = item && ctx.tech(item.technique);
  const sl = tech?.slots.find((x) => x.name === slotName);
  const asset = draft.assets[key];
  if (!sl || !asset) return false;
  const why = whyNot(sl, asset);
  if (why) { toast(why, 'warn'); return false; }
  const oldKey = item.slots?.[slotName]?.asset;
  let convert = null;
  if (oldKey && oldKey !== key && slotKind(sl) === 'image') {
    const oldRegions = draft.assets[oldKey]?.regions || {}, newRegions = asset.regions || {};
    const affected = [{ it: item, where: target.overlayId ? `${shot.id}/${item.id}` : shot.id },
      ...(!target.overlayId ? (shot.overlays || []).filter((o) => !o.slots?.image?.asset).map((o) => ({ it: o, where: `${shot.id}/${o.id}` })) : [])];
    const dangling = [];
    for (const name of Object.keys(oldRegions)) {
      if (newRegions[name]) continue;
      const uses = affected.flatMap(({ it, where }) => scanRegionRefs(it.params, name).map((r) => ({ where, param: r.param })));
      if (uses.length) dangling.push({ name, uses });
    }
    if (dangling.length) {
      const a = await askRegionChange(dangling);
      if (a === 'cancel') return false;
      if (a === 'coords') convert = { dangling, oldRegions, affected: affected.map((x) => x.it.id) };
    }
  }
  // a new picture in a shot: the camera of the technique is re-fitted in the SAME undo step
  const refit = !target.overlayId && slotKind(sl) === 'image' ? await cameraRefit(shot, { ...(shot.slots || {}), [slotName]: { asset: key } }) : null;
  const apply = (it, shotNow) => {
    (it.slots ||= {})[slotName] = { asset: key };
    if (!target.overlayId) applyRefit(it, refit);
    if (convert) {
      for (const { name } of convert.dangling) {
        const r = convert.oldRegions[name];
        const targets = [it, ...(!target.overlayId ? (shotNow.overlays || []).filter((o) => !o.slots?.image?.asset) : [])];
        for (const x of targets) if (x.params) x.params = replaceRegionRefs(x.params, name, [Math.round(r.x), Math.round(r.y)]);
      }
    }
  };
  commitTarget(`Chọn hình cho slot ${slotName}`, target, (it, shotOrD) => apply(it, target.overlayId ? shotOrD : st().draft.shots.find((s) => s.id === target.shotId)));
  return true;
}
export function clearSlot(target, slotName) {
  commitTarget(`Bỏ hình khỏi slot ${slotName}`, target, (it) => { if (it.slots) delete it.slots[slotName]; if (it.slots && !Object.keys(it.slots).length && target.overlayId) delete it.slots; });
}

// ---------------------------------------------------------------- regions: part of the draft (undo, redo, unsaved marker, saved with Lưu)
const regionsOf = (d, key) => d.assets[key]?.regions || {};
export function regionUse(assetKey, name) { return regionUsage(st().draft, assetKey, name); }
export function addRegion(assetKey, name, r) {
  return st().commit(`Thêm vùng ${name}`, (d) => { const a = d.assets[assetKey]; if (a) (a.regions ||= {})[name] = r; });
}
/** Move/resize/label a region. Drags use `coalesce` so one drag is one undo step. */
export function patchRegion(assetKey, name, patch, coalesce = null) {
  return st().commit(`Sửa vùng ${name}`, (d) => { const r = regionsOf(d, assetKey)[name]; if (r) Object.assign(r, patch); }, { coalesce: coalesce ? `${coalesce}:${assetKey}:${name}` : null });
}
/** Delete a region. Refused while an overlay or shot uses it: returns {ok:false, usage}. */
export function deleteRegion(assetKey, name) {
  const usage = regionUse(assetKey, name);
  if (usage.length) return { ok: false, usage };
  st().commit(`Xóa vùng ${name}`, (d) => { if (d.assets[assetKey]?.regions) delete d.assets[assetKey].regions[name]; });
  return { ok: true, usage: [] };
}
/** Rename a region; `updateRefs` rewrites every parameter that names it. */
export function renameRegion(assetKey, from, to, updateRefs) {
  return st().commit(`Đổi tên vùng ${from} thành ${to}`, (d) => {
    const regs = d.assets[assetKey]?.regions;
    if (!regs || !regs[from] || regs[to]) return;
    const ordered = Object.fromEntries(Object.entries(regs).map(([k, v]) => [k === from ? to : k, v]));
    d.assets[assetKey].regions = ordered;
    if (!updateRefs) return;
    const holds = (slots) => Object.values(slots || {}).some((v) => v?.asset === assetKey);
    for (const s of d.shots) {
      const shotHolds = holds(s.slots);
      if (shotHolds) { if (s.params) s.params = replaceRegionRefs(s.params, from, to); if (s.transition_in?.params) s.transition_in.params = replaceRegionRefs(s.transition_in.params, from, to); }
      for (const o of s.overlays || []) if ((shotHolds || holds(o.slots)) && o.params) o.params = replaceRegionRefs(o.params, from, to);
    }
  });
}
