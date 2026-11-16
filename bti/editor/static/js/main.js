import { api, ApiError } from './api.js';
import { MOCK, STYLE_ID, DEFAULT_PROJECT } from './config.js';
import { ctx, bus, setRegistry } from './ctx.js';
import { $, h, toast, modal, debounce, fmtTime } from './util.js';
import { initPreview, requestFrame } from './preview.js';
import { initTimeline, seek, ensureVisible, requestDraw, fitView, zoomToShowWords } from './timeline.js';
import { initInspector, setTab, currentTab, render as renderInspector } from './inspector.js';
import { openGallery } from './gallery.js';
import { openProposals } from './proposals.js';
import * as A from './actions.js';
import { shotIndexAt, wordIndexAt, stripDerived } from './logic.js';

const q = new URLSearchParams(location.search);
const st = ctx.store;
const msg = (t) => { $('#status-msg').textContent = t; };

// ---------- boot
async function boot() {
  document.title = (MOCK ? '[MOCK] ' : '') + document.title;
  wireTopbar(); wireKeys();
  initPreview(); initTimeline(); initInspector();
  await loadHealth();
  try { setRegistry(await api.style(STYLE_ID)); }
  catch (e) { toast('Không tải được registry kỹ thuật: ' + (e.status || e.message), 'err', 9000); return; }
  let projects = [];
  try { projects = await api.projects(); } catch (e) { toast('Không tải được danh sách dự án: ' + (e.status || e.message), 'err', 9000); }
  // hide lab_*, demo_* and projects without a storyboard (those live in the library), unless ?all=1
  if (!new URLSearchParams(location.search).has('all') && !MOCK) {
    const keep = projects.filter((p) => p.has_storyboard !== false && !/^(lab_|demo_)/.test(p.id) || p.id === DEFAULT_PROJECT);
    if (keep.length) projects = keep;
  }
  const pick = $('#project-pick');
  pick.replaceChildren(...projects.map((p) => h('option', { value: p.id, text: `${p.title || p.id} (${fmtTime(p.duration || 0).replace(/\.\d+$/, '')})` })));
  pick.onchange = () => switchProject(pick.value);
  const pid = DEFAULT_PROJECT && projects.find((p) => p.id === DEFAULT_PROJECT) ? DEFAULT_PROJECT : projects[0]?.id;
  if (!pid) { toast('Chưa có dự án nào.', 'warn'); return; }
  pick.value = pid;
  await loadProject(pid);
  applyUrlParams();
}

async function loadHealth() {
  const b = $('#health');
  try {
    const hl = await api.health(); ctx.health = hl;
    const stub = hl.engine === 'stub' || hl.media === 'stub';
    b.textContent = `engine: ${hl.engine} | media: ${hl.media}${MOCK ? ' | MOCK' : ''}`;
    b.className = 'badge ' + (stub ? 'stub' : 'ok');
    b.title = stub ? 'Đang chạy bản stub: khung hình/hình ảnh chưa phải thật' : 'Engine và media thật';
  } catch { b.textContent = 'backend không phản hồi'; b.className = 'badge bad'; }
}

async function switchProject(pid) {
  if (st.dirty && !confirm('Có thay đổi chưa lưu. Chuyển dự án sẽ bỏ chúng. Tiếp tục?')) { $('#project-pick').value = ctx.pid; return; }
  await loadProject(pid);
}

async function loadProject(pid) {
  msg('đang mở dự án...');
  let p;
  try { p = await api.project(pid); } catch (e) { toast('Không mở được dự án: ' + (e.status || e.message), 'err', 8000); msg(''); return; }
  ctx.pid = pid; pauseNow(); ctx.t = 0;
  st.load(p.storyboard, p.timing, p.rev);
  ctx.issues = p.issues || []; bus.emit('issues');
  try { const as = await api.assets(pid); ctx.assetInfo = as || {}; } catch { ctx.assetInfo = {}; }
  setupAudio();
  st.select(st.draft.shots[0]?.id || null);
  fitView(); seek(0); updateTop(); msg('');
  refreshProposalCount();
  history.replaceState(null, '', location.href);
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
}
const validateSoon = debounce(async () => {
  if (!ctx.pid || !st.draft) return;
  try { const r = await api.validate(ctx.pid, ctx.draftPlain()); ctx.issues = r.issues || []; bus.emit('issues'); updateTop(); } catch { /* keep the old list */ }
}, 700);

