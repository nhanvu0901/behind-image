// "Dựng hình" step: the storyboard editing view. Mounted by the shell at #/project/<id>/edit.
// The modules next to it (preview, timeline, inspector, ...) are shared state of ONE editing session; mount() resets them
// and everything started here is registered on the view's scope, so leaving the view stops it all.
import { api, ApiError } from '../api.js';
import { MOCK, STYLE_ID } from '../config.js';
import { ctx, bus, setRegistry } from '../ctx.js';
import * as U from '../util.js';
import { h, toast, errorToast, modal, debounce, fmtTime, setStatus, ask, confirmDialog, detailFold } from '../util.js';
import { stripDerived } from '../logic.js';
import { mergeStoryboard, mergedNote } from '../sbmerge.js';
import { jobFailText } from '../errmsg.js';
import { EDIT_LABELS, IDENTITY_LABELS } from '../labels.js';
import { initPreview, requestFrame } from '../preview.js';
import { initTimeline, seek, ensureVisible, fitView, zoomToShowWords } from '../timeline.js';
import { initInspector, setTab } from '../inspector.js';
import { openGallery } from '../gallery.js';
import { openProposals } from '../proposals.js';
import { mountDraftPanel } from '../draftpanel.js';
import { mountPromptEdit } from '../promptedit.js';
import { mountIdentityPick } from '../identitypick.js';
import * as A from '../actions.js';
import { shotIndexAt, wordIndexAt, clone } from '../logic.js';
import * as E from '../edit.js';
import { resolveShortcut, factsOf } from '../shortcuts.js';
import { outsideIssues } from '../checks.js';
import { missingLabel } from '../slots.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';
import { mountSimple } from '../sbsimple.js';             // c4pages: the simple page (list of shots in words) over the same player, box and editor
import { EDIT_PAGE_LABELS as PAGE } from '../labels.js';

