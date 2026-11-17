// "Xuất video" step: what will be made, the long job with its parts, and the result (player, report card, description, files).
// Mounted by the shell at #/project/<id>/export. Words on screen are Vietnamese; errors go through errmsg.js (describeError);
// the entries below that errmsg.js and labels.js do not have yet are kept in the local tables EXPORT_ERRORS / EXPORT_LABELS
// until CORE merges them (docs/qa/BUILD_export.md, "Needs another agent").
import { api } from '../api.js';
import { describeError, isVietnamese, STAGE_CODES } from '../errmsg.js';
import { EXPORT_LABELS } from '../labels.js';
import { h, kids, toast, errorToast, errorInto, detailFold, confirmDialog } from '../util.js';
import { watchIdle, jobWatcher } from '../idlewatch.js';
import { projectHash } from '../router.js';

const POLL_MS = 2000;

// ------------------------------------------------------------------ local tables
export const EXPORT_ERRORS = { ...STAGE_CODES.longjob, ...STAGE_CODES.export };
export { EXPORT_LABELS };

export function errText(e) {
  const c = e?.body?.code;
  if (typeof c === 'string' && EXPORT_ERRORS[c]) return { text: EXPORT_ERRORS[c], detail: e.body.detail || '' };
  return describeError(e);
}

// ------------------------------------------------------------------ small helpers (pure, exported for tests)
export function fmtDuration(sec) {
  sec = Math.max(0, Math.round(Number(sec) || 0));
  const m = Math.floor(sec / 60), s = sec % 60;
  if (m >= 60) return `${Math.floor(m / 60)} giờ ${m % 60} phút`;
  return m ? `${m} phút${s ? ` ${s} giây` : ''}` : `${s} giây`;
}
export function fmtEstimate(sec) {
  sec = Number(sec) || 0;
  if (sec < 90) return 'dưới 2 phút';
  const m = Math.round(sec / 60);
  return m >= 90 ? `khoảng ${(m / 60).toFixed(1).replace('.', ',')} giờ` : `khoảng ${m} phút`;
}
export function fmtSize(n) {
  n = Number(n) || 0;
  return n >= 1073741824 ? (n / 1073741824).toFixed(2) + ' GB' : n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB';
}
export const isActive = (j) => !!j && ['queued', 'waiting', 'running'].includes(j.state);
export function jobMessage(job) {
  const code = job?.error_code, raw = String(job?.error || '');
  if (job?.state === 'cancelled') return 'Đã hủy. Những đoạn đã dựng xong được giữ lại; bấm "Xuất video" để làm tiếp.';
  if (job?.state === 'interrupted') return 'Việc xuất bị gián đoạn vì máy chủ khởi động lại. Bấm "Xuất video" để làm tiếp: những đoạn đã dựng xong được giữ lại.';
  if (code && EXPORT_ERRORS[code]) return EXPORT_ERRORS[code];
  return isVietnamese(raw) ? raw : 'Việc xuất video bị lỗi. Xem "chi tiết".';
}

// ------------------------------------------------------------------ view
let root = null, scope = null, shell = null, S = null, seen = jobWatcher();

function ensureCss() {
  if (document.querySelector('link[data-export-css]')) return;
  const l = h('link', { rel: 'stylesheet', href: new URL('../../css/export.css', import.meta.url).href });
  l.dataset.exportCss = '1';
  document.head.append(l);
}

const P = () => `/api/projects/${encodeURIComponent(S.pid)}`;
const $ = (s) => root?.querySelector(s);

async function load() {
  S.data = await api.get(`${P()}/export`);
  if (!S.job && isActive(S.data.job)) S.job = S.data.job;
  if (!S.job && !S.last) {
    // a failed or stopped run that left nothing behind: say what happened
    try {
      const list = await api.get(`${P()}/longjobs?kind=export`);
      const last = (Array.isArray(list) ? list : list?.items || list?.jobs || []).slice().sort((a, b) => (b.created || 0) - (a.created || 0))[0];
      S.last = last && ['error', 'cancelled', 'interrupted'].includes(last.state) && S.data.state !== 'done' ? last : null;
    } catch { S.last = null; }
  }
  paint();
  if (isActive(S.job)) startPolling();
}

