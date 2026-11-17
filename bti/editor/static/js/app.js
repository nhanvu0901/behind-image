// The app shell: a persistent frame (name, project picker, project title, stepper, health, messages) and ONE view at a time.
// The views live in ./views/*.js and export mount(host, ctx) -> { isDirty?, save?, pipelineChanged?, unmount? }.
import { api, setViewSignal, setNetworkHook } from './api.js';
import { MOCK, SHOW_ALL } from './config.js';
import { h, toast, errorToast, errorInto, setStatus, closeAllModals, ask, modal } from './util.js';
import { describeError } from './errmsg.js';
import { createScope } from './lifecycle.js';
import { parseHash, projectHash, legacyTarget } from './router.js';
import { renderStepper, landing } from './stepper.js';
import { setNavigator } from './nav.js';
import { stageLabel } from './labels.js';

const $ = (s) => document.querySelector(s);
const S = { hash: null, route: null, pid: null, pipeline: null, projects: [], view: null, scope: null, seq: 0, skipGuard: false, guarding: false };

const VIEWS = {
  home: () => import('./views/home.js'),
  library: () => import('./views/library.js'),
  artwork: () => import('./views/artwork.js'),
  script: () => import('./views/script.js'),
  info: () => import('./views/placeholder.js'),
  storyboard: () => import('./views/storyboard.js'),
  voice: () => import('./views/voice.js'),
  picks: () => import('./views/picks.js'),
  export: () => import('./views/export.js'),
};
const here = () => location.pathname + location.search;

// ---------------------------------------------------------------- what the views may ask of the shell
export const shell = {
  go: (hash) => go(hash),
  get pid() { return S.pid; },
  get pipeline() { return S.pipeline; },
  get projects() { return S.projects; },
  refreshPipeline,
  refreshProjects,
  deleteProject,
};

// ---------------------------------------------------------------- navigation
async function go(hash) {
  if (S.guarding) return false;
  if (hash === (location.hash || '#/') || (hash === '#/' && !location.hash)) {
    if (!(await guardLeave())) return false;
    await navigate(parseHash(location.hash));      // same address: reload the view
    return true;
  }
  if (!(await guardLeave())) return false;
  S.skipGuard = true;
  setTimeout(() => { S.skipGuard = false; }, 1500);
  location.hash = hash;
  return true;
}

/** Leaving a view with unsaved work asks first. Resolves true when it is fine to leave. */
async function guardLeave() {
  const v = S.view;
  if (!v?.isDirty?.()) return true;
  S.guarding = true;
  try {
    const c = await ask({
      title: 'Có thay đổi chưa lưu',
      message: (v.dirtyMessage?.() || 'Bước này có thay đổi chưa lưu.') + '\n\nNếu rời đi mà không lưu, thay đổi sẽ mất.',
      cancelValue: 'stay',
      buttons: [{ text: 'Ở lại', value: 'stay' }, { text: 'Bỏ thay đổi và rời đi', value: 'discard', cls: 'danger' }, { text: 'Lưu rồi rời đi', value: 'save', cls: 'primary' }],
    });
    if (c === 'save') { await v.save?.(); return !v.isDirty?.(); }
    return c === 'discard';
  } finally { S.guarding = false; }
}

async function onHash() {
  const hash = location.hash || '#/';
  if (hash === S.hash) return;
  const skip = S.skipGuard; S.skipGuard = false;
  if (!skip && !(await guardLeave())) { history.replaceState(null, '', here() + (S.hash || '#/')); return; }
  await navigate(parseHash(hash));
}

function disposeView() {
  const v = S.view, sc = S.scope;
  S.view = null; S.scope = null;
  try { v?.unmount?.(); } catch (e) { console.error('unmount', e); }
  sc?.dispose();
  setViewSignal(null);
  closeAllModals();
  setStatus('');
  $('#view').replaceChildren();
}

const msgView = (text, ...kids) => $('#view').replaceChildren(h('div', { class: 'view-msg' }, text, ...kids));