let root = null, scope = null, shell = null;
const $ = (s) => root.querySelector(s);
const st = ctx.store;
const msg = (t) => setStatus(t);
// c4pages: the page has two faces over the same player, request box and editor: "simple" (the list of shots in words, the default) and "hand" (the editor as it always was).
// The owner's last choice is remembered per project; a link that needs the editor (?select=, ?open=, ?t=, ?zoom=, ?source= or ?mode=hand) opens it there.
let mode = 'simple', simple = null, fitted = false;
const MODE_KEY = (pid) => `bti.edit.mode.${pid}`;
function initialMode(pid) {
  const q = new URLSearchParams(location.search);
  const forced = q.get('mode');
  if (forced === 'hand' || forced === 'simple') return forced;
  if (['select', 'open', 't', 'zoom', 'source'].some((k) => q.has(k))) return 'hand';
  try { return localStorage.getItem(MODE_KEY(pid)) === 'hand' ? 'hand' : 'simple'; } catch { return 'simple'; }
}
/** The request box sits beside the player in the editor; on the simple page it is the last of the three zones, so it comes after the list in the Tab order too. */
function placeBox(m) {
  const box = $('#prompt-edit-container'), main = $('#main');
  if (!box || !main) return;
  if (m === 'simple') main.insertBefore(box, $('#inspector')); else $('#preview-pane').append(box);
}
/** Switch between the simple page and the editor. The editor is drawn exactly as it was; the simple page repaints its list from the draft. */
function setMode(m, { persist = true } = {}) {
  if (!root || (m === mode && root.dataset.mode === m)) return;
  mode = m; root.dataset.mode = m; placeBox(m);
  if (persist) { try { localStorage.setItem(MODE_KEY(ctx.pid), m); } catch { /* the choice is simply not remembered */ } }
  if (m === 'simple') {
    for (const id of ['view-source', 'view-regions']) { const c = $('#' + id); if (c?.checked) { c.checked = false; c.dispatchEvent(new Event('change')); } }     // the simple page shows the picture as the video does
    if (ctx.pick || ctx.slotPick) { ctx.pick = null; ctx.slotPick = null; bus.emit('pick'); }
    simple?.paint();
  } else fitTimelineWhenShown();
  simple?.notify();                                                                                                      // the request box looks at the selection of the page or of the editor
  updateTop();
}
/** The timeline was hidden (zero width) while the simple page showed: whatever it fitted then is not a view. Fit it once it has a size (the resize observer runs after the frame). */
function fitTimelineWhenShown(n = 0) {
  const v = window.__tl;
  if (!v) return;
  if (v.W > 0) { if (!fitted || !Number.isFinite(v.view.t0) || !(v.view.pps > 0)) { fitted = true; fitView(); ensureVisible(ctx.t); } return; }
  if (n < 40) requestAnimationFrame(() => fitTimelineWhenShown(n + 1));
}
/** A link to a shot or a problem that needs the editor: the editor, with that shot (and overlay) selected and its tab open. */
function openInEditor({ shot = null, overlay = null } = {}) {
  setMode('hand');
  if (shot && st.shotById(shot)) { A.selectItem(shot, overlay || null); setTab(overlay ? 'overlay' : 'shot'); ensureVisible(ctx.t); }
}
const nextStep = () => { const nx = shell.pipeline && nextOpenable(shell.pipeline.steps, 'edit'); return nx ? { label: nx.label, go: () => shell.go(projectHash(ctx.pid, nx.id)) } : null; };
const HTML = `
  <div class="sbar" id="sbar"></div>
  <div class="vbar" id="ebar">
    <button id="btn-simple" title="${PAGE.hand.backHint}">${PAGE.hand.back}</button>
    <span class="sep"></span>
    <button id="btn-save" class="primary" title="Lưu (Ctrl+S)">Lưu<span id="dirty-dot" class="dot" hidden></span></button>
    <button id="btn-check" title="Kiểm tra storyboard">Kiểm tra <span id="issue-count" class="count">0</span></button>
    <span class="sep"></span>
    <button id="btn-undo" title="Hoàn tác (Ctrl+Z)">Hoàn tác</button>
    <button id="btn-redo" title="Làm lại (Ctrl+Shift+Z)">Làm lại</button>
    <span class="sep"></span>
    <button id="btn-draft" title="Dựng bản nháp storyboard từ giọng đọc và hình đã chọn">Bản nháp</button>
    <button id="btn-proposals" title="Đề xuất từ agent">Đề xuất <span id="prop-count" class="count" hidden>0</span></button>
    <button id="btn-approve" title="Duyệt storyboard đã lưu (cần lưu trước, không còn lỗi)">Duyệt</button>
    <span id="approve-state" class="badge" title="Trạng thái duyệt"></span>
    <button id="incomplete-state" class="badge warn-badge" title="Mục chưa đủ: bấm để xem danh sách" hidden></button>
    <button id="btn-clip" title="Dựng clip 10 giây từ vị trí đầu phát">Xem thử 10 giây</button>
    <span class="grow"></span>
    <button id="btn-next" class="primary" hidden></button>
  </div>
  <main id="main">
    <section id="preview-pane">
      <div id="preview-tools">
        <label class="chk"><input type="checkbox" id="view-source"> Ảnh gốc (xem toàn ảnh để kéo khung)</label>
        <label class="chk"><input type="checkbox" id="view-regions"> Hiện vùng (region)</label>
        <span class="muted" id="map-note"></span>
        <span class="grow"></span>
        <span id="identity-container"></span>
        <span class="muted" id="frame-state"></span>
      </div>
      <div id="stage"><div id="stage-box"><canvas id="frame"></canvas><svg id="handles"></svg></div></div>
      <div id="transport">
        <button id="t-prev" title="Shot trước ([)">&#9664;</button>
        <button id="t-play" title="Phát/Dừng (Space)">&#9654;</button>
        <button id="t-next" title="Shot sau (])">&#9654;&#9654;</button>
        <span id="t-time" class="mono">0:00.00</span>
        <span class="muted">/</span><span id="t-total" class="mono muted">0:00.00</span>
        <span class="sep"></span>
        <span class="muted">Từ:</span><span id="t-word" class="word-now">-</span>
        <span class="grow"></span>
        <span id="t-audio" class="muted" hidden>Không có âm thanh</span>
        <span id="t-shot" class="muted"></span>
      </div>
      <div id="prompt-edit-container"></div>
    </section>
    <section id="sel-panel"></section>
    <section id="shots-col" aria-label="${PAGE.listTitle}"><div class="empty muted">${PAGE.loading}</div></section>
    <aside id="inspector">
      <nav id="tabs">
        <button data-tab="shot" class="active">Shot</button>
        <button data-tab="overlay">Lớp phủ</button>
        <button data-tab="media">Hình</button>
        <button data-tab="issues">Lỗi <span id="tab-issues-n" class="count" hidden>0</span></button>
      </nav>
      <div id="tab-body"></div>
    </aside>
  </main>
  <section id="timeline-wrap">
    <div id="tl-bar">
      <button id="tl-split" title="Cắt tại đầu phát (S)">Cắt (S)</button>
      <button id="tl-merge" title="Gộp với shot trước">Gộp trước</button>
      <button id="tl-delete" title="Xóa shot (Delete)">Xóa</button>
      <button id="tl-lock" title="Khóa/mở khóa (L)">Khóa (L)</button>
      <span class="sep"></span>
      <button id="tl-zout" title="Thu nhỏ">-</button>
      <button id="tl-zin" title="Phóng to">+</button>
      <button id="tl-fit" title="Vừa toàn bộ">Vừa</button>
      <span class="muted" id="tl-hint">Alt khi kéo = đặt tự do (không bám từ) | Ctrl+cuộn = zoom | Shift+cuộn = kéo ngang</span>
      <span class="grow"></span>
      <span class="muted mono" id="tl-info"></span>
    </div>
    <div id="timeline"><canvas id="tl-canvas"></canvas></div>
  </section>`;

// ---------- mount
/** Step 5 of a project that has no storyboard yet (the usual case after steps 3 and 4): the draft panel instead of an empty editor.
 *  The proposal it makes is adopted as the first storyboard by "Áp dụng"; then the view is opened again as the editor. */
function mountFirstDraft(host, mctx) {
  const pid = mctx.pipeline.project, sc = mctx.scope, sh = mctx.shell;
  const box = h('div', { class: 'draft-first', style: { maxWidth: '760px', margin: '24px auto', padding: '0 16px' } });
  const slot = h('div');
  box.append(h('h1', { text: `${mctx.step.n}. ${mctx.step.label}` }),
    h('p', { class: 'muted', text: 'Dự án chưa có storyboard. Dựng một bản nháp từ giọng đọc và hình đã chọn: kết quả là một đề xuất, bạn xem rồi bấm "Áp dụng" để nó thành storyboard đầu tiên, sau đó sửa tiếp ở đây.' }),
    slot);
  host.append(box);
  const reopen = () => { sh.refreshPipeline(); sh.go(projectHash(pid, 'edit')); };
  mountDraftPanel(slot, { pid, scope: sc, onJobEnd: () => sh.refreshPipeline(), onProposal: (id) => { ctx.reset(); ctx.pid = pid; openProposals(reopen, id); } });
  return {};
}

