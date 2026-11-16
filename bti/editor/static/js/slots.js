// Pure rules about slots and about what is "incomplete" (design rules 1 to 3 of the front-end fix round):
//  - a slot takes only an asset of its own kind: image, video or mask (these are different kinds);
//  - an overlay may carry slots like a shot;
//  - an item with an empty required slot is INCOMPLETE: saved normally, never approved.

/** image | video | mask | text. The registry says "image" for a mask slot, so the name decides (mask, mask_1 ... mask_6). */
export const slotKind = (sl) => (sl.type === 'mask' || (sl.type === 'image' && /^mask(_\d+)?$/.test(sl.name)) ? 'mask' : sl.type);
export const assetKind = (a) => (a?.kind === 'video' ? 'video' : a?.kind === 'mask' ? 'mask' : 'image');
export const KIND_VI = { image: 'ảnh', video: 'video', mask: 'mặt nạ (mask)', text: 'chữ' };
export const fits = (sl, asset) => slotKind(sl) !== 'text' && !!asset && slotKind(sl) === assetKind(asset);
/** Why an asset cannot go into a slot ('' when it can). */
export const whyNot = (sl, asset) => (fits(sl, asset) ? '' : `Slot "${sl.name}" cần ${KIND_VI[slotKind(sl)] || slotKind(sl)}, hình này là ${KIND_VI[assetKind(asset)]}.`);

/** The slots a shot (or overlay) keeps when its technique changes. Same-name slots stay when the asset still fits; empty slots
 * then take the OLD assets of kind image, in order, but only into image slots: never the painting into a video or mask slot. */
export function carrySlots(newSlots, oldSlots, assets) {
  const out = {};
  const used = new Set();
  for (const sl of newSlots) {
    const cur = oldSlots?.[sl.name];
    if (!cur) continue;
    if (slotKind(sl) === 'text') { if (cur.text != null) out[sl.name] = { ...cur }; continue; }
    if (cur.asset && fits(sl, assets[cur.asset])) { out[sl.name] = { ...cur }; used.add(cur.asset); }
  }
  const spare = Object.values(oldSlots || {}).map((v) => v?.asset).filter((k) => k && assetKind(assets[k]) === 'image' && !used.has(k));
  let i = 0;
  for (const sl of newSlots) {
    if (out[sl.name] || slotKind(sl) !== 'image' || i >= spare.length) continue;
    out[sl.name] = { asset: spare[i++] };
  }
  return out;
}

/** The asset an item uses for a slot. An overlay without its own `image` entry draws over its shot's picture; every other
 * overlay slot (mask, ...) is the overlay's own (engine: slot_key(overlay, name)). */
export function effectiveSlot(item, slotName, shot, isOverlay) {
  const own = item.slots?.[slotName];
  if (own && (own.asset || own.text)) return { ...own, own: true };
  if (isOverlay && shot && slotName === 'image') {          // the engine draws an overlay over its shot's picture; every other slot is the overlay's own
    const inh = shot.slots?.image;
    if (inh?.asset) return { ...inh, own: false };
    for (const v of Object.values(shot.slots || {})) if (v?.asset) return { ...v, own: false };
  }
  return null;
}

/** Empty required slots of an item: [{name, kind}] */
export function missingSlots(item, tech, shot, isOverlay) {
  const out = [];
  for (const sl of tech?.slots || []) {
    if (!sl.required) continue;
    const e = effectiveSlot(item, sl.name, shot, isOverlay);
    // a text "slot" is filled through the parameter of the same name (engine: p["title"], p["text"]); slots.<name>.text is accepted too
    const ok = slotKind(sl) === 'text' ? !!(String(item.params?.[sl.name] ?? '').trim() || e?.text) : !!(e && e.asset);
    if (!ok) out.push({ name: sl.name, kind: slotKind(sl) });
  }
  return out;
}