async function navigate(route) {
  const seq = ++S.seq;
  disposeView();
  S.hash = location.hash || '#/';
  S.route = route;
  if (MOCK && (route.name === 'library' || (route.name === 'project' && route.step === 'script'))) {
    toast('Chế độ mock chỉ có trang Dựng hình.', 'warn');
    S.skipGuard = true; location.hash = '#/'; return;
  }
  let pipeline = null;
  S.pid = null; S.pipeline = null;
  try {
    if (route.name === 'project') {
      if (!S.projects.some((x) => x.id === route.pid)) await refreshProjects();   // e.g. a project that was just created
      pipeline = await api.pipeline(route.pid);
      if (seq !== S.seq) return;
      S.pid = route.pid; S.pipeline = pipeline;
      if (!route.step) {
        route = { ...route, step: landing(pipeline) };
        S.route = route;
        history.replaceState(null, '', here() + projectHash(route.pid, route.step));
        S.hash = location.hash;
      }
    } else if (route.name === 'library') {
      pipeline = await api.pipelineTemplate();
      if (seq !== S.seq) return;
      S.pipeline = pipeline;
    }
  } catch (e) {
    if (seq !== S.seq) return;
    S.route = { name: 'notfound' };
    renderFrame();
    msgView(e.status === 404 ? 'Không có dự án này.' : 'Không mở được dự án: ' + describeError(e).text, h('div', null, h('a', { class: 'lnk', href: '#/', text: 'Về danh sách dự án' })));
    return;
  }
  renderFrame();
  if (route.name === 'notfound') return msgView('Địa chỉ này không có trong ứng dụng.', h('div', null, h('a', { class: 'lnk', href: '#/', text: 'Về danh sách dự án' })));
  await mountView(route, pipeline, seq);
}

function pickView(route, pipeline) {
  if (route.name === 'home') return { mod: 'home' };
  if (route.name === 'library') return { mod: 'library' };
  const step = pipeline.steps.find((s) => s.id === route.step);
  if (step.state === 'no_data') return { mod: 'info', kind: 'nodata', step };
  if (step.state === 'locked') return { mod: 'info', kind: 'locked', step };
  return { mod: { artwork: 'artwork', script: 'script', voice: 'voice', picks: 'picks', edit: 'storyboard', export: 'export' }[step.id], step };
}

async function mountView(route, pipeline, seq) {
  const host = $('#view');
  const pick = pickView(route, pipeline);
  const scope = createScope();
  S.scope = scope;
  setViewSignal(scope.signal);
  host.replaceChildren(h('div', { class: 'view-msg', text: 'Đang tải...' }));
  let inst = null;
  try {
    const mod = await VIEWS[pick.mod]();
    if (seq !== S.seq) return;
    host.replaceChildren();
    S.view = inst = (await mod.mount(host, { shell, scope, route, pipeline, step: pick.step, kind: pick.kind })) || {};
    if (seq !== S.seq) { inst.unmount?.(); }
  } catch (e) {
    if (seq !== S.seq) return;
    console.error(e);
    host.replaceChildren(h('div', { class: 'view-msg' }, 'Lỗi khi mở trang: ' + describeError(e).text));
    errorToast(e, 'Lỗi khi mở trang: ');
  }
}

// ---------------------------------------------------------------- frame
function renderPicker() {
  const sel = $('#project-pick');
  const list = S.projects.filter((x) => SHOW_ALL || !/^(lab_|demo_)/.test(x.id) || x.id === S.pid);
  sel.replaceChildren(h('option', { value: '', text: list.length ? '- Chọn dự án -' : '(chưa có dự án)' }),
    ...list.map((x) => h('option', { value: x.id, disabled: !!x.data_error, text: x.data_error ? `${x.id} (dự án hỏng)` : `${x.title || x.id} (${x.id})` })));
  sel.value = S.pid && list.some((x) => x.id === S.pid) ? S.pid : '';
}

function renderFrame() {
  const r = S.route, p = S.pipeline;
  renderPicker();
  // title and painting of the current project
  const info = $('#frame-project');
  if (S.pid && p) {
    const pt = p.painting;
    info.replaceChildren(h('span', { class: 'pt', text: p.title }),
      pt?.title ? h('span', { class: 'pp', text: [pt.title, [pt.artist, pt.year].filter(Boolean).join(', ')].filter(Boolean).join(' · ') }) : null,
      h('span', { class: 'tag', text: stageLabel(p.stage), title: 'Giai đoạn của dự án' }));
  } else if (r?.name === 'library') info.replaceChildren(h('span', { class: 'pp', text: 'Video mới: chọn một tác phẩm' }));
  else info.replaceChildren();
  // stepper
  const st = $('#stepper');
  if (r?.name === 'project' || r?.name === 'library') {
    st.hidden = false;
    renderStepper(st, p, r.name === 'library' ? 'artwork' : r.step, onStep);
  } else st.hidden = true;
}

function onStep(step, v) {
  if (!v.openable) { toast(`${step.label}: ${step.reason}`, 'warn', 7000); return; }
  if (!S.pid) { go(step.id === 'artwork' ? '#/library' : '#/'); return; }
  if (S.route?.name === 'project' && S.route.step === step.id) return;   // already here
  go(projectHash(S.pid, step.id));
}

