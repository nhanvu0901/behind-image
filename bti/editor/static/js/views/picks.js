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
import { h, toast, errorToast, setStatus, modal, ask, confirmDialog, debounce } from '../util.js';
import { makeSpaces } from '../coords.js';
import { createQueue } from '../queue.js';
import { describeError, jobErrorText } from '../errmsg.js';
import { projectHash } from '../router.js';
import * as L from './picks_logic.js';

// ------------------------------------------------------------------ words
const LBL = {
  flag: { rejected: 'Giấy phép bị hạn chế', unknown: 'Chưa rõ giấy phép', small: 'Ảnh nhỏ' },
  flagHelp: {
    rejected: 'Giấy phép của ảnh này hạn chế việc dùng lại. Vẫn dùng được; hãy tự cân nhắc khi đăng video.',
    unknown: 'Chưa rõ giấy phép của ảnh này. Vẫn dùng được; mô tả video sẽ ghi nguồn.',
    small: 'Ảnh dưới 1200 px ở cạnh ngắn, có thể bị mờ khi phóng to. Vẫn dùng được.',
  },
  role: { main: 'Cả bức tranh', detail: 'Chi tiết', context: 'Bối cảnh', compare: 'So sánh', document: 'Tài liệu', map: 'Bản đồ', video: 'Video' },
  tabs: { main: 'Tranh chính', search: 'Tìm kiếm', books: 'Sách', suggest: 'Gợi ý', upload: 'Tải lên' },
  issue: {
    no_main: 'Chưa chọn tranh chính.', asset_file_missing: (i) => `Thiếu tệp ảnh của hình ${i.asset}.`,
    unknown_asset: (i) => `Dòng ${i.beat} dùng hình ${i.asset} không còn trong danh sách.`,
    unknown_region: (i) => `Dòng ${i.beat} dùng vùng "${i.region}" của hình ${i.asset}, vùng này không còn.`,
    beat_no_pick: (i) => `Dòng ${i.beat} chưa có hình: bản nháp sẽ dùng tranh chính ở đó.`,
    beat_unknown: (i) => `Có hình cho dòng ${i.beat} nhưng dòng này không còn trong lời dẫn.`,
    asset_flag: (i) => `Hình ${i.asset}: ${LBL.flag[i.flag] || i.flag}.`,
  },
  reason: { picks_edited: 'Chọn hình đã đổi sau khi duyệt.', narration_changed: 'Lời dẫn đã đổi sau khi duyệt hình.', narration_not_approved: 'Lời dẫn chưa được duyệt.' },
};
// error `code` of the picks routes -> sentence; anything else goes through errmsg.js
const ERR = {
  stale: 'Chọn hình đã đổi ở nơi khác (tab khác hoặc tác vụ nền). Đang tải lại bản mới nhất.',
  source_unreachable: 'Nguồn ảnh đang bận hoặc không trả lời. Thử lại sau vài giây.',
  source_error: 'Nguồn ảnh báo lỗi. Thử lại hoặc chọn nguồn khác.',
  not_found: 'Không tìm thấy ảnh này ở nguồn.',
  unknown_source: 'Nguồn ảnh này không có trong danh sách.',
  query_required: 'Gõ từ khóa để tìm.',
  narration_not_approved: 'Lời dẫn chưa được duyệt (hoặc đã đổi sau khi duyệt). Duyệt lời dẫn ở bước Kịch bản trước.',
  picks_have_errors: 'Chọn hình còn lỗi nên chưa duyệt được. Bấm "Kiểm tra" để xem.',
  image_empty: 'Tệp ảnh trống.', image_unreadable: 'Tệp này không phải ảnh đọc được.', image_truncated: 'Tệp ảnh bị cắt dở, không đọc hết được. Tải lại tệp đầy đủ.',
  region_name: 'Tên vùng không hợp lệ (chữ, số, dấu cách, - hoặc _; tối đa 40 ký tự).', region_shape: 'Vùng không hợp lệ.', region_outside: 'Tâm vùng nằm ngoài bức ảnh.',
  confirm_required: 'Cần bạn xác nhận chi phí trước khi chạy.', suggest_off: 'Gợi ý thêm đang tắt trong cấu hình.', suggest_no_key: 'Chưa có khóa You.com trên máy chủ.',
  suggest_failed: 'You.com không trả lời được. Thử lại sau.', busy: 'Đang có một lượt gợi ý chạy cho dự án này.', too_many: 'Chọn tối đa 40 dòng một lần.',
  longjob_missing: 'Bộ chạy việc dài chưa có trên máy chủ.',
};
const failText = (e) => ERR[e?.body?.code] || describeError(e).text;
const fail = (e, prefix = '') => { const t = ERR[e?.body?.code]; if (t) toast(prefix + t, 'err', 8000); else errorToast(e, prefix); };

