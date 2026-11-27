// "Chọn hình" step: for each beat of the approved narration, the owner chooses what is on screen. Mounted at #/project/<id>/picks.
//
// Rules of this view:
//  - The draft (D) holds the beats and the main painting; it is saved by PUT with the revision it was loaded at (409 = changed
//    elsewhere). Everything that adds a picture (import, upload, regions, approval) goes through ONE queue (Q) and saves the
//    draft first, then replaces the draft with the server's answer, so a request never runs on a stale revision.
//  - A licence or a size problem never blocks anything: the flag is only shown.
//  - The paid "Gợi ý thêm" runs only when the owner confirms it, once per click.
//  - Words and error texts that are not yet in labels.js / errmsg.js live in the tables LBL and ERR below (CORE merges them).
import { api } from '../api.js';
import { h, kids, toast, errorToast, setStatus, modal, ask, confirmDialog, debounce } from '../util.js';
import { makeSpaces } from '../coords.js';
import { createQueue } from '../queue.js';
import { describeError, jobErrorText, sourceLimitText, STAGE_CODES } from '../errmsg.js';
import { PICKS_LABELS, SOURCE_LABELS, PICKS_AUTO_LABELS } from '../labels.js';
import { projectHash } from '../router.js';
import { watchIdle, jobWatcher } from '../idlewatch.js';
import { mountPromptEdit } from '../promptedit.js';          // c2box: the prompt box of this step
import * as L from './picks_logic.js';
import { mountPicksAuto } from './picks_auto.js';                                // c3picks: "Để agent chọn hình"
import { mountPickRows } from './picks_rows.js';                                // c4pages: the simple page (rows with their pictures); the hand tools below stay as they were
import { voiceStarts, issueSentence, captionEditOp } from './picks_rows_logic.js';
import { PICKS_PAGE_LABELS as PW } from '../labels.js';

// ------------------------------------------------------------------ words
const LBL = PICKS_LABELS;
// error `code` of the picks routes -> sentence (errmsg.js); anything else goes through describeError
const ERR = { ...STAGE_CODES.longjob, ...STAGE_CODES.picks };
const failText = (e) => ERR[e?.body?.code] || describeError(e).text;
/** The reason in a search banner, for one entry of `errors` ({source, code, retry_after}): a source that limits downloads says for how long, else the table's sentence. */
export const searchErrorText = (e) => (e?.code === 'source_rate_limited' ? sourceLimitText(e) : ERR[e?.code] || 'không tìm được.');
const fail = (e, prefix = '') => { const t = ERR[e?.body?.code]; if (t) toast(prefix + t, 'err', 8000); else errorToast(e, prefix); };

// ------------------------------------------------------------------ state
let root = null, scope = null, shell = null;
const $ = (s) => root?.querySelector(s);
const S = { pid: null, data: null, beat: null, tab: 'main', q: { text: '', sources: { commons: true, met: true, pexels: true, pixabay: true, osm: false }, res: null, busy: false, for: '' },
  v: { text: '', res: null, busy: false, importing: false }, books: null, sugg: { beats: {} }, job: null };
let auto = null;                                                              // c3picks: the agent's bar (views/picks_auto.js)
let rows = null, mode = 'simple', starts = new Map(), rowsQueued = false;     // c4pages: the simple page (views/picks_rows.js), which face shows, the start of each line from the voice
let D = null, R = null, dirty = false, editVersion = 0, Q = createQueue({ onBusy: (b) => setStatus(b ? 'đang xử lý...' : '') }), pollId = null;

const P = () => `/api/projects/${S.pid}/picks`;
const pipeChanged = () => shell?.refreshPipeline();
const assets = () => D?.assets || {};
const mainAsset = () => assets()[D?.main_asset] || null;
const chapters = () => S.data?.narration?.chapters || [];
const allBeats = () => chapters().flatMap((c) => c.beats);
const beatOf = (id) => allBeats().find((b) => b.id === id) || null;
const imgUrl = (a, w = 480) => `${api.fileUrl(S.pid, a.file)}?w=${w}`;

function applyData(r) {
  S.data = r; R = r.rev; D = L.clone(r.picks); dirty = false;
  if (!S.beat || !beatOf(S.beat)) S.beat = allBeats()[0]?.id || null;
}

// ------------------------------------------------------------------ saving
function touch() { dirty = true; editVersion++; paintStatus(); save(); }
const save = debounce(() => { Q.run(saveNow).catch(() => {}); }, 700);
async function saveNow() {
  if (!dirty || !D) return;
  const v = editVersion;
  setStatus('đang lưu...');
  try {
    const r = await api.put(P(), { picks: D, base_rev: R });
    S.data = r; R = r.rev;
    if (v === editVersion) { D = L.clone(r.picks); dirty = false; }
    paintStatus(); paintTop(); paintLeft();
    pipeChanged();
  } catch (e) {
    if (e?.status === 409) await recover(); else fail(e, 'Không lưu được: ');
    throw e;
  } finally { setStatus(''); }
}
/** Save the draft, run `fn` (a request that changes picks.json and answers the whole state), take its answer as the new draft. */
function serverOp(fn, then) {
  return Q.run(async () => {
    save.cancel?.();
    await saveNow();
    let r;
    try { r = await fn(); } catch (e) { fail(e); throw e; }
    applyData(r); renderAll(); pipeChanged();
    return then ? then(r) : r;
  }).catch(() => null);
}
/** The picks changed elsewhere. Take the server's version and put the owner's edit back when it still makes sense: a beat that
 *  still exists keeps its items whose picture (and region) still exist; one line says what was not kept. */
async function recover() {
  const mine = D ? L.clone(D) : null;
  let fresh;
  try { fresh = await api.get(P()); } catch (e) { fail(e, 'Không tải được: '); return; }
  applyData(fresh);
  let lost = 0, kept = 0;
  if (mine) {
    for (const [bid, b] of Object.entries(mine.beats || {})) {
      if (JSON.stringify(L.ensureBeat(D, bid)) === JSON.stringify(b)) continue;
      if (!beatOf(bid)) { lost += (b.items || []).length; delete D.beats[bid]; continue; }
      const items = (b.items || []).filter((i) => D.assets[i.asset] && (!i.region || i.region in D.assets[i.asset].regions));
      lost += (b.items || []).length - items.length;
      D.beats[bid] = { ...b, items }; kept++;
    }
    if (kept) { dirty = true; editVersion++; }
  }
  toast(lost ? `Chọn hình đã đổi ở nơi khác. Đã giữ phần bạn vừa sửa, trừ ${lost} hình không còn.` : kept ? 'Chọn hình đã đổi ở nơi khác. Đã giữ phần bạn vừa sửa.' : ERR.stale, 'warn', 8000);
  renderAll();
  if (kept) save();
}
async function reload() {
  try { applyData(await api.get(P())); renderAll(); } catch (e) { fail(e, 'Không tải được: '); }
}

// ------------------------------------------------------------------ pieces
function flagBadge(flag) {
  return flag ? h('span', { class: 'pk-flag ' + flag, text: LBL.flag[flag] || flag, title: LBL.flagHelp[flag] || '' }) : null;
}
const credit = (a) => a?.credit || {};
function thumb(a, region, box = 64) {
  const el = h('div', { class: 'pk-thumb', style: { width: box + 'px', height: box + 'px' } });
  if (!a) return el;
  const crop = region ? L.cropStyle(a, a.regions?.[region], box) : null;
  el.style.backgroundImage = `url("${imgUrl(a, crop ? 900 : 200)}")`;
  if (crop) Object.assign(el.style, crop); else el.classList.add('fit');
  return el;
}

