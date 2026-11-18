// Pure helpers of the "Chọn hình" view (no DOM, no network): editing the picks document and the arithmetic of regions.
// Tested in tests/picks/picks_logic.test.mjs. A "doc" is the `picks` object of GET /api/projects/{pid}/picks.
export const ROLES = ['main', 'detail', 'context', 'compare', 'document', 'map', 'video'];
export const MIN_SHORT = 1200;

export const clone = (o) => JSON.parse(JSON.stringify(o));

/** The beat record of `id`, created (empty, "todo") when the document has none. */
export function ensureBeat(doc, id) {
  if (!doc.beats[id]) doc.beats[id] = { items: [], status: 'todo', note: '' };
  return doc.beats[id];
}

/** Role of a new item: a video asset is "video", the whole main painting is "main", a region of anything is a "detail", any other picture is "context". */
export function defaultRole(doc, assetKey, region) {
  if (doc?.assets?.[assetKey]?.kind === 'video') return 'video';
  if (region) return 'detail';
  return doc.main_asset === assetKey ? 'main' : 'context';
}

/** Add an item to a beat (the beat becomes "picked"). Returns the index of the new item. */
export function addItem(doc, beatId, { asset, region = null, role = null, note = '' }) {
  const b = ensureBeat(doc, beatId);
  b.items.push({ asset, region: region || null, role: role || defaultRole(doc, asset, region), note });
  b.status = 'picked';
  return b.items.length - 1;
}

export function removeItem(doc, beatId, i) {
  const b = doc.beats[beatId];
  if (!b || !b.items[i]) return false;
  b.items.splice(i, 1);
  if (!b.items.length && b.status === 'picked') b.status = 'todo';
  return true;
}

/** Move item `i` by `dir` (-1 up, +1 down). Returns the new index (the same when it cannot move). */
export function moveItem(doc, beatId, i, dir) {
  const b = doc.beats[beatId];
  const j = i + dir;
  if (!b || !b.items[i] || j < 0 || j >= b.items.length) return i;
  [b.items[i], b.items[j]] = [b.items[j], b.items[i]];
  return j;
}

export function setItem(doc, beatId, i, patch) {
  const it = doc.beats[beatId]?.items[i];
  if (it) Object.assign(it, patch);
  return !!it;
}

/** "Skip this beat": it is not counted as missing. Turning it off goes back to "picked" or "todo". */
export function toggleSkip(doc, beatId) {
  const b = ensureBeat(doc, beatId);
  b.status = b.status === 'skip' ? (b.items.length ? 'picked' : 'todo') : 'skip';
  return b.status;
}

export const countPicks = (doc, beatId) => doc.beats[beatId]?.items.length || 0;
export const beatStatus = (doc, beatId) => doc.beats[beatId]?.status || 'todo';

/** {done, total}: beats of a chapter that have a pick or are skipped. */
export function chapterProgress(chapter, doc) {
  const total = chapter.beats.length;
  const done = chapter.beats.filter((b) => countPicks(doc, b.id) > 0 || beatStatus(doc, b.id) === 'skip').length;
  return { done, total };
}

/** Beats that have no pick and are not skipped, in narration order. */
export function emptyBeats(chapters, doc) {
  return chapters.flatMap((c) => c.beats).filter((b) => !countPicks(doc, b.id) && beatStatus(doc, b.id) !== 'skip').map((b) => b.id);
}

/** Remove the items that point at `assetKey` (and the main painting when it is that one). */
export function dropAsset(doc, assetKey) {
  delete doc.assets[assetKey];
  if (doc.main_asset === assetKey) doc.main_asset = null;
  for (const b of Object.values(doc.beats)) {
    b.items = b.items.filter((i) => i.asset !== assetKey);
    if (!b.items.length && b.status === 'picked') b.status = 'todo';
  }
}

// ---------------------------------------------------------------- regions
const NAME_OK = /^[A-Za-z0-9_][A-Za-z0-9_ .-]{0,39}$/;
export const regionNameOk = (n) => NAME_OK.test(String(n || ''));

/** A region name that is not used yet: `want` itself, or `want_2`, `want_3`... */
export function freeRegionName(existing, want) {
  const base = String(want || 'VUNG').trim().replace(/[^A-Za-z0-9_ .-]/g, '').slice(0, 34) || 'VUNG';
  if (!(base in existing)) return base;
  for (let n = 2; n < 1000; n++) if (!(`${base}_${n}` in existing)) return `${base}_${n}`;
  return base;
}

/** A circle drawn from its centre `p0` to a point `p1` of the pointer (source pixels), kept inside the picture. */
export function circleFromDrag(p0, p1, w, h) {
  const r = Math.max(8, Math.round(Math.hypot(p1[0] - p0[0], p1[1] - p0[1])));
  const x = Math.min(Math.max(Math.round(p0[0]), 0), w || Infinity), y = Math.min(Math.max(Math.round(p0[1]), 0), h || Infinity);
  return { x, y, rx: r, ry: r };
}

/** CSS of a square box that shows only a region of an image (used for the thumbnail of an item with a region).
 *  `box` px is the side; the region's circle fills the box. The background is scaled from the asset's size, so it works with
 *  any resized copy of the image. */
export function cropStyle(asset, region, box = 64) {
  if (!asset?.width || !asset?.height || !region) return null;
  const d = 2 * Math.max(region.rx || 120, region.ry || 120);
  const k = box / d;
  return { backgroundSize: `${Math.round(asset.width * k)}px ${Math.round(asset.height * k)}px`,
    backgroundPosition: `${Math.round(box / 2 - region.x * k)}px ${Math.round(box / 2 - region.y * k)}px` };
}

// ---------------------------------------------------------------- what to show
export const FLAG_ORDER = ['rejected', 'unknown', 'small'];
export const sizeText = (w, h) => (w && h ? `${w}×${h}` : 'chưa biết kích thước');
export const isSmall = (w, h) => !!(w && h && Math.min(w, h) < MIN_SHORT);

/** `show` words of a beat that are names of dossier details ("D5") are shown with the dossier's name. */
export function showWords(show, details) {
  const names = Object.fromEntries((details || []).map((d) => [d.id, d.label]));
  return (show || []).map((w) => ({ raw: w, text: names[w] ? `${w}: ${names[w]}` : w, query: names[w] || w, detail: !!names[w] }));
}

/** Names to offer when the owner draws a region: the dossier's details (D1...) not yet used on this asset. */
export function regionNameChoices(details, regions) {
  return (details || []).filter((d) => !(d.id in (regions || {}))).map((d) => ({ name: d.id, label: d.label }));
}