export async function mount(host, mctx) {
  scope = mctx.scope; shell = mctx.shell;
  const pid = mctx.pipeline.project;
  if (mctx.pipeline.has_storyboard === false) return mountFirstDraft(host, mctx);
  root = h('div', { class: 'edit-root' });
  root.innerHTML = HTML;
  host.append(root);
  simple = null; fitted = false; mode = initialMode(pid); root.dataset.mode = mode; placeBox(mode);
  bus.clear(); ctx.reset();
  audio = new Audio(); audioOk = false; vStart = 0; vT0 = 0; raf = 0; saving = null; saveAgain = false; ctx.serverIssues = [];
  // the first listeners: derived state that every other module reads, and the rule "selecting moves the playhead into the item"
  st.on((kind) => { if (kind !== 'select') ctx.refreshIncomplete(); else A.alignPlayhead(); });
  bus.on('issues', () => ctx.refreshIncomplete());
  scope.add(() => {                                       // leaving the view: stop playback, audio, timers, subscribers
    ctx.playing = false; cancelAnimationFrame(raf);
    audio.pause(); audio.removeAttribute('src'); audio.load();
    validateSoon.cancel(); bus.clear(); ctx.reset();
    window.__bti = null; window.__tl = null;
  });
  wireTopbar(); wireKeys();
  scope.on(root, 'click', (e) => { const b = e.target.closest?.('button'); if (b && b.closest('#ebar, #tl-bar, #transport, #sbar')) b.blur(); });   // Space plays, it does not press the last button again
  scope.on($('#preview-tools'), 'change', (e) => e.target.blur?.());
  initPreview(root, scope); initTimeline(root, scope); initInspector(root);
  try { setRegistry(await api.style(STYLE_ID)); }
  catch (e) { errorToast(e, 'Không tải được danh sách kỹ thuật: ', 9000); return view; }
  await loadProject(pid);
  if (!st.draft && mode === 'simple') { mode = 'hand'; root.dataset.mode = 'hand'; placeBox('hand'); }      // the project did not load: its message is shown where the editor puts it
  $('#btn-simple').onclick = () => setMode('simple');
  if (st.draft) {                                                                       // c4pages: the simple page; its selection is what the request box reads while it is showing
    simple = mountSimple(root, { pid: ctx.pid, scope, shell, hooks: { approve, save, setMode, openInEditor, approving: () => approving, next: nextStep } });
    simple.selection.active = () => mode === 'simple';
  }
  const promptBox = $('#prompt-edit-container');
  if (promptBox) {
    mountPromptEdit(promptBox, { pid: ctx.pid, scope, takeIn: takeInTurn, onPreview: ({ t0, t1 }) => previewClip(t0, t1), sel: simple?.selection || null });
  }
  const identityBox = $('#identity-container');          // "Kiểu mở đầu và mốc chương": changes the saved storyboard on the server, then it is taken in like a turn of the prompt box
  if (identityBox) mountIdentityPick(identityBox, { pid: ctx.pid, scope, takeIn: () => takeInTurn(null, { ok: '', merged: IDENTITY_LABELS.tookInMerged, fail: IDENTITY_LABELS.tookInFail }) });
  applyUrlParams();
  window.__bti = { ctx, store: st, save, play, seek, audio, A, E, api, setMode, simple, get mode() { return mode; } };
  return view;
}
const view = {
  isDirty: () => st.dirty,
  save: async () => { await save(); return !st.dirty; },
  dirtyMessage: () => 'Storyboard có chỗ sửa chưa lưu.',
  pipelineChanged: () => { updateApprove(); if (mode === 'simple') simple?.paintBar(); },
};

async function loadProject(pid) {
  msg('đang mở dự án...');
  let p;
  try { p = await api.project(pid); } catch (e) {
    msg('');
    if (e.status === 409 && e.body && (e.body.corrupt || e.body.data_error)) { showDataError(pid, e.body); return; }
    errorToast(e, 'Không mở được dự án: ', 8000); return;
  }
  ctx.pid = pid; ctx.renderKey = p.render_key || null; pauseNow(); ctx.t = 0;
  st.load(p.storyboard, p.timing, p.rev);
  setIssues(p.issues || []);
  try { const as = await api.assets(pid); ctx.assetInfo = as || {}; } catch { ctx.assetInfo = {}; }
  setupAudio();
  st.select(st.draft.shots[0]?.id || null);
  fitView(); seek(0); updateTop(); msg('');
  normalizeIds();
  refreshProposalCount();
}

/** An unusable storyboard/timing file: say so in the view, and for a corrupt storyboard offer the newest good copy from history/. */
function showDataError(pid, body) {
  const main = $('#main');
  const kind = body.data_error === 'timing' ? 'tệp thời gian (timing)' : body.corrupt ? 'storyboard.json' : 'dữ liệu của dự án';
  const box = h('div', { class: 'banner warn', style: { margin: '16px', flexDirection: 'column', alignItems: 'flex-start' } },
    h('div', { text: `Không mở được ${kind}: tệp hỏng hoặc thiếu.` }), body.detail ? detailFold(body.detail) : null);
  if (body.corrupt) {
    box.append(h('div', { class: 'hint', title: body.restore_from || '', text: body.restore_from ? 'Có một bản sao gần nhất trong thư mục lịch sử của dự án.' : 'Dự án không có bản sao nào trong lịch sử.' }));
    if (body.restore_from) box.append(h('button', { class: 'primary', text: 'Khôi phục bản gần nhất', onclick: async (ev) => {
      ev.target.disabled = true;
      try { await api.post(`/api/projects/${encodeURIComponent(pid)}/storyboard/restore`, {}); toast('Đã khôi phục', 'ok'); box.remove(); await loadProject(pid); }
      catch (e) { errorToast(e, 'Không khôi phục được: ', 6000); ev.target.disabled = false; }
    } }));
  }
  main.prepend(box);
}