// ------------------------------------------------------------------ top bar: the main painting
function paintTop() {
  const top = $('#pk-top'); if (!top) return;
  if (mode === 'simple') { rows?.paintHeader(); paintStatus(); return; }          // c4pages: the header of the simple page
  const a = mainAsset(), d = S.data, errs = (d.issues || []).filter((i) => i.level === 'error');
  const nv = d.narration;
  top.replaceChildren(...kids(
    h('button', { id: 'pk-back', class: 'pk-back', text: PW.back, title: PW.backTitle, onclick: () => setMode('simple') }),
    h('div', { class: 'pk-main' }, thumb(a, null, 72),
      h('div', { class: 'pk-maininfo' },
        h('div', { class: 'pk-maintitle', text: a ? (a.title || D.main_asset) : 'Chưa chọn tranh chính' }),
        h('div', { class: 'muted', text: a ? [a.artist, a.year, L.sizeText(a.width, a.height)].filter(Boolean).join(' · ') : 'Bắt đầu bằng việc chọn bức tranh chính của video (tab "Tranh chính").' }),
        a ? flagBadge(credit(a).flag) : null)),
    h('div', { class: 'pk-topbtns' },
      a ? h('button', { text: 'Vùng trên tranh', title: 'Vẽ các vùng chi tiết trên tranh chính', onclick: () => regionEditor(D.main_asset) }) : null,
      h('button', { text: `Kiểm tra${errs.length ? ` (${errs.length} lỗi)` : ''}`, class: errs.length ? 'danger' : '', onclick: checkDialog }),
      h('span', { id: 'pk-state', class: 'muted' }),
      h('button', { class: 'primary', id: 'pk-approve', text: d.approved ? 'Đã duyệt' : 'Duyệt chọn hình', disabled: !!d.approved && !dirty, onclick: approve })),
    !nv.present ? h('div', { class: 'pk-banner warn', text: 'Dự án chưa có lời dẫn. Hãy viết và duyệt lời dẫn ở bước Kịch bản.' })
      : !nv.approved ? h('div', { class: 'pk-banner warn' }, `Lời dẫn chưa được duyệt${nv.reason === 'narration_edited' ? ' (đã đổi sau khi duyệt)' : ''}: bạn vẫn chọn hình được, nhưng chưa duyệt chọn hình được. `,
        h('a', { class: 'lnk', href: projectHash(S.pid, 'script'), text: 'Mở bước Kịch bản' }))
      : d.approval_reason ? h('div', { class: 'pk-banner warn', text: 'Đã duyệt trước đó nhưng cần duyệt lại. ' + (LBL.reason[d.approval_reason] || '') }) : null));
  paintStatus();
}
function paintStatus() {
  const el = $('#pk-state'); if (!el) return;
  el.textContent = dirty ? 'chưa lưu...' : S.data?.approved ? 'đã duyệt' : 'đã lưu';
}

function issueText(i) {
  if (mode === 'simple') return issueSentence(i, { numberOf: (id) => allBeats().findIndex((b) => b.id === id) + 1 || null, assets: assets() });       // c4pages: a line by its number, a picture by its title
  const t = LBL.issue[i.code]; return typeof t === 'function' ? t(i) : t || (i.level === 'error' ? 'Có một lỗi trong chọn hình.' : 'Có một điều cần xem trong chọn hình.');
}
function checkDialog() {
  const iss = S.data.issues || [];
  const errs = iss.filter((i) => i.level === 'error'), warns = iss.filter((i) => i.level !== 'error');
  const row = (i) => h('li', { class: i.level, onclick: () => { if (i.beat && beatOf(i.beat)) { S.beat = i.beat; m.close(); if (mode === 'simple') rows?.select(i.beat, {}, { scroll: true }); else renderAll(); } } }, issueText(i));
  const m = modal({ title: 'Kiểm tra chọn hình', cls: 'wide v-pk',
    body: h('div', { class: 'body' },
      !iss.length ? h('p', { text: PW.issue.noneAtAll }) : null,
      errs.length ? h('div', null, h('h4', { text: `Lỗi (${errs.length}): phải sửa trước khi duyệt` }), h('ul', { class: 'pk-issues' }, errs.map(row))) : null,
      warns.length ? h('div', null, h('h4', { text: `Cảnh báo (${warns.length}): không chặn việc duyệt` }), h('ul', { class: 'pk-issues' }, warns.map(row))) : null),
    footer: h('footer', null, h('button', { text: 'Đóng', onclick: () => m.close() })) });
}
async function approve() {
  const d = S.data;
  if (!d.narration.approved) return toast(ERR.narration_not_approved, 'warn', 7000);
  const none = L.emptyBeats(chapters(), D).length;
  if (none && !(await confirmDialog(mode === 'simple' ? PW.confirmEmpty(none) : `${none} dòng chưa có hình. Bản nháp sẽ dùng tranh chính ở những dòng đó. Vẫn duyệt?`, { title: 'Duyệt chọn hình', ok: 'Duyệt' }))) return;
  await serverOp(() => api.post(`${P()}/approve`, { rev: R }), () => toast('Đã duyệt chọn hình.', 'ok'));
}

// ------------------------------------------------------------------ left: chapters and beats
function paintLeft() {
  const col = $('#pk-left'); if (!col) return;
  const top = col.scrollTop;
  col.replaceChildren(...chapters().map((c) => {
    const pr = L.chapterProgress(c, D);
    return h('div', { class: 'pk-chap' }, h('div', { class: 'pk-chaph' }, h('b', { text: c.title || c.id }), h('span', { class: 'count' + (pr.done === pr.total ? '' : ' warnc'), text: `${pr.done}/${pr.total}` })),
      c.beats.map((b) => {
        const n = L.countPicks(D, b.id), st = L.beatStatus(D, b.id);
        return h('button', { class: 'pk-beat' + (S.beat === b.id ? ' sel' : '') + (st === 'skip' ? ' skip' : ''), title: b.text, onclick: () => { S.beat = b.id; paintLeft(); paintMid(); paintRight(); fireSelect(); } },
          h('span', { class: 'bid', text: b.id }), h('span', { class: 'bt', text: b.text }),
          st === 'skip' ? h('span', { class: 'tag', text: 'bỏ qua' }) : h('span', { class: 'count' + (n ? '' : ' none'), text: String(n) }));
      }));
  }));
  col.scrollTop = top;
  queueRows();
}
/** c4pages: draw the rows of the simple page again, once per frame however many changes came. */
function queueRows() {
  if (!rows || rowsQueued) return;
  rowsQueued = true;
  requestAnimationFrame(() => { rowsQueued = false; if (rows && mode === 'simple') rows.paint(); });
}
/** c4pages: switch between the simple page and the hand tools. `beat`: the line the hand tools open on; `tab`: the tab of the right column. */
function setMode(m, beat = null, tab = null) {
  if (!root) return;
  mode = m; root.dataset.mode = m;
  if (m === 'hand') {
    if (beat && beatOf(beat)) S.beat = beat;
    if (tab) S.tab = tab;
    renderAll(); fireSelect();
    if (tab === 'books') loadBooks();
    $('#pk-mid')?.scrollTo?.(0, 0);
  } else { rows?.paint(); paintTop(); if (S.beat) rows?.select(S.beat, {}, { scroll: true }); else rows?.notify(); }       // the line the owner worked on in the hand tools is the one selected
}

