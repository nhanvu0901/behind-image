// "Giọng đọc" step (step 3): approved narration -> audio/mix.m4a + timing.json. Mounted by the shell at #/project/<id>/voice.
// Everything the owner reads is Vietnamese. Words come from labels.js (VOICE_LABELS) and the sentences of error codes from errmsg.js (STAGE_CODES).
import { api } from '../api.js';
import { h, kids, toast, errorToast, confirmDialog, setStatus } from '../util.js';
import { createQueue } from '../queue.js';
import { errorText, jobErrorText, STAGE_CODES } from '../errmsg.js';
import { VOICE_LABELS } from '../labels.js';
import { nextOpenable } from '../stepper.js';
import { projectHash } from '../router.js';
import { watchIdle, jobWatcher } from '../idlewatch.js';

let root = null, scope = null, shell = null;
const S = { pid: null, d: null, job: null, table: null, tableDirty: false, playing: null };
let Q = createQueue(), poll = null, audio = null;

const { state: STATE_TEXT, job: JOB_STATE, reason: REASON_TEXT } = VOICE_LABELS;
const CODE_TEXT = { ...STAGE_CODES.longjob, ...STAGE_CODES.voice };
const codeText = (e) => (e?.body && typeof e.body === 'object' && CODE_TEXT[e.body.code]) || null;
const fail = (e, prefix = '') => { const t = codeText(e); if (t) toast((prefix ? prefix + ' ' : '') + t, 'error', 9000); else errorToast(e, prefix); };

const $ = (s) => root?.querySelector(s);
const P = () => `/api/projects/${encodeURIComponent(S.pid)}`;
const fmtMin = (sec) => (sec < 90 ? `${Math.max(1, Math.round(sec))} giây` : `${Math.round(sec / 60)} phút`);
const fmtClock = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;

// ---------------------------------------------------------------- loading
async function load() {
  S.d = await api.get(`${P()}/voice`);
  if (!S.tableDirty) S.table = Object.entries(S.d.pronounce || {}).map(([k, v]) => ({ k, v }));
  paint();
  const run = S.d.state === 'running' ? await api.get(`/api/projects/${S.pid}/longjobs?kind=voice`).catch(() => null) : null;
  const active = run?.items?.find((j) => ['queued', 'waiting', 'running'].includes(j.state));
  if (active) watch(active.id);
  else if (!S.job) {                                   // show how the last run ended, once
    const last = (await api.get(`/api/projects/${S.pid}/longjobs?kind=voice`).catch(() => null))?.items?.[0];
    if (last && ['error', 'interrupted'].includes(last.state) && S.d.state !== 'done') { S.job = last; paintJob(); }
  }
}

let seen = jobWatcher();
function watch(id) {
  seen.know(id);
  clearInterval(poll);
  const tick = async () => {
    let j;
    try { j = await api.get(`/api/longjobs/${id}`); } catch { return; }
    S.job = j; paintJob();
    if (!['queued', 'waiting', 'running'].includes(j.state)) {
      clearInterval(poll); poll = null;
      if (j.state === 'done') toast('Giọng đọc đã xong.', 'ok');
      else if (j.state === 'error' || j.state === 'interrupted') toast(CODE_TEXT[j.error_code] || jobErrorText(j).text, 'error', 9000);
      await load(); shell?.refreshPipeline();
      scope.timeout(() => shell?.refreshPipeline(), 1000);           // once more a moment later: the stepper must not keep saying "Đang chạy"
    }
  };
  poll = scope.interval(tick, 2000);
  tick();
}

// ---------------------------------------------------------------- actions
const generate = (body) => Q.run(async () => {
  try {
    const r = await api.post(`${P()}/voice/generate`, body);
    toast('Đã bắt đầu. Bạn có thể rời trang này, máy vẫn chạy.', 'ok');
    await load(); watch(r.job_id);
  } catch (e) {
    const b = e?.body;
    if (b?.code === 'voice_busy' && b.job_id) watch(b.job_id);
    fail(e);
  }
});
const cancel = async () => {
  if (!S.job) return;
  try { await api.post(`/api/longjobs/${S.job.id}/cancel`); toast('Đang hủy...', 'warn'); } catch (e) { fail(e); }
};
const saveSettings = (patch) => Q.run(async () => {
  try { S.d = await api.put(`${P()}/voice/settings`, patch); if (!('pronounce' in patch)) { /* keep unsaved table rows */ } else { S.tableDirty = false; S.table = Object.entries(S.d.pronounce || {}).map(([k, v]) => ({ k, v })); } paint(); shell?.refreshPipeline(); toast('Đã lưu.', 'ok', 1800); }
  catch (e) { fail(e); }
});
const savePronounce = () => {
  const table = {};
  for (const r of S.table) { const k = r.k.trim(), v = r.v.trim(); if (k && v) table[k] = v; }
  return saveSettings({ pronounce: table });
};