/** Ids must be unique (shots in the storyboard, overlays in their shot). A storyboard that comes in with duplicates (an old
 * merge, a proposal, an import) is repaired as an edit the user can undo and must save. */
function normalizeIds() {
  if (!E.dedupeIds(clone(st.draft)).length) return;
  let n = 0;
  st.commit('Sửa id trùng', (d) => { n = E.dedupeIds(d).length; });
  toast(`Đã cấp lại ${n} id trùng; cần lưu.`, 'warn', 5000);
}

/** The issue list: what the server says plus the checks only the page makes (points outside the picture). */
function setIssues(serverList) {
  ctx.serverIssues = serverList || [];
  let local = [];
  try { local = st.draft ? outsideIssues(st.draft, (id) => ctx.tech(id)).filter((i) => !ctx.serverIssues.some((x) => x.path === i.path)) : []; } catch { local = []; }
  ctx.issues = [...ctx.serverIssues, ...local];
  ctx.refreshIncomplete(); bus.emit('issues'); updateTop();
}

async function refreshProposalCount() {
  try { ctx.proposalsCount = (await api.proposals(ctx.pid)).length; } catch { ctx.proposalsCount = 0; }
  updateTop();
}

// ---------- topbar
function updateTop() {
  $('#dirty-dot').hidden = !st.dirty;
  $('#btn-undo').disabled = !st.canUndo; $('#btn-redo').disabled = !st.canRedo;
  const n = ctx.issues.length, errs = ctx.issues.filter((i) => i.level === 'error').length;
  const c = $('#issue-count'); c.textContent = n; c.className = 'count' + (errs ? ' err' : n ? ' warnc' : '');
  const pc = $('#prop-count'); pc.hidden = !ctx.proposalsCount; pc.textContent = ctx.proposalsCount;
  $('#t-total').textContent = fmtTime(ctx.duration());
  updateApprove();
  if (mode === 'simple') simple?.paintBar();
}
/** Ask the server to check the draft. The answer is used only if the draft has not changed since the question (a newer one is on its way). */
async function runValidate() {
  if (!ctx.pid || !st.draft) return null;
  const v = st.editVersion;
  try {
    const r = await api.validate(ctx.pid, ctx.draftPlain());
    if (st.editVersion !== v) { validateSoon(); return null; }
    setIssues(r.issues || []); return r;
  } catch { return null; /* keep the old list */ }
}
const validateSoon = debounce(runValidate, 700);

/** Items with an empty required slot or parameter, in timeline order: [{shotId, overlayId, label, names}] */
function incompleteItems() {
  const out = [];
  for (const s of st.draft?.shots || []) {
    const a = ctx.incompleteOf(s.id);
    if (a) out.push({ shotId: s.id, overlayId: null, label: `Shot ${s.id} (${s.technique})`, names: a });
    for (const o of s.overlays || []) { const b = ctx.incompleteOf(s.id, o.id); if (b) out.push({ shotId: s.id, overlayId: o.id, label: `Lớp phủ ${o.id} của ${s.id} (${o.technique})`, names: b }); }
  }
  return out;
}
/** Approval is refused while anything is incomplete: say which items, and take the owner to them. */
async function showIncomplete(items = incompleteItems(), opt = {}) {
  if (!items.length) return;
  const go = (it) => { A.selectItem(it.shotId, it.overlayId); setTab(it.overlayId ? 'overlay' : 'shot'); ensureVisible(ctx.t); };
  let dlg;
  const rows = items.map((it) => h('div', { class: 'list-item', onclick: () => { dlg.close(); go(it); } }, h('b', { text: it.label }), h('span', { class: 'grow', style: { flex: 1 } }), h('span', { class: 'chip partial', text: it.chip || missingLabel(it.names) })));
  const choice = ask({ title: opt.title || `Chưa duyệt được: ${items.length} mục chưa đủ`, cancelValue: 'close',
    message: opt.message || 'Storyboard vẫn lưu được, nhưng chỉ duyệt được khi mọi mục bắt buộc đã điền. Bấm một dòng để tới mục đó.',
    body: h('div', { class: 'list', style: { maxHeight: '45vh', overflow: 'auto', marginTop: '8px' } }, ...rows),
    buttons: [{ text: 'Đóng', value: 'close' }, { text: opt.firstText || 'Tới mục đầu tiên', value: 'first', cls: 'primary' }] });
  dlg = { close: () => document.querySelector('#modal-root .modal.ask header button')?.click() };
  if ((await choice) === 'first') go(items[0]);
}

/** The `undrawable` issues of a refused approval, as list items that lead to the shot (or overlay). */
function undrawableItems(issues) {
  const out = [];
  for (const i of issues || []) {
    if (i.code !== 'undrawable') continue;
    const p = E.parseIssuePath(i.path) || {};
    const shot = (i.shot && st.shotById(i.shot)) || st.draft.shots[p.shot];
    if (!shot) continue;
    const ov = p.overlay != null ? (shot.overlays || [])[p.overlay] : (i.overlay ? (shot.overlays || []).find((o) => o.id === i.overlay) : null);
    out.push({ shotId: shot.id, overlayId: ov?.id || null, label: ov ? `Lớp phủ ${ov.id} của ${shot.id} (${ov.technique})` : `Shot ${shot.id} (${shot.technique})`, chip: 'không vẽ được' });
  }
  return out;
}

