// The rows of the simple page of step 4 ("Chọn hình"): one row per narration line, with the pictures that will be on screen while it is spoken, a plain caption
// for each, the agent's reason, the count of lines without a picture, the numbers of the header and the three lists of what the project has.
// Pure: no DOM, no network. Tested in tests/editor_frontend/picksrows.test.mjs. The words are labels.js (PICKS_PAGE_LABELS).
import { PICKS_PAGE_LABELS as W } from '../labels.js';
import { minSec } from '../editlogic.js';

const ID_LOOKING = /^[A-Z0-9_]{2,}$/;
const text = (v) => (typeof v === 'string' ? v.replace(/\s+/g, ' ').trim() : '');

/** The first sentence of a line and the rest ("Xem cả đoạn" shows the rest). A line with one sentence has no rest. */
export function splitSentence(line) {
  const t = text(line);
  const m = /^(.+?[.!?…]["”')\]]*)\s+(.+)$/s.exec(t);
  return m ? { first: m[1], rest: m[2], hasMore: true } : { first: t, rest: '', hasMore: false };
}

/** The name of a region for a caption: its label, never its key. */
export function regionLabel(asset, key) {
  const label = text(asset?.regions?.[key]?.label);
  return label && !ID_LOOKING.test(label) ? label : '';
}

/** The plain caption under a picture of a line: "Cả bức tranh", "Cận cảnh: khuôn mặt", "Ảnh: ...", "Clip 6 giây: ...", "Bản đồ: ...". */
export function captionOf(item, assets, mainKey) {
  const a = assets?.[item?.asset];
  if (!a) return W.caption.gone;
  const title = text(a.title);
  if (a.kind === 'video' || item.role === 'video') {
    const d = Number(a.duration);
    return W.caption.clip(d > 0 ? Math.round(d) : 0, title);
  }
  if (item.region) { const l = regionLabel(a, item.region); return l ? W.caption.detail(l) : W.caption.detailAny; }
  if (item.role === 'main' || (item.asset === mainKey && item.role !== 'context' && item.role !== 'document' && item.role !== 'compare' && item.role !== 'map')) return W.caption.whole;
  if (item.role === 'map') return W.caption.map(title.replace(/^Bản đồ\s+/i, ''));
  if (item.role === 'document') return W.caption.document(title);
  if (item.role === 'compare') return W.caption.compare(title);
  return W.caption.image(title);
}

/** Start of each narration line (seconds) from the voice step's answer (GET /api/projects/{pid}/voice): the first chunk of the line. Only when the voice is done;
 *  while it is not, or after the narration changed, a time would be a guess and the rows say no time. -> Map(beat id -> seconds) */
export function voiceStarts(voice) {
  const out = new Map();
  if (!voice || voice.state !== 'done') return out;
  for (const c of voice.chunks || []) {
    if (!c?.beat || !Number.isFinite(c.start)) continue;
    if (!out.has(c.beat) || c.start < out.get(c.beat)) out.set(c.beat, c.start);
  }
  return out;
}

const chapterName = (c, i) => {
  const name = text(c?.title);
  const n = i + 1;
  return !name || /^c\d+$/i.test(name) ? W.chapter.n(n) : W.chapter.named(n, ID_LOOKING.test(name) || (name === name.toUpperCase() && name !== name.toLowerCase()) ? name[0] + name.slice(1).toLowerCase().replace(/_/g, ' ') : name);
};

/** What the page draws for the lines. `chapters`: [{id, title, beats: [{id, text}]}] of the narration; `doc`: the picks document; `starts`: Map beat -> seconds;
 *  `reasonFor(beatId, rec)`: the agent's reason for a line ('' when the line is no longer as the agent wrote it).
 *  -> { rows: [{id, number, time, first, rest, hasMore, status, pics, reason, group}], groups: [{key, index, title, ids, done, total}], order, chapterRows, counts } */
export function pickRows({ chapters = [], doc = null, starts = new Map(), reasonFor = null } = {}) {
  const D = doc || { beats: {}, assets: {}, main_asset: null };
  const rows = [], groups = [];
  let n = 0;
  chapters.forEach((c, ci) => {
    const g = { key: c.id || `c${ci + 1}`, index: ci, title: chapterName(c, ci), ids: [], done: 0, total: 0 };
    groups.push(g);
    for (const b of c.beats || []) {
      n++;
      const rec = D.beats?.[b.id] || { items: [], status: 'todo', note: '' };
      const items = rec.items || [];
      const status = items.length ? 'picked' : rec.status === 'skip' ? 'skip' : 'empty';
      const t = starts.get(b.id);
      const { first, rest, hasMore } = splitSentence(b.text);
      rows.push({
        id: b.id, number: n, time: Number.isFinite(t) ? minSec(t) : '', t0: Number.isFinite(t) ? t : null, first, rest, hasMore, status, note: rec.note || '',
        pics: items.map((it, index) => ({ index, key: it.asset, region: it.region || null, role: it.role || '', caption: captionOf(it, D.assets, D.main_asset), gone: !D.assets?.[it.asset],
          video: D.assets?.[it.asset]?.kind === 'video' || it.role === 'video', flag: D.assets?.[it.asset]?.credit?.flag || null })),
        reason: reasonFor ? text(reasonFor(b.id, rec)) : '', group: g.key,
      });
      g.ids.push(b.id); g.total++;
      if (items.length || status === 'skip') g.done++;
    }
  });
  const missing = rows.filter((r) => r.status === 'empty').map((r) => r.id);
  const withPics = rows.filter((r) => r.pics.length).length;
  return {
    rows, groups, order: rows.map((r) => r.id), chapterRows: Object.fromEntries(groups.map((g) => [g.key, g.ids])),
    counts: { total: rows.length, withPics, skipped: rows.filter((r) => r.status === 'skip').length, missing, missingCount: missing.length },
  };
}

/** The line a click on "3 đoạn chưa có hình" leads to: the first one without a picture, then the next after the one given. Goes round. null when none. */
export function nextMissing(list, fromId = null) {
  const bad = list.rows.filter((r) => r.status === 'empty');
  if (!bad.length) return null;
  if (!fromId) return bad[0];
  const at = list.rows.find((r) => r.id === fromId)?.number ?? 0;
  return bad.find((r) => r.number > at) || bad[0];
}

/** The numbers of the header: "25/28 đoạn đã có hình" (pictures or skipped), "3 đoạn chưa có hình", "2 đoạn bỏ qua". */
export function headerNumbers(counts) {
  const settled = counts.withPics + counts.skipped;                          // a line that needs no picture of its own is settled, as the agent's sentence counts it
  return {
    progress: counts.total ? W.progress(settled, counts.total) : W.noLines,
    missing: counts.missingCount ? W.missing(counts.missingCount) : '',
    skipped: counts.skipped ? W.skipped(counts.skipped) : '',
    fraction: counts.total ? settled / counts.total : 0,
  };
}

/** The button "Duyệt chọn hình": can it be pressed, and what is still missing when it cannot. `d`: GET .../picks; `doc`: the document the page holds (the saved one when null); `dirty`: unsaved edits; `emptyCount`: lines without a picture. */
export function approveState({ d, doc = null, dirty = false, emptyCount = 0, busy = false } = {}) {
  const nv = d?.narration || {};
  const errs = (d?.issues || []).filter((i) => i.level === 'error');
  const noMain = !(doc || d?.picks)?.main_asset;
  let why = '';
  if (!nv.present) why = W.approveWhy.noNarration;
  else if (!nv.approved) why = W.approveWhy.narration;
  else if (noMain) why = W.approveWhy.main;
  else if (errs.length) why = W.approveWhy.errors(errs.length);
  else if (busy) why = W.approveWhy.saving;
  const approved = !!d?.approved && !dirty;
  const note = !why && !approved ? (d?.approval_reason ? W.approveWhy.again : emptyCount ? W.approveWhy.emptyLines(emptyCount) : '') : '';
  return { approved, label: approved ? W.top.approved : W.top.approve, canPress: !why && !approved && !busy, why, note, errors: errs.length };
}

/** What stands in the way of the page, once: no lines, no main painting, or a narration that is not approved (the pictures can still be chosen, not approved). -> { kind, text } | null */
export function pageBlocker(d, doc = null) {
  const nv = d?.narration || {};
  if (!nv.present) return { kind: 'no_narration', text: W.approveWhy.noNarration };
  if (!(doc || d?.picks)?.main_asset) return { kind: 'no_main', text: W.main.none + ' ' + W.main.noneHelp };
  if (!nv.approved) return { kind: 'narration_unapproved', text: nv.reason === 'narration_edited' ? W.approveWhy.narrationEdited : W.approveWhy.narrationSoft };
  return null;
}

// ---------------------------------------------------------------- the three lists: the regions of the main painting, the context pictures, the clips
/** For each thing the project has, where it is used (the numbers of the lines). -> { regions: [{key, label, usedIn}], context: [{key, title, usedIn, flag}], clips: [{key, title, seconds, usedIn}] } */
export function sectionsOf(doc, rows) {
  const D = doc || { assets: {}, beats: {}, main_asset: null };
  const numberOf = new Map((rows || []).map((r) => [r.id, r.number]));
  const used = (pred) => [...new Set(Object.entries(D.beats || {}).flatMap(([bid, rec]) => ((rec.items || []).some(pred) && numberOf.has(bid) ? [numberOf.get(bid)] : [])))].sort((a, b) => a - b);
  const main = D.assets?.[D.main_asset];
  const regions = Object.entries(main?.regions || {}).map(([key]) => ({ key, label: regionLabel(main, key) || W.sections.regionUnnamed, usedIn: used((it) => it.asset === D.main_asset && it.region === key) }));
  const others = Object.entries(D.assets || {}).filter(([k]) => k !== D.main_asset);
  const context = others.filter(([, a]) => a.kind !== 'video').map(([key, a]) => ({ key, title: text(a.title) || W.caption.image(''), usedIn: used((it) => it.asset === key), flag: a.credit?.flag || null }));
  const clips = others.filter(([, a]) => a.kind === 'video').map(([key, a]) => ({ key, title: text(a.title) || W.caption.clip(0, ''), seconds: Number(a.duration) > 0 ? Math.round(Number(a.duration)) : 0, usedIn: used((it) => it.asset === key) }));
  return { regions, context, clips };
}

/** The scope words of the request box on this page ("2 đoạn đang chọn (4, 5)"): the numbers of the selected lines, in order. */
export const selectedNumbers = (ids, rows) => { const by = new Map((rows || []).map((r) => [r.id, r.number])); return ids.map((id) => by.get(id)).filter((x) => x != null).sort((a, b) => a - b); };

// ---------------------------------------------------------------- the check of the picks, in words with no line id ("Kiểm tra" on the simple page)
/** One issue of GET .../picks in a sentence that names a line by its number and a picture by its title, never by an id. `numberOf(beatId)`: the number of a line. */
export function issueSentence(issue, { numberOf = () => null, assets = {} } = {}) {
  const n = issue?.beat ? numberOf(issue.beat) : null;
  const line = n ? W.lineNo(n) : W.issue.aLine;
  const pic = text(assets?.[issue?.asset]?.title);
  switch (issue?.code) {
    case 'no_main': return W.issue.noMain;
    case 'beat_no_pick': return W.issue.noPick(line);
    case 'outside_no_picture': return W.issue.outsideNoPicture(line);          // a line about something outside the painting that shows only the main painting
    case 'unknown_asset': return W.issue.unknownAsset(line);
    case 'unknown_region': return W.issue.unknownRegion(line);
    case 'beat_unknown': return W.issue.beatUnknown;
    case 'asset_file_missing': return W.issue.fileMissing(pic);
    case 'asset_flag': return W.issue.flag(pic, issue.flag);
    default: return issue?.level === 'error' ? W.issue.otherError : W.issue.otherWarn;
  }
}