// ------------------------------------------------------------------ middle: the beat and its tray
function paintMid() {
  const col = $('#pk-mid'); if (!col) return;
  const b = beatOf(S.beat);
  if (!b) return col.replaceChildren(h('div', { class: 'muted pad', text: 'Chưa có dòng lời dẫn nào. Hãy viết lời dẫn ở bước Kịch bản.' }));
  const rec = D.beats[b.id] || { items: [], status: 'todo', note: '' };
  const facts = S.data.narration.facts || {};
  const words = L.showWords(b.show, S.data.details);
  const main = mainAsset();
  const mainRegions = main ? Object.entries(main.regions || {}) : [];
  col.replaceChildren(...kids(
    h('div', { class: 'pk-beattext' }, h('span', { class: 'bid', text: b.id }), ' ', b.text),
    words.length ? h('div', { class: 'pk-show' }, h('span', { class: 'muted', text: 'Gợi ý hình: ' }), words.map((w) => h('button', { class: 'det' + (w.detail ? ' d' : ''), title: 'Tìm hình theo từ này', text: w.text, onclick: () => searchFor(w.query) }))) : null,
    b.facts.length ? h('details', { class: 'pk-facts' }, h('summary', { text: `Dữ kiện (${b.facts.length})` }), h('ul', null, b.facts.map((f) => h('li', { text: `${f}: ${facts[f] || ''}` })))) : null,
    h('h3', { class: 'sh', text: `Hình của dòng này (${rec.items.length})` }),
    rec.items.length ? h('div', { class: 'pk-tray' }, rec.items.map((it, i) => trayItem(b.id, it, i, rec.items.length)))
      : h('div', { class: 'muted pad', text: rec.status === 'skip' ? 'Dòng này được bỏ qua: không tính là thiếu hình.' : 'Chưa có hình. Bản nháp sẽ dùng tranh chính ở dòng này. Thêm hình từ cột bên phải hoặc từ các nút dưới đây.' }),
    autoWhy(b.id, rec),
    h('div', { class: 'pk-quick' },
      main ? h('button', { text: '+ Cả tranh chính', onclick: () => addTo(b.id, { asset: D.main_asset }) }) : null,
      mainRegions.map(([name, r]) => h('button', { text: `+ ${r.label || name}`, title: `Vùng ${name} của tranh chính`, onclick: () => addTo(b.id, { asset: D.main_asset, region: name }) })),
      main ? h('button', { text: 'Vẽ vùng mới...', onclick: () => regionEditor(D.main_asset) }) : null),
    h('div', { class: 'pk-beatfoot' },
      h('label', { class: 'cb' }, h('input', { type: 'checkbox', checked: rec.status === 'skip', onchange: () => { L.toggleSkip(D, b.id); touch(); paintLeft(); paintMid(); } }), ' Bỏ qua dòng này (không tính là thiếu hình)'),
      h('input', { type: 'text', class: 'grow', placeholder: 'Ghi chú cho dòng này (không bắt buộc)', value: rec.note || '', oninput: (e) => { L.ensureBeat(D, b.id).note = e.target.value; $('#pk-mid .pk-agentwhy')?.remove(); touch(); } }))));       // c3picks: a note of the owner's is no longer the agent's reason
}
/** c3picks: the reason the agent gave for a line, under its pictures, while the line is still as the agent wrote it. */
function autoWhy(beatId, rec) {
  const t = auto?.reasonFor(beatId, rec);
  return t ? h('div', { class: 'pk-agentwhy', title: PICKS_AUTO_LABELS.lineWhyTitle, text: PICKS_AUTO_LABELS.lineWhy(t) }) : null;
}
function trayItem(beatId, it, i, n) {
  const a = assets()[it.asset];
  const isVideo = a?.kind === 'video';
  const regions = a && !isVideo ? Object.keys(a.regions || {}) : [];
  const sel = (vals, cur, lab) => { const s = h('select'); for (const v of vals) s.append(h('option', { value: v, text: lab(v), selected: v === cur })); return s; };
  const reg = sel(['', ...regions], it.region || '', (v) => (v ? (a.regions[v].label ? `${v}: ${a.regions[v].label}` : v) : 'Cả bức ảnh'));
  reg.onchange = () => { L.setItem(D, beatId, i, { region: reg.value || null }); touch(); paintMid(); };
  const roleVals = isVideo ? L.VIDEO_ROLES : L.ROLES.filter((r) => r !== 'video');
  const role = sel(roleVals, it.role || (isVideo ? 'video' : 'detail'), (v) => LBL.role[v] || v);
  role.onchange = () => { L.setItem(D, beatId, i, { role: role.value }); touch(); };
  const bad = !a || (!isVideo && it.region && !(it.region in (a.regions || {})));
  const vTag = isVideo ? h('span', { class: 'pk-vbadge', text: a.duration ? `VIDEO · ${Number(a.duration).toFixed(1)}s` : 'VIDEO' }) : null;
  const mediaPreview = isVideo
    ? h('video', {
        class: 'pk-tray-video',
        src: api.fileUrl(S.pid, a.file),
        controls: true,
        muted: true,
        playsinline: true,
        preload: 'metadata',
        style: { width: '120px', maxHeight: '80px', borderRadius: '4px', background: '#000', objectFit: 'contain' },
      })
    : thumb(a, it.region, 64);
  return h('div', { class: 'pk-item' + (bad ? ' bad' : '') },
    mediaPreview,
    h('div', { class: 'pk-itembody' },
      h('div', { class: 'pk-itemtitle' }, vTag, a ? (a.title || it.asset) : `(hình ${it.asset} không còn)`, ' ', a ? flagBadge(credit(a).flag) : null),
      h('div', { class: 'pk-itemrow' }, a && !isVideo ? reg : null, role),
      h('input', { type: 'text', placeholder: 'Ghi chú', value: it.note || '', oninput: (e) => { L.setItem(D, beatId, i, { note: e.target.value }); touch(); } })),
    h('div', { class: 'pk-itembtns' },
      h('button', { class: 'small', text: '▲', title: 'Lên', disabled: i === 0, onclick: () => { L.moveItem(D, beatId, i, -1); touch(); paintMid(); } }),
      h('button', { class: 'small', text: '▼', title: 'Xuống', disabled: i === n - 1, onclick: () => { L.moveItem(D, beatId, i, 1); touch(); paintMid(); } }),
      h('button', { class: 'small danger', text: '✕', title: 'Bỏ hình này khỏi dòng', onclick: () => { L.removeItem(D, beatId, i); touch(); paintLeft(); paintMid(); } })));
}
function addTo(beatId, item) { L.addItem(D, beatId, item); touch(); paintLeft(); paintMid(); }