function updateApprove() {
  if (!st.draft) return;
  const ap = st.draft.approvals?.storyboard || null;
  const errs = ctx.issues.filter((i) => i.level === 'error').length;
  const inc = incompleteItems();
  const cur = !!ap && ap.rev === st.rev && !st.dirty;
  const chip = $('#approve-state'), btn = $('#btn-approve');
  chip.textContent = cur ? 'Đã duyệt' : ap ? 'Duyệt cũ (đã sửa)' : 'Chưa duyệt';
  chip.className = 'badge ' + (cur ? 'ok' : ap ? 'stub' : '');
  chip.title = ap ? `Duyệt bản ${String(ap.rev).slice(0, 8)} lúc ${ap.approved_at || '?'}` : 'Storyboard chưa được duyệt';
  const ic = $('#incomplete-state');
  ic.hidden = !inc.length; ic.textContent = `${inc.length} mục chưa đủ`; ic.onclick = () => showIncomplete();
  // Duyệt stays clickable when only incomplete items stand in the way: the click explains which (a disabled button would not)
  btn.disabled = st.dirty || errs > 0 || (!!ap && ap.rev === st.rev) || approving;
  btn.textContent = approving ? 'Đang duyệt...' : 'Duyệt';
  btn.classList.toggle('busy', approving);
  btn.title = st.dirty ? 'Lưu trước khi duyệt' : errs ? 'Còn lỗi, chưa duyệt được' : inc.length ? `Còn ${inc.length} mục chưa đủ: bấm để xem` : cur ? 'Bản này đã được duyệt' : 'Duyệt storyboard đã lưu';
  // after an approval: "Tiếp tục" leads to the next step that can be opened
  const nx = shell.pipeline && nextOpenable(shell.pipeline.steps, 'edit'), bn = $('#btn-next');
  bn.hidden = !(cur && nx);
  if (nx) { bn.textContent = `Tiếp tục: ${nx.label}`; bn.title = nx.state === 'not_built' ? 'Bước kế tiếp chưa được xây dựng' : ''; bn.onclick = () => shell.go(projectHash(ctx.pid, nx.id)); }
}
let approving = false;
async function approve() {
  if (approving) return;                                   // a second click while the check runs does nothing
  if (st.dirty) { toast('Lưu trước khi duyệt.', 'warn'); return; }
  const inc = incompleteItems();
  if (inc.length) { if (mode === 'simple') simple.showProblems(); else await showIncomplete(inc); return; }
  approving = true; updateApprove(); msg('đang kiểm tra khi duyệt...');
  try {
    const r = await api.approve(ctx.pid, st.rev);
    st.setApprovals(r.approvals);                          // only the server-owned approvals: an edit made meanwhile stays unsaved
    toast('Đã duyệt bản ' + st.rev.slice(0, 8), 'ok', 2500);
    shell.refreshPipeline();
  } catch (e) {
    const issues = e.body?.issues || e.body?.detail?.issues;
    if (e.status === 409) toast('Bản trên server đã đổi, tải lại dự án rồi duyệt lại.', 'err', 6000);
    else if (e.status === 422 && mode === 'simple') {                  // c4pages: the problems in words, not the technical list
      if (issues) setIssues(issues);
      if (simple.list?.summary.problemShots || simple.list?.summary.general) simple.showProblems(); else toast(PAGE.top.cannotApprove, 'err', 6000);
    } else if (e.status === 422) {
      if (issues) setIssues(issues);
      const bad = undrawableItems(issues), inc2 = incompleteItems();
      if (bad.length) await showIncomplete(bad, { title: `Chưa duyệt được: ${bad.length} chỗ không vẽ được`, message: 'Khi thử vẽ lại, các shot dưới đây không dựng được hình với giá trị hiện tại. Sửa tham số của chúng (hoặc đổi kỹ thuật) rồi duyệt lại. Bấm một dòng để tới đó.', firstText: 'Tới chỗ đầu tiên' });
      else if (inc2.length) await showIncomplete(inc2);
      else { setTab('issues'); toast('Không duyệt được: storyboard còn lỗi. Xem tab Lỗi.', 'err', 6000); }
    } else errorToast(e, 'Duyệt thất bại: ');
  } finally { approving = false; msg(''); updateApprove(); if (mode === 'simple') simple?.paintBar(); }
}

function wireTopbar() {
  $('#btn-approve').onclick = approve;
  bus.on('audio-state', (ok) => { audioOk = ok && audioOk; $('#t-audio').hidden = ok; });
  $('#btn-save').onclick = save;
  $('#btn-check').onclick = async () => { await validateNow(); setTab('issues'); };
  $('#incomplete-state').onclick = () => showIncomplete();
  $('#btn-undo').onclick = () => st.undo(); $('#btn-redo').onclick = () => st.redo();
  $('#btn-proposals').onclick = () => openProposals(applied);
  $('#btn-draft').onclick = () => {
    const slot = h('div', { class: 'body', style: { width: 'min(640px, 92vw)', minHeight: '240px' } });
    let off = null;
    const dlg = modal({ title: 'Bản nháp storyboard', body: slot, onClose: () => off?.() });
    off = mountDraftPanel(slot, { pid: ctx.pid, scope, inDialog: true, onJobEnd: () => shell.refreshPipeline(), onProposal: (id) => { dlg.close(); openProposals(applied, id); } });
  };
  $('#btn-clip').onclick = () => previewClip();
  $('#t-prev').onclick = () => stepShot(-1); $('#t-next').onclick = () => stepShot(1);
  $('#t-play').onclick = () => togglePlay();
  $('#tl-split').onclick = () => A.splitAtPlayhead();
  $('#tl-merge').onclick = () => st.shot && A.mergePrev(st.shot.id);
  $('#tl-delete').onclick = () => st.shot && A.deleteShotAction(st.shot.id);
  $('#tl-lock').onclick = () => A.toggleLock();
  bus.on('proposals', updateTop);
  st.on((kind) => {
    updateTop(); updateTransport();
    if (kind === 'draft') validateSoon();
  });
  bus.on('time', () => { if (ctx.playing) resyncPlay(); followPlayhead(); updateTransport(); }); bus.on('tick', updateTransport);   // a seek while playing moves the audio too
}
async function validateNow() {
  const r = await runValidate();
  if (!r && st.draft) { await runValidate(); }
  toast(ctx.issues.length ? `${ctx.issues.length} vấn đề` : 'Không có vấn đề', ctx.issues.length ? 'warn' : 'ok');
}

