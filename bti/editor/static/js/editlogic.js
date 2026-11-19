// The pure parts of "edit the storyboard by a typed instruction" (promptedit.js draws; this file decides).
// No DOM, no network. Tested in tests/editor_frontend/editlogic.test.mjs.
//   scope words, the default scope, the turn card data for every status, the progress line, the clock, the preview range.
import { STAGE_CODES, isVietnamese } from './errmsg.js';
import { EDIT_LABELS as L, BOX_LABELS as BL } from './labels.js';

export const ACTIVE = new Set(['queued', 'waiting', 'running']);
export const TURN_STATUS = ['running', 'applied', 'no_change', 'needs_choice', 'failed', 'cancelled', 'undone', 'escalate'];
/** Every code the edit, resolve, undo, frames and thread routes (and the job behind them) can answer. Each has a sentence (tested). */
export const EDIT_CODES = [
  'edit_empty_instruction', 'edit_bad_scope', 'bad_model', 'scope_needs_storyboard', 'stale_revision', 'busy', 'agy_missing',
  'unknown_chapter', 'edit_needs_agy', 'edit_no_storyboard', 'edit_outside_scope', 'edit_no_change', 'edit_locked_changed', 'edit_degraded',
  'compile_error', 'compile_empty', 'spec_invalid', 'escalate', 'draft_no_output', 'draft_tampered', 'cancelled', 'interrupted',
  'bad_action', 'not_needs_choice', 'turn_data_lost', 'already_undone', 'turn_not_applied', 'undo_unavailable', 'undo_conflict', 'undo_failed',
  'real_models_off', 'edit_failed', 'agy_busy', 'agy_config', 'agy_auth', 'agy_error', 'agy_model', 'agy_no_result', 'agy_rate_limit', 'agy_timeout',
  'timing_shape', 'picks_shape', 'picks_no_main', 'main_asset_unreadable', 'storyboard_corrupt', 'project_missing', 'template_missing', 'workspace_invalid',
  'claude_missing', 'claude_auth', 'claude_rate_limit', 'claude_model', 'claude_config', 'claude_outdated', 'claude_error', 'claude_no_result', 'claude_timeout',      // worker claudeprov (claude_outdated: worker followups)
  // c2box: what a turn of the typed operations can end with (the operations' own codes are in STAGE_CODES.ops) and what its routes can answer
  'unknown_op', 'out_of_scope', 'locked', 'validation_failed', 'unknown_shot', 'unknown_overlay', 'unknown_beat', 'unknown_asset', 'unknown_region', 'unknown_param',
  'unknown_slot', 'wrong_technique_kind', 'technique_unavailable', 'slot_kind_mismatch', 'shot_too_short', 'not_consecutive', 'span_mismatch',
  'invalid_field', 'invalid_request', 'edit_running', 'batch_not_found', 'turn_not_found', 'timing_unusable',
];

const pad2 = (n) => String(n).padStart(2, '0');
const ID_LOOKING = /\b[sc]\d{2,4}\b|[a-z]+_[a-z]+/;