function startPolling() {
  seen.know(S.job?.id);
  if (S.timer) return;
  S.timer = scope.interval(poll, POLL_MS);
  poll();
}
async function poll() {
  if (!S?.job || S.busyPoll) return;                  // the interval is registered once; with no job it does nothing
  S.busyPoll = true;
  try {
    const j = await api.get(`/api/longjobs/${encodeURIComponent(S.job.id)}`);
    if (isActive(j)) { S.job = j; paintJob(); return; }
    S.job = null;
    S.last = j.state === 'done' ? null : j;
    await load();
    shell?.refreshPipeline?.();
    scope.timeout(() => shell?.refreshPipeline?.(), 1000);       // once more a moment later: the stepper must not keep saying "Đang chạy"
    if (j.state === 'done') toast('Xuất video xong.', 'ok');
    else toast(jobMessage(j), j.state === 'error' ? 'err' : 'warn', 9000);
  } catch (e) {
    if (e?.status === 404) { S.job = null; await load().catch(() => {}); }
  } finally { if (S) S.busyPoll = false; }
}

async function start() {
  const btn = $('#ex-start');
  if (btn) btn.disabled = true;
  try {
    const r = await api.post(`${P()}/export/start`, {});
    S.last = null;
    S.job = r.job && r.job.id ? r.job : { id: r.job_id, state: 'queued', progress: 0, parts: [] };
    paint();
    startPolling();
    shell?.refreshPipeline?.();
  } catch (e) {
    toast(errText(e).text, 'err', 9000);
    if (btn) btn.disabled = false;
    if (e?.body?.code) await load().catch(() => {});
  }
}

async function cancel() {
  if (!S.job) return;
  const ok = await confirmDialog('Dừng việc xuất video? Những đoạn đã dựng xong được giữ lại, lần sau sẽ làm tiếp từ chỗ đó.', { title: 'Hủy xuất video', ok: 'Dừng lại', cancel: 'Tiếp tục xuất', danger: true });
  if (!ok) return;
  try { await api.post(`/api/longjobs/${encodeURIComponent(S.job.id)}/cancel`, {}); toast('Đang dừng...', 'warn'); poll(); } catch (e) { toast(errText(e).text, 'err', 9000); }
}

async function copyText(text, btn) {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else { const ta = h('textarea', { value: text, style: { position: 'fixed', opacity: 0 } }); document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove(); }
    btn.textContent = 'Đã chép';
    scope.timeout(() => { btn.textContent = 'Chép mô tả'; }, 2000);
  } catch { toast('Không chép được. Hãy bôi đen và chép tay.', 'warn'); }
}

// ------------------------------------------------------------------ painting
function paint() {
  if (!root) return;
  const d = S.data;
  root.replaceChildren(...kids(
    h('h1', { text: '6. Xuất video' }),
    h('div', { class: 'ex-sub muted', text: 'Dựng bản cuối từ storyboard đã duyệt và giọng đọc: video MP4 có phụ đề bên trong, tệp phụ đề riêng, mô tả và mục lục.' }),
    staleBox(d), blockedBox(d), lastErrorBox(), planBox(d), h('div', { id: 'ex-job' }), resultBox(d)));
  paintJob();
}