/** A turn of "Sửa video bằng lời" changed the saved storyboard (applied, chosen, undone): the editor takes the new one in.
 *  No unsaved edits: reload and keep the selection and the playhead. Unsaved edits: the same rebase merge as with another tab (fresh undo history). */
async function takeInTurn(_turn, texts = null) {
  const T = { ok: EDIT_LABELS.tookIn, merged: EDIT_LABELS.tookInMerged, fail: EDIT_LABELS.tookInFail, ...(texts || {}) };      // `ok: ''`: no toast when nothing was unsaved (the caller says it itself)
  let theirs;
  try { theirs = await api.project(ctx.pid); } catch (e) { errorToast(e, T.fail); return; }
  if (!st.dirty) {
    const sel = st.sel.shot, ov = st.sel.overlay, t = ctx.t;
    st.load(theirs.storyboard, theirs.timing, theirs.rev);
    setIssues(theirs.issues || []);
    const keep = st.shotById(sel);
    st.select(keep ? sel : (st.draft.shots[0]?.id || null), keep && ov && (keep.overlays || []).some((o) => o.id === ov) ? ov : null);
    seek(t);
    refreshProposalCount(); updateTop(); shell.refreshPipeline();
    if (T.ok) toast(T.ok, 'ok', 3500);
    return;
  }
  const base = JSON.parse(st.savedSnap || '{}'), mine = JSON.parse(st.snap()), m = mergeStoryboard(base, mine, JSON.parse(snapOfBoard(theirs.storyboard)));
  let bad = m.status === 'conflict';
  if (!bad) {
    try { bad = ((await api.validate(ctx.pid, m.value)).issues || []).some((i) => i.level === 'error'); }
    catch (e) { errorToast(e, T.fail, 7000); return; }
  }
  if (bad) { await conflictDialog(theirs, 2); return; }
  st.rebase(m.value, theirs.storyboard, theirs.rev, undefined, { fresh: true });
  setIssues(theirs.issues || []); validateSoon(); shell.refreshPipeline();
  toast(T.merged, 'ok', 7000);
}

function applied(res) {
  st.load(res.storyboard, st.timing, res.rev);
  setIssues(res.issues || []); st.select(st.draft.shots.find((s) => s.id === st.sel.shot)?.id || st.draft.shots[0].id);
  normalizeIds();
  refreshProposalCount(); updateTop();
}

// ---------- save. The save flow never replaces what the user typed: see Store.beginSave / finishSave.
let saving = null, saveAgain = false;
/** One save at a time; a second request while one is in flight runs after it, and only if something is still unsaved. */
function save() {
  if (!st.draft) return Promise.resolve();
  if (saving) { saveAgain = true; return saving; }
  saving = (async () => {
    try { let ok; do { saveAgain = false; ok = await saveOnce(); } while (ok && saveAgain && st.dirty); }
    finally { saving = null; updateTop(); }
  })();
  return saving;
}
async function saveOnce(tries = 0) {
  const btn = $('#btn-save'); btn.disabled = true; msg('đang lưu...');
  const sent = st.beginSave();                               // exactly what is sent; edits from now on are not part of this save
  try {
    const r = await api.save(ctx.pid, sent.board, sent.rev);
    if (r.render_key) ctx.renderKey = r.render_key;
    const { edited } = st.finishSave(sent, r.storyboard, r.rev);
    setIssues(r.issues || []);
    if (edited) validateSoon();                              // the answer is about what was sent; the page changed since
    toast(edited ? 'Đã lưu (còn sửa đổi mới hơn chưa lưu)' : 'Đã lưu', 'ok', 1800);
    shell.refreshPipeline();
    return true;
  } catch (e) {
    if (e instanceof ApiError && e.status === 409 && !(e.body && e.body.data_error)) return await resolveConflict(tries);
    if (e instanceof ApiError && e.status === 422) {
      setIssues(e.body?.issues || e.body?.detail?.issues || []); setTab('issues');
      toast('Không lưu được: storyboard còn lỗi. Xem tab Lỗi.', 'err', 6000);
    } else errorToast(e, 'Lưu thất bại: ', 6000);
    return false;
  } finally { btn.disabled = false; msg(''); }
}