// ------------------------------------------------------------------ right: candidates
function paintRight() {
  const col = $('#pk-right'); if (!col) return;
  const tabs = h('div', { class: 'tabs' }, Object.entries(LBL.tabs).map(([k, t]) => h('button', { class: S.tab === k ? 'active' : '', text: t, onclick: () => { S.tab = k; paintRight(); if (k === 'books') loadBooks(); if (k === 'suggest') loadSuggestions(); } })));
  const body = h('div', { class: 'pk-tabbody' });
  col.replaceChildren(tabs, body);
  ({ main: tabMain, search: tabSearch, books: tabBooks, suggest: tabSuggest, video: tabVideo, upload: tabUpload })[S.tab](body);
}
/** Buttons of a candidate card: it becomes the main painting, or is added to the current beat. `imp` imports it and answers the state. */
function useButtons(imp, { mainOnly = false } = {}) {
  const beat = S.beat;
  const act = (asMain) => serverOp(() => imp(asMain), (r) => {
    if (!asMain && beat && r.asset_key) { L.addItem(D, beat, { asset: r.asset_key }); touch(); renderAll(); }
    if (asMain) { toast('Đã chọn tranh chính.', 'ok'); S.tab = 'search'; renderAll(); }
  });
  return h('div', { class: 'pk-cardbtns' },
    h('button', { class: mainOnly ? 'primary small' : 'small', text: 'Làm tranh chính', onclick: () => act(true) }),
    mainOnly ? null : h('button', { class: 'primary small', text: 'Thêm vào dòng', disabled: !beat, title: beat ? 'Thêm vào dòng đang chọn' : 'Chọn một dòng ở cột trái', onclick: () => act(false) }));
}
function candCard(c, opts) {
  const isVid = c.kind === 'video' || String(c.mime || '').startsWith('video/');
  const srcName = SOURCE_LABELS[c.source] || c.source;
  const beat = S.beat;
  const imp = (asMain) => api.post(`${P()}/import`, { source: c.source, source_id: c.source_id, as_main: asMain });
  const act = (asMain) => serverOp(() => imp(asMain), (r) => {
    if (!asMain && beat && r?.asset_key) {
      L.addItem(D, beat, { asset: r.asset_key, role: isVid ? 'video' : null });
      touch();
      renderAll();
    }
    if (asMain) {
      toast('Đã chọn tranh chính.', 'ok');
      S.tab = 'search';
      renderAll();
    }
  });

  const cardBtns = h('div', { class: 'pk-cardbtns' },
    !isVid ? h('button', { class: opts?.mainOnly ? 'primary small' : 'small', text: 'Làm tranh chính', onclick: () => act(true) }) : null,
    opts?.mainOnly ? null : h('button', {
      class: 'primary small',
      text: isVid ? 'Thêm video vào dòng' : 'Thêm vào dòng',
      disabled: !beat,
      title: beat ? 'Thêm vào dòng đang chọn' : 'Chọn một dòng ở cột trái',
      onclick: () => act(false),
    }));

  return h('div', { class: 'pk-card' },
    h('img', { src: c.thumb_url, loading: 'lazy', alt: '' }),
    h('div', { class: 'pk-cardbody' },
      h('div', { class: 'pk-cardtitle' },
        isVid ? h('span', { class: 'tag', text: 'Video' }, ' ') : null,
        c.title || c.source_id),
      h('div', { class: 'muted', text: [c.author, c.licence || 'chưa rõ giấy phép'].filter(Boolean).join(' · ') }),
      h('div', { class: 'muted' },
        c.width && c.height ? [L.sizeText(c.width, c.height), ' · '] : null,
        srcName,
        c.page_url ? [' · ', h('a', { class: 'lnk', href: c.page_url, target: '_blank', rel: 'noopener', text: 'trang nguồn' })] : null),
      flagBadge(c.flag),
      c.imported ? h('div', { class: 'tag', text: 'Đã có trong dự án' }) : null),
    cardBtns);
}
function searchForm(initial) {
  const q = h('input', { type: 'search', class: 'grow', placeholder: 'Từ khóa, ví dụ tên tranh và tác giả', value: S.q.text || initial || '' });
  const go = () => runSearch(q.value);
  q.onkeydown = (e) => { if (e.key === 'Enter') go(); };
  const srcInfo = (k) => S.data?.sources?.[k] || { available: true, has_key: true };
  const src = (k, defaultLabel) => {
    const info = srcInfo(k);
    const hasKey = info.has_key !== false;
    const label = hasKey ? (SOURCE_LABELS[k] || defaultLabel) : `${SOURCE_LABELS[k] || defaultLabel} (chưa có khóa)`;
    return h('label', { class: 'cb' + (!hasKey ? ' muted' : '') },
      h('input', {
        type: 'checkbox',
        checked: hasKey && !!S.q.sources[k],
        disabled: !hasKey,
        onchange: (e) => { S.q.sources[k] = e.target.checked; },
      }),
      ' ' + label);
  };
  return h('div', { class: 'pk-searchform' },
    h('div', { class: 'pk-row' }, q, h('button', { class: 'primary', text: 'Tìm', onclick: go, disabled: S.q.busy })),
    h('div', { class: 'pk-row pk-sources-row' },
      src('commons', 'Wikimedia Commons'),
      src('met', 'The Met'),
      src('pexels', 'Pexels'),
      src('pixabay', 'Pixabay'),
      src('osm', 'OpenStreetMap (Bản đồ)')));
}
function results(opts) {
  const r = S.q.res;
  if (S.q.busy) return h('div', { class: 'muted pad', text: 'Đang tìm...' });
  if (!r) return h('div', { class: 'muted pad', text: 'Chưa tìm gì. Gõ từ khóa rồi bấm Tìm.' });
  return h('div', null,
    (r.errors || []).map((e) => h('div', { class: 'pk-banner warn', text: `${SOURCE_LABELS[e.source] || e.source}: ${searchErrorText(e)}` })),
    r.items.length ? h('div', { class: 'pk-grid' }, r.items.map((c) => candCard(c, opts))) : h('div', { class: 'muted pad', text: `Không có kết quả cho "${r.query}".` }));
}
async function runSearch(text, beat = null) {
  const srcInfo = (k) => S.data?.sources?.[k] || { available: true, has_key: true };
  const sources = Object.keys(S.q.sources).filter((k) => S.q.sources[k] && srcInfo(k).has_key !== false);
  if (!sources.length) return toast('Chọn ít nhất một nguồn.', 'warn');
  S.q.text = text; S.q.busy = true; paintRight();
  try { S.q.res = await api.post(`${P()}/search`, { query: text, beat, sources, kind: 'all' }); S.q.text = S.q.res.query; }
  catch (e) { S.q.res = null; fail(e, 'Không tìm được: '); }
  S.q.busy = false; paintRight();
}
function searchFor(text) { S.tab = 'search'; S.q.text = text; runSearch(text); }
function tabMain(body) {
  const a = mainAsset();
  body.append(h('p', { class: 'muted', text: a ? 'Đổi tranh chính nếu cần. Các dòng đã dùng tranh cũ vẫn giữ nguyên hình đó.' : 'Tìm bức tranh chính của video theo tên và tác giả, hoặc lấy từ sách ở tab "Sách", hoặc tải lên.' }),
    searchForm(S.data.default_main_query), results({ mainOnly: true }));
}
function tabSearch(body) {
  const b = beatOf(S.beat);
  const row = h('div', { class: 'pk-row' }, b ? h('button', { class: 'small', text: 'Dùng chữ gợi ý của dòng này', onclick: () => runSearch('', S.beat) }) : null);
  body.append(searchForm(''), row, results({}));
}
async function loadBooks() {
  if (S.books) return;
  try { S.books = await api.get(`${P()}/book-images`); } catch (e) { S.books = { images: [], pages: [] }; fail(e, 'Không tải được ảnh sách: '); }
  paintRight();
}
function bookCard(x) {
  return h('div', { class: 'pk-card' }, h('img', { src: api.url(x.thumb_url), loading: 'lazy', alt: '' }),
    h('div', { class: 'pk-cardbody' }, h('div', { class: 'pk-cardtitle', text: x.label }), h('div', { class: 'muted', text: x.width ? L.sizeText(x.width, x.height) : 'trang đầy đủ' })),
    useButtons((asMain) => api.post(`${P()}/import-book-image`, { source_id: x.source_id, as_main: asMain })));
}
function tabBooks(body) {
  if (!S.books) return body.append(h('div', { class: 'muted pad', text: 'Đang tải...' }));
  const { images, pages } = S.books;
  body.append(h('p', { class: 'muted', text: 'Ảnh lấy từ sách của dự án. Giấy phép của ảnh trong sách không rõ nên được gắn cờ.' }),
    h('h3', { class: 'sh', text: `Ảnh trong sách (${images.length})` }),
    images.length ? h('div', { class: 'pk-grid' }, images.map(bookCard)) : h('div', { class: 'muted', text: 'Không có ảnh nhúng nào.' }),
    h('details', { class: 'pk-pages' }, h('summary', { text: `Cả trang sách (${pages.length})` }), h('div', { class: 'pk-grid' }, pages.map(bookCard))));
}
function tabUpload(body) {
  const f = (label, name, ph = '') => h('label', { class: 'lb' }, label, h('input', { type: 'text', name, placeholder: ph }));
  const mainCb = h('input', { type: 'checkbox', name: 'as_main' });
  const form = h('form', { class: 'pk-upload' },
    h('p', { class: 'muted', text: 'Ảnh (jpg, png, webp) hoặc video (mp4, mov, webm, m4v), tối đa 80 MB. Các ô dưới đây không bắt buộc; âm thanh gốc của video sẽ tự động tắt khi dựng.' }),
    h('input', { type: 'file', name: 'file', accept: '.jpg,.jpeg,.png,.webp,.mp4,.webm,.mov,.m4v', required: true }),
    f('Tên ảnh / video', 'title'), f('Tác giả', 'author'), f('Nguồn (đường dẫn)', 'source_url'), f('Giấy phép', 'licence', 'ví dụ CC BY 4.0, public domain'),
    h('label', { class: 'cb' }, mainCb, ' Đặt làm tranh chính (chỉ dùng cho ảnh)'),
    h('button', { class: 'primary', type: 'submit', text: 'Tải lên' }));
  form.onsubmit = (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    const fileObj = fd.get('file');
    if (!fileObj?.size) return toast('Chọn một tệp ảnh hoặc video.', 'warn');
    const isVid = /\.(mp4|webm|mov|m4v)$/i.test(fileObj.name || '');
    if (isVid && mainCb.checked) return toast(ERR.video_not_main, 'warn');
    fd.set('as_main', mainCb.checked ? '1' : '');
    const beat = S.beat, asMain = mainCb.checked;
    serverOp(() => api.post(`${P()}/upload`, fd), (r) => {
      if (!asMain && beat && r.asset_key) {
        L.addItem(D, beat, { asset: r.asset_key, role: r.asset?.kind === 'video' ? 'video' : null });
        touch(); renderAll();
      }
      toast(asMain ? 'Đã chọn tranh chính.' : (r.asset?.kind === 'video' ? 'Đã tải video lên.' : 'Đã tải ảnh lên.'), 'ok');
    });
  };
  body.append(form);
}

