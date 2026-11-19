// "Kịch bản" step: sources | outline | narration. Mounted by the shell at #/project/<id>/script.
//
// Rules of this view (see docs/design/2026-11-16-script-voice-picks-design.md section 2 and docs/qa/FIXES_ui_shell_library_script.md):
//  - A server answer never overwrites something the owner typed. Every answer goes through reconcile(): a three-way merge of
//    (B) the last version of the server the page knew, (D) the draft on screen, and (the answer). Both changed the same unit
//    -> the owner decides.
//  - Every request that changes a draft goes through ONE queue (Q), so a request is never sent before the previous answer
//    has updated the revision it depends on. Actions are queued as intents and worked out when their turn comes.
//  - While a model job writes a document, saving that document is held (the job writes it too); the draft stays on the page
//    and is merged with the job's result when the job ends.
import { api } from '../api.js';
import { chapterDiffItems, headerRole } from '../chapdiff.js';
import { h, kids, toast, errorToast, errorInto, detailFold, fillSelect, modal as uiModal, confirmDialog, modalOpen, setStatus } from '../util.js';
import { LEVEL } from '../labels.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';
import { wordCount, tokenCount, findFolded, fold } from '../text.js';
import { createQueue } from '../queue.js';
import { mergeDoc, deepEqual } from '../merge.js';
import { issueText, jobErrorText, parseFailText } from '../errmsg.js';
import { mountAgentPick, quotaNode } from '../agentpick.js';
import { sourceWords, usedAgent, isQuota, STEP_SCRIPT } from '../agentlogic.js';
import { AGENT_LABELS as AL } from '../labels.js';

let root = null, scope = null, shell = null;     // the view root, its lifecycle scope and the shell (set by mount)
const $ = (s) => root?.querySelector(s);
const modal = (o) => uiModal({ ...o, cls: (o.cls || '') + ' v-scr' });   // dialogs opened here carry the scope class of this view
const S = { pid: null, brief: null, pick: null, tab: null, search: '', hl: [], focus: 'narr' };      // `pick`: the agent select of the toolbar (agentpick.js)
const D = { outline: null, narr: null };                       // drafts (what is on screen)
const R = { outline: null, narr: null };                       // revisions of the saved files
const B = { outline: null, narr: null };                       // the last saved documents the page knew (base of the merges)
const ST = { outline: {}, narr: {} };                          // approved, stale, issues, last_paste
const dirty = { outline: false, narr: false };
const hist = { outline: { past: [], future: [], key: '', at: 0 }, narr: { past: [], future: [], key: '', at: 0 } };
const PASTE = { outline: '', narration: '' };                  // text typed in the paste dialog survives closing the dialog
let jobPoll = null, currentJob = null, lastRun = null, Q = createQueue();
function resetState() {
  Object.assign(S, { pid: null, brief: null, pick: null, tab: null, search: '', hl: [], focus: 'narr' });
  D.outline = D.narr = null; R.outline = R.narr = null; B.outline = B.narr = null; ST.outline = {}; ST.narr = {};
  dirty.outline = dirty.narr = false;
  for (const k of ['outline', 'narr']) hist[k] = { past: [], future: [], key: '', at: 0 };
  PASTE.outline = PASTE.narration = '';
  jobPoll = null; currentJob = null; lastRun = null;
  Q = createQueue({ onBusy: (b) => setStatus(b ? 'đang xử lý...' : '') });
}

const J = (url) => api.get(url);
const send = (method, url, body) => api.send(method, url, body);
const pipeChanged = () => shell?.refreshPipeline();       // saving, approving or pasting can move the stage of the project
const P = () => `/api/projects/${S.pid}`;
const ids = (s) => String(s).split(/[,;，；、\s]+/).map((x) => x.trim()).filter(Boolean);
const clone = (o) => JSON.parse(JSON.stringify(o));
// Text areas grow with their text. Browsers with CSS `field-sizing` do it themselves (script.css); for the others the heights
// are set in ONE pass (all reset, all read, all written), because fitting them one by one forces a layout each time, which
// took half a minute for the 800 lines of a 500 KB paste.
const NATIVE_FIT = typeof CSS !== 'undefined' && CSS.supports?.('field-sizing', 'content');
const fitMany = (list) => {
  if (NATIVE_FIT || !list.length) return;
  for (const t of list) t.style.height = 'auto';
  const hs = list.map((t) => Math.min(t.scrollHeight + 2, 520));
  list.forEach((t, i) => { t.style.height = hs[i] + 'px'; });
};
const fit = (ta) => fitMany([ta]);
const fitAll = (el) => scope?.raf(() => fitMany([...el.querySelectorAll('textarea:not(.big)')]));
const words = wordCount;
const KIND = {
  outline: { key: 'outline', url: 'outline', field: 'outline', label: 'dàn ý', collections: ['chapters', 'facts', 'hook_options'] },
  narr: { key: 'narr', url: 'narration', field: 'narration', label: 'lời dẫn', collections: ['chapters'] },
};

// ------------------------------------------------------------------ history
function mutate(kind, fn, key = '') {
  const hs = hist[kind], now = Date.now();
  if (!(key && hs.key === key && now - hs.at < 1500)) { hs.past.push(JSON.stringify(D[kind])); if (hs.past.length > 200) hs.past.shift(); hs.future = []; }
  hs.key = key; hs.at = now; S.focus = kind;
  fn();
  setDirty(kind, true);
}
function undoRedo(dir) {
  const kind = S.focus, hs = hist[kind];
  const from = dir < 0 ? hs.past : hs.future, to = dir < 0 ? hs.future : hs.past;
  if (!from.length || !D[kind]) return toast('Không còn gì để ' + (dir < 0 ? 'hoàn tác' : 'làm lại'));
  to.push(JSON.stringify(D[kind]));
  D[kind] = JSON.parse(from.pop()); hs.key = '';
  setDirty(kind, !deepEqual(D[kind], B[kind])); renderAll();
}
function setDirty(kind, v) { dirty[kind] = v; refreshChrome(); }

// ------------------------------------------------------------------ keeping the focus when a column is drawn again
const fieldsOf = (col) => [...col.querySelectorAll('textarea,input,select')];
function snapFocus() {
  const a = document.activeElement, col = a?.closest?.('.col-b');
  if (!col || !root?.contains(col)) return null;
  return { col: col.id, i: fieldsOf(col).indexOf(a), s: a.selectionStart, e: a.selectionEnd, top: col.scrollTop };
}
function restoreFocus(f) {
  if (!f || f.i < 0 || !root) return;
  const col = $('#' + f.col), el = col && fieldsOf(col)[f.i];
  if (!el) return;
  el.focus({ preventScroll: true });
  try { if (f.s !== null && f.s !== undefined) el.setSelectionRange(f.s, f.e); } catch { /* not a text field */ }
  col.scrollTop = f.top;
}

// ------------------------------------------------------------------ the server's answer and the draft: reconcile
const keyOf = (c) => (c.id !== undefined ? `${c.key}:${c.id}` : c.key);
const NAMES = { thesis: 'Câu hỏi chính', hook_choice: 'Câu mở được chọn', target_words: 'Mục tiêu số từ', title: 'Tên', hook_options: 'Các câu mở' };
function conflictLabel(c) {
  const el = c.mine || c.theirs;
  if (c.key === 'chapters') return `Chương ${c.id}${el?.title ? ' ' + el.title : ''}`;
  if (c.key === 'facts') return `Dữ kiện ${c.id}`;
  if (c.key === 'hook_options') return `Câu mở ${c.id}`;
  return NAMES[c.key] || c.key;
}
function previewOf(el) {
  if (el === undefined || el === null) return '(không có / đã bị xóa)';
  const cut = (t) => { t = String(t).replace(/\s+/g, ' ').trim(); return t.length > 220 ? t.slice(0, 220) + '...' : t; };
  if (typeof el !== 'object') return cut(el);
  if (Array.isArray(el.beats)) return `${el.beats.length} dòng: ` + cut(el.beats.map((b) => b.text).join(' '));
  if (el.claim !== undefined) return cut(el.claim);
  if (el.purpose !== undefined || el.word_budget !== undefined) return cut(`${el.title || ''}, ${el.word_budget} từ. ${el.purpose || ''}`);
  if (el.text !== undefined) return cut(el.text);
  return cut(JSON.stringify(el));
}
/** Both the owner and the server changed the same units. Resolves { "key[:id]": 'mine' | 'theirs' }; closing = keep mine. */
function askConflicts(kind, conflicts, why) {
  return new Promise((resolve) => {
    const choice = {};
    for (const c of conflicts) choice[keyOf(c)] = 'mine';
    let done = false;
    const fin = (v) => { if (!done) { done = true; resolve(v); } };
    const rows = conflicts.map((c, n) => h('div', { class: 'cf-row' }, h('div', { class: 'cf-name', text: conflictLabel(c) }),
      ['mine', 'theirs'].map((who) => h('label', { class: 'cf-opt' },
        h('input', { type: 'radio', name: 'cf' + n, checked: who === 'mine', onchange: () => { choice[keyOf(c)] = who; } }),
        h('span', null, h('b', { text: who === 'mine' ? 'Giữ bản của tôi: ' : 'Lấy bản mới: ' }), h('span', { class: 'muted', text: previewOf(who === 'mine' ? c.mine : c.theirs) }))))));
    const m = modal({ title: `Hai bản sửa khác nhau (${KIND[kind].label})`, cls: 'wide', backdrop: false, onClose: () => fin(choice),
      body: h('div', { class: 'body' }, h('p', { text: why + ' Với mỗi chỗ dưới đây, chọn bản nào giữ lại. Chỗ nào không trùng nhau thì đã được ghép tự động.' }), ...rows),
      footer: h('footer', null, h('button', { text: 'Giữ hết bản của tôi', onclick: () => { for (const k of Object.keys(choice)) choice[k] = 'mine'; fin(choice); m.close(); } }),
        h('button', { class: 'primary', text: 'Áp dụng lựa chọn', onclick: () => { fin(choice); m.close(); } })) });
  });
}
/**
 * The ONE place where a server answer `r` ({ outline|narration, rev, ...}) meets the draft. Returns true when the draft changed.
 * `base` = the version the answer is derived from (default: the last version the page knew).
 */
