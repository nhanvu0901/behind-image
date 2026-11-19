// The list of shots of the simple page of step 5 ("Dựng hình"): rows, chapters, problems in words, the numbers of the header. Pure: no DOM, no network.
// Tested in tests/editor_frontend/shotlist.test.mjs. The sentence of a shot is shotsentence.js; the words are labels.js (EDIT_PAGE_LABELS).
import { shotSentence } from './shotsentence.js';
import { issueTarget } from './sbissues.js';
import { EDIT_PAGE_LABELS as W } from './labels.js';
import { minSec, durationWords, chapterId, chapterAt } from './editlogic.js';
import { wordIndexAt } from './logic.js';

/** A name written as an id ("THE_MIRROR", "THE MERCHANT CITY") read as words: "The mirror", "The merchant city". */
const asWords = (s) => {
  const t = s.replace(/_/g, ' ').replace(/\s+/g, ' ').trim();
  return t.length > 2 && t === t.toUpperCase() && t !== t.toLowerCase() ? t[0] + t.slice(1).toLowerCase() : t;
};

/** "Chương 2 · Gương" when the chapter has a name, "Chương 2" when it has not or when the name is only an id such as "c03". */
export function chapterTitle(ch, i) {
  const name = typeof ch?.name === 'string' ? ch.name.trim() : (typeof ch?.title === 'string' ? ch.title.trim() : '');
  const n = (i < 0 ? 0 : i) + 1;
  return !name || /^c\d+$/i.test(name) ? W.chapter.n(n) : W.chapter.named(n, asWords(name));
}

// ---------------------------------------------------------------- problems
/** What kind of trouble an issue is (a word of W.problems.text) and whether the page counts it ("cần sửa"): an error, or a shot that is not complete or cannot be drawn. */
export function problemKind(issue) {
  const code = String(issue?.code || '');
  let kind = 'other';
  if (code === 'incomplete') kind = 'incomplete';
  else if (code === 'undrawable') kind = 'undrawable';
  else if (/^asset_|^slot_asset_kind$|^param_not_asset$|^unknown_slot$|^asset_undefined$/.test(code)) kind = 'asset';
  else if (code === 'region_undefined' || code === 'region_needs_image') kind = 'region';
  else if (code === 'shot_too_short' || code === 'element_too_short') kind = 'short';
  else if (/^overlay_(outside_shot|ends_before_start|dur)$/.test(code)) kind = 'outside';
  else if (/^(anchor_invalid|stale_anchor|camera_keys_order|camera_rel_range|start_negative|shots_out_of_order)$/.test(code)) kind = 'time';
  return { kind, counted: issue?.level === 'error' || kind === 'incomplete' || kind === 'undrawable' };
}

/** The counted problems of the storyboard: { byShot: Map(shot id -> [{kind, text, overlay}]), general: [{kind, text}] }. The same sentence for the same shot is kept once.
 *  A problem about the whole video (no shot) is "general". The sentences have no id, no technique and no parameter name. */
export function problemsOf(issues, draft) {
  const byShot = new Map(), general = [];
  const seen = new Set();
  for (const i of issues || []) {
    const { kind, counted } = problemKind(i);
    if (!counted) continue;
    const tg = issueTarget(i, draft);
    const text = W.problems.text[kind];
    if (tg.kind === 'shot') {
      const shot = draft.shots[tg.shot];
      const key = `${shot.id}|${kind}|${tg.overlay != null ? 'o' : ''}`;
      if (seen.has(key)) continue;
      seen.add(key);
      if (!byShot.has(shot.id)) byShot.set(shot.id, []);
      byShot.get(shot.id).push({ kind, text, overlay: tg.overlay != null ? (shot.overlays || [])[tg.overlay]?.id || null : null });
    } else if (tg.kind === 'asset' && tg.shots.length) {
      for (const sid of tg.shots) {
        const key = `${sid}|${kind}|`;
        if (seen.has(key)) continue;
        seen.add(key);
        if (!byShot.has(sid)) byShot.set(sid, []);
        byShot.get(sid).push({ kind, text, overlay: null });
      }
    } else if (!seen.has('g|' + kind)) { seen.add('g|' + kind); general.push({ kind, text: kind === 'other' ? W.problems.generalText : text }); }
  }
  return { byShot, general };
}