// ------------------------------------------------------------------ video (YouTube link or You.com search)
function fmtDur(s) {
  const t = Math.max(0, Math.round(Number(s || 0)));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`;
}
async function runVideoInspect(urlText) {
  const url = String(urlText || '').trim();
  if (!url) return toast('Dán link YouTube để xem.', 'warn');
  S.v.text = url; S.v.busy = true; paintRight();
  try {
    S.v.res = await api.post(`${P()}/video-search`, { url, query: '' });
  } catch (e) {
    S.v.res = null;
    if (e.body?.code === 'tool_missing' || e.code === 'tool_missing') {
      S.v.toolMissing = true;
      paintRight();
      return;
    }
    fail(e, 'Không đọc được video: ');
  } finally {
    S.v.busy = false;
    paintRight();
  }
}
async function runVideoSearchPaid(queryText, beat = null) {
  const q = String(queryText || '').trim();
  if (!q && !beat) return toast('Gõ từ khóa tìm kiếm trước.', 'warn');
  const ok = await confirmDialog('Tìm đoạn video trên YouTube qua You.com sẽ tốn tiền API. Bạn muốn tiếp tục?', { title: 'Tìm video qua You.com', ok: 'Tìm' });
  if (!ok) return;
  S.v.text = q; S.v.busy = true; paintRight();
  try {
    S.v.res = await api.post(`${P()}/video-search`, { query: q, beat, confirm_paid: true });
    if (S.v.res?.query) S.v.text = S.v.res.query;
  } catch (e) {
    S.v.res = null;
    if (e.body?.code === 'tool_missing' || e.code === 'tool_missing') {
      S.v.toolMissing = true;
      paintRight();
      return;
    }
    fail(e, 'Không tìm được video: ');
  } finally {
    S.v.busy = false;
    paintRight();
  }
}
function videoCard(v) {
  if (v.error || v.error_code) {
    const errText = ERR[v.error_code || v.error] || ERR.video_fetch_failed || 'Không đọc được thông tin video.';
    return h('div', { class: 'pk-vcard' },
      h('div', { class: 'pk-cardtitle' }, h('a', { class: 'lnk', href: v.url, target: '_blank', rel: 'noopener', text: v.title || v.url })),
      h('div', { class: 'muted', text: `Không đọc được thông tin video: ${errText}` }));
  }
  const first = (v.moments || [])[0] || { start: 0, end: Math.min(Number(v.duration || 10), 10) };
  const s0 = Number(first.start || 0), e0 = Math.max(s0 + 1, Number(first.end || s0 + 8));
  const iframe = v.embeddable !== false ? h('iframe', {
    class: 'pk-vframe',
    src: `https://www.youtube.com/embed/${encodeURIComponent(v.id)}?start=${Math.floor(s0)}&end=${Math.ceil(e0)}`,
    allow: 'autoplay; encrypted-media', allowfullscreen: true, referrerpolicy: 'strict-origin-when-cross-origin',
  }) : null;
  const player = iframe || h('a', { href: `${v.url}&t=${Math.floor(s0)}s`, target: '_blank', rel: 'noopener' },
    v.thumb_url ? h('img', { src: v.thumb_url, alt: '', style: { width: '100%', aspectRatio: '16/9', objectFit: 'cover', borderRadius: '4px' } }) : null,
    h('div', { class: 'muted', text: 'Video này tắt nhúng — bấm để mở trên YouTube ↗' }));
  const durMax = Math.max(1, Math.round(Number(v.duration || 120)));
  const startIn = h('input', { type: 'number', min: 0, max: durMax, step: 0.5, value: String(s0.toFixed(1)) });
  const endIn = h('input', { type: 'number', min: 0.5, max: durMax, step: 0.5, value: String(e0.toFixed(1)) });
  const startRange = h('input', { type: 'range', min: 0, max: durMax, step: 0.5, value: s0, class: 'pk-vslider' });
  const endRange = h('input', { type: 'range', min: 0, max: durMax, step: 0.5, value: e0, class: 'pk-vslider' });
  startRange.oninput = () => {
    let s = Number(startRange.value);
    const e = Number(endIn.value);
    if (s > e - 0.5) { s = Math.max(0, e - 0.5); startRange.value = s; }
    startIn.value = s.toFixed(1);
  };
  endRange.oninput = () => {
    const s = Number(startIn.value);
    let e = Number(endRange.value);
    if (e < s + 0.5) { e = Math.min(durMax, s + 0.5); endRange.value = e; }
    endIn.value = e.toFixed(1);
  };
  startIn.oninput = () => {
    const s = Number(startIn.value);
    if (Number.isFinite(s)) startRange.value = s;
  };
  endIn.oninput = () => {
    const e = Number(endIn.value);
    if (Number.isFinite(e)) endRange.value = e;
  };
  const noteIn = h('input', { type: 'text', class: 'grow', placeholder: 'Ghi chú (khớp với câu nào trong lời dẫn)' });
  const momentsEl = (v.moments || []).length ? h('div', { class: 'pk-vmoments' },
    h('div', { class: 'muted', text: 'Đoạn gợi ý:' }),
    v.moments.map((m) => h('div', { class: 'pk-vmoment' },
      h('button', { class: 'small', text: `▶ ${Number(m.start).toFixed(1)}–${Number(m.end).toFixed(1)}s`, onclick: () => {
        startIn.value = Number(m.start).toFixed(1);
        startRange.value = Number(m.start);
        endIn.value = Number(m.end).toFixed(1);
        endRange.value = Number(m.end);
        if (iframe) iframe.src = `https://www.youtube.com/embed/${encodeURIComponent(v.id)}?autoplay=1&start=${Math.floor(m.start)}&end=${Math.ceil(m.end)}`;
      } }),
      h('span', { class: 'muted', text: LBL.momentWhy(m.why) }))))
    : h('div', { class: 'muted', text: 'Không có mốc tự động — chỉnh giây bắt đầu/kết thúc bên dưới.' });
  const beat = S.beat;
  const isToolMissing = S.data?.video_tools?.available === false || S.v.toolMissing;
  const impDisabled = !beat || S.v.importing || isToolMissing;
  const impBtn = h('button', {
    class: 'primary small', text: S.v.importing ? 'Đang cắt...' : 'Cắt & thêm vào dòng',
    disabled: impDisabled,
    title: beat ? 'Tải đoạn này (tắt tiếng) và thêm vào dòng đang chọn' : 'Chọn một dòng ở cột trái',
    onclick: async () => {
      const a = Number(startIn.value), b = Number(endIn.value);
      if (!Number.isFinite(a) || !Number.isFinite(b) || a < 0 || b - a < 0.5 || b - a > 120) {
        return toast(ERR.video_bad_range, 'warn');
      }
      S.v.importing = true; paintRight();
      try {
        const r = await api.post(`${P()}/import-clip`, { url: v.url, start: a, end: b, title: v.title || '', beat_id: beat, role: 'video', note: noteIn.value.trim() });
        if (r?.job_id) {
          watch(r.job_id);
        }
      } catch (e) {
        S.v.importing = false;
        fail(e, 'Không cắt được video: ');
        paintRight();
      }
    },
  });
  const reasonSpan = !beat ? h('span', { class: 'muted pk-btn-reason', text: 'Chọn dòng ở cột trái để thêm' })
    : S.v.importing ? h('span', { class: 'muted pk-btn-reason', text: 'Đang cắt clip...' }) : null;
  const metaText = [v.channel, fmtDur(v.duration), v.height ? `${v.height}p` : '', v.vertical ? 'dọc' : '', v.match != null ? `khớp ${v.match}` : ''].filter(Boolean).join(' · ');
  return h('div', { class: 'pk-vcard' },
    h('div', { class: 'pk-vhead' },
      h('div', { class: 'pk-cardtitle' }, h('a', { class: 'lnk', href: v.url, target: '_blank', rel: 'noopener', text: v.title || v.url })),
      h('div', { class: 'muted', text: metaText }),
      flagBadge(v.flag)),
    player, momentsEl,
    h('div', { class: 'pk-vtrim' },
      h('div', { class: 'pk-vtrim-row' },
        h('label', null, 'Từ giây', startIn, startRange),
        h('label', null, 'Đến giây', endIn, endRange)),
      h('div', { class: 'pk-vtrim-action' },
        noteIn,
        h('div', { class: 'pk-vtrim-btnwrap' }, impBtn, reasonSpan))));
}
function tabVideo(body) {
  const b = beatOf(S.beat);
  const vtools = S.data?.video_tools;
  const isToolMissing = vtools?.available === false || S.v.toolMissing;
  const clipJob = S.job?.meta?.action === 'clip' ? S.job : null;
  const qIn = h('input', { type: 'search', class: 'grow', placeholder: 'Dán link YouTube (miễn phí) hoặc nhập từ khóa tìm đoạn video...', value: S.v.text || '', disabled: isToolMissing });
  const looksLikeUrl = (s) => /youtube\.com|youtu\.be/i.test(String(s || ''));
  qIn.onkeydown = (e) => {
    if (e.key === 'Enter') {
      if (looksLikeUrl(qIn.value)) runVideoInspect(qIn.value);
      else runVideoSearchPaid(qIn.value);
    }
  };
  const r = S.v.res;
  const list = S.v.busy ? h('div', { class: 'muted pad', text: 'Đang tìm thông tin video và gợi ý đoạn...' })
    : !r ? h('div', { class: 'muted pad', text: 'Dán link YouTube (miễn phí) hoặc tìm bằng You.com rồi cắt đoạn 0,5–120 giây.' })
      : r.items?.length ? h('div', { class: 'pk-vlist' }, r.items.map(videoCard))
        : h('div', { class: 'muted pad', text: 'Không tìm thấy video phù hợp.' });
  if (isToolMissing) {
    const code = vtools?.code || 'tool_missing';
    body.append(h('div', { class: 'pk-banner warn', text: ERR[code] || ERR.tool_missing }));
  }
  if (clipJob) {
    body.append(h('div', { class: 'pk-job' },
      h('div', { text: `Đang cắt đoạn video: ${Math.round((clipJob.progress || 0) * 100)}%` }),
      h('div', { class: 'muted', text: (clipJob.parts || []).filter((p) => p.state === 'running').map((p) => p.note || p.title).join(' · ') || 'Đang xử lý...' }),
      h('button', { class: 'small', text: 'Hủy', onclick: () => api.post(`/api/longjobs/${clipJob.id}/cancel`).catch((e) => fail(e)) })));
  }
  body.append(
    h('p', { class: 'muted', text: 'Dán link YouTube trực tiếp (miễn phí) hoặc tìm trên YouTube qua You.com (tốn tiền). Video cắt ra tự động tắt âm thanh gốc.' }),
    h('div', { class: 'pk-searchform' },
      h('div', { class: 'pk-row' }, qIn),
      h('div', { class: 'pk-row' },
        h('button', { text: 'Xem link (miễn phí)', disabled: S.v.busy || isToolMissing, onclick: () => runVideoInspect(qIn.value) }),
        h('button', { class: 'primary', text: 'Tìm trên YouTube (You.com, tốn tiền)', disabled: S.v.busy || isToolMissing, onclick: () => runVideoSearchPaid(qIn.value) }),
        b ? h('button', { class: 'small', text: 'Dùng chữ gợi ý của dòng này (tốn tiền)', disabled: S.v.busy || isToolMissing, onclick: () => runVideoSearchPaid('', S.beat) }) : null)),
    list);
}