function stopAudio() { if (audio) { audio.pause(); audio = null; } S.playing = null; for (const b of root?.querySelectorAll('.vc-play') || []) b.textContent = '▶'; }
function playChunk(c, btn) {
  if (S.playing === c.id) { stopAudio(); return; }
  stopAudio();
  audio = new Audio(api.url(`${P()}/voice/chunks/${c.id}.wav`));
  S.playing = c.id; btn.textContent = '■';
  audio.onended = () => stopAudio();
  audio.onerror = () => { stopAudio(); toast('Không nghe được câu này.', 'warn'); };
  audio.play().catch(() => stopAudio());
}

// ---------------------------------------------------------------- painting
function paint() {
  const d = S.d; if (!root || !d) return;
  const run = d.state === 'running' || (S.job && ['queued', 'waiting', 'running'].includes(S.job.state));
  const none = !d.approved && d.state === 'none';
  const hold = !d.approved && d.state !== 'none';           // the narration is being edited: what exists stays, nothing new is read until it is approved again
  const top = $('#vc-top'); top.replaceChildren();
  top.append(h('span', { class: `vc-chip vc-${d.state}`, text: STATE_TEXT[d.state] || d.state }),
    h('span', { class: 'muted', text: d.detail }));
  const acts = $('#vc-acts'); acts.replaceChildren();
  const first = d.state === 'none' || !d.counts || d.counts.cached === 0;
  acts.append(...kids(
    h('button', { class: 'primary', text: first ? 'Tạo giọng đọc' : d.state === 'stale' ? 'Đọc lại phần đã đổi' : 'Tạo lại nếu thiếu', disabled: run || none || hold || !d.configured, title: !d.configured ? CODE_TEXT.voice_not_configured : none || hold ? 'Cần duyệt lời dẫn trước.' : '', onclick: () => generate({ scope: 'changed' }) }),
    run ? h('button', { text: 'Hủy', onclick: cancel }) : null,
    !run && !first ? h('button', { text: 'Đọc lại toàn bộ', title: 'Bỏ các câu đã đọc và đọc lại tất cả (rất lâu).', disabled: hold || !d.configured, onclick: async () => { if (await confirmDialog(`Đọc lại toàn bộ ${d.counts.total} câu? Việc này mất rất lâu (khoảng ${fmtMin((d.counts.total ? d.estimate.seconds : 0) || 3000)} trở lên).`, { ok: 'Đọc lại tất cả', danger: true })) generate({ scope: 'all' }); } }) : null));
  const info = $('#vc-info'); info.replaceChildren();
  if (!d.approved && d.state === 'none') info.append(h('div', { class: 'box warn', text: d.detail || 'Cần duyệt lời dẫn ở bước Kịch bản trước.' }));
  const why = (d.reasons || []).filter((r) => REASON_TEXT[r] && d.state !== 'none');
  const byReason = d.counts?.by_reason || {};
  const mixed = why.filter((r) => byReason[r]).length > 1;                       // several reasons at once: say how many sentences each one covers
  for (const r of why) info.append(h('div', { class: 'box warn', text: REASON_TEXT[r] + (mixed && byReason[r] ? ` (${byReason[r]} câu)` : '') }));
  if (d.counts && d.counts.missing > 0 && d.estimate) info.append(h('div', { class: 'muted', text: `Còn ${d.counts.missing}/${d.counts.total} câu chưa đọc: chia ${d.estimate.parts} phần, ước tính ${fmtMin(d.estimate.seconds)} máy chạy (máy chỉ chạy một việc nặng một lúc).` }));
  if (!d.configured) info.append(h('div', { class: 'box warn', text: CODE_TEXT.voice_not_configured }));
  if (d.timing?.quality === 'even') info.append(h('div', { class: 'box warn', text: 'Thời điểm từng từ được chia đều trong mỗi câu (chưa có máy đo từ). Chỉ chính xác ở đầu và cuối câu.' }));
  else if (d.timing?.quality === 'aligned' && d.timing.match_rate != null) info.append(h('div', { class: 'muted', text: `Thời điểm từ đã được đo, khớp ${(d.timing.match_rate * 100).toFixed(0)}% số từ.` }));
  paintJob(); paintMix(); paintSettings(); paintScript(); paintTable();
  paintNext();
}

