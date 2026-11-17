// The storyboard draft panel (design 7): what is ready, the model, "Dựng bản nháp", progress, cancel, then open the proposal.
// Mounted by the storyboard view into a container element it owns:
//   const unmount = mountDraftPanel(container, { pid, scope, onProposal: (proposalId) => openProposals(onApplied, proposalId) });
// The panel is self contained: it talks to /api/projects/{pid}/draft and /api/longjobs/{id} through the generic verbs of api.js.
// The Vietnamese words are in TEXT below; errors go through errmsg.js (describeError via errorToast / errorInto).
import { api } from './api.js';
import { h, errorToast, errorInto, confirmDialog } from './util.js';
import { jobErrorText } from './errmsg.js';

const TEXT = {
  title: 'Bản nháp storyboard',
  intro: 'Agent đọc lời dẫn đã có giọng đọc và các hình bạn đã chọn, rồi dựng sẵn từng cảnh. Kết quả là một đề xuất: bạn xem và chấp nhận từng thay đổi, không có gì tự đổi.',
  voice: 'Giọng đọc',
  picks: 'Chọn hình',
  model: 'Mô hình',
  modelDefault: 'Mặc định',
  start: 'Dựng bản nháp',
  startAuto: 'Dựng tự động (không dùng agent)',
  cancel: 'Dừng',
  open: 'Mở đề xuất',
  running: 'Đang dựng bản nháp...',
  waiting: 'Đang chờ...',
  notReady: 'Chưa đủ dữ liệu: xong bước Giọng đọc và Chọn hình trước.',
  confirmReplace: 'Dự án đã có storyboard. Bản nháp mới chỉ là một đề xuất, không ghi đè gì cho đến khi bạn chấp nhận. Dựng bản nháp?',
  stale: 'Bản nháp này dựng từ giọng đọc hoặc danh sách hình đã đổi.',
  last: 'Lần dựng gần nhất',
  tampered: 'Lần dựng bị bỏ vì agent đã đổi tệp ngoài thư mục làm việc.',
  doneNote: 'Xong. Có %n cảnh.',
  issues: '%n mục còn dở, xem trong đề xuất.',
  loadingModels: 'Đang tải danh sách mô hình...',
  noModels: 'Chưa lấy được danh sách mô hình (agy chưa đăng nhập?). Dùng mô hình mặc định.',
  partState: { queued: 'chờ', waiting: 'chờ máy', running: 'đang chạy', done: 'xong', error: 'lỗi', cancelled: 'đã dừng', interrupted: 'bị ngắt' },
};
const ACTIVE = new Set(['queued', 'waiting', 'running']);