// ------------------------------------------------------------------ suggestions (paid)
async function loadSuggestions() {
  try { S.sugg = await api.get(`${P()}/suggestions`); } catch { /* none yet */ }
  paintRight();
}
function tabSuggest(body) {
  const s = S.data.suggest || {};
  const j = S.job;
  body.append(h('p', { class: 'muted', text: 'Gợi ý thêm hỏi You.com xem nên cho xem hình gì ở mỗi dòng. Việc này tính tiền và chỉ chạy khi bạn bấm nút.' }));
  if (!s.available) body.append(h('div', { class: 'pk-banner warn', text: 'Gợi ý thêm đang tắt trong cấu hình (config/picks.json).' }));
  else body.append(h('div', { class: 'pk-row' },
    h('button', { class: 'primary', text: 'Gợi ý thêm cho dòng này (tốn tiền)', disabled: !S.beat || !!j, onclick: () => suggestFor([S.beat]) }),
    h('button', { text: 'Cho các dòng chưa có hình (tốn tiền)', disabled: !!j, onclick: () => suggestFor(L.emptyBeats(chapters(), D).slice(0, 40)) })));
  if (j && !['clip', 'auto'].includes(j.meta?.action)) body.append(h('div', { class: 'pk-job' }, h('div', { text: `Đang chạy: ${Math.round((j.progress || 0) * 100)}%` }), h('div', { class: 'muted', text: (j.parts || []).filter((p) => p.state === 'running').map((p) => `${p.title}: ${p.note || ''}`).join(' · ') }),
    h('button', { class: 'small', text: 'Hủy', onclick: () => api.post(`/api/longjobs/${j.id}/cancel`).catch((e) => fail(e)) })));
  const mine = S.sugg.beats?.[S.beat];
  if (mine) {
    body.append(h('h3', { class: 'sh', text: `Gợi ý cho ${S.beat}` }));
    if (!mine.items.length) body.append(h('div', { class: 'muted', text: 'You.com không đề xuất được gì cho dòng này.' }));
    for (const it of mine.items) body.append(h('div', { class: 'pk-sug' },
      h('div', null, h('b', { text: it.what }), ' ', h('span', { class: 'tag', text: it.kind })),
      h('div', { class: 'muted', text: it.why }),
      h('div', { class: 'pk-show' }, (it.search_terms || []).map((t) => h('button', { class: 'det', text: t, title: 'Tìm hình theo từ này', onclick: () => searchFor(t) }))),
      (it.candidates || []).length ? h('div', { class: 'pk-grid' }, it.candidates.map((c) => candCard(c))) : null));
  } else if (S.beat) body.append(h('div', { class: 'muted pad', text: 'Chưa có gợi ý cho dòng này.' }));
}
async function suggestFor(ids) {
  if (!ids.length) return toast('Không có dòng nào để gợi ý.', 'warn');
  const ok = await ask({ title: 'Gợi ý thêm tốn tiền', cancelValue: false,
    message: `Việc này gọi You.com cho ${ids.length} dòng và tính tiền cho mỗi dòng. Chỉ chạy khi bạn xác nhận ở đây.\n\nTiếp tục?`,
    buttons: [{ text: 'Hủy', value: false }, { text: `Chạy (${ids.length} dòng)`, value: true, cls: 'primary' }] });
  if (!ok) return;
  try { const r = await api.post(`${P()}/suggest`, { beats: ids, confirm_paid: true }); watch(r.job_id); }
  catch (e) { fail(e, 'Không chạy được: '); }
}
let seen = jobWatcher();
function watch(id) {
  seen.know(id);
  clearInterval(pollId);
  const tick = async () => {
    try {
      const j = await api.get(`/api/longjobs/${id}`);
      if (['queued', 'waiting', 'running'].includes(j.state)) {
        S.job = j;
        if (j.meta?.action === 'clip') S.v.importing = true;
        if (S.tab === 'suggest' || S.tab === 'video') paintRight();
        return;
      }
      clearInterval(pollId);
      const wasClip = S.job?.meta?.action === 'clip' || j.meta?.action === 'clip';
      S.job = null;
      S.v.importing = false;
      if (j.state === 'error') {
        toast(ERR[j.error_code] || jobErrorText(j).text, 'err', 9000);
      } else if (j.state === 'cancelled') {
        toast('Đã hủy.', 'warn');
      } else if (j.state === 'done') {
        if (wasClip) toast('Đã cắt đoạn video và thêm vào dòng.', 'ok');
      }
      try {
        applyData(await api.get(P()));
        renderAll();
      } catch { /* ignore */ }
      if (!wasClip) await loadSuggestions();
      pipeChanged();
      scope.timeout(pipeChanged, 1000);
    } catch (e) {
      clearInterval(pollId);
      S.job = null;
      S.v.importing = false;
      paintRight();
      fail(e);
    }
  };
  pollId = scope.interval(tick, 1000);
  tick();
}