function paintJob() {
  const box = $('#vc-job'); if (!box) return; box.replaceChildren();
  const j = S.job; if (!j) return;
  const live = ['queued', 'waiting', 'running'].includes(j.state);
  box.append(h('h3', { class: 'sh', text: live ? 'Đang chạy' : `Lần chạy gần nhất: ${JOB_STATE[j.state] || j.state}` }));
  const bar = (p) => h('div', { class: 'vc-bar' }, h('i', { style: { width: Math.round((p || 0) * 100) + '%' } }));
  if (live) box.append(bar(j.progress));
  for (const p of j.parts || []) box.append(h('div', { class: `vc-part vc-p-${p.state}` }, h('span', { text: p.title }), h('span', { class: 'muted', text: p.state === 'running' ? `${Math.round((p.progress || 0) * 100)}% ${p.note || ''}` : (JOB_STATE[p.state] || p.state) + (p.state === 'waiting' && p.note ? ` — ${p.note}` : '') })));
  if (j.state === 'error' || j.state === 'interrupted') box.append(h('div', { class: 'box err', text: CODE_TEXT[j.error_code] || jobErrorText(j).text }));
  if (j.result?.low_match) box.append(h('div', { class: 'box warn', text: 'Máy đo từ khớp ít với lời dẫn. Nghe lại vài câu để kiểm tra.' }));
  if (live) setStatus('đang tạo giọng đọc...'); else setStatus('');
}

function paintMix() {
  const box = $('#vc-mix'); box.replaceChildren();
  const m = S.d.mix; if (!m?.exists) return;
  box.append(h('h3', { class: 'sh', text: 'Nghe cả bài' }),
    h('audio', { controls: true, preload: 'none', src: api.url(`${P()}/voice/mix?v=${encodeURIComponent(S.d.mix.bytes)}`), style: { width: '100%' } }),
    h('div', { class: 'muted', text: [m.duration ? `Dài ${fmtClock(m.duration)}` : '', m.loudness?.i != null ? `âm lượng ${m.loudness.i.toFixed(1)} LUFS` : '', m.loudness?.tp != null ? `đỉnh ${m.loudness.tp.toFixed(1)} dB` : ''].filter(Boolean).join(' · ') }));
  if (S.d.state === 'stale') box.append(h('div', { class: 'muted', text: 'Bản này là bản cũ, chưa khớp lời dẫn hiện tại.' }));
}

function paintSettings() {
  const box = $('#vc-set'); box.replaceChildren();
  const s = S.d.settings; if (!s) return;
  const [lo, hi] = S.d.defaults.tempo_range;
  const tempo = h('input', { type: 'number', min: lo, max: hi, step: 0.01, value: s.tempo });
  const pad = h('input', { type: 'checkbox', checked: s.pad });
  box.append(h('h3', { class: 'sh', text: 'Tốc độ và nhạc nền' }),
    h('div', { class: 'fieldrow' }, h('label', { text: `Tốc độ đọc (${lo} đến ${hi})` }), tempo),
    h('div', { class: 'fieldrow' }, pad, h('label', { text: 'Nhạc nền nhẹ dưới giọng đọc' })),
    h('div', { class: 'muted', text: 'Đổi tốc độ hoặc nhạc nền không phải đọc lại, chỉ ghép lại (vài phút).' }),
    h('button', { text: 'Lưu cài đặt', onclick: () => saveSettings({ tempo: Number(tempo.value), pad: pad.checked }) }));
}

function paintScript() {
  const box = $('#vc-script'); box.replaceChildren();
  const d = S.d; if (!d.chunks.length) return;
  box.append(h('h3', { class: 'sh', text: 'Lời dẫn theo chương' }));
  const titles = Object.fromEntries(d.chapters.map((c) => [c.id, c.title || c.id]));
  let cur = null, lastBeat = null;
  for (const c of d.chunks) {
    if (c.chapter !== cur) { cur = c.chapter; lastBeat = null; box.append(h('div', { class: 'vc-ch', text: `${titles[cur] || cur}` })); }
    const btn = h('button', { class: 'vc-play', text: S.playing === c.id ? '■' : '▶', title: 'Nghe câu này', disabled: !c.cached, onclick: (ev) => playChunk(c, ev.currentTarget) });
    const tags = [!c.cached ? h('span', { class: 'vc-tag warn', text: 'chưa đọc' }) : c.new && d.state !== 'none' ? h('span', { class: 'vc-tag', text: 'đã đổi' }) : null,
      c.sec ? h('span', { class: 'muted vc-sec', text: c.sec.toFixed(1) + ' giây' }) : null];
    const again = h('button', { class: 'vc-again', text: 'Đọc lại câu này', title: 'Đọc câu này bằng một lần đọc khác', disabled: S.d.state === 'running' || !d.configured || !d.approved, onclick: () => generate({ scope: [c.id], reseed: [c.id] }) });
    box.append(h('div', { class: 'vc-row' + (c.beat !== lastBeat ? ' vc-newbeat' : ''), title: c.spoken !== c.text ? `Đọc là: ${c.spoken}` : '' }, btn, h('div', { class: 'vc-text' }, h('span', { text: c.text }), c.spoken !== c.text ? h('div', { class: 'vc-spoken muted', text: 'đọc là: ' + c.spoken }) : null), h('div', { class: 'vc-side' }, tags, again)));
    lastBeat = c.beat;
  }
}

