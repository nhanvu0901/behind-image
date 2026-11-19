// Pure helpers of the "Chọn hình" view (no DOM, no network): editing the picks document and the arithmetic of regions.
// Tested in tests/picks/picks_logic.test.mjs. A "doc" is the `picks` object of GET /api/projects/{pid}/picks.
export const ROLES = ['main', 'detail', 'context', 'compare', 'document', 'map', 'video'];
export const VIDEO_ROLES = ['video', 'context', 'compare'];
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

// ---------------------------------------------------------------- c3picks: "Để agent chọn hình" (the agent chooses the pictures)
// The decisions of the button, the progress line and the result sentence; no DOM, no network. The words are PICKS_AUTO_LABELS (labels.js).
// The server writes the same result sentence in `result.sentence` (bti/picks/auto/texts.py); a test keeps the two equal.
import { PICKS_AUTO_LABELS as AL } from '../labels.js';

export const AUTO_ACTIVE = ['queued', 'waiting', 'running'];
export const autoRunning = (job) => !!job && AUTO_ACTIVE.includes(job.state);

/** The result of a finished run in one sentence, from its numbers: "Agent đã chọn hình cho 25/28 đoạn. 3 đoạn chưa có hình phù hợp." ('' for no result). */
export function autoResultText(result) {
  if (!result || !Number.isFinite(result.lines_total) || !Number.isFinite(result.lines_done)) return '';
  const without = Array.isArray(result.lines_without) ? result.lines_without.length : 0;
  return `Agent đã chọn hình cho ${result.lines_done}/${result.lines_total} đoạn.` + (without > 0 ? ` ${without} đoạn chưa có hình phù hợp.` : '');
}

/** The second line of a result: what was made ("9 hình mới, 6 vùng chi tiết, 2 clip."), '' when nothing. */
export function autoDetailText(result) {
  if (!result) return '';
  const parts = [];
  if (result.pictures_imported > 0) parts.push(AL.detail.pictures(result.pictures_imported));
  if (result.regions_made > 0) parts.push(AL.detail.regions(result.regions_made));
  if (result.clips > 0) parts.push(AL.detail.clips(result.clips));
  if (result.lines_kept > 0) parts.push(AL.detail.kept(result.lines_kept));
  if (result.lines_by_others > 0) parts.push(AL.detail.others(result.lines_by_others));
  return parts.length ? parts.join(', ') + '.' : '';
}

/** What the controls of the agent's bar do now. `st`: {doc, chapters, job, approved, narrationOk, hasMain, agentUsable, last}.
 *  start: "Để agent chọn hình" (works on the lines without pictures; when every line is settled or the picks are approved it needs the owner's
 *  word first: `confirm: 'redo'`, and the request says `redo`). again: "Chọn lại phần còn thiếu", only after a run, only while lines still have
 *  no picture. cancel: while the job runs. `select`: the agent select is locked while it runs. `body` is what is sent to POST .../picks/auto. */
export function autoControls(st) {
  const running = autoRunning(st.job);
  const missing = emptyBeats(st.chapters || [], st.doc || { beats: {} });
  const total = (st.chapters || []).reduce((n, c) => n + c.beats.length, 0);
  let why = '';
  if (running) why = AL.disabled.running;
  else if (!st.narrationOk) why = AL.disabled.narration;
  else if (!st.hasMain) why = AL.disabled.main;
  else if (st.agentUsable === false) why = AL.disabled.agent;
  const redo = !!st.approved || (total > 0 && missing.length === 0);
  return {
    running,
    missing,
    start: { disabled: !!why, title: why, confirm: redo ? 'redo' : null, body: { beats: null, redo } },
    again: { visible: !running && !!st.last && missing.length > 0 && !!st.hasMain && !!st.narrationOk, disabled: st.agentUsable === false,
      confirm: st.approved ? 'approved' : null, body: { beats: missing, redo: !!st.approved } },
    cancel: { visible: running },
    select: { disabled: running },
  };
}

/** The progress line of a running job: the part that works now ("Tìm hình (2/4) - Đang tìm hình 3/12: ..."), and how far it is (0 to 1). */
export function autoProgress(job) {
  if (!autoRunning(job)) return { text: '', fraction: 0 };
  const parts = job.parts || [];
  const p = parts.find((x) => x.state === 'running') || parts.find((x) => x.state === 'waiting');
  const text = !p ? AL.starting : p.state === 'waiting' ? `${p.title} - ${p.note || AL.waiting}` : p.note ? `${p.title} - ${p.note}` : p.title;
  return { text, fraction: Math.max(0, Math.min(1, Number(job.progress) || 0)) };
}

/** The agent's reason to show under the pictures of a line: only while the line is still as the agent wrote it (its note is the reason it
 *  gave, and it has pictures or needs none). `reasons` is {beat id: reason} of GET .../picks/auto. */
export function autoReasonFor(rec, reasons, beatId) {
  const why = reasons?.[beatId];
  if (!why || !rec || rec.note !== why) return '';
  return (rec.items?.length || rec.status === 'skip') ? why : '';
}

/** The lines the last run could not fill, for the list under the result: [{no, text}] (`text` is the sentence of why). */
export const autoWithout = (result) => (Array.isArray(result?.lines_without) ? result.lines_without.map((w) => ({ no: w.no, text: AL.withoutLine(w.no, w.why) })) : []);

/** What a line that DID get pictures is still missing, for the list under the result: the sentences of why (lines the run left without pictures are in `autoWithout`). */
export function autoMissing(result) {
  const out = new Set((result?.lines_without || []).map((w) => w.beat));
  return (result?.missing || []).filter((m) => !out.has(m.beat) && typeof m.why === 'string' && m.why).map((m) => m.why);
}