// ------------------------------------------------------------------ regions editor
function regionEditor(key) {
  const a = assets()[key]; if (!a) return;
  const work = L.clone(a.regions || {});
  let draw = null;                                       // {x, y, rx, ry} being drawn
  const img = h('img', { class: 'pk-reg-img', src: imgUrl(a, 1400), alt: '' });
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg'); svg.setAttribute('class', 'pk-reg-svg');
  const list = h('div', { class: 'pk-reglist' });
  const nameIn = h('input', { type: 'text', list: 'pk-names', placeholder: 'Tên vùng (D1, D2... hoặc tự đặt)' });
  const labelIn = h('input', { type: 'text', placeholder: 'Nhãn hiển thị (không bắt buộc)' });
  const dl = h('datalist', { id: 'pk-names' });
  const hint = h('div', { class: 'muted', text: 'Kéo chuột trên ảnh: bấm vào tâm vùng rồi kéo ra tới mép vùng.' });
  let S2 = null;
  const spaces = () => { const r = img.getBoundingClientRect(); S2 = makeSpaces({ canvas: { w: a.width, h: a.height }, view: { W: r.width || 1, H: r.height || 1 } }); svg.setAttribute('viewBox', `0 0 ${r.width} ${r.height}`); return S2; };
  const ell = (rg, cls) => { const e = document.createElementNS(svgNS, 'ellipse'); const [k] = [S2.scale('canvas')]; const [cx, cy] = S2.canvasToScreen(rg.x, rg.y);
    e.setAttribute('cx', cx); e.setAttribute('cy', cy); e.setAttribute('rx', (rg.rx || 20) * k[0]); e.setAttribute('ry', (rg.ry || rg.rx || 20) * k[1]); e.setAttribute('class', cls); return e; };
  const paint = () => {
    S2 = spaces(); svg.replaceChildren();
    for (const [n, r] of Object.entries(work)) { svg.append(ell(r, 'reg')); const t = document.createElementNS(svgNS, 'text'); const [x, y] = S2.canvasToScreen(r.x, r.y); t.setAttribute('x', x + 4); t.setAttribute('y', y - 4); t.textContent = r.label || n; svg.append(t); }
    if (draw) svg.append(ell(draw, 'draw'));
    list.replaceChildren(...Object.entries(work).map(([n, r]) => h('div', { class: 'pk-regrow' }, h('b', { text: n }), h('span', { class: 'muted', text: r.label || '' }), h('button', { class: 'small danger', text: 'Xóa', onclick: () => { delete work[n]; paint(); } }))));
    dl.replaceChildren(...L.regionNameChoices(S.data.details, work).map((c) => h('option', { value: c.name, label: c.label })));
    addBtn.disabled = !draw;
  };
  const pt = (e) => { const r = svg.getBoundingClientRect(); return S2.screenToCanvas(e.clientX - r.left, e.clientY - r.top); };
  let start = null;
  svg.onpointerdown = (e) => { spaces(); start = pt(e); draw = L.circleFromDrag(start, start, a.width, a.height); svg.setPointerCapture(e.pointerId); paint(); };
  svg.onpointermove = (e) => { if (start) { draw = L.circleFromDrag(start, pt(e), a.width, a.height); paint(); } };
  svg.onpointerup = () => { start = null; };
  const addBtn = h('button', { class: 'primary', text: 'Thêm vùng này', disabled: true, onclick: () => {
    const want = nameIn.value.trim();
    if (want && !L.regionNameOk(want)) return toast(ERR.region_name, 'warn');
    const det = (S.data.details || []).find((d) => d.id === want);
    const n = L.freeRegionName(work, want || 'VUNG');
    work[n] = { ...draw, label: labelIn.value.trim() || det?.label || '' };
    draw = null; nameIn.value = ''; labelIn.value = ''; paint();
  } });
  img.onload = paint;
  const m = modal({ title: `Vùng trên "${a.title || key}"`, cls: 'wide v-pk pk-regmodal',
    body: h('div', { class: 'body pk-reg' }, h('div', { class: 'pk-reg-stage' }, img, svg),
      h('div', { class: 'pk-reg-side' }, hint, nameIn, dl, labelIn, addBtn, h('h4', { text: 'Các vùng' }), list)),
    footer: h('footer', null, h('button', { text: 'Hủy', onclick: () => m.close() }),
      h('button', { class: 'primary', text: 'Lưu các vùng', onclick: () => { m.close(); serverOp(() => api.put(`${P()}/assets/${encodeURIComponent(key)}/regions`, { regions: work, base_rev: R }), () => toast('Đã lưu các vùng.', 'ok')); } })) });
  scope.on(window, 'resize', paint);
}