async function refreshPipeline() {
  if (!S.pid) return null;
  const pid = S.pid;
  try {
    const p = await api.pipeline(pid);
    if (S.pid !== pid) return null;
    S.pipeline = p;
    renderFrame();
    S.view?.pipelineChanged?.(p);
    return p;
  } catch { return S.pipeline; }
}

async function refreshProjects() {
  try { S.projects = await api.projects({ signal: null }); } catch (e) { errorToast(e, 'Không tải được danh sách dự án: '); }
  if (S.route) renderPicker();                     // the picker in the bar always shows what the server has (a project just deleted or created)
  return S.projects;
}

/** Delete a project after the owner types its id. Resolves true when it was deleted. */
function deleteProject(p) {
  return new Promise((resolve) => {
    let done = false;
    const fin = (v) => { if (!done) { done = true; resolve(v); } };
    const input = h('input', { type: 'text', spellcheck: false, autocomplete: 'off', placeholder: p.id, style: { width: '100%' } });
    const err = h('div', { class: 'hint err' });
    const btn = h('button', { class: 'danger', text: 'Xóa vĩnh viễn', disabled: true, onclick: async () => {
      btn.disabled = true;
      try {
        await api.deleteProject(p.id, input.value.trim());
        S.projects = S.projects.filter((x) => x.id !== p.id); renderPicker();     // gone from the picker at once, before the list is fetched again
        fin(true); m.close(); toast(`Đã xóa dự án ${p.id}`, 'ok');
      } catch (e) { errorInto(err, e); btn.disabled = false; }
    } });
    input.addEventListener('input', () => { btn.disabled = input.value.trim() !== p.id; });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !btn.disabled) btn.click(); });
    const m = modal({ title: 'Xóa dự án', onClose: () => fin(false),
      body: h('div', { class: 'body', style: { width: '480px' } },
        h('p', null, 'Xóa cả thư mục ', h('b', { text: p.title || p.id }), ' (', h('span', { class: 'mono', text: p.id }), '): kịch bản, giọng đọc, storyboard, hình đã nhập. Không khôi phục được.'),
        h('label', { class: 'lb', text: `Gõ đúng mã dự án "${p.id}" để xác nhận` }), input, err),
      footer: h('footer', null, h('button', { text: 'Hủy', onclick: () => m.close() }), btn) });
    setTimeout(() => input.focus(), 30);
  });
}

// ---------------------------------------------------------------- health badge
async function loadHealth() {
  const b = $('#health');
  try {
    const hl = await api.health();
    const stub = hl.engine === 'stub' || hl.media === 'stub';
    b.textContent = `engine: ${hl.engine} | media: ${hl.media}${MOCK ? ' | MOCK' : ''}`;
    b.className = 'badge ' + (stub ? 'stub' : 'ok');
    b.title = stub ? 'Đang chạy bản stub: khung hình/hình ảnh chưa phải thật' : 'Engine và media thật';
  } catch { b.textContent = 'backend không phản hồi'; b.className = 'badge bad'; }
}

// ---------------------------------------------------------------- boot
async function boot() {
  const t = legacyTarget(location);                       // /?project=x  ->  /#/project/x/edit
  if (t) history.replaceState(null, '', location.pathname + t.search + t.hash);
  document.title = (MOCK ? '[MOCK] ' : '') + document.title;
  setNavigator(go);
  $('#btn-new').onclick = () => go('#/library');
  $('#project-pick').onchange = (e) => { const v = e.target.value; if (!v) go('#/'); else go(projectHash(v)); setTimeout(() => { $('#project-pick').value = S.pid || ''; }, 0); };
  document.addEventListener('click', (e) => {            // every in-app link goes through go(), so unsaved work is asked about
    const a = e.target.closest?.('a[href^="#/"]');
    if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || a.target) return;
    e.preventDefault(); go(a.getAttribute('href'));
  });
  window.addEventListener('hashchange', onHash);
  let lastSync = 0;                                      // another tab may have created or deleted a project: refresh the picker when this tab is looked at again
  window.addEventListener('focus', () => { if (Date.now() - lastSync > 5000 && !S.guarding) { lastSync = Date.now(); refreshProjects(); } });
  window.addEventListener('beforeunload', (e) => { if (S.view?.isDirty?.()) { e.preventDefault(); e.returnValue = ''; } });
  setNetworkHook((state, url) => { if (state === 'up' || !/\/api\/health/.test(url)) loadHealth(); });   // the badges follow the server at once, not 30 s later
  setInterval(loadHealth, 30000);
  await Promise.all([loadHealth(), refreshProjects()]);
  await navigate(parseHash(location.hash));
}

window.__app = { S, shell };
boot().catch((e) => { document.body.prepend(h('pre', { class: 'pre', text: 'Lỗi khởi động: ' + describeError(e).text })); });