function updateApprove() {
  if (!st.draft) return;
  const ap = st.draft.approvals?.storyboard || null;
  const errs = ctx.issues.filter((i) => i.level === 'error').length;
  const cur = !!ap && ap.rev === st.rev && !st.dirty;
  const chip = $('#approve-state'), btn = $('#btn-approve');
  chip.textContent = cur ? 'Đã duyệt' : ap ? 'Duyệt cũ (đã sửa)' : 'Chưa duyệt';
  chip.className = 'badge ' + (cur ? 'ok' : ap ? 'stub' : '');
  chip.title = ap ? `Duyệt bản ${String(ap.rev).slice(0, 8)} lúc ${ap.approved_at || '?'}` : 'Storyboard chưa được duyệt';
  btn.disabled = st.dirty || errs > 0 || (!!ap && ap.rev === st.rev);
  btn.title = st.dirty ? 'Lưu trước khi duyệt' : errs ? 'Còn lỗi, chưa duyệt được' : cur ? 'Bản này đã được duyệt' : 'Duyệt storyboard đã lưu';
}
async function approve() {
  btn_approve_busy(true);
  try {
    const r = await api.approve(ctx.pid, st.rev);
    const d = stripDerived(st.draft); d.approvals = r.approvals;
    st.markSaved(d, st.rev);
    toast('Đã duyệt bản ' + st.rev.slice(0, 8), 'ok', 2500);
  } catch (e) {
    if (e.status === 409) toast('Bản trên server đã đổi, tải lại dự án rồi duyệt lại.', 'err', 6000);
    else if (e.status === 422) { ctx.issues = e.body?.issues || ctx.issues; bus.emit('issues'); setTab('issues'); toast('Không duyệt được: còn lỗi trong storyboard', 'err', 6000); }
    else toast('Duyệt thất bại: ' + (e.status || e.message), 'err');
  } finally { btn_approve_busy(false); updateApprove(); }
}
const btn_approve_busy = (b) => { $('#btn-approve').disabled = b; };

function wireTopbar() {
  $('#btn-approve').onclick = approve;
  bus.on('audio-state', (ok) => { audioOk = ok && audioOk; $('#t-audio').hidden = ok; });
  $('#btn-save').onclick = save;
  $('#btn-check').onclick = async () => { await validateNow(); setTab('issues'); };
  $('#btn-undo').onclick = () => st.undo(); $('#btn-redo').onclick = () => st.redo();
  $('#btn-proposals').onclick = () => openProposals(applied);
  $('#btn-clip').onclick = previewClip;
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
  bus.on('time', updateTransport); bus.on('tick', updateTransport);
  window.addEventListener('beforeunload', (e) => { if (st.dirty) { e.preventDefault(); e.returnValue = ''; } });
}
async function validateNow() {
  try { const r = await api.validate(ctx.pid, ctx.draftPlain()); ctx.issues = r.issues || []; bus.emit('issues'); updateTop(); toast(ctx.issues.length ? `${ctx.issues.length} vấn đề` : 'Không có vấn đề', ctx.issues.length ? 'warn' : 'ok'); }
  catch (e) { toast('Kiểm tra thất bại: ' + (e.status || e.message), 'err'); }
}

function applied(res) {
  st.load(res.storyboard, st.timing, res.rev);
  ctx.issues = res.issues || []; bus.emit('issues'); st.select(st.draft.shots.find((s) => s.id === st.sel.shot)?.id || st.draft.shots[0].id);
  refreshProposalCount(); updateTop();
}