function paintTable() {
  const box = $('#vc-table'); box.replaceChildren();
  if (!S.d.approved && !S.d.chunks.length) return;
  box.append(h('h3', { class: 'sh', text: 'Bảng phát âm' }),
    h('div', { class: 'muted', text: 'Chữ viết trong lời dẫn và cách máy đọc. Ví dụ: "Arnolfini" đọc là "Ar-nol-phi-ni". Số, năm, thế kỷ đã được đọc tự động.' }));
  const rows = h('div', { class: 'vc-rows' });
  const paintRows = () => {
    rows.replaceChildren(...S.table.map((r, i) => h('div', { class: 'fieldrow' },
      h('input', { type: 'text', value: r.k, placeholder: 'chữ viết', oninput: (e) => { r.k = e.target.value; S.tableDirty = true; } }),
      h('span', { text: '→' }),
      h('input', { type: 'text', value: r.v, placeholder: 'cách đọc', oninput: (e) => { r.v = e.target.value; S.tableDirty = true; } }),
      h('button', { text: 'Xóa', onclick: () => { S.table.splice(i, 1); S.tableDirty = true; paintRows(); } }))));
  };
  paintRows();
  box.append(rows, h('div', { class: 'fieldrow' }, h('button', { text: 'Thêm dòng', onclick: () => { S.table.push({ k: '', v: '' }); S.tableDirty = true; paintRows(); } }), h('button', { class: 'primary', text: 'Lưu bảng phát âm', onclick: savePronounce })),
    h('div', { class: 'muted', text: 'Sau khi lưu, chỉ những câu có chữ này mới phải đọc lại.' }));
}

function paintNext() {
  const box = $('#vc-next'); box.replaceChildren();
  if (S.d.state !== 'done') return;
  const pl = shell?.pipeline; const next = pl ? nextOpenable(pl.steps, 'voice') : null;
  if (next) box.append(h('button', { class: 'primary', text: `Tiếp tục: ${next.label}`, onclick: () => shell.go(projectHash(S.pid, next.id)) }));
}

// ---------------------------------------------------------------- mount
export async function mount(host, ctx) {
  scope = ctx.scope; shell = ctx.shell;
  Object.assign(S, { pid: ctx.pipeline.project, d: null, job: null, table: null, tableDirty: false, playing: null });
  Q = createQueue({ onBusy: (b) => setStatus(b ? 'đang xử lý...' : '') });
  poll = null; audio = null; seen = jobWatcher();
  root = h('div', { class: 'vc-root v-vc' },
    h('div', { class: 'vc-head' }, h('h1', { text: '3. Giọng đọc' }), h('div', { id: 'vc-top', class: 'vc-top' }), h('div', { id: 'vc-acts', class: 'vc-acts' })),
    h('div', { class: 'vc-body' },
      h('div', { class: 'vc-col' }, h('div', { id: 'vc-info' }), h('div', { id: 'vc-job' }), h('div', { id: 'vc-mix' }), h('div', { id: 'vc-next', class: 'vc-next' }), h('div', { id: 'vc-set' }), h('div', { id: 'vc-table' })),
      h('div', { class: 'vc-col vc-wide', id: 'vc-script' })));
  host.append(root);
  scope.add(() => stopAudio());
  try { await load(); } catch (e) { fail(e, 'Không mở được giọng đọc.'); }
  // a job started in another tab or window shows up here within a few seconds
  watchIdle(scope, { root: () => root, idle: () => !poll && !['queued', 'waiting', 'running'].includes(S.job?.state),
    check: async () => {                                  // one cheap GET: the list of voice jobs
      if (seen(await api.get(`/api/projects/${S.pid}/longjobs?kind=voice`))) { await load(); shell?.refreshPipeline(); }     // a job runs, or ran and ended, elsewhere
    } });
  window.__voice = { S };
  return {
    isDirty: () => S.tableDirty,
    save: () => savePronounce(),
    dirtyMessage: () => 'Bảng phát âm có chỗ sửa chưa lưu.',
    pipelineChanged: () => { load().catch(() => {}); },
    unmount() { window.__voice = null; clearInterval(poll); root = null; },
  };
}