const NAME_RE = /(?:slot|param(?:eter)?)\s+['"]([^'"]+)['"]/i;
export const isIncompleteIssue = (i) => i?.code === 'incomplete';
/** The missing names an `incomplete` issue talks about. */
export function issueMissing(issue) {
  if (Array.isArray(issue.missing) && issue.missing.length) return issue.missing.map(String);
  const m = String(issue.message || '').match(NAME_RE);
  return [m ? m[1] : String(issue.message || 'chưa đủ')];
}
/** Issue path ("shots[3].overlays[0].slots.mask") -> key 'sNNNN' or 'sNNNN/oN' of the item it belongs to. */
export function itemKeyOfPath(draft, path) {
  const m = String(path || '').match(/^shots\[(\d+)\](?:\.overlays\[(\d+)\])?/);
  if (!m) return null;
  const s = draft.shots[+m[1]];
  if (!s) return null;
  if (m[2] == null) return s.id;
  const o = (s.overlays || [])[+m[2]];
  return o ? `${s.id}/${o.id}` : null;
}

/** Map item key -> sorted unique missing names, from the registry rules (immediate) and the server's `incomplete` issues. */
export function incompleteMap(draft, techOf, issues) {
  const map = new Map();
  const add = (key, name) => { if (!map.has(key)) map.set(key, new Set()); map.get(key).add(name); };
  for (const s of draft?.shots || []) {
    for (const m of missingSlots(s, techOf(s.technique), s, false)) add(s.id, m.name);
    for (const o of s.overlays || []) for (const m of missingSlots(o, techOf(o.technique), s, true)) add(`${s.id}/${o.id}`, m.name);
  }
  for (const i of issues || []) {
    if (!isIncompleteIssue(i)) continue;
    const key = itemKeyOfPath(draft, i.path);
    if (key) for (const n of issueMissing(i)) add(key, n);
  }
  return new Map([...map].map(([k, v]) => [k, [...v].sort()]));
}
export const missingLabel = (names) => `thiếu: ${names.join(', ')}`;

/** Where a region name is used: every string equal to `name` inside params (deep). Returns [{path, param}]. */
export function scanRegionRefs(params, name, base = 'params') {
  const out = [];
  const walk = (v, path, param) => {
    if (typeof v === 'string') { if (v === name) out.push({ path, param }); }
    else if (Array.isArray(v)) v.forEach((x, i) => walk(x, `${path}[${i}]`, param));
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) walk(x, `${path}.${k}`, param || k);
  };
  for (const [k, v] of Object.entries(params || {})) walk(v, `${base}.${k}`, k);
  return out;
}
/** Replace every string equal to `from` inside a value (deep); `to` may be any value (a name or an [x, y]). Returns the new value. */
export function replaceRegionRefs(v, from, to) {
  if (typeof v === 'string') return v === from ? (Array.isArray(to) ? [...to] : to) : v;
  if (Array.isArray(v)) return v.map((x) => replaceRegionRefs(x, from, to));
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, replaceRegionRefs(x, from, to)]));
  return v;
}

/** All uses of a region of asset `assetKey` in the draft: items whose slots hold that asset (an overlay sees its shot's slots too)
 * and whose params name the region. Returns [{shotId, overlayId|null, technique, param, where}] */
export function regionUsage(draft, assetKey, name) {
  const out = [];
  const holds = (slots) => Object.values(slots || {}).some((v) => v?.asset === assetKey);
  for (const s of draft.shots) {
    const shotHolds = holds(s.slots);
    const items = [{ it: s, ov: null, ok: shotHolds }, ...(s.overlays || []).map((o) => ({ it: o, ov: o, ok: shotHolds || holds(o.slots) }))];
    for (const { it, ov, ok } of items) {
      if (!ok) continue;
      const refs = scanRegionRefs(it.params, name);
      if (it === s && s.transition_in) refs.push(...scanRegionRefs(s.transition_in.params, name, 'transition_in.params'));
      for (const r of refs) out.push({ shotId: s.id, overlayId: ov ? ov.id : null, technique: it.technique, param: r.param, where: ov ? `${s.id}/${ov.id}` : s.id });
    }
  }
  return out;
}