// ---------------------------------------------------------------- the rows
/** Everything the page draws, from the draft with its derived times (`_t0`, `_t1`).
 *  -> { rows: [{id, index, number, t0, t1, time, length, sentence, locked, problems, group}],
 *       groups: [{key, index, title, number, ids, t0, t1, problems}], order: [ids], chapterRows: {key: [ids]}, summary: {shots, seconds, problemShots, general} }
 *  `chapters`: timing.chapters ([{id?, name, start, end}] or word ranges); `words`: timing.words (for chapters that carry only word ranges). */
export function buildShotList({ draft, chapters = [], words = [], issues = [], env = {} } = {}) {
  const shots = draft?.shots || [];
  const probs = problemsOf(issues, draft || { shots: [] });
  const byWord = chapters.some((c) => c.start == null);
  const groups = [], groupOf = new Map();
  const rows = shots.map((s, index) => {
    const t0 = Number.isFinite(s._t0) ? s._t0 : 0, t1 = Number.isFinite(s._t1) ? s._t1 : t0;
    let gi = -1;
    if (chapters.length) { const c = chapterAt(chapters, t0, byWord ? wordIndexAt(words, t0) : -1); gi = c ? chapters.indexOf(c) : 0; }
    const key = gi >= 0 ? chapterId(chapters[gi], gi) : 'all';
    if (!groupOf.has(key)) { const g = { key, index: groups.length, title: gi >= 0 ? chapterTitle(chapters[gi], gi) : '', number: gi + 1, ids: [], t0, t1, problems: 0 }; groups.push(g); groupOf.set(key, g); }
    const g = groupOf.get(key);
    const pr = probs.byShot.get(s.id) || [];
    g.ids.push(s.id); g.t1 = t1; g.problems += pr.length ? 1 : 0;
    return { id: s.id, index, number: index + 1, t0, t1, time: minSec(t0), length: durationWords(t1 - t0), sentence: shotSentence(s, env), locked: !!s.locked,
      problems: pr, group: key };
  });
  const problemShots = rows.filter((r) => r.problems.length).length;
  return {
    rows, groups, order: rows.map((r) => r.id),
    chapterRows: Object.fromEntries(groups.map((g) => [g.key, g.ids])),
    summary: { shots: rows.length, seconds: rows.length ? rows[rows.length - 1].t1 : 0, problemShots, general: probs.general.length },
    general: probs.general,
  };
}

/** The first row with a problem after row `fromId` (or the first at all): where "2 cảnh cần sửa" leads. */
export function nextProblem(list, fromId = null) {
  const bad = list.rows.filter((r) => r.problems.length);
  if (!bad.length) return null;
  const i = fromId ? bad.findIndex((r) => r.index > (list.rows.find((x) => x.id === fromId)?.index ?? -1)) : 0;
  return bad[i >= 0 ? i : 0];
}

/** The line of the header: "93 cảnh · 14:24". */
export const summaryText = (summary) => `${W.shots(summary.shots)} · ${minSec(summary.seconds)}`;

/** The words spoken from t0 to t1 (for "Lời đang đọc"), at most `max` characters. */
export function spokenText(words, t0, t1, max = 200) {
  const out = [];
  for (const w of words || []) if (Number.isFinite(w?.s) && w.s >= t0 - 1e-6 && w.s < t1 - 1e-6 && typeof w.w === 'string') out.push(w.w);
  const t = out.join(' ').replace(/\s+/g, ' ').trim();
  return t.length > max ? t.slice(0, max - 1).trimEnd() + '…' : t;
}

/** The numbers of the shots as the box says them: "12", "12, 13" ("12, 13, 14 và 3 cảnh nữa" past six). */
export function numbersText(nums) {
  const s = [...nums].sort((a, b) => a - b);
  return s.length > 6 ? `${s.slice(0, 6).join(', ')} và ${s.length - 6} cảnh nữa` : s.join(', ');
}

/** The approval as the header shows it. `ap`: draft.approvals.storyboard; `rev`: the revision that is open; `dirty`: unsaved edits; `problemShots`: shots to fix.
 *  -> { state: 'approved' | 'old' | 'none', label, canPress, why }   (`why`: what is still missing when it cannot be pressed) */
export function approveView({ ap = null, rev = null, dirty = false, problemShots = 0, approving = false } = {}) {
  const cur = !!ap && ap.rev === rev && !dirty;
  const state = cur ? 'approved' : ap ? 'old' : 'none';
  const label = approving ? W.top.approving : cur ? W.top.approved : W.top.approve;
  let why = '';
  if (!cur) { if (dirty) why = W.top.approveSave; else if (problemShots > 0) why = W.top.approveFix(problemShots); }
  return { state, label, canPress: !cur && !approving, why, current: cur };
}