// ------------------------------------------------------------------ whole page
const BAR = `<div id="pk-top" class="pk-top"></div>
<div id="pk-auto" class="pk-auto"></div>
<div id="pk-body" class="pk-body">
  <section class="pk-col pk-col-rows"><div id="pk-rows-col" class="pk-rows-col"></div></section>
  <section class="pk-col pk-col-hand"><div class="col-h"><h2>Dòng lời dẫn</h2></div><div id="pk-left" class="col-b"></div></section>
  <section class="pk-col pk-col-hand"><div class="col-h"><h2>Dòng này</h2></div><div id="pk-mid" class="col-b"></div></section>
  <section class="pk-col pk-col-hand"><div class="col-h"><h2>Tìm hình</h2></div><div id="pk-right" class="col-b"></div></section>
  <section class="pk-col pk-col-box"><div class="col-h"><h2>Sửa chọn hình bằng lời</h2></div><div id="pk-box" class="col-b pk-box"></div></section>
</div>`;
function renderAll() { paintTop(); paintLeft(); paintMid(); paintRight(); }

// ------------------------------------------------------------------ c2box: the prompt box of this step ("Sửa chọn hình bằng lời")
const selectListeners = new Set();
function fireSelect() { for (const fn of [...selectListeners]) { try { fn(S.beat); } catch { /* one listener never stops the others */ } } }
/** A turn of the box changed picks.json on the server (or undid its batch): take the saved picks in; what the owner has not saved yet is put back. */
async function takeInPicks() {
  if (dirty) await recover(); else await reload();
  pipeChanged();
}
const boxApi = {
  chapters: () => chapters(),
  currentBeat: () => S.beat,
  onSelect: (fn) => { selectListeners.add(fn); return () => selectListeners.delete(fn); },
  rev: () => R,
  isDirty: () => dirty,
  save: () => Q.run(saveNow).catch(() => null),
  openSearch: () => { S.tab = 'search'; paintRight(); $('#pk-right')?.scrollIntoView?.({ block: 'nearest' }); },
  agentStarted: () => auto?.follow?.(),                                          // join2: the card handed lines to the pictures agent: its bar shows that job at once
};

/** c4pages: what the rows of the simple page ask of this page (the data, the saving and the hand tools stay here). */
const rowsApi = {
  simple: () => mode === 'simple',
  projectTitle: () => shell?.pipeline?.title || '',
  data: () => S.data, doc: () => D, chapters: () => chapters(), starts: () => starts,
  reasonFor: (beatId, rec) => auto?.reasonFor(beatId, rec) || '',
  whyMissing: (beatId) => auto?.whyMissing?.(beatId) || '',
  thumb: (a, region, box) => thumb(a, region, box),
  videoUrl: (a) => api.fileUrl(S.pid, a.file),
  setCaption: (key, value) => serverOp(async () => {
    await api.post(`${P()}/ops`, { base_rev: R, actor: 'human', ops: [captionEditOp(key, value)] });
    return api.get(P());
  }),
  isDirty: () => dirty, busy: () => dirty || Q.busy === true,
  add: (beatId, item) => { const index = L.addItem(D, beatId, item); touch(); paintLeft(); paintMid(); return { beatId, index, asset: item.asset, region: item.region || null }; },
  /** Take back the picture "+" just added, when that line still has it at that place. */
  undoAdd: (t) => {
    const it = D.beats[t.beatId]?.items[t.index];
    if (!it || it.asset !== t.asset || (it.region || null) !== t.region) return false;
    L.removeItem(D, t.beatId, t.index); touch(); paintLeft(); paintMid();
    return true;
  },
  openHand: (beatId, tab = null) => setMode('hand', beatId, tab),
  setCurrent: (beatId) => { S.beat = beatId; },
  approve: () => approve(), check: () => checkDialog(), drawRegions: () => { if (D?.main_asset) regionEditor(D.main_asset); },
  get scriptHref() { return projectHash(S.pid, 'script'); },
};

export async function mount(host, ctx) {
  scope = ctx.scope; shell = ctx.shell;
  Object.assign(S, { pid: ctx.pipeline.project, data: null, beat: null, tab: 'main', books: null, sugg: { beats: {} }, job: null });
  S.q = { text: '', sources: { commons: true, met: true }, res: null, busy: false };
  S.v = { text: '', res: null, busy: false, importing: false };
  D = null; R = null; dirty = false; editVersion = 0; pollId = null; seen = jobWatcher();
  Q = createQueue({ onBusy: (b) => setStatus(b ? 'đang xử lý...' : '') });
  rows = null; starts = new Map(); rowsQueued = false;
  const q = new URLSearchParams(location.search);
  mode = q.get('mode') === 'hand' ? 'hand' : 'simple';                          // c4pages: the page opens on the rows; ?mode=hand opens the hand tools (links and probes)
  root = h('div', { class: 'pk-root v-pk' }); root.innerHTML = BAR; root.dataset.mode = mode; host.append(root);
  root.append(h('div', { class: 'view-msg pk-loading', id: 'pk-loading', text: PW.loading }));
  try { applyData(await api.get(P())); } catch (e) {
    root.replaceChildren(h('div', { class: 'view-msg pk-fail' }, failText(e), ' ', h('button', { class: 'small', id: 'pk-retry', text: PW.retry, onclick: () => shell.go(projectHash(S.pid, 'picks')) })));
    return {};
  }
  root.querySelector('#pk-loading')?.remove();
  S.tab = D.main_asset ? 'search' : 'main';
  rows = mountPickRows({ top: $('#pk-top'), col: $('#pk-rows-col'), scope, api: rowsApi });
  rows.selection.active = () => mode === 'simple';
  scope.on(document, 'keydown', (e) => {                                           // Escape closes the hand tools (a dialog or a field answers its own Escape first)
    if (e.key !== 'Escape' || mode !== 'hand' || e.defaultPrevented || document.querySelector('#modal-root .backdrop')) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    setMode('simple');
  });
  renderAll();
  rows.paint();
  api.get(`/api/projects/${S.pid}/voice`).then((v) => { starts = voiceStarts(v); queueRows(); }).catch(() => { /* no times: the rows say the line number only */ });
  auto = mountPicksAuto($('#pk-auto'), { pid: S.pid, scope, onInfo: queueRows,   // c3picks
    state: () => ({ doc: D, chapters: chapters(), approved: !!S.data?.approved, narrationOk: !!S.data?.narration?.approved, hasMain: !!mainAsset() }),
    reload, saveFirst: () => Q.run(saveNow).catch(() => {}) });
  selectListeners.clear();
  const boxHost = $('#pk-box');
  if (boxHost) mountPromptEdit(boxHost, { pid: S.pid, scope, kind: 'picks', takeIn: takeInPicks, onJobEnd: pipeChanged, picks: boxApi, sel: rows.selection, words: PW.box });
  try { const r = await api.get(`/api/projects/${S.pid}/longjobs?kind=picks`); const run = (r.items || r || []).find?.((j) => ['queued', 'waiting', 'running'].includes(j.state)); if (run) watch(run.id); } catch { /* the runner may not answer */ }
  loadSuggestions();
  // a suggestion job started in another tab shows up here within a few seconds
  watchIdle(scope, { root: () => root, idle: () => !S.job && !dirty,
    check: async () => {
      const r = await api.get(`/api/projects/${S.pid}/longjobs?kind=picks`);
      const what = seen(r);
      const run = what === 'active' ? (r.items || r || []).find?.((j) => ['queued', 'waiting', 'running'].includes(j.state)) : null;
      if (run) { watch(run.id); pipeChanged(); }
      else if (what === 'changed') { await loadSuggestions(); pipeChanged(); }               // a suggestion job ended elsewhere
    } });
  return {
    isDirty: () => dirty,
    save: () => Q.run(saveNow),
    dirtyMessage: () => 'Chọn hình có chỗ sửa chưa lưu.',
    pipelineChanged: () => {},
    unmount() { clearInterval(pollId); auto?.unmount(); auto = null; rows?.unmount(); rows = null; root = null; },
  };
}