/** Someone else saved a newer storyboard. Take what only they changed, keep what only I changed; ask only when both changed the same thing. */
async function resolveConflict(tries) {
  let theirs;
  try { theirs = await api.project(ctx.pid); } catch (e) { errorToast(e, 'Không tải được bản trên máy chủ: ', 7000); return false; }
  const base = JSON.parse(st.savedSnap || '{}'), mine = JSON.parse(st.snap());
  const theirsDoc = JSON.parse(snapOfBoard(theirs.storyboard));
  const m = mergeStoryboard(base, mine, theirsDoc);
  if (m.status !== 'conflict' && tries < 2) {
    let bad = false;
    if (m.status === 'merged') {
      try { const v = await api.validate(ctx.pid, m.value); bad = (v.issues || []).some((i) => i.level === 'error'); }
      catch (e) { errorToast(e, 'Không kiểm tra được bản ghép: ', 7000); return false; }
    }
    if (!bad) {
      st.rebase(m.value, theirs.storyboard, theirs.rev, undefined, { fresh: true });
      if (m.status === 'merged') toast(mergedNote(m.fromTheirs) + ' Hoàn tác không quay lại trước lúc ghép.', 'ok', 7000);
      setIssues(theirs.issues || []); validateSoon();
      if (!st.dirty) return true;
      return await saveOnce(tries + 1);
    }
  }
  return await conflictDialog(theirs, tries);
}
const snapOfBoard = (b) => { const c = stripDerived(b); delete c.approvals; return JSON.stringify(c); };

/** Both sides changed the same thing: the owner chooses. Every choice leaves the tab able to save again. */
async function conflictDialog(theirs, tries) {
  const choice = await ask({ title: 'Có người sửa storyboard này ở nơi khác', cancelValue: 'later',
    message: 'Bản trên máy chủ đã đổi kể từ lúc bạn mở (tab khác hoặc đề xuất tự động vừa lưu), và có chỗ cả hai cùng sửa nên không tự ghép được.',
    body: h('div', { class: 'hint', style: { marginTop: '8px' }, text: '"Ghi đè" giữ bản của bạn (bản kia vẫn nằm trong lịch sử của dự án). "Lấy bản trên máy chủ" bỏ các sửa đổi chưa lưu của bạn. "Để sau" giữ nguyên bản nháp, chưa lưu.' }),
    buttons: [{ text: 'Để sau', value: 'later' }, { text: 'Lấy bản trên máy chủ', value: 'theirs' }, { text: 'Ghi đè bằng bản của tôi', value: 'mine', cls: 'primary' }] });
  if (choice === 'theirs') {
    if (await confirmDialog('Các sửa đổi chưa lưu của bạn sẽ bị bỏ, storyboard được tải lại từ máy chủ. Tiếp tục?', { title: 'Lấy bản trên máy chủ', ok: 'Bỏ bản của tôi', danger: true })) { await loadProject(ctx.pid); return true; }
    return await conflictDialog(theirs, tries);
  }
  if (choice === 'mine') {
    if (!(await confirmDialog('Bản của bạn sẽ thay bản trên máy chủ. Bản kia vẫn được giữ trong lịch sử của dự án. Tiếp tục?', { title: 'Ghi đè', ok: 'Ghi đè', danger: true }))) return await conflictDialog(theirs, tries);
    let latest;
    try { latest = await api.project(ctx.pid); } catch (e) { errorToast(e, 'Không tải được bản trên máy chủ: ', 7000); return false; }
    st.rebase(JSON.parse(st.snap()), latest.storyboard, latest.rev, 'Ghi đè bản trên máy chủ');
    return await saveOnce(2);
  }
  return false;                                              // "Để sau": the draft stays, the next save asks again
}

async function previewClip(from = null, to = null) {
  const t0 = from ?? ctx.t, t1 = to ?? Math.min(ctx.duration(), t0 + 10);
  const btn = $('#btn-clip'); btn.disabled = true;
  try {
    const { job_id } = await api.preview(ctx.pid, { t0, t1, width: 640, fps: 15, storyboard: ctx.draftPlain() });
    for (;;) {
      const j = await api.job(job_id);
      msg(`dựng clip: ${j.state} ${Math.round((j.progress || 0) * 100)}%`);
      if (j.state === 'done') {
        const video = h('video', { src: api.url(j.result_url), controls: true, autoplay: true, style: { maxWidth: '86vw', maxHeight: '70vh', background: '#000' } });
        modal({ title: `Xem thử ${fmtTime(t0)} - ${fmtTime(t1)}`, body: h('div', { class: 'body' }, video), onClose: () => video.pause() });
        if (MOCK) toast('Mock: clip minh họa là clip mẫu của kỹ thuật, không phải render thật', 'warn', 5000);
        break;
      }
      if (j.state === 'error') { const d = jobFailText(j); toast('Không dựng được clip: ' + d.text, 'err', 7000, d.detail); break; }
      await new Promise((r) => scope.timeout(r, 500));
    }
  } catch (e) { errorToast(e, 'Không dựng được clip: '); }
  finally { btn.disabled = false; msg(''); }
}