async function reconcile(kind, r, base = B[kind], why = 'Bản trên máy chủ đã đổi trong lúc bạn đang sửa.') {
  const K = KIND[kind], server = r[K.field], mine = D[kind];
  ST[kind] = r; R[kind] = r.rev;
  let next = server;
  const edited = !!mine && !!server && !deepEqual(mine, base);
  if (edited) {                                                 // the owner has edits: never overwrite them
    const opts = { collections: K.collections };
    let res = mergeDoc(base, mine, server, opts);
    if (res.conflicts.length) res = mergeDoc(base, mine, server, opts, await askConflicts(kind, res.conflicts, why));
    next = res.value;
  } else if (mine && !server) next = mine;
  const changed = !deepEqual(next, mine);
  if (changed && edited) { hist[kind].past.push(JSON.stringify(mine)); hist[kind].future = []; hist[kind].key = ''; }   // Hoàn tác brings the old draft back
  // When nothing changed keep the very object the fields on screen are bound to (their handlers edit it); a changed one is redrawn by the caller
  D[kind] = changed ? next : mine; B[kind] = server ? clone(server) : null;
  dirty[kind] = !!next && !deepEqual(next, server);
  return changed;
}
const redraw = (changed) => { if (!root) return; if (changed) { const f = snapFocus(); renderAll(); restoreFocus(f); } else refreshChrome(); };

// ------------------------------------------------------------------ loading
async function loadAll() {
  S.brief = await J(`${P()}/brief`);
  const [o, n] = [await J(`${P()}/outline`), await J(`${P()}/narration`)];
  await reconcile('outline', o); await reconcile('narr', n);
  if (!S.tab || !S.brief.sources.some((s) => s.code === S.tab)) S.tab = S.brief.sources[0]?.code || null;
  renderAll();
}
/** True while a model job is writing this document. */
// Since the server writes a narration job's chapters under the same lock as saves and keeps what was saved meanwhile, only an OUTLINE
// job still holds the outline's save: a save during it would make the job end in a conflict and throw the model's outline into the paste box.
const jobBlocks = (kind) => !!currentJob && ['queued', 'running'].includes(currentJob.state) && currentJob.kind === 'outline' && kind === 'outline';
const HELD = 'Đang có tác vụ mô hình lập dàn ý. Chữ bạn sửa được giữ trên trang và sẽ được ghép với kết quả khi tác vụ xong; sau đó bấm Lưu.';

/** Save one draft (inside the queue). true = saved or nothing to save; false = not saved (the owner has been told why). */
async function saveNow(kind, tries = 0) {
  const K = KIND[kind];
  if (!D[kind] || !dirty[kind]) return true;
  if (jobBlocks(kind)) { toast(HELD, 'warn', 9000); return false; }
  const sent = clone(D[kind]);
  try {
    const r = await send('PUT', `${P()}/${K.url}`, { [K.field]: sent, base_rev: R[kind] });
    redraw(await reconcile(kind, r, sent));
    if (kind === 'outline') { await refreshNarrStatus(); redraw(false); }
    pipeChanged();
    return true;
  } catch (e) {
    if (e.status === 409 && tries === 0) return recoverStale(kind, true);
    errorToast(e); return false;
  }
}
/** The approval of the narration depends on the outline's: after the outline is saved, approved or replaced, read the
 *  narration's status again (not its text: the draft stays as it is). */
async function refreshNarrStatus() {
  try { const r = await J(`${P()}/narration`); if (r.rev === R.narr) { const keep = ST.narr.last_paste; ST.narr = { ...r, last_paste: r.last_paste ?? keep }; } } catch { /* the next save tells */ }
}
/** The file changed under us (another tab, or a job): fetch it, merge it into the draft, and (when asked) save once more. */
async function recoverStale(kind, retry) {
  try {
    const r = await J(`${P()}/${KIND[kind].url}`);
    redraw(await reconcile(kind, r, B[kind], `Bản ${KIND[kind].label} đã đổi ở nơi khác (tab khác hoặc tác vụ nền).`));
    if (retry && dirty[kind]) {
      toast(`Bản ${KIND[kind].label} đã đổi ở nơi khác. Phần bạn sửa được ghép vào bản mới và lưu lại.`, 'warn', 7000);
      return saveNow(kind, 1);
    }
    toast(`Bản ${KIND[kind].label} đã đổi ở nơi khác. Đã tải bản mới và giữ phần bạn sửa; hãy xem lại rồi bấm lại.`, 'warn', 8000);
    return false;
  } catch (e) { errorToast(e, 'Không tải lại được: '); return false; }
}
const saveAllNow = async () => { const a = await saveNow('outline'); const b = await saveNow('narr'); return a && b; };
/** The Lưu button and Ctrl+S. */
const saveAll = ({ quiet = false } = {}) => Q.run(async () => {
  if (!dirty.outline && !dirty.narr) { if (!quiet) toast('Không có gì cần lưu', '', 1500); return true; }
  const ok = await saveAllNow();
  if (ok && !quiet) toast('Đã lưu', 'ok', 1500);
  return ok;
});