// ---------------------------------------------------------------- time
/** "HH:MM:SS", 24-hour, from the server's local time stamp "2026-11-18T01:00:00" (or any date string). */
export function clockTime(iso) {
  if (!iso) return '';
  const m = /^\d{4}-\d{2}-\d{2}[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?$/.exec(String(iso));
  if (m) return `${m[1]}:${m[2]}:${m[3]}`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}
/** A position in the video: "1:05". */
export function minSec(t) {
  const x = Math.max(0, Math.floor(Number(t) || 0));
  return `${Math.floor(x / 60)}:${pad2(x % 60)}`;
}
/** "2,5 giây" or "1 phút 20 giây". */
export function durationWords(sec) {
  const s = Number(sec);
  if (!(s >= 0.1)) return '';
  if (s < 60) return L.secs(Math.round(s * 10) / 10);
  return L.minSecs(Math.floor(s / 60), Math.round(s % 60));
}

// ---------------------------------------------------------------- shots and chapters
export const shotNumber = (shots, id) => { const i = (shots || []).findIndex((s) => s.id === id); return i < 0 ? null : i + 1; };
export const chapterId = (ch, i) => (ch && ch.id) || `c${pad2((i < 0 ? 0 : i) + 1)}`;
/** "Chương: The Merchant", else "Chương 3" (an id such as c03 is never shown). */
export function chapterLabel(ch, i) {
  const name = ch && typeof ch.name === 'string' ? ch.name.trim() : '';
  return name && !/^c\d+$/i.test(name) ? `Chương: ${name}` : `Chương ${(i < 0 ? 0 : i) + 1}`;
}
/** The chapter at time `t` (`wIdx`: the word at that time, for chapters that carry only word ranges). */
export function chapterAt(chapters, t, wIdx = -1) {
  const list = chapters || [];
  let c = list.find((x) => x.start != null && x.end != null && x.start <= t && t < x.end);
  if (!c && list.length) c = list.find((x) => x.w0 != null && x.w0 <= wIdx && wIdx < x.w1) || list[0];
  return c || null;
}

const numbersText = (nums) => (nums.length > 6 ? `${nums.slice(0, 6).join(', ')} và ${nums.length - 6} cảnh nữa` : nums.join(', '));
/** The scope in words, never a raw id. scope: {kind, shots, chapter}. `current`: "đang chọn" (the box), else the plain form (a turn). */
export function scopeWords(scope, { shots = [], chapters = [], current = false } = {}) {
  const kind = scope?.kind || (scope?.shots ? 'shots' : scope?.chapter ? 'chapter' : 'all');
  if (kind === 'all') return L.scopeAll;
  if (kind === 'chapter') {
    const i = chapters.findIndex((c, k) => chapterId(c, k) === scope.chapter);
    return i >= 0 ? chapterLabel(chapters[i], i) : 'Một chương';
  }
  const ids = scope?.shots || [];
  const nums = ids.map((id) => shotNumber(shots, id)).filter((n) => n != null).sort((a, b) => a - b);
  if (!ids.length) return L.noShotChosen;
  if (ids.length === 1) return nums.length ? `Cảnh ${nums[0]}${current ? ' đang chọn' : ''}` : '1 cảnh';
  return `${ids.length} cảnh${current ? ' đang chọn' : ''}${nums.length ? ` (${numbersText(nums)})` : ''}`;
}

/** What a send would edit. choice: 'auto' | 'shots' | 'chapter' | 'all'.
 * Default (auto): the selected shot(s), else the chapter at the playhead (else the whole video when there are no chapters).
 * -> { kind, payload, words, ok, why } */
export function pickScope({ choice = 'auto', selected = [], shots = [], chapters = [], t = 0, wIdx = -1 } = {}) {
  const valid = new Set(shots.map((s) => s.id));
  const sel = selected.filter((id) => valid.has(id));
  const chap = chapterAt(chapters, t, wIdx);
  const ci = chap ? chapters.indexOf(chap) : -1;
  let kind = choice;
  if (kind === 'auto') kind = sel.length ? 'shots' : (chap ? 'chapter' : 'all');
  if (kind === 'shots') {
    if (!sel.length) return { kind, payload: null, words: L.noShotChosen, ok: false, why: L.noShotChosen };
    return { kind, payload: { shots: sel }, words: scopeWords({ kind, shots: sel }, { shots, current: true }), ok: true, why: '' };
  }
  if (kind === 'chapter') {
    if (!chap) return { kind, payload: null, words: L.chapterHere, ok: false, why: L.chapterHere };
    return { kind, payload: { chapter: chapterId(chap, ci) }, words: chapterLabel(chap, ci), ok: true, why: '' };
  }
  return { kind: 'all', payload: { all: true }, words: L.scopeAll, ok: true, why: '' };
}

/** The scope of an old turn, for "Thử lại": shots that are gone are dropped; null when nothing is left to edit. */
export function retryScope(turn, shots) {
  const s = turn?.scope || {};
  if (s.kind === 'all') return { all: true };
  if (s.kind === 'chapter' && s.chapter) return { chapter: s.chapter };
  const valid = new Set((shots || []).map((x) => x.id));
  const ids = (s.shots || []).filter((id) => valid.has(id));
  return ids.length ? { shots: ids } : null;
}

// ---------------------------------------------------------------- c2box: the same box on the pictures page (step 4): the scope is narration lines
/** The numbers the owner sees for narration lines: their place in the narration, from 1 (the server counts the same way). */
export const beatNumbers = (chapters) => new Map((chapters || []).flatMap((c) => (c.beats || []).map((b) => b.id)).map((id, i) => [id, i + 1]));
const listWords = (nums) => (nums.length > 6 ? `${nums.slice(0, 6).join(', ')} và ${nums.length - 6} dòng nữa` : nums.join(', '));
/** The scope of a send on the pictures page. choice: 'auto' | 'beats' | 'chapter' | 'all'. Default: the selected line(s), else the chapter of the line
 *  being looked at, else the whole video. `chapters`: [{id, title, beats: [{id}]}] as the page has them. -> { kind, payload, words, ok, why } */
export function pickBeatScope({ choice = 'auto', selected = [], chapters = [], beat = null } = {}) {
  const nums = beatNumbers(chapters);
  const sel = selected.filter((id) => nums.has(id));
  const chap = (chapters || []).find((c) => (c.beats || []).some((b) => b.id === beat)) || null;
  let kind = choice;
  if (kind === 'auto') kind = sel.length ? 'beats' : (chap ? 'chapter' : 'all');
  const P = BL.pictures;
  if (!nums.size) return { kind, payload: null, words: P.noNarration, ok: false, why: P.noNarration };
  if (kind === 'beats') {
    if (!sel.length) return { kind, payload: null, words: P.noLineChosen, ok: false, why: P.noLineChosen };
    const list = sel.map((id) => nums.get(id)).sort((a, b) => a - b);
    return { kind, payload: { beats: sel }, words: P.linesWords(sel.length, listWords(list)), ok: true, why: '' };
  }
  if (kind === 'chapter') {
    if (!chap) return { kind, payload: null, words: P.chapterHere, ok: false, why: P.chapterHere };
    const name = typeof chap.title === 'string' && chap.title.trim() && !/^c\d+$/i.test(chap.title.trim()) ? `Chương: ${chap.title.trim()}` : `Chương ${(chapters.indexOf(chap) + 1)}`;
    return { kind, payload: { chapter: chap.id }, words: name, ok: true, why: '' };
  }
  return { kind: 'all', payload: { all: true }, words: P.scopeAll, ok: true, why: '' };
}
/** The scope of an old turn of the pictures box, for "Thử lại": lines that are gone are dropped; null when nothing is left to edit. */
export function retryBeatScope(turn, beatIds) {
  const s = turn?.scope || {};
  if (s.kind === 'all') return { all: true };
  if (s.kind === 'chapter' && s.chapter) return { chapter: s.chapter };
  const valid = new Set(beatIds || []);
  const ids = (s.beats || []).filter((id) => valid.has(id));
  return ids.length ? { beats: ids } : null;
}

// ---------------------------------------------------------------- selecting several shots
/** Clicking shots while "Chọn nhiều cảnh" is on adds them. `playing`: the playhead moves the selection by itself, so nothing is added. */
export function addToSelection(selected, id, { multi, playing = false } = {}) {
  if (!multi || playing || !id || selected.includes(id)) return selected;
  return [...selected, id];
}

// ---------------------------------------------------------------- codes and sentences
/** One Vietnamese sentence for an error code of the edit routes; never the code itself. */
export function codeText(code) {
  if (typeof code !== 'string') return L.failedGeneric;
  return STAGE_CODES.draft?.[code] || STAGE_CODES.ops?.[code] || STAGE_CODES.longjob?.[code] || L.failedGeneric;
}
const vi = (s) => (typeof s === 'string' && s.trim() && isVietnamese(s) && !ID_LOOKING.test(s) ? s.trim() : '');

// ---------------------------------------------------------------- the model's quota is used up
export const QUOTA_CODES = new Set(['rate_limit', 'agy_rate_limit', 'claude_rate_limit']);       // worker claudeprov: Claude Code's usage limit is a quota too
const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
/** A moment from the server: a local time stamp "2026-11-18T14:20:00", an ISO string with a zone, or epoch seconds. null when unreadable. */
export function parseMoment(v) {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return Number.isFinite(v) ? new Date(v < 1e12 ? v * 1000 : v) : null;
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?$/.exec(String(v));
  const d = m ? new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0)) : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}