// ---------- transport and playback
let audio = null;
let audioOk = false, vStart = 0, vT0 = 0, raf = 0;
function setupAudio() {
  const u = st.draft?.audio ? api.audioUrl(ctx.pid) : '';      // no audio named in the storyboard: no request for it
  audioOk = !!u && !ctx.noAudio; audio.src = u ? api.url(u) : ''; audio.preload = 'auto';
  audio.onerror = () => { audioOk = false; };
}
/** Whoever moves the playhead (ruler, keys, a script), the selection follows it into the shot it lands in. */
function followPlayhead() {
  if (!st.draft) return;
  const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)];
  if (s && st.sel.shot !== s.id) st.select(s.id);
}
function updateTransport() {
  if (!st.draft) return;
  $('#t-time').textContent = fmtTime(ctx.t);
  const w = ctx.words(), i = wordIndexAt(w, ctx.t);
  $('#t-word').textContent = i >= 0 ? w[i].w : '-';
  const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)];
  $('#t-shot').textContent = s ? `${s.id} | ${s.technique} | ${(s._t1 - s._t0).toFixed(1)} s` : '';
  $('#t-play').innerHTML = ctx.playing ? '&#10074;&#10074;' : '&#9654;';
}
function stepShot(dir) {
  const shots = st.draft.shots; const i = shotIndexAt(shots, ctx.t + (dir < 0 ? -0.05 : 0));
  const n = Math.min(shots.length - 1, Math.max(0, i + dir));
  A.selectItem(shots[n].id); ensureVisible(shots[n]._t0);   // selecting puts the playhead in the shot
}
function togglePlay() { ctx.playing ? pauseNow() : play(); }
function play() {
  if (ctx.t >= ctx.duration() - 0.05) ctx.t = 0;
  ctx.playing = true; vStart = performance.now(); vT0 = ctx.t;
  if (audioOk) { audio.currentTime = ctx.t; audio.play().catch(() => { audioOk = false; vStart = performance.now(); vT0 = ctx.t; }); }
  const loop = () => {
    if (!ctx.playing) return;
    ctx.t = audioOk && !audio.paused ? audio.currentTime : vT0 + (performance.now() - vStart) / 1000;
    if (ctx.t >= ctx.duration()) { pauseNow(); ctx.t = ctx.duration(); }
    const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)];
    if (s && st.sel.shot !== s.id && !st.sel.overlay) st.select(s.id);
    bus.emit('tick'); raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop); updateTransport();
}
/** The playhead was moved by someone else (ruler, selection, keys) while playing: audio and clock follow it. */
function resyncPlay() {
  vStart = performance.now(); vT0 = ctx.t;
  if (audioOk) { try { audio.currentTime = ctx.t; } catch { /* not loaded yet */ } }
}
function pauseNow() { ctx.playing = false; cancelAnimationFrame(raf); audio.pause(); updateTransport(); if (st.draft) requestFrame(); }

/** The shell's own answer when it has one (util.modalOpen), else whatever sits in the dialog layer. */
const modalIsOpen = () => (typeof U.modalOpen === 'function' ? U.modalOpen() : false) || !!document.querySelector('#modal-root .backdrop');

// ---------- keyboard: shortcuts.js decides (dialogs, typing, focused controls, pick modes), this only runs the action
function wireKeys() {
  scope.on(document, 'keydown', (e) => {
    const act = resolveShortcut(factsOf(e, { modalOpen: modalIsOpen(), picking: !!ctx.pick, slotPicking: !!ctx.slotPick, hasDraft: !!st.draft }));
    if (!act) return;
    if (mode === 'simple' && ['split', 'lock', 'delete'].includes(act)) return;                    // c4pages: nothing is cut, locked or deleted from a page that shows no timeline
    if (act !== 'escape') e.preventDefault();
    switch (act) {
      case 'swallow': break;
      case 'save': save(); break;
      case 'undo': st.undo(); break;
      case 'redo': st.redo(); break;
      case 'play': togglePlay(); break;
      case 'split': A.splitAtPlayhead(); break;
      case 'lock': A.toggleLock(); break;
      case 'delete': if (st.overlay) A.removeOverlayAction(st.overlay.id, st.sel.shot); else if (st.shot) A.deleteShotAction(st.shot.id); break;
      case 'prev': stepShot(-1); break;
      case 'next': stepShot(1); break;
      case 'wordprev': case 'wordnext': {
        const back = act === 'wordprev';
        const w = ctx.words(), i = wordIndexAt(w, ctx.t + (back ? -0.001 : 0)), n = Math.max(0, Math.min(w.length - 1, i + (back ? (w[i] && w[i].s < ctx.t - 0.001 ? 0 : -1) : 1)));
        if (w[n]) { seek(w[n].s); ensureVisible(w[n].s); const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)]; if (s) st.select(s.id); }
        break;
      }
      case 'cancelpick': { const slot = ctx.slotPick; ctx.pick = null; ctx.slotPick = null; bus.emit('pick'); if (slot) bus.emit('tab', slot.overlayId ? 'overlay' : 'shot'); break; }
      case 'escape': ctx.pick = null; break;
    }
  });
}

// ---------- URL parameters (used for screenshots): ?open=gallery|media|proposals|issues|overlay&select=s0002&t=12&zoom=1
function applyUrlParams() {
  const q = new URLSearchParams(location.search);
  const sel = q.get('select');
  if (sel && st.shotById(sel)) {
    const ov = q.get('overlay');
    st.select(sel, ov || null);
    if (!q.get('t')) seek(st.shotById(sel)._t0 + 0.5);
  }
  if (q.get('t')) seek(parseFloat(q.get('t')));
  if (q.get('zoom')) { zoomToShowWords(); ensureVisible(ctx.t); }
  if (q.get('source') === '1') { $('#view-source').checked = true; $('#view-source').dispatchEvent(new Event('change')); }
  const open = q.get('open');
  if (open === 'gallery') $('#tab-body').querySelector('.tech-card')?.click();
  else if (open === 'gallery-all') openGallery({ title: 'Thư viện kỹ thuật (tất cả)', kinds: ['base', 'overlay', 'transition', 'card'], q: (q.get('gq') || '').toLowerCase() });
  else if (open === 'proposals') openProposals(applied, q.get('prop'));
  else if (open) setTab(open);
  if (open === 'media' && q.get('search')) scope.timeout(() => [...document.querySelectorAll('#tab-body button')].find((b) => b.textContent === 'Tìm')?.click(), 50);
  if (q.get('scroll')) scope.timeout(() => { const b = $('#tab-body'); b.scrollTop = b.scrollHeight; }, 900);
}