function staleBox(d) {
  if (d.state !== 'stale') return null;
  return h('div', { class: 'box warn ex-stale' }, h('b', { text: 'Cần xuất lại. ' }), EXPORT_LABELS.stale[d.reason] || d.detail || '', ' Bản cũ vẫn xem được bên dưới.');
}
function blockedBox(d) {
  if (!d.blocked || isActive(S.job)) return null;
  const c = d.blocked.code;
  const back = ['not_approved', 'approval_stale', 'no_storyboard', 'plan_failed', 'storyboard_unreadable'].includes(c) ? 'edit' : ['no_audio', 'no_timing'].includes(c) ? 'voice' : null;
  const step = (S.pipeline?.steps || []).find((s) => s.id === back);
  return h('div', { class: 'box warn ex-blocked' }, h('b', { text: 'Chưa xuất được. ' }), EXPORT_ERRORS[c] || 'Dự án chưa sẵn sàng để xuất.',
    back ? h('div', { style: { marginTop: '6px' } }, h('button', { text: back === 'edit' ? 'Mở bước Dựng hình' : 'Mở bước Giọng đọc', onclick: () => shell.go(projectHash(S.pid, back)), disabled: step?.state === 'locked' || null })) : null);
}
function lastErrorBox() {
  if (!S.last || isActive(S.job)) return null;
  const box = h('div', { class: `box ${S.last.state === 'error' ? 'err' : 'warn'} ex-last` }, h('b', { text: 'Lần xuất trước chưa xong. ' }), jobMessage(S.last));
  if (S.last.error && !isVietnamese(S.last.error)) box.append(detailFold(S.last.error));
  return box;
}
function planBox(d) {
  const p = d.plan, running = isActive(S.job);
  const rows = [];
  if (p) {
    rows.push(['Độ dài video', fmtDuration(p.duration)]);
    rows.push(['Chia thành', `${p.parts} đoạn dựng${p.parts_done ? ` (đã có sẵn ${p.parts_done})` : ''}`]);
    rows.push(['Thời gian dự kiến', p.parts_done === p.parts ? 'ngắn: chỉ ghép lại' : `${fmtEstimate(p.estimate_seconds)} (máy chủ dựng bằng bộ xử lý, khoảng 2 phút máy cho 1 phút video)`]);
    rows.push(['Hình có trong video', `${p.assets_used} hình, mỗi hình có dòng ghi nguồn trong mô tả`]);
  }
  return h('div', { class: 'box ex-plan' }, h('h4', { text: 'Sẽ làm ra' }),
    p ? h('table', { class: 'ex-kv' }, rows.map(([k, v]) => h('tr', null, h('th', { text: k }), h('td', { text: v })))) : h('div', { class: 'muted', text: 'Chưa có kế hoạch vì dự án chưa sẵn sàng.' }),
    p?.flagged?.length ? h('div', { class: 'hint warn', text: `Có ${p.flagged.length} hình chưa rõ giấy phép: mô tả video sẽ có ghi chú để bạn kiểm tra trước khi đăng. Việc xuất không bị chặn.` }) : null,
    h('div', { class: 'ex-acts' },
      h('button', { id: 'ex-start', class: 'primary', text: d.state === 'done' ? 'Xuất lại video' : 'Xuất video', disabled: running || !p || null, onclick: start }),
      running ? h('button', { id: 'ex-cancel', class: 'danger', text: 'Hủy', onclick: cancel }) : null,
      h('span', { class: 'hint', text: 'Việc này chạy nền: bạn có thể đóng trang, máy chủ vẫn làm tiếp.' })));
}

function paintJob() {
  const host = $('#ex-job');
  if (!host) return;
  const j = S.job;
  if (!j) { host.replaceChildren(); return; }
  const pct = Math.round((j.progress || 0) * 100);
  host.replaceChildren(h('div', { class: 'box ex-prog' },
    h('h4', { text: `Tiến độ: ${EXPORT_LABELS.job[j.state] || j.state}` }),
    h('div', { class: 'bar' }, h('i', { style: { width: pct + '%' } })), h('div', { class: 'muted', text: `${pct}%` }),
    h('ol', { class: 'ex-parts' }, (j.parts || []).map((p) => h('li', { class: 'st-' + p.state },
      h('span', { class: 'ttl', text: p.title }),
      h('span', { class: 'pst', text: EXPORT_LABELS.parts[p.state] || p.state }),
      p.state === 'running' ? h('span', { class: 'muted', text: ` ${Math.round((p.progress || 0) * 100)}%` }) : null,
      p.note ? h('span', { class: 'muted note', text: ' ' + (isVietnamese(p.note) ? p.note : '') }) : null)))));
}