// ------------------------------------------------------------------ state
let root = null, scope = null, shell = null;
const $ = (s) => root?.querySelector(s);
const S = { pid: null, data: null, beat: null, tab: 'main', q: { text: '', sources: { commons: true, met: true }, res: null, busy: false, for: '' },
  books: null, sugg: { beats: {} }, job: null };
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
  const a = mainAsset(), d = S.data, errs = (d.issues || []).filter((i) => i.level === 'error');
  const nv = d.narration;
  top.replaceChildren(
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
      : d.approval_reason ? h('div', { class: 'pk-banner warn', text: 'Đã duyệt trước đó nhưng cần duyệt lại. ' + (LBL.reason[d.approval_reason] || '') }) : null);
  paintStatus();
}
function paintStatus() {
  const el = $('#pk-state'); if (!el) return;
  el.textContent = dirty ? 'chưa lưu...' : S.data?.approved ? 'đã duyệt' : 'đã lưu';
}

function issueText(i) { const t = LBL.issue[i.code]; return typeof t === 'function' ? t(i) : t || (i.level === 'error' ? 'Có một lỗi trong chọn hình.' : 'Có một điều cần xem trong chọn hình.'); }
function checkDialog() {
  const iss = S.data.issues || [];
  const errs = iss.filter((i) => i.level === 'error'), warns = iss.filter((i) => i.level !== 'error');
  const row = (i) => h('li', { class: i.level, onclick: () => { if (i.beat && beatOf(i.beat)) { S.beat = i.beat; m.close(); renderAll(); } } }, issueText(i));
  const m = modal({ title: 'Kiểm tra chọn hình', cls: 'wide v-pk',
    body: h('div', { class: 'body' },
      !iss.length ? h('p', { text: 'Không có gì cần xem. Có thể duyệt.' }) : null,
      errs.length ? h('div', null, h('h4', { text: `Lỗi (${errs.length}): phải sửa trước khi duyệt` }), h('ul', { class: 'pk-issues' }, errs.map(row))) : null,
      warns.length ? h('div', null, h('h4', { text: `Cảnh báo (${warns.length}): không chặn việc duyệt` }), h('ul', { class: 'pk-issues' }, warns.map(row))) : null),
    footer: h('footer', null, h('button', { text: 'Đóng', onclick: () => m.close() })) });
}
async function approve() {
  const d = S.data;
  if (!d.narration.approved) return toast(ERR.narration_not_approved, 'warn', 7000);
  const none = L.emptyBeats(chapters(), D).length;
  if (none && !(await confirmDialog(`${none} dòng chưa có hình. Bản nháp sẽ dùng tranh chính ở những dòng đó. Vẫn duyệt?`, { title: 'Duyệt chọn hình', ok: 'Duyệt' }))) return;
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
        return h('button', { class: 'pk-beat' + (S.beat === b.id ? ' sel' : '') + (st === 'skip' ? ' skip' : ''), title: b.text, onclick: () => { S.beat = b.id; paintLeft(); paintMid(); paintRight(); } },
          h('span', { class: 'bid', text: b.id }), h('span', { class: 'bt', text: b.text }),
          st === 'skip' ? h('span', { class: 'tag', text: 'bỏ qua' }) : h('span', { class: 'count' + (n ? '' : ' none'), text: String(n) }));
      }));
  }));
  col.scrollTop = top;
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
  col.replaceChildren(
    h('div', { class: 'pk-beattext' }, h('span', { class: 'bid', text: b.id }), ' ', b.text),
    words.length ? h('div', { class: 'pk-show' }, h('span', { class: 'muted', text: 'Gợi ý hình: ' }), words.map((w) => h('button', { class: 'det' + (w.detail ? ' d' : ''), title: 'Tìm hình theo từ này', text: w.text, onclick: () => searchFor(w.query) }))) : null,
    b.facts.length ? h('details', { class: 'pk-facts' }, h('summary', { text: `Dữ kiện (${b.facts.length})` }), h('ul', null, b.facts.map((f) => h('li', { text: `${f}: ${facts[f] || ''}` })))) : null,
    h('h3', { class: 'sh', text: `Hình của dòng này (${rec.items.length})` }),
    rec.items.length ? h('div', { class: 'pk-tray' }, rec.items.map((it, i) => trayItem(b.id, it, i, rec.items.length)))
      : h('div', { class: 'muted pad', text: rec.status === 'skip' ? 'Dòng này được bỏ qua: không tính là thiếu hình.' : 'Chưa có hình. Bản nháp sẽ dùng tranh chính ở dòng này. Thêm hình từ cột bên phải hoặc từ các nút dưới đây.' }),
    h('div', { class: 'pk-quick' },
      main ? h('button', { text: '+ Cả tranh chính', onclick: () => addTo(b.id, { asset: D.main_asset }) }) : null,
      mainRegions.map(([name, r]) => h('button', { text: `+ ${r.label || name}`, title: `Vùng ${name} của tranh chính`, onclick: () => addTo(b.id, { asset: D.main_asset, region: name }) })),
      main ? h('button', { text: 'Vẽ vùng mới...', onclick: () => regionEditor(D.main_asset) }) : null),
    h('div', { class: 'pk-beatfoot' },
      h('label', { class: 'cb' }, h('input', { type: 'checkbox', checked: rec.status === 'skip', onchange: () => { L.toggleSkip(D, b.id); touch(); paintLeft(); paintMid(); } }), ' Bỏ qua dòng này (không tính là thiếu hình)'),
      h('input', { type: 'text', class: 'grow', placeholder: 'Ghi chú cho dòng này (không bắt buộc)', value: rec.note || '', oninput: (e) => { L.ensureBeat(D, b.id).note = e.target.value; touch(); } })));
}
function trayItem(beatId, it, i, n) {
  const a = assets()[it.asset];
  const regions = a ? Object.keys(a.regions || {}) : [];
  const sel = (vals, cur, lab) => { const s = h('select'); for (const v of vals) s.append(h('option', { value: v, text: lab(v), selected: v === cur })); return s; };
  const reg = sel(['', ...regions], it.region || '', (v) => (v ? (a.regions[v].label ? `${v}: ${a.regions[v].label}` : v) : 'Cả bức ảnh'));
  reg.onchange = () => { L.setItem(D, beatId, i, { region: reg.value || null }); touch(); paintMid(); };
  const role = sel(L.ROLES, it.role, (v) => LBL.role[v]);
  role.onchange = () => { L.setItem(D, beatId, i, { role: role.value }); touch(); };
  const bad = !a || (it.region && !(it.region in (a.regions || {})));
  return h('div', { class: 'pk-item' + (bad ? ' bad' : '') },
    thumb(a, it.region, 64),
    h('div', { class: 'pk-itembody' },
      h('div', { class: 'pk-itemtitle' }, a ? (a.title || it.asset) : `(hình ${it.asset} không còn)`, ' ', a ? flagBadge(credit(a).flag) : null),
      h('div', { class: 'pk-itemrow' }, a ? reg : null, role),
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
  ({ main: tabMain, search: tabSearch, books: tabBooks, suggest: tabSuggest, upload: tabUpload })[S.tab](body);
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
  return h('div', { class: 'pk-card' },
    h('img', { src: c.thumb_url, loading: 'lazy', alt: '' }),
    h('div', { class: 'pk-cardbody' },
      h('div', { class: 'pk-cardtitle', text: c.title || c.source_id, title: c.title }),
      h('div', { class: 'muted', text: [c.author, c.licence || 'chưa rõ giấy phép'].filter(Boolean).join(' · ') }),
      h('div', { class: 'muted' }, L.sizeText(c.width, c.height), ' · ', c.source === 'met' ? 'The Met' : 'Wikimedia Commons', c.page_url ? [' · ', h('a', { class: 'lnk', href: c.page_url, target: '_blank', rel: 'noopener', text: 'trang nguồn' })] : null),
      flagBadge(c.flag),
      c.imported ? h('div', { class: 'tag', text: 'Đã có trong dự án' }) : null),
    useButtons((asMain) => api.post(`${P()}/import`, { source: c.source, source_id: c.source_id, as_main: asMain }), opts));
}
function searchForm(initial) {
  const q = h('input', { type: 'search', class: 'grow', placeholder: 'Từ khóa, ví dụ tên tranh và tác giả', value: S.q.text || initial || '' });
  const go = () => runSearch(q.value);
  q.onkeydown = (e) => { if (e.key === 'Enter') go(); };
  const src = (k, t) => h('label', { class: 'cb' }, h('input', { type: 'checkbox', checked: S.q.sources[k], onchange: (e) => { S.q.sources[k] = e.target.checked; } }), ' ' + t);
  return h('div', { class: 'pk-searchform' }, h('div', { class: 'pk-row' }, q, h('button', { class: 'primary', text: 'Tìm', onclick: go, disabled: S.q.busy })), h('div', { class: 'pk-row' }, src('commons', 'Wikimedia Commons'), src('met', 'The Met')));
}
function results(opts) {
  const r = S.q.res;
  if (S.q.busy) return h('div', { class: 'muted pad', text: 'Đang tìm...' });
  if (!r) return h('div', { class: 'muted pad', text: 'Chưa tìm gì. Gõ từ khóa rồi bấm Tìm.' });
  return h('div', null,
    (r.errors || []).map((e) => h('div', { class: 'pk-banner warn', text: `${e.source === 'met' ? 'The Met' : 'Wikimedia Commons'}: ${ERR[e.code] || 'không tìm được.'}` })),
    r.items.length ? h('div', { class: 'pk-grid' }, r.items.map((c) => candCard(c, opts))) : h('div', { class: 'muted pad', text: `Không có kết quả cho "${r.query}".` }));
}
async function runSearch(text, beat = null) {
  const sources = Object.keys(S.q.sources).filter((k) => S.q.sources[k]);
  if (!sources.length) return toast('Chọn ít nhất một nguồn.', 'warn');
  S.q.text = text; S.q.busy = true; paintRight();
  try { S.q.res = await api.post(`${P()}/search`, { query: text, beat, sources }); S.q.text = S.q.res.query; }
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
  const form = h('form', { class: 'pk-upload' },
    h('p', { class: 'muted', text: 'Ảnh của bạn (jpg, png, webp, tối đa 80 MB). Các ô dưới đây không bắt buộc; để trống giấy phép thì ảnh được gắn cờ "Chưa rõ giấy phép".' }),
    h('input', { type: 'file', name: 'file', accept: '.jpg,.jpeg,.png,.webp', required: true }),
    f('Tên ảnh', 'title'), f('Tác giả', 'author'), f('Nguồn (đường dẫn)', 'source_url'), f('Giấy phép', 'licence', 'ví dụ CC BY 4.0, public domain'),
    h('label', { class: 'cb' }, h('input', { type: 'checkbox', name: 'as_main' }), ' Đặt làm tranh chính'),
    h('button', { class: 'primary', type: 'submit', text: 'Tải lên' }));
  form.onsubmit = (ev) => {
    ev.preventDefault();
    const fd = new FormData(form);
    if (!fd.get('file')?.size) return toast('Chọn một tệp ảnh.', 'warn');
    fd.set('as_main', form.elements.as_main.checked ? '1' : '');
    const beat = S.beat, asMain = form.elements.as_main.checked;
    serverOp(() => api.post(`${P()}/upload`, fd), (r) => {
      if (!asMain && beat && r.asset_key) { L.addItem(D, beat, { asset: r.asset_key }); touch(); renderAll(); }
      toast(asMain ? 'Đã chọn tranh chính.' : 'Đã tải ảnh lên.', 'ok');
    });
  };
  body.append(form);
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
  if (j) body.append(h('div', { class: 'pk-job' }, h('div', { text: `Đang chạy: ${Math.round((j.progress || 0) * 100)}%` }), h('div', { class: 'muted', text: (j.parts || []).filter((p) => p.state === 'running').map((p) => `${p.title}: ${p.note || ''}`).join(' · ') }),
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
function watch(id) {
  clearInterval(pollId);
  const tick = async () => {
    try {
      const j = await api.get(`/api/longjobs/${id}`);
      if (['queued', 'waiting', 'running'].includes(j.state)) { S.job = j; if (S.tab === 'suggest') paintRight(); return; }
      clearInterval(pollId); S.job = null;
      if (j.state === 'error') toast(ERR[j.error_code] || jobErrorText(j), 'err', 9000);
      else if (j.state === 'cancelled') toast('Đã hủy.', 'warn');
      await loadSuggestions(); pipeChanged();
    } catch (e) { clearInterval(pollId); S.job = null; fail(e); }
  };
  pollId = scope.interval(tick, 2000); tick();
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
<div id="pk-body" class="pk-body">
  <section class="pk-col"><div class="col-h"><h2>Dòng lời dẫn</h2></div><div id="pk-left" class="col-b"></div></section>
  <section class="pk-col"><div class="col-h"><h2>Dòng này</h2></div><div id="pk-mid" class="col-b"></div></section>
  <section class="pk-col"><div class="col-h"><h2>Tìm hình</h2></div><div id="pk-right" class="col-b"></div></section>
</div>`;
function renderAll() { paintTop(); paintLeft(); paintMid(); paintRight(); }

export async function mount(host, ctx) {
  scope = ctx.scope; shell = ctx.shell;
  Object.assign(S, { pid: ctx.pipeline.project, data: null, beat: null, tab: 'main', books: null, sugg: { beats: {} }, job: null });
  S.q = { text: '', sources: { commons: true, met: true }, res: null, busy: false };
  D = null; R = null; dirty = false; editVersion = 0; pollId = null;
  Q = createQueue({ onBusy: (b) => setStatus(b ? 'đang xử lý...' : '') });
  root = h('div', { class: 'pk-root v-pk' }); root.innerHTML = BAR; host.append(root);
  try { applyData(await api.get(P())); } catch (e) { root.replaceChildren(h('div', { class: 'view-msg', text: failText(e) })); return {}; }
  S.tab = D.main_asset ? 'search' : 'main';
  renderAll();
  try { const r = await api.get(`/api/projects/${S.pid}/longjobs?kind=picks`); const run = (r.items || r || []).find?.((j) => ['queued', 'waiting', 'running'].includes(j.state)); if (run) watch(run.id); } catch { /* the runner may not answer */ }
  loadSuggestions();
  return {
    isDirty: () => dirty,
    save: () => Q.run(saveNow),
    dirtyMessage: () => 'Chọn hình có chỗ sửa chưa lưu.',
    pipelineChanged: () => {},
    unmount() { clearInterval(pollId); root = null; },
  };
}