/** "lúc 14:20" for today, "lúc 14:20 ngày 25/11" for another day (with the year when it is another year). */
export function whenWords(d, now) {
  const hm = `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  if (sameDay(d, now)) return L.quota.at(hm);
  const date = `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}${d.getFullYear() !== now.getFullYear() ? '/' + d.getFullYear() : ''}`;
  return L.quota.atDate(hm, date);
}
const spanWords = (sec) => (sec < 3600 ? L.quota.minutes(Math.max(1, Math.ceil(sec / 60))) : sec < 86400 ? L.quota.hours(Math.round(sec / 3600)) : L.quota.days(Math.round(sec / 86400)));
/** What a failed turn says when the model's quota is used up: { headline, extra } or null when it is not that. `now` is a Date (tests give one). */
export function quotaView(turn, now = new Date()) {
  const hasTime = turn?.retry_at !== undefined && turn?.retry_at !== null && turn?.retry_at !== '';
  const hasAfter = Number.isFinite(Number(turn?.retry_after_seconds)) && turn?.retry_after_seconds !== null && turn?.retry_after_seconds !== '';
  if (!QUOTA_CODES.has(turn?.error) && !hasTime && !hasAfter) return null;
  let d = hasTime ? parseMoment(turn.retry_at) : null;
  if (!d && hasAfter && Number(turn.retry_after_seconds) > 0) d = new Date(now.getTime() + Number(turn.retry_after_seconds) * 1000);
  const open = d ? L.quota.opensAt(whenWords(d, now)) : L.quota.unknown;
  return { headline: L.quota.lead, extra: `${open} ${L.quota.other}` };
}

// ---------------------------------------------------------------- the turn card
export function normStatus(s) {
  if (TURN_STATUS.includes(s)) return s;
  if (s === 'done') return 'old';
  return 'failed';                                  // 'error', 'refused' and anything unknown of an older thread
}
const TONE = { running: 'run', applied: 'ok', no_change: 'muted', needs_choice: 'warn', failed: 'bad', cancelled: 'muted', undone: 'muted', old: 'muted', escalate: 'warn' };

/** The way the edit was made, in words: "sửa nhanh · mất 2,5 giây". */
export function wayLine(turn) {
  const bits = [];
  const path = L.path[turn?.path];
  if (path) bits.push(turn.escalated ? `${path}, ${L.pathEscalated}` : path);
  const d = durationWords(turn?.seconds);
  if (d) bits.push(L.took(d));
  return bits.join(' · ');
}

/** All a card shows, for one turn. env: { shots, chapters }. */
export function turnView(turn, env = {}) {
  const status = normStatus(turn?.status);
  const shots = env.shots || [], chapters = env.chapters || [];
  const detail = [];
  const summaryVi = vi(turn?.summary);
  if (turn?.summary && !summaryVi) detail.push(String(turn.summary));
  if (turn?.notes && turn.notes !== turn.summary) detail.push(String(turn.notes));

  const changes = (Array.isArray(turn?.changes) ? turn.changes : []).map((c) => {
    const what = vi(c.what);
    if (c.what && !what) detail.push(String(c.what));
    const num = c.number ?? shotNumber(shots, c.shot_id);
    const lines = (Array.isArray(c.facts) ? c.facts : []).filter((x) => vi(x));      // c2box: the sentences of the batch about this shot (server-written)
    return {
      shotId: c.shot_id || '', number: num, op: c.op || 'changed', opText: L.change[c.op] || L.change.changed,
      title: num != null ? L.shotAt(num, minSec(c.start)) : minSec(c.start), what, lines: c.what_source === 'batch' && lines.length ? lines : (what ? [what] : []),
      hasBefore: c.op !== 'added', hasAfter: c.op !== 'removed',
    };
  });

  let headline = '';
  let extra = '';
  let quota = false;
  if (status === 'applied') headline = summaryVi || (turn?.doc === 'picks' ? BL.pictures.applied : L.applied);
  else if (status === 'no_change') { headline = summaryVi || L.noChange; extra = L.noChangeHelp; }
  else if (status === 'cancelled') headline = L.cancelled;
  else if (status === 'undone') headline = L.undone;
  else if (status === 'old') headline = summaryVi || L.old;
  else if (status === 'failed') {
    const q = quotaView(turn, env.now || new Date());
    if (q) { headline = q.headline; extra = q.extra; quota = true; }
    else {
      headline = codeText(turn?.error);
      if (summaryVi && summaryVi !== headline) extra = summaryVi;
    }
    if (turn?.error) detail.push(`mã: ${turn.error}`);
  } else if (status === 'escalate') {
    headline = vi(turn?.reason) || summaryVi || BL.escalate;
    extra = turn?.doc === 'picks' ? BL.pictures.escalate : BL.slow.hint;
  } else if (status === 'needs_choice') {
    const given = Array.isArray(turn?.conflicts) ? turn.conflicts : [];
    const listChanged = given.some((c) => c && typeof c === 'object' && c.kind === 'list');
    const givenIds = given.map((c) => (typeof c === 'string' ? c : (c && c.kind === 'shot' ? c.id : null))).filter(Boolean);   // the server sends {kind: 'shot', id} or {kind: 'list'}
    const touched = (Array.isArray(turn?.changes) ? turn.changes : []).map((c) => c.shot_id).filter(Boolean);
    const conflicts = givenIds.length || listChanged ? givenIds : (touched.length ? touched : (Array.isArray(turn?.scope?.shots) ? turn.scope.shots : []));   // not listed: the shots the turn touched, else the shots of its scope
    const nums = conflicts.map((id) => shotNumber(shots, id)).filter((n) => n != null).sort((a, b) => a - b);
    headline = summaryVi || '';
    extra = nums.length ? L.choiceLead(`cảnh ${numbersText(nums)}`) : (listChanged ? L.choiceLeadList : L.choiceLeadAny);
  }

  const canPreview = status === 'applied' && changes.some((c) => c.hasAfter) && turn?.doc !== 'picks';
  // c2box: a turn of the typed operations also carries the batch's own sentences (what the card shows for the pictures, which have no shot)
  const sentences = (Array.isArray(turn?.batch_changes) ? turn.batch_changes : []).map((b) => ({ text: String(b?.what || ''), time: b?.time || null })).filter((b) => b.text);
  const slowLimits = status === 'running' && turn?.path === 'deep' && turn?.limits && Number.isFinite(Number(turn.limits.minutes))
    ? BL.slow.limits(Number(turn.limits.minutes), Number(turn.limits.repairs ?? 0)) : '';
  return {
    id: turn?.id || '', status, tone: TONE[status], badge: BL.status[status] || L.status[status], doc: turn?.doc === 'picks' ? 'picks' : 'storyboard', sentences, limits: slowLimits,
    time: clockTime(turn?.at), scope: scopeWords(turn?.scope, { shots, chapters }), instruction: String(turn?.instruction || ''),
    way: status === 'running' ? '' : wayLine(turn), headline, extra, changes, detail: detail.join('\n'),
    showChanges: status === 'applied' && changes.length > 0, showSentences: status === 'applied' && changes.length === 0 && sentences.length > 0,
    noChanges: status === 'applied' && changes.length === 0 && sentences.length === 0,
    actions: {
      cancel: status === 'running',
      preview: canPreview,
      undo: status === 'applied' ? (turn?.has_undo === false ? 'gone' : 'yes') : '',
      choices: status === 'needs_choice',
      retry: status === 'failed' && !!turn?.instruction,
      settings: quota,                                 // "Chọn mô hình khác": opens the settings dialog
      escalate: status === 'escalate' ? (turn?.doc === 'picks' ? 'manual' : 'slow') : '',          // c2box: "Làm kỹ hơn" (step 5) or "Tìm hình bằng tay" (step 4)
    },
  };
}

// ---------------------------------------------------------------- running job
/** The progress line from the long job of the edit ({progress, parts: [{key, state, note}]}): words from labels, never the model's raw text. */
export function progressView(job) {
  const P = L.progress;
  const parts = Array.isArray(job?.parts) ? job.parts : [];
  const part = parts.find((p) => p.state === 'running') || parts.find((p) => p.state === 'waiting' || p.state === 'queued');
  let line = P.queued;
  if (part) {
    const note = String(part.note || '');
    let m;
    if (/^Đang nghĩ/.test(note)) line = P.think;
    else if (/^Đang kiểm tra|^Đang ghép/.test(note)) line = P.check;
    else if (/^Chuyển sang/.test(note)) line = P.deep;
    else if ((m = /^Bước (\d+)/.exec(note))) line = P.agentStep(Number(m[1]));
    else if (/^Đang áp dụng/.test(note)) line = P.write;
    else if (part.key === 'prepare') line = P.prepare;
    else if (part.key === 'edit' || part.key === 'agent') line = P.agent;
    else if (part.key === 'apply') line = P.write;
    else if (part.key === 'compile') line = P.check;
    else line = P.agent;
  } else if (parts.length && parts.every((p) => p.state === 'done')) line = P.write;
  const f = Number(job?.progress);
  return { line, fraction: Number.isFinite(f) ? Math.min(1, Math.max(0, f)) : 0 };
}

// ---------------------------------------------------------------- after a turn
/** The changed range to preview: from the first changed shot to the end of the last one in the current storyboard, at most `max` seconds. */
export function previewRange(turn, shots, { max = 10, fallback = 4 } = {}) {
  const ch = (turn?.changes || []).filter((c) => c.op !== 'removed');
  if (!ch.length) return null;
  const starts = [], ends = [];
  for (const c of ch) {
    const s = (shots || []).find((x) => x.id === c.shot_id);
    const a = s && s._t0 != null ? s._t0 : Number(c.start) || 0;
    starts.push(a);
    ends.push(s && s._t1 != null ? s._t1 : a + fallback);
  }
  const t0 = Math.min(...starts);
  const t1 = Math.min(Math.max(...ends), t0 + max);
  return t1 > t0 ? { t0, t1 } : null;
}

/** What the editor does when a turn changed the saved storyboard. */
export const takeInPlan = (dirty) => (dirty ? 'merge' : 'reload');

/** A state of a turn that changed the saved storyboard (applied by a job, resolved to applied, undone). */
export const changedStoryboard = (turn) => ['applied', 'undone'].includes(turn?.status);
/** The turns whose state is new since the last look and changed the storyboard. `seen`: Map id -> status. Updates `seen`. First look: only remembers. */
export function newlyChanged(turns, seen, first) {
  const out = [];
  for (const t of turns || []) {
    const was = seen.get(t.id);
    seen.set(t.id, t.status);
    if (!first && was !== t.status && changedStoryboard(t)) out.push(t);
  }
  return out;
}

// ---------------------------------------------------------------- the model settings (settings.js draws; this decides)
const isAgy = (id) => typeof id === 'string' && id.startsWith('agy:');
/** A model the owner can pick: the server says it is enabled, and an `agy` entry that could not list its models (`agy.ok === false`) is not a model. */
const usable = (m) => m && m.id && m.enabled !== false && !(m.agy && m.agy.ok === false);
/** The display name of a model id from the list (`label`, else `name`), else the id without its `agy:` prefix. */
export function modelName(models, id) {
  const m = (models || []).find((x) => x.id === id);
  return (m && (m.label || m.name)) || String(id ?? '').replace(/^agy:/, '');
}
/** The text of an option: the display name, then the id as secondary text (nothing twice). */
export function modelOptionText(models, id) {
  const name = modelName(models, id);
  return name === id || name === String(id).replace(/^agy:/, '') ? String(id) : `${name} (${id})`;
}
/** 'ok' | 'down': the list the server gave has no model of agy in it (agy could not answer, or nothing at all). One line for the dialog, not a note on every row. */
export function modelListState(resp) {
  const models = Array.isArray(resp?.models) ? resp.models : [];
  return models.some((m) => usable(m) && isAgy(m.id)) ? 'ok' : 'down';
}
/** The rows of the dialog from GET /api/settings/models: one per role, with the models it may use. */
export function modelRows(resp) {
  const models = (Array.isArray(resp?.models) ? resp.models : []).filter(usable);
  return (Array.isArray(resp?.roles) ? resp.roles : []).map((r) => ({
    role: r.role, serverLabel: r.label || r.role, value: r.value || r.model || '', agentic: !!r.agentic, fromSetting: r.source === 'setting',
    options: models.filter((m) => !r.agentic || isAgy(m.id)).map((m) => m.id),
  }));
}
/** What to PUT: only the roles whose dropdown shows another model than the server holds. */
export function modelChanges(rows, values) {
  const out = {};
  for (const r of rows) { const v = values[r.role]; if (v && v !== r.value) out[r.role] = v; }
  return out;
}
/** "Dùng một mô hình cho tất cả": every role that may use `id` takes it; the others keep their value. */
export function applyAllModels(rows, values, id) {
  const next = { ...values };
  for (const r of rows) if (r.options.includes(id)) next[r.role] = id;
  return next;
}