function resultBox(d) {
  if (!d.manifest || !(d.state === 'done' || d.state === 'stale')) return null;
  const m = d.manifest, files = d.files || [], video = files.find((f) => f.key === 'video');
  const card = (m.report || []).map((it) => {
    const help = EXPORT_LABELS.reportHelp[it.key];
    const val = it.key === 'size' ? fmtSize(it.value) : it.value === null || it.value === undefined ? '—' : String(it.value);
    return h('tr', { class: 'rp-' + it.status },
      h('th', { text: EXPORT_LABELS.report[it.key] || it.key }), h('td', { class: 'mono', text: val }),
      h('td', { class: 'muted', text: help && it.expected !== null && it.expected !== undefined && it.status !== 'ok' ? `${help} (cần: ${it.expected})` : help || '' }),
      h('td', null, h('span', { class: 'badge ' + (it.status === 'ok' ? 'ok' : it.status === 'warn' ? 'warn' : 'bad'), text: EXPORT_LABELS.status[it.status] || it.status })));
  });
  const desc = d.description ?? '';
  const copyBtn = h('button', { text: 'Chép mô tả' });
  copyBtn.onclick = () => copyText(desc, copyBtn);
  return h('div', { class: 'ex-result' },
    h('div', { class: 'box' }, h('h4', { text: 'Video đã xuất' }),
      video ? h('video', { class: 'ex-video', controls: true, preload: 'metadata', src: api.url(video.url) }) : h('div', { class: 'muted', text: 'Không còn tệp video.' }),
      h('div', { class: 'muted', text: `${fmtDuration(m.duration)} · ${m.cues} dòng phụ đề · ${m.chapters} mục lục · xuất lúc ${String(m.created || '').replace('T', ' ').slice(0, 16)}` })),
    h('div', { class: 'box' }, h('h4', { text: 'Phiếu kiểm tra' }), h('table', { class: 'ex-card' }, card),
      (m.notes || []).length ? h('div', { class: 'hint warn', text: 'Có hình cần kiểm tra giấy phép trước khi đăng (xem ghi chú trong mô tả).' }) : null),
    h('div', { class: 'box' }, h('h4', { text: 'Mô tả video' }), h('textarea', { class: 'ex-desc', readOnly: true, rows: 14, value: desc }),
      h('div', { class: 'ex-acts' }, copyBtn)),
    h('div', { class: 'box' }, h('h4', { text: 'Tệp' }),
      h('div', { class: 'files' }, files.map((f) => h('div', { class: 'file' },
        h('span', { text: EXPORT_LABELS.files[f.key] || f.name }), h('code', { text: `projects/${S.pid}/export/${f.name}` }), h('span', { class: 'muted', text: fmtSize(f.size) }),
        h('a', { class: 'lnk', href: api.url(f.url), target: '_blank', rel: 'noopener', text: 'Mở' }),
        h('a', { class: 'lnk', href: api.url(f.url) + '?download=1', text: 'Tải về' }))))));
}

// ------------------------------------------------------------------ mount
export async function mount(host, ctx) {
  ensureCss();
  scope = ctx.scope; shell = ctx.shell;
  seen = jobWatcher();
  S = { pid: ctx.pipeline.project, pipeline: ctx.pipeline, data: null, job: null, last: null, timer: null, busyPoll: false };
  root = h('div', { class: 'infov v-exp', 'data-step': 'export' });
  host.append(root);
  try { await load(); } catch (e) { errorInto(root, e); }
  // an export started in another tab shows up here within a few seconds (one cheap GET: the list of export jobs)
  watchIdle(scope, { root: () => root, idle: () => !!S && !isActive(S.job),
    check: async () => {
      const list = await api.get(`${P()}/longjobs?kind=export`);
      const what = seen(list);
      if (!what || !S || isActive(S.job)) return;
      const act = (Array.isArray(list) ? list : list?.items || list?.jobs || []).find(isActive);
      if (act) { S.job = act; S.last = null; }
      await load(); shell?.refreshPipeline?.();                                                 // a job runs, or ran and ended, elsewhere
    } });
  return {
    pipelineChanged: () => { if (!isActive(S?.job)) load().catch(() => {}); },
    unmount() { root = null; S = null; },
  };
}