// ------------------------------------------------------------------ top bar
const approvedFlag = (k) => !!ST[k].approved && !dirty[k];
/** Why a recorded approval of the narration no longer stands (`approval_reason` of the server), in words. */
const WHY = {
  outline_changed: { badge: 'dàn ý đã đổi, cần duyệt lại', text: 'Lời dẫn này đã được duyệt cho một bản dàn ý cũ. Dàn ý đã đổi sau đó nên phải duyệt lại lời dẫn. Thường chỉ cần kiểm tra lại các chương rồi bấm Duyệt, không phải viết lại.' },
  narration_edited: { badge: 'đã sửa sau khi duyệt', text: 'Lời dẫn đã được sửa sau lần duyệt trước. Đọc lại rồi bấm Duyệt lời dẫn để chốt.' },
  outline_not_approved: { badge: 'chờ duyệt dàn ý', text: 'Dàn ý chưa được duyệt (hoặc đã sửa sau khi duyệt), nên lời dẫn chưa duyệt được. Hãy duyệt dàn ý trước.' },
};
const approvalWhy = (st) => (!st.approved && st.approval_reason ? WHY[st.approval_reason] || null : null);
/** One difference with its own action buttons. `after` runs when a button was used (the refusal dialog closes itself). */
function diffRow(it, after = () => {}) {
  const run = {
    drop: () => dropChapter(it.chapter),
    write: () => runDialog('narration', [it.chapter]),
    add_empty: () => doOp({ op: 'add_chapter', chapter: it.chapter }),
    add_beat: () => doOp({ op: 'insert', chapter: it.chapter, after: D.narr?.chapters.find((c) => c.id === it.chapter)?.beats.at(-1)?.id || null }),
    order: () => doOp({ op: 'order_like_outline' }),
  };
  return h('div', { class: 'diff-row', 'data-diff': it.kind, 'data-chapter': it.chapter || '', style: { display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' } },
    h('span', { text: it.text }),
    ...it.actions.map((a) => h('button', { class: 'small' + (a.id === 'drop' ? ' danger' : ''), 'data-act': a.id, text: a.label, onclick: () => { after(); run[a.id](); } })));
}
const diffItems = (d) => chapterDiffItems(d, D.outline, D.narr);
/** Remove a chapter that the outline does not have from the narration. Asks once; Hoàn tác brings it back. */
async function dropChapter(id) {
  const ch = D.narr?.chapters.find((c) => c.id === id);
  const n = ch ? ch.beats.length : 0;
  if (!(await confirmDialog(`Xóa chương ${id}${n ? ` và ${n} dòng của nó` : ''} khỏi lời dẫn? Bạn có thể bấm Hoàn tác để lấy lại.`, { title: 'Xóa chương khỏi lời dẫn', ok: 'Xóa', danger: true }))) return;
  return doOp({ op: 'drop_chapter', chapter: id });
}
/** The note above the narration: why it is not approved (when it was before), what changed in the outline, which chapters differ. */
function approvalNote() {
  const st = ST.narr, w = approvalWhy(st), diff = diffItems(st.chapter_diff);
  const lines = [];
  if (w) lines.push(h('div', { text: w.text }));
  if (st.stale && !w && !st.approved) lines.push(h('div', { class: 'hint', text: 'Dàn ý đã đổi kể từ lúc lời dẫn này được viết. Chỉ để bạn biết, vẫn lưu và duyệt được.' }));
  for (const it of diff) lines.push(diffRow(it));
  return lines.length ? h('div', { class: 'banner warn approval-note', style: { flexDirection: 'column', alignItems: 'flex-start' } }, ...lines) : null;
}

function refreshChrome() {
  if (!root) return;
  $('#dirty-dot').hidden = !(dirty.outline || dirty.narr);
  const iss = [...(ST.outline.issues || []), ...(ST.narr.issues || [])].filter((i) => i.level !== 'info');
  const c = $('#issue-count'); c.textContent = iss.length; c.className = 'count' + (iss.some((i) => i.level === 'error') ? ' err' : iss.length ? ' warnc' : '');
  const badge = (el, k) => {
    const st = ST[k];
    if (!D[k]) { el.textContent = 'chưa có'; el.className = 'badge none'; return; }
    if (dirty[k]) { el.textContent = jobBlocks(k) ? 'đang sửa, chưa lưu (đang chờ tác vụ)' : 'đang sửa, chưa lưu'; el.className = 'badge warn'; }
    else if (st.approved) { el.textContent = 'đã duyệt'; el.className = 'badge ok'; }
    else if (k === 'narr' && approvalWhy(st)) { const w = approvalWhy(st); el.textContent = w.badge; el.title = w.text; el.className = 'badge warn'; }
    else if (st.stale && k !== 'narr') { el.textContent = 'duyệt đã cũ'; el.className = 'badge warn'; }
    else { el.textContent = 'chưa duyệt'; el.className = 'badge'; }
  };
  badge($('#out-badge'), 'outline'); badge($('#nar-badge'), 'narr');
  const next = !approvedFlag('outline') ? 'outline' : 'narr';
  const b = $('#btn-approve'); b.textContent = next === 'outline' ? 'Duyệt dàn ý' : 'Duyệt lời dẫn';
  b.disabled = !D[next] || !!currentJob; b.dataset.kind = next;
  $('#approve-state').textContent = approvedFlag('narr') ? 'Lời dẫn đã duyệt' : approvedFlag('outline') ? 'Dàn ý đã duyệt' : 'Chưa duyệt gì';
  $('#approve-state').className = 'badge' + (approvedFlag('narr') ? ' ok' : '');
  $('#btn-write').disabled = !!currentJob; $('#btn-outline').disabled = !!currentJob;
  renderStatus();
  const nx = shell?.pipeline && nextOpenable(shell.pipeline.steps, 'script'), bn = $('#btn-next');
  bn.hidden = !(approvedFlag('narr') && nx);
  if (nx) { bn.textContent = `Tiếp tục: ${nx.label}`; bn.title = nx.state === 'not_built' ? 'Bước kế tiếp chưa được xây dựng' : ''; bn.onclick = () => shell.go(projectHash(S.pid, nx.id)); }
}

// ------------------------------------------------------------------ number fields: whole numbers in a sensible range, or the old value comes back
function intField({ value, min, max, label, onValid, id, style, step = 1, integer = true }) {
  const inp = h('input', { type: 'number', id, min, max, step, value, style, 'aria-label': label });
  inp.dataset.good = String(value);
  inp.addEventListener('change', () => {
    const raw = inp.value.trim(), v = Number(raw);
    if (raw === '' || !Number.isFinite(v) || (integer && !Number.isInteger(v)) || v < min || v > max) {
      toast(`${label}: nhập ${integer ? 'số nguyên' : 'một số'} từ ${min} đến ${max}. Giữ giá trị cũ ${inp.dataset.good}.`, 'warn', 6000);
      inp.value = inp.dataset.good; return;
    }
    inp.dataset.good = String(v); onValid(v);
  });
  return inp;
}

// ------------------------------------------------------------------ sources column
function srcBody() {
  const b = S.brief, body = $('#src-body'), src = b.sources.find((s) => s.code === S.tab);
  $('#src-note').textContent = `${b.totals.paragraphs} đoạn, ${b.totals.words} từ`;
  const kids = [];
  const p = b.painting;
  if (b.totals.included === 0) kids.push(h('div', { class: 'conf', role: 'alert', text: 'Chưa có nguồn nào được dùng. Dự án này chỉ có bản dịch máy: tick "Dùng sách này làm nguồn" ở sách bên dưới (nếu chấp nhận rủi ro) rồi mới lập dàn ý.' }));
  kids.push(h('h3', { class: 'sh', text: 'Tác phẩm' }), h('div', null, h('b', { text: p.title }), h('div', { class: 'muted', text: [p.artist, p.year].filter(Boolean).join(', ') })));
  kids.push(h('div', { class: 'fieldrow', style: { marginTop: '8px' } },
    h('label', { text: 'Mục tiêu (từ)' }), intField({ value: b.options.target_words, min: 300, max: 20000, step: 50, label: 'Mục tiêu số từ', onValid: (v) => setOption({ target_words: v }) }),
    h('label', { text: 'Từ/giây' }), intField({ value: b.options.wps, min: 0.5, max: 6, step: 0.01, label: 'Số từ mỗi giây', integer: false, onValid: (v) => setOption({ wps: v }) })));
  if (b.conflicts.length) {
    kids.push(h('h3', { class: 'sh', text: 'Các nguồn không thống nhất' }));
    for (const c of b.conflicts) kids.push(h('div', { class: 'conf', text: `${c.field}: ` + c.values.map((v) => `${v.src || v.work_id} ghi "${v.value}"`).join(' / ') }));
  }
  kids.push(h('h3', { class: 'sh', text: 'Chi tiết có tên' }),
    h('div', null, b.details.length ? b.details.map((d) => h('span', { class: 'det', title: d.where.map((w) => `${w.src}: ${w.paras.join(', ')}`).join('; '), onclick: () => focusParas(d.where.flatMap((w) => w.paras)) }, h('b', { text: d.id }), d.name)) : h('span', { class: 'muted', text: 'Không có' })));
  kids.push(h('h3', { class: 'sh', text: 'Sách' }),
    h('div', { class: 'tabs' }, b.sources.map((s) => h('button', { class: (s.code === S.tab ? 'active ' : '') + (s.low_trust ? 'low' : ''), onclick: () => { S.tab = s.code; renderSources(); }, text: `${s.code} ${s.book_id.split('_')[0]}` }))));
  if (src) {
    const chkLabel = src.low_trust
      ? 'Dùng sách này làm nguồn (đã đọc và chấp nhận rủi ro)'
      : 'Dùng sách này làm nguồn';
    kids.push(h('div', { class: 'src-head' }, h('b', { text: src.book_title }), h('span', { class: 'muted', text: `${src.paragraphs.length} đoạn, ${src.words} từ` }),
      src.low_trust ? h('span', { class: 'tag lowtrust', title: src.trust_note, text: 'bản dịch máy, không dùng làm nguồn sự kiện' }) : null),
      h('label', { class: 'chk', style: { display: 'flex', gap: '6px', marginBottom: '6px' } }, h('input', { type: 'checkbox', checked: src.included, 'data-src': src.book_id, onchange: (e) => toggleSource(src, e.target) }), chkLabel),
      h('input', { type: 'search', placeholder: 'Tìm trong sách này (không cần gõ dấu)', value: S.search, style: { width: '100%', marginBottom: '8px' }, oninput: (e) => { S.search = e.target.value; renderParas(); } }),
      h('div', { id: 'paras' }));
  }
  body.replaceChildren(...kids.filter(Boolean));
  renderParas();
}
function renderParas() {
  const box = $('#paras'); if (!box) return;
  const src = S.brief.sources.find((s) => s.code === S.tab), q = S.search.trim(), fq = fold(q);
  const out = []; let cur = null;
  for (const p of src.paragraphs) {
    const hit = q ? findFolded(p.text, q) : null;
    if (q && !hit && !fold(p.id).includes(fq)) continue;
    if (p.section !== cur) { cur = p.section; if (cur) out.push(h('div', { class: 'para-sec', text: cur })); }
    const tx = h('span', { class: 'tx' });
    if (hit) tx.append(p.text.slice(0, hit[0]), h('mark', { text: p.text.slice(hit[0], hit[1]) }), p.text.slice(hit[1])); else tx.textContent = p.text;
    out.push(h('div', { class: 'para' + (p.kind === 'quote' ? ' quote' : '') + (S.hl.includes(p.id) ? ' hl' : ''), id: 'para-' + p.id }, h('span', { class: 'pid mono', text: p.id, title: 'Bấm để chép mã vào bộ nhớ tạm', onclick: () => navigator.clipboard?.writeText(p.id).catch(() => {}) }), tx));
  }
  box.replaceChildren(...(out.length ? out : [h('div', { class: 'muted', text: 'Không có đoạn nào khớp.' })]));
}
const renderSources = srcBody;
function focusParas(list) {
  S.hl = list.filter(Boolean);
  if (!S.hl.length) return;
  const code = S.hl[0].split('-')[0];
  if (S.brief.sources.some((s) => s.code === code) && S.tab !== code) { S.tab = code; S.search = ''; }
  srcBody();
  const el = document.getElementById('para-' + S.hl[0]);
  if (el) el.scrollIntoView({ block: 'center', behavior: 'smooth' });
  else toast(`Không thấy đoạn ${S.hl[0]} trong nguồn`, 'warn');
}
const factSources = (fid) => (D.outline?.facts.find((f) => f.id === fid)?.sources) || [];
/** Brief options (target words, words per second, low-trust books): queued with everything else, answers merged without redrawing what the owner is typing in. */
function setOption(o, { redrawSources = false } = {}) {
  return Q.run(async () => {
    try {
      S.brief.options = await send('PUT', `${P()}/brief/options`, o);
      S.brief = await J(`${P()}/brief`);
      toast('Đã lưu', 'ok', 1000);
      if (!root) return;
      $('#src-note').textContent = `${S.brief.totals.paragraphs} đoạn, ${S.brief.totals.words} từ`;
      if (redrawSources) { const f = snapFocus(); srcBody(); restoreFocus(f); }
      refreshMinutes(); refreshChrome();
    } catch (e) { errorToast(e); if (redrawSources && root) srcBody(); }
  });
}
async function toggleSource(src, box) {
  const curLow = new Set(S.brief.options.include_low || []);
  const curExc = new Set(S.brief.options.exclude || []);
  if (box.checked) {
    curExc.delete(src.book_id);
    curExc.delete(src.work_id);
    curExc.delete(src.code);
    if (src.low_trust) curLow.add(src.book_id);
  } else {
    if (src.low_trust) {
      curLow.delete(src.book_id);
      curLow.delete(src.work_id);
      curLow.delete(src.code);
    }
    curExc.add(src.book_id);
  }
  await setOption({ include_low: [...curLow], exclude: [...curExc] }, { redrawSources: true });
}
function refreshMinutes() {
  const wps = S.brief?.options.wps || 2.41;
  root?.querySelectorAll('[data-wb]').forEach((el) => { el.textContent = `khoảng ${(Number(el.dataset.wb) / wps / 60).toFixed(1)} phút`; });
}

// ------------------------------------------------------------------ outline column
const chip = (cls, text, fn, title) => h('span', { class: 'chip ' + cls, text, title, onclick: fn });
const srcChips = (list) => h('div', { class: 'chips' }, list.map((s) => chip('src', s, () => focusParas([s]), 'Xem đoạn nguồn')));
const factChips = (list) => h('div', { class: 'chips' }, list.map((f) => chip(D.outline?.facts.some((x) => x.id === f) ? 'fact' : 'bad', f, () => focusParas(factSources(f)), 'Xem các đoạn nguồn của dữ kiện này')));
function issueFor(kind, pred) { return (ST[kind].issues || []).filter((i) => i.level !== 'info' && pred(i)); }
let beatIssues = new Map();                       // beat id -> its issues (one pass per drawing, not one pass per line)
const indexBeatIssues = () => { beatIssues = new Map(); for (const i of ST.narr.issues || []) if (i.beat && i.level !== 'info') { if (!beatIssues.has(i.beat)) beatIssues.set(i.beat, []); beatIssues.get(i.beat).push(i); } };
const issueHint = (is) => (is.length ? h('div', { class: 'hint warn', text: is.map((x) => issueText(x).text).join(' ') }) : null);

function outBody() {
  const body = $('#out-body'), o = D.outline;
  if (!o) {
    body.replaceChildren(h('div', { class: 'empty' }, 'Chưa có dàn ý.', h('br'), 'Bấm "Lập dàn ý" để mô hình viết, hoặc "Dán" để dán dàn ý đã nhờ Gemini viết.', h('br'),
      h('button', { class: 'primary', onclick: () => runDialog('outline'), text: 'Lập dàn ý' }), h('button', { onclick: () => pasteDialog('outline'), text: 'Dán dàn ý' })));
    return;
  }
  const kids = [];
  kids.push(h('h3', { class: 'sh', text: 'Câu hỏi chính (thesis)' }), h('textarea', { id: 'out-thesis', value: o.thesis, rows: 2, oninput: (e) => { fit(e.target); mutate('outline', () => { o.thesis = e.target.value; }, 'thesis'); } }));
  kids.push(h('h3', { class: 'sh', id: 'out-hooks' }, 'Câu mở đầu (chọn một)'));
  o.hook_options.forEach((hk) => kids.push(h('div', { class: 'hookrow' },
    h('input', { type: 'radio', name: 'hook', checked: o.hook_choice === hk.id, title: 'Chọn câu này', onchange: () => mutate('outline', () => { o.hook_choice = hk.id; }) }),
    h('textarea', { value: hk.text, rows: 2, oninput: (e) => mutate('outline', () => { hk.text = e.target.value; }, 'hook' + hk.id) }),
    h('button', { class: 'small danger', text: 'x', title: 'Xóa', onclick: () => { mutate('outline', () => { o.hook_options = o.hook_options.filter((x) => x !== hk); if (o.hook_choice === hk.id) o.hook_choice = o.hook_options[0]?.id || null; }); outBody(); } }))));
  kids.push(h('button', { class: 'small', text: '+ Thêm câu mở', onclick: () => { mutate('outline', () => { const n = Math.max(0, ...o.hook_options.map((x) => Number(x.id.replace(/\D/g, '')) || 0)) + 1; o.hook_options.push({ id: 'h' + n, text: '' }); if (!o.hook_choice) o.hook_choice = 'h' + n; }); outBody(); } }));

  const tw = o.chapters.reduce((a, c) => a + (Number(c.word_budget) || 0), 0);
  kids.push(h('h3', { class: 'sh' }, 'Các chương', h('span', { class: 'muted', style: { textTransform: 'none' }, text: `ngân sách ${tw} / mục tiêu ` }),
    intField({ id: 'out-target', value: o.target_words, min: 0, max: 20000, label: 'Mục tiêu số từ của dàn ý', style: { width: '80px', padding: '1px 5px' }, onValid: (v) => { mutate('outline', () => { o.target_words = v; }); outBody(); } })));
  o.chapters.forEach((c, i) => {
    const is = issueFor('outline', (x) => x.chapter === c.id);
    kids.push(h('div', { class: 'card' + (is.some((x) => x.level === 'error') ? ' err' : ''), 'data-ocard': c.id },
      h('div', { class: 'r' }, h('span', { class: 'small-id mono', text: c.id }),
        h('input', { type: 'text', class: 'ttl', value: c.title, oninput: (e) => mutate('outline', () => { c.title = e.target.value; }, 'ct' + c.id) }),
        h('button', { class: 'small', text: '↑', disabled: i === 0, onclick: () => { mutate('outline', () => { [o.chapters[i - 1], o.chapters[i]] = [o.chapters[i], o.chapters[i - 1]]; }); outBody(); } }),
        h('button', { class: 'small', text: '↓', disabled: i === o.chapters.length - 1, onclick: () => { mutate('outline', () => { [o.chapters[i + 1], o.chapters[i]] = [o.chapters[i], o.chapters[i + 1]]; }); outBody(); } }),
        h('button', { class: 'small danger', text: 'Xóa', onclick: async () => { if (await confirmDialog(`Xóa chương ${c.id} khỏi dàn ý?`, { title: 'Xóa chương', ok: 'Xóa', danger: true })) { mutate('outline', () => { o.chapters = o.chapters.filter((x) => x !== c); }); outBody(); } } })),
      h('div', { class: 'r' }, h('label', { text: 'Vai trò' }),
        fillSelect(h('select', { onchange: (e) => mutate('outline', () => { c.role = e.target.value; }) }), ['cold_open', 'chapter', 'closing'], c.role, (r) => ({ cold_open: 'mở đầu', chapter: 'chương', closing: 'kết' }[r] || r)),
        h('label', { class: 'chk', style: { display: 'inline-flex', gap: '4px', width: 'auto', whiteSpace: 'nowrap' }, title: 'Hiện thẻ tiêu đề chương trong video' }, h('input', { type: 'checkbox', checked: c.card, onchange: (e) => mutate('outline', () => { c.card = e.target.checked; }) }), 'thẻ chương')),
      h('div', { class: 'r' }, h('label', { text: 'Số từ' }), intField({ value: c.word_budget, min: 0, max: 20000, label: `Số từ của chương ${c.id}`, style: { width: '110px', flex: 'none' }, onValid: (v) => { mutate('outline', () => { c.word_budget = v; }); outBody(); } }), h('span', { class: 'muted', 'data-wb': c.word_budget, text: `khoảng ${(c.word_budget / (S.brief.options.wps || 2.41) / 60).toFixed(1)} phút` })),
      h('div', { class: 'r' }, h('label', { text: 'Mục đích' }), h('textarea', { value: c.purpose, rows: 2, oninput: (e) => mutate('outline', () => { c.purpose = e.target.value; }, 'cp' + c.id) })),
      h('div', { class: 'r' }, h('label', { text: 'Dữ kiện' }), h('input', { type: 'text', value: c.facts.join(', '), onchange: (e) => { mutate('outline', () => { c.facts = ids(e.target.value); }); outBody(); } })), factChips(c.facts),
      h('div', { class: 'r' }, h('label', { text: 'Cho xem' }), h('input', { type: 'text', value: c.show.join('; '), title: 'Ngăn cách bằng dấu ;', onchange: (e) => mutate('outline', () => { c.show = e.target.value.split(';').map((x) => x.trim()).filter(Boolean); }) })),
      issueHint(is)));
  });
  kids.push(h('button', { class: 'small', text: '+ Thêm chương', onclick: () => { mutate('outline', () => { const n = Math.max(0, o.chapters.length, ...o.chapters.map((x) => Number(x.id.replace(/\D/g, '')) || 0), o.counters?.chapter || 0) + 1; o.chapters.push({ id: 'c' + String(n).padStart(2, '0'), role: 'chapter', title: 'CHƯƠNG MỚI', card: true, purpose: '', word_budget: 200, facts: [], show: [] }); }); outBody(); } }));

  kids.push(h('h3', { class: 'sh', text: 'Bảng dữ kiện' }));
  o.facts.forEach((f) => {
    const is = issueFor('outline', (x) => x.fact === f.id);
    kids.push(h('div', { class: 'card' + (f.certainty === 'disputed' ? ' warnc' : ''), 'data-fact': f.id },
      h('div', { class: 'r' }, h('span', { class: 'small-id mono', text: f.id }),
        fillSelect(h('select', { style: { width: '150px', flex: 'none' }, onchange: (e) => { mutate('outline', () => { f.certainty = e.target.value; }); outBody(); } }), ['established', 'likely', 'disputed'], f.certainty, (c) => ({ established: 'chắc chắn', likely: 'nhiều khả năng', disputed: 'tranh cãi' }[c] || c)),
        h('input', { type: 'text', value: f.sources.join(', '), placeholder: 'mã đoạn nguồn, ví dụ PAY-07, HOD-02', onchange: (e) => { mutate('outline', () => { f.sources = ids(e.target.value).map((x) => x.toUpperCase()); }); outBody(); } }),
        h('button', { class: 'small danger', text: 'Xóa', onclick: () => { mutate('outline', () => { o.facts = o.facts.filter((x) => x !== f); }); outBody(); } })),
      srcChips(f.sources),
      h('textarea', { value: f.claim, rows: 2, oninput: (e) => mutate('outline', () => { f.claim = e.target.value; }, 'fc' + f.id) }),
      h('div', { class: 'r', style: { marginTop: '4px' } }, h('label', { text: 'Mâu thuẫn' }), h('input', { type: 'text', value: f.conflict || '', placeholder: 'để trống nếu các nguồn thống nhất', oninput: (e) => mutate('outline', () => { f.conflict = e.target.value || null; }, 'fx' + f.id) })),
      issueHint(is)));
  });
  kids.push(h('button', { class: 'small', text: '+ Thêm dữ kiện', onclick: () => { mutate('outline', () => { const n = Math.max(0, o.counters?.fact || 0, ...o.facts.map((x) => Number(x.id.replace(/\D/g, '')) || 0)) + 1; o.counters = { ...(o.counters || {}), fact: n }; o.facts.push({ id: 'f' + String(n).padStart(2, '0'), claim: '', sources: [], certainty: 'likely', conflict: null }); }); outBody(); } }));
  if (o.source?.kind) kids.push(h('div', { class: 'hint', style: { marginTop: '14px' }, text: `Nguồn dàn ý: ${sourceWords(S.pick?.agents(), o.source)}, ${(o.source.created_at || '').slice(0, 16).replace('T', ' ')}` }));
  body.replaceChildren(...kids);
  fitAll(body);
}

// ------------------------------------------------------------------ narration column
const chapWords = (ch) => ch.beats.reduce((a, b) => a + words(b.text), 0);
const chapBudget = (ch) => ST.narr.stats?.chapters.find((c) => c.id === ch.id)?.budget || D.outline?.chapters.find((c) => c.id === ch.id)?.word_budget || 0;
const chapWcText = (ch) => { const bud = chapBudget(ch); return `${chapWords(ch)}${bud ? ' / ' + bud : ''} từ`; };
function narBody() {
  const body = $('#nar-body'), n = D.narr;
  if (!n) {
    body.replaceChildren(h('div', { class: 'empty' }, 'Chưa có lời dẫn.', h('br'), approvedFlag('outline') ? 'Dàn ý đã duyệt. Bấm "Viết lời dẫn" hoặc dán bản đã viết.' : 'Cần duyệt dàn ý trước, rồi mô hình mới viết lời dẫn.', h('br'),
      h('button', { class: 'primary', onclick: () => runDialog('narration'), disabled: !approvedFlag('outline'), text: 'Viết lời dẫn' }), h('button', { onclick: () => pasteDialog('narration'), text: 'Dán lời dẫn' })));
    return;
  }
  const kids = [approvalNote()].filter(Boolean);
  indexBeatIssues();
  for (const ch of n.chapters) {
    kids.push(h('div', { class: 'chap', id: 'chap-' + ch.id },
      h('div', { class: 'chap-h' }, h('span', { class: 'cid mono', text: ch.id }), h('span', { class: 'ttl', text: ch.title }),
        ch.card ? h('span', { class: 'tag', text: 'thẻ chương' }) : null,
        h('span', { class: 'wc mono', 'data-wc': ch.id, text: chapWcText(ch) }),
        h('button', { class: 'small', text: chapWords(ch) ? 'Viết lại chương' : 'Viết chương này', title: 'Mô hình viết lại chương này, kèm ghi chú của bạn', onclick: () => runDialog('narration', ch.id) }),
        headerRole(ch.id, D.outline).inOutline ? null : h('button', { class: 'small danger', 'data-act': 'drop', text: 'Xóa chương này khỏi lời dẫn', title: 'Dàn ý không có chương này', onclick: () => dropChapter(ch.id) }),
        h('button', { class: 'small', text: '+ Dòng', onclick: () => doOp({ op: 'insert', chapter: ch.id, after: ch.beats.at(-1)?.id || null }) })),
      ...ch.beats.map((b, i) => beatEl(ch, b, i))));
  }
  for (const it of diffItems(ST.narr.chapter_diff).filter((x) => x.kind === 'missing')) kids.push(h('div', { class: 'card warnc' }, diffRow(it)));
  if (n.source?.kind) kids.push(h('div', { class: 'hint', text: `Nguồn lời dẫn: ${sourceWords(S.pick?.agents(), n.source)}, ${(n.source.created_at || '').slice(0, 16).replace('T', ' ')}` }));
  body.replaceChildren(...kids);
  fitAll(body);
}
function beatEl(ch, b, i) {
  const is = beatIssues.get(b.id) || [];
  const lvl = is.some((x) => x.level === 'error') ? ' err' : is.length ? ' warnb' : '';
  const wcn = h('span', { class: 'wcn mono' });
  const upd = () => { const w = words(b.text); wcn.textContent = `${w} từ`; wcn.className = 'wcn mono' + (w > 90 ? ' over' : ''); };
  const ta = h('textarea', { value: b.text, disabled: b.locked, spellcheck: true, oninput: (e) => {
    mutate('narr', () => { b.text = e.target.value; }, 'bt' + b.id); fit(e.target); upd();
    const wc = root?.querySelector(`[data-wc="${ch.id}"]`); if (wc) wc.textContent = chapWcText(ch);
    renderStatus();
  } });
  const el = h('div', { class: 'beat' + lvl + (b.locked ? ' locked' : ''), id: 'beat-' + b.id },
    ta,
    h('div', { class: 'tools' }, h('span', { class: 'bid mono', text: b.id }), wcn,
      h('button', { class: 'small', text: 'Tách', title: 'Tách thành hai dòng tại vị trí con trỏ', disabled: b.locked, onclick: () => {
        // the server splits on whitespace tokens (str.split), so count tokens, not words
        const at = tokenCount(ta.value.slice(0, ta.selectionStart)), all = tokenCount(ta.value);
        if (at <= 0 || at >= all) return toast('Đặt con trỏ vào giữa câu rồi bấm Tách', 'warn');
        doOp({ op: 'split', beat: b.id, at_word: at });
      } }),
      h('button', { class: 'small', text: 'Gộp lên', title: 'Gộp với dòng phía trên', disabled: b.locked || i === 0, onclick: () => doOp({ op: 'merge', beat: b.id }) }),
      h('button', { class: 'small danger', text: 'Bỏ', title: 'Bỏ dòng này (mã không bị dùng lại)', disabled: b.locked, onclick: () => doOp({ op: 'drop', beat: b.id }) }),
      h('button', { class: 'small', text: 'Chèn dưới', onclick: () => doOp({ op: 'insert', chapter: ch.id, after: b.id }) }),
      h('button', { class: 'small', text: '↑', title: 'Chuyển lên', onclick: () => moveBeat(b.id, -1) }),
      h('button', { class: 'small', text: '↓', title: 'Chuyển xuống', onclick: () => moveBeat(b.id, 1) }),
      h('label', { class: 'chk', title: 'Khóa: không sửa, không bị viết lại' }, h('input', { type: 'checkbox', checked: b.locked, onchange: (e) => { mutate('narr', () => { b.locked = e.target.checked; }); narBody(); } }), 'khóa')),
    h('div', { class: 'meta' }, h('span', { class: 'l', text: 'dữ kiện' }), h('input', { type: 'text', value: b.facts.join(', '), onchange: (e) => { mutate('narr', () => { b.facts = ids(e.target.value).map((x) => x.toLowerCase()); }); narBody(); } }),
      h('span', { class: 'l', text: 'cho xem' }), h('input', { type: 'text', value: b.show.join('; '), title: 'Ngăn cách bằng dấu ;', onchange: (e) => mutate('narr', () => { b.show = e.target.value.split(';').map((x) => x.trim()).filter(Boolean); }) })),
    b.facts.length ? factChips(b.facts) : null,
    h('div', { class: 'meta' }, h('span', { class: 'l', text: 'ghi chú' }), h('input', { type: 'text', value: b.note, placeholder: 'ghi chú riêng, không đọc lên', oninput: (e) => mutate('narr', () => { b.note = e.target.value; }, 'bn' + b.id) })),
    ...is.map((x) => h('div', { class: 'iss ' + (x.level === 'error' ? 'e' : ''), text: issueText(x).text })));
  if (b.facts.length) el.querySelector('.chips')?.classList.add('flat');
  upd();
  return el;
}
/** Moving a line up or down is queued as an INTENT: the concrete operation is worked out when its turn comes, from the
 *  document as the previous operation left it, so two quick clicks are two steps (never a false conflict). */
function moveBeat(bid, dir) {
  return doOp(() => {
    const chs = D.narr?.chapters || [], ch = chs.find((c) => c.beats.some((b) => b.id === bid));
    if (!ch) return null;
    const i = ch.beats.findIndex((b) => b.id === bid), ci = chs.indexOf(ch);
    if (dir < 0) {
      if (i > 0) return { op: 'move', beat: bid, to_chapter: ch.id, after: i > 1 ? ch.beats[i - 2].id : null };
      if (ci > 0) return { op: 'move', beat: bid, to_chapter: chs[ci - 1].id, after: chs[ci - 1].beats.at(-1)?.id || null };
    } else {
      if (i < ch.beats.length - 1) return { op: 'move', beat: bid, to_chapter: ch.id, after: ch.beats[i + 1].id };
      if (ci < chs.length - 1) return { op: 'move', beat: bid, to_chapter: chs[ci + 1].id, after: null };
    }
    toast('Không thể chuyển xa hơn', 'warn');
    return null;
  });
}
/** A structural operation on the narration. `op` is an object, or a function returning one when its turn comes (null = nothing to do). */
function doOp(op) {
  return Q.run(async () => {
    if (jobBlocks('narr')) { toast('Đang có tác vụ mô hình viết lời dẫn. Chờ nó xong rồi mới sửa cấu trúc (tách, gộp, bỏ, chuyển dòng).', 'warn', 7000); return; }
    if (!(await saveNow('narr'))) return;             // the draft goes first, so the operation is applied to what is on screen
    const o = typeof op === 'function' ? op() : op;
    if (!o) return;
    S.focus = 'narr';
    const before = D.narr ? JSON.stringify(D.narr) : null;
    try {
      const r = await send('POST', `${P()}/narration/ops`, { base_rev: R.narr, ops: [o] });
      redraw(await reconcile('narr', r)); pipeChanged();
      if (before && JSON.stringify(D.narr) !== before) { hist.narr.past.push(before); hist.narr.future = []; hist.narr.key = ''; }   // Hoàn tác puts the document back as it was before the operation
      const id = r.results?.[0]?.id;
      if (id && o.op !== 'merge' && root) scope.timeout(() => { const t = document.querySelector(`#beat-${id} textarea`); t?.scrollIntoView({ block: 'center' }); t?.focus(); }, 30);
    } catch (e) {
      if (e.status === 409) await recoverStale('narr', false);
      else errorToast(e);
    }
  });
}

// ------------------------------------------------------------------ status bar
function renderStatus() {
  if (!root) return;
  const n = D.narr, o = D.outline, wps = S.brief?.options.wps || 2.41;
  const total = n ? n.chapters.reduce((a, c) => a + chapWords(c), 0) : 0;
  const target = o?.target_words || S.brief?.options.target_words || 0;
  $('#st-totals').innerHTML = '';
  $('#st-totals').append(h('div', null, h('b', { text: `${total}` }), ` từ, khoảng `, h('b', { text: (total / wps / 60).toFixed(1) }), ' phút'), h('div', { class: 'muted', text: `mục tiêu ${target} từ (${(target / wps / 60).toFixed(1)} phút), ${wps} từ/giây` }));
  const bars = [];
  for (const c of o?.chapters || []) {
    const ch = n?.chapters.find((x) => x.id === c.id), w = ch ? chapWords(ch) : 0, bud = Number(c.word_budget) || 0;
    const r = bud ? w / bud : 0, cls = !ch ? '' : Math.abs(r - 1) > 0.3 ? 'far' : Math.abs(r - 1) > 0.15 ? 'off' : '';
    bars.push(h('div', { class: 'bar ' + cls, title: `${c.id} ${c.title}: ${w} / ${bud} từ` }, h('div', { class: 't', text: c.id + ' ' + c.title }), h('div', { class: 'tr' }, h('i', { style: { width: Math.min(100, (r / 1.6) * 100) + '%' } }), h('b'))));
  }
  $('#st-bars').replaceChildren(...bars);
  const jb = $('#st-job'); jb.replaceChildren();
  const j = currentJob;
  if (j) {
    jb.append(h('div', null, h('b', { text: j.kind === 'outline' ? 'Đang lập dàn ý' : 'Đang viết lời dẫn' }), ` (${usedAgent(S.pick?.agents(), j).label || j.model}) `, j.state === 'running' || j.state === 'queued' ? h('button', { class: 'small danger', text: 'Hủy', onclick: () => send('POST', `/api/jobs/${j.id}/cancel`).catch((e) => errorToast(e)) }) : null),
      h('div', null, j.chapters.map((c) => h('span', { class: 'jc ' + c.state, title: `${c.id} ${c.title}: ${c.state}${c.attempts > 1 ? ', thử lần ' + c.attempts : ''} ${c.message || ''}` }))),
      h('div', { class: 'muted', text: j.chapters.filter((c) => ['running', 'retrying'].includes(c.state)).map((c) => `${c.id}${c.state === 'retrying' ? ' (thử lại)' : ''}`).join(', ') || j.state }));
  } else jb.append(h('span', { class: 'muted', text: 'Không có tác vụ đang chạy' }));
}

// ------------------------------------------------------------------ jobs
/** Start a model job. The request names NO model: the server uses the agent of this project's step (the select of the toolbar). */
async function startJob(kind, body) {
  const out = await Q.run(async () => {
    if (!(await saveAllNow())) return { stop: true };
    try { const r = await send('POST', `${P()}/${kind}/generate`, body); return { jid: r.job_id }; }
    catch (e) { return { err: e }; }
  });
  if (out.jid) return watch(out.jid);
  const e = out.err;
  if (!e) return;
  if (e.status === 409 && e.body?.locked) { if (await confirmDialog('Có dòng đang khóa trong chương này. Vẫn viết lại và thay cả dòng khóa?', { title: 'Dòng đang khóa', ok: 'Viết lại cả dòng khóa', danger: true })) return startJob(kind, { ...body, force: true }); }
  else if (e.status === 409 && e.body?.job_id) watch(e.body.job_id);
  else errorToast(e);
}
function watch(jid) {
  clearInterval(jobPoll);
  let busy = false, ending = false;
  const tick = async () => {
    if (busy || ending) return;                              // a slow answer must not start a second end-of-job
    busy = true;
    try {
      const j = await J(`/api/jobs/${jid}`);
      currentJob = j; refreshChrome();
      if (['done', 'error', 'cancelled'].includes(j.state)) { ending = true; clearInterval(jobPoll); await jobEnded(j); }
    } catch (e) { ending = true; clearInterval(jobPoll); currentJob = null; errorToast(e); refreshChrome(); }
    finally { busy = false; }
  };
  jobPoll = scope.interval(tick, 700); tick();
}
async function jobEnded(j) {
  let changed = false;
  try {
    await Q.run(async () => {
      const [o, n] = [await J(`${P()}/outline`), await J(`${P()}/narration`)];
      const a = await reconcile('outline', o, B.outline, 'Tác vụ mô hình vừa ghi vào dàn ý.');
      const b = await reconcile('narr', n, B.narr, 'Tác vụ mô hình vừa ghi vào lời dẫn.');
      changed = a || b;
    });
  } catch (e) { errorToast(e, 'Không tải lại được kết quả của tác vụ: '); }
  currentJob = null;
  redraw(changed);
  if (!root) return;
  const kept = dirty.outline || dirty.narr;
  if (j.state === 'done') toast((j.kind === 'outline' ? 'Dàn ý đã viết xong. Hãy đọc, sửa rồi duyệt.' : 'Lời dẫn đã viết xong. Hãy đọc, sửa rồi duyệt.') + (kept ? ' Chữ bạn gõ trong lúc chạy được giữ lại, chưa lưu.' : ''), 'ok', 6000);
  else if (j.state === 'cancelled') toast('Đã hủy. Phần đã viết xong được giữ lại.' + (kept ? ' Chữ bạn gõ trong lúc chạy cũng được giữ, chưa lưu.' : ''), 'warn', kept ? 7000 : 4200);
  else {
    const je = jobErrorText(j);
    if (!isQuota(j)) toast(je.text + (kept ? ' Chữ bạn gõ trong lúc chạy được giữ lại, chưa lưu.' : ''), 'err', 12000, je.detail);
    else {
      // the agent's quota is used up: one sentence (the agent and the time) and ONE button that stores the other agent as this step's choice
      // and runs the same request again; the system never switches by itself
      const m = modal({ title: AL.quota.scriptTitle,
        body: h('div', { class: 'body' }, quotaNode({ pid: S.pid, step: STEP_SCRIPT, rec: j, rerun: async () => { m.close(); await S.pick?.refresh(); retryLast(j.kind); } }),
          h('p', { class: 'hint', text: AL.quota.scriptKept + (kept ? ' Chữ bạn gõ trong lúc chạy cũng được giữ lại, chưa lưu.' : '') })) });
    }
    if (j.error_kind === 'validation' || j.error_kind === 'parse') { if (D.narr || ST.narr.last_paste || ST.outline.last_paste) toast('Câu trả lời lỗi được giữ trong ô "Dán".', 'warn', 8000); }
  }
  const sk = j.result?.skipped || [];
  if (sk.length) toast('Các dòng bạn khóa trong lúc chạy được giữ nguyên, mô hình không viết lại: ' + sk.map((x) => `${x.chapter}: ${(x.beats || []).join(', ')}`).join('; ') + '.', 'warn', 12000);
  if (j.error_kind === 'conflict' && j.kind === 'outline') {
    const m = modal({ title: 'Dàn ý đã đổi trong lúc mô hình viết', body: h('div', { class: 'body' }, h('p', { text: 'Bạn đã lưu dàn ý khi mô hình đang viết, nên dàn ý của mô hình không được ghi đè lên bản của bạn. Bản của bạn còn nguyên.' }), h('p', { text: 'Câu trả lời của mô hình được giữ trong ô "Dán". Mở ra để xem, rồi dán nếu muốn thay bản hiện tại (bản cũ vẫn giữ ở .prev.json).' })),
      footer: h('footer', null, h('button', { text: 'Để sau', onclick: () => m.close() }), h('button', { class: 'primary', text: 'Mở ô Dán', onclick: () => { m.close(); pasteDialog('outline'); } })) });
  }
  pipeChanged();
}
function retryLast(kind = null) { if (!lastRun && kind) lastRun = { kind, body: {} }; if (lastRun) startJob(lastRun.kind, lastRun.body); }

function runDialog(kind, chapters) {
  const agent = S.pick?.effective();
  if (S.brief && S.brief.totals.included === 0) return toast('Chưa có nguồn nào được dùng, mô hình sẽ không có gì để viết. Ở cột Nguồn, tick "Dùng sách này làm nguồn" cho một sách dịch máy (nếu chấp nhận rủi ro).', 'err', 10000);
  const chs = chapters ? [].concat(chapters) : null;
  const exists = kind === 'outline' ? !!D.outline : !!D.narr && !chs;
  const notes = h('textarea', { rows: 4, placeholder: kind === 'outline' ? 'Ví dụ: tập trung vào chiếc gương, bỏ phần giả kim thuật' : 'Ví dụ: ngắn hơn, bớt tiểu sử, thêm một cách đọc khác' });
  const title = kind === 'outline' ? 'Lập dàn ý' : chs ? `Viết lại ${chs.join(', ')}` : 'Viết lời dẫn';
  const m = modal({ title, cls: 'wide', body: h('div', { class: 'body' },
    h('p', null, 'Agent: ', h('b', { text: agent?.label || AL.noneYet })), exists ? h('p', { class: 'hint warn', text: kind === 'outline' ? 'Dàn ý hiện tại sẽ bị thay (bản cũ giữ ở outline.prev.json) và mất trạng thái duyệt.' : 'Lời dẫn hiện tại sẽ bị thay (bản cũ giữ ở narration.prev.json).' }) : null,
    h('label', { class: 'lb', text: 'Ghi chú cho mô hình (tùy chọn)' }), notes),
    footer: h('footer', null, h('button', { onclick: () => m.close(), text: 'Hủy' }), h('button', { class: 'primary', text: 'Chạy', onclick: () => { m.close(); lastRun = { kind, body: { notes: notes.value, ...(chs ? { chapters: chs } : {}) } }; startJob(kind, lastRun.body); } })) });
  scope.timeout(() => notes.focus(), 30);
}

// ------------------------------------------------------------------ copy prompt and paste dialogs
function copyDialog(phase = 'outline') {
  const notes = h('textarea', { rows: 2, placeholder: 'Ghi chú thêm cho prompt (tùy chọn)' });
  const chap = h('select', null, h('option', { value: '', text: 'Tất cả các chương' }), ...(D.outline?.chapters || []).map((c) => h('option', { value: c.id, text: `${c.id} ${c.title}` })));
  const box = h('textarea', { class: 'big', readOnly: true, spellcheck: false, onfocus: (e) => e.target.select() });
  const info = h('div', { class: 'hint' });
  const tabs = {};
  let seq = 0;
  const setPhase = async (ph) => {
    phase = ph; for (const [k, b] of Object.entries(tabs)) b.classList.toggle('active', k === ph);
    chap.style.display = ph === 'script' ? '' : 'none';
    const mine = ++seq;                                       // an older answer must not replace a newer one
    try {
      const q = new URLSearchParams({ phase: ph, notes: notes.value, chapters: ph === 'script' ? chap.value : '' });
      const t = await api.get(`${P()}/prompt?${q}`);
      if (mine !== seq) return;
      box.value = t; info.className = 'hint'; info.textContent = `${t.length} ký tự, ${words(t)} từ. Dán vào Gemini, rồi dán câu trả lời của nó vào nút "Dán".`;
    } catch (e) { if (mine !== seq) return; box.value = ''; errorInto(info, e); info.className = 'hint err'; }
  };
  tabs.outline = h('button', { text: 'Prompt dàn ý', onclick: () => setPhase('outline') });
  tabs.script = h('button', { text: 'Prompt lời dẫn', onclick: () => setPhase('script') });
  notes.addEventListener('change', () => setPhase(phase)); chap.addEventListener('change', () => setPhase(phase));
  const copy = h('button', { class: 'primary', text: 'Sao chép', onclick: async () => {
    box.focus(); box.select();
    try { await navigator.clipboard.writeText(box.value); toast('Đã sao chép vào bộ nhớ tạm', 'ok', 1800); } catch { try { document.execCommand('copy'); toast('Đã sao chép', 'ok', 1800); } catch { toast('Trình duyệt chặn bộ nhớ tạm. Văn bản đã được bôi đen, bấm Ctrl+C (Cmd+C).', 'warn', 7000); } }
  } });
  const m = modal({ title: 'Sao chép prompt', cls: 'wide', body: h('div', { class: 'body' }, h('div', { class: 'tabs' }, tabs.outline, tabs.script, chap), notes, h('div', { style: { height: '8px' } }), box, info), footer: h('footer', null, copy, h('button', { onclick: () => m.close(), text: 'Đóng' })) });
  setPhase(phase);
}
function pasteDialog(kind = 'outline') {
  PASTE.outline = PASTE.outline || ST.outline.last_paste || ''; PASTE.narration = PASTE.narration || ST.narr.last_paste || '';
  let cur = kind;
  const ta = h('textarea', { class: 'big', placeholder: 'Dán nguyên câu trả lời của mô hình vào đây. Phần mở đầu, danh sách câu mở, bảng kiểm tra và đếm từ sẽ được tự bỏ.', value: PASTE[cur], 'aria-label': 'Câu trả lời của mô hình' });
  const err = h('div', { role: 'alert' }), merge = h('input', { type: 'checkbox' });
  const mergeLbl = h('label', { class: 'chk' }, merge, 'Chỉ thay các chương có trong bản dán (giữ các chương khác)');
  const tabs = {};
  ta.addEventListener('input', () => { PASTE[cur] = ta.value; ta.classList.remove('invalid'); if (err.dataset.empty) err.replaceChildren(); });
  const setKind = (k) => { PASTE[cur] = ta.value; cur = k; ta.value = PASTE[k]; err.replaceChildren(); ta.classList.remove('invalid'); for (const [x, b] of Object.entries(tabs)) b.classList.toggle('active', x === k); mergeLbl.style.display = k === 'narration' ? '' : 'none'; };
  tabs.outline = h('button', { text: 'Dán dàn ý', onclick: () => setKind('outline') }); tabs.narration = h('button', { text: 'Dán lời dẫn', onclick: () => setKind('narration') });
  const showErr = (text, empty) => { err.dataset.empty = empty ? '1' : ''; err.replaceChildren(h('div', { class: 'hint err', text })); };
  const go = h('button', { class: 'primary', text: 'Phân tích và lưu', onclick: async () => {
    const text = ta.value, kk = cur === 'outline' ? 'outline' : 'narr', withMerge = cur === 'narration' && merge.checked;
    if (!text.trim()) { showErr('Chưa có gì để phân tích. Dán câu trả lời của mô hình vào ô trên rồi bấm lại.', true); ta.classList.add('invalid'); ta.focus(); return; }
    if (jobBlocks(kk)) { showErr('Đang có tác vụ mô hình ghi vào phần này. Chờ nó xong hoặc bấm Hủy, rồi dán lại.'); return; }
    // "only replace these chapters": the other chapters (with the owner's unsaved edits) stay, so they are saved first
    if (!withMerge && dirty[kk] && !(await confirmDialog('Bản đang sửa chưa lưu sẽ bị thay. Tiếp tục?', { title: 'Thay bản đang sửa', ok: 'Tiếp tục', danger: true }))) return;
    if (!withMerge && D[kk] && !(await confirmDialog('Bản hiện có sẽ bị thay bằng bản dán (bản cũ giữ ở tệp .prev.json). Tiếp tục?', { title: 'Thay bằng bản dán', ok: 'Tiếp tục', danger: true }))) return;
    err.replaceChildren(); go.disabled = true;
    try {
      let force = false, r = null;
      for (;;) {
        try {
          r = await Q.run(async () => {
            if (withMerge && dirty.narr && !(await saveNow('narr'))) return null;
            const base = D[kk] ? clone(D[kk]) : null;               // only what the owner types AFTER this point survives the answer
            const rr = await send('POST', `${P()}/${cur}/import`, { text, merge: withMerge, ...(force ? { force: true } : {}) });
            redraw(await reconcile(kk, rr, base, 'Có thay đổi mới trong lúc đang dán.'));
            if (kk === 'outline') { await refreshNarrStatus(); redraw(false); }
            return rr;
          });
          break;
        } catch (e) {
          // locked lines would be replaced: say which, and replace them only when the owner agrees
          if (e.status === 409 && Array.isArray(e.body?.locked) && !force) {
            const list = e.body.locked.join(', ');
            if (await confirmDialog(`Bản dán sẽ thay cả các dòng đang khóa: ${list}.\n\nBản dán được giữ lại. Vẫn thay cả các dòng khóa?`, { title: 'Có dòng đang khóa', ok: 'Thay cả dòng khóa', danger: true })) { force = true; continue; }
            showErr(`Chưa dán: sẽ thay các dòng đang khóa (${list}). Mở khóa các dòng đó, hoặc chọn "Chỉ thay các chương có trong bản dán" cho chương khác.`);
            go.disabled = false; return;
          }
          throw e;
        }
      }
      if (!r) { go.disabled = false; return; }
      PASTE[cur] = ''; pipeChanged(); m.close();
      toast('Đã đọc và lưu. ' + ((r.parse_issues || []).length ? `Có ${r.parse_issues.length} lưu ý, xem hộp "Lưu ý khi đọc bản dán".` : ''), 'ok', 5000);
      if (r.parse_issues?.length) showParseIssues(r.parse_issues);
    } catch (e) {
      if (e.status === 422) {
        PASTE[cur] = text; if (cur === 'outline') ST.outline.last_paste = text; else ST.narr.last_paste = text;
        err.replaceChildren(...kids(h('div', { class: 'hint err', text: parseFailText(e.body?.error || e.body?.detail || '') + ' Văn bản vừa dán đã được giữ lại, sẽ hiện lại khi tải trang. Không có gì bị ghi đè.' }), paragraphList(e.body?.paragraphs)));
      } else { const box = h('div', { class: 'hint err' }); errorInto(box, e); err.replaceChildren(box); }
    } finally { go.disabled = false; }
  } });
  const m = modal({ title: 'Dán câu trả lời của mô hình', cls: 'wide', backdrop: false, onClose: () => { PASTE[cur] = ta.value; },
    body: h('div', { class: 'body' }, h('div', { class: 'tabs' }, tabs.outline, tabs.narration), ta, h('div', { style: { margin: '6px 0' } }, mergeLbl), err), footer: h('footer', null, h('button', { onclick: () => m.close(), text: 'Đóng' }), go) });
  setKind(kind);
  scope.timeout(() => ta.focus(), 30);
}
/** What the parser saw, in Vietnamese: paragraphs with their word counts, under the chapter line they sit in. */
function paragraphList(paras) {
  if (!Array.isArray(paras) || !paras.length) return null;
  const rows = [h('div', { class: 'muted', text: `Máy đọc thấy ${paras.length} đoạn:` })];
  let cur = Symbol();
  for (const p of paras.slice(0, 60)) {
    if (p.heading !== cur) { cur = p.heading; rows.push(h('div', { class: 'para-sec', text: cur ? `## ${cur}` : '(trước dòng chương nào)' })); }
    rows.push(h('div', null, `[${p.n}] ${p.words} từ: "${p.start}"`));
  }
  if (paras.length > 60) rows.push(h('div', { class: 'muted', text: `... và ${paras.length - 60} đoạn nữa` }));
  return h('div', { class: 'pre' }, ...rows);
}
function showParseIssues(list) {
  modal({ title: 'Lưu ý khi đọc bản dán', body: h('div', { class: 'body' }, ...list.map((i) => issueRow(i))) });
}
function issueRow(i, extra) {
  const t = issueText(i);
  return h('div', { class: 'issue-row' }, h('span', { class: 'lv ' + i.level, text: LEVEL[i.level] || i.level }),
    h('span', null, t.text, t.generic && t.detail ? detailFold(t.detail) : null, extra || null));
}

// ------------------------------------------------------------------ check list and approve
/** Where an issue lives on the page: the line of the narration, the card of the outline, or the field it is about. */
function issueTarget(kind, i) {
  if (i.beat) return document.getElementById('beat-' + i.beat);
  if (['outline_missing', 'outline_not_approved', 'outline_stale'].includes(i.code)) return $('#col-out .col-h');
  if (kind === 'narr') return i.chapter ? document.getElementById('chap-' + i.chapter) : $('#nar-body');
  if (i.fact) return $(`[data-fact="${i.fact}"]`);
  if (i.chapter) return $(`[data-ocard="${i.chapter}"]`);
  if (i.code === 'no_thesis') return $('#out-thesis');
  if (i.code === 'no_hook_choice') return $('#out-hooks');
  if (i.code === 'budget_sum') return $('#out-target');
  return $('#out-body');
}
const flashTimers = new WeakMap();
function gotoIssue(kind, i, dlg) {
  dlg.close();
  const el = issueTarget(kind, i);
  if (!el) return toast('Không tìm thấy chỗ này trên trang (có thể đã bị xóa). Hãy lưu lại để cập nhật danh sách.', 'warn', 6000);
  el.scrollIntoView({ block: el.getBoundingClientRect().height > innerHeight * 0.5 ? 'start' : 'center', behavior: 'smooth' });
  clearTimeout(flashTimers.get(el));
  el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');     // restarts the highlight when the same place is chosen twice
  flashTimers.set(el, setTimeout(() => el.classList.remove('flash'), 1900));
  if (el.matches('textarea,input')) el.focus({ preventScroll: true });
}
function checkDialog() {
  const rows = [];
  let m;
  for (const [k, label] of [['outline', 'Dàn ý'], ['narr', 'Lời dẫn']]) {
    const list = (ST[k].issues || []).slice().sort((a, b) => ['error', 'warning', 'info'].indexOf(a.level) - ['error', 'warning', 'info'].indexOf(b.level));
    rows.push(h('h3', { class: 'sh', text: label + (dirty[k] ? ' (kết quả của bản đã lưu, hãy lưu lại để cập nhật)' : '') }));
    if (!list.length) rows.push(h('div', { class: 'muted', text: 'Không có gì.' }));
    for (const i of list) {
      const canGo = i.level !== 'info' || i.beat;
      rows.push(issueRow(i, canGo ? h('a', { href: '#', class: 'goto', style: { marginLeft: '8px', color: 'var(--accent)' }, text: i.beat ? 'đến dòng' : 'đến chỗ này', onclick: (e) => { e.preventDefault(); gotoIssue(k, i, m); } }) : null));
    }
  }
  m = modal({ title: 'Kiểm tra', cls: 'wide', body: h('div', { class: 'body' }, ...rows) });
}
function approve() {
  return Q.run(async () => {
    const kind = $('#btn-approve').dataset.kind, kk = kind === 'outline' ? 'outline' : 'narr';
    if (!(await saveAllNow())) return;
    try {
      const r = await send('POST', `${P()}/${KIND[kk].url}/approve`, { rev: R[kk] });
      redraw(await reconcile(kk, r));
      if (kk === 'outline') { await refreshNarrStatus(); redraw(false); }
      toast(kind === 'outline' ? 'Đã duyệt dàn ý' : 'Đã duyệt lời dẫn', 'ok');
      pipeChanged();
    } catch (e) {
      if (e.status === 409 && !e.body?.issues && /changed|rev/i.test(String(e.body?.detail || ''))) return void (await recoverStale(kk, false));
      if (e.body?.chapter_diff) {                          // refused because the chapters differ: list them
        ST.narr.chapter_diff = e.body.chapter_diff; renderAll();
        const items = diffItems(e.body.chapter_diff);
        if (items.length) { const m = modal({ title: 'Chưa duyệt được lời dẫn: chương không khớp dàn ý', body: h('div', { class: 'body', style: { maxWidth: '560px' } }, h('p', { text: 'Lời dẫn và dàn ý phải có cùng các chương, cùng thứ tự. Mỗi chỗ khác nhau có nút sửa ngay:' }), ...items.map((it) => diffRow(it, () => m.close()))) }); }
      }
      if (e.body?.issues) { ST[kk].issues = e.body.issues; renderAll(); if (!e.body?.chapter_diff) checkDialog(); }
      errorToast(e, '', 9000);
    }
  });
}

function renderAll() {
  if (!root) return;
  const f = snapFocus();
  srcBody(); outBody(); narBody(); refreshChrome();
  restoreFocus(f);
}

// ------------------------------------------------------------------ mount
const BAR = `
  <div class="vbar" id="sbar">
    <span id="agent-pick-host" class="agent-host"></span>
    <span class="sep"></span>
    <button id="btn-outline" title="Mô hình viết dàn ý từ các đoạn sách đã đánh số">Lập dàn ý</button>
    <button id="btn-write" title="Mô hình viết lời dẫn từng chương, theo dàn ý đã duyệt">Viết lời dẫn</button>
    <button id="btn-copy" title="Lấy prompt để dán vào Gemini hoặc chat khác">Sao chép prompt</button>
    <button id="btn-paste" title="Dán câu trả lời của mô hình (dàn ý hoặc lời dẫn)">Dán</button>
    <span class="sep"></span>
    <button id="btn-save" class="primary" title="Lưu (Ctrl+S)">Lưu<span id="dirty-dot" class="dot" hidden></span></button>
    <button id="btn-undo" title="Hoàn tác (Ctrl+Z)">Hoàn tác</button>
    <button id="btn-redo" title="Làm lại (Ctrl+Shift+Z)">Làm lại</button>
    <button id="btn-check" title="Danh sách lỗi và cảnh báo">Kiểm tra <span id="issue-count" class="count">0</span></button>
    <button id="btn-approve" title="Duyệt bản đã lưu (cần lưu trước, không còn lỗi)">Duyệt</button>
    <span id="approve-state" class="badge" title="Trạng thái duyệt"></span>
    <span class="grow"></span>
    <button id="btn-next" class="primary" hidden></button>
  </div>
  <main id="smain">
    <section class="col" id="col-src"><div class="col-h"><h2>Nguồn</h2><span class="muted" id="src-note"></span></div><div class="col-b" id="src-body"></div></section>
    <section class="col" id="col-out"><div class="col-h"><h2>Dàn ý</h2><span id="out-badge" class="badge"></span></div><div class="col-b" id="out-body"></div></section>
    <section class="col" id="col-nar"><div class="col-h"><h2>Lời dẫn</h2><span id="nar-badge" class="badge"></span></div><div class="col-b" id="nar-body"></div></section>
  </main>
  <footer id="sstatus">
    <div id="st-totals" class="mono"></div>
    <div id="st-bars"></div>
    <div id="st-job"></div>
  </footer>`;

export async function mount(host, ctx) {
  resetState();
  scope = ctx.scope; shell = ctx.shell;
  S.pid = ctx.pipeline.project;
  root = h('div', { class: 'scr-root v-scr' });
  root.innerHTML = BAR;
  host.append(root);
  // the agent select (the same on every step that calls a model); the page does not wait for it. A change of the list of agents (the answer of
  // GET /api/agents arriving) redraws the source lines, which name the agent by its label.
  S.pick = mountAgentPick($('#agent-pick-host'), { pid: S.pid, step: STEP_SCRIPT, scope, onChange: () => { if (root) { outBody(); narBody(); } } });
  S.pick.ready.then(() => { if (root) { outBody(); narBody(); } });
  $('#btn-outline').onclick = () => runDialog('outline');
  $('#btn-write').onclick = () => { if (!approvedFlag('outline')) return toast('Cần duyệt dàn ý trước khi viết lời dẫn.', 'warn'); runDialog('narration'); };
  $('#btn-copy').onclick = () => copyDialog(approvedFlag('outline') && D.outline ? 'script' : 'outline');
  $('#btn-paste').onclick = () => pasteDialog(D.outline && approvedFlag('outline') ? 'narration' : 'outline');
  $('#btn-save').onclick = () => saveAll(); $('#btn-undo').onclick = () => undoRedo(-1); $('#btn-redo').onclick = () => undoRedo(1);
  $('#btn-check').onclick = checkDialog; $('#btn-approve').onclick = approve;
  scope.on(document, 'keydown', (e) => {                 // removed when the view is left: Ctrl+S and Ctrl+Z never reach another view
    const mod = e.ctrlKey || e.metaKey, k = (e.key || '').toLowerCase();
    if (mod && k === 's') { e.preventDefault(); if (!modalOpen()) saveAll(); }
    else if (mod && k === 'z' && !modalOpen() && !(e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT')) { e.preventDefault(); undoRedo(e.shiftKey ? 1 : -1); }
  });
  await loadAll();
  const jobs = await J(`${P()}/script/jobs`).catch(() => []);
  const run = jobs.find((j) => ['queued', 'running'].includes(j.state));
  if (run) watch(run.id);
  if (ST.outline.last_paste && !D.outline) toast('Có bản dán dàn ý bị lỗi được giữ lại. Mở "Dán" để xem.', 'warn', 6000);
  if (ST.narr.last_paste) toast('Có bản dán lời dẫn bị lỗi được giữ lại. Mở "Dán" để xem.', 'warn', 6000);
  window.__scr = { S, D, R, B, ST, dirty, mutate, saveAll, doOp, pasteDialog, copyDialog, checkDialog, runDialog, reconcile, renderAll, queue: () => Q };
  return {
    isDirty: () => dirty.outline || dirty.narr,
    save: () => saveAll({ quiet: true }),
    dirtyMessage: () => `Kịch bản có chỗ sửa chưa lưu${dirty.outline ? ' (dàn ý)' : ''}${dirty.narr ? ' (lời dẫn)' : ''}.`,
    pipelineChanged: () => refreshChrome(),
    unmount() { window.__scr = null; root = null; },
  };
}