async function save() {
  if (!st.draft) return;
  const btn = $('#btn-save'); btn.disabled = true; msg('đang lưu...');
  try {
    const r = await api.save(ctx.pid, ctx.draftPlain(), st.rev);
    st.markSaved(r.storyboard, r.rev); ctx.issues = r.issues || []; bus.emit('issues'); updateTop();
    toast('Đã lưu', 'ok', 1800);
  } catch (e) {
    if (e instanceof ApiError && e.status === 409) {
      const dlg = modal({ title: 'Xung đột phiên bản (409)', body: h('div', { class: 'body', style: { maxWidth: '460px' } }, h('p', { text: 'Storyboard trên server đã thay đổi kể từ khi bạn mở (có thể agent hoặc cửa sổ khác vừa lưu).' }), h('p', { class: 'muted', text: 'Tải lại sẽ bỏ các thay đổi chưa lưu của bạn. Hoặc giữ bản nháp, xuất ra xem rồi tải lại sau.' })),
        footer: h('footer', null, h('button', { text: 'Giữ bản nháp', onclick: () => dlg.close() }), h('button', { class: 'primary', text: 'Tải lại từ server', onclick: async () => { dlg.close(); await loadProject(ctx.pid); } })) });
    } else if (e instanceof ApiError && e.status === 422) {
      ctx.issues = e.body?.issues || e.body?.detail?.issues || []; bus.emit('issues'); updateTop(); setTab('issues');
      toast('Không lưu được: storyboard còn lỗi', 'err', 6000);
    } else toast('Lưu thất bại: ' + (e.status || '') + ' ' + e.message, 'err', 6000);
  } finally { btn.disabled = false; msg(''); }
}

async function previewClip() {
  const t0 = ctx.t, t1 = Math.min(ctx.duration(), t0 + 10);
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
      if (j.state === 'error') { toast('Dựng clip lỗi: ' + (j.error || ''), 'err', 7000); break; }
      await new Promise((r) => setTimeout(r, 500));
    }
  } catch (e) { toast('Không dựng được clip: ' + (e.status || e.message), 'err'); }
  finally { btn.disabled = false; msg(''); }
}

// ---------- transport and playback
const audio = new Audio();
let audioOk = false, vStart = 0, vT0 = 0, raf = 0;
function setupAudio() {
  const u = api.audioUrl(ctx.pid);
  audioOk = !!u && !ctx.noAudio; audio.src = u ? api.url(u) : ''; audio.preload = 'auto';
  audio.onerror = () => { audioOk = false; };
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
  st.select(shots[n].id); seek(shots[n]._t0 + 0.01); ensureVisible(shots[n]._t0);
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
function pauseNow() { ctx.playing = false; cancelAnimationFrame(raf); audio.pause(); updateTransport(); if (st.draft) requestFrame(); }

// ---------- keyboard
function wireKeys() {
  document.addEventListener('keydown', (e) => {
    const tag = (e.target.tagName || '').toLowerCase();
    const typing = ['input', 'textarea', 'select'].includes(tag) && !(e.target.type === 'checkbox' || e.target.type === 'range');
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return; }
    if (typing) return;
    if (mod && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? st.redo() : st.undo(); return; }
    if (mod && e.key.toLowerCase() === 'y') { e.preventDefault(); st.redo(); return; }
    if (mod || !st.draft) return;
    switch (e.key) {
      case ' ': e.preventDefault(); togglePlay(); break;
      case 's': case 'S': A.splitAtPlayhead(); break;
      case 'l': case 'L': A.toggleLock(); break;
      case 'Delete': case 'Backspace':
        if (st.overlay) A.removeOverlayAction(st.overlay.id); else if (st.shot) A.deleteShotAction(st.shot.id); break;
      case '[': stepShot(-1); break;
      case ']': stepShot(1); break;
      case 'ArrowLeft': case 'ArrowRight': {
        e.preventDefault();
        const w = ctx.words(), i = wordIndexAt(w, ctx.t + (e.key === 'ArrowLeft' ? -0.001 : 0)), n = Math.max(0, Math.min(w.length - 1, i + (e.key === 'ArrowLeft' ? (w[i] && w[i].s < ctx.t - 0.001 ? 0 : -1) : 1)));
        if (w[n]) { seek(w[n].s); ensureVisible(w[n].s); const s = st.draft.shots[shotIndexAt(st.draft.shots, ctx.t)]; if (s) st.select(s.id); }
        break;
      }
      case 'Escape': ctx.pick = null; break;
    }
  });
}

// ---------- URL parameters (used for screenshots): ?open=gallery|media|proposals|issues|overlay&select=s0002&t=12&zoom=1
function applyUrlParams() {
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
  if (open === 'media' && q.get('search')) setTimeout(() => [...document.querySelectorAll('#tab-body button')].find((b) => b.textContent === 'Tìm')?.click(), 50);
  if (q.get('scroll')) setTimeout(() => { const b = $('#tab-body'); b.scrollTop = b.scrollHeight; }, 900);
}

boot();
window.__bti = { ctx, store: st, save, play, seek, audio };