export function mountDraftPanel(container, { pid, scope = null, onProposal = null } = {}) {
  let dead = false, timer = null, jobId = null, info = null, models = null, modelsErr = null, job = null;
  const root = h('div', { class: 'draft-panel' });
  container.replaceChildren(root);

  const poll = () => { clearTimeout(timer); if (!dead) timer = setTimeout(tick, 1500); };
  scope?.add?.(() => unmount());

  async function load() {
    try { info = await api.get(`/api/projects/${encodeURIComponent(pid)}/draft`); } catch (e) { if (!dead) errorInto(root, e, 'Không đọc được trạng thái bản nháp: '); return; }
    if (dead) return;
    jobId = info.job_id || jobId;
    render();
    if (jobId && !job) tick();
  }
  async function loadModels() {
    try { const r = await api.get(`/api/projects/${encodeURIComponent(pid)}/draft/models`); models = r.models || []; modelsErr = r.error || null; if (r.default && info) info.default_model = r.default; }
    catch { models = []; modelsErr = TEXT.noModels; }
    if (!dead) render();
  }
  async function tick() {
    if (dead || !jobId) return;
    try { job = await api.get(`/api/longjobs/${encodeURIComponent(jobId)}`); } catch (e) { if (!dead) poll(); return; }
    if (dead) return;
    if (!ACTIVE.has(job.state)) {
      const finished = job; jobId = null;
      await load();
      job = finished;
      render();
      return;
    }
    render();
    poll();
  }
  async function start(provider) {
    if (info?.state?.proposal && provider && !(await confirmDialog(TEXT.confirmReplace, { ok: TEXT.start }))) return;
    const body = { provider };
    const sel = root.querySelector('select.draft-model');
    if (provider === 'agy' && sel && sel.value) body.model = sel.value;
    try {
      const r = await api.post(`/api/projects/${encodeURIComponent(pid)}/draft/start`, body);
      jobId = r.job_id; job = null; render(); tick();
    } catch (e) { errorToast(e, 'Không bắt đầu được: '); }
  }
  async function cancel() {
    if (!jobId) return;
    try { await api.post(`/api/longjobs/${encodeURIComponent(jobId)}/cancel`, {}); tick(); } catch (e) { errorToast(e, 'Không dừng được: '); }
  }

  function readyRow(label, r) {
    return h('div', { class: 'row' }, h('span', { class: 'chip ' + (r.ok ? 'ok' : 'partial'), text: r.ok ? 'xong' : 'chưa' }), h('b', { text: ' ' + label + ': ' }), r.detail);
  }
  function render() {
    if (dead || !info) return;
    const running = !!(jobId && job && ACTIVE.has(job.state)) || (!!jobId && !job);
    const kids = [h('h4', { text: TEXT.title }), h('div', { class: 'hint', text: TEXT.intro }),
      readyRow(TEXT.voice, info.ready.voice), readyRow(TEXT.picks, info.ready.picks)];
    const st = info.state || {};
    if (st.state === 'stale') kids.push(h('div', { class: 'banner warn', text: TEXT.stale }));
    if (running) {
      const parts = (job?.parts || []).map((p) => h('div', { class: 'hint' }, `${p.title}: ${TEXT.partState[p.state] || p.state}`, p.note ? ' - ' + p.note : ''));
      kids.push(h('div', { class: 'row' }, h('b', { text: TEXT.running }), h('progress', { max: 1, value: job?.progress ?? 0 }), h('button', { class: 'small', text: TEXT.cancel, onclick: cancel })), ...parts);
    } else {
      const sel = h('select', { class: 'draft-model' }, h('option', { value: '', text: `${TEXT.modelDefault} (${info.default_model})` }),
        ...(models || []).map((m) => h('option', { value: m.slug, text: m.label ? `${m.label} (${m.slug})` : m.slug })));
      kids.push(h('div', { class: 'row' }, h('label', { text: TEXT.model + ': ' }), sel),
        models === null ? h('div', { class: 'hint', text: TEXT.loadingModels }) : (modelsErr && !(models || []).length ? h('div', { class: 'hint', text: TEXT.noModels }) : null),
        h('div', { class: 'row' }, h('button', { class: 'primary', text: TEXT.start, disabled: !info.ready.ok, onclick: () => start('agy') }),
          h('button', { class: 'small', text: TEXT.startAuto, disabled: !info.ready.ok, onclick: () => start('auto') })),
        info.ready.ok ? null : h('div', { class: 'hint warn', text: TEXT.notReady }));
      const lr = info.last_run;
      if (job && job.state === 'error') kids.push(h('div', { class: 'banner warn', text: jobErrorText(job).text }));
      if (lr && lr.status === 'tampered') kids.push(h('div', { class: 'banner warn', text: TEXT.tampered }));
      if (st.proposal) {
        const note = lr && lr.status === 'done' ? [TEXT.doneNote.replace('%n', lr.n_shots), (lr.errors_left || lr.incomplete) ? ' ' + TEXT.issues.replace('%n', (lr.errors_left || 0) + (lr.incomplete || 0)) : ''].join('') : st.detail;
        kids.push(h('div', { class: 'row' }, h('span', { class: 'hint', text: note }), onProposal ? h('button', { class: 'primary small', text: TEXT.open, onclick: () => onProposal(st.proposal) }) : null));
      }
    }
    root.replaceChildren(...kids.filter(Boolean));
  }
  function unmount() { dead = true; clearTimeout(timer); root.remove(); }

  load().then(loadModels);
  return unmount;
}
